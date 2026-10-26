"""Cité des Voleurs, phase 3.2 : mécaniques relues des §101 à 200.

Mêmes principes que la phase 3.1 : règles pures sans Qt, interface avec un PDF
synthétique aux passages neutres. Aucun texte du livre.
"""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox, QPushButton

from grimoire_modules.cite import rules
from grimoire_modules.cite.controller import PENDING_REASON
from grimoire_modules.cite.encounters import COMBATS, escape_status
from grimoire_modules.fighting_fantasy.adventure import new_group_combat
from tests.test_cite_mechanics import CiteMechanicsWindowTests, hero

MISSION = [rules.ARROW, rules.PEARLS, 'Cheveux de sorcière', 'Fleur de lotus']


class CiteSecondHundredRulesTests(unittest.TestCase):
    def test_arrival_effects_of_the_second_hundred(self):
        character = hero(inventory=['Épée', 'Armure de cuir', 'Lanterne', 'Bouquet de fleurs'])
        rules.apply_entry(character, 106)
        rules.apply_entry(character, 172)
        self.assertEqual(character['inventory'], ['Épée', 'Armure de cuir'])
        self.assertEqual(character['gold'], 32)
        rules.apply_entry(character, 123)
        self.assertEqual((character['gold'], character['chance']), (35, 10))
        self.assertIn(rules.SKELETON_KEY, character['inventory'])
        rules.apply_entry(character, 134)
        self.assertEqual(character['gold'], 0)
        rules.apply_entry(character, 125)
        self.assertEqual(character['habilete'], 9)
        self.assertIn(rules.CURSED_SHIELD, character['locked_items'])

    def test_arrows_heal_twice_their_number_and_the_sword_is_exchanged(self):
        character = hero(endurance=20)
        rules.volley(character, 2)
        # VO : 3 points d’Endurance par flèche, puis 2 points de Chance.
        self.assertEqual((character['endurance'], character['chance']), (14, 7))
        with self.assertRaises(ValueError):
            rules.volley(character, 3)
        rules.apply_entry(character, 126)
        self.assertEqual((character['endurance'], character['habilete']), (18, 9))
        self.assertIn(rules.PLAIN_SWORD, character['inventory'])
        self.assertNotIn('Épée', character['inventory'])
        self.assertNotIn(rules.PLAIN_SWORD, rules.magic_payment_choices(character))

    def test_volley_can_kill(self):
        character = hero(endurance=17)
        rules.volley(character, 6)
        self.assertEqual((character['endurance'], character['chance']), (0, 9))

    def test_failed_tests_cost_what_the_book_prints(self):
        character = hero(gold=3)
        self.assertEqual(rules.resolve_test(character, 190, 12), 296)
        self.assertEqual(character['gold'], 0)
        winner = hero()
        self.assertEqual(rules.resolve_test(winner, 190, 5), 38)
        self.assertEqual(winner['gold'], 30)
        unlucky = hero(chance=5)
        self.assertEqual(rules.resolve_test(unlucky, 192, 11), 304)
        self.assertEqual((unlucky['habilete'], unlucky['chance']), (9, 4))
        lucky = hero(chance=5)
        rules.resolve_test(lucky, 192, 4)
        self.assertEqual(lucky['habilete'], 10)

    def test_double_luck_counts_failures(self):
        self.assertEqual(rules.resolve_double(hero(chance=9), 128, [9, 8]), 340)
        self.assertEqual(rules.resolve_double(hero(chance=9), 128, [9, 9]), 149)
        character = hero(chance=9)
        self.assertEqual(rules.resolve_double(character, 128, [12, 12]), 19)
        self.assertEqual(character['chance'], 7)
        with self.assertRaises(ValueError):
            rules.resolve_double(character, 128, [2, 2])

    def test_pickpocket_takes_one_coin_or_one_item(self):
        character = hero(gold=2, locked_items=['Lanterne'])
        self.assertEqual(rules.pocket_choices(character), [rules.POCKET_GOLD, 'Épée', 'Armure de cuir'])
        rules.pick_pocket(character, rules.POCKET_GOLD)
        self.assertEqual(character['gold'], 1)
        with self.assertRaises(ValueError):
            rules.pick_pocket(character, 'Épée')
        other = hero()
        with self.assertRaises(ValueError):
            rules.pick_pocket(other, 'Lanterne magique')
        rules.pick_pocket(other, 'Lanterne')
        self.assertNotIn('Lanterne', other['inventory'])
        empty = hero(gold=0, inventory=[])
        self.assertIsNone(rules.pick_pocket(empty, None))

    def test_poultice_heals_once_and_is_consumed(self):
        character = hero(endurance=17, inventory=['Épée', rules.POULTICE])
        rules.use_poultice(character, 6)
        self.assertEqual(character['endurance'], 20)
        self.assertEqual(character['inventory'], ['Épée'])
        with self.assertRaises(ValueError):
            rules.use_poultice(character, 3)

    def test_mission_needs_the_four_items_and_the_tattoo(self):
        character = hero(inventory=['Épée'] + MISSION)
        self.assertFalse(rules.route_available(character, 108, 201, visited=[108]))
        self.assertTrue(rules.route_available(character, 108, 299, visited=[108]))
        self.assertTrue(rules.route_available(character, 156, 201, visited=[279, 156]))
        self.assertFalse(rules.route_available(character, 156, 299, visited=[279, 156]))
        character['inventory'].remove('Fleur de lotus')
        self.assertFalse(rules.route_available(character, 156, 201, visited=[279]))

    def test_gold_rules_on_routes(self):
        character = hero(gold=12)
        self.assertTrue(rules.route_available(character, 182, 279))
        self.assertFalse(rules.route_available(character, 182, 354))
        self.assertTrue(rules.route_available(hero(gold=9), 182, 354))
        self.assertTrue(rules.pay_route(character, 150, 367))
        self.assertEqual(character['gold'], 0)
        deferred = hero(gold=6)
        self.assertTrue(rules.pay_route(deferred, 315, 132))
        self.assertEqual(deferred['gold'], 0)
        rules.apply_entry(deferred, 132)
        self.assertIn(rules.SILVER_BROOCH, deferred['inventory'])

    def test_item_payments_offer_only_accepted_objects(self):
        character = hero(inventory=['Épée', 'Armure de cuir', 'Lanterne', 'Anneau de Feu'],
                         potion='Potion d’Adresse', potion_doses=2)
        self.assertEqual(rules.item_payment_choices(character, (113, 141)), ['Lanterne'])
        magic = rules.item_payment_choices(character, (187, 260))
        self.assertEqual(magic, ['Anneau de Feu', 'Potion d’Adresse (potion de départ)'])
        self.assertFalse(rules.route_available(character, 187, 341))
        with self.assertRaises(ValueError):
            rules.pay_route(character, 187, 260, ['Lanterne'])
        rules.pay_route(character, 187, 260, [magic[1]])
        self.assertEqual(character['potion_doses'], 0)
        self.assertIn('Anneau de Feu', character['inventory'])
        bare = hero(inventory=['Épée', 'Armure de cuir'])
        self.assertFalse(rules.route_available(bare, 113, 141))
        self.assertFalse(rules.route_available(bare, 187, 260))
        self.assertTrue(rules.route_available(bare, 187, 341))

    def test_item_conditions_of_the_second_hundred(self):
        character = hero(inventory=['Épée', 'Fleur de lotus'])
        self.assertFalse(rules.route_available(character, 184, 55))
        self.assertTrue(rules.route_available(character, 184, 308))
        self.assertFalse(rules.route_available(character, 61, 172))
        character['inventory'].append('Fleurs d’or')
        self.assertTrue(rules.route_available(character, 184, 55))
        self.assertFalse(rules.route_available(character, 61, 172))
        character['inventory'].append('Anneau de Feu')
        self.assertTrue(rules.route_available(character, 193, 286))
        self.assertFalse(rules.route_available(character, 193, 163))

    def test_new_endings(self):
        for number in (129, 142):
            character = hero()
            self.assertTrue(rules.finish_ending(character, number))
            self.assertEqual(character['endurance'], 0)

    def test_jeweller_drawer_is_taken_by_choice(self):
        """§114 : VO « Take what you will » — rien n’est pris d’office."""
        character = hero()
        rules.apply_entry(character, 114)
        self.assertEqual((character['gold'], character['inventory']), (30, ['Épée', 'Armure de cuir', 'Lanterne']))
        ring = 'Bague ornée de pierreries'
        self.assertEqual(rules.loot_choices(114), ['13 Pièces d’Or', ring, ring, ring])
        rules.take_loot(character, 114, ['13 Pièces d’Or', ring])
        self.assertEqual(character['gold'], 43)
        self.assertEqual(character['inventory'].count(ring), 1)
        with self.assertRaises(ValueError):
            rules.take_loot(character, 114, [ring])
        greedy = hero()
        with self.assertRaises(ValueError):
            rules.take_loot(greedy, 114, [ring] * 4)
        self.assertFalse(rules.loot_taken(greedy, 114))


