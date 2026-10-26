"""Cycle de l'introduction : entrée consommée, fin/erreur et continuité musicale."""
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal, Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget, QDialog
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest, QSignalSpy

from intro_video import IntroVideoDialog


class FakePlayer(QObject):
    mediaStatusChanged = Signal(object)
    errorOccurred = Signal(object, str)
    EndOfMedia = QMediaPlayer.EndOfMedia
    InvalidMedia = QMediaPlayer.InvalidMedia

    def __init__(self, parent):
        super().__init__(parent)
        self.sources = []
        self.plays = self.stops = 0

    def setVideoOutput(self, widget):
        self.video = widget

    def setSource(self, url):
        self.sources.append(url)

    def play(self):
        self.plays += 1

    def stop(self):
        self.stops += 1


class FakeVideo(QWidget):
    def setAspectRatioMode(self, mode):
        self.mode = mode


class IntroVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def dialog(self, path=None):
        with patch('PySide6.QtMultimedia.QMediaPlayer', FakePlayer), \
             patch('PySide6.QtMultimediaWidgets.QVideoWidget', FakeVideo):
            dialog = IntroVideoDialog(path or Path(__file__).resolve().parents[1] / 'assets/video/introduction.mp4')
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog.start()
        return dialog

    def test_key_skips_once_and_releases_video(self):
        dialog = self.dialog()
        finished = QSignalSpy(dialog.finished)
        QTest.keyClick(dialog.video, Qt.Key_Space)
        dialog.finish()
        self.assertEqual(finished.count(), 1)
        self.assertEqual(dialog.player.stops, 1)
        self.assertTrue(dialog.player.sources[-1].isEmpty())
        self.assertFalse(dialog.watchdog.isActive())

    def test_click_on_video_skips(self):
        dialog = self.dialog()
        QTest.mouseClick(dialog.video, Qt.LeftButton)
        self.assertTrue(dialog._finished)
        self.assertFalse(dialog.isVisible())

    def test_native_window_input_is_consumed(self):
        dialog = self.dialog()
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        self.assertTrue(dialog.eventFilter(QObject(), event))
        self.assertTrue(dialog._finished)

    def test_end_error_and_watchdog_all_continue(self):
        for reason in ('end', 'error', 'watchdog'):
            with self.subTest(reason=reason):
                dialog = self.dialog()
                finished = QSignalSpy(dialog.finished)
                if reason == 'end':
                    dialog.player.mediaStatusChanged.emit(QMediaPlayer.EndOfMedia)
                elif reason == 'error':
                    dialog.player.errorOccurred.emit(QMediaPlayer.FormatError, 'bad media')
                else:
                    dialog.watchdog.timeout.emit()
                self.assertEqual(finished.count(), 1)
                self.assertEqual(dialog.player.stops, 1)

    def test_missing_video_continues_without_starting_player(self):
        dialog = self.dialog(Path('/nonexistent/bifurk-intro.mp4'))
        self.assertTrue(dialog._finished)
        self.assertEqual(dialog.player.plays, 0)

    def test_game_interface_waits_for_intro_without_stopping_music(self):
        from main import MainWindow
        window = MainWindow()
        # Nettoyage complet (ordre inverse) : détruire le faux dialogue d'intro,
        # fermer puis détruire la fenêtre et vider les destructions différées,
        # pour que rien ne survive au test (menu de démarrage réel, minuterie…).
        self.addCleanup(QApplication.sendPostedEvents, None, QEvent.DeferredDelete)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        dialog = QDialog(window)
        dialog.start = lambda: None
        self.addCleanup(QApplication.sendPostedEvents, None, QEvent.DeferredDelete)
        with patch('main.QApplication.platformName', return_value='windows'), \
             patch('intro_video.IntroVideoDialog', return_value=dialog), \
             patch.object(window.intro_music, 'menu') as music, \
             patch.object(window.intro_music, 'fade_out') as fade, \
             patch.object(window, '_show_startup_menu') as menu, \
             patch('main.QTimer.singleShot', side_effect=lambda _, action: action()):
            window._play_startup_intro()
            music.assert_called_once()
            menu.assert_not_called()
            self.assertFalse(window.isVisible())
            dialog.accept()
            menu.assert_called_once()
            self.assertTrue(window.isVisible())
            self.assertTrue(window.isFullScreen())
            self.assertTrue(window._fullscreen)
            window.toggle_fullscreen()
            self.assertFalse(window.isFullScreen())
            fade.assert_not_called()
            self.assertIsNone(window._intro_dialog)


class IntroVideoChoiceTests(unittest.TestCase):
    def test_wide_screens_get_the_21x9_film(self):
        from unittest.mock import MagicMock

        from PySide6.QtCore import QSize

        import main
        window = types.SimpleNamespace(screen=lambda: screen)
        screen = MagicMock()
        choose = main.MainWindow._intro_video_path
        screen.size.return_value = QSize(3440, 1440)
        self.assertEqual(choose(window).name, 'introduction_21x9.mp4')
        screen.size.return_value = QSize(1920, 1080)
        self.assertEqual(choose(window).name, 'introduction.mp4')
