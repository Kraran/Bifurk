"""Dossier musique_perso : lecture, tirage aléatoire sans répétition et option en direct.

Le lecteur Qt est un Mock et les morceaux sont des fichiers vides dans des dossiers
temporaires : aucune carte son ni aucun décodeur n'est sollicité. Les fins de morceau
et les erreurs du lecteur sont simulées en appelant les gestionnaires de signaux."""
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Property, QAbstractAnimation, QObject
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
)

import main
from custom_music import AUDIO_EXTENSIONS, ShuffleBag, scan_tracks
from intro_music import IntroMusic

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'assets' / 'sounds' / 'FantasyFair.m4a'
END = QMediaPlayer.MediaStatus.EndOfMedia


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


def immediate(_ms, callback):
    """Remplacer QTimer.singleShot(0, …) : le saut d'un fichier illisible est synchrone."""
    callback()


class Folder:
    """Dossier temporaire de morceaux factices."""
    def __init__(self, case, *names):
        folder = tempfile.TemporaryDirectory()
        case.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'musique_perso'
        self.path.mkdir()
        for name in names:
            self.add(name)

    def add(self, name):
        (self.path / name).write_bytes(b'')
        return self.path / name


def service(folder=None, **kwargs):
    music = IntroMusic(DEFAULT, custom_folder=folder, **kwargs)
    music.output = VolumeOutput()
    music.player = Mock()
    music.bag.rng = random.Random(1234)
    return music


def sources(music):
    """Noms des fichiers successivement chargés dans le lecteur."""
    return [Path(call.args[0].toLocalFile()).name for call in music.player.setSource.call_args_list]


def fading(music):
    return music.fade is not None and music.fade.state() == QAbstractAnimation.State.Running


class ScanTests(unittest.TestCase):
    def test_only_audio_files_at_top_level_case_insensitive_and_sorted(self):
        folder = Folder(self, 'b.ogg', 'A.MP3', 'notes.txt', 'LISEZMOI.txt', '.gitkeep',
                        '.cache.mp3', 'pochette.jpg', 'd.FLAC', 'e.wav', 'f.m4a', 'g.opus', 'sans_extension')
        (folder.path / 'album.mp3').mkdir()
        (folder.path / 'album.mp3' / 'cache.mp3').write_bytes(b'')
        self.assertEqual([p.name for p in scan_tracks(folder.path)],
                         ['A.MP3', 'b.ogg', 'd.FLAC', 'e.wav', 'f.m4a', 'g.opus'])

    def test_supported_formats_and_missing_folder(self):
        self.assertTrue({'.mp3', '.m4a', '.ogg', '.flac', '.wav'} <= AUDIO_EXTENSIONS)
        self.assertNotIn('.txt', AUDIO_EXTENSIONS)
        self.assertEqual(scan_tracks(Path(tempfile.gettempdir()) / 'bifurk-dossier-absent-xyz'), [])


class ShuffleBagTests(unittest.TestCase):
    def test_every_track_once_per_round_and_no_consecutive_repeat_across_reshuffles(self):
        tracks = [f'piste-{n}' for n in range(5)]
        for seed in range(40):
            bag = ShuffleBag(random.Random(seed))
            played = [bag.next(lambda: tracks) for _ in range(5 * 30)]
            for start in range(0, len(played), 5):
                self.assertCountEqual(played[start:start + 5], tracks)
            self.assertFalse(any(a == b for a, b in zip(played, played[1:])), seed)

    def test_two_tracks_alternate_and_one_track_may_repeat(self):
        for seed in range(20):
            bag = ShuffleBag(random.Random(seed))
            played = [bag.next(lambda: ['a', 'b']) for _ in range(20)]
            self.assertFalse(any(a == b for a, b in zip(played, played[1:])))
        bag = ShuffleBag(random.Random(0))
        self.assertEqual([bag.next(lambda: ['seul']) for _ in range(3)], ['seul'] * 3)

    def test_refill_is_requested_only_when_the_round_ends(self):
        refill = Mock(side_effect=[['a', 'b', 'c'], ['a', 'b', 'c', 'd']])
        bag = ShuffleBag(random.Random(3))
        first = [bag.next(refill) for _ in range(3)]
        self.assertEqual(refill.call_count, 1)
        second = [bag.next(refill) for _ in range(4)]
        self.assertEqual(refill.call_count, 2)
        self.assertCountEqual(first, 'abc')
        self.assertCountEqual(second, 'abcd')

    def test_empty_folder_gives_nothing(self):
        self.assertIsNone(ShuffleBag().next(lambda: []))

    def test_shuffle_does_not_touch_the_game_random_generator(self):
        state = random.getstate()
        bag = ShuffleBag()
        for _ in range(10):
            bag.next(lambda: list('abcdef'))
        self.assertEqual(random.getstate(), state)


class CustomMusicServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        p = patch('intro_music.QTimer.singleShot', immediate)
        p.start()
        self.addCleanup(p.stop)

    def test_default_is_off_and_plays_fantasyfair(self):
        folder = Folder(self, 'a.mp3')
        music = service(folder.path)
        self.assertFalse(music.custom)
        music.menu()
        self.assertEqual(sources(music), ['FantasyFair.m4a'])
        music.player.setLoops.assert_called_once_with(QMediaPlayer.Infinite.value)

    def test_tracks_chain_randomly_without_repeat_and_folder_is_reread_at_wrap(self):
        folder = Folder(self, 'a.mp3', 'b.ogg', 'c.flac')
        music = service(folder.path, custom=True)
        music.menu()
        music.player.setLoops.assert_called_with(1)
        for _ in range(2):
            music._media_status(END)
        self.assertCountEqual(sources(music), ['a.mp3', 'b.ogg', 'c.flac'])
        folder.add('d.wav')                       # ajouté pendant la lecture
        for _ in range(4):
            music._media_status(END)
        played = sources(music)
        self.assertCountEqual(played[3:], ['a.mp3', 'b.ogg', 'c.flac', 'd.wav'])
        self.assertFalse(any(a == b for a, b in zip(played, played[1:])))
        self.assertEqual(music.mode, 'custom')
        self.assertEqual(music.player.play.call_count, len(played))

    def test_unreadable_files_are_skipped_once(self):
        folder = Folder(self, 'casse.mp3', 'bon-1.ogg', 'bon-2.flac')
        music = service(folder.path, custom=True)
        def play():
            if music.current_track.name == 'casse.mp3':
                music._media_error(QMediaPlayer.Error.FormatError, 'illisible')
        music.player.play.side_effect = play
        music.menu()
        for _ in range(8):
            music._media_status(END)
        played = sources(music)
        self.assertEqual(played.count('casse.mp3'), 1)
        self.assertEqual(music.mode, 'custom')
        self.assertIn(music.current_track.name, ('bon-1.ogg', 'bon-2.flac'))
        self.assertEqual({p.name for p in music.playable_tracks()}, {'bon-1.ogg', 'bon-2.flac'})

    def test_error_and_invalid_status_for_the_same_file_skip_only_once(self):
        patch.stopall()                             # vrai report par la boucle d'événements
        folder = Folder(self, 'casse.mp3', 'bon.ogg')
        music = service(folder.path, custom=True)
        music.bag.next = Mock(side_effect=[folder.path / 'casse.mp3', folder.path / 'bon.ogg'])
        music.menu()
        music._media_status(QMediaPlayer.MediaStatus.InvalidMedia)
        music._media_error(QMediaPlayer.Error.ResourceError, 'illisible')
        QApplication.processEvents()
        self.assertEqual(sources(music), ['casse.mp3', 'bon.ogg'])
        self.assertEqual(music.bad_tracks, {folder.path / 'casse.mp3'})

    def test_real_deferred_skip_runs_on_the_next_event_loop_turn(self):
        patch.stopall()
        folder = Folder(self, 'casse.mp3', 'bon.ogg')
        music = service(folder.path, custom=True)
        music.bag.next = Mock(side_effect=[folder.path / 'casse.mp3', folder.path / 'bon.ogg'])
        music.menu()
        music._media_error(QMediaPlayer.Error.FormatError, 'illisible')
        self.assertEqual(sources(music), ['casse.mp3'])   # pas de rechargement dans le signal
        QApplication.processEvents()
        self.assertEqual(sources(music), ['casse.mp3', 'bon.ogg'])

    def test_all_files_bad_falls_back_to_default_music_quietly(self):
        folder = Folder(self, 'x.mp3', 'y.ogg')
        music = service(folder.path, custom=True)
        music.player.play.side_effect = lambda: (music.mode == 'custom'
                                                 and music._media_error(QMediaPlayer.Error.FormatError, ''))
        music.menu()
        self.assertEqual(sources(music)[-1], 'FantasyFair.m4a')
        self.assertEqual(music.mode, 'default')
        music.player.setLoops.assert_called_with(QMediaPlayer.Infinite.value)
        count = len(sources(music))
        music.fade_out()
        music.menu()                               # retour au menu : pas de nouvel essai
        self.assertEqual(len(sources(music)), count)
        self.assertEqual(music.playable_tracks(), [])

    def test_empty_folder_plays_default_without_restarting_it_on_each_screen(self):
        folder = Folder(self, 'LISEZMOI.txt')
        music = service(folder.path, custom=True)
        for _ in range(3):
            music.menu()
        self.assertEqual(sources(music), ['FantasyFair.m4a'])
        self.assertEqual(music.mode, 'default')
        folder.add('nouveau.mp3')                  # ajouté puis menu suivant : pris en compte
        music.menu()
        self.assertEqual(sources(music), ['FantasyFair.m4a', 'nouveau.mp3'])

    def test_missing_folder_keeps_default_music(self):
        music = service(Path(tempfile.gettempdir()) / 'bifurk-absent-xyz', custom=True)
        music.menu()
        self.assertEqual(sources(music), ['FantasyFair.m4a'])

    def test_volume_slider_and_mute_apply_to_custom_tracks(self):
        folder = Folder(self, 'a.mp3', 'b.mp3')
        music = service(folder.path, custom=True, volume_percent=50)
        music.menu()
        self.assertAlmostEqual(music.output.level, 0.45 * 0.5)
        music.set_volume(0)
        music.player.stop.assert_called_once()
        music.set_volume(80)
        self.assertAlmostEqual(music.output.level, 0.45 * 0.8)
        self.assertEqual(len(sources(music)), 1)   # reprise du même morceau
        muted = service(folder.path, custom=True, volume_percent=0)
        muted.menu()
        muted.player.play.assert_not_called()

    def test_without_persistent_option_custom_music_fades_in_game_then_resumes(self):
        folder = Folder(self, 'a.mp3', 'b.mp3')
        music = service(folder.path, custom=True)
        music.menu()
        music.fade_out()
        self.assertTrue(fading(music))
        music._media_status(END)                   # fin de morceau pendant le fondu
        self.assertTrue(fading(music))
        music.fade.setCurrentTime(music.FADE_MS)
        music.player.stop.assert_called_once()
        loaded = len(sources(music))
        music.menu()
        self.assertFalse(fading(music))
        self.assertEqual(len(sources(music)), loaded)

    def test_with_persistent_option_the_playlist_continues_in_game(self):
        folder = Folder(self, 'a.mp3', 'b.mp3', 'c.mp3')
        music = service(folder.path, custom=True, persistent=True)
        music.menu()
        music.fade_out()
        for _ in range(5):
            music._media_status(END)
        self.assertFalse(fading(music))
        music.player.stop.assert_not_called()
        self.assertEqual(len(sources(music)), 6)
        self.assertAlmostEqual(music.output.level, music.target_volume)
        music.set_persistent(False)                 # décoché en partie : fondu habituel
        self.assertTrue(fading(music))

    def test_live_toggle_in_menu_switches_immediately(self):
        folder = Folder(self, 'a.mp3', 'b.mp3')
        music = service(folder.path)
        music.menu()
        music.set_custom(True)
        self.assertIn(sources(music)[-1], ('a.mp3', 'b.mp3'))
        music.set_custom(False)
        self.assertEqual(sources(music)[-1], 'FantasyFair.m4a')
        music.player.setLoops.assert_called_with(QMediaPlayer.Infinite.value)
        music.set_custom(True)
        self.assertEqual(music.mode, 'custom')

    def test_live_toggle_in_game_waits_unless_music_is_persistent(self):
        folder = Folder(self, 'a.mp3', 'b.mp3')
        music = service(folder.path)
        music.menu()
        music.fade_out()
        music.fade.setCurrentTime(music.FADE_MS)
        plays = music.player.play.call_count
        music.set_custom(True)
        self.assertEqual(music.player.play.call_count, plays)   # pas de relance en partie
        music.menu()
        self.assertEqual(music.mode, 'custom')
        persistent = service(folder.path, persistent=True)
        persistent.menu()
        persistent.fade_out()
        persistent.set_custom(True)
        self.assertEqual(persistent.mode, 'custom')
        persistent.set_custom(False)
        self.assertEqual(sources(persistent)[-1], 'FantasyFair.m4a')

    def test_toggling_again_retries_files_that_failed(self):
        folder = Folder(self, 'x.mp3')
        music = service(folder.path, custom=True)
        music.player.play.side_effect = lambda: (music.mode == 'custom'
                                                 and music._media_error(QMediaPlayer.Error.FormatError, ''))
        music.menu()
        self.assertEqual(music.mode, 'default')
        music.player.play.side_effect = None       # fichier remplacé par une version lisible
        music.set_custom(False)
        music.set_custom(True)
        self.assertEqual((music.mode, music.current_track.name), ('custom', 'x.mp3'))


