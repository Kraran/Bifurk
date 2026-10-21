"""Short local effects. Audio is lazy and never changes the game's random stream."""
from PySide6.QtCore import QObject, QUrl


class SoundBank(QObject):
    def __init__(self, folder, enabled=True, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.enabled = enabled
        self.effects = {}

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            for effect in self.effects.values():
                effect.stop()

    def play(self, name):
        if not self.enabled:
            return
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() in ('offscreen', 'minimal'):
            return
        path = self.folder / f'{name}.wav'
        if not path.is_file():
            return
        try:
            from PySide6.QtMultimedia import QSoundEffect
            if name not in self.effects:
                effect = QSoundEffect(self)
                effect.setVolume(.45)
                effect.setSource(QUrl.fromLocalFile(str(path)))
                self.effects[name] = effect
            self.effects[name].play()
        except (ImportError, RuntimeError):
            pass  # Reading and playing remain available without an audio device.
