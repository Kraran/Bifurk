"""Présentation multi-grimoires avec PDF synthétiques ; contrôle privé conditionnel de l'édition."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

import main
from grimoire_library import GrimoireLibraryDialog, imported_grimoires
from grimoire_modules.registry import available_modules, module_for_pdf, pdf_digest
from save_slots import SaveSlotsDialog


class ForetPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.modules = {m.engine: m for m in available_modules()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for key, path in {'APP_DIR': self.root, 'BOOKS_DIR': self.root/'donnees/grimoires',
                          'SAVES_DIR': self.root/'donnees/sauvegardes',
                          'SETTINGS_DIR': self.root/'donnees/parametres'}.items():
            mock = patch.object(main, key, path)
            mock.start()
            self.addCleanup(mock.stop)
        main.init_portable_dirs()
        self.sources = {}
        for name in ('foret', 'sorcier'):
            path = self.root / f'{name}.pdf'
            with pymupdf.open() as document:
                for index in range(170):
                    page = document.new_page(width=504.6, height=842)
                    if index == 0:
                        page.draw_rect(page.rect, color=(.3,.4,.2), fill=(.7,.7,.4))
                    if index == 18:
                        page.insert_text((30,40), '1\nUne foret. Rendez-vous au 2.\n2\nUne clairiere.\n86\nUne tour.\n350\nUn chemin.')
                document.save(path)
            self.sources[name] = path
        def recognize(path):
            return self.modules['foret-1983' if 'foret' in Path(path).name else 'sorcier-1982']
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, side_effect=recognize)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information','warning','critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        mock = patch.object(self.w, '_roll', side_effect=lambda count, *a, **k: ([3]*count, 3*count))
        self.roll = mock.start()
        self.addCleanup(mock.stop)

    def open(self, name='foret'):
        self.w.open_pdf(self.sources[name], startup=True)

    def start(self):
        self.w._begin_adventure('Eldan')

    def test_cover_title_starting_resources_and_preparation_notice(self):
        self.open()
        self.assertEqual(self.w.book_module.id, 'foret_malediction_1983')
        self.assertEqual(self.w.book_label.text(), 'La Forêt de la Malédiction')
        self.assertIn('La Forêt de la Malédiction', self.w.reader.toPlainText())
        self.assertIn('préparation', self.w.reader.toPlainText())
        self.assertEqual(self.w.scene_entry['type'], 'couverture')
        self.assertTrue(self.w.scene_art.is_book_art)
        self.assertIsNotNone(self.w.findChild(QPushButton, 'readPrologue'))
        self.assertEqual(self.w.character['gold'], 30)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)

    def test_analysed_title_and_corrected_cave_route_are_presented_without_effects(self):
        self.open()
        self.start()
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.assertEqual(self.w.paragraph_title.text(), 'La tour de Yaztromo')
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any('Suivre le mage' in button.text() for button in buttons))
        self.w.paragraphs[267] = 'Rendez-vous au 196. Sinon rendez-vous au 25.'
        self.w.paragraphs[196] = 'La caverne.'
        self.w.paragraphs[25] = 'Une bifurcation.'
        self.w.go_to(267)
        self.assertNotIn('href="paragraph:1"', self.w.reader.toHtml())
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any(button.isEnabled() and '196' in button.text() for button in buttons))
        self.assertFalse(any('confirmer' in button.text() for button in buttons))
        self.assertIn('paragraph:196',self.w.reader.toHtml())
        self.assertEqual(self.w.character, before)
        self.assertEqual(self.roll.call_count, dice)

    def test_shop_purchases_are_saved_and_undoable_without_free_charges(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs[261] = 'Les achats.'
        self.w.go_to(261)
        before = self.w._snapshot()
        self.w.perform_foret_action('buy', ('Bottes à Bondir', 2))
        self.assertEqual(self.w.character['gold'], 26)
        self.assertEqual(rules.available(self.w.character, 'Bottes de Saut'), 2)
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.w._restore(before)
        self.assertEqual(rules.available(self.w.character, 'Bottes à Bondir'), 0)
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(rules.available(self.w.character, 'Bottes à Bondir'), 2)

    def test_pair_can_change_target_each_round_and_popup_reads_both_enemies(self):
        from combat_dialog import CombatDialog
        self.open()
        self.start()
        self.w.paragraphs[377] = 'Deux adversaires.'
        self.w.go_to(377)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            self.w.perform_foret_action('target', 1)
            self.w.combat_round()
            self.assertEqual([enemy['stamina'] for enemy in self.w._foret_combat()['groups'][0]], [5,4])
            self.w.perform_foret_action('target', 0)
            self.w.combat_round()
        self.assertEqual([enemy['stamina'] for enemy in self.w._foret_combat()['groups'][0]], [3,4])
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual([enemy['stamina'] for enemy in dialog.roster], [3,4])
        self.assertEqual(self.w._foret_combat()['assaults'], 2)

    def test_rock_beast_flee_is_enabled_after_exactly_three_assaults(self):
        self.open()
        self.start()
        self.w.character['habilete'] = 8
        self.w.paragraphs.update({84:'Une bête.',245:'Le chemin.'})
        self.w.go_to(84)
        for index in range(3):
            self.assertFalse(self.w.can_flee_combat())
            self.w.combat_round()
        self.assertTrue(self.w.can_flee_combat())
        before = self.w.character['endurance']
        with patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.escape_scripted_combat(84)
        self.assertEqual(self.w.current_paragraph,245)
        self.assertEqual(self.w.character['endurance'],before-2)

    def test_ghoul_fourth_wounding_hit_ends_adventure(self):
        self.open()
        self.start()
        self.w.character['habilete'] = 1
        self.w.character['endurance'] = 20
        self.w.paragraphs[227] = 'Une goule.'
        self.w.go_to(227)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            for index in range(3):
                self.w.combat_round()
                self.assertGreater(self.w.character['endurance'],0)
            self.w.combat_round()
        self.assertEqual(self.w.character['endurance'],0)
        self.assertFalse(self.w.combat_available())

    def test_lethal_whip_stops_normal_damage_and_further_dice(self):
        self.open()
        self.start()
        self.w.character['endurance'] = 1
        self.w.paragraphs[107] = 'Un démon.'
        self.w.go_to(107)
        with patch.object(self.w, '_roll', side_effect=[([3,3],6),([3,3],6),([1],1)]) as roll, \
                patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.combat_round()
        self.assertEqual(roll.call_count,3)
        self.assertEqual(self.w.character['endurance'],0)
        self.assertEqual(self.w._foret_combat()['groups'][0][0]['stamina'],10)

    def test_popup_does_not_declare_victory_after_only_one_pygmy_dies(self):
        from combat_dialog import CombatDialog
        from unittest.mock import Mock
        self.open()
        self.start()
        self.w.paragraphs[377] = 'Deux adversaires.'
        self.w.go_to(377)
        self.w._foret_combat()['groups'][0][0]['stamina'] = 2
        self.w._foret_sync_enemy()
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        dialog.present_roll = Mock()
        dialog.choose_luck = Mock(return_value=False)
        self.w._combat_dialog = dialog
        self.addCleanup(setattr, self.w, '_combat_dialog', None)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            dialog._run(self.w.combat_round)
        self.assertIsNone(dialog.outcome)
        self.assertEqual([enemy['stamina'] for enemy in dialog.roster],[0,6])
        self.assertEqual(self.w.enemy_name.text(),'Pygmée B')

    def test_flee_platform_applies_both_escape_wound_and_fall(self):
        self.open()
        self.start()
        self.w.paragraphs.update({352:'Un adversaire.',156:'Une chute.'})
        self.w.go_to(352)
        before = self.w.character['endurance']
        with patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.escape_scripted_combat(352)
        self.assertEqual(self.w.character['endurance'],before-5)
        snapshot = self.w._snapshot()
        self.w._restore(snapshot)
        self.assertEqual(self.w.character['endurance'],before-5)

    def test_lethal_fever_does_not_roll_dice(self):
        self.open()
        self.start()
        self.w.paragraphs[259] = 'La fièvre.'
        self.w.go_to(259)
        self.w.character['endurance'] = 3
        dice = self.roll.call_count
        self.w.perform_foret_action('fever')
        self.assertEqual(self.roll.call_count,dice)
        self.assertEqual(self.w.character['endurance'],0)

    def test_popup_full_hunter_sequence_only_ends_after_last_pair(self):
        from combat_dialog import CombatDialog
        from unittest.mock import Mock
        self.open()
        self.start()
        self.w.character['habilete'] = 20
        self.w.paragraphs.update({96:'Les chasseurs.',62:'Après les chasseurs.'})
        self.w.go_to(96)
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        dialog.present_roll = Mock()
        self.w._combat_dialog = dialog
        self.addCleanup(setattr,self.w,'_combat_dialog',None)
        with patch.object(self.w,'_assault_luck_choice',return_value=QMessageBox.No):
            for _ in range(30):
                if dialog.outcome:
                    break
                dialog._run(self.w.combat_round)
        self.assertEqual(dialog.outcome,'Victoire')
        self.assertEqual(self.w.current_paragraph,62)
        self.assertTrue(all(enemy['stamina'] == 0 for enemy in dialog.roster))

    def test_manual_discard_removes_purchase_charge_and_cursed_ring_stays_locked(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs[261] = 'Les achats.'
        self.w.go_to(261)
        self.w.perform_foret_action('buy',('Anneau de Lumière',1))
        row = self.w.character['inventory'].index('Anneau de Lumière')
        self.w.inventory_list.setCurrentRow(row)
        self.w.remove_item()
        self.assertEqual(rules.peek(self.w.character)['charges']['Anneau de Lumière'],0)
        self.w.paragraphs[133] = 'Un anneau.'
        self.w.go_to(133)
        self.w.perform_foret_action('entry')
        row = self.w.character['inventory'].index('Anneau de Lenteur')
        self.w.inventory_list.setCurrentRow(row)
        self.w.remove_item()
        self.assertIn('Anneau de Lenteur',self.w.character['inventory'])

    def test_return_to_yaztromo_requires_a_new_luck_test_each_visit(self):
        self.open()
        self.start()
        self.w.paragraphs[98] = 'Le retour dangereux.'
        self.w.character['chance'] = 10
        dice = self.roll.call_count
        for _ in range(2):
            self.w.go_to(98)
            self.assertNotIn(1,self.w._reading_link_targets())
            self.w.perform_foret_action('ambush')
            self.assertEqual(self.w.current_paragraph,1)
        self.assertEqual(self.roll.call_count,dice+2)
        self.assertEqual(self.w.character['chance'],8)
        self.assertEqual(self.w.character['gold'],30)

    def test_confirmed_eel_is_playable_and_victory_goes_to_131(self):
        self.open()
        self.start()
        self.w.paragraphs.update({186:'Une anguille.',131:'Après la rivière.'})
        self.w.go_to(186)
        self.assertTrue(self.w.combat_available())
        self.assertEqual(self.w.enemy_name.text(),'Anguille Carnivore')
        self.assertEqual((self.w.enemy_skill.value(),self.w.enemy_endurance.value()),(5,4))
        self.assertFalse(self.w.can_flee_combat())
        self.assertNotIn(131,self.w._reading_link_targets())
        with patch.object(self.w,'_assault_luck_choice',return_value=QMessageBox.No):
            self.w.combat_round()
            self.assertEqual(self.w.current_paragraph,186)
            self.w.combat_round()
        self.assertEqual(self.w.current_paragraph,131)

    def test_enchanted_weapon_in_selector_and_removal_never_changes_initial_skill(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.character['habilete'] = 6
        self.w.character['initial']['habilete'] = 10
        self.w.paragraphs.update({70:'La lame.',334:'Le chemin.'})
        self.w.go_to(70)
        self.w.perform_foret_action('enchanted_sword')
        self.assertEqual(self.w._ff_combat_profile()['skill'],8)
        self.assertEqual(self.w.weapon_combo.currentText(),rules.ENCHANTED_SWORD)
        self.w.change_weapon('Épée')
        self.assertEqual(self.w._ff_combat_profile()['skill'],6)
        self.w.change_weapon(rules.ENCHANTED_SWORD)
        row = self.w.character['inventory'].index(rules.ENCHANTED_SWORD)
        self.w.inventory_list.setCurrentRow(row)
        self.w.remove_item()
        self.assertEqual(self.w._ff_combat_profile()['skill'],6)
        self.assertEqual(self.w.character['initial']['habilete'],10)
        self.assertFalse(self.w.character.get('magic_sword_bonus_active',False))

    def test_gnome_payment_returns_weapon_and_loading_keeps_payment(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs.update({192:'Le gnome.',12:'Le tarif.'})
        self.w.go_to(192)
        self.w.perform_foret_action('gnome_sword')
        self.assertNotIn('Épée',self.w.character['inventory'])
        self.w.go_to(12)
        self.assertEqual(self.w._reading_link_targets(),set())
        self.w.perform_foret_action('payment',(10,[]))
        self.assertIn('Épée',self.w.character['inventory'])
        self.assertEqual(self.w.character['gold'],20)
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path,self.w._save_data())
        self.assertTrue(self.w.load_game(path,announce=False))
        self.assertTrue(rules.payment_resolved(self.w.character,12))
        self.w.perform_foret_action('payment',(10,[]))
        self.assertEqual(self.w.character['gold'],20)

    def test_lantern_luck_failure_requires_item_choice_and_cannot_be_replayed(self):
        self.open()
        self.start()
        self.w.paragraphs.update({356:'La lampe.',395:'Un éclair.',370:'Une perte.',231:'Le chemin.'})
        self.w.go_to(356)
        self.w.perform_foret_action('entry')
        self.w.character['chance'] = 1
        before = self.w.character['endurance']
        self.w.go_to(395)
        self.w.perform_foret_action('lantern')
        self.assertEqual(self.w.current_paragraph,370)
        self.assertEqual(self.w.character['endurance'],before-3)
        self.assertEqual(self.w._reading_link_targets(),set())
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('Lanterne',False)):
            self.w.perform_foret_action('lost_item')
        self.assertEqual(self.w.current_paragraph,370)
        self.assertIn('Lanterne',self.w.character['inventory'])
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('Lanterne',True)):
            self.w.perform_foret_action('lost_item')
        self.assertEqual(self.w.current_paragraph,231)
        self.assertNotIn('Lanterne',self.w.character['inventory'])
        snapshot = self.w._snapshot()
        self.w._restore(snapshot)
        self.assertEqual(self.w.character['endurance'],before-3)

    def test_leaving_lantern_behind_does_not_keep_a_free_wish(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs.update({356:'La lampe.',231:'Le chemin.',34:'Le génie.'})
        self.w.go_to(356)
        self.w.perform_foret_action('entry')
        self.w.go_to(231)
        self.assertNotIn('Lanterne magique',self.w.character['inventory'])
        self.w.go_to(356)
        self.assertNotIn(34,self.w._reading_link_targets())
        self.assertTrue(rules.entry_resolved(self.w.character,356))

    def test_repeat_meals_allowed_outside_combat_but_not_in_pending_combat(self):
        self.open()
        self.start()
        self.w.character['initial']['endurance'] = 24
        self.w.character['endurance'] = 5
        self.w.character['provisions'] = 10
        self.w.use_care('meal')
        self.w.use_care('meal')
        self.assertEqual((self.w.character['endurance'],self.w.character['provisions']),(13,8))
        self.w.paragraphs[377] = 'Deux adversaires.'
        self.w.go_to(377)
        self.assertFalse(self.w.care_options()[1]['enabled'])
        self.w.use_care('meal')
        self.assertEqual(self.w.character['provisions'],8)

    def test_dart_luck_is_awarded_even_when_optional_treasure_is_left(self):
        self.open()
        self.start()
        self.w.paragraphs.update({219:'Une fléchette.',300:'Le chemin.'})
        self.w.character['chance'] -= 2
        before = self.w.character['chance']
        self.w.go_to(219)
        self.w.perform_foret_action('entry')
        self.assertEqual(self.w.character['chance'],before+1)
        self.assertNotIn('Fléchette d’argent (valeur 5 Or)',self.w.character['inventory'])
        self.assertIn(300,self.w._reading_link_targets())

    def test_prologue_is_private_page_view_and_never_awards_resources_twice(self):
        self.open()
        before = self.w._snapshot()
        dice = self.roll.call_count
        self.w.show_prologue()
        dialog = self.w.prologue_dialog
        self.assertEqual((dialog.first_page, dialog.last_page, dialog.pages.count()), (14,16,3))
        dialog.pages.setCurrentIndex(2)
        self.assertEqual(dialog.viewer.accessibleName(), 'Prologue — page PDF 16')
        self.w.show_prologue()
        self.assertIs(self.w.prologue_dialog, dialog)
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.roll.call_count, dice)

    def test_rules_interval_and_old_book_views_close_when_switching(self):
        self.open()
        self.w.show_rules()
        rules = self.w.rules_dialog
        self.assertEqual((rules.first_page, rules.last_page), (4,13))
        self.w.show_prologue()
        prologue = self.w.prologue_dialog
        self.open('sorcier')
        self.assertFalse(rules.isVisible())
        self.assertFalse(prologue.isVisible())
        self.assertIsNone(self.w.rules_dialog)
        self.assertIsNone(self.w.prologue_dialog)
        self.assertEqual(self.w.character['gold'], 1)
        self.assertNotIn('Carte de Yaztromo', self.w.character['inventory'])
        self.w.show_rules()
        self.assertEqual((self.w.rules_dialog.first_page, self.w.rules_dialog.last_page), (3,14))

    def test_reroll_start_and_save_load_do_not_reapply_starting_gold(self):
        self.open()
        self.w._reroll_adventurer()
        self.assertEqual(self.w.character['gold'], 30)
        self.start()
        self.w.character['gold'] = 12
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.open('sorcier')
        self.start()
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.book_module.engine, 'foret-1983')
        self.assertEqual(self.w.character['gold'], 12)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.book_event_catalogue['reviewed_count'], 400)
        self.assertEqual(self.w.preferences['last_book'], Path(self.w.pdf_path).name)

    def test_consultation_never_activates_sorcier_paragraph_rules(self):
        self.open()
        self.start()
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.w.go_to(86)
        self.w.go_to(350)
        self.w.combat_round()
        self.assertEqual(self.w.character, before)
        self.assertIsNone(self.w.crocodile_combat)
        self.assertIsNone(self.w.piranha_combat)
        self.assertEqual(self.w.completed_book_events, set())
        self.assertFalse(self.w.combat_button.isEnabled())
        self.assertEqual(self.roll.call_count, dice)
        self.assertIsNone(self.w.scene_entry)
        self.assertFalse(self.w.scene_art.is_book_art)
        self.assertTrue(self.w.scene_art.background_art.isNull())

    def test_library_lists_both_covers_and_preselects_last_book(self):
        self.open('sorcier')
        self.open()
        books = imported_grimoires(main.BOOKS_DIR)
        self.assertEqual(len(books), 2)
        dialog = GrimoireLibraryDialog(books, self.w.pdf_path, self.w)
        try:
            self.assertIn('La Forêt', dialog.books.currentItem().text())
            self.assertFalse(dialog.books.currentItem().icon().isNull())
            self.assertIn('préparation', dialog.books.currentItem().text())
            dialog.choose()
            self.assertEqual(dialog.selected_path, self.w.pdf_path)
        finally:
            dialog.deleteLater()

    def test_library_cancel_keeps_game_and_two_book_new_game_opens_selected_module(self):
        self.open('sorcier')
        sorcier = self.w.pdf_path
        self.open()
        self.start()
        before = self.w._snapshot()
        with patch.object(self.w, '_select_grimoire', return_value=None):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)), \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)) as selector:
            self.w._start_new_game()
        selector.assert_called_once()
        self.assertEqual(self.w.book_module.engine, 'sorcier-1982')
        self.assertIsNone(self.w.current_paragraph)

    def test_save_slots_identify_the_adventure_without_adding_text_rows(self):
        self.open()
        self.start()
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        dialog = SaveSlotsDialog(main.SAVES_DIR, False, self.w)
        try:
            button = dialog.findChild(QPushButton, 'saveSlot1')
            self.assertIn('La Forêt de la Malédiction', button.text().splitlines()[0])
            self.assertEqual(len(button.text().splitlines()), 3)
        finally:
            dialog.deleteLater()


class ForetEditionContractTests(unittest.TestCase):
    def test_presentation_catalogues_are_honest_about_pending_paragraphs(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        events = module.catalogue('events')
        self.assertEqual(module.rules_pages, (4,13))
        self.assertEqual(module.intro_pages, (14,16))
        self.assertEqual(module.status, 'preview')
        self.assertEqual(len(events['paragraphs']), 400)
        self.assertEqual(events['review_pending'], [])
        self.assertEqual(events['automation_pending'], list(range(1,401)))

    def test_private_pdf_is_recognized_and_cover_crop_fits_real_page(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        root = Path(__file__).resolve().parents[1]
        candidates = [*root.glob('*.pdf'), *(root/'donnees/grimoires').glob('*.pdf'),
                      *(root.parent/'attachments').rglob('*.pdf')]
        path = next((p for p in candidates if pdf_digest(p) == module.pdf_sha256), None)
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        self.assertEqual(module_for_pdf(path).id, module.id)
        with pymupdf.open(path) as document:
            self.assertEqual(len(document), 170)
            rect = pymupdf.Rect(module.catalogue('illustrations')['illustrations'][0]['rect'])
            self.assertTrue(document[0].rect.contains(rect))
