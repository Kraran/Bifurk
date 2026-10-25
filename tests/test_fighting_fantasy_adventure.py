"""Services d'aventure communs (P3.0) : clé de livre explicite et Forêt inchangée."""
import copy
import random
import unittest
from collections import Counter

from grimoire_modules.fighting_fantasy import adventure
from grimoire_modules.foret import rules as foret


def hero(**extra):
    data = {'habilete': 9, 'endurance': 18, 'chance': 7,
            'initial': {'habilete': 10, 'endurance': 20, 'chance': 9},
            'gold': 6, 'inventory': ['Épée', 'Corde', 'Corde', 'Anneau de Lenteur']}
    data.update(extra)
    return data


class BookStateTests(unittest.TestCase):
    def test_each_book_keeps_its_own_saved_state(self):
        character = hero()
        self.assertEqual(adventure.peek_state(character, 'cite'), {})
        self.assertNotIn('book_state', character, 'une lecture ne crée aucun marqueur')
        self.assertTrue(adventure.grant_reward(character, 'cite', 'coffre', gold=2))
        self.assertTrue(adventure.grant_reward(character, 'foret', 'coffre', gold=1))
        self.assertFalse(adventure.grant_reward(character, 'cite', 'coffre', gold=2))
        self.assertEqual(character['gold'], 9)
        self.assertEqual(character['book_state'], {'cite': {'rewards': ['coffre']},
                                                   'foret': {'rewards': ['coffre']}})
        self.assertIs(adventure.book_state(character, 'cite'), character['book_state']['cite'])

    def test_finished_adventure_refuses_actions(self):
        for character in (hero(endurance=0), hero(book_facts={'adventure_ended': True})):
            with self.subTest(character=character), self.assertRaisesRegex(ValueError, 'L’aventure est terminée.'):
                adventure.grant_reward(character, 'cite', 'x')
        adventure.ensure_alive(hero())

    def test_reward_luck_stays_under_initial_cap(self):
        character = hero()
        adventure.grant_reward(character, 'cite', 'fontaine', luck=5, items=['Clé'])
        self.assertEqual((character['chance'], character['inventory'][-1]), (9, 'Clé'))
        for bad in ({'identity': ''}, {'identity': 'a', 'gold': -1}, {'identity': 'a', 'items': ['']},
                    {'identity': 'a', 'luck': 1.5}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adventure.grant_reward(hero(), 'cite', **bad)

    def test_dice_rejects_bool_and_out_of_range(self):
        self.assertEqual(adventure.dice(7), 7)
        for value, low, high in ((True, 2, 12), (13, 2, 12), (0, 1, 6), ('3', 1, 6)):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, f'Jet attendu entre {low} et {high}.'):
                adventure.dice(value, low, high)


