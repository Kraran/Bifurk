"""Boutique sans spoiler, exemplaires regroupés dans la sacoche, écus en péril qui pulsent."""
import re
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QStyleOptionViewItem

import adventurer_sheet
from adventurer_sheet import INVENTORY_QUANTITY_ROLE
from grimoire_modules.foret import rules, labels
from test_ameliorations_partie import WindowCase


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

if __name__ == '__main__':
    unittest.main()
