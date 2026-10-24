"""Améliorations issues de la partie d'essai : messages, alerte, libellés, soins, boutique."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QMessageBox

import main
from grimoire_modules.registry import available_modules
from grimoire_modules.foret import rules, feedback


class WindowCase(unittest.TestCase):
    """Fenêtre réelle sur PDF synthétique ; les dés passent par random.randint."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.modules = {m.engine: m for m in available_modules()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for key, path in {'APP_DIR': root, 'BOOKS_DIR': root/'donnees/grimoires',
                          'SAVES_DIR': root/'donnees/sauvegardes',
                          'SETTINGS_DIR': root/'donnees/parametres'}.items():
            mock = patch.object(main, key, path)
            mock.start()
            self.addCleanup(mock.stop)
        main.init_portable_dirs()
        (main.SETTINGS_DIR/'preferences.json').write_text(json.dumps(
            {'sound_enabled': False, 'ambient_enabled': False, 'music_enabled': False}))
        self.sources = {}
        for name in ('foret', 'sorcier'):
            path = root / f'{name}.pdf'
            with pymupdf.open() as document:
                for index in range(170):
                    page = document.new_page(width=504.6, height=842)
                    if index == 18:
                        page.insert_text((30, 40), '1\nUne foret. Rendez-vous au 2.\n2\nUne clairiere.')
                document.save(path)
            self.sources[name] = path

        def recognize(path):
            return self.modules['foret-1983' if 'foret' in Path(path).name else 'sorcier-1982']
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, side_effect=recognize)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information', 'warning', 'critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        self.addCleanup(self.w.sounds._close_log)
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)

    def begin(self, name='foret', paragraphs=()):
        self.w.open_pdf(self.sources[name], startup=True)
        self.w._begin_adventure('Eldan')
        self.w.paragraphs.update({n: f'Texte du paragraphe {n}.' for n in paragraphs})
        return self.w

    def dice(self, *faces):
        values = iter(faces)
        return patch('random.randint', side_effect=lambda a, b: next(values))


class MessageFrameTests(WindowCase):
    def test_fever_reports_roll_and_losses(self):
        w = self.begin(paragraphs=(259,))
        w.go_to(259)
        w.character.update(endurance=8, chance=6)
        with self.dice(4, 3):
            w.perform_foret_action('fever')
        self.assertEqual(w.message_frame.text(),
                         'Chance : 4+3=7 > 6, raté. Endurance 8 → 3, Chance 6 → 5.')
        self.assertEqual(w.rules_log.text(), w.message_frame.text())

    def test_lucky_roll_and_destination(self):
        w = self.begin(paragraphs=(278, 35, 132))
        w.go_to(278)
        w.character['chance'] = 9
        with self.dice(2, 3):
            w.perform_foret_action('spiked_pit')
        text = w.message_frame.text()
        self.assertTrue(text.startswith('Chance : 2+3=5 ≤ 9, réussi.'), text)
        self.assertIn('Chance 9 → 8', text)

    def test_resource_loss_and_gold_are_listed(self):
        before = feedback.snapshot({'provisions': 10, 'gold': 12, 'inventory': ['Épée']})
        after = feedback.snapshot({'provisions': 0, 'gold': 2, 'inventory': ['Épée', 'Corde']})
        self.assertEqual(feedback.describe_changes(before, after),
                         ['Or 12 → 2', 'Provisions 10 → 0', 'Obtenu : Corde'])

    def test_second_luck_test_uses_reduced_score(self):
        before = feedback.snapshot({'habilete': 9, 'chance': 7})
        trace = [{'rolls': [3, 4], 'total': 7, 'chance': 7}, {'rolls': [3, 4], 'total': 7, 'chance': 7}]
        self.assertEqual(feedback.describe_rolls('chance', trace, before),
                         ['Chance : 3+4=7 ≤ 7, réussi', 'Chance : 3+4=7 > 6, raté'])

    def test_stale_message_cleared_on_move_but_not_on_undo(self):
        w = self.begin(paragraphs=(55, 56))
        w.go_to(55)
        w.rules_log.setText('⚑ Victoire !')
        w.go_to(55)  # rester sur place ne vide rien
        self.assertEqual(w.message_frame.text(), '⚑ Victoire !')
        w.go_to(56)
        self.assertEqual(w.message_frame.text(), '')
        self.assertTrue(w.message_frame.isHidden())
        w.undo_action()
        self.assertTrue(w.message_frame.text().startswith('Action annulée'))

    def test_message_of_the_moving_action_survives(self):
        w = self.begin(paragraphs=(308, 148))
        w.go_to(308)
        w.rules_log.setText('⚑ Victoire !')
        w.perform_foret_action('swap')
        self.assertEqual(w.current_paragraph, 148)
        self.assertNotIn('Victoire', w.message_frame.text())
        self.assertIn('Vous voici au §148', w.message_frame.text())

    def test_arrival_damage_reported(self):
        w = self.begin(paragraphs=(155, 156))
        w.go_to(155)
        endurance = w.character['endurance']
        w.go_to(156)
        self.assertEqual(w.message_frame.text(),
                         f'À l’arrivée au §156 : Endurance {endurance} → {endurance - 3}.')

    def test_sorcier_messages_stay_coherent(self):
        w = self.begin('sorcier', paragraphs=(1, 2, 3))
        w.go_to(1)
        w.rules_log.setText('⚑ Victoire !')
        w.go_to(2)
        self.assertNotIn('Victoire', w.message_frame.text())
        # Un message écrit dans la même action que le déplacement reste affiché.
        def move_with_message(window):
            window.rules_log.setText('Épreuve §2 : destination §3.')
            window.go_to(3)
        main._track_action(move_with_message, 'Essai')(w)
        self.assertEqual(w.current_paragraph, 3)
        self.assertIn('Épreuve §2', w.message_frame.text())


