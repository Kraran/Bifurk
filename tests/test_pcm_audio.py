"""Mélange PCM, chevauchement et lecture des assets sans sortie native.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import array
import logging
import sys
import unittest
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWidgets import QApplication

from pcm_audio import Mixer, PcmEffect
from sound_effects import EFFECT_LABELS


def decode(data):
    """Décoder le PCM little endian en entiers signés pour comparer les échantillons attendus."""
    samples = array.array('h', data)
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tolist()


class PcmAudioTests(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.parent = QObject()
        self.parent.logger = logging.getLogger('pcm-test')
        self.parent._pcm_mixer = Mixer(self.parent)
        self.mixer = self.parent._pcm_mixer

    def effect(self, samples):
        """Préparer une voix chargée en mémoire, sans fichier ni sortie audio native."""
        effect = PcmEffect(self.parent)
        effect.samples = array.array('h', samples)
        effect._status = effect.Ready
        effect.play()
        return effect

    def test_idle_silence_then_immediate_attack_and_replay(self):
        self.assertEqual(self.mixer.readData(400), bytes(400))
        effect = self.effect([12000, -10000])
        self.assertEqual(decode(self.mixer.readData(12)),
                         [12000, 12000, -10000, -10000, 0, 0])
        self.assertFalse(effect.isPlaying())
        effect.play()
        self.assertEqual(decode(self.mixer.readData(4)), [12000, 12000])

    def test_overlap_clips_safely_and_stopping_one_preserves_ambient(self):
        ambient = self.effect([1000])
        ambient.setLoopCount(-2)
        effect = self.effect([32000, -32000])
        self.assertEqual(decode(self.mixer.readData(8)),
                         [32767, 32767, -31000, -31000])
        effect.stop()
        self.assertEqual(decode(self.mixer.readData(8)), [1000] * 4)
        self.assertTrue(ambient.isPlaying())

    def test_every_shipped_asset_produces_nonzero_pcm(self):
        folder = Path(__file__).resolve().parents[1] / 'assets/sounds'
        for name in [*EFFECT_LABELS, 'ambient', 'ambient_cite']:
            with self.subTest(name=name):
                effect = PcmEffect(self.parent)
                effect.setSource(QUrl.fromLocalFile(str(folder / f'{name}.wav')))
                self.assertEqual(effect.status(), effect.Ready)
                effect.play()
                self.assertTrue(any(decode(self.mixer.readData(44100 * 4))))
                effect.stop()

    def test_bad_asset_reports_error_instead_of_playing(self):
        effect = PcmEffect(self.parent)
        with self.assertLogs('pcm-test', level='ERROR'):
            effect.setSource(QUrl.fromLocalFile('/missing/audio.wav'))
        effect.play()
        self.assertEqual(effect.status(), effect.Error)
        self.assertFalse(effect.isPlaying())
