"""Ambiance selon le paragraphe : catalogues par zones avec exceptions (Sorcier, Forêt, Cité).

Le catalogue est validé (chaque paragraphe dans une seule zone, scènes connues,
statut proposé ou vérifié) ; le jeu passe à la scène du paragraphe, garde la scène
précédente pour une exception « garder », et revient à la boucle du livre sans
catalogue, hors paragraphe ou quand Réglages demande la boucle du livre.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_ambiances_paragraphe
"""
import json
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QDialog

import main
from ambience_map import KEEP, AmbienceMap, parse_paragraphs
from grimoire_modules.registry import available_modules
from sound_effects import SCENES, SoundBank
from tests.test_sound_feedback import FakeEffect


def sorcier():
    return next(module for module in available_modules() if module.engine == 'sorcier-1982')


def catalogue(**changes):
    data = {'schema_version': 1,
            'zones': [{'label': 'Galeries', 'scene': 'caverne', 'status': 'proposé', 'paragraphs': ['1-6']},
                      {'label': 'Rivière', 'scene': 'riviere', 'status': 'vérifié', 'paragraphs': [7, '8-10']}],
            'exceptions': [{'label': 'Taverne', 'scene': 'taverne', 'status': 'proposé', 'paragraphs': [3]},
                           {'label': 'Garder', 'scene': None, 'status': 'proposé', 'paragraphs': [9]}]}
    data.update(changes)
    return data


class CatalogueTests(unittest.TestCase):
    def test_zones_and_exceptions_resolve_every_paragraph(self):
        ambience = AmbienceMap(catalogue(), 10, SCENES)
        self.assertEqual([ambience.scene_for(n) for n in range(1, 11)],
                         ['caverne', 'caverne', 'taverne', 'caverne', 'caverne', 'caverne',
                          'riviere', 'riviere', KEEP, 'riviere'])
        self.assertIsNone(ambience.scene_for(11))
        self.assertEqual(ambience.zone_for(3)['label'], 'Galeries')

    def test_invalid_catalogues_are_refused(self):
        zones = catalogue()['zones']
        bad = {
            'paragraphe sans zone': catalogue(zones=[zones[0]]),
            'deux zones': catalogue(zones=[zones[0], {**zones[1], 'paragraphs': ['6-10']}]),
            'scène inconnue': catalogue(zones=[{**zones[0], 'scene': 'lune'}, zones[1]]),
            'garder dans une zone': catalogue(zones=[{**zones[0], 'scene': None}, zones[1]]),
            'statut inconnu': catalogue(zones=[{**zones[0], 'status': 'peut-être'}, zones[1]]),
            'deux exceptions': catalogue(exceptions=[{'label': 'A', 'scene': 'foyer', 'status': 'proposé',
                                                      'paragraphs': [2]}] * 2),
            'schéma': catalogue(schema_version=2),
        }
        for name, data in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                AmbienceMap(data, 10, SCENES)
        for spec in ([], [0], ['3-1'], ['2-12'], [1, 1], ['a-b'], [2.5]):
            with self.subTest(spec), self.assertRaises(ValueError):
                parse_paragraphs(spec, 10)

    def test_sorcier_catalogue_is_valid_and_bound_to_its_edition(self):
        module = sorcier()
        ambience = AmbienceMap.from_module(module)
        scenes = {ambience.scene_for(n) for n in range(1, module.paragraph_count + 1)}
        self.assertLessEqual(scenes - {KEEP}, set(SCENES))
        self.assertEqual(ambience.scene_for(1), 'souterrain')     # Entrée humide de la caverne.
        self.assertEqual(ambience.scene_for(218), 'riviere')      # Berge sud de la rivière.
        self.assertEqual(ambience.scene_for(227), 'taverne')      # Partie de cartes des Nains.
        self.assertEqual(ambience.scene_for(279), 'crypte')       # Le Vampire.
        self.assertEqual(ambience.scene_for(106), 'vent')         # Caverne du Dragon.
        self.assertIs(ambience.scene_for(161), KEEP)              # Monstre errant.
        data = json.loads(dict(module.catalogue_paths)['ambiences'].read_text(encoding='utf-8'))
        self.assertEqual(data['pdf_sha256'], module.pdf_sha256)
        self.assertTrue(all(entry['status'] in ('proposé', 'vérifié')
                            for entry in [*data['zones'], *data['exceptions']]))
        self.assertTrue(all(entry['status'] == 'vérifié'
                            for entry in [*data['zones'], *data['exceptions']]))

    def test_foret_and_cite_catalogues_cover_their_places(self):
        expected = {
            'foret-1983': {1: 'foyer', 285: 'foret_nuit', 142: 'riviere', 109: 'vent',
                           196: 'caverne', 69: 'souterrain', 227: 'crypte', 199: 'marais',
                           204: 'rue', 97: 'foret'},
            'cite-1983': {74: 'rue', 62: 'taverne', 87: 'port', 148: 'marche', 321: 'souterrain',
                          337: 'crypte', 53: 'foyer', 31: 'riviere', 358: 'vent', 370: 'foret'},
        }
        for engine, scenes in expected.items():
            module = next(m for m in available_modules() if m.engine == engine)
            ambience = AmbienceMap.from_module(module)
            with self.subTest(engine):
                self.assertEqual({n: ambience.scene_for(n) for n in scenes}, scenes)
                data = json.loads(dict(module.catalogue_paths)['ambiences'].read_text(encoding='utf-8'))
                self.assertEqual(data['pdf_sha256'], module.pdf_sha256)


class FollowParagraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patcher = patch.object(SoundBank, '_backend', return_value=FakeEffect)
        self.patcher.start()
        self.w = main.MainWindow()
        self.w.sounds.set_ambient_enabled(True)
        self.w.book_module = sorcier()
        self.w._load_ambience_map()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()
        self.patcher.stop()

    def test_scene_follows_the_paragraph_and_keeps_it_for_a_wandering_monster(self):
        w, sounds = self.w, self.w.sounds
        w._ambience_follow_paragraph(218)
        self.assertEqual((sounds.scene, sounds.ambient), ('riviere', 'scene_riviere'))
        w._ambience_follow_paragraph(161)
        self.assertEqual(sounds.scene, 'riviere')
        w._ambience_follow_paragraph(2)
        self.assertEqual((sounds.scene, sounds.ambient), ('caverne', 'ambient'))
        w._ambience_follow_paragraph(None)        # Page de titre : boucle du livre.
        self.assertIsNone(sounds.scene)
        # Après un chargement sur un monstre errant : la dernière scène visitée revient.
        w.visited_paragraphs = [1, 227, 161]
        w._ambience_follow_paragraph(161)
        self.assertEqual(sounds.scene, 'taverne')

    def test_book_mode_and_missing_catalogue_play_the_book_loop(self):
        w, sounds = self.w, self.w.sounds
        w.preferences['ambient_mode'] = 'book'
        w._ambience_follow_paragraph(218)
        self.assertIsNone(sounds.scene)
        w.preferences['ambient_mode'] = 'paragraph'
        w._ambience_follow_paragraph(218)
        self.assertEqual(sounds.scene, 'riviere')
        w.book_module = None                      # Accueil : aucun catalogue.
        w._load_ambience_map()
        self.assertIsNone(w.ambience_map)
        w._ambience_follow_paragraph(218)
        self.assertIsNone(sounds.scene)

    def test_moving_to_a_paragraph_plays_its_scene(self):
        w = self.w
        w.paragraphs = {n: f'Paragraphe {n}.' for n in range(1, 401)}
        w.go_to(1)
        self.assertEqual(w.sounds.scene, 'souterrain')
        w.go_to(218)
        self.assertEqual(w.sounds.scene, 'riviere')

    def test_settings_switch_between_paragraph_scenes_and_the_book_loop(self):
        w = self.w
        w._ambience_follow_paragraph(218)
        seen = {}

        def fake_exec():
            mode = w.findChild(QComboBox, 'ambientMode')
            seen['items'] = [mode.itemData(i) for i in range(mode.count())]
            mode.setCurrentIndex(mode.findData('book'))
            seen['during'] = w.sounds.scene
            return 0

        w.current_paragraph = 218
        with patch.object(main.MainWindow, '_save_preferences'), \
                patch.object(QDialog, 'exec', side_effect=fake_exec):
            w.show_ambience()
        self.assertEqual(seen, {'items': ['paragraph', 'book'], 'during': None})
        self.assertEqual(w.preferences['ambient_mode'], 'book')
        self.assertIsNone(w.sounds.scene)   # Toujours la boucle du livre après fermeture.


if __name__ == '__main__':
    unittest.main()
