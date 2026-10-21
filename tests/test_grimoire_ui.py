"""Behaviour of the illustrated reader, without a private PDF."""
import unittest
from unittest.mock import patch

from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from main import MainWindow


class GrimoireInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.paragraphs = {
            1: "Une porte se dresse devant vous. Pour entrer, rendez-vous au 2.",
            2: "Vous découvrez une salle déserte.",
        }
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_choice_card_keeps_navigation_and_undo(self):
        w = self.window
        w.go_to(1)
        button = next(w.choice_layout.itemAt(i).widget() for i in range(w.choice_layout.count())
                      if isinstance(w.choice_layout.itemAt(i).widget(), QPushButton))
        button.click()
        self.assertEqual(w.current_paragraph, 2)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 1)

    def test_hidden_art_stays_hidden_when_following_a_choice(self):
        w = self.window
        w.go_to(1)
        w.art_toggle.click()
        w.go_to(2)
        self.assertTrue(w.scene_art.isHidden())
        w.art_toggle.click()
        self.assertFalse(w.scene_art.isHidden())

    def test_illustration_is_inline_without_modal_dialog(self):
        w = self.window
        w.pdf_path = "/tmp/bifurk-ui-test.pdf"
        w.illustration_catalogue = {"illustrations": []}
        illustration = QPixmap(80, 120)
        illustration.fill()
        with patch("main.images_for_paragraph", return_value=[{"id": "demo"}]), \
                patch.object(w, "_illustration_pixmap", return_value=illustration), \
                patch.object(w, "show_paragraph_illustration") as modal:
            w.go_to(1)
            self.assertTrue(w.scene_art.is_book_art)
            modal.assert_not_called()
        w.illustration_catalogue = None
        w.go_to(2)
        self.assertFalse(w.scene_art.is_book_art)

    def test_small_window_keeps_controls_reachable(self):
        w = self.window
        w.resize(930, 650)
        w.go_to(1)
        self.app.processEvents()
        page = w.findChild(QScrollArea, "pageScroll")
        self.assertEqual(w.width(), 930)
        self.assertEqual(page.horizontalScrollBar().maximum(), 0)
        self.assertLessEqual(w.scene_art.geometry().right(), page.geometry().left() + 1)
        self.assertGreaterEqual(w.reader.height(), 230)
        self.assertTrue(w.choice_group.isVisible())
        w.adventure_tabs.setCurrentIndex(1)
        self.assertEqual(w.adventure_tabs.currentIndex(), 1)

    def test_inventory_icons_do_not_change_saved_item_names(self):
        w = self.window
        names = ["Épée", "Clé 111", "Clé rouge 111"]
        w.character["inventory"] = names[:]
        w._refresh_character()
        self.assertEqual([w.inventory_list.item(i).text() for i in range(3)], names)
        self.assertTrue(all(not w.inventory_list.item(i).icon().isNull() for i in range(3)))
        self.assertEqual(w.character["inventory"], names)

    def test_inventory_rows_remain_compact_with_many_objects(self):
        w = self.window
        w.character["inventory"] = [f"Clé {number}" for number in range(12)]
        w._refresh_character()
        self.app.processEvents()
        first = w.inventory_list.visualItemRect(w.inventory_list.item(0))
        self.assertLessEqual(first.height(), 44)
        self.assertGreaterEqual(w.inventory_list.viewport().height(), first.height() * 3)

    def test_opening_shows_cover_and_double_click_opens_displayed_image(self):
        w = self.window
        book_cover = {"id": "cover", "type": "couverture"}
        chapter_art = {"id": "chapter", "type": "illustration", "statut": "verifie", "paragraphes": [1]}
        catalogue = {"illustrations": [book_cover, chapter_art]}
        image = QPixmap(100, 150)
        image.fill()
        with patch.object(w, "_themed_file_dialog", return_value="/tmp/ui-book.pdf"), \
                patch("main.extract_paragraphs", return_value=w.paragraphs), \
                patch("main.import_book", return_value="/tmp/ui-book.pdf"), \
                patch("main.catalogue_for_pdf", return_value=catalogue), \
                patch("main.load_book_events", return_value=None), \
                patch.object(w, "_illustration_pixmap", return_value=image), \
                patch.object(w, "_show_illustration") as popup:
            w.open_pdf()
            popup.assert_not_called()
            self.assertEqual(w.scene_entry, book_cover)
            QTest.mouseDClick(w.scene_art, Qt.LeftButton)
            popup.assert_called_once_with(book_cover, "Couverture du grimoire")
            popup.reset_mock()
            w.go_to(1)
            self.assertEqual(w.scene_entry, chapter_art)
            QTest.mouseDClick(w.scene_art, Qt.LeftButton)
            popup.assert_called_once_with(chapter_art, "Illustration — paragraphe 1")
            w.go_to(2)
            self.assertEqual(w.scene_entry, book_cover)


if __name__ == "__main__":
    unittest.main()
