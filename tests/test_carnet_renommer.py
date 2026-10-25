"""Marque-pages : le clic voyage, renommer passe par une commande dédiée (plume, F2, menu)."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

import main
from carnet import BookmarkRow


class RenameTests(unittest.TestCase):
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
        self.w.paragraphs = {1: 'Un chemin.', 2: 'Une salle.', 3: 'Une porte.'}
        self.w.character['name'] = 'Eldan'
        self.w.go_to(1)
        self.w.show()
        QTest.qWaitForWindowExposed(self.w)
        self.w.add_bookmark(3, 'Porte')
        self.w.add_bookmark(2, 'Salle')
        self.w.open_carnet('bookmarks')
        self.settle()

    def settle(self):
        for _ in range(3):
            self.app.processEvents()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def row(self, number):
        rows = [r for r in self.w.carnet_overlay.book.findChildren(BookmarkRow)
                if r.bookmark['paragraph'] == number and r.isVisible()]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def window_point(self, widget, point=None):
        """Point du widget en coordonnées de la fenêtre : les événements passent par Qt comme un vrai clic."""
        point = point if point is not None else widget.rect().center()
        return widget.mapTo(self.w, point)

    def asks(self, answer):
        return patch.object(QMessageBox, 'question', return_value=answer)

    def test_single_click_travels_with_the_usual_confirmation(self):
        with self.asks(QMessageBox.Yes) as question, \
                patch.object(QInputDialog, 'getText') as rename:
            QTest.mouseClick(self.w.windowHandle(), Qt.LeftButton, Qt.NoModifier,
                             self.window_point(self.row(3), QPoint(150, 32)))
            self.settle()
        question.assert_called_once()
        rename.assert_not_called()
        self.assertEqual(self.w.current_paragraph, 3)
        self.assertFalse(self.w.carnet_is_open())

    def test_double_click_travels_once_and_never_renames(self):
        point = self.window_point(self.row(3), QPoint(150, 32))
        with self.asks(QMessageBox.No) as question, \
                patch.object(QInputDialog, 'getText') as rename:
            QTest.mouseDClick(self.w.windowHandle(), Qt.LeftButton, Qt.NoModifier, point)
            self.settle()
        self.assertEqual(question.call_count, 1)
        rename.assert_not_called()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual([b['label'] for b in self.w.bookmarks], ['Porte', 'Salle'])
        # Deux clics bien espacés restent deux demandes de voyage distinctes.
        QTest.qWait(QApplication.doubleClickInterval() + 50)
        with self.asks(QMessageBox.No) as question:
            QTest.mouseClick(self.w.windowHandle(), Qt.LeftButton, Qt.NoModifier, point)
            self.settle()
        question.assert_called_once()

    def test_pen_appears_on_hover_or_focus_and_renames_without_travelling(self):
        row = self.row(3)
        pen = row.rename_button
        self.assertFalse(pen.isVisible())
        self.assertIn('F2', pen.toolTip())
        self.assertIn('Renommer', pen.toolTip())
        self.assertIn('F2', row.toolTip())
        center = row.rect().center()
        QApplication.sendEvent(row, QEnterEvent(center, row.mapTo(self.w, center), row.mapToGlobal(center)))
        self.assertTrue(pen.isVisible())
        QApplication.sendEvent(row, QEvent(QEvent.Leave))
        self.assertFalse(pen.isVisible())
        row.setFocus(Qt.TabFocusReason)
        self.settle()
        self.assertTrue(pen.isVisible())
        self.assertFalse(pen.geometry().intersects(row.close_button.geometry()))
        with self.asks(QMessageBox.Yes) as question, \
                patch.object(QInputDialog, 'getText', return_value=('Porte du passeur', True)) as rename:
            QTest.mouseClick(self.w.windowHandle(), Qt.LeftButton, Qt.NoModifier,
                             self.window_point(pen))
            self.settle()
        rename.assert_called_once()
        question.assert_not_called()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertTrue(self.w.carnet_is_open())
        self.assertEqual(self.w.bookmarks[0]['label'], 'Porte du passeur')

    def test_f2_renames_the_focused_row_and_keeps_keyboard_focus(self):
        self.row(2).setFocus(Qt.TabFocusReason)
        self.settle()
        with self.asks(QMessageBox.Yes) as question, \
                patch.object(QInputDialog, 'getText', return_value=('Grande salle', True)) as rename:
            QTest.keyClick(self.row(2), Qt.Key_F2)
            self.settle()
        rename.assert_called_once()
        self.assertEqual(rename.call_args.kwargs.get('text'), 'Salle')
        question.assert_not_called()
        self.assertEqual([b['label'] for b in self.w.bookmarks], ['Porte', 'Grande salle'])
        self.assertTrue(self.row(2).hasFocus())
        with patch.object(QInputDialog, 'getText', return_value=('', False)):
            QTest.keyClick(self.row(2), Qt.Key_F2)  # Annuler : libellé inchangé.
        self.assertEqual(self.w.bookmarks[1]['label'], 'Grande salle')
        with self.asks(QMessageBox.Yes):
            QTest.keyClick(self.row(2), Qt.Key_Space)  # Le clavier voyage toujours.
            self.settle()
        self.assertEqual(self.w.current_paragraph, 2)

    def test_context_menu_offers_rename_with_its_shortcut(self):
        menu = self.row(3).context_menu()
        actions = {a.text(): a for a in menu.actions()}
        self.assertEqual(actions['Renommer…'].shortcut().toString(), 'F2')
        with self.asks(QMessageBox.Yes) as question, \
                patch.object(QInputDialog, 'getText', return_value=('Pont', True)):
            actions['Renommer…'].trigger()
            self.settle()
        question.assert_not_called()
        self.assertEqual(self.w.bookmarks[0]['label'], 'Pont')

    def test_hint_no_longer_promises_double_click(self):
        hint = self.w.carnet_overlay.book.marks_hint.text()
        self.assertNotIn('double', hint.lower())
        self.assertIn('F2', hint)


if __name__ == '__main__':
    unittest.main()
