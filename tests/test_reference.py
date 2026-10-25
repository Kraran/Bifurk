"""Extraction, catalogue et scénarios de règles de référence.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
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
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])
        cls.pdf = next(ROOT.glob('*.pdf'), None)
        cls.paragraphs = bifurk.extract_paragraphs(cls.pdf) if cls.pdf else {}

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.window = bifurk.MainWindow()

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
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

    def test_special_combat_is_autoprepared_without_reset_button(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {16: "OGRE HABILETÉ: 8 ENDURANCE: 10"}
        w.go_to(16)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Ogre", 8, 10))
        labels = [w.event_layout.itemAt(i).widget().text()
                  for i in range(w.event_layout.count())
                  if hasattr(w.event_layout.itemAt(i).widget(), "text")]
        self.assertFalse(any("Préparer le combat" in label for label in labels))
        w.enemy_endurance.setValue(3)
        w._render_choices_and_events(w.paragraphs[16])
        self.assertEqual(w.enemy_endurance.value(), 3)
        labels = [w.event_layout.itemAt(i).widget().text()
                  for i in range(w.event_layout.count())
                  if hasattr(w.event_layout.itemAt(i).widget(), "text")]
        self.assertFalse(any("Préparer le combat" in label for label in labels))

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
            # Un itinéraire grisé (clé manquante) reste affiché mais pas cliquable.
            return [w.choice_layout.itemAt(i).widget().text()
                    for i in range(w.choice_layout.count())
                    if hasattr(w.choice_layout.itemAt(i).widget(), "text")
                    and w.choice_layout.itemAt(i).widget().isEnabled()]
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
        self.assertTrue(any("Lancer les 2 dés" in t for t in labels))
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

    def test_ferryman_3_gold_gate_and_transaction(self):
        from book_events import DATA_PATH, available_routes, follow_catalogue_route
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["3"]
        hero = {"gold": 2, "inventory": []}
        self.assertEqual([r["target"] for r in available_routes(hero, entry)], [127])
        self.assertFalse(follow_catalogue_route(hero, entry, 272))
        self.assertEqual(hero["gold"], 2)
        hero["gold"] = 4
        self.assertTrue(follow_catalogue_route(hero, entry, 272))
        self.assertEqual(hero["gold"], 1)
        self.assertTrue(follow_catalogue_route(hero, entry, 127))
        self.assertEqual(hero["gold"], 1)

    def test_ferryman_3_route_button_and_text_link_pay_once_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {3: "Payer au 272 ou menacer au 127.", 272: "Barque.", 127: "Menace."}
        w.character["gold"] = 3
        w.go_to(3)
        w.follow_catalogue_choice(272)
        self.assertEqual((w.current_paragraph, w.character["gold"]), (272, 0))
        w.undo_action()
        self.assertEqual((w.current_paragraph, w.character["gold"]), (3, 3))
        w.follow_link(QUrl("paragraph:272"))
        self.assertEqual((w.current_paragraph, w.character["gold"]), (272, 0))
        w.undo_action()
        w.character["gold"] = 2
        with patch.object(QMessageBox, "information") as msg:
            w.follow_link(QUrl("paragraph:272"))
            msg.assert_called_once()
        self.assertEqual((w.current_paragraph, w.character["gold"]), (3, 2))

    def test_book_trade_34_requires_relinquishing_unlocked_item(self):
        from book_events import trade_inventory_item
        hero = {"inventory": ["Épée", "Casque ensorcelé"],
                "equipped_weapon": "Épée",
                "locked_items": ["Casque ensorcelé"]}
        self.assertFalse(trade_inventory_item(hero, "Maillet en bois dur", "Casque ensorcelé"))
        self.assertFalse(trade_inventory_item(hero, "Maillet en bois dur", "Inexistant"))
        self.assertEqual(hero["inventory"], ["Épée", "Casque ensorcelé"])
        self.assertTrue(trade_inventory_item(hero, "Maillet en bois dur", "Épée"))
        self.assertIsNone(hero["equipped_weapon"])
        self.assertEqual(hero["inventory"], ["Casque ensorcelé", "Maillet en bois dur"])
        self.assertFalse(trade_inventory_item(hero, "Maillet en bois dur", "Casque ensorcelé"))

    def test_book_trade_34_single_choice_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {34: "Outils du Squelette.", 96: "Bruitage."}
        w.go_to(34)
        with patch("main.QInputDialog.getItem", return_value=("Épée", True)):
            w.take_book_trade("ciseau")
        self.assertIn("Ciseau à lame d'argent", w.character["inventory"])
        self.assertNotIn("Épée", w.character["inventory"])
        self.assertTrue(any(k.startswith("34:trade:") for k in w.completed_optional_events))
        with patch("main.QInputDialog.getItem") as chooser:
            w.take_book_trade("maillet")
            chooser.assert_not_called()
        w.undo_action()
        self.assertIn("Épée", w.character["inventory"])
        self.assertNotIn("Ciseau à lame d'argent", w.character["inventory"])
        self.assertFalse(any(k.startswith("34:trade:") for k in w.completed_optional_events))

    def test_goblin_33_victory_opens_147_reward_once(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {33: "Farfadet.", 147: "Boîte.", 320: "Porte."}
        w.character["chance"] = 5
        w.go_to(33)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Farfadet", 6, 4))
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12),
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
            self.assertEqual(w.current_paragraph, 33)
            w.combat_round()
        self.assertEqual(w.current_paragraph, 147)
        self.assertEqual(w.character["gold"], 2)
        self.assertEqual(w.character["chance"], 7)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 33)
        self.assertEqual(w.enemy_endurance.value(), 2)
        self.assertEqual(w.character["gold"], 1)

    def test_goblin_33_flee_cost_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {33: "Farfadet.", 320: "Couloir."}
        w.go_to(33)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(33)
        self.assertEqual(w.current_paragraph, 320)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 33)
        self.assertEqual(w.character["endurance"], 20)

    def test_etre_41_first_hit_opens_310_not_kill(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {41: "Être.", 310: "Invulnérable."}
        w.go_to(41)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Être", 9, 6))
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 310)
        self.assertEqual(w.enemy_endurance.value(), 4)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 41)
        self.assertEqual(w.enemy_endurance.value(), 6)

    def test_etre_41_outcome_is_blocked_before_first_hit(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {41: "Être. Rendez-vous au 310.", 310: "Arme inutile."}
        w.go_to(41)
        self.assertTrue(w._combat_exit_pending(310))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:310"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 41)

    def test_spider_61_requires_two_assaults_to_escape(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {61: "Araignée géante.", 375: "Croisement.", 29: "Victoire."}
        w.go_to(61)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Araignée géante", 7, 8))
        with patch.object(QMessageBox, "question") as question:
            w.escape_scripted_combat(61)
            question.assert_not_called()
        self.assertEqual(w.current_paragraph, 61)
        # Deux égalités, sans dégâts et sans dialogue, comptent comme deux assauts.
        with patch.object(w, "_roll", side_effect=[
                ([3, 3], 6), ([2, 3], 5),
                ([3, 3], 6), ([2, 3], 5)]):
            w.combat_round()
            w.combat_round()
        self.assertEqual(w.book_combat_assaults[61], 2)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(61)
        self.assertEqual(w.current_paragraph, 375)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 61)
        self.assertEqual(w.character["endurance"], 20)
        self.assertEqual(w.book_combat_assaults[61], 2)

    def test_spider_61_victory_routes_to_29(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {61: "Araignée géante.", 29: "Après le combat.", 375: "Croisement."}
        w.go_to(61)
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 29)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 61)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_guard_71_luck_is_checked_before_decrement(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        test = data["paragraphs"]["71"]["roll"]
        hero = {"chance": 8}
        self.assertEqual(resolve_roll(test, 8, hero)["target"], 301)
        self.assertEqual(resolve_roll(test, 9, hero)["target"], 248)
        self.assertEqual(hero["chance"], 8)

    def test_guard_71_roll_navigates_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {71: "Lutin endormi.", 301: "Passage.", 248: "Le garde se réveille."}
        w.go_to(71)
        with patch.object(w, "_roll", return_value=([4, 4], 8)):
            w.resolve_book_roll(71)
        self.assertEqual(w.current_paragraph, 301)
        self.assertEqual(w.character["chance"], 7)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 71)
        self.assertEqual(w.character["chance"], 8)
        self.assertNotIn(71, w.completed_book_events)
        with patch.object(w, "_roll", return_value=([6, 6], 12)):
            w.resolve_book_roll(71)
        self.assertEqual(w.current_paragraph, 248)

    def test_310_exit_is_211_without_equipment_bonus(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"habilete": 8, "initial": {"habilete": 10}, "inventory": ["Épée"]}
        entry = data["paragraphs"]["310"]
        self.assertEqual([route["target"] for route in available_routes(hero, entry)], [211])
        self.assertEqual(hero["habilete"], 8)

    def test_quail_eggs_38_are_optional_and_once(self):
        from book_events import DATA_PATH, apply_option, available_options
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"provisions": 4, "inventory": []}
        entry = data["paragraphs"]["38"]
        completed = set()
        self.assertEqual(hero["provisions"], 4)
        self.assertEqual(len(available_options(hero, entry, completed, 38)), 1)
        self.assertTrue(apply_option(hero, completed, 38, "oeufs", data))
        self.assertEqual(hero["provisions"], 6)
        self.assertFalse(apply_option(hero, completed, 38, "oeufs", data))
        self.assertEqual(hero["provisions"], 6)

    def test_enchanted_bench_meal_caps_stats_and_consumes_one_provision(self):
        from book_events import enchanted_bench_meal
        hero = {"endurance": 10, "habilete": 7, "provisions": 2,
                "initial": {"endurance": 20, "habilete": 9}}
        self.assertTrue(enchanted_bench_meal(hero))
        self.assertEqual((hero["endurance"], hero["habilete"], hero["provisions"]),
                         (16, 8, 1))
        hero["endurance"], hero["habilete"] = 18, 9
        self.assertTrue(enchanted_bench_meal(hero))
        self.assertEqual((hero["endurance"], hero["habilete"], hero["provisions"]),
                         (20, 9, 0))
        self.assertFalse(enchanted_bench_meal(hero))

    def test_bench_58_must_have_food_to_visit_15(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["58"]
        self.assertEqual([r["target"] for r in available_routes(
            {"provisions": 0}, entry)], [367])
        self.assertEqual([r["target"] for r in available_routes(
            {"provisions": 1}, entry)], [15, 367])

    def test_enchanted_meal_15_is_required_once_and_undoable(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {15: "Banc enchanté. Rendez-vous au 367.",
                        367: "Le couloir."}
        w.character["provisions"] = 3
        w.character["endurance"] = 10
        w.character["habilete"] = 7
        w.go_to(15)
        with patch.object(QMessageBox, "information") as warning:
            w.follow_link(QUrl("paragraph:367"))
            warning.assert_called_once()
        self.assertEqual(w.current_paragraph, 15)
        w.take_enchanted_meal()
        self.assertEqual(w.character["provisions"], 2)
        self.assertEqual(w.character["endurance"], 16)
        self.assertEqual(w.character["habilete"], 8)
        self.assertIn(15, w.completed_book_events)
        w.take_enchanted_meal()
        self.assertEqual(w.character["provisions"], 2)
        w.undo_action()
        self.assertNotIn(15, w.completed_book_events)
        self.assertEqual((w.character["provisions"], w.character["endurance"],
                          w.character["habilete"]), (3, 10, 7))
        w.take_enchanted_meal()
        w.follow_catalogue_choice(367)
        self.assertEqual(w.current_paragraph, 367)

    def test_two_goblins_19_are_prepared_sequentially_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {19: "Deux Lutins.", 317: "Le Fromage."}
        w.go_to(19)
        self.assertEqual(w.book_combat_sequence, {"paragraph": 19, "index": 0})
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Lutin 1", 5, 5))
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 19)
        self.assertEqual(w.book_combat_sequence["index"], 1)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Lutin 2", 5, 6))
        w.undo_action()
        self.assertEqual(w.book_combat_sequence["index"], 0)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_two_goblins_19_victory_unlocks_317_and_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {19: "Deux Lutins. Rendez-vous au 317.",
                        317: "Le Fromage.", 303: "Couloir."}
        w.go_to(19)
        self.assertTrue(w._combat_exit_pending(317))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:317"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 19)
        w.book_combat_sequence["index"] = 1
        w._set_book_enemy({"name": "Lutin 2", "skill": 5, "stamina": 2})
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 317)
        self.assertIn(19, w.prepared_book_encounters)
        self.assertIsNone(w.book_combat_sequence)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 19)
        self.assertEqual(w.book_combat_sequence["index"], 1)
        self.assertNotIn(19, w.prepared_book_encounters)

    def test_goblin_cheese_317_optional_and_consumable_at_32(self):
        from book_events import DATA_PATH, apply_option, available_options
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        character = {"inventory": [], "chance": 4, "initial": {"chance": 9}}
        completed = set()
        self.assertEqual(len(available_options(
            character, data["paragraphs"]["317"], completed, 317)), 1)
        self.assertTrue(apply_option(character, completed, 317, "fromage", data))
        self.assertIn("Fromage", character["inventory"])
        self.assertFalse(apply_option(character, completed, 317, "fromage", data))
        self.assertTrue(apply_option(character, completed, 32, "jeter_fromage", data))
        self.assertEqual(character["chance"], 6)
        self.assertNotIn("Fromage", character["inventory"])

    def test_cheese_317_pickup_undo_and_safe_return_route(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {317: "Fromage. Rendez-vous au 303.", 303: "Nord."}
        w.go_to(317)
        w.apply_optional_book_event(317, "fromage")
        self.assertIn("Fromage", w.character["inventory"])
        w.undo_action()
        self.assertNotIn("Fromage", w.character["inventory"])
        w.follow_catalogue_choice(303)
        self.assertEqual(w.current_paragraph, 303)

    def test_verified_early_choice_routes_35_36_57_84(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        choices = {
            35: [136, 361],
            36: [263, 353],
            57: [16, 2, 119],
            84: [204, 280, 377],
        }
        for paragraph, expected in choices.items():
            with self.subTest(paragraph=paragraph):
                entry = data["paragraphs"][str(paragraph)]
                self.assertEqual(
                    [route["target"] for route in available_routes({}, entry)],
                    expected)

    def test_shelter_77_meal_is_optional_and_undoable(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {77: "Un abri pour manger ; est 345, ouest 18.",
                        345: "Est.", 18: "Ouest."}
        w.character["endurance"] = 10
        w.character["provisions"] = 3
        w.go_to(77)
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 3))
        buttons = [
            w.event_layout.itemAt(i).widget()
            for i in range(w.event_layout.count())
            if hasattr(w.event_layout.itemAt(i).widget(), "text")
        ]
        meal_buttons = [b for b in buttons if "Prendre un repas" in b.text()]
        self.assertEqual(len(meal_buttons), 1)
        self.assertTrue(meal_buttons[0].isEnabled())
        meal_buttons[0].click()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (14, 2))
        w.undo_action()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 3))
        w.follow_catalogue_choice(345)
        self.assertEqual(w.current_paragraph, 345)
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 3))

    def test_shelter_77_meal_disabled_without_provisions(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {77: "Abri.", 345: "Est.", 18: "Ouest."}
        w.character["provisions"] = 0
        w.go_to(77)
        buttons = [
            w.event_layout.itemAt(i).widget()
            for i in range(w.event_layout.count())
            if hasattr(w.event_layout.itemAt(i).widget(), "text")
        ]
        meal_buttons = [b for b in buttons if "Prendre un repas" in b.text()]
        self.assertEqual(len(meal_buttons), 1)
        self.assertFalse(meal_buttons[0].isEnabled())
        self.assertEqual(w.character["provisions"], 0)
        w.follow_catalogue_choice(18)
        self.assertEqual(w.current_paragraph, 18)

    def test_ogre_57_branch_to_scripted_encounter(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {57: "Ogre.", 16: "Le combat contre l'Ogre.",
                        2: "Fuite.", 119: "Diversion."}
        w.go_to(57)
        w.follow_catalogue_choice(16)
        self.assertEqual(w.current_paragraph, 16)
        self.assertEqual(
            (w.enemy_name.text(), w.enemy_skill.value(), w.enemy_endurance.value()),
            ("Ogre", 8, 10))
        w.undo_action()
        self.assertEqual(w.current_paragraph, 57)
        self.assertNotIn(16, w.prepared_book_encounters)

    def test_verified_corridor_routes_match_1982_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            9: [34, 322], 21: [339, 293], 23: [326, 229],
            30: [67, 267], 37: [366, 11, 277], 42: [257, 113],
            43: [354, 52], 46: [4, 206], 48: [391, 60],
            52: [391, 362, 354, 234, 291], 54: [308, 179],
            62: [6, 89], 63: [281, 10], 66: [104, 99],
            67: [267, 177], 78: [159, 237], 79: [137, 267],
            85: [106, 373, 318, 59], 90: [253],
        }
        for paragraph, targets in expected.items():
            with self.subTest(paragraph=paragraph):
                entry = data["paragraphs"][str(paragraph)]
                routes = available_routes({}, entry)
                self.assertEqual([route["target"] for route in routes], targets)
                self.assertEqual(len({route["target"] for route in routes}), len(targets))
                self.assertTrue(all(route["label"].strip() for route in routes))

    def test_five_distinct_options_in_corridor_52(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {
            52: "Au carrefour en T.", 391: "Sud.", 362: "Secret sud.",
            354: "Nord.", 234: "Secret nord.", 291: "Est."}
        w.go_to(52)
        buttons = [w.choice_layout.itemAt(i).widget()
                   for i in range(w.choice_layout.count())]
        self.assertEqual(len(buttons), 5)
        self.assertEqual(len({button.text() for button in buttons}), 5)
        w.follow_catalogue_choice(234)
        self.assertEqual(w.current_paragraph, 234)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 52)

    def test_four_distinct_routes_at_crossroads_85(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {85: "Croisée des chemins.", 106: "N.",
                        373: "S.", 318: "E.", 59: "O."}
        w.go_to(85)
        self.assertEqual(w.choice_layout.count(), 4)
        w.follow_catalogue_choice(318)
        self.assertEqual(w.current_paragraph, 318)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 85)

    def test_rest_area_90_meal_is_optional_and_refreshes_button(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {90: "Niche de repos.", 253: "Vers le nord."}
        w.character["provisions"] = 1
        w.character["endurance"] = 10
        w.go_to(90)
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 1))
        def meal_buttons():
            return [widget for i in range(w.event_layout.count())
                    if (widget := w.event_layout.itemAt(i).widget()) is not None
                    and hasattr(widget, "text") and "Prendre un repas" in widget.text()]
        self.assertEqual(len(meal_buttons()), 1)
        self.assertTrue(meal_buttons()[0].isEnabled())
        meal_buttons()[0].click()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (14, 0))
        self.assertFalse(meal_buttons()[0].isEnabled())
        w.undo_action()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 1))
        self.assertTrue(meal_buttons()[0].isEnabled())
        w.follow_catalogue_choice(253)
        self.assertEqual(w.current_paragraph, 253)

    def test_rest_area_90_can_be_skipped_without_spending_provisions(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {90: "Niche de repos.", 253: "Vers le nord."}
        w.character["provisions"] = 0
        w.go_to(90)
        self.assertEqual(w.character["provisions"], 0)
        w.follow_catalogue_choice(253)
        self.assertEqual(w.current_paragraph, 253)
        self.assertEqual(w.character["provisions"], 0)

    def test_verified_routes_92_through_115_match_1982_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            92: [71], 93: [8], 94: [260, 329], 95: [205],
            96: [374], 97: [334, 247, 292], 98: [358],
            99: [383], 100: [346, 91], 101: [327],
            102: [303, 19, 68], 103: [252, 359],
            104: [49], 107: [148, 197], 111: [249],
            113: [285, 78], 114: [359], 115: [95, 313, 330],
        }
        for paragraph, destinations in expected.items():
            with self.subTest(paragraph=paragraph):
                entry = data["paragraphs"][str(paragraph)]
                actual = available_routes({}, entry)
                self.assertEqual([route["target"] for route in actual], destinations)
                self.assertTrue(all(route["label"].strip() for route in actual))
                self.assertEqual(len(actual), len(set(destinations)))

    def test_room_102_can_choose_two_goblins_combat_19(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {102: "Salle de torture.", 303: "Couloir.",
                        19: "Deux Lutins.", 68: "Feinte.", 317: "Fromage."}
        w.go_to(102)
        self.assertEqual(w.choice_layout.count(), 3)
        w.follow_catalogue_choice(19)
        self.assertEqual(w.current_paragraph, 19)
        self.assertEqual(w.book_combat_sequence, {"paragraph": 19, "index": 0})
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Lutin 1", 5, 5))
        w.undo_action()
        self.assertEqual(w.current_paragraph, 102)
        self.assertIsNone(w.book_combat_sequence)

    def test_room_97_three_distinct_choices_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {97: "Vieil homme.", 334: "Conversation.",
                        247: "Attaque.", 292: "Départ."}
        w.go_to(97)
        self.assertEqual(w.choice_layout.count(), 3)
        w.follow_catalogue_choice(334)
        self.assertEqual(w.current_paragraph, 334)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 97)

    def test_hand_108_prepares_combat_and_victory_185(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {108: "Une main vous agrippe.", 185: "Victoire."}
        w.go_to(108)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Main", 6, 4))
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 185)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 108)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_hand_108_cannot_skip_combat_via_text_link(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {108: "Si victoire rendez-vous au 185.", 185: "Victoire."}
        w.go_to(108)
        self.assertTrue(w._combat_exit_pending(185))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:185"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 108)

    def test_new_routes_117_to_141_match_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            117: [354, 308], 120: [197], 121: [103, 359],
            124: [138, 76], 128: [210, 58], 129: [104],
            133: [52], 134: [202, 325, 87], 136: [229],
            137: [354], 141: [66, 111],
        }
        for number, targets in expected.items():
            with self.subTest(paragraph=number):
                self.assertEqual(
                    [r["target"] for r in available_routes(
                        {}, data["paragraphs"][str(number)])], targets)

    def test_skeleton_ruse_123_all_six_die_faces(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["123"]["roll"]
        for die in range(1, 7):
            with self.subTest(die=die):
                branch = resolve_roll(roll, die, {"chance": 6})
                expected = 184 if die <= 3 else 164 if die <= 5 else 140
                self.assertEqual(branch["target"], expected)
                self.assertEqual(
                    branch.get("effects", []),
                    [{"kind": "stat", "key": "chance", "amount": 2}]
                    if die <= 3 else [])

    def test_skeleton_ruse_123_win_luck_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {123: "Squelettes.", 184: "Bateaux.",
                        164: "Surveillance.", 140: "Combat."}
        w.character["chance"] = 5
        w.go_to(123)
        with patch.object(w, "_roll", return_value=([2], 2)):
            w.resolve_book_roll(123)
        self.assertEqual(w.current_paragraph, 184)
        self.assertEqual(w.character["chance"], 7)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 123)
        self.assertEqual(w.character["chance"], 5)
        self.assertNotIn(123, w.completed_book_events)

    def test_ferryman_127_costs_five_gold_or_fights(self):
        from book_events import DATA_PATH, available_routes, follow_catalogue_route
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["127"]
        hero = {"gold": 4}
        self.assertEqual([r["target"] for r in available_routes(hero, entry)], [188])
        self.assertFalse(follow_catalogue_route(hero, entry, 272))
        hero["gold"] = 6
        self.assertTrue(follow_catalogue_route(hero, entry, 272))
        self.assertEqual(hero["gold"], 1)
        self.assertTrue(follow_catalogue_route(hero, entry, 188))
        self.assertEqual(hero["gold"], 1)

    def test_sorcerer_142_fight_cannot_be_skipped_and_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {142: "Sorcier. Victoire au 396.", 396: "Victoire."}
        w.go_to(142)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Sorcier", 11, 18))
        self.assertTrue(w._combat_exit_pending(396))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:396"))
            alert.assert_called_once()
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 396)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 142)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_four_gray_creatures_122_three_routes(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual([r["target"] for r in available_routes(
            {}, data["paragraphs"]["122"])], [268, 282, 13])

    def test_shared_meal_131_reduces_restoration_and_consumes_food(self):
        from book_events import shared_meal
        hero = {"endurance": 10, "provisions": 2,
                "initial": {"endurance": 20}}
        self.assertTrue(shared_meal(hero))
        self.assertEqual((hero["endurance"], hero["provisions"]), (12, 1))
        hero["endurance"] = 19
        self.assertTrue(shared_meal(hero))
        self.assertEqual((hero["endurance"], hero["provisions"]), (20, 0))
        self.assertFalse(shared_meal(hero))

    def test_shared_meal_131_ui_optional_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {131: "Repas partagé.", 291: "Couloir."}
        w.character["endurance"] = 10
        w.character["provisions"] = 1
        w.go_to(131)
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 1))
        widgets = [w.event_layout.itemAt(i).widget()
                   for i in range(w.event_layout.count())]
        meal = [widget for widget in widgets if hasattr(widget, "text")
                and "Partager un repas" in widget.text()]
        self.assertEqual(len(meal), 1)
        meal[0].click()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (12, 0))
        w.undo_action()
        self.assertEqual((w.character["endurance"], w.character["provisions"]), (10, 1))
        w.follow_catalogue_choice(291)
        self.assertEqual(w.current_paragraph, 291)
        self.assertEqual(w.character["provisions"], 1)

    def test_creature_treasure_135_optional_gold_and_automatic_luck(self):
        from book_events import DATA_PATH, apply_entry, apply_option
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"chance": 5, "gold": 2, "provisions": 1,
                "initial": {"chance": 10}, "inventory": []}
        completed, chosen = set(), set()
        self.assertTrue(apply_entry(hero, completed, 135, data))
        self.assertEqual((hero["chance"], hero["gold"]), (7, 2))
        self.assertFalse(apply_entry(hero, completed, 135, data))
        self.assertTrue(apply_option(hero, chosen, 135, "or18", data))
        self.assertEqual(hero["gold"], 20)
        self.assertFalse(apply_option(hero, chosen, 135, "or18", data))

    def test_creature_treasure_135_undo_reward_and_exit(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {135: "La boîte contenant l'or.", 360: "Porte nord."}
        w.character["chance"] = 4
        w.character["gold"] = 1
        w.go_to(135)
        self.assertEqual((w.character["chance"], w.character["gold"]), (6, 1))
        w.apply_optional_book_event(135, "or18")
        self.assertEqual(w.character["gold"], 19)
        w.undo_action()
        self.assertEqual((w.character["chance"], w.character["gold"]), (6, 1))
        w.undo_action()
        self.assertEqual(w.character["chance"], 4)

    def test_ogre_diversion_119_discards_one_item_or_gold(self):
        from book_events import throw_diversion_item
        hero = {"inventory": ["Fromage", "Épée"], "gold": 2,
                "locked_items": []}
        self.assertFalse(throw_diversion_item(hero, "Absent"))
        self.assertTrue(throw_diversion_item(hero))
        self.assertEqual(hero["gold"], 1)
        self.assertEqual(hero["inventory"], ["Fromage", "Épée"])
        self.assertTrue(throw_diversion_item(hero, "Fromage"))
        self.assertEqual(hero["inventory"], ["Épée"])
        self.assertEqual(hero["gold"], 1)
        self.assertTrue(throw_diversion_item(hero, "Épée"))
        self.assertEqual(hero["inventory"], [])
        self.assertTrue(throw_diversion_item(hero))
        self.assertEqual(hero["gold"], 0)
        self.assertFalse(throw_diversion_item({"inventory": [], "gold": 0}))

    def test_ogre_diversion_119_does_not_discard_locked_gear(self):
        from book_events import throw_diversion_item
        hero = {"inventory": ["Casque maudit"], "locked_items": ["Casque maudit"],
                "gold": 3}
        self.assertFalse(throw_diversion_item(hero, "Casque maudit"))
        self.assertTrue(throw_diversion_item(hero))
        self.assertEqual(hero["gold"], 2)
        self.assertEqual(hero["inventory"], ["Casque maudit"])

    def test_ogre_diversion_119_ui_offers_coin_despite_inventory_and_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtWidgets import QInputDialog
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {119: "Faire diversion puis §269.", 269: "Bifurcation."}
        w.character["inventory"] = ["Épée", "Fromage"]
        w.character["gold"] = 2
        w.go_to(119)
        def choose_gold(parent, title, prompt, choices, selected, editable):
            self.assertIn("🪙 Jeter une pièce d'or", choices)
            self.assertIn("Fromage", choices)
            return ("🪙 Jeter une pièce d'or", True)
        with patch.object(QInputDialog, "getItem", side_effect=choose_gold):
            w.throw_book_diversion()
        self.assertEqual(w.character["gold"], 1)
        self.assertEqual(w.character["inventory"], ["Épée", "Fromage"])
        self.assertIn(119, w.completed_book_events)
        w.undo_action()
        self.assertEqual(w.character["gold"], 2)
        self.assertEqual(w.character["inventory"], ["Épée", "Fromage"])
        self.assertNotIn(119, w.completed_book_events)

    def test_ogre_diversion_119_coin_not_shown_without_gold(self):
        from book_events import DATA_PATH
        from PySide6.QtWidgets import QInputDialog
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {119: "Faire diversion.", 269: "Bifurcation."}
        w.character["inventory"] = ["Fromage"]
        w.character["gold"] = 0
        w.go_to(119)
        def choose_item(parent, title, prompt, choices, selected, editable):
            self.assertEqual(choices, ["Fromage"])
            return ("Fromage", True)
        with patch.object(QInputDialog, "getItem", side_effect=choose_item):
            w.throw_book_diversion()
        self.assertEqual(w.character["inventory"], [])
        self.assertEqual(w.character["gold"], 0)

    def test_ogre_diversion_119_ui_unlocks_route_and_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {119: "Faire diversion puis §269.", 269: "Bifurcation."}
        w.character["inventory"] = []
        w.character["gold"] = 2
        w.go_to(119)
        with patch.object(QMessageBox, "information") as warning:
            w.follow_link(QUrl("paragraph:269"))
            warning.assert_called_once()
        w.throw_book_diversion()
        self.assertEqual(w.character["gold"], 1)
        self.assertIn(119, w.completed_book_events)
        w.throw_book_diversion()
        self.assertEqual(w.character["gold"], 1)
        w.undo_action()
        self.assertEqual(w.character["gold"], 2)
        self.assertNotIn(119, w.completed_book_events)
        w.throw_book_diversion()
        w.follow_catalogue_choice(269)
        self.assertEqual(w.current_paragraph, 269)

    def test_sea_worm_143_victory_routes_to_44(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {143: "Ver marin géant.", 44: "Victoire.", 399: "Rivière."}
        w.go_to(143)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Ver marin géant", 7, 7))
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 44)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 143)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_sea_worm_143_escape_requires_three_assaults_and_loses_meal(self):
        from book_events import DATA_PATH, flee_available
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {143: "Ver marin géant.", 44: "Victoire.", 399: "Rivière."}
        w.character["provisions"] = 3
        w.go_to(143)
        rules = w.book_event_catalogue["paragraphs"]["143"]["combat"]
        self.assertFalse(flee_available(rules, 2, 7, 20))
        self.assertTrue(flee_available(rules, 3, 7, 20))
        with patch.object(QMessageBox, "question") as question:
            w.escape_scripted_combat(143)
            question.assert_not_called()
        self.assertEqual(w.current_paragraph, 143)
        w.book_combat_assaults[143] = 3
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(143)
        self.assertEqual(w.current_paragraph, 399)
        self.assertEqual(w.character["provisions"], 2)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 143)
        self.assertEqual(w.character["provisions"], 3)
        self.assertEqual(w.character["endurance"], 20)

    def test_new_routes_145_to_154_match_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            145: [363], 146: [366, 11], 148: [230],
            149: [181, 265, 355], 150: [222, 297, 133], 154: [41]
        }
        for paragraph, targets in expected.items():
            with self.subTest(paragraph=paragraph):
                routes = available_routes({}, data["paragraphs"][str(paragraph)])
                self.assertEqual([route["target"] for route in routes], targets)

    def test_bronze_key_99_at_145_optional_without_repeating_luck(self):
        from book_events import DATA_PATH, apply_entry, apply_option
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"chance": 5, "initial": {"chance": 9},
                "inventory": []}
        entered, chosen = set(), set()
        self.assertTrue(apply_entry(hero, entered, 145, data))
        self.assertEqual(hero["chance"], 6)
        self.assertNotIn("Clé de bronze 99", hero["inventory"])
        self.assertTrue(apply_option(hero, chosen, 145, "cle99", data))
        self.assertIn("Clé de bronze 99", hero["inventory"])
        self.assertFalse(apply_entry(hero, entered, 145, data))
        self.assertFalse(apply_option(hero, chosen, 145, "cle99", data))
        self.assertEqual(hero["chance"], 6)

    def test_dragon_152_prepared_victory_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {152: "Dragon.", 371: "Après le Dragon."}
        w.go_to(152)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Dragon", 10, 12))
        self.assertTrue(w._combat_exit_pending(371))
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 371)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 152)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_door_156_skill_check_two_dice_all_results(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["156"]["roll"]
        for total in range(2, 13):
            with self.subTest(total=total):
                target = resolve_roll(roll, total, {"habilete": 8})["target"]
                self.assertEqual(target, 343 if total <= 8 else 92)

    def test_door_156_failure_goes_to_92_and_undo(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {156: "Enfoncer la porte.", 343: "Ouverte.", 92: "Échec."}
        w.character["habilete"] = 8
        w.go_to(156)
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:343"))
            alert.assert_called_once()
        with patch.object(w, "_roll", return_value=([5, 5], 10)):
            w.resolve_book_roll(156)
        self.assertEqual(w.current_paragraph, 92)
        self.assertEqual(w.character["habilete"], 8)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 156)
        self.assertNotIn(156, w.completed_book_events)

    def test_corridors_157_to_180_match_verified_routes(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            157: [4, 329], 160: [267], 162: [23, 69],
            164: [129, 236], 167: [187, 359],
            168: [372, 65, 293], 169: [400],
            171: [337, 187], 174: [198], 175: [177, 267],
            176: [270, 375], 177: [52, 391, 175],
            178: [162], 180: [70, 329, 22],
        }
        for number, targets in expected.items():
            with self.subTest(paragraph=number):
                routes = available_routes({}, data["paragraphs"][str(number)])
                self.assertEqual([r["target"] for r in routes], targets)
                self.assertTrue(all(r["label"] for r in routes))

    def test_swimming_166_six_results_one_die(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["166"]["roll"]
        for die in range(1, 7):
            with self.subTest(die=die):
                target = resolve_roll(roll, die, {})["target"]
                self.assertEqual(target, 218 if die <= 4 else 158)

    def test_swimming_166_piranha_branch_undo_and_later_victory(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {166: "Nage dans la rivière.", 158: "Piranhas.",
                        218: "Berge sud."}
        w.go_to(166)
        with patch.object(w, "_roll", return_value=([6], 6)):
            w.resolve_book_roll(166)
        self.assertEqual(w.current_paragraph, 158)
        self.assertEqual(
            (w.enemy_name.text(), w.enemy_skill.value(), w.enemy_endurance.value()),
            ("Piranhas", 5, 5))
        w.undo_action()
        self.assertEqual(w.current_paragraph, 166)
        self.assertNotIn(166, w.completed_book_events)
        with patch.object(w, "_roll", return_value=([2], 2)):
            w.resolve_book_roll(166)
        self.assertEqual(w.current_paragraph, 218)

    def test_piranhas_158_cannot_bypass_victory(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {158: "Piranhas. Si victoire au 218.", 218: "Berge sud."}
        w.go_to(158)
        self.assertTrue(w._combat_exit_pending(218))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:218"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 158)

    def test_piranhas_158_victory_goes_218_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {158: "Piranhas.", 218: "Berge sud."}
        w.go_to(158)
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 218)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 158)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_riverbank_218_four_travel_choices(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = data["paragraphs"]["218"]
        self.assertEqual(
            [route["target"] for route in available_routes({}, entry)],
            [3, 386, 209, 316])
        w = self.window
        w.book_event_catalogue = data
        w.paragraphs = {218: "Rivière.", 3: "Bac.", 386: "Radeau.",
                        209: "Pont.", 316: "Nage."}
        w.go_to(218)
        self.assertEqual(w.choice_layout.count(), 4)
        w.follow_catalogue_choice(209)
        self.assertEqual(w.current_paragraph, 209)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 218)

    def test_verified_routes_181_to_210(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            181: [355, 265], 183: [266, 237], 184: [322, 34],
            185: [162], 187: [171, 308], 190: [167, 359],
            191: [308, 392, 46], 193: [93, 338],
            194: [142, 105], 196: [280], 197: [48, 295],
            200: [387], 203: [38, 66], 205: [254, 380],
            207: [83, 154], 208: [397, 363], 210: [225, 357]
        }
        for paragraph, targets in expected.items():
            with self.subTest(paragraph=paragraph):
                routes = available_routes({}, data["paragraphs"][str(paragraph)])
                self.assertEqual([r["target"] for r in routes], targets)
                self.assertEqual(len(targets), len(set(targets)))

    def test_three_outcomes_of_skeleton_bluff_195(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["195"]["roll"]
        for die in range(1, 7):
            with self.subTest(die=die):
                branch = resolve_roll(roll, die, {"chance": 6})
                expected = 140 if die <= 2 else 164 if die <= 4 else 9
                self.assertEqual(branch["target"], expected)
                self.assertEqual(branch.get("effects", []),
                    [{"kind": "stat", "key": "chance", "amount": 2}]
                    if die >= 5 else [])

    def test_skeleton_bluff_195_adds_luck_once_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {195: "Bluff des Squelettes.", 140: "Combat.",
                        164: "Méfiance.", 9: "Hangar."}
        w.character["chance"] = 5
        w.go_to(195)
        with patch.object(w, "_roll", return_value=([5], 5)):
            w.resolve_book_roll(195)
        self.assertEqual(w.current_paragraph, 9)
        self.assertEqual(w.character["chance"], 7)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 195)
        self.assertEqual(w.character["chance"], 5)
        self.assertNotIn(195, w.completed_book_events)

    def test_rat_werewolf_188_fight_and_flee(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {188: "Rat-garou.", 209: "Pont.", 342: "Victoire."}
        w.go_to(188)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Rat-garou", 8, 5))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(188)
        self.assertEqual(w.current_paragraph, 209)
        self.assertEqual(w.character["endurance"], 18)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 188)
        self.assertEqual(w.character["endurance"], 20)

    def test_rat_werewolf_188_victory_and_blocked_link(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {188: "Rat-garou. Victoire §342.", 342: "Victoire.",
                        209: "Pont."}
        w.go_to(188)
        with patch.object(QMessageBox, "information") as warning:
            w.follow_link(QUrl("paragraph:342"))
            warning.assert_called_once()
        w.enemy_endurance.setValue(2)
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 342)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 188)
        self.assertEqual(w.enemy_endurance.value(), 2)

    def test_rewards_181_183_196_automatic_once(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        char = {"habilete": 6, "endurance": 10, "gold": 1,
                "initial": {"habilete": 8, "endurance": 14}}
        done = set()
        self.assertTrue(apply_entry(char, done, 181, data))
        self.assertEqual(char["habilete"], 5)
        self.assertTrue(apply_entry(char, done, 183, data))
        self.assertEqual((char["habilete"], char["endurance"]), (6, 14))
        self.assertTrue(apply_entry(char, done, 196, data))
        self.assertEqual(char["gold"], 6)
        for paragraph in (181, 183, 196):
            self.assertFalse(apply_entry(char, done, paragraph, data))
        self.assertEqual(char["gold"], 6)

    def test_verified_routes_212_to_235(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            212: [369, 120], 214: [271, 104, 99],
            215: [142, 105], 217: [118], 219: [182],
            220: [171], 222: [85], 223: [53, 300],
            224: [118], 225: [77, 63], 226: [267],
            228: [85], 229: [69], 231: [182],
            232: [375], 233: [198], 235: [176, 5],
        }
        for paragraph, targets in expected.items():
            with self.subTest(paragraph=paragraph):
                routes = available_routes({}, data["paragraphs"][str(paragraph)])
                self.assertEqual([route["target"] for route in routes], targets)

    def test_locked_door_213_all_dice_results_and_wound(self):
        from book_events import DATA_PATH, resolve_roll
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = data["paragraphs"]["213"]["roll"]
        for total in range(2, 13):
            with self.subTest(total=total):
                outcome = resolve_roll(roll, total, {"habilete": 8})
                self.assertEqual(outcome["target"], 36 if total <= 8 else 314)
                self.assertEqual(outcome.get("effects", []),
                    [] if total <= 8 else
                    [{"kind": "stat", "key": "endurance", "amount": -1}])

    def test_locked_door_213_failure_costs_endurance_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {213: "Porte verrouillée.", 314: "Couloir.", 36: "Pièce."}
        w.character["habilete"] = 8
        w.character["endurance"] = 14
        w.go_to(213)
        with patch.object(w, "_roll", return_value=([5, 5], 10)):
            w.resolve_book_roll(213)
        self.assertEqual(w.current_paragraph, 314)
        self.assertEqual(w.character["endurance"], 13)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 213)
        self.assertEqual(w.character["endurance"], 14)
        self.assertNotIn(213, w.completed_book_events)

    def test_fountain_216_exact_restoration_once_and_optional_food(self):
        from book_events import DATA_PATH, apply_entry
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"endurance": 12, "habilete": 4, "chance": 2,
                "initial": {"endurance": 18, "habilete": 9, "chance": 8},
                "provisions": 2}
        completed = set()
        self.assertTrue(apply_entry(hero, completed, 216, data))
        self.assertEqual((hero["endurance"], hero["habilete"],
                          hero["chance"], hero["provisions"]), (16, 9, 8, 2))
        self.assertFalse(apply_entry(hero, completed, 216, data))
        self.assertEqual(hero["endurance"], 16)
        self.assertTrue(data["paragraphs"]["216"]["optional_meal"])

    def test_fountain_216_entry_meal_choice_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {216: "Fontaine.", 384: "Sortie."}
        w.character["endurance"] = 10
        w.character["habilete"] = 6
        w.character["chance"] = 5
        w.character["provisions"] = 2
        w.go_to(216)
        initial = w.character["initial"]
        self.assertEqual(w.character["endurance"], 14)
        self.assertEqual(w.character["habilete"], initial["habilete"])
        self.assertEqual(w.character["chance"], initial["chance"])
        self.assertEqual(w.character["provisions"], 2)
        meal_buttons = [w.event_layout.itemAt(i).widget()
            for i in range(w.event_layout.count())
            if hasattr(w.event_layout.itemAt(i).widget(), "text")
            and "Prendre un repas" in w.event_layout.itemAt(i).widget().text()]
        self.assertEqual(len(meal_buttons), 1)
        meal_buttons[0].click()
        self.assertEqual(w.character["endurance"], 18)
        self.assertEqual(w.character["provisions"], 1)
        w.undo_action()
        self.assertEqual(w.character["endurance"], 14)
        self.assertEqual(w.character["provisions"], 2)
        w.follow_catalogue_choice(384)
        self.assertEqual(w.current_paragraph, 384)

    def test_corridor_routes_237_to_260_match_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            237: [285], 238: [70, 180, 329], 239: [88, 149],
            241: [90], 242: [379, 139], 244: [143, 399],
            245: [198], 246: [329, 180, 70], 247: [292],
            250: [366], 252: [312, 226],
            254: [352, 333, 279, 380], 255: [193, 93],
            256: [398, 297, 114], 257: [168, 293],
            259: [7], 260: [359, 329],
        }
        for n, destinations in expected.items():
            with self.subTest(paragraph=n):
                character = {"inventory": ["Épée"]} if n == 242 else {}
                actual = available_routes(character, data["paragraphs"][str(n)])
                self.assertEqual([route["target"] for route in actual], destinations)
                self.assertTrue(all(route["label"] for route in actual))

    def test_candle_239_and_portrait_241_automatic_effects_only_once(self):
        from book_events import DATA_PATH, apply_entry
        catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"chance": 4, "habilete": 8,
                "initial": {"chance": 10, "habilete": 11}}
        completed = set()
        self.assertTrue(apply_entry(hero, completed, 239, catalogue))
        self.assertEqual(hero["chance"], 5)
        self.assertTrue(apply_entry(hero, completed, 241, catalogue))
        self.assertEqual(hero["habilete"], 7)
        self.assertFalse(apply_entry(hero, completed, 239, catalogue))
        self.assertFalse(apply_entry(hero, completed, 241, catalogue))
        self.assertEqual((hero["chance"], hero["habilete"]), (5, 7))

    def test_trap_243_even_and_odd_die_with_existing_option_ids(self):
        from book_events import DATA_PATH, resolve_roll
        catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        rules = catalogue["paragraphs"]["243"]["roll"]
        for die in range(1, 7):
            with self.subTest(die=die):
                branch = resolve_roll(rules, die, {})
                self.assertEqual(branch["target"], 128)
                amounts = {e["key"]: e["amount"] for e in branch["effects"]}
                self.assertEqual(amounts,
                    {"habilete": -1, "endurance": -2} if die % 2 == 0
                    else {"habilete": -3, "endurance": -1})
        self.assertEqual(
            resolve_roll({"dice": 1, "branches": [
                {"when": "odd", "target": 128},
                {"when": "otherwise", "target": 1}]}, 5, {})["target"], 128)

    def test_serpent_240_prepares_combat_before_key_at_145(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {240: "Serpent : victoire §145.", 145: "Clé n°99.", 363: "Sortie."}
        w.go_to(240)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Serpent", 5, 2))
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:145"))
            alert.assert_called_once()
        with patch.object(w, "_roll", side_effect=[
                ([1, 1], 2), ([6, 6], 12)]), \
                patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w.current_paragraph, 145)
        self.assertNotIn("Clé de bronze 99", w.character["inventory"])
        w.undo_action()
        self.assertEqual(w.current_paragraph, 240)

    def test_giant_bats_251_can_escape_immediately_or_win(self):
        from book_events import DATA_PATH, flee_available
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {251: "Chauves-souris.", 344: "Victoire.", 399: "Rivière."}
        w.go_to(251)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Chauves-souris géantes", 6, 6))
        rules = w.book_event_catalogue["paragraphs"]["251"]["combat"]
        self.assertTrue(flee_available(rules, 0, 6, 20))
        previous = w.character["endurance"]
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(251)
        self.assertEqual(w.current_paragraph, 399)
        self.assertEqual(w.character["endurance"], previous - 2)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 251)

    def test_revisit_212_hides_drink_after_369_and_protects_link(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {212: "Boire §369 ou poursuivre §120.",
                        369: "Liquide.", 120: "Nord."}
        w.go_to(212)
        self.assertEqual(w.choice_layout.count(), 2)
        w.follow_catalogue_choice(369)
        self.assertEqual(w.current_paragraph, 369)
        w.go_to(212)
        self.assertEqual(w.choice_layout.count(), 1)
        with patch.object(QMessageBox, "information") as alert:
            w.follow_link(QUrl("paragraph:369"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 212)
        with patch.object(QMessageBox, "information") as alert:
            w.follow_catalogue_choice(369)
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 212)
        w.follow_catalogue_choice(120)
        self.assertEqual(w.current_paragraph, 120)

    def test_reader_links_are_handled_by_bifurk_not_qtextbrowser(self):
        from PySide6.QtCore import QUrl
        w = self.window
        self.assertFalse(w.reader.openLinks())
        self.assertFalse(w.reader.openExternalLinks())
        w.paragraphs = {212: "Boire au 369 ou continuer au 120.",
                        369: "Bouteille.", 120: "Couloir."}
        w.go_to(212)
        w.reader.anchorClicked.emit(QUrl("paragraph:369"))
        self.assertEqual(w.current_paragraph, 369)

    def test_reader_links_preserve_212_revisit_protection(self):
        from PySide6.QtCore import QUrl
        w = self.window
        w.paragraphs = {212: "Boire au 369 ou continuer au 120.",
                        369: "Bouteille.", 120: "Couloir."}
        w.go_to(212)
        w.reader.anchorClicked.emit(QUrl("paragraph:369"))
        w.go_to(212)
        self.assertEqual(w.current_paragraph, 212)
        with patch.object(QMessageBox, "information") as alert:
            w.reader.anchorClicked.emit(QUrl("paragraph:369"))
            alert.assert_called_once()
        self.assertEqual(w.current_paragraph, 212)

    def test_verified_routes_261_to_290_match_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            261: [345], 262: [199, 251], 265: [88],
            267: [312, 246, 79, 349], 268: [13, 282],
            269: [225], 270: [61, 394, 375], 271: [336, 214],
            272: [7], 274: [324, 356, 98], 276: [182],
            277: [146, 366, 11], 278: [156, 92], 280: [311],
            281: [10], 283: [251], 284: [46, 392],
            285: [213, 314], 288: [182], 290: [198],
        }
        for number, targets in expected.items():
            with self.subTest(paragraph=number):
                entry = data["paragraphs"][str(number)]
                routes = available_routes({}, entry)
                self.assertEqual([route["target"] for route in routes], targets)
                self.assertEqual(len(routes), len({r["target"] for r in routes}))
                self.assertTrue(all(route["label"] for route in routes))

    def test_crossroads_267_has_four_independent_routes_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {267: "Carrefour.", 312: "Nord.", 246: "Sud.",
                        79: "Ouest.", 349: "Est."}
        w.go_to(267)
        self.assertEqual(w.choice_layout.count(), 4)
        w.follow_catalogue_choice(349)
        self.assertEqual(w.current_paragraph, 349)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 267)

    def test_giant_rats_287_requires_actual_cheese_not_old_choice_marker(self):
        from book_events import DATA_PATH, available_routes
        catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        entry = catalogue["paragraphs"]["287"]
        with_cheese = {"inventory": ["Épée", "Fromage"]}
        without_cheese = {"inventory": ["Épée"]}
        self.assertEqual([r["target"] for r in available_routes(with_cheese, entry)], [32])
        self.assertEqual([r["target"] for r in available_routes(without_cheese, entry)], [309])
        self.assertEqual(with_cheese["inventory"], ["Épée", "Fromage"])
        self.assertEqual(without_cheese["inventory"], ["Épée"])

    def test_giant_rats_287_buttons_and_direct_text_links_follow_same_rule(self):
        from book_events import DATA_PATH
        from PySide6.QtCore import QUrl
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {287: "Rats géants, §32 ou §309.",
                        32: "Le Fromage.", 309: "Trois Rats."}
        w.character["inventory"] = ["Épée"]
        w.go_to(287)
        def enabled_choices():
            # Le choix du Fromage reste visible, grisé, tant qu'il manque.
            return [w.choice_layout.itemAt(i).widget() for i in range(w.choice_layout.count())
                    if w.choice_layout.itemAt(i).widget().isEnabled()]
        self.assertEqual(len(enabled_choices()), 1)
        with patch.object(QMessageBox, "information") as info:
            w.follow_link(QUrl("paragraph:32"))
            info.assert_called_once()
        self.assertEqual(w.current_paragraph, 287)
        w.character["inventory"].append("Fromage")
        w._render_choices_and_events(w.paragraphs[287])
        self.assertEqual(len(enabled_choices()), 1)
        with patch.object(QMessageBox, "information") as info:
            w.follow_link(QUrl("paragraph:309"))
            info.assert_called_once()
        self.assertEqual(w.current_paragraph, 287)
        w.follow_catalogue_choice(32)
        self.assertEqual(w.current_paragraph, 32)
        self.assertIn("Fromage", w.character["inventory"])
        w.undo_action()
        self.assertEqual(w.current_paragraph, 287)

    def test_ferryman_272_has_no_second_charge_after_127(self):
        from book_events import DATA_PATH, apply_entry, follow_catalogue_route
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        hero = {"gold": 10}
        self.assertTrue(follow_catalogue_route(hero, data["paragraphs"]["127"], 272))
        self.assertEqual(hero["gold"], 5)
        self.assertFalse(apply_entry(hero, set(), 272, data))
        self.assertTrue(follow_catalogue_route(hero, data["paragraphs"]["272"], 7))
        self.assertEqual(hero["gold"], 5)

    def test_verified_routes_291_to_320_match_pdf(self):
        from book_events import DATA_PATH, available_routes
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        expected = {
            291: [315, 52, 227], 293: [113],
            297: [150, 256], 299: [260, 359],
            300: [102, 303], 301: [82, 208], 302: [198],
            303: [128, 243], 307: [134, 87],
            308: [187, 54, 160, 354], 312: [308],
            314: [223, 300], 315: [306, 291],
            318: [85, 228], 320: [363],
        }
        for number, targets in expected.items():
            with self.subTest(paragraph=number):
                routes = available_routes({}, data["paragraphs"][str(number)])
                self.assertEqual([route["target"] for route in routes], targets)
                self.assertEqual(len({route["target"] for route in routes}), len(targets))

    def test_bridge_298_one_die_only_six_causes_fall(self):
        from book_events import DATA_PATH, resolve_roll
        catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = catalogue["paragraphs"]["298"]["roll"]
        self.assertEqual(roll["dice"], 1)
        for face in range(1, 7):
            with self.subTest(face=face):
                outcome = resolve_roll(roll, face, {})
                self.assertEqual(outcome["target"], 86 if face == 6 else 7)
                self.assertFalse(outcome.get("effects"))

    def test_swim_316_uses_stamina_not_skill_and_has_no_chance_cost(self):
        from book_events import DATA_PATH, resolve_roll
        catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        roll = catalogue["paragraphs"]["316"]["roll"]
        self.assertEqual(roll["dice"], 2)
        for face_sum in range(2, 13):
            with self.subTest(total=face_sum):
                outcome = resolve_roll(roll, face_sum, {
                    "endurance": 8, "habilete": 2, "chance": 1})
                self.assertEqual(outcome["target"], 151 if face_sum <= 8 else 218)
                self.assertFalse(outcome.get("effects"))

    def test_bridge_298_roll_then_undo_preserves_character(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {298: "Pont glissant.", 86: "Rivière.", 7: "Berge."}
        w.go_to(298)
        initial = dict(w.character)
        with patch.object(w, "_roll", return_value=([6], 6)):
            w.resolve_book_roll(298)
        self.assertEqual(w.current_paragraph, 86)
        self.assertEqual(w.character, initial)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 298)
        self.assertNotIn(298, w.completed_book_events)

    def test_werewolf_304_fight_can_escape_to_66_or_win_203(self):
        from book_events import DATA_PATH, flee_available
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {304: "Loup-garou.", 66: "Porte sud.", 203: "Victoire."}
        w.go_to(304)
        self.assertEqual((w.enemy_name.text(), w.enemy_skill.value(),
                          w.enemy_endurance.value()), ("Loup-garou", 8, 8))
        rules = w.book_event_catalogue["paragraphs"]["304"]["combat"]
        self.assertTrue(flee_available(rules, 0, 8, 20))
        self.assertTrue(w._combat_exit_pending(203))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            w.escape_scripted_combat(304)
        self.assertEqual(w.current_paragraph, 66)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 304)
        self.assertEqual(w.enemy_endurance.value(), 8)

    def test_crossroads_308_four_buttons_and_undo(self):
        from book_events import DATA_PATH
        w = self.window
        w.book_event_catalogue = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        w.paragraphs = {308: "Croisement.", 187: "Ouest.", 54: "Nord.",
                        160: "Sud.", 354: "Est."}
        w.go_to(308)
        self.assertEqual(w.choice_layout.count(), 4)
        w.follow_catalogue_choice(160)
        self.assertEqual(w.current_paragraph, 160)
        w.undo_action()
        self.assertEqual(w.current_paragraph, 308)

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
        import pymupdf as fitz
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

    def test_known_cover_bounds(self):
        if not self.pdf:
            self.skipTest('PDF privé absent')
        import pymupdf as fitz
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
