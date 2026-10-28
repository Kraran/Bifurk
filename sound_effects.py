"""Banque des sons locaux, réglages de lecture et diagnostics audio.

Les effets et l'ambiance ont des interrupteurs indépendants ; la boucle
d'ambiance dépend du livre ouvert (caverne par défaut, ville pour la Cité,
forêt pour la Forêt), ou de la scène en cours. Une demande peut
attendre la disponibilité de son fichier ; couper le son supprime les demandes
concernées pour éviter un déclenchement tardif. Avec le backend PCM, les ambiances
ne sont décodées qu'à leur première demande, au plus MAX_DECODED_AMBIENCES restent en
mémoire, et elles entrent et sortent en fondu (AMBIENT_FADE_MS). Les curseurs de
Réglages règlent séparément le volume des effets et celui de l'ambiance. Le backend PCM est désactivé avec
les plateformes Qt offscreen/minimal ; les tests injectent leurs propres doublures.
Le journal est borné et son indisponibilité ne doit jamais empêcher de jouer.

Variantes : « page_2.wav », « page_3.wav »… complètent « page.wav ». Chaque lecture en
tire une, sans répéter la précédente, avec un léger écart de volume, par un
générateur propre à la banque : les dés et le hasard de la partie n'en dépendent pas.
Pendant un combat, duck_ambient() baisse l'ambiance en douceur.

Scènes (SCENES) : une scène remplace la boucle du livre par la sienne, en fondu
enchaîné, et peut jouer de temps à autre un son ponctuel (goutte, hibou…) choisi par
le même générateur privé, à un intervalle tiré dans sa fourchette « every ». Les
sons ponctuels suivent l'interrupteur et le curseur de l'ambiance, pas ceux des
effets. set_scene(None) revient à la boucle du livre."""
from PySide6.QtCore import QObject, QTimer, QUrl
import logging
import random
import re
from logging.handlers import RotatingFileHandler

EFFECT_LABELS = {
    'page': 'Page tournée', 'dice': 'Dés', 'swords': 'Combat',
    'item': 'Objet récupéré', 'coins': 'Pièces', 'key': 'Serrure',
    'potion': 'Potion', 'hit': 'Blessure', 'victory': 'Victoire', 'death': 'Défaite',
    'door': 'Porte', 'flee': 'Fuite', 'meal': 'Repas', 'magic': 'Magie',
    'growl': 'Bête', 'growl_giant': 'Ogre ou géant', 'growl_shade': 'Spectre',
    'growl_slime': 'Créature visqueuse',
}
MAX_VARIANTS = 9
VOLUMES = {'swords': .72, 'growl': .55, 'growl_giant': .55, 'growl_shade': .55, 'growl_slime': .55}
AMBIENT_DUCK = .45           # Niveau de l'ambiance pendant un combat.

# Cri de l'adversaire à l'ouverture d'un combat, d'après son nom.
CREATURE_SOUNDS = (
    (r'ogre|géant|troll|minotaure|cyclope|golem|colosse', 'growl_giant'),
    (r'spectre|fantôme|vampire|goule|zombie|squelette|mort|ombre|banshee|âme|liche|momie',
     'growl_shade'),
    (r'vase|gelée|limace|ver|sangsue|slime|blob|boue', 'growl_slime'),
)


def creature_sound(name):
    """Effet de cri d'un adversaire : bête par défaut, sinon géant, spectre ou créature visqueuse."""
    lowered = str(name).casefold()
    for pattern, effect in CREATURE_SOUNDS:
        if re.search(pattern, lowered):
            return effect
    return 'growl'