class LowEnduranceAlertTests(WindowCase):
    def combat_setup(self, endurance):
        from grimoire_modules.foret.encounters import COMBATS
        number = min(COMBATS)
        w = self.begin(paragraphs=(number,))
        w.go_to(number)
        w.character.update(endurance=endurance, potion='Potion de Vigueur', potion_doses=2)
        w.character['initial']['endurance'] = 20
        w._refresh_character()
        return w

    def test_main_page_alert_and_urgent_seal(self):
        w = self.combat_setup(3)
        self.assertEqual(w.low_endurance_alert(),
                         'Endurance faible : 3. Un soin est à portée : Potion de Vigueur — 2 dose(s).')
        self.assertTrue(w.care_button.urgent)
        self.assertFalse(w.endurance_alert.isHidden())
        self.assertEqual(w.care_button.toolTip(), w.low_endurance_alert())

    def test_no_alert_above_threshold_or_without_care(self):
        w = self.combat_setup(5)
        self.assertEqual(w.low_endurance_alert(), '')
        self.assertFalse(w.care_button.urgent)
        self.assertTrue(w.endurance_alert.isHidden())
        w.character.update(endurance=2, potion_doses=0, provisions=0)
        w._refresh_character()
        self.assertEqual(w.low_endurance_alert(), '')
        self.assertTrue(w.endurance_alert.isHidden())

    def test_combat_dialog_highlights_care(self):
        from combat_dialog import CombatDialog
        w = self.combat_setup(4)
        dialog = CombatDialog(w)
        self.addCleanup(dialog.deleteLater)
        w._combat_dialog = dialog
        self.addCleanup(setattr, w, '_combat_dialog', None)
        dialog.refresh_stats()
        self.assertTrue(dialog.care.property('urgent'))
        self.assertFalse(dialog.alert.isHidden())
        self.assertIn('Endurance faible : 4', dialog.alert.text())
        w.character['endurance'] = 12
        dialog.refresh_stats()
        self.assertFalse(dialog.care.property('urgent'))
        self.assertTrue(dialog.alert.isHidden())


if __name__ == '__main__':
    unittest.main()
