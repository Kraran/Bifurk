"""Préférences, dernier livre et indépendance des réglages d’ambiance.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
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
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
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
        """Construire une fenêtre de test avec les options demandées."""
        window = main.MainWindow(**kwargs)
        self.windows.append(window)
        return window

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
        for window in self.windows:
            window.close(); window.deleteLater()
        self.app.processEvents()

    def book(self, name='book.pdf'):
        """Créer le fichier PDF factice destiné aux contrôles de référence portable."""
        path = self.root/name
        path.write_bytes(b'%PDF-test-book')
        return path

    def pdf_mocks(self):
        """Remplacer extraction et catalogues pour isoler la session de la lecture d’un vrai PDF."""
        for name, value in [('extract_paragraphs', {1:'Première salle.',2:'Deuxième salle.'}),
                            ('catalogue_for_pdf', None), ('load_book_events', None)]:
            p = patch.object(main, name, return_value=value)
            p.start(); self.addCleanup(p.stop)

    def test_startup_loads_selected_slot_instead_of_autosave(self):
        self.pdf_mocks()
        w = self.window()
        w.open_pdf(self.book(), startup=True)
        w._begin_adventure('Éléanor')
        w.set_stat('endurance', 13)
        slot = main.SAVES_DIR/'emplacement-1.json'
        w._write_atomic(slot, w._save_data())
        w.set_stat('endurance', 2)
        def choose(dialog):
            self.assertFalse(dialog.new_game_requested)
            dialog.selected_path = str(slot)
            return main.QDialog.Accepted
        with patch.object(main.SaveSlotsDialog, 'exec', choose):
            restored = self.window(startup=True)
            self.app.processEvents()
        self.assertEqual(restored.character['name'], 'Éléanor')
        self.assertEqual(restored.character['endurance'], 13)

    def test_startup_new_game_opens_last_book_intro(self):
        self.pdf_mocks()
        w = self.window()
        w.open_pdf(self.book(), startup=True)
        w._begin_adventure('Éléanor')
        w.go_to(2)
        def choose(dialog):
            dialog.new_game_requested = True
            return main.QDialog.Accepted
        with patch.object(main.SaveSlotsDialog, 'exec', choose):
            restored = self.window(startup=True)
            self.app.processEvents()
        self.assertEqual(restored.pdf_path, w.pdf_path)
        self.assertIsNone(restored.current_paragraph)
        self.assertNotIn('name', restored.character)
        self.assertFalse(restored.adventure_tabs.isEnabled())

    def test_startup_without_preferences_never_migrates_autosave(self):
        self.pdf_mocks()
        w = self.window()
        w.open_pdf(self.book(), startup=True)
        w._begin_adventure('Éléanor')
        w.preferences_path.unlink()
        with patch.object(main.SaveSlotsDialog, 'exec', return_value=main.QDialog.Rejected), \
                patch.object(main.MainWindow, 'load_game') as load:
            restored = self.window(startup=True)
            self.app.processEvents()
        load.assert_not_called()
        self.assertIsNone(restored.pdf_path)

    def test_startup_new_game_without_book_opens_import_picker(self):
        def choose(dialog):
            dialog.new_game_requested = True
            return main.QDialog.Accepted
        with patch.object(main.SaveSlotsDialog, 'exec', choose), \
                patch.object(main.MainWindow, '_themed_file_dialog', return_value=None) as picker:
            restored = self.window(startup=True)
            self.app.processEvents()
        picker.assert_called_once_with(kind='pdf')
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
