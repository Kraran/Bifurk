"""Scènes d'ambiance : boucles et sons ponctuels partagés entre les livres.

Fichiers préparés par scripts/prepare_book_ambiences.py (sections scene_ambiences et
scene_spots de sources.json), sources CC0 créditées ; SoundBank passe d'une scène à
l'autre en fondu et joue les sons ponctuels au hasard, sous l'interrupteur de l'ambiance.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_scenes_ambiance
"""
import json
import random
import unittest
import wave
from unittest.mock import patch

import numpy as np
from PySide6.QtWidgets import QApplication, QComboBox, QDialog

import main
from sound_effects import (AMBIENT_LABELS, SCENE_LOOPS, SCENES, SPOT_SOUNDS, SPOT_VOLUME,
                           SoundBank)
from tests.test_book_ambiences import pcm as decoded_pcm
from tests.test_sound_feedback import FakeEffect, plays

SOUNDS = main.ASSET_DIR/'sounds'
MANIFEST = json.loads((SOUNDS/'sources.json').read_text(encoding='utf-8'))


def pcm(name):
    """Boucle décodée telle que le jeu l'entend, en tableau NumPy (calculs rapides)."""
    params, samples = decoded_pcm(name)
    return params, np.frombuffer(samples, dtype=np.int16).astype(float)


def rms_dbfs(samples):
    return 20*np.log10(np.sqrt(np.mean(samples**2))/32768)


def spot_files(name):
    return sorted(SOUNDS.glob(f'{name}.wav')) + sorted(SOUNDS.glob(f'{name}_[2-9].wav'))


class SceneAssetTests(unittest.TestCase):
    def test_catalogue_points_to_existing_loops_and_spots(self):
        self.assertGreaterEqual(len(SCENES), 12)
        for key, scene in SCENES.items():
            with self.subTest(key):
                self.assertTrue((SOUNDS/f"{scene['loop']}.ogg").is_file())
                self.assertEqual(scene['label'], scene['label'].strip())
                if 'spots' in scene:
                    self.assertTrue(spot_files(scene['spots']))
                    low, high = scene['every']
                    self.assertTrue(2 <= low < high <= 60)
        self.assertEqual(set(SCENE_LOOPS), set(MANIFEST['scene_ambiences']))
        self.assertEqual(set(SPOT_SOUNDS), set(MANIFEST['scene_spots']))

    def test_loops_are_mono_22k_short_light_and_level_capped(self):
        for name in SCENE_LOOPS:
            with self.subTest(name):
                params, loop = pcm(name)
                self.assertEqual((params.nchannels, params.sampwidth, params.framerate), (1, 2, 22050))
                self.assertTrue(30 <= params.nframes/params.framerate <= 60)
                self.assertLess((SOUNDS/f'{name}.ogg').stat().st_size, 400_000)
                # Niveau visé, ou moins si le plafond de crête l'impose (feu qui crépite).
                self.assertLess(rms_dbfs(loop), MANIFEST['scene_ambiences'][name]['rms_dbfs'] + .3)
                self.assertGreater(rms_dbfs(loop), MANIFEST['scene_ambiences'][name]['rms_dbfs'] - 3)
                self.assertLessEqual(abs(loop).max(), 27500)

    def test_loops_wrap_without_a_seam(self):
        for name in SCENE_LOOPS:
            with self.subTest(name):
                params, loop = pcm(name)
                steps = abs(np.diff(loop))[::7]
                self.assertLess(abs(loop[0]-loop[-1]), np.percentile(steps, 99))
                head, tail = loop[:params.framerate], loop[-params.framerate:]
                # Fond comparé par la médiane : une goutte isolée ne compte pas.
                self.assertLess(abs(20*np.log10(np.median(abs(head))/np.median(abs(tail)))), 4)

    def test_spots_are_short_mono_wav_with_quiet_edges(self):
        for name in SPOT_SOUNDS:
            files = spot_files(name)
            self.assertEqual(len(files), len(MANIFEST['scene_spots'][name]['cuts']))
            for path in files:
                with self.subTest(path.name), wave.open(str(path)) as stream:
                    self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()),
                                     (1, 2, 22050))
                    self.assertLessEqual(stream.getnframes(), 3*22050)
                    samples = np.frombuffer(stream.readframes(stream.getnframes()), '<i2').astype(float)
                self.assertLessEqual(abs(samples).max(), 27500)
                self.assertLess(abs(samples[:3]).max(), 2000)   # Pas de clic d'attaque.
                self.assertLess(abs(samples[-3:]).max(), 200)   # Sortie en fondu.

    def test_scene_assets_stay_within_the_budget(self):
        files = [SOUNDS/f'{name}.ogg' for name in SCENE_LOOPS]
        files += [path for name in SPOT_SOUNDS for path in spot_files(name)]
        self.assertLess(sum(path.stat().st_size for path in files), 5_000_000)

    def test_sources_are_cc0_hashed_and_credited(self):
        sources = MANIFEST['scene_sources']
        used = {spec['archive'] for spec in MANIFEST['scene_ambiences'].values()}
        used |= {layer['archive'] for spec in MANIFEST['scene_ambiences'].values()
                 for layer in spec.get('layers', ())}
        used |= {cut['archive'] for spec in MANIFEST['scene_spots'].values() for cut in spec['cuts']}
        self.assertEqual(used, set(sources))
        credits = {path: (main.ASSET_DIR/path).read_text(encoding='utf-8')
                   for path in ('sounds/CREDITS.md', 'ABOUT-CREDITS.md')}
        licences = (main.ASSET_DIR.parent/'LICENCES-ET-REMERCIEMENTS.txt').read_text(encoding='utf-8')
        for archive, source in sources.items():
            with self.subTest(archive):
                self.assertEqual(source['license'], 'CC0-1.0')
                self.assertRegex(source['sha256'], '^[0-9a-f]{64}$')
                self.assertTrue(source['page'].startswith('https://bigsoundbank.com/'))
                for text in (*credits.values(), licences):
                    self.assertIn(source['page'], text)
        for name in (*SCENE_LOOPS, *SPOT_SOUNDS):
            for path, text in credits.items():
                self.assertIn(name, text, path)


class SceneSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def bank(self, **options):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            return SoundBank(SOUNDS, **options)

    def test_scene_replaces_the_book_loop_then_gives_it_back(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(SOUNDS, ambient_enabled=True)
            bank.set_ambient_track('cite-1983')
            city, port = bank.effects['ambient_cite'], bank.effects['scene_port']
            self.assertEqual((port.volume, port.loops), (city.volume, city.loops))
            bank.set_scene('port')
            self.assertEqual((bank.ambient, bank.ambient_label()), ('scene_port', 'port'))
            self.assertEqual((city.stop_count, port.play_count), (1, 1))
            bank.set_ambient_track('foret-1983')  # La scène garde sa boucle.
            self.assertEqual((bank.ambient, bank.book_ambient), ('scene_port', 'ambient_foret'))
            bank.set_scene(None)
            self.assertEqual((bank.ambient, bank.ambient_label(), port.stop_count), ('ambient_foret', 'forêt', 1))
            bank.set_scene('foret')  # Scène dont la boucle est déjà celle du livre : rien ne bouge.
            self.assertEqual(bank.effects['ambient_foret'].play_count, 1)
            with self.assertRaises(ValueError):
                bank.set_scene('lune')

    def test_spots_follow_the_ambient_switch_and_their_scene_only(self):
        state = random.getstate()
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(SOUNDS)
            self.assertEqual(bank._base_volume['spot_goutte'], SPOT_VOLUME)
            bank.set_scene('souterrain')
            self.assertFalse(bank._spot_timer.isActive())   # Ambiance coupée : rien de prévu.
            bank._spot_tick()
            self.assertEqual(plays(bank, 'spot_goutte'), 0)
            bank.set_ambient_enabled(True)
            self.assertTrue(bank._spot_timer.isActive())
            self.assertTrue(4000 <= bank._spot_timer.remainingTime() <= 10000)
            bank._spot_tick()
            self.assertEqual(plays(bank, 'spot_goutte'), 1)
            bank.set_enabled(False)  # Couper les effets ne coupe pas les sons de la scène.
            bank._spot_tick()
            self.assertEqual(plays(bank, 'spot_goutte'), 2)
            bank.play('spot_hibou')  # Hibou hors de sa scène : refusé.
            self.assertEqual(plays(bank, 'spot_hibou'), 0)
            bank.set_scene('riviere')  # Sans son ponctuel.
            self.assertFalse(bank._spot_timer.isActive())
            bank.set_scene('foret_nuit')
            self.assertTrue(bank._spot_timer.isActive())
            bank.set_ambient_enabled(False)
            self.assertFalse(bank._spot_timer.isActive())
        self.assertEqual(random.getstate(), state)  # Le hasard de la partie n'est pas touché.

    def test_every_scene_can_be_played(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(SOUNDS, ambient_enabled=True)
            for key, scene in SCENES.items():
                with self.subTest(key):
                    bank.set_scene(key)
                    self.assertEqual(bank.ambient, scene['loop'])
                    self.assertTrue(bank.effects[scene['loop']].isPlaying())
            bank.set_scene(None)
            self.assertEqual(bank.ambient, 'ambient')
            self.assertEqual(set(AMBIENT_LABELS) & set(SCENE_LOOPS), set())


class ScenePreviewTests(unittest.TestCase):
    """Réglages → Ambiance : écoute d'essai d'une scène, rendue à la fermeture."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_plays_a_scene_and_gives_the_previous_one_back(self):
        seen = {}

        def fake_exec():
            combo = main_window.findChild(QComboBox, 'scenePreview')
            seen['items'] = [combo.itemData(i) for i in range(combo.count())]
            seen['enabled'] = combo.isEnabled()
            combo.setCurrentIndex(combo.findData('taverne'))
            seen['during'] = (main_window.sounds.scene, main_window.sounds.ambient)
            return 0

        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            main_window = main.MainWindow()
            try:
                main_window.sounds.set_ambient_enabled(True)
                main_window.sounds.set_scene('port')
                with patch.object(QDialog, 'exec', side_effect=fake_exec):
                    main_window.show_ambience()
                self.assertEqual(seen['items'], [None, *SCENES])
                self.assertTrue(seen['enabled'])
                self.assertEqual(seen['during'], ('taverne', 'scene_taverne'))
                self.assertEqual(main_window.sounds.scene, 'port')
            finally:
                main_window.close()
                main_window.deleteLater()


if __name__ == '__main__':
    unittest.main()
