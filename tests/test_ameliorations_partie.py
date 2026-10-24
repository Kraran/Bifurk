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


class EventLabelTests(WindowCase):
    def buttons(self, w):
        from PySide6.QtWidgets import QPushButton
        layout = w.event_layout
        found = {}
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                found[widget.text()] = widget
        return found

    def test_damage_and_resource_amounts_in_labels(self):
        w = self.begin(paragraphs=(108, 145))
        w.go_to(108)
        buttons = self.buttons(w)
        self.assertIn('Blessure : −3 Endurance', buttons)
        self.assertEqual(buttons['Blessure : −3 Endurance'].toolTip(), 'Effets : Endurance −3.')
        w.character['provisions'] = 10
        w.go_to(145)
        self.assertIn('Perdre vos 10 Provisions', self.buttons(w))

    def test_finds_drop_value_in_label_but_keep_it_in_tooltip(self):
        from grimoire_modules.foret import labels
        label, tip = labels.entry_button(rules.ENTRY_RULES[106], {'inventory': []})
        self.assertEqual(label, 'Recueillir : Bague d’or à émeraude, +2 Chance')
        self.assertIn('(valeur 15 Or)', tip)
        label, _ = labels.entry_button(rules.ENTRY_RULES[305], {})
        self.assertEqual(label, 'Recueillir : 10 Or, Couteau à lancer')

    def test_tests_show_score_and_outcomes(self):
        w = self.begin(paragraphs=(90, 259, 22))
        w.character['chance'] = 8
        w.go_to(90)
        button = next(b for t, b in self.buttons(w).items() if t.startswith('Tenter votre Chance'))
        self.assertEqual(button.text(), 'Tenter votre Chance (2d6 ≤ 8)')
        self.assertIn('§210', button.toolTip())
        self.assertIn('perte de 3 Endurance', button.toolTip())
        w.go_to(259)
        self.assertIn('Affronter la fièvre : −3 Endurance, puis Chance (2d6 ≤ 8)', self.buttons(w))
        w.go_to(22)
        self.assertIn('Gaz toxique : −1d6 Endurance, −2 Habileté', self.buttons(w))

    def test_equipment_label_shows_skill_bonus(self):
        w = self.begin(paragraphs=(2,))
        w.character['inventory'].append('Casque magique')
        w._refresh_character()
        w.go_to(2)
        button = self.buttons(w)['Porter Casque magique (+1 Habileté)']
        self.assertIn('+1', button.toolTip())


class CareMenuTests(WindowCase):
    def menu_entries(self, w):
        from PySide6.QtWidgets import QMenu
        seen = {}

        case = self

        class CaptureMenu(QMenu):
            def exec(self, *args):
                case.assertTrue(self.toolTipsVisible())
                seen.update({a.text(): (a.isEnabled(), a.toolTip()) for a in self.actions()})
        with patch.object(main, 'QMenu', CaptureMenu):
            w.show_care_menu()
        return seen

    def test_owned_cares_only_and_real_reasons(self):
        w = self.begin(paragraphs=(2,))
        w.go_to(2)
        w.character.update(endurance=20, provisions=3, potion='Potion de Vigueur', potion_doses=2)
        w.character['initial']['endurance'] = 20
        entries = self.menu_entries(w)
        self.assertEqual(set(entries), {'Potion de Vigueur — 2 dose(s)', 'Prendre un repas'})
        self.assertEqual(entries['Prendre un repas'], (False, 'Endurance déjà à son maximum (20/20).'))
        self.assertEqual(entries['Potion de Vigueur — 2 dose(s)'][1], 'Endurance déjà à son maximum (20/20).')
        w.character.update(endurance=12, provisions=0, potion_doses=0)
        w.character['inventory'].append(rules.ELVEN_BREAD)
        entries = self.menu_entries(w)
        self.assertEqual(entries['Prendre un repas'], (False, 'Plus de provisions.'))
        self.assertEqual(entries['Potion de Vigueur — 0 dose(s)'], (False, 'Fiole vide : plus aucune dose.'))
        self.assertTrue(entries['Pain elfique (+4 Endurance)'][0])
        self.assertNotIn('Potion de Force (+5 Endurance)', entries)

    def test_already_ate_tooltip_and_combat_reason(self):
        from grimoire_modules.fighting_fantasy.controller import MEAL_ALREADY_TAKEN
        from grimoire_modules.foret.encounters import COMBATS
        w = self.begin(paragraphs=(2, min(COMBATS)))
        w.go_to(2)
        w.character.update(endurance=10, provisions=3)
        w.use_care('meal')
        entries = self.menu_entries(w)
        self.assertEqual(entries['Prendre un repas — déjà mangé ici'], (False, MEAL_ALREADY_TAKEN))
        w.go_to(min(COMBATS))
        meal = next(o for o in w.care_options() if o['id'] == 'meal')
        self.assertEqual(meal['reason'], 'Pas de repas pendant un combat.')
        self.assertEqual(next(o for o in w.care_options(in_combat=True) if o['id'] == 'meal')['reason'],
                         'Pas de repas pendant un combat.')

    def test_special_meal_paragraph_reason(self):
        w = self.begin(paragraphs=(328,))
        w.go_to(328)
        w.character.update(endurance=10, provisions=3)
        meal = next(o for o in w.care_options() if o['id'] == 'meal')
        self.assertFalse(meal['enabled'])
        self.assertIn('commande du passage', meal['reason'])



