"""Menu de démarrage : continuer la dernière partie et couvertures des sauvegardes.

« Continuer la dernière partie » reprend la sauvegarde lisible la plus récente,
emplacements et autosave confondus ; chaque emplacement montre la couverture de son
grimoire quand le PDF du joueur est disponible.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_continuer_couvertures
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton

import main
from save_slots import SaveSlotsDialog, latest_save


class ContinueAndCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        window = main.MainWindow()
        window.character['name'] = 'Ilda'
        cls.template = window._save_data()
        window.deleteLater()

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def write(self, name, minutes_ago, **changes):
        data = {**self.template, **changes,
                'saved_at': (datetime.now().astimezone() - timedelta(minutes=minutes_ago)).isoformat()}
        (self.folder / name).write_text(json.dumps(data), encoding='utf-8')
        return self.folder / name

    def dialog(self, **options):
        dialog = SaveSlotsDialog(self.folder, False, None, **options)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_latest_save_compares_slots_and_autosave(self):
        self.assertIsNone(latest_save(self.folder))
        slot = self.write('emplacement-2.json', 10, save_name='Ancienne')
        self.assertEqual(latest_save(self.folder)[0], slot)
        auto = self.write('autosave.json', 1, save_name='Récente')
        path, data, origin = latest_save(self.folder)
        self.assertEqual((path, data['save_name'], origin), (auto, 'Récente', 'sauvegarde automatique'))
        auto.write_text('{illisible', encoding='utf-8')     # Un fichier abîmé est ignoré.
        self.assertEqual(latest_save(self.folder)[2], 'emplacement 2')

    def test_continue_button_only_at_startup_and_returns_the_latest_save(self):
        self.write('emplacement-1.json', 30)
        auto = self.write('autosave.json', 2, book_title='La Cité des Voleurs', current_paragraph=250)
        self.assertIsNone(self.dialog().findChild(QPushButton, 'continueAdventure'))
        dialog = self.dialog(startup=True)
        resume = dialog.findChild(QPushButton, 'continueAdventure')
        self.assertTrue(resume.text().startswith('Continuer la dernière partie\nIlda  ·  La Cité des Voleurs  ·  §250'))
        self.assertEqual(dialog.findChild(QPushButton, 'newAdventure').property('dialogAction'), 'secondary')
        resume.click()
        self.assertEqual((dialog.selected_path, dialog.result()), (str(auto), 1))

    def test_without_any_save_new_game_stays_the_main_action(self):
        dialog = self.dialog(startup=True)
        self.assertIsNone(dialog.findChild(QPushButton, 'continueAdventure'))
        self.assertEqual(dialog.findChild(QPushButton, 'newAdventure').property('dialogAction'), 'primary')

    def test_slots_show_the_cover_given_by_the_controller(self):
        self.write('emplacement-1.json', 5)
        pixmap = QPixmap(20, 30)
        pixmap.fill()
        dialog = self.dialog(startup=True, cover_for=lambda data: QIcon(pixmap))
        for name in ('saveSlot1', 'continueAdventure'):
            button = dialog.findChild(QPushButton, name)
            self.assertFalse(button.icon().isNull(), name)
            self.assertEqual(button.iconSize(), SaveSlotsDialog.COVER_SIZE)
        self.assertTrue(dialog.findChild(QPushButton, 'saveSlot2').icon().isNull())   # Libre.
        broken = self.dialog(cover_for=lambda data: 1 / 0)   # Une couverture en panne n'empêche rien.
        self.assertTrue(broken.findChild(QPushButton, 'saveSlot1').isEnabled())

    def test_controller_cover_finds_the_book_once_even_from_a_windows_save(self):
        window = main.MainWindow()
        self.addCleanup(window.deleteLater)
        main.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
        (main.BOOKS_DIR / 'livre.pdf').write_bytes(b'%PDF')
        module = next(m for m in main.available_modules() if m.engine == 'sorcier-1982')
        reference = str((main.BOOKS_DIR / 'livre.pdf').relative_to(main.APP_DIR)).replace('/', '\\')
        drawn = QIcon(QPixmap(4, 4))
        with patch.object(main, 'cover_icon', return_value=drawn) as cover:
            for _ in range(2):
                self.assertIs(window._save_cover({'pdf_path': reference, 'module_id': module.id}), drawn)
            self.assertTrue(window._save_cover({'pdf_path': None}).isNull())
        cover.assert_called_once()
        self.assertEqual(cover.call_args.args[0].module, module)


if __name__ == '__main__':
    unittest.main()
