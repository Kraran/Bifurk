"""Tests de référence : aucun PDF ni texte du livre n'est embarqué."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as bifurk
from navigation import destinations, render_links
from rules_engine import encounters, stat_events
from illustrations import catalogue_for_pdf, images_for_paragraph
from PySide6.QtWidgets import QApplication, QMessageBox


class Reference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.pdf = next(ROOT.glob('*.pdf'), None)
        cls.paragraphs = bifurk.extract_paragraphs(cls.pdf) if cls.pdf else {}

    def setUp(self):
        self.window = bifurk.MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_book_event_catalogue_coverage_and_safety(self):
        from book_events import DATA_PATH, verified_entry, load_book_events
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        reviewed = {int(n) for n in data["paragraphs"]}
        pending = set(data["review_pending"])
        self.assertEqual(reviewed | pending, set(range(1, 401)))
        self.assertFalse(reviewed & pending)
        self.assertEqual(data["reviewed_count"], len(reviewed))
        self.assertIsNone(verified_entry(None, 11))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "different.pdf"
            path.write_bytes(b"not the specified edition")
            self.assertIsNone(load_book_events(path))

    def test_verified_events_once_and_undo(self):
        from book_events import apply_entry
        w = self.window
        w.book_event_catalogue = {"paragraphs": {
            "49": {"status": "verifie", "mode": "automatique",
                   "note": "Perte d'Endurance", "effects": [
                       {"kind": "stat", "key": "endurance", "amount": -2}]},
            "53": {"status": "verifie", "mode": "des",
                   "note": "Test conditionnel"},
        }}
        w.paragraphs = {49: "La pièce.", 53: "La porte."}
        w.go_to(49)
        self.assertEqual(w.character["endurance"], 18)
        self.assertEqual(w.completed_book_events, {49})
        w.go_to(49)
        self.assertEqual(w.character["endurance"], 18)
        w.go_to(53)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.character["endurance"], 20)
        self.assertEqual(w.completed_book_events, set())
        w.redo_action()
        self.assertEqual(w.character["endurance"], 18)
        self.assertEqual(w.completed_book_events, {49})

    def test_book_event_stat_caps_and_items(self):
        from book_events import apply_entry
        cat = {"paragraphs": {"75": {"status": "verifie", "mode": "automatique",
               "effects": [{"kind": "stat", "key": "chance", "amount": 3},
                           {"kind": "item", "name": "Clé 111"}]}}}
        character = {"chance": 7, "initial": {"chance": 8}, "inventory": []}
        completed = set()
        self.assertTrue(apply_entry(character, completed, 75, cat))
        self.assertEqual(character["chance"], 8)
        self.assertEqual(character["inventory"], ["Clé 111"])
        self.assertFalse(apply_entry(character, completed, 75, cat))

    def test_scripted_roll_resolves_fortune_and_skill(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))["paragraphs"]
        character = {"habilete": 8, "chance": 9, "endurance": 15}
        self.assertEqual(resolve_roll(data["47"]["roll"], 6, character)["target"], 158)
        self.assertEqual(resolve_roll(data["47"]["roll"], 5, character)["target"], 298)
        self.assertEqual(resolve_roll(data["53"]["roll"], 8, character)["target"], 155)
        fail = resolve_roll(data["53"]["roll"], 9, character)
        self.assertEqual(fail["target"], 300)
        self.assertEqual(fail["effects"][0]["amount"], -1)
        self.assertEqual(resolve_roll(data["55"]["roll"], 9, character)["target"], 7)
        self.assertEqual(resolve_roll(data["55"]["roll"], 10, character)["target"], 166)
        self.assertEqual(resolve_roll(data["243"]["roll"], 3, character)["effects"][0]["amount"], -3)
        self.assertEqual(resolve_roll(data["243"]["roll"], 4, character)["effects"][0]["amount"], -1)

    def test_scripted_roll_applies_effects_and_can_undo(self):
        from book_events import DATA_PATH
        w = self.window
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.book_event_catalogue = data
        w.paragraphs = {53: "Une porte.", 300: "Un couloir."}
        w.go_to(53)
        with patch.object(w, "_roll", return_value=([4, 5], 9)):
            w.resolve_book_roll(53)
        self.assertEqual(w.current_paragraph, 300)
        self.assertEqual(w.character["endurance"], 19)
        self.assertIn(53, w.completed_book_events)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 53)
        self.assertEqual(w.character["endurance"], 20)
        self.assertNotIn(53, w.completed_book_events)
        w.redo_action()
        self.assertEqual(w.current_paragraph, 300)
        self.assertEqual(w.character["endurance"], 19)
        self.assertIn(53, w.completed_book_events)

    def test_gold_and_optional_rewards_are_explicit(self):
        from book_events import DATA_PATH, apply_option, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        character = {"gold": 1, "provisions": 10, "chance": 5,
                     "initial": {"chance": 8}, "inventory": []}
        completed, optional = set(), set()
        self.assertTrue(apply_entry(character, completed, 147, data))
        self.assertEqual(character["gold"], 2)
        self.assertEqual(character["chance"], 7)
        self.assertFalse(apply_option(character, optional, 50, "missing", data))
        self.assertTrue(apply_option(character, optional, 50, "cle9", data))
        self.assertFalse(apply_option(character, optional, 50, "cle9", data))
        self.assertIn("Clé de bronze 9", character["inventory"])
        self.assertEqual(character["provisions"], 10)
        self.assertTrue(apply_option(character, optional, 38, "oeufs", data))
        self.assertEqual(character["provisions"], 12)

    def test_optional_reward_undo_and_redo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {50: "La petite clé de bronze."}
        w.go_to(50)
        self.assertNotIn("Clé de bronze 9", w.character["inventory"])
        w.apply_optional_book_event(50, "cle9")
        self.assertIn("Clé de bronze 9", w.character["inventory"])
        self.assertIn("50:cle9", w.completed_optional_events)
        w.undo_action()
        self.assertNotIn("Clé de bronze 9", w.character["inventory"])
        self.assertNotIn("50:cle9", w.completed_optional_events)
        w.redo_action()
        self.assertIn("Clé de bronze 9", w.character["inventory"])
        self.assertIn("50:cle9", w.completed_optional_events)

    def test_special_combat_still_shows_prepare_button(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {16: "OGRE HABILETÉ: 8 ENDURANCE: 10"}
        w.go_to(16)
        labels = [w.event_layout.itemAt(i).widget().text()
                  for i in range(w.event_layout.count())
                  if hasattr(w.event_layout.itemAt(i).widget(), "text")]
        self.assertTrue(any("Préparer le combat" in label for label in labels))

    def test_luck_trial_checks_score_before_spending_point(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {74: "Épreuve de Chance", 279: "Vous résistez.", 118: "Échec."}
        w.character["chance"] = 8
        w.go_to(74)
        with patch.object(w, "_roll", return_value=([4, 4], 8)):
            w.resolve_book_roll(74)
        self.assertEqual(w.current_paragraph, 279)
        self.assertEqual(w.character["chance"], 7)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 74)
        self.assertEqual(w.character["chance"], 8)
        self.assertNotIn(74, w.completed_book_events)
        with patch.object(w, "_roll", return_value=([5, 4], 9)):
            w.resolve_book_roll(74)
        self.assertEqual(w.current_paragraph, 118)
        self.assertEqual(w.character["chance"], 7)

    def test_book_combat_is_prepared_once_without_resetting_enemy(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {8: "Le Barbare attaque.", 16: "L'Ogre attaque."}
        w.go_to(8)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Barbare", 7, 6))
        w.enemy_endurance.setValue(2)
        w.go_to(8)
        self.assertEqual(w.enemy_endurance.value(), 2)
        w.go_to(16)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Ogre", 8, 10))
        self.assertEqual(w.prepared_book_encounters, {8, 16})
        w.undo_action()
        self.assertEqual(w.enemy_endurance.value(), 2)
        self.assertEqual(w.prepared_book_encounters, {8})
        w.redo_action()
        self.assertEqual(w.enemy_endurance.value(), 10)

    def test_sequence_combat_is_not_falsely_autoprepared(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {20: "Quatre Nains attaquent.", 86: "Le Crocodile."}
        w.go_to(20)
        self.assertEqual(w.enemy_name.text(), "Nain 1")
        w.go_to(86)
        # Le combat limité ne modifie pas la progression des Nains.
        self.assertEqual(w.enemy_name.text(), "Crocodile")
        self.assertEqual(w.prepared_book_encounters, set())
        self.assertEqual(w.book_combat_sequence["index"], 0)
        self.assertEqual(w.crocodile_combat["assaults"], 0)

    def test_holy_water_restores_to_floor_without_lowering_current_stats(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        char = {"endurance": 7, "habilete": 5, "chance": 4,
                "initial": {"endurance": 20, "habilete": 11, "chance": 9},
                "inventory": []}
        done = set()
        self.assertTrue(apply_entry(char, done, 109, data))
        self.assertEqual((char["endurance"], char["habilete"], char["chance"]),
                         (18, 10, 8))
        char2 = {"endurance": 20, "habilete": 11, "chance": 8,
                 "initial": {"endurance": 20, "habilete": 11, "chance": 9},
                 "inventory": []}
        self.assertTrue(apply_entry(char2, set(), 109, data))
        self.assertEqual((char2["endurance"], char2["habilete"], char2["chance"]),
                         (20, 11, 9))

    def test_book_routes_follow_inventory_and_gold(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))["paragraphs"]
        char = {"gold": 0, "inventory": []}
        self.assertEqual([r["target"] for r in available_routes(char, data["264"])], [129])
        self.assertEqual([r["target"] for r in available_routes(char, data["204"])], [280, 377])
        char["inventory"].append("Clé du Hangar à Bateaux")
        char["gold"] = 1
        self.assertEqual([r["target"] for r in available_routes(char, data["264"])], [80])
        self.assertEqual([r["target"] for r in available_routes(char, data["204"])], [130, 280, 377])

    def test_book_route_buttons_respect_inventory(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {264: "La porte résiste.", 80: "Porte ouverte.", 129: "Rivière."}
        w.character["inventory"] = []
        w.go_to(264)
        def destinations():
            return [w.choice_layout.itemAt(i).widget().text()
                    for i in range(w.choice_layout.count())
                    if hasattr(w.choice_layout.itemAt(i).widget(), "text")]
        self.assertTrue(any("§129" in label for label in destinations()))
        self.assertFalse(any("§80" in label for label in destinations()))
        w.character["inventory"].append("Clé du Hangar à Bateaux")
        w.go_to(264)
        self.assertTrue(any("§80" in label for label in destinations()))
        self.assertFalse(any("§129" in label for label in destinations()))

    def test_luck_fall_paragraph_18_success_and_failure(self):
        from book_events import DATA_PATH
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w = self.window
        w.book_event_catalogue = data
        w.paragraphs = {18: "Une fosse.", 261: "La bifurcation.", 348: "La chute."}
        w.character["chance"] = 8
        w.go_to(18)
        with patch.object(w, "_roll", return_value=([3, 5], 8)):
            w.resolve_book_roll(18)
        self.assertEqual((w.current_paragraph, w.character["chance"],
                          w.character["endurance"]), (261, 7, 20))
        w.undo_action()
        self.assertEqual((w.current_paragraph, w.character["chance"],
                          w.character["endurance"]), (18, 8, 20))
        with patch.object(w, "_roll", return_value=([5, 4], 9)):
            w.resolve_book_roll(18)
        self.assertEqual((w.current_paragraph, w.character["chance"],
                          w.character["endurance"]), (348, 7, 19))

    def test_optional_luck_trial_does_not_fire_on_entry(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {82: "Une boîte près du dormeur.", 208: "Couloir.", 147: "Boîte."}
        w.go_to(82)
        self.assertEqual(w.character["chance"], 8)
        self.assertEqual(w.completed_book_events, set())
        labels = [w.event_layout.itemAt(i).widget().text()
                  for i in range(w.event_layout.count())
                  if hasattr(w.event_layout.itemAt(i).widget(), "text")]
        self.assertTrue(any("Lancer le dé" in t for t in labels))
        self.assertTrue(any("§208" in w.choice_layout.itemAt(i).widget().text()
                            for i in range(w.choice_layout.count())
                            if hasattr(w.choice_layout.itemAt(i).widget(), "text")))

    def test_direct_text_links_respect_scripted_routes(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {204: "Allez au 130.", 130: "Jeu.", 280: "Sortie.", 377: "Combat."}
        w.character["gold"] = 0
        w.go_to(204)
        with patch.object(QMessageBox, "information") as message:
            w.follow_link(QUrl("paragraph:130"))
            self.assertEqual(w.current_paragraph, 204)
            message.assert_called_once()
        w.character["gold"] = 1
        w.follow_link(QUrl("paragraph:130"))
        self.assertEqual(w.current_paragraph, 130)

    def test_paragraph_91_success_two_rolls_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {91: "Vous trichez aux cartes.", 131: "Vous partez." , 20: "Les Nains attaquent."}
        w.character["chance"] = 8
        w.character["gold"] = 1
        w.go_to(91)
        with patch.object(w, "_roll", side_effect=[
                ([3, 5], 8), ([4, 6], 10)]) as rolls:
            w.resolve_book_roll(91)
            self.assertEqual(rolls.call_count, 2)
        self.assertEqual(w.current_paragraph, 131)
        self.assertEqual((w.character["chance"], w.character["gold"]), (7, 11))
        self.assertIn(91, w.completed_book_events)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 91)
        self.assertEqual((w.character["chance"], w.character["gold"]), (8, 1))
        self.assertNotIn(91, w.completed_book_events)
        w.redo_action()
        self.assertEqual(w.current_paragraph, 131)
        self.assertEqual((w.character["chance"], w.character["gold"]), (7, 11))

    def test_paragraph_91_failure_one_roll_no_gold(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {91: "Vous trichez aux cartes.", 20: "Les Nains attaquent."}
        w.character["chance"] = 8
        w.character["gold"] = 1
        w.go_to(91)
        with patch.object(w, "_roll", return_value=([5, 5], 10)) as rolls:
            w.resolve_book_roll(91)
            rolls.assert_called_once_with(2)
        self.assertEqual(w.current_paragraph, 20)
        self.assertEqual((w.character["chance"], w.character["gold"]), (7, 1))

    def test_scripted_roll_missing_destination_does_not_spend_luck(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {91: "Vous trichez aux cartes."}
        w.go_to(91)
        with patch.object(w, "_roll", return_value=([1, 1], 2)), patch.object(QMessageBox, "warning"):
            w.resolve_book_roll(91)
        self.assertEqual(w.current_paragraph, 91)
        self.assertEqual(w.character["chance"], 8)
        self.assertEqual(w.character["gold"], 1)
        self.assertNotIn(91, w.completed_book_events)

    def test_four_dwarves_sequence_prepares_next_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {20: "Quatre Nains attaquent.", 376: "Victoire."}
        w.go_to(20)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Nain 1", 7, 6))
        self.assertEqual(w.book_combat_sequence, {"paragraph": 20, "index": 0})
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Nain 2", 7, 7))
        self.assertEqual(w.book_combat_sequence["index"], 1)
        w.undo_action()
        self.assertEqual(w.book_combat_sequence["index"], 0)
        self.assertEqual(w.enemy_endurance.value(), 2)
        w.redo_action()
        self.assertEqual(w.book_combat_sequence["index"], 1)
        self.assertEqual(w.enemy_name.text(), "Nain 2")

    def test_four_dwarves_victory_goes_to_376(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {20: "Quatre Nains attaquent.", 376: "Victoire."}
        w.go_to(20)
        w.book_combat_sequence["index"] = 3
        w._set_book_enemy({"name": "Nain 4", "skill": 5, "stamina": 2})
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 376)
        self.assertIsNone(w.book_combat_sequence)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 20)
        self.assertEqual(w.book_combat_sequence["index"], 3)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_sequence_does_not_advance_on_other_paragraphs(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {20: "Nains.", 91: "Cartes."}
        w.go_to(20)
        w.go_to(91)
        w.enemy_endurance.setValue(0)
        w._advance_scripted_sequence()
        self.assertEqual(w.book_combat_sequence["index"], 0)

    def test_crocodile_two_assaults_then_diversion(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {86: "Le Crocodile.", 259: "Victoire.", 350: "Remous."}
        w.go_to(86)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Crocodile", 7, 6))
        with patch.object(w, "_roll", return_value=([3, 3], 6)):
            # 8+6 against 7+6 : two successful assaults, no Chance.
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
                w.combat_round()
                w.combat_round()
        self.assertEqual(w.crocodile_combat["assaults"], 2)
        self.assertEqual(w.enemy_endurance.value(), 2)
        with patch.object(w, "_roll") as dice:
            w.combat_round()
            dice.assert_not_called()
        w.choose_crocodile_strategy("diversion")
        self.assertEqual(w.crocodile_combat["phase"], "diversion")
        with patch.object(w, "_roll", return_value=([3, 3], 6)), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 350)
        self.assertIsNone(w.crocodile_combat)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 86)
        self.assertEqual(w.crocodile_combat["phase"], "diversion")
        self.assertEqual(w.crocodile_combat["assaults"], 2)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_crocodile_victory_and_continue_choice(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {86: "Le Crocodile.", 259: "Victoire.", 350: "Remous."}
        w.go_to(86)
        with patch.object(w, "_roll", return_value=([3, 3], 6)), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
            w.combat_round()
        w.choose_crocodile_strategy("continue")
        self.assertEqual(w.crocodile_combat["phase"], "continue")
        with patch.object(w, "_roll", return_value=([3, 3], 6)), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 259)
        self.assertIsNone(w.crocodile_combat)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 86)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_crocodile_tied_assault_counts_and_restores(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {86: "Le Crocodile.", 259: "Victoire.", 350: "Remous."}
        w.go_to(86)
        # Player 8+5 = 13, crocodile 7+6 = 13.
        with patch.object(w, "_roll", side_effect=[
                ([3, 3], 6), ([2, 3], 5)]):
            w.combat_round()
        self.assertEqual(w.crocodile_combat["assaults"], 1)
        self.assertEqual(w.enemy_endurance.value(), 6)
        w.undo_action()
        self.assertEqual(w.crocodile_combat["assaults"], 0)

    def test_escape_gate_for_ogre_and_luckless_penalty(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {16: "OGRE HABILETÉ: 8 ENDURANCE: 10", 269: "Couloir."}
        w.go_to(16)
        with patch.object(QMessageBox, "question") as question:
            w.escape_scripted_combat(16)
            question.assert_not_called()
        self.assertEqual(w.current_paragraph, 16)
        # Deux égalités comptent comme deux assauts.
        with patch.object(w, "_roll", return_value=([3, 3], 6)):
            w.combat_round()
            w.combat_round()
        self.assertEqual(w.book_combat_assaults[16], 2)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(16)
        self.assertEqual((w.current_paragraph, w.character["endurance"],
                          w.character["chance"]), (269, 18, 8))
        w.undo_action()
        self.assertEqual((w.current_paragraph, w.character["endurance"],
                          w.book_combat_assaults[16]), (16, 20, 2))

    def test_escape_uses_chance_and_restores_on_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {8: "BARBARE HABILETÉ: 7 ENDURANCE: 6", 189: "Couloir."}
        w.go_to(8)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
                patch.object(w, "_roll", return_value=([4, 4], 8)):
            w.escape_scripted_combat(8)
        self.assertEqual((w.current_paragraph, w.character["endurance"],
                          w.character["chance"]), (189, 19, 7))
        w.undo_action()
        self.assertEqual((w.current_paragraph, w.character["endurance"],
                          w.character["chance"]), (8, 20, 8))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
                patch.object(w, "_roll", return_value=([6, 6], 12)):
            w.escape_scripted_combat(8)
        self.assertEqual((w.current_paragraph, w.character["endurance"],
                          w.character["chance"]), (189, 17, 7))

    def test_escape_dwarves_abandons_sequence_and_undo_restores(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {20: "Quatre Nains attaquent.", 291: "Porte."}
        w.go_to(20)
        self.assertEqual(w.book_combat_sequence["index"], 0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(20)
        self.assertEqual(w.current_paragraph, 291)
        self.assertIsNone(w.book_combat_sequence)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 20)
        self.assertEqual(w.book_combat_sequence["index"], 0)

    def test_escape_engine_damage_rules(self):
        from book_events import escape_damage, flee_available
        self.assertEqual(escape_damage(8), (2, 0))
        self.assertEqual(escape_damage(8, 8), (1, 1))
        self.assertEqual(escape_damage(8, 9), (3, 1))
        self.assertFalse(flee_available({"escape_target": 269, "escape_after_assaults": 2}, 1, 10, 20))
        self.assertTrue(flee_available({"escape_target": 269, "escape_after_assaults": 2}, 2, 10, 20))
        self.assertFalse(flee_available({"escape_target": 269}, 0, 0, 20))

    def test_crocodile_victory_reward_from_paragraph_259(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        character = {"habilete": 7, "chance": 5,
                     "initial": {"habilete": 10, "chance": 8}, "inventory": []}
        completed = set()
        self.assertTrue(apply_entry(character, completed, 259, data))
        self.assertEqual((character["habilete"], character["chance"]), (8, 7))
        self.assertFalse(apply_entry(character, completed, 259, data))

    def test_paragraph_189_has_both_choices_and_links(self):
        """Le §189 propose §90 ET §25, y compris avec « irez alors »."""
        passage = ("Vous pouvez traverser cette pièce (et vous rendre au 90), "
                   "ou vous attarder pour contempler les tableaux "
                   "(vous irez alors au 25).")
        self.assertEqual([target for _, _, target in destinations(passage)], [90, 25])
        html = render_links(passage, {25, 90})
        self.assertIn('href="paragraph:90"', html)
        self.assertIn('href="paragraph:25"', html)
        w = self.window
        self.assertEqual([choice["target"] for choice in w._paragraph_choices(passage)],
                         [90, 25])

    def test_destination_irez_alors_whitespace_variants(self):
        for expression in ("vous irez alors au 25", "vous irez au 25",
                           "irez alors au 25", "vous allez alors au 25",
                           "vous allez au 25"):
            with self.subTest(expression=expression):
                self.assertEqual([n for _, _, n in destinations(expression)], [25])

    def test_real_book_missing_destination_forms(self):
        """Formulations contrôlées dans les §§36, 66, 67, 78, 130 et 330."""
        examples = [
            ("vous irez dans ce cas au 353", 353),
            ("vous allez dans ce cas au 104", 104),
            ("en vous rendant au 177", 177),
            ("en allant au 237", 237),
            ("Rendez-vous après au 280", 280),
            ("Rendez-vous maintenant au 81", 81),
            ("en vous rendant au 345", 345),
        ]
        for phrase, target in examples:
            with self.subTest(phrase=phrase):
                self.assertEqual([n for _, _, n in destinations(phrase)], [target])
                self.assertIn(f'href="paragraph:{target}"',
                              render_links(phrase, {target}))

    def test_real_pdf_detects_second_choices_across_17_paragraphs(self):
        """Audit ciblé fondé sur les passages de l'édition PDF fournie."""
        if not self.paragraphs:
            self.skipTest("PDF de référence absent")
        expected = {
            36: 353, 66: 104, 67: 177, 77: 345, 78: 237,
            130: 280, 151: 158, 156: 92, 177: 391, 211: 173,
            213: 314, 234: 43, 291: 315, 295: 48, 306: 291,
            315: 306, 330: 81,
        }
        for paragraph, target in expected.items():
            with self.subTest(paragraph=paragraph, target=target):
                self.assertIn(paragraph, self.paragraphs)
                choices = [number for _, _, number in
                           destinations(self.paragraphs[paragraph])]
                self.assertIn(target, choices)

    def test_magic_sword_optional_bonus_updates_initial_maximum(self):
        from book_events import DATA_PATH, apply_entry, apply_option
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"habilete": 7, "chance": 6,
                "initial": {"habilete": 9, "chance": 9},
                "inventory": ["Épée"]}
        done, options = set(), set()
        self.assertTrue(apply_entry(hero, done, 27, data))
        self.assertEqual(hero["chance"], 8)
        self.assertEqual(hero["habilete"], 7)
        self.assertEqual(hero["initial"]["habilete"], 9)
        self.assertTrue(apply_option(hero, options, 27, "epee_magique", data))
        self.assertEqual(hero["initial"]["habilete"], 11)
        self.assertEqual(hero["habilete"], 9)
        self.assertNotIn("Épée", hero["inventory"])
        self.assertIn("Épée magique", hero["inventory"])
        self.assertFalse(apply_option(hero, options, 27, "epee_magique", data))

    def test_cyclops_gem_option_requires_item(self):
        from book_events import DATA_PATH, apply_option, available_options
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["31"]
        hero = {"habilete": 7, "initial": {"habilete": 10},
                "inventory": []}
        done = set()
        self.assertEqual(available_options(hero, entry, done, 31), [])
        self.assertFalse(apply_option(hero, done, 31, "utiliser_pierre", data))
        self.assertEqual(hero["habilete"], 7)
        hero["inventory"].append("Pierre précieuse de la statue")
        self.assertEqual(len(available_options(hero, entry, done, 31)), 1)
        self.assertTrue(apply_option(hero, done, 31, "utiliser_pierre", data))
        self.assertEqual(hero["habilete"], 9)
        self.assertIn("Pierre précieuse de la statue", hero["inventory"])

    def test_cheese_option_is_consumed_and_luck_awarded_once(self):
        from book_events import DATA_PATH, apply_option, available_options
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["32"]
        hero = {"chance": 5, "initial": {"chance": 8}, "inventory": []}
        done = set()
        self.assertFalse(apply_option(hero, done, 32, "jeter_fromage", data))
        hero["inventory"].append("Fromage")
        self.assertEqual(len(available_options(hero, entry, done, 32)), 1)
        self.assertTrue(apply_option(hero, done, 32, "jeter_fromage", data))
        self.assertEqual(hero["chance"], 7)
        self.assertNotIn("Fromage", hero["inventory"])
        self.assertFalse(apply_option(hero, done, 32, "jeter_fromage", data))

    def test_sword_and_cheese_actions_restore_with_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {27: "Épée magique.", 32: "Rats."}
        w.character["inventory"] = ["Épée", "Fromage"]
        w.character["habilete"] = 7
        w.go_to(27)
        initial_max = w.character["initial"]["habilete"]
        w.apply_optional_book_event(27, "epee_magique")
        self.assertEqual(w.character["initial"]["habilete"], initial_max + 2)
        w.undo_action()
        self.assertEqual(w.character["initial"]["habilete"], initial_max)
        self.assertIn("Épée", w.character["inventory"])
        self.assertNotIn("Épée magique", w.character["inventory"])
        w.go_to(32)
        w.apply_optional_book_event(32, "jeter_fromage")
        self.assertNotIn("Fromage", w.character["inventory"])
        w.undo_action()
        self.assertIn("Fromage", w.character["inventory"])

    def test_cursed_helmet_is_locked_and_skill_penalty_once(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"habilete": 9, "initial": {"habilete": 10},
                "inventory": [], "locked_items": []}
        visited = set()
        self.assertTrue(apply_entry(hero, visited, 202, data))
        self.assertEqual(hero["habilete"], 8)
        self.assertIn("Casque ensorcelé", hero["inventory"])
        self.assertIn("Casque ensorcelé", hero["locked_items"])
        self.assertFalse(apply_entry(hero, visited, 202, data))
        self.assertEqual(hero["habilete"], 8)

    def test_cursed_helmet_cannot_be_removed_in_ui_and_undo_restores(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {202: "Casque maudit.", 87: "Sortie."}
        w.go_to(202)
        self.assertIn("Casque ensorcelé", w.character["locked_items"])
        idx = w.character["inventory"].index("Casque ensorcelé")
        w.inventory_list.setCurrentRow(idx)
        with patch.object(QMessageBox, "information") as message:
            w.remove_item()
            message.assert_called_once()
        self.assertIn("Casque ensorcelé", w.character["inventory"])
        w.undo_action()
        self.assertNotIn("Casque ensorcelé", w.character.get("inventory", []))
        self.assertNotIn("Casque ensorcelé", w.character.get("locked_items", []))

    def test_river_sword_acquired_and_discarded_at_153(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"endurance": 20, "initial": {"endurance": 20},
                "inventory": ["Épée"], "locked_items": []}
        visited = set()
        self.assertTrue(apply_entry(hero, visited, 344, data))
        self.assertIn("Épée trouvée dans la rivière", hero["inventory"])
        self.assertTrue(apply_entry(hero, visited, 153, data))
        self.assertEqual(hero["endurance"], 19)
        self.assertNotIn("Épée trouvée dans la rivière", hero["inventory"])
        self.assertIn("Épée", hero["inventory"])
        self.assertFalse(apply_entry(hero, visited, 153, data))

    def test_river_sword_discard_keeps_other_equipment_and_routes(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["344"]
        self.assertEqual([r["target"] for r in available_routes(
            {"inventory": ["Épée"]}, entry)], [56, 153])
        hero = {"endurance": 9, "initial": {"endurance": 20},
                "inventory": ["Épée magique", "Armure de cuir"]}
        from book_events import apply_entry
        self.assertTrue(apply_entry(hero, set(), 153, data))
        self.assertEqual(hero["endurance"], 8)
        self.assertEqual(hero["inventory"], ["Épée magique", "Armure de cuir"])

    def test_river_sword_combat_bonus_only_while_equipped(self):
        from book_events import combat_skill, equip_weapon
        hero = {"habilete": 8, "initial": {"habilete": 10},
                "inventory": ["Épée", "Épée trouvée dans la rivière"],
                "equipped_weapon": "Épée"}
        self.assertEqual(combat_skill(hero), 8)
        self.assertTrue(equip_weapon(hero, "Épée trouvée dans la rivière"))
        self.assertEqual(combat_skill(hero), 9)
        self.assertEqual(hero["habilete"], 8)
        self.assertTrue(equip_weapon(hero, "Épée"))
        self.assertEqual(combat_skill(hero), 8)
        self.assertFalse(equip_weapon(hero, "Épée inexistante"))

    def test_magic_sword_bonus_disappears_and_returns_on_switch(self):
        from book_events import DATA_PATH, apply_entry, apply_option, equip_weapon, combat_skill
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"habilete": 8, "chance": 7,
                "initial": {"habilete": 10, "chance": 9},
                "inventory": ["Épée", "Épée trouvée dans la rivière"],
                "equipped_weapon": "Épée"}
        self.assertTrue(apply_entry(hero, set(), 27, data))
        self.assertTrue(apply_option(hero, set(), 27, "epee_magique", data))
        self.assertEqual((hero["habilete"], hero["initial"]["habilete"]), (10, 12))
        self.assertEqual(hero["equipped_weapon"], "Épée magique")
        self.assertTrue(equip_weapon(hero, "Épée trouvée dans la rivière"))
        self.assertEqual((hero["habilete"], hero["initial"]["habilete"]), (8, 10))
        self.assertEqual(combat_skill(hero), 9)
        self.assertTrue(equip_weapon(hero, "Épée magique"))
        self.assertEqual((hero["habilete"], hero["initial"]["habilete"]), (10, 12))
        self.assertFalse(equip_weapon(hero, "Épée magique"))

    def test_weapon_switch_is_undoable_and_not_a_stat_bonus_from_river(self):
        w = self.window
        w.character["inventory"].append("Épée trouvée dans la rivière")
        w.character["equipped_weapon"] = "Épée"
        w._refresh_character()
        w.change_weapon("Épée trouvée dans la rivière")
        self.assertEqual(w.character["equipped_weapon"], "Épée trouvée dans la rivière")
        self.assertEqual(w.character["habilete"], 8)
        w.undo_action()
        self.assertEqual(w.character["equipped_weapon"], "Épée")
        w.redo_action()
        self.assertEqual(w.character["equipped_weapon"], "Épée trouvée dans la rivière")

    def test_river_sword_replaces_old_weapon_at_56(self):
        from book_events import DATA_PATH, apply_entry, equipped_weapon, combat_skill
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"habilete": 8, "initial": {"habilete": 10},
                "inventory": ["Épée"], "equipped_weapon": "Épée"}
        visited = set()
        self.assertTrue(apply_entry(hero, visited, 344, data))
        self.assertTrue(apply_entry(hero, visited, 56, data))
        self.assertNotIn("Épée", hero["inventory"])
        self.assertEqual(equipped_weapon(hero), "Épée trouvée dans la rivière")
        self.assertEqual(combat_skill(hero), 9)

    def test_moon_shield_requires_relinquishing_an_item(self):
        from book_events import SHIELD_NAME, take_moon_shield
        hero = {"inventory": ["Épée", "Casque ensorcelé"],
                "locked_items": ["Casque ensorcelé"],
                "equipped_weapon": "Épée"}
        before = list(hero["inventory"])
        self.assertFalse(take_moon_shield(hero, "Casque ensorcelé"))
        self.assertFalse(take_moon_shield(hero, "Objet imaginaire"))
        self.assertEqual(hero["inventory"], before)
        self.assertTrue(take_moon_shield(hero, "Épée"))
        self.assertIn(SHIELD_NAME, hero["inventory"])
        self.assertNotIn("Épée", hero["inventory"])
        self.assertIsNone(hero["equipped_weapon"])
        self.assertFalse(take_moon_shield(hero, "Casque ensorcelé"))
        self.assertTrue(hero["shield_equipped"])

    def test_moon_shield_reduces_damage_only_on_six(self):
        from book_events import shield_damage
        self.assertEqual(shield_damage(2, 6), 1)
        self.assertEqual(shield_damage(1, 6), 0)
        self.assertEqual(shield_damage(3, 6), 2)
        self.assertEqual(shield_damage(2, 5), 2)
        with self.assertRaises(ValueError):
            shield_damage(2, 7)

    def test_moon_shield_combat_and_undo(self):
        from book_events import SHIELD_NAME
        w = self.window
        w.character["inventory"].append(SHIELD_NAME)
        w.character["shield_equipped"] = True
        w._refresh_character()
        w.enemy_skill.setValue(12)
        w.enemy_endurance.setValue(6)
        with patch.object(w, "_roll", side_effect=[
                ([6, 6], 12), ([1, 1], 2), ([6], 6)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.character["endurance"], 19)
        w.undo_action()
        self.assertEqual(w.character["endurance"], 20)

    def test_moon_shield_pickup_and_undo(self):
        from book_events import DATA_PATH, SHIELD_NAME
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {155: "Le bouclier au croissant.", 300: "Couloir."}
        w.go_to(155)
        with patch("main.QInputDialog.getItem", return_value=("Épée", True)):
            w.take_book_shield()
        self.assertIn(SHIELD_NAME, w.character["inventory"])
        self.assertNotIn("Épée", w.character["inventory"])
        w.undo_action()
        self.assertIn("Épée", w.character["inventory"])
        self.assertNotIn(SHIELD_NAME, w.character["inventory"])

    def test_piranhas_stamina_matches_book_six_outcomes(self):
        from book_events import piranha_stamina
        self.assertEqual(piranha_stamina(True), 1)
        self.assertEqual(piranha_stamina(False, 1), 5)
        self.assertEqual(piranha_stamina(False, 2), 5)
        for roll in (3, 4, 5, 6):
            self.assertEqual(piranha_stamina(False, roll), 1)
        with self.assertRaises(ValueError):
            piranha_stamina(False)
        with self.assertRaises(ValueError):
            piranha_stamina(False, 7)

    def test_piranhas_wounded_crocodile_needs_no_extra_roll(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {86: "Crocodile.", 350: "Piranhas.", 7: "Rive."}
        w.go_to(86)
        w.character["initial"]["chance"] = 10
        w.crocodile_combat["assaults"] = 2
        w.crocodile_combat["wounded"] = True
        w.choose_crocodile_strategy("diversion")
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 350)
        self.assertTrue(w.piranha_source_wounded)
        self.assertEqual(w.piranha_combat["stamina"], 1)
        self.assertEqual(w.enemy_endurance.value(), 1)
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 7)
        self.assertIn(350, w.completed_book_events)
        self.assertEqual(w.character["chance"], 9)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 350)
        self.assertEqual(w.enemy_endurance.value(), 1)
        self.assertEqual(w.character["chance"], 8)

    def test_piranhas_healthy_crocodile_roll_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {350: "Piranhas.", 7: "Rive."}
        w.piranha_source_wounded = False
        w.go_to(350)
        self.assertEqual(w.piranha_combat["status"], "roll_pending")
        with patch.object(w, "_roll", return_value=([2], 2)):
            w.roll_piranha_target()
        self.assertEqual((w.enemy_skill.value(), w.enemy_endurance.value()), (5, 5))
        self.assertEqual(w.piranha_combat["status"], "fighting")
        w.undo_action()
        self.assertEqual(w.piranha_combat["status"], "roll_pending")
        with patch.object(w, "_roll", return_value=([5], 5)):
            w.roll_piranha_target()
        self.assertEqual(w.enemy_endurance.value(), 1)

    def test_piranhas_cannot_skip_victory_via_text_link(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {350: "Piranhas. Rendez-vous au 7.", 7: "Rive."}
        w.piranha_source_wounded = True
        w.go_to(350)
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:7"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 350)
        self.assertTrue(w.piranha_source_wounded)

    def test_rotten_bridge_209_six_falls_otherwise_47(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["209"]["roll"]
        for total in range(1, 7):
            with self.subTest(total=total):
                result = resolve_roll(roll, total, self.window.character)
                self.assertEqual(result["target"], 158 if total == 6 else 47)

    def test_rotten_bridge_209_roll_navigates_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {209: "Pont.", 47: "Vous tenez bon.", 158: "Chute."}
        w.go_to(209)
        with patch.object(w, "_roll", return_value=([5], 5)):
            w.resolve_book_roll(209)
        self.assertEqual(w.current_paragraph, 47)
        self.assertIn(209, w.completed_book_events)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 209)
        self.assertNotIn(209, w.completed_book_events)
        with patch.object(w, "_roll", return_value=([6], 6)):
            w.resolve_book_roll(209)
        self.assertEqual(w.current_paragraph, 158)

    def test_silver_crucifix_is_item_not_immediate_gold(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"gold": 2, "inventory": []}
        done = set()
        self.assertTrue(apply_entry(hero, done, 170, data))
        self.assertEqual(hero["gold"], 2)
        self.assertIn("Crucifix en argent (valeur 4 PO)", hero["inventory"])
        self.assertFalse(apply_entry(hero, done, 170, data))

    def test_wooden_stakes_273_are_optional_and_once(self):
        from book_events import DATA_PATH, apply_entry, apply_option
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"inventory": []}
        done, selected = set(), set()
        self.assertFalse(apply_entry(hero, done, 273, data))
        self.assertNotIn("Cinq piquets de bois", hero["inventory"])
        self.assertTrue(apply_option(hero, selected, 273, "cinq_piquets", data))
        self.assertIn("Cinq piquets de bois", hero["inventory"])
        self.assertFalse(apply_option(hero, selected, 273, "cinq_piquets", data))

    def test_dwarves_reward_376_luck_and_optional_coins_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {376: "Pièces de cuivre.", 291: "Couloir."}
        w.character["chance"] = 3
        w.character["gold"] = 1
        w._refresh_character()
        w.go_to(376)
        self.assertEqual(w.character["chance"], 6)
        self.assertEqual(w.character["gold"], 1)
        w.apply_optional_book_event(376, "pieces_cuivre")
        self.assertEqual(w.character["gold"], 5)
        w.undo_action()
        self.assertEqual(w.character["gold"], 1)
        self.assertEqual(w.character["chance"], 6)
        w.undo_action()
        self.assertEqual(w.character["chance"], 3)
        self.assertEqual(w.current_paragraph, None)

    def test_mandatory_dice_links_cannot_skip_roll_209(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {
            209: "Sur 6, rendez-vous au 158. Sinon rendez-vous au 47.",
            47: "Couloir.", 158: "Rivière."}
        w.go_to(209)
        with patch.object(QMessageBox, "information") as message:
            w.follow_link(QUrl("paragraph:158"))
            message.assert_called_once()
        self.assertEqual(w.current_paragraph, 209)
        self.assertEqual(w._paragraph_choices(w.paragraphs[209])[-1]["target"], 47)
        with patch.object(w, "_roll", return_value=([6], 6)):
            w.resolve_book_roll(209)
        self.assertEqual(w.current_paragraph, 158)

    def test_navigation_and_html(self):
        self.assertEqual([n for _, _, n in destinations('Rendez-\n vous au 12. Allez au 4.')], [12, 4])
        rendered = render_links('<script> Rendez-vous au 12 et allez au 8.', {12})
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('href="paragraph:12"', rendered)
        self.assertNotIn('href="paragraph:8"', rendered)

    def test_rules(self):
        self.assertEqual(encounters('GOBELIN HABILETÉ 7 ENDURANCE 8')[0]['skill'], 7)
        self.assertEqual(stat_events("Vous perdez 2 points d'endurance.")[0]['amount'], -2)
        self.assertEqual(stat_events("Si vous tombez, vous perdez 2 points d'endurance."), [])

    def test_meal_and_undo(self):
        w = self.window
        w.character['endurance'] = 19
        w.eat_meal()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (20, 9))
        w.undo_action()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (19, 10))
        w.redo_action()
        self.assertEqual(w.character['provisions'], 9)

    def test_atomic_save_and_containment(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'save.json'
            self.window._write_atomic(path, {'test': 'français'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'test': 'français'})
            self.assertEqual(list(Path(folder).iterdir()), [path])
            self.assertTrue(bifurk.within_directory(path, ROOT))
            self.assertFalse(bifurk.within_directory(ROOT / '..' / 'outside.json', ROOT))

    def test_import_is_local_and_identical(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(bifurk, 'BOOKS_DIR', Path(folder)):
            target = Path(bifurk.import_book(self.pdf))
            self.assertTrue(target.is_relative_to(folder))
            self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), hashlib.sha256(self.pdf.read_bytes()).digest())
            self.assertEqual(bifurk.import_book(self.pdf), str(target))

    def test_portable_relative_save_after_move(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            books = root / 'donnees' / 'grimoires'
            books.mkdir(parents=True)
            pdf = books / 'test.pdf'
            pdf.write_bytes(b'%PDF-test-portable')
            w = self.window
            w.pdf_path = str(pdf)
            saves = root / 'donnees' / 'sauvegardes'
            with patch.object(bifurk, 'APP_DIR', root), patch.object(bifurk, 'BOOKS_DIR', books), patch.object(bifurk, 'SAVES_DIR', saves):
                data = w._save_data()
                self.assertFalse(Path(data['pdf_path']).is_absolute())
                w._autosave()
                self.assertTrue((saves / 'autosave.json').is_file())
            moved = root / 'deplace'
            moved_books = moved / 'donnees' / 'grimoires'
            moved_books.mkdir(parents=True)
            (moved_books / pdf.name).write_bytes(pdf.read_bytes())
            with patch.object(bifurk, 'APP_DIR', moved), patch.object(bifurk, 'BOOKS_DIR', moved_books):
                self.assertEqual(bifurk.resolve_book_reference(data['pdf_path']), str(moved_books / pdf.name))

    def test_400_sections(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        self.assertEqual(set(self.paragraphs), set(range(1, 401)))
        for n, text in self.paragraphs.items():
            with self.subTest(paragraph=n):
                self.assertTrue(text.strip())
                self.assertTrue(all(target in self.paragraphs for _, _, target in destinations(text)))

    def test_all_sections_render(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        w = self.window
        w.paragraphs = self.paragraphs
        for number in range(1, 401):
            with self.subTest(paragraph=number):
                w.go_to(number)
                self.assertEqual(w.current_paragraph, number)
                self.assertTrue(w.reader.toPlainText().strip())
                self.app.processEvents()

    def test_catalogue_geometry_and_render(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import fitz
        cat = catalogue_for_pdf(self.pdf)
        self.assertIsNotNone(cat)
        w = self.window
        w.pdf_path = str(self.pdf)
        with fitz.open(self.pdf) as doc:
            self.assertEqual(len(doc), cat['pdf_pages'])
            for entry in cat['illustrations']:
                with self.subTest(image=entry['id']):
                    page = doc[entry['page_pdf'] - 1]
                    rect = fitz.Rect(entry['rect'])
                    self.assertFalse(rect.is_empty)
                    self.assertFalse((page.rect & rect).is_empty)
                    self.assertFalse(w._illustration_pixmap(entry, scale=.25).isNull())
                    for n in entry['paragraphes']:
                        self.assertIn(n, self.paragraphs)
                        self.assertIn(entry, images_for_paragraph(cat, n))
                    if entry['type'] == 'ornement':
                        self.assertFalse(entry['paragraphes'])

    @unittest.expectedFailure
    def test_known_cover_bounds(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import fitz
        cat = catalogue_for_pdf(self.pdf)
        with fitz.open(self.pdf) as doc:
            entry = cat['illustrations'][0]
            self.assertTrue(doc[entry['page_pdf'] - 1].rect.contains(fitz.Rect(entry['rect'])))

    def test_known_luck_cannot_be_negative(self):
        self.window.character['chance'] = 0
        self.window.test_luck()
        self.assertGreaterEqual(self.window.character['chance'], 0)

    def test_known_combat_undo_restores_enemy(self):
        w = self.window
        before = w.enemy_endurance.value()
        with patch.object(w, '_roll', side_effect=[([1, 1], 2), ([6, 6], 12)]), patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
            w.combat_round()
        w.undo_action()
        self.assertEqual(w.enemy_endurance.value(), before)

    def test_combat_enemy_state_roundtrip(self):
        w = self.window
        w.enemy_name.setText("Orque")
        w.enemy_skill.setValue(7)
        w.enemy_endurance.setValue(9)
        state = w._snapshot()
        w.enemy_name.setText("Gobelin")
        w.enemy_skill.setValue(5)
        w.enemy_endurance.setValue(2)
        w._restore(state)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(), w.enemy_endurance.value()), ("Orque", 7, 9))
        self.assertEqual((w._save_data()["enemy_name"], w._save_data()["enemy_endurance"]), ("Orque", 9))

    def test_known_loading_restores_catalogue(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        w = self.window
        w.pdf_path = str(self.pdf)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'save.json'
            w._write_atomic(path, w._save_data())
            with patch.object(w, '_themed_save_dialog', return_value=str(path)), patch.object(bifurk, 'resolve_book_reference', return_value=str(self.pdf)), patch.object(QMessageBox, 'information'):
                w.load_game()
            self.assertIsNotNone(w.illustration_catalogue)


if __name__ == '__main__':
    unittest.main(verbosity=2)
