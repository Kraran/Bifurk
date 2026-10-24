"""Icônes de sacoche : chaque objet connu des deux grimoires a son dessin dédié.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_icones_objets.
Les objets sont recensés depuis les règles et catalogues (jamais depuis les PDF) :
un objet ajouté plus tard sans icône fera échouer le test.
"""
import json
import unittest
from pathlib import Path

from PySide6.QtCore import QPointF, QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

import adventurer_sheet
import book_events
import item_icons
from grimoire_modules.foret import rules as foret

ROOT = Path(__file__).resolve().parents[1]
DEPART = ('Épée', 'Armure de cuir', 'Lanterne')  # gabarit de main.MainWindow
ITEM_KINDS = {'item', 'has_item', 'remove_item', 'discard_if_present', 'missing_item',
              'equip_weapon', 'locked_item'}


def _starting_items():
    names = set(DEPART)
    for path in (ROOT / 'catalogues/modules').glob('*.json'):
        names.update(json.loads(path.read_text(encoding='utf-8')).get('starting_items', []))
    return names


def foret_items():
    names = {name for name, _ in foret.SHOP}
    names.update(foret.ALIASES)
    names.update(foret.ALIASES.values())
    names.update(foret.EQUIPMENT)
    names.update(foret.DURABLE)
    names.update(name + item_icons.EXHAUSTED_SUFFIX for name in foret.DURABLE)
    names.update((foret.HAMMER_HEAD, foret.HAMMER_HANDLE, foret.ENCHANTED_SWORD, foret.ELVEN_BREAD,
                  foret.BELL, foret.SILVER_DART, foret.GOLD_INGOT))
    names.update(foret.GOBLIN_LOOT)
    names.update(foret.DRAGON_FLUTES)
    for rules in (foret.ENTRY_RULES, foret.OPTIONAL_FINDS):
        for rule in rules.values():
            names.update(rule.get('items', ()))
            for key in ('use', 'wear', 'equip'):
                if rule.get(key):
                    names.add(rule[key])
    names.update(branch[0] for branch in foret.ITEM_BRANCHES.values())
    names.update(foret.OPTIONAL_ITEM_ROUTES.values())
    return names


def sorcier_items():
    data = json.loads((ROOT / 'catalogues/evenements_sorcier_1982.json').read_text(encoding='utf-8'))
    names = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get('kind') in ITEM_KINDS and node.get('name'):
                names.add(node['name'])
            for choice in node.get('trade_choices', ()):
                names.add(choice['name'])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    names.add(book_events.SHIELD_NAME)
    names.update(("Ciseau à lame d'argent", 'Ciseau à lame d’argent'))
    return names


def known_items():
    return sorted(_starting_items() | foret_items() | sorcier_items())


