"""Corrections issues de la partie de test du Sorcier : blocage du §249, règles,
jets visibles et titres sans révélation anticipée.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Aucun texte du PDF n'est embarqué : les paragraphes sont des textes factices."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as bifurk
from book_events import DATA_PATH, missing_requirement
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

FORET_PATH = ROOT / 'catalogues' / 'evenements_foret_1983.json'


class CorrectionsSorcier(unittest.TestCase):
    """Régressions de la partie de test ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.w = bifurk.MainWindow()
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.paragraphs = {n: f'Passage de test {n}.' for n in range(1, 401)}
        for name, value in [('information', QMessageBox.Ok), ('warning', QMessageBox.Ok),
                            ('question', QMessageBox.No), ('exec', QMessageBox.No)]:
            mock = patch.object(QMessageBox, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        autosave = patch.object(self.w, '_autosave', return_value=None)
        autosave.start()
        self.addCleanup(autosave.stop)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    # --- outils -----------------------------------------------------------------
    def choice_buttons(self):
        layout = self.w.choice_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())
                if isinstance(layout.itemAt(i).widget(), QPushButton)]

    def event_buttons(self):
        layout = self.w.event_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())
                if isinstance(layout.itemAt(i).widget(), QPushButton)]

    def win_round(self, extra=()):
        with patch.object(self.w, '_roll', side_effect=[*extra, ([1, 1], 2), ([6, 6], 12)]):
            self.w.combat_round()

    # --- 1. §249 : choix visibles après la victoire --------------------------------
    def test_249_choices_visible_after_victory_and_potion(self):
        w = self.w
        w.go_to(249)
        w.character.update(habilete=12, endurance=10)
        for _ in range(3):
            if w.enemy_endurance.value() > 0:
                self.win_round(extra=[([6], 6)])  # souffle du chien raté
        self.assertEqual(w.enemy_endurance.value(), 0)
        self.assertEqual(w.current_paragraph, 249)
        self.assertFalse(w.choice_group.isHidden())
        self.assertEqual(sorted(b.isEnabled() for b in self.choice_buttons()), [True, True])
        w.character.update(potion='Potion de Vigueur', potion_doses=2, endurance=5)
        w.use_care('potion')
        self.assertFalse(w.choice_group.isHidden())
        self.assertEqual(len(self.choice_buttons()), 2)

    def test_choice_group_follows_buttons_after_every_render(self):
        w = self.w
        w.go_to(3)
        self.assertFalse(w.choice_group.isHidden())
        w.go_to(161)  # aucun choix direct : le groupe est masqué
        self.assertTrue(w.choice_group.isHidden())

    # --- 2. Règles : choix grisés avec leur raison -------------------------------
    def test_payer_3_greyed_with_reason(self):
        w = self.w
        w.character['gold'] = 2
        w.go_to(3)
        pay = next(b for b in self.choice_buttons() if 'Payer' in b.text())
        self.assertFalse(pay.isEnabled())
        self.assertIn('3 pièces d’or (vous en avez 2)', pay.text())
        self.assertIn('Indisponible', pay.toolTip())
        w.character['gold'] = 3
        w.go_to(3)
        pay = next(b for b in self.choice_buttons() if 'Payer' in b.text())
        self.assertTrue(pay.isEnabled())

    def test_payer_127_greyed_with_reason(self):
        w = self.w
        w.character['gold'] = 4
        w.go_to(127)
        give = next(b for b in self.choice_buttons() if 'Donner' in b.text())
        self.assertFalse(give.isEnabled())
        self.assertIn('5 pièces d’or (vous en avez 4)', give.toolTip())

    def test_shop_option_334_greyed_with_reason(self):
        w = self.w
        w.character['gold'] = 7
        w.go_to(334)
        candle = next(b for b in self.event_buttons() if 'Chandelle' in b.text())
        self.assertFalse(candle.isEnabled())
        self.assertIn('20 pièces d’or (vous en avez 7)', candle.toolTip())

    def test_story_conditions_stay_hidden(self):
        char = {'gold': 0, 'inventory': [], 'facts': []}
        self.assertIsNone(missing_requirement(char, {'kind': 'visit_count', 'paragraph': 227, 'max': 1}))
        self.assertIsNone(missing_requirement(char, {'kind': 'fact', 'key': 'secret'}))
        self.assertEqual(missing_requirement(char, {'kind': 'has_item', 'name': 'Fromage'}),
                         'Il vous faut « Fromage ».')
        self.assertIsNone(missing_requirement({'gold': 5}, {'kind': 'min_stat', 'key': 'gold', 'value': 3}))

    def test_meal_offered_at_203(self):
        w = self.w
        w.character.update(provisions=3, endurance=8)
        w.go_to(203)
        meal = next(b for b in self.event_buttons() if 'repas' in b.text().lower())
        self.assertTrue(meal.isEnabled())
        meal.click()
        self.assertEqual(w.character['provisions'], 2)

    def test_meal_at_218_only_when_arriving_from_158_or_316(self):
        w = self.w
        w.character.update(provisions=3, endurance=8)
        w.go_to(209)
        w.go_to(218)
        self.assertFalse(any('repas' in b.text().lower() for b in self.event_buttons()))
        w.go_to(316)
        w.go_to(218)
        self.assertTrue(any('repas' in b.text().lower() and b.isEnabled() for b in self.event_buttons()))

    def test_starting_gold_is_one(self):
        # L'introduction du livre fait emporter une seule pièce d'or pour le voyage.
        self.assertEqual(self.w._new_character_template()['gold'], 1)

    # --- 3. Jets visibles --------------------------------------------------------
    def test_wandering_roll_is_shown(self):
        w = self.w
        w.go_to(295)
        w.follow_catalogue_choice(161)
        w.follow_link(QUrl('paragraph:48'))
        with patch.object(w, '_roll', return_value=([4], 4)):
            w.perform_book_action('wandering')
        self.assertIn('Monstre errant : 1d6 = 4 → Rat géant', w.rules_log.text())

    def test_roll_kept_after_automatic_jump_82_and_156(self):
        w = self.w
        w.character['chance'] = 9
        w.go_to(82)
        with patch.object(w, '_roll', return_value=([3, 4], 7)):
            w.resolve_book_roll(82)
        self.assertEqual(w.current_paragraph, 147)
        self.assertIn('dés [3, 4] = 7 contre Chance 9 : réussite', w.rules_log.text())
        w.character['habilete'] = 6
        w.go_to(156)
        with patch.object(w, '_roll', return_value=([6, 5], 11)):
            w.resolve_book_roll(156)
        self.assertEqual(w.current_paragraph, 92)
        self.assertIn('contre Habileté 6 : échec', w.rules_log.text())

    def test_three_rolls_kept_at_305(self):
        w = self.w
        w.go_to(305)
        w.character['chance'] = 10
        for total in (5, 6, 7):
            with patch.object(w, '_roll', return_value=([total], total)):
                w.perform_book_action('three_luck')
        self.assertEqual(w.current_paragraph, 162)
        log = w.rules_log.text()
        for n in (1, 2, 3):
            self.assertIn(f'jet {n} :', log)

    def test_cards_346_dice_kept_after_jump(self):
        w = self.w
        w.character.update(gold=5, chance=9)
        w.go_to(346)
        with patch.object(w, '_roll', side_effect=[([3, 4], 7), ([5, 6], 11)]):
            w.perform_book_action('cards_luck')
        self.assertEqual(w.current_paragraph, 131)
        self.assertIn('Chance [3, 4] = 7 contre 9 : réussite, gain [5, 6] = 11', w.rules_log.text())

    def test_no_choice_message_points_to_event(self):
        w = self.w
        w.go_to(305)
        layout = w.choice_layout
        texts = [layout.itemAt(i).widget().text() for i in range(layout.count())
                 if layout.itemAt(i).widget() is not None]
        self.assertIn('La suite dépend de l’événement ci-dessous.', texts)

    # --- 4. Pas de révélation anticipée ------------------------------------------
    def test_sorcier_labels_do_not_spoil(self):
        p = self.catalogue['paragraphs']
        labels = [r['label'] for r in p['227']['routes']] + [r['label'] for r in p['358']['routes']]
        self.assertFalse(any('Nain' in label or 'Sorcier' in label for label in labels))
        for number, word in [(179, 'Minotaure'), (249, 'feu'), (142, 'Sorcier'),
                             (168, 'Farfadet'), (230, 'Goule'), (100, 'Nain')]:
            self.assertNotIn(word, p[str(number)]['title'])

    def test_foret_titles_do_not_spoil(self):
        p = json.loads(FORET_PATH.read_text(encoding='utf-8'))['paragraphs']
        for number, word in [(29, 'Orque'), (57, 'Wyverne'), (196, 'Troll'), (265, 'Géant'),
                             (285, 'Loup'), (328, 'Dévoreuse'), (133, 'Lenteur'), (360, 'Bandit')]:
            self.assertNotIn(word, p[str(number)]['title'])
        self.assertNotIn('coupure', ' '.join(r['label'] for r in p['295']['routes']))

    # --- 5. Carnet ---------------------------------------------------------------
    def test_open_carnet_labels_follow_current_paragraph(self):
        w = self.w
        w.show()
        w.go_to(295)
        w.open_carnet()
        w.go_to(161)
        self.assertEqual(w.carnet_overlay.book.insert_button.text(), '§  Insérer §161')
        w.close_carnet()


if __name__ == '__main__':
    unittest.main()
