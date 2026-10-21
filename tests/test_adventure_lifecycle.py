import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QMessageBox

import main
from save_slots import SaveSlotsDialog


class AdventureLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        for key in ('SAVES_DIR', 'SETTINGS_DIR'):
            p = patch.object(main, key, self.root / key)
            p.start()
            self.addCleanup(p.stop)
        self.w = main.MainWindow()
        self.w.paragraphs = {1: 'Une porte.', 2: 'Une salle.'}
        self.w.pdf_path = str(self.root / 'livre.pdf')

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def start(self, name='Éléanor'):
        self.w._show_book_title()
        self.w.choice_layout.itemAt(1).widget().setText(name)
        self.w.choice_layout.itemAt(2).widget().click()

    def test_intro_requires_nonblank_name_before_first_paragraph(self):
        self.w._show_book_title()
        field = self.w.choice_layout.itemAt(1).widget()
        start = self.w.choice_layout.itemAt(2).widget()
        self.assertFalse(start.isEnabled())
        field.setText('   ')
        self.assertFalse(start.isEnabled())
        field.setText('  Éléanor  ')
        start.click()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.character['name'], 'Éléanor')
        self.assertEqual(self.w._save_data()['save_name'], 'Éléanor')

    def test_death_restart_resets_all_progress_and_equipment(self):
        self.start()
        w = self.w
        w.character['inventory'].append('Trésor')
        w.character['book_facts'] = {'cle': True}
        w.completed_book_events.add(2)
        w.encounter_history['2'] = [{'name': 'Orque', 'status': 'vaincu'}]
        w.go_to(2)
        w.set_stat('endurance', 0)
        self.assertIn('Fin de l’aventure', w.paragraph_title.text())
        self.assertIn('Éléanor', w.reader.toPlainText())
        self.assertFalse(w.adventure_tabs.isEnabled())
        self.assertFalse(w.stats_group.isEnabled())
        self.assertEqual(w.stat_spins['endurance'].value(), 0)
        w.go_to(1)
        self.assertEqual(w.current_paragraph, 2)
        w.findChild(QPushButton, 'restartAdventure').click()
        self.assertIsNone(w.current_paragraph)
        w.choice_layout.itemAt(1).widget().setText('Balthazar')
        w.choice_layout.itemAt(2).widget().click()
        self.assertEqual(w.current_paragraph, 1)
        self.assertGreater(w.character['endurance'], 0)
        self.assertNotIn('Trésor', w.character['inventory'])
        self.assertNotIn('cle', w.character.get('book_facts', {}))
        self.assertEqual(w.encounter_history, {})
        self.assertNotIn(2, w.completed_book_events)
        self.assertTrue(w.adventure_tabs.isEnabled())
        self.assertTrue(w.stats_group.isEnabled())
        self.assertFalse(w.redo_stack)

    def test_death_page_survives_font_and_theme_changes(self):
        self.start()
        self.w.set_stat('endurance', 0)
        self.w.change_reader_font_size(2)
        self.assertIn('s’achève ici', self.w.reader.toPlainText())
        self.w.apply_theme(self.w.theme.id)
        self.assertIn('s’achève ici', self.w.reader.toPlainText())

    def test_death_is_restored_and_undo_revives_without_replaying_audio(self):
        self.start()
        w = self.w
        w.set_stat('endurance', 0)
        state = w._snapshot()
        with patch.object(w.sounds, 'play') as sound:
            w.undo_action()
            self.assertTrue(w.adventure_tabs.isEnabled())
            w._restore(state)
            self.assertIn('Fin de l’aventure', w.paragraph_title.text())
            sound.assert_not_called()

    def test_five_slots_metadata_overwrite_confirmation_and_load(self):
        self.start()
        w = self.w
        folder = main.SAVES_DIR
        folder.mkdir(exist_ok=True)
        path = folder / 'emplacement-3.json'
        data = w._save_data()
        w._write_atomic(path, data)
        dialog = SaveSlotsDialog(folder, False, w)
        buttons = [dialog.findChild(QPushButton, f'saveSlot{i}') for i in range(1, 6)]
        self.assertEqual(len(buttons), 5)
        self.assertEqual([b.isEnabled() for b in buttons], [False, False, True, False, False])
        self.assertIn('Éléanor', buttons[2].text())
        self.assertIn(f'Habileté {w.character["habilete"]}', buttons[2].text())
        self.assertIn('Endurance', buttons[2].text())
        self.assertIn('Chance', buttons[2].text())
        buttons[2].click()
        self.assertEqual(dialog.selected_path, str(path))
        saving = SaveSlotsDialog(folder, True, w)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            saving.findChild(QPushButton, 'saveSlot3').click()
        self.assertIsNone(saving.selected_path)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            saving.findChild(QPushButton, 'saveSlot3').click()
        self.assertEqual(saving.selected_path, str(path))
        w.character['name'] = 'Autre'
        self.assertTrue(w.load_game(path, announce=False))
        self.assertEqual(w.character['name'], 'Éléanor')
        self.assertEqual(w.character['initial'], data['character']['initial'])

    def test_legacy_save_and_corrupt_slot(self):
        folder = main.SAVES_DIR
        folder.mkdir(exist_ok=True)
        path = folder / 'emplacement-1.json'
        w = self.w
        w.go_to(1)
        legacy = w._save_data()
        legacy.pop('saved_at')
        legacy.pop('save_name')
        w._write_atomic(path, legacy)
        (folder / 'emplacement-2.json').write_text('{broken')
        dialog = SaveSlotsDialog(folder, False, w)
        self.assertIn('Aventurier sans nom', dialog.findChild(QPushButton, 'saveSlot1').text())
        self.assertFalse(dialog.findChild(QPushButton, 'saveSlot2').isEnabled())
        self.assertTrue(w.load_game(path, announce=False))
        self.assertEqual(w.current_paragraph, 1)
