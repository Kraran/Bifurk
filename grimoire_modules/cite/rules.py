"""Règles relues des §1 à 100 de la Cité des Voleurs, sans Qt ni hasard.

Les tables ci-dessous résument les seuls événements de la tranche analysée :
effets d’arrivée, épreuves, boutiques, prix des renvois et conditions d’objets.
Les jets sont fournis par l’appelant. L’état sauvegardé est rangé sous
``character['book_state']['cite']`` ; aucun texte du livre n’y est recopié.
Les paragraphes 101 à 400 restent en consultation : seuls les prix des renvois
qui mènent dans la tranche (le paiement y est décrit) sont appliqués ailleurs.
"""
import unicodedata

from ..fighting_fantasy import adventure
from ..fighting_fantasy.adventure import dice, ensure_alive

BOOK = 'cite'
ANALYSED = range(1, 101)

ARROW = 'Flèche d’argent'
MAIL = 'Cotte de mailles'
SHIELD = 'Bouclier'
GOLD_BROOCH = 'Broche scorpion d’or'
SILVER_BROOCH = 'Broche scorpion d’argent'
INSECT_BRACELET = 'Bracelet-insecte d’argent'

# Habileté de port : la cotte de mailles « ajoute 2 points » tant qu’elle est
# portée (§46) et les retire quand il faut l’enlever (§11). Le score de base de
# la fiche n’est pas modifié : le plafond initial des règles reste intact.
EQUIPMENT_SKILL = ((MAIL, 2),)

# Effets d’arrivée appliqués une seule fois par partie. Clés : endurance,
# habilete, chance, gold (variations), gain (objets), lose (mots-clés d’objets
# retirés s’ils sont présents), provisions ('all' : toutes retirées).
ENTRY_EFFECTS = {
    2: {'lose': ('bracelet',)},
    7: {'chance': 2, 'gain': ('Six perles noires',)},
    8: {'chance': 1, 'gain': (GOLD_BROOCH,)},
    11: {'habilete': -1, 'lose': ('bouclier',), 'remove_mail': True},
    13: {'gain': (SILVER_BROOCH,)},
    16: {'gold': 12, 'chance': 1},
    19: {'endurance': -4, 'habilete': -1},
    32: {'endurance': -4, 'habilete': -1},
    35: {'endurance': -2},
    37: {'endurance': 2},
    38: {'gain': (INSECT_BRACELET,)},
    42: {'provisions': 'all', 'gain': (ARROW,)},
    43: {'habilete': -2, 'chance': -2},
    46: {'gain': (MAIL,)},
    47: {'endurance': -3},
    54: {'gold': 2, 'gain': ('Laissez-passer de marchand',)},
    55: {'gold': 10, 'lose': ('fleur',)},
    58: {'endurance': -1},
    79: {'endurance': -4, 'habilete': -1},
    82: {'lose': ('contrôle mental',), 'gain': ('Mèche de cheveux de Sorcière',)},
    85: {'gain': (ARROW,)},
    88: {'endurance': -4, 'habilete': -1},
    89: {'habilete': -2},
    92: {'gain': ('Miroir',)},
    94: {'endurance': 6},
    97: {'chance': 1, 'gain': ('Clef en fer',)},
    98: {'endurance': 3, 'chance': 1},
}

# Épreuves à deux issues : (caractéristique, réussite, échec, blessure d’échec).
BRANCH_TESTS = {
    15: ('chance', 75, 298, 0),
    18: ('habilete', 102, 225, 0),
    47: ('habilete', 313, 81, 0),
    49: ('chance', 10, 311, 0),
    64: ('chance', 353, 309, 1),
    69: ('habilete', 355, 151, 0),
    81: ('chance', 392, 243, 0),
}

# Événements à résoudre avant de repartir : un dé de soin, le larcin de l’Elfe.
DIE_HEAL = 83
THEFT = 63
THEFT_ITEMS, THEFT_GOLD = 2, 5
# Le larcin vise le sac à dos : arme, armures et bijoux portés n’y sont pas.
WORN_KEYWORDS = ('epee', 'armure', 'cotte de mailles', 'broche', 'anneau', 'bracelet')

# Boutiques facultatives : (article, prix), et nombre maximal d’achats.
SHOPS = {
    36: {'items': (('Anneau d’Invisibilité', 10), ('Anneau de Feu', 8), ('Anneau de Glace', 7)),
         'limit': 1},
    52: {'items': (('Poignard de Jet', 4), ('Corde d’Escalade', 2), ('Croc de Boucher', 2),
                   ('Lance en Fer', 1), ('Lanterne', 3)), 'limit': None},
    66: {'items': (('Clef spéciale du Nain', 10),), 'limit': 1},
}

