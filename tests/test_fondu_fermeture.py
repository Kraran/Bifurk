"""Fondu audio à la fermeture : différé seulement quand du son joue dans une fenêtre affichée.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_fondu_fermeture
"""
import gc
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication

import main
from pcm_audio import Mixer


def spin(app, seconds):
    done = threading.Event()
    QTimer.singleShot(int(seconds * 1000), done.set)
    while not done.is_set():
        app.processEvents()


class QuitFadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = Path(tempfile.mkdtemp())
        for name in ('SETTINGS_DIR', 'SAVES_DIR'):
            patcher = patch.object(main, name, folder)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.w = main.MainWindow()
        self.w._autosave = lambda: None

    def tearDown(self):
        self.w._quit_fade_state = 'done'
        self.w.close()
        self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()

    def test_hidden_or_headless_window_closes_at_once(self):
        self.w.tts.shutdown = MagicMock()
        self.w._audio_audible = lambda: True
        self.w.close()  # Plateforme offscreen et fenêtre jamais affichée : aucun délai.
        self.w.tts.shutdown.assert_called_once()
        self.assertIsNone(self.w._quit_fade_state)

    def test_audible_window_fades_then_closes(self):
        w = self.w
        w.show()
        w.tts.shutdown = MagicMock()
        w.tts.duck = MagicMock()
        w._audio_audible = lambda: True
        mixer = w.sounds._pcm_mixer = Mixer(w.sounds)
        with patch.object(main.QApplication, 'platformName', return_value='windows'):
            w.close()
            self.assertTrue(w.isVisible())          # La fermeture attend la fin du fondu.
            self.assertEqual(w._quit_fade_state, 'running')
            w.tts.shutdown.assert_not_called()
            self.assertFalse(w.centralWidget().isEnabled())
            spin(self.app, w.QUIT_FADE_MS / 1000 + .5)
        self.assertEqual(w._quit_fade_state, 'done')
        self.assertFalse(w.isVisible())
        w.tts.shutdown.assert_called_once()
        self.assertEqual(mixer.gain, 0.0)
        self.assertEqual(w.tts.duck.call_args_list[-1].args[0], 0.0)

    def test_second_request_closes_immediately(self):
        w = self.w
        w.show()
        w.tts.shutdown = MagicMock()
        w._audio_audible = lambda: True
        with patch.object(main.QApplication, 'platformName', return_value='windows'):
            w.close()
            self.assertTrue(w.isVisible())
            w.close()
        self.assertFalse(w.isVisible())
        w.tts.shutdown.assert_called_once()

    def test_silent_window_closes_at_once(self):
        w = self.w
        w.show()
        w._audio_audible = lambda: False
        with patch.object(main.QApplication, 'platformName', return_value='windows'):
            w.close()
        self.assertFalse(w.isVisible())

    def test_mixer_gain_scales_every_voice(self):
        mixer = Mixer()
        voice = MagicMock(spec=['samples', 'position', 'volume', 'loops', 'isPlaying', 'stop'],
                          samples=[10000, 10000], position=0, volume=0.5, loops=1)
        voice.isPlaying.return_value = True
        mixer.voices.append(voice)
        mixer.gain = 0.5
        import array
        data = array.array('h', mixer.readData(4))
        self.assertEqual(list(data), [2500, 2500])


if __name__ == '__main__':
    unittest.main()
