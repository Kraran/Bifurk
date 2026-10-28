"""Chemins des grimoires dans les sauvegardes : toujours « / », anciennes « \\ » acceptées.

Une sauvegarde écrite sous Windows (donnees\\grimoires\\livre.pdf) doit se recharger
partout ; un chemin absolu ou une sortie du dossier grimoires restent refusés.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_chemins_sauvegarde
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import main


class BookReferenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.books = self.root / 'donnees' / 'grimoires'
        (self.books / 'serie').mkdir(parents=True)
        self.pdf = self.books / 'serie' / 'Livre (1983).pdf'
        self.pdf.write_bytes(b'%PDF-test')
        for name, value in (('APP_DIR', self.root), ('BOOKS_DIR', self.books)):
            patcher = patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_windows_and_posix_references_resolve_to_the_same_book(self):
        for reference in ('donnees/grimoires/serie/Livre (1983).pdf',
                          'donnees\\grimoires\\serie\\Livre (1983).pdf'):
            with self.subTest(reference=reference):
                self.assertEqual(main.resolve_book_reference(reference), str(self.pdf.resolve()))

    def test_absolute_and_escaping_references_are_refused(self):
        for reference in ('C:\\Bifurk\\donnees\\grimoires\\serie\\Livre (1983).pdf',
                          'C:donnees\\grimoires\\serie\\Livre (1983).pdf',
                          '\\\\serveur\\partage\\Livre (1983).pdf',
                          str(self.pdf), '/etc/passwd',
                          'donnees\\grimoires\\..\\..\\..\\Livre (1983).pdf', '', None):
            with self.subTest(reference=reference):
                self.assertIsNone(main.resolve_book_reference(reference))

    def test_portable_reference_keeps_posix_paths(self):
        self.assertEqual(main.portable_reference('a\\b\\c.pdf'), 'a/b/c.pdf')
        self.assertEqual(main.portable_reference('a/b/c.pdf'), 'a/b/c.pdf')


class SavedPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_and_last_book_are_written_with_slashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            books = root / 'donnees' / 'grimoires'
            (books / 'serie').mkdir(parents=True)
            pdf = books / 'serie' / 'livre.pdf'
            pdf.write_bytes(b'%PDF-test')
            with patch.object(main, 'APP_DIR', root), patch.object(main, 'BOOKS_DIR', books):
                w = main.MainWindow()
                try:
                    w.pdf_path = str(pdf)
                    self.assertEqual(w._save_data()['pdf_path'], 'donnees/grimoires/serie/livre.pdf')
                    with patch.object(w, '_save_preferences'):
                        w._remember_book()
                    self.assertEqual(w.preferences['last_book'], 'serie/livre.pdf')
                finally:
                    w.close()
                    w.deleteLater()


if __name__ == '__main__':
    unittest.main()
