"""Dés 3D : géométrie finale, cycle modal et intégrité du hasard du moteur.

Les trajectoires sont testées sans attendre leur durée réelle. Les scénarios de
jeu observent la présentation avec des doublures ; un vrai exec Qt contrôle aussi
la révélation du résultat et la fermeture sans relance.
"""
import math
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import call, patch

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from dice_dialog import DiceCanvas, DiceDialog, D20_FACES, FACES, PIPS, die_angles, transformed


class DiceDialogTests(unittest.TestCase):
    """Les faces visibles doivent être celles réellement utilisées, quelle que soit la fermeture."""

    @classmethod
    def setUpClass(cls):
        """Partager l'unique application Qt de la suite."""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Mémoriser les widgets pour les détruire après chaque scénario."""
        self.widgets = []

    def tearDown(self):
        """Terminer les animations et libérer les fenêtres sans laisser de timer actif."""
        for widget in self.widgets:
            if isinstance(widget, DiceDialog):
                widget.canvas.finish()
            widget.close()
            widget.deleteLater()
        self.app.processEvents()

    def dialog(self, rolls=(2, 5), *, sides=6):
        """Construire un dialogue réel pour contrôler le cycle de révélation."""
        dialog = DiceDialog(rolls, 'Combat — Aventurier', sides=sides)
        self.widgets.append(dialog)
        return dialog

    def test_each_final_front_face_matches_the_roll_and_opposites_sum_to_seven(self):
        for value in range(1, 7):
            with self.subTest(value=value):
                depths = {face: transformed(normal, value, 1)[2]
                          for face, normal, u, v in FACES}
                self.assertEqual(max(depths, key=depths.get), value)
                self.assertEqual(len(PIPS[value]), value)
                self.assertTrue(all(math.isfinite(n) for n in die_angles(value, .5)))
        for value, normal, u, v in FACES:
            opposite = next(other for other, n, _, _ in FACES
                            if n == tuple(-x for x in normal))
            self.assertEqual(value + opposite, 7)

    def test_animation_and_painting_do_not_consume_random_numbers(self):
        dialog = self.dialog()
        state = random.getstate()
        dialog.resize(560, 430)
        for progress in (0, .15, .5, .9, 1):
            dialog.canvas.progress = progress
            self.assertFalse(dialog.grab().isNull())
        self.assertEqual(random.getstate(), state)

    def test_skip_or_escape_reveals_then_continues_without_replacing_faces(self):
        dialog = self.dialog((1, 6))
        dialog.show()
        self.app.processEvents()
        self.assertTrue(dialog.canvas.timer.isActive())
        QTest.keyClick(dialog, Qt.Key_Escape)
        self.assertTrue(dialog.isVisible())
        self.assertFalse(dialog.canvas.timer.isActive())
        self.assertEqual(dialog.result.text(), 'Résultat : 1 + 6 = 7')
        self.assertEqual(dialog.proceed.text(), 'Continuer')
        QTest.keyClick(dialog, Qt.Key_Escape)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(dialog.canvas.rolls, (1, 6))

    def test_finished_emits_once_and_single_die_result_is_readable(self):
        dialog = self.dialog((4,))
        signals = []
        dialog.canvas.finished.connect(lambda: signals.append(True))
        dialog.canvas.finish()
        dialog.canvas.finish()
        self.assertEqual(signals, [True])
        self.assertEqual(dialog.canvas.progress, 1)
        self.assertEqual(dialog.result.text(), 'Résultat : 4')

    def test_actual_modal_loop_reveals_and_closes(self):
        dialog = self.dialog()
        dialog.canvas.DURATION_MS = 1
        reached_end = []

        def finish_and_continue():
            reached_end.append(dialog.canvas._finished)
            dialog.proceed.click()

        dialog.canvas.finished.connect(finish_and_continue)
        # Attendre le signal réel plutôt que supposer l'ordre de deux timers
        # lorsque toute la suite Qt charge la boucle événementielle.
        watchdog = QTimer(dialog)
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda: dialog.done(DiceDialog.Rejected))
        watchdog.start(2000)
        try:
            self.assertEqual(dialog.exec(), DiceDialog.Accepted)
        finally:
            watchdog.stop()
        self.assertEqual(reached_end, [True])
        self.assertFalse(dialog.canvas.timer.isActive())
        self.assertEqual(dialog.result.text(), 'Résultat : 2 + 5 = 7')

    def test_native_close_during_motion_shows_result_before_closing(self):
        dialog = self.dialog()
        dialog.show()
        dialog.close()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.canvas.progress, 1)
        dialog.close()
        self.assertFalse(dialog.isVisible())

    def test_invalid_dice_are_rejected(self):
        for rolls in ([], [0], [7], [True], [1, 2, 3, 4]):
            with self.subTest(rolls=rolls), self.assertRaises(ValueError):
                DiceCanvas(rolls)

    def test_roll_draws_once_and_preserves_original_result_after_presentation(self):
        window = main.MainWindow()
        self.widgets.append(window)
        with patch('main.random.randint', side_effect=[2, 6]) as draw, \
                patch.object(window, '_show_dice_roll') as show:
            self.assertEqual(window._roll(2, context='Chance'), ([2, 6], 8))
        self.assertEqual(draw.call_args_list, [call(1, 6), call(1, 6)])
        show.assert_called_once_with([2, 6], 'Chance')

    def test_free_dice_variants_animate_without_drawing_extra_results(self):
        window = main.MainWindow()
        self.widgets.append(window)
        with patch.object(window, '_show_dice_roll') as show, \
                patch('main.random.randint', side_effect=[1, 2, 6, 20]) as draw:
            window.roll_free_dice('3d6')
            window.roll_free_dice('1d20')
        self.assertEqual(draw.call_args_list, [call(1, 6)] * 3 + [call(1, 20)])
        self.assertEqual(show.call_args_list[0].args[0], [1, 2, 6])
        self.assertEqual(show.call_args_list[1].args[0], [20])
        self.assertEqual(show.call_args_list[1].kwargs, {'sides': 20})

    def test_all_twenty_faces_land_on_the_requested_number(self):
        self.assertEqual({face[0] for face in D20_FACES}, set(range(1, 21)))
        # Un icosaèdre a 12 sommets, 30 arêtes égales et 20 faces triangulaires.
        vertices = {point for *_, corners in D20_FACES for point in corners}
        edges = {tuple(sorted((corners[i], corners[(i+1) % 3])))
                 for *_, corners in D20_FACES for i in range(3)}
        self.assertEqual((len(vertices), len(edges)), (12, 30))
        self.assertAlmostEqual(min(math.dist(*edge) for edge in edges),
                               max(math.dist(*edge) for edge in edges))
        for value, center, *_ in D20_FACES:
            with self.subTest(value=value):
                depths = {number: transformed(origin, value, 1, sides=20)[2]
                          for number, origin, *_ in D20_FACES}
                self.assertEqual(max(depths, key=depths.get), value)
                opposite = next(number for number, origin, *_ in D20_FACES
                                if all(math.isclose(a, -b, abs_tol=1e-9)
                                       for a, b in zip(center, origin)))
                self.assertEqual(value + opposite, 21)

    def test_extended_dice_render_and_reveal_using_the_same_dialog(self):
        state = random.getstate()
        for rolls, sides, result in (((1, 3, 6), 6, 'Résultat : 1 + 3 + 6 = 10'),
                                     ((20,), 20, 'Résultat : 20')):
            with self.subTest(sides=sides):
                dialog = self.dialog(rolls, sides=sides)
                dialog.show()
                for progress in (0, .2, .6, 1):
                    dialog.canvas.progress = progress
                    self.assertFalse(dialog.grab().isNull())
                dialog.proceed.click()
                self.assertTrue(dialog.isVisible())
                self.assertEqual(dialog.result.text(), result)
                dialog.proceed.click()
                self.assertFalse(dialog.isVisible())
        self.assertEqual(random.getstate(), state)
        for rolls, sides in (([21], 20), ([0], 20), ([1, 2], 20), ([1], 12)):
            with self.subTest(rolls=rolls, sides=sides), self.assertRaises(ValueError):
                DiceCanvas(rolls, sides=sides)

    def test_actions_keep_free_dice_without_the_manual_luck_entry(self):
        window = main.MainWindow()
        self.widgets.append(window)
        actions = window.tools_button.menu().actions()
        self.assertFalse(any('Chance' in action.text() for action in actions))
        dice = next(action.menu() for action in actions if action.menu())
        self.assertEqual([action.text() for action in dice.actions()], ['1d6', '2d6', '3d6', '1d20'])

    def test_game_can_open_real_popup_and_return_same_faces(self):
        window = main.MainWindow()
        self.widgets.append(window)
        shown = []

        def read_and_continue():
            dialog = next(w for w in self.app.topLevelWidgets() if isinstance(w, DiceDialog))
            dialog.canvas.finish()
            shown.append((dialog.canvas.rolls, dialog.result.text()))
            dialog.accept()

        QTimer.singleShot(0, read_and_continue)
        with patch.object(main.QApplication, 'platformName', return_value='windows'), \
                patch('main.random.randint', side_effect=[4, 5]):
            self.assertEqual(window._roll(2), ([4, 5], 9))
        self.assertEqual(shown, [((4, 5), 'Résultat : 4 + 5 = 9')])

    def test_combat_presents_enemy_then_hero_and_keeps_one_undo_entry(self):
        window = main.MainWindow()
        self.widgets.append(window)
        window.enemy_name.setText('Gardien')
        window.enemy_skill.setValue(8)
        window.enemy_endurance.setValue(6)
        window.character['name'] = 'Éléanor'
        window.character['habilete'] = 8
        with patch.object(window, '_show_dice_roll') as show, \
                patch('main.random.randint', side_effect=[1, 2, 3, 4]), \
                patch.object(QMessageBox, 'exec', return_value=QMessageBox.No), \
                patch.object(window, '_autosave'):
            window.combat_round()
        self.assertEqual(show.call_args_list, [call([1, 2], 'Combat — Gardien'),
                                              call([3, 4], 'Combat — Éléanor')])
        self.assertEqual(window.enemy_endurance.value(), 4)
        self.assertEqual(len(window.undo_stack), 1)
        with patch.object(window, '_show_dice_roll') as show, patch.object(window, '_autosave'):
            window.undo_action()
        show.assert_not_called()
        self.assertEqual(window.enemy_endurance.value(), 6)



class RoundedDiceLookTests(unittest.TestCase):
    """D6 aux arêtes arrondies et points creusés : géométrie et rendu de la face posée."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pips_stay_on_the_flat_part_of_each_face(self):
        from dice_dialog import DiceCanvas, PIPS
        reach = max(abs(c) for pips in PIPS.values() for xy in pips for c in xy) + .145 + .035
        self.assertLess(reach, DiceCanvas.FLAT)

    def test_landed_die_shows_a_dark_engraved_pip_on_a_light_face(self):
        from dice_dialog import DiceCanvas
        canvas = DiceCanvas((1,))
        canvas.resize(320, 240)
        canvas.finish()
        image = canvas.grab().toImage()
        # Autour du dé : un creux d'encre sombre et une face ivoire claire, sans contour tracé.
        light = [image.pixelColor(x, y).lightness() for x in range(110, 210, 2) for y in range(70, 170, 2)]
        self.assertLess(min(light), 70)
        self.assertGreater(max(light), 190)


if __name__ == '__main__':
    unittest.main()
