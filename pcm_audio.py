"""Mélange des sons de Bifurk dans un flux PCM continu partagé (NumPy).

Un seul QAudioSink consomme Mixer pour toute une SoundBank. Même sans voix active,
le flux produit du silence : la sortie Windows reste ouverte et ne perd pas
l'attaque des sons courts. Les fichiers mono 16 bits deviennent un mélange stéréo
44,1 kHz ; un WAV à 22,05 kHz est doublé au chargement. Les boucles d'ambiance sont
livrées en OGG Vorbis : QAudioDecoder (moteur FFmpeg de Qt Multimedia) les décode
une fois, en mémoire, en PCM mono 16 bits à 22,05 kHz, doublé comme un WAV. Le
rééchantillonneur de FFmpeg perdrait quelques échantillons en fin de fichier : le
doublement garde le compte exact, la boucle reste sans couture.

Le mélange travaille par blocs NumPy : chaque voix ajoute une tranche de ses
échantillons multipliée par son niveau (volume × fondu × canal × gain général),
puis la somme est saturée en 16 bits signé et dupliquée gauche / droite.

- Fondus : fade_in() / fade_out() font varier le gain d'une voix en rampe linéaire,
  échantillon par échantillon ; un fondu de sortie arrête la voix à zéro.
- Canaux : Mixer.channels règle séparément « effects » et « ambient » (curseurs de
  Réglages), Mixer.gain baisse tout (fondu de fermeture).
- Chargement différé : defer_source() mémorise le fichier sans le décoder (état
  Unloaded) ; load() le décode à la première demande, release() libère la mémoire.

readData est un rappel du système audio : ne pas y accéder aux widgets ni y faire
d'E/S disque. Le propriétaire Qt doit arrêter le sink avant de détruire le mixer.
Aucun tirage aléatoire ici : activer le son ne doit pas changer une partie."""
import wave

import numpy as np
from PySide6.QtCore import QIODevice, QObject, QUrl, Signal


def _as_samples(samples):
    """Vue int16 des échantillons d'une voix, sans copie pour un tableau ou un array('h')."""
    if isinstance(samples, np.ndarray):
        return samples
    try:
        return np.frombuffer(samples, dtype=np.int16)
    except TypeError:
        return np.asarray(samples, dtype=np.int16)


class Mixer(QIODevice):
    """Périphérique séquentiel en lecture : silence continu ou somme des voix actives."""
    RATE = 44100

    def __init__(self, parent=None):
        """Ouvrir le QIODevice en lecture et conserver les voix pour toute la durée de la banque."""
        super().__init__(parent)
        self.voices = []
        self.gain = 1.0  # Gain général : le fondu de fermeture le baisse jusqu'à 0.
        self.channels = {'effects': 1.0, 'ambient': 1.0}  # Curseurs de Réglages.
        self.duck = self.duck_target = 1.0  # Baisse de l'ambiance pendant un combat.
        self.open(QIODevice.ReadOnly)

    def isSequential(self):
        """Indiquer à Qt que le flux audio ne possède ni position de fichier ni fin prévisible."""
        return True

    def bytesAvailable(self):
        """Annoncer des données même au repos pour garder la sortie audio alimentée."""
        # Entre deux actions, le mélangeur fournit du silence : la sortie reste éveillée.
        return 65536 + super().bytesAvailable()

    def readData(self, maximum):
        """Produire au plus maximum octets en trames stéréo de quatre octets.

        Additionner les voix mono avec leur niveau, recommencer les boucles Infinite,
        arrêter les autres à leur fin, puis saturer en 16 bits signé avant duplication
        gauche / droite. Sans voix, retourner du silence de même durée."""
        frames = maximum // 4  # Stereo signed 16-bit PCM.
        if self.duck != self.duck_target and frames > 0:
            # Rapprochement progressif (≈ 0,3 s) : pas de saut de volume audible.
            step = min(1.0, frames / (self.RATE * .3))
            self.duck += (self.duck_target - self.duck) * step
            if abs(self.duck - self.duck_target) < .01:
                self.duck = self.duck_target
        active = [voice for voice in self.voices if voice.isPlaying()]
        if not active or frames <= 0:
            return bytes(max(frames, 0) * 4)
        mixed = np.zeros(frames, dtype=np.float64)
        for voice in active:
            self._mix_voice(voice, mixed, frames)
        # Additionner d'abord, saturer ensuite : un dépassement ne doit pas
        # reboucler en entier signé et produire un claquement numérique.
        np.clip(mixed, -32768, 32767, out=mixed)
        stereo = np.repeat(mixed.astype(np.int16), 2).astype('<i2')
        return stereo.tobytes()

    def _mix_voice(self, voice, mixed, frames):
        samples = _as_samples(voice.samples)
        length = len(samples)
        if length == 0:
            voice.stop()
            return
        channel = getattr(voice, 'channel', 'effects')
        level = voice.volume * self.gain * self.channels.get(channel, 1.0)
        if channel == 'ambient':
            level *= self.duck
        envelope = voice.envelope(frames) if hasattr(voice, 'envelope') else None
        filled = 0
        while filled < frames:
            if voice.position >= length:
                if voice.loops == -2:
                    voice.position = 0
                else:
                    voice.stop()
                    break
            take = min(frames - filled, length - voice.position)
            chunk = samples[voice.position:voice.position + take] * level
            if envelope is not None:
                chunk = chunk * envelope[filled:filled + take]
            # Tronquer chaque voix vers zéro comme l'ancien mélange entier.
            mixed[filled:filled + take] += np.trunc(chunk)
            voice.position += take
            filled += take
        if hasattr(voice, 'envelope'):
            voice.end_of_block()

    def writeData(self, data):
        """Refuser l’écriture : le mixer est exclusivement une source pour QAudioSink."""
        return -1


