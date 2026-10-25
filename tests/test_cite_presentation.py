"""Cité des Voleurs, phase 1 : reconnaissance et consultation avec PDF synthétiques.

Aucun texte du livre n'est utilisé ; un contrôle conditionnel vérifie l'édition privée
si elle est présente localement.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
)

import main
from grimoire_library import GrimoireLibraryDialog, imported_grimoires
from grimoire_modules.controller import CONTROLLERS
from grimoire_modules.registry import (
    SUPPORTED_ENGINES,
    available_modules,
    module_for_pdf,
    pdf_digest,
)

CATALOGUES = Path(__file__).resolve().parents[1] / 'catalogues'


def _strings(value):
    """Parcourir clés et valeurs textuelles d'un catalogue JSON."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


class CiteCatalogueTests(unittest.TestCase):
    def test_manifest_declares_preview_engine_pages_and_starting_gold(self):
        module = next(m for m in available_modules() if m.id == 'cite_voleurs_1983')
        self.assertEqual(module.engine, 'cite-1983')
        self.assertIn('cite-1983', SUPPORTED_ENGINES)
        self.assertEqual(CONTROLLERS['cite-1983'].__name__, 'CiteController')
        self.assertEqual(module.title, 'La Cité des Voleurs')
        self.assertEqual((module.paragraph_count, module.rules_pages, module.intro_pages), (400, (4, 13), (14, 18)))
        self.assertEqual(module.intro_title, 'Les terribles messagers de Zanbar Bone')
        self.assertEqual((module.status, module.starting_gold, module.starting_items), ('preview', 30, ()))

    def test_catalogues_share_the_edition_digest_and_contain_no_rules_yet(self):
        module = next(m for m in available_modules() if m.engine == 'cite-1983')
        events = module.catalogue('events')
        art = module.catalogue('illustrations')
        self.assertEqual(events['pdf_sha256'], module.pdf_sha256)
        self.assertEqual(art['pdf_sha256'], module.pdf_sha256)
        self.assertEqual(events['paragraphs'], {})
        self.assertEqual((events['total_paragraphs'], events['reviewed_count']), (400, 0))
        self.assertEqual(events['review_pending'], list(range(1, 401)))
        self.assertEqual([entry['type'] for entry in art['illustrations']], ['couverture'])
        self.assertEqual(art['pdf_pages'], 177)

    def test_catalogue_files_are_plain_json_without_book_text(self):
        for name in ('modules/cite_voleurs_1983.json', 'cite_voleurs_1983.json', 'evenements_cite_1983.json'):
            with self.subTest(name=name):
                data = json.loads((CATALOGUES / name).read_text(encoding='utf-8'))
                strings = list(_strings(data))
                # Titres, identifiants et empreintes seulement : aucun passage narratif.
                self.assertLessEqual(max(map(len, strings)), 64)

    def test_private_pdf_is_recognized_and_cover_crop_fits_real_page(self):
        module = next(m for m in available_modules() if m.engine == 'cite-1983')
        root = Path(__file__).resolve().parents[1]
        candidates = [*root.glob('*.pdf'), *(root/'donnees/grimoires').glob('*.pdf'),
                      *(root.parent/'attachments').rglob('*.pdf')]
        path = next((p for p in candidates if pdf_digest(p) == module.pdf_sha256), None)
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        self.assertEqual(module_for_pdf(path).id, module.id)
        with pymupdf.open(path) as document:
            self.assertEqual(len(document), 177)
            entry = module.catalogue('illustrations')['illustrations'][0]
            page = document[entry['page_pdf'] - 1]
            rect = pymupdf.Rect(entry['rect'])
            self.assertTrue(page.rect.contains(rect))
            self.assertTrue(any(max(abs(a-b) for a, b in zip(rect, image['bbox'])) < 3
                                for image in page.get_image_info()))


