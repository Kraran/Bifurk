"""Géométrie des vues, zoom, clics et régularité de la mise en page Qt.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PySide6.QtGui import QPixmap, QWheelEvent, QTextDocument
from PySide6.QtCore import Qt, QPoint, QPointF, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea, QWidget

from main import MainWindow
from grimoire_ui import IllustrationDialog


class GrimoireInterfaceTests(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.window = MainWindow()
        self.window.paragraphs = {
            1: "Une porte se dresse devant vous. Pour entrer, rendez-vous au 2.",
            2: "Vous découvrez une salle déserte.",
        }
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
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

    def test_first_text_line_has_same_spacing_as_following_lines(self):
        w = self.window
        for size in (14, 20, 34):
            with self.subTest(size=size):
                w.reader_font_size = size
                w._render_paragraph_text('Première ligne.\nDeuxième ligne.\nTroisième ligne.')
                self.app.processEvents()
                document = w.reader.document()
                block = document.begin()
                positions = []
                while block.isValid():
                    positions.append(document.documentLayout().blockBoundingRect(block).y())
                    block = block.next()
                self.assertEqual(len(positions), 3)
                self.assertAlmostEqual(positions[1] - positions[0], positions[2] - positions[1], places=2)

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
        # Proposition UI : sous 1100 px l'illustration est masquée automatiquement.
        self.assertFalse(w.scene_art.isVisible())
        self.assertGreaterEqual(w.reader.height(), 230)
        self.assertTrue(w.choice_group.isVisible())
        self.assertEqual(w.adventure_tabs.count(), 1)
        self.assertEqual(w.adventure_tabs.tabText(0), 'Sacoche')
        self.assertFalse(w.adventure_tabs.tabBar().isVisible())

    def test_inventory_icons_do_not_change_saved_item_names(self):
        w = self.window
        names = ["Épée", "Clé 111", "Clé rouge 111"]
        w.character["inventory"] = names[:]
        w._refresh_character()
        self.assertEqual([w.inventory_list.item(i).text() for i in range(3)], names)
        self.assertTrue(all(not w.inventory_list.item(i).icon().isNull() for i in range(3)))
        self.assertEqual(w.character["inventory"], names)

    def test_inventory_grid_keeps_slots_compact_with_many_objects(self):
        """La sacoche est une grille de cases : plusieurs objets par rangée, cases bornées."""
        w = self.window
        w.character["inventory"] = [f"Clé {number}" for number in range(12)]
        w._refresh_character()
        self.app.processEvents()
        rects = [w.inventory_list.visualItemRect(w.inventory_list.item(i)) for i in range(3)]
        self.assertLessEqual(rects[0].height(), 96)
        self.assertEqual({rect.top() for rect in rects}, {rects[0].top()})
        self.assertLess(rects[0].left(), rects[1].left())
        self.assertGreaterEqual(w.inventory_list.viewport().height(), rects[0].height())

    def test_sheet_mirrors_initial_values_potion_and_weapon_choice(self):
        w = self.window
        w.character.update(inventory=["Épée", "Épée magique", "Lanterne"], potion="Potion de Vigueur", potion_doses=1)
        w._refresh_character()
        self.app.processEvents()
        initial = w.character.get("initial", {})
        self.assertEqual(w.stat_medallions["endurance"].initial, initial.get("endurance"))
        self.assertEqual(w.potion_value.text(), "1/2")
        self.assertEqual(w.potion_token.caption, "VIGUEUR")
        self.assertFalse(w.potion_combo.isVisible())
        # Deux armes : la bannière de choix apparaît et le double-clic équipe.
        self.assertFalse(w.weapon_combo.isHidden())
        w._equip_from_grid(w.inventory_list.item(1))
        self.assertEqual(__import__("book_events").equipped_weapon(w.character), "Épée magique")
        self.assertIn("Arme équipée", w.inventory_list.item(1).toolTip())

    def test_opening_shows_cover_and_double_click_opens_displayed_image(self):
        w = self.window
        book_cover = {"id": "cover", "type": "couverture"}
        chapter_art = {"id": "chapter", "type": "illustration", "statut": "verifie", "paragraphes": [1]}
        catalogue = {"title": "Le Sorcier de la Montagne de Feu", "illustrations": [book_cover, chapter_art]}
        image = QPixmap(100, 150)
        image.fill()
        with patch.object(w, "_themed_file_dialog", return_value="/tmp/ui-book.pdf"), \
                patch("main.extract_paragraphs", return_value=w.paragraphs), \
                patch("main.import_book", return_value="/tmp/ui-book.pdf"), \
                patch("main.module_for_pdf", return_value=SimpleNamespace(
                    id='test', title='Le Sorcier de la Montagne de Feu', engine='sorcier-1982', rules_pages=(3, 14),
                    catalogue=lambda kind: catalogue if kind == 'illustrations' else None)), \
                patch.object(w, "_illustration_pixmap", return_value=image), \
                patch.object(w, "_show_illustration") as popup:
            w.open_pdf()
            popup.assert_not_called()
            self.assertIsNone(w.current_paragraph)
            self.assertEqual(w.visited_paragraphs, [])
            self.assertIn("Le Sorcier de la Montagne de Feu", w.reader.toPlainText())
            self.assertEqual(w.scene_entry, book_cover)
            QTest.mouseDClick(w.scene_art, Qt.LeftButton)
            popup.assert_called_once_with(book_cover, "Couverture du grimoire")
            popup.reset_mock()
            name = w.creation_name_field
            name.setText('Éléanor')
            w.creation_start_button.click()
            self.assertEqual(w.current_paragraph, 1)
            self.assertEqual(w.scene_entry, chapter_art)
            QTest.mouseDClick(w.scene_art, Qt.LeftButton)
            popup.assert_called_once_with(chapter_art, "Illustration — paragraphe 1")
            w.undo_action()
            self.assertIsNone(w.current_paragraph)
            self.assertEqual(w.scene_entry, book_cover)
            self.assertIn("Le Sorcier de la Montagne de Feu", w.reader.toPlainText())
            w.go_to(2)
            self.assertIsNone(w.current_paragraph)
            w.creation_start_button.click()
            w.go_to(2)
            self.assertIsNone(w.scene_entry)
            self.assertFalse(w.scene_art.is_book_art)

    def test_fixed_background_ignores_click_double_click_drag_and_wheel(self):
        scene = self.window.scene_art
        background = QPixmap(300, 600)
        background.fill()
        scene.set_background_art(background)
        with patch.object(self.window, '_show_illustration') as popup:
            QTest.mouseClick(scene, Qt.LeftButton)
            QTest.mouseDClick(scene, Qt.LeftButton)
            QTest.mousePress(scene, Qt.LeftButton, pos=QPoint(50, 60))
            QTest.mouseMove(scene, QPoint(100, 130))
            QTest.mouseRelease(scene, Qt.LeftButton, pos=QPoint(100, 130))
            wheel = QWheelEvent(QPointF(80, 80), QPointF(scene.mapToGlobal(QPoint(80, 80))),
                                QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                                Qt.NoScrollPhase, False)
            self.app.sendEvent(scene, wheel)
            popup.assert_not_called()
        self.assertFalse(scene.is_book_art)
        self.assertEqual(scene.zoom, 1.0)
        self.assertEqual(scene.pan, QPointF())
        self.assertEqual(scene.cursor().shape(), Qt.ArrowCursor)
        self.assertEqual(scene.toolTip(), '')
        scene.set_theme(self.window.theme)
        self.assertEqual(scene.picture.cacheKey(), background.cacheKey())

    def test_image_zoom_pan_and_click_reset(self):
        scene = self.window.scene_art
        image = QPixmap(600, 600)
        image.fill()
        scene.set_book_art(image)
        center = scene.rect().center()
        wheel = QWheelEvent(QPointF(center), QPointF(scene.mapToGlobal(center)),
                            QPoint(), QPoint(0, 720), Qt.NoButton, Qt.NoModifier,
                            Qt.NoScrollPhase, False)
        QApplication.sendEvent(scene, wheel)
        self.assertGreater(scene.zoom, 1)
        QTest.mousePress(scene, Qt.LeftButton, pos=center)
        self.assertEqual(scene.cursor().shape(), Qt.CrossCursor)
        QTest.mouseMove(scene, center + QPoint(30, 20))
        QTest.mouseRelease(scene, Qt.LeftButton, pos=center + QPoint(30, 20))
        self.assertGreater(scene.zoom, 1)
        self.assertNotEqual(scene.pan, QPointF())
        QTest.mouseClick(scene, Qt.LeftButton, pos=center)
        self.assertEqual(scene.zoom, 1)
        self.assertEqual(scene.pan, QPointF())
        scene.set_book_art(image)
        self.assertEqual(scene.zoom, 1)

    def test_enlargement_window_can_maximize_and_restore_default_size(self):
        w = self.window
        image = QPixmap(300, 500)
        image.fill()
        def inspect(dialog):
            dialog.show()
            self.app.processEvents()
            original = dialog.default_size
            self.assertTrue(dialog.windowFlags() & Qt.WindowMaximizeButtonHint)
            self.assertNotEqual(dialog.minimumSize(), dialog.maximumSize())
            dialog.resize(original.width() + 80, original.height() + 40)
            self.app.processEvents()
            self.assertNotEqual(dialog.size(), original)
            dialog.showMaximized()
            self.app.processEvents()
            self.assertTrue(dialog.isMaximized())
            dialog.restore_default_size()
            self.app.processEvents()
            self.assertEqual(dialog.size(), original)
            dialog.toggle_fullscreen()
            self.app.processEvents()
            self.assertTrue(dialog.isFullScreen())
            QTest.keyClick(dialog, Qt.Key_Escape)
            self.app.processEvents()
            self.assertFalse(dialog.isFullScreen())
            self.assertEqual(dialog.size(), original)
            dialog.close()
            return 0
        with patch.object(w, "_illustration_pixmap", return_value=image), \
                patch.object(IllustrationDialog, "exec", inspect):
            w._show_illustration({"page_pdf": 1}, "Illustration")
        self.assertFalse(any("Voir l’illustration du paragraphe" in b.text()
                             for b in w.findChildren(QPushButton)))


    def test_long_paragraph_opens_with_illuminated_drop_cap(self):
        w = self.window
        long_text = 'Votre torche révèle une porte de pierre. ' * 5
        w._render_paragraph_text(long_text)
        html = w.reader.toHtml()
        self.assertIn('bifurk-initial:', html)
        self.assertTrue(w.reader.toPlainText().rstrip().endswith('porte de pierre.'))
        url = next(f.name() for f in self._image_formats(w.reader.document()))
        self.assertIsNotNone(w.reader.document().resource(QTextDocument.ImageResource, QUrl(url)))
        self.assertIn('otre torche', w.reader.toPlainText())
        # Texte court ou ne commençant pas par une lettre : pas de lettrine.
        for text in ('Une porte.', '« ' + long_text):
            with self.subTest(text=text[:12]):
                w._render_paragraph_text(text)
                self.assertNotIn('bifurk-initial:', w.reader.toHtml())

    @staticmethod
    def _image_formats(document):
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fmt = it.fragment().charFormat()
                if fmt.isImageFormat():
                    yield fmt.toImageFormat()
                it += 1
            block = block.next()

    def test_choice_card_shows_seal_number_and_destination_without_changing_text(self):
        from grimoire_ui import ChoiceCard
        card = ChoiceCard('Prendre le passage ouest  →  §71')
        card.set_shortcut_number(3)
        self.assertEqual(card.text(), 'Prendre le passage ouest  →  §71')
        self.assertEqual(card._caption.text(), 'Prendre le passage ouest')
        self.assertEqual(card._destination, '§71')
        self.assertEqual(card.toolTip(), 'Touche 3')
        plain = ChoiceCard('Ouvrir une chronique sauvegardée')
        self.assertEqual(plain._caption.text(), 'Ouvrir une chronique sauvegardée')
        self.assertEqual(plain._destination, '')

    def test_header_commands_are_painted_medallions_with_tooltips(self):
        from grimoire_chrome import MedallionButton
        w = self.window
        header = w.findChild(QWidget, 'grimoireHeader')
        for button in (w.undo_btn, w.redo_btn, w.rules_button, w.map_button,
                       w.open_btn, w.settings_button):
            with self.subTest(button=button.caption):
                self.assertIsInstance(button, MedallionButton)
                self.assertTrue(header.isAncestorOf(button))
                self.assertTrue(button.toolTip())
        self.assertIsNotNone(w.settings_button.menu())
        self.assertEqual(w.paragraph_number.objectName(), 'paragraphNumber')

    def test_compact_window_keeps_choice_plaques_and_sheet_seals_inside(self):
        w = self.window
        w.resize(930, 650)
        w.go_to(1)
        self.app.processEvents()
        side = w.findChild(QScrollArea, 'sideScroll')
        # Sous 1100 px, la fiche est en tiroir : on la déplie pour la mesurer.
        w.toggle_sheet_drawer(True)
        self.app.processEvents()
        self.assertEqual(side.verticalScrollBar().maximum(), 0)
        self.assertEqual(side.horizontalScrollBar().maximum(), 0)
        self.assertTrue(w.stats_heading.isHidden())
        w.resize(1600, 900)
        self.app.processEvents()
        self.assertFalse(w.stats_heading.isHidden())

    def _choice_button(self):
        w = self.window
        return next(w.choice_layout.itemAt(i).widget() for i in range(w.choice_layout.count())
                    if isinstance(w.choice_layout.itemAt(i).widget(), QPushButton))

    def test_narrow_window_folds_sheet_into_a_drawer(self):
        w = self.window
        side = w.findChild(QScrollArea, 'sideScroll')
        w.resize(930, 650)
        w.go_to(1)
        self.app.processEvents()
        self.assertTrue(w.sheet_strip.isVisible())
        self.assertFalse(side.isVisible())
        self.assertNotIn(side, [w.splitter.widget(i) for i in range(w.splitter.count())])
        self.assertIn('8', w.sheet_strip.toolTip())
        # Un clic sur la bande déplie la fiche par-dessus la page, sans la déplacer.
        QTest.qWait(20)
        page_geometry = w.reader_panel.geometry()
        QTest.mouseClick(w.sheet_strip, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(side.isVisible())
        self.assertTrue(w.drawer_scrim.isVisible())
        self.assertEqual(w.reader_panel.geometry(), page_geometry)
        self.assertLessEqual(side.geometry().right(), w.sheet_strip.geometry().left())
        self.assertGreaterEqual(side.width(), 365)
        # Un clic à côté la referme.
        QTest.mouseClick(w.drawer_scrim, Qt.LeftButton, pos=QPoint(20, 20))
        self.app.processEvents()
        self.assertFalse(side.isVisible())
        self.assertFalse(w.drawer_scrim.isVisible())
        # Tab (hors champ de saisie) l'ouvre, Échap la referme.
        w.reader.setFocus()
        w.sheet_shortcut.activated.emit()
        self.app.processEvents()
        self.assertTrue(side.isVisible())
        w.escape_shortcut.activated.emit()
        self.app.processEvents()
        self.assertFalse(side.isVisible())
        # Une action de jeu la referme aussi.
        w.toggle_sheet_drawer(True)
        self._choice_button().click()
        self.app.processEvents()
        self.assertEqual(w.current_paragraph, 2)
        self.assertFalse(side.isVisible())

    def test_tab_in_an_editable_field_keeps_moving_focus(self):
        from PySide6.QtWidgets import QLineEdit
        w = self.window
        w.resize(930, 650)
        self.app.processEvents()
        w.toggle_sheet_drawer(True)
        self.app.processEvents()
        field = w.side_scroll.findChild(QLineEdit)
        if field is None:
            self.skipTest('pas de champ de saisie visible dans la fiche')
        field.setFocus()
        w._tab_sheet_drawer()
        self.assertTrue(w.side_scroll.isVisible())

    def test_wide_window_keeps_sheet_in_the_splitter(self):
        w = self.window
        side = w.findChild(QScrollArea, 'sideScroll')
        w.resize(930, 650)
        self.app.processEvents()
        w.toggle_sheet_drawer(True)
        w.resize(1600, 900)
        self.app.processEvents()
        self.assertFalse(w.sheet_strip.isVisible())
        self.assertFalse(w.drawer_scrim.isVisible())
        self.assertTrue(side.isVisible())
        self.assertEqual(w.splitter.indexOf(side), 2)
        self.assertGreaterEqual(side.width(), 330)
        w.toggle_sheet_drawer(True)
        self.assertFalse(w._drawer_open)

    def test_reading_mode_hides_sheet_and_banner(self):
        w = self.window
        header = w.findChild(QWidget, 'grimoireHeader')
        side = w.findChild(QScrollArea, 'sideScroll')
        w.resize(930, 650)
        w.go_to(1)
        self.app.processEvents()
        self.assertIn(w.reading_action, w.settings_button.menu().actions())
        self.assertIn('F10', w.reading_action.text())
        w.reading_action.trigger()
        self.app.processEvents()
        self.assertTrue(w.reading_mode)
        self.assertFalse(header.isVisible())
        self.assertFalse(w.sheet_strip.isVisible())
        self.assertFalse(side.isVisible())
        self.assertTrue(w.reading_exit_button.isVisible())
        self.assertTrue(w.reader.isVisible())
        self.assertTrue(self._choice_button().isVisible())
        w.escape_shortcut.activated.emit()
        self.app.processEvents()
        self.assertFalse(w.reading_mode)
        self.assertTrue(header.isVisible())
        self.assertTrue(w.sheet_strip.isVisible())
        # F10 marche aussi en grand écran, et une seconde fois pour revenir.
        w.resize(1600, 900)
        self.app.processEvents()
        w.toggle_reading_mode()
        self.app.processEvents()
        self.assertFalse(side.isVisible())
        w.toggle_reading_mode()
        self.app.processEvents()
        self.assertTrue(side.isVisible())
        self.assertTrue(header.isVisible())

    def test_story_font_follows_window_height_until_user_chooses(self):
        w = self.window
        for size, expected in (((930, 650), 16), ((1280, 720), 17), ((1600, 900), 20)):
            with self.subTest(size=size):
                w.resize(*size)
                self.app.processEvents()
                self.assertEqual(w.reader_font_size, expected)
        w.resize(930, 650)
        self.app.processEvents()
        w.change_reader_font_size(2)
        self.assertEqual(w.reader_font_size, 18)
        w.resize(1600, 900)
        self.app.processEvents()
        self.assertEqual(w.reader_font_size, 18)

    def test_low_window_uses_one_line_page_header_and_slim_banner(self):
        w = self.window
        w.resize(1280, 720)
        w.go_to(1)
        self.app.processEvents()
        self.assertTrue(w.undo_btn.slim)
        self.assertFalse(w.subtitle_label.isVisible())
        self.assertGreaterEqual(w.title_row.indexOf(w.paragraph_title), 0)
        self.assertTrue(w.undo_btn.toolTip())
        card = self._choice_button()
        self.assertTrue(card.tight)
        self.assertIn('§2', card._caption.text())
        self.assertTrue(card.isVisible())
        w.resize(1600, 900)
        self.app.processEvents()
        self.assertFalse(w.undo_btn.slim)
        self.assertTrue(w.subtitle_label.isVisible())
        self.assertEqual(w.title_row.indexOf(w.paragraph_title), -1)
        self.assertEqual(w.reader_layout.indexOf(w.paragraph_title), 0)

    def test_stat_shields_fill_as_gauges_and_replace_the_health_bar(self):
        from PySide6.QtWidgets import QProgressBar
        from adventurer_sheet import gauge_ratio
        w = self.window
        w.character["initial"] = {"habilete": 11, "endurance": 20, "chance": 9}
        w.character.update(habilete=11, endurance=10, chance=2)
        w._refresh_character()
        self.app.processEvents()
        self.assertEqual(w.findChildren(QProgressBar), [])
        self.assertFalse(hasattr(w, "stat_bars"))
        medals = w.stat_medallions
        self.assertEqual(medals["habilete"].ratio(), 1.0)
        self.assertAlmostEqual(medals["endurance"].ratio(), .5)
        self.assertAlmostEqual(medals["chance"].ratio(), 2 / 9)
        self.assertEqual(medals["endurance"].gauge_text(), "10 / 20")
        self.assertIn("10 / 20", medals["endurance"].toolTip())
        # Bornes : jamais négative, plafonnée au-dessus du départ, pleine sans maximum connu.
        self.assertEqual(gauge_ratio(0, 20), 0.0)
        self.assertEqual(gauge_ratio(-3, 20), 0.0)
        self.assertEqual(gauge_ratio(12, 8), 1.0)
        self.assertEqual(gauge_ratio(5, None), 1.0)
        # La couleur occupe le bas de l'écu, le haut reste creux et sombre.
        image = medals["endurance"].grab().toImage()
        cx = image.width() // 2
        low = image.pixelColor(cx - 22, int(image.height() * .78))
        high = image.pixelColor(cx - 22, int(image.height() * .38))
        self.assertGreater(low.red(), high.red() + 40)
        self.assertGreater(low.lightness(), high.lightness())
        self.assertEqual(w.sheet_strip.state["endurance"], (10, 20))

    def test_banner_icons_keep_clear_of_the_gilded_edge(self):
        w = self.window
        header = w.header_frame
        for size in ((1600, 900), (1280, 720), (930, 650)):
            w.resize(*size)
            w.go_to(1)
            self.app.processEvents()
            for button in (w.undo_btn, w.settings_button):
                with self.subTest(size=size, button=button.caption):
                    geo = button.geometry()
                    self.assertGreaterEqual(geo.top(), 7)
                    self.assertGreaterEqual(header.height() - 1 - geo.bottom(), 6)
                    self.assertGreaterEqual(header.width() - 1 - geo.right(), 26)

    def test_shop_and_sale_icons_stay_sharp_at_each_scale(self):
        from PySide6.QtCore import QSize

        from item_icons import item_qicon
        for name in ('Miroir', 'Anneau de Glace', 'Bougie de couleur', 'Lanterne'):
            icon = item_qicon(name)
            for ratio in (1, 1.25, 1.5):
                with self.subTest(name=name, ratio=ratio):
                    pixmap = icon.pixmap(QSize(28, 28), ratio)
                    self.assertGreaterEqual(pixmap.width(), round(28 * ratio))
                    image = pixmap.toImage()
                    inked = sum(image.pixelColor(x, y).alpha() > 0
                                for x in range(0, image.width(), 2) for y in range(0, image.height(), 2))
                    self.assertGreater(inked, 20)

if __name__ == "__main__":
    unittest.main()
