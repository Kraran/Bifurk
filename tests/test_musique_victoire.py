"""Musique de victoire : « Achievement » en boucle au §400, puis retour à la normale.

Les lecteurs Qt sont des Mock et les volumes des propriétés Qt réelles : aucune
carte son n'est sollicitée. La fenêtre vérifie le déclenchement au §400 seulement.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_musique_victoire
"""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation
from PySide6.QtWidgets import QApplication

import main
from intro_music import IntroMusic
from sound_effects import SoundBank
from tests.test_ambiances_paragraphe import sorcier
from tests.test_musique_perso import DEFAULT, VolumeOutput, service
from tests.test_sound_feedback import FakeEffect

ROOT = Path(__file__).resolve().parents[1]
VICTORY = ROOT / 'assets' / 'sounds' / 'Achievement.ogg'


def victory_service(**kwargs):
    music = service(victory_path=VICTORY, **kwargs)
    music.victory_output = VolumeOutput()
    music.victory_player = Mock()
    music.victory_fade = QPropertyAnimation(music.victory_output, b'volume', music)
    music.victory_fade.finished.connect(music._victory_faded)
    return music


def running(animation):
    return animation is not None and animation.state() == QAbstractAnimation.State.Running


class VictoryAssetTests(unittest.TestCase):
    def test_optimised_ogg_is_shipped(self):
        data = VICTORY.read_bytes()
        self.assertEqual(data[:4], b'OggS')
        self.assertLess(len(data), 2_500_000)       # MP3 d'origine : 4,8 Mo


class VictoryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_victory_fades_the_menu_music_and_loops_at_slider_volume(self):
        music = victory_service()
        music.menu()
        plays = music.player.play.call_count
        music.start_victory()
        self.assertTrue(music.victory)
        self.assertTrue(running(music.fade))
        self.assertEqual(music.fade.duration(), IntroMusic.VICTORY_FADE_MS)
        music.victory_player.play.assert_called_once()
        self.assertAlmostEqual(music.victory_output.level, music.target_volume)
        music.menu()                               # pas de FantasyFair par-dessus
        self.assertEqual(music.player.play.call_count, plays)
        music.start_victory()                      # rafraîchissement : rien ne redémarre
        music.victory_player.play.assert_called_once()

    def test_slider_applies_to_victory_and_zero_mutes_it(self):
        music = victory_service()
        music.start_victory()
        music.set_volume(50)
        self.assertAlmostEqual(music.victory_output.level, IntroMusic.VOLUME * .5)
        music.set_volume(0)
        music.victory_player.stop.assert_called()
        music.set_volume(80)
        self.assertEqual(music.victory_player.play.call_count, 3)

    def test_leaving_victory_fades_it_and_resumes_menu_music_only_when_due(self):
        music = victory_service()
        music.start_victory()
        music.stop_victory()
        self.assertFalse(music.victory)
        self.assertTrue(running(music.victory_fade))
        music.player.play.assert_not_called()      # en partie, sans musique permanente
        music.victory_fade.setCurrentTime(music.victory_fade.duration())
        music.victory_player.stop.assert_called_once()

        music = victory_service()
        music.menu()
        music.start_victory()
        plays = music.player.play.call_count
        music.stop_victory()
        self.assertEqual(music.player.play.call_count, plays + 1)

    def test_persistent_music_returns_after_victory(self):
        music = victory_service(persistent=True)
        music.fade_out()
        music.start_victory()
        music.stop_victory()
        self.assertFalse(running(music.fade))
        self.assertAlmostEqual(music.output.level, music.target_volume)

    def test_state_is_tracked_without_audio_output(self):
        music = IntroMusic(DEFAULT, victory_path=VICTORY)
        music.start_victory()
        self.assertTrue(music.victory)
        self.assertIsNone(music.victory_player)
        music.stop_victory()
        self.assertFalse(music.victory)


class VictoryWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patcher = patch.object(SoundBank, '_backend', return_value=FakeEffect)
        self.patcher.start()
        self.w = main.MainWindow()
        self.w.sounds.duck_ambient = Mock()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()
        self.patcher.stop()

    def test_paragraph_400_of_a_grimoire_starts_and_any_other_screen_stops(self):
        w, music = self.w, self.w.intro_music
        self.assertEqual(music.victory_path.name, 'Achievement.ogg')
        w.book_module = sorcier()
        w._ambience_follow_paragraph(399)
        self.assertFalse(music.victory)
        w._ambience_follow_paragraph(400)
        self.assertTrue(music.victory)
        w.sounds.duck_ambient.assert_called_once_with(True)
        w._ambience_follow_paragraph(400)          # rafraîchissement
        w.sounds.duck_ambient.assert_called_once_with(True)
        w._ambience_follow_paragraph(None)         # accueil, chargement…
        self.assertFalse(music.victory)
        w.sounds.duck_ambient.assert_called_with(False)

    def test_no_victory_without_a_recognised_grimoire(self):
        self.w.book_module = None
        self.w._ambience_follow_paragraph(400)
        self.assertFalse(self.w.intro_music.victory)
        self.w.sounds.duck_ambient.assert_not_called()


if __name__ == '__main__':
    unittest.main()