class PaymentTests(unittest.TestCase):
    def test_payment_checks_follow_the_forest_order(self):
        cases = [({'gold': 7}, {}, 'Paiement en or impossible.'),
                 ({'items': ['Corde'] * 3}, {}, 'Objet de paiement absent'),
                 ({'items': ['Anneau de Lenteur']}, {'cursed': ('Anneau de Lenteur',)}, 'verrouillé'),
                 ({'items': ['Épée']}, {'usable': lambda name: 0}, 'achetés et encore utilisables'),
                 ({'gold': 1, 'items': ['Corde']}, {'units': 3}, 'exactement 3 unités')]
        for payment, options, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                adventure.validate_payment(hero(), payment.get('gold', 0), payment.get('items', ()), **options)
        locked = hero(locked_items=['Épée'])
        with self.assertRaisesRegex(ValueError, adventure.LOCKED_MESSAGE):
            adventure.validate_payment(locked, 0, ['Épée'])

    def test_pay_removes_copies_charges_and_worn_state(self):
        character = hero(book_state={'cite': {'charges': {'Corde': 2}, 'worn': ['Corde']}})
        selected = adventure.pay(character, 'cite', gold=2, items=['Corde', 'Corde'])
        self.assertEqual(selected, Counter({'Corde': 2}))
        self.assertEqual((character['gold'], character['inventory']), (4, ['Épée', 'Anneau de Lenteur']))
        self.assertEqual(character['book_state']['cite'], {'charges': {'Corde': 0}, 'worn': []})

    def test_route_cost_is_paid_once_and_only_when_chosen(self):
        character, paid = hero(), []
        def pay_gold(amount):
            paid.append(amount)
        self.assertFalse(adventure.pay_route(character, 'cite', 1, 2, None, pay_gold=pay_gold))
        self.assertTrue(adventure.pay_route(character, 'cite', 1, 2, ('gold', 3), pay_gold=pay_gold))
        self.assertTrue(adventure.route_paid(character, 'cite', 1, 2))
        self.assertFalse(adventure.pay_route(character, 'cite', 1, 2, ('gold', 3), pay_gold=pay_gold))
        self.assertTrue(adventure.pay_route(character, 'cite', 3, 4, ('chance', 9), pay_gold=pay_gold))
        self.assertEqual((paid, character['chance']), ([3], 0))


