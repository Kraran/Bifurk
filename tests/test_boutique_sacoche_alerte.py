"""Boutique sans spoiler, exemplaires regroupés dans la sacoche, écus en péril qui pulsent."""
import re
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect, QSize, Qt as _Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QLabel, QListWidget, QMessageBox,
                               QPushButton, QSpinBox, QStyleOptionViewItem)

import adventurer_sheet
from adventurer_sheet import (INVENTORY_QUANTITY_ROLE, ALERT_THRESHOLD, PULSE_PERIOD_MS,
                              StatMedallion, SheetStrip)
from grimoire_modules.cite import rules as cite
from grimoire_modules.foret import rules, labels
from test_ameliorations_partie import WindowCase
from tests import test_cite_mechanics as cite_mechanics


class ShopSpoilerTests(WindowCase):
    def test_no_description_tells_how_often_the_book_uses_an_item(self):
        self.assertTrue(rules.SHOP)
        for name in rules.SHOP:
            text = rules.shop_description(name)
            self.assertNotIn('passage', text.casefold(), name)
            self.assertNotIn('§', text, name)
            self.assertIsNone(re.search(r'\d', text), (name, text))
            self.assertNotIn('cinq', text, name)
        self.assertFalse(hasattr(rules, 'shop_uses'))

    def test_neutral_kinds_are_kept(self):
        self.assertEqual(rules.shop_description('Perche à Sonder'),
                         'Objet durable : il reste dans le sac, mais sa magie ne sert qu’une fois.')
        self.assertIn('sachet', rules.shop_description('Capsules de Feu'))
        self.assertEqual(rules.shop_description('Potion Antipoison'),
                         'Usage unique : l’article disparaît du sac une fois employé.')

    def test_shop_dialog_shows_neutral_text_and_tooltips(self):
        from grimoire_modules.foret import actions
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QComboBox, QLabel
        w = self.begin(paragraphs=(261,))
        w.go_to(261)
        seen = []

        class Probe(actions.QDialog):
            def exec(self):
                selector = self.findChild(QComboBox)
                label = next(l for l in self.findChildren(QLabel) if l.objectName() == 'shopDescription')
                for index in range(selector.count()):
                    selector.setCurrentIndex(index)
                    seen.append((selector.itemData(index, Qt.ToolTipRole) or '', label.text()))
                return 0
        with patch.object(actions, 'QDialog', Probe):
            w._foret_shop()
        self.assertEqual(len(seen), len(rules.SHOP))
        for tip, text in seen:
            for value in (tip, text):
                self.assertNotIn('passage', value.casefold())

    def test_event_tooltips_do_not_reveal_later_outcomes(self):
        character = {'habilete': 9, 'endurance': 18, 'chance': 8, 'provisions': 5,
                     'gold': 3, 'inventory': ['Épée']}
        noose = labels.command_button(358, character)[1]
        self.assertIn('§40', noose)
        self.assertIn('§218', noose)        # la route d'échec est visible dans le paragraphe
        self.assertNotIn('retrouvée', noose)
        carrot = labels.command_button(192, character)[1]
        self.assertNotIn('suite', carrot)
        self.assertNotIn('mémorisée', carrot)


