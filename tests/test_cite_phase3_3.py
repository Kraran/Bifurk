"""Cité des Voleurs, phase 3.3 : mécaniques relues des §201 à 300.

Mêmes principes que les phases 3.1 et 3.2 : règles pures sans Qt, interface avec
un PDF synthétique aux passages neutres. Aucun texte du livre.
"""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from grimoire_modules.cite import feedback, rules
from grimoire_modules.cite.controller import COMBAT_REASON, PENDING_REASON
from grimoire_modules.cite.encounters import COMBATS, profile
from tests.test_cite_mechanics import CiteMechanicsWindowTests, hero
from tests.test_cite_phase3_2 import CiteSecondHundredWindowTests

MISSION = [rules.ARROW, rules.PEARLS, 'Cheveux de sorcière', 'Fleur de lotus']


class CiteThirdHundredRulesTests(unittest.TestCase):
    def test_arrival_effects_of_the_third_hundred(self):
        character = hero(inventory=['Épée', 'Pierres précieuses'])
        rules.apply_entry(character, 201)
        self.assertEqual(character['endurance'], 20)
        self.assertIn(rules.BOW, character['inventory'])
        rules.apply_entry(character, 240)
        self.assertEqual(character['gold'], 39)
        self.assertNotIn('Pierres précieuses', character['inventory'])
        rules.apply_entry(character, 221)
        self.assertEqual((character['gold'], character['chance']), (0, 7))
        rules.apply_entry(character, 295)
        self.assertEqual((character['gold'], character['chance']), (12, 8))
        rules.apply_entry(character, 243)
        self.assertEqual(character['endurance'], 15)

    def test_tattoo_is_locked_and_counts_for_the_mission(self):
        character = hero(inventory=['Épée'] + MISSION)
        self.assertFalse(rules.mission_ready(character, ()))
        rules.apply_entry(character, 279)
        self.assertIn(rules.TATTOO, character['inventory'])
        self.assertIn(rules.TATTOO, character['locked_items'])
        self.assertTrue(rules.mission_ready(character, ()))
        self.assertTrue(rules.route_available(character, 239, 201))
        self.assertFalse(rules.route_available(character, 239, 299))

    def test_garlic_does_not_match_chain_mail(self):
        self.assertFalse(rules.has_item(hero(inventory=['Cotte de mailles']), 'ail'))
        self.assertTrue(rules.has_item(hero(inventory=[rules.GARLIC]), 'ail'))
        self.assertTrue(rules.route_available(hero(inventory=[rules.GARLIC]), 292, 254))
        self.assertFalse(rules.route_available(hero(inventory=[rules.GARLIC]), 292, 210))

    def test_failed_luck_at_203_is_a_printed_death(self):
        character = hero(chance=5)
        self.assertIsNone(rules.resolve_test(character, 203, 12))
        self.assertEqual(character['endurance'], 0)
        self.assertEqual(rules.peek(character)['ending'], 203)
        lucky = hero()
        self.assertEqual(rules.resolve_test(lucky, 203, 3), 244)
        self.assertEqual(lucky['endurance'], 18)

    def test_pill_die(self):
        character = hero()
        self.assertTrue(rules.pending_test(character, 223))
        self.assertEqual(rules.resolve_die_test(character, 223, 4), 165)
        self.assertEqual(character['gold'], 50)
        with self.assertRaises(ValueError):
            rules.resolve_die_test(character, 223, 4)
        poisoned = hero()
        self.assertIsNone(rules.resolve_die_test(poisoned, 223, 1))
        self.assertEqual((poisoned['endurance'], poisoned['gold']), (0, 30))
        self.assertTrue(poisoned['book_facts']['adventure_ended'])

    def test_mixture_restricts_the_final_choice(self):
        character = hero()
        self.assertTrue(all(rules.route_available(character, 244, t) for _n, t in rules.MIXTURES))
        rules.choose_mixture(character, 337)
        self.assertEqual([t for _n, t in rules.MIXTURES if rules.route_available(character, 244, t)], [337])
        self.assertTrue(any(name.startswith('Mélange') for name in character['inventory']))
        with self.assertRaises(ValueError):
            rules.choose_mixture(character, 9)

    def test_creature_die_drives_paragraph_138(self):
        character = hero()
        self.assertEqual(rules.roll_creature(character, 5), ('Homme-Singe', 7, 6))
        self.assertTrue(rules.route_available(character, 138, 312))
        self.assertFalse(rules.route_available(character, 138, 283))
        orc = hero()
        rules.roll_creature(orc, 1)
        self.assertEqual([t for t in (312, 283) if rules.route_available(orc, 138, t)], [283])
        self.assertEqual(profile(201, rules.CREATURES[6]),
                         [[{'name': 'Troll des Cavernes', 'skill': 8, 'stamina': 7}]])

    def test_gambling_follows_the_printed_rule(self):
        character = hero(gold=5)
        self.assertEqual(rules.gamble(character, [7, 8, 9], 10), ('gagnée', 6))
        self.assertEqual(rules.gamble(character, [7, 8, 9], 9), ('égalité', 0))
        self.assertEqual(rules.gamble(character, [7, 12, 3], 11), ('perdue', -2))
        self.assertEqual(character['gold'], 9)
        rules.gamble(character, [2, 2, 2], 3)
        self.assertEqual(rules.can_gamble(character), 'Les Nains se sont lassés : quatre parties au plus.')
        poor = hero(gold=1)
        self.assertIsNotNone(rules.can_gamble(poor))
        with self.assertRaises(ValueError):
            rules.gamble(poor, [2, 2, 2], 12)

    def test_brawl_takes_two_backpack_items(self):
        character = hero(inventory=['Épée', 'Armure de cuir', 'Lanterne', 'Miroir', 'Corde'])
        with self.assertRaises(ValueError):
            rules.brawl_loss(character, ['Lanterne'])
        rules.brawl_loss(character, ['Lanterne', 'Corde'])
        self.assertEqual(character['inventory'], ['Épée', 'Armure de cuir', 'Miroir'])
        self.assertTrue(rules.brawl_resolved(character))

    def test_loot_is_optional_and_taken_once(self):
        character = hero()
        self.assertEqual(rules.loot_choices(208), ['2 Pièces d’Or', rules.GARLIC, 'Vieux osselets'])
        rules.take_loot(character, 208, ['2 Pièces d’Or', rules.GARLIC])
        self.assertEqual(character['gold'], 32)
        self.assertIn(rules.GARLIC, character['inventory'])
        with self.assertRaises(ValueError):
            rules.take_loot(character, 208, [])
        empty = hero()
        rules.take_loot(empty, 220, [])
        self.assertTrue(rules.loot_taken(empty, 220))
        self.assertEqual(rules.loot_choices(220).count('Gobelet en argent'), 2)

    def test_candles_can_be_bought_repeatedly_and_hot_meal_once(self):
        character = hero(gold=3, endurance=19)
        rules.buy(character, 241, 'Bougie de couleur')
        rules.buy(character, 241, 'Bougie de couleur')
        self.assertEqual(character['inventory'].count('Bougie de couleur'), 2)
        rules.hot_meal(character)
        self.assertEqual((character['gold'], character['endurance']), (0, 20))
        with self.assertRaises(ValueError):
            rules.hot_meal(character)

    def test_golden_flower_trade(self):
        character = hero(inventory=['Épée', 'Lanterne', 'Marchandise', 'Anneau de Feu'], provisions=1,
                         potion=None)
        self.assertEqual(rules.trade_choices(character), ['Épée', 'Anneau de Feu'])
        rules.trade_flower(character, 'Anneau de Feu')
        self.assertIn(rules.GOLDEN_FLOWER, character['inventory'])
        self.assertNotIn('Anneau de Feu', character['inventory'])
        with self.assertRaises(ValueError):
            rules.trade_flower(character, 'Épée')
        hungry = hero(inventory=['Lanterne'], potion=None)
        rules.trade_flower(hungry, rules.TRADE_PROVISIONS_LABEL)
        self.assertEqual(hungry['provisions'], 8)

    def test_route_costs_of_the_third_hundred(self):
        character = hero(gold=12, chance=9)
        self.assertTrue(rules.route_available(character, 300, 347))
        rules.pay_route(character, 300, 347)
        self.assertEqual((character['gold'], character['chance']), (2, 7))
        self.assertFalse(rules.route_available(hero(gold=4), 276, 109))
        shown = hero(gold=5)
        self.assertTrue(rules.route_available(shown, 276, 109))
        rules.pay_route(shown, 276, 109)
        self.assertEqual(shown['gold'], 5)
        hungry = hero(provisions=1)
        self.assertFalse(rules.route_available(hungry, 264, 121))
        fed = hero(provisions=3)
        rules.pay_route(fed, 264, 121)
        self.assertEqual(fed['provisions'], 1)
        self.assertFalse(rules.pay_route(fed, 264, 121))

    def test_item_conditions_of_the_third_hundred(self):
        character = hero(inventory=['Épée', rules.SKELETON_KEY])
        self.assertEqual([t for t in (228, 4, 365) if rules.route_available(character, 259, t)], [228])
        bare = hero()
        self.assertEqual([t for t in (228, 4, 365) if rules.route_available(bare, 259, t)], [4, 365])

    def test_feedback_describes_a_gambling_round(self):
        before = feedback.snapshot(hero())
        after = feedback.snapshot(hero(gold=36))
        trace = [{'rolls': [3, 4], 'total': 7}, {'rolls': [2, 2], 'total': 4},
                 {'rolls': [5, 4], 'total': 9}, {'rolls': [6, 5], 'total': 11}]
        text = feedback.summary(before, after, kind='gamble', trace=trace)
        self.assertIn('Nains : 3+4=7, 2+2=4, 5+4=9 ; vous : 6+5=11 — partie gagnée', text)
        self.assertIn('Or 30 → 36', text)


