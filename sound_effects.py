"""Banque des sons locaux, réglages de lecture et diagnostics audio.

Les effets et l'ambiance ont des interrupteurs indépendants ; la boucle
d'ambiance dépend du livre ouvert (caverne par défaut, ville pour la Cité,
forêt pour la Forêt). Une demande peut
attendre la disponibilité de son fichier ; couper le son supprime les demandes
concernées pour éviter un déclenchement tardif. Avec le backend PCM, les ambiances
ne sont décodées qu'à leur première demande, au plus MAX_DECODED_AMBIENCES restent en
mémoire, et elles entrent et sortent en fondu (AMBIENT_FADE_MS). Les curseurs de
Réglages règlent séparément le volume des effets et celui de l'ambiance. Le backend PCM est désactivé avec
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
# Une seule boucle d’ambiance à la fois, choisie par le module du livre ouvert ;
# la caverne reste celle du Sorcier et de l’écran sans livre.
AMBIENT_TRACKS = {'cite-1983': 'ambient_cite', 'foret-1983': 'ambient_foret'}
AMBIENT_LABELS = {'ambient': 'caverne', 'ambient_cite': 'ville', 'ambient_foret': 'forêt'}
# Extensions cherchées, dans cet ordre, pour chaque son de la banque.
SOUND_SUFFIXES = ('.wav', '.ogg')
AMBIENT_FADE_MS = 2500       # Fondu enchaîné entre deux ambiances.
MAX_DECODED_AMBIENCES = 3    # Ambiances gardées décodées en mémoire (≈ 4 Mo chacune).


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
        self.ambient = 'ambient'
        self.effects = {}
        self.pending = set()
        self.levels = {'effects': 1.0, 'ambient': 1.0}
        self._ambient_recent = []  # Ambiances décodées, de la plus ancienne à la plus récente.
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
        """Créer chaque effet au plus une fois et connecter ses signaux avant de charger le fichier.

        Les paramètres par défaut des lambdas figent le nom de chaque effet : éviter
        la capture tardive de la variable de boucle."""
        backend = self._backend()
        if backend is None:
            return
        for name in [*EFFECT_LABELS, *BOOK_SOUNDS.values(), *AMBIENT_LABELS]:
            # Effets courts en WAV (attaque immédiate) ; boucles d'ambiance en OGG Vorbis.
            path = next((candidate for candidate in (self.folder / f'{name}{suffix}'
                                                     for suffix in SOUND_SUFFIXES)
                         if candidate.is_file()), None)
            if name in self.effects or path is None:
                continue
            effect = backend(self)
            self.effects[name] = effect
            effect.setVolume(.10 if name in AMBIENT_LABELS else .80 if name in BOOK_SOUNDS.values()
                             else .72 if name == 'swords' else .50)
            if name in AMBIENT_LABELS:
                # Les PySide6 récents exposent Loop comme une énumération ; le setter attend un entier.
                effect.setLoopCount(getattr(backend.Infinite, 'value', backend.Infinite))
            if hasattr(effect, 'channel'):
                effect.channel = 'ambient' if name in AMBIENT_LABELS else 'effects'
            effect.statusChanged.connect(lambda n=name: self._ready(n))
            effect.playingChanged.connect(lambda n=name: self._playing_changed(n))
            if name in AMBIENT_LABELS and hasattr(effect, 'defer_source'):
                effect.defer_source(QUrl.fromLocalFile(str(path)))  # Décodée à la demande.
            else:
                effect.setSource(QUrl.fromLocalFile(str(path)))
        self._apply_levels()

    def _apply_levels(self):
        mixer = getattr(self, '_pcm_mixer', None)
        if mixer is not None:
            mixer.channels.update(self.levels)

    def set_effects_volume(self, percent):
        """Curseur « Volume des effets » : 100 % garde les niveaux d'origine."""
        self.levels['effects'] = max(0.0, float(percent) / 100)
        self._apply_levels()

    def set_ambient_volume(self, percent):
        """Curseur « Volume de l'ambiance » : 100 % garde le niveau d'origine."""
        self.levels['ambient'] = max(0.0, float(percent) / 100)
        self._apply_levels()

    def _start(self, name, effect):
        """Lancer un son prêt : les ambiances entrent en fondu, les effets d'un coup."""
        if name in AMBIENT_LABELS and hasattr(effect, 'fade_in'):
            effect.fade_in(AMBIENT_FADE_MS)
            self._remember_ambient(name)
        else:
            effect.play()

    def _stop_ambient(self, name, fade=True):
        """Arrêter une ambiance en fondu (ou net : fermeture, backend sans fondu)."""
        effect = self.effects.get(name)
        if effect is None:
            return
        if fade and hasattr(effect, 'fade_out'):
            effect.fade_out(AMBIENT_FADE_MS)
        else:
            effect.stop()

    def _remember_ambient(self, name):
        """Garder en mémoire les dernières ambiances, libérer les plus anciennes arrêtées."""
        if name in self._ambient_recent:
            self._ambient_recent.remove(name)
        self._ambient_recent.append(name)
        for old in list(self._ambient_recent[:-MAX_DECODED_AMBIENCES]):
            effect = self.effects.get(old)
            if old != self.ambient and effect is not None and hasattr(effect, 'release') \
                    and not effect.isPlaying() and effect.release():
                self._ambient_recent.remove(old)
                self.logger.info('released %s', old)

    def _allowed(self, name):
        """Vérifier le réglage propre à l’ambiance du livre courant ou celui des effets ponctuels."""
        if name in AMBIENT_LABELS:
            return self.ambient_enabled and name == self.ambient
        return self.enabled

    def ambient_label(self):
        """Nommer la boucle du livre courant dans le réglage d’ambiance."""
        return AMBIENT_LABELS[self.ambient]

    def set_ambient_track(self, engine):
        """Remplacer la boucle selon le module ouvert, sous le même interrupteur d’ambiance."""
        name = AMBIENT_TRACKS.get(engine, 'ambient')
        if name == self.ambient:
            return
        self.logger.info('ambient track=%s', name)
        self.pending.discard(self.ambient)
        self._stop_ambient(self.ambient)  # Fondu enchaîné avec la nouvelle boucle.
        self.ambient = name
        if self.ambient_enabled:
            self.play(name)

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
                self._start(name, effect)
        elif effect.status() == backend.Error:
            self.pending.discard(name)

    def set_enabled(self, enabled):
        """Activer les effets ou arrêter leurs voix et demandes en attente sans couper l’ambiance."""
        self.enabled = bool(enabled)
        self.logger.info('effects enabled=%s', self.enabled)
        if not self.enabled:
            self.pending.intersection_update(AMBIENT_LABELS)
            for name, effect in self.effects.items():
                if name not in AMBIENT_LABELS:
                    effect.stop()
        else:
            self.preload()

    def set_ambient_enabled(self, enabled, *, fade=True):
        """Démarrer ou interrompre la boucle d’ambiance indépendamment des effets."""
        self.ambient_enabled = bool(enabled)
        if enabled:
            self.play(self.ambient)
        else:
            self.pending.discard(self.ambient)
            self._stop_ambient(self.ambient, fade)

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
            self._start(name, effect)
        elif effect.status() != backend.Error:
            self.pending.add(name)
            if effect.status() == getattr(backend, 'Unloaded', None):
                effect.load()  # Décodage à la demande ; _ready lancera le son.
