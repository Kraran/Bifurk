"""Présentation multi-grimoires avec PDF synthétiques ; contrôle privé conditionnel de l'édition."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton, QSpinBox, QListWidget, QLabel

import main
from grimoire_library import GrimoireLibraryDialog, imported_grimoires
from grimoire_modules.registry import available_modules, module_for_pdf, pdf_digest
from save_slots import SaveSlotsDialog


class ForetPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.modules = {m.engine: m for m in available_modules()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for key, path in {'APP_DIR': self.root, 'BOOKS_DIR': self.root/'donnees/grimoires',
                          'SAVES_DIR': self.root/'donnees/sauvegardes',
                          'SETTINGS_DIR': self.root/'donnees/parametres'}.items():
            mock = patch.object(main, key, path)
            mock.start()
            self.addCleanup(mock.stop)
        main.init_portable_dirs()
        self.sources = {}
        for name in ('foret', 'sorcier'):
            path = self.root / f'{name}.pdf'
            with pymupdf.open() as document:
                for index in range(170):
                    page = document.new_page(width=504.6, height=842)
                    if index == 0:
                        page.draw_rect(page.rect, color=(.3,.4,.2), fill=(.7,.7,.4))
                    if index == 18:
                        page.insert_text((30,40), '1\nUne foret. Rendez-vous au 2.\n2\nUne clairiere.\n86\nUne tour.\n350\nUn chemin.')
                document.save(path)
            self.sources[name] = path
        def recognize(path):
            return self.modules['foret-1983' if 'foret' in Path(path).name else 'sorcier-1982']
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, side_effect=recognize)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information','warning','critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        # Le DeferredDelete Qt peut suivre le nettoyage du dossier temporaire.
        self.addCleanup(self.w.sounds._close_log)
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        mock = patch.object(self.w, '_roll', side_effect=lambda count, *a, **k: ([3]*count, 3*count))
        self.roll = mock.start()
        self.addCleanup(mock.stop)

    def open(self, name='foret'):
        self.w.open_pdf(self.sources[name], startup=True)

    def start(self):
        self.w._begin_adventure('Eldan')

    def test_book_announcements_on_open_not_on_creation_refresh(self):
        for name, engine in (('foret','foret-1983'), ('sorcier','sorcier-1982')):
            with self.subTest(book=name), patch.object(self.w.sounds, 'play_book_intro') as play:
                self.open(name)
                play.assert_called_once_with(engine)
                play.reset_mock()
                self.w._show_book_title()
                self.w.change_reader_font_size(2)
                play.assert_not_called()

    def test_book_announcements_on_successful_load_only(self):
        for name, engine in (('foret','foret-1983'), ('sorcier','sorcier-1982')):
            with self.subTest(book=name):
                self.open(name)
                self.start()
                path = main.SAVES_DIR/f'annonce-{name}.json'
                self.w._write_atomic(path, self.w._save_data())
                with patch.object(self.w.sounds, 'play_book_intro') as play, \
                     patch('main.extract_paragraphs', return_value=dict(self.w.paragraphs)):
                    self.assertTrue(self.w.load_game(path, announce=False))
                    play.assert_called_once_with(engine)
                    play.reset_mock()
                    path.write_text('{}', encoding='utf-8')
                    self.assertFalse(self.w.load_game(path, announce=False))
                    play.assert_not_called()

    def test_book_announcement_on_cover_popup_only(self):
        self.open()
        self.start()
        with patch.object(self.w.sounds, 'play_book_intro') as play, \
             patch.object(QDialog, 'exec', return_value=0):
            self.w.show_cover()
            play.assert_called_once_with('foret-1983')

    def test_forest_ordinary_meals_repeat_save_and_undo(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs[55] = 'Un chemin tranquille.'
        w.go_to(55)
        w.character['endurance'] = 10
        w.character['initial']['endurance'] = 20
        w.character['provisions'] = 3
        meal = lambda: next(o for o in w.care_options() if o['id'] == 'meal')
        self.assertTrue(meal()['enabled'])
        w.use_care('meal')
        self.assertEqual((w.character['endurance'], w.character['provisions']), (14, 2))
        self.assertTrue(meal()['enabled'])
        path = main.SAVES_DIR/'repas-foret.json'
        w._write_atomic(path, w._save_data())
        with patch('main.extract_paragraphs', return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path, announce=False))
        self.assertTrue(meal()['enabled'])
        w.use_care('meal')
        self.assertEqual((w.character['endurance'], w.character['provisions']), (18, 1))
        w.undo_action()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (14, 2))
        w.redo_action()
        self.assertEqual((w.character['endurance'], w.character['provisions']), (18, 1))
        w.use_care('meal')
        self.assertEqual((w.character['endurance'], w.character['provisions']), (20, 0))
        w.character['endurance'] = 12
        before = copy.deepcopy(w.character)
        w.use_care('meal')
        self.assertFalse(meal()['enabled'])
        self.assertEqual(w.character, before)

    def test_forest_meals_reject_combat_special_passages_and_full_health(self):
        from types import SimpleNamespace
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({55:'Chemin.', 304:'Convalescence.', 328:'Chaise.'})
        w.go_to(55)
        w.character['endurance'] = 10
        for number, combat, dialog, endurance in (
                (55, False, None, w.character['initial']['endurance']),
                (55, True, None, 10),
                (55, False, SimpleNamespace(outcome=None), 10),
                (304, False, None, 10), (328, False, None, 10)):
            with self.subTest(number=number, combat=combat, dialog=dialog):
                w.current_paragraph = number
                w.character['endurance'] = endurance
                with patch.object(w, 'combat_available', return_value=combat), \
                     patch.object(w, '_combat_dialog', dialog):
                    before = copy.deepcopy(w.character)
                    w.use_care('meal')
                    w.eat_meal()
                    self.assertEqual(w.character, before)

    def test_sorcier_meals_still_require_a_permitted_passage(self):
        self.open('sorcier')
        self.start()
        w = self.w
        w.character['endurance'] = 1
        w.book_event_catalogue = {'paragraphs': {'1': {
            'status':'verifie', 'mode':'narratif', 'note':'Passage de test.'}}}
        w.current_paragraph = 1
        self.assertFalse(next(o for o in w.care_options() if o['id'] == 'meal')['enabled'])
        w.book_event_catalogue['paragraphs']['1']['optional_meal'] = True
        self.assertTrue(next(o for o in w.care_options() if o['id'] == 'meal')['enabled'])
        w.use_care('meal')
        self.assertFalse(next(o for o in w.care_options() if o['id'] == 'meal')['enabled'])

    def test_forest_art_selection_popup_save_and_no_stale_image(self):
        self.open()
        self.assertTrue(self.w.scene_art.background_art.isNull())
        self.start()
        w = self.w
        w.paragraphs.update({91:'Œil d’Ambre.',55:'Sans illustration.'})
        self.assertEqual(w.scene_entry['paragraphes'],[1])
        self.assertTrue(w.prologue_action.isVisible())
        w.prologue_action.trigger()
        self.assertEqual(w.prologue_dialog.last_page,17)
        w.prologue_dialog.close()
        w.go_to(91)
        self.assertEqual(w.scene_entry['paragraphes'],[91])
        self.assertTrue(w.scene_art.is_book_art)
        self.assertIn('91',w.scene_art.accessibleName())
        before = copy.deepcopy(w._snapshot())
        dice = self.roll.call_count
        with patch('main.IllustrationDialog.exec',return_value=QDialog.Rejected):
            w._enlarge_scene_art()
        self.assertEqual(w._snapshot(),before)
        self.assertEqual(self.roll.call_count,dice)
        with patch.object(w,'_show_illustration') as popup:
            w.show_cover()
            self.assertIn('La Forêt de la Malédiction',popup.call_args.args[1])
            self.assertNotIn('Sorcier',popup.call_args.args[1])
        path = main.SAVES_DIR/'illustration.json'
        w._write_atomic(path,w._save_data())
        w.go_to(55)
        self.assertIsNone(w.scene_entry)
        self.assertFalse(w.scene_art.is_book_art)
        self.assertEqual(w.scene_art.picture.toImage(),main.QPixmap(str(main.ASSET_DIR/'foret.jpg')).toImage())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(w.scene_entry['paragraphes'],[91])
        self.assertTrue(w.scene_art.is_book_art)

    def test_door_and_both_darts_outcomes_use_only_the_required_dice(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({73:'Porte.',327:'Ouvert.',112:'Départ.',309:'Fléchettes.',77:'Sain.',197:'Poison.'})
        base = w._snapshot()
        cases = [(73,'door',[2],327,8),(73,'door',[12],112,8),
                 (309,'darts',[2,2],77,6),(309,'darts',[12,2],197,6),
                 (309,'darts',[2,12],197,6),(309,'darts',[12,12],197,6)]
        for number,action,totals,target,chance in cases:
            with self.subTest(number=number,totals=totals):
                w._restore(base)
                w.character.update(habilete=8,chance=8,endurance=20)
                w.go_to(number)
                with patch.object(w,'_roll',side_effect=[([t//2]*2,t) for t in totals]) as dice:
                    w.perform_foret_action(action)
                    self.assertEqual(dice.call_count,len(totals))
                self.assertEqual(w.current_paragraph,target)
                self.assertEqual((w.character['chance'],w.character['endurance']),(chance,20))

    def test_chest_failure_retry_then_lethal_egg_is_one_undoable_chain(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({372:'Coffre.',48:'Œuf.',288:'Sortie.'})
        w.character.update(habilete=8,endurance=3)
        w.go_to(372)
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_foret_action('lift')
        self.assertEqual((w.current_paragraph,w.character['endurance']),(372,2))
        self.assertEqual(w._reading_link_targets(),{288})
        path = main.SAVES_DIR/'coffre-essai-rate.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        with patch.object(w,'_roll',return_value=([1,1],2)):
            w.perform_foret_action('lift')
        self.assertEqual(w.current_paragraph,48)
        self.assertEqual(w.character['endurance'],2)
        w.perform_foret_action('egg_explosion')
        self.assertEqual(w.character['endurance'],0)
        w.undo_action()
        self.assertEqual((w.current_paragraph,w.character['endurance']),(48,2))

    def test_wrestling_loses_only_one_stake_at_first_failed_test(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({266:'Mise.',129:'Défaite.',354:'Victoire.'})
        base = w._snapshot()
        for failure in (0,1,2,None):
            with self.subTest(failure=failure):
                w._restore(base)
                w.character.update(gold=30,habilete=8)
                w.go_to(266)
                totals = [2]*3 if failure is None else [2]*failure+[12]
                with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('10 pièces d’or',True)), \
                     patch.object(w,'_roll',side_effect=[([t//2]*2,t) for t in totals]) as dice:
                    w.perform_foret_action('wrestle')
                    self.assertEqual(dice.call_count,len(totals))
                self.assertEqual(w.current_paragraph,354 if failure is None else 129)
                self.assertEqual(w.character['gold'],30 if failure is None else 20)
                self.assertNotIn('Poudre de Lévitation',w.character['inventory'])
                if failure is None:
                    w.perform_foret_action('entry')
                    self.assertIn('Poudre de Lévitation',w.character['inventory'])
                    self.assertTrue(rules.entry_resolved(w.character,78))

    def test_fever_survival_followup_and_convalescence_starvation(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({259:'Fièvre.',244:'Guérison.',19:'Excision.',18:'Suite.',304:'Jambe.',69:'Tunnel.'})
        base = w._snapshot()
        for stamina,total,target,remaining in ((20,2,244,17),(20,12,19,15),(4,12,259,0)):
            with self.subTest(stamina=stamina,total=total):
                w._restore(base)
                w.character.update(endurance=stamina,chance=8)
                w.go_to(259)
                with patch.object(w,'_roll',return_value=([total//2]*2,total)) as dice:
                    w.perform_foret_action('fever')
                    self.assertEqual(dice.call_count,1)
                self.assertEqual((w.current_paragraph,w.character['endurance']),(target,remaining))
                self.assertEqual(w.character['chance'],7)
                if target == 19:
                    w.perform_foret_action('entry')
                    self.assertEqual(w.character['endurance'],14)
        for rations in (4,5):
            w._restore(base)
            w.character.update(provisions=rations,habilete=8,endurance=20)
            w.go_to(304)
            w.perform_foret_action('convalescence')
            self.assertEqual(w.character['endurance'],20 if rations == 5 else 0)
            if rations == 5:
                self.assertEqual((w.current_paragraph,w.character['provisions'],w.character['habilete']),(69,0,6))

    def test_transformation_routes_after_demon_or_attacking_yaztromo(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({107:'Démon.',152:'Couronne.',333:'Transformation.',54:'Attaque.',399:'Grenouille.'})
        w.character.update(habilete=12,endurance=24)
        base = w._snapshot()
        w.go_to(107)
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for _ in range(5):w.combat_round()
        self.assertEqual(w.current_paragraph,152)
        w.perform_foret_action('entry')
        w.follow_foret_route(333)
        self.assertTrue(w.character['book_facts']['adventure_ended'])
        self.assertEqual(w.character['endurance'],24)
        w.undo_action()
        self.assertEqual(w.current_paragraph,152)
        w._restore(base)
        w.follow_foret_route(54)
        w.follow_foret_route(399)
        self.assertEqual(w.current_paragraph,399)
        self.assertTrue(w.character['book_facts']['adventure_ended'])
        self.assertEqual(w.character['endurance'],24)

    def test_all_shop_item_branches_distinguish_missing_manual_valid_and_spent(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        for number,(item,present,absent) in rules.ITEM_BRANCHES.items():
            for status in ('missing','manual','charged','spent'):
                with self.subTest(number=number,status=status):
                    w._restore(base)
                    if status == 'manual':w.character['inventory'].append(item)
                    elif status in ('charged','spent'):
                        rules.buy(w.character,item)
                        if status == 'spent':rules.consume(w.character,item)
                    if number == 173:rules.resolve_entry(w.character,78)
                    if number == 322:rules.buy(w.character,'Anneau de Lumière')
                    w.go_to(number)
                    if number in rules.ENTRY_RULES:w.perform_foret_action('entry')
                    before = copy.deepcopy(w.character)
                    targets = w._reading_link_targets()
                    expected,blocked = (present,absent) if status == 'charged' else (absent,present)
                    self.assertIn(expected,targets)
                    self.assertNotIn(blocked,targets)
                    self.assertEqual(w.character,before)

    def test_all_branch_tests_save_and_undo_success_and_failure(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        for number,(stat,success,failure,damage) in rules.BRANCH_TESTS.items():
            for passed in (True,False):
                with self.subTest(number=number,passed=passed):
                    w._restore(base)
                    w.character.update(habilete=8,chance=8,endurance=20)
                    if number == 158:rules.buy(w.character,'Bandeau de Concentration')
                    w.go_to(number)
                    before = copy.deepcopy(w._snapshot())
                    total = 2 if passed else 12
                    with patch.object(w,'_roll',return_value=([total//2]*2,total)) as dice:
                        w.perform_foret_action('branch_test')
                        self.assertEqual(dice.call_count,1)
                    target = success if passed else failure
                    self.assertEqual(w.current_paragraph,target)
                    self.assertEqual(w.character['chance'],7 if stat == 'chance' else 8)
                    self.assertEqual(w.character['endurance'],20-(damage if not passed else 0))
                    after = copy.deepcopy(w._snapshot())
                    w.undo_action()
                    self.assertEqual(w._snapshot(),before)
                    w.redo_action()
                    path = main.SAVES_DIR/f'branche-{number}-{passed}.json'
                    w._write_atomic(path,w._save_data())
                    with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                        self.assertTrue(w.load_game(path,announce=False))
                    self.assertEqual(w.character,after['character'])
                    w.go_to(number)
                    self.assertEqual(w._reading_link_targets(),{target})
                    before_repeat = copy.deepcopy(w.character)
                    with patch.object(w,'_roll') as dice:
                        w.perform_foret_action('branch_test')
                        dice.assert_not_called()
                    self.assertEqual(w.character,before_repeat)

    def test_every_flee_branch_with_luck_success_failure_and_lethal_wound(self):
        from grimoire_modules.foret import rules
        from grimoire_modules.foret.encounters import COMBATS
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for number,profile in COMBATS.items():
                if 'escape_target' not in profile:continue
                for mode in ('no_luck','lucky','unlucky','lethal'):
                    with self.subTest(number=number,mode=mode):
                        w._restore(base)
                        w.character.update(habilete=12,endurance=24,chance=8)
                        w.go_to(number)
                        for _ in range(profile.get('escape_after_assaults',0)):w.combat_round()
                        self.assertTrue(w.can_flee_combat())
                        if mode == 'lethal':w.character['endurance'] = 1
                        before = copy.deepcopy(w._snapshot())
                        answer = QMessageBox.Yes if mode in ('lucky','unlucky') else QMessageBox.No
                        total = 2 if mode == 'lucky' else 12
                        with patch.object(w,'_ask_combat_question',return_value=answer), \
                             patch.object(w,'_roll',return_value=([total//2]*2,total)) as dice:
                            w.escape_scripted_combat(number)
                            self.assertEqual(dice.call_count,int(answer == QMessageBox.Yes))
                        cost = 1 if answer == QMessageBox.Yes else 0
                        damage = {'no_luck':2,'lucky':1,'unlucky':3,'lethal':2}[mode]
                        if profile['escape_target'] == 156 and mode != 'lethal':damage += 3
                        self.assertEqual(w.character['endurance'],max(0,before['character']['endurance']-damage))
                        self.assertEqual(w.character['chance'],8-cost)
                        escaped = rules.peek(w.character)['combats'][profile['identity']]
                        self.assertTrue(escaped['escaped'])
                        self.assertFalse(escaped['finished'])
                        self.assertEqual(escaped['groups'],before['character']['book_state']['foret']['combats'][profile['identity']]['groups'])
                        self.assertEqual(w.current_paragraph,number if mode == 'lethal' else profile['escape_target'])
                        w.undo_action()
                        self.assertEqual(w._snapshot(),before)

    def test_failed_quest_retry_preserves_loot_spent_charges_and_can_die_on_return(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({204:'Village.',381:'Nouvelle tentative.',98:'Retour.',261:'Boutique.'})
        rules.buy(w.character,'Bottes à Bondir')
        rules.consume(w.character,'Bottes à Bondir')
        rules.resolve_entry(w.character,232)
        w.character['chance'] = 8
        initial = copy.deepcopy(w.character)
        w.go_to(204)
        w.follow_foret_route(381)
        w.follow_foret_route(98)
        w.perform_foret_action('ambush')
        self.assertEqual(w.current_paragraph,1)
        w.follow_foret_route(261)
        self.assertEqual(w.character['gold'],initial['gold'])
        self.assertEqual(w.character['inventory'],initial['inventory'])
        self.assertEqual(rules.available(w.character,'Bottes à Bondir'),0)
        self.assertEqual(w.character['chance'],7)
        self.assertFalse(rules.entry_resolved(w.character,312))
        w.go_to(204)
        w.follow_foret_route(381)
        w.follow_foret_route(98)
        before = copy.deepcopy(w._snapshot())
        with patch.object(w,'_roll',return_value=([6,6],12)):
            w.perform_foret_action('ambush')
        self.assertEqual(w.character['endurance'],0)
        self.assertEqual(w.character['gold'],initial['gold'])
        self.assertEqual(w.character['inventory'],initial['inventory'])
        w.undo_action()
        self.assertEqual(w._snapshot(),before)

    def test_complete_hammer_quest_by_holy_water_or_ghoul_combat(self):
        from grimoire_modules.foret import rules
        self.open()
        # Un héros légal ayant obtenu les maxima aux tirages de création.
        self.w._adventurer_draft = {'habilete':12,'endurance':24,'chance':12}
        self.start()
        w = self.w
        catalogue = w.book_event_catalogue['paragraphs']
        w.paragraphs.update({int(n):entry['title'] for n,entry in catalogue.items()})
        w.follow_foret_route(261)
        base = w._snapshot()
        prefix = [261,177,160,8,392,157,337,230,137,55,168,117,232,358,40,
                  274,109,124,180,361,86,208,99,209,28,52,78,349,291,145,
                  285,388,316,198,87,90,210,43,50,188,221,378,67,113,149,
                  306,391,200,351,292,95,173]
        suffix = [112,103,360,279,246,204]
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No), \
             patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('10 pièces d’or',True)):
            for holy_water in (True,False):
                with self.subTest(holy_water=holy_water):
                    w._restore(base)
                    purchases = ['Gant d’Adresse au Lancer','Brassard de Force']
                    if holy_water:purchases.append('Eau Bénite')
                    for item in purchases:w.perform_foret_action('buy',(item,1))
                    path = prefix + ([58] if holy_water else [227,312]) + suffix
                    for index,number in enumerate(path):
                        self.assertEqual(w.current_paragraph,number,f'Parcours au §{number}')
                        if w.combat_available():
                            rounds = 0
                            while w.combat_available() and rounds < 30:
                                w.combat_round()
                                rounds += 1
                            self.assertLess(rounds,30)
                        elif number in rules.ENTRY_RULES:
                            w.perform_foret_action('entry')
                        elif number == 358:w.perform_foret_action('snare')
                        elif number == 52:w.perform_foret_action('bracelet')
                        elif number == 388:w.perform_foret_action('werewolf_exit')
                        elif number == 90:w.perform_foret_action('branch_test')
                        elif number == 279:w.perform_foret_action('payment',(5,[]))
                        if number in (232,173,279):
                            saved = copy.deepcopy(w.character)
                            save_path = main.SAVES_DIR/f'parcours-{holy_water}-{number}.json'
                            w._write_atomic(save_path,w._save_data())
                            with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                                self.assertTrue(w.load_game(save_path,announce=False))
                            self.assertEqual(w.character,saved)
                        self.assertGreater(w.character['endurance'],0)
                        self.assertGreaterEqual(w.character['gold'],0)
                        if index+1 < len(path):
                            target = path[index+1]
                            if w.current_paragraph != target:
                                self.assertIn(target,w._reading_link_targets(),f'Route {number} → {target}')
                                w.follow_foret_route(target)
                    self.assertTrue(rules.hammer_complete(w.character))
                    self.assertNotIn('Poudre de Lévitation',w.character['inventory'])
                    self.assertIn('Petite clé d’argent',w.character['inventory'])
                    for item in purchases:self.assertEqual(rules.available(w.character,item),0)
                    self.assertEqual(w.character['provisions'],0)
                    # La mise du bras de fer n’est perdue qu’en cas d’échec.
                    expected_gold = 30-sum(rules.PRICES[item] for item in purchases)+25-5
                    self.assertEqual(w.character['gold'],expected_gold)
                    w.perform_foret_action('hammer')
                    self.assertEqual(w.current_paragraph,400)
                    self.assertTrue(w.character['book_facts']['adventure_ended'])
                    self.assertFalse(rules.hammer_complete(w.character))
                    self.assertEqual(w.character['gold'],expected_gold)
                    w.undo_action()
                    self.assertEqual(w.current_paragraph,204)
                    self.assertTrue(rules.hammer_complete(w.character))
                    w.redo_action()
                    final = copy.deepcopy(w.character)
                    save_path = main.SAVES_DIR/f'victoire-parcours-{holy_water}.json'
                    w._write_atomic(save_path,w._save_data())
                    with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                        self.assertTrue(w.load_game(save_path,announce=False))
                    self.assertEqual(w.character,final)

    def test_victory_closes_play_only_after_real_handover(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({204:'Village.',400:'Victoire.',311:'Butin.'})
        w.go_to(400)
        self.assertFalse(w.character.get('book_facts',{}).get('adventure_ended',False))
        w.character['inventory'] += [rules.HAMMER_HEAD,rules.HAMMER_HANDLE]
        w.go_to(204)
        gold = w.character['gold']
        w.perform_foret_action('hammer')
        self.assertTrue(w.character['book_facts']['adventure_ended'])
        self.assertEqual(w.current_paragraph,400)
        self.assertFalse(w.tools_button.isEnabled())
        ended = copy.deepcopy(w._snapshot())
        w.go_to(311)
        w.perform_foret_action('entry')
        w.set_stat('gold',999)
        self.assertEqual(w._snapshot(),ended)
        self.assertEqual(w.character['gold'],gold)
        w.undo_action()
        self.assertFalse(w.character.get('book_facts',{}).get('adventure_ended',False))
        self.assertEqual(w.current_paragraph,204)
        self.assertTrue(w.tools_button.isEnabled())

    def test_ghoul_story_death_is_undoable_and_restored_as_dead(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs[2] = 'Fin après défaite.'
        before = copy.deepcopy(w._snapshot())
        w.go_to(2)
        self.assertEqual(w.character['endurance'],0)
        self.assertFalse(w.tools_button.isEnabled())
        w.undo_action()
        self.assertEqual(w._snapshot(),before)
        w.redo_action()
        path = main.SAVES_DIR/'goule-defaite.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(w.character['endurance'],0)

    def test_transformations_block_play_preserve_stats_save_and_allow_undo(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({333:'Couronne.',399:'Grenouille.',68:'Soin.',167:'Vouivre.'})
        base = w._snapshot()
        for number in (333,399):
            with self.subTest(number=number):
                w._restore(base)
                before = copy.deepcopy(w.character)
                w.go_to(number)
                self.assertEqual(w.character['endurance'],before['endurance'])
                self.assertEqual(rules.peek(w.character)['ending'],number)
                self.assertEqual(w._reading_link_targets(),set())
                self.assertFalse(w.tools_button.isEnabled())
                self.assertFalse(w.care_button.isEnabled())
                ended = copy.deepcopy(w._snapshot())
                w.go_to(68)
                w.perform_foret_action('entry')
                w.set_stat('endurance',1)
                w.use_care('meal')
                w.test_luck()
                self.assertEqual(w._snapshot(),ended)
                w.undo_action()
                self.assertEqual(w.character,before)
                self.assertTrue(w.tools_button.isEnabled())
                w.redo_action()
                path = main.SAVES_DIR/f'fin-{number}.json'
                w._write_atomic(path,w._save_data())
                with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                    self.assertTrue(w.load_game(path,announce=False))
                w.go_to(167)
                self.assertEqual(w.current_paragraph,number)
                self.assertEqual(w.character['endurance'],before['endurance'])
                self.assertFalse(w.stat_spins['endurance'].isEnabled())

    def test_village_missing_parts_opens_retry_and_handover_is_undoable(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({204:'Village.',381:'Échec.',98:'Retour.',400:'Victoire.'})
        w.go_to(204)
        self.assertEqual(w._reading_link_targets(),{381})
        w.follow_foret_route(381)
        self.assertEqual(w.current_paragraph,381)
        w.character['inventory'] += [rules.HAMMER_HEAD,rules.HAMMER_HEAD]
        w.go_to(204)
        self.assertEqual(w._reading_link_targets(),{381})
        w.character['inventory'].append(rules.HAMMER_HANDLE)
        self.assertEqual(w._reading_link_targets(),set())
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('hammer')
        self.assertEqual(w.current_paragraph,400)
        self.assertTrue(rules.peek(w.character)['won'])
        self.assertEqual(w.character['inventory'].count(rules.HAMMER_HEAD),1)
        w.undo_action()
        self.assertEqual(w._snapshot(),before)
        w.redo_action()
        path = main.SAVES_DIR/'marteau-remis.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.go_to(204)
        self.assertEqual(w.current_paragraph,400)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('hammer')
        self.assertEqual(w.character['inventory'].count(rules.HAMMER_HEAD),1)

    def test_payment_route_rechecks_inventory_at_click_without_charging(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({271:'Gnome.',297:'Prix.',67:'Départ.',346:'Arragon.',32:'Tribut.',111:'Défi.'})
        for source,target,gold,items in ((271,297,0,['Bijou']),(346,32,10,['Bijou','Bijou'])):
            w.character.update(gold=gold,inventory=items)
            w.go_to(source)
            self.assertIn(target,w._reading_link_targets())
            w.character['inventory'].clear()
            w.follow_foret_route(target)
            self.assertEqual(w.current_paragraph,source)
            self.assertEqual(w.character['gold'],gold)

    def test_fixed_payment_choices_dialog_cancel_save_and_undo(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({17:'Puits.',172:'Puits.',89:'Offrande.',256:'Tunnel.',238:'Ouest.',281:'Est.',160:'Corbeau.',343:'Conseil.',8:'Nord.',239:'Est.',366:'Centaure.',127:'Traversée.',178:'Gué.',298:'Araignée.'})
        base = w._snapshot()
        for source,target,price in ((17,89,1),(160,343,1),(366,127,3)):
            with self.subTest(source=source):
                w._restore(base)
                w.character['gold'] = price
                w.go_to(source)
                self.assertIn(target,w._reading_link_targets())
                w.follow_foret_route(target)
                self.assertEqual(w.character['gold'],price)
                self.assertEqual(w._reading_link_targets(),set())
                before = copy.deepcopy(w._snapshot())
                with patch('grimoire_modules.foret.actions.QDialog.exec',lambda dialog:dialog.reject()):
                    w._foret_payment_dialog()
                self.assertEqual(w._snapshot(),before)
                w.perform_foret_action('payment',(price,[]))
                self.assertEqual(w.character['gold'],0)
                self.assertTrue(w._reading_link_targets())
                w.undo_action()
                self.assertEqual(w.character['gold'],price)
                w.redo_action()
                path = main.SAVES_DIR/f'paiement-{target}.json'
                w._write_atomic(path,w._save_data())
                with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                    self.assertTrue(w.load_game(path,announce=False))
                w.perform_foret_action('payment',(price,[]))
                self.assertEqual(w.character['gold'],0)
                self.assertTrue(rules.payment_resolved(w.character,target))
                if target == 89:
                    w.go_to(172)
                    w.follow_foret_route(89)
                    self.assertEqual(w.character['gold'],0)

    def test_egg_roll_save_undo_and_lethal_explosion(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({48:'Œuf.',288:'Sortie.'})
        w.go_to(48)
        self.assertEqual(w._reading_link_targets(),set())
        base = w._snapshot()
        calls = self.roll.call_count
        w.perform_foret_action('egg_explosion')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(w.character['endurance'],base['character']['endurance']-3)
        w.undo_action()
        self.assertEqual(w.character,base['character'])
        w.redo_action()
        path = main.SAVES_DIR/'oeuf.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.perform_foret_action('egg_explosion')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(w._reading_link_targets(),{288})
        w._restore(base)
        w.character['endurance'] = 2
        w.perform_foret_action('egg_explosion')
        self.assertEqual(w.character['endurance'],0)

    def test_copper_flute_avoids_wyvern_combat_and_preserves_living_enemy(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({132:'Vouivre.',167:'Combat.',258:'Flûte.',305:'Butin.',200:'Porte.',351:'Escalier.',112:'Chemin.'})
        w.go_to(200)
        w.perform_foret_action('entry')
        self.assertEqual(w._reading_link_targets(),set())
        w.character['inventory'].append('Petite clé d’argent')
        w.perform_foret_action('entry')
        self.assertEqual(w._reading_link_targets(),{351,112})
        self.assertIn('Petite clé d’argent',w.character['inventory'])
        rules.take_goblin_loot(w.character,items=[rules.GOBLIN_LOOT[0]])
        w.go_to(132)
        self.assertEqual(w._reading_link_targets(),{258})
        w.follow_foret_route(258)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertEqual(w._reading_link_targets(),{305})
        self.assertIn(rules.GOBLIN_LOOT[0],w.character['inventory'])
        path = main.SAVES_DIR/'vouivre-endormie.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.go_to(167)
        self.assertFalse(w.combat_available())
        self.assertNotIn('wyvern',rules.peek(w.character).get('combats',{}))
        self.assertEqual(w._reading_link_targets(),{305})

    def test_optional_finds_save_undo_and_departure_without_taking(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({371:'Mains.',93:'Sortie.',383:'Orques.',254:'Nord.'})
        w.character['endurance'] = w.character['initial']['endurance']-3
        for number,target in ((371,93),(383,254)):
            w.go_to(number)
            w.perform_foret_action('entry')
            before = copy.deepcopy(w.character)
            self.assertEqual(w._reading_link_targets(),{target})
            w.follow_foret_route(target)
            self.assertEqual(w.character,before)
            w.go_to(number)
            w.perform_foret_action('optional_find')
            after = copy.deepcopy(w.character)
            self.assertNotEqual(after,before)
            w.undo_action()
            self.assertEqual(w.character,before)
            w.redo_action()
            path = main.SAVES_DIR/f'facultatif-{number}.json'
            w._write_atomic(path,w._save_data())
            with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                self.assertTrue(w.load_game(path,announce=False))
            w.perform_foret_action('optional_find')
            self.assertEqual(w.character,after)
            self.assertFalse(rules.take_optional_find(w.character,number))

    def test_fixed_effects_gate_routes_and_restore_without_repeating(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        numbers = (19,68,108,143,159,202,250,269,275,277,283,311,345)
        catalogue = w.book_event_catalogue['paragraphs']
        for number in numbers:
            w.paragraphs[number] = 'Effet à appliquer.'
            for route in catalogue[str(number)]['routes']:
                w.paragraphs[route['target']] = 'Suite.'
        w.character['endurance'] = 10
        base = w._snapshot()
        for number in numbers:
            with self.subTest(number=number):
                w._restore(base)
                w.go_to(number)
                self.assertEqual(w._reading_link_targets(),set())
                before = copy.deepcopy(w.character)
                w.perform_foret_action('entry')
                expected = {r['target'] for r in catalogue[str(number)]['routes']}
                self.assertEqual(w._reading_link_targets(),expected)
                after = copy.deepcopy(w.character)
                w.undo_action()
                self.assertEqual(w.character,before)
                w.redo_action()
                self.assertEqual(w.character,after)
                path = main.SAVES_DIR/f'effet-{number}.json'
                w._write_atomic(path,w._save_data())
                with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                    self.assertTrue(w.load_game(path,announce=False))
                w.perform_foret_action('entry')
                self.assertTrue(rules.entry_resolved(w.character,number))
                self.assertEqual(w.character,after)
                if number == 275:
                    self.assertNotIn('Casque magique',w.character['inventory'])
                if number == 277:
                    w.follow_foret_route(234)
                    self.assertEqual(w.character['endurance'],9)

    def test_new_loot_requires_collection_and_survives_save_and_undo(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({50:'Clé.',188:'Nord.',116:'Collier.',314:'Matin.',305:'Butin.',374:'Gantelet.',133:'Anneau.',360:'Départ.'})
        initial_gold = w.character['gold']
        for number,targets in ((50,{188}),(116,{314}),(305,{374,133,360})):
            w.go_to(number)
            self.assertEqual(w._reading_link_targets(),set())
            before = copy.deepcopy(w.character)
            w.perform_foret_action('entry')
            self.assertEqual(w._reading_link_targets(),targets)
            collected = copy.deepcopy(w.character)
            w.undo_action()
            self.assertEqual(w.character,before)
            w.redo_action()
            self.assertEqual(w.character,collected)
            w.perform_foret_action('entry')
            self.assertEqual(w.character,collected)
        self.assertEqual(w.character['gold'],initial_gold+10)
        self.assertNotIn('Anneau de Lenteur',w.character['inventory'])
        self.assertNotIn('Gantelet d’Adresse à Combattre',w.character['inventory'])
        path = main.SAVES_DIR/'trouvailles.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        saved = copy.deepcopy(w.character)
        for number in (50,116,305):
            w.go_to(number)
            w.perform_foret_action('entry')
            self.assertTrue(rules.entry_resolved(w.character,number))
        self.assertEqual(saved,w.character)

    def test_lantern_failure_loss_cancel_restore_and_no_repeat(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({395:'Éclair.',370:'Objet perdu.',231:'Faucons.',154:'Lanterne noircie.'})
        w.character['inventory'] += ['Lanterne magique','Lanterne']
        rules.buy(w.character,'Anneau de Lumière',2)
        w.character['chance'] = 1
        w.character['endurance'] = 20
        w.go_to(395)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('lantern_flash')
        self.assertEqual((w.current_paragraph,w.character['endurance'],w.character['chance']),(370,17,0))
        self.assertEqual(w._reading_link_targets(),set())
        before = copy.deepcopy(w._snapshot())
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('',False)):
            w.perform_foret_action('lose_item')
        self.assertEqual(w._snapshot(),before)
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('Anneau de Lumière',True)):
            w.perform_foret_action('lose_item')
        self.assertEqual(w.current_paragraph,231)
        self.assertEqual(rules.available(w.character,'Anneau de Lumière'),1)
        self.assertIn('Lanterne magique',w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.current_paragraph,370)
        self.assertEqual(rules.available(w.character,'Anneau de Lumière'),2)
        w.redo_action()
        saved = w._save_data()
        path = main.SAVES_DIR/'lanterne.json'
        w._write_atomic(path,saved)
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(rules.available(w.character,'Anneau de Lumière'),1)
        rolls = self.roll.call_count
        w.go_to(395)
        w.perform_foret_action('lantern_flash')
        self.assertEqual(self.roll.call_count,rolls)
        self.assertEqual(w._reading_link_targets(),{370})

    def test_lantern_success_discard_and_hawks_sequence(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({395:'Éclair.',154:'Lanterne noircie.',231:'Faucons.',224:'Victoire.',332:'Fuite.'})
        w.character['inventory'] += ['Lanterne magique','Lanterne']
        w.character['chance'] = 10
        w.character['endurance'] = 20
        w.character['habilete'] = 20
        w.go_to(395)
        w.perform_foret_action('lantern_flash')
        self.assertEqual((w.current_paragraph,w.character['chance'],w.character['endurance']),(154,9,20))
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('discard_lantern')
        self.assertNotIn('Lanterne magique',w.character['inventory'])
        self.assertIn('Lanterne',w.character['inventory'])
        self.assertEqual(w.current_paragraph,231)
        self.assertTrue(w.can_flee_combat())
        self.assertEqual([e['stamina'] for e in w._combat_roster()],[4,3,4])
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for _ in range(6):
                w.combat_round()
        self.assertEqual(w.current_paragraph,224)
        w.go_to(231)
        self.assertFalse(w.combat_available())
        self.assertEqual(w._reading_link_targets(),{224})

    def test_lantern_lethal_flash_never_asks_for_item_and_empty_bag_stays_unresolved(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({395:'Éclair.',370:'Objet perdu.',231:'Faucons.'})
        w.character['inventory'] = ['Lanterne magique']
        w.character['chance'] = 0
        w.character['endurance'] = 3
        w.go_to(395)
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem') as choose:
            w.perform_foret_action('lantern_flash')
        choose.assert_not_called()
        self.assertEqual(w.character['endurance'],0)
        w.undo_action()
        w.character['inventory'] = []
        w.go_to(370)
        w.perform_foret_action('lose_item')
        self.assertEqual(w.current_paragraph,370)
        self.assertFalse(w._book_state(370).get('foret_resolved'))

    def test_gnome_chain_payment_save_restore_and_undo_do_not_duplicate_sword(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({192:'La carotte.',46:'Le papillon.',12:'Le prix.',271:'La conversation.',67:'Le chemin.'})
        w.character['chance'] = 8
        w.go_to(192)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('gnome_sword')
        self.assertNotIn('Épée',w.character['inventory'])
        self.assertEqual(w._reading_link_targets(),{12,46})
        w.go_to(46)
        w.perform_foret_action('entry')
        self.assertEqual(w.character['chance'],6)
        w.go_to(12)
        self.assertEqual(w._reading_link_targets(),set())
        path = main.SAVES_DIR/'gnome.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(rules.peek(w.character)['gnome_sword'],'Épée')
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('payment',(10,['Lanterne']))
        self.assertEqual(w._snapshot(),before)
        gold = w.character['gold']
        w.perform_foret_action('payment',(10,[]))
        self.assertEqual(w.character['gold'],gold-10)
        self.assertEqual(w.character['inventory'].count('Épée'),1)
        self.assertEqual(w._reading_link_targets(),{271,67})
        w.undo_action()
        self.assertNotIn('Épée',w.character['inventory'])
        self.assertEqual(w.character['gold'],gold)
        w.redo_action()
        w.perform_foret_action('payment',(10,[]))
        self.assertEqual(w.character['gold'],gold-10)
        self.assertEqual(w.character['inventory'].count('Épée'),1)
        w.go_to(46)
        w.perform_foret_action('entry')
        self.assertEqual(w.character['chance'],6)

    def test_enchanted_sword_display_weapon_switch_care_save_and_loss(self):
        from grimoire_modules.foret import rules
        from combat_dialog import CombatDialog
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({70:'L’épée.',334:'Le chemin.',377:'Les Pygmées.'})
        w.character['habilete'] = 8
        w.character['initial']['habilete'] = 8
        w.go_to(70)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        self.assertEqual(w.stat_bars['habilete'].format(),'10 / 8')
        self.assertEqual(w._reading_link_targets(),{334})
        w.weapon_combo.setCurrentText('Épée')
        self.assertEqual(w.stat_spins['habilete'].value(),8)
        w.weapon_combo.setCurrentText(rules.ENCHANTED_SWORD)
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        w.character.update(habilete=5,potion="Potion d'Adresse",potion_doses=2)
        w.drink_potion()
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        self.assertEqual(w.character['initial']['habilete'],8)
        self.assertFalse(w.care_options()[0]['enabled'])
        w.go_to(377)
        dialog = CombatDialog(w)
        self.addCleanup(dialog.deleteLater)
        self.assertIn('Habileté 10',dialog.hero.text())
        self.assertEqual(w._ff_combat_profile()['skill'],10)
        stamina = w.character['endurance']
        with patch.object(w,'_roll',side_effect=[([6,6],12),([4,4],8),([6,6],12),([4,4],8)]), \
                patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            w.combat_round()
        self.assertEqual(w._combat_roster()[0]['stamina'],3)
        self.assertEqual(w.character['endurance'],stamina)
        path = main.SAVES_DIR/'epee.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        row = w.character['inventory'].index(rules.ENCHANTED_SWORD)
        w.inventory_list.setCurrentRow(row)
        w.remove_item()
        self.assertEqual(w.stat_spins['habilete'].value(),8)
        w.undo_action()
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        w.redo_action()
        self.assertEqual(w.stat_spins['habilete'].value(),8)

    def test_silver_box_gas_one_die_save_undo_and_alias_cannot_repeat(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({22:'Gaz.',169:'Même gaz.',358:'Sortie.',85:'La cage.'})
        w.character.update(habilete=8,endurance=20)
        w.go_to(22)
        self.assertEqual(w._reading_link_targets(),set())
        calls = self.roll.call_count
        w.perform_foret_action('gas')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(self.roll.call_args.args,(1,))
        self.assertEqual((w.character['habilete'],w.character['endurance']),(6,17))
        self.assertEqual(w._reading_link_targets(),{358})
        path = main.SAVES_DIR/'gaz.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.go_to(169)
        w.perform_foret_action('gas')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(w.character['inventory'].count('Boîte d’argent'),1)
        self.assertEqual(w._reading_link_targets(),{85,358})
        w.undo_action()
        w.undo_action()
        self.assertEqual((w.character['habilete'],w.character['endurance']),(8,20))
        self.assertNotIn('Boîte d’argent',w.character['inventory'])
        w.redo_action()
        self.assertEqual(w.character['inventory'].count('Boîte d’argent'),1)

    def test_filter_search_and_stone_sword_routes_require_their_tests(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({60:'Filtres.',183:'Protection.',44:'Trop tard.',182:'Le rocher.',70:'L’épée.',334:'Le chemin.'})
        w.go_to(60)
        calls = self.roll.call_count
        w.perform_foret_action('find_filters')
        self.assertEqual(self.roll.call_count,calls)
        self.assertEqual(w._reading_link_targets(),set())
        rules.buy(w.character,'Filtres à Nez')
        w.character['chance'] = 10
        w.perform_foret_action('find_filters')
        self.assertEqual((w.current_paragraph,w.character['chance']),(183,9))
        self.assertEqual(rules.available(w.character,'Filtres à Nez'),1)
        w.perform_foret_action('entry')
        self.assertEqual(rules.available(w.character,'Filtres à Nez'),0)
        w.character['habilete'] = 6
        w.go_to(182)
        self.assertEqual(w._reading_link_targets(),set())
        before = copy.deepcopy(w.character)
        w.perform_foret_action('stone_sword')
        self.assertEqual(w.current_paragraph,70)
        self.assertEqual(w.character['chance'],before['chance'])
        self.assertEqual(w.character['endurance'],before['endurance'])
        w.perform_foret_action('entry')
        self.assertEqual(w.stat_spins['habilete'].value(),8)

    def test_arrow_branch_damage_is_applied_only_at_its_paragraph_and_undoable(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({81:'Flèche.',4:'Blessure.',49:'Combat.',93:'Croisement.'})
        w.character.update(chance=0,endurance=20)
        w.go_to(81)
        self.assertEqual(w._reading_link_targets(),set())
        calls = self.roll.call_count
        w.perform_foret_action('branch_test')
        self.assertEqual((w.current_paragraph,w.character['endurance'],w.character['chance']),(4,20,0))
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertEqual(w.character['endurance'],16)
        w.perform_foret_action('entry')
        self.assertEqual(w.character['endurance'],16)
        w.undo_action()
        self.assertEqual(w.character['endurance'],20)
        w.redo_action()
        w.go_to(81)
        w.perform_foret_action('branch_test')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(w._reading_link_targets(),{4})

    def test_immediate_arrow_damage_stops_on_death_and_skill_preserves_luck(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({90:'Flèche.',210:'Esquive.',348:'Blessure.',251:'Centaure.',63:'Esquive.',260:'Blessure.'})
        w.character.update(chance=0,endurance=3)
        w.go_to(90)
        w.perform_foret_action('branch_test')
        self.assertEqual(w.character['endurance'],0)
        self.assertEqual(w.current_paragraph,90)
        w.undo_action()
        w.character.update(habilete=5,endurance=20,chance=8)
        w.go_to(251)
        w.perform_foret_action('branch_test')
        self.assertEqual((w.current_paragraph,w.character['endurance'],w.character['chance']),(260,16,8))

    def test_troll_luck_failure_prepares_combat_and_saved_test_is_not_repeated(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({376:'Le sac.',74:'Butin.',310:'Troll.',101:'Butin.'})
        w.character['chance'] = 0
        w.go_to(376)
        w.perform_foret_action('branch_test')
        self.assertEqual(w.current_paragraph,310)
        self.assertTrue(w.combat_available())
        self.assertEqual((w.enemy_skill.value(),w.enemy_endurance.value()),(8,9))
        path = main.SAVES_DIR/'epreuve.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        calls = self.roll.call_count
        w.go_to(376)
        w.perform_foret_action('branch_test')
        self.assertEqual(self.roll.call_count,calls)
        self.assertEqual(w._reading_link_targets(),{310})

    def test_elven_bread_care_combat_undo_save_and_no_second_find(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({257:'Pain.',31:'Le puits.',377:'Combat.'})
        w.character.update(endurance=20,provisions=0,chance=5)
        w.character['initial']['endurance'] = 20
        w.go_to(257)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertEqual((w.character['endurance'],w.character['chance']),(20,6))
        bread = lambda: next(o for o in w.care_options() if o['id'] == 'elven_bread')
        self.assertFalse(bread()['enabled'])
        w.use_care('elven_bread')
        self.assertIn(rules.ELVEN_BREAD,w.character['inventory'])
        w.character['endurance'] = 17
        w.go_to(377)
        before = copy.deepcopy(w._snapshot())
        self.assertFalse(bread()['enabled'])
        w.perform_foret_action('elven_bread')
        self.assertEqual(w._snapshot(),before)
        w.go_to(31)
        self.assertTrue(bread()['enabled'])
        w.use_care('elven_bread')
        self.assertEqual((w.character['endurance'],w.character['provisions']),(20,0))
        self.assertNotIn(rules.ELVEN_BREAD,w.character['inventory'])
        w.undo_action()
        self.assertEqual(w.character['endurance'],17)
        self.assertIn(rules.ELVEN_BREAD,w.character['inventory'])
        w.redo_action()
        path = main.SAVES_DIR/'pain.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.go_to(257)
        w.perform_foret_action('entry')
        self.assertNotIn(rules.ELVEN_BREAD,w.character['inventory'])
        self.assertEqual(w.character['chance'],6)

    def test_monk_bell_route_and_exchange_are_persistent_and_undoable(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({191:'Le moine.',184:'Le soin.',390:'Le chemin.'})
        w.character.update(endurance=10,potion_doses=1)
        w.character['initial']['endurance'] = 20
        w.go_to(191)
        self.assertNotIn(184,w._reading_link_targets())
        w.character['inventory'].append(rules.BELL)
        self.assertIn(184,w._reading_link_targets())
        w.go_to(184)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertEqual((w.character['endurance'],w.character['potion_doses']),(14,1))
        self.assertNotIn(rules.BELL,w.character['inventory'])
        self.assertEqual(w._reading_link_targets(),{390})
        w.undo_action()
        self.assertEqual(w.character['endurance'],10)
        self.assertIn(rules.BELL,w.character['inventory'])
        w.redo_action()
        w.perform_foret_action('entry')
        self.assertEqual(w.character['endurance'],14)

    def test_snare_dropped_sword_save_payment_and_undo_restore_identity_and_bonus(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({70:'Épée.',358:'Piège.',218:'Secours.',40:'Liberté.',274:'Chemin.'})
        w.character.update(habilete=8,endurance=20,chance=0,gold=10)
        w.go_to(70)
        w.perform_foret_action('entry')
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        w.go_to(358)
        self.assertEqual(w._reading_link_targets(),set())
        calls = self.roll.call_count
        w.perform_foret_action('snare')
        self.assertEqual((w.current_paragraph,w.character['chance']),(218,0))
        self.assertNotIn(rules.ENCHANTED_SWORD,w.character['inventory'])
        self.assertEqual(w.stat_spins['habilete'].value(),8)
        self.assertEqual(w._reading_link_targets(),set())
        path = main.SAVES_DIR/'piege.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('payment',(0,[rules.ENCHANTED_SWORD]))
        self.assertEqual(w._snapshot(),before)
        w.perform_foret_action('payment',(5,[]))
        self.assertEqual(w.character['gold'],5)
        self.assertEqual(w.stat_spins['habilete'].value(),10)
        self.assertEqual(w.character['inventory'].count(rules.ENCHANTED_SWORD),1)
        self.assertEqual(w.character['endurance'],20)
        self.assertEqual(w._reading_link_targets(),{274})
        w.undo_action()
        self.assertEqual(w.stat_spins['habilete'].value(),8)
        self.assertEqual(w.character['gold'],10)
        w.redo_action()
        w.perform_foret_action('payment',(5,[]))
        self.assertEqual(w.character['gold'],5)
        w.go_to(358)
        w.perform_foret_action('snare')
        self.assertEqual(self.roll.call_count,calls+1)
        self.assertEqual(w._reading_link_targets(),{218})

    def test_snare_success_and_missing_sword_do_not_create_or_destroy_equipment(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({358:'Piège.',40:'Liberté.',218:'Secours.'})
        w.character['chance'] = 10
        w.go_to(358)
        w.character['inventory'].remove('Épée')
        calls = self.roll.call_count
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('snare')
        self.assertEqual(self.roll.call_count,calls)
        self.assertEqual(w._snapshot(),before)
        w.character['inventory'].append('Épée')
        w.perform_foret_action('snare')
        self.assertEqual((w.current_paragraph,w.character['chance']),(40,9))
        self.assertEqual(w.character['inventory'].count('Épée'),1)

    def test_ordinary_resource_loss_save_undo_and_later_revisit_do_not_reapply(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({145:'Naufrage.',285:'Le camp.',353:'Le réveil.',26:'Cabane.',220:'Chemin.'})
        w.character.update(provisions=7,gold=30,endurance=20)
        inventory = list(w.character['inventory'])
        w.go_to(145)
        self.assertEqual(w._reading_link_targets(),set())
        calls = self.roll.call_count
        w.perform_foret_action('entry')
        self.assertEqual((w.character['provisions'],w.character['gold'],w.character['endurance']),(0,30,20))
        self.assertEqual(w.character['inventory'],inventory)
        self.assertEqual(self.roll.call_count,calls)
        self.assertEqual(w._reading_link_targets(),{285})
        w.undo_action()
        self.assertEqual(w.character['provisions'],7)
        w.redo_action()
        path = main.SAVES_DIR/'naufrage.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.character['provisions'] = 3
        w.perform_foret_action('entry')
        self.assertEqual(w.character['provisions'],3)

    def test_silver_dart_can_be_left_or_taken_separately_and_undo_does_not_repeat_luck(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({219:'Fléchette.',300:'Le chemin.'})
        w.character.update(chance=5,gold=20)
        w.go_to(219)
        w.perform_foret_action('entry')
        self.assertEqual((w.character['chance'],w.character['gold']),(6,20))
        self.assertNotIn(rules.SILVER_DART,w.character['inventory'])
        self.assertEqual(w._reading_link_targets(),{300})
        w.go_to(300)
        self.assertNotIn(rules.SILVER_DART,w.character['inventory'])
        w.go_to(219)
        w.perform_foret_action('silver_dart')
        self.assertEqual(w.character['inventory'].count(rules.SILVER_DART),1)
        w.undo_action()
        self.assertNotIn(rules.SILVER_DART,w.character['inventory'])
        self.assertEqual(w.character['chance'],6)
        w.redo_action()
        w.perform_foret_action('silver_dart')
        self.assertEqual(w.character['inventory'].count(rules.SILVER_DART),1)
        self.assertEqual((w.character['chance'],w.character['gold']),(6,20))

    def test_donation_card_and_link_recheck_gold_and_undo_cost_with_navigation(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({243:'Don.',166:'Bénédiction.',33:'Refus.'})
        w.character['gold'] = 1
        w.go_to(243)
        button = next(w.choice_layout.itemAt(i).widget() for i in range(w.choice_layout.count())
                      if '§166' in w.choice_layout.itemAt(i).widget().text())
        w.character['gold'] = 0
        button.click()
        self.assertEqual(w.current_paragraph,243)
        w.character['gold'] = 1
        w.follow_link(QUrl('paragraph:166'))
        self.assertEqual((w.current_paragraph,w.character['gold']),(166,0))
        w.undo_action()
        self.assertEqual((w.current_paragraph,w.character['gold']),(243,1))
        w.redo_action()
        self.assertEqual((w.current_paragraph,w.character['gold']),(166,0))
        w.go_to(243)
        w.follow_foret_route(166)
        self.assertEqual(w.character['gold'],0)

    def test_immediate_feline_escape_costs_chance_not_endurance(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({130:'Femme Féline.',153:'Combat.',355:'Fuite.'})
        w.character.update(chance=8,endurance=20)
        w.go_to(130)
        before = copy.deepcopy(w.character)
        w._render_choices_and_events(w.paragraphs[130])
        self.assertEqual(w.character,before)
        w.follow_foret_route(355)
        self.assertEqual((w.current_paragraph,w.character['chance'],w.character['endurance']),(355,7,20))
        w.undo_action()
        self.assertEqual((w.current_paragraph,w.character['chance']),(130,8))

    def test_bandit_payment_is_shared_across_the_three_passages(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({360:'Bandits.',279:'Paiement.',246:'Passage.',204:'Village.',104:'Combat.'})
        w.character.update(gold=5,inventory=[])
        w.go_to(246)
        self.assertNotIn(204,w._reading_link_targets())
        w.go_to(360)
        w.follow_foret_route(279)
        self.assertEqual(w.character['gold'],5)
        w.perform_foret_action('payment',(5,[]))
        self.assertEqual(w.character['gold'],0)
        w.follow_foret_route(246)
        w.follow_foret_route(204)
        self.assertEqual((w.current_paragraph,w.character['gold']),(204,0))

    def test_partial_goblin_loot_cancel_save_and_undo_preserve_remaining_stock(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({301:'Butin.',157:'Chemin.'})
        w.character.update(gold=10,provisions=4)
        w.go_to(301)
        before = copy.deepcopy(w._snapshot())
        with patch('grimoire_modules.foret.actions.QDialog.exec',lambda dialog: dialog.reject()):
            w._foret_loot_dialog()
        self.assertEqual(w._snapshot(),before)
        def pick(dialog):
            dialog.findChild(QSpinBox).setValue(1)
            items = dialog.findChild(QListWidget)
            items.item(1).setSelected(True)
            next(button for button in dialog.findChildren(QPushButton)
                 if button.text() == 'Prendre la sélection').click()
            return dialog.result()
        with patch('grimoire_modules.foret.actions.QDialog.exec',pick):
            w._foret_loot_dialog()
        self.assertEqual((w.character['gold'],w.character['provisions']),(11,4))
        w.undo_action()
        self.assertEqual(rules.remaining_goblin_loot(w.character),(3,list(rules.GOBLIN_LOOT)))
        w.redo_action()
        path = main.SAVES_DIR/'butin.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        self.assertEqual(rules.remaining_goblin_loot(w.character),(2,[rules.GOBLIN_LOOT[0],rules.GOBLIN_LOOT[2]]))
        w.perform_foret_action('goblin_loot',(2,[rules.GOBLIN_LOOT[0],rules.GOBLIN_LOOT[2]]))
        self.assertEqual(rules.remaining_goblin_loot(w.character),(0,[]))
        self.assertEqual(w.character['gold'],13)
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('goblin_loot',(1,[]))
        self.assertEqual(w._snapshot(),before)
        w.follow_foret_route(157)
        self.assertEqual(w.current_paragraph,157)

    def test_all_new_ordinary_combats_reach_only_their_victory_after_last_enemy(self):
        from grimoire_modules.foret.encounters import COMBATS
        self.open()
        self.start()
        w = self.w
        numbers = (7,9,15,29,43,79,117,118,128,153,167,181,203,212,241,265,286,290,298,303,317,330,347)
        w.character['habilete'] = 30
        base = w._snapshot()
        for number in numbers:
            w.paragraphs[number] = 'Combat.'
            w.paragraphs[COMBATS[number]['victory_target']] = 'Victoire.'
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for number in numbers:
                with self.subTest(number=number):
                    w._restore(base)
                    w.go_to(number)
                    self.assertEqual(w._reading_link_targets(),set())
                    stamina = w.character['endurance']
                    calls = self.roll.call_count
                    rounds = 0
                    while w.current_paragraph == number and rounds < 30:
                        w.combat_round()
                        rounds += 1
                    self.assertEqual(w.current_paragraph,COMBATS[number]['victory_target'])
                    self.assertEqual(w.character['endurance'],stamina)
                    self.assertEqual(self.roll.call_count-calls,2*rounds)
                    w.go_to(number)
                    self.assertFalse(w.combat_available())
                    self.assertEqual(w._reading_link_targets(),{COMBATS[number]['victory_target']})

    def test_new_ordinary_combats_apply_normal_lethal_hit_without_extra_rolls(self):
        self.open()
        self.start()
        w = self.w
        numbers = (7,9,15,29,43,79,117,118,128,153,167,181,203,212,241,265,286,290,298,303,317,330,347)
        w.character.update(habilete=1,endurance=2)
        base = w._snapshot()
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for number in numbers:
                with self.subTest(number=number):
                    w._restore(base)
                    w.paragraphs[number] = 'Combat.'
                    w.go_to(number)
                    calls = self.roll.call_count
                    w.combat_round()
                    self.assertEqual(w.character['endurance'],0)
                    self.assertEqual(w.current_paragraph,number)
                    self.assertEqual(self.roll.call_count-calls,2)
                    w.combat_round()
                    self.assertEqual(self.roll.call_count-calls,2)

    def test_ordinary_combat_aliases_share_wounds_and_potion_counts_encounters(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        w = self.w
        w.character['habilete'] = 30
        w.paragraphs.update({9:'Gobelin.',117:'Même Gobelin.',232:'Butin.',203:'Changeur.',286:'Même Changeur.',
                             7:'Essaims.',23:'Sortie.'})
        rules.drink_combat_potion(w.character)
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            w.go_to(9)
            w.combat_round()
            self.assertEqual(w.enemy_endurance.value(),2)
            w.go_to(117)
            self.assertEqual(w.enemy_endurance.value(),2)
            self.assertEqual(rules.peek(w.character)['combat_potion_remaining'],1)
            w.combat_round()
            self.assertEqual(w.current_paragraph,232)
            w.go_to(7)
            for _ in range(6):
                if w.current_paragraph != 7:break
                w.combat_round()
            self.assertEqual(w.current_paragraph,23)
            self.assertEqual(rules.peek(w.character)['combat_potion_remaining'],0)
            w.go_to(203)
            w.combat_round()
            self.assertEqual(w.enemy_endurance.value(),8)
            w.go_to(286)
            self.assertEqual(w.enemy_endurance.value(),8)

    def test_new_flee_routes_use_combat_damage_without_initial_chance_cost(self):
        self.open()
        self.start()
        w = self.w
        w.character.update(endurance=20,chance=8)
        base = w._snapshot()
        with patch.object(w,'_ask_combat_question',return_value=QMessageBox.No):
            for number,target in ((29,254),(43,188),(153,355),(212,107),(290,358),(317,41)):
                with self.subTest(number=number):
                    w._restore(base)
                    w.paragraphs.update({number:'Combat.',target:'Fuite.'})
                    w.go_to(number)
                    self.assertTrue(w.can_flee_combat())
                    calls = self.roll.call_count
                    w.escape_scripted_combat(number)
                    self.assertEqual((w.current_paragraph,w.character['endurance'],w.character['chance']),(target,18,8))
                    self.assertEqual(self.roll.call_count,calls)

    def test_leech_salt_empty_ration_then_save_undo_and_no_second_cost(self):
        self.open()
        self.start()
        w = self.w
        w.paragraphs.update({178:'Sangsue.',298:'Araignée.'})
        w.character.update(provisions=0,endurance=20,chance=8)
        w.go_to(178)
        self.assertEqual(w._reading_link_targets(),set())
        before = copy.deepcopy(w._snapshot())
        w.perform_foret_action('leech_salt')
        self.assertEqual(w._snapshot(),before)
        w.character['provisions'] = 1
        w.perform_foret_action('leech_salt')
        self.assertEqual((w.current_paragraph,w.character['provisions'],w.character['endurance']),(298,0,20))
        self.assertTrue(w.combat_available())
        w.undo_action()
        self.assertEqual((w.current_paragraph,w.character['provisions']),(178,1))
        w.redo_action()
        path = main.SAVES_DIR/'sel.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        w.go_to(178)
        w.perform_foret_action('leech_salt')
        self.assertEqual(w.character['provisions'],0)
        self.assertEqual(w._reading_link_targets(),{298})

    def test_confirmed_orcs_and_lutins_resume_at_second_enemy_and_reach_their_loot(self):
        self.open()
        self.start()
        w = self.w
        w.character['habilete'] = 30
        w.paragraphs.update({29:'Orques.',317:'Lutins.',383:'Camp.',301:'Butin.'})
        base = w._snapshot()
        with patch.object(w,'_assault_luck_choice',return_value=QMessageBox.No):
            for number,stamina,target in ((29,6,383),(317,7,301)):
                with self.subTest(number=number):
                    w._restore(base)
                    w.go_to(number)
                    calls = self.roll.call_count
                    for _ in range(3):w.combat_round()
                    self.assertEqual(w.current_paragraph,number)
                    self.assertEqual(self.roll.call_count-calls,6)
                    self.assertEqual(w._foret_combat()['group'],1)
                    self.assertEqual([e['stamina'] for e in w._combat_roster()],[0,stamina])
                    path = main.SAVES_DIR/f'sequence-{number}.json'
                    w._write_atomic(path,w._save_data())
                    with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                        self.assertTrue(w.load_game(path,announce=False))
                    self.assertEqual(w.enemy_endurance.value(),stamina)
                    self.assertEqual([e['stamina'] for e in w._combat_roster()],[0,stamina])
                    w.combat_round()
                    self.assertEqual(w.enemy_endurance.value(),stamina-2)
                    w.undo_action()
                    self.assertEqual(w.enemy_endurance.value(),stamina)
                    w.redo_action()
                    for _ in range(4):
                        if w.current_paragraph != number:break
                        w.combat_round()
                    self.assertEqual(w.current_paragraph,target)
                    if number == 317:
                        gold = w.character['gold']
                        w.perform_foret_action('goblin_loot',(1,[]))
                        self.assertEqual(w.character['gold'],gold+1)

    def test_cover_title_starting_resources_and_ready_notice(self):
        self.open()
        self.assertEqual(self.w.book_module.id, 'foret_malediction_1983')
        self.assertEqual(self.w.book_label.text(), 'La Forêt de la Malédiction')
        self.assertIn('La Forêt de la Malédiction', self.w.reader.toPlainText())
        self.assertNotIn('préparation', self.w.reader.toPlainText())
        self.assertEqual(self.w.scene_entry['type'], 'couverture')
        self.assertTrue(self.w.scene_art.is_book_art)
        self.assertIsNotNone(self.w.findChild(QPushButton, 'readPrologue'))
        self.assertEqual(self.w.character['gold'], 30)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)

    def test_analysed_title_and_corrected_cave_route_are_presented_without_effects(self):
        self.open()
        self.start()
        self.assertFalse(any('en préparation' in label.text()
                             for label in self.w.event_group.findChildren(QLabel)))
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.assertEqual(self.w.paragraph_title.text(), 'La tour de Yaztromo')
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any('Suivre le mage' in button.text() for button in buttons))
        self.w.paragraphs[267] = 'Rendez-vous au 196. Sinon rendez-vous au 25.'
        self.w.paragraphs[196] = 'La caverne.'
        self.w.paragraphs[25] = 'Une bifurcation.'
        self.w.go_to(267)
        self.assertNotIn('href="paragraph:1"', self.w.reader.toHtml())
        buttons = [self.w.choice_layout.itemAt(i).widget()
                   for i in range(self.w.choice_layout.count())]
        self.assertTrue(any(button.isEnabled() and '196' in button.text() for button in buttons))
        self.assertFalse(any('confirmer' in button.text() for button in buttons))
        self.assertIn('paragraph:196',self.w.reader.toHtml())
        self.assertEqual(self.w.character, before)
        self.assertEqual(self.roll.call_count, dice)

    def test_shop_purchases_are_saved_and_undoable_without_free_charges(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs[261] = 'Les achats.'
        self.w.go_to(261)
        before = self.w._snapshot()
        self.w.perform_foret_action('buy', ('Bottes à Bondir', 2))
        self.assertEqual(self.w.character['gold'], 26)
        self.assertEqual(rules.available(self.w.character, 'Bottes de Saut'), 2)
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.w._restore(before)
        self.assertEqual(rules.available(self.w.character, 'Bottes à Bondir'), 0)
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(rules.available(self.w.character, 'Bottes à Bondir'), 2)

    def test_pair_can_change_target_each_round_and_popup_reads_both_enemies(self):
        from combat_dialog import CombatDialog
        self.open()
        self.start()
        self.w.paragraphs[377] = 'Deux adversaires.'
        self.w.go_to(377)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            self.w.perform_foret_action('target', 1)
            self.w.combat_round()
            self.assertEqual([enemy['stamina'] for enemy in self.w._foret_combat()['groups'][0]], [5,4])
            self.w.perform_foret_action('target', 0)
            self.w.combat_round()
        self.assertEqual([enemy['stamina'] for enemy in self.w._foret_combat()['groups'][0]], [3,4])
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual([enemy['stamina'] for enemy in dialog.roster], [3,4])
        self.assertEqual(self.w._foret_combat()['assaults'], 2)

    def test_rock_beast_flee_is_enabled_after_exactly_three_assaults(self):
        self.open()
        self.start()
        self.w.character['habilete'] = 8
        self.w.paragraphs.update({84:'Une bête.',245:'Le chemin.'})
        self.w.go_to(84)
        for index in range(3):
            self.assertFalse(self.w.can_flee_combat())
            self.w.combat_round()
        self.assertTrue(self.w.can_flee_combat())
        before = self.w.character['endurance']
        with patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.escape_scripted_combat(84)
        self.assertEqual(self.w.current_paragraph,245)
        self.assertEqual(self.w.character['endurance'],before-2)

    def test_ghoul_fourth_wounding_hit_ends_adventure(self):
        self.open()
        self.start()
        self.w.character['habilete'] = 1
        self.w.character['endurance'] = 20
        self.w.paragraphs[227] = 'Une goule.'
        self.w.go_to(227)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            for index in range(3):
                self.w.combat_round()
                self.assertGreater(self.w.character['endurance'],0)
            self.w.combat_round()
        self.assertEqual(self.w.character['endurance'],0)
        self.assertFalse(self.w.combat_available())

    def test_lethal_whip_stops_normal_damage_and_further_dice(self):
        self.open()
        self.start()
        self.w.character['endurance'] = 1
        self.w.paragraphs[107] = 'Un démon.'
        self.w.go_to(107)
        with patch.object(self.w, '_roll', side_effect=[([3,3],6),([3,3],6),([1],1)]) as roll, \
                patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.combat_round()
        self.assertEqual(roll.call_count,3)
        self.assertEqual(self.w.character['endurance'],0)
        self.assertEqual(self.w._foret_combat()['groups'][0][0]['stamina'],10)

    def test_popup_does_not_declare_victory_after_only_one_pygmy_dies(self):
        from combat_dialog import CombatDialog
        from unittest.mock import Mock
        self.open()
        self.start()
        self.w.paragraphs[377] = 'Deux adversaires.'
        self.w.go_to(377)
        self.w._foret_combat()['groups'][0][0]['stamina'] = 2
        self.w._foret_sync_enemy()
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        dialog.present_roll = Mock()
        dialog.choose_luck = Mock(return_value=False)
        self.w._combat_dialog = dialog
        self.addCleanup(setattr, self.w, '_combat_dialog', None)
        with patch.object(self.w, '_assault_luck_choice', return_value=QMessageBox.No):
            dialog._run(self.w.combat_round)
        self.assertIsNone(dialog.outcome)
        self.assertEqual([enemy['stamina'] for enemy in dialog.roster],[0,6])
        self.assertEqual(self.w.enemy_name.text(),'Pygmée B')

    def test_flee_platform_applies_both_escape_wound_and_fall(self):
        self.open()
        self.start()
        self.w.paragraphs.update({352:'Un adversaire.',156:'Une chute.'})
        self.w.go_to(352)
        before = self.w.character['endurance']
        with patch.object(self.w, '_ask_combat_question', return_value=QMessageBox.No):
            self.w.escape_scripted_combat(352)
        self.assertEqual(self.w.character['endurance'],before-5)
        snapshot = self.w._snapshot()
        self.w._restore(snapshot)
        self.assertEqual(self.w.character['endurance'],before-5)

    def test_lethal_fever_does_not_roll_dice(self):
        self.open()
        self.start()
        self.w.paragraphs[259] = 'La fièvre.'
        self.w.go_to(259)
        self.w.character['endurance'] = 3
        dice = self.roll.call_count
        self.w.perform_foret_action('fever')
        self.assertEqual(self.roll.call_count,dice)
        self.assertEqual(self.w.character['endurance'],0)

    def test_popup_full_hunter_sequence_only_ends_after_last_pair(self):
        from combat_dialog import CombatDialog
        from unittest.mock import Mock
        self.open()
        self.start()
        self.w.character['habilete'] = 20
        self.w.paragraphs.update({96:'Les chasseurs.',62:'Après les chasseurs.'})
        self.w.go_to(96)
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        dialog.present_roll = Mock()
        self.w._combat_dialog = dialog
        self.addCleanup(setattr,self.w,'_combat_dialog',None)
        with patch.object(self.w,'_assault_luck_choice',return_value=QMessageBox.No):
            for _ in range(30):
                if dialog.outcome:
                    break
                dialog._run(self.w.combat_round)
        self.assertEqual(dialog.outcome,'Victoire')
        self.assertEqual(self.w.current_paragraph,62)
        self.assertTrue(all(enemy['stamina'] == 0 for enemy in dialog.roster))

    def test_manual_discard_removes_purchase_charge_and_cursed_ring_stays_locked(self):
        from grimoire_modules.foret import rules
        self.open()
        self.start()
        self.w.paragraphs[261] = 'Les achats.'
        self.w.go_to(261)
        self.w.perform_foret_action('buy',('Anneau de Lumière',1))
        row = self.w.character['inventory'].index('Anneau de Lumière')
        self.w.inventory_list.setCurrentRow(row)
        self.w.remove_item()
        self.assertEqual(rules.peek(self.w.character)['charges']['Anneau de Lumière'],0)
        self.w.paragraphs[133] = 'Un anneau.'
        self.w.go_to(133)
        self.w.perform_foret_action('entry')
        row = self.w.character['inventory'].index('Anneau de Lenteur')
        self.w.inventory_list.setCurrentRow(row)
        self.w.remove_item()
        self.assertIn('Anneau de Lenteur',self.w.character['inventory'])

    def test_return_to_yaztromo_requires_a_new_luck_test_each_visit(self):
        self.open()
        self.start()
        self.w.paragraphs[98] = 'Le retour dangereux.'
        self.w.character['chance'] = 10
        dice = self.roll.call_count
        for _ in range(2):
            self.w.go_to(98)
            self.assertNotIn(1,self.w._reading_link_targets())
            self.w.perform_foret_action('ambush')
            self.assertEqual(self.w.current_paragraph,1)
        self.assertEqual(self.roll.call_count,dice+2)
        self.assertEqual(self.w.character['chance'],8)
        self.assertEqual(self.w.character['gold'],30)

    def test_confirmed_eel_is_playable_and_victory_goes_to_131(self):
        self.open()
        self.start()
        self.w.paragraphs.update({186:'Une anguille.',131:'Après la rivière.'})
        self.w.go_to(186)
        self.assertTrue(self.w.combat_available())
        self.assertEqual(self.w.enemy_name.text(),'Anguille Carnivore')
        self.assertEqual((self.w.enemy_skill.value(),self.w.enemy_endurance.value()),(5,4))
        self.assertFalse(self.w.can_flee_combat())
        self.assertNotIn(131,self.w._reading_link_targets())
        with patch.object(self.w,'_assault_luck_choice',return_value=QMessageBox.No):
            self.w.combat_round()
            self.assertEqual(self.w.current_paragraph,186)
            self.w.combat_round()
        self.assertEqual(self.w.current_paragraph,131)

    def test_prologue_is_private_page_view_and_never_awards_resources_twice(self):
        self.open()
        before = self.w._snapshot()
        dice = self.roll.call_count
        self.w.show_prologue()
        dialog = self.w.prologue_dialog
        self.assertEqual((dialog.first_page, dialog.last_page, dialog.pages.count()), (14,17,4))
        dialog.pages.setCurrentIndex(2)
        self.assertEqual(dialog.viewer.accessibleName(), 'Prologue — page PDF 16')
        self.w.show_prologue()
        self.assertIs(self.w.prologue_dialog, dialog)
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.roll.call_count, dice)

    def test_rules_interval_and_old_book_views_close_when_switching(self):
        self.open()
        self.w.show_rules()
        rules = self.w.rules_dialog
        self.assertEqual((rules.first_page, rules.last_page), (4,13))
        self.w.show_prologue()
        prologue = self.w.prologue_dialog
        self.open('sorcier')
        self.assertFalse(rules.isVisible())
        self.assertFalse(prologue.isVisible())
        self.assertIsNone(self.w.rules_dialog)
        self.assertIsNone(self.w.prologue_dialog)
        self.assertEqual(self.w.character['gold'], 1)
        self.assertNotIn('Carte de Yaztromo', self.w.character['inventory'])
        self.w.show_rules()
        self.assertEqual((self.w.rules_dialog.first_page, self.w.rules_dialog.last_page), (3,14))

    def test_reroll_start_and_save_load_do_not_reapply_starting_gold(self):
        self.open()
        self.w._reroll_adventurer()
        self.assertEqual(self.w.character['gold'], 30)
        self.start()
        self.w.character['gold'] = 12
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.open('sorcier')
        self.start()
        self.assertTrue(self.w.load_game(path, announce=False))
        self.assertEqual(self.w.book_module.engine, 'foret-1983')
        self.assertEqual(self.w.character['gold'], 12)
        self.assertEqual(self.w.character['inventory'].count('Carte de Yaztromo'), 1)
        self.assertEqual(self.w.current_paragraph, 1)
        self.assertEqual(self.w.book_event_catalogue['reviewed_count'], 400)
        self.assertEqual(self.w.preferences['last_book'], Path(self.w.pdf_path).name)

    def test_consultation_never_activates_sorcier_paragraph_rules(self):
        self.open()
        self.start()
        before = copy.deepcopy(self.w.character)
        dice = self.roll.call_count
        self.w.go_to(86)
        self.w.go_to(350)
        self.w.combat_round()
        self.assertEqual(self.w.character, before)
        self.assertIsNone(self.w.crocodile_combat)
        self.assertIsNone(self.w.piranha_combat)
        self.assertEqual(self.w.completed_book_events, set())
        self.assertFalse(self.w.combat_button.isEnabled())
        self.assertEqual(self.roll.call_count, dice)
        self.assertIsNone(self.w.scene_entry)
        self.assertFalse(self.w.scene_art.is_book_art)
        self.assertEqual(self.w.scene_art.background_art.toImage(),main.QPixmap(str(main.ASSET_DIR/'foret.jpg')).toImage())

    def test_library_lists_both_covers_and_preselects_last_book(self):
        self.open('sorcier')
        self.open()
        books = imported_grimoires(main.BOOKS_DIR)
        self.assertEqual(len(books), 2)
        dialog = GrimoireLibraryDialog(books, self.w.pdf_path, self.w)
        try:
            self.assertIn('La Forêt', dialog.books.currentItem().text())
            self.assertFalse(dialog.books.currentItem().icon().isNull())
            self.assertIn('Aventure complète', dialog.books.currentItem().text())
            dialog.choose()
            self.assertEqual(dialog.selected_path, self.w.pdf_path)
        finally:
            dialog.deleteLater()

    def test_library_cancel_keeps_game_and_two_book_new_game_opens_selected_module(self):
        self.open('sorcier')
        sorcier = self.w.pdf_path
        self.open()
        self.start()
        before = self.w._snapshot()
        with patch.object(self.w, '_select_grimoire', return_value=None):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)), \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.w.show_library()
        self.assertEqual(self.w._snapshot(), before)
        with patch.object(self.w, '_select_grimoire', return_value=('open', sorcier)) as selector:
            self.w._start_new_game()
        selector.assert_called_once()
        self.assertEqual(self.w.book_module.engine, 'sorcier-1982')
        self.assertIsNone(self.w.current_paragraph)

    def test_save_slots_identify_the_adventure_and_tracking(self):
        self.open()
        self.start()
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        dialog = SaveSlotsDialog(main.SAVES_DIR, False, self.w)
        try:
            button = dialog.findChild(QPushButton, 'saveSlot1')
            self.assertIn('La Forêt de la Malédiction', button.text().splitlines()[0])
            self.assertEqual(len(button.text().splitlines()), 4)
            self.assertIn('Partie suivie', button.text())
            dialog.show()
            self.app.processEvents()
            self.assertGreaterEqual(button.height(), 4 * button.fontMetrics().lineSpacing() + 32)
        finally:
            dialog.deleteLater()


    def test_audit_loot_dialog_cancel_exchange_and_crown_gate(self):
        from grimoire_modules.foret import rules
        self.open(); self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        w.go_to(146)
        self.assertEqual(w._reading_link_targets(),{245})
        w.perform_foret_action('entry')
        self.assertIn('Morceau de pierre de la Bête Rocheuse',w.character['inventory'])
        w.go_to(152)
        self.assertEqual(w._reading_link_targets(),set())
        w.perform_foret_action('entry')
        self.assertIn(333,w._reading_link_targets())
        self.assertNotIn('Couronne du Démon de Feu',rules.peek(w.character).get('worn',[]))
        w.go_to(242)
        before = copy.deepcopy(w._snapshot())
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('',False)):
            w.perform_foret_action('gold_ingot')
        self.assertEqual(w._snapshot(),before)
        item = rules.removable_items(w.character)[0]
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem',return_value=(item,True)):
            w.perform_foret_action('gold_ingot')
        after = copy.deepcopy(w._snapshot())
        self.assertEqual(w.character['gold'],before['character']['gold'])
        self.assertIn(rules.GOLD_INGOT,w.character['inventory'])
        self.assertEqual(w._reading_link_targets(),{121})
        w.undo_action(); self.assertEqual(w._snapshot(),before)
        w.redo_action(); self.assertEqual(w._snapshot(),after)
        path = main.SAVES_DIR/'lingot.json'
        w._write_atomic(path,w._save_data())
        with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
            self.assertTrue(w.load_game(path,announce=False))
        with patch('grimoire_modules.foret.actions.QInputDialog.getItem') as dialog:
            w.perform_foret_action('gold_ingot')
            dialog.assert_not_called()

    def test_chest_barrel_both_orders_and_refusing_shield_survive_history(self):
        from grimoire_modules.foret import rules
        self.open(); self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        for take_shield in (True,False):
            w._restore(base)
            w.go_to(293)
            self.assertEqual(w._reading_link_targets(),{215,389,88})
            w.follow_foret_route(215)
            self.assertTrue(rules.peek(w.character)['barrel_examined'])
            w.follow_foret_route(248 if take_shield else 201)
            if take_shield:w.perform_foret_action('entry')
            w.follow_foret_route(389)
            w.perform_foret_action('entry')
            self.assertEqual(w._reading_link_targets(),{88})
            self.assertEqual('Bouclier d’empereur' in w.character['inventory'],take_shield)
            w.go_to(201); self.assertEqual(w._reading_link_targets(),{88})
            w.go_to(293); self.assertEqual(w._reading_link_targets(),{88})
            path = main.SAVES_DIR/'tonneau.json'
            w._write_atomic(path,w._save_data())
            with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                self.assertTrue(w.load_game(path,announce=False))
            self.assertEqual(w._reading_link_targets(),{88})
        w._restore(base)
        w.go_to(389); w.perform_foret_action('entry')
        self.assertEqual(w._reading_link_targets(),{215,88})
        before = copy.deepcopy(w._snapshot())
        w.follow_foret_route(215)
        w.undo_action(); self.assertEqual(w._snapshot(),before)
        self.assertFalse(rules.peek(w.character).get('barrel_examined',False))
        w.redo_action()
        w.follow_foret_route(248); w.perform_foret_action('entry')
        self.assertEqual(w._reading_link_targets(),{88})

    def test_emergency_exits_save_undo_and_normal_paths_are_not_bypassed(self):
        from grimoire_modules.foret import rules
        self.open(); self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        for number,target in ((12,67),(14,255),(218,274),(178,298),(328,118),(358,218),(370,231)):
            with self.subTest(number=number):
                w._restore(base)
                w.character.update(gold=0,provisions=0,inventory=[],equipped_weapon=None)
                w.go_to(number)
                before = copy.deepcopy(w._snapshot())
                self.assertTrue(any('Sortie de secours' in b.text() for b in w.event_group.findChildren(QPushButton)))
                with patch.object(w,'_roll') as dice:w.perform_foret_action('emergency_exit')
                dice.assert_not_called()
                self.assertEqual(w.current_paragraph,target)
                self.assertEqual(w.character['endurance'],before['character']['endurance'])
                after = copy.deepcopy(w._snapshot())
                w.undo_action(); self.assertEqual(w._snapshot(),before)
                w.redo_action(); self.assertEqual(w._snapshot(),after)
                path = main.SAVES_DIR/f'secours-{number}.json'
                w._write_atomic(path,w._save_data())
                with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                    self.assertTrue(w.load_game(path,announce=False))
                w.go_to(number)
                self.assertEqual(w._reading_link_targets(),{target})
                before_repeat = copy.deepcopy(w.character)
                w.perform_foret_action('emergency_exit')
                self.assertEqual(w.character,before_repeat)


    def test_ring_gauntlet_trials_cannot_repeat_after_save_or_item_loss(self):
        self.open(); self.start()
        w = self.w
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        base = w._snapshot()
        for first,second in ((133,374),(374,133)):
            w._restore(base)
            w.go_to(first); w.perform_foret_action('entry')
            self.assertEqual(w._reading_link_targets(),{second,360})
            w.follow_foret_route(second)
            before = copy.deepcopy(w._snapshot())
            w.perform_foret_action('entry')
            self.assertEqual(w._reading_link_targets(),{360})
            after = copy.deepcopy(w._snapshot())
            w.undo_action(); self.assertEqual(w._snapshot(),before)
            w.redo_action(); self.assertEqual(w._snapshot(),after)
            w.character['inventory'].clear()
            path = main.SAVES_DIR/'essais.json'
            w._write_atomic(path,w._save_data())
            with patch('main.extract_paragraphs',return_value=dict(w.paragraphs)):
                self.assertTrue(w.load_game(path,announce=False))
            self.assertEqual(w._reading_link_targets(),{360})
            w.go_to(first); self.assertEqual(w._reading_link_targets(),{360})


    def test_minimum_window_keeps_adventurer_values_in_view_for_both_books(self):
        from PySide6.QtWidgets import QScrollArea
        for name in ('foret','sorcier'):
            with self.subTest(book=name):
                self.open(name); self.start()
                w = self.w
                w.show(); w.resize(930,650)
                self.app.processEvents()
                scroll = w.findChild(QScrollArea,'sideScroll')
                self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
                for key in ('habilete','endurance','chance'):
                    spin = w.stat_spins[key]
                    self.assertGreaterEqual(spin.width(),60)
                    self.assertTrue(scroll.widget().rect().contains(spin.mapTo(scroll.widget(),spin.rect().topLeft())))
                    self.assertTrue(scroll.widget().rect().contains(spin.mapTo(scroll.widget(),spin.rect().bottomRight())))


    def test_mouse_choices_and_band_test_keep_undo_and_redo_atomic(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QScrollArea
        self.open()
        w = self.w
        w.show(); w.resize(930,650)
        w.creation_name_field.setText('Eldan')
        QTest.mouseClick(w.creation_start_button,Qt.LeftButton)
        self.assertIsNone(w._adventurer_draft)
        w.paragraphs.update({int(n):e['title'] for n,e in w.book_event_catalogue['paragraphs'].items()})
        w.go_to(1)
        route = next(w.choice_layout.itemAt(i).widget() for i in range(w.choice_layout.count())
                     if w.choice_layout.itemAt(i).widget().text().endswith('§261'))
        for area in w.findChildren(QScrollArea):
            if area.widget() and area.widget().isAncestorOf(route):area.ensureWidgetVisible(route)
        self.app.processEvents()
        QTest.mouseClick(route,Qt.LeftButton,pos=route.rect().center())
        self.assertEqual(w.current_paragraph,261)
        w.perform_foret_action('buy',('Bandeau de Concentration',1))
        w.go_to(158)
        before = copy.deepcopy(w._snapshot())
        blocked = w.choice_layout.itemAt(0).widget()
        self.assertFalse(blocked.isEnabled())
        QTest.mouseClick(blocked,Qt.LeftButton)
        self.assertEqual(w._snapshot(),before)
        action = next(w.event_layout.itemAt(i).widget() for i in range(w.event_layout.count())
                      if isinstance(w.event_layout.itemAt(i).widget(),QPushButton)
                      and 'Bandeau' in w.event_layout.itemAt(i).widget().text())
        for area in w.findChildren(QScrollArea):
            if area.widget() and area.widget().isAncestorOf(action):area.ensureWidgetVisible(action)
        self.app.processEvents()
        with patch.object(w,'_roll',return_value=([1,1],2)) as dice:
            QTest.mouseClick(action,Qt.LeftButton)
        self.assertEqual(dice.call_count,1)
        self.assertEqual(w.current_paragraph,47)
        self.assertEqual(w.character['chance'],before['character']['chance']-1)
        after = copy.deepcopy(w._snapshot())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes) as confirm:
            QTest.mouseClick(w.undo_btn,Qt.LeftButton)
            self.assertEqual(w._snapshot(),before)
            QTest.mouseClick(w.redo_btn,Qt.LeftButton)
        self.assertEqual(confirm.call_count, 2)
        self.assertEqual(w.adventure_tracking['status'], 'assisted')
        self.assertEqual(w._snapshot(),after)


class ForetEditionContractTests(unittest.TestCase):
    def test_illustrations_have_verified_associations_and_exclude_ornaments(self):
        from illustrations import images_for_paragraph
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        cat = module.catalogue('illustrations')
        expected = {1,15,29,38,49,57,69,90,91,107,142,160,181,212,230,253,
                    265,285,294,317,340,351,360,378,396}
        self.assertEqual(len(cat['illustrations']),75)
        self.assertEqual(len({e['id'] for e in cat['illustrations']}),75)
        for n in range(1,401):
            entries = images_for_paragraph(cat,n)
            self.assertEqual(len(entries),int(n in expected),f'§{n}')
            for entry in entries:
                self.assertEqual(entry['type'],'illustration')
                self.assertIn(entry['statut'],('verifie_legende','verifie_position'))
        ornaments = [e for e in cat['illustrations'] if e['type']=='ornement']
        self.assertEqual(len(ornaments),47)
        self.assertTrue(all(not e['paragraphes'] for e in ornaments))
        self.assertEqual(next(e['page_pdf'] for e in cat['illustrations'] if e['type']=='carte'),17)

    def test_presentation_catalogues_mark_completed_integration(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        events = module.catalogue('events')
        self.assertEqual(module.rules_pages, (4,13))
        self.assertEqual(module.intro_pages, (14,17))
        self.assertEqual(module.status, 'ready')
        self.assertEqual(len(events['paragraphs']), 400)
        self.assertEqual(events['review_pending'], [])
        self.assertEqual(events['automation_pending'], [])

    def test_private_pdf_is_recognized_and_cover_crop_fits_real_page(self):
        module = next(m for m in available_modules() if m.engine == 'foret-1983')
        root = Path(__file__).resolve().parents[1]
        candidates = [*root.glob('*.pdf'), *(root/'donnees/grimoires').glob('*.pdf'),
                      *(root.parent/'attachments').rglob('*.pdf')]
        path = next((p for p in candidates if pdf_digest(p) == module.pdf_sha256), None)
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        self.assertEqual(module_for_pdf(path).id, module.id)
        with pymupdf.open(path) as document:
            self.assertEqual(len(document), 170)
            catalogue = module.catalogue('illustrations')
            actual = [(i+1,image) for i,page in enumerate(document) for image in page.get_image_info()]
            self.assertEqual(len(actual),len(catalogue['illustrations']))
            for entry in catalogue['illustrations']:
                with self.subTest(image=entry['id']):
                    page = document[entry['page_pdf']-1]
                    rect = pymupdf.Rect(entry['rect'])
                    self.assertTrue(page.rect.contains(rect))
                    self.assertTrue(any(n==entry['page_pdf'] and max(abs(a-b) for a,b in zip(rect,im['bbox']))<3
                                        for n,im in actual))
                    self.assertGreater(page.get_pixmap(clip=rect).width,0)