class CustomMusicFolderTests(unittest.TestCase):
    def test_startup_creates_the_folder_next_to_the_program(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'Bifurk' / 'musique_perso'
            with patch.multiple(main, MUSIC_DIR=target, SAVES_DIR=Path(root) / 's',
                                BOOKS_DIR=Path(root) / 'g', SETTINGS_DIR=Path(root) / 'p'):
                main.init_portable_dirs()
            self.assertTrue(target.is_dir())
        self.assertEqual(main.MUSIC_DIR, main.APP_DIR / 'musique_perso')

    def test_repository_ships_readme_but_ignores_personal_tracks(self):
        readme = (ROOT / 'musique_perso' / 'LISEZMOI.txt').read_text(encoding='utf-8')
        self.assertIn('MP3', readme)
        self.assertIn('aleatoire', readme)
        self.assertTrue((ROOT / 'musique_perso' / '.gitkeep').is_file())
        if not shutil.which('git') or not (ROOT / '.git').exists():
            self.skipTest('git indisponible')
        def ignored(name):
            return subprocess.run(['git', 'check-ignore', '-q', f'musique_perso/{name}'], cwd=ROOT).returncode == 0
        self.assertTrue(ignored('mon morceau.mp3'))
        self.assertTrue(ignored('album.flac'))
        self.assertFalse(ignored('LISEZMOI.txt'))
        self.assertFalse(ignored('.gitkeep'))


class CustomMusicWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.music_dir = self.folder / 'musique_perso'
        self.music_dir.mkdir()
        for name, value in (('SETTINGS_DIR', self.folder), ('SAVES_DIR', self.folder),
                            ('MUSIC_DIR', self.music_dir)):
            p = patch.object(main, name, value)
            p.start()
            self.addCleanup(p.stop)
        for name in ('information', 'warning', 'critical'):
            p = patch.object(QMessageBox, name)
            p.start()
            self.addCleanup(p.stop)

    def window(self):
        window = main.MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def dialog(self, window, action=None):
        """Ouvrir Ambiances et relever la case, l'indice et le bouton."""
        found = {}
        def inspect(dialog):
            box = dialog.findChild(QCheckBox, 'customMusic')
            hint = dialog.findChild(QLabel, 'customMusicHint')
            found.update(text=box.text(), checked=box.isChecked(), hint=not hint.isHidden(),
                         button=dialog.findChild(QPushButton, 'openCustomMusic'))
            if action:
                action(dialog, box)
                found['hint_after'] = not hint.isHidden()
            return 0
        with patch.object(QDialog, 'exec', inspect):
            window.show_ambience()
        return found

    def test_checkbox_unchecked_by_default_and_preference_round_trip(self):
        window = self.window()
        self.assertFalse(window.intro_music.custom)
        self.assertEqual(window.intro_music.custom_folder, self.music_dir)
        found = self.dialog(window, lambda dialog, box: box.setChecked(True))
        self.assertEqual(found['text'], 'Jouer ma musique')
        self.assertFalse(found['checked'])
        self.assertTrue(window.intro_music.custom)
        stored = json.loads((self.folder / 'preferences.json').read_text(encoding='utf-8'))
        self.assertIs(stored['custom_music'], True)
        restored = self.window()
        self.assertTrue(restored.intro_music.custom)
        self.assertTrue(self.dialog(restored, lambda dialog, box: box.setChecked(False))['checked'])
        self.assertFalse(self.window().intro_music.custom)

    def test_unexpected_preference_value_keeps_the_default(self):
        (self.folder / 'preferences.json').write_text('{"custom_music": 1}', encoding='utf-8')
        self.assertFalse(self.window().intro_music.custom)

    def test_hint_appears_only_when_checked_and_nothing_is_playable(self):
        window = self.window()
        found = self.dialog(window, lambda dialog, box: box.setChecked(True))
        self.assertFalse(found['hint'])
        self.assertTrue(found['hint_after'])
        (self.music_dir / 'morceau.ogg').write_bytes(b'')
        found = self.dialog(window, lambda dialog, box: box.setChecked(False))
        self.assertFalse(found['hint'])
        self.assertFalse(found['hint_after'])

    def test_open_folder_button_uses_the_desktop_file_manager(self):
        window = self.window()
        shutil.rmtree(self.music_dir)               # supprimé par le joueur : recréé
        with patch.object(main.QDesktopServices, 'openUrl') as open_url:
            self.dialog(window, lambda dialog, box: dialog.findChild(QPushButton, 'openCustomMusic').click())
        url = open_url.call_args.args[0]
        self.assertEqual(Path(url.toLocalFile()), self.music_dir)
        self.assertTrue(self.music_dir.is_dir())


if __name__ == '__main__':
    unittest.main()
