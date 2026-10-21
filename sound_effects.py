"""Preloaded local effects; independent of the game's random stream."""
from PySide6.QtCore import QObject, QUrl
import logging
from logging.handlers import RotatingFileHandler

EFFECT_LABELS = {
    'page': 'Page tournée', 'dice': 'Dés', 'swords': 'Combat',
    'item': 'Objet récupéré', 'coins': 'Pièces', 'key': 'Serrure',
    'potion': 'Potion', 'hit': 'Blessure', 'victory': 'Victoire', 'death': 'Défaite',
}


class SoundBank(QObject):
    def __init__(self, folder, enabled=True, parent=None, ambient_enabled=False,
                 diagnostic_path=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f'bifurk.audio.{id(self)}')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if diagnostic_path is not None:
            try:
                diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(diagnostic_path, maxBytes=128_000,
                                              backupCount=1, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                self.logger.addHandler(handler)
                self.destroyed.connect(lambda: self._close_log())
            except OSError:
                pass  # Diagnostics must never prevent the game from opening.
        self.folder = folder
        self.enabled = enabled
        self.ambient_enabled = ambient_enabled
        self.effects = {}
        self.pending = set()
        self.logger.info('session effects=%s ambient=%s', enabled, ambient_enabled)
        self.preload()
        if ambient_enabled:
            self.set_ambient_enabled(True)

    def _close_log(self):
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()

    def _playing_changed(self, name):
        effect = self.effects[name]
        self.logger.info('playing %s=%s', name, effect.isPlaying())

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
            effect.playingChanged.connect(lambda n=name: self._playing_changed(n))
            effect.setSource(QUrl.fromLocalFile(str(path)))

    def _allowed(self, name):
        return self.ambient_enabled if name == 'ambient' else self.enabled

    def _ready(self, name):
        backend = self._backend()
        effect = self.effects.get(name)
        if backend is None or effect is None:
            return
        self.logger.info('status %s=%s', name, effect.status())
        if effect.status() == backend.Ready and name in self.pending:
            self.pending.discard(name)
            if self._allowed(name):
                effect.play()
        elif effect.status() == backend.Error:
            self.pending.discard(name)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.logger.info('effects enabled=%s', self.enabled)
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
        self.logger.info('request %s allowed=%s', name, self._allowed(name))
        if not self._allowed(name):
            return
        self.preload()
        effect = self.effects.get(name)
        backend = self._backend()
        if effect is None or backend is None:
            self.logger.info('unavailable %s', name)
            return
        self.logger.info('dispatch %s status=%s', name, effect.status())
        if effect.status() == backend.Ready:
            effect.play()
        elif effect.status() != backend.Error:
            self.pending.add(name)
