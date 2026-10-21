"""Commandes permanentes, soins réglementaires et défilement du champ de bataille.

Les scénarios utilisent le catalogue vérifié, des widgets Qt réels et des dés
contrôlés. Les vérifications de géométrie simulent une fenêtre basse avec beaucoup
d'actions et de coups : le contenu doit défiler, pas déborder sur les commandes.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QPushButton

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from book_events import DATA_PATH
from combat_dialog import CombatDialog


class CombatControlsTests(unittest.TestCase):
    """Ne permettre ni fuite hors règle, ni repas en combat, ni second jet au soin."""

    @classmethod
    def setUpClass(cls):
        """Partager l'application et les données de référence sans PDF."""
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        """Créer une partie isolée et empêcher toute écriture de sauvegarde réelle."""
        autosave = patch.object(main.MainWindow, '_autosave')
        autosave.start()
        self.addCleanup(autosave.stop)
        self.w = main.MainWindow()
        self.w.character['name'] = 'Éléanor'
        self.w.paragraphs = {n: 'Passage de test.' for n in range(1, 401)}
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)

    def tearDown(self):
        """Fermer les vues et libérer les minuteries Qt après chaque contrôle."""
        self.w._combat_dialog = None
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def session(self, number):
        """Préparer un vrai combat et son dialogue sans lancer automatiquement un assaut."""
        self.w.go_to(number)
        self.w.undo_stack.clear()
        dialog = CombatDialog(self.w)
        self.w._combat_popup = self.w._combat_dialog = dialog
        return dialog

    def test_flee_is_permanent_and_respects_assault_threshold_and_missing_destination(self):
        dialog = self.session(16)
        self.assertEqual(dialog.flee.text(), 'Fuir')
        self.assertFalse(dialog.flee.isEnabled())
        self.w.book_combat_assaults[16] = 2
        dialog.refresh_stats()
        self.assertTrue(dialog.flee.isEnabled())
        dialog.busy = True
        dialog._refresh_footer()
        self.assertFalse(dialog.flee.isEnabled())
        dialog.busy = False
        self.w.paragraphs.pop(269)
        dialog._refresh_footer()
        self.assertFalse(dialog.flee.isEnabled())

    def test_initial_flee_is_available_before_any_enemy_roll(self):
        dialog = self.session(8)
        with patch.object(self.w, '_roll') as roll:
            dialog.show()
            self.app.processEvents()
        roll.assert_not_called()
        self.assertTrue(dialog.flee.isEnabled())
        self.assertEqual(dialog.phase, 'next')
        self.assertEqual(self.w.book_combat_assaults.get(8, 0), 0)
        dialog.close()

    def test_meals_forbidden_in_combat_but_potion_available(self):
        dialog = self.session(16)
        self.w.character.update(endurance=4, potion='Potion de Vigueur', potion_doses=1)
        dialog.refresh_stats()
        self.assertTrue(dialog.care.isEnabled())
        options = self.w.care_options(in_combat=True)
        self.assertTrue(options[0]['enabled'])
        self.assertFalse(options[1]['enabled'])
        self.w.use_care('meal')
        self.assertEqual(self.w.character['provisions'], 10)
        dialog._apply_care('potion')
        self.assertEqual(self.w.character['endurance'], 20)
        self.assertEqual(self.w.character['potion_doses'], 0)
        self.assertFalse(dialog.care.isEnabled())
        self.assertEqual(self.w.stat_spins['endurance'].value(), 20)

    def test_potion_during_player_pause_keeps_rolls_and_one_undo_transaction(self):
        dialog = self.session(8)
        self.w.character.update(habilete=20, endurance=1, potion='Potion de Vigueur', potion_doses=1)
        self.w.enemy_endurance.setValue(2)
        dialog.choose_luck = Mock(return_value=False)

        def present(rolls, context, *, opponent=False):
            if not opponent:
                dialog.phase = 'player'
                dialog._apply_care('potion')

        dialog.present_roll = present
        with patch('main.random.randint', return_value=1) as draw:
            dialog._run(self.w.combat_round)
        self.assertEqual(draw.call_count, 4)
        self.assertEqual(dialog.outcome, 'Victoire')
        self.assertEqual(self.w.character['endurance'], 20)
        self.assertEqual(len(self.w.undo_stack), 1)
        self.w._combat_dialog = None
        self.w.undo_action()
        self.assertEqual(self.w.character['endurance'], 1)
        self.assertEqual(self.w.character['potion_doses'], 1)

    def test_authorized_meal_once_and_undo_restores_permission(self):
        self.w.go_to(77)
        self.w.character['endurance'] = 8
        self.w.undo_stack.clear()
        self.assertTrue(self.w.care_options()[1]['enabled'])
        self.w.use_care('meal')
        self.w.use_care('meal')
        self.assertEqual((self.w.character['endurance'], self.w.character['provisions']), (12, 9))
        self.assertEqual(len(self.w.undo_stack), 1)
        self.assertFalse(self.w.care_options()[1]['enabled'])
        self.w.undo_action()
        self.assertTrue(self.w.care_options()[1]['enabled'])
        self.assertEqual((self.w.character['endurance'], self.w.character['provisions']), (8, 10))

    def test_meal_requires_book_permission_and_useful_healing(self):
        self.w.go_to(1)
        self.w.character['endurance'] = 8
        self.assertFalse(self.w.care_options()[1]['enabled'])
        self.w.go_to(77)
        self.w.character['endurance'] = 20
        self.assertFalse(self.w.care_options()[1]['enabled'])
        self.w.character.update(endurance=8, provisions=0)
        self.assertFalse(self.w.care_options()[1]['enabled'])

    def test_post_piranhas_meal_and_fortune_at_full_chance_remain_usable(self):
        self.w.piranha_combat = {'status': 'victory'}
        self.w.go_to(7)
        self.w.character.update(endurance=8, potion='Potion de Bonne Fortune', potion_doses=1)
        self.assertTrue(all(o['enabled'] for o in self.w.care_options()))
        self.w.use_care('potion')
        self.assertEqual(self.w.character['chance'], 9)
        self.assertEqual(self.w.character['initial']['chance'], 9)

    def test_shield_and_weapon_use_same_state_as_inventory(self):
        dialog = self.session(8)
        self.w.character['equipped_weapon'] = 'Épée'
        self.w.character['inventory'] += ['Bouclier au croissant', 'Épée magique']
        self.w._refresh_character()
        dialog.weapon.setCurrentText('Épée magique')
        self.assertEqual(self.w.character['equipped_weapon'], 'Épée magique')
        dialog.shield.setChecked(True)
        self.assertTrue(self.w.character['shield_equipped'])
        self.assertTrue(self.w.shield_check.isChecked())

    def test_reader_no_longer_creates_combat_and_dice_tabs(self):
        self.w.go_to(1)
        self.w.show()
        self.app.processEvents()
        self.assertEqual(self.w.adventure_tabs.count(), 1)
        self.assertEqual(self.w.adventure_tabs.tabText(0), 'Sacoche')
        self.assertFalse(self.w.adventure_tabs.tabBar().isVisible())
        self.assertTrue(self.w.combat_button.isVisible())
        self.assertTrue(self.w.tools_button.isVisible())
        self.assertFalse(self.w._engine_fields.isVisible())

    def test_long_history_and_many_actions_scroll_inside_their_frames(self):
        dialog = self.session(16)
        for i in range(20):
            source = QPushButton(f'Action spéciale {i} — Choisir cette stratégie et poursuivre le combat dans la salle')
            source.setProperty('combatAction', True)
            self.w.event_layout.addWidget(source)
        dialog._refresh_actions()
        for i in range(120):
            dialog.log(f'Assaut {i} : attaque 16 contre 12. Deux points d’Endurance perdus.')
        dialog.resize(900, 620)
        dialog.show()
        dialog._begin_timer.stop()
        self.app.processEvents()
        self.assertEqual(dialog.size().height(), 620)
        self.assertGreater(dialog.history.verticalScrollBar().maximum(), 0)
        self.assertGreater(dialog.action_scroll.verticalScrollBar().maximum(), 0)
        self.assertLessEqual(dialog.action_scroll.widget().width(), dialog.action_scroll.viewport().width())
        self.assertLess(dialog.action_scroll.mapTo(dialog, dialog.action_scroll.rect().bottomLeft()).y(), dialog.prompt.y())
        self.assertLessEqual(dialog.flee.geometry().bottom(), dialog.height())
        self.assertEqual(dialog.history.horizontalScrollBar().maximum(), 0)
        dialog.close()


if __name__ == '__main__':
    unittest.main()
