"""Annonces des livres : intégrité des WAV, priorité et respect de la coupure du son."""
import hashlib
import json
import unittest
import wave
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main import ASSET_DIR
from sound_effects import SoundBank, BOOK_SOUNDS
from tests.test_sound_feedback import FakeEffect


class BookSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_prepared_assets_are_verified_pcm_with_no_clipped_samples(self):
        manifest = json.loads((ASSET_DIR/'sounds/book_sounds.json').read_text(encoding='utf-8'))
        import array
        for name in BOOK_SOUNDS.values():
            path = ASSET_DIR/'sounds'/f'{name}.wav'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             manifest['sounds'][name]['output_sha256'])
            with wave.open(str(path)) as stream:
                self.assertEqual((stream.getnchannels(),stream.getsampwidth(),stream.getframerate()), (1,2,22050))
                samples = array.array('h', stream.readframes(stream.getnframes()))
                self.assertGreater(len(samples), 22050)
                self.assertLess(max(map(abs, samples)), 32767)
                self.assertEqual(samples[0], 0)
                self.assertEqual(samples[-1], 0)

    def test_new_announcement_stops_previous_and_mute_prevents_late_play(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR/'sounds')
            bank.play_book_intro('sorcier-1982')
            sorcier, foret = bank.effects['book_sorcier'], bank.effects['book_foret']
            self.assertEqual(sorcier.play_count,1)
            self.assertEqual(sorcier.volume, .80)
            stops = sorcier.stop_count
            bank.play_book_intro('foret-1983')
            self.assertGreater(sorcier.stop_count, stops)
            self.assertEqual(foret.play_count, 1)
            foret.state = FakeEffect.Loading
            bank.play_book_intro('foret-1983')
            self.assertIn('book_foret',bank.pending)
            bank.set_enabled(False)
            foret.state = FakeEffect.Ready
            foret.statusChanged.emit()
            self.assertEqual(foret.play_count, 1)
            self.assertNotIn('book_foret',bank.pending)
            bank.play_book_intro('sorcier-1982')
            self.assertEqual(sorcier.play_count, 1)
            bank.set_enabled(True)
            bank.play_book_intro(None)
            self.assertEqual(foret.play_count, 1)
            self.assertEqual(sorcier.play_count,1)
