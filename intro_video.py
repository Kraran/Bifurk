"""Cinématique d'accueil muette, indépendante de la musique et de la partie.

Un seul lecteur vidéo existe pendant l'introduction. Aucune sortie audio ne lui
est associée ; la musique appartient à IntroMusic et survit à la fermeture de
cette fenêtre. Une erreur de décodage ne doit jamais bloquer l'accès au jeu.
"""
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

from audio_configuration import configure_audio_backend


class IntroVideoDialog(QDialog):
    """Afficher une seule fois le film ; tout clic ou toute touche le termine."""
    def __init__(self, path, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        configure_audio_backend()
        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.path = Path(path)
        self._finished = False
        self.setWindowTitle('Bifurk — Introduction')
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setStyleSheet('QDialog { background: black; } QLabel { color: #c9ac77; background: black; padding: 12px; font-size: 15px; }')
        self.player = QMediaPlayer(self)
        # Le fichier est sans piste audio ; ne pas créer de QAudioOutput constitue
        # une seconde garantie et évite de concurrencer le lecteur musical.
        self.video = QVideoWidget(self)
        self.video.setAspectRatioMode(Qt.KeepAspectRatio)
        self.player.setVideoOutput(self.video)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video, 1)
        hint = QLabel('Cliquez ou appuyez sur une touche pour commencer', self)
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        self.setAccessibleName('Introduction de Bifurk. Une touche ou un clic permet de passer.')
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(self.finish)
        # Filet de sécurité pour un backend bloqué, sans dialogue d'erreur modal.
        # Le film livré dure six secondes ; ce délai ne tronque pas sa lecture.
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.setInterval(20000)
        self.watchdog.timeout.connect(self.finish)
        self.finished.connect(self._cleanup)

    def start(self):
        """Brancher les entrées avant le chargement pour permettre de passer immédiatement."""
        QApplication.instance().installEventFilter(self)
        self.watchdog.start()
        if not self.path.is_file():
            self.finish()
            return
        self.player.setSource(QUrl.fromLocalFile(str(self.path.resolve())))
        if not self._finished:
            self.player.play()

    def _media_status(self, status):
        """Fin naturelle et fichier illisible rejoignent exactement le même parcours."""
        from PySide6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.EndOfMedia, QMediaPlayer.InvalidMedia):
            self.finish()

    def eventFilter(self, watched, event):
        """Intercepter aussi les événements des fenêtres vidéo natives.

        Le jeu est encore masqué : toutes les entrées Qt pendant le film lui
        appartiennent, y compris celles adressées à un QWindow interne."""
        if not self._finished and self.isVisible():
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
                return True
            if event.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
                self.finish()
                return True
        return super().eventFilter(watched, event)

    def finish(self, *_):
        """Continuer une seule fois, même si stop() déclenche un autre signal média."""
        if self._finished:
            return
        self._finished = True
        self.accept()

    def _cleanup(self, *_):
        """Libérer la vidéo et son filtre ; ne jamais toucher au lecteur musical."""
        self._finished = True
        self.watchdog.stop()
        QApplication.instance().removeEventFilter(self)
        self.player.stop()
        self.player.setSource(QUrl())
