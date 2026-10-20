"""Régression de la partie réelle bloquée au §249."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as bifurk
from book_events import DATA_PATH, SHIELD_NAME
from navigation import destinations
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton


class FireDog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.w = bifurk.MainWindow()
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.paragraphs = {249:'Chien de test.',66:'Sortie sud.',304:'Vieil homme.'}
        for name, value in [('question',QMessageBox.No),('exec',QMessageBox.No),('information',QMessageBox.Ok)]:
            p = patch.object(QMessageBox, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.w.go_to(249)

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def tie(self, flame):
        # Héros H8+6 = 14 ; Chien H7+7 = 14.
        with patch.object(self.w,'_roll',side_effect=[([flame],flame),([3,4],7),([3,3],6)]):
            self.w.combat_round()

    def win(self, flame=6):
        with patch.object(self.w,'_roll',side_effect=[([flame],flame),([1,1],2),([6,6],12)]):
            self.w.combat_round()

    def test_arrival_prepares_h7_e6_no_stale_dialogue_routes(self):
        w=self.w
        self.assertEqual((w.enemy_name.text(),w.enemy_skill.value(),w.enemy_endurance.value()),('Chien',7,6))
        self.assertEqual([r['target'] for r in self.catalogue['paragraphs']['249']['routes']],[66,304])
        self.assertFalse(any(isinstance(w.choice_layout.itemAt(i).widget(),QPushButton) for i in range(w.choice_layout.count())))
        for target in (141,165,304):
            w.follow_link(QUrl(f'paragraph:{target}'))
            self.assertEqual(w.current_paragraph,249)

    def test_six_faces_fire_is_separate_even_when_attacks_tie(self):
        w=self.w
        for face in range(1,7):
            before=w.character['endurance']
            self.tie(face)
            self.assertEqual(w.character['endurance'],before-int(face<=2))
            self.assertEqual(w.enemy_endurance.value(),6)
        self.assertEqual(w.book_combat_assaults[249],6)
        self.assertTrue(any('Souffle' in w.combat_journal.item(i).text() for i in range(w.combat_journal.count())))

    def test_fire_damage_is_added_to_normal_wound(self):
        w=self.w
        with patch.object(w,'_roll',side_effect=[([1],1),([6,6],12),([1,1],2)]):
            w.combat_round()
        self.assertEqual(w.character['endurance'],17)
        self.assertEqual(w.enemy_endurance.value(),6)
        w.undo_action()
        self.assertEqual(w.character['endurance'],20)
        self.assertEqual(w.book_combat_assaults.get(249,0),0)
        w.redo_action()
        self.assertEqual(w.character['endurance'],17)

    def test_chance_alternative_uses_pre_spend_score_and_one_cost(self):
        w=self.w
        w.character['chance']=7
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(w,'_roll',side_effect=[([3,4],7),([3,4],7),([3,3],6)]) as roll:
            w.combat_round()
        self.assertEqual(w.character['endurance'],20)
        self.assertEqual(w.character['chance'],6)
        self.assertEqual([c.args for c in roll.call_args_list],[(2,),(2,),(2,)])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(w,'_roll',side_effect=[([6,6],12),([3,4],7),([3,3],6)]):
            w.combat_round()
        self.assertEqual((w.character['endurance'],w.character['chance']),(19,5))

    def test_chance_zero_cannot_become_negative(self):
        w=self.w
        w.character['chance']=0
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(w,'_roll',side_effect=[([1,1],2),([3,4],7),([3,3],6)]):
            w.combat_round()
        self.assertEqual(w.character['chance'],0)
        self.assertEqual(w.character['endurance'],19)

    def test_fatal_flame_stops_before_attack_rolls(self):
        w=self.w
        w.character['endurance']=1
        with patch.object(w,'_roll',return_value=([1],1)) as roll:
            w.combat_round()
        roll.assert_called_once_with(1)
        self.assertEqual(w.current_paragraph,249)
        self.assertEqual(w.character['endurance'],0)
        self.assertEqual(w.enemy_endurance.value(),6)
        w.follow_link(QUrl('paragraph:66'))
        w.follow_catalogue_choice(304)
        self.assertEqual(w.current_paragraph,249)
        with patch.object(w,'_roll') as roll:
            w.combat_round()
        roll.assert_not_called()
        w.undo_action()
        self.assertEqual(w.character['endurance'],1)

    def test_fire_does_not_use_physical_shield_reduction(self):
        w=self.w
        w.character['inventory'].append(SHIELD_NAME)
        w.character['shield_equipped']=True
        with patch.object(w,'_roll',side_effect=[([2],2),([3,4],7),([3,3],6)]) as roll:
            w.combat_round()
        self.assertEqual(roll.call_count,3)
        self.assertEqual(w.character['endurance'],19)

    def test_victory_awards_luck_once_and_preserves_two_choices(self):
        w=self.w
        w.character['chance']=4
        w.enemy_endurance.setValue(2)
        self.win()
        self.assertEqual(w.current_paragraph,249)
        self.assertEqual(w.character['chance'],5)
        self.assertTrue(w.character['book_facts']['dog249_defeated'])
        self.assertEqual(w.choice_layout.count(),2)
        w.combat_round()
        w.go_to(249)
        self.assertEqual(w.character['chance'],5)
        w.follow_catalogue_choice(304)
        self.assertEqual(w.current_paragraph,304)
        self.assertEqual(w.enemy_name.text(),'Loup-garou')

    def test_victory_luck_is_capped_and_undo_restores_combat(self):
        w=self.w
        w.enemy_endurance.setValue(2)
        self.win(flame=1)
        self.assertEqual((w.character['chance'],w.character['endurance']),(8,19))
        w.undo_action()
        self.assertEqual(w.current_paragraph,249)
        self.assertEqual(w.enemy_endurance.value(),2)
        self.assertEqual(w.character['endurance'],20)
        self.assertFalse(w.character.get('book_facts',{}).get('dog249_defeated'))
        w.redo_action()
        self.assertTrue(w.character['book_facts']['dog249_defeated'])
        self.assertEqual(w.character['endurance'],19)

    def test_leave_after_victory_is_free_by_button_or_link(self):
        w=self.w
        w.enemy_endurance.setValue(2)
        self.win()
        before=w.character['endurance']
        w.follow_catalogue_choice(66)
        self.assertEqual(w.current_paragraph,66)
        self.assertEqual(w.character['endurance'],before)
        w.undo_action()
        w.follow_link(QUrl('paragraph:66'))
        self.assertEqual(w.current_paragraph,66)
        self.assertEqual(w.character['endurance'],before)

    def test_flee_before_victory_is_paid_without_reward(self):
        w=self.w
        w.character['chance']=4
        w.follow_link(QUrl('paragraph:66'))
        self.assertEqual(w.current_paragraph,66)
        self.assertEqual((w.character['endurance'],w.character['chance']),(18,4))
        self.assertFalse(w.character.get('book_facts',{}).get('dog249_defeated'))
        w.undo_action()
        self.assertEqual(w.enemy_endurance.value(),6)
        self.assertEqual(w.character['endurance'],20)

    def test_fire_is_rolled_on_the_round_that_kills_dog_too(self):
        w=self.w
        w.enemy_endurance.setValue(2)
        before=w.character['endurance']
        self.win(flame=1)
        self.assertEqual(w.enemy_endurance.value(),0)
        self.assertEqual(w.character['endurance'],before-1)

    def test_save_load_mid_fight_and_after_victory_never_resets_enemy(self):
        w=self.w
        self.win()
        self.assertEqual(w.enemy_endurance.value(),4)
        for won in (False,True):
            if won:
                w.enemy_endurance.setValue(2)
                self.win()
            expected=w._snapshot()
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'dog.json'
                w._write_atomic(path,w._save_data())
                w.enemy_endurance.setValue(99)
                with patch.object(w,'_themed_save_dialog',return_value=str(path)):
                    w.load_game()
            self.assertEqual(w._snapshot(),expected)
            w.go_to(249)
            self.assertEqual(w.enemy_endurance.value(),expected['enemy_endurance'])

    def test_legacy_save_blocked_at249_initializes_only_missing_dog(self):
        w=self.w
        state=w._snapshot()
        state['prepared_book_encounters']=[]
        state['enemy_name']='Rat-garou'
        state['enemy_skill']=8
        state['enemy_endurance']=0
        state['character']['endurance']=13
        w._restore(state)
        self.assertEqual(w.character['endurance'],13)
        self.assertEqual((w.enemy_name.text(),w.enemy_skill.value(),w.enemy_endurance.value()),('Chien',7,6))
        self.assertIn(249,w.prepared_book_encounters)
        self.win()
        snapshot=w._snapshot()
        w._restore(snapshot)
        self.assertEqual(w.enemy_endurance.value(),4)

    def test_pdf249_targets_and_encounter_match_catalogue(self):
        pdf=next(ROOT.glob('*.pdf'),None)
        if pdf is None:
            self.skipTest('PDF privé absent')
        text=bifurk.extract_paragraphs(pdf)[249]
        self.assertEqual({target for _,_,target in destinations(text)},{66,304})
        from rules_engine import encounters
        self.assertIn({'name':'Chien','skill':7,'stamina':6},encounters(text))


if __name__=='__main__':
    unittest.main()