class InventoryStackTests(WindowCase):
    def names(self, w):
        return [w.inventory_list.item(i).text() for i in range(w.inventory_list.count())]

    def quantity(self, w, name):
        item = next(w.inventory_list.item(i) for i in range(w.inventory_list.count())
                    if w.inventory_list.item(i).text() == name)
        return item.data(INVENTORY_QUANTITY_ROLE), item.toolTip()

    def select(self, w, name):
        w.inventory_list.setCurrentRow(self.names(w).index(name))

    def test_copies_share_one_slot_with_count(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['inventory'] = ['Épée', 'Potion Antipoison', 'Corde Magique',
                                    'Potion Antipoison', 'Potion Antipoison']
        w._refresh_character()
        self.assertEqual(self.names(w), ['Épée', 'Potion Antipoison', 'Corde Magique'])
        self.assertEqual(self.quantity(w, 'Potion Antipoison'),
                         (3, 'Potion Antipoison — 3 exemplaires'))
        self.assertEqual(self.quantity(w, 'Corde Magique')[0], 1)
        self.assertIn('Arme équipée', self.quantity(w, 'Épée')[1])

    def test_removing_one_copy_decrements(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['inventory'] = ['Épée', 'Potion Antipoison', 'Corde Magique', 'Potion Antipoison']
        w._refresh_character()
        self.select(w, 'Potion Antipoison')
        w.remove_item()
        self.assertEqual(w.character['inventory'], ['Épée', 'Potion Antipoison', 'Corde Magique'])
        self.assertEqual(self.quantity(w, 'Potion Antipoison')[0], 1)
        self.select(w, 'Potion Antipoison')
        w.remove_item()
        self.assertEqual(self.names(w), ['Épée', 'Corde Magique'])

    def test_manual_removal_with_undo_targets_one_copy(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['inventory'] = ['Épée', 'Capsules de Feu', 'Capsules de Feu']
        w._refresh_character()
        self.select(w, 'Capsules de Feu')
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.assertIsNot(w.manual_inventory(True), False)
        self.assertEqual(w.character['inventory'].count('Capsules de Feu'), 1)
        self.assertEqual(self.quantity(w, 'Capsules de Feu')[0], 1)

    def test_consuming_a_copy_decrements(self):
        w = self.begin(paragraphs=(261,))
        w.go_to(261)
        w.character['gold'] = 20
        w.perform_foret_action('buy', ('Potion Antipoison', 2))
        self.assertEqual(self.quantity(w, 'Potion Antipoison')[0], 2)
        rules.consume(w.character, 'Potion Antipoison')
        w._refresh_character()
        self.assertEqual(self.quantity(w, 'Potion Antipoison')[0], 1)

    def test_second_weapon_copy_keeps_weapon_equipped(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['inventory'] = ['Épée', 'Épée']
        w._refresh_character()
        self.select(w, 'Épée')
        w.remove_item()
        self.assertEqual(w.character['inventory'], ['Épée'])
        self.assertIn('Arme équipée', self.quantity(w, 'Épée')[1])

    def test_compact_grid_and_collapsed_heading_stay_coherent(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['inventory'] = ['Épée', 'Potion Antipoison', 'Potion Antipoison']
        w._refresh_character()
        w.inventory_list.set_compact(True)
        self.assertEqual(w.inventory_list.count(), 2)
        w.inventory_toggle.setChecked(False)
        self.assertTrue(w.inventory_toggle.text().endswith('(3 objets)'), w.inventory_toggle.text())
        w.character['inventory'].pop()
        w._refresh_character()
        self.assertTrue(w.inventory_toggle.text().endswith('(2 objets)'), w.inventory_toggle.text())
        w.inventory_toggle.setChecked(True)

    def paint_slot(self, quantity, compact, equipped=False):
        grid = adventurer_sheet.InventoryGrid()
        grid.compact = compact
        grid.addItem('Potion Antipoison')
        item = grid.item(0)
        item.setData(INVENTORY_QUANTITY_ROLE, quantity)
        if equipped:
            item.setToolTip('Potion Antipoison — Arme équipée')
        size = QSize(46, 46) if compact else QSize(74, 90)
        image = QImage(size, QImage.Format_ARGB32)
        image.fill(QColor('#000000'))
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, size.width(), size.height())
        p = QPainter(image)
        grid.itemDelegate().paint(p, option, grid.model().index(0, 0))
        p.end()
        grid.deleteLater()
        return image

    def corner_has_parchment(self, image, compact):
        span = 14 if compact else 18
        return any(QColor(image.pixel(x, y)).lightness() > 180
                   for x in range(3, 3 + span) for y in range(3, 3 + span))

    def test_badge_painted_top_left_only_for_several_copies(self):
        for compact in (False, True):
            self.assertTrue(self.corner_has_parchment(self.paint_slot(3, compact, equipped=True), compact))
            self.assertFalse(self.corner_has_parchment(self.paint_slot(1, compact), compact))


class ShieldAlertTests(WindowCase):
    def test_pulse_level_is_slow_and_soft(self):
        self.assertGreaterEqual(PULSE_PERIOD_MS, 1500)
        self.assertLessEqual(PULSE_PERIOD_MS, 2000)
        self.assertEqual(ALERT_THRESHOLD, 2)

    def test_shields_pulse_at_two_or_less_and_stop_above(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character['endurance'] = 2
        w._refresh_character()
        self.assertTrue(w.stat_medallions['endurance'].pulse.active)
        self.assertFalse(w.stat_medallions['habilete'].pulse.active)
        self.assertEqual(w.sheet_strip.alerts, {'endurance'})
        self.assertTrue(w.sheet_strip.pulse.active)
        w.character['chance'] = 0
        w._refresh_character()
        self.assertTrue(w.stat_medallions['chance'].pulse.active)
        w.character.update(endurance=3, chance=5)
        w._refresh_character()
        self.assertFalse(any(m.pulse.active for m in w.stat_medallions.values()))
        self.assertFalse(w.sheet_strip.pulse.active)
        self.assertEqual(w.sheet_strip.alerts, set())

    def test_dead_or_finished_hero_does_not_pulse(self):
        w = self.begin(paragraphs=(55,))
        w.go_to(55)
        w.character.update(endurance=1, chance=1)
        w._refresh_character()
        self.assertTrue(w.stat_medallions['chance'].pulse.active)
        w.character['endurance'] = 0
        w._refresh_character()
        self.assertFalse(any(m.pulse.active for m in w.stat_medallions.values()))
        self.assertFalse(w.sheet_strip.pulse.active)
        w.character.update(endurance=5, chance=1)
        w.character.setdefault('book_facts', {})['adventure_ended'] = True
        w._refresh_character()
        self.assertFalse(w.stat_medallions['chance'].pulse.active)

    def test_halo_follows_the_pulse(self):
        def redness(level, alert=True):
            from PySide6.QtWidgets import QSpinBox
            medallion = StatMedallion('endurance', 'ENDURANCE', QSpinBox())
            medallion.resize(100, 128)
            medallion.set_gauge(2, 20)
            medallion.set_alert(alert)
            medallion.pulse.frozen = level
            image = medallion.grab().toImage()
            medallion.set_alert(False)
            medallion.deleteLater()
            return sum(1 for x in range(image.width()) for y in range(image.height())
                       if (c := QColor(image.pixel(x, y))).red() > 150 and c.green() < 110 and c.blue() < 110)
        off, low, high = redness(0, alert=False), redness(0.0), redness(1.0)
        self.assertGreater(high, low)
        self.assertGreaterEqual(low, off)

    def test_pulse_clock_cycles(self):
        strip = SheetStrip()
        strip.set_alerts({'chance'})
        levels = []
        with patch.object(strip.pulse._clock, 'elapsed',
                          side_effect=[0, PULSE_PERIOD_MS // 2, PULSE_PERIOD_MS]):
            levels = [strip.pulse.level() for _ in range(3)]
        self.assertAlmostEqual(levels[0], 0.0)
        self.assertAlmostEqual(levels[1], 1.0)
        self.assertAlmostEqual(levels[2], 0.0)
        strip.set_alerts(())
        self.assertFalse(strip.pulse.active)
        self.assertEqual(strip.pulse.level(), 0.0)
        strip.deleteLater()


if __name__ == '__main__':
    unittest.main()


def _cite_text_is_neutral(test, text, name=''):
    """Ni chiffre, ni renvoi, ni annonce d’usage : seulement ce qu’est l’article."""
    test.assertNotIn('§', text, name)
    test.assertNotIn('passage', text.casefold(), name)
    test.assertIsNone(re.search(r'\d', text), (name, text))
    for word in ('inutile', 'plus tard', 'servira', 'fois sur'):
        test.assertNotIn(word, text.casefold(), (name, text))


class CiteShopRulesTests(unittest.TestCase):
    def test_descriptions_say_only_what_the_book_prints(self):
        character = cite_mechanics.hero(gold=99)
        for number, shop in cite.SHOPS.items():
            for name, _price in shop['items']:
                _cite_text_is_neutral(self, cite.shop_description(character, number, name), name)
            cite.buy(character, number, shop['items'][0][0])
            for name, _price in shop['items']:
                _cite_text_is_neutral(self, cite.shop_description(character, number, name), name)

    def test_shop_rule_is_said_once_in_the_header_not_per_item(self):
        character = cite_mechanics.hero(gold=99)
        for number, shop in cite.SHOPS.items():
            rule = cite.shop_rule(number)
            for name, _price in shop['items']:
                self.assertNotIn(rule, cite.shop_description(character, number, name), (number, name))

    def test_quantity_only_where_the_book_allows_copies(self):
        character = cite_mechanics.hero(gold=5)
        cite.buy(character, 241, 'Bougie de couleur', 3)
        self.assertEqual(character['gold'], 2)
        self.assertEqual(character['inventory'].count('Bougie de couleur'), 3)
        self.assertEqual(cite.can_buy(character, 241, 'Bougie de couleur', 3),
                         'Pas assez d’or : il vous faut 3 Pièces d’Or (vous en avez 2).')
        self.assertIsNotNone(cite.can_buy(character, 52, 'Lanterne', 2))


class CiteShopAndSaleWindowTests(unittest.TestCase):
    setUpClass = classmethod(cite_mechanics.CiteMechanicsWindowTests.setUpClass.__func__)
    setUp = cite_mechanics.CiteMechanicsWindowTests.setUp
    open = cite_mechanics.CiteMechanicsWindowTests.open
    start = cite_mechanics.CiteMechanicsWindowTests.start
    buttons = cite_mechanics.CiteMechanicsWindowTests.buttons
    play = cite_mechanics.CiteMechanicsWindowTests.play
    events = cite_mechanics.CiteMechanicsWindowTests.events
    event_button = cite_mechanics.CiteMechanicsWindowTests.event_button

    def run_shop(self, number, steps):
        """Ouvrir la boutique du passage et jouer steps(dialog) à la place de l’utilisateur."""
        self.play()
        self.w.go_to(number)
        seen = {}

        def exec_(dialog):
            seen['dialog'] = dialog
            steps(dialog)
            return QDialog.Accepted
        with patch.object(QDialog, 'exec', exec_):
            self.event_button('Faire ses achats').click()
        return seen

    @staticmethod
    def widgets(dialog):
        return (dialog.findChild(QComboBox), next(lab for lab in dialog.findChildren(QLabel)
                                                  if lab.objectName() == 'shopDescription'),
                next(lab for lab in dialog.findChildren(QLabel) if lab.objectName() == 'shopBalance'),
                next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Acheter'),
                dialog.findChild(QSpinBox))

    def test_city_shop_shows_price_balance_icon_and_neutral_text(self):
        seen = []

        def steps(dialog):
            selector, description, balance, buy, quantity = self.widgets(dialog)
            self.assertFalse(quantity.isVisibleTo(dialog))
            for index in range(selector.count()):
                selector.setCurrentIndex(index)
                self.assertFalse(selector.itemIcon(index).isNull())
                seen.append((selector.itemText(index), selector.itemData(index, _Qt.ToolTipRole),
                             description.text(), balance.text()))
            selector.setCurrentIndex(1)
            buy.click()
        self.run_shop(52, steps)
        self.assertEqual(len(seen), len(cite.SHOPS[52]['items']))
        for text, tip, description, balance in seen:
            _cite_text_is_neutral(self, description, text)
            self.assertNotIn('§', tip)
            self.assertRegex(tip, r'^\d+ Pièces? d’Or\.$')
            self.assertNotIn(cite.shop_rule(52), description)
            self.assertTrue(balance.startswith('Or disponible : 30 Pièces d’Or — prix : '))
        self.assertEqual(seen[1][0], 'Corde d’Escalade — 2 Pièces d’Or')
        self.assertEqual(self.w.character['gold'], 28)
        self.assertIn('Corde d’Escalade', self.w.character['inventory'])

    def test_single_purchase_shop_closes_the_other_rings(self):
        state = {}

        def steps(dialog):
            selector, description, _balance, buy, _quantity = self.widgets(dialog)
            selector.setCurrentIndex(2)
            buy.click()
            selector.setCurrentIndex(0)
            state['enabled'] = buy.isEnabled()
            state['tip'] = buy.toolTip()
            state['text'] = description.text()
            state['items'] = [selector.model().item(i).isEnabled() for i in range(selector.count())]
        self.run_shop(36, steps)
        self.assertIn(cite.SHOPS[36]['items'][2][0], self.w.character['inventory'])
        self.assertFalse(state['enabled'])
        self.assertEqual(state['tip'], 'Le livre ne permet qu’un seul achat ici.')
        self.assertTrue(state['text'].endswith('Le livre ne permet qu’un seul achat ici.'))
        self.assertEqual(state['items'], [True, False, False])

    def test_candles_are_bought_by_quantity_with_a_total(self):
        state = {}

        def steps(dialog):
            _selector, _description, balance, buy, quantity = self.widgets(dialog)
            self.assertTrue(quantity.isVisibleTo(dialog))
            quantity.setValue(3)
            state['balance'] = balance.text()
            buy.click()
            state['after'] = balance.text()
            quantity.setValue(28)
            state['tip'] = buy.toolTip()
        self.run_shop(241, steps)
        self.assertEqual(state['balance'], 'Or disponible : 30 Pièces d’Or — total : 3 × 1 = 3 Pièces d’Or')
        self.assertTrue(state['after'].startswith('Or disponible : 27 Pièces d’Or'))
        self.assertEqual(state['tip'], 'Pas assez d’or : il vous faut 28 Pièces d’Or (vous en avez 27).')
        self.assertEqual(self.w.character['inventory'].count('Bougie de couleur'), 3)
        self.w.undo_action()
        self.assertEqual((self.w.character['gold'], self.w.character['inventory'].count('Bougie de couleur')),
                         (30, 0))

    def run_sale(self, pick, confirm):
        self.play()
        self.w.character['inventory'] += ['Gobelet en argent', 'Miroir', 'Passe-partout']
        self.w.go_to(cite.PAWNBROKER)
        seen = {}

        def exec_(dialog):
            items = dialog.findChild(QListWidget, 'saleItems')
            balance = next(lab for lab in dialog.findChildren(QLabel) if lab.objectName() == 'saleBalance')
            sell = next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Vendre…')
            seen['empty'] = (balance.text(), sell.isEnabled())
            seen['offers'] = [items.item(i).text() for i in range(items.count())]
            self.assertTrue(all(not items.item(i).icon().isNull() for i in range(items.count())))
            for i in range(items.count()):
                items.item(i).setSelected(items.item(i).text().split(' — ')[0] in pick)
            seen['balance'] = balance.text()
            sell.click()
            seen['after'] = [items.item(i).text() for i in range(items.count())]
            return QDialog.Accepted
        with patch.object(QDialog, 'exec', exec_), patch.object(self.w.sounds, 'play') as sound, \
                patch.object(self.w, '_cite_confirm_sale', return_value=confirm) as asked:
            self.event_button('prêteur sur gages').click()
        seen['asked'] = asked.call_args
        seen['sounds'] = [c.args[0] for c in sound.call_args_list]
        return seen

    def test_sale_is_symmetric_to_buying_and_asks_first(self):
        seen = self.run_sale({'Gobelet en argent', 'Miroir'}, confirm=True)
        self.assertEqual(seen['empty'], ('Or disponible : 30 Pièces d’Or — rien de sélectionné', False))
        self.assertIn('Passe-partout — 15 Pièces d’Or', seen['offers'])
        self.assertEqual(seen['balance'], 'Or disponible : 30 Pièces d’Or — vous recevrez 9 Pièces d’Or')
        self.assertEqual(seen['asked'].args, (['Gobelet en argent', 'Miroir'], 9))
        self.assertEqual(self.w.character['gold'], 39)
        self.assertIn('coins', seen['sounds'])
        self.assertEqual(seen['after'], ['Passe-partout — 15 Pièces d’Or'])
        self.w.undo_action()
        self.assertEqual(self.w.character['gold'], 30)
        self.assertIn('Miroir', self.w.character['inventory'])

    def test_declined_sale_keeps_everything(self):
        seen = self.run_sale({'Passe-partout'}, confirm=False)
        self.assertEqual(seen['asked'].args, (['Passe-partout'], 15))
        self.assertEqual(self.w.character['gold'], 30)
        self.assertIn('Passe-partout', self.w.character['inventory'])
        self.assertNotIn('coins', seen['sounds'])
        self.assertIn('Passe-partout — 15 Pièces d’Or', seen['after'])

    def test_confirmation_names_items_and_total(self):
        self.play()
        shown = {}

        def answer(choice):
            def exec_(box):
                shown['text'], shown['title'] = box.text(), box.windowTitle()
                next(b for b in box.buttons() if b.text() == choice).click()
                return 0
            return exec_
        with patch.object(QMessageBox, 'exec', answer('Vendre')):
            self.assertTrue(self.w._cite_confirm_sale(['Gobelet en argent', 'Miroir'], 9))
        self.assertEqual(shown, {'text': 'Vendre Gobelet en argent et Miroir pour 9 Pièces d’Or ?',
                                 'title': 'Confirmer la vente'})
        with patch.object(QMessageBox, 'exec', answer('Garder')):
            self.assertFalse(self.w._cite_confirm_sale(['Miroir'], 1))
