"""Lecture des sons courts par un flux PCM continu partagé.

Un seul QAudioSink consomme Mixer pour toute une SoundBank. Même sans voix active,
le flux produit du silence : la sortie Windows reste ouverte et ne perd pas
l'attaque des sons courts. Les fichiers mono 16 bits deviennent un mélange stéréo
44,1 kHz ; les ambiances 22,05 kHz sont doublées à la lecture du fichier.

readData est un rappel du système audio : ne pas y accéder aux widgets ni y faire
d'E/S disque. Le propriétaire Qt doit arrêter le sink avant de détruire le mixer.
Aucun tirage aléatoire ici : activer le son ne doit pas changer une partie."""
import array
import sys
import wave

from PySide6.QtCore import QIODevice, QObject, Signal


class Mixer(QIODevice):
    """Périphérique séquentiel en lecture : silence continu ou somme des voix actives."""
    RATE = 44100

    def __init__(self, parent=None):
        """Ouvrir le QIODevice en lecture et conserver les voix pour toute la durée de la banque."""
        super().__init__(parent)
        self.voices = []
        self.open(QIODevice.ReadOnly)

    def isSequential(self):
        """Indiquer à Qt que le flux audio ne possède ni position de fichier ni fin prévisible."""
        return True

    def bytesAvailable(self):
        # Silence is available even between actions: the output stays awake.
        """Annoncer des données même au repos pour garder la sortie audio alimentée."""
        return 65536 + super().bytesAvailable()

    def readData(self, maximum):
        """Produire au plus maximum octets en trames stéréo de quatre octets.

        Additionner les voix mono avec leur volume, recommencer les boucles Infinite,
        arrêter les autres à leur fin, puis saturer en 16 bits signé avant duplication
        gauche / droite. Sans voix, retourner du silence de même durée."""
        frames = maximum // 4  # Stereo signed 16-bit PCM.
        active = [voice for voice in self.voices if voice.isPlaying()]
        if not active:
            return bytes(frames * 4)
        mixed = [0] * frames
        # Les voix possèdent leurs propres curseurs : redémarrer un dé ne coupe
        # ni l'ambiance ni les autres effets déjà en cours.
        for voice in active:
            samples = voice.samples
            for i in range(frames):
                if voice.position == len(samples):
                    if voice.loops == -2:
                        voice.position = 0
                    else:
                        voice.stop()
                        break
                mixed[i] += int(samples[voice.position] * voice.volume)
                voice.position += 1
        stereo = array.array('h')
        for sample in mixed:
            # Additionner d'abord, saturer ensuite : un dépassement ne doit pas
            # reboucler en entier signé et produire un claquement numérique.
            sample = max(-32768, min(32767, sample))
            stereo.extend((sample, sample))
        if sys.byteorder != 'little':
            stereo.byteswap()
        return stereo.tobytes()

    def writeData(self, data):
        """Refuser l’écriture : le mixer est exclusivement une source pour QAudioSink."""
        return -1


class PcmEffect(QObject):
    """Adaptateur de lecture partageant le mixer et le sink de sa SoundBank parente."""
    statusChanged = Signal()
    playingChanged = Signal()
    Ready, Loading, Error, Infinite = 2, 1, 3, -2

    def __init__(self, parent):
        """Créer la sortie partagée seulement pour le premier effet, puis enregistrer la voix."""
        super().__init__(parent)
        self.samples = array.array('h')
        self.position = 0
        self.volume = 1.0
        self.loops = 1
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
            # A zero-argument slot avoids PySide's QAudio::State conversion bug.
            # Query the state instead of forwarding the enum through the slot.
            sink.stateChanged.connect(
                lambda: parent.logger.info('PCM state=%s error=%s', sink.state(), sink.error()))
            parent._pcm_mixer = mixer
            parent._pcm_sink = sink
            # Stop native callbacks before the mixer is destroyed.
            parent.destroyed.connect(sink.stop)
            sink.start(mixer)
        parent._pcm_mixer.voices.append(self)

    def setSource(self, url):
        """Charger et valider un WAV mono PCM 16 bits puis émettre statusChanged.

        Accepter 44,1 kHz ou 22,05 kHz ; doubler les échantillons du second format.
        Une erreur journalisée passe l’effet à Error sans empêcher l’ouverture du jeu."""
        try:
            with wave.open(url.toLocalFile(), 'rb') as source:
                if (source.getnchannels() != 1 or source.getsampwidth() != 2
                        or source.getframerate() not in (22050, Mixer.RATE)):
                    raise ValueError('Unsupported PCM asset')
                samples = array.array('h', source.readframes(source.getnframes()))
                if sys.byteorder != 'little':
                    samples.byteswap()
                if source.getframerate() == 22050:
                    # Conversion simple à rapport entier 2 : chaque échantillon
                    # dure deux trames dans le flux commun à 44100 Hz.
                    samples = array.array('h', (s for s in samples for _ in range(2)))
                if not samples:
                    raise ValueError('Empty PCM asset')
                self.samples = samples
            self._status = self.Ready
        except (OSError, EOFError, wave.Error, ValueError) as exc:
            self.parent().logger.error('PCM asset error: %s', exc)
            self._status = self.Error
        self.statusChanged.emit()

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

    def play(self):
        """Repartir du début si le fichier est prêt, y compris pour un effet déjà actif."""
        if self._status != self.Ready:
            return
        self.position = 0
        if not self._playing:
            self._playing = True
            self.playingChanged.emit()

    def stop(self):
        """Retirer la voix du mélange et émettre playingChanged uniquement si elle jouait."""
        if self._playing:
            self._playing = False
            self.playingChanged.emit()