# Prix payés en choisissant le renvoi : la destination décrit le paiement.
ROUTE_COSTS = {(3, 37): 3, (91, 332): 1, (315, 8): 6, (169, 46): 20,
               (276, 41): 15, (246, 98): 2}
COST_LABELS = {(315, 8): '6 Pièces d’Or'}
# §248 : 10 Pièces d’Or ou deux objets magiques ; « Sinon » mène au §42.
ARROW_OFFER, ARROW_PRICE, ARROW_ITEMS, ARROW_FALLBACK = (248, 85), 10, 2, (248, 42)

# Conditions d’objet imprimées : (mot-clé recherché dans le sac, présent ?).
ITEM_ROUTES = {
    (14, 237): ('anneau de feu', True), (14, 191): ('anneau de feu', False),
    (35, 305): ('miroir', True), (35, 382): ('anneau de glace', True),
    (44, 18): ('poignard de jet', True), (44, 225): ('poignard de jet', False),
    (53, 328): ('argent', True), (53, 39): ('argent', False),
    (61, 172): ('fleur', True), (61, 350): ('fleur', False),
    (80, 392): ('broche scorpion', True), (80, 215): ('broche scorpion', False),
}
# « Si vous ne l’avez pas encore fait » : la destination ne doit pas avoir été lue.
NOT_YET_ROUTES = {(7, 232), (13, 273), (43, 175), (43, 209), (96, 319)}

ENDINGS = (9, 56, 59, 70)
DEATHS = (9, 59, 70)


def state(character):
    return adventure.book_state(character, BOOK)


def peek(character):
    return adventure.peek_state(character, BOOK)


def _fold(text):
    text = unicodedata.normalize('NFKD', str(text).replace('’', "'")).casefold()
    return ''.join(c for c in text if not unicodedata.combining(c))


def matching_items(character, keyword):
    """Exemplaires du sac dont le nom contient le mot-clé (casse et accents ignorés)."""
    key = _fold(keyword)
    return [name for name in character.get('inventory', []) if key in _fold(name)]


def has_item(character, keyword):
    return bool(matching_items(character, keyword))


def effective_skill(character):
    """Habileté de la fiche plus le bonus de la cotte de mailles portée."""
    bonus = sum(value for name, value in EQUIPMENT_SKILL if name in character.get('inventory', []))
    return character.get('habilete', 0) + bonus


def _cap(character, key):
    return character.get('initial', {}).get(key, character[key])


def _change(character, key, amount):
    if amount > 0:
        character[key] = max(character[key], min(_cap(character, key), character[key] + amount))
    else:
        character[key] = max(0, character[key] + amount)


def entry_resolved(character, number):
    return number in peek(character).get('entries', [])


def apply_entry(character, number):
    """Appliquer une fois l’effet d’arrivée relu ; False si déjà appliqué ou absent."""
    effect = ENTRY_EFFECTS.get(number)
    if effect is None or entry_resolved(character, number):
        return False
    ensure_alive(character)
    inventory = character.setdefault('inventory', [])
    for keyword in effect.get('lose', ()):
        for name in matching_items(character, keyword)[:1]:
            inventory.remove(name)
    if effect.get('remove_mail') and MAIL in inventory:
        inventory.remove(MAIL)
    if effect.get('provisions') == 'all':
        character['provisions'] = 0
    character['gold'] = character.get('gold', 0) + effect.get('gold', 0)
    inventory.extend(effect.get('gain', ()))
    for key in ('habilete', 'chance'):
        if effect.get(key):
            _change(character, key, effect[key])
    if effect.get('endurance'):
        if effect['endurance'] < 0:
            adventure.damage_hero(character, BOOK, -effect['endurance'])
        else:
            _change(character, 'endurance', effect['endurance'])
    state(character).setdefault('entries', []).append(number)
    return True


def resolve_test(character, number, total):
    """Résoudre l’épreuve et renvoyer la destination (None si la blessure tue)."""
    ensure_alive(character)
    if number not in BRANCH_TESTS or test_resolved(character, number):
        raise ValueError('Cette épreuve est déjà résolue.')
    dice(total)
    target = adventure.branch_test(character, BOOK, BRANCH_TESTS[number], total,
                                   effective_skill(character))
    state(character).setdefault('tests', {})[str(number)] = target
    return target


def test_target(character, number):
    return peek(character).get('tests', {}).get(str(number))


def test_resolved(character, number):
    return str(number) in peek(character).get('tests', {})


def heal_die(character, die):
    """§83 : un dé d’Endurance gagnée, plafonnée au total initial ; une seule fois."""
    ensure_alive(character)
    if peek(character).get('die_heal') is not None:
        raise ValueError('Ce soin est déjà lancé.')
    dice(die, 1, 6)
    _change(character, 'endurance', die)
    state(character)['die_heal'] = die
    return die


