import json
import array
import math
import random
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, call

from PySide6.QtWidgets import QApplication, QMessageBox
from book_events import DATA_PATH
from main import MainWindow, ASSET_DIR
from sound_effects import SoundBank, EFFECT_LABELS


class Signal:
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)
    def emit(self):
        for callback in self.callbacks: callback()


class FakeEffect:
    Ready, Loading, Error, Infinite = 2, 1, 3, -2
    def __init__(self, parent):
        self.statusChanged = Signal()
        self.state = self.Ready
        self.play_count = self.stop_count = 0
    def setVolume(self, value): self.volume = value
    def setLoopCount(self, count): self.loops = count
    def setSource(self, url): self.source = url
    def status(self): return self.state
    def play(self): self.play_count += 1
    def stop(self): self.stop_count += 1


class SoundFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_all_effects_are_preloaded_and_muting_cancels_late_sound(self):
        state = random.getstate()
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR/'sounds')
            self.assertEqual(set(bank.effects), {*EFFECT_LABELS, 'ambient'})
            page = bank.effects['page']
            bank.play('page')
            self.assertIs(bank.effects['page'], page)
            self.assertEqual(page.play_count, 1)
            page.state = FakeEffect.Loading
            bank.play('page')
            bank.set_enabled(False)
            page.state = FakeEffect.Ready
            page.statusChanged.emit()
            self.assertEqual(page.play_count, 1)
            self.assertNotIn('page', bank.pending)
        self.assertEqual(random.getstate(), state)

    def test_ambient_has_independent_mute_and_loops(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR/'sounds', ambient_enabled=True)
            ambient = bank.effects['ambient']
            self.assertEqual(ambient.loops, FakeEffect.Infinite)
            self.assertEqual(ambient.play_count, 1)
            bank.set_enabled(False)
            self.assertEqual(ambient.stop_count, 0)
            bank.set_ambient_enabled(False)
            self.assertEqual(ambient.stop_count, 1)

    def test_free_sound_manifest_and_page_has_immediate_audible_attack(self):
        manifest = json.loads((ASSET_DIR/'sounds/sources.json').read_text())
        self.assertEqual(manifest['license'], 'CC0-1.0')
        self.assertTrue(set(EFFECT_LABELS) <= manifest['effects'].keys())
        for name in [*EFFECT_LABELS, 'ambient']:
            self.assertTrue((ASSET_DIR/'sounds'/f'{name}.wav').is_file())
        with wave.open(str(ASSET_DIR/'sounds/page.wav')) as file:
            rate = file.getframerate()
            attack = array.array('h', file.readframes(int(rate * .04)))
            rms = math.sqrt(sum(v*v for v in attack)/len(attack))
            self.assertGreater(rms, 1000)  # Reject a long silent/faint lead-in.

    def setUp(self):
        self.w = MainWindow()
        self.w.paragraphs = {1:'Salle.', 2:'Suite.'}

    def tearDown(self):
        self.w.close(); self.w.deleteLater(); self.app.processEvents()

    def test_combat_is_audible_before_result_dialog(self):
        w = self.w
        w.go_to(1)
        def result(_):
            self.assertIn(call('swords'), play.call_args_list)
            return QMessageBox.No
        with patch.object(w.sounds, 'play') as play, \
                patch.object(w, '_roll', side_effect=[([1,1],2),([6,6],12)]), \
                patch.object(QMessageBox, 'exec', result):
            w.combat_round()
            self.assertEqual(play.call_args_list.count(call('swords')), 1)

    def test_page_starts_before_rendering_and_does_not_repeat_on_refresh(self):
        w = self.w
        original = w._render_paragraph_text
        def render(text):
            play.assert_any_call('page')
            return original(text)
        with patch.object(w.sounds, 'play') as play, patch.object(w, '_render_paragraph_text', render):
            w.go_to(1)
            w.go_to(1)
            self.assertEqual(play.call_args_list.count(call('page')), 1)

    def test_potion_coins_items_and_damage_trigger_only_on_state_change(self):
        w = self.w
        w.go_to(1)
        with patch.object(w.sounds, 'play') as play:
            w.set_stat('gold', 4)
            play.assert_called_once_with('coins'); play.reset_mock()
            w.set_stat('gold', 4)
            play.assert_not_called()
            w.change_potion('Potion de Vigueur'); play.reset_mock()
            w.drink_potion()
            play.assert_called_once_with('potion'); play.reset_mock()
            w.set_stat('endurance', 5)
            play.assert_called_once_with('hit'); play.reset_mock()
            w.item_input.setText('Objet de test'); w.add_item()
            play.assert_called_once_with('item'); play.reset_mock()
            w.set_stat('endurance', 0)
            play.assert_called_once_with('death'); play.reset_mock()
            w.undo_action(); w.redo_action()
            play.assert_not_called()

    def test_key_and_victory_cues_use_real_catalogue_actions(self):
        w = self.w
        w.book_event_catalogue = json.loads(DATA_PATH.read_text())
        w.paragraphs.update({383:'Porte.',80:'Hangar.',240:'Serpent.',145:'Récompense.'})
        w.character['inventory'].append('Clé du Hangar à Bateaux')
        w.go_to(383)
        with patch.object(w.sounds, 'play') as play:
            w.follow_catalogue_choice(80)
            play.assert_any_call('key')
            w.go_to(240); play.reset_mock()
            with patch.object(w, '_roll', side_effect=[([1,1],2),([6,6],12)]), \
                    patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
                w.combat_round()
            play.assert_any_call('victory')
