"""Scénarios de règles particuliers, avec dés imposés et sans Qt ni hasard."""
from copy import deepcopy
import json
import unittest
from grimoire_modules.foret import rules as r
from grimoire_modules.foret.encounters import COMBATS


def hero(**changes):
    character = {'habilete':8,'endurance':20,'chance':8,'gold':30,'provisions':10,
                 'initial':{'habilete':8,'endurance':20,'chance':10},'inventory':[]}
    character.update(changes)
    return character


class ForetMechanicsTests(unittest.TestCase):
    def test_branch_tests_all_totals_costs_and_damage_locations(self):
        for number,(stat,success,failure,damage) in r.BRANCH_TESTS.items():
            for total in range(2,13):
                with self.subTest(number=number,total=total):
                    c = hero()
                    target = r.resolve_branch_test(c,number,total)
                    passed = total <= 8
                    self.assertEqual(target,success if passed else failure)
                    self.assertEqual(c['chance'],7 if stat == 'chance' else 8)
                    self.assertEqual(c['endurance'],20 if passed else 20-damage)

    def test_branch_test_lethal_damage_and_enchanted_skill(self):
        for number,damage in ((90,3),(251,4)):
            c = hero(endurance=damage,chance=0)
            self.assertIsNone(r.resolve_branch_test(c,number,12))
            self.assertEqual(c['endurance'],0)
        c = hero()
        r.resolve_entry(c,70)
        self.assertEqual(r.resolve_branch_test(c,251,10),63)
        self.assertEqual(c['chance'],8)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.resolve_branch_test(c,90,True)
        self.assertEqual(c,before)

    def test_helmet_route_requires_wearing_and_presence(self):
        c = hero(chance=12)
        r.resolve_entry(c,4)
        self.assertEqual((c['endurance'],c['chance']),(16,12))
        c = hero(inventory=['Casque magique'])
        self.assertTrue(r.route_available(c,295,30))
        self.assertFalse(r.route_available(c,295,225))
        r.wear(c,'Casque magique')
        self.assertTrue(r.route_available(c,295,225))
        self.assertFalse(r.route_available(c,295,30))
        c['inventory'].clear()
        self.assertTrue(r.route_available(c,295,30))

    def test_silver_box_gas_aliases_share_one_roll_and_one_box(self):
        for paragraph in (22,169):
            c = hero()
            self.assertTrue(r.inhale_gas(c,paragraph,4))
            self.assertEqual((c['habilete'],c['endurance']),(6,16))
            before = deepcopy(c)
            self.assertFalse(r.inhale_gas(c,169 if paragraph == 22 else 22,6))
            self.assertEqual(c,before)
            self.assertEqual(c['inventory'].count('Boîte d’argent'),1)
            r.buy(c,'Filtres à Nez')
            self.assertFalse(r.resolve_entry(c,338))
            self.assertEqual(r.available(c,'Filtres à Nez'),1)
        c = hero()
        r.buy(c,'Filtres à Nez')
        r.resolve_entry(c,365)
        before = deepcopy(c)
        self.assertFalse(r.inhale_gas(c,22,6))
        self.assertEqual(c,before)

    def test_gas_validates_dice_and_stops_loot_on_death_and_mushroom_preserves_skill(self):
        c = hero(endurance=3)
        before = deepcopy(c)
        for die in (True,0,7):
            with self.assertRaises(ValueError):r.inhale_gas(c,22,die)
            self.assertEqual(c,before)
        r.inhale_gas(c,22,3)
        self.assertEqual(c['endurance'],0)
        self.assertNotIn('Boîte d’argent',c['inventory'])
        c = hero()
        r.inhale_gas(c,222,6)
        self.assertEqual((c['habilete'],c['endurance']),(8,14))
        self.assertEqual(c['inventory'],[])

    def test_mushroom_filter_luck_and_stone_sword_skill_have_distinct_costs(self):
        c = hero()
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.find_mushroom_filters(c,2)
        self.assertEqual(c,before)
        r.buy(c,'Filtres à Nez')
        self.assertEqual(r.find_mushroom_filters(c,2),183)
        self.assertEqual(c['chance'],7)
        self.assertEqual(r.available(c,'Filtres à Nez'),1)
        self.assertEqual(r.find_mushroom_filters(c,12),44)
        before = deepcopy(c)
        self.assertEqual(r.extract_stone_sword(c,8),70)
        self.assertEqual(r.extract_stone_sword(c,9),334)
        self.assertEqual(c,before)

    def test_enchanted_sword_bonus_requires_verified_source_and_equipped_copy(self):
        c = hero(inventory=[r.ENCHANTED_SWORD],equipped_weapon=r.ENCHANTED_SWORD)
        self.assertEqual(r.effective_skill(c),8)
        c['inventory'] = ['Épée']
        self.assertTrue(r.resolve_entry(c,70))
        self.assertFalse(r.resolve_entry(c,70))
        self.assertEqual(c['inventory'].count(r.ENCHANTED_SWORD),1)
        self.assertEqual((c['habilete'],c['initial']['habilete'],r.effective_skill(c)),(8,8,10))
        self.assertEqual(r.combined_door({**c,'chance':10},10),327)
        self.assertEqual(r.lift_chest(c,10),48)
        self.assertEqual(r.arm_wrestling(c,[10,10,10],gold=10),354)
        c['equipped_weapon'] = 'Épée'
        self.assertEqual(r.effective_skill(c),8)
        c['equipped_weapon'] = r.ENCHANTED_SWORD
        r.lose_backpack_item(c,r.ENCHANTED_SWORD)
        self.assertEqual(r.effective_skill(c),8)
        self.assertFalse(r.resolve_entry(c,70))

    def test_enchanted_sword_potions_wish_and_gnome_preserve_base_skill(self):
        from grimoire_modules.fighting_fantasy.rules import drink_potion
        c = hero(habilete=5,inventory=['Épée'],equipped_weapon='Épée',
                 potion="Potion d'Adresse",potion_doses=2)
        r.resolve_entry(c,70)
        self.assertEqual(r.effective_skill(c),7)
        drink_potion(c)
        self.assertEqual((r.effective_skill(c),c['habilete'],c['initial']['habilete']),(10,8,8))
        r.transform_gnome_sword(c)
        self.assertEqual(r.effective_skill(c),8)
        r.pay_paragraph(c,12,gold=10)
        self.assertEqual(r.effective_skill(c),10)
        c['habilete'] = 4
        c['inventory'].append('Lanterne magique')
        r.make_wish(c,'habilete')
        self.assertEqual(r.effective_skill(c),10)

    def test_gnome_transforms_and_returns_same_weapon_only_once(self):
        c = hero(inventory=['Épée'],equipped_weapon='Épée')
        self.assertTrue(r.transform_gnome_sword(c))
        self.assertEqual(c['inventory'],[])
        self.assertEqual(r.peek(c)['gnome_sword'],'Épée')
        self.assertFalse(r.transform_gnome_sword(c))
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.pay_paragraph(c,12,gold=9)
        self.assertEqual(c,before)
        self.assertTrue(r.pay_paragraph(c,12,gold=10))
        self.assertEqual((c['gold'],c['inventory'],c['equipped_weapon']),(20,['Épée'],'Épée'))
        self.assertFalse(r.pay_paragraph(c,12,gold=10))
        self.assertFalse(r.transform_gnome_sword(c))
        self.assertEqual(c['inventory'],['Épée'])

    def test_gnome_two_selected_objects_are_alternative_to_gold_and_remove_charges(self):
        c = hero()
        r.buy(c,'Anneau de Lumière',2)
        before = deepcopy(c)
        for gold,items in ((10,['Anneau de Lumière']),(0,['Anneau de Lumière']),(0,['Anneau de Lumière']*3)):
            with self.assertRaises(ValueError):r.pay_paragraph(c,12,gold=gold,items=items)
            self.assertEqual(c,before)
        self.assertTrue(r.pay_paragraph(c,12,items=['Anneau de Lumière']*2))
        self.assertEqual(c['gold'],24)
        self.assertEqual(r.available(c,'Anneau de Lumière'),0)
        self.assertNotIn('Épée',c['inventory'])
        c = hero(gold=0,inventory=['Objet verrouillé','Bijou'],locked_items=['Objet verrouillé'])
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.pay_paragraph(c,12,items=c['inventory'])
        self.assertEqual(c,before)

    def test_lantern_flash_success_failure_and_lethal_damage(self):
        for total, endurance, target, remaining in ((2,20,154,20),(12,20,370,17),(12,3,None,0)):
            with self.subTest(total=total,endurance=endurance):
                c = hero(endurance=endurance, inventory=['Lanterne magique','Lanterne'])
                self.assertEqual(r.lantern_flash(c,total),target)
                self.assertEqual((c['endurance'],c['chance']),(remaining,7))
                self.assertIn('Lanterne magique',c['inventory'])
        c = hero(inventory=['Lanterne'])
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.lantern_flash(c,2)
        self.assertEqual(c,before)

    def test_lantern_discard_and_selected_loss_preserve_other_copies_and_charges(self):
        c = hero(inventory=['Lanterne magique','Lanterne'])
        self.assertEqual(r.discard_lantern(c),231)
        self.assertEqual(c['inventory'],['Lanterne'])
        r.buy(c,'Anneau de Lumière',2)
        self.assertEqual(r.lose_backpack_item(c,'Anneau de Lumière'),231)
        self.assertEqual(r.available(c,'Anneau de Lumière'),1)
        c['inventory'].append('Casque magique')
        r.wear(c,'Casque magique')
        r.lose_backpack_item(c,'Casque magique')
        self.assertEqual(r.attack_bonus(c),0)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.lose_backpack_item(c,'Absent')
        self.assertEqual(c,before)
        c['inventory'].append('Anneau de Lenteur')
        r.wear(c,'Anneau de Lenteur')
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.lose_backpack_item(c,'Anneau de Lenteur')
        self.assertEqual(c,before)

    def test_shop_multiple_copies_and_single_charge(self):
        c = hero()
        r.buy(c, 'Bottes de Saut', 2)
        self.assertEqual(c['gold'],26)
        r.consume(c,'Bottes de Saut')
        self.assertEqual(r.available(c,'Bottes à Bondir'),1)
        self.assertIn('Bottes à Bondir (magie épuisée)',c['inventory'])
        r.consume(c,'Bottes à Bondir')
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.consume(c,'Bottes à Bondir')
        self.assertEqual(c,before)

    def test_invalid_purchase_has_no_partial_mutation(self):
        for name, quantity in [('Capsules de Feu',11),('Inconnu',1),('Eau Bénite',True),('Eau Bénite',0)]:
            c = hero()
            with self.assertRaises(ValueError):r.buy(c,name,quantity)
            self.assertEqual(c,hero())

    def test_manually_added_item_is_not_a_purchased_charge(self):
        c = hero(inventory=['Filtres à Nez'])
        self.assertEqual(r.available(c,'Filtres à Nez'),0)
        with self.assertRaises(ValueError):r.consume(c,'Filtres à Nez')

    def test_capsules_are_one_packet_not_five_uses(self):
        c = hero()
        r.buy(c,'Capsules de Feu')
        r.resolve_entry(c,350)
        self.assertEqual(r.available(c,'Capsules de Feu'),0)
        self.assertFalse(r.resolve_entry(c,350))

    def test_alias_and_atomic_failed_use_do_not_award_loot(self):
        c = hero()
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.resolve_entry(c,58)
        self.assertEqual(c,before)
        r.buy(c,'Eau Bénite')
        r.resolve_entry(c,58)
        self.assertEqual(c['gold'],52)
        self.assertFalse(r.resolve_entry(c,312))
        self.assertEqual(c['inventory'].count(r.HAMMER_HEAD),1)

    def test_two_paths_to_same_box_do_not_spend_second_filter(self):
        c = hero()
        r.buy(c,'Filtres à Nez',2)
        self.assertTrue(r.resolve_entry(c,338))
        self.assertFalse(r.resolve_entry(c,365))
        self.assertEqual(r.available(c,'Filtres à Nez'),1)

    def test_reward_variants_do_not_farm_gold_or_powder(self):
        c = hero()
        for number in (74,101,287,74):r.resolve_entry(c,number)
        self.assertEqual(c['gold'],35)
        for number in (78,354):r.resolve_entry(c,number)
        self.assertEqual(c['inventory'].count('Poudre de Lévitation'),1)

    def test_payment_counts_each_copy_and_gold_coin_as_unit(self):
        c = hero(inventory=['gem','gem'])
        r.pay(c,gold=3,items=['gem','gem'],units=5)
        self.assertEqual((c['gold'],c['inventory']),(27,[]))
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.pay(c,gold=3,items=['missing'],units=5)
        self.assertEqual(c,before)

    def test_giving_magic_item_removes_charge_and_curse_cannot_be_given(self):
        c = hero()
        r.buy(c,'Anneau de Lumière')
        r.pay(c,items=['Anneau de Lumière'],magic_only=True)
        self.assertEqual(r.available(c,'Anneau de Lumière'),0)
        r.resolve_entry(c,133)
        with self.assertRaises(ValueError):r.pay(c,items=['Anneau de Lenteur'])
        with self.assertRaises(ValueError):r.wear(c,'Anneau de Lenteur',False)

    def test_equipment_changes_attack_without_changing_skill(self):
        c = hero()
        for n in (179,302,374,133):r.resolve_entry(c,n)
        self.assertEqual(r.attack_bonus(c),1)
        self.assertEqual(r.attack_bonus(c,49),-2)
        self.assertEqual(c['habilete'],8)
        r.wear(c,'Casque magique',False)
        self.assertEqual(r.attack_bonus(c),0)

    def test_two_combat_potion_survives_rounds_and_save_reload(self):
        c = hero()
        r.drink_combat_potion(c)
        for _ in range(20):r.begin_encounter(c,'hunters')
        self.assertEqual(r.peek(c)['combat_potion_remaining'],1)
        c = json.loads(json.dumps(c))
        self.assertEqual(r.attack_bonus(c,encounter='hunters'),1)
        r.begin_encounter(c,'bandits')
        r.begin_encounter(c,'ghoul')
        self.assertEqual(r.attack_bonus(c,encounter='bandits'),1)
        self.assertEqual(r.attack_bonus(c,encounter='ghoul'),0)
        self.assertFalse(r.drink_combat_potion(c))

    def test_emperor_shield_threshold_and_luck_order(self):
        c = hero()
        r.resolve_entry(c,248)
        self.assertEqual([r.shield_damage(c,2,die) for die in range(1,7)],[2,2,2,1,1,1])
        self.assertEqual(r.shield_damage(c,2,4,lucky=False),2)
        self.assertEqual(r.shield_damage(c,2,4,lucky=True),0)

    def test_door_compares_both_scores_without_luck_cost(self):
        c = hero(chance=5)
        self.assertEqual(r.combined_door(c,6),112)
        self.assertEqual(r.combined_door(c,5),327)
        self.assertEqual(c['chance'],5)

    def test_darts_always_cost_two_luck_and_compare_to_decreasing_score(self):
        c = hero(chance=8)
        self.assertEqual(r.darts(c,[9,2]),197)
        self.assertEqual(c['chance'],6)
        c = hero(chance=8)
        self.assertEqual(r.darts(c,[8,8]),197)
        self.assertEqual(c['chance'],6)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.darts(c,[2,99])
        self.assertEqual(c,before)

    def test_arm_wrestling_stops_on_failure_and_only_loser_pays(self):
        c = hero()
        self.assertEqual(r.arm_wrestling(c,[2,8,8],gold=10),354)
        self.assertEqual(c['gold'],30)
        self.assertEqual(r.arm_wrestling(c,[2,9],gold=10),129)
        self.assertEqual(c['gold'],20)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.arm_wrestling(c,[9,2],gold=10)
        self.assertEqual(c,before)

    def test_bracelet_wins_without_dice_and_consumes_one_charge(self):
        c = hero()
        r.buy(c,'Brassard de Force')
        self.assertEqual(r.arm_wrestling(c,[],gold=10,bracelet=True),78)
        self.assertEqual(c['gold'],27)
        self.assertEqual(r.available(c,'Brassard de Force'),0)

    def test_chest_retry_is_not_once_only_and_death_stops_retries(self):
        c = hero(endurance=2)
        self.assertEqual(r.lift_chest(c,12),372)
        self.assertIsNone(r.lift_chest(c,12))
        with self.assertRaises(ValueError):r.lift_chest(c,2)

    def test_convalescence_consumes_five_without_healing_and_can_kill(self):
        c = hero(endurance=6)
        self.assertEqual(r.convalescence(c),69)
        self.assertEqual((c['provisions'],c['endurance'],c['habilete']),(5,6,6))
        c = hero(provisions=4)
        self.assertIsNone(r.convalescence(c))
        self.assertEqual(c['endurance'],0)

    def test_cursed_meal_hurts_instead_of_healing(self):
        c = hero(endurance=8)
        self.assertEqual(r.cursed_meal(c),118)
        self.assertEqual((c['endurance'],c['provisions']),(4,9))
        c = hero(provisions=0)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.cursed_meal(c)
        self.assertEqual(c,before)

    def test_wounds_survive_healing_and_count_hits_not_damage(self):
        c = hero()
        for _ in range(3):r.damage_hero(c,1,'ghoul')
        self.assertFalse(r.ghoul_paralysed(c,'ghoul'))
        r.damage_hero(c,1,'ghoul')
        self.assertTrue(r.ghoul_paralysed(c,'ghoul'))
        r.damage_hero(c,2,'werewolf')
        c['endurance'] = 20
        self.assertTrue(r.werewolf_wounded(c,'werewolf'))

    def test_whip_only_hits_on_one_or_two_and_luck_is_optional(self):
        c = hero()
        self.assertEqual(r.whip(c,3),0)
        self.assertEqual(r.whip(c,2),1)
        self.assertEqual(r.whip(c,1,2),0)
        self.assertEqual(c['chance'],7)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.whip(c,6,2)
        self.assertEqual(c,before)

    def test_fake_hammer_cannot_complete_quest(self):
        c = hero(inventory=[r.HAMMER_HEAD,'Faux manche'])
        with self.assertRaises(ValueError):r.hand_over_hammer(c)
        c['inventory'].append(r.HAMMER_HANDLE)
        self.assertTrue(r.hand_over_hammer(c))
        self.assertTrue(c['book_facts']['adventure_won'])
        self.assertFalse(r.hand_over_hammer(c))

    def test_group_transition_and_copy_are_persistent_and_independent(self):
        profile = deepcopy(COMBATS[96]['groups'])
        combat = r.new_group_combat(profile)
        combat['groups'][0][0]['stamina'] = 0
        self.assertTrue(r.advance_group(combat))
        self.assertEqual(combat['group'],1)
        self.assertEqual(profile[0][0]['stamina'],6)
        self.assertFalse(r.advance_group(combat))

    def test_contextual_payment_rejects_wrong_tariff_and_is_not_repeated(self):
        c = hero(inventory=['gem','gem'])
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.pay_paragraph(c,32,gold=10,items=['gem'])
        self.assertEqual(c,before)
        self.assertTrue(r.pay_paragraph(c,32,gold=10,items=['gem','gem']))
        self.assertEqual((c['gold'],c['chance']),(20,7))
        self.assertFalse(r.pay_paragraph(c,32,gold=10,items=['gem','gem']))

    def test_magic_payment_rejects_an_object_without_purchase_provenance(self):
        c = hero(inventory=['Brassard de Force','Anneau de Lumière'])
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.pay_paragraph(c,36,items=c['inventory'])
        self.assertEqual(c,before)

    def test_five_units_tribute_does_not_convert_treasure_value_to_gold(self):
        c = hero(inventory=['Médaillon d’or (valeur 5 Or)'])
        r.pay_paragraph(c,279,gold=4,items=['Médaillon d’or (valeur 5 Or)'])
        self.assertEqual(c['gold'],26)
        self.assertEqual(c['inventory'],[])

    def test_charge_gates_routes_and_spent_boots_do_not_unlock_escape(self):
        c = hero()
        self.assertFalse(r.route_available(c,319,228))
        self.assertTrue(r.route_available(c,319,14))
        r.buy(c,'Bottes de Saut')
        self.assertTrue(r.route_available(c,319,228))
        r.consume(c,'Bottes à Bondir')
        self.assertFalse(r.route_available(c,319,228))

    def test_amber_eye_requires_wearing_not_just_possession(self):
        c = hero()
        r.resolve_entry(c,91)
        self.assertTrue(r.route_available(c,170,223))
        r.wear(c,'Œil d’Ambre',False)
        self.assertFalse(r.route_available(c,170,223))
        self.assertTrue(r.route_available(c,170,346))

    def test_pit_and_fever_check_survival_after_each_loss(self):
        c = hero(endurance=4,chance=3)
        self.assertIsNone(r.spiked_pit(c,12))
        self.assertEqual((c['endurance'],c['chance']),(0,2))
        c = hero(endurance=2,chance=3)
        self.assertIsNone(r.fever_test(c,12))
        self.assertEqual(c['endurance'],0)

    def test_failed_return_ambush_kills_without_resetting_resources(self):
        c = hero(chance=3,gold=7)
        self.assertIsNone(r.return_ambush(c,12))
        self.assertEqual((c['endurance'],c['gold'],c['chance']),(0,7,2))

    def test_levitation_powder_is_consumed_without_becoming_a_shop_charge(self):
        c = hero()
        r.resolve_entry(c,354)
        r.resolve_entry(c,173)
        self.assertNotIn('Poudre de Lévitation',c['inventory'])
        self.assertFalse(r.resolve_entry(c,173))

    def test_wish_restores_only_selected_stat_and_consumes_only_magic_lamp(self):
        c = hero(habilete=3,chance=2,inventory=['Lanterne','Lanterne magique'])
        r.make_wish(c,'habilete')
        self.assertEqual((c['habilete'],c['chance']),(8,2))
        self.assertEqual(c['inventory'],['Lanterne'])
        with self.assertRaises(ValueError):r.make_wish(c,'chance')

    def test_swapping_current_stats_does_not_swap_initial_caps(self):
        c = hero(habilete=8,chance=3)
        caps = deepcopy(c['initial'])
        r.swap_skill_luck(c)
        self.assertEqual((c['habilete'],c['chance']),(3,8))
        self.assertEqual(c['initial'],caps)

    def test_runtime_scope_matches_implementation_and_shop_catalogue(self):
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[1]/'catalogues/evenements_foret_1983.json').read_text(encoding='utf-8'))
        self.assertEqual([(item['name'],item['gold_price']) for item in data['shop_analysis']['items']], list(r.SHOP))
        self.assertEqual(data['mechanics_implementation']['combat_paragraphs'],sorted(COMBATS))
        self.assertEqual(data['mechanics_implementation']['entry_effect_paragraphs'],sorted(r.ENTRY_RULES))
