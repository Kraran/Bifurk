"""Cité des Voleurs : réparations OCR ciblées, sans texte du livre au-delà des fragments fautifs."""
import unittest
from copy import deepcopy

from grimoire_modules.registry import available_modules
from navigation import destinations
from pdf_text_repairs import CITE_ROUTE_ERRATA, CITE_TYPOGRAPHY, repair_cite_ocr


def targets(text):
    return [target for _, _, target in destinations(text)]


class CiteErrataTests(unittest.TestCase):
    def sample(self):
        # Récits synthétiques : seuls les fragments mal reconnus sont reproduits.
        return {110: 'Une porte. Ouvrez-la, rendez-vous ai 239.',
                258: 'Un choix. Sinon, rendez-\nvous an 318.',
                262: 'Une ruelle. Partez, rendez-vous »u 375.',
                168: 'Une victoire (rendez-vous au 159). Sinon rendez-vous au 12.',
                182: 'Un tatouage, rendez-vous au 351.',
                5: 'Un quai. Rendez-vous au 6.'}

    def test_unreadable_route_words_become_links(self):
        data = self.sample()
        self.assertEqual(targets(data[110]), [])
        repair_cite_ocr(data)
        self.assertEqual(targets(data[110]), [239])
        self.assertEqual(targets(data[258]), [318])
        self.assertEqual(targets(data[262]), [375])

    def test_misread_targets_are_corrected_once_and_only_there(self):
        data = self.sample()
        repair_cite_ocr(data)
        self.assertEqual(targets(data[168]), [359, 12])
        self.assertEqual(targets(data[182]), [354])
        self.assertEqual(data[5], 'Un quai. Rendez-vous au 6.')
        # Le même fragment ailleurs n'est jamais corrigé.
        other = {200: 'Une victoire (rendez-vous au 159).'}
        repair_cite_ocr(other)
        self.assertEqual(targets(other[200]), [159])
        self.assertEqual(set(CITE_ROUTE_ERRATA), {168, 182})

    def test_repair_is_idempotent_and_keeps_missing_paragraphs_absent(self):
        data = self.sample()
        repair_cite_ocr(data)
        snapshot = deepcopy(data)
        repair_cite_ocr(data)
        self.assertEqual(data, snapshot)
        empty = {}
        repair_cite_ocr(empty)
        self.assertEqual(empty, {})

    def test_typography_replaces_characters_without_changing_routes(self):
        data = {7: 'Vous attendez ŕ immobile ŕ puis HABiLETÉ. Rendez-vous au 8.'}
        repair_cite_ocr(data)
        self.assertEqual(data[7], 'Vous attendez — immobile — puis HABILETÉ. Rendez-vous au 8.')
        for number, fixes in CITE_TYPOGRAPHY.items():
            for old, new in fixes:
                with self.subTest(number=number, old=old):
                    self.assertNotEqual(old, new)
                    # Une coquille ne peut ni créer ni supprimer un renvoi.
                    self.assertEqual(targets(old), targets(new))

    def test_repair_is_applied_only_by_the_city_module(self):
        modules = {module.engine: module for module in available_modules()}
        for engine in ('sorcier-1982', 'foret-1983'):
            data = self.sample()
            modules[engine].repair_paragraphs(data)
            self.assertEqual(targets(data[110]), [], engine)
        data = self.sample()
        modules['cite-1983'].repair_paragraphs(data)
        self.assertEqual(targets(data[110]), [239])

    def test_first_paragraph_fragments_follow_the_paper_copy(self):
        # Fragments seuls, relus sur l'exemplaire papier ; les renvois restent ceux du catalogue.
        data = {1: 'des collines; sans, le- groupe, affronter du garde. Rendez-vous au 202, '
                   'rendez-vous au 33, rendez-vous au 49.'}
        repair_cite_ocr(data)
        self.assertEqual(data[1], 'des collines ; sans, le groupe, affronter un garde. Rendez-vous au 202, '
                                  'rendez-vous au 33, rendez-vous au 49.')
        self.assertEqual(targets(data[1]), [202, 33, 49])


if __name__ == '__main__':
    unittest.main()