class CiteSecondHundredEncounterTests(unittest.TestCase):
    def test_ogre_and_jeweller_escapes(self):
        ogre = new_group_combat([[dict(e) for e in g] for g in COMBATS[140]['groups']])
        self.assertFalse(escape_status(140, ogre)[0])
        ogre['assaults'] = 3
        self.assertTrue(escape_status(140, ogre)[0])
        jeweller = new_group_combat([[dict(e) for e in g] for g in COMBATS[170]['groups']])
        self.assertTrue(escape_status(170, jeweller)[0])
        self.assertEqual((COMBATS[152]['attack'], COMBATS[157]['attack']), (-2, -3))


class CiteSecondHundredWindowTests(unittest.TestCase):
    setUpClass = classmethod(CiteMechanicsWindowTests.setUpClass.__func__)
    setUp = CiteMechanicsWindowTests.setUp
    open = CiteMechanicsWindowTests.open
    start = CiteMechanicsWindowTests.start
    buttons = CiteMechanicsWindowTests.buttons
    play = CiteMechanicsWindowTests.play
    events = CiteMechanicsWindowTests.events
    event_button = CiteMechanicsWindowTests.event_button
    winning_rolls = CiteMechanicsWindowTests.winning_rolls

    def fixed_rolls(self, *faces):
        queue = list(faces)

        def traced(count, *args, **kwargs):
            rolls = [queue.pop(0) for _ in range(count)]
            if isinstance(getattr(self.w, '_roll_trace', None), list):
                self.w._roll_trace.append({'rolls': rolls, 'total': sum(rolls),
                                            'chance': self.w.character.get('chance')})
            return rolls, sum(rolls)
        self.roll.side_effect = traced

    def no_spoiler(self):
        for button in self.buttons() + [b for b in self.events() if hasattr(b, 'toolTip')]:
            self.assertNotIn('§', button.toolTip())

    def test_attack_malus_reaches_the_combat_profile(self):
        self.play()
        self.w.go_to(157)
        self.assertEqual(self.w._ff_combat_profile()['attack_bonus'], -3)
        self.assertEqual(self.w.enemy_name.text(), 'Premier Garde de la Ville')

    def test_fire_ring_skips_the_mummy_fight(self):
        self.play()
        self.w.character['inventory'].append('Anneau de Feu')
        self.w.go_to(193)
        self.assertFalse(self.w.combat_available())
        cards = {b.text(): b for b in self.buttons()}
        self.assertTrue(next(b for t, b in cards.items() if '286' in t).isEnabled())
        self.assertFalse(next(b for t, b in cards.items() if '163' in t).isEnabled())
        self.w.undo_action()
        self.w.character['inventory'].remove('Anneau de Feu')
        self.w.go_to(193)
        self.assertTrue(self.w.combat_available())

    def test_knife_wager_logs_the_lost_gold(self):
        self.play()
        self.w.go_to(190)
        self.assertTrue(all(b.toolTip().startswith('Indisponible : ' + PENDING_REASON) for b in self.buttons()))
        self.no_spoiler()
        self.fixed_rolls(6, 6)
        self.event_button('Épreuve d’Habileté').click()
        self.assertEqual((self.w.current_paragraph, self.w.character['gold']), (296, 25))
        self.assertIn('Or 30 → 25', self.w.rules_log.text())

    def test_double_luck_button(self):
        self.play()
        self.w.go_to(128)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.no_spoiler()
        self.fixed_rolls(4, 4, 6, 6)
        self.event_button('Tenter deux fois').click()
        self.assertEqual(self.w.current_paragraph, 149)
        log = self.w.rules_log.text()
        self.assertIn('8 ≤ 9, réussi', log)
        self.assertIn('12 > 8, raté', log)

    def test_volley_then_pickpocket_block_until_resolved(self):
        self.play()
        self.w.go_to(137)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.fixed_rolls(1)
        chance = self.w.character['chance']
        self.event_button('flèches reçues').click()
        self.assertEqual(self.w.character['endurance'], 15)
        self.assertEqual(self.w.character['chance'], chance - rules.VOLLEY_AFTER)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.w.go_to(148)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.w.perform_cite_action('pocket', rules.POCKET_GOLD)
        self.assertEqual(self.w.character['gold'], 29)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.w.undo_action()
        self.assertEqual(self.w.character['gold'], 30)

    def test_jeweller_drawer_button_is_optional(self):
        self.play()
        self.w.go_to(114)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        gold = self.w.character['gold']
        with patch.object(self.w, '_cite_pick_items', return_value=['13 Pièces d’Or']):
            self.event_button('Garder').click()
        self.assertEqual(self.w.character['gold'], gold + 13)
        self.assertNotIn('Bague ornée de pierreries', self.w.character['inventory'])
        self.assertFalse(any('Garder' in b.text() for b in self.events() if isinstance(b, QPushButton)))
        self.w.undo_action()
        self.assertEqual(self.w.character['gold'], gold)

    def test_poultice_button_outside_combat_only(self):
        self.play()
        self.w.character['endurance'] = 12
        self.w.go_to(167)
        self.assertIn(rules.POULTICE, self.w.character['inventory'])
        self.fixed_rolls(4)
        self.event_button('emplâtre').click()
        self.assertEqual(self.w.character['endurance'], 16)
        self.assertNotIn(rules.POULTICE, self.w.character['inventory'])
        self.w.character['inventory'].append(rules.POULTICE)
        self.w.go_to(166)
        self.assertFalse(self.event_button('emplâtre').isEnabled())

    def test_item_payment_route_asks_for_one_object(self):
        self.play()
        self.w.go_to(113)
        card = next(b for b in self.buttons() if '141' in b.text())
        self.assertIn('Un objet est remis', card.toolTip())
        with patch.object(self.w, '_cite_pick_items', return_value=['Lanterne']):
            card.click()
        self.assertEqual(self.w.current_paragraph, 141)
        self.assertNotIn('Lanterne', self.w.character['inventory'])

    def test_mission_cards_show_only_the_printed_condition(self):
        self.play()
        self.w.go_to(156)
        card = next(b for b in self.buttons() if '201' in b.text())
        self.assertFalse(card.isEnabled())
        self.assertTrue(card.toolTip().startswith('Indisponible : condition du livre non remplie'))
        self.assertNotIn('flèche', card.toolTip().casefold())
        self.no_spoiler()

    def test_ogre_escape_after_three_assaults(self):
        self.play()
        mock = patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No)
        mock.start()
        self.addCleanup(mock.stop)
        self.w.go_to(140)
        self.assertFalse(self.w.combat_flee_status()[0])
        self.fixed_rolls(*([1, 1, 1, 1] * 3))
        for _ in range(3):
            self.w.combat_round()
        self.assertTrue(self.w.combat_flee_status()[0])
