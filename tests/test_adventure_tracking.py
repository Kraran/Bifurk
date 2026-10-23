"""Suivi et confirmations des interventions, sans modifier les règles normales."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
import main
from adventure_tracking import new_tracking, read_tracking
from save_slots import SaveSlotsDialog, read_save


class AdventureTrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for key in ('SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            replacement = patch.object(main, key, self.root/key)
            replacement.start()
            self.addCleanup(replacement.stop)
        main.init_portable_dirs()
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        self.w.paragraphs = {1:'Un chemin.', 2:'Une salle.', 3:'Une porte.'}
        self.w.character['name'] = 'Eldan'
        self.w.current_paragraph = 1
        self.w.adventure_tracking = new_tracking()
        self.w._refresh_character()
        self.w._update_tracking_badge()

    def confirm(self, yes=True):
        return patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes if yes else QMessageBox.No)

    def test_refusing_stat_edit_restores_widget_without_mark_or_history(self):
        before = self.w._snapshot()
        with self.confirm(False) as question:
            self.w.stat_spins['endurance'].setValue(3)
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.w.stat_spins['endurance'].value(), before['character']['endurance'])
        self.assertEqual(self.w.adventure_tracking, new_tracking())
        self.assertEqual(self.w.undo_stack, [])
        self.assertEqual(question.call_args.args[-1], QMessageBox.No)

    def test_mark_survives_undo_redo_and_restore_and_autosave(self):
        pdf = self.root/'livre.pdf'
        pdf.write_bytes(b'PDF prive de test')
        self.w.pdf_path = str(pdf)
        with self.confirm():
            self.w.manual_set_stat('endurance', 3)
            self.assertEqual(self.w.adventure_tracking['status'], 'assisted')
            self.w.manual_history(False)
            self.assertEqual(self.w.character['endurance'], 20)
            self.w.manual_history(True)
        self.assertEqual(self.w.character['endurance'], 3)
        self.assertEqual(len(self.w.adventure_tracking['events']), 3)
        self.w._restore(self.w.undo_stack[0][1])
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')
        data = read_save(main.SAVES_DIR/'autosave.json')
        self.assertEqual(data['adventure_tracking']['status'], 'assisted')
        self.assertNotIn('adventure_tracking', self.w._snapshot())

    def test_travel_inventory_and_enemy_edits_confirm_and_log(self):
        with self.confirm(False):
            self.assertFalse(self.w.manual_travel(2))
        self.assertEqual(self.w.current_paragraph, 1)
        with self.confirm():
            self.assertTrue(self.w.manual_travel(2))
            self.w.item_input.setText('Objet de test')
            self.w.manual_inventory(False)
            self.w.inventory_list.setCurrentRow(len(self.w.character['inventory'])-1)
            self.w.manual_inventory(True)
            self.w._enemy_edit_before = self.w._snapshot()
            self.w.enemy_skill.setValue(12)
            self.w._finish_manual_enemy_edit()
        self.assertEqual(self.w.current_paragraph, 2)
        self.assertNotIn('Objet de test', self.w.character['inventory'])
        self.assertEqual(self.w.enemy_skill.value(), 12)
        self.assertEqual(len(self.w.adventure_tracking['events']), 4)

    def test_normal_actions_and_noops_do_not_mark(self):
        with patch.object(QMessageBox, 'question') as question:
            self.w.go_to(2)
            self.w._refresh_character()
            self.w.manual_travel(2)
            self.w.manual_travel(999)
            self.w.manual_inventory(False)
            self.w.manual_set_stat('endurance', 20)
            question.assert_not_called()
        self.assertEqual(self.w.adventure_tracking, new_tracking())

        with self.confirm():
            self.assertFalse(self.w._run_assisted('Sans effet', lambda: None))
        self.assertEqual(self.w.adventure_tracking, new_tracking())

    def test_map_confirmation_can_be_cancelled_without_closing_the_map(self):
        from exploration_map import ExplorationMapDialog
        self.w.visited_paragraphs = [1, 2]
        dialog = ExplorationMapDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog.select_place(2)
        with self.confirm(False):
            dialog.travel()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.adventure_tracking['status'], 'tracked')
        with self.confirm():
            dialog.travel()
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self.w.current_paragraph, 2)
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')

    def test_save_load_legacy_and_earlier_save_are_independent(self):
        base = self.w._save_data()
        with self.confirm():
            self.w.manual_set_stat('endurance', 3)
        assisted = self.w._save_data()
        path = main.SAVES_DIR/'emplacement-1.json'
        for data, status in ((assisted,'assisted'), (base,'tracked')):
            self.w._write_atomic(path, data)
            self.assertTrue(self.w.load_game(path, announce=False))
            self.assertEqual(self.w.adventure_tracking['status'], status)
            dialog = SaveSlotsDialog(main.SAVES_DIR, False, self.w)
            self.addCleanup(dialog.deleteLater)
            self.addCleanup(dialog.close)
            from adventure_tracking import LABELS
            self.assertIn(LABELS[status], dialog.findChild(main.QPushButton, 'saveSlot1').text())
        base.pop('adventure_tracking')
        base['character'].pop('name', None)  # Ancien héros sans nom, partie déjà commencée.
        self.w._write_atomic(path, base)
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.adventure_tracking['status'], 'unverified')
        with self.confirm():
            self.w.manual_set_stat('endurance', 2)
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')

    def test_new_adventure_resets_mark_and_invalid_tracking_is_rejected(self):
        self.w.pdf_path = str(self.root/'livre.pdf')
        with self.confirm():
            self.w.manual_set_stat('endurance', 3)
        with patch.object(self.w, '_roll_adventurer', return_value=copy.deepcopy(self.w.character['initial'])):
            self.w._restart_adventure()
        self.w._begin_adventure('Nouvel aventurier')
        self.assertEqual(self.w.adventure_tracking, new_tracking())
        bad = self.w._save_data()
        bad['adventure_tracking'] = {'version':1, 'status':'tracked', 'events':[{'reason':'X','at':'2026-10-23'}]}
        path = self.root/'invalide.json'
        self.w._write_atomic(path, bad)
        with self.assertRaises(ValueError):
            read_save(path)
        self.assertEqual(read_tracking(None)['status'], 'unverified')

    def test_undo_back_to_creation_cannot_clear_mark_by_starting_again(self):
        self.w.current_paragraph = None
        self.w._adventurer_draft = copy.deepcopy(self.w.character['initial'])
        self.w._begin_adventure('Eldan')
        with self.confirm():
            self.w.manual_history(False)
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')
        self.assertIsNotNone(self.w._adventurer_draft)
        self.w._begin_adventure('Eldan')
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')
