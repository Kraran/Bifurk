"""Choix de matériel : coût réel, résultats des dés et absence d’effets du Sorcier."""
from copy import deepcopy
import unittest
from grimoire_modules.foret import rules as r


def hero(**changes):
    c = {'habilete':6,'endurance':12,'chance':7,'gold':30,'provisions':10,
         'initial':{'habilete':10,'endurance':20,'chance':10},'inventory':['Épée','Lanterne']}
    c.update(changes)
    return c


class ForetTradesLanternTests(unittest.TestCase):
    def test_sword_only_changes_effective_skill_without_changing_caps_or_healing(self):
        c = hero()
        self.assertTrue(r.take_enchanted_sword(c))
        self.assertEqual(r.forest_combat_skill(c),8)
        for _ in range(3):
            r.equip_forest_weapon(c,'Épée')
            self.assertEqual(r.forest_combat_skill(c),6)
            r.equip_forest_weapon(c,r.ENCHANTED_SWORD)
        self.assertEqual((c['habilete'],c['initial']['habilete']),(6,10))
        c['habilete'] = 9
        self.assertEqual(r.forest_combat_skill(c),10)
        c['habilete'] = 12
        self.assertEqual(r.forest_combat_skill(c),12)
        self.assertFalse(r.take_enchanted_sword(c))

    def test_gnome_returns_original_enchanted_weapon_once_against_gold(self):
        c = hero()
        r.take_enchanted_sword(c)
        r.confiscate_sword(c)
        self.assertNotIn(r.ENCHANTED_SWORD,c['inventory'])
        self.assertTrue(r.pay_paragraph(c,12,gold=10))
        self.assertEqual(c['gold'],20)
        self.assertEqual(c['inventory'].count(r.ENCHANTED_SWORD),1)
        self.assertEqual(r.forest_weapon(c),r.ENCHANTED_SWORD)
        self.assertFalse(r.pay_paragraph(c,12,gold=10))
        self.assertEqual(c['gold'],20)

    def test_two_distinct_copies_of_a_valuable_can_pay_without_creating_gold(self):
        c = hero()
        r.confiscate_sword(c)
        r.resolve_entry(c,202)
        jewel = 'Boucle d’oreille en or (valeur 5 Or)'
        self.assertTrue(r.pay_paragraph(c,12,items=[jewel,jewel]))
        self.assertEqual(c['gold'],30)
        self.assertNotIn(jewel,c['inventory'])
        self.assertIn('Épée',c['inventory'])

    def test_wrong_payment_never_partially_pays_or_returns_sword(self):
        c = hero()
        r.confiscate_sword(c)
        before = deepcopy(c)
        for gold, items in [(9,[]),(10,['Lanterne']),(0,['Lanterne','Lanterne'])]:
            with self.assertRaises(ValueError):r.pay_paragraph(c,12,gold=gold,items=items)
            self.assertEqual(c,before)

    def test_ingot_exchanges_one_object_and_does_not_credit_28_gold(self):
        c = hero()
        r.buy(c,'Bottes à Bondir')
        gold = c['gold']
        self.assertTrue(r.take_ingot(c,'Bottes à Bondir'))
        self.assertEqual(c['gold'],gold)
        self.assertEqual(r.available(c,'Bottes à Bondir'),0)
        self.assertIn('Lingot d’or (valeur 28 Or)',c['inventory'])
        self.assertFalse(r.take_ingot(c,'Lanterne'))
        self.assertIn('Lanterne',c['inventory'])

    def test_lantern_success_then_discard_does_not_consume_travel_lantern(self):
        c = hero()
        r.resolve_entry(c,356)
        self.assertEqual(r.light_lantern(c,2),154)
        self.assertEqual(c['chance'],6)
        r.resolve_entry(c,154)
        self.assertNotIn('Lanterne magique',c['inventory'])
        self.assertIn('Lanterne',c['inventory'])
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.light_lantern(c,2)
        self.assertEqual(c,before)

    def test_lantern_failure_hurts_before_item_loss_and_never_recasts_wish(self):
        c = hero()
        r.resolve_entry(c,356)
        self.assertEqual(r.light_lantern(c,12),370)
        self.assertEqual(c['endurance'],9)
        r.buy(c,'Filtres à Nez')
        self.assertTrue(r.lose_backpack_item(c,'Filtres à Nez'))
        self.assertEqual(r.available(c,'Filtres à Nez'),0)
        self.assertFalse(r.lose_backpack_item(c,'Lanterne'))
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.make_wish(c,'chance')
        self.assertEqual(c,before)

    def test_lethal_lantern_returns_no_destination_and_invalid_roll_is_atomic(self):
        c = hero(endurance=3)
        r.resolve_entry(c,356)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.light_lantern(c,99)
        self.assertEqual(c,before)
        self.assertIsNone(r.light_lantern(c,12))
        self.assertEqual(c['endurance'],0)

    def test_ordinary_lantern_does_not_allow_lantern_roll(self):
        c = hero()
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.light_lantern(c,2)
        self.assertEqual(c,before)

    def test_lost_cursed_ring_does_not_remove_anything(self):
        c = hero()
        r.resolve_entry(c,133)
        before = deepcopy(c)
        with self.assertRaises(ValueError):r.lose_backpack_item(c,'Anneau de Lenteur')
        self.assertEqual(c,before)

    def test_gain_or_gold_reward_never_reduces_chance_above_cap_after_swap(self):
        c = hero(chance=12)
        r.reward(c,'treasure',gold=3)
        r.resolve_entry(c,174)
        self.assertEqual(c['chance'],12)
        self.assertEqual(c['gold'],33)