class CiteThirdHundredEncounterTests(unittest.TestCase):
    def test_new_fights(self):
        self.assertEqual(COMBATS[217]['groups'][1][0], profile(217)[1][0])
        self.assertEqual(COMBATS[226]['escape'], 78)
        self.assertEqual(COMBATS[253]['wound'], 4)
        with self.assertRaises(ValueError):
            profile(201)


class CiteThirdHundredWindowTests(unittest.TestCase):
    setUpClass = classmethod(CiteMechanicsWindowTests.setUpClass.__func__)
    setUp = CiteMechanicsWindowTests.setUp
    open = CiteMechanicsWindowTests.open
    start = CiteMechanicsWindowTests.start
    buttons = CiteMechanicsWindowTests.buttons
    play = CiteMechanicsWindowTests.play
    events = CiteMechanicsWindowTests.events
    event_button = CiteMechanicsWindowTests.event_button
    fixed_rolls = CiteSecondHundredWindowTests.fixed_rolls
    no_spoiler = CiteSecondHundredWindowTests.no_spoiler

    def luck_no(self):
        mock = patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No)
        mock.start()
        self.addCleanup(mock.stop)

    def test_mixture_then_creature_then_fight(self):
        self.play()
        self.w.go_to(201)
        self.assertTrue(all(b.toolTip().startswith('Indisponible : ' + PENDING_REASON) for b in self.buttons()))
        self.assertFalse(self.event_button('la créature').isEnabled())
        self.no_spoiler()
        self.w.perform_cite_action('mixture', 129)
        self.fixed_rolls(5)
        self.event_button('la créature').click()
        self.assertTrue(self.w.combat_available())
        self.assertEqual(self.w.enemy_name.text(), 'Homme-Singe')
        self.assertTrue(all(b.toolTip().startswith('Indisponible : ' + COMBAT_REASON) for b in self.buttons()))
        self.assertIn('Homme-Singe', self.w.rules_log.text())

    def test_gamble_button_counts_rounds(self):
        self.play()
        self.w.go_to(206)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.no_spoiler()
        self.fixed_rolls(1, 1, 2, 2, 3, 3, 6, 6)
        self.event_button('Jouer une partie').click()
        self.assertEqual(self.w.character['gold'], 36)
        self.assertIn('partie gagnée', self.w.rules_log.text())
        self.assertIn('(1/4)', self.event_button('Jouer une partie').text())

    def test_pill_die_button(self):
        self.play()
        self.w.go_to(223)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.fixed_rolls(3)
        self.event_button('Lancer un dé').click()
        self.assertEqual(self.w.current_paragraph, 165)
        self.assertEqual(self.w.character['gold'], 50)

    def test_brawl_blocks_until_items_are_chosen(self):
        self.play()
        self.w.character['inventory'] += ['Miroir', 'Corde']
        self.w.go_to(266)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        with patch.object(self.w, '_cite_pick_items', return_value=['Miroir', 'Corde']):
            self.event_button('Constater la perte').click()
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.assertNotIn('Miroir', self.w.character['inventory'])

    def test_loot_trade_and_meal_are_optional(self):
        self.play()
        self.w.go_to(285)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        with patch.object(self.w, '_cite_pick_items', return_value=['Trousseau de clefs']):
            self.event_button('Garder').click()
        self.assertIn('Trousseau de clefs', self.w.character['inventory'])
        self.w.go_to(293)
        with patch.object(self.w, '_cite_pick_items', return_value=[rules.TRADE_PROVISIONS_LABEL]):
            self.event_button('fleur dorée').click()
        self.assertIn(rules.GOLDEN_FLOWER, self.w.character['inventory'])
        self.w.character['endurance'] = 1
        self.w.go_to(287)
        gold = self.w.character['gold']
        self.event_button('Manger chaud').click()
        self.assertEqual((self.w.character['endurance'], self.w.character['gold']), (3, gold - 1))

    def test_snake_bites_cost_four(self):
        self.play()
        self.luck_no()
        self.w.go_to(253)
        endurance = self.w.character['endurance']
        self.fixed_rolls(6, 6, 1, 1)
        self.w.combat_round()
        self.assertEqual(self.w.character['endurance'], endurance - 4)

    def test_route_tooltips_name_only_the_cost(self):
        self.play()
        self.w.go_to(300)
        card = next(b for b in self.buttons() if '347' in b.text())
        self.assertIn('Chance −2', card.toolTip())
        self.w.go_to(276)
        card = next(b for b in self.buttons() if '109' in b.text())
        self.assertIn('à montrer, rien n’est payé', card.toolTip())
        self.no_spoiler()

