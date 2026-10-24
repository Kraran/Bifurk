"""Carnet de notes et marque-pages : données facultatives de sauvegarde et navigation suivie."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

import main
from carnet import entry_header, read_bookmarks, read_notes, references, split_references
from save_slots import read_save


class CarnetDataTests(unittest.TestCase):
    def test_missing_or_invalid_fields_give_an_empty_carnet(self):
        self.assertEqual(read_notes(None), '')
        self.assertEqual(read_notes(42), '')
        self.assertEqual(read_bookmarks(None), [])
        raw = [{'paragraph': 12, 'label': '  Pont  '}, {'paragraph': 12, 'label': 'doublon'},
               {'paragraph': '7'}, {'paragraph': True}, 'texte', {'paragraph': -3},
               {'paragraph': 40, 'label': 'x' * 200, 'at': '2026-10-24T20:05'}]
        marks = read_bookmarks(raw)
        self.assertEqual([m['paragraph'] for m in marks], [12, 40])
        self.assertEqual(marks[0], {'paragraph': 12, 'label': 'Pont', 'at': ''})
        self.assertEqual(len(marks[1]['label']), 60)

    def test_references_and_entry_headers(self):
        self.assertEqual(references('Revenir au §12 puis au § 7, pas au 30.'), [12, 7])
        self.assertEqual(split_references('Voir §3 !'), [('Voir ', None), ('§3', 3), (' !', None)])
        header = entry_header(37, stamp=False)
        self.assertEqual(header, '✦ §37')
        self.assertIn('§37 — ', entry_header(37))


class CarnetWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for key in ('SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            replacement = patch.object(main, key, self.root/key)
            replacement.start()
            self.addCleanup(replacement.stop)
        main.init_portable_dirs()
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        pdf = self.root/'livre.pdf'
        pdf.write_bytes(b'PDF prive de test')
        self.w.pdf_path = str(pdf)
        self.w.paragraphs = {1: 'Un chemin, rendez-vous au 2.', 2: 'Une salle.', 3: 'Une porte.'}
        self.w.character['name'] = 'Eldan'
        self.w.go_to(1)
        self.w.show()
        self.app.processEvents()

    def label(self, text='', ok=True):
        return patch.object(QInputDialog, 'getText', return_value=(text, ok))

    def test_ribbon_marks_current_paragraph_with_optional_label(self):
        ribbon = self.w.bookmark_ribbon
        self.assertTrue(ribbon.isVisible())
        self.assertFalse(ribbon.isChecked())
        with self.label('', ok=False):
            self.w.toggle_bookmark()
        self.assertEqual(self.w.bookmarks, [])
        with self.label('  Le pont  '):
            self.w.toggle_bookmark()
        self.assertEqual([(b['paragraph'], b['label']) for b in self.w.bookmarks], [(1, 'Le pont')])
        self.assertTrue(ribbon.isChecked())
        self.assertTrue(self.w.add_bookmark(3))
        self.assertFalse(self.w.add_bookmark(3))
        self.w.toggle_bookmark()  # Déjà marqué : B retire le marque-page.
        self.assertEqual([b['paragraph'] for b in self.w.bookmarks], [3])
        self.assertFalse(ribbon.isChecked())

    def test_notes_and_bookmarks_travel_in_autosave_and_slots_but_not_in_undo(self):
        self.w.notes = '✦ §1\nClé sous la statue (§3).'
        self.w.add_bookmark(3, 'Porte')
        self.assertNotIn('notes', self.w._snapshot())
        data = read_save(main.SAVES_DIR/'autosave.json')
        self.assertEqual(data['notes'], self.w.notes)
        self.assertEqual(data['bookmarks'][0]['paragraph'], 3)
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.w._reset_carnet()
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.notes, '✦ §1\nClé sous la statue (§3).')
        self.assertEqual([b['label'] for b in self.w.bookmarks], ['Porte'])
        legacy = self.w._save_data()
        legacy.pop('notes')
        legacy.pop('bookmarks')
        self.w._write_atomic(path, legacy)
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual((self.w.notes, self.w.bookmarks), ('', []))

    def test_bookmark_travel_is_confirmed_recorded_and_undoable(self):
        self.w.add_bookmark(3, 'Porte')
        self.w.notes = 'à garder'
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.assertFalse(self.w.go_to_bookmark(3))
        self.assertEqual(self.w.current_paragraph, 1)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.assertTrue(self.w.go_to_bookmark(3))
        self.assertEqual(self.w.current_paragraph, 3)
        self.assertTrue(self.w.bookmark_ribbon.isChecked())
        self.assertEqual(self.w.adventure_tracking['status'], 'assisted')
        self.assertTrue(self.w.undo_stack)
        self.w.undo_action()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.notes, 'à garder')
        self.assertFalse(self.w.bookmark_ribbon.isChecked())

    def test_carnet_inserts_clickable_reference_and_blocks_choice_keys(self):
        self.w.open_carnet()
        book = self.w.carnet_overlay.book
        self.assertTrue(self.w.carnet_is_open())
        book.editor.insertPlainText('Voir')
        book.insert_button.click()
        self.assertEqual(self.w.notes.strip(), 'Voir §1')
        cursor = book.editor.document().find('§1')
        self.assertEqual(cursor.charFormat().anchorHref(), 'paragraph:1')
        book.entry_button.click()
        self.assertIn('✦ §1 — ', self.w.notes)
        with patch.object(self.w, '_visible_choice_cards') as cards:
            self.w._activate_choice(1)
        cards.assert_not_called()
        self.w.close_carnet()
        self.assertFalse(self.w.carnet_is_open())
        self.assertIn('Voir §1', read_save(main.SAVES_DIR/'autosave.json')['notes'])
        book.editor.set_notes(self.w.notes)
        self.assertEqual(book.editor.plain(), self.w.notes)


if __name__ == '__main__':
    unittest.main()
