"""Contrat des modules sans diffuser le texte du PDF privé."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from grimoire_modules.registry import available_modules, module_for_pdf, CATALOGUES
from grimoire_modules.controller import ModuleActions, CONTROLLERS


class ModuleRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'modules').mkdir()

    def add_book(self, identity, content, pages=(3, 14)):
        pdf = self.root / f'{identity}.pdf'
        pdf.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        manifest = {'schema_version': 1, 'id': identity, 'title': identity,
                    'engine': 'sorcier-1982', 'pdf_sha256': digest,
                    'paragraph_count': 2, 'rules_pages': list(pages),
                    'catalogues': {'events': f'{identity}-events.json',
                                   'illustrations': f'{identity}-art.json'}}
        (self.root / manifest['catalogues']['events']).write_text(json.dumps({
            'pdf_sha256': digest, 'paragraphs': {'1': {'status': 'verifie',
                'combat': {'enemies': [{'name': identity, 'skill': 6, 'stamina': 4}]}}}}))
        (self.root / manifest['catalogues']['illustrations']).write_text(json.dumps({
            'pdf_sha256': digest, 'illustrations': [], 'title': identity}))
        path = self.root / 'modules' / f'{identity}.json'
        path.write_text(json.dumps(manifest))
        return pdf, path

    def test_two_books_select_separate_combat_databases_and_rules(self):
        first, _ = self.add_book('first', b'edition one')
        second, _ = self.add_book('second', b'edition two', (5, 12))
        a = module_for_pdf(first, catalogue_root=self.root)
        b = module_for_pdf(second, catalogue_root=self.root)
        self.assertEqual(a.id, 'first')
        self.assertEqual(b.rules_pages, (5, 12))
        self.assertEqual(b.catalogue('events')['paragraphs']['1']['combat']['enemies'][0]['name'], 'second')
        data = a.catalogue('events')
        data['paragraphs'].clear()
        self.assertTrue(a.catalogue('events')['paragraphs'])

    def test_unknown_or_replaced_pdf_never_receives_known_rules(self):
        pdf, _ = self.add_book('first', b'original')
        self.assertIsNotNone(module_for_pdf(pdf, catalogue_root=self.root))
        pdf.write_bytes(b'replacement')
        self.assertIsNone(module_for_pdf(pdf, catalogue_root=self.root))
        self.assertIsNone(module_for_pdf(None, catalogue_root=self.root))

    def test_duplicate_identity_or_edition_is_rejected(self):
        _, path = self.add_book('first', b'original')
        (path.parent / 'duplicate.json').write_text(path.read_text())
        with self.assertRaises(ValueError):
            available_modules(self.root)

    def test_cross_book_catalogue_is_rejected(self):
        _, path = self.add_book('first', b'original')
        self.add_book('second', b'another')
        manifest = json.loads(path.read_text())
        manifest['catalogues']['events'] = 'second-events.json'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            available_modules(self.root)

    def test_invalid_engine_pages_and_resource_escape_are_rejected(self):
        _, path = self.add_book('first', b'original')
        original = json.loads(path.read_text())
        for update in ({'engine': 'unsupported'}, {'rules_pages': [14, 3]},
                       {'catalogues': {'events': '../outside.json'}}, {'intro_pages': None},
                       {'intro_pages': [14, 16], 'intro_title': ''}, {'starting_gold': -1},
                       {'starting_items': [5]}, {'status': 'unknown'}):
            with self.subTest(update=update):
                path.write_text(json.dumps(original | update))
                with self.assertRaises(ValueError):
                    available_modules(self.root)

    def test_shipped_module_matches_both_catalogues(self):
        modules = available_modules()
        sorcier = next(m for m in modules if m.id == 'sorcier_montagne_feu_1982')
        self.assertEqual(len(sorcier.catalogue('events')['paragraphs']), 400)
        self.assertEqual(sorcier.catalogue('illustrations')['pdf_sha256'], sorcier.pdf_sha256)
        self.assertEqual(sorcier.rules_pages, (3, 14))

    def test_dispatch_changes_controller_when_book_changes(self):
        class First:
            def combat_round(owner):
                return 'first'
        class Second:
            def combat_round(owner):
                return 'second'
        owner = SimpleNamespace(book_module=SimpleNamespace(engine='one'))
        with patch.dict(CONTROLLERS, {'one': First, 'two': Second}):
            self.assertEqual(ModuleActions.combat_round(owner), 'first')
            owner.book_module = SimpleNamespace(engine='two')
            self.assertEqual(ModuleActions.combat_round(owner), 'second')
            owner.book_module = SimpleNamespace(engine='missing')
            with self.assertRaises(ValueError):
                ModuleActions.combat_round(owner)


class ModuleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_save_records_module_and_wrong_module_does_not_replace_current_game(self):
        from main import MainWindow
        w = MainWindow()
        self.addCleanup(w.deleteLater)
        self.addCleanup(w.close)
        w.book_module = available_modules()[0]
        self.assertEqual(w._save_data()['module_id'], w.book_module.id)
        before = w._snapshot()
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / 'book.pdf'
            pdf.write_bytes(b'placeholder')
            with patch('main.read_save', return_value={'pdf_path': 'book.pdf',
                    'pdf_sha256': None, 'module_id': 'wrong-module'}), \
                 patch('main.resolve_book_reference', return_value=str(pdf)), \
                 patch('main.module_for_pdf', return_value=w.book_module), \
                 patch('main.extract_paragraphs') as extract:
                self.assertFalse(w.load_game(Path(folder) / 'slot.json', announce=False))
                extract.assert_not_called()
        self.assertEqual(w._snapshot(), before)

    def test_rules_viewer_uses_module_page_range(self):
        import pymupdf
        from rules_viewer import RulesDialog
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / 'rules.pdf'
            with pymupdf.open() as document:
                for index in range(8):
                    page = document.new_page(width=100, height=100)
                    page.insert_text((10, 30), f'Page {index + 1}')
                document.save(pdf)
            dialog = RulesDialog(pdf, pages=(5, 7))
            try:
                self.assertEqual(dialog.pages.count(), 3)
                self.assertEqual(dialog.viewer.accessibleName(), 'Règles — page PDF 5')
                dialog.pages.setCurrentIndex(2)
                self.assertEqual(dialog.viewer.accessibleName(), 'Règles — page PDF 7')
                self.assertFalse(dialog.following.isEnabled())
            finally:
                dialog.close()
                dialog.deleteLater()