BOOK_SOUNDS = {'sorcier-1982': 'book_sorcier', 'foret-1983': 'book_foret', 'cite-1983': 'book_cite'}
# Une seule boucle d’ambiance à la fois, choisie par le module du livre ouvert ;
# la caverne reste celle du Sorcier et de l’écran sans livre.
AMBIENT_TRACKS = {'cite-1983': 'ambient_cite', 'foret-1983': 'ambient_foret'}
AMBIENT_LABELS = {'ambient': 'caverne', 'ambient_cite': 'ville', 'ambient_foret': 'forêt'}
# Extensions cherchées, dans cet ordre, pour chaque son de la banque.
SOUND_SUFFIXES = ('.wav', '.ogg')
# Scènes partagées entre les livres : boucle de fond (fichier sans extension) et,
# facultativement, sons ponctuels joués au hasard toutes les « every » secondes.
SCENES = {
    'caverne': {'label': 'caverne', 'loop': 'ambient', 'spots': 'spot_goutte', 'every': (8, 18)},
    'souterrain': {'label': 'souterrain humide', 'loop': 'scene_souterrain',
                   'spots': 'spot_goutte', 'every': (4, 10)},
    'crypte': {'label': 'crypte', 'loop': 'scene_crypte', 'spots': 'spot_goutte', 'every': (15, 32)},
    'riviere': {'label': 'rivière', 'loop': 'scene_riviere'},
    'marais': {'label': 'marais', 'loop': 'scene_marais', 'spots': 'spot_grenouille', 'every': (6, 16)},
    'foret': {'label': 'forêt', 'loop': 'ambient_foret'},
    'foret_nuit': {'label': 'forêt la nuit', 'loop': 'scene_foret_nuit',
                   'spots': 'spot_hibou', 'every': (12, 30)},
    'vent': {'label': 'lande venteuse', 'loop': 'scene_vent'},
    'rue': {'label': 'rue de la ville', 'loop': 'ambient_cite'},
    'marche': {'label': 'marché', 'loop': 'scene_marche'},
    'port': {'label': 'port', 'loop': 'scene_port'},
    'taverne': {'label': 'taverne', 'loop': 'scene_taverne'},
    'foyer': {'label': 'intérieur au coin du feu', 'loop': 'scene_foyer'},
}
SCENE_LOOPS = tuple(dict.fromkeys(scene['loop'] for scene in SCENES.values()
                                  if scene['loop'] not in AMBIENT_LABELS))
