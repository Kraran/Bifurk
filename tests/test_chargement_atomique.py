"""Chargement tout ou rien, historique contrôlé et fondu de la lecture vocale.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_chargement_atomique
"""
import gc
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

import main
import tts
from save_slots import read_save


def wait_for(condition, app, timeout=3.0):
    done = threading.Event()
    QTimer.singleShot(int(timeout * 1000), done.set)
    while not condition() and not done.is_set():
        app.processEvents()
    return condition()


class LoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        for name, value in (('SETTINGS_DIR', self.folder), ('SAVES_DIR', self.folder)):
            patcher = patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.w = main.MainWindow()
        autosave = patch.object(self.w, '_autosave')
        autosave.start()
        self.addCleanup(autosave.stop)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()

    def start_old_game(self):
        w = self.w
        self.old_pdf = str(self.folder / 'ancien.pdf')  # Hors de Bifurk : aucune vraie donnée.
        w.pdf_path, w._book_digest = self.old_pdf, (self.old_pdf, 'a' * 64)
        w.paragraphs = {1: 'Une porte.', 2: 'Une salle.'}
        w._adventurer_draft = None
        w.character['name'] = 'Ancien'
        w.current_paragraph = 1
        w.visited_paragraphs = [1]
        w.undo_stack = [('Changer de paragraphe', w._snapshot())]
        w.action_history = ['Changer de paragraphe']
        w.notes = 'Note ancienne'

    def write_save(self, data):
        path = self.folder / 'emplacement-1.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def test_failed_restore_puts_the_previous_game_back(self):
        self.start_old_game()
        w = self.w
        data = json.loads(json.dumps(w._save_data()))
        data.update(save_name='Nouveau', current_paragraph=5, visited_paragraphs=[5],
                    action_history=[], undo_stack=[], redo_stack=[], notes='Nouvelle note')
        data['character']['name'] = 'Nouveau'
        book = ('nouveau.pdf', {5: 'Cinq.'}, None, None, None, 'b' * 64)
        real_restore = main.MainWindow._restore
        calls = []

        def restore(state):
            calls.append(state)
            if len(calls) == 1:
                w.character = dict(state['character'])  # Effet partiel avant la panne.
                raise RuntimeError('panne pendant la restauration')
            return real_restore(w, state)

        with patch.object(w, '_restore', side_effect=restore):
            with self.assertRaisesRegex(RuntimeError, 'panne'):
                w._apply_loaded_save(data, book)
        self.assertEqual(len(calls), 2)
        self.assertEqual(w.pdf_path, self.old_pdf)
        self.assertEqual(w._book_digest, (self.old_pdf, 'a' * 64))
        self.assertEqual(w.paragraphs, {1: 'Une porte.', 2: 'Une salle.'})
        self.assertEqual(w.character['name'], 'Ancien')
        self.assertEqual(w.current_paragraph, 1)
        self.assertEqual([label for label, _ in w.undo_stack], ['Changer de paragraphe'])
        self.assertEqual(w.notes, 'Note ancienne')

    def test_corrupt_undo_entry_is_refused_at_loading(self):
        self.start_old_game()
        data = json.loads(json.dumps(self.w._save_data()))
        good = self.write_save(data)
        self.assertEqual(len(read_save(good)['undo_stack']), 1)
        for broken in (['label'], ['label', {}], ['label', {'character': {'habilete': 'x'}}],
                       [3, data['undo_stack'][0][1]]):
            data['undo_stack'] = [broken]
            with self.subTest(entry=broken), self.assertRaisesRegex(ValueError, 'Annuler'):
                read_save(self.write_save(data))
        data['undo_stack'] = []
        data['redo_stack'] = [['label', {'character': {}, 'current_paragraph': 1}]]
        with self.assertRaisesRegex(ValueError, 'Rétablir'):
            read_save(self.write_save(data))

    def test_load_game_keeps_the_game_when_the_save_is_corrupt(self):
        self.start_old_game()
        data = json.loads(json.dumps(self.w._save_data()))
        data['undo_stack'] = [['label', {'character': None}]]
        path = self.write_save(data)
        with patch.object(main.QMessageBox, 'critical') as critical:
            self.assertFalse(self.w.load_game(path))
        critical.assert_called_once()
        self.assertEqual(self.w.character['name'], 'Ancien')
        self.assertEqual(self.w.pdf_path, self.old_pdf)

    def test_close_stops_the_voice_at_once(self):
        with patch.object(self.w.tts, 'shutdown') as shutdown:
            self.w.close()
        shutdown.assert_called_once()


class FadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def playing_reader(self):
        reader = tts.ParagraphReader()
        player, output = MagicMock(), MagicMock()
        player.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
        output.volume.return_value = 0.8
        path = Path(tempfile.mkstemp(prefix='bifurk-tts-', suffix='.mp3')[1])
        reader._player, reader._output, reader._temp_file = player, output, path
        return reader, player, output, path

    def test_fade_out_lowers_the_volume_then_stops_and_deletes(self):
        reader, player, output, path = self.playing_reader()
        finished = []
        reader.finished.connect(lambda: finished.append(1))
        reader.fade_out()
        self.assertIsNone(reader._player)       # Une nouvelle lecture peut démarrer aussitôt.
        self.assertFalse(reader.is_busy())
        self.assertEqual(finished, [1])
        self.assertTrue(path.exists())           # Encore audible pendant le fondu.
        player.stop.assert_not_called()
        self.assertTrue(wait_for(lambda: not reader.is_fading(), self.app))
        player.stop.assert_called_once()
        self.assertFalse(path.exists())
        volumes = [call.args[0] for call in output.setVolume.call_args_list]
        self.assertEqual(volumes[-1], 0.0)
        self.assertEqual(volumes, sorted(volumes, reverse=True))

    def test_second_interruption_ends_the_first_fade_at_once(self):
        reader, first, _output, first_path = self.playing_reader()
        reader.fade_out()
        second, output = MagicMock(), MagicMock()
        second.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
        output.volume.return_value = 0.8
        second_path = Path(tempfile.mkstemp(prefix='bifurk-tts-', suffix='.mp3')[1])
        reader._player, reader._output, reader._temp_file = second, output, second_path
        reader.fade_out()
        first.stop.assert_called_once()
        self.assertFalse(first_path.exists())
        self.assertTrue(second_path.exists())
        self.assertTrue(wait_for(lambda: not reader.is_fading(), self.app))
        self.assertFalse(second_path.exists())

    def test_shutdown_ends_the_fade_at_once(self):
        reader, player, _output, path = self.playing_reader()
        reader.fade_out()
        reader.shutdown()
        player.stop.assert_called_once()
        self.assertFalse(path.exists())
        self.assertFalse(reader.is_fading())

    def test_plain_stop_cuts_without_fade(self):
        reader, player, _output, path = self.playing_reader()
        reader.stop()
        player.stop.assert_called_once()
        self.assertFalse(path.exists())
        self.assertFalse(reader.is_fading())


if __name__ == '__main__':
    unittest.main()