class PcmEffect(QObject):
    """Adaptateur de lecture partageant le mixer et le sink de sa SoundBank parente."""
    statusChanged = Signal()
    playingChanged = Signal()
    Unloaded, Loading, Ready, Error, Infinite = 0, 1, 2, 3, -2

    def __init__(self, parent):
        """Créer la sortie partagée seulement pour le premier effet, puis enregistrer la voix."""
        super().__init__(parent)
        self.samples = np.zeros(0, dtype=np.int16)
        self.position = 0
        self.volume = 1.0
        self.loops = 1
        self.channel = 'effects'
        self.gain = 1.0          # Gain de fondu courant.
        self._fade_target = 1.0
        self._fade_step = 0.0    # Variation de gain par trame ; 0 hors fondu.
        self._stop_after_fade = False
        self._url = None
        self._playing = False
        self._status = self.Loading
        if not hasattr(parent, '_pcm_mixer'):
            from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
            mixer = Mixer(parent)
            fmt = QAudioFormat()
            fmt.setSampleRate(Mixer.RATE)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.Int16)
            device = QMediaDevices.defaultAudioOutput()
            parent.logger.info('PCM output=%s format_supported=%s',
                               device.description(), device.isFormatSupported(fmt))
            sink = QAudioSink(device, fmt, parent)
            sink.setBufferSize(8192)
            # Un slot sans argument évite le bogue de conversion de QAudio::State dans PySide :
            # l'état est relu plutôt que transmis par le signal.
            sink.stateChanged.connect(
                lambda: parent.logger.info('PCM state=%s error=%s', sink.state(), sink.error()))
            parent._pcm_mixer = mixer
            parent._pcm_sink = sink
            # Arrêter les rappels natifs avant la destruction du mélangeur.
            parent.destroyed.connect(sink.stop)
            sink.start(mixer)
        parent._pcm_mixer.voices.append(self)

    # --- chargement ----------------------------------------------------------
    def defer_source(self, url):
        """Mémoriser le fichier sans le décoder : état Unloaded jusqu'à load()."""
        self._url = QUrl(url)
        self._status = self.Unloaded

    def load(self):
        """Décoder le fichier mémorisé par defer_source (ou rechargé après release)."""
        if self._status == self.Unloaded and self._url is not None:
            self.setSource(self._url)

    def release(self):
        """Libérer les échantillons d'une voix arrêtée ; elle redevient Unloaded."""
        if self._playing or self._url is None or self._status != self.Ready:
            return False
        self.samples = np.zeros(0, dtype=np.int16)
        self._status = self.Unloaded
        return True

    def setSource(self, url):
        """Charger et valider un WAV mono PCM 16 bits puis émettre statusChanged.

        Accepter 44,1 kHz ou 22,05 kHz ; doubler les échantillons du second format.
        Un autre format (OGG des ambiances) est décodé en arrière-plan : l'effet reste
        Loading jusqu'à la fin, et SoundBank rejoue alors une demande en attente.
        Une erreur journalisée passe l’effet à Error sans empêcher l’ouverture du jeu."""
        self._url = QUrl(url)
        self._status = self.Loading
        if not url.toLocalFile().lower().endswith('.wav'):
            self._decode(url)
            return
        try:
            with wave.open(url.toLocalFile(), 'rb') as source:
                if (source.getnchannels() != 1 or source.getsampwidth() != 2
                        or source.getframerate() not in (22050, Mixer.RATE)):
                    raise ValueError('Unsupported PCM asset')
                samples = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2')
                if source.getframerate() == 22050:
                    # Conversion simple à rapport entier 2 : chaque échantillon
                    # dure deux trames dans le flux commun à 44100 Hz.
                    samples = np.repeat(samples, 2)
                if not len(samples):
                    raise ValueError('Empty PCM asset')
                self.samples = samples.astype(np.int16)
            self._status = self.Ready
        except (OSError, EOFError, wave.Error, ValueError) as exc:
            self.parent().logger.error('PCM asset error: %s', exc)
            self._status = self.Error
        self.statusChanged.emit()

    def _decode(self, url):
        """Décoder un fichier compressé en PCM mono 16 bits (22,05 kHz doublés, ou 44,1 kHz)."""
        from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat
        wanted = QAudioFormat()
        wanted.setSampleRate(Mixer.RATE // 2)
        wanted.setChannelCount(1)
        wanted.setSampleFormat(QAudioFormat.Int16)
        # Gardé comme enfant (pas de deleteLater) : il ne sert qu'une fois par fichier.
        decoder = self._decoder = QAudioDecoder(self)
        decoder.setAudioFormat(wanted)
        chunks = []
        state = {'done': False, 'rate': None}

        def finish(error=None):
            if state['done']:
                return
            state['done'] = True
            decoder.stop()
            samples = np.frombuffer(b''.join(chunks), dtype=np.int16)  # Int16 Qt : boutisme natif.
            if state['rate'] == Mixer.RATE // 2:
                samples = np.repeat(samples, 2)
            if error is None and not len(samples):
                error = 'Empty PCM asset'
            if error is None:
                self.samples = samples
                self._status = self.Ready
            else:
                self.parent().logger.error('PCM asset error: %s (%s)', error, url.toLocalFile())
                self._status = self.Error
            self.statusChanged.emit()

        def ready():
            buffer = decoder.read()
            if not buffer.isValid() or state['done']:
                return
            fmt = buffer.format()
            if (fmt.channelCount(), fmt.sampleFormat()) != (1, QAudioFormat.Int16) or \
                    fmt.sampleRate() not in (Mixer.RATE // 2, Mixer.RATE) or \
                    state['rate'] not in (None, fmt.sampleRate()):
                finish('Unsupported decoded format')
                return
            state['rate'] = fmt.sampleRate()
            chunks.append(bytes(buffer.constData()))

        decoder.bufferReady.connect(ready)
        decoder.finished.connect(finish)
        decoder.error.connect(lambda *_args: finish(decoder.errorString() or 'Decoder error'))
        decoder.setSource(url)
        decoder.start()

    # --- état et réglages --------------------------------------------------------
    def status(self):
        """Retourner l’état de disponibilité attendu par SoundBank."""
        return self._status

    def setVolume(self, volume):
        """Mémoriser le gain de cette voix ; la saturation est appliquée au mélange final."""
        self.volume = volume

    def setLoopCount(self, loops):
        """Mémoriser la valeur de boucle ; le mixer reconnaît Infinite pour l’ambiance continue."""
        self.loops = loops

    def isPlaying(self):
        """Indiquer si cette voix participe au prochain mélange."""
        return self._playing

    # --- lecture et fondus -------------------------------------------------------
    def play(self):
        """Repartir du début si le fichier est prêt, y compris pour un effet déjà actif."""
        if self._status != self.Ready:
            return
        self.position = 0
        self.gain, self._fade_target, self._fade_step = 1.0, 1.0, 0.0
        self._stop_after_fade = False
        if not self._playing:
            self._playing = True
            self.playingChanged.emit()

    def fade_in(self, ms):
        """Démarrer depuis le silence et monter jusqu'au volume normal en ms millisecondes."""
        if self._status != self.Ready:
            return
        if self._playing and not self._stop_after_fade:
            return  # Déjà audible : ne pas repartir du début.
        if not self._playing:
            self.play()
            self.gain = 0.0
        self._ramp(1.0, ms, stop=False)

    def fade_out(self, ms):
        """Descendre jusqu'au silence en ms millisecondes, puis arrêter la voix."""
        if not self._playing:
            return
        if ms <= 0:
            self.stop()
            return
        self._ramp(0.0, ms, stop=True)

    def _ramp(self, target, ms, *, stop):
        frames = max(1, int(Mixer.RATE * ms / 1000))
        self._fade_target = target
        self._fade_step = (target - self.gain) / frames
        self._stop_after_fade = stop
        if self._fade_step == 0:
            self.end_of_block()

    def envelope(self, frames):
        """Gain par trame du prochain bloc (rampe de fondu), ou None hors fondu."""
        if self._fade_step == 0:
            return None if self.gain == 1.0 else np.full(frames, self.gain)
        ramp = self.gain + self._fade_step * np.arange(1, frames + 1)
        if self._fade_step > 0:
            np.minimum(ramp, self._fade_target, out=ramp)
        else:
            np.maximum(ramp, self._fade_target, out=ramp)
        self.gain = float(ramp[-1])
        return ramp

    def end_of_block(self):
        """Clore un fondu atteint : gain figé, voix arrêtée après un fondu de sortie."""
        if self._fade_step and self.gain == self._fade_target:
            self._fade_step = 0.0
            if self._stop_after_fade:
                self._stop_after_fade = False
                self.stop()
        elif not self._fade_step and self._stop_after_fade and self.gain == 0.0:
            self._stop_after_fade = False
            self.stop()

    def is_fading_out(self):
        return self._playing and self._stop_after_fade

    def stop(self):
        """Retirer la voix du mélange et émettre playingChanged uniquement si elle jouait."""
        if self._playing:
            self._playing = False
            self._fade_step = 0.0
            self._stop_after_fade = False
            self.gain = 1.0
            self.playingChanged.emit()
