"""Menu de démarrage robuste : enchaînement post-intro unique, fermeture pendant le menu.

Régression : closeEvent rejetait encore le dialogue d'intro (destruction différée
non traitée), réémettant finished ; l'enchaînement relançait alors un menu de
démarrage sur une fenêtre fermée, détruite pendant exec() →
« RuntimeError: … SaveSlotsDialog already deleted ».
Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_menu_demarrage"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QDialog

import main
from main import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def flush_deletes():
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


class StartupMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(main, 'SAVES_DIR', Path(tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(flush_deletes)

    def make_window(self):
        window = MainWindow()

        def dispose():
            if shiboken6.isValid(window):
                window.close()
                window.deleteLater()
        self.addCleanup(dispose)
        return window

    def play_intro(self, window, menu):
        """Lancer la cinématique avec un faux dialogue ; menu remplace _show_startup_menu."""
        dialog = QDialog(window)
        dialog.start = lambda: None
        for patcher in (patch('main.QApplication.platformName', return_value='windows'),
                        patch('intro_video.IntroVideoDialog', return_value=dialog),
                        patch.object(window.intro_music, 'menu'),
                        patch.object(window, '_show_startup_menu', menu),
                        patch('main.QTimer.singleShot', side_effect=lambda _, action: action())):
            patcher.start()
            self.addCleanup(patcher.stop)
        window._play_startup_intro()
        return dialog

    def test_post_intro_chain_triggered_twice_opens_single_menu(self):
        window = self.make_window()
        calls = []
        dialog = self.play_intro(window, lambda: calls.append(1))
        dialog.accept()
        dialog.finished.emit(QDialog.Rejected)  # réémission (ex. closeEvent avant destruction)
        dialog.reject()
        self.assertEqual(calls, [1])
        self.assertIsNone(window._intro_dialog)

    def test_closing_during_intro_launches_no_menu(self):
        window = self.make_window()
        calls = []
        self.play_intro(window, lambda: calls.append(1))
        window.close()  # closeEvent rejette le dialogue d'intro → finished
        self.assertEqual(calls, [])
        self.assertFalse(window.isVisible())

    def test_close_after_intro_does_not_reopen_menu(self):
        window = self.make_window()
        calls = []
        self.play_intro(window, lambda: calls.append(1))
        window._intro_dialog.accept()
        window.close()  # le dialogue d'intro, pas encore détruit, est rejeté à nouveau
        self.assertEqual(calls, [1])

    def test_startup_menu_not_reentrant(self):
        window = self.make_window()
        opened = []

        def fake_exec(dialog):
            opened.append(dialog)
            window._show_startup_menu()  # second déclenchement pendant le menu
            return QDialog.Rejected
        with patch('main.SaveSlotsDialog.exec', fake_exec):
            window._show_startup_menu()
        self.assertEqual(len(opened), 1)
        self.assertFalse(window._startup_menu_open)

    def test_startup_menu_skipped_once_window_closed(self):
        window = self.make_window()
        window.show()
        window.close()
        with patch('main.SaveSlotsDialog.exec') as exec_:
            window._show_startup_menu()
        exec_.assert_not_called()

    def _menu_with_window_event(self, event):
        """Ouvrir le vrai menu ; pendant exec(), event(window) ferme ou détruit la fenêtre."""
        window = self.make_window()
        window.show()
        QTimer.singleShot(0, lambda: event(window))
        with patch.object(MainWindow, 'load_game') as load, \
             patch.object(MainWindow, '_start_new_game') as new_game, \
             patch.object(window.intro_music, 'menu'):
            window._show_startup_menu()  # ne doit lever aucune exception
        load.assert_not_called()
        new_game.assert_not_called()
        return window

    def test_closing_window_while_menu_open_raises_nothing(self):
        window = self._menu_with_window_event(lambda w: w.close())
        self.assertTrue(shiboken6.isValid(window))
        self.assertFalse(window._startup_menu_open)

    def test_window_deleted_while_menu_open_raises_nothing(self):
        def close_and_delete(w):
            w.close()
            w.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self._menu_with_window_event(close_and_delete)

    def test_window_destroyed_while_menu_open_raises_nothing(self):
        window = self._menu_with_window_event(shiboken6.delete)
        self.assertFalse(shiboken6.isValid(window))

    def test_intro_then_place_labels_stderr_clean(self):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'tests.test_intro_video', 'tests.test_place_labels'],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('already deleted', result.stderr)


if __name__ == '__main__':
    unittest.main()
