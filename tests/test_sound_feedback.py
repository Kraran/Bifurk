"""Déclenchement et priorité des sons, sans périphérique audio réel.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import json
import array
import math
import random
import unittest
import wave
import os
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from unittest.mock import patch, call

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QPushButton
from book_events import DATA_PATH
from main import MainWindow, ASSET_DIR
from sound_effects import SoundBank, EFFECT_LABELS, BOOK_SOUNDS


class Signal:
    """Doublure minimale d’un signal Qt ; conserve les callbacks à invoquer dans le test."""
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)
    def emit(self):
        """Invoquer les callbacks connectés pour simuler la notification du backend."""
        for callback in self.callbacks: callback()


class Loop(Enum):
    """Énumération factice reproduisant la valeur Infinite des backends Qt récents."""
    Infinite = -2


class FakeEffect:
    """Backend audio instrumenté : compte les lectures et arrêts sans émettre de son."""
    Ready, Loading, Error, Infinite = 2, 1, 3, Loop.Infinite
    def __init__(self, parent):
        self.statusChanged = Signal()
        self.playingChanged = Signal()
        self.state = self.Ready
        self.play_count = self.stop_count = 0
    def setVolume(self, value): self.volume = value
    def setLoopCount(self, count):
        """Exiger un entier comme le binding Qt afin de détecter la régression Enum / int."""
        if not isinstance(count, int):
            raise TypeError('loopCount must be an integer')
        self.loops = count
    def setSource(self, url): self.source = url
    def status(self): return self.state
    def play(self): self.play_count += 1
    def stop(self): self.stop_count += 1
    def isPlaying(self): return self.play_count > self.stop_count


def plays(bank, name):
    """Lectures d'un effet, toutes variantes confondues (« page », « page_2 »…)."""
    return sum(effect.play_count for effect in [bank.effects[name], *bank.variants.get(name, ())])


