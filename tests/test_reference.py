"""Tests de référence : aucun PDF ni texte du livre n'est embarqué."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as bifurk
from navigation import destinations, render_links
from rules_engine import encounters, stat_events
from illustrations import catalogue_for_pdf, images_for_paragraph
from PySide6.QtWidgets import QApplication, QMessageBox


class Reference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.pdf = next(ROOT.glob('*.pdf'), None)
        cls.paragraphs = bifurk.extract_paragraphs(cls.pdf) if cls.pdf else {}

    def setUp(self):
        self.window = bifurk.MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_navigation_and_html(self):
        self.assertEqual([n for _, _, n in destinations('Rendez-\n vous au 12. Allez au 4.')], [12, 4])
        rendered = render_links('<script> Rendez-vous au 12 et allez au 8.', {12})
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('href="paragraph:12"', rendered)
        self.assertNotIn('href="paragraph:8"', rendered)

    def test_rules(self):
        self.assertEqual(encounters('GOBELIN HABILETÉ 7 ENDURANCE 8')[0]['skill'], 7)
        self.assertEqual(stat_events("Vous perdez 2 points d'endurance.")[0]['amount'], -2)
        self.assertEqual(stat_events("Si vous tombez, vous perdez 2 points d'endurance."), [])

    def test_meal_and_undo(self):
        w = self.window
        w.character['endurance'] = 19
        w.eat_meal()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (20, 9))
        w.undo_action()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (19, 10))
        w.redo_action()
        self.assertEqual(w.character['provisions'], 9)

    def test_atomic_save_and_containment(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'save.json'
            self.window._write_atomic(path, {'test': 'français'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'test': 'français'})
            self.assertEqual(list(Path(folder).iterdir()), [path])
            self.assertTrue(bifurk.within_directory(path, ROOT))
            self.assertFalse(bifurk.within_directory(ROOT / '..' / 'outside.json', ROOT))

    def test_import_is_local_and_identical(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(bifurk, 'BOOKS_DIR', Path(folder)):
            target = Path(bifurk.import_book(self.pdf))
            self.assertTrue(target.is_relative_to(folder))
            self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), hashlib.sha256(self.pdf.read_bytes()).digest())
            self.assertEqual(bifurk.import_book(self.pdf), str(target))

    def test_portable_relative_save_after_move(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            books = root / 'donnees' / 'grimoires'
            books.mkdir(parents=True)
            pdf = books / 'test.pdf'
            pdf.write_bytes(b'%PDF-test-portable')
            w = self.window
            w.pdf_path = str(pdf)
            saves = root / 'donnees' / 'sauvegardes'
            with patch.object(bifurk, 'APP_DIR', root), patch.object(bifurk, 'BOOKS_DIR', books), patch.object(bifurk, 'SAVES_DIR', saves):
                data = w._save_data()
                self.assertFalse(Path(data['pdf_path']).is_absolute())
                w._autosave()
                self.assertTrue((saves / 'autosave.json').is_file())
            moved = root / 'deplace'
            moved_books = moved / 'donnees' / 'grimoires'
            moved_books.mkdir(parents=True)
            (moved_books / pdf.name).write_bytes(pdf.read_bytes())
            with patch.object(bifurk, 'APP_DIR', moved), patch.object(bifurk, 'BOOKS_DIR', moved_books):
                self.assertEqual(bifurk.resolve_book_reference(data['pdf_path']), str(moved_books / pdf.name))

    def test_400_sections(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        self.assertEqual(set(self.paragraphs), set(range(1, 401)))
        for n, text in self.paragraphs.items():
            with self.subTest(paragraph=n):
                self.assertTrue(text.strip())
                self.assertTrue(all(target in self.paragraphs for _, _, target in destinations(text)))

    def test_all_sections_render(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        w = self.window
        w.paragraphs = self.paragraphs
        for number in range(1, 401):
            with self.subTest(paragraph=number):
                w.go_to(number)
                self.assertEqual(w.current_paragraph, number)
                self.assertTrue(w.reader.toPlainText().strip())
                self.app.processEvents()

    def test_catalogue_geometry_and_render(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import fitz
        cat = catalogue_for_pdf(self.pdf)
        self.assertIsNotNone(cat)
        w = self.window
        w.pdf_path = str(self.pdf)
        with fitz.open(self.pdf) as doc:
            self.assertEqual(len(doc), cat['pdf_pages'])
            for entry in cat['illustrations']:
                with self.subTest(image=entry['id']):
                    page = doc[entry['page_pdf'] - 1]
                    rect = fitz.Rect(entry['rect'])
                    self.assertFalse(rect.is_empty)
                    self.assertFalse((page.rect & rect).is_empty)
                    self.assertFalse(w._illustration_pixmap(entry, scale=.25).isNull())
                    for n in entry['paragraphes']:
                        self.assertIn(n, self.paragraphs)
                        self.assertIn(entry, images_for_paragraph(cat, n))
                    if entry['type'] == 'ornement':
                        self.assertFalse(entry['paragraphes'])

    @unittest.expectedFailure
    def test_known_cover_bounds(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import fitz
        cat = catalogue_for_pdf(self.pdf)
        with fitz.open(self.pdf) as doc:
            entry = cat['illustrations'][0]
            self.assertTrue(doc[entry['page_pdf'] - 1].rect.contains(fitz.Rect(entry['rect'])))

    @unittest.expectedFailure
    def test_known_luck_cannot_be_negative(self):
        self.window.character['chance'] = 0
        self.window.test_luck()
        self.assertGreaterEqual(self.window.character['chance'], 0)

    @unittest.expectedFailure
    def test_known_combat_undo_restores_enemy(self):
        w = self.window
        before = w.enemy_endurance.value()
        with patch.object(w, '_roll', side_effect=[([1, 1], 2), ([6, 6], 12)]), patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
            w.combat_round()
        w.undo_action()
        self.assertEqual(w.enemy_endurance.value(), before)

    @unittest.expectedFailure
    def test_known_loading_restores_catalogue(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        w = self.window
        w.pdf_path = str(self.pdf)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'save.json'
            w._write_atomic(path, w._save_data())
            with patch.object(w, '_themed_save_dialog', return_value=str(path)), patch.object(bifurk, 'resolve_book_reference', return_value=str(self.pdf)), patch.object(QMessageBox, 'information'):
                w.load_game()
            self.assertIsNotNone(w.illustration_catalogue)


if __name__ == '__main__':
    unittest.main(verbosity=2)
