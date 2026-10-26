"""Lecture vocale des paragraphes (voix Edge) sans réseau : edge_tts est simulé.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_tts
"""
import gc
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QSlider

import main
import tts


def fake_edge_tts(fail=False):
    """Module edge_tts minimal : écrit un faux MP3 ou échoue comme sans réseau."""
    calls = []

    class Communicate:
        def __init__(self, text, voice, rate='+0%', volume='+0%'):
            calls.append((text, voice, rate) if volume == '+0%' else (text, voice, rate, volume))

        async def save(self, path):
            if fail:
                raise OSError('réseau indisponible')
            Path(path).write_bytes(b'ID3fake')

    async def list_voices():
        raise OSError('réseau indisponible')

    return types.SimpleNamespace(Communicate=Communicate, list_voices=list_voices), calls


def wait_for(condition, app, timeout=3.0):
    done = threading.Event()
    QTimer.singleShot(int(timeout*1000), done.set)
    while not condition() and not done.is_set():
        app.processEvents()
    return condition()


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_voice_and_offline_voice_list(self):
        module, _ = fake_edge_tts()
        with patch.dict(sys.modules, {'edge_tts': module}):
            tts._refresh_voices()  # Service injoignable : la liste de secours reste.
        with patch('threading.Thread'):
            voices = tts.available_french_voices()
        self.assertEqual(tts.DEFAULT_VOICE, 'fr-FR-RemyMultilingualNeural')
        self.assertIn(tts.DEFAULT_VOICE, voices)
        self.assertEqual(tts.ParagraphReader().voice, tts.DEFAULT_VOICE)

    def test_synthesis_runs_off_the_main_thread_and_plays_on_it(self):
        module, calls = fake_edge_tts()
        reader = tts.ParagraphReader()
        played = []
        def play(request, filename):
            played.append((threading.current_thread() is threading.main_thread(), Path(filename).read_bytes()))
            Path(filename).unlink()
        with patch.dict(sys.modules, {'edge_tts': module}), \
                patch.object(tts.ParagraphReader, '_play', autospec=True,
                             side_effect=lambda self, r, f: play(r, f)):
            reader.speak('  Vous entrez dans la forêt.  ')
            self.assertTrue(reader.is_busy())
            self.assertTrue(wait_for(lambda: played, self.app))
        self.assertEqual(calls, [('Vous entrez dans la forêt.', tts.DEFAULT_VOICE, '+0%')])
        self.assertEqual(played, [(True, b'ID3fake')])

    def test_network_failure_is_quiet(self):
        module, _ = fake_edge_tts(fail=True)
        reader = tts.ParagraphReader()
        errors, finished = [], []
        reader.error.connect(errors.append)
        reader.finished.connect(lambda: finished.append(1))
        with patch.dict(sys.modules, {'edge_tts': module}):
            reader.speak('Texte')
            self.assertTrue(wait_for(lambda: finished, self.app))
        self.assertEqual(len(errors), 1)
        self.assertIn('indisponible', errors[0])
        self.assertFalse(reader.is_busy())

    def test_new_request_supersedes_the_previous_one(self):
        reader = tts.ParagraphReader()
        with patch('threading.Thread'):
            reader.speak('Premier')
            first = reader._request
            reader.speak('Second')
        path = Path(tempfile.mkstemp(suffix='.mp3')[1])
        reader._play(first, str(path))  # Synthèse périmée : fichier supprimé, rien n’est joué.
        self.assertFalse(path.exists())
        self.assertIsNone(reader._player)


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = Path(tempfile.mkdtemp())
        patcher = patch.object(main, 'SETTINGS_DIR', self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.w = main.MainWindow()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()

    def test_button_reads_the_current_paragraph(self):
        button = self.w.tts_button
        self.assertIsInstance(button, main.PageToolButton)
        self.assertEqual(button.toolTip(), 'Lire le paragraphe à voix haute')
        self.assertEqual(self.w.tts.voice, tts.DEFAULT_VOICE)
        self.w.paragraphs = {12: 'Un loup surgit des fourrés.'}
        self.w.current_paragraph = 12
        with patch.object(self.w.tts, 'speak') as speak:
            button.click()
        speak.assert_called_once_with('Un loup surgit des fourrés.')
        with patch.object(self.w.tts, 'is_busy', return_value=True), patch.object(self.w.tts, 'stop') as stop:
            button.click()  # Second clic pendant la lecture : arrêt.
        stop.assert_called_once()

    def test_voice_choice_is_saved_and_restored(self):
        chosen = []
        def capture():
            dialog = self.w.findChild(QDialog, 'ambienceDialog')
            combo = dialog.findChild(QComboBox, 'ttsVoice')
            chosen.append(combo.currentData())
            combo.setCurrentIndex(combo.findData('fr-FR-DeniseNeural'))
            dialog.reject()
        QTimer.singleShot(0, capture)
        self.w.show_ambience()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()
        self.assertEqual(chosen, [tts.DEFAULT_VOICE])
        self.assertEqual(self.w.tts.voice, 'fr-FR-DeniseNeural')
        saved = json.loads((self.settings/'preferences.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['tts_voice'], 'fr-FR-DeniseNeural')
        again = main.MainWindow()
        self.addCleanup(again.deleteLater)
        self.assertEqual(again.tts.voice, 'fr-FR-DeniseNeural')


    def test_voice_volume_is_applied_saved_and_restored(self):
        def adjust():
            dialog = self.w.findChild(QDialog, 'ambienceDialog')
            slider = dialog.findChild(QSlider, 'ttsVolume')
            self.assertEqual(slider.value(), 80)
            slider.setValue(35)
            dialog.reject()
        QTimer.singleShot(0, adjust)
        self.w.show_ambience()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()
        self.assertAlmostEqual(self.w.tts._volume, 0.35)
        saved = json.loads((self.settings/'preferences.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['tts_volume'], 35)
        again = main.MainWindow()
        self.addCleanup(again.deleteLater)
        self.assertAlmostEqual(again.tts._volume, 0.35)



class VolumeAndPreloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_volume_above_100_asks_the_service_for_a_louder_voice(self):
        reader = tts.ParagraphReader()
        reader.set_volume(1.4)
        self.assertEqual((reader._volume, reader._gain), (1.0, '+40%'))
        reader.set_volume(3)
        self.assertEqual(reader._gain, '+50%')
        reader.set_volume(0.5)
        self.assertEqual((reader._volume, reader._gain), (0.5, '+0%'))

    def test_next_chunk_is_preloaded_on_the_spare_player_and_swapped_in(self):
        reader = tts.ParagraphReader()
        reader._pending, reader._synth_done = True, False
        folder = Path(tempfile.mkdtemp())
        files = [folder/f'{i}.mp3' for i in range(3)]
        for f in files:
            f.write_bytes(b'ID3fake')
        for f in files:
            reader._play(reader._request, str(f))
        first = reader._player
        self.assertEqual(reader._temp_file, files[0])
        self.assertEqual(reader._spare_file, files[1])
        reader._play_next()  # Fin du premier morceau.
        self.assertIsNot(reader._player, first)
        self.assertEqual(reader._temp_file, files[1])
        self.assertEqual(reader._spare_file, files[2])
        self.assertFalse(files[0].exists())
        reader.stop()
        self.assertFalse(any(f.exists() for f in files))


if __name__ == '__main__':
    unittest.main()


class PrepareSpeechTextTests(unittest.TestCase):
    def test_layout_line_breaks_are_joined(self):
        from tts import prepare_speech_text
        raw = "Vous entrez dans la\nruelle sombre et un aven-\nturier vous salue.\nIl sourit.\n\nRendez-vous au 12."
        self.assertEqual(prepare_speech_text(raw),
                         "Vous entrez dans la ruelle sombre et un aventurier vous salue.\nIl sourit.\n\nRendez-vous au 12.")

    def test_compound_words_keep_their_hyphen(self):
        from tts import prepare_speech_text
        self.assertEqual(prepare_speech_text("allez au\nRendez-\nVous"), "allez au Rendez-Vous")


class SplitSpeechChunksTests(unittest.TestCase):
    def test_first_chunk_is_short_and_nothing_is_lost(self):
        from tts import split_speech_chunks
        text = ' '.join(f'Phrase numéro {i} de la ruelle sombre.' for i in range(30))
        chunks = split_speech_chunks(text)
        self.assertGreater(len(chunks), 2)
        self.assertLessEqual(len(chunks[0]), 160)
        self.assertEqual(' '.join(chunks), text)


class ParagraphChangeTests(unittest.TestCase):
    def test_reading_follows_the_new_paragraph_only_when_active(self):
        calls = []
        fake = types.SimpleNamespace(is_busy=lambda: busy[0], stop=lambda: calls.append('stop'),
                                     speak=lambda text: calls.append(('speak', text)))
        busy = [False]
        window = types.SimpleNamespace(tts=fake, _restoring=False, paragraphs={2: 'Deux.'})
        follow = main.BifurkWindow._tts_follow_paragraph if hasattr(main, 'BifurkWindow') else None
        if follow is None:
            follow = next(cls for cls in vars(main).values()
                          if isinstance(cls, type) and hasattr(cls, '_tts_follow_paragraph'))._tts_follow_paragraph
        follow(window, 2)
        self.assertEqual(calls, [])
        busy[0] = True
        follow(window, 2)
        self.assertEqual(calls, [('speak', 'Deux.')])
        window._restoring = True
        follow(window, 2)
        self.assertEqual(calls[-1], 'stop')
