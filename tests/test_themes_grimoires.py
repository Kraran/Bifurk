"""Thèmes de grimoire : Standard, un thème par livre, choix dans Réglages → Thème.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_themes_grimoires
"""
import colorsys
import gc
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

import adventurer_sheet
import main
import theme_palette
import themes

BOOKS = {'sorcier-1982': 'sorcier', 'foret-1983': 'foret', 'cite-1983': 'cite'}


def hue(color):
    color = QColor(color)
    return colorsys.rgb_to_hsv(color.redF(), color.greenF(), color.blueF())[0] * 360


class PaletteTests(unittest.TestCase):
    def tearDown(self):
        theme_palette.configure(None)

    def test_shipped_themes_and_order(self):
        found = themes.available_themes(main.ASSET_DIR / 'themes')
        self.assertEqual(found['grimoire'].name, 'Standard')
        self.assertEqual({found[key].data['book']: key for key in BOOKS.values()}, BOOKS)
        for key in BOOKS.values():
            theme = found[key]
            self.assertIsNotNone(theme.recolor)
            for asset in ('parchment', 'leather', 'page', 'sheet'):
                self.assertTrue(theme.assets[asset].is_file(), (key, asset))
                self.assertEqual(theme.assets[asset].parent.name, key)
            css = theme.stylesheet('serif', 'sans-serif')
            self.assertNotIn('#7a2632', css.lower())  # Le bordeaux du Standard est recoloré.

    def test_standard_is_untouched_and_book_themes_recolor_crimson(self):
        found = themes.available_themes(main.ASSET_DIR / 'themes')
        self.assertEqual(theme_palette.tint('#7a2632', None).name(), '#7a2632')
        self.assertEqual(found['grimoire'].stylesheet('serif', 'sans').count('#7a2632') > 0, True)
        sorcier = theme_palette.tint('#7a2632', found['sorcier'].recolor)
        self.assertLess(abs(hue(sorcier) - hue('#c25a26')), 3)       # Cire couleur braise.
        leather = theme_palette.tint('#3a2219', found['foret'].recolor)
        self.assertLess(abs(hue(leather) - hue('#3a3a17')), 3)        # Cuir d'écorce.
        for color in ('#123f70', '#d8b46c'):                          # Liens et or conservés.
            self.assertLess(abs(hue(theme_palette.tint(color, found['cite'].recolor)) - hue(color)), 4)

    def test_module_constants_follow_the_palette_but_shields_keep_their_colors(self):
        found = themes.available_themes(main.ASSET_DIR / 'themes')
        endurance = QColor(adventurer_sheet.StatMedallion.TINTS['endurance'])
        theme_palette.configure(found['sorcier'].recolor, found['sorcier'].assets)
        self.assertNotEqual(adventurer_sheet.BORDEAUX.name(), '#7a2632')
        self.assertEqual(adventurer_sheet.StatMedallion.TINTS['endurance'], endurance)
        theme_palette.configure(None)
        self.assertEqual(adventurer_sheet.BORDEAUX.name(), '#7a2632')


class WindowThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = Path(tempfile.mkdtemp())
        patcher = patch.object(main, 'SETTINGS_DIR', self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.w = main.MainWindow()
        self.w._autosave = lambda: None

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()
        theme_palette.configure(None)
        themes.set_active_theme(None)

    def saved(self):
        path = self.settings / 'preferences.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

    def open_book(self, engine):
        self.w.book_module = SimpleNamespace(engine=engine) if engine else None
        self.w._apply_book_theme(rerender=True)

    def test_each_book_opens_on_its_theme_by_default(self):
        self.assertEqual(self.w.theme.id, 'grimoire')
        for engine, key in BOOKS.items():
            self.open_book(engine)
            self.assertEqual(self.w.theme.id, key)
            self.assertIs(themes.default_theme(), self.w.theme)
        self.open_book(None)  # Livre non reconnu : aucun module.
        self.assertEqual(self.w.theme.id, 'grimoire')
        self.assertNotIn('theme', self.saved())

    def test_explicit_choice_wins_until_automatic_is_chosen_again(self):
        self.w.choose_theme('cite')
        self.assertEqual(self.saved()['theme'], 'cite')
        self.open_book('sorcier-1982')
        self.assertEqual(self.w.theme.id, 'cite')
        self.assertTrue(self.w.theme_actions['cite'].isChecked())
        self.w.choose_theme('auto')
        self.assertNotIn('theme', self.saved())
        self.assertEqual(self.w.theme.id, 'sorcier')
        self.assertTrue(self.w.theme_actions['auto'].isChecked())

    def test_settings_menu_lists_automatic_then_standard_and_books(self):
        labels = [action.text() for action in self.w.theme_menu.actions() if not action.isSeparator()]
        self.assertTrue(labels[0].startswith('Selon le grimoire ouvert'))
        self.assertEqual(labels[1:], ['Standard', 'L’Antre de Zagor', 'Le Sous-bois de Darkwood',
                                      'Le Port du Sable Noir'])
        self.w.theme_actions['foret'].trigger()
        self.assertEqual((self.w.theme.id, self.saved()['theme']), ('foret', 'foret'))

    def test_saved_choice_is_restored_at_startup(self):
        self.w.choose_theme('sorcier')
        again = main.MainWindow()
        self.addCleanup(again.deleteLater)
        self.assertEqual(again.theme.id, 'sorcier')
        again.book_module = SimpleNamespace(engine='cite-1983')
        again._apply_book_theme()
        self.assertEqual(again.theme.id, 'sorcier')


if __name__ == '__main__':
    unittest.main()
