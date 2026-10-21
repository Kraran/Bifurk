"""One continuous PCM stream for short, overlapping game effects."""
import array
import sys
import wave

from PySide6.QtCore import QIODevice, QObject, Signal


class Mixer(QIODevice):
    RATE = 44100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.voices = []
        self.open(QIODevice.ReadOnly)

    def isSequential(self):
        return True

    def bytesAvailable(self):
        # Silence is available even between actions: the output stays awake.
        return 65536 + super().bytesAvailable()

    def readData(self, maximum):
        frames = maximum // 4  # Stereo signed 16-bit PCM.
        active = [voice for voice in self.voices if voice.isPlaying()]
        if not active:
            return bytes(frames * 4)
        mixed = [0] * frames
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
            sample = max(-32768, min(32767, sample))
            stereo.extend((sample, sample))
        if sys.byteorder != 'little':
            stereo.byteswap()
        return stereo.tobytes()

    def writeData(self, data):
        return -1


class PcmEffect(QObject):
    """SoundBank adapter; all effects share their parent's audio sink."""
    statusChanged = Signal()
    playingChanged = Signal()
    Ready, Loading, Error, Infinite = 2, 1, 3, -2

    def __init__(self, parent):
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
        try:
            with wave.open(url.toLocalFile(), 'rb') as source:
                if (source.getnchannels() != 1 or source.getsampwidth() != 2
                        or source.getframerate() not in (22050, Mixer.RATE)):
                    raise ValueError('Unsupported PCM asset')
                samples = array.array('h', source.readframes(source.getnframes()))
                if sys.byteorder != 'little':
                    samples.byteswap()
                if source.getframerate() == 22050:
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
        return self._status

    def setVolume(self, volume):
        self.volume = volume

    def setLoopCount(self, loops):
        self.loops = loops

    def isPlaying(self):
        return self._playing

    def play(self):
        if self._status != self.Ready:
            return
        self.position = 0
        if not self._playing:
            self._playing = True
            self.playingChanged.emit()

    def stop(self):
        if self._playing:
            self._playing = False
            self.playingChanged.emit()
