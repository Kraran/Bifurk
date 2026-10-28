"""Moteur audio : mélange NumPy, fondus, canaux de volume, ambiances décodées à la demande.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_moteur_audio
"""
import logging
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

import main
import sound_effects
from pcm_audio import Mixer, PcmEffect
from sound_effects import SoundBank


def frames(mixer, count):
    """Lire count trames et rendre le canal gauche."""
    return np.frombuffer(mixer.readData(count * 4), dtype='<i2')[::2]


def wait(app, condition, timeout=5.0):
    done = threading.Event()
    QTimer.singleShot(int(timeout * 1000), done.set)
    while not condition() and not done.is_set():
        app.processEvents()
    return condition()


class VoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QObject()
        self.parent.logger = logging.getLogger('moteur-test')
        self.mixer = self.parent._pcm_mixer = Mixer(self.parent)

    def voice(self, value=10000, length=Mixer.RATE, loops=-2):
        effect = PcmEffect(self.parent)
        effect.samples = np.full(length, value, dtype=np.int16)
        effect._status = effect.Ready
        effect.setLoopCount(loops)
        return effect

    def test_fade_in_rises_from_silence_then_holds(self):
        effect = self.voice()
        effect.fade_in(100)                      # 4 410 trames.
        first = frames(self.mixer, 4410)
        self.assertLess(first[0], 10)
        self.assertTrue(np.all(np.diff(first.astype(int)) >= 0))
        self.assertEqual(first[-1], 10000)
        self.assertTrue(np.all(frames(self.mixer, 100) == 10000))

    def test_fade_out_reaches_silence_and_stops_the_voice(self):
        effect = self.voice()
        effect.play()
        effect.fade_out(50)
        out = frames(self.mixer, 2205)
        self.assertTrue(np.all(np.diff(out.astype(int)) <= 0))
        self.assertFalse(effect.isPlaying())
        self.assertTrue(np.all(frames(self.mixer, 10) == 0))

    def test_fading_back_in_does_not_restart_the_loop(self):
        effect = self.voice()
        effect.play()
        frames(self.mixer, 1000)
        effect.fade_out(1000)
        frames(self.mixer, 100)
        effect.fade_in(10)
        self.assertTrue(effect.isPlaying())
        self.assertEqual(effect.position, 1100)

    def test_channels_scale_effects_and_ambience_separately(self):
        effect, ambience = self.voice(8000), self.voice(4000)
        ambience.channel = 'ambient'
        effect.play(), ambience.play()
        self.mixer.channels.update(effects=.5, ambient=0.0)
        self.assertTrue(np.all(frames(self.mixer, 10) == 4000))

    def test_deferred_source_is_decoded_on_demand_and_can_be_released(self):
        effect = PcmEffect(self.parent)
        effect.defer_source(main.QUrl.fromLocalFile(str(main.ASSET_DIR / 'sounds/ambient_cite.ogg')))
        self.assertEqual((effect.status(), len(effect.samples)), (effect.Unloaded, 0))
        effect.load()
        self.assertTrue(wait(self.app, lambda: effect.status() == effect.Ready))
        self.assertEqual(len(effect.samples), 45 * Mixer.RATE)
        self.assertTrue(effect.release())
        self.assertEqual((effect.status(), len(effect.samples)), (effect.Unloaded, 0))

    def test_mixing_four_voices_is_fast_enough(self):
        for value in (1000, 2000, 3000, 4000):
            self.voice(value, length=Mixer.RATE * 45).play()
        start = time.perf_counter()
        for _ in range(50):
            self.mixer.readData(8192)            # 50 blocs ≈ 2,3 s de son.
        self.assertLess(time.perf_counter() - start, .5)


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def bank(self):
        with patch.object(SoundBank, '_backend', return_value=PcmEffect):
            bank = SoundBank(main.ASSET_DIR / 'sounds', ambient_enabled=False)
        patcher = patch.object(SoundBank, '_backend', return_value=PcmEffect)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: bank._pcm_sink.stop())
        return bank

    def test_ambiences_wait_until_asked_and_crossfade(self):
        bank = self.bank()
        cave, forest = bank.effects['ambient'], bank.effects['ambient_foret']
        self.assertEqual({bank.effects[n].status() for n in sound_effects.AMBIENT_LABELS}, {PcmEffect.Unloaded})
        self.assertEqual(bank.effects['page'].status(), PcmEffect.Ready)
        bank.set_ambient_enabled(True)
        self.assertTrue(wait(self.app, cave.isPlaying))
        self.assertEqual(cave.channel, 'ambient')
        mixer = bank._pcm_mixer
        blocks = int(sound_effects.AMBIENT_FADE_MS / 1000 * Mixer.RATE / 2048) + 2
        for _ in range(blocks):                   # Fin du fondu d'entrée de la caverne.
            mixer.readData(2048 * 4)
        self.assertEqual(cave.gain, 1.0)
        bank.set_ambient_track('foret-1983')
        self.assertTrue(cave.is_fading_out())
        self.assertTrue(wait(self.app, forest.isPlaying))
        for _ in range(blocks):
            mixer.readData(2048 * 4)
        self.assertFalse(cave.isPlaying())
        self.assertEqual(forest.gain, 1.0)

    def test_old_ambiences_are_released_beyond_the_memory_limit(self):
        bank = self.bank()
        with patch.object(sound_effects, 'MAX_DECODED_AMBIENCES', 1):
            bank.set_ambient_enabled(True)
            cave = bank.effects['ambient']
            self.assertTrue(wait(self.app, cave.isPlaying))
            bank.set_ambient_track('cite-1983')
            cave.stop()                           # Fondu terminé.
            city = bank.effects['ambient_cite']
            self.assertTrue(wait(self.app, city.isPlaying))
        self.assertEqual(cave.status(), PcmEffect.Unloaded)

    def test_volume_sliders_reach_the_mixer(self):
        bank = self.bank()
        bank.set_effects_volume(40)
        bank.set_ambient_volume(150)
        self.assertEqual(bank._pcm_mixer.channels, {'effects': .4, 'ambient': 1.5})


if __name__ == '__main__':
    unittest.main()
