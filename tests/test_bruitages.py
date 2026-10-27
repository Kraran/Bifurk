"""Bruitages : variantes sans répétition, nouveaux effets et leurs déclencheurs.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bruitages
"""
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

import main
from main import ASSET_DIR, MainWindow
from pcm_audio import Mixer
from sound_effects import AMBIENT_DUCK, EFFECT_LABELS, SoundBank, creature_sound
from tests.test_sound_feedback import FakeEffect, plays


class VariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def bank(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            return SoundBank(ASSET_DIR / 'sounds')

    def test_every_effect_has_its_files_and_variants_are_found(self):
        for name in EFFECT_LABELS:
            self.assertTrue((ASSET_DIR / 'sounds' / f'{name}.wav').is_file(), name)
        bank = self.bank()
        self.assertEqual({name: len(bank.variants[name]) for name in ('page', 'dice', 'hit', 'growl', 'door')},
                         {'page': 2, 'dice': 2, 'hit': 3, 'growl': 2, 'door': 1})

    def test_variants_never_repeat_back_to_back_nor_touch_the_dice(self):
        state = random.getstate()
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR / 'sounds')
            group = [bank.effects['hit'], *bank.variants['hit']]
            history = []
            for _ in range(60):
                before = [effect.play_count for effect in group]
                bank.play('hit')
                after = [effect.play_count for effect in group]
                history.append(next(i for i, (a, b) in enumerate(zip(before, after)) if b > a))
                self.assertLessEqual(group[history[-1]].volume, .5)
                self.assertGreaterEqual(group[history[-1]].volume, .5 * .85)
        self.assertTrue(all(a != b for a, b in zip(history, history[1:])))
        self.assertEqual(set(history), {0, 1, 2, 3})
        self.assertEqual(random.getstate(), state)

    def test_muting_stops_variants_too(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR / 'sounds')
            bank.set_enabled(False)
        self.assertTrue(all(v.stop_count == 1 for v in bank.variants['page']))

    def test_creature_cries(self):
        for name, effect in (('Ogre', 'growl_giant'), ('GÉANT DES COLLINES', 'growl_giant'),
                             ('Vampire', 'growl_shade'), ('Squelette', 'growl_shade'),
                             ('Vase géante', 'growl_giant'), ('Ver des sables', 'growl_slime'),
                             ('Orque', 'growl'), ('Loup', 'growl')):
            self.assertEqual(creature_sound(name), effect, name)

    def test_combat_ducks_the_ambience_smoothly(self):
        mixer = Mixer()
        bank = self.bank()
        bank._pcm_mixer = mixer
        bank.duck_ambient(True)
        self.assertEqual(mixer.duck_target, AMBIENT_DUCK)
        mixer.readData(2048 * 4)                  # Pas de voix : la baisse progresse quand même.
        self.assertTrue(AMBIENT_DUCK < mixer.duck < 1.0)
        bank.duck_ambient(False)
        self.assertEqual(mixer.duck_target, 1.0)


class TriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        for patcher in (patch.object(SoundBank, '_backend', return_value=FakeEffect),
                        patch.object(main, 'SETTINGS_DIR', Path(tempfile.mkdtemp())),
                        patch.object(main, 'SAVES_DIR', Path(tempfile.mkdtemp()))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.w = MainWindow()
        self.w._autosave = lambda: None
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)

    def played(self):
        return {name for name in self.w.sounds.effects if plays(self.w.sounds, name)}

    def test_door_only_when_the_choice_opens_or_crosses_it(self):
        w = self.w
        w.paragraphs = {1: 'Si vous voulez ouvrir la porte, rendez-vous au 2. '
                           'Si vous préférez ne pas franchir la porte, rendez-vous au 3. '
                           'Pour suivre le couloir, rendez-vous au 4.', 2: 'A.', 3: 'B.', 4: 'C.'}
        self.assertTrue(w._route_through_door(1, 2))
        self.assertFalse(w._route_through_door(1, 3))
        self.assertFalse(w._route_through_door(1, 4))

    def test_meal_flee_and_catalogue_sounds(self):
        w = self.w
        w.paragraphs = {5: 'Combat.', 9: 'Fuite.', 12: 'Salle.'}
        w.book_event_catalogue = {'paragraphs': {
            '5': {'status': 'verifie', 'combat': {'escape_target': 9}},
            '12': {'status': 'verifie', 'sound': 'magic'}}}
        w.current_paragraph = 5
        before = w._snapshot()
        w.character['provisions'] -= 1
        w.character['endurance'] -= 0
        w.character['endurance'] += 4
        w._play_state_sounds(before)
        self.assertEqual(self.played(), {'meal'})
        before = w._snapshot()
        w.current_paragraph, w.character['endurance'] = 9, w.character['endurance'] - 2
        w._play_state_sounds(before)
        self.assertIn('flee', self.played())
        before = w._snapshot()
        w.current_paragraph = 12
        w._play_state_sounds(before)
        self.assertIn('magic', self.played())

    def test_new_combat_cries_once_and_ducks_the_ambience(self):
        w = self.w
        w.sounds.set_enabled(True)
        w.paragraphs = {1: 'Salle.'}
        w.go_to(1)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            w.prepare_encounter({'name': 'Ogre', 'skill': 8, 'stamina': 10})
        class Dialog:  # Doublure : une vraie fenêtre de combat n'est pas utile ici.
            def __init__(self, owner):
                self.outcome, self.paragraphs, self.roster = None, {1}, [{'name': 'Ogre'}]
            refresh_stats = deleteLater = lambda self: None
            exec = lambda self: QDialog.Rejected
        with patch.object(w.sounds, 'duck_ambient') as duck, patch('main.CombatDialog', Dialog):
            w.findChild(QPushButton, 'combatButton').click()
            w.findChild(QPushButton, 'combatButton').click()   # Reprise du même combat.
        self.assertEqual(plays(w.sounds, 'growl_giant'), 1)
        self.assertEqual([c.args for c in duck.call_args_list], [(True,), (False,), (True,), (False,)])


if __name__ == '__main__':
    unittest.main()