LOOP_NAMES = (*AMBIENT_LABELS, *SCENE_LOOPS)
SPOT_SOUNDS = tuple(dict.fromkeys(scene['spots'] for scene in SCENES.values() if 'spots' in scene))
SPOT_VOLUME = .06            # Sons ponctuels, sur le canal de l'ambiance.
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
        self.ambient = 'ambient'   # Boucle entendue : celle de la scène, sinon celle du livre.
        self.book_ambient = 'ambient'
        self.scene = None
        self._spot_timer = QTimer(self)
        self._spot_timer.setSingleShot(True)
        # Lambda : une méthode liée connectée plante PySide quand un test patche la classe.
        self._spot_timer.timeout.connect(lambda: self._spot_tick())
        self.effects = {}
        self.pending = set()
        self.levels = {'effects': 1.0, 'ambient': 1.0}
        self.variants = {}         # nom -> autres effets (« page_2 »…), en plus de effects[nom]
        self._base_volume = {}
        self._last_variant = {}
        self._rng = random.Random()  # Jamais le générateur des dés.
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
        group = [self.effects[name], *self.variants.get(name, ())]
        self.logger.info('playing %s=%s', name, any(effect.isPlaying() for effect in group))

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
        for name in [*EFFECT_LABELS, *BOOK_SOUNDS.values(), *LOOP_NAMES, *SPOT_SOUNDS]:
            # Effets courts en WAV (attaque immédiate) ; boucles d'ambiance en OGG Vorbis.
            path = next((candidate for candidate in (self.folder / f'{name}{suffix}'
                                                     for suffix in SOUND_SUFFIXES)
                         if candidate.is_file()), None)
            if name in self.effects or path is None:
                continue
            effect = backend(self)
            self.effects[name] = effect
            volume = (.10 if name in LOOP_NAMES else SPOT_VOLUME if name in SPOT_SOUNDS
                      else .80 if name in BOOK_SOUNDS.values() else VOLUMES.get(name, .50))
            self._base_volume[name] = volume
            effect.setVolume(volume)
            if name in LOOP_NAMES:
                # Les PySide6 récents exposent Loop comme une énumération ; le setter attend un entier.
                effect.setLoopCount(getattr(backend.Infinite, 'value', backend.Infinite))
            channel = 'ambient' if name in LOOP_NAMES or name in SPOT_SOUNDS else 'effects'
            if hasattr(effect, 'channel'):
                effect.channel = channel
            effect.statusChanged.connect(lambda n=name: self._ready(n))
            effect.playingChanged.connect(lambda n=name: self._playing_changed(n))
            if name in LOOP_NAMES and hasattr(effect, 'defer_source'):
                effect.defer_source(QUrl.fromLocalFile(str(path)))  # Décodée à la demande.
            else:
                effect.setSource(QUrl.fromLocalFile(str(path)))
            if name in EFFECT_LABELS or name in SPOT_SOUNDS:
                self._load_variants(backend, name, volume, channel)
        self._apply_levels()

    def _load_variants(self, backend, name, volume, channel='effects'):
        """Charger « nom_2 », « nom_3 »… : prêts tout de suite, comme l'effet de base."""
        found = []
        for index in range(2, MAX_VARIANTS + 1):
            path = self.folder / f'{name}_{index}.wav'
            if not path.is_file():
                continue
            variant = backend(self)
            variant.setVolume(volume)
            if hasattr(variant, 'channel'):
                variant.channel = channel
            variant.playingChanged.connect(lambda n=name: self._playing_changed(n))
            variant.setSource(QUrl.fromLocalFile(str(path)))
            found.append(variant)
        self.variants[name] = found

    def _pick(self, name):
        """Choisir une variante prête, jamais deux fois de suite la même."""
        backend = self._backend()
        ready = [effect for effect in [self.effects[name], *self.variants.get(name, ())]
                 if backend is None or effect.status() == backend.Ready]
        if len(ready) <= 1:
            return ready[0] if ready else self.effects[name]
        last = self._last_variant.get(name)
        choice = self._rng.choice([effect for effect in ready if effect is not last])
        self._last_variant[name] = choice
        return choice

    def duck_ambient(self, ducked):
        """Baisser l'ambiance pendant un combat (ou la rétablir), en douceur."""
        mixer = getattr(self, '_pcm_mixer', None)
        if mixer is not None and hasattr(mixer, 'duck_target'):
            mixer.duck_target = AMBIENT_DUCK if ducked else 1.0

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
        if name in LOOP_NAMES and hasattr(effect, 'fade_in'):
            effect.fade_in(AMBIENT_FADE_MS)
            self._remember_ambient(name)
        elif name in EFFECT_LABELS or name in SPOT_SOUNDS:
            effect = self._pick(name)
            # Léger écart de volume : deux coups successifs ne sonnent pas identiques.
            effect.setVolume(self._base_volume.get(name, .5) * self._rng.uniform(.85, 1.0))
            effect.play()
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
        if name in LOOP_NAMES:
            return self.ambient_enabled and name == self.ambient
        if name in SPOT_SOUNDS:
            return self.ambient_enabled and SCENES.get(self.scene, {}).get('spots') == name
        return self.enabled

    def ambient_label(self):
        """Nommer la scène en cours, sinon la boucle du livre, dans le réglage d’ambiance."""
        if self.scene is not None:
            return SCENES[self.scene]['label']
        return AMBIENT_LABELS[self.ambient]

    def _switch_loop(self, name):
        """Passer à une autre boucle en fondu enchaîné, sous le même interrupteur."""
        if name == self.ambient:
            return
        self.logger.info('ambient track=%s', name)
        self.pending.discard(self.ambient)
        self._stop_ambient(self.ambient)  # Fondu enchaîné avec la nouvelle boucle.
        self.ambient = name
        if self.ambient_enabled:
            self.play(name)

    def set_ambient_track(self, engine):
        """Choisir la boucle du livre ouvert ; une scène en cours garde la sienne."""
        self.book_ambient = AMBIENT_TRACKS.get(engine, 'ambient')
        if self.scene is None:
            self._switch_loop(self.book_ambient)

    def set_scene(self, scene):
        """Jouer la boucle et les sons ponctuels d’une scène, ou revenir au livre (None)."""
        if scene is not None and scene not in SCENES:
            raise ValueError(f'Scène inconnue : {scene}')
        if scene == self.scene:
            return
        self.logger.info('scene=%s', scene)
        self.scene = scene
        self.pending.difference_update(SPOT_SOUNDS)
        self._switch_loop(SCENES[scene]['loop'] if scene else self.book_ambient)
        self._schedule_spot()

    def _schedule_spot(self):
        """Programmer le prochain son ponctuel de la scène, ou n’en programmer aucun."""
        self._spot_timer.stop()
        scene = SCENES.get(self.scene, {})
        if self.ambient_enabled and 'spots' in scene:
            self._spot_timer.start(round(self._rng.uniform(*scene['every']) * 1000))

    def _spot_tick(self):
        """Jouer un son ponctuel de la scène, puis programmer le suivant."""
        spots = SCENES.get(self.scene, {}).get('spots')
        if spots:
            self.play(spots)
        self._schedule_spot()

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
            self.pending.intersection_update({*LOOP_NAMES, *SPOT_SOUNDS})
            for name, effect in self.effects.items():
                if name not in LOOP_NAMES and name not in SPOT_SOUNDS:
                    effect.stop()
                    for variant in self.variants.get(name, ()):
                        variant.stop()
        else:
            self.preload()

    def set_ambient_enabled(self, enabled, *, fade=True):
        """Démarrer ou interrompre la boucle d’ambiance indépendamment des effets."""
        self.ambient_enabled = bool(enabled)
        if enabled:
            self.play(self.ambient)
        else:
            self.pending.discard(self.ambient)
            self.pending.difference_update(SPOT_SOUNDS)
            self._stop_ambient(self.ambient, fade)
        self._schedule_spot()

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
