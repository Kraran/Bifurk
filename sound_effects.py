"""Banque des sons locaux, réglages de lecture et diagnostics audio.

Les effets et l'ambiance ont des interrupteurs indépendants. Une demande peut
attendre la disponibilité de son fichier ; couper le son supprime les demandes
concernées pour éviter un déclenchement tardif. Le backend PCM est désactivé avec
les plateformes Qt offscreen/minimal ; les tests injectent leurs propres doublures.
Le journal est borné et son indisponibilité ne doit jamais empêcher de jouer."""
from PySide6.QtCore import QObject, QUrl
import logging
from logging.handlers import RotatingFileHandler

EFFECT_LABELS = {
    'page': 'Page tournée', 'dice': 'Dés', 'swords': 'Combat',
    'item': 'Objet récupéré', 'coins': 'Pièces', 'key': 'Serrure',
    'potion': 'Potion', 'hit': 'Blessure', 'victory': 'Victoire', 'death': 'Défaite',
}
BOOK_SOUNDS = {'sorcier-1982': 'book_sorcier', 'foret-1983': 'book_foret', 'cite-1983': 'book_cite'}


class SoundBank(QObject):
    """Service Qt central de préchargement et lecture, indépendant de l’état de partie."""
    def __init__(self, folder, enabled=True, parent=None, ambient_enabled=False,
                 diagnostic_path=None):
        """Préparer le journal borné, les réglages et les effets ; démarrer l’ambiance si demandée."""
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
                pass  # Le journal de diagnostic ne doit jamais empêcher le jeu de s'ouvrir.
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
        """Détacher et fermer les handlers à la destruction pour libérer le fichier Windows."""
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()

    def _playing_changed(self, name):
        """Tracer le changement d’activité de l’effet pour le diagnostic local."""
        effect = self.effects[name]
        self.logger.info('playing %s=%s', name, effect.isPlaying())

    def _backend(self):
        """Choisir le backend PCM hors tests sans écran ; retourner None s’il est indisponible."""
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() in ('offscreen', 'minimal'):
            return None
        try:
            from pcm_audio import PcmEffect
            return PcmEffect
        except ImportError:
            return None

    def preload(self):
        """Créer chaque effet au plus une fois et connecter ses signaux avant de charger le WAV.

        Les paramètres par défaut des lambdas figent le nom de chaque effet : éviter
        la capture tardive de la variable de boucle."""
        backend = self._backend()
        if backend is None:
            return
        for name in [*EFFECT_LABELS, *BOOK_SOUNDS.values(), 'ambient']:
            path = self.folder / f'{name}.wav'
            if name in self.effects or not path.is_file():
                continue
            effect = backend(self)
            self.effects[name] = effect
            effect.setVolume(.10 if name == 'ambient' else .80 if name in BOOK_SOUNDS.values()
                             else .72 if name == 'swords' else .50)
            if name == 'ambient':
                # Les PySide6 récents exposent Loop comme une énumération ; le setter attend un entier.
                effect.setLoopCount(getattr(backend.Infinite, 'value', backend.Infinite))
            effect.statusChanged.connect(lambda n=name: self._ready(n))
            effect.playingChanged.connect(lambda n=name: self._playing_changed(n))
            effect.setSource(QUrl.fromLocalFile(str(path)))

    def _allowed(self, name):
        """Vérifier le réglage propre à l’ambiance ou celui des effets ponctuels."""
        return self.ambient_enabled if name == 'ambient' else self.enabled

    def play_book_intro(self, engine):
        """Une seule annonce à la fois, y compris si une demande attend le chargement."""
        for name in BOOK_SOUNDS.values():
            self.pending.discard(name)
            if name in self.effects:
                self.effects[name].stop()
        name = BOOK_SOUNDS.get(engine)
        if name:
            self.play(name)

    def _ready(self, name):
        """Rejouer une demande en attente seulement si le fichier est prêt et toujours autorisé."""
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
        """Activer les effets ou arrêter leurs voix et demandes en attente sans couper l’ambiance."""
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
        """Démarrer ou interrompre la boucle d’ambiance indépendamment des effets."""
        self.ambient_enabled = bool(enabled)
        if enabled:
            self.play('ambient')
        else:
            self.pending.discard('ambient')
            if 'ambient' in self.effects:
                self.effects['ambient'].stop()

    def play(self, name):
        """Déclencher un effet prêt ou mémoriser sa demande pendant le chargement.

        Un asset absent ou en erreur est seulement journalisé ; aucun jet aléatoire
        ni décision de jeu ne dépend du succès de la lecture."""
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
