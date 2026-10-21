"""Preloaded local effects; independent of the game's random stream."""
from PySide6.QtCore import QObject, QUrl

EFFECT_LABELS = {
    'page': 'Page tournée', 'dice': 'Dés', 'swords': 'Combat',
    'item': 'Objet récupéré', 'coins': 'Pièces', 'key': 'Serrure',
    'potion': 'Potion', 'hit': 'Blessure', 'victory': 'Victoire', 'death': 'Défaite',
}


class SoundBank(QObject):
    def __init__(self, folder, enabled=True, parent=None, ambient_enabled=False):
        super().__init__(parent)
        self.folder = folder
        self.enabled = enabled
        self.ambient_enabled = ambient_enabled
        self.effects = {}
        self.pending = set()
        self.preload()
        if ambient_enabled:
            self.set_ambient_enabled(True)

    def _backend(self):
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() in ('offscreen', 'minimal'):
            return None
        try:
            from PySide6.QtMultimedia import QSoundEffect
            return QSoundEffect
        except ImportError:
            return None

    def preload(self):
        backend = self._backend()
        if backend is None:
            return
        for name in [*EFFECT_LABELS, 'ambient']:
            path = self.folder / f'{name}.wav'
            if name in self.effects or not path.is_file():
                continue
            effect = backend(self)
            self.effects[name] = effect
            effect.setVolume(.10 if name == 'ambient' else .72 if name == 'swords' else .50)
            if name == 'ambient':
                # Recent PySide6 exposes Loop as an Enum, while the setter takes int.
                effect.setLoopCount(getattr(backend.Infinite, 'value', backend.Infinite))
            effect.statusChanged.connect(lambda n=name: self._ready(n))
            effect.setSource(QUrl.fromLocalFile(str(path)))

    def _allowed(self, name):
        return self.ambient_enabled if name == 'ambient' else self.enabled

    def _ready(self, name):
        backend = self._backend()
        effect = self.effects.get(name)
        if backend is None or effect is None:
            return
        if effect.status() == backend.Ready and name in self.pending:
            self.pending.discard(name)
            if self._allowed(name):
                effect.play()
        elif effect.status() == backend.Error:
            self.pending.discard(name)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.pending.intersection_update({'ambient'})
            for name, effect in self.effects.items():
                if name != 'ambient':
                    effect.stop()
        else:
            self.preload()

    def set_ambient_enabled(self, enabled):
        self.ambient_enabled = bool(enabled)
        if enabled:
            self.play('ambient')
        else:
            self.pending.discard('ambient')
            if 'ambient' in self.effects:
                self.effects['ambient'].stop()

    def play(self, name):
        if not self._allowed(name):
            return
        self.preload()
        effect = self.effects.get(name)
        backend = self._backend()
        if effect is None or backend is None:
            return
        if effect.status() == backend.Ready:
            effect.play()
        elif effect.status() != backend.Error:
            self.pending.add(name)
