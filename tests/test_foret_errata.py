"""Corrections confirmées : préserver le récit extrait et limiter l’édition visée."""
from copy import deepcopy
import unittest
from grimoire_modules.registry import available_modules
from pdf_text_repairs import repair_foret_confirmed_errata


class ForetErrataTests(unittest.TestCase):
    def test_missing_eel_ending_and_wrong_cave_reference_are_repaired_once(self):
        paragraphs = {186:'Un passage de rivière.',267:'Entrez, rendez-vous\nau 1%. Sinon rendez-vous au 25.',187:'Autre passage.'}
        repair_foret_confirmed_errata(paragraphs)
        self.assertTrue(paragraphs[186].startswith('Un passage de rivière.'))
        self.assertIn('HABILETÉ : 5 — ENDURANCE : 4',paragraphs[186])
        self.assertIn('rendez-vous au 131',paragraphs[186])
        self.assertIn('au 196',paragraphs[267])
        self.assertIn('au 25',paragraphs[267])
        self.assertEqual(paragraphs[187],'Autre passage.')
        snapshot = deepcopy(paragraphs)
        repair_foret_confirmed_errata(paragraphs)
        self.assertEqual(paragraphs,snapshot)

    def test_other_module_does_not_apply_forest_errata(self):
        modules = {module.engine:module for module in available_modules()}
        original = {186:'Une rivière.',267:'Rendez-vous au 1%.'}
        data = deepcopy(original)
        modules['sorcier-1982'].repair_paragraphs(data)
        self.assertEqual(data,original)
        modules['foret-1983'].repair_paragraphs(data)
        self.assertIn('au 196',data[267])

    def test_corrected_or_absent_paragraphs_remain_unchanged(self):
        data = {186:'ANGUILLE — rendez-vous au 131.',267:'Rendez-vous au 196 ou au 25.'}
        original = deepcopy(data)
        repair_foret_confirmed_errata(data)
        self.assertEqual(data,original)
        empty = {}
        repair_foret_confirmed_errata(empty)
        self.assertEqual(empty,{})