class CitePresentationTests(unittest.TestCase):
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
        for name in ('cite', 'foret'):
            path = main.BOOKS_DIR / f'{name}.pdf'
            with pymupdf.open() as document:
                for index in range(177):
                    page = document.new_page(width=504.6, height=842)
                    if index == 0:
                        page.draw_rect(page.rect, color=(.2,.2,.3), fill=(.5,.5,.6))
                    if index == 19:
                        page.insert_text((30,40), '1\nUne route. Rendez-vous au 2.\n2\nUne porte.'
                                                  '\n86\nUn quai.\n156\nUne ruelle.\n350\nUn pont.')
                document.save(path)
            self.sources[name] = path
        engines = {'cite': 'cite-1983', 'foret': 'foret-1983'}
        def recognize(path):
            return self.modules[engines[Path(path).stem]]
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, side_effect=recognize)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information','warning','critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        self.addCleanup(self.w.sounds._close_log)
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        mock = patch.object(self.w, '_roll', side_effect=lambda count, *a, **k: ([3]*count, 3*count))
        self.roll = mock.start()
        self.addCleanup(mock.stop)

    def open(self, name='cite'):
        self.w.open_pdf(self.sources[name], startup=True)

    def start(self):
        self.w._begin_adventure('Eldan')

    def buttons(self):
        return [self.w.choice_layout.itemAt(i).widget() for i in range(self.w.choice_layout.count())]

    def test_library_lists_the_city_as_in_preparation(self):
        dialog = GrimoireLibraryDialog(imported_grimoires(main.BOOKS_DIR), self.sources['cite'], self.w)
        self.addCleanup(dialog.deleteLater)
        items = dialog.findChild(QListWidget)
        texts = [items.item(i).text() for i in range(items.count())]
        city = next(text for text in texts if text.startswith('La Cité des Voleurs'))
        self.assertIn('En préparation', city)

    def test_cover_title_starting_gold_and_preparation_notice(self):
        with patch.object(self.w.sounds, 'play_book_intro') as play:
            self.open()
            play.assert_called_once_with('cite-1983')
        self.assertEqual(self.w.book_module.id, 'cite_voleurs_1983')
        self.assertEqual(self.w.book_label.text(), 'La Cité des Voleurs')
        self.assertIn('La Cité des Voleurs', self.w.reader.toPlainText())
        self.assertIn('préparation', self.w.reader.toPlainText())
        self.assertEqual(self.w.scene_entry['type'], 'couverture')
        self.assertIsNotNone(self.w.findChild(QPushButton, 'readPrologue'))
        self.assertEqual(self.w.character['gold'], 30)
        self.assertEqual(self.w.character['provisions'], 10)
        self.assertNotIn('Carte de Yaztromo', self.w.character['inventory'])

    def test_prologue_and_rules_use_the_city_pages_without_awarding_resources(self):
        self.open()
        before = self.w._snapshot()
        dice = self.roll.call_count
        self.w.show_prologue()
        dialog = self.w.prologue_dialog
        self.assertEqual((dialog.first_page, dialog.last_page, dialog.pages.count()), (14, 18, 5))
        self.w.show_rules()
        self.assertEqual((self.w.rules_dialog.first_page, self.w.rules_dialog.last_page), (4, 13))
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.roll.call_count, dice)

    def test_switching_books_rebuilds_each_starting_profile(self):
        self.open('foret')
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)
        self.w.show_rules()
        rules = self.w.rules_dialog
        self.open()
        self.assertFalse(rules.isVisible())
        self.assertEqual(self.w.character['gold'], 30)
        self.assertNotIn('Carte de Yaztromo', self.w.character['inventory'])

    def test_consultation_applies_no_effect_of_other_books(self):
        self.open()
        self.start()
        self.assertFalse(self.w.combat_available())
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        # Ces numéros déclenchent des règles du Sorcier ou de la Forêt ; ici, rien.
        for number in (2, 86, 156, 350):
            self.w.go_to(number)
            self.assertEqual(self.w.current_paragraph, number)
            self.assertEqual(self.w.paragraph_title.text(), 'La Cité des Voleurs')
        self.assertEqual(self.w.character, before)
        self.assertEqual(self.roll.call_count, dice)
        self.assertIsNone(self.w.piranha_combat)
        self.w.combat_round()
        self.assertIn('préparation', self.w.rules_log.text())

    def test_printed_links_navigate_and_preparation_notice_is_shown(self):
        self.open()
        self.start()
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertTrue(any(b.isEnabled() and '2' in b.text() for b in self.buttons()))
        self.assertTrue(any('en préparation' in label.text().casefold()
                            for label in self.w.event_group.findChildren(QLabel)))
        self.w.follow_link(QUrl('paragraph:2'))
        self.assertEqual(self.w.current_paragraph, 2)
        self.w.follow_link(QUrl('paragraph:399'))
        self.assertEqual(self.w.current_paragraph, 2)
        self.w.follow_link(QUrl('https://example.org'))
        self.assertEqual(self.w.current_paragraph, 2)

    def test_meal_allowed_anywhere_outside_combat_once_per_passage(self):
        from grimoire_modules.fighting_fantasy.controller import MEAL_ALREADY_TAKEN
        self.open()
        self.start()
        w = self.w
        w.go_to(86)
        w.character['endurance'] = 8
        w.character['initial']['endurance'] = 20
        meal = lambda: next(o for o in w.care_options() if o['id'] == 'meal')
        self.assertTrue(meal()['enabled'])
        w.use_care('meal')
        self.assertEqual((w.character['endurance'], w.character['provisions']), (12, 9))
        self.assertEqual(meal()['reason'], MEAL_ALREADY_TAKEN)
        before = copy.deepcopy(w.character)
        w.eat_meal()
        self.assertEqual(w.character, before)
        w.go_to(156)
        self.assertTrue(meal()['enabled'])

    def test_save_load_keeps_module_position_and_spent_gold(self):
        self.open()
        self.start()
        self.w.go_to(86)
        self.w.character['gold'] = 12
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.open('foret')
        self.start()
        with patch('main.extract_paragraphs', return_value=dict(self.w.paragraphs)):
            self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.book_module.engine, 'cite-1983')
        self.assertEqual((self.w.character['gold'], self.w.current_paragraph), (12, 86))
        self.assertEqual(self.w.paragraph_title.text(), 'La Cité des Voleurs')


if __name__ == '__main__':
    unittest.main()
