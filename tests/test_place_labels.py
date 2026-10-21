import json
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton, QTextBrowser, QDialog

from book_events import DATA_PATH
from main import MainWindow
from navigation import choice_caption


class PlaceLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        self.assertEqual(w.paragraph_title.text(), 'L’entrée de la montagne  ·  §1')
        self.assertEqual(w.event_layout.count(), 0)
        buttons = [w.choice_layout.itemAt(i).widget()
                   for i in range(w.choice_layout.count())]
        buttons = [b for b in buttons if isinstance(b, QPushButton)]
        self.assertEqual([b.text() for b in buttons], [
            'Prendre le passage ouest  →  §71', 'Prendre le passage est  →  §278'])
        buttons[0].click()
        self.assertEqual(w.current_paragraph, 71)
        self.assertEqual(w.paragraph_title.text(), 'La guérite du garde  ·  §71')

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

    def test_unknown_edition_keeps_numbered_headings_and_safe_fallback(self):
        w = self.window()
        w.paragraphs[1] = 'Rendez-vous au 71.'
        w.go_to(1)
        self.assertEqual(w.paragraph_title.text(), 'Paragraphe 1')
        self.assertEqual(w.choice_layout.itemAt(0).widget().text(),
                         'Poursuivre le chemin  →  §71')
