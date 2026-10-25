"""Cité des Voleurs, phase 3.1 : mécaniques relues des §1 à 100.

Les règles pures sont testées sans Qt ; l’interface avec un PDF synthétique dont
les paragraphes sont remplacés par des textes neutres. Aucun texte du livre.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from grimoire_modules.cite import rules
from grimoire_modules.cite.controller import (
    ANALYSED_NOTICE,
    COMBAT_REASON,
    PENDING_REASON,
    PREVIEW_NOTICE,
    CiteController,
)
from grimoire_modules.cite.encounters import COMBATS, escape_status, victory_target
from grimoire_modules.fighting_fantasy.adventure import new_group_combat
from tests.test_cite_presentation import CitePresentationTests

CATALOGUE = json.loads((Path(__file__).resolve().parents[1] / 'catalogues/evenements_cite_1983.json')
                       .read_text(encoding='utf-8'))


def routes(number):
    return [route['target'] for route in CATALOGUE['paragraphs'][str(number)]['routes']]


def hero(**changes):
    character = {'habilete': 10, 'endurance': 18, 'chance': 9, 'gold': 30, 'provisions': 10,
                 'initial': {'habilete': 10, 'endurance': 20, 'chance': 10},
                 'inventory': ['Épée', 'Armure de cuir', 'Lanterne'], 'locked_items': []}
    character.update(changes)
    return character


class CiteTablesTests(unittest.TestCase):
    def test_every_coded_destination_is_a_catalogued_route(self):
        """Les tables ne créent aucun renvoi : elles conditionnent ceux du livre."""
        pairs = (list(rules.ITEM_ROUTES) + list(rules.NOT_YET_ROUTES) + list(rules.ROUTE_COSTS)
                 + [rules.ARROW_OFFER, rules.ARROW_FALLBACK])
        for source, target in pairs:
            self.assertIn(target, routes(source), (source, target))
        for number, (_stat, success, failure, _damage) in rules.BRANCH_TESTS.items():
            self.assertEqual(sorted(routes(number)), sorted({success, failure}), number)
        for number, data in COMBATS.items():
            exits = {data['victory'], data.get('escape'), data.get('quick', (0, None))[1]} - {None}
            self.assertEqual(set(routes(number)), exits, number)
        for number in rules.ENDINGS:
            self.assertEqual(routes(number), [])

    def test_analysed_slice_is_the_first_hundred(self):
        tables = (set(rules.ENTRY_EFFECTS) | set(rules.BRANCH_TESTS) | set(rules.SHOPS) | set(COMBATS)
                  | {rules.DIE_HEAL, rules.THEFT} | {s for s, _ in rules.ITEM_ROUTES}
                  | {s for s, _ in rules.NOT_YET_ROUTES} | set(rules.ENDINGS))
        self.assertTrue(all(n in rules.ANALYSED for n in tables))
        for number in range(1, 101):
            self.assertEqual(CATALOGUE['paragraphs'][str(number)]['status'], 'analyse_verifiee')
        self.assertEqual(CATALOGUE['paragraphs']['101']['status'], 'renvois_verifies')


class CiteRulesTests(unittest.TestCase):
    def test_entry_effects_apply_once_and_respect_initial_caps(self):
        character = hero()
        self.assertTrue(rules.apply_entry(character, 16))
        self.assertEqual((character['gold'], character['chance']), (42, 10))
        self.assertFalse(rules.apply_entry(character, 16))
        self.assertEqual(character['gold'], 42)
        rules.apply_entry(character, 94)
        self.assertEqual(character['endurance'], 20)
        rules.apply_entry(character, 19)
        self.assertEqual((character['endurance'], character['habilete']), (16, 9))
        rules.apply_entry(character, 42)
        self.assertEqual(character['provisions'], 0)
        self.assertIn(rules.ARROW, character['inventory'])
        self.assertFalse(rules.apply_entry(character, 1))

    def test_mail_adds_skill_while_carried_and_is_lost_at_eleven(self):
        character = hero(inventory=['Épée', 'Bouclier'])
        rules.apply_entry(character, 46)
        self.assertEqual(rules.effective_skill(character), 12)
        rules.apply_entry(character, 11)
        self.assertEqual(character['inventory'], ['Épée'])
        self.assertEqual((character['habilete'], rules.effective_skill(character)), (9, 9))

    def test_losses_only_take_matching_items(self):
        character = hero(inventory=['Épée', 'Fleur bleue'])
        rules.apply_entry(character, 2)
        rules.apply_entry(character, 55)
        self.assertEqual(character['inventory'], ['Épée'])
        self.assertEqual(character['gold'], 40)

    def test_branch_tests_spend_luck_or_use_effective_skill(self):
        character = hero()
        self.assertEqual(rules.resolve_test(character, 49, 9), 10)
        self.assertEqual(character['chance'], 8)
        with self.assertRaises(ValueError):
            rules.resolve_test(character, 49, 2)
        self.assertEqual(rules.test_target(character, 49), 10)
        self.assertEqual(rules.resolve_test(character, 64, 12), 309)
        self.assertEqual(character['endurance'], 17)
        character['inventory'].append(rules.MAIL)
        self.assertEqual(rules.resolve_test(character, 18, 12), 102)
        self.assertEqual(rules.resolve_test(character, 69, 12), 355)

    def test_shops_keep_their_printed_limits(self):
        character = hero(gold=20)
        rules.buy(character, 36, 'Anneau de Feu')
        self.assertEqual(character['gold'], 12)
        self.assertIsNotNone(rules.can_buy(character, 36, 'Anneau de Glace'))
        rules.buy(character, 52, 'Lanterne')
        with self.assertRaises(ValueError):
            rules.buy(character, 52, 'Lanterne')
        rules.buy(character, 52, 'Poignard de Jet')
        self.assertEqual(character['gold'], 5)
        with self.assertRaises(ValueError):
            rules.buy(character, 66, 'Clef spéciale du Nain')

    def test_elf_takes_two_backpack_items_and_up_to_five_gold(self):
        character = hero(gold=3, inventory=['Épée', 'Armure de cuir', rules.GOLD_BROOCH, 'Lanterne',
                                            'Miroir', 'Corde d’Escalade'])
        self.assertEqual(rules.theft_choices(character), ['Lanterne', 'Miroir', 'Corde d’Escalade'])
        with self.assertRaises(ValueError):
            rules.elf_theft(character, ['Lanterne'])
        with self.assertRaises(ValueError):
            rules.elf_theft(character, ['Épée', 'Miroir'])
        rules.elf_theft(character, ['Lanterne', 'Miroir'])
        self.assertEqual(character['gold'], 0)
        self.assertNotIn('Miroir', character['inventory'])
        lone = hero(inventory=['Épée', 'Miroir'])
        self.assertEqual(rules.theft_required(lone), 1)

    def test_die_heal_is_capped_and_single(self):
        character = hero(endurance=17)
        rules.heal_die(character, 6)
        self.assertEqual(character['endurance'], 20)
        with self.assertRaises(ValueError):
            rules.heal_die(character, 2)

    def test_item_and_visit_conditions(self):
        character = hero()
        self.assertFalse(rules.route_available(character, 35, 305))
        self.assertTrue(rules.route_available(character, 35, 189))
        self.assertTrue(rules.route_available(character, 44, 225))
        character['inventory'].append('Poignard de Jet')
        self.assertTrue(rules.route_available(character, 44, 18))
        self.assertFalse(rules.route_available(character, 44, 225))
        character['inventory'].append('Bracelet-insecte d’argent')
        self.assertTrue(rules.route_available(character, 53, 328))
        self.assertFalse(rules.route_available(character, 53, 39))
        self.assertTrue(rules.route_available(character, 7, 232, visited=[1]))
        self.assertFalse(rules.route_available(character, 7, 232, visited=[232]))

    def test_route_prices_are_paid_once_on_choice(self):
        character = hero(gold=3)
        self.assertTrue(rules.route_available(character, 3, 37))
        self.assertTrue(rules.pay_route(character, 3, 37))
        self.assertEqual(character['gold'], 0)
        self.assertFalse(rules.pay_route(character, 3, 37))
        self.assertTrue(rules.route_available(character, 3, 37))
        self.assertFalse(rules.route_available(hero(gold=5), 169, 46))

    def test_arrow_offer_accepts_gold_or_two_items_and_otherwise_falls_back(self):
        poor = hero(gold=0, inventory=['Épée', 'Armure de cuir', 'Miroir'])
        self.assertFalse(rules.route_available(poor, 248, 85))
        self.assertTrue(rules.route_available(poor, 248, 42))
        rich = hero(gold=10)
        self.assertTrue(rules.route_available(rich, 248, 85))
        self.assertFalse(rules.route_available(rich, 248, 42))
        rules.pay_route(rich, 248, 85)
        self.assertEqual(rich['gold'], 0)
        traded = hero(gold=0, inventory=['Épée', 'Miroir', 'Lanterne'])
        with self.assertRaises(ValueError):
            rules.pay_route(traded, 248, 85, ['Épée', 'Miroir'])
        rules.pay_route(traded, 248, 85, ['Miroir', 'Lanterne'])
        self.assertEqual(traded['inventory'], ['Épée'])

    def test_endings_close_the_adventure(self):
        character = hero()
        self.assertTrue(rules.finish_ending(character, 9))
        self.assertEqual(character['endurance'], 0)
        prison = hero()
        rules.finish_ending(prison, 56)
        self.assertTrue(prison['book_facts']['adventure_ended'])
        self.assertEqual(prison['endurance'], 18)


class CiteEncounterTests(unittest.TestCase):
    def test_guard_outcome_depends_on_assault_count(self):
        self.assertEqual(victory_target(10, 6), 212)
        self.assertEqual(victory_target(10, 7), 130)
        self.assertEqual(victory_target(5, 40), 371)

    def test_escape_conditions_follow_the_printed_passage(self):
        troll = new_group_combat([[dict(e) for e in g] for g in COMBATS[73]['groups']])
        self.assertFalse(escape_status(73, troll)[0])
        troll['group'] = 1
        allowed, tip = escape_status(73, troll)
        self.assertTrue(allowed)
        self.assertIn('Habileté −1', tip)
        queen = new_group_combat([[dict(e) for e in g] for g in COMBATS[88]['groups']])
        self.assertIn('0/3', escape_status(88, queen)[1])
        queen['assaults'] = 3
        self.assertTrue(escape_status(88, queen)[0])
        self.assertFalse(escape_status(5, queen)[0])
        for allowed, tip in (escape_status(73, troll), escape_status(88, queen)):
            self.assertNotIn('§', tip)


class CiteMechanicsWindowTests(unittest.TestCase):
    setUpClass = classmethod(CitePresentationTests.setUpClass.__func__)
    setUp = CitePresentationTests.setUp
    open = CitePresentationTests.open
    start = CitePresentationTests.start
    buttons = CitePresentationTests.buttons

    def play(self):
        self.open()
        self.start()
        self.w.paragraphs.update({n: f'Passage neutre {n}.' for n in range(1, 401)})
        self.w.character['initial']['endurance'] = 20

    def events(self):
        return [self.w.event_layout.itemAt(i).widget() for i in range(self.w.event_layout.count())]

    def event_button(self, text):
        return next(b for b in self.events() if isinstance(b, QPushButton) and text in b.text())

    def winning_rolls(self):
        self.roll.side_effect = lambda count, *a, opponent=False, **k: (
            ([1] * count, count) if opponent else ([6] * count, 6 * count))
        mock = patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No)
        mock.start()
        self.addCleanup(mock.stop)

    def test_combat_blocks_routes_then_leads_to_the_printed_victory(self):
        self.play()
        self.winning_rolls()
        self.w.go_to(22)
        self.assertTrue(self.w.combat_available())
        card = self.buttons()[0]
        self.assertFalse(card.isEnabled())
        self.assertTrue(card.toolTip().startswith('Indisponible : ' + COMBAT_REASON))
        self.assertEqual(self.w.enemy_name.text(), 'Premier Lutin')
        for _ in range(3):
            self.w.combat_round()
        self.assertEqual(self.w.enemy_name.text(), 'Deuxième Lutin')
        for _ in range(3):
            self.w.combat_round()
        self.assertEqual(self.w.current_paragraph, 198)
        self.assertIn(22, self.w.completed_book_events)
        self.w.undo_action()
        self.assertEqual(self.w.current_paragraph, 22)
        self.assertTrue(self.w.combat_available())

    def test_silver_brooch_heals_after_a_won_fight(self):
        self.play()
        self.winning_rolls()
        self.w.character['inventory'].append(rules.SILVER_BROOCH)
        self.w.character['endurance'] = 15
        self.w.go_to(72)
        for _ in range(2):
            self.w.combat_round()
        self.assertEqual(self.w.current_paragraph, 208)
        self.assertEqual(self.w.character['endurance'], 16)

    def test_luck_test_button_hides_destinations_and_moves_on(self):
        self.play()
        self.w.go_to(49)
        self.assertTrue(all(not b.isEnabled() and b.toolTip().startswith('Indisponible : ' + PENDING_REASON)
                            for b in self.buttons()))
        button = self.event_button('Tenter votre Chance')
        self.assertNotIn('§', button.text() + button.toolTip())
        def traced(count, *args, **kwargs):
            if isinstance(getattr(self.w, '_roll_trace', None), list):
                self.w._roll_trace.append({'rolls': [3] * count, 'total': 3 * count,
                                            'chance': self.w.character.get('chance')})
            return [3] * count, 3 * count
        self.roll.side_effect = traced
        button.click()
        self.assertEqual(self.w.current_paragraph, 10)
        self.assertIn('Chance 9 → 8', self.w.rules_log.text())
        self.assertIn('3+3=6 ≤ 9, réussi', self.w.rules_log.text())
        self.assertTrue(self.w.combat_available())

    def test_arrival_effects_are_logged_once_and_undone(self):
        self.play()
        self.w.go_to(16)
        self.assertEqual(self.w.character['gold'], 42)
        self.assertIn('À l’arrivée au §16', self.w.rules_log.text())
        self.w.go_to(1)
        self.w.go_to(16)
        self.assertEqual(self.w.character['gold'], 42)

    def test_paid_route_is_charged_on_click_and_greyed_when_unaffordable(self):
        self.play()
        self.w.go_to(3)
        card = next(b for b in self.buttons() if '37' in b.text())
        self.assertIn('3 Pièces d’Or', card.toolTip())
        card.click()
        self.assertEqual((self.w.current_paragraph, self.w.character['gold']), (37, 27))
        self.w.character['gold'] = 2
        self.w.go_to(3)
        card = next(b for b in self.buttons() if '37' in b.text())
        self.assertTrue(card.isEnabled(), 'un prix déjà payé ne se repaie pas')

    def test_item_condition_greys_the_card_with_the_printed_condition_only(self):
        self.play()
        self.w.go_to(35)
        cards = {b.text(): b for b in self.buttons()}
        mirror = next(b for text, b in cards.items() if '305' in text)
        self.assertFalse(mirror.isEnabled())
        self.assertTrue(mirror.toolTip().startswith('Indisponible : condition du livre non remplie (Miroir).'))
        self.assertNotIn('305', mirror.toolTip())
        self.assertTrue(any(isinstance(w, QLabel) and w.text() == ANALYSED_NOTICE for w in self.events()))

    def test_shop_buys_from_printed_prices(self):
        self.play()
        self.w.go_to(52)
        self.assertTrue(self.event_button('Faire ses achats').isEnabled())
        self.w.perform_cite_action('buy', 'Poignard de Jet')
        self.assertEqual(self.w.character['gold'], 26)
        self.assertIn('Poignard de Jet', self.w.character['inventory'])
        self.w.go_to(44)
        card = next(b for b in self.buttons() if '18' in b.text())
        self.assertTrue(card.isEnabled())

    def test_theft_and_die_heal_block_until_resolved(self):
        self.play()
        self.w.go_to(63)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.w.perform_cite_action('theft', ['Lanterne'])
        self.assertEqual(self.w.character['gold'], 25)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))
        self.w.character['endurance'] = 10
        self.w.go_to(83)
        self.assertFalse(any(b.isEnabled() for b in self.buttons()))
        self.event_button('Lancer un dé').click()
        self.assertEqual(self.w.character['endurance'], 13)
        self.assertTrue(all(b.isEnabled() for b in self.buttons()))

    def test_endings_and_unanalysed_passages(self):
        self.play()
        self.w.go_to(56)
        self.assertTrue(self.w.character['book_facts']['adventure_ended'])
        self.assertTrue(any('Aventure terminée' in w.text() for w in self.events() if isinstance(w, QLabel)))
        self.w.undo_action()
        self.w.go_to(202)
        self.assertTrue(any(isinstance(w, QLabel) and w.text() == PREVIEW_NOTICE for w in self.events()))
        self.assertTrue(all(b.isEnabled() for b in self.buttons() if b.toolTip()[:11] != 'Indisponibl'))

    def test_gate_is_the_only_source_for_links(self):
        self.play()
        self.w.go_to(44)
        targets, _ = CiteController._reading_link_gate(self.w)
        self.assertEqual(targets, {225})
        self.assertEqual(self.w._reading_link_targets(), {225})
