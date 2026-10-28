"""Musique des menus : flux compressé en boucle et fondu indépendant des effets.

Le lecteur conserve le M4A original et le décode en continu, sans charger plusieurs
minutes de PCM en mémoire. Les écrans demandent simplement menu() ou fade_out().
Le service possède son animation Qt : un retour au menu annule le fondu précédent.
L'option « musique permanente » (persistent) neutralise fade_out() : la boucle continue
pendant la partie, au volume du curseur, jusqu'à la coupure ou à la fermeture.
L'option « ma musique » (custom) remplace la boucle FantasyFair par les morceaux du
dossier musique_perso, enchaînés en ordre aléatoire ; menu(), fade_out(), le curseur
et la musique permanente s'appliquent de la même façon. Sans morceau lisible, la
musique habituelle reprend, sans dialogue d'erreur.
La victoire (§400) passe par start_victory() : la musique en cours s'éteint en
1,5 s et « Achievement » boucle au volume du curseur jusqu'à stop_victory(), qui
rend la main à la musique d'accueil si elle doit jouer (menus ou musique permanente).
La mort du héros fait de même avec « Towards the Horizon » (start_epilogue /
stop_epilogue) : les deux morceaux partagent un second lecteur, un seul joue à la fois.
"""
from PySide6.QtCore import QAbstractAnimation, QObject, QPropertyAnimation, QTimer, QUrl
from PySide6.QtGui import QGuiApplication

from audio_configuration import configure_audio_backend
from custom_music import ShuffleBag, scan_tracks


