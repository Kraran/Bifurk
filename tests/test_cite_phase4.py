"""Cité des Voleurs, phase 4 : vente, jeux d’argent, états, variantes de combat, quête finale.

Les mécaniques sont celles des phases 3.1 à 3.4 ; ces tests vérifient chaque puce
de la phase 4 du plan, ainsi que ses deux changements : le tatouage est une marque
hors du sac, et le choix final du §244 n’affiche ni carte grisée ni infobulle.
Aucun texte du livre : PDF synthétique aux passages neutres.
"""
import copy
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from grimoire_modules.cite import feedback, rules
from grimoire_modules.cite.encounters import COMBATS, escape_status, victory_target
from grimoire_modules.fighting_fantasy.adventure import new_group_combat
from tests import test_cite_mechanics as mechanics
from tests import test_cite_phase3_2 as second_hundred
from tests.test_cite_mechanics import hero

MISSION = ['Flèche d’argent', 'Perles noires', 'Cheveux de Sorcière', 'Fleur de lotus']


class CitePhaseFourRulesTests(unittest.TestCase):
    # ----- États qui ne sont pas des objets ---------------------------------------
    def test_tattoo_is_a_mark_out_of_the_bag(self):
        character = hero(inventory=['Épée'] + MISSION)
        rules.apply_entry(character, 279)
        self.assertEqual(rules.marks(character), [rules.TATTOO])
        self.assertNotIn(rules.TATTOO, character['inventory'])
        self.assertNotIn(rules.TATTOO, rules.theft_choices(character))
        self.assertNotIn(rules.TATTOO, [name for name, _price in rules.pawn_choices(character)])
        self.assertNotIn(rules.TATTOO, rules.magic_payment_choices(character))
        self.assertTrue(rules.mission_ready(character, ()))
        # Relire le §279 (retour au §316) ne double pas la marque.
        rules.add_mark(character, rules.TATTOO)
        self.assertEqual(rules.marks(character), [rules.TATTOO])

    def test_legacy_tattoo_in_the_bag_becomes_a_mark(self):
        character = hero(inventory=['Épée', rules.TATTOO] + MISSION, locked_items=[rules.TATTOO])
        self.assertTrue(rules.mission_ready(character, ()))
        self.assertTrue(rules.migrate_marks(character))
        self.assertNotIn(rules.TATTOO, character['inventory'])
        self.assertNotIn(rules.TATTOO, character['locked_items'])
        self.assertEqual(rules.marks(character), [rules.TATTOO])
        self.assertFalse(rules.migrate_marks(character))
        self.assertTrue(rules.mission_ready(character, ()))

    def test_marks_and_creature_memory_live_in_the_book_state(self):
        character = hero()
        rules.apply_entry(character, 279)
        rules.choose_mixture(character, 9)
        rules.roll_creature(character, rules.APE_MAN)
        saved = copy.deepcopy(character)
        self.assertEqual(rules.marks(saved), [rules.TATTOO])
        self.assertEqual(rules.peek(saved)['creature'], rules.APE_MAN)
        self.assertTrue(rules.route_available(saved, 138, 312))
        self.assertFalse(rules.route_available(saved, 138, 283))

    def test_arrival_summary_names_the_mark(self):
        character = hero()
        before = feedback.snapshot(character)
        rules.apply_entry(character, 279)
        self.assertEqual(feedback.describe_changes(before, feedback.snapshot(character)),
                         ['Marque : ' + rules.TATTOO])

    # ----- Quête finale et choix final ---------------------------------------------
    def test_final_quest_is_checked_only_by_the_written_routes(self):
        character = hero(inventory=['Épée'] + MISSION[:3])
        rules.apply_entry(character, 279)
        for source in (108, 156, 239, 367):
            self.assertFalse(rules.route_available(character, source, 201))
            self.assertTrue(rules.route_available(character, source, 299))
        character['inventory'].append(MISSION[3])
        for source in (108, 156, 239, 367):
            self.assertTrue(rules.route_available(character, source, 201))
            self.assertFalse(rules.route_available(character, source, 299))

    def test_only_the_prepared_mixture_is_shown_at_244(self):
        character = hero()
        targets = [target for _name, target in rules.MIXTURES]
        self.assertEqual([t for t in targets if rules.route_shown(character, 244, t)], targets)
        rules.choose_mixture(character, 129)
        self.assertEqual([t for t in targets if rules.route_shown(character, 244, t)], [129])
        self.assertTrue(rules.route_shown(character, 243, 1))

    # ----- Vente et jeux d’argent ----------------------------------------------------
    def test_sales_follow_the_printed_prices(self):
        character = hero(gold=0, inventory=['Épée', 'Deux pierres précieuses'])
        rules.apply_entry(character, 240)
        self.assertEqual(character['gold'], 9)
        self.assertNotIn('Deux pierres précieuses', character['inventory'])

    def test_stakes_are_checked_against_the_purse(self):
        self.assertIsNotNone(rules.can_gamble(hero(gold=rules.GAMBLE_STAKE - 1)))
        self.assertIsNone(rules.can_gamble(hero(gold=rules.GAMBLE_STAKE)))
        with self.assertRaises(ValueError):
            rules.gamble(hero(gold=1), [2, 2, 2], 12)

    # ----- Variantes de combat --------------------------------------------------------
    def test_combat_variants_of_the_plan(self):
        self.assertEqual(COMBATS[157]['attack'], -3)
        self.assertEqual(COMBATS[253]['wound'], 4)
        self.assertEqual(COMBATS[392]['fire'], (1, 2, 3))
        self.assertEqual(len(COMBATS[326]['groups'][0]), 2)
        self.assertEqual((victory_target(10, 6), victory_target(10, 7)), (212, 130))
        combat = new_group_combat([[{'name': 'Ogre', 'skill': 8, 'stamina': 9}]])
        combat['assaults'] = 2
        self.assertFalse(escape_status(140, combat)[0])
        combat['assaults'] = 3
        self.assertTrue(escape_status(140, combat)[0])

    # ----- Soins et pertes ----------------------------------------------------------------
    def test_die_heals_are_capped(self):
        character = hero(endurance=18)
        rules.heal_die(character, 6)
        self.assertEqual(character['endurance'], 20)
        kept = hero(endurance=10)
        rules.apply_entry(kept, 167)
        self.assertTrue(rules.has_item(kept, 'emplatre'))
        rules.use_poultice(kept, 4)
        self.assertEqual(kept['endurance'], 14)
        self.assertFalse(rules.has_item(kept, 'emplatre'))

    def test_armour_removed_at_11(self):
        character = hero(inventory=['Épée', rules.MAIL, rules.SHIELD])
        rules.apply_entry(character, 11)
        self.assertNotIn(rules.MAIL, character['inventory'])
        self.assertNotIn(rules.SHIELD, character['inventory'])


