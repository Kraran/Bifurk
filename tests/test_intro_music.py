"""Contrôler boucle, fondu et changements d'écran sans dépendre d'une carte son."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QAbstractAnimation, QObject, Property
from PySide6.QtWidgets import QApplication

from intro_music import IntroMusic
import main


class VolumeOutput(QObject):
    """Propriété Qt réelle pour exercer l'animation de volume sans périphérique audio."""
    def __init__(self):
        super().__init__()
        self.level = 0.0

    def get_volume(self):
        return self.level

    def set_volume(self, value):
        self.level = value

    volume = Property(float, get_volume, set_volume)

    def setVolume(self, value):
        self.level = value


class IntroMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def service(self):
        music = IntroMusic(Path('assets/sounds/FantasyFair.m4a'))
        music.output = VolumeOutput()
        music.player = Mock()
        return music

    def test_backend_sets_integer_loop_count_and_original_source(self):
        """Les énumérations PySide doivent être converties pour setLoops(int)."""
        music = IntroMusic(Path('assets/sounds/FantasyFair.m4a'))
        with patch('intro_music.QGuiApplication.platformName', return_value='windows'), \
                patch('PySide6.QtMultimedia.QAudioOutput'), \
                patch('PySide6.QtMultimedia.QMediaPlayer') as player_type:
            player_type.Infinite.value = -1
            music.menu()
            player_type.return_value.setLoops.assert_called_once_with(-1)
            source = player_type.return_value.setSource.call_args.args[0]
            self.assertTrue(source.toLocalFile().endswith('FantasyFair.m4a'))
            player_type.return_value.play.assert_called_once()

    def test_menu_preserves_player_and_interrupts_fade(self):
        music = self.service()
        music.menu()
        self.assertEqual(music.output.level, music.VOLUME)
        with patch.object(IntroMusic, 'fade_out'):
            music.menu()
        self.assertTrue(music.in_menu)
        self.assertEqual(music.player.play.call_count, 2)

    def test_mute_stops_immediately_and_only_menu_can_resume(self):
        music = self.service()
        music.menu()
        music.set_enabled(False)
        music.player.stop.assert_called_once()
        music.set_enabled(True)
        self.assertEqual(music.player.play.call_count, 2)
        music.in_menu = False
        music.set_enabled(False)
        music.set_enabled(True)
        self.assertEqual(music.player.play.call_count, 2)

    def test_real_qt_volume_fade_and_return_to_menu(self):
        # La vraie animation Qt agit sur une propriété QObject sans serveur audio.
        music = self.service()
        music.menu()
        music.fade_out()
        self.assertEqual(music.fade.duration(), 10000)
        music.fade.setCurrentTime(5000)
        self.assertAlmostEqual(music.output.level, music.VOLUME / 2, places=4)
        music.fade_out()
        self.assertEqual(music.fade.currentTime(), 5000)
        music.menu()
        self.assertEqual(music.fade.state(), QAbstractAnimation.State.Stopped)
        self.assertAlmostEqual(music.output.level, music.VOLUME, places=4)
        music.fade_out()
        music.fade.setCurrentTime(10000)
        self.assertAlmostEqual(music.output.level, 0.0, places=4)
        music.player.stop.assert_called_once()

    def test_new_game_and_save_load_drive_music_after_content_is_ready(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(main, 'SAVES_DIR', Path(folder)), \
                patch.object(main, 'SETTINGS_DIR', Path(folder)):
            window = main.MainWindow()
            self.addCleanup(window.deleteLater)
            self.addCleanup(window.close)
            window.paragraphs = {1: 'Une porte.'}
            window.pdf_path = str(Path(folder) / 'livre.pdf')
            window.intro_music = Mock()
            window._show_book_title()
            window.intro_music.menu.assert_called_once()
            observed = []
            window.intro_music.fade_out.side_effect = lambda: observed.append(window.current_paragraph)
            window._begin_adventure('Éléanor')
            self.assertEqual(observed, [1])
            data = window._save_data()
            data['pdf_path'] = ''
            save = Path(folder) / 'emplacement-1.json'
            window._write_atomic(save, data)
            window.intro_music.reset_mock()
            self.assertTrue(window.load_game(save, announce=False))
            window.intro_music.menu.assert_called_once()
            window.intro_music.fade_out.assert_called_once()
            self.assertEqual(observed, [1, 1])
