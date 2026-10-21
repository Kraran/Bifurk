"""Combat intégré : règles réelles, attentes Qt, couleurs et chronique multi-adversaires.

Les tests de moteur remplacent seulement la présentation et la décision de
Chance. Les tests modaux pilotent les vrais boutons et minuteries, sans attendre
1,25 seconde par animation. Aucun PDF ni binaire compilé n'est nécessaire.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from book_events import DATA_PATH
from combat_dialog import CombatDialog


class CombatDialogTests(unittest.TestCase):
    """Observer les mutations du contrôleur sans créer un moteur de combat alternatif."""

    @classmethod
    def setUpClass(cls):
        """Partager l'application Qt et le catalogue vérifié sans texte du livre."""
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        """Isoler les écritures et les confirmations pour chaque scénario."""
        for target, value in (('_autosave', None),):
            patcher = patch.object(main.MainWindow, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.w = main.MainWindow()
        self.w.character['name'] = 'Éléanor'
        self.w.paragraphs = {n: 'Passage de test.' for n in range(1, 401)}
        self.w.character['habilete'] = 20
        self.w.enemy_name.setText('Gardien')
        self.w.enemy_endurance.setValue(2)

    def tearDown(self):
        """Détruire les fenêtres seulement après libération des boucles imbriquées."""
        self.w._combat_dialog = None
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def prepare(self, number):
        """Préparer un vrai paragraphe catalogué, puis isoler l'historique de ses assauts."""
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.go_to(number)
        self.w.undo_stack.clear()

    def session(self):
        """Brancher la vue sur le moteur ; remplacer seulement l'attente visuelle pour les tests de règles."""
        dialog = CombatDialog(self.w)
        dialog.present_roll = Mock()
        dialog.choose_luck = Mock(return_value=False)
        self.w._combat_popup = self.w._combat_dialog = dialog
        return dialog

    def run_round(self, dialog):
        """Tous les dés valent un ; la différence d'Habileté décide du gagnant sans hasard de test."""
        with patch('main.random.randint', return_value=1):
            dialog._run(self.w.combat_round)

    def test_damage_updates_both_character_sheet_and_popup_immediately(self):
        self.w.character['habilete'] = 1
        dialog = self.session()
        self.run_round(dialog)
        self.assertEqual(self.w.character['endurance'], 18)
        self.assertEqual(self.w.stat_spins['endurance'].value(), 18)
        self.assertIn('Endurance 18', dialog.hero.text())
        self.assertIn('Héros -2 PV', dialog.history.toPlainText())
        self.assertEqual(len(self.w.undo_stack), 1)

    def test_sequence_only_announces_victory_after_last_enemy(self):
        self.w.book_event_catalogue = {'paragraphs': {'1': {
            'status': 'verifie', 'mode': 'combat', 'note': 'Rencontre de test',
            'combat': {'mode': 'sequence', 'enemies': [
                {'name': 'A', 'skill': 3, 'stamina': 2},
                {'name': 'B', 'skill': 4, 'stamina': 2}], 'victory_target': 2}}}}
        self.w.go_to(1)
        self.w.undo_stack.clear()
        dialog = self.session()
        self.run_round(dialog)
        self.assertIsNone(dialog.outcome)
        self.assertEqual(self.w.enemy_name.text(), 'B')
        self.assertEqual(dialog.roster[0]['stamina'], 0)
        self.run_round(dialog)
        self.assertEqual(dialog.outcome, 'Victoire')
        self.assertEqual(dialog.banner.text(), 'VICTOIRE')
        self.assertEqual(self.w.current_paragraph, 2)
        self.assertEqual([e['stamina'] for e in dialog.roster], [0, 0])
        self.assertIn('A :', dialog.history.toPlainText())
        self.assertIn('B :', dialog.history.toPlainText())
        self.assertEqual(len(self.w.undo_stack), 2)

    def test_head_and_skeleton_pairs_keep_history_and_allow_target_selection(self):
        self.prepare(140)
        dialog = self.session()
        for _ in range(30):
            if dialog.outcome:
                break
            state = self.w._book_state(140)
            if state.get('choose_pair'):
                dialog._refresh_actions()
                self.assertEqual(dialog.actions.count(), 2)
                dialog.actions.itemAt(0).widget().click()
            self.run_round(dialog)
        self.assertEqual(dialog.outcome, 'Victoire')
        self.assertEqual(self.w.current_paragraph, 395)
        self.assertIn('Chef Squelette', dialog.history.toPlainText())
        self.assertIn('deuxième attaque parée', dialog.history.toPlainText())
        self.assertEqual(len(dialog.roster), 5)
        self.assertTrue(any(call.kwargs.get('opponent') for call in dialog.present_roll.call_args_list))

    def test_crocodile_strategy_stays_inside_window_without_false_victory(self):
        self.w.character['habilete'] = 1
        self.w.character['endurance'] = 100
        self.prepare(86)
        dialog = self.session()
        self.run_round(dialog)
        self.run_round(dialog)
        dialog._refresh_actions()
        choices = [dialog.actions.itemAt(i).widget() for i in range(dialog.actions.count())]
        self.assertTrue(any('Continuer le combat' in b.text() for b in choices))
        next(b for b in choices if 'dernier assaut' in b.text()).click()
        self.run_round(dialog)
        self.assertEqual(self.w.current_paragraph, 350)
        self.assertEqual(dialog.outcome, 'Combat terminé')
        self.assertGreater(self.w.enemy_endurance.value(), 0)

    def test_silver_creature_continues_across_its_paragraphs(self):
        self.w.character['habilete'] = 1
        self.w.character['endurance'] = 100
        self.w.character['inventory'].append('Arme en argent')
        self.prepare(173)
        dialog = self.session()
        for _ in range(3):
            self.run_round(dialog)
        self.assertEqual(self.w.current_paragraph, 24)
        self.assertIsNone(dialog.outcome)
        self.assertEqual(dialog.paragraphs, {173, 24})
        self.assertGreater(self.w.enemy_endurance.value(), 0)

    def test_flee_choice_remains_accessible_between_assaults(self):
        self.prepare(8)
        dialog = self.session()
        self.run_round(dialog)
        self.assertEqual(dialog.phase, 'next')
        self.assertTrue(dialog.primary.isEnabled())
        self.assertFalse(dialog._begin_timer.isActive())
        flee = dialog.flee
        self.assertTrue(flee.isEnabled())
        flee.click()
        self.assertEqual(self.w.current_paragraph, 189)
        self.assertEqual(self.w.character['endurance'], 18)
        self.assertEqual(dialog.outcome, 'Combat terminé')

    def test_fatal_fire_breath_announces_defeat_without_rolling_attacks(self):
        self.prepare(249)
        self.w.character['endurance'] = 1
        dialog = self.session()
        with patch('main.random.randint', return_value=1) as draw:
            dialog._run(self.w.combat_round)
        self.assertEqual(draw.call_count, 1)
        self.assertEqual(dialog.outcome, 'Défaite')
        self.assertEqual(dialog.banner.text(), 'DÉFAITE')
        self.assertEqual(self.w.character['endurance'], 0)
        self.assertIn('Éléanor', self.w.reader.toPlainText())
        self.assertFalse(self.w.stats_group.isEnabled())

    def test_history_does_not_drop_older_assaults(self):
        dialog = self.session()
        for i in range(90):
            dialog.log(f'Coup {i}')
        self.assertIn('Coup 0\n', dialog.history.toPlainText())
        self.assertIn('Coup 89', dialog.history.toPlainText())

    def test_luck_is_resolved_inline_and_updates_character_sheet(self):
        self.w.enemy_endurance.setValue(3)
        dialog = self.session()
        dialog.choose_luck.return_value = True
        self.run_round(dialog)
        self.assertEqual(dialog.outcome, 'Victoire')
        self.assertEqual(self.w.character['chance'], 7)
        self.assertEqual(self.w.stat_spins['chance'].value(), 7)
        self.assertIn('Chance 7', dialog.hero.text())
        self.assertEqual(dialog.present_roll.call_count, 3)

    def test_piranhas_initial_roll_prepares_correct_opponent_in_same_window(self):
        self.w.piranha_source_wounded = False
        self.prepare(350)
        dialog = self.session()
        self.assertIn('à déterminer', dialog.enemies.toPlainText())
        dialog._refresh_actions()
        button = next(dialog.actions.itemAt(i).widget() for i in range(dialog.actions.count())
                      if 'Piranhas' in dialog.actions.itemAt(i).widget().text())
        with patch('main.random.randint', return_value=1):
            button.click()
        self.assertEqual(self.w.enemy_name.text(), 'Piranhas')
        self.assertEqual(dialog.roster[0]['stamina'], 5)
        self.assertNotIn('à déterminer', dialog.enemies.toPlainText())
        self.assertIsNone(dialog.outcome)

    def test_wandering_monster_is_selected_and_fought_without_stale_opponent(self):
        self.prepare(295)
        self.w.go_to(161)
        target = self.w._book_state(161)['return_target']
        dialog = self.session()
        self.assertEqual(dialog.roster, [])
        dialog._refresh_actions()
        with patch('main.random.randint', return_value=1):
            dialog.actions.itemAt(0).widget().click()
        self.assertEqual(dialog.roster[0]['name'], 'Lutin')
        self.run_round(dialog)
        self.run_round(dialog)
        self.assertEqual(dialog.outcome, 'Victoire')
        self.assertEqual(self.w.current_paragraph, target)
        self.assertTrue(self.w._book_state(161).get('won'))

    def drive_modal(self, *, pause_at_player=False):
        """Piloter les vrais événements Qt et fermer proprement même en cas de régression."""
        observations = []
        failures = []
        timer = QTimer()
        timer.setInterval(2)
        watchdog = QTimer()
        watchdog.setSingleShot(True)

        def drive():
            dialog = self.w._combat_dialog
            if dialog is None:
                return
            if dialog.phase == 'animating' and dialog._canvas:
                observations.append(('animation', dialog._canvas.color))
                dialog._canvas.finish()
            elif dialog.phase == 'player':
                observations.append(('waiting', self.w.enemy_endurance.value(),
                                     dialog._trays[True].progress))
                if pause_at_player:
                    dialog.reject()
                else:
                    dialog.primary.click()
            elif dialog.phase == 'luck':
                dialog.secondary.click()
            elif dialog.outcome:
                observations.append(('outcome', dialog.outcome))
                dialog.primary.click()

        def timeout():
            failures.append('Le combat modal ne répond plus')
            if self.w._combat_dialog:
                self.w._combat_dialog.reject()

        timer.timeout.connect(drive)
        watchdog.timeout.connect(timeout)
        timer.start()
        watchdog.start(3000)
        try:
            with patch('main.random.randint', side_effect=[1, 1, 6, 6]):
                self.w.open_combat()
        finally:
            timer.stop()
            watchdog.stop()
        self.assertEqual(failures, [])
        return observations

    def test_real_modal_enemy_red_automatic_hero_white_requires_click(self):
        observations = self.drive_modal()
        self.assertIn(('animation', '#b52c39'), observations)
        self.assertIn(('waiting', 2, 1.0), observations)
        self.assertIn(('animation', self.w.theme.color('page')), observations)
        self.assertIn(('outcome', 'Victoire'), observations)
        self.assertEqual(len(self.w.undo_stack), 1)

    def test_pause_resolves_started_round_and_resume_keeps_chronicle(self):
        self.w.enemy_endurance.setValue(6)
        self.drive_modal(pause_at_player=True)
        popup = self.w._combat_popup
        self.assertEqual(self.w.enemy_endurance.value(), 4)
        self.assertIsNone(popup.outcome)
        self.assertEqual(self.w._action_depth, 0)
        chronicle = popup.history.toPlainText()
        with patch.object(popup, 'exec', return_value=0):
            self.w.open_combat()
        self.assertIs(self.w._combat_popup, popup)
        self.assertEqual(popup.history.toPlainText(), chronicle)

    def test_restore_discards_cached_visual_history(self):
        dialog = self.session()
        self.run_round(dialog)
        self.w._combat_dialog = None
        self.w.undo_action()
        self.assertIsNone(self.w._combat_popup)


if __name__ == '__main__':
    unittest.main()
