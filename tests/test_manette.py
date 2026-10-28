"""Manette : lecture XInput simulée, répétition des directions, navigation et halo.

Aucune manette réelle : XInputGetState est remplacée par une fonction Python et la
navigation est éprouvée sur des dialogues construits pour l'occasion, puis sur les
commandes propres à la fenêtre principale.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_manette
"""
import unittest
from unittest.mock import patch

import shiboken6

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QGridLayout, QLineEdit,
                               QListWidget, QPushButton, QSlider, QVBoxLayout)

import main
from gamepad import FocusHalo, GamepadNavigator, GamepadPoller, PadState, XInputBackend


class FakeBackend:
    def __init__(self):
        self.state = None
        self.slot = 0

    def poll(self, now):
        return self.state


def fake_xinput(connected):
    """XInputGetState simulée : connected = {emplacement: (boutons, lx, ly)}."""
    calls = []

    def get_state(slot, pointer):
        calls.append(slot)
        if slot not in connected:
            return 1167
        buttons, lx, ly = connected[slot]
        pad = pointer._obj.Gamepad
        pad.wButtons, pad.sThumbLX, pad.sThumbLY = buttons, lx, ly
        return 0
    return get_state, calls


class BackendTests(unittest.TestCase):
    def test_xinput_state_is_decoded_and_the_pad_found_on_any_slot(self):
        function, calls = fake_xinput({2: (0x1000 | 0x0001 | 0x0200, 32767, -4000)})
        backend = XInputBackend(function)
        state = backend.poll(0.0)
        self.assertEqual(backend.slot, 2)
        self.assertEqual(state.buttons, {'a', 'up', 'rb'})
        self.assertAlmostEqual(state.lx, 1.0)
        self.assertEqual(state.ly, 0.0)                 # zone morte
        calls.clear()
        backend.poll(.1)
        self.assertEqual(calls, [2])                    # seul l'emplacement connu est lu

    def test_empty_slots_are_rescanned_sparingly(self):
        function, calls = fake_xinput({})
        backend = XInputBackend(function)
        self.assertIsNone(backend.poll(0.0))
        self.assertEqual(calls, [0, 1, 2, 3])
        backend.poll(.5)
        self.assertEqual(len(calls), 4)
        backend.poll(XInputBackend.RESCAN_S + .01)
        self.assertEqual(len(calls), 8)

    def test_no_backend_outside_windows(self):
        with patch('gamepad.sys.platform', 'linux'):
            self.assertIsNone(XInputBackend.create())


class PollerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.backend = FakeBackend()
        self.poller = GamepadPoller(self.backend, require_active=False)
        self.events, self.scrolls = [], []
        self.poller.pressed.connect(self.events.append)
        self.poller.scrolled.connect(lambda dx, dy: self.scrolls.append((dx, dy)))

    def test_buttons_fire_once_and_directions_repeat_after_a_delay(self):
        self.backend.state = PadState({'a', 'down'})
        self.poller.tick(0.0)
        self.poller.tick(.1)
        self.assertEqual(self.events, ['a', 'down'])
        self.poller.tick(GamepadPoller.REPEAT_DELAY_S + .01)
        self.poller.tick(GamepadPoller.REPEAT_DELAY_S + .05)
        self.poller.tick(GamepadPoller.REPEAT_DELAY_S + GamepadPoller.REPEAT_S + .02)
        self.assertEqual(self.events, ['a', 'down', 'down', 'down'])
        self.backend.state = PadState()
        self.poller.tick(2.0)
        self.backend.state = PadState({'a'})
        self.poller.tick(2.1)
        self.assertEqual(self.events[-1], 'a')

    def test_left_stick_triggers_and_right_stick(self):
        self.backend.state = PadState(lx=-.9, lt=.8, ry=.5)
        self.poller.tick(0.0)
        self.assertEqual(self.events, ['left', 'lt'])
        self.assertEqual(self.scrolls, [(0.0, .5)])

    def test_nothing_is_sent_while_another_application_is_active(self):
        self.poller.require_active = True
        self.backend.state = PadState({'a'})
        with patch('gamepad.QApplication.applicationState', return_value=Qt.ApplicationInactive):
            self.poller.tick(0.0)
        self.assertEqual(self.events, [])


class NavigatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = QDialog()
        layout = QVBoxLayout(self.dialog)
        self.name = QLineEdit()                      # jamais sélectionné
        layout.addWidget(self.name)
        grid = QGridLayout()
        self.buttons = {}
        for row in range(2):
            for col in range(2):
                button = QPushButton(f'{row}{col}')
                button.setMinimumSize(80, 30)
                grid.addWidget(button, row, col)
                self.buttons[row, col] = button
        layout.addLayout(grid)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10)
        self.slider.setValue(5)
        layout.addWidget(self.slider)
        self.check = QCheckBox('Option')
        layout.addWidget(self.check)
        self.dialog.resize(300, 260)
        self.dialog.show()
        self.app.processEvents()
        self.main = QDialog()                        # fenêtre principale fictive, jamais ciblée
        self.nav = GamepadNavigator(self.main)
        self.nav.target = lambda: self.dialog

    def tearDown(self):
        self.app.removeEventFilter(self.nav)
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def test_spatial_moves_skip_text_fields(self):
        nav = self.nav
        nav.handle('down')
        self.assertIs(nav.current, self.buttons[0, 0])
        nav.handle('right')
        self.assertIs(nav.current, self.buttons[0, 1])
        nav.handle('down')
        self.assertIs(nav.current, self.buttons[1, 1])
        nav.handle('left')
        self.assertIs(nav.current, self.buttons[1, 0])
        nav.handle('up')
        nav.handle('up')                               # le champ texte est ignoré
        self.assertIs(nav.current, self.buttons[0, 0])
        self.assertNotIn(self.name, nav.candidates(self.dialog, self.dialog))

    def test_slider_moves_inside_then_leaves_vertically(self):
        nav = self.nav
        nav.select(self.slider)
        nav.handle('right')
        self.assertEqual(self.slider.value(), 6)
        nav.handle('left')
        nav.handle('left')
        self.assertEqual(self.slider.value(), 4)
        nav.handle('down')
        self.assertIs(nav.current, self.check)

    def test_a_clicks_and_toggles_b_closes_the_dialog(self):
        nav, clicked = self.nav, []
        self.buttons[1, 0].clicked.connect(lambda: clicked.append(True))
        nav.select(self.buttons[1, 0])
        nav.handle('a')
        self.assertEqual(clicked, [True])
        nav.select(self.check)
        nav.handle('a')
        self.assertTrue(self.check.isChecked())
        nav.handle('b')
        self.assertFalse(self.dialog.isVisible())

    def test_halo_follows_the_selection_and_mouse_takes_over(self):
        nav = self.nav
        nav.select(self.buttons[0, 1])
        nav.handle('right')                            # bord : la sélection reste
        halo = self.dialog.findChild(FocusHalo, 'gamepadHalo')
        self.assertIsNotNone(halo)
        self.assertTrue(halo.isVisible())
        self.assertTrue(halo.geometry().contains(nav.rect_in(self.buttons[0, 1], self.dialog)))
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(self.buttons[0, 0], press)
        self.assertFalse(nav.active)
        self.assertFalse(halo.isVisible())

    def test_list_moves_between_items_then_leaves_at_the_edge(self):
        items = QListWidget()
        items.addItems(['Épée', 'Lanterne'])
        activated = []
        items.activated.connect(lambda index: activated.append(index.row()))
        self.dialog.layout().addWidget(items)
        self.dialog.resize(300, 420)
        self.app.processEvents()
        nav = self.nav
        nav.select(items)
        self.assertEqual(items.currentRow(), 0)
        nav.handle('down')
        self.assertEqual(items.currentRow(), 1)
        nav.handle('a')
        self.assertEqual(activated, [1])
        nav.handle('up')
        nav.handle('up')
        self.assertIs(nav.current, self.check)

    def test_a_deleted_selection_moves_to_the_window_default(self):
        nav = self.nav
        nav.handle('down')
        nav.select(self.buttons[1, 1])
        shiboken6.delete(self.buttons[1, 1])           # page suivante : cartes reconstruites
        self.buttons[0, 0].setFocus()
        nav.refresh()
        self.assertIs(nav.current, self.buttons[0, 0])


class MainWindowGamepadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = main.MainWindow()
        self.w.resize(1500, 900)
        self.w.show()
        self.app.processEvents()
        self.nav = self.w.gamepad.navigator
        self.nav.target = lambda: self.w

    def tearDown(self):
        self.app.removeEventFilter(self.nav)
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def test_settings_menu_offers_the_gamepad_window(self):
        labels = [action.text() for action in self.w.settings_button.menu().actions()]
        self.assertIn('Manette…', labels)

    def test_first_selection_without_a_book_is_grimoires_then_zones_cycle(self):
        nav, w = self.nav, self.w
        nav.handle('down')
        self.assertIs(nav.current, w.open_btn)
        for zone in (w.reader_panel, w.side_scroll, w.header_frame):
            nav.handle('rb')
            self.assertTrue(zone.isAncestorOf(nav.current), zone.objectName())
        nav.handle('lb')
        self.assertTrue(w.side_scroll.isAncestorOf(nav.current))

    def test_game_buttons(self):
        w = self.w
        size = w.reader_font_size
        self.nav.handle('rt')
        self.assertEqual(w.reader_font_size, size + 2)
        self.nav.handle('lt')
        self.assertEqual(w.reader_font_size, size)
        self.nav.handle('back')
        self.assertTrue(w.reading_mode)
        self.nav.handle('b')
        self.assertFalse(w.reading_mode)
        with patch.object(w, 'manual_history') as history:
            w.undo_btn.setEnabled(True)
            self.nav.handle('y')
            history.assert_called_once_with(False)

    def test_right_stick_scrolls_the_book_text(self):
        w = self.w
        w.reader.setPlainText('ligne\n' * 400)
        self.app.processEvents()
        bar = w.reader.verticalScrollBar()
        self.nav.scroll(0.0, -1.0)
        self.assertGreater(bar.value(), 0)

    def test_gamepad_window_toggles_the_preference(self):
        w = self.w
        with patch.object(QDialog, 'exec', lambda dialog: dialog.findChild(QCheckBox, 'gamepadEnabled').click()), \
                patch.object(w, '_save_preferences'):
            w.show_gamepad()
        self.assertFalse(w.preferences['gamepad_enabled'])
        self.assertFalse(w.gamepad.enabled)


if __name__ == '__main__':
    unittest.main()
