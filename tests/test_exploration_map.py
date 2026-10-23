"""Carte graphique : confidentialité, consultation sans déplacement et grands parcours.

Les scénarios emploient des lieux fictifs et un historique réel du contrôleur.
Aucun PDF ni tirage aléatoire n'est nécessaire pour vérifier le graphe.
"""
import copy
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from exploration_map import ExplorationMapDialog, PlaceItem, place_positions, route_direction
from main import MainWindow


class ExplorationMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        self.w.paragraphs = {n: 'Passage de test.' for n in range(1, 401)}
        self.w.visited_paragraphs = [1, 2, 3, 4]
        self.w.current_paragraph = 3
        self.w.transitions = [[1, 2], [2, 3], [3, 4], [4, 3]]
        self.w.encounter_history = {'2': [{'name': 'Gardien <rouge>', 'status': 'vaincu'},
                                          {'name': 'Sentinelle', 'status': 'fui'}],
                                     '3': [{'name': 'Ombre', 'status': 'rencontré'}]}
        self.w.book_event_catalogue = {'paragraphs': {
            str(n): {'status': 'verifie', 'title': title, 'routes': routes}
            for n, title, routes in [(1, 'Entrée', [{'target': 2, 'label': 'Avancer'},
                                                   {'target': 99, 'label': 'Tourner'}]),
                                      (2, 'Salle des gardiens', []), (3, 'Carrefour', []),
                                      (4, 'Passage oublié', []), (99, 'Trésor secret', [])]}}
        self.dialog = ExplorationMapDialog(self.w)
        self.addCleanup(self.dialog.deleteLater)
        self.addCleanup(self.dialog.close)
        self.dialog.show()
        self.app.processEvents()

    def test_map_contains_only_visited_places_and_remembered_enemies(self):
        before = copy.deepcopy(self.w.encounter_history)
        self.assertEqual(set(self.dialog.nodes), {1, 2, 3, 4})
        self.assertEqual(self.dialog.current, 3)
        self.assertTrue(self.dialog.nodes[3].current)
        self.dialog.select_place(1)
        self.assertIn('§ 99 · non exploré', self.dialog.details.toPlainText())
        self.assertNotIn('Trésor secret', self.dialog.details.toPlainText())
        self.assertFalse(any('Trésor secret' in self.dialog.index.item(i).text()
                             for i in range(self.dialog.index.count())))
        self.dialog.select_place(2)
        text = self.dialog.details.toPlainText()
        self.assertIn('Gardien <rouge> — vaincu', text)
        self.assertIn('Sentinelle — fui', text)
        self.assertEqual(self.w.encounter_history, before)

    def test_selection_search_zoom_and_focus_never_change_game_state(self):
        before = self.w._snapshot()
        self.dialog.select_place(2, focus=True)
        self.dialog.search.setText('gardiens')
        self.assertEqual([self.dialog.index.item(i).data(Qt.UserRole)
                          for i in range(self.dialog.index.count())
                          if not self.dialog.index.item(i).isHidden()], [2])
        self.dialog.overview_button.click()
        self.dialog.position_button.click()
        self.assertEqual(self.dialog.selected, 3)
        self.assertEqual(self.dialog.view.transform().m11(), 1)
        self.assertIn('Vous êtes ici', self.dialog.details.toPlainText())
        self.dialog.previous_button.click()
        self.assertEqual(self.dialog.selected, 4)
        self.assertEqual(self.w._snapshot(), before)

    def test_clicking_a_graph_node_only_selects_it(self):
        self.dialog.select_place(2, focus=True)
        point = self.dialog.view.mapFromScene(self.dialog.nodes[2].sceneBoundingRect().center())
        before = self.w._snapshot()
        QTest.mouseClick(self.dialog.view.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.dialog.selected, 2)
        self.assertTrue(self.dialog.nodes[2].isSelected())
        self.assertEqual(self.w._snapshot(), before)

    def test_only_explicit_travel_calls_existing_navigation(self):
        with patch.object(self.w, 'go_to') as go:
            self.dialog._select_link(QUrl('place:2'))
            self.dialog.select_place(99)
            self.dialog._select_link(QUrl('https://example.com'))
            go.assert_not_called()
            self.assertEqual(self.dialog.selected, 2)
            self.dialog.travel_button.click()
            go.assert_called_once_with(2)

    def test_wheel_zoom_is_bounded_and_position_restores_readable_size(self):
        view = self.dialog.view
        old_scale = view.transform().m11()
        event = QWheelEvent(QPointF(80, 80), QPointF(view.mapToGlobal(QPoint(80, 80))),
                            QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                            Qt.NoScrollPhase, False)
        self.app.sendEvent(view.viewport(), event)
        self.assertGreater(view.transform().m11(), old_scale)
        view.zoom(1000)
        self.assertLessEqual(view.transform().m11(), 2.5)
        view.zoom(.000001)
        self.assertAlmostEqual(view.transform().m11(), .03)
        self.dialog.focus_current()
        self.assertEqual(view.transform().m11(), 1)
        visible = view.mapToScene(view.viewport().rect()).boundingRect()
        self.assertTrue(visible.contains(self.dialog.nodes[3].sceneBoundingRect()))

    def test_cycle_branch_and_disconnected_layout_has_no_overlap(self):
        edges = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 1), (9, 9), (999, 1)]
        positions = place_positions([1, 2, 3, 4, 9], edges)
        self.assertEqual(positions, place_positions([1, 2, 3, 4, 9], edges))
        rectangles = [QPointF(point) for point in positions.values()]
        for index, point in enumerate(rectangles):
            for other in rectangles[index + 1:]:
                self.assertTrue(abs(point.x() - other.x()) >= PlaceItem.WIDTH
                                or abs(point.y() - other.y()) >= PlaceItem.HEIGHT)

    def test_cardinal_routes_cycles_and_collisions(self):
        edges = [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (2, 1)]
        directions = {(1, 2): (0, -1), (1, 3): (0, 1), (1, 4): (1, 0),
                      (1, 5): (-1, 0), (1, 6): (0, -1), (2, 1): (1, 0)}
        points = place_positions(range(1, 7), edges, directions)
        self.assertLess(points[2].y(), points[1].y())
        self.assertGreater(points[3].y(), points[1].y())
        self.assertGreater(points[4].x(), points[1].x())
        self.assertLess(points[5].x(), points[1].x())
        self.assertLess(points[6].y(), points[1].y())
        self.assertEqual(len({(p.x(), p.y()) for p in points.values()}), 6)
        self.assertEqual(points[1], QPointF(0, 0))
        self.assertEqual(points, place_positions(range(1, 7), edges, directions))

    def test_direction_is_taken_only_from_unambiguous_movement(self):
        self.assertEqual(route_direction('Continuer vers le nord'), (0, -1))
        self.assertEqual(route_direction("Poursuivre à l’est"), (1, 0))
        for label in ('Regarder vers le nord', 'Ne pas aller au sud',
                      'Une montagne au nord', 'Aller au nord-est', 'Continuer'):
            self.assertIsNone(route_direction(label), label)

    def test_undirected_long_path_is_compact(self):
        points = place_positions(range(1, 64), [(n, n+1) for n in range(1, 63)])
        self.assertLess(max(p.x() for p in points.values()) - min(p.x() for p in points.values()), 330 * 16)
        self.assertGreater(len({p.y() for p in points.values()}), 1)

    def test_dialog_uses_route_labels_without_revealing_unknown_places(self):
        self.w.book_event_catalogue['paragraphs']['1'] = {
            'status': 'verifie', 'routes': [{'target': 2, 'label': 'Continuer vers le nord'},
                       {'target': 99, 'label': 'Partir au sud'}]}
        dialog = ExplorationMapDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        self.assertLess(dialog.nodes[2].pos().y(), dialog.nodes[1].pos().y())
        self.assertNotIn(99, dialog.nodes)

    def test_large_map_keeps_all_places_and_current_position(self):
        self.w.visited_paragraphs = list(range(1, 401))
        self.w.transitions = [[n, n+1] for n in range(1, 400)]
        self.w.current_paragraph = 400
        large = ExplorationMapDialog(self.w)
        self.addCleanup(large.deleteLater)
        self.addCleanup(large.close)
        large.resize(900, 620)
        large.show()
        self.app.processEvents()
        large.overview()
        large.focus_current()
        self.assertEqual(len(large.nodes), 400)
        self.assertEqual(large.selected, 400)
        self.assertEqual(large.index.count(), 400)
        self.assertFalse(large.grab().isNull())

    def test_empty_exploration_can_be_opened_before_paragraph_one(self):
        self.w.current_paragraph = None
        self.w.visited_paragraphs = []
        self.w.transitions = []
        empty = ExplorationMapDialog(self.w)
        self.addCleanup(empty.deleteLater)
        self.addCleanup(empty.close)
        self.assertEqual(empty.nodes, {})
        self.assertFalse(empty.position_button.isEnabled())
        self.assertFalse(empty.previous_button.isEnabled())
        self.assertFalse(empty.travel_button.isEnabled())
        self.assertIn('entrée dans l’aventure', empty.details.toPlainText())
