"""Titres de lieux et libellés des destinations sans références numériques doubles.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import json
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton, QTextBrowser, QDialog
from PySide6.QtGui import QFontMetrics

from book_events import DATA_PATH
from main import MainWindow
from navigation import choice_caption


class PlaceLabelsTests(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def test_caption_never_repeats_destination_reference(self):
        for label in ('Continuer vers §71', 'Continuer vers le paragraphe 71',
                      'Prendre le passage ouest → §71', 'Prendre le passage ouest'):
            with self.subTest(label=label):
                caption = choice_caption(label, 71)
                self.assertEqual(caption.count('71'), 1)
                self.assertEqual(caption.count('§'), 1)
                self.assertTrue(caption.endswith('→  §71'))
        self.assertEqual(choice_caption('Payer 3 pièces d’or', 272),
                         'Payer 3 pièces d’or  →  §272')

    def test_catalogue_covers_all_scenes_with_action_only_route_labels(self):
        paragraphs = self.catalogue['paragraphs']
        self.assertEqual(set(paragraphs), {str(n) for n in range(1, 401)})
        for number, entry in paragraphs.items():
            with self.subTest(number=number):
                self.assertTrue(entry['title'].strip())
                self.assertLessEqual(len(entry['title']), 60)
                for route in entry.get('routes', []):
                    self.assertTrue(route['label'].strip())
                    self.assertNotRegex(route['label'], r'§|(?i:paragraphe)')
                    self.assertNotRegex(route['label'], r'(?i)^Continuer vers\s*\d')

    def window(self):
        """Construire une fenêtre et enregistrer son nettoyage à la fin du test."""
        w = MainWindow()
        self.addCleanup(w.deleteLater)
        self.addCleanup(w.close)
        w.paragraphs = {
            1: 'Vers l’ouest, rendez-vous au 71. Vers l’est, rendez-vous au 278.',
            71: 'Une guérite.', 278: 'Une porte fermée.',
        }
        return w

    def test_opening_choices_describe_directions_without_revealing_destinations(self):
        w = self.window()
        w.book_event_catalogue = self.catalogue
        w.go_to(1)
        self.assertEqual(w.paragraph_title.text(), 'L’entrée de la montagne')
        self.assertEqual(w.paragraph_number.text(), '§ 1')
        self.assertEqual(w.event_layout.count(), 0)
        buttons = [w.choice_layout.itemAt(i).widget()
                   for i in range(w.choice_layout.count())]
        buttons = [b for b in buttons if isinstance(b, QPushButton)]
        self.assertEqual([b.text() for b in buttons], [
            'Prendre le passage ouest  →  §71', 'Prendre le passage est  →  §278'])
        buttons[0].click()
        self.assertEqual(w.current_paragraph, 71)
        self.assertEqual(w.paragraph_title.text(), 'La guérite du garde')
        self.assertEqual(w.paragraph_number.text(), '§ 71')

    def test_map_names_only_visited_scenes(self):
        w = self.window()
        w.book_event_catalogue = self.catalogue
        w.go_to(1)
        captured = []
        def inspect(dialog):
            captured.append(dialog.findChild(QTextBrowser).toPlainText())
            return QDialog.Rejected
        with patch.object(QDialog, 'exec', inspect):
            w.show_map()
        self.assertIn('L’entrée de la montagne', captured[0])
        self.assertNotIn('La guérite du garde', captured[0])
        self.assertNotIn('La porte du passage est', captured[0])

    def test_title_fits_one_line_with_number_below_on_small_window(self):
        w = self.window()
        w.book_event_catalogue = self.catalogue
        w.paragraphs[223] = 'Une porte fermée.'
        w.go_to(223)
        w.resize(930, 800)
        w.show()
        self.app.processEvents()
        self.assertEqual(w.paragraph_title.text(), 'La porte solidement fermée')
        self.assertEqual(w.paragraph_number.text(), '§ 223')
        self.assertFalse(w.paragraph_title.wordWrap())
        self.assertLessEqual(QFontMetrics(w.paragraph_title.fitted_font()).horizontalAdvance(
            w.paragraph_title.text()), w.paragraph_title.width())
        self.assertGreaterEqual(w.paragraph_number.y(),
                                w.paragraph_title.y() + w.paragraph_title.height())

    def test_unknown_edition_keeps_numbered_headings_and_safe_fallback(self):
        w = self.window()
        w.paragraphs[1] = 'Rendez-vous au 71.'
        w.go_to(1)
        self.assertEqual(w.paragraph_title.text(), 'Paragraphe')
        self.assertEqual(w.paragraph_number.text(), '§ 1')
        self.assertEqual(w.choice_layout.itemAt(0).widget().text(),
                         'Poursuivre le chemin  →  §71')


class CiteStreetCatalogueTests(unittest.TestCase):
    """Cité des Voleurs : rues, lieux partagés et directions relues pour la carte (P6)."""
    STREETS = frozenset({'Porte du Sable Noir', 'Rue du Port', 'Rue du Sabot', "Rue de l'Écurie", 'Rue de la Tour',
               'Rue du Moulin', 'Rue du Marché', 'Rue de la Clef', "Rue de l'Horloge", 'Rue de la Bougie',
               'Rue du Pont', 'Jardin public', 'Remparts', 'Égouts', 'Tour de Zanbar Bone', 'Hors les murs'})

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        path = DATA_PATH.parent / 'evenements_cite_1983.json'
        cls.catalogue = json.loads(path.read_text(encoding='utf-8'))

    def test_every_passage_has_a_street_or_building(self):
        paragraphs = self.catalogue['paragraphs']
        self.assertTrue(self.catalogue['street_map'])
        self.assertEqual({entry['place'] for entry in paragraphs.values()}, self.STREETS)
        self.assertEqual(len(paragraphs), 400)

    def test_shared_places_group_passages_of_the_same_street(self):
        spots = {}
        for number, entry in self.catalogue['paragraphs'].items():
            if 'spot' in entry:
                spots.setdefault(entry['spot'], []).append(int(number))
        self.assertEqual(sorted(map(sorted, spots.values())),
                         [[30, 333], [78, 369], [103, 196, 304], [104, 174], [182, 316]])
        for numbers in spots.values():
            self.assertEqual(len({self.catalogue['paragraphs'][str(n)]['place'] for n in numbers}), 1)

    def test_reviewed_directions_are_cardinal_and_cover_the_city(self):
        directions = {}
        for number, entry in self.catalogue['paragraphs'].items():
            for route in entry['routes']:
                if 'direction' in route:
                    self.assertIn(route['direction'], {'nord', 'sud', 'est', 'ouest'})
                    directions[(int(number), route['target'])] = route['direction']
        self.assertGreaterEqual(len(directions), 160)
        expected = {(74, 116): 'nord', (74, 95): 'ouest', (74, 17): 'est', (78, 216): 'est',
                    (369, 216): 'est', (30, 76): 'nord', (333, 76): 'nord', (304, 148): 'nord'}
        self.assertEqual({key: directions.get(key) for key in expected}, expected)

    def test_city_map_hides_unvisited_streets_and_titles(self):
        w = MainWindow()
        self.addCleanup(w.deleteLater)
        self.addCleanup(w.close)
        w.paragraphs = {n: 'Passage de test.' for n in range(1, 401)}
        w.book_event_catalogue = self.catalogue
        w.visited_paragraphs = [1, 33, 381, 74, 116]
        w.transitions = [[1, 33], [33, 381], [381, 74], [74, 116]]
        w.current_paragraph = 116
        captured = []

        def inspect(dialog):
            self.assertLess(dialog.nodes[116].pos().y(), dialog.nodes[74].pos().y())
            dialog.select_place(74)
            captured.append(dialog.details.toPlainText())
            captured.extend(dialog.index.item(i).text() for i in range(dialog.index.count()))
            captured.extend(item.toolTip() for item in dialog.scene.items())
            return QDialog.Rejected
        with patch.object(QDialog, 'exec', inspect):
            w.show_map()
        text = '\n'.join(captured)
        self.assertIn('§ 95 · non exploré', text)
        self.assertIn('— Rue du Marché —', text)
        for hidden in ('Rue de la Clef', "Rue de l'Horloge", 'serrurier', 'haillons'):
            self.assertNotIn(hidden, text)
