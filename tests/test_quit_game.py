"""Quitter depuis le bouton : confirmation, annulation et arrêt des ressources."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
import main


class QuitGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        for key in ('SAVES_DIR', 'SETTINGS_DIR'):
            replacement = patch.object(main, key, Path(self.folder.name)/key)
            replacement.start()
            self.addCleanup(replacement.stop)
        main.init_portable_dirs()
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        self.w.show()
        self.app.processEvents()

    def test_cancel_keeps_window_state_audio_and_dialog_open(self):
        dialog = QDialog(self.w)
        dialog.show()
        before = self.w._snapshot()
        with patch.object(main.QMessageBox, 'question', return_value=QMessageBox.No) as question, \
             patch.object(self.w.intro_music, 'set_enabled') as music, \
             patch.object(self.w.sounds, 'set_enabled') as effects:
            QTest.mouseClick(self.w.quit_button, Qt.LeftButton)
            question.assert_called_once()
            self.assertEqual(question.call_args.args[-1], QMessageBox.No)
            self.assertTrue(self.w.isVisible())
            self.assertTrue(dialog.isVisible())
            self.assertEqual(self.w._snapshot(), before)
            music.assert_not_called()
            effects.assert_not_called()

    def test_confirm_closes_children_stops_audio_and_releases_log(self):
        dialog = QDialog(self.w)
        dialog.show()
        self.w.intro_music.fade = Mock()
        self.w.intro_music.player = Mock()
        self.w.sounds.effects = {'ambient': Mock(), 'dice': Mock()}
        self.w.sounds.pending.update({'dice', 'ambient'})
        self.w.sounds._pcm_sink = Mock()
        with patch.object(main.QMessageBox, 'question', return_value=QMessageBox.Yes):
            QTest.mouseClick(self.w.quit_button, Qt.LeftButton)
        self.assertFalse(self.w.isVisible())
        self.assertFalse(dialog.isVisible())
        self.w.intro_music.fade.stop.assert_called_once()
        self.w.intro_music.player.stop.assert_called_once()
        for effect in self.w.sounds.effects.values():
            effect.stop.assert_called_once()
        self.w.sounds._pcm_sink.stop.assert_called_once()
        self.assertEqual(self.w.sounds.pending, set())
        self.assertEqual(self.w.sounds.logger.handlers, [])
        log = main.SETTINGS_DIR/'audio.log'
        log.rename(log.with_suffix('.closed'))
