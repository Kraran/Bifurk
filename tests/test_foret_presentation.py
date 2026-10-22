"""Présentation multi-grimoires avec PDF synthétiques ; contrôle privé conditionnel de l'édition."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

import main
from grimoire_library import GrimoireLibraryDialog, imported_grimoires
from grimoire_modules.registry import available_modules, module_for_pdf, pdf_digest
from save_slots import SaveSlotsDialog


class ForetPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.modules = {m.engine: m for m in available_modules()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for key, path in {'APP_DIR': self.root, 'BOOKS_DIR': self.root/'donnees/grimoires',
                          'SAVES_DIR': self.root/'donnees/sauvegardes',
                          'SETTINGS_DIR': self.root/'donnees/parametres'}.items():
            mock = patch.object(main, key, path)
            mock.start()
            self.addCleanup(mock.stop)
        main.init_portable_dirs()
        self.sources = {}
        for name in ('foret', 'sorcier'):
            path = self.root / f'{name}.pdf'
            with pymupdf.open() as document:
                for index in range(170):
                    page = document.new_page(width=504.6, height=842)
                    if index == 0:
                        page.draw_rect(page.rect, color=(.3,.4,.2), fill=(.7,.7,.4))
                    if index == 18:
                        page.insert_text((30,40), '1\nUne foret. Rendez-vous au 2.\n2\nUne clairiere.\n86\nUne tour.\n350\nUn chemin.')
                document.save(path)
            self.sources[name] = path
        def recognize(path):
            return self.modules['foret-1983' if 'foret' in Path(path).name else 'sorcier-1982']
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, side_effect=recognize)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information','warning','critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        mock = patch.object(self.w, '_roll', side_effect=lambda count, *a, **k: ([3]*count, 3*count))
        self.roll = mock.start()
        self.addCleanup(mock.stop)

    def open(self, name='foret'):
        self.w.open_pdf(self.sources[name], startup=True)

    def start(self):
        self.w._begin_adventure('Eldan')

    def test_cover_title_starting_resources_and_preparation_notice(self):
        self.open()
        self.assertEqual(self.w.book_module.id, 'foret_malediction_1983')
        self.assertEqual(self.w.book_label.text(), 'La Forêt de la Malédiction')
        self.assertIn('La Forêt de la Malédiction', self.w.reader.toPlainText())
        self.assertIn('préparation', self.w.reader.toPlainText())
        self.assertEqual(self.w.scene_entry['type'], 'couverture')
        self.assertTrue(self.w.scene_art.is_book_art)
        self.assertIsNotNone(self.w.findChild(QPushButton, 'readPrologue'))
        self.assertEqual(self.w.character['gold'], 30)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)

    def test_analysed_title_routes_and_source_warning_are_presented_without_effects(self):
        self.open()
        self.start()
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.assertEqual(self.w.paragraph_title.text(), 'La tour de Yaztromo')
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any('Suivre le mage' in button.text() for button in buttons))
        self.w.paragraphs[267] = 'Rendez-vous au 1%. Sinon rendez-vous au 25.'
        self.w.paragraphs[25] = 'Une bifurcation.'
        self.w.go_to(267)
        self.assertNotIn('href="paragraph:1"', self.w.reader.toHtml())
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any(not button.isEnabled() and 'confirmer' in button.text()
                            for button in buttons))
        self.assertEqual(self.w.character, before)
        self.assertEqual(self.roll.call_count, dice)

    def test_prologue_is_private_page_view_and_never_awards_resources_twice(self):
        self.open()
        before = self.w._snapshot()
        dice = self.roll.call_count
        self.w.show_prologue()
        dialog = self.w.prologue_dialog
        self.assertEqual((dialog.first_page, dialog.last_page, dialog.pages.count()), (14,16,3))
        dialog.pages.setCurrentIndex(2)
        self.assertEqual(dialog.viewer.accessibleName(), 'Prologue — page PDF 16')
        self.w.show_prologue()
        self.assertIs(self.w.prologue_dialog, dialog)
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.roll.call_count, dice)

    def test_rules_interval_and_old_book_views_close_when_switching(self):
        self.open()
        self.w.show_rules()
        rules = self.w.rules_dialog
        self.assertEqual((rules.first_page, rules.last_page), (4,13))
        self.w.show_prologue()
        prologue = self.w.prologue_dialog
        self.open('sorcier')
        self.assertFalse(rules.isVisible())
        self.assertFalse(prologue.isVisible())
        self.assertIsNone(self.w.rules_dialog)
        self.assertIsNone(self.w.prologue_dialog)
        self.assertEqual(self.w.character['gold'], 1)
        self.assertNotIn('Carte de Yaztromo', self.w.character['inventory'])
        self.w.show_rules()
        self.assertEqual((self.w.rules_dialog.first_page, self.w.rules_dialog.last_page), (3,14))

    def test_reroll_start_and_save_load_do_not_reapply_starting_gold(self):
        self.open()
        self.w._reroll_adventurer()
        self.assertEqual(self.w.character['gold'], 30)
        self.start()
        self.w.character['gold'] = 12
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.open('sorcier')
        self.start()
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.book_module.engine, 'foret-1983')
        self.assertEqual(self.w.character['gold'], 12)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.book_event_catalogue['reviewed_count'], 400)
        self.assertEqual(self.w.preferences['last_book'], Path(self.w.pdf_path).name)

    def test_consultation_never_activates_sorcier_paragraph_rules(self):
        self.open()
        self.start()
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.w.go_to(86)
        self.w.go_to(350)
        self.w.combat_round()
        self.assertEqual(self.w.character, before)
        self.assertIsNone(self.w.crocodile_combat)
        self.assertIsNone(self.w.piranha_combat)
        self.assertEqual(self.w.completed_book_events, set())
        self.assertFalse(self.w.combat_button.isEnabled())
        self.assertEqual(self.roll.call_count, dice)
        self.assertIsNone(self.w.scene_entry)
        self.assertFalse(self.w.scene_art.is_book_art)
        self.assertTrue(self.w.scene_art.background_art.isNull())

    def test_library_lists_both_covers_and_preselects_last_book(self):
        self.open('sorcier')
        self.open()
        books = imported_grimoires(main.BOOKS_DIR)
        self.assertEqual(len(books), 2)
        dialog = GrimoireLibraryDialog(books, self.w.pdf_path, self.w)
        try:
            self.assertIn('La Forêt', dialog.books.currentItem().text())
            self.assertFalse(dialog.books.currentItem().icon().isNull())
            self.assertIn('préparation', dialog.books.currentItem().text())
            dialog.choose()
            self.assertEqual(dialog.selected_path, self.w.pdf_path)
        finally:
            dialog.deleteLater()

    def test_library_cancel_keeps_game_and_two_book_new_game_opens_selected_module(self):
        self.open('sorcier')
        sorcier = self.w.pdf_path
        self.open()
        self.start()
        before = self.w._snapshot()
        with patch.object(self.w, '_select_grimoire', return_value=None):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)), \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)) as selector:
            self.w._start_new_game()
        selector.assert_called_once()
        self.assertEqual(self.w.book_module.engine, 'sorcier-1982')
        self.assertIsNone(self.w.current_paragraph)

    def test_save_slots_identify_the_adventure_without_adding_text_rows(self):
        self.open()
        self.start()
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        dialog = SaveSlotsDialog(main.SAVES_DIR, False, self.w)
        try:
            button = dialog.findChild(QPushButton, 'saveSlot1')
            self.assertIn('La Forêt de la Malédiction', button.text().splitlines()[0])
            self.assertEqual(len(button.text().splitlines()), 3)
        finally:
            dialog.deleteLater()


class ForetEditionContractTests(unittest.TestCase):
    def test_presentation_catalogues_are_honest_about_pending_paragraphs(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        events = module.catalogue('events')
        self.assertEqual(module.rules_pages, (4,13))
        self.assertEqual(module.intro_pages, (14,16))
        self.assertEqual(module.status, 'preview')
        self.assertEqual(len(events['paragraphs']), 400)
        self.assertEqual(events['review_pending'], [])
        self.assertEqual(events['automation_pending'], list(range(1,401)))

    def test_private_pdf_is_recognized_and_cover_crop_fits_real_page(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        root = Path(__file__).resolve().parents[1]
        candidates = [*root.glob('*.pdf'), *(root/'donnees/grimoires').glob('*.pdf'),
                      *(root.parent/'attachments').rglob('*.pdf')]
        path = next((p for p in candidates if pdf_digest(p) == module.pdf_sha256), None)
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        self.assertEqual(module_for_pdf(path).id, module.id)
        with pymupdf.open(path) as document:
            self.assertEqual(len(document), 170)
            rect = pymupdf.Rect(module.catalogue('illustrations')['illustrations'][0]['rect'])
            self.assertTrue(document[0].rect.contains(rect))
