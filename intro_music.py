"""Musique des menus : flux compressé en boucle et fondu indépendant des effets.

Le lecteur conserve le M4A original et le décode en continu, sans charger plusieurs
minutes de PCM en mémoire. Les écrans demandent simplement menu() ou fade_out().
Le service possède son animation Qt : un retour au menu annule le fondu précédent.
"""
from PySide6.QtCore import QAbstractAnimation, QObject, QPropertyAnimation, QUrl
from PySide6.QtGui import QGuiApplication
from audio_configuration import configure_audio_backend


class IntroMusic(QObject):
    """Piloter FantasyFair uniquement pendant l'accueil et la préparation d'une partie."""
    VOLUME = 0.45
    DEFAULT_VOLUME_PERCENT = 70
    FADE_MS = 10000

    def __init__(self, path, enabled=True, parent=None, volume_percent=DEFAULT_VOLUME_PERCENT):
        """Préparer l'état sans ouvrir de périphérique audio avant le premier menu."""
        super().__init__(parent)
        self.path = path
        self.volume_percent = max(0, min(100, int(volume_percent))) if enabled else 0
        self.enabled = self.volume_percent > 0
        self.in_menu = False
        self.player = self.output = self.fade = None

    def _create_player(self):
        """Désactiver la sortie dans les tests sans écran ; Qt décode le M4A en production."""
        if QGuiApplication.platformName() in ('offscreen', 'minimal') or not self.path.is_file():
            return False
        configure_audio_backend()
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.setLoops(QMediaPlayer.Infinite.value)
        self.player.setSource(QUrl.fromLocalFile(str(self.path.resolve())))
        return True

    def menu(self):
        """Jouer en boucle, sans recommencer le morceau entre deux écrans de préparation."""
        self.in_menu = True
        if self.fade:
            self.fade.stop()
        if not self.enabled or (self.player is None and not self._create_player()):
            return
        self.output.setVolume(self.target_volume)
        self.player.play()

    def fade_out(self):
        """Réduire le volume pendant dix secondes puis arrêter le flux à volume nul."""
        self.in_menu = False
        if self.player is None or not self.enabled:
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
        elif self.in_menu:
            self.menu()
        elif self.fade and self.fade.state() == QAbstractAnimation.State.Running:
            elapsed = self.fade.currentTime()
            self.fade.setStartValue(self.target_volume)
            self.fade.setCurrentTime(elapsed)

    def set_enabled(self, enabled):
        """Conserver l'interface interne de coupure ; le réglage utilisateur est le volume."""
        self.set_volume((self.volume_percent or self.DEFAULT_VOLUME_PERCENT) if enabled else 0)
