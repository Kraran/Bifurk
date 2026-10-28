"""Barre de titre Windows aux couleurs du thème (DWM), simulée hors Windows.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_barre_titre
"""
import ctypes
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QWidget

import main


class FakeDwm:
    """DwmSetWindowAttribute enregistré ; refuse les attributs donnés (Windows 10…)."""
    def __init__(self, refused=()):
        self.calls, self.refused = [], set(refused)

    def __call__(self, hwnd, attribute, pointer, size):
        value = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents.value
        self.calls.append((attribute, value))
        return -2147024809 if attribute in self.refused else 0   # E_INVALIDARG


class NativeTitlebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = main.MainWindow()
        self.addCleanup(self.window.deleteLater)

    def apply(self, widget, refused=(), theme=None):
        fake = FakeDwm(refused)
        with patch.object(main.sys, 'platform', 'win32'), patch.object(main, '_dwm', return_value=fake), \
                patch.object(main, '_note_titlebar_failure') as note:
            ok = main.set_native_titlebar(widget, theme)
        return ok, dict(fake.calls), fake.calls, note

    def test_theme_colors_are_sent_as_colorref_with_dark_mode_first(self):
        for key in ('grimoire', 'sorcier', 'foret', 'cite'):
            theme = self.window.themes[key]
            with self.subTest(key):
                ok, values, calls, note = self.apply(self.window, theme=theme)
                caption, text, border = (main._colorref(c) for c in main.titlebar_colors(theme))
                self.assertTrue(ok)
                self.assertEqual(calls[0], (20, 1))
                self.assertEqual((values[35], values[36], values[34]), (caption, text, border))
                note.assert_not_called()
        standard = self.window.themes['grimoire'].color('icon_background')
        self.assertEqual(main._colorref(standard) & 0xFF, int(standard[1:3], 16))   # Rouge en premier octet.

    def test_windows_10_falls_back_to_dark_mode_and_notes_the_refusal(self):
        ok, values, calls, note = self.apply(self.window, refused=(20, 34, 35, 36))
        self.assertFalse(ok)
        self.assertEqual([a for a, _ in calls[:2]], [20, 19])   # Ancien numéro du mode sombre.
        note.assert_called_once()

    def test_every_titled_window_but_not_menus_or_frameless_ones(self):
        self.assertTrue(main._has_native_titlebar(self.window))
        self.assertTrue(main._has_native_titlebar(QDialog()))
        self.assertTrue(main._has_native_titlebar(QWidget(None, Qt.Window)))
        self.assertFalse(main._has_native_titlebar(QMenu()))
        self.assertFalse(main._has_native_titlebar(QWidget(None, Qt.Window | Qt.FramelessWindowHint)))
        self.assertFalse(main._has_native_titlebar(QWidget(self.window)))

    def test_theme_change_repaints_visible_title_bars(self):
        self.window.show()
        with patch.object(main, 'set_native_titlebar') as paint:
            self.window._activate_theme('cite')
        self.assertIn(self.window, [call.args[0] for call in paint.call_args_list])
        self.assertIs(paint.call_args.args[1], self.window.themes['cite'])
        self.window._activate_theme('grimoire')

    def test_other_platforms_are_left_alone(self):
        with patch.object(main.sys, 'platform', 'linux'), patch.object(main, '_dwm') as dwm:
            self.assertFalse(main.set_native_titlebar(self.window))
        dwm.assert_not_called()


if __name__ == '__main__':
    unittest.main()
