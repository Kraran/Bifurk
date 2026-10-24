"""Boutique sans spoiler, exemplaires regroupés dans la sacoche, écus en péril qui pulsent."""
import re
import unittest
from unittest.mock import patch

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

if __name__ == '__main__':
    unittest.main()
