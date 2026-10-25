"""Copie du texte de lecture : la lettrine rend sa vraie lettre, pas U+FFFC.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_lettrine_copie.
Texte de test inventé ; aucun extrait de livre n'est embarqué."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication

import main

TEXT = ('Votre torche grésille dans le couloir humide. ' * 4).strip()


class DropCapCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        for key in ('SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            p = patch.object(main, key, root / key)
            p.start()
            self.addCleanup(p.stop)
        main.init_portable_dirs()
        self.w = main.MainWindow()
        self.w.show()
        self.app.processEvents()
        self.reader = self.w.reader
        self.w._render_paragraph_text(TEXT)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def select(self, start, end):
        cursor = QTextCursor(self.reader.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.reader.setTextCursor(cursor)

    def image_names(self):
        names = []
        block = self.reader.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fmt = it.fragment().charFormat()
                if fmt.isImageFormat():
                    names.append(fmt.toImageFormat().name())
                it += 1
            block = block.next()
        return names

    def test_rendering_still_uses_the_drop_cap_image(self):
        self.assertIsInstance(self.reader, main.QTextBrowser)
        self.assertEqual(len(self.image_names()), 1)
        self.assertTrue(self.image_names()[0].startswith('bifurk-initial:'))
        self.assertTrue(self.reader.toPlainText().startswith('\ufffcotre torche'))

    def test_selection_from_drop_cap_copies_real_letter(self):
        self.select(0, len('Votre torche'))
        mime = self.reader.createMimeDataFromSelection()
        self.assertEqual(mime.text(), 'Votre torche')
        self.assertNotIn('\ufffc', mime.text())

    def test_ctrl_c_and_select_all_put_letter_on_clipboard(self):
        self.select(0, len('Votre torche'))
        self.reader.copy()  # Ctrl+C et « Copier » du menu contextuel
        self.assertEqual(QApplication.clipboard().text(), 'Votre torche')
        self.reader.selectAll()
        self.reader.copy()
        self.assertEqual(QApplication.clipboard().text(), TEXT)

    def test_context_menu_copy_puts_letter_on_clipboard(self):
        QApplication.clipboard().clear()
        self.select(0, len('Votre torche'))
        menu = self.reader.createStandardContextMenu()
        self.addCleanup(menu.deleteLater)
        copy = next(a for a in menu.actions() if a.objectName() == 'edit-copy')
        copy.trigger()
        self.assertEqual(QApplication.clipboard().text(), 'Votre torche')

    def test_every_exported_format_has_the_letter(self):
        self.select(0, len('Votre torche'))
        mime = self.reader.createMimeDataFromSelection()
        for name in mime.formats():
            data = bytes(mime.data(name))
            if name != 'application/vnd.oasis.opendocument.text':  # archive zip
                self.assertNotIn('\ufffc'.encode(), data, name)

    def test_html_mime_contains_letter_not_image(self):
        self.select(0, len('Votre torche'))
        mime = self.reader.createMimeDataFromSelection()
        self.assertTrue(mime.hasHtml())
        html = mime.html()
        self.assertNotIn('<img', html)
        self.assertNotIn('bifurk-initial', html)
        document = QTextDocument()
        document.setHtml(html)
        self.assertEqual(document.toPlainText(), 'Votre torche')

    def test_partial_selection_without_drop_cap_is_unaffected(self):
        start = len('Votre ')
        self.select(start, start + len('torche grésille'))
        mime = self.reader.createMimeDataFromSelection()
        self.assertEqual(mime.text(), 'torche grésille')
        self.assertNotIn('V', mime.html().split('<body')[-1].split('torche')[0])

    def test_other_images_are_left_unchanged(self):
        image = QImage(4, 4, QImage.Format_ARGB32)
        image.fill(0)
        self.reader.document().addResource(QTextDocument.ImageResource, QUrl('bifurk-image:x'), image)
        self.reader.setHtml('<p><img src="bifurk-image:x" alt="X">Une salle.</p>')
        self.select(0, len('\ufffcUne'))
        mime = self.reader.createMimeDataFromSelection()
        self.assertEqual(mime.text(), '\ufffcUne')

    def test_letter_parsing(self):
        self.assertEqual(main.drop_cap_letter(f'bifurk-initial:{ord("É")}-42'), 'É')
        self.assertIsNone(main.drop_cap_letter('bifurk-initial:abc-42'))
        self.assertIsNone(main.drop_cap_letter('bifurk-image:86-42'))


if __name__ == '__main__':
    unittest.main()
