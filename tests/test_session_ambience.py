import copy
import json
import random
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, call

from PySide6.QtWidgets import QApplication, QMessageBox
import main
from grimoire_ui import IlluminatedPage
from themes import available_themes
from sound_effects import SoundBank


class SessionAmbienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        for name, value in {
            'APP_DIR': self.root, 'BOOKS_DIR': self.root/'donnees/grimoires',
            'SAVES_DIR': self.root/'donnees/sauvegardes', 'SETTINGS_DIR': self.root/'donnees/parametres',
        }.items():
            p = patch.object(main, name, value)
            p.start(); self.addCleanup(p.stop)
        main.init_portable_dirs()
        for name in ('information', 'warning', 'critical'):
            p = patch.object(QMessageBox, name)
            p.start(); self.addCleanup(p.stop)
        self.windows = []

    def window(self, **kwargs):
        window = main.MainWindow(**kwargs)
        self.windows.append(window)
        return window

    def tearDown(self):
        for window in self.windows:
            window.close(); window.deleteLater()
        self.app.processEvents()

    def book(self, name='book.pdf'):
        path = self.root/name
        path.write_bytes(b'%PDF-test-book')
        return path

    def pdf_mocks(self):
        for name, value in [('extract_paragraphs', {1:'Première salle.',2:'Deuxième salle.'}),
                            ('catalogue_for_pdf', None), ('load_book_events', None)]:
            p = patch.object(main, name, return_value=value)
            p.start(); self.addCleanup(p.stop)

    def test_restart_uses_imported_copy_and_restores_matching_autosave(self):
        self.pdf_mocks()
        source = self.book()
        w = self.window()
        w.open_pdf(source, startup=True)
        imported = Path(w.pdf_path)
        self.assertTrue(imported.is_relative_to(main.BOOKS_DIR))
        w.go_to(1)
        w.set_stat('endurance', 13)
        source.unlink()
        restored = self.window(restore_session=True)
        self.app.processEvents()
        self.assertEqual(Path(restored.pdf_path), imported)
        self.assertEqual(restored.current_paragraph, 1)
        self.assertEqual(restored.character['endurance'], 13)
        self.assertEqual(restored.visited_paragraphs, [1])

    def test_different_book_autosave_is_not_applied(self):
        self.pdf_mocks()
        w = self.window()
        w.open_pdf(self.book('first.pdf'), startup=True)
        last = Path(w.pdf_path)
        other = main.BOOKS_DIR/'other.pdf'; other.write_bytes(b'%PDF-other')
        data = w._save_data()
        data['pdf_path'] = str(other.relative_to(main.APP_DIR))
        data['character']['endurance'] = 1
        w._write_atomic(main.SAVES_DIR/'autosave.json', data)
        restored = self.window(restore_session=True)
        self.app.processEvents()
        self.assertEqual(Path(restored.pdf_path), last)
        self.assertIsNone(restored.current_paragraph)
        self.assertEqual(restored.character['endurance'], 20)

    def test_existing_installation_resumes_without_preferences_file(self):
        self.pdf_mocks()
        w = self.window()
        w.open_pdf(self.book(), startup=True)
        w.go_to(2)
        w.preferences_path.unlink()
        restored = self.window(restore_session=True)
        self.app.processEvents()
        self.assertEqual(restored.current_paragraph, 2)
        self.assertEqual(restored.pdf_path, w.pdf_path)
        self.assertTrue(restored.preferences_path.is_file())

    def test_missing_last_book_does_not_open_file_picker(self):
        main.MainWindow._write_atomic(self.window(), main.SETTINGS_DIR/'preferences.json',
                                     {'last_book':'missing.pdf'})
        with patch.object(main.MainWindow, '_themed_file_dialog') as picker:
            restored = self.window(restore_session=True)
            self.app.processEvents()
        picker.assert_not_called()
        self.assertIsNone(restored.pdf_path)

    def test_audio_follows_real_game_events_without_changing_dice(self):
        w = self.window()
        w.paragraphs = {1:'Une salle.'}
        with patch.object(w.sounds, 'play') as play:
            w.go_to(1); w.go_to(1)
            self.assertEqual(play.call_args_list, [call('page')])
            play.reset_mock()
            with patch('main.random.randint', side_effect=[2,5]):
                self.assertEqual(w._roll(2), ([2,5],7))
            play.assert_called_once_with('dice')
            play.reset_mock()
            with patch('main.random.randint', side_effect=[1,1,6,6]), \
                    patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
                w.combat_round()
            self.assertEqual(play.call_args_list, [call('dice'),call('dice'),call('swords')])

    def test_theme_change_keeps_game_and_updates_painted_page(self):
        w = self.window()
        w.paragraphs = {1:'Une salle.'}; w.go_to(1)
        before = w._snapshot()
        folder = self.root/'themes/night'; folder.mkdir(parents=True)
        manifest = copy.deepcopy(w.theme.data)
        manifest.update(id='night', name='Thème de test', stylesheet='theme.qss')
        manifest['assets'] = {key:str(path) for key,path in w.theme.assets.items()}
        manifest['colors']['ink'] = '#332211'
        (folder/'theme.json').write_text(json.dumps(manifest))
        (folder/'theme.qss').write_text('QWidget { color: ${ink}; }')
        w.themes.update(available_themes(folder.parent))
        w.apply_theme('night')
        self.assertEqual(w._snapshot(), before)
        self.assertIn('#332211', w.styleSheet())
        self.assertEqual(w.findChild(IlluminatedPage).theme.id, 'night')
        self.assertEqual(json.loads(w.preferences_path.read_text())['theme'], 'night')

    def test_effects_are_valid_pcm_and_muting_stops_playback(self):
        state = random.getstate()
        bank = SoundBank(main.ASSET_DIR/'sounds')
        from unittest.mock import Mock
        effect = Mock(); bank.effects['page'] = effect
        bank.set_enabled(False); bank.play('page')
        effect.stop.assert_called_once()
        effect.play.assert_not_called()
        self.assertEqual(random.getstate(), state)
        for name in ('page','dice','swords'):
            with wave.open(str(main.ASSET_DIR/'sounds'/f'{name}.wav')) as sound:
                self.assertEqual((sound.getnchannels(), sound.getsampwidth()), (1,2))
                self.assertGreater(sound.getnframes(), 1000)