class IntroMusic(QObject):
    """Piloter FantasyFair pendant l'accueil et la préparation, ou toute la session si permanente."""
    VOLUME = 0.45
    DEFAULT_VOLUME_PERCENT = 70
    FADE_MS = 10000
    VICTORY_FADE_MS = 1500

    def __init__(self, path, enabled=True, parent=None, volume_percent=DEFAULT_VOLUME_PERCENT,
                 persistent=False, custom_folder=None, custom=False, victory_path=None,
                 epilogue_path=None):
        """Préparer l'état sans ouvrir de périphérique audio avant le premier menu."""
        super().__init__(parent)
        self.path = path
        self.volume_percent = max(0, min(100, int(volume_percent))) if enabled else 0
        self.enabled = self.volume_percent > 0
        self.in_menu = False
        self.persistent = bool(persistent)
        self.player = self.output = self.fade = None
        self.custom_folder = custom_folder
        self.custom = bool(custom)
        # mode : 'default' (FantasyFair en boucle), 'custom' (dossier) ou None (aucune source).
        self.mode = self.current_track = None
        self.bad_tracks = set()   # illisibles pendant la session ; réessayés après une bascule
        self.bag = ShuffleBag()
        self.victory_path = victory_path
        self.epilogue_path = epilogue_path
        # Morceau spécial en cours : 'victory', 'epilogue' ou None ; suivi même sans
        # sortie audio (tests hors écran).
        self.special = None
        self._special_source = None
        self.victory_player = self.victory_output = self.victory_fade = None

    def _create_player(self):
        """Désactiver la sortie dans les tests sans écran ; Qt décode le M4A en production."""
        if QGuiApplication.platformName() in ('offscreen', 'minimal'):
            return False
        if not self.path.is_file() and not self._wants_custom():
            return False
        configure_audio_backend()
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(self._media_error)
        return True

    @property
    def victory(self):
        return self.special == 'victory'

    def _special_path(self, kind):
        return self.victory_path if kind == 'victory' else self.epilogue_path

    def _create_victory_player(self):
        """Second lecteur, en boucle infinie, pour la victoire et la mort du héros."""
        if (QGuiApplication.platformName() in ('offscreen', 'minimal')
                or not any(path is not None and path.is_file()
                           for path in (self.victory_path, self.epilogue_path))):
            return False
        configure_audio_backend()
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self.victory_output = QAudioOutput(self)
        self.victory_player = QMediaPlayer(self)
        self.victory_player.setAudioOutput(self.victory_output)
        self.victory_player.setLoops(QMediaPlayer.Infinite.value)
        self.victory_fade = QPropertyAnimation(self.victory_output, b'volume', self)
        self.victory_fade.finished.connect(self._victory_faded)
        return True

    def _victory_faded(self):
        if self.special is None and self.victory_player is not None:
            self.victory_player.stop()

    def start_victory(self):
        """Victoire : éteindre la musique en cours en 1,5 s et boucler « Achievement »."""
        self.start_special('victory')

    def stop_victory(self):
        """Quitter la victoire : fondu de la boucle, puis reprise de l'accueil s'il doit jouer."""
        self.stop_special('victory')

    def start_epilogue(self):
        """Mort du héros : « Towards the Horizon » remplace la musique en cours."""
        self.start_special('epilogue')

    def stop_epilogue(self):
        self.stop_special('epilogue')

    def start_special(self, kind):
        if self.special == kind:
            return
        already = self.special is not None
        self.special = kind
        if not already and self.player is not None and self.output is not None:
            if self.fade is None:
                self.fade = QPropertyAnimation(self.output, b'volume', self)
                self.fade.finished.connect(self.player.stop)
            self.fade.stop()
            self.fade.setDuration(self.VICTORY_FADE_MS)
            self.fade.setStartValue(self.output.property('volume'))
            self.fade.setEndValue(0.0)
            self.fade.start()
        self._play_special()

    def _play_special(self):
        path = self._special_path(self.special)
        if (not self.enabled or path is None
                or (self.victory_player is None and not self._create_victory_player())):
            return
        if self._special_source != path:
            self.victory_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            self._special_source = path
        self.victory_fade.stop()
        self.victory_output.setVolume(self.target_volume)
        self.victory_player.play()

    def stop_special(self, kind=None):
        """Fondu du morceau spécial (seulement s'il s'agit de kind), puis reprise de l'accueil."""
        if self.special is None or (kind is not None and self.special != kind):
            return
        self.special = None
        if self.victory_player is not None:
            self.victory_fade.stop()
            self.victory_fade.setDuration(self.VICTORY_FADE_MS)
            self.victory_fade.setStartValue(self.victory_output.property('volume'))
            self.victory_fade.setEndValue(0.0)
            self.victory_fade.start()
        if self.in_menu or self.persistent:
            self._play()

    def _use_default(self):
        """Charger la boucle FantasyFair ; False si le fichier livré manque."""
        from PySide6.QtMultimedia import QMediaPlayer
        self.mode, self.current_track = 'default', None
        if not self.path.is_file():
            self.mode = None
            return False
        self.player.setLoops(QMediaPlayer.Infinite.value)
        self.player.setSource(QUrl.fromLocalFile(str(self.path.resolve())))
        return True

    def _wants_custom(self):
        return self.custom and self.custom_folder is not None

    def playable_tracks(self):
        """Morceaux du dossier personnel, relus à chaque appel, hors fichiers déjà en échec."""
        if self.custom_folder is None:
            return []
        return [track for track in scan_tracks(self.custom_folder) if track not in self.bad_tracks]

    def _next_track(self):
        """Enchaîner un morceau tiré au sort, ou revenir à FantasyFair si aucun n'est lisible."""
        track = self.bag.next(self.playable_tracks)
        while track is not None and track in self.bad_tracks:
            track = self.bag.next(self.playable_tracks)
        if track is None:
            if self._use_default():
                self.player.play()
            return
        self.mode, self.current_track = 'custom', track
        self.player.setLoops(1)
        self.player.setSource(QUrl.fromLocalFile(str(track.resolve())))
        self.player.play()

    def _media_status(self, status):
        """Fin d'un morceau personnel : passer au suivant (fondu en cours compris)."""
        from PySide6.QtMultimedia import QMediaPlayer
        if self.mode != 'custom':
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._next_track()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._media_error()

    def _media_error(self, *_):
        """Écarter le morceau illisible, une seule fois, puis passer au suivant hors du signal."""
        track = self.current_track
        if self.mode != 'custom' or track is None or track in self.bad_tracks:
            return
        self.bad_tracks.add(track)
        QTimer.singleShot(0, lambda: self._skip_failed(track))

    def _skip_failed(self, track):
        if self.mode == 'custom' and self.current_track == track:
            self._next_track()

    def menu(self):
        """Jouer en boucle, sans recommencer le morceau entre deux écrans de préparation."""
        self.in_menu = True
        self._play()

    def _play(self):
        """Annuler un fondu et jouer au volume du curseur, sauf en sourdine ou pendant un
        morceau spécial (victoire, écran de fin)."""
        if self.special:
            return
        if self.fade:
            self.fade.stop()
        if not self.enabled or (self.player is None and not self._create_player()):
            return
        self.output.setVolume(self.target_volume)
        # Le dossier est relu au démarrage de la lecture ; vide, FantasyFair continue
        # sans être rechargé (pas de reprise au début à chaque écran).
        if self._wants_custom() and (self.mode == 'custom' or self.playable_tracks()):
            if self.mode == 'custom':
                self.player.play()
            else:
                self.bag.reset()
                self._next_track()
            return
        if self.mode != 'default' and not self._use_default():
            return
        self.player.play()

    def fade_out(self):
        """Réduire le volume pendant dix secondes puis arrêter le flux à volume nul.

        Musique permanente : l'entrée en partie ne coupe plus la boucle."""
        self.in_menu = False
        if self.persistent or self.player is None or not self.enabled:
            return
        if self.fade is None:
            self.fade = QPropertyAnimation(self.output, b'volume', self)
            self.fade.finished.connect(self.player.stop)
        # Les rafraîchissements et les changements de paragraphe ne prolongent pas le fondu.
        if self.fade.state() == QAbstractAnimation.State.Running:
            return
        self.fade.setDuration(self.FADE_MS)
        self.fade.setStartValue(self.output.property('volume'))
        self.fade.setEndValue(0.0)
        self.fade.start()

    @property
    def target_volume(self):
        """100 % correspond au niveau historique 0,45 ; 70 % vaut donc 0,315."""
        return self.VOLUME * self.volume_percent / 100

    def set_volume(self, percent):
        """Appliquer le curseur immédiatement, sans relancer une musique déjà fondue.

        Pendant le fondu, modifier son amplitude en conservant le temps écoulé :
        le curseur ne doit jamais repousser la fin des dix secondes.
        """
        self.volume_percent = max(0, min(100, int(percent)))
        self.enabled = self.volume_percent > 0
        if not self.enabled:
            if self.fade:
                self.fade.stop()
            if self.player:
                self.player.stop()
            if self.victory_player:
                self.victory_fade.stop()
                self.victory_player.stop()
        elif self.special:
            self._play_special()
        elif self.in_menu or self.persistent:
            self._play()
        elif self.fade and self.fade.state() == QAbstractAnimation.State.Running:
            elapsed = self.fade.currentTime()
            self.fade.setStartValue(self.target_volume)
            self.fade.setCurrentTime(elapsed)

    def set_enabled(self, enabled):
        """Conserver l'interface interne de coupure ; le réglage utilisateur est le volume."""
        self.set_volume((self.volume_percent or self.DEFAULT_VOLUME_PERCENT) if enabled else 0)

    def set_persistent(self, persistent):
        """Activer : relancer la boucle si elle est arrêtée ou en fondu (hors sourdine).

        Désactiver : retrouver le comportement historique, soit un fondu de dix
        secondes en partie, rien de changé dans les menus."""
        self.persistent = bool(persistent)
        if self.persistent:
            self._play()
        elif not self.in_menu:
            self.fade_out()

    def set_custom(self, custom):
        """Basculer entre le dossier personnel et FantasyFair ; relire le dossier.

        La bascule s'entend tout de suite si la musique doit jouer (menus ou musique
        permanente) ; sinon, elle vaut pour la prochaine reprise."""
        self.custom = bool(custom)
        self.bad_tracks.clear()
        self.bag.reset()
        if self.mode == 'custom' and self.custom:
            self.mode = None  # relire le dossier et tirer un nouveau morceau
        if self.in_menu or self.persistent:
            self._play()