class ShopTests(WindowCase):
    def open_shop(self, w, steps):
        """Ouvrir la vraie boutique et jouer `steps(dialog)` à la place de la boucle modale."""
        from grimoire_modules.foret import actions

        class Probe(actions.QDialog):
            def exec(self):
                steps(self)
                return 0
        with patch.object(actions, 'QDialog', Probe):
            w._foret_shop()

    def widgets(self, dialog):
        from PySide6.QtWidgets import QComboBox, QSpinBox, QLabel, QPushButton
        labels = {l.objectName(): l for l in dialog.findChildren(QLabel)}
        buy = next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Acheter')
        return dialog.findChild(QComboBox), dialog.findChild(QSpinBox), labels, buy

    def test_rules_refuse_second_durable(self):
        c = {'gold': 30, 'endurance': 20, 'inventory': []}
        rules.shop_buy(c, 'Corde Magique')
        with self.assertRaises(ValueError):
            rules.shop_buy(c, 'Corde Magique')
        with self.assertRaises(ValueError):
            rules.shop_buy(c, 'Bottes à Bondir', 2)
        rules.consume(c, 'Corde Magique')
        with self.assertRaises(ValueError):
            rules.shop_buy(c, 'Corde Magique')
        rules.shop_buy(c, 'Potion Antipoison', 3)
        self.assertEqual(c['gold'], 30 - 3 - 6)

    def test_descriptions_only_from_coded_rules(self):
        self.assertIn('Objet durable', rules.shop_description('Corde Magique'))
        self.assertIn('2 passages', rules.shop_description('Corde Magique'))
        self.assertIn('cinq capsules', rules.shop_description('Capsules de Feu'))
        self.assertIn('Aucun passage', rules.shop_description('Perche à Sonder'))
        self.assertIn('disparaît du sac', rules.shop_description('Potion de Guérison'))

    def test_dialog_total_description_and_owned_durable(self):
        w = self.begin(paragraphs=(261,))
        w.go_to(261)
        w.character['gold'] = 20
        seen = {}

        def steps(dialog):
            selector, quantity, labels, buy = self.widgets(dialog)
            selector.setCurrentIndex(selector.findData('Potion Antipoison'))
            quantity.setValue(3)
            seen['total'] = labels['shopBalance'].text()
            self.assertIn('disparaît du sac', labels['shopDescription'].text())
            selector.setCurrentIndex(selector.findData('Corde Magique'))
            seen['durable_max'] = quantity.maximum()
            seen['after_switch'] = labels['shopBalance'].text()
            buy.click()
            seen['owned_text'] = selector.currentText()
            seen['buy_enabled'] = buy.isEnabled()
            seen['owned_enabled'] = selector.model().item(selector.currentIndex()).isEnabled()
            seen['description'] = labels['shopDescription'].text()
        self.open_shop(w, steps)
        self.assertEqual(seen['total'], 'Or disponible : 20 — total : 3 × 2 = 6 pièces d’or')
        self.assertEqual(seen['durable_max'], 1)
        self.assertEqual(seen['after_switch'], 'Or disponible : 20 — total : 1 × 3 = 3 pièces d’or')
        self.assertEqual(w.character['gold'], 17)
        self.assertTrue(seen['owned_text'].endswith('déjà dans le sac'))
        self.assertFalse(seen['buy_enabled'])
        self.assertFalse(seen['owned_enabled'])
        self.assertIn('ne se rachète pas', seen['description'])
        w.perform_foret_action('buy', ('Corde Magique', 1))
        self.assertEqual(w.character['gold'], 17)
        self.assertEqual(w.character['inventory'].count('Corde Magique'), 1)


if __name__ == '__main__':
    unittest.main()