class SoundFeedbackTests(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_all_effects_are_preloaded_and_muting_cancels_late_sound(self):
        state = random.getstate()
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR/'sounds')
            self.assertEqual(set(bank.effects), {*EFFECT_LABELS, *BOOK_SOUNDS.values(), 'ambient', 'ambient_cite', 'ambient_foret'})
            page = bank.effects['page']
            bank.play('page')
            self.assertIs(bank.effects['page'], page)
            self.assertEqual(plays(bank, 'page'), 1)
            page.state = FakeEffect.Loading
            bank.play('page')
            bank.set_enabled(False)
            page.state = FakeEffect.Ready
            page.statusChanged.emit()
            self.assertEqual(plays(bank, 'page'), 1)
            self.assertNotIn('page', bank.pending)
        self.assertEqual(random.getstate(), state)

    def test_ambient_has_independent_mute_and_loops(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(ASSET_DIR/'sounds', ambient_enabled=True)
            ambient = bank.effects['ambient']
            self.assertEqual(ambient.loops, FakeEffect.Infinite.value)
            self.assertEqual(ambient.play_count, 1)
            bank.set_enabled(False)
            self.assertEqual(ambient.stop_count, 0)
            bank.set_ambient_enabled(False)
            self.assertEqual(ambient.stop_count, 1)

    def test_diagnostics_distinguish_requests_mute_and_backend_playback(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(SoundBank, '_backend', return_value=FakeEffect):
            path = Path(directory) / 'audio.log'
            bank = SoundBank(ASSET_DIR/'sounds', diagnostic_path=path)
            bank.play('dice')
            bank.effects['dice'].playingChanged.emit()
            bank.set_enabled(False)
            bank.play('page')
            bank._close_log()
            log = path.read_text()
            self.assertIn('request dice allowed=True', log)
            self.assertIn('dispatch dice status=2', log)
            self.assertIn('playing dice=True', log)
            self.assertIn('request page allowed=False', log)

    def test_game_buttons_keep_using_audio_after_ambience_dialog_closes(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            w = MainWindow()
            try:
                w.sounds.set_enabled(True)
                w.paragraphs = {1: 'Salle.', 2: 'Suite.'}
                def preview():
                    dialog = w.findChild(QDialog)
                    next(b for b in dialog.findChildren(QPushButton)
                         if b.text() == 'Écouter').click()
                    dialog.reject()
                QTimer.singleShot(0, preview)
                w.show_ambience()
                self.assertEqual(plays(w.sounds, 'page'), 1)
                w.go_to(1)
                self.assertEqual(plays(w.sounds, 'page'), 2)
                w.roll_free_dice('1d6')
                self.assertEqual(plays(w.sounds, 'dice'), 1)
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                    w.prepare_encounter({'name': 'Gardien', 'skill': 7, 'stamina': 6})
                # Le bouton ouvre désormais le combat complet ; ce test audio
                # isole son lancement, puis exerce un assaut du moteur sans attente.
                with patch('main.CombatDialog.exec', return_value=QDialog.Rejected) as opened:
                    w.findChild(QPushButton, 'combatButton').click()
                opened.assert_called_once()
                with patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
                    w.combat_round()
                self.assertEqual(plays(w.sounds, 'swords'), 1)
            finally:
                w.close()
                w.deleteLater()

    def test_preload_with_real_qt_multimedia_accepts_infinite_loop(self):
        # Isolate native audio initialization; Linux CI has no PipeWire configuration.
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        if sys.platform.startswith('linux'):
            environment['QT_AUDIO_BACKEND'] = 'pulseaudio'
        script = """
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QSoundEffect
from sound_effects import SoundBank
from pcm_audio import PcmEffect
app = QApplication([])
with patch.object(SoundBank, '_backend', return_value=QSoundEffect):
    bank = SoundBank(Path('assets/sounds'))
    assert bank.effects['ambient'].loopCount() == -2
with patch.object(SoundBank, '_backend', return_value=PcmEffect):
    pcm = SoundBank(Path('assets/sounds'))
    import time
    deadline = time.monotonic() + 10  # Les boucles OGG se décodent en arrière-plan.
    while any(effect.status() == effect.Loading for effect in pcm.effects.values()) \
            and time.monotonic() < deadline:
        app.processEvents()
    # Les ambiances restent non décodées tant qu'elles ne sont pas demandées.
    assert all(effect.status() == (effect.Unloaded if effect.channel == 'ambient' else effect.Ready)
               for effect in pcm.effects.values())
    pcm.play('page')
    assert any(pcm._pcm_mixer.readData(44100 * 4))
    pcm._pcm_sink.stop()
print('native preload OK')
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=ASSET_DIR.parent,
                                env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('native preload OK', result.stdout)
        self.assertNotIn('Cannot call meta function', result.stderr)
        self.assertNotIn('TypeError:', result.stderr)

    def test_free_sound_manifest_and_page_has_immediate_audible_attack(self):
        manifest = json.loads((ASSET_DIR/'sounds/sources.json').read_text())
        self.assertEqual(manifest['license'], 'CC0-1.0')
        self.assertTrue(set(EFFECT_LABELS) <= manifest['effects'].keys())
        for name in EFFECT_LABELS:
            self.assertTrue((ASSET_DIR/'sounds'/f'{name}.wav').is_file())
        self.assertTrue((ASSET_DIR/'sounds'/'ambient.ogg').is_file())  # Boucle livrée en OGG.
        with wave.open(str(ASSET_DIR/'sounds/page.wav')) as file:
            rate = file.getframerate()
            attack = array.array('h', file.readframes(int(rate * .04)))
            rms = math.sqrt(sum(v*v for v in attack)/len(attack))
            self.assertGreater(rms, 1000)  # Refuser une longue amorce silencieuse ou trop faible.

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.w = MainWindow()
        self.w.paragraphs = {1:'Salle.', 2:'Suite.'}

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
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
            w.character.update(potion='Potion de Vigueur', potion_doses=2, endurance=1)
            play.reset_mock()
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
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))
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
