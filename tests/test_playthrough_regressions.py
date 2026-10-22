"""Régressions tirées de la partie jouée : commandes, renvois et correction d'édition.

Les jets contrôlés ici servent à vérifier les règles après la partie réelle ;
ils ne constituent pas un parcours de jeu ni une simulation présentée comme telle.
Le texte utilisé pour tester le déplacement du fragment est une fiction minimale.
"""
import copy
import json
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QMessageBox

import main
from book_events import DATA_PATH
from combat_dialog import CombatDialog
from navigation import destinations
from pdf_text_repairs import repair_misplaced_fragment


class PlaythroughRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.w = main.MainWindow()
        self.w.paragraphs = {n: 'Passage de test.' for n in range(1, 401)}
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.autosave = patch.object(self.w, '_autosave')
        self.autosave.start()
        self.addCleanup(self.autosave.stop)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def test_combat_requires_current_encounter_and_living_opponent(self):
        self.w.go_to(1)
        self.assertFalse(self.w.combat_button.isEnabled())
        with patch.object(CombatDialog, 'exec') as dialog:
            self.w.open_combat()
        dialog.assert_not_called()
        self.w.go_to(33)
        self.assertTrue(self.w.combat_button.isEnabled())
        self.w.enemy_endurance.setValue(0)
        self.w._refresh_action_controls()
        self.assertFalse(self.w.combat_button.isEnabled())
        self.w.go_to(92)
        self.assertFalse(self.w.combat_button.isEnabled())

    def test_pending_encounters_remain_playable_inside_popup_without_stale_enemy(self):
        self.w.go_to(295)
        self.w.go_to(161)
        self.w.enemy_endurance.setValue(0)
        self.w._refresh_action_controls()
        self.assertTrue(self.w.combat_button.isEnabled())
        self.w.piranha_source_wounded = False
        self.w.go_to(350)
        self.w.enemy_endurance.setValue(0)
        self.w._refresh_action_controls()
        self.assertEqual(self.w.piranha_combat['status'], 'roll_pending')
        self.assertTrue(self.w.combat_button.isEnabled())

    def test_potion_choice_and_reroll_appear_before_final_creation_validation(self):
        self.w.pdf_path = 'livre-de-test.pdf'
        self.w._show_book_title()
        layout = self.w.choice_layout
        potion = self.w.findChild(QComboBox, 'startingPotion')
        self.assertLess(layout.indexOf(potion), layout.indexOf(self.w.creation_start_button))
        self.assertLess(layout.indexOf(self.w.creation_reroll_button), layout.indexOf(self.w.creation_start_button))
        self.assertFalse(self.w.combat_button.isEnabled())

    def test_confirmed_generic_encounter_does_not_follow_player_to_other_room(self):
        self.w.book_event_catalogue = None
        self.w.go_to(1)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.w.prepare_encounter({'name': 'Gardien', 'skill': 6, 'stamina': 4})
        self.assertTrue(self.w.combat_button.isEnabled())
        self.w.go_to(2)
        self.assertFalse(self.w.combat_button.isEnabled())

    def test_weakened_wizard_reaches_same_door_as_alternative_duel(self):
        self.w.character['habilete'] = 20
        self.w.go_to(289)
        self.assertEqual(self.w.enemy_skill.value(), 7)
        self.assertEqual(self.w.enemy_endurance.value(), 12)
        self.assertTrue(self.w._combat_exit_pending(396))
        with patch('main.random.randint', return_value=1), \
                patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            for _ in range(6):
                self.w.combat_round()
        self.assertEqual(self.w.current_paragraph, 396)
        self.assertEqual(self.w.enemy_endurance.value(), 0)
        self.assertFalse(self.w.combat_button.isEnabled())
        correction = self.catalogue['paragraphs']['289']['editorial_correction']
        self.assertEqual(correction['target'], self.catalogue['paragraphs']['142']['combat']['victory_target'])

    def test_luck_and_skill_trials_announce_correct_number_of_dice(self):
        for number, label in ((71, '🎲 Lancer les 2 dés'), (156, '🎲 Lancer les 2 dés'),
                              (339, '🎲 Lancer le dé')):
            self.w.go_to(number)
            texts = [self.w.event_layout.itemAt(i).widget().text()
                     for i in range(self.w.event_layout.count())
                     if isinstance(self.w.event_layout.itemAt(i).widget(), QPushButton)]
            self.assertIn(label, texts)

    def test_inventory_hints_do_not_confuse_victory_or_luck_with_objects(self):
        for number in (8, 17, 179):
            self.w.go_to(number)
            self.w._render_conditions('Si vous avez déjà tué le Gardien, continuez.')
            self.assertEqual(self.w.condition_layout.count(), 0)
        self.w.book_event_catalogue = None
        self.w._render_conditions('Si vous avez eu de la chance, continuez.')
        self.assertEqual(self.w.condition_layout.count(), 0)
        self.w._render_conditions('Si vous avez une lanterne, continuez.')
        self.assertTrue(any('lanterne' in self.w.condition_layout.itemAt(i).widget().text()
                            for i in range(self.w.condition_layout.count())
                            if isinstance(self.w.condition_layout.itemAt(i).widget(), QLabel)))

    def test_glued_destination_numbers_keep_all_map_exits(self):
        text = 'Rendez-vous au 294Fouiller ailleurs. Rendez-vous au 275Examiner. Rendez-vous au 148.'
        self.assertEqual([n for _, _, n in destinations(text)], [294, 275, 148])
        self.assertEqual(destinations('Rendez-vous au 1234.'), [])

    def test_misplaced_fragment_is_moved_once_and_never_invented(self):
        fragment = "bruit d'eau. Une autre salle paraît sur le point d'être ouverte, en train de s'ouvrir !"
        data = {253: 'Salle A. Qu’allez-vous faire 1 ' + fragment + '\nChoix A.',
                254: 'Salle B. On écoute en entendant un\nTandis que la porte bouge.'}
        repair_misplaced_fragment(data)
        self.assertNotIn(fragment, data[253])
        self.assertIn('Qu’allez-vous faire ?', data[253])
        self.assertIn(fragment, data[254])
        self.assertIn("un bruit d'eau", data[254])
        once = copy.deepcopy(data)
        repair_misplaced_fragment(data)
        self.assertEqual(data, once)
        incomplete = {253: once[253], 254: 'Autre édition sans raccord.'}
        original = copy.deepcopy(incomplete)
        repair_misplaced_fragment(incomplete)
        self.assertEqual(incomplete, original)
