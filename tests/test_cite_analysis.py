"""Cité des Voleurs, phase 2 : catalogue des renvois relus, audit et liens de lecture."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QUrl

from book_events import verified_entry
from grimoire_modules.cite.controller import CiteController
from grimoire_modules.registry import pdf_digest
from navigation import render_links
from tools.audit_cite import audit

ROOT = Path(__file__).resolve().parents[1]


class CiteAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'catalogues/evenements_cite_1983.json').read_text(encoding='utf-8'))

    def broken(self, change):
        catalogue = deepcopy(self.data)
        change(catalogue['paragraphs'])
        with self.assertRaises(ValueError):
            audit(catalogue)

    def test_audit_covers_every_paragraph_without_gap(self):
        report = audit(self.data)
        self.assertEqual((report['paragraphs'], report['routes']), (400, 671))
        self.assertEqual((report['orphans'], report['unreachable']), ([], []))
        self.assertEqual(report['blocking_source_issues'], [])
        self.assertEqual(report['terminal_paragraphs'], [9, 56, 59, 70, 129, 142, 210, 288, 299, 346, 400])

    def test_catalogue_never_enables_runtime_events(self):
        for number in range(1, 401):
            self.assertIsNone(verified_entry(self.data, number))
        catalogue = deepcopy(self.data)
        catalogue['analysis_contract']['conditions_are_executable'] = True
        with self.assertRaises(ValueError):
            audit(catalogue)

    def test_audit_rejects_duplicates_bad_modes_and_empty_labels(self):
        def duplicate(entries):
            entries['1']['routes'].append(dict(entries['1']['routes'][0]))
        def mode(entries):
            entries['400']['mode'] = 'choix'
        def label(entries):
            entries['1']['routes'][0]['label'] = ' '
        def missing(entries):
            del entries['2']
        for change in (duplicate, mode, label, missing):
            with self.subTest(change=change.__name__):
                self.broken(change)

    def test_audit_rejects_orphans_and_unreachable_paragraphs(self):
        def orphan(entries):
            # Retirer l'unique renvoi vers un passage le rend orphelin.
            for entry in entries.values():
                entry['routes'] = [r for r in entry['routes'] if r['target'] != 354]
                entry['mode'] = 'fin' if not entry['routes'] else 'suite' if len(entry['routes']) == 1 else 'choix'
        def island(entries):
            # Deux passages qui ne se rejoignent qu'entre eux restent inaccessibles.
            for entry in entries.values():
                entry['routes'] = [r for r in entry['routes'] if r['target'] not in (9, 56)]
                entry['mode'] = 'fin' if not entry['routes'] else 'suite' if len(entry['routes']) == 1 else 'choix'
            entries['9'].update(mode='suite', routes=[{'target': 56, 'label': 'Suite'}])
            entries['56'].update(mode='suite', routes=[{'target': 9, 'label': 'Suite'}])
        for change in (orphan, island):
            with self.subTest(change=change.__name__):
                self.broken(change)

    def test_corrected_references_are_recorded_for_paper_confirmation(self):
        issues = {(i['paragraph'], i['kind']): i for i in self.data['source_issues']}
        for number, target in ((168, 359), (182, 354)):
            issue = issues[(number, 'invalid_reference')]
            self.assertEqual(issue['confirmed_target'], target)
            self.assertFalse(issue['candidate_confirmed'])
            self.assertIn(target, [r['target'] for r in self.data['paragraphs'][str(number)]['routes']])
        for number in (110, 258, 262):
            self.assertEqual(issues[(number, 'broken_reference')]['status'], 'resolved')

    def owner(self, number, paragraphs):
        owner = SimpleNamespace(book_event_catalogue=self.data, current_paragraph=number,
                                paragraphs=paragraphs, visited=[], visited_paragraphs=[],
                                character={'endurance': 10, 'gold': 0, 'inventory': []})
        owner._paragraph_choices = lambda text: []
        owner._reading_link_targets = lambda: CiteController._reading_link_targets(owner)
        owner.combat_available = lambda: False
        owner._cite_combat = lambda: None
        owner.follow_cite_route = owner.visited.append
        return owner

    def test_only_catalogued_routes_present_in_the_pdf_are_links(self):
        routes = [r['target'] for r in self.data['paragraphs']['1']['routes']]
        present = {1: '', 2: '', routes[0]: ''}
        owner = self.owner(1, present)
        self.assertEqual(owner._reading_link_targets(), {routes[0]})
        html = render_links(f'Rendez-vous au 2. Rendez-vous au {routes[0]}. Rendez-vous au {routes[1]}.',
                            owner._reading_link_targets())
        self.assertIn(f'href="paragraph:{routes[0]}"', html)
        self.assertNotIn('href="paragraph:2"', html)
        self.assertNotIn(f'href="paragraph:{routes[1]}"', html)
        for target in (2, routes[1], routes[0]):
            CiteController.follow_link(owner, QUrl(f'paragraph:{target}'))
        self.assertEqual(owner.visited, [routes[0]])

    def test_without_catalogue_entry_text_routes_remain_available(self):
        owner = self.owner(1, {1: 'x', 2: ''})
        owner.book_event_catalogue = {'paragraphs': {}}
        owner._paragraph_choices = lambda text: [{'target': 2, 'label': 'Suite'}]
        self.assertEqual(CiteController._reading_link_targets(owner), {2})

    def test_private_pdf_matches_every_catalogued_route(self):
        candidates = [*ROOT.glob('*.pdf'), *(ROOT / 'donnees/grimoires').glob('*.pdf'),
                      *(ROOT.parent / 'attachments').rglob('*.pdf')]
        path = next((p for p in candidates if pdf_digest(p) == self.data['pdf_sha256']), None)
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        report = audit(self.data, path)
        self.assertTrue(report['pdf_provenance_checked'])
        self.assertEqual(report['routes'], 671)


if __name__ == '__main__':
    unittest.main()