class CitePhaseFourWindowTests(unittest.TestCase):
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

    @staticmethod
    def bare_tooltip(card):
        """Seul le raccourci clavier commun (« Touche 1 ») : ni condition ni indice."""
        tip = card.toolTip()
        return not tip or (tip.startswith('Touche ') and len(tip.split()) == 2)

    def test_final_choice_has_no_greyed_card_nor_tooltip(self):
        self.play()
        rules.choose_mixture(self.w.character, 337)
        self.w.go_to(244)
        cards = self.buttons()
        self.assertEqual(len(cards), 1)
        self.assertIn('337', cards[0].text())
        self.assertTrue(cards[0].isEnabled())
        self.assertTrue(self.bare_tooltip(cards[0]))
        self.no_spoiler()

    def test_final_choice_without_a_recorded_mixture_keeps_three_open_cards(self):
        self.play()
        self.w.go_to(244)
        cards = self.buttons()
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(card.isEnabled() and self.bare_tooltip(card) for card in cards))

    def test_tattoo_arrival_is_reported_and_kept_out_of_the_bag(self):
        self.play()
        self.w.go_to(279)
        self.assertNotIn(rules.TATTOO, self.w.character['inventory'])
        self.assertIn('Marque : ' + rules.TATTOO, self.w.rules_log.text())
        names = [self.w.inventory_list.item(i).text() for i in range(self.w.inventory_list.count())]
        self.assertNotIn(rules.TATTOO, names)

    def test_legacy_save_with_a_tattoo_item_is_migrated_on_restore(self):
        self.play()
        self.w.go_to(307)
        state = self.w._snapshot()
        state['character']['inventory'].append(rules.TATTOO)
        state['character'].setdefault('locked_items', []).append(rules.TATTOO)
        self.w._restore(state)
        self.assertNotIn(rules.TATTOO, self.w.character['inventory'])
        self.assertEqual(rules.marks(self.w.character), [rules.TATTOO])

    def test_quick_victory_at_10_and_slow_victory_route(self):
        self.play()
        self.luck_no()
        self.w.character['endurance'] = 20
        self.w.go_to(10)
        # Trois assauts perdus puis quatre gagnés : sept assauts, la suite est le §130.
        lose = [6, 6, 1, 1]
        win = [1, 1, 6, 6]
        self.fixed_rolls(*(lose * 3 + win * 4))
        for _ in range(7):
            self.w.combat_round()
        self.assertEqual(self.w.current_paragraph, 130)
        self.w.undo_action()
        self.assertEqual(self.w.current_paragraph, 10)

    def test_ogre_escape_opens_after_three_assaults(self):
        self.play()
        self.luck_no()
        self.w.character['endurance'] = 20
        self.w.go_to(140)
        allowed, reason = self.w.combat_flee_status()
        self.assertFalse(allowed)
        self.assertIn('0/3', reason)
        self.fixed_rolls(*([6, 6, 1, 1] * 3))
        for _ in range(3):
            self.w.combat_round()
        self.assertTrue(self.w.combat_flee_status()[0])

    def test_losses_and_gambling_can_be_undone(self):
        self.play()
        self.w.character['inventory'] += ['Miroir', 'Corde']
        self.w.go_to(63)
        chosen = rules.theft_choices(self.w.character)[:rules.theft_required(self.w.character)]
        before = (self.w.character['gold'], list(self.w.character['inventory']))
        self.w.perform_cite_action('theft', chosen)
        self.assertNotEqual((self.w.character['gold'], self.w.character['inventory']), before)
        self.w.undo_action()
        self.assertEqual((self.w.character['gold'], self.w.character['inventory']), before)
        self.w.go_to(206)
        gold = self.w.character['gold']
        self.fixed_rolls(6, 6, 6, 6, 6, 6, 1, 1)
        self.event_button('Jouer une partie').click()
        self.assertEqual(self.w.character['gold'], gold - rules.GAMBLE_STAKE)
        self.w.undo_action()
        self.assertEqual(self.w.character['gold'], gold)

    def test_dice_games_show_the_stake_without_spoiling(self):
        self.play()
        self.w.go_to(206)
        button = self.event_button('Jouer une partie')
        self.assertIn(str(rules.GAMBLE_STAKE), button.text())
        self.no_spoiler()
        self.w.character['gold'] = 1
        self.w.go_to(206)
        self.assertFalse(self.event_button('Jouer une partie').isEnabled())
