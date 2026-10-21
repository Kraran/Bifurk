import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from book_events import DATA_PATH
from main import MainWindow
from rules_viewer import RulesDialog


class ExplorationRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = MainWindow()
        self.w.book_event_catalogue = json.loads(DATA_PATH.read_text())
        self.w.paragraphs = {n: "Paragraphe de test." for n in (116, 378, 42, 240, 145, 249, 66)}
        for method in ("question", "exec"):
            p = patch.object(QMessageBox, method, return_value=QMessageBox.No)
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def win_round(self):
        with patch.object(self.w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]):
            self.w.combat_round()

    def test_victory_record_is_saved_and_undo_restores_encounter(self):
        w = self.w
        w.go_to(240)
        self.win_round()
        self.assertEqual(w.current_paragraph, 145)
        self.assertIn("Serpent — vaincu", w._map_monsters_html(240))
        saved = w._save_data()
        self.assertEqual(saved["encounter_history"]["240"][0]["status"], "vaincu")
        w.undo_action()
        self.assertIn("Serpent — rencontré", w._map_monsters_html(240))
        w.redo_action()
        self.assertIn("Serpent — vaincu", w._map_monsters_html(240))

    def test_escape_is_recorded_only_when_it_succeeds(self):
        w = self.w
        w.go_to(249)
        w.escape_scripted_combat(249)
        self.assertEqual(w.current_paragraph, 66)
        self.assertIn("Chien — fui", w._map_monsters_html(249))
        w.undo_action()
        self.assertIn("Chien — rencontré", w._map_monsters_html(249))
        w.character["endurance"] = 1
        w.escape_scripted_combat(249)
        self.assertNotIn("— fui", w._map_monsters_html(249))

    def test_sequence_tracks_defeated_enemy_and_fleeing_next_enemy(self):
        w = self.w
        w.go_to(116)
        for _ in range(3):
            self.win_round()
        self.assertIn("Farfadet ivre 1 — vaincu", w._map_monsters_html(116))
        self.assertIn("Farfadet ivre 2 — rencontré", w._map_monsters_html(116))
        w.escape_scripted_combat(116)
        self.assertIn("Farfadet ivre 1 — vaincu", w._map_monsters_html(116))
        self.assertIn("Farfadet ivre 2 — fui", w._map_monsters_html(116))

    def test_dragon_neutralized_without_reusing_a_previous_enemy(self):
        w = self.w
        w.go_to(240)
        self.win_round()
        w.paragraphs.update({106: "Dragon.", 26: "Formule.", 371: "Dragon neutralisé."})
        w.go_to(106)
        w.go_to(26)
        w.go_to(371)
        self.assertIn("Dragon — vaincu", w._map_monsters_html(106))
        self.assertNotIn("Serpent", w._map_monsters_html(106))

    def test_rules_read_exact_pdf_pages_without_changing_game(self):
        import fitz
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rules.pdf"
            with fitz.open() as doc:
                for number in range(1, 16):
                    page = doc.new_page(width=300, height=400)
                    page.insert_text((20, 30), f"Page {number}")
                doc.save(path)
            w = self.w
            w.pdf_path = str(path)
            before = w._snapshot()
            w.show_rules()
            dialog = w.rules_dialog
            try:
                self.assertIsInstance(dialog, RulesDialog)
                self.assertFalse(dialog.isModal())
                self.assertEqual(dialog.pages.count(), 12)
                self.assertEqual(dialog.viewer.accessibleName(), "Règles — page PDF 3")
                dialog.pages.setCurrentIndex(11)
                self.assertEqual(dialog.viewer.accessibleName(), "Règles — page PDF 14")
                self.assertFalse(dialog.following.isEnabled())
                self.assertEqual(w._snapshot(), before)
                w.show_rules()
                self.assertIs(w.rules_dialog, dialog)
            finally:
                dialog.close()
