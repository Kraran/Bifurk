"""Cité des Voleurs, phase 3.4 : mécaniques relues des §301 à 400.

Mêmes principes que les phases précédentes : règles pures sans Qt, interface
avec un PDF synthétique aux passages neutres. Aucun texte du livre.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QDialog, QListWidget, QMessageBox, QPushButton

from grimoire_modules.cite import feedback, rules
from grimoire_modules.cite.controller import COMBAT_REASON, PENDING_REASON
from grimoire_modules.cite.encounters import COMBATS, profile
from tests import test_cite_mechanics as mechanics
from tests import test_cite_phase3_2 as second_hundred
from tests.test_cite_mechanics import hero

CATALOGUE = Path(__file__).resolve().parents[1] / 'catalogues' / 'evenements_cite_1983.json'


class CiteFourthHundredRulesTests(unittest.TestCase):
    def test_arrival_effects_of_the_fourth_hundred(self):
        character = hero()
        rules.apply_entry(character, 305)
        self.assertEqual(character['endurance'], 16)
        rules.apply_entry(character, 324)
        self.assertEqual(character['gold'], 45)
        self.assertIn('Deux pierres précieuses', character['inventory'])
        rules.apply_entry(character, 340)
        self.assertEqual((character['gold'], character['chance']), (70, 10))
        self.assertIn(rules.MAGNIFICENT_SHIELD, character['inventory'])
        rules.apply_entry(character, 338)
        self.assertEqual(character['chance'], 7)
        rules.apply_entry(character, 341)
        self.assertEqual(character['gold'], 65)

    def test_skill_gains_are_capped_by_the_initial_score(self):
        character = hero(habilete=9)
        rules.apply_entry(character, 362)
        self.assertEqual(character['habilete'], 10)
        self.assertIn('Bottes magiques', character['inventory'])
        rules.apply_entry(character, 374)
        self.assertEqual(character['habilete'], 10)
        rules.apply_entry(character, 387)
        self.assertEqual(character['habilete'], 9)

    def test_melting_silver_and_payments_never_go_below_zero(self):
        character = hero(gold=1, inventory=['Épée', 'Gobelet d’argent', 'Flûte d’argent', 'Lanterne'])
        rules.apply_entry(character, 343)
        self.assertEqual(character['inventory'], ['Épée', 'Lanterne'])
        self.assertEqual(character['endurance'], 15)
        rules.apply_entry(character, 341)
        self.assertEqual(character['gold'], 0)
        rules.apply_entry(character, 364)
        self.assertEqual(character['gold'], 0)

    def test_fine_routes_keep_one_gold_piece(self):
        for source, gold, kept in ((150, 30, 1), (335, 0, 0)):
            character = hero(gold=gold)
            self.assertTrue(rules.pay_route(character, source, 367))
            self.assertEqual(character['gold'], 0)
            rules.apply_entry(character, 367)
            self.assertEqual(character['gold'], kept)

    def test_pawnbroker_prices_and_locked_items(self):
        self.assertEqual(rules.pawn_price('Passe-partout'), 15)
        self.assertEqual(rules.pawn_price('Anneau de Feu'), 12)
        self.assertEqual(rules.pawn_price('Broche scorpion de cuivre'), 10)
        self.assertEqual(rules.pawn_price('Casque magique'), 7)
        self.assertIsNone(rules.pawn_price('Épée'))
        character = hero(inventory=['Épée', 'Miroir', 'Gobelet d’argent', 'Casque magique'],
                         locked_items=['Casque magique'])
        self.assertEqual(rules.pawn_choices(character), [('Miroir', 1), ('Gobelet d’argent', 8)])
        self.assertEqual(rules.pawn_sell(character, ['Miroir', 'Gobelet d’argent']), 9)
        self.assertEqual(character['gold'], 39)
        self.assertEqual(character['inventory'], ['Épée', 'Casque magique'])
        with self.assertRaises(ValueError):
            rules.pawn_sell(character, ['Casque magique'])
        with self.assertRaises(ValueError):
            rules.pawn_sell(character, ['Épée'])

    def test_cannonball_alternates_until_the_first_one(self):
        won = hero()
        self.assertEqual(rules.cannonball(won, [4, 1]), (False, 5))
        self.assertEqual(won['gold'], 35)
        self.assertTrue(rules.cannon_resolved(won))
        with self.assertRaises(ValueError):
            rules.cannonball(won, [1])
        lost = hero(gold=3)
        self.assertEqual(rules.cannonball(lost, [6, 5, 1]), (True, -3))
        self.assertEqual(lost['gold'], 0)
        for invalid in ([], [3, 4], [1, 2, 1], [7, 1]):
            with self.assertRaises(ValueError):
                rules.cannonball(hero(), invalid)

    def test_printed_item_conditions(self):
        self.assertTrue(rules.route_available(hero(inventory=['Clef en fer']), 353, 181))
        self.assertFalse(rules.route_available(hero(inventory=['Clef en fer']), 353, 389))
        self.assertTrue(rules.route_available(hero(inventory=[]), 353, 304))
        self.assertFalse(rules.route_available(hero(inventory=[]), 352, 106))
        self.assertTrue(rules.route_available(hero(), 352, 106))
        self.assertTrue(rules.route_available(hero(gold=9), 354, 307))
        self.assertFalse(rules.route_available(hero(gold=9), 354, 316))
        self.assertTrue(rules.route_available(hero(gold=10), 354, 316))
        self.assertFalse(rules.route_available(hero(gold=10), 354, 307))
        self.assertTrue(rules.has_item(hero(inventory=['Potion de contrôle mental']), 'contrôle mental'))

    def test_shield_and_helmet_add_attack_strength(self):
        self.assertEqual(rules.attack_bonus(hero()), 0)
        self.assertEqual(rules.attack_bonus(hero(inventory=[rules.MAGNIFICENT_SHIELD, rules.MAGIC_HELMET])), 2)

    def test_the_eleven_endings(self):
        self.assertEqual(len(rules.ENDINGS), 11)
        self.assertIn(rules.VICTORY, rules.ENDINGS)
        self.assertIn(346, rules.DEATHS)
        self.assertNotIn(rules.VICTORY, rules.DEATHS)
        character = hero()
        rules.finish_ending(character, 400)
        self.assertEqual(rules.peek(character)['ending'], 400)

    def test_the_whole_book_is_analysed(self):
        self.assertEqual(rules.ANALYSED, range(1, 401))
        events = json.loads(CATALOGUE.read_text(encoding='utf-8'))
        self.assertEqual(events['analysis_contract']['analysed_range'], [1, 400])
        self.assertTrue(all(entry['status'] == 'analyse_verifiee' for entry in events['paragraphs'].values()))
        self.assertEqual(events['paragraphs']['354']['analysis'], 'événement, renvoi conditionnel')


class CiteFourthHundredEncounterTests(unittest.TestCase):
    def test_new_fights(self):
        self.assertEqual(len(COMBATS[311]['groups'][1]), 2)
        self.assertEqual(len(COMBATS[326]['groups'][0]), 2)
        self.assertEqual(COMBATS[323]['wound'], 3)
        self.assertEqual(COMBATS[392]['fire'], (1, 2, 3))
        self.assertEqual([len(g) for g in profile(385)], [1, 1, 1])
        self.assertEqual(COMBATS[357]['escape_after_assaults'], 3)


class CiteFourthHundredWindowTests(unittest.TestCase):
    setUpClass = classmethod(mechanics.CiteMechanicsWindowTests.setUpClass.__func__)
    setUp = mechanics.CiteMechanicsWindowTests.setUp
    open = mechanics.CiteMechanicsWindowTests.open
    start = mechanics.CiteMechanicsWindowTests.start
    buttons = mechanics.CiteMechanicsWindowTests.buttons
    play = mechanics.CiteMechanicsWindowTests.play
    events = mechanics.CiteMechanicsWindowTests.events
    event_button = mechanics.CiteMechanicsWindowTests.event_button
    fixed_rolls = second_hundred.CiteSecondHundredWindowTests.fixed_rolls
    no_spoiler = second_hundred.CiteSecondHundredWindowTests.no_spoiler

    def luck_no(self):
        mock = patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No)
        mock.start()
        self.addCleanup(mock.stop)

    def test_pawnbroker_sells_at_printed_prices(self):
        self.play()
        self.w.character['inventory'] += ['Miroir', 'Passe-partout']
        self.w.go_to(354)
        button = self.event_button('prêteur sur gages')
        self.assertTrue(button.isEnabled())
        self.no_spoiler()
        offered = []

        def sell(dialog):
            items = dialog.findChild(QListWidget, 'saleItems')
            offered.extend(items.item(i).text() for i in range(items.count()))
            for i in range(items.count()):
                items.item(i).setSelected(items.item(i).text().startswith('Passe-partout'))
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Vendre…').click()
            return QDialog.Accepted
        with patch.object(QDialog, 'exec', sell), \
                patch.object(self.w, '_cite_confirm_sale', return_value=True) as confirm:
            button.click()
        confirm.assert_called_once_with(['Passe-partout'], 15)
        self.assertIn('Miroir — 1 Pièce d’Or', offered)
        self.assertEqual(self.w.character['gold'], 45)
        self.assertNotIn('Passe-partout', self.w.character['inventory'])
        card = next(b for b in self.buttons() if '316' in b.text())
        self.assertIn('à montrer, rien n’est payé', card.toolTip())
        self.w.undo_action()
        self.assertIn('Passe-partout', self.w.character['inventory'])

    def test_cannonball_blocks_until_played(self):
        self.play()
        self.w.go_to(378)
        self.assertTrue(all(b.toolTip().startswith('Indisponible : ' + PENDING_REASON) for b in self.buttons()))
        self.no_spoiler()
        self.fixed_rolls(5, 6, 1)
        self.event_button('boulet de canon').click()
        self.assertEqual(self.w.character['gold'], 25)
        self.assertIn('vous lâchez le boulet', self.w.rules_log.text())
        self.assertIn('Or 30 → 25', self.w.rules_log.text())
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.assertFalse(any('boulet' in b.text() for b in self.events() if hasattr(b, 'text')))

    def test_simultaneous_fight_lets_the_hero_choose_a_target(self):
        self.play()
        self.luck_no()
        self.w.go_to(326)
        self.assertTrue(self.w.combat_available())
        self.assertTrue(all(b.toolTip().startswith('Indisponible : ' + COMBAT_REASON) for b in self.buttons()))
        self.assertEqual(self.w.enemy_name.text(), 'Premier Chien Sauvage')
        self.event_button('Cibler Deuxième Chien Sauvage').click()
        self.assertEqual(self.w.enemy_name.text(), 'Deuxième Chien Sauvage')
        endurance = self.w.character['endurance']
        # Assaut contre la cible gagné (6+6 contre 1+1), parade perdue (6+6 contre 1+1).
        self.fixed_rolls(1, 1, 6, 6, 6, 6, 1, 1)
        self.w.combat_round()
        combat = self.w._cite_combat()
        self.assertEqual([e['stamina'] for e in combat['groups'][0]], [4, 1])
        self.assertEqual(self.w.character['endurance'], endurance - 2)

    def test_fire_breath_burns_on_low_faces(self):
        self.play()
        self.luck_no()
        self.w.go_to(392)
        endurance = self.w.character['endurance']
        self.fixed_rolls(1, 1, 6, 6, 2)
        self.w.combat_round()
        self.assertEqual(self.w.character['endurance'], endurance - 1)
        self.fixed_rolls(1, 1, 6, 6, 5)
        self.w.combat_round()
        self.assertEqual(self.w.character['endurance'], endurance - 1)

    def test_fines_tooltips_hide_the_refund(self):
        self.play()
        self.w.go_to(150)
        card = next(b for b in self.buttons() if '367' in b.text())
        self.assertIn('Tout votre or est remis', card.toolTip())
        self.no_spoiler()
        card.click()
        self.assertEqual((self.w.current_paragraph, self.w.character['gold']), (367, 1))

    def test_victory_paragraph_ends_the_adventure(self):
        self.play()
        self.w.go_to(400)
        texts = [b.text() for b in self.events() if hasattr(b, 'text')]
        self.assertTrue(any(t.startswith('Victoire') for t in texts))
        self.assertTrue(self.w.character['book_facts'].get('adventure_ended')
                        or rules.peek(self.w.character).get('ending') == 400)


class CiteFourthHundredFeedbackTests(unittest.TestCase):
    def test_cannon_summary_names_who_drops_the_ball(self):
        before = feedback.snapshot(hero())
        trace = [{'rolls': [4], 'total': 4}, {'rolls': [1], 'total': 1}]
        self.assertIn('il lâche le boulet', ' '.join(feedback.describe_rolls('cannon', trace, before)))
