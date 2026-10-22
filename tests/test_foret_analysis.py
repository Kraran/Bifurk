"""Garanties de la revue : provenance, couverture et séparation analyse/exécution."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from PySide6.QtCore import QUrl
from book_events import verified_entry
from grimoire_modules.foret.controller import ForetController
from navigation import render_links
from tools.audit_foret import audit


class ForetAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).resolve().parents[1] /
                               'catalogues/evenements_foret_1983.json').read_text(encoding='utf-8'))

    def test_complete_analysis_does_not_enable_events(self):
        self.assertEqual(audit(self.data)['paragraphs'], 400)
        for number in range(1, 401):
            self.assertIsNone(verified_entry(self.data, number))

    def test_shop_prices_and_single_use_are_recorded(self):
        items = self.data['shop_analysis']['items']
        self.assertEqual(len(items), 17)
        self.assertEqual([item['gold_price'] for item in items],
                         [3,2,3,2,2,3,3,2,3,3,3,2,2,3,3,3,3])
        self.assertTrue(all(item['uses_per_purchase'] == 1 for item in items))

    def test_source_corrections_are_confirmed_and_no_longer_blocking(self):
        entries = self.data['paragraphs']
        self.assertEqual([route['target'] for route in entries['186']['routes']], [131])
        self.assertEqual(entries['186']['source_issues'][0]['status'], 'resolved')
        self.assertEqual([route['target'] for route in entries['267']['routes']], [196,25])
        self.assertEqual(entries['267']['source_issues'][0]['confirmed_target'],196)
        self.assertNotIn('unresolved_routes',entries['267'])
        self.assertEqual(audit(self.data)['blocking_source_issues'],[])

    def test_invalid_reference_cannot_be_followed_through_text(self):
        owner = SimpleNamespace(book_event_catalogue=self.data, current_paragraph=267,
                                paragraphs={1:'',25:'',196:''}, visited=[])
        owner.character = {'endurance':10}
        owner.combat_available = lambda: False
        owner._foret_combat = lambda: None
        owner._book_state = lambda number: {}
        owner._analysed_reading_entry = lambda: ForetController._analysed_reading_entry(owner)
        owner._reading_link_targets = lambda: ForetController._reading_link_targets(owner)
        owner.go_to = owner.visited.append
        html = render_links('Rendez-vous au 1%. Sinon rendez-vous au 25.', owner._reading_link_targets())
        self.assertNotIn('href="paragraph:1"', html)
        self.assertIn('href="paragraph:25"', html)
        for target in (1,196,25):
            ForetController.follow_link(owner, QUrl(f'paragraph:{target}'))
        self.assertEqual(owner.visited, [196,25])

    def test_route_conditions_remain_descriptive(self):
        route = self.data['paragraphs']['3']['routes'][0]
        self.assertEqual(route['target'], 322)
        self.assertIn('Anneau', route['condition_text'])
        self.assertFalse(self.data['analysis_contract']['conditions_are_executable'])
