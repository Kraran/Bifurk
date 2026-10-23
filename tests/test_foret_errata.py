"""Corrections confirmées : préserver le récit extrait et limiter l’édition visée."""
from copy import deepcopy
import unittest
from grimoire_modules.registry import available_modules
from pdf_text_repairs import repair_foret_confirmed_errata, repair_foret_typography
from navigation import destinations


class ForetErrataTests(unittest.TestCase):
    def test_typography_preserves_routes_numbers_and_valid_tests(self):
        data = {51: 'Un Test de Chance. Continuer vers Test, rendez-vous au 397.',
                109: 'Aller à Test. Rendez-vous au 72.',
                188: 'La direction de Test, rendez-vous au 359.',
                100: 'Vous réalisez ŕ et avec terreur ŕ le danger.',
                261: 'Potion Antipoison Ŕ    2 pièces d’Or\nEau Bénite ŕ    3 pièces d’Or\n'
                     'Corde Magique Ŕ    3 pièces d’Or\nBrassard de Force-    3 pièces d’Or',
                400: 'Les marques sur votre coips.',
                2: 'Un Test. Votre coips. Un signe ŕ conserver.'}
        original = deepcopy(data)
        repair_foret_typography(data)
        self.assertIn('Un Test de Chance. Continuer vers l’est', data[51])
        self.assertIn('Aller à l’est', data[109])
        self.assertIn('direction de l’est', data[188])
        self.assertEqual(data[100], 'Vous réalisez — et avec terreur — le danger.')
        self.assertNotIn('Ŕ', data[261])
        self.assertNotIn('ŕ', data[261])
        self.assertIn('Brassard de Force —', data[261])
        self.assertEqual(data[400], 'Les marques sur votre corps.')
        self.assertEqual(data[2], original[2])
        for number in data:
            self.assertEqual([target for _, _, target in destinations(data[number])],
                             [target for _, _, target in destinations(original[number])])
        snapshot = deepcopy(data)
        repair_foret_typography(data)
        self.assertEqual(data, snapshot)

    def test_typography_is_applied_only_by_the_forest_module(self):
        modules = {module.engine: module for module in available_modules()}
        data = {51: 'Continuer vers Test.', 400: 'Votre quête. Votre coips.'}
        original = deepcopy(data)
        modules['sorcier-1982'].repair_paragraphs(data)
        self.assertEqual(data, original)
        modules['foret-1983'].repair_paragraphs(data)
        self.assertIn('vers l’est', data[51])

    def test_victory_colophon_is_removed_without_truncating_story(self):
        data = {400:"Récit final. Votre quête est terminée.\n\nAchevé d’imprimer le 12 septembre 1984\nImprimerie."}
        repair_foret_confirmed_errata(data)
        self.assertEqual(data[400],'Récit final. Votre quête est terminée.')
        before = deepcopy(data)
        repair_foret_confirmed_errata(data)
        self.assertEqual(data,before)

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