def render(name, half=17):
    image = QImage(46, 46, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    adventurer_sheet.paint_item(painter, name, QPointF(23, 23), half)
    painter.end()
    return image


def opaque_pixels(image):
    return sum(1 for y in range(image.height()) for x in range(image.width())
               if QColor.fromRgba(image.pixel(x, y)).alpha() > 40)


class ItemIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.items = known_items()

    def test_inventory_census_covers_both_books(self):
        self.assertGreaterEqual(len(foret_items()), 60)
        self.assertGreaterEqual(len(sorcier_items()), 30)
        for name in ('Carte de Yaztromo', 'Lingot d’or (valeur 28 Or)', 'Clé 111', 'Livre du Vampire'):
            self.assertIn(name, self.items)

    def test_every_known_item_has_a_dedicated_drawing(self):
        missing = [name for name in self.items if item_icons.item_icon_id(name) not in item_icons.DRAWINGS]
        self.assertEqual(missing, [])

    def test_every_drawing_is_used_and_renders_on_a_transparent_background(self):
        used = {item_icons.item_icon_id(name) for name in self.items}
        self.assertEqual(used, set(item_icons.DRAWINGS))
        for name in self.items:
            for half in (17, 12):  # case pleine et case compacte
                with self.subTest(name=name, half=half):
                    image = render(name, half)
                    self.assertEqual(QColor.fromRgba(image.pixel(0, 0)).alpha(), 0)
                    self.assertGreater(opaque_pixels(image), half * half * .25)

    def test_distinct_objects_get_distinct_images(self):
        images = {}
        for name in self.items:
            images.setdefault(item_icons.item_icon_id(name), render(name))
        seen = {}
        for icon, image in images.items():
            key = bytes(image.constBits())
            self.assertNotIn(key, seen, f'{icon} identique à {seen.get(key)}')
            seen[key] = icon

    def test_close_items_are_told_apart(self):
        groups = (
            ('Clé 111', 'Clé rouge 111', 'Clé 125', 'Clé de bronze 9', 'Clé de bronze 99',
             'Clé de cuivre 66', 'Clé du Hangar à Bateaux', 'Petite clé d’argent'),
            ('Potion de Guérison', 'Potion de Contrôle des Plantes', 'Potion de Tranquillité',
             'Potion de Contrôle des Insectes', 'Potion Antipoison', 'Potion de Force',
             "Potion d'Invisibilité", 'Eau Bénite', 'Bouteille d’eau sainte'),
            ('Anneau de Lumière', 'Anneau de Lenteur', 'Anneau d’or (valeur 10 Or)',
             'Bague d’or à émeraude (valeur 15 Or)', 'Pierre précieuse de la statue'),
            ('Médaillon d’or (valeur 9 Or)', 'Médaillon d’or (valeur 5 Or)'),
            ('Épée', 'Épée magique', 'Épée enchantée', 'Épée trouvée dans la rivière'),
            ('Bouclier de bois', 'Bouclier au croissant', 'Bouclier d’empereur'),
        )
        for group in groups:
            ids = [item_icons.item_icon_id(name) for name in group]
            self.assertEqual(len(set(ids)), len(group), group)

    def test_names_are_matched_whatever_the_apostrophe_or_case(self):
        self.assertEqual(item_icons.item_icon_id("Gousses d'Ail"), item_icons.item_icon_id('Gousses d’Ail'))
        self.assertEqual(item_icons.item_icon_id('bouclier AU croissant'), 'shield_crescent')
        self.assertEqual(item_icons.item_icon_id('Corde Magique (magie épuisée)'), 'rope_magic')
        self.assertTrue(item_icons.is_exhausted('Corde Magique (magie épuisée)'))

    def test_exhausted_magic_is_drawn_dimmed(self):
        bright = render('Corde Magique')
        dim = render('Corde Magique (magie épuisée)')
        alpha = lambda image: sum(QColor.fromRgba(image.pixel(x, y)).alpha()
                                  for y in range(image.height()) for x in range(image.width()))
        self.assertLess(alpha(dim), alpha(bright) * .6)

    def test_unknown_names_keep_the_generic_keyword_art(self):
        self.assertIsNone(item_icons.item_icon_id('Objet griffonné à la main'))
        self.assertGreater(opaque_pixels(render('Objet griffonné à la main')), 50)
        self.assertEqual(item_icons.generic_key_number('Clé 42'), '42')
        self.assertIsNone(item_icons.generic_key_number('Clef sans numéro'))
        self.assertNotEqual(bytes(render('Clé 42').constBits()), bytes(render('Clé 43').constBits()))

    def test_inventory_slot_paints_the_dedicated_icon(self):
        grid = adventurer_sheet.InventoryGrid() if hasattr(adventurer_sheet, 'InventoryGrid') else None
        self.assertIsNotNone(grid)
        grid.addItem('Clé de cuivre 66')
        grid.resize(200, 200)
        option_rect = QRect(0, 0, 74, 90)
        image = QImage(74, 90, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        from PySide6.QtWidgets import QStyleOptionViewItem
        option = QStyleOptionViewItem()
        option.rect = option_rect
        grid.itemDelegate().paint(painter, option, grid.model().index(0, 0))
        painter.end()
        copper = QColor(item_icons.METALS['copper'][1])
        found = any(abs(QColor.fromRgba(image.pixel(x, y)).red() - copper.red()) < 30
                    and abs(QColor.fromRgba(image.pixel(x, y)).green() - copper.green()) < 30
                    and abs(QColor.fromRgba(image.pixel(x, y)).blue() - copper.blue()) < 30
                    for y in range(5, 45) for x in range(10, 64))
        self.assertTrue(found)
        grid.deleteLater()


if __name__ == '__main__':
    unittest.main()
