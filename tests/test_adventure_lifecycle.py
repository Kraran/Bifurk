"""Création du héros, relances, mort, reprise et cinq emplacements.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import tempfile
import unittest
import pymupdf
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QPushButton, QMessageBox

import main
from save_slots import SaveSlotsDialog


class AdventureLifecycleTests(unittest.TestCase):
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
        for key in ('APP_DIR', 'SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            p = patch.object(main, key, self.root if key == 'APP_DIR' else self.root / key)
            p.start()
            self.addCleanup(p.stop)
        main.init_portable_dirs()
        pdf = main.BOOKS_DIR / 'livre.pdf'
        with pymupdf.open() as document:
            document.new_page().insert_text((72, 72), '1\nUne porte.\n2\nUne salle.')
            document.save(pdf)
        self.w = main.MainWindow()
        self.w.paragraphs = {1: 'Une porte.', 2: 'Une salle.'}
        self.w.pdf_path = str(pdf)

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def start(self, name='Éléanor'):
        """Valider un aventurier nommé dans le livre de test pour préparer un scénario en jeu."""
        self.w._show_book_title()
        self.w.creation_name_field.setText(name)
        self.w.creation_start_button.click()

    def test_starting_potion_survives_reroll_and_cannot_be_refilled(self):
        """Le choix accompagne le héros, puis la fiole devient immuable pendant la partie."""
        w = self.w
        w._show_book_title()
        w.findChild(QComboBox, 'startingPotion').setCurrentText("Potion d'Adresse")
        w._reroll_adventurer()
        w._begin_adventure('Éléanor')
        self.assertEqual(w.character['potion'], "Potion d'Adresse")
        self.assertEqual(w.character['potion_doses'], 2)
        self.assertFalse(w.potion_combo.isEnabled())
        for remaining in (1, 0):
            w.character['habilete'] = 1
            w.drink_potion()
            self.assertEqual(w.character['habilete'], w.character['initial']['habilete'])
            self.assertEqual(w.character['potion_doses'], remaining)
        w.change_potion('Potion de Vigueur')
        w.character['habilete'] = 1
        w.drink_potion()
        self.assertEqual(w.character['potion'], "Potion d'Adresse")
        self.assertEqual(w.character['potion_doses'], 0)
        self.assertEqual(w.character['habilete'], 1)
        saved = w._snapshot()
        w._restore(saved)
        self.assertEqual(w.character['potion_doses'], 0)

    def test_fortune_two_doses_raise_initial_luck_each_time(self):
        """Chaque mesure ajoute un point au plafond puis remplit la Chance jusqu'à ce plafond."""
        self.start()
        w = self.w
        w.character.update(potion='Potion de Bonne Fortune', potion_doses=2, chance=1)
        initial = w.character['initial']['chance']
        for dose in (1, 2):
            w.drink_potion()
            self.assertEqual(w.character['initial']['chance'], initial + dose)
            self.assertEqual(w.character['chance'], initial + dose)
            self.assertEqual(w.character['potion_doses'], 2 - dose)
        w.drink_potion()
        self.assertEqual(w.character['initial']['chance'], initial + 2)

    def test_vigor_dose_is_not_wasted_at_full_health_or_after_death(self):
        self.start()
        w = self.w
        w.drink_potion()
        self.assertEqual(w.character['potion_doses'], 2)
        w.character['endurance'] = 1
        w.drink_potion()
        self.assertEqual(w.character['endurance'], w.character['initial']['endurance'])
        self.assertEqual(w.character['potion_doses'], 1)
        w.character['endurance'] = 0
        w.drink_potion()
        self.assertEqual(w.character['potion_doses'], 1)
        self.assertEqual(w.character['endurance'], 0)

    def test_intro_requires_nonblank_name_before_first_paragraph(self):
        self.w._show_book_title()
        field = self.w.creation_name_field
        start = self.w.creation_start_button
        self.assertFalse(start.isEnabled())
        field.setText('   ')
        self.assertFalse(start.isEnabled())
        field.setText('  Éléanor  ')
        start.click()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.character['name'], 'Éléanor')
        self.assertEqual(self.w._save_data()['save_name'], 'Éléanor')

    def test_automatic_creation_uses_book_dice_and_validation_keeps_roll(self):
        with patch('main.random.randint', side_effect=[1, 2, 3, 4]) as dice:
            self.w._show_book_title()
            self.assertEqual(dice.call_count, 4)
            stats = {'habilete': 7, 'endurance': 17, 'chance': 10}
            self.assertEqual(self.w.character['initial'], stats)
            self.assertIn('Endurance 17', self.w.reader.toPlainText())
            self.w.go_to(2)
            self.assertIsNone(self.w.current_paragraph)
            self.w.creation_name_field.setText('Éléanor')
            self.w.creation_start_button.click()
            self.assertEqual(dice.call_count, 4)
        self.assertEqual(self.w.character['initial'], stats)
        self.assertEqual({k: self.w.character[k] for k in stats}, stats)
        self.assertEqual(self.w.character['inventory'], ['Épée', 'Armure de cuir', 'Lanterne'])
        self.assertEqual((self.w.character['provisions'], self.w.character['gold']), (10, 1))
        self.assertFalse(any('Créer un aventurier' in b.text()
                             for b in self.w.findChildren(QPushButton)))

    def test_two_rerolls_maximum_and_last_roll_starts_automatically(self):
        w = self.w
        with patch('main.random.randint', side_effect=[1]*4 + [3]*4 + [6]*4) as dice:
            w._show_book_title()
            w.creation_name_field.setText('Éléanor')
            w.creation_reroll_button.click()
            self.assertIsNone(w.current_paragraph)
            self.assertEqual(w._creation_rerolls, 1)
            self.assertEqual(w.character['initial'], {'habilete': 9, 'endurance': 18, 'chance': 9})
            w.creation_reroll_button.click()
            self.assertEqual(w.current_paragraph, 1)
            self.assertEqual(w.character['initial'], {'habilete': 12, 'endurance': 24, 'chance': 12})
            w._reroll_adventurer()
            self.assertEqual(dice.call_count, 12)

    def test_last_reroll_without_name_is_locked_until_name_is_entered(self):
        w = self.w
        with patch('main.random.randint', return_value=1) as dice:
            w._show_book_title()
            w.creation_reroll_button.click()
            w.creation_reroll_button.click()
            self.assertIsNone(w.current_paragraph)
            self.assertFalse(w.creation_reroll_button.isEnabled())
            self.assertFalse(w.creation_start_button.isEnabled())
            w._reroll_adventurer()
            w.creation_name_field.setText('Éléanor')
            w.creation_start_button.click()
            self.assertEqual(w.current_paragraph, 1)
            self.assertEqual(w.character['initial'], {'habilete': 7, 'endurance': 14, 'chance': 7})
            self.assertEqual(dice.call_count, 12)

    def test_refresh_and_undo_never_grant_extra_rerolls(self):
        w = self.w
        with patch('main.random.randint', return_value=4) as dice:
            w._show_book_title()
            w.creation_name_field.setText('Éléanor')
            w.creation_reroll_button.click()
            w.apply_theme(w.theme.id)
            w.change_reader_font_size(2)
            self.assertEqual(w._creation_rerolls, 1)
            self.assertEqual(w.creation_name_field.text(), 'Éléanor')
            self.assertEqual(dice.call_count, 8)
            w.creation_start_button.click()
            accepted = w.character['initial'].copy()
            w.undo_action()
            self.assertIsNone(w.current_paragraph)
            self.assertFalse(w.creation_reroll_button.isEnabled())
            w._reroll_adventurer()
            self.assertEqual(w.character['initial'], accepted)
            self.assertEqual(dice.call_count, 8)
            w.redo_action()
            self.assertEqual(w.current_paragraph, 1)
            self.assertEqual(dice.call_count, 8)

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
        w.creation_name_field.setText('Balthazar')
        w.creation_start_button.click()
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

    def test_incomplete_format_and_corrupt_slot_are_not_loadable(self):
        folder = main.SAVES_DIR
        folder.mkdir(exist_ok=True)
        path = folder / 'emplacement-1.json'
        self.start()
        data = self.w._save_data()
        data.pop('saved_at')
        self.w._write_atomic(path, data)
        (folder / 'emplacement-2.json').write_text('{broken')
        dialog = SaveSlotsDialog(folder, False, self.w)
        self.assertFalse(dialog.findChild(QPushButton, 'saveSlot1').isEnabled())
        self.assertFalse(dialog.findChild(QPushButton, 'saveSlot2').isEnabled())
        before = self.w._snapshot()
        self.assertFalse(self.w.load_game(path, announce=False))
        self.assertEqual(self.w._snapshot(), before)

    def test_delete_requires_confirmation_and_frees_only_selected_slot(self):
        self.start()
        folder = main.SAVES_DIR
        path = folder/'emplacement-2.json'
        other = folder/'emplacement-3.json'
        self.w._write_atomic(path, self.w._save_data())
        self.w._write_atomic(other, self.w._save_data())
        dialog = SaveSlotsDialog(folder, False, self.w, startup=True)
        self.assertIsNotNone(dialog.findChild(QPushButton, 'newAdventure'))
        self.assertFalse(dialog.findChild(QPushButton, 'deleteSlot1').isEnabled())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            dialog.findChild(QPushButton, 'deleteSlot2').click()
        self.assertTrue(path.is_file())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            dialog.findChild(QPushButton, 'deleteSlot2').click()
        self.assertFalse(path.exists())
        self.assertTrue(other.is_file())
        self.assertFalse(dialog.findChild(QPushButton, 'saveSlot2').isEnabled())
        self.assertFalse(dialog.findChild(QPushButton, 'deleteSlot2').isEnabled())
        self.assertIsNone(dialog.selected_path)
        self.assertFalse(dialog.result())
        dialog.findChild(QPushButton, 'newAdventure').click()
        self.assertTrue(dialog.new_game_requested)

    def test_delete_failure_keeps_slot_available(self):
        self.start()
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        dialog = SaveSlotsDialog(main.SAVES_DIR, True, self.w)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes), \
                patch.object(Path, 'unlink', side_effect=PermissionError('Accès refusé')), \
                patch.object(QMessageBox, 'critical') as error:
            dialog.findChild(QPushButton, 'deleteSlot1').click()
        error.assert_called_once()
        self.assertTrue(path.is_file())
        self.assertTrue(dialog.findChild(QPushButton, 'saveSlot1').isEnabled())

    def test_load_menu_can_start_new_adventure_without_deleting_slots(self):
        self.start()
        w = self.w
        path = main.SAVES_DIR/'emplacement-1.json'
        w._write_atomic(path, w._save_data())
        saved = path.read_bytes()
        w.character['inventory'].append('Trésor')
        w.go_to(2)
        def choose_new(dialog):
            button = dialog.findChild(QPushButton, 'newAdventure')
            self.assertIsNotNone(button)
            button.click()
            return dialog.result()
        with patch.object(SaveSlotsDialog, 'exec', choose_new), \
                patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes) as confirm:
            w.load_game()
        confirm.assert_called_once()
        self.assertIsNone(w.current_paragraph)
        self.assertEqual(w._creation_rerolls, 0)
        self.assertIsNotNone(w._adventurer_draft)
        self.assertNotIn('Trésor', w.character['inventory'])
        self.assertEqual(path.read_bytes(), saved)
        w.creation_name_field.setText('Balthazar')
        w.creation_start_button.click()
        self.assertEqual(w.current_paragraph, 1)
        self.assertEqual(w.character['name'], 'Balthazar')
        self.assertEqual(w.visited_paragraphs, [1])
        self.assertEqual(w.encounter_history, {})
        self.assertEqual(path.read_bytes(), saved)

    def test_declining_new_game_keeps_load_menu_and_current_adventure(self):
        self.start()
        self.w.go_to(2)
        before = self.w._snapshot()
        dialog = SaveSlotsDialog(main.SAVES_DIR, False, self.w)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No) as confirm:
            dialog.findChild(QPushButton, 'newAdventure').click()
        confirm.assert_called_once()
        self.assertFalse(dialog.new_game_requested)
        self.assertEqual(dialog.result(), 0)
        self.assertEqual(self.w._snapshot(), before)
        startup = SaveSlotsDialog(main.SAVES_DIR, False, self.w, startup=True)
        with patch.object(QMessageBox, 'question') as confirm:
            startup.findChild(QPushButton, 'newAdventure').click()
        confirm.assert_not_called()
        self.assertTrue(startup.new_game_requested)
