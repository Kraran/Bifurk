"""Variations animées : valeurs réelles, cumul d'action et restaurations silencieuses."""
import random
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from combat_dialog import CombatDialog
from main import MainWindow
from stat_feedback import STAT_LABELS, rich_stat_anchor


class StatFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = MainWindow()
        self.w.paragraphs = {1: 'Une galerie tranquille.'}
        self.w.go_to(1)
        self.w.show()
        self.app.processEvents()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)

    def test_real_values_update_immediately_and_repaint_does_not_repeat_delta(self):
        self.w.set_stat('endurance', 18)
        badge = self.w.stat_feedback.active['endurance'][0]
        self.assertEqual(badge.text(), '−2')
        self.assertEqual(self.w.stat_spins['endurance'].value(), 18)
        self.assertEqual(self.w.stat_bars['endurance'].value(), 90)
        self.assertTrue(badge.testAttribute(Qt.WA_TransparentForMouseEvents))
        badge.animation.setCurrentTime(400)
        self.w._refresh_character()
        self.assertIs(self.w.stat_feedback.active['endurance'][0], badge)
        self.assertEqual(badge.animation.currentTime(), 400)

    def test_healing_uses_effective_gain_up_to_the_initial_maximum(self):
        self.w.set_stat('endurance', 18)
        self.w.character.update(potion='Potion de Vigueur', potion_doses=1)
        self.w.drink_potion()
        badge = self.w.stat_feedback.active['endurance'][0]
        self.assertEqual(badge.text(), '+2')
        self.assertEqual(self.w.character['endurance'], 20)
        self.assertEqual(self.w.character['potion_doses'], 0)

    def test_one_action_combines_rapid_changes_but_next_action_starts_its_own_delta(self):
        self.w.character['endurance'] = 19
        self.w._refresh_character()
        self.w.character['endurance'] = 17
        self.w._refresh_character()
        self.assertEqual(self.w.stat_feedback.active['endurance'][0].text(), '−3')
        self.w.set_stat('endurance', 15)
        self.assertEqual(self.w.stat_feedback.active['endurance'][0].text(), '−2')

    def test_restore_clears_old_badges_and_sets_new_reference_silently(self):
        original = self.w._snapshot()
        self.w.set_stat('endurance', 12)
        self.assertIn('endurance', self.w.stat_feedback.active)
        self.w._restore(original)
        self.assertEqual(self.w.stat_feedback.active, {})
        self.w.set_stat('endurance', 19)
        self.assertEqual(self.w.stat_feedback.active['endurance'][0].text(), '−1')

    def test_creation_and_hidden_window_do_not_announce_false_gains(self):
        self.w.current_paragraph = None
        with patch('main.random.randint', return_value=1):
            self.w._prepare_adventurer()
        self.assertEqual(self.w.stat_feedback.active, {})
        self.w._adventurer_draft = None
        self.w.current_paragraph = 1
        self.w._refresh_character()
        self.assertEqual(self.w.stat_feedback.active, {})
        self.w.hide()
        self.w.character['chance'] -= 1
        self.w._refresh_character()
        self.assertEqual(self.w.stat_feedback.active, {})
        self.w.show()
        self.w._refresh_character()
        self.assertEqual(self.w.stat_feedback.active, {})

    def test_animation_finishes_without_changing_state_history_or_randomness(self):
        self.w.set_stat('chance', 7)
        state, rng = self.w._snapshot(), random.getstate()
        badge = self.w.stat_feedback.active['chance'][0]
        badge.animation.setCurrentTime(badge.DURATION_MS)
        self.assertNotIn('chance', self.w.stat_feedback.active)
        self.assertFalse(badge.isVisible())
        self.assertEqual(self.w._snapshot(), state)
        self.assertEqual(random.getstate(), rng)

    def combat(self):
        self.w.enemy_skill.setValue(10)
        self.w.enemy_endurance.setValue(10)
        dialog = CombatDialog(self.w)
        dialog.present_roll = Mock()
        dialog.choose_luck = Mock(return_value=False)
        self.w._combat_dialog = dialog
        self.addCleanup(setattr, self.w, '_combat_dialog', None)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog._begin_timer.stop()
        self.app.processEvents()
        return dialog

    def test_actual_combat_hit_animates_both_views_without_repeating_damage(self):
        dialog = self.combat()
        with patch('main.random.randint', return_value=1) as draw:
            dialog._run(self.w.combat_round)
        self.assertEqual(draw.call_count, 4)
        self.assertEqual(self.w.character['endurance'], 18)
        self.assertEqual(dialog.stat_feedback.active['endurance'][0].text(), '−2')
        self.assertEqual(self.w.stat_feedback.active['endurance'][0].text(), '−2')
        self.assertIn('Endurance 18', dialog.hero.text())
        badge = dialog.stat_feedback.active['endurance'][0]
        dialog.refresh_stats()
        self.assertIs(dialog.stat_feedback.active['endurance'][0], badge)

    def test_combat_anchors_follow_wrapped_names_and_unicode(self):
        self.w.character['name'] = '🌙 Endurance 20 ' + 'Longnom ' * 4
        dialog = self.combat()
        anchors = [rich_stat_anchor(dialog.hero, f'{label} {self.w.character[key]}')
                   for key, label in STAT_LABELS.items()]
        self.assertLess(anchors[0].y(), anchors[1].y())
        self.assertLess(anchors[1].y(), anchors[2].y())
        self.assertTrue(all(0 <= point.y() <= dialog.hero.height() for point in anchors))
