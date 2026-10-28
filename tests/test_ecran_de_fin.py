"""Écran de fin : bilan de la partie, carte « chronique » ; musiques de victoire et de mort.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_ecran_de_fin
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

import main
from chronicle import LISTED, ChronicleDialog, adventure_summary, defeated_line
from sound_effects import SoundBank
from tests.test_ambiances_paragraphe import sorcier
from tests.test_musique_victoire import victory_service
from tests.test_sound_feedback import FakeEffect

ROOT = Path(__file__).resolve().parents[1]
EPILOGUE = ROOT / 'assets' / 'sounds' / 'TowardsTheHorizon.ogg'


def character(**changes):
    hero = {'name': 'Kraran', 'habilete': 10, 'endurance': 4, 'chance': 6, 'gold': 12,
            'inventory': ['Épée', 'Lanterne', 'Corde'],
            'initial': {'habilete': 11, 'endurance': 20, 'chance': 9}}
    hero.update(changes)
    return hero


class SummaryTests(unittest.TestCase):
    def test_counts_visits_path_and_combats(self):
        encounters = {'12': [{'name': 'Orque', 'status': 'vaincu'}, {'name': 'Gobelin', 'status': 'fui'}],
                      '80': [{'name': 'Dragon', 'status': 'repoussé'}],
                      '95': [{'name': 'Troll', 'status': 'rencontré'}]}
        summary = adventure_summary(character(), [1, 12, 80, 12, 95], [(1, 12), (12, 80), (80, 12), (12, 95)],
                                    encounters)
        self.assertEqual((summary['visited'], summary['total'], summary['steps']), (4, 400, 4))
        self.assertEqual(summary['won'], ['Orque', 'Dragon'])
        self.assertEqual((summary['met'], summary['fled']), (4, 1))
        self.assertEqual(summary['stats'], [('Habileté', 10, 11), ('Endurance', 4, 20), ('Chance', 6, 9)])
        self.assertEqual((summary['gold'], summary['items']), (12, 3))

    def test_defeated_line_names_a_dozen_then_counts(self):
        self.assertEqual(defeated_line([]), 'Aucun adversaire vaincu.')
        names = [f'Garde {n}' for n in range(LISTED + 3)]
        line = defeated_line(names)
        self.assertIn('Garde 0, Garde 1', line)
        self.assertTrue(line.endswith('et 3 autres.'))


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, outcome='victory'):
        summary = adventure_summary(character(), [1, 2, 3], [(1, 2), (2, 3)],
                                    {'2': [{'name': 'Orque', 'status': 'vaincu'}]})
        dialog = ChronicleDialog(outcome, summary, hero='Kraran', book='Le Sorcier', tracking='Partie suivie')
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_tiles_show_the_summary(self):
        dialog = self.make()
        self.assertEqual(dialog.tiles['Paragraphes visités'], ('3', 'sur 400 (1 %)'))
        self.assertEqual(dialog.tiles['Combats gagnés'], ('1', 'sur 1 adversaire'))
        self.assertEqual(dialog.tiles['Endurance'], ('4', 'sur 20 au départ'))
        self.assertEqual(dialog.tiles['Sacoche'], ('3', 'objets'))

    def test_buttons_set_the_choice(self):
        for name, expected, result in (('chronicleRestart', 'restart', QDialog.Accepted),
                                       ('chronicleLoad', 'load', QDialog.Accepted),
                                       ('chronicleClose', None, QDialog.Rejected)):
            with self.subTest(name):
                dialog = self.make('death')
                dialog.findChild(QPushButton, name).click()
                self.assertEqual((dialog.choice, dialog.result()), (expected, result))


class EpilogueMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_death_music_replaces_victory_then_hands_back(self):
        music = victory_service(epilogue_path=EPILOGUE)
        music.start_victory()
        music.start_epilogue()
        self.assertEqual(music.special, 'epilogue')
        self.assertFalse(music.victory)
        loaded = [Path(c.args[0].toLocalFile()).name for c in music.victory_player.setSource.call_args_list]
        self.assertEqual(loaded, ['Achievement.ogg', 'TowardsTheHorizon.ogg'])
        music.stop_victory()                       # sans effet : c'est l'épilogue qui joue
        self.assertEqual(music.special, 'epilogue')
        music.menu()
        plays = music.player.play.call_count
        music.stop_epilogue()
        self.assertIsNone(music.special)
        self.assertEqual(music.player.play.call_count, plays + 1)   # retour à l'accueil

    def test_optimised_ogg_is_shipped(self):
        data = EPILOGUE.read_bytes()
        self.assertEqual(data[:4], b'OggS')
        self.assertLess(len(data), 4_500_000)      # MP3 d'origine : 9,2 Mo


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patcher = patch.object(SoundBank, '_backend', return_value=FakeEffect)
        self.patcher.start()
        self.w = main.MainWindow()
        self.w.character['name'] = 'Kraran'

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()
        self.patcher.stop()

    def cards(self):
        layout = self.w.choice_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())
                if layout.itemAt(i).widget() is not None and layout.itemAt(i).widget().objectName() == 'epilogueCard']

    def test_no_chronicle_while_the_adventure_goes_on(self):
        self.w.book_module = sorcier()
        self.w.current_paragraph = 120
        self.assertIsNone(self.w._adventure_outcome())
        self.assertIsNone(self.w._add_epilogue_card())

    def test_victory_card_once_and_music_round_trip(self):
        w = self.w
        w.book_module = sorcier()
        w.current_paragraph = 400
        self.assertEqual(w._adventure_outcome(), 'victory')
        w._add_epilogue_card()
        w._add_epilogue_card()
        self.assertEqual([c.text() for c in self.cards()], ['✦  Conclure la chronique'])
        w._ambience_follow_paragraph(400)
        heard = []
        with patch.object(QDialog, 'exec', lambda dialog: heard.append(w.intro_music.special)):
            self.assertIsNone(w.show_epilogue())
        self.assertEqual(heard, ['victory'])       # la victoire garde uniquement Achievement
        self.assertTrue(w.intro_music.victory)

    def test_death_page_offers_the_chronicle_first_and_restart_works(self):
        w = self.w
        w.character['endurance'] = 0
        w._show_death_page()
        self.assertEqual(w.intro_music.special, 'epilogue')   # Towards the Horizon dès la mort
        first = w.choice_layout.itemAt(0).widget()
        self.assertEqual(first.objectName(), 'epilogueCard')
        self.assertEqual(w._adventure_outcome(), 'death')
        with patch.object(QDialog, 'exec', lambda dialog: dialog.findChild(QPushButton, 'chronicleRestart').click()), \
                patch.object(w, '_restart_adventure') as restart:
            self.assertEqual(w.show_epilogue(), 'restart')
        restart.assert_called_once_with()
        self.assertEqual(w.intro_music.special, 'epilogue')   # la chronique ne change pas la musique
        w._ambience_follow_paragraph(None)                     # page de titre d'une nouvelle partie
        self.assertIsNone(w.intro_music.special)

    def test_undo_out_of_death_stops_the_death_music(self):
        w = self.w
        w.book_module = sorcier()
        w.current_paragraph = 50
        w.character['endurance'] = 0
        w._add_epilogue_card()
        self.assertEqual(w.intro_music.special, 'epilogue')
        w.character['endurance'] = 7                           # état rétabli par Annuler
        w._ambience_follow_paragraph(50)
        self.assertIsNone(w.intro_music.special)
        w.character['endurance'] = 0
        w._add_epilogue_card()
        w._ambience_follow_paragraph(400)                      # la victoire remplace la mort
        self.assertEqual(w.intro_music.special, 'victory')

    def test_printed_ending_without_death(self):
        w = self.w
        w.current_paragraph = 56
        w.character.setdefault('book_facts', {})['adventure_ended'] = True
        self.assertEqual(w._adventure_outcome(), 'ending')


if __name__ == '__main__':
    unittest.main()
