"""Fin de la revue 351–400 : règles, protections et reprise des sauvegardes."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as bifurk
from book_events import DATA_PATH, available_routes, available_options, combat_skill, condition_met
from navigation import destinations
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog


class FinalEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.w = bifurk.MainWindow()
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.paragraphs = {n: f'Passage de test {n}.' for n in range(1, 401)}
        for name, value in [('information', QMessageBox.Ok), ('warning', QMessageBox.Ok),
                            ('question', QMessageBox.No), ('exec', QMessageBox.No)]:
            mock = patch.object(QMessageBox, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def win(self):
        with patch.object(self.w, '_roll', side_effect=[([1, 1], 2), ([6, 6], 12)]):
            self.w.combat_round()

    def test_catalogue_has_400_verified_paragraphs_and_no_pending(self):
        self.assertEqual(self.catalogue['reviewed_count'], 400)
        self.assertEqual(self.catalogue['review_pending'], [])
        self.assertEqual({int(n) for n in self.catalogue['paragraphs']}, set(range(1, 401)))
        self.assertTrue(all(e['status'] == 'verifie' for e in self.catalogue['paragraphs'].values()))

    def test_final_routes_match_the_private_pdf(self):
        pdf = next(ROOT.glob('*.pdf'), None)
        if pdf is None:
            self.skipTest('PDF privé absent')
        self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), self.catalogue['pdf_sha256'])
        texts = bifurk.extract_paragraphs(pdf)
        for n in range(351, 401):
            e = self.catalogue['paragraphs'][str(n)]
            targets = {r['target'] for r in e.get('routes', [])}
            targets |= {b['target'] for b in e.get('roll', {}).get('branches', [])}
            combat = e.get('combat', {})
            targets |= {combat[k] for k in ('victory_target', 'escape_target') if combat.get(k)}
            if n == 379:
                targets.add(139)
            self.assertEqual(targets, {t for _, _, t in destinations(texts[n])}, f'§{n}')

    def test_four_way_crossroads_354_and_359(self):
        w = self.w
        for n, expected in [(354, [308, 52, 14, 234]), (359, [190, 94, 121, 385])]:
            w.go_to(n)
            self.assertEqual(w.choice_layout.count(), 4)
            self.assertEqual([r['target'] for r in available_routes(w.character, self.catalogue['paragraphs'][str(n)])], expected)
            w.follow_catalogue_choice(expected[2])
            self.assertEqual(w.current_paragraph, expected[2])
            w.undo_action()
            self.assertEqual(w.current_paragraph, n)

    def test_vampire_352_and_noise_355_cost_once_and_undo(self):
        w = self.w
        for n, key in [(352, 'endurance'), (355, 'habilete')]:
            old = w.character[key]
            w.go_to(n)
            self.assertEqual(w.character[key], old - 1)
            w.go_to(n)
            self.assertEqual(w.character[key], old - 1)
            w.undo_action()
            self.assertEqual(w.character[key], old)

    def test_gas361_acquires_key_before_roll_and_does_not_duplicate_it(self):
        w = self.w
        w.go_to(361)
        self.assertIn('Clé 125', w.character['inventory'])
        w.go_to(35)
        w.go_to(361)
        self.assertEqual(w.character['inventory'].count('Clé 125'), 1)
        with patch.object(w, '_roll') as roll:
            w.follow_link(QUrl('paragraph:136'))
            w.follow_catalogue_choice(136)
        roll.assert_not_called()
        self.assertEqual(w.current_paragraph, 361)

    def test_gas361_all_totals_use_skill_and_do_not_spend_luck(self):
        w = self.w
        w.go_to(361)
        for total in range(2, 13):
            w.character.update(habilete=8, endurance=10, chance=3)
            with patch.object(w, '_roll', return_value=([total], total)):
                w.resolve_book_roll(361)
            self.assertEqual(w.current_paragraph, 136)
            self.assertEqual((w.character['habilete'], w.character['endurance']), (8, 10) if total <= 8 else (6, 7))
            self.assertEqual(w.character['chance'], 3)
            w.undo_action()
            self.assertEqual(w.current_paragraph, 361)
            self.assertEqual((w.character['habilete'], w.character['endurance']), (8, 10))
            self.assertNotIn(361, w.completed_book_events)
            self.assertIn('Clé 125', w.character['inventory'])

    def test_gas361_fatal_inhalation_blocks_destination(self):
        w = self.w
        w.go_to(361)
        w.character['endurance'] = 3
        with patch.object(w, '_roll', return_value=([6, 6], 12)):
            w.resolve_book_roll(361)
        self.assertEqual(w.character['endurance'], 0)
        self.assertEqual(w.current_paragraph, 361)
        w.follow_link(QUrl('paragraph:136'))
        self.assertEqual(w.current_paragraph, 361)

    def test_gas361_missing_destination_keeps_roll_unresolved(self):
        w = self.w
        w.go_to(361)
        del w.paragraphs[136]
        before = w._snapshot()
        with patch.object(w, '_roll', return_value=([6, 6], 12)):
            w.resolve_book_roll(361)
        self.assertEqual(w._snapshot(), before)

    def test_five_goblins_sequence_exact_profiles_and_victory(self):
        w = self.w
        w.go_to(365)
        for index, (h, e) in enumerate([(6, 5), (6, 5), (4, 4), (3, 4), (2, 4)]):
            self.assertEqual(w.book_combat_sequence['index'], index)
            self.assertEqual((w.enemy_skill.value(), w.enemy_endurance.value()), (h, e))
            w.follow_link(QUrl('paragraph:183'))
            self.assertEqual(w.current_paragraph, 365)
            w.enemy_endurance.setValue(2)
            self.win()
        self.assertEqual(w.current_paragraph, 183)
        self.assertIsNone(w.book_combat_sequence)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 365)
        self.assertEqual(w.book_combat_sequence['index'], 4)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_goblin_sequence_escape_is_paid_and_restored_by_undo(self):
        w = self.w
        w.go_to(365)
        w.enemy_endurance.setValue(2)
        self.win()
        w.escape_scripted_combat(365)
        self.assertEqual(w.current_paragraph, 237)
        self.assertEqual(w.character['endurance'], 18)
        self.assertIsNone(w.book_combat_sequence)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 365)
        self.assertEqual(w.book_combat_sequence['index'], 1)
        self.assertEqual(w.enemy_endurance.value(), 5)
        self.assertEqual(w.character['endurance'], 20)

    def test_dragon371_and_skeleton374_rewards_optional_meals(self):
        w = self.w
        for n, gain in [(371, 3), (374, 2)]:
            w.character.update(chance=1, endurance=10)
            w.go_to(n)
            self.assertEqual(w.character['chance'], 1 + gain)
            self.assertEqual((w.character['endurance'], w.character['provisions']), (10, 10))
            w.eat_meal()
            self.assertEqual((w.character['endurance'], w.character['provisions']), (14, 9))
            w.undo_action()
            self.assertEqual((w.character['endurance'], w.character['provisions']), (10, 10))
            self.assertEqual(w.character['chance'], 1 + gain)

    def test_imp377_mandatory_fight_unlocks196_and_once_only_gold(self):
        w = self.w
        w.go_to(377)
        self.assertEqual((w.enemy_skill.value(), w.enemy_endurance.value()), (5, 7))
        w.follow_link(QUrl('paragraph:196'))
        self.assertEqual(w.current_paragraph, 377)
        w.enemy_endurance.setValue(2)
        self.win()
        self.assertEqual(w.current_paragraph, 196)
        self.assertEqual(w.character['gold'], 6)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 377)
        self.assertEqual(w.character['gold'], 1)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_chest379_luck_uses_old_score_destroys_only_equipped_sword(self):
        w = self.w
        w.character['inventory'].append('Épée trouvée dans la rivière')
        w.character['equipped_weapon'] = 'Épée'
        w.character['chance'] = 7
        w.go_to(379)
        w.follow_link(QUrl('paragraph:139'))
        self.assertEqual(w.current_paragraph, 379)
        with patch.object(w, '_roll', return_value=([3, 4], 7)):
            w.perform_book_action('chest_luck')
        self.assertEqual(w.current_paragraph, 139)
        self.assertEqual(w.character['chance'], 6)
        self.assertNotIn('Épée', w.character['inventory'])
        self.assertIn('Épée trouvée dans la rivière', w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.current_paragraph, 379)
        self.assertIn('Épée', w.character['inventory'])
        self.assertEqual(w.character['chance'], 7)

    def test_chest379_destroy_magic_sword_removes_its_stat_bonus(self):
        w = self.w
        w.character.update(habilete=10, equipped_weapon='Épée magique', magic_sword_bonus_active=True)
        w.character['initial']['habilete'] = 10
        w.character['inventory'].append('Épée magique')
        w.go_to(379)
        with patch.object(w, '_roll', return_value=([1, 1], 2)):
            w.perform_book_action('chest_luck')
        self.assertEqual(w.character['habilete'], 8)
        self.assertEqual(w.character['initial']['habilete'], 8)
        self.assertNotIn('Épée magique', w.character['inventory'])
        self.assertIn('Épée', w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.character['habilete'], 10)
        self.assertTrue(w.character['magic_sword_bonus_active'])

    def test_chest379_unlucky_is_terminal_and_cannot_reroll(self):
        w = self.w
        w.go_to(379)
        w.character['chance'] = 1
        with patch.object(w, '_roll', return_value=([6, 6], 12)):
            w.perform_book_action('chest_luck')
        self.assertEqual((w.character['endurance'], w.character['chance']), (0, 0))
        self.assertEqual(w.current_paragraph, 379)
        with patch.object(w, '_roll') as roll:
            w.perform_book_action('chest_luck')
        roll.assert_not_called()

    def test_chest379_no_sword_or_missing_destination_changes_nothing(self):
        w = self.w
        w.go_to(379)
        w.character['inventory'] = []
        before = w._snapshot()
        with patch.object(w, '_roll') as roll:
            w.perform_book_action('chest_luck')
        roll.assert_not_called()
        self.assertEqual(w._snapshot(), before)
        w.character['inventory'] = ['Épée']
        del w.paragraphs[139]
        before = w._snapshot()
        w.perform_book_action('chest_luck')
        self.assertEqual(w._snapshot(), before)

    def test_chest242_does_not_offer_strike_without_a_sword(self):
        e = self.catalogue['paragraphs']['242']
        self.assertEqual([r['target'] for r in available_routes({'inventory': []}, e)], [139])
        self.assertEqual([r['target'] for r in available_routes({'inventory': ['Épée']}, e)], [379, 139])

    def test_hangar383_rechecks_actual_key_at_click(self):
        w = self.w
        w.go_to(383)
        w.follow_link(QUrl('paragraph:80'))
        self.assertEqual(w.current_paragraph, 383)
        w.character['inventory'].append('Clé du Hangar à Bateaux')
        w.follow_catalogue_choice(80)
        self.assertEqual(w.current_paragraph, 80)
        self.assertIn('Clé du Hangar à Bateaux', w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.current_paragraph, 383)

    def test_wrong_keys387_are_terminal(self):
        w = self.w
        w.go_to(387)
        self.assertEqual(w.character['endurance'], 0)
        w.follow_link(QUrl('paragraph:139'))
        self.assertEqual(w.current_paragraph, 387)
        w.undo_action()
        self.assertEqual(w.character['endurance'], 20)

    def test_first_corpse294_then390_cannot_pay_twice(self):
        w = self.w
        w.character['chance'] = 1
        w.go_to(294)
        self.assertEqual(w.character['gold'], 6)
        w.go_to(390)
        options = available_options(w.character, self.catalogue['paragraphs']['390'], w.completed_optional_events, 390)
        self.assertNotIn('pieces5', [o['id'] for o in options])
        w.apply_optional_book_event(390, 'pieces5')
        self.assertEqual(w.character['gold'], 6)
        self.assertEqual(w.character['chance'], 4)

    def test_first_corpse390_then294_does_not_repeat_gold_or_luck(self):
        w = self.w
        w.character['chance'] = 1
        w.go_to(390)
        w.apply_optional_book_event(390, 'pieces5')
        self.assertEqual((w.character['gold'], w.character['chance']), (6, 3))
        w.go_to(294)
        self.assertEqual((w.character['gold'], w.character['chance']), (6, 3))
        w.undo_action()
        w.undo_action()
        self.assertEqual(w.character['gold'], 1)
        self.assertFalse(w.character.get('book_facts', {}).get('first_body_searched'))

    def test_second_corpse393_optional_loot_is_once_and_bottle_consumes369(self):
        w = self.w
        w.go_to(393)
        for option in ('pieces8', 'parchemin', 'bouteille'):
            w.apply_optional_book_event(393, option)
        w.apply_optional_book_event(393, 'pieces8')
        self.assertEqual(w.character['gold'], 9)
        self.assertIn('Bouteille d’eau sainte', w.character['inventory'])
        w.follow_catalogue_choice(369)
        self.assertEqual(w.current_paragraph, 369)
        self.assertNotIn('Bouteille d’eau sainte', w.character['inventory'])
        self.assertTrue(w.character['book_facts']['holy_water_consumed'])
        w.undo_action()
        self.assertEqual(w.current_paragraph, 393)
        self.assertIn('Bouteille d’eau sainte', w.character['inventory'])
        self.assertFalse(w.character.get('book_facts', {}).get('holy_water_consumed'))

    def test_consumed_bottle_cannot_be_recollected_but_other_loot_can(self):
        w = self.w
        w.go_to(393)
        w.follow_catalogue_choice(369)
        w.follow_catalogue_choice(109)
        w.go_to(393)
        w.apply_optional_book_event(393, 'bouteille')
        self.assertNotIn('Bouteille d’eau sainte', w.character['inventory'])
        w.apply_optional_book_event(393, 'pieces8')
        self.assertEqual(w.character['gold'], 9)
        w.follow_link(QUrl('paragraph:369'))
        self.assertEqual(w.current_paragraph, 393)
        w.follow_catalogue_choice(212)
        w.follow_link(QUrl('paragraph:369'))
        self.assertEqual(w.current_paragraph, 212)

    def test_spider394_penalty_changes_attack_not_character_skill(self):
        w = self.w
        w.go_to(394)
        self.assertEqual((w.enemy_skill.value(), w.enemy_endurance.value()), (7, 8))
        # Sans -2 : 8+5 > 7+5 ; avec -2 le monstre touche.
        with patch.object(w, '_roll', side_effect=[([2, 3], 5), ([2, 3], 5)]):
            w.combat_round()
        self.assertEqual(w.character['endurance'], 18)
        self.assertEqual(w.character['habilete'], 8)
        self.assertEqual(combat_skill(w.character), 8)
        w.follow_link(QUrl('paragraph:232'))
        self.assertEqual(w.current_paragraph, 394)
        w.enemy_endurance.setValue(2)
        self.win()
        self.assertEqual(w.current_paragraph, 232)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 394)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_final_door396_counts_two_distinct_keys_and_preserves_them(self):
        w = self.w
        for keys, cost in [([], 5), (['Clé 9'], 5), (['Clé 9', 'clé 9'], 5),
                           (['Clé 9', 'Clé 125'], 0), (['Clé du Hangar à Bateaux', 'Clé 111'], 0)]:
            w.go_to(396)
            w.character.update(endurance=20, inventory=keys[:])
            w.follow_catalogue_choice(242)
            self.assertEqual(w.current_paragraph, 242)
            self.assertEqual(w.character['endurance'], 20-cost)
            self.assertEqual(w.character['inventory'], keys)
            w.undo_action()
            self.assertEqual(w.current_paragraph, 396)
            self.assertEqual(w.character['endurance'], 20)

    def test_final_door396_fatal_force_stays_outside(self):
        w = self.w
        w.go_to(396)
        w.character.update(endurance=5, inventory=[])
        w.follow_link(QUrl('paragraph:242'))
        self.assertEqual(w.current_paragraph, 396)
        self.assertEqual(w.character['endurance'], 0)
        w.undo_action()
        self.assertEqual(w.character['endurance'], 5)

    def test_real_key_combination_can_reach_victory(self):
        w = self.w
        keys = ['Clé de bronze 99', 'Clé 111', 'Clé rouge 111']
        w.character['inventory'] += keys
        w.go_to(139)
        with patch.object(QInputDialog, 'getItem', side_effect=[(k, True) for k in keys]):
            w.perform_book_action('keys')
        self.assertEqual(w.current_paragraph, 321)
        w.follow_catalogue_choice(169)
        w.follow_catalogue_choice(400)
        self.assertEqual(w.current_paragraph, 400)
        self.assertTrue(w.character['book_facts']['adventure_won'])
        self.assertEqual(w.character['gold'], 1)
        self.assertTrue(all(k in w.character['inventory'] for k in keys))
        w.undo_action()
        self.assertFalse(w.character.get('book_facts', {}).get('adventure_won'))

    def test_both111_keys_can_be_collected_from_their_actual_sources(self):
        w = self.w
        w.go_to(75)
        w.go_to(258)
        w.apply_optional_book_event(258, 'cle111')
        w.go_to(145)
        w.apply_optional_book_event(145, 'cle99')
        self.assertIn('Clé 111', w.character['inventory'])
        self.assertIn('Clé rouge 111', w.character['inventory'])
        self.assertIn('Clé de bronze 99', w.character['inventory'])
        w.go_to(139)
        keys = ['Clé 111', 'Clé rouge 111', 'Clé de bronze 99']
        with patch.object(QInputDialog, 'getItem', side_effect=[(k, True) for k in keys]):
            w.perform_book_action('keys')
        self.assertEqual(w.current_paragraph, 321)
        self.assertEqual(w._book_state(139)['tried'], [[99, 111, 111]])
        w.follow_catalogue_choice(169)
        w.follow_catalogue_choice(400)
        self.assertTrue(w.character['book_facts']['adventure_won'])

    def test_same_physical_key_cannot_be_counted_twice(self):
        w = self.w
        w.go_to(139)
        w.character['inventory'] = ['Clé 111', 'clé 111', 'Clé de bronze 99']
        before = w._snapshot()
        with patch.object(QInputDialog, 'getItem') as choose:
            w.perform_book_action('keys')
        choose.assert_not_called()
        self.assertEqual(w._snapshot(), before)

    def test_final_progress_actual_save_load_does_not_repeat_rewards(self):
        w = self.w
        w.go_to(393)
        w.apply_optional_book_event(393, 'pieces8')
        w.follow_catalogue_choice(369)
        before = w._snapshot()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'final.json'
            w._write_atomic(path, w._save_data())
            w.character['book_facts'].clear()
            with patch.object(w, '_themed_save_dialog', return_value=str(path)):
                w.load_game()
        self.assertEqual(w._snapshot(), before)
        w.go_to(393)
        w.apply_optional_book_event(393, 'pieces8')
        self.assertEqual(w.character['gold'], 9)
        w.follow_catalogue_choice(369)
        self.assertEqual(w.current_paragraph, 393)


if __name__ == '__main__':
    unittest.main()
