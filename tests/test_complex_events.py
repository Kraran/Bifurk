"""Rencontres et interactions complexes, avec jets et décisions contrôlés.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
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
from book_events import DATA_PATH, available_routes, combat_skill
from navigation import destinations
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog


class ComplexEvents(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.w = bifurk.MainWindow()
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.paragraphs = {n:f'Passage de test {n}.' for n in range(1,401)}
        for name, value in [('information', QMessageBox.Ok), ('warning', QMessageBox.Ok),
                            ('question', QMessageBox.No), ('exec', QMessageBox.No)]:
            mock = patch.object(QMessageBox, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def win_round(self):
        """Imposer un assaut victorieux avec dés et choix de Chance contrôlés."""
        with patch.object(self.w, '_roll', side_effect=[([1,1],2),([6,6],12)]):
            self.w.combat_round()

    def lose_round(self):
        """Imposer un assaut perdu sans dépendre du générateur aléatoire."""
        with patch.object(self.w, '_roll', side_effect=[([6,6],12),([1,1],2)]):
            self.w.combat_round()

    def test_all_321_to_350_have_verified_entries(self):
        for n in range(321,351):
            self.assertEqual(self.catalogue['paragraphs'][str(n)]['status'], 'verifie')
        expected={321:[169],323:[8,255],324:[358],326:[35,229],
                  329:[157,392,299,238],332:[329,4],335:[182],336:[66,172,249],
                  337:[267],341:[46,392,220,191],342:[7],343:[92],
                  345:[381,311],347:[182],349:[267,30]}
        for n, targets in expected.items():
            self.assertEqual([r['target'] for r in self.catalogue['paragraphs'][str(n)]['routes']],targets)

    def test_key66_trade_cancel_locked_and_undo(self):
        w=self.w;w.go_to(322)
        w.character['locked_items']=['Armure de cuir']
        before=w._snapshot()
        with patch.object(QInputDialog,'getItem',return_value=('Épée',False)):
            w.take_book_trade('cle66')
        self.assertEqual(w._snapshot(),before)
        with patch.object(QInputDialog,'getItem',return_value=('Armure de cuir',True)):
            w.take_book_trade('cle66')
        self.assertEqual(w._snapshot(),before)
        with patch.object(QInputDialog,'getItem',return_value=('Épée',True)):
            w.take_book_trade('cle66')
        self.assertIn('Clé de cuivre 66',w.character['inventory'])
        self.assertNotIn('Épée',w.character['inventory'])
        before=copy.deepcopy(w.character)
        w.take_book_trade('cle66')
        self.assertEqual(w.character,before)
        w.undo_action()
        self.assertIn('Épée',w.character['inventory'])
        self.assertNotIn('Clé de cuivre 66',w.character['inventory'])

    def test_helmet_adds_attack_only_and_requires_possession(self):
        w=self.w;w.go_to(325)
        self.assertEqual(w.character['habilete'],8)
        self.assertEqual(combat_skill(w.character),9)
        w.go_to(325)
        self.assertEqual(combat_skill(w.character),9)
        w.character['inventory'].remove('Casque magique')
        self.assertEqual(combat_skill(w.character),8)

    def test_vampire_treasure_exchange_is_atomic_and_optional(self):
        w=self.w;w.character['chance']=1;w.go_to(327)
        self.assertEqual(w.character['chance'],4)
        self.assertEqual(w.character['gold'],1)
        with patch.object(QInputDialog,'getItem',return_value=('Lanterne',True)):
            w.take_book_trade('tresor_vampire')
        self.assertEqual(w.character['gold'],31)
        self.assertIn('Morceau de bois en Y',w.character['inventory'])
        self.assertIn('Livre du Vampire',w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.character['gold'],1)
        self.assertIn('Lanterne',w.character['inventory'])
        self.assertEqual(w.character['chance'],4)

    def test_y_sticks_exchange_and_rum_caps(self):
        w=self.w;w.go_to(328)
        with patch.object(QInputDialog,'getItem',return_value=('Lanterne',True)):
            w.take_book_trade('bois_y')
        self.assertIn('Deux morceaux de bois en Y',w.character['inventory'])
        w.character.update(endurance=18,chance=7)
        w.go_to(330)
        self.assertEqual((w.character['endurance'],w.character['chance']),(20,8))
        w.go_to(330)
        self.assertEqual(w.character['endurance'],20)
        w.undo_action()
        self.assertEqual((w.character['endurance'],w.character['chance']),(18,7))

    def test_candle_purchase_rechecks_cost_once_and_unlocks_darkness(self):
        w=self.w;w.go_to(334)
        w.apply_optional_book_event(334,'chandelle')
        self.assertNotIn('Chandelle bleue',w.character['inventory'])
        w.character['gold']=20
        w.apply_optional_book_event(334,'chandelle')
        self.assertEqual(w.character['gold'],0)
        w.apply_optional_book_event(334,'chandelle')
        self.assertEqual(w.character['gold'],0)
        w.go_to(292)
        routes=available_routes(w.character,self.catalogue['paragraphs']['292'])
        self.assertEqual([r['target'] for r in routes],[239])
        w.follow_link(QUrl('paragraph:40'))
        self.assertEqual(w.current_paragraph,292)
        w.follow_catalogue_choice(239)
        self.assertEqual(w.current_paragraph,239)

    def test_new_single_combats_block_victory_and_undo(self):
        w=self.w
        for n,target,h,e in [(331,287,8,8),(338,75,10,10)]:
            w.prepared_book_encounters.clear();w.go_to(n)
            self.assertEqual((w.enemy_skill.value(),w.enemy_endurance.value()),(h,e))
            w.follow_link(QUrl(f'paragraph:{target}'))
            w.follow_catalogue_choice(target)
            self.assertEqual(w.current_paragraph,n)
            w.enemy_endurance.setValue(2)
            self.win_round()
            self.assertEqual(w.current_paragraph,target)
            w.undo_action()
            self.assertEqual(w.current_paragraph,n)
            self.assertEqual(w.enemy_endurance.value(),2)

    def test_poison_dart_each_die_and_death_stops_navigation(self):
        w=self.w
        for face in range(1,7):
            w.character['endurance']=10;w.completed_book_events.discard(339);w.go_to(339)
            w.follow_link(QUrl('paragraph:201'))
            w.follow_catalogue_choice(201)
            self.assertEqual(w.current_paragraph,339)
            with patch.object(w,'_roll',return_value=([face],face)):
                w.resolve_book_roll(339)
            self.assertEqual(w.current_paragraph,201)
            self.assertEqual(w.character['endurance'],10-face)
            w.undo_action()
            self.assertEqual(w.current_paragraph,339)
            self.assertEqual(w.character['endurance'],10)
        w.character['endurance']=1
        with patch.object(w,'_roll',return_value=([6],6)):
            w.resolve_book_roll(339)
        self.assertEqual(w.character['endurance'],0)
        self.assertEqual(w.current_paragraph,339)
        w.follow_link(QUrl('paragraph:201'))
        self.assertEqual(w.current_paragraph,339)

    def test_portrait_routes_require_actual_objects(self):
        entry=self.catalogue['paragraphs']['340']
        self.assertEqual([r['target'] for r in available_routes({'inventory':[]},entry)],[])
        ch={'inventory':['Épée','Fromage','Cinq piquets de bois','Pierre précieuse de la statue']}
        self.assertEqual([r['target'] for r in available_routes(ch,entry)],[388,31,241,45])

    def test_cards_all_totals_parity_and_gold_floor(self):
        w=self.w
        for total in range(2,13):
            w.completed_book_events.discard(346);w.character.update(gold=3,chance=1);w.go_to(346)
            with patch.object(w,'_roll',return_value=([total],total)):
                w.perform_book_action('cards')
            self.assertEqual(w.character['gold'],3+total if total%2 else max(0,3-total))
            self.assertEqual(w.character['chance'],3 if total%2 else 1)
            self.assertEqual(w.current_paragraph,131)
            w.undo_action()
            self.assertEqual(w.character['gold'],3)
            self.assertEqual(w.current_paragraph,346)

    def test_cards_luck_uses_old_score_and_second_roll_only_on_success(self):
        w=self.w;w.character.update(gold=20,chance=7);w.go_to(346)
        with patch.object(w,'_roll',side_effect=[([3,4],7),([6,6],12)]) as roll:
            w.perform_book_action('cards_luck')
        self.assertEqual(roll.call_count,2)
        self.assertEqual((w.character['gold'],w.character['chance']),(32,8))
        w.undo_action();w.character['chance']=1
        with patch.object(w,'_roll',return_value=([1,1],2)) as roll:
            w.perform_book_action('cards_luck')
        self.assertEqual(roll.call_count,1)
        self.assertEqual((w.character['gold'],w.character['chance']),(18,0))
        w.go_to(346)
        with patch.object(w,'_roll') as roll:
            w.perform_book_action('cards_luck')
        roll.assert_not_called()
        w.perform_book_action('resolved_exit')
        self.assertEqual(w.current_paragraph,131)

    def test_invisibility_is_consumed_only_on_valid_route_and_undo(self):
        w=self.w;w.go_to(348)
        w.follow_link(QUrl('paragraph:51'))
        self.assertEqual(w.current_paragraph,348)
        w.character['inventory'].append("Potion d'Invisibilité")
        w.character['chance']=1
        w.follow_link(QUrl('paragraph:51'))
        self.assertEqual(w.current_paragraph,51)
        self.assertNotIn("Potion d'Invisibilité",w.character['inventory'])
        self.assertEqual(w.character['chance'],3)
        w.undo_action()
        self.assertEqual(w.current_paragraph,348)
        self.assertIn("Potion d'Invisibilité",w.character['inventory'])
        self.assertEqual(w.character['chance'],1)

    def test_rope_repeats_until_success_or_death_and_undo(self):
        w=self.w;w.go_to(125);w.character['chance']=7
        w.follow_link(QUrl('paragraph:73'))
        self.assertEqual(w.current_paragraph,125)
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_book_action('rope')
        self.assertEqual((w.character['endurance'],w.character['chance']),(19,6))
        self.assertNotIn(125,w.completed_book_events)
        with patch.object(w,'_roll',return_value=([3,3],6)):
            w.perform_book_action('rope')
        self.assertEqual(w.current_paragraph,73)
        self.assertEqual(w.character['chance'],5)
        w.undo_action()
        self.assertEqual(w.current_paragraph,125)
        self.assertEqual(w.character['chance'],6)
        w.character.update(chance=0,endurance=1)
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_book_action('rope')
        self.assertEqual(w.character['endurance'],0)
        with patch.object(w,'_roll') as roll:
            w.perform_book_action('rope')
        roll.assert_not_called()

    def test_three_luck_stops_at_first_failure_and_restores_progress(self):
        w=self.w;w.go_to(305);w.character['chance']=8
        for total in (8,7):
            with patch.object(w,'_roll',return_value=([total],total)):
                w.perform_book_action('three_luck')
        self.assertEqual(w.current_paragraph,305)
        self.assertEqual(w._book_state(305)['successes'],2)
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_book_action('three_luck')
        self.assertEqual(w.current_paragraph,108)
        self.assertEqual(w.character['chance'],5)
        w.undo_action()
        self.assertEqual(w.current_paragraph,305)
        self.assertEqual(w._book_state(305)['successes'],2)
        with patch.object(w,'_roll',return_value=([3,3],6)):
            w.perform_book_action('three_luck')
        self.assertEqual(w.current_paragraph,162)

    def test_wagers_bounds_tie_loss_win_repeated_and_cancel(self):
        w=self.w;w.go_to(130);w.character.update(gold=5,habilete=1,endurance=1,chance=1)
        before=w._snapshot()
        with patch.object(QInputDialog,'getInt',return_value=(6,True)),patch.object(w,'_roll') as roll:
            w.perform_book_action('wager')
        self.assertEqual(w._snapshot(),before);roll.assert_not_called()
        for totals,delta in [((7,7),0),((2,12),-1),((12,2),1)]:
            gold=w.character['gold']
            with patch.object(QInputDialog,'getInt',return_value=(1,True)),patch.object(w,'_roll',side_effect=[([x],x) for x in totals]):
                w.perform_book_action('wager')
            self.assertEqual(w.character['gold'],gold+delta)
        self.assertEqual((w.character['habilete'],w.character['endurance'],w.character['chance']),(3,3,3))
        w.undo_action()
        self.assertEqual((w.character['habilete'],w.character['endurance'],w.character['chance']),(1,1,1))
        before=w._snapshot()
        with patch.object(QInputDialog,'getInt',return_value=(1,False)):
            w.perform_book_action('wager')
        self.assertEqual(w._snapshot(),before)

    def test_keys_three_distinct_inventory_numbers_and_sum_no_consumption(self):
        w=self.w;w.go_to(139)
        names=['Clé de bronze 9','Clé de cuivre 66','Clé 111']
        w.character['inventory']+=names
        before=copy.deepcopy(w.character['inventory'])
        with patch.object(QInputDialog,'getItem',side_effect=[(n,True) for n in names]):
            w.perform_book_action('keys')
        self.assertEqual(w.current_paragraph,186)
        self.assertEqual(w.character['inventory'],before)
        w.undo_action()
        self.assertEqual(w.current_paragraph,139)
        self.assertFalse(w._book_state(139).get('tried'))
        with patch.object(QInputDialog,'getItem',side_effect=[(names[0],True),('',False)]):
            w.perform_book_action('keys')
        self.assertEqual(w.current_paragraph,139)
        self.assertFalse(w._book_state(139).get('tried'))

    def test_key_trap_uses_chance_and_death_or_damage_then_allows_keys(self):
        w=self.w;w.go_to(198);w.character['chance']=7
        w.perform_book_action('keys')
        self.assertEqual(w.current_paragraph,198)
        with patch.object(w,'_roll',return_value=([3,4],7)):
            w.perform_book_action('key_trap')
        self.assertEqual((w.character['endurance'],w.character['chance']),(18,6))
        before=w._snapshot()
        w.perform_book_action('key_trap')
        self.assertEqual(w._snapshot(),before)
        w.undo_action();w.character['chance']=1
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_book_action('key_trap')
        self.assertEqual(w.character['endurance'],0)
        self.assertEqual(w.character['chance'],0)

    def test_key182_penalty_is_per_attempt_and_undoable(self):
        w=self.w;w.go_to(182)
        self.assertEqual(w.character['endurance'],18)
        w.go_to(139);w.go_to(182)
        self.assertEqual(w.character['endurance'],16)
        w.undo_action()
        self.assertEqual(w.character['endurance'],18)
        w.redo_action()
        self.assertEqual(w.character['endurance'],16)

    def test_treasure_201_excludes_other_choices_and_undo(self):
        w=self.w;w.go_to(201);w.perform_book_action('loot','or')
        self.assertEqual(w.character['gold'],26)
        w.perform_book_action('loot','potion')
        self.assertNotIn("Potion d'Invisibilité",w.character['inventory'])
        w.undo_action();w.perform_book_action('loot','potion')
        self.assertEqual(w.character['gold'],1)
        self.assertIn("Potion d'Invisibilité",w.character['inventory'])

    def test_two_loot_choices_preserve_order_for_identification(self):
        w=self.w;w.go_to(313)
        w.perform_book_action('loot','crucifix');w.perform_book_action('loot','or')
        w.perform_book_action('loot','epee')
        self.assertEqual(w._book_state(313)['loot'],['crucifix','or'])
        self.assertEqual(w.character['gold'],1)
        w.follow_catalogue_choice(221);w.perform_book_action('identify')
        self.assertEqual(w.current_paragraph,170)
        self.assertIn('Crucifix en argent (valeur 4 PO)',w.character['inventory'])
        w.go_to(319);w.perform_book_action('identify_next')
        self.assertEqual(w.current_paragraph,110)
        self.assertEqual(w.character['gold'],11) # 8 + 2 cachées dans la botte
        w.go_to(319);w.perform_book_action('identify_next')
        self.assertEqual(w.current_paragraph,81)

    def test_revisits_are_saved_and_undo_does_not_count_as_new_visit(self):
        w=self.w
        for n,first,second in [(206,341,284),(227,131,291)]:
            w.go_to(n)
            entry=self.catalogue['paragraphs'][str(n)]
            self.assertIn(first,[r['target'] for r in available_routes(w.character,entry)])
            w.go_to(first);w.go_to(n)
            self.assertEqual([r['target'] for r in available_routes(w.character,entry)],[second])
            snapshot=json.loads(json.dumps(w._snapshot()))
            w._restore(snapshot)
            self.assertEqual(w.character['book_visits'][str(n)],2)
            w.undo_action()
            self.assertEqual(w.character['book_visits'][str(n)],1)

    def test_sequences_new_enemies_and_zombie_reward_timing(self):
        w=self.w
        for number,target,count in [(199,283,2),(282,115,4),(309,124,3)]:
            w.book_combat_sequence=None;w.character['chance']=1;w.go_to(number)
            for index in range(count):
                self.assertEqual(w.book_combat_sequence['index'],index)
                w.follow_link(QUrl(f'paragraph:{target}'))
                self.assertEqual(w.current_paragraph,number)
                w.enemy_endurance.setValue(2);self.win_round()
                if number==282:
                    self.assertEqual(w.character['chance'],3)
            self.assertEqual(w.current_paragraph,target)
            w.undo_action()
            self.assertEqual(w.current_paragraph,number)
            self.assertEqual(w.book_combat_sequence['index'],count-1)

    def test_ghoul_four_wounds_not_damage_and_death(self):
        w=self.w;w.go_to(230)
        for i in range(4):
            self.lose_round()
            self.assertEqual(w._book_state(230)['wounds'],i+1)
        self.assertEqual(w.current_paragraph,64)
        self.assertEqual(w.character['endurance'],0)
        w.undo_action()
        self.assertEqual(w.current_paragraph,230)
        self.assertEqual(w._book_state(230)['wounds'],3)
        self.assertEqual(w.character['endurance'],14)
        w.character['endurance']=1;self.lose_round()
        self.assertEqual(w.current_paragraph,64)

    def test_ghoul_victory_before_fourth_wound(self):
        w=self.w;w.go_to(230);self.lose_round();w.enemy_endurance.setValue(2)
        self.win_round()
        self.assertEqual(w.current_paragraph,390)

    def test_silver_only_damage_and_every_third_wound(self):
        w=self.w;w.go_to(211)
        self.win_round()
        self.assertEqual(w.enemy_endurance.value(),6)
        w.follow_link(QUrl('paragraph:173'))
        self.assertEqual(w.current_paragraph,211)
        w.character['inventory'].append("Ciseau à lame d'argent")
        w.follow_link(QUrl('paragraph:173'))
        self.assertEqual(w.current_paragraph,173)
        for i in range(3):self.lose_round()
        self.assertEqual(w.current_paragraph,24)
        self.assertEqual(w.character['habilete'],7)
        for i in range(3):self.lose_round()
        self.assertEqual(w.character['habilete'],6)
        self.assertEqual(w.enemy_endurance.value(),6)
        w.undo_action()
        self.assertEqual(w.character['habilete'],7)

    def test_silver_arrow_consumed_and_lucky_victory_is_undoable(self):
        w=self.w;w.character['inventory'] += ["Ciseau à lame d'argent",'Arc','Flèche d’argent']
        w.go_to(173)
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_book_action('silver_arrow')
        self.assertEqual(w.current_paragraph,135)
        self.assertNotIn('Flèche d’argent',w.character['inventory'])
        w.undo_action()
        self.assertIn('Flèche d’argent',w.character['inventory'])
        self.assertEqual(w.enemy_endurance.value(),6)

    def test_wandering_context_all_six_monsters_and_return(self):
        w=self.w
        for source,target in [(295,48),(306,291)]:
            for face in range(1,7):
                w.go_to(source);w.follow_catalogue_choice(161)
                w.follow_link(QUrl(f'paragraph:{target}'))
                self.assertEqual(w.current_paragraph,161)
                with patch.object(w,'_roll',return_value=([face],face)):
                    w.perform_book_action('wandering')
                monster=self.catalogue['paragraphs']['161']['combat']['enemies'][face-1]
                self.assertEqual(w.enemy_name.text(),monster['name'])
                self.assertEqual(w.enemy_endurance.value(),monster['stamina'])
                w.enemy_endurance.setValue(2);self.win_round()
                self.assertEqual(w.current_paragraph,target)
                w.undo_action()
                self.assertEqual(w.current_paragraph,161)
                self.assertEqual(w.enemy_endurance.value(),2)

    def test_wandering_direct_entry_cannot_invent_return(self):
        w=self.w;w.go_to(161)
        before=w.enemy_name.text()
        with patch.object(w,'_roll') as roll:
            w.perform_book_action('wandering');w.combat_round()
        roll.assert_not_called()
        self.assertEqual(w.enemy_name.text(),before)

    def test_vampire_escape_needs_six_rounds_then_six_more_after_failure(self):
        w=self.w;w.go_to(333)
        with patch.object(w,'_roll') as roll:w.escape_scripted_combat(333)
        roll.assert_not_called()
        w.book_combat_assaults[333]=6;w.character['chance']=2
        with patch.object(w,'_roll',return_value=([3,3],6)):
            w.escape_scripted_combat(333)
        self.assertEqual(w.current_paragraph,333)
        self.assertEqual(w._book_state(333)['escape_after'],12)
        self.assertEqual(w.character['chance'],1)
        with patch.object(w,'_roll') as roll:w.escape_scripted_combat(333)
        roll.assert_not_called()
        w.book_combat_assaults[333]=12;w.character['chance']=8
        with patch.object(w,'_roll',return_value=([4,4],8)):
            w.escape_scripted_combat(333)
        self.assertEqual(w.current_paragraph,380)
        self.assertEqual((w.character['chance'],w.character['endurance']),(7,18))
        w.undo_action()
        self.assertEqual(w.current_paragraph,333)
        self.assertEqual(w.character['endurance'],20)

    def test_vampire_hypnosis_on_unlucky_11_or_12(self):
        w=self.w;w.go_to(333);w.book_combat_assaults[333]=6;w.character['chance']=1
        with patch.object(w,'_roll',return_value=([5,6],11)):
            w.escape_scripted_combat(333)
        self.assertEqual(w.current_paragraph,224)
        self.assertEqual(w.character['chance'],0)

    def test_vampire_stake_lucky_and_unlucky_routes(self):
        w=self.w;w.go_to(17)
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_book_action('stake_luck')
        self.assertEqual(w.current_paragraph,17)
        self.assertEqual(w._book_state(17)['vampire_stamina'],7)
        w.perform_book_action('stake_continue');self.assertEqual(w.current_paragraph,144)
        w.undo_action();w.undo_action()
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_book_action('stake_luck')
        self.assertEqual(w.current_paragraph,327)

    def test_paired_skeletons_choose_one_target_and_defend_other(self):
        w=self.w;w.go_to(140)
        self.assertEqual(w.enemy_endurance.value(),5)
        w.enemy_endurance.setValue(2);self.win_round()
        self.assertTrue(w._book_state(140)['choose_pair'])
        with patch.object(w,'_roll') as roll:w.combat_round()
        roll.assert_not_called()
        for index in (0,1):
            w.perform_book_action('pair_target',index)
            before=w.character['endurance']
            # L'ennemi ciblé meurt, le second porte tout de même son coup.
            w.enemy_endurance.setValue(2)
            with patch.object(w,'_roll',side_effect=[([1,1],2),([6,6],12),([6,6],12),([1,1],2)]):
                w.combat_round()
            self.assertEqual(w.character['endurance'],before-2)
        self.assertEqual(w.current_paragraph,395)
        self.assertIn(140,w.completed_book_events)
        w.undo_action()
        self.assertEqual(w.current_paragraph,140)
        self.assertEqual(w.enemy_endurance.value(),2)
        self.assertEqual(w._book_state(140)['pair'],1)

    def test_paired_skeleton_defender_cannot_be_wounded(self):
        w=self.w;w.go_to(140);w.enemy_endurance.setValue(2);self.win_round()
        w.perform_book_action('pair_target',0)
        defender=copy.deepcopy(w._book_state(140)['defender'])
        with patch.object(w,'_roll',side_effect=[([1,1],2),([6,6],12),([1,1],2),([6,6],12)]):
            w.combat_round()
        self.assertEqual(w._book_state(140)['defender'],defender)
        self.assertEqual(w.enemy_endurance.value(),4)

    def test_complex_state_json_roundtrip_and_actual_save_load(self):
        w=self.w;w.go_to(305)
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_book_action('three_luck')
        state=json.loads(json.dumps(w._snapshot()))
        w._restore(state)
        self.assertEqual(w._book_state(305)['successes'],1)
        self.assertEqual(w.character['chance'],7)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json'
            w._write_atomic(path,w._save_data())
            w.character['book_state'].clear()
            with patch.object(w,'_themed_save_dialog',return_value=str(path)):
                w.load_game()
        self.assertEqual(w._book_state(305)['successes'],1)
        self.assertEqual(w.current_paragraph,305)

    def test_source_rules_not_enabled_for_unrecognized_book(self):
        w=self.w;w.book_event_catalogue=None;w.go_to(325)
        self.assertNotIn('Casque magique',w.character['inventory'])
        before=w._snapshot()
        w.perform_book_action('cards')
        self.assertEqual(w._snapshot(),before)

    def test_coverage_is_complete_through_350(self):
        self.assertFalse([n for n in range(1,351) if str(n) not in self.catalogue['paragraphs']])
        self.assertTrue(all(n>350 for n in self.catalogue['review_pending']))

    def test_alarm12_requires_wandering_combat_once_and_returns_to_choices(self):
        w=self.w;w.go_to(12)
        w.follow_link(QUrl('paragraph:256'))
        self.assertEqual(w.current_paragraph,12)
        w.follow_catalogue_choice(161)
        with patch.object(w,'_roll',return_value=([1],1)):
            w.perform_book_action('wandering')
        w.enemy_endurance.setValue(2);self.win_round()
        self.assertEqual(w.current_paragraph,12)
        self.assertEqual([r['target'] for r in available_routes(w.character,self.catalogue['paragraphs']['12'])],[256,364])
        w.undo_action()
        self.assertEqual(w.current_paragraph,161)
        self.assertFalse(w.character.get('book_facts',{}).get('alarm12_done'))
        self.win_round();w.follow_catalogue_choice(364)
        self.assertEqual(w.current_paragraph,364)

    def test_remaining_wandering_sources_preserve_their_return(self):
        w=self.w
        for source,target in [(14,117),(234,43)]:
            w.go_to(source);w.follow_catalogue_choice(161)
            with patch.object(w,'_roll',return_value=([1],1)):
                w.perform_book_action('wandering')
            w.enemy_endurance.setValue(2);self.win_round()
            self.assertEqual(w.current_paragraph,target)

    def test_giant_opening_luck_required_before_assault_and_escape(self):
        w=self.w;w.go_to(163)
        w.enemy_endurance.setValue(2)
        with patch.object(w,'_roll') as roll:w.combat_round()
        roll.assert_not_called()
        self.assertEqual(w.current_paragraph,163)
        w.character['chance']=1
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_book_action('opening_luck')
        self.assertEqual((w.character['endurance'],w.character['chance']),(19,0))
        self.win_round()
        self.assertEqual(w.current_paragraph,28)
        w.undo_action()
        self.assertEqual(w.current_paragraph,163)
        self.assertTrue(w._book_state(163)['opening_done'])
        w.undo_action()
        self.assertFalse(w._book_state(163).get('opening_done'))

    def test_minotaur_victory_empty_revisit_is_free_and_no_reward_reset(self):
        w=self.w;w.go_to(179);w.enemy_endurance.setValue(2);self.win_round()
        self.assertEqual(w.current_paragraph,258)
        self.assertTrue(w.character['book_facts']['minotaur_dead'])
        w.go_to(179)
        self.assertEqual(w.choice_layout.count(),1)
        endurance=w.character['endurance']
        w.follow_link(QUrl('paragraph:54'))
        self.assertEqual(w.current_paragraph,54)
        self.assertEqual(w.character['endurance'],endurance)
        w.go_to(179);w.follow_link(QUrl('paragraph:258'))
        self.assertEqual(w.current_paragraph,179)

    def test_invisible_sorcerer_attack_bonus_and_three_damage(self):
        w=self.w;w.go_to(39)
        # H8 + 2 + 7 = 17, contre H11 + 5 = 16 : seul le bonus gagne.
        with patch.object(w,'_roll',side_effect=[([2,3],5),([3,4],7)]):w.combat_round()
        self.assertEqual(w.enemy_endurance.value(),15)
        self.assertEqual(w.character['habilete'],8)
        w.undo_action()
        self.assertEqual(w.enemy_endurance.value(),18)

    def test_invisible_sorcerer_defense_all_six_faces(self):
        w=self.w;w.go_to(39)
        for face,damage in [(1,2),(2,1),(3,2),(4,1),(5,2),(6,0)]:
            w.character['endurance']=20
            with patch.object(w,'_roll',side_effect=[([6,6],12),([1,1],2),([face],face)]):w.combat_round()
            self.assertEqual(w.character['endurance'],20-damage)

    def test_invisibility_and_silver_arrow_routes_consume_once(self):
        w=self.w;w.go_to(105)
        w.character['inventory'] += ["Potion d'Invisibilité",'Arc','Flèche d’argent']
        w.follow_catalogue_choice(194)
        self.assertNotIn('Flèche d’argent',w.character['inventory'])
        w.undo_action()
        self.assertIn('Flèche d’argent',w.character['inventory'])
        w.follow_catalogue_choice(39)
        self.assertEqual(w.current_paragraph,39)
        self.assertNotIn("Potion d'Invisibilité",w.character['inventory'])
        self.assertEqual(w.enemy_endurance.value(),18)

    def test_drunk_goblins_attack_bonus_is_specific_to_encounter(self):
        w=self.w;w.go_to(116)
        # H8 + 1 + 2 = 11 contre H5 + 5 = 10.
        with patch.object(w,'_roll',side_effect=[([2,3],5),([1,1],2)]):w.combat_round()
        self.assertEqual(w.enemy_endurance.value(),3)
        self.assertEqual(w.character['habilete'],8)
        self.assertEqual(w.book_combat_sequence['index'],0)

    def test_choose_armor_does_not_keep_two_and_can_undo(self):
        w=self.w;w.go_to(313);w.perform_book_action('loot','armure')
        w.follow_catalogue_choice(221);w.perform_book_action('identify')
        self.assertEqual(w.current_paragraph,72)
        w.follow_link(QUrl('paragraph:319'));self.assertEqual(w.current_paragraph,72)
        w.perform_book_action('armor_new')
        self.assertEqual(w.current_paragraph,319)
        self.assertIn('Armure trouvée',w.character['inventory'])
        self.assertNotIn('Armure de cuir',w.character['inventory'])
        w.undo_action()
        self.assertIn('Armure de cuir',w.character['inventory'])
        self.assertEqual(w.current_paragraph,72)

    def test_dragon_formula_is_remembered_beyond_inventory_and_saved(self):
        w=self.w;w.go_to(126)
        self.assertEqual([r['target'] for r in available_routes(w.character,self.catalogue['paragraphs']['126'])],[152])
        w.go_to(296);w.go_to(126)
        self.assertEqual([r['target'] for r in available_routes(w.character,self.catalogue['paragraphs']['126'])],[26])
        w.follow_catalogue_choice(26)
        self.assertEqual(w.current_paragraph,26)
        w.follow_catalogue_choice(371)
        self.assertEqual(w.current_paragraph,371)

    def test_swimming_return_cost_can_be_fatal_and_blocks_arrival(self):
        w=self.w;w.go_to(151);w.character['endurance']=1
        w.follow_catalogue_choice(218)
        self.assertEqual(w.current_paragraph,151)
        self.assertEqual(w.character['endurance'],0)
        w.undo_action()
        self.assertEqual(w.character['endurance'],1)

    def test_precombat_escape_always_has_cost_even_with_previous_enemy_dead(self):
        w=self.w;w.go_to(65);w.enemy_endurance.setValue(0)
        w.escape_scripted_combat(65)
        self.assertEqual(w.current_paragraph,293)
        self.assertEqual(w.character['endurance'],18)
        w.undo_action()
        self.assertEqual(w.current_paragraph,65)
        self.assertEqual(w.character['endurance'],20)

    def test_interrupted_meal_finishes_once_after_worm_victory(self):
        w=self.w;w.go_to(143);w.character['endurance']=10;w.enemy_endurance.setValue(2)
        self.win_round()
        self.assertEqual(w.current_paragraph,44)
        self.assertEqual((w.character['endurance'],w.character['provisions']),(14,9))
        w.go_to(44)
        self.assertEqual((w.character['endurance'],w.character['provisions']),(14,9))
        w.undo_action()
        self.assertEqual(w.current_paragraph,143)
        self.assertEqual((w.character['endurance'],w.character['provisions']),(10,10))

    def test_real_pdf_321_350_routes_match_explicit_references(self):
        pdf=next(ROOT.glob('*.pdf'),None)
        if pdf is None:self.skipTest('PDF privé absent')
        texts=bifurk.extract_paragraphs(pdf)
        for n in range(321,351):
            entry=self.catalogue['paragraphs'][str(n)]
            targets={r['target'] for r in entry.get('routes',[])}
            targets|={b['target'] for b in entry.get('roll',{}).get('branches',[])}
            combat=entry.get('combat',{})
            targets|={combat[k] for k in ('victory_target','escape_target','hypnosis_target') if combat.get(k)}
            if n==346:targets.add(131)
            # Les renvois conditionnels doivent rester liés à ce paragraphe réel.
            self.assertEqual(targets,{t for _,_,t in destinations(texts[n])},f'§{n}')

    def test_mid_pair_save_load_restores_opponent_and_defender(self):
        w=self.w;w.go_to(140);w.enemy_endurance.setValue(2);self.win_round()
        w.perform_book_action('pair_target',1)
        w.enemy_endurance.setValue(3)
        expected=w._snapshot()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fight.json'
            w._write_atomic(path,w._save_data())
            w.enemy_name.setText('Autre adversaire')
            w.enemy_skill.setValue(12);w.enemy_endurance.setValue(99)
            w.character['book_state'].clear()
            with patch.object(w,'_themed_save_dialog',return_value=str(path)):
                w.load_game()
        self.assertEqual(w._snapshot(),expected)

    def test_silver_third_wound_link_and_arrow_without_bow_are_blocked(self):
        w=self.w;w.character['inventory'] += ["Ciseau à lame d'argent",'Flèche d’argent']
        w.go_to(173)
        w.follow_link(QUrl('paragraph:24'))
        self.assertEqual(w.current_paragraph,173)
        with patch.object(w,'_roll') as roll:w.perform_book_action('silver_arrow')
        roll.assert_not_called()
        self.assertIn('Flèche d’argent',w.character['inventory'])


if __name__=='__main__':
    unittest.main()
