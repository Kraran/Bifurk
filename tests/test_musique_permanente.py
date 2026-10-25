"""Option « musique permanente » : défaut, préférence, transitions et bascule en direct.

Le lecteur Qt est remplacé par un Mock et la sortie par une propriété Qt réelle :
aucune carte son n'est nécessaire et le vrai fondu QPropertyAnimation est exercé."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Property, QAbstractAnimation, QObject
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QMessageBox

import main
from intro_music import IntroMusic


class VolumeOutput(QObject):
    """Propriété Qt réelle animée par le fondu, sans périphérique audio."""
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


def service(**kwargs):
    """Service musical prêt à jouer, avec lecteur simulé."""
    music = IntroMusic(Path('assets/sounds/FantasyFair.m4a'), **kwargs)
    music.output = VolumeOutput()
    music.player = Mock()
    return music


def fading(music):
    return music.fade is not None and music.fade.state() == QAbstractAnimation.State.Running


class PersistentMusicServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_is_off_and_entering_the_game_still_fades(self):
        music = service()
        self.assertFalse(music.persistent)
        music.menu()
        music.fade_out()
        self.assertTrue(fading(music))
        music.fade.setCurrentTime(music.FADE_MS)
        music.player.stop.assert_called_once()

    def test_persistent_music_survives_the_game_transitions(self):
        music = service(persistent=True)
        music.menu()                      # accueil, cinématique muette, préparation
        for _ in range(3):                # début d'aventure, chargement réussi ou annulé
            music.fade_out()
            music.menu()
            music.fade_out()
        self.assertFalse(fading(music))
        music.player.stop.assert_not_called()
        self.assertAlmostEqual(music.output.level, music.target_volume)

    def test_persistent_music_respects_slider_and_mute(self):
        music = service(persistent=True)
        music.menu()
        music.fade_out()
        music.set_volume(40)
        self.assertAlmostEqual(music.output.level, 0.45 * 0.40)
        music.set_volume(0)
        music.player.stop.assert_called_once()
        plays = music.player.play.call_count
        music.set_persistent(True)        # la sourdine reste prioritaire
        self.assertEqual(music.player.play.call_count, plays)
        music.set_volume(60)              # en partie, quitter la sourdine relance la boucle
        self.assertEqual(music.player.play.call_count, plays + 1)
        self.assertAlmostEqual(music.output.level, 0.45 * 0.60)

    def test_without_option_unmuting_in_game_does_not_restart(self):
        music = service()
        music.menu()
        music.fade_out()
        music.set_volume(0)
        plays = music.player.play.call_count
        music.set_volume(60)
        self.assertEqual(music.player.play.call_count, plays)

    def test_live_toggle_in_game(self):
        music = service()
        music.menu()
        music.fade_out()
        music.fade.setCurrentTime(music.FADE_MS)   # fondu terminé : musique arrêtée
        plays = music.player.play.call_count
        music.set_persistent(True)
        self.assertEqual(music.player.play.call_count, plays + 1)
        self.assertAlmostEqual(music.output.level, music.target_volume)
        music.set_persistent(False)                # comportement historique : fondu
        self.assertTrue(fading(music))
        self.assertEqual(music.fade.duration(), 10000)
        music.fade.setCurrentTime(music.FADE_MS)
        self.assertEqual(music.player.stop.call_count, 2)

    def test_live_toggle_interrupts_a_running_fade(self):
        music = service()
        music.menu()
        music.fade_out()
        music.fade.setCurrentTime(4000)
        music.set_persistent(True)
        self.assertFalse(fading(music))
        self.assertAlmostEqual(music.output.level, music.target_volume)

    def test_live_toggle_in_menu_keeps_playing(self):
        music = service()
        music.menu()
        music.set_persistent(True)
        music.set_persistent(False)
        self.assertFalse(fading(music))
        music.player.stop.assert_not_called()
        self.assertTrue(music.in_menu)


class PersistentMusicWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        for name in ('SETTINGS_DIR', 'SAVES_DIR'):
            p = patch.object(main, name, self.folder)
            p.start()
            self.addCleanup(p.stop)
        for name in ('information', 'warning', 'critical'):
            p = patch.object(QMessageBox, name)
            p.start()
            self.addCleanup(p.stop)

    def window(self):
        window = main.MainWindow()
        # close() libère audio.log avant la suppression du dossier temporaire.
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def checkbox(self, window, action=None):
        found = []
        def inspect(dialog):
            box = dialog.findChild(QCheckBox, 'musicPersistent')
            found.append((box.text(), box.isChecked()))
            if action:
                action(box)
            return 0
        with patch.object(QDialog, 'exec', inspect):
            window.show_ambience()
        return found[0]

    def test_checkbox_unchecked_by_default_and_preference_round_trip(self):
        window = self.window()
        self.assertFalse(window.intro_music.persistent)
        label, checked = self.checkbox(window, lambda box: box.setChecked(True))
        self.assertEqual(label, 'Garder la musique en fond pendant la partie')
        self.assertFalse(checked)
        self.assertTrue(window.intro_music.persistent)
        stored = json.loads((self.folder / 'preferences.json').read_text(encoding='utf-8'))
        self.assertIs(stored['music_persistent'], True)
        restored = self.window()
        self.assertTrue(restored.intro_music.persistent)
        self.assertEqual(self.checkbox(restored, lambda box: box.setChecked(False))[1], True)
        self.assertFalse(self.window().intro_music.persistent)

    def test_unexpected_preference_value_keeps_the_default(self):
        (self.folder / 'preferences.json').write_text('{"music_persistent": "oui"}', encoding='utf-8')
        self.assertFalse(self.window().intro_music.persistent)

    def test_new_game_and_load_keep_persistent_music_playing(self):
        window = self.window()
        window.paragraphs = {1: 'Une porte.'}
        window.pdf_path = str(self.folder / 'livre.pdf')
        music = service(persistent=True)
        window.intro_music = music
        window._show_book_title()
        window._begin_adventure('Éléanor')
        data = window._save_data()
        data['pdf_path'] = ''
        save = self.folder / 'emplacement-1.json'
        window._write_atomic(save, data)
        self.assertTrue(window.load_game(save, announce=False))
        self.assertFalse(fading(music))
        music.player.stop.assert_not_called()
        self.assertAlmostEqual(music.output.level, music.target_volume)

    def test_new_game_without_option_fades_as_before(self):
        window = self.window()
        window.paragraphs = {1: 'Une porte.'}
        window.pdf_path = str(self.folder / 'livre.pdf')
        music = service()
        window.intro_music = music
        window._show_book_title()
        window._begin_adventure('Éléanor')
        self.assertTrue(fading(music))


if __name__ == '__main__':
    unittest.main()
