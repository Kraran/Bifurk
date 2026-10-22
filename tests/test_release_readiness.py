"""Régressions de préparation 1.1.2 : rafraîchissements stables et fenêtres libérées."""
import contextlib
import io
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
from shiboken6 import isValid

from main import MainWindow, DialogThemeFilter
from combat_dialog import CombatDialog
from grimoire_ui import IllustrationDialog


class ReleaseReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        self.w.show()
        self.app.processEvents()

    def test_character_refresh_preserves_inventory_selection_and_does_not_redraw_icons(self):
        self.w.character['inventory'] += [f'Clé {number}' for number in range(25)]
        self.w._refresh_character()
        self.app.processEvents()
        items = self.w.inventory_list
        items.setCurrentRow(15)
        items.verticalScrollBar().setValue(items.verticalScrollBar().maximum())
        current, scroll = items.currentItem(), items.verticalScrollBar().value()
        with patch('main.inventory_icon') as draw:
            self.w.character['endurance'] -= 2
            self.w._refresh_character()
            self.w._refresh_character()
        draw.assert_not_called()
        self.assertIs(items.currentItem(), current)
        self.assertEqual(items.verticalScrollBar().value(), scroll)
        self.assertEqual(self.w.stat_spins['endurance'].value(), 18)

    def test_inventory_cache_invalidates_for_items_weapon_and_theme_colors(self):
        self.w.character['inventory'].append('Épée magique')
        self.w.character['equipped_weapon'] = 'Épée magique'
        self.w._refresh_character()
        item = next(self.w.inventory_list.item(i) for i in range(self.w.inventory_list.count())
                    if self.w.inventory_list.item(i).text() == 'Épée magique')
        self.assertIn('Arme équipée', item.toolTip())
        self.assertEqual(self.w.weapon_combo.currentText(), 'Épée magique')
        from grimoire_ui import inventory_icon
        self.w.theme.colors['icon_ink'] = '#ffffff'
        with patch('main.inventory_icon', wraps=inventory_icon) as draw:
            self.w._refresh_character()
        self.assertEqual(draw.call_count, len(self.w.character['inventory']))
        self.w.character['inventory'].remove('Épée magique')
        self.w._refresh_character()
        self.assertNotIn('Épée magique', [self.w.inventory_list.item(i).text()
                                        for i in range(self.w.inventory_list.count())])

    def test_cancelled_file_selectors_release_their_models_and_deferred_translation(self):
        dialogs = []
        def cancel(dialog):
            dialogs.append(dialog)
            return QDialog.Rejected
        with patch.object(QFileDialog, 'exec', cancel), patch('main.franciser_selecteur') as translate:
            for _ in range(3):
                self.assertIsNone(self.w._themed_file_dialog())
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
            translate.assert_not_called()
        self.assertTrue(all(not isValid(dialog) for dialog in dialogs))
        self.assertEqual(self.w.findChildren(QFileDialog), [])

    def test_hero_update_does_not_rebuild_enemy_document_or_weapon_selection(self):
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        document_changes, resets = [], []
        dialog.enemies.document().contentsChanged.connect(lambda: document_changes.append(True))
        dialog.weapon.model().modelReset.connect(lambda: resets.append(True))
        self.w.character['endurance'] -= 2
        dialog.refresh_stats()
        dialog.refresh_stats()
        self.assertEqual(document_changes, [])
        self.assertEqual(resets, [])
        self.assertIn('Endurance 18', dialog.hero.text())

    def test_closed_illustration_releases_its_pixels_and_widgets(self):
        dialogs = []
        def close(dialog):
            dialogs.append(dialog)
            return QDialog.Rejected
        picture = QPixmap(80, 120)
        picture.fill()
        with patch.object(self.w, '_illustration_pixmap', return_value=picture), \
                patch.object(IllustrationDialog, 'exec', close):
            self.w._show_illustration({'page_pdf': 1}, 'Illustration de test')
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertFalse(isValid(dialogs[0]))
        self.assertEqual(self.w.findChildren(IllustrationDialog), [])

    def test_immediately_closed_dialogs_do_not_call_destroyed_cpp_objects(self):
        """Reproduire une fermeture avant les retouches de barre native différées."""
        event_filter = DialogThemeFilter(self.app)
        self.addCleanup(event_filter.deleteLater)
        self.app.installEventFilter(event_filter)
        self.addCleanup(self.app.removeEventFilter, event_filter)
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            for _ in range(3):
                dialog = QDialog(self.w)
                dialog.show()
                dialog.close()
                dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
        self.assertNotIn('RuntimeError', errors.getvalue())