class EncounterTests(unittest.TestCase):
    def test_branch_test_spends_luck_or_compares_skill(self):
        character = hero()
        self.assertEqual(adventure.branch_test(character, 'cite', ('chance', 10, 20, 2), 7, 9), 10)
        self.assertEqual(character['chance'], 6)
        self.assertEqual(adventure.branch_test(character, 'cite', ('habilete', 10, 20, 2), 10, 9), 20)
        self.assertEqual((character['endurance'], character['chance']), (16, 6))
        dying = hero(endurance=2)
        self.assertIsNone(adventure.branch_test(dying, 'cite', ('habilete', 10, 20, 3), 12, 9))

    def test_wounds_are_remembered_per_encounter(self):
        character = hero(endurance=3)
        self.assertEqual(adventure.damage_hero(character, 'cite', 2, 'garde'), 2)
        self.assertEqual(adventure.damage_hero(character, 'cite', 5, 'garde'), 1)
        self.assertEqual(adventure.damage_hero(character, 'cite', 1, 'garde'), 0)
        self.assertEqual(character['book_state']['cite']['wounds'], {'garde': 2})
        with self.assertRaisesRegex(ValueError, 'Blessure invalide.'):
            adventure.damage_hero(character, 'cite', -1)

    def test_group_combat_advances_after_each_group_dies(self):
        groups = [[{'name': 'A', 'skill': 6, 'stamina': 4}], [{'name': 'B', 'skill': 5, 'stamina': 3}]]
        combat = adventure.new_group_combat(groups)
        combat['groups'][0][0]['stamina'] = 0
        self.assertEqual(groups[0][0]['stamina'], 4, 'les profils sont copiés')
        self.assertTrue(adventure.advance_group(combat))
        self.assertFalse(adventure.advance_group(combat))
        combat['groups'][1][0]['stamina'] = 0
        self.assertTrue(adventure.advance_group(combat))
        self.assertTrue(combat['finished'])
        for bad in ([], [[]], [[{'name': 'C', 'skill': 1, 'stamina': 0}]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adventure.new_group_combat(bad)


# Implémentations de la Forêt avant P3.0 (commit 697699f), recopiées telles quelles :
# elles servent d'oracle pour vérifier que les enveloppes n'ont rien changé.
def _old_state(c):
    return c.setdefault('book_state', {}).setdefault('foret', {})


def _old_peek(c):
    return c.get('book_state', {}).get('foret', {})


def _old_alive(c):
    if c['endurance'] <= 0 or c.get('book_facts', {}).get('adventure_ended'):
        raise ValueError('L’aventure est terminée.')


def _old_validate(c, gold, items, *, magic_only=False, units=None):
    _old_alive(c)
    if type(gold) is not int or gold < 0 or gold > c.get('gold', 0):
        raise ValueError('Paiement en or impossible.')
    selected = Counter(items)
    inventory = Counter(c.get('inventory', []))
    if any(not isinstance(name, str) or count > inventory[name] for name, count in selected.items()):
        raise ValueError('Objet de paiement absent ou sélectionné trop souvent.')
    if selected.get('Anneau de Lenteur') or any(selected.get(name) for name in c.get('locked_items', [])):
        raise ValueError('Un objet verrouillé ou l’anneau maudit ne peut pas être retiré.')
    if magic_only and any(count > foret.available(c, name) for name, count in selected.items()):
        raise ValueError('Le paiement exige des objets achetés et encore utilisables.')
    if units is not None and gold + sum(selected.values()) != units:
        raise ValueError(f'Le tribut exige exactement {units} unités (une pièce ou un objet).')
    return selected


def _old_pay(c, *, gold=0, items=(), magic_only=False, units=None):
    selected = _old_validate(c, gold, items, magic_only=magic_only, units=units)
    c['gold'] -= gold
    for name, count in selected.items():
        for _ in range(count):
            c['inventory'].remove(name)
        data = _old_state(c)
        if name in data.get('charges', {}):
            data['charges'][name] = max(0, data['charges'][name] - count)
        if name in data.get('worn', []):
            data['worn'].remove(name)


def _old_reward(c, identity, *, gold=0, items=(), luck=0):
    _old_alive(c)
    if not isinstance(identity, str) or not identity or type(gold) is not int or gold < 0:
        raise ValueError('Source de récompense invalide.')
    items = list(items)
    if not all(isinstance(name, str) and name for name in items) or type(luck) is not int:
        raise ValueError('Récompense invalide.')
    if identity in _old_peek(c).get('rewards', []):
        return False
    c['gold'] = c.get('gold', 0) + gold
    c.setdefault('inventory', []).extend(items)
    cap = c.get('initial', {}).get('chance', c['chance'])
    if luck:
        c['chance'] = min(cap, max(0, c['chance'] + luck))
    _old_state(c).setdefault('rewards', []).append(identity)
    return True


def _old_damage(c, amount, encounter=None):
    if type(amount) is not int or amount < 0:
        raise ValueError('Blessure invalide.')
    before = c['endurance']
    c['endurance'] = max(0, before - amount)
    if encounter is not None and before > c['endurance']:
        wounds = _old_state(c).setdefault('wounds', {})
        wounds[encounter] = wounds.get(encounter, 0) + 1
    return before - c['endurance']


def _old_pay_route(c, paragraph, target):
    _old_alive(c)
    cost = foret.ROUTE_COSTS.get((paragraph, target))
    if cost is None or f'{paragraph}:{target}' in _old_peek(c).get('paid_routes', []):
        return False
    resource, amount = cost
    if resource == 'gold':
        _old_pay(c, gold=amount)
    else:
        c[resource] = max(0, c[resource] - amount)
    _old_state(c).setdefault('paid_routes', []).append(f'{paragraph}:{target}')
    return True


def _old_branch(c, paragraph, total):
    _old_alive(c)
    foret.dice(total)
    stat, success, failure, damage = foret.BRANCH_TESTS[paragraph]
    passed = foret.spend_luck(c, total) if stat == 'chance' else total <= foret.effective_skill(c)
    if passed:
        return success
    _old_damage(c, damage)
    return failure if c['endurance'] > 0 else None


class ForestEquivalenceTests(unittest.TestCase):
    """Rejouer des appels tirés au hasard (graine fixe) sur l'oracle et sur la Forêt actuelle."""

    ITEMS = ('Épée', 'Corde', 'Anneau de Lenteur', 'Potion de Guérison', 'Bracelet d’Habileté', 'Bouclier d’empereur')

    def random_hero(self, r):
        inventory = [r.choice(self.ITEMS) for _ in range(r.randint(0, 6))]
        character = hero(endurance=r.choice([0, 1, 2, 5, 18]), chance=r.randint(0, 9), gold=r.randint(0, 6),
                         inventory=inventory)
        data = {}
        if r.random() < .5:
            data['charges'] = {name: r.randint(0, 2) for name in r.sample(self.ITEMS, 2)}
        if r.random() < .5:
            data['worn'] = r.sample(self.ITEMS, 2)
        if r.random() < .5:
            data['rewards'] = ['coffre']
        if r.random() < .3:
            data['paid_routes'] = ['243:166']
        if data:
            character['book_state'] = {'foret': data}
        if r.random() < .2:
            character['locked_items'] = [r.choice(self.ITEMS)]
        if r.random() < .1:
            character['book_facts'] = {'adventure_ended': True}
        return character

    def call(self, function, character, *args, **kwargs):
        try:
            return ('ok', function(character, *args, **kwargs), character)
        except ValueError as exc:
            return ('error', str(exc), character)

    def test_forest_wrappers_match_previous_implementation(self):
        r = random.Random(697699)
        routes = list(foret.ROUTE_COSTS) + [(1, 2)]
        for step in range(4000):
            base = self.random_hero(r)
            items = [r.choice(base['inventory'] or self.ITEMS) for _ in range(r.randint(0, 3))]
            gold = r.choice([0, 1, 2, 7, -1, True])
            kind = step % 6
            if kind == 0:
                options = {'magic_only': r.random() < .4, 'units': r.choice([None, 1, 2, 3])}
                old = self.call(_old_pay, copy.deepcopy(base), gold=gold, items=items, **options)
                new = self.call(foret.pay, copy.deepcopy(base), gold=gold, items=items, **options)
            elif kind == 1:
                options = {'magic_only': r.random() < .4, 'units': r.choice([None, 2])}
                old = self.call(_old_validate, copy.deepcopy(base), gold, items, **options)
                new = self.call(foret._validate_payment, copy.deepcopy(base), gold, items, **options)
            elif kind == 2:
                args = (r.choice(['coffre', 'autre', '', 3]),)
                options = {'gold': gold, 'items': items, 'luck': r.choice([0, 1, 3, -2])}
                old = self.call(_old_reward, copy.deepcopy(base), *args, **options)
                new = self.call(foret.reward, copy.deepcopy(base), *args, **options)
            elif kind == 3:
                args = (r.choice([0, 1, 3, 30, -1]), r.choice([None, 'combat:1']))
                old = self.call(_old_damage, copy.deepcopy(base), *args)
                new = self.call(foret.damage_hero, copy.deepcopy(base), *args)
            elif kind == 4:
                args = r.choice(routes)
                old = self.call(_old_pay_route, copy.deepcopy(base), *args)
                new = self.call(foret.pay_route, copy.deepcopy(base), *args)
            else:
                paragraph = r.choice([p for p in foret.BRANCH_TESTS if p != 158])
                args = (paragraph, r.choice([2, 5, 7, 9, 12, 13]))
                old = self.call(_old_branch, copy.deepcopy(base), *args)
                new = self.call(foret.resolve_branch_test, copy.deepcopy(base), *args)
            self.assertEqual(old, new, f'écart à l’appel {step} ({kind})')

    def test_forest_saved_state_key_and_messages_are_unchanged(self):
        character = hero()
        foret.reward(character, 'coffre')
        self.assertEqual(list(character['book_state']), ['foret'])
        self.assertIs(foret.state(character), character['book_state']['foret'])
        with self.assertRaisesRegex(ValueError, 'Un objet verrouillé ou l’anneau maudit ne peut pas être retiré.'):
            foret.pay(character, items=['Anneau de Lenteur'])


if __name__ == '__main__':
    unittest.main()
