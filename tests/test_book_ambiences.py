"""Boucles d’ambiance propres aux livres : ville (Cité) et forêt (Forêt de la Malédiction).

Même format, même réglage et même volume de lecture que la caverne qu’elles remplacent ;
niveau RMS commun fixé par scripts/prepare_book_ambiences.py, raccord sans couture,
source CC0 créditée avec son empreinte.
"""
import json
import math
import unittest
import wave
from unittest.mock import patch

import main
from sound_effects import AMBIENT_LABELS, AMBIENT_TRACKS, SoundBank
from tests.test_sound_feedback import FakeEffect

LOOPS = {'ambient_cite': ('cite-1983', 'ville'), 'ambient_foret': ('foret-1983', 'forêt')}
TARGET_RMS_DBFS = -31.7


def pcm(name):
    """Lire un WAV livré : paramètres et échantillons 16 bits."""
    with wave.open(str(main.ASSET_DIR/'sounds'/f'{name}.wav')) as stream:
        params = stream.getparams()
        data = stream.readframes(stream.getnframes())
    return params, memoryview(data).cast('h')


def rms_dbfs(samples):
    return 20*math.log10(math.sqrt(sum(v*v for v in samples)/len(samples))/32768)


class BookAmbienceAssetTests(unittest.TestCase):
    def test_loops_match_the_cave_format_and_the_common_level(self):
        cave_params, _ = pcm('ambient')
        for name in LOOPS:
            with self.subTest(name):
                params, loop = pcm(name)
                self.assertEqual((params.nchannels, params.sampwidth, params.framerate),
                                 (cave_params.nchannels, cave_params.sampwidth, cave_params.framerate))
                self.assertEqual((params.nchannels, params.sampwidth, params.framerate), (1, 2, 22050))
                self.assertTrue(30 <= params.nframes/params.framerate <= 60)
                self.assertLess((main.ASSET_DIR/f'sounds/{name}.wav').stat().st_size, 2_500_000)
                self.assertLess(abs(rms_dbfs(loop) - TARGET_RMS_DBFS), .3)
                self.assertLessEqual(max(map(abs, loop)), 27500)

    def test_loops_wrap_without_a_seam(self):
        for name in LOOPS:
            with self.subTest(name):
                params, loop = pcm(name)
                # Le saut de fin vers début reste dans le grain du signal.
                steps = sorted(abs(loop[i+1]-loop[i]) for i in range(0, len(loop)-1, 7))
                self.assertLess(abs(loop[0]-loop[-1]), steps[int(len(steps)*.99)])
                head, tail = loop[:params.framerate], loop[-params.framerate:]
                self.assertLess(abs(rms_dbfs(head) - rms_dbfs(tail)), 4)

    def test_sources_are_cc0_described_and_credited(self):
        manifest = json.loads((main.ASSET_DIR/'sounds/sources.json').read_text())['book_ambiences']
        self.assertEqual(set(manifest), set(LOOPS))
        credits = {path: (main.ASSET_DIR/path).read_text(encoding='utf-8')
                   for path in ('sounds/CREDITS.md', 'ABOUT-CREDITS.md')}
        for name, (book, _) in LOOPS.items():
            with self.subTest(name):
                source = manifest[name]
                self.assertEqual((source['license'], source['book']), ('CC0-1.0', book))
                self.assertEqual(source['rms_dbfs'], TARGET_RMS_DBFS)
                self.assertTrue(source['page'].startswith('https://bigsoundbank.com/'))
                self.assertTrue(source['download'].startswith('https://bigsoundbank.com/UPLOAD/'))
                self.assertRegex(source['sha256'], '^[0-9a-f]{64}$')
                for text in credits.values():
                    self.assertIn(f'{name}.wav', text)
                    self.assertIn(source['page'], text)


class BookAmbienceSwitchTests(unittest.TestCase):
    def test_tracks_and_labels(self):
        self.assertEqual(AMBIENT_TRACKS, {book: name for name, (book, _) in LOOPS.items()})
        self.assertEqual(AMBIENT_LABELS, {'ambient': 'caverne', **{n: label for n, (_, label) in LOOPS.items()}})

    def test_one_switch_swaps_the_loop_with_the_open_book(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(main.ASSET_DIR/'sounds', ambient_enabled=True)
            cave, city, forest = (bank.effects[n] for n in ('ambient', 'ambient_cite', 'ambient_foret'))
            for loop in (city, forest):
                self.assertEqual((loop.volume, loop.loops), (cave.volume, cave.loops))
            self.assertEqual((cave.play_count, city.play_count, forest.play_count), (1, 0, 0))
            for engine in ('sorcier-1982', None):
                bank.set_ambient_track(engine)
                self.assertEqual((bank.ambient, bank.ambient_label(), cave.stop_count), ('ambient', 'caverne', 0))
            bank.set_ambient_track('foret-1983')
            self.assertEqual((bank.ambient_label(), cave.stop_count, forest.play_count), ('forêt', 1, 1))
            bank.set_ambient_track('cite-1983')
            self.assertEqual((bank.ambient_label(), forest.stop_count, city.play_count), ('ville', 1, 1))
            bank.set_enabled(False)  # Couper les effets ne coupe pas l’ambiance.
            self.assertEqual(city.stop_count, 0)
            bank.play('ambient')  # La caverne ne rejoue pas pendant la Cité.
            bank.play('ambient_foret')
            self.assertEqual((cave.play_count, forest.play_count), (1, 1))
            bank.set_ambient_enabled(False)
            self.assertEqual(city.stop_count, 1)
            bank.set_ambient_track('foret-1983')
            self.assertEqual((bank.ambient, forest.play_count), ('ambient_foret', 1))
            bank.set_ambient_enabled(True)
            self.assertEqual((forest.play_count, city.play_count), (2, 1))
            bank.set_ambient_track('sorcier-1982')
            self.assertEqual((bank.ambient, forest.stop_count, cave.play_count), ('ambient', 2, 2))


if __name__ == '__main__':
    unittest.main()
