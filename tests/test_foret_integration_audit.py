"""La revue de clôture ne doit ni oublier un passage ni masquer une dérive."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from tools.audit_foret_integration import REVIEW, CATALOGUE, audit, markdown, runtime_inventory


class ForetIntegrationAuditTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads(REVIEW.read_text(encoding='utf-8'))
        self.catalogue = json.loads(CATALOGUE.read_text(encoding='utf-8'))

    def test_complete_review_tracks_fixes_and_completed_adventure(self):
        result = audit(self.review,self.catalogue)
        self.assertEqual(sum(result['classifications'].values()),400)
        self.assertEqual(result['routes'],641)
        self.assertTrue(self.catalogue['mechanics_implementation']['complete_adventure'])
        self.assertTrue(all(f.get('resolution') for f in self.review['findings']))
        self.assertEqual(self.review['paragraphs']['158']['status'],'couvert')
        self.assertEqual(self.review['paragraphs']['242']['status'],'couvert')
        self.assertEqual(self.review['paragraphs']['178']['status'],'couvert')
        self.assertEqual(result['unregistered_runtime_paragraphs'],[])
        self.assertEqual(result['registered_without_runtime'],[])
        report = markdown(self.review,result)
        self.assertIn('| 400 |',report)
        self.assertIn('F01',report)

    def test_missing_or_extra_passage_cannot_pass_as_complete(self):
        for change in ('missing','extra'):
            review = deepcopy(self.review)
            if change=='missing':review['paragraphs'].pop('146')
            else:review['paragraphs']['401']=deepcopy(review['paragraphs']['400'])
            with self.subTest(change=change),self.assertRaises(ValueError):
                audit(review,self.catalogue)

    def test_runtime_drift_requires_revisiting_the_review(self):
        inventory = runtime_inventory()
        inventory[146] = ['option']
        with patch('tools.audit_foret_integration.runtime_inventory',return_value=inventory):
            with self.assertRaisesRegex(ValueError,'146'):
                audit(self.review,self.catalogue)

    def test_wrong_edition_or_source_page_is_rejected(self):
        for change in ('edition','page'):
            review = deepcopy(self.review)
            if change=='edition':review['pdf_sha256']='0'*64
            else:review['paragraphs']['158']['source_page_pdf']=1
            with self.subTest(change=change),self.assertRaises(ValueError):
                audit(review,self.catalogue)

    def test_findings_cannot_disappear_from_their_passages(self):
        self.review['paragraphs']['158']['findings']=[]
        with self.assertRaisesRegex(ValueError,'158'):
            audit(self.review,self.catalogue)

    def test_narrative_or_unsupported_classification_cannot_hide_an_effect(self):
        for status in ('narratif','inconnu'):
            review = deepcopy(self.review)
            review['paragraphs']['158']['status']=status
            with self.subTest(status=status),self.assertRaises(ValueError):
                audit(review,self.catalogue)