def theft_choices(character):
    """Objets du sac à dos que l’Elfe peut prendre (pas l’équipement porté)."""
    locked = set(character.get('locked_items', []))
    return [name for name in character.get('inventory', [])
            if name not in locked and not any(key in _fold(name) for key in WORN_KEYWORDS)]


def theft_resolved(character):
    return 'theft' in peek(character)


def theft_required(character):
    return min(THEFT_ITEMS, len(theft_choices(character)))


def elf_theft(character, items):
    """§63 : deux objets du sac et 5 Pièces d’Or, ou ce qu’il en reste."""
    ensure_alive(character)
    if theft_resolved(character):
        raise ValueError('Le larcin est déjà constaté.')
    items = list(items)
    choices = list(theft_choices(character))
    if len(items) != theft_required(character):
        raise ValueError(f'Choisissez {theft_required(character)} objet(s) du sac à dos.')
    for name in items:
        if name not in choices:
            raise ValueError('Objet absent du sac à dos ou déjà choisi.')
        choices.remove(name)
    gold = min(THEFT_GOLD, character.get('gold', 0))
    adventure.pay(character, BOOK, gold=gold, items=items)
    state(character)['theft'] = {'gold': gold, 'items': items}
    return gold


def shop_bought(character, number):
    return peek(character).get('shops', {}).get(str(number), [])


def can_buy(character, number, name):
    """None si l’achat est possible, sinon la raison affichée."""
    shop = SHOPS.get(number)
    prices = dict(shop['items']) if shop else {}
    if name not in prices:
        return 'Article inconnu.'
    bought = shop_bought(character, number)
    if shop['limit'] is not None and len(bought) >= shop['limit']:
        return 'Le livre ne permet qu’un seul achat ici.'
    if name in bought:
        return 'Article déjà acheté.'
    if character.get('gold', 0) < prices[name]:
        return 'Pas assez de Pièces d’Or.'
    return None


def buy(character, number, name):
    ensure_alive(character)
    reason = can_buy(character, number, name)
    if reason:
        raise ValueError(reason)
    adventure.pay(character, BOOK, gold=dict(SHOPS[number]['items'])[name])
    character.setdefault('inventory', []).append(name)
    state(character).setdefault('shops', {}).setdefault(str(number), []).append(name)


def arrow_offer_payable(character):
    return (character.get('gold', 0) >= ARROW_PRICE
            or len(magic_payment_choices(character)) >= ARROW_ITEMS)


def magic_payment_choices(character):
    """Objets proposables à l’orfèvre : tout le sac sauf l’équipement de départ."""
    locked = set(character.get('locked_items', [])) | {'Épée', 'Armure de cuir'}
    return [name for name in character.get('inventory', []) if name not in locked]


def route_cost(source, target):
    return ROUTE_COSTS.get((source, target))


def route_available(character, source, target, visited=()):
    """Tester la condition imprimée d’un renvoi, sans rien modifier."""
    key = (source, target)
    if key in NOT_YET_ROUTES and target in visited:
        return False
    if key in ITEM_ROUTES:
        keyword, present = ITEM_ROUTES[key]
        if has_item(character, keyword) != present:
            return False
    if key == ARROW_OFFER:
        return adventure.route_paid(character, BOOK, *key) or arrow_offer_payable(character)
    if key == ARROW_FALLBACK:
        return not arrow_offer_payable(character)
    cost = route_cost(source, target)
    if cost is not None and not adventure.route_paid(character, BOOK, source, target):
        return character.get('gold', 0) >= cost
    return True


def pay_route(character, source, target, items=()):
    """Payer le prix du renvoi choisi ; les objets ne servent qu’à l’offre du §248."""
    if (source, target) == ARROW_OFFER:
        if adventure.route_paid(character, BOOK, source, target):
            return False
        items = list(items)
        if items:
            choices = magic_payment_choices(character)
            if len(items) != ARROW_ITEMS or any(items.count(n) > choices.count(n) for n in items):
                raise ValueError('Choisissez deux objets du sac.')
            adventure.pay(character, BOOK, items=items)
        else:
            adventure.pay(character, BOOK, gold=ARROW_PRICE)
        state(character).setdefault('paid_routes', []).append(f'{source}:{target}')
        return True
    cost = route_cost(source, target)
    return adventure.pay_route(character, BOOK, source, target,
                               None if cost is None else ('gold', cost),
                               pay_gold=lambda amount: adventure.pay(character, BOOK, gold=amount))


def finish_ending(character, number):
    """Fin imprimée (mort ou échec) : l’aventure se termine sans blessure inventée."""
    if number not in ENDINGS or peek(character).get('ending'):
        return False
    state(character)['ending'] = number
    if number in DEATHS:
        character['endurance'] = 0
    character.setdefault('book_facts', {})['adventure_ended'] = True
    return True
