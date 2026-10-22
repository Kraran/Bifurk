"""Contrat du socle commun, exercé sans contrôleur ni catalogue du Sorcier."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QMessageBox
from grimoire_modules.fighting_fantasy import rules
from grimoire_modules.fighting_fantasy.controller import FightingFantasyActions


def character():
    return {'habilete': 8, 'endurance': 20, 'chance': 8,
            'initial': {'habilete': 8, 'endurance': 20, 'chance': 8},
            'provisions': 10, 'inventory': [], 'potion': 'Potion de Vigueur',
            'potion_doses': 2}


class CommonRulesTests(unittest.TestCase):
    def test_creation_bounds_and_impossible_rolls(self):
        self.assertEqual(rules.adventurer_stats(1, 2, 1), {'habilete': 7, 'endurance': 14, 'chance': 7})
        self.assertEqual(rules.adventurer_stats(6, 12, 6), {'habilete': 12, 'endurance': 24, 'chance': 12})
        for values in ((0, 2, 1), (1, 13, 1), (1, 2, 7)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                rules.adventurer_stats(*values)

    def test_luck_uses_pre_spend_score_and_never_becomes_negative(self):
        hero = character()
        self.assertTrue(rules.spend_luck(hero, 8))
        self.assertEqual(hero['chance'], 7)
        self.assertFalse(rules.spend_luck(hero, 8))
        hero['chance'] = 0
        self.assertFalse(rules.spend_luck(hero, 2))
        self.assertEqual(hero['chance'], 0)
        before = copy.deepcopy(hero)
        with self.assertRaises(ValueError):
            rules.spend_luck(hero, 13)
        self.assertEqual(hero, before)

    def test_combat_and_escape_damage_tables(self):
        for lucky, attack, defense in ((None, 2, 2), (True, 4, 1), (False, 1, 3)):
            with self.subTest(lucky=lucky):
                self.assertEqual(rules.combat_damage(attacking=True, lucky=lucky), attack)
                self.assertEqual(rules.combat_damage(attacking=False, lucky=lucky), defense)
        self.assertEqual(rules.escape_damage(8), (2, 0))
        self.assertEqual(rules.escape_damage(8, 8), (1, 1))
        self.assertEqual(rules.escape_damage(8, 9), (3, 1))

    def test_vigor_and_skill_have_two_doses_without_changing_caps(self):
        for potion, stat in (("Potion d'Adresse", 'habilete'), ('Potion de Vigueur', 'endurance')):
            with self.subTest(potion=potion):
                hero = character()
                hero['potion'] = potion
                initial = copy.deepcopy(hero['initial'])
                for remaining in (1, 0):
                    hero[stat] = 1
                    result = rules.drink_potion(hero)
                    self.assertEqual(result.remaining, remaining)
                    self.assertEqual(hero[stat], initial[stat])
                    self.assertEqual(hero['initial'], initial)
                hero[stat] = 1
                self.assertIsNone(rules.drink_potion(hero))
                self.assertEqual(hero[stat], 1)

    def test_each_fortune_dose_increases_initial_luck_once(self):
        hero = character()
        hero['potion'] = 'Potion de Bonne Fortune'
        for expected in (9, 10):
            self.assertTrue(rules.potion_useful(hero))
            rules.drink_potion(hero)
            self.assertEqual(hero['chance'], expected)
            self.assertEqual(hero['initial']['chance'], expected)
        self.assertIsNone(rules.drink_potion(hero))
        self.assertEqual(hero['initial']['chance'], 10)

    def test_useless_unknown_and_post_death_potions_do_not_mutate(self):
        for update in ({}, {'potion': 'Potion inconnue'}, {'endurance': 0}):
            with self.subTest(update=update):
                hero = character() | update
                before = copy.deepcopy(hero)
                self.assertIsNone(rules.drink_potion(hero))
                self.assertEqual(hero, before)

    def test_meal_is_capped_costs_one_provision_and_cannot_revive(self):
        hero = character()
        hero['endurance'] = 18
        result = rules.eat_meal(hero)
        self.assertEqual((result.after, result.remaining), (20, 9))
        hero['provisions'] = 0
        hero['endurance'] = 5
        self.assertIsNone(rules.eat_meal(hero))
        hero.update(provisions=1, endurance=0)
        self.assertIsNone(rules.eat_meal(hero))
        self.assertEqual(hero['provisions'], 1)


class Value:
    """Champ minimal d'un hôte : les règles n'exigent pas une fenêtre du Sorcier."""
    def __init__(self, value):
        self.content = value

    def value(self):
        return self.content

    def setValue(self, value):
        self.content = value

    def text(self):
        return self.content

    def setText(self, value):
        self.content = value


class CommonHost(FightingFantasyActions):
    """Hôte volontairement dépourvu d'état Crocodile/Piranhas ou d'actions du Sorcier."""
    def __init__(self):
        self.character = character()
        self.current_paragraph = 1
        self.paragraphs = {1: 'Départ', 2: 'Sortie'}
        self.book_event_catalogue = {'paragraphs': {'1': {'status': 'verifie', 'combat': {
            'enemies': [{'name': 'Adversaire', 'skill': 8, 'stamina': 4}]}}}}
        self.book_combat_sequence = None
        self.book_combat_assaults = {}
        self.prepared_book_encounters = set()
        self.encounter_history = {}
        self._adventurer_draft = None
        self._combat_dialog = None
        self.enemy_skill, self.enemy_endurance = Value(8), Value(4)
        self.enemy_name = Value('Adversaire')
        self.rules_log, self.combat_state = Value(''), Value('')
        self.sounds = SimpleNamespace(play=Mock())
        self._refresh_character = Mock()
        self._render_choices_and_events = Mock()
        self._remember_monster = Mock()
        self._assault_luck_choice = Mock(return_value=QMessageBox.No)
        self._ask_combat_question = Mock(return_value=QMessageBox.No)
        self._roll = Mock()
        self.assaults = []

    def _log_assault(self, player, enemy, attack, defense, outcome):
        self._book_round_played = True
        self._ff_record_assault()
        self.assaults.append((attack, defense, outcome))

    def go_to(self, number):
        self.current_paragraph = number


class CommonControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_assault_does_not_inherit_sorcier_objects_or_special_modes(self):
        host = CommonHost()
        host.character.update(inventory=['Épée trouvée dans la rivière', 'Casque magique', 'Bouclier au croissant'],
            shield_equipped=True, book_facts={'magic_helmet_equipped': True})
        host.book_event_catalogue['paragraphs']['1']['combat']['mode'] = 'fire_breath'
        host._roll.side_effect = [([3, 3], 6), ([3, 3], 6)]
        host.combat_round()
        self.assertEqual(host._roll.call_count, 2)
        self.assertEqual(host.assaults, [(14, 14, 'Parade')])
        self.assertEqual(host.character['endurance'], 20)
        # Même inventaire, mais sans réduction de bouclier sur une vraie blessure.
        host._roll.side_effect = [([6, 6], 12), ([1, 1], 2)]
        host.combat_round()
        self.assertEqual(host.character['endurance'], 18)
        self.assertEqual(host._roll.call_count, 4)

    def test_optional_luck_modifies_damage_and_spends_only_one_point(self):
        for winning, lucky, expected in ((True, True, 4), (True, False, 1), (False, True, 1), (False, False, 3)):
            with self.subTest(winning=winning, lucky=lucky):
                host = CommonHost()
                host.enemy_endurance.setValue(10)
                host._assault_luck_choice.return_value = QMessageBox.Yes
                low, high = ([1, 1], 2), ([6, 6], 12)
                host._roll.side_effect = [low if winning else high, high if winning else low,
                                         ([3, 3], 6) if lucky else ([6, 6], 12)]
                host.combat_round()
                self.assertEqual(host.character['chance'], 7)
                self.assertEqual(host._roll.call_count, 3)
                self.assertEqual(10 - host.enemy_endurance.value() if winning else 20 - host.character['endurance'], expected)

    def test_parries_count_for_flee_and_escape_pays_damage_before_navigation(self):
        host = CommonHost()
        combat = host.book_event_catalogue['paragraphs']['1']['combat']
        combat.update(escape_target=2, escape_after_assaults=2)
        host._roll.side_effect = [([3, 3], 6)] * 4
        self.assertFalse(host.can_flee_combat())
        host.combat_round()
        self.assertFalse(host.can_flee_combat())
        host.combat_round()
        self.assertTrue(host.can_flee_combat())
        host.escape_scripted_combat(1)
        self.assertEqual((host.character['endurance'], host.current_paragraph), (18, 2))
        self.assertEqual(host._roll.call_count, 4)

    def test_fatal_escape_never_reaches_destination(self):
        host = CommonHost()
        host.book_event_catalogue['paragraphs']['1']['combat']['escape_target'] = 2
        host.character['endurance'] = 1
        host.escape_scripted_combat(1)
        self.assertEqual((host.character['endurance'], host.current_paragraph), (0, 1))
        host._roll.assert_not_called()

    def test_meal_permission_is_per_passage_and_once_only(self):
        host = CommonHost()
        host.character['endurance'] = 10
        self.assertFalse(host.care_options()[1]['enabled'])
        host.book_event_catalogue['paragraphs']['1']['optional_meal'] = True
        self.assertFalse(host.care_options(in_combat=True)[1]['enabled'])
        host.use_care('meal')
        self.assertEqual((host.character['endurance'], host.character['provisions']), (14, 9))
        host.use_care('meal')
        self.assertEqual((host.character['endurance'], host.character['provisions']), (14, 9))

    def test_no_dice_after_death_or_defeated_enemy(self):
        for hero_dead in (True, False):
            host = CommonHost()
            if hero_dead:
                host.character['endurance'] = 0
            else:
                host.enemy_endurance.setValue(0)
            host.combat_round()
            host._roll.assert_not_called()

    def test_sequence_prepares_next_enemy_and_follows_final_victory_only(self):
        host = CommonHost()
        enemies = [{'name': 'Premier', 'skill': 8, 'stamina': 2},
                   {'name': 'Second', 'skill': 8, 'stamina': 2}]
        host.book_event_catalogue['paragraphs']['1']['combat'].update(
            mode='sequence', enemies=enemies, victory_target=2)
        host.book_combat_sequence = {'paragraph': 1, 'index': 0}
        host.enemy_endurance.setValue(2)
        host._roll.side_effect = [([1, 1], 2), ([6, 6], 12)] * 2
        host.combat_round()
        self.assertEqual(host.current_paragraph, 1)
        self.assertEqual((host.enemy_name.text(), host.enemy_endurance.value()), ('Second', 2))
        host.combat_round()
        self.assertEqual(host.current_paragraph, 2)
        self.assertIsNone(host.book_combat_sequence)
        self.assertEqual(host._roll.call_count, 4)

    def test_common_controller_works_through_real_window_dispatch_and_undo(self):
        from main import MainWindow
        from grimoire_modules.controller import CONTROLLERS
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.book_module = SimpleNamespace(engine='common-test', id='common-test')
        window.current_paragraph = 1
        window.paragraphs = {1: 'Rencontre'}
        window.book_event_catalogue = {'paragraphs': {'1': {'status': 'verifie'}}}
        with patch.dict(CONTROLLERS, {'common-test': FightingFantasyActions}), \
             patch.object(window, '_roll', side_effect=[([6, 6], 12), ([1, 1], 2)]), \
             patch.object(window, '_assault_luck_choice', return_value=QMessageBox.No):
            from combat_dialog import CombatDialog
            window.character['inventory'] += ['Épée trouvée dans la rivière', 'Casque magique']
            window.character['book_facts'] = {'magic_helmet_equipped': True}
            dialog = CombatDialog(window)
            try:
                self.assertIn('Habileté de combat : 8', dialog.hero.text())
            finally:
                dialog.close()
                dialog.deleteLater()
            before = window.character['endurance']
            window.combat_round()
            self.assertEqual(window.character['endurance'], before - 2)
            self.assertEqual(len(window.undo_stack), 1)
            # La restauration de l'écran narratif appartient à l'adaptateur du livre.
            with patch.object(window, '_restore') as restore:
                window.undo_action()
                self.assertEqual(restore.call_args.args[0]['character']['endurance'], before)
