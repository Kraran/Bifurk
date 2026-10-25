"""Retrait de l’amorce dans scripts/prepare_sounds : fenêtre comptée en trames."""
import array
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from scripts.prepare_sounds import normalize


def write_wav(path, frames, rate, channels):
    samples = array.array('h', [value for frame in frames for value in frame])
    if sys.byteorder != 'little':
        samples.byteswap()
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


def read_frames(path):
    with wave.open(str(path), 'rb') as stream:
        channels = stream.getnchannels()
        samples = array.array('h', stream.readframes(stream.getnframes()))
        rate = stream.getframerate()
    if sys.byteorder != 'little':
        samples.byteswap()
    return rate, channels, [tuple(samples[i:i + channels]) for i in range(0, len(samples), channels)]


class TrimAttackTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'stereo.wav'

    def test_stereo_trim_keeps_ten_ms_and_channel_order(self):
        # 9 kHz : la fenêtre de 5 ms vaut 45 trames, un nombre impair d’échantillons
        # par canal ; l’attaque tombe là où une coupe comptée en échantillons
        # serait décalée d’une demi-trame et intervertirait les canaux.
        rate, attack = 9000, 923
        quiet = [(50, -50)] * attack          # bruit faible, canaux distincts
        loud = [(20000, -10000)] * 900
        write_wav(self.path, quiet + loud, rate, 2)

        normalize(self.path, trim_attack=True)

        out_rate, channels, frames = read_frames(self.path)
        self.assertEqual((out_rate, channels), (rate, 2))
        self.assertTrue(all(len(frame) == 2 for frame in frames))
        self.assertTrue(all(left > 0 > right for left, right in frames),
                        'un canal gauche positif et droit négatif partout : pas d’inversion')
        kept = next(i for i, (left, _) in enumerate(frames) if left > 1000)
        # 10 ms = 90 trames, à une fenêtre (45 trames) près selon l’alignement.
        self.assertGreaterEqual(kept, 90)
        self.assertLessEqual(kept, 135)
        self.assertEqual(len(frames) - kept, len(loud))

    def test_mono_trim_unchanged(self):
        rate, attack = 44100, 4410
        write_wav(self.path, [(0,)] * attack + [(20000,)] * 2000, rate, 1)

        normalize(self.path, trim_attack=True)

        _, channels, frames = read_frames(self.path)
        self.assertEqual(channels, 1)
        kept = next(i for i, (value,) in enumerate(frames) if value)
        self.assertEqual(kept, 450)  # attaque à 4410, fenêtre 4400, deux fenêtres de 220 gardées
        self.assertEqual(max(value for (value,) in frames), 27500)


if __name__ == '__main__':
    unittest.main()
