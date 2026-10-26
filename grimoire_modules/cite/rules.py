"""Règles relues des §1 à 400 de la Cité des Voleurs, sans Qt ni hasard.

Les tables ci-dessous résument les seuls événements de la tranche analysée :
effets d’arrivée, épreuves, boutiques, prix des renvois et conditions d’objets.
Les jets sont fournis par l’appelant. L’état sauvegardé est rangé sous
``character['book_state']['cite']`` ; aucun texte du livre n’y est recopié.
Depuis la phase 3.4, les 400 paragraphes sont analysés ; la VO anglaise fait
référence en cas de divergence avec la traduction.
"""
import re
import unicodedata

from ..fighting_fantasy import adventure
from ..fighting_fantasy.adventure import dice, ensure_alive

BOOK = 'cite'
ANALYSED = range(1, 401)

ARROW = 'Flèche d’argent'
MAIL = 'Cotte de mailles'
SHIELD = 'Bouclier'
GOLD_BROOCH = 'Broche scorpion d’or'
SILVER_BROOCH = 'Broche scorpion d’argent'
INSECT_BRACELET = 'Bracelet-insecte d’argent'
PEARLS = 'Six perles noires'
SKELETON_KEY = 'Passe-partout'
EYE_RING = 'Anneau de l’Œil d’Or'
POULTICE = 'Emplâtre d’herbes'
CURSED_SHIELD = 'Bouclier à la tour'
PLAIN_SWORD = 'Épée de combat ordinaire'
BOW = 'Arc en bois d’if'
GARLIC = 'Gousse d’ail'
TATTOO = 'Tatouage au front'
GOLDEN_FLOWER = 'Fleur dorée à dix pétales'

# Familles d’objets : (mots-clés acceptés, mots-clés exclus). Un nom libre saisi
# dans l’inventaire est reconnu par mot-clé ; ces familles évitent qu’une fleur
# de lotus passe pour un bouquet, ou une fleur dorée pour l’inverse.
ITEM_KINDS = {
    'bouquet': (('bouquet', 'fleur'), ('lotus', "d'or", 'doree')),
    'fleurs d’or': (("fleurs d'or", "fleur d'or", 'fleur doree', 'fleurs dorees'), ()),
    'épée': (('epee',), ()),
    # « =ail » : le nom exact ; « ail » seul se retrouverait dans « cotte de mailles ».
    'ail': (("d'ail", '=ail'), ()),
    'œil d’or': (("œil d'or", "oeil d'or"), ()),
    'pierres précieuses': (('pierres precieuses', 'pierre precieuse'), ()),
    # §265 « contrôle mental » ; la potion du §359 s’appelle « Contrôle de l’esprit ».
    'contrôle mental': (('controle mental', "controle de l'esprit"), ()),
}

# Habileté de port : la cotte de mailles « ajoute 2 points » tant qu’elle est
# portée (§46) et les retire quand il faut l’enlever (§11). Le score de base de
# la fiche n’est pas modifié : le plafond initial des règles reste intact.
EQUIPMENT_SKILL = ((MAIL, 2),)
# Force d’Attaque : le bouclier du §340 et le casque du §376 ajoutent 1 point
# à chaque Assaut tant qu’ils sont dans l’inventaire (pas à l’Habileté).
MAGNIFICENT_SHIELD = 'Bouclier magnifique'
MAGIC_HELMET = 'Casque magique'
EQUIPMENT_ATTACK = ((MAGNIFICENT_SHIELD, 1), (MAGIC_HELMET, 1))

# Effets d’arrivée appliqués une seule fois par partie. Clés : endurance,
# habilete, chance, gold (variations), gain (objets), lose (mots-clés d’objets
# retirés s’ils sont présents), provisions ('all' : toutes retirées), pay (or
# remis, au plus ce que l’on possède), lose_all (tous les objets du mot-clé).
ENTRY_EFFECTS = {
    2: {'lose': ('bracelet',)},
    7: {'chance': 2, 'gain': ('Six perles noires',)},
    8: {'chance': 2, 'gain': (GOLD_BROOCH,)},  # VO : 2 points (la traduction en donne 1).
    11: {'habilete': -1, 'lose': ('bouclier',), 'remove_mail': True},
    13: {'gain': (SILVER_BROOCH,)},
    16: {'gold': 12, 'chance': 1},
    19: {'endurance': -4, 'habilete': -1},
    32: {'endurance': -4, 'habilete': -1},
    35: {'endurance': -2},
    37: {'chance': 2},  # VO : 2 points de Chance (la traduction dit Endurance).
    38: {'gain': (INSECT_BRACELET,)},
    42: {'provisions': 'all', 'gain': (ARROW,)},
    43: {'habilete': -2, 'chance': -2},
    46: {'gain': (MAIL,)},
    47: {'endurance': -3},
    54: {'gold': 2, 'gain': ('Laissez-passer de marchand',)},
    55: {'gold': 10, 'lose': ('fleurs d’or',)},
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
    106: {'lose': ('lanterne',)},
    111: {'chance': 2, 'gain': (PEARLS,)},
    123: {'gold': 3, 'chance': 1, 'gain': (SKELETON_KEY,)},
    # Bouclier maudit : impossible de s’en débarrasser (objet verrouillé).
    125: {'habilete': -1, 'gain': (CURSED_SHIELD,), 'lock': True},
    # 2 points par flèche reçue au §137, puis l’épée d’Owen Carralif échangée.
    126: {'arrow_heal': 2, 'habilete': -1, 'swap_sword': PLAIN_SWORD},
    132: {'gain': (SILVER_BROOCH,)},
    134: {'gold_all': True},
    147: {'gold': 16},
    149: {'endurance': -2},
    155: {'endurance': -3},
    163: {'chance': 2, 'gain': (EYE_RING,)},
    167: {'chance': 1, 'gain': (POULTICE,)},
    172: {'gold': 2, 'lose': ('bouquet',)},
    186: {'gold': 4},
    194: {'gain': ('Boule de verre',)},
    198: {'gold': 9, 'gain': ('Crâne d’ivoire à chaîne d’argent',)},
    199: {'gold': 5},
    # §201 : nuit sous l’orme, puis l’arc taillé pour la flèche d’argent.
    201: {'endurance': 2, 'gain': (BOW,)},
    209: {'gold': 12},
    211: {'endurance': 1},
    221: {'gold_all': True, 'chance': -2},
    230: {'chance': 1},
    233: {'endurance': 1},
    # §240 : les deux pierres précieuses vendues 9 Pièces d’Or (prix du §302).
    240: {'gold': 9, 'lose': ('pierres précieuses',)},
    242: {'endurance': -1},
    243: {'endurance': -5},
    273: {'chance': 2, 'gain': (GOLD_BROOCH,)},
    274: {'gold': 5},
    # Le tatouage figure dans l’inventaire ; il ne peut être ni volé ni remis.
    279: {'gain': (TATTOO,), 'lock': True},
    295: {'gold': 12, 'chance': 1},
    298: {'endurance': -4},
    # ----- Phase 3.4 : §301 à 400 (valeurs relues sur la VO) -----
    305: {'endurance': -2},
    306: {'gold': 2, 'gain': ('Laissez-passer de marchand',)},
    312: {'gain': ('Chouette en or',)},
    322: {'gold': 11},
    # §324 : on n’emporte que l’or et les pierres ; essayer le gant mène au §89.
    324: {'gold': 15, 'gain': ('Deux pierres précieuses',)},
    325: {'endurance': 5},
    # §328 : l’objet d’argent est remis en choisissant le renvoi du §53.
    328: {'gold': 2},
    330: {'endurance': -3},
    332: {'chance': 1},
    338: {'chance': -3},
    340: {'chance': 1, 'gold': 25, 'gain': (MAGNIFICENT_SHIELD,)},
    341: {'pay': 5},
    # §343 : « tous vos objets d’argent » fondent (flèche d’argent comprise).
    343: {'endurance': -3, 'lose_all': ('argent',)},
    351: {'gain': ('Clef en fer',)},
    359: {'gold': 8, 'endurance': 2,
          'gain': ('Potion de Contrôle de l’esprit', 'Flûte en argent', 'Morceau de craie',
                   'Bandeau pour l’œil')},
    362: {'gain': ('Bottes magiques',), 'habilete': 1},
    364: {'pay': 2},
    365: {'habilete': -1},
    366: {'endurance': -2},
    # §367 : on garde 1 Pièce d’Or escamotée sur l’amende (VO « except 1 Gold Piece »).
    367: {'refund_all_gold': 1},
    373: {'endurance': -4, 'habilete': -1},
    374: {'gain': ('Bouclier du chevalier',), 'habilete': 1},
    376: {'gain': (MAGIC_HELMET,), 'chance': 1},
    379: {'endurance': -2},
    380: {'endurance': 4},
    387: {'gain': ('Broche scorpion de cuivre',), 'habilete': -1},
    395: {'chance': -4},
    397: {'gold': 1},
}

# Épreuves à deux issues : (caractéristique, réussite, échec, blessure d’échec).
# Un échec None est une fin imprimée sans renvoi (§203) : l’aventure s’arrête.
BRANCH_TESTS = {
    15: ('chance', 75, 298, 0),
    18: ('habilete', 102, 225, 0),
    47: ('habilete', 313, 81, 0),
    49: ('chance', 10, 311, 0),
    64: ('chance', 353, 309, 1),
    69: ('habilete', 355, 151, 0),
    81: ('chance', 304, 243, 0),  # VO : fuite vers le nord au §304 (imprimé 392).
    120: ('chance', 84, 152, 0),
    162: ('chance', 7, 226, 0),
    168: ('habilete', 359, 266, 0),
    175: ('chance', 204, 373, 0),
    190: ('habilete', 38, 296, 0),
    # §192 : une seule suite ; l’échec coûte 1 point d’Habileté.
    192: ('chance', 304, 304, 0),
    203: ('chance', 244, None, 0),
    214: ('chance', 158, 379, 0),
    229: ('chance', 23, 343, 0),
    247: ('chance', 384, 134, 0),
    251: ('chance', 269, 330, 0),
    252: ('chance', 275, 155, 0),
    291: ('chance', 74, 10, 2),
    389: ('habilete', 159, 304, 0),
    390: ('chance', 144, 59, 0),
    391: ('chance', 235, 142, 0),
}
# Pertes imprimées en cas d’échec, en plus du renvoi : (ressource, montant).
TEST_PENALTIES = {190: ('gold', 5), 192: ('habilete', 1)}
# §128 : deux fois la Chance ; la destination dépend du nombre d’échecs (0, 1, 2).
DOUBLE_TESTS = {128: ('chance', (340, 149, 19))}
# Un dé décisif : (faces mortelles, renvoi sinon, Pièces d’Or gagnées sinon).
DIE_TESTS = {223: ((1,), 165, 20)}

# Événements à résoudre avant de repartir : un dé de soin, le larcin de l’Elfe.
DIE_HEAL = 83
THEFT = 63
THEFT_ITEMS, THEFT_GOLD = 2, 5
# §148 : 1 Pièce d’Or ou un objet, au choix du joueur. §137 : un dé de flèches,
# puis 2 points de Chance perdus si l’on survit (VO ; la traduction dit Endurance).
POCKET, POCKET_GOLD = 148, '1 Pièce d’Or'
VOLLEY, VOLLEY_HIT, VOLLEY_AFTER = 137, 3, 2
# Le larcin vise le sac à dos : arme, armures et bijoux portés n’y sont pas.
WORN_KEYWORDS = ('epee', 'armure', 'cotte de mailles', 'broche', 'anneau', 'bracelet')

# §201 : le mélange de deux ingrédients, puis un dé désigne la créature.
MIXTURE = 201
MIXTURES = (('Cheveux de Sorcière et perles noires', 9),
            ('Perles noires et fleur de lotus', 129),
            ('Fleur de lotus et cheveux de Sorcière', 337))
MIXTURE_ROUTES = 244
CREATURE = 201
CREATURES = {1: ('Orque', 5, 4), 2: ('Serpent Géant', 6, 6), 3: ('Loup', 5, 5),
             4: ('Pygmée', 4, 4), 5: ('Homme-Singe', 7, 6), 6: ('Troll des Cavernes', 8, 7)}
# §138 : la suite dépend de la créature affrontée au §201 (5 : l’Homme-Singe).
CREATURE_ROUTES = {(138, 312): True, (138, 283): False}
APE_MAN = 5
# §206 : « Qui gagne prend » — mise de 2, gain de 6, quatre parties au plus.
GAMBLE, GAMBLE_STAKE, GAMBLE_WIN, GAMBLE_ROUNDS, GAMBLE_DWARVES = 206, 2, 6, 4, 3
# §266 : deux objets du sac à dos perdus dans la bousculade, au choix du joueur.
BRAWL, BRAWL_ITEMS = 266, 2
# Butins facultatifs : « prenez ce que vous voulez » (une seule fouille).
LOOTS = {
    # §114 : VO « Take what you will » — trois bagues et 13 Pièces d’Or, au choix.
    114: {'gold': 13, 'items': ('Bague ornée de pierreries',) * 3},
    208: {'gold': 2, 'items': (GARLIC, 'Vieux osselets')},
    # §220 : le contenu de la vitrine est décrit au §146.
    220: {'gold': 0, 'items': ('Gobelet en argent', 'Gobelet en argent', 'Calice en argent',
                               'Cuillère en argent')},
    285: {'gold': 7, 'items': ('Trousseau de clefs', 'Morceau de pain rassis')},
}
# §287 : un repas chaud facultatif, (prix, Endurance gagnée).
HOT_MEAL, HOT_MEAL_PRICE, HOT_MEAL_GAIN = 287, 1, 2
# §293 : la fleur dorée contre un objet magique, une pièce d’armure ou deux Provisions
# (VO : « piece of armour » ; la traduction dit « une arme »).
TRADE, TRADE_PROVISIONS = 293, 2
TRADE_PROVISIONS_LABEL = 'Deux portions de Provisions'
ARMOUR_KEYWORDS = ('armure', 'cotte de mailles', 'bouclier', 'casque', 'cuirasse', 'heaume')

# Boutiques facultatives : (article, prix), nombre maximal d’achats, et
# « repeat » quand un article s’achète en autant d’exemplaires qu’on le désire.
SHOPS = {
    36: {'items': (('Anneau d’Invisibilité', 10), ('Anneau de Feu', 8), ('Anneau de Glace', 7)),
         'limit': 1},
    52: {'items': (('Poignard de Jet', 4), ('Corde d’Escalade', 2), ('Croc de Boucher', 2),
                   ('Lance en Fer', 1), ('Lanterne', 3)), 'limit': None},
    66: {'items': (('Clef spéciale du Nain', 10),), 'limit': 1},
    241: {'items': (('Bougie de couleur', 1),), 'limit': None, 'repeat': True},
}

# Prix payés en choisissant le renvoi : la destination décrit le paiement.
ROUTE_COSTS = {(3, 37): 3, (91, 332): 1, (315, 8): 6, (169, 46): 20,
               (276, 41): 15, (246, 98): 2, (315, 132): 6, (119, 233): 3, (151, 351): 10,
               (160, 211): 1, (160, 242): 1, (182, 279): 10, (183, 366): 1, (183, 167): 4,
               (222, 370): 1, (276, 267): 10, (300, 347): 10, (342, 289): 1,
               (316, 279): 10, (381, 261): 3, (394, 368): 2}
# §300 : laisser l’or coûte aussi 2 points de Chance.
ROUTE_LUCK = {(300, 347): 2}
# §276→§109 : les cinq pièces sont offertes puis refusées (§109) ; il faut les avoir.
GOLD_SHOWN_ROUTES = {(276, 109): 5, (354, 316): 10}
# §264 : partager ses vivres coûte deux portions de Provisions.
PROVISION_ROUTES = {(264, 121): 2}
COST_LABELS = {(315, 8): '6 Pièces d’Or', (315, 132): '6 Pièces d’Or'}
# §150 : l’amende est tout l’or du sac ; §182 : renoncer seulement sans 10 Pièces d’Or.
ALL_GOLD_ROUTES = {(150, 367), (335, 367)}
GOLD_BELOW_ROUTES = {(182, 354): 10, (354, 307): 10}
# Renvois payés par un objet choisi : sac à dos (§113) ou objet magique exigé (§187).
ITEM_PAYMENTS = {(113, 141): 'backpack', (187, 260): 'magic', (53, 328): 'silver'}
NO_MAGIC_ROUTE = (187, 341)
MAGIC_KEYWORDS = ('anneau', 'armure magique', 'potion')
STARTING_POTION = 'potion de départ'
# §248 : 10 Pièces d’Or ou deux objets magiques ; « Sinon » mène au §42.
ARROW_OFFER, ARROW_PRICE, ARROW_ITEMS, ARROW_FALLBACK = (248, 85), 10, 2, (248, 42)

# Conditions d’objet imprimées : (mot-clé recherché dans le sac, présent ?).
ITEM_ROUTES = {
    (14, 237): ('anneau de feu', True), (14, 191): ('anneau de feu', False),
    (35, 305): ('miroir', True), (35, 382): ('anneau de glace', True),
    (44, 18): ('poignard de jet', True), (44, 225): ('poignard de jet', False),
    (53, 328): ('argent', True), (53, 39): ('argent', False),
    (61, 172): ('bouquet', True), (61, 350): ('bouquet', False),
    (80, 392): ('broche scorpion', True), (80, 215): ('broche scorpion', False),
    (118, 2): ('bracelet-insecte', True), (118, 166): ('bracelet-insecte', False),
    (146, 220): ('passe-partout', True), (146, 388): ('passe-partout', False),
    (184, 55): ('fleurs d’or', True), (184, 308): ('fleurs d’or', False),
    (193, 286): ('anneau de feu', True), (193, 163): ('anneau de feu', False),
    (257, 385): ('œil d’or', True), (257, 70): ('œil d’or', False),
    (258, 318): ('crâne d’ivoire', True), (258, 47): ('crâne d’ivoire', False),
    (259, 228): ('passe-partout', True), (259, 4): ('passe-partout', False),
    (259, 365): ('passe-partout', False),
    (263, 153): ('chouette', True), (263, 281): ('chouette', False),
    (265, 82): ('contrôle mental', True), (265, 390): ('contrôle mental', False),
    (290, 219): ('laissez-passer', True), (290, 335): ('laissez-passer', False),
    (292, 254): ('ail', True), (292, 210): ('ail', False),
    (334, 255): ('laissez-passer', True), (334, 99): ('laissez-passer', False),
    (336, 302): ('pierres précieuses', True),
    (352, 106): ('lanterne', True),
    # §353 « clef métallique » : la clef en fer du §97 ou du §351.
    (353, 181): ('clef en fer', True), (353, 389): ('clef en fer', False),
    (353, 304): ('clef en fer', False),
    (358, 108): ('corde', True),
}
# §108 et §156 : les objets nécessaires contre le Prince de la Nuit et le tatouage.
MISSION_ITEMS = ('flèche d’argent', 'perles noires', 'cheveux de sorcière', 'lotus')
TATTOO_PARAGRAPHS = (279,)
MISSION_ROUTES = {(108, 201): True, (108, 299): False, (156, 201): True, (156, 299): False,
                  (239, 201): True, (239, 299): False, (367, 201): True, (367, 299): False}
# « Si vous ne l’avez pas encore fait » : la destination ne doit pas avoir été lue.
NOT_YET_ROUTES = {(7, 232), (13, 273), (43, 175), (43, 209), (96, 319),
                  (104, 118), (111, 232), (174, 356), (176, 271), (204, 209), (204, 43),
                  (209, 175), (209, 43), (273, 13), (284, 232), (373, 209), (373, 43),
                  (383, 271)}

ENDINGS = (9, 56, 59, 70, 129, 142, 210, 288, 299, 346, 400)
DEATHS = (9, 59, 70, 129, 142, 210, 288, 346)
VICTORY = 400


def state(character):
    return adventure.book_state(character, BOOK)


def peek(character):
    return adventure.peek_state(character, BOOK)


def _fold(text):
    text = unicodedata.normalize('NFKD', str(text).replace('’', "'")).casefold()
    return ''.join(c for c in text if not unicodedata.combining(c))


def _matches(name, keyword):
    if keyword in ITEM_KINDS:
        accepted, excluded = ITEM_KINDS[keyword]
        folded = _fold(name)
        return (any(folded == _fold(key[1:]) if key.startswith('=') else _fold(key) in folded
                    for key in accepted)
                and not any(_fold(key) in folded for key in excluded))
    return _fold(keyword) in _fold(name)


def matching_items(character, keyword):
    """Exemplaires du sac dont le nom contient le mot-clé (casse et accents ignorés)."""
    return [name for name in character.get('inventory', []) if _matches(name, keyword)]


def has_item(character, keyword):
    return bool(matching_items(character, keyword))


def effective_skill(character):
    """Habileté de la fiche plus le bonus de la cotte de mailles portée."""
    bonus = sum(value for name, value in EQUIPMENT_SKILL if name in character.get('inventory', []))
    return character.get('habilete', 0) + bonus


def attack_bonus(character):
    """Bonus de Force d’Attaque du bouclier (§340) et du casque (§376) emportés."""
    return sum(value for name, value in EQUIPMENT_ATTACK if name in character.get('inventory', []))


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
    locked = set(character.get('locked_items', []))
    for keyword in effect.get('lose_all', ()):
        for name in [n for n in matching_items(character, keyword) if n not in locked]:
            inventory.remove(name)
    if effect.get('pay'):
        adventure.pay(character, BOOK, gold=min(effect['pay'], character.get('gold', 0)))
    if effect.get('refund_all_gold'):
        paid = state(character).get('all_gold_paid', 0)
        character['gold'] = character.get('gold', 0) + min(effect['refund_all_gold'], paid)
    if effect.get('remove_mail') and MAIL in inventory:
        inventory.remove(MAIL)
    if effect.get('provisions') == 'all':
        character['provisions'] = 0
    if effect.get('gold_all'):
        character['gold'] = 0
    if effect.get('swap_sword'):
        for name in matching_items(character, 'épée')[:1]:
            inventory[inventory.index(name)] = effect['swap_sword']
    if effect.get('arrow_heal'):
        _change(character, 'endurance', effect['arrow_heal'] * peek(character).get('arrows', 0))
    character['gold'] = character.get('gold', 0) + effect.get('gold', 0)
    inventory.extend(effect.get('gain', ()))
    if effect.get('lock'):
        character.setdefault('locked_items', []).extend(effect.get('gain', ()))
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
    stat = BRANCH_TESTS[number][0]
    passed = total <= (character['chance'] if stat == 'chance' else effective_skill(character))
    target = adventure.branch_test(character, BOOK, BRANCH_TESTS[number], total,
                                   effective_skill(character))
    if not passed and BRANCH_TESTS[number][2] is None and character['endurance'] > 0:
        _end(character, number, death=True)
    if not passed and number in TEST_PENALTIES and target is not None:
        resource, amount = TEST_PENALTIES[number]
        if resource == 'gold':
            adventure.pay(character, BOOK, gold=min(amount, character.get('gold', 0)))
        else:
            _change(character, resource, -amount)
    state(character).setdefault('tests', {})[str(number)] = target
    return target


def resolve_double(character, number, totals):
    """§128 : deux tests de Chance ; la destination dépend du nombre d’échecs."""
    ensure_alive(character)
    if number not in DOUBLE_TESTS or test_resolved(character, number):
        raise ValueError('Cette épreuve est déjà résolue.')
    totals = list(totals)
    if len(totals) != 2:
        raise ValueError('Deux jets sont nécessaires.')
    for total in totals:
        dice(total)
    failures = sum(not adventure.stat_test(character, 'chance', total, 0) for total in totals)
    target = DOUBLE_TESTS[number][1][failures]
    state(character).setdefault('tests', {})[str(number)] = target
    return target


def resolve_die_test(character, number, die):
    """§223 : un dé ; une face mortelle termine l’aventure, sinon l’or promis est gagné."""
    ensure_alive(character)
    if number not in DIE_TESTS or test_resolved(character, number):
        raise ValueError('Ce dé est déjà lancé.')
    dice(die, 1, 6)
    deadly, target, gold = DIE_TESTS[number]
    if die in deadly:
        _end(character, number, death=True)
        target = None
    else:
        character['gold'] = character.get('gold', 0) + gold
    state(character).setdefault('tests', {})[str(number)] = target
    return target


def pending_test(character, number):
    return ((number in BRANCH_TESTS or number in DOUBLE_TESTS or number in DIE_TESTS)
            and not test_resolved(character, number))


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
    if name in bought and not shop.get('repeat'):
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
    locked = set(character.get('locked_items', [])) | {'Épée', 'Armure de cuir', PLAIN_SWORD}
    return [name for name in character.get('inventory', []) if name not in locked]


def route_cost(source, target):
    return ROUTE_COSTS.get((source, target))


def mission_ready(character, visited=()):
    """§108/§156/§239 : les quatre objets réunis et le tatouage fait (§279 lu)."""
    return (all(has_item(character, keyword) for keyword in MISSION_ITEMS)
            and (TATTOO in character.get('inventory', [])
                 or any(number in visited for number in TATTOO_PARAGRAPHS)))


def item_payment_choices(character, key):
    """Objets acceptés par un renvoi payé en nature (§113 : sac ; §187 : magie)."""
    if ITEM_PAYMENTS.get(key) == 'backpack':
        return theft_choices(character)
    if ITEM_PAYMENTS.get(key) == 'silver':
        locked = set(character.get('locked_items', []))
        return [name for name in matching_items(character, 'argent') if name not in locked]
    if ITEM_PAYMENTS.get(key) != 'magic' and key != NO_MAGIC_ROUTE:
        return []
    locked = set(character.get('locked_items', []))
    choices = [name for name in character.get('inventory', [])
               if name not in locked and any(_fold(k) in _fold(name) for k in MAGIC_KEYWORDS)]
    if character.get('potion') and character.get('potion_doses', 0) > 0:
        choices.append(f"{character['potion']} ({STARTING_POTION})")
    return choices


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
    if key in MISSION_ROUTES:
        return mission_ready(character, visited) == MISSION_ROUTES[key]
    if key in GOLD_BELOW_ROUTES:
        return character.get('gold', 0) < GOLD_BELOW_ROUTES[key]
    if key in GOLD_SHOWN_ROUTES:
        return character.get('gold', 0) >= GOLD_SHOWN_ROUTES[key]
    if key in CREATURE_ROUTES:
        creature = peek(character).get('creature')
        return creature is None or (creature == APE_MAN) == CREATURE_ROUTES[key]
    if source == MIXTURE_ROUTES:
        mixture = peek(character).get('mixture')
        return mixture is None or mixture == target
    if key in PROVISION_ROUTES and not adventure.route_paid(character, BOOK, *key):
        return character.get('provisions', 0) >= PROVISION_ROUTES[key]
    if key in ITEM_PAYMENTS:
        return adventure.route_paid(character, BOOK, *key) or bool(item_payment_choices(character, key))
    if key == NO_MAGIC_ROUTE:
        return not item_payment_choices(character, key)
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
    if (source, target) in ITEM_PAYMENTS:
        if adventure.route_paid(character, BOOK, source, target):
            return False
        items = list(items)
        choices = item_payment_choices(character, (source, target))
        if len(items) != 1 or items[0] not in choices:
            raise ValueError('Choisissez un objet accepté.')
        if items[0].endswith(f'({STARTING_POTION})'):
            character['potion_doses'] = 0
        else:
            adventure.pay(character, BOOK, items=items)
        state(character).setdefault('paid_routes', []).append(f'{source}:{target}')
        return True
    if (source, target) in ALL_GOLD_ROUTES:
        if adventure.route_paid(character, BOOK, source, target):
            return False
        state(character)['all_gold_paid'] = character.get('gold', 0)
        adventure.pay(character, BOOK, gold=character.get('gold', 0))
        state(character).setdefault('paid_routes', []).append(f'{source}:{target}')
        return True
    if (source, target) in PROVISION_ROUTES:
        if adventure.route_paid(character, BOOK, source, target):
            return False
        amount = PROVISION_ROUTES[(source, target)]
        if character.get('provisions', 0) < amount:
            raise ValueError('Pas assez de Provisions.')
        character['provisions'] -= amount
        state(character).setdefault('paid_routes', []).append(f'{source}:{target}')
        return True
    cost = route_cost(source, target)
    paid = adventure.pay_route(character, BOOK, source, target,
                               None if cost is None else ('gold', cost),
                               pay_gold=lambda amount: adventure.pay(character, BOOK, gold=amount))
    if paid and (source, target) in ROUTE_LUCK:
        _change(character, 'chance', -ROUTE_LUCK[(source, target)])
    return paid


def volley(character, die):
    """§137 : un dé de flèches, 3 points d’Endurance chacune, puis 2 de Chance si l’on survit."""
    ensure_alive(character)
    if peek(character).get('arrows') is not None:
        raise ValueError('La volée est déjà lancée.')
    dice(die, 1, 6)
    state(character)['arrows'] = die
    adventure.damage_hero(character, BOOK, VOLLEY_HIT * die)
    if character['endurance'] > 0:
        _change(character, 'chance', -VOLLEY_AFTER)
    return die


def volley_resolved(character):
    return peek(character).get('arrows') is not None


def pocket_choices(character):
    """§148 : une Pièce d’Or ou n’importe quel objet non verrouillé."""
    locked = set(character.get('locked_items', []))
    gold = [POCKET_GOLD] if character.get('gold', 0) > 0 else []
    return gold + [name for name in character.get('inventory', []) if name not in locked]


def pocket_resolved(character):
    return 'pocket' in peek(character)


def _loot_gold_label(amount):
    return f'{amount} Pièce{"s" if amount > 1 else ""} d’Or'


def loot_choices(number):
    loot = LOOTS[number]
    return ([_loot_gold_label(loot['gold'])] if loot['gold'] else []) + list(loot['items'])


def loot_taken(character, number):
    return str(number) in peek(character).get('loots', {})


def take_loot(character, number, chosen):
    """Garder ce que l’on veut du butin, en une seule fouille."""
    ensure_alive(character)
    if number not in LOOTS or loot_taken(character, number):
        raise ValueError('Ce butin est déjà partagé.')
    chosen = list(chosen)
    pool = loot_choices(number)
    for name in chosen:
        if name not in pool:
            raise ValueError('Objet absent du butin.')
        pool.remove(name)
    loot = LOOTS[number]
    for name in chosen:
        if loot['gold'] and name == _loot_gold_label(loot['gold']):
            character['gold'] = character.get('gold', 0) + loot['gold']
        else:
            character.setdefault('inventory', []).append(name)
    state(character).setdefault('loots', {})[str(number)] = chosen
    return chosen


def pick_pocket(character, choice):
    """§148 : le larcin choisi par le joueur ; None si le sac et la bourse sont vides."""
    ensure_alive(character)
    if pocket_resolved(character):
        raise ValueError('Le larcin est déjà constaté.')
    choices = pocket_choices(character)
    if choices and choice not in choices:
        raise ValueError('Choisissez une Pièce d’Or ou un objet du sac.')
    if not choices:
        choice = None
    elif choice == POCKET_GOLD:
        adventure.pay(character, BOOK, gold=1)
    else:
        adventure.pay(character, BOOK, items=[choice])
    state(character)['pocket'] = choice
    return choice


def use_poultice(character, die):
    """Emplâtre du §167 : un dé d’Endurance (plafonnée), puis l’emplâtre est utilisé."""
    ensure_alive(character)
    if not has_item(character, 'emplatre'):
        raise ValueError('Aucun emplâtre dans le sac.')
    dice(die, 1, 6)
    character['inventory'].remove(matching_items(character, 'emplatre')[0])
    _change(character, 'endurance', die)
    return die


def _end(character, number, death):
    state(character)['ending'] = number
    if death:
        character['endurance'] = 0
    character.setdefault('book_facts', {})['adventure_ended'] = True


def finish_ending(character, number):
    """Fin imprimée (mort ou échec) : l’aventure se termine sans blessure inventée."""
    if number not in ENDINGS or peek(character).get('ending'):
        return False
    _end(character, number, number in DEATHS)
    return True


# ----- Phase 3.3 : §201 à 300 ---------------------------------------------------
def choose_mixture(character, target):
    """§201 : deux ingrédients broyés ensemble ; le §244 n’offre ensuite que ce mélange."""
    ensure_alive(character)
    if peek(character).get('mixture') is not None:
        raise ValueError('Le mélange est déjà préparé.')
    names = {t: name for name, t in MIXTURES}
    if target not in names:
        raise ValueError('Mélange inconnu.')
    state(character)['mixture'] = target
    character.setdefault('inventory', []).append(f'Mélange en bourse de cuir ({names[target].lower()})')
    return names[target]


def mixture_ready(character):
    return peek(character).get('mixture') is not None


def roll_creature(character, die):
    """§201 : le dé désigne la créature ; elle est retenue pour le §138."""
    ensure_alive(character)
    if peek(character).get('creature') is not None:
        raise ValueError('La créature est déjà désignée.')
    dice(die, 1, 6)
    state(character)['creature'] = die
    return CREATURES[die]


def creature_rolled(character):
    return peek(character).get('creature') is not None


def gamble_rounds(character):
    return peek(character).get('gamble', [])


def can_gamble(character):
    """None si une partie est possible, sinon la raison affichée."""
    if len(gamble_rounds(character)) >= GAMBLE_ROUNDS:
        return 'Les Nains se sont lassés : quatre parties au plus.'
    if character.get('gold', 0) < GAMBLE_STAKE:
        return f'Il faut miser {GAMBLE_STAKE} Pièces d’Or.'
    return None


def gamble(character, dwarves, own):
    """§206 : battre chacun des trois Nains gagne 6 ; être battu par l’un d’eux perd 2.

    Une égalité avec le meilleur Nain n’est ni gagnée ni perdue : la mise est reprise."""
    ensure_alive(character)
    reason = can_gamble(character)
    if reason:
        raise ValueError(reason)
    dwarves = list(dwarves)
    if len(dwarves) != GAMBLE_DWARVES:
        raise ValueError('Trois jets de Nains sont nécessaires.')
    for total in dwarves + [own]:
        dice(total)
    if own > max(dwarves):
        result, change = 'gagnée', GAMBLE_WIN
    elif own < max(dwarves):
        result, change = 'perdue', -GAMBLE_STAKE
    else:
        result, change = 'égalité', 0
    character['gold'] = character.get('gold', 0) + change
    state(character).setdefault('gamble', []).append({'dwarves': dwarves, 'own': own, 'result': result})
    return result, change


def brawl_resolved(character):
    return 'brawl' in peek(character)


def brawl_required(character):
    return min(BRAWL_ITEMS, len(theft_choices(character)))


def brawl_loss(character, items):
    """§266 : deux objets du sac à dos perdus, choisis par le joueur."""
    ensure_alive(character)
    if brawl_resolved(character):
        raise ValueError('La perte est déjà constatée.')
    items = list(items)
    choices = list(theft_choices(character))
    if len(items) != brawl_required(character):
        raise ValueError(f'Choisissez {brawl_required(character)} objet(s) du sac à dos.')
    for name in items:
        if name not in choices:
            raise ValueError('Objet absent du sac à dos ou déjà choisi.')
        choices.remove(name)
    adventure.pay(character, BOOK, items=items)
    state(character)['brawl'] = items
    return items


def hot_meal_eaten(character):
    return bool(peek(character).get('hot_meal'))


def hot_meal(character):
    """§287 : 1 Pièce d’Or pour 2 points d’Endurance, plafonnés au total initial."""
    ensure_alive(character)
    if hot_meal_eaten(character):
        raise ValueError('Le repas chaud est déjà pris.')
    if character.get('gold', 0) < HOT_MEAL_PRICE:
        raise ValueError('Pas assez de Pièces d’Or.')
    adventure.pay(character, BOOK, gold=HOT_MEAL_PRICE)
    _change(character, 'endurance', HOT_MEAL_GAIN)
    state(character)['hot_meal'] = True


def _word(name, keywords):
    folded = _fold(name)
    return any(re.search(r'\b' + re.escape(key) + r'\b', folded) for key in keywords)


def trade_choices(character):
    """§293 : un objet magique (comme au §187), une pièce d’armure, ou deux Provisions."""
    locked = set(character.get('locked_items', []))
    choices = [TRADE_PROVISIONS_LABEL] if character.get('provisions', 0) >= TRADE_PROVISIONS else []
    choices += [name for name in character.get('inventory', [])
                if name not in locked and (_word(name, ARMOUR_KEYWORDS)
                                           or any(_fold(k) in _fold(name) for k in MAGIC_KEYWORDS))]
    if character.get('potion') and character.get('potion_doses', 0) > 0:
        choices.append(f"{character['potion']} ({STARTING_POTION})")
    return choices


def traded(character):
    return 'trade' in peek(character)


def trade_flower(character, choice):
    """§293 : la fleur dorée contre l’objet ou les Provisions choisis, une seule fois."""
    ensure_alive(character)
    if traded(character):
        raise ValueError('L’échange est déjà conclu.')
    if choice not in trade_choices(character):
        raise ValueError('Mme Pipe n’accepte pas cet échange.')
    if choice == TRADE_PROVISIONS_LABEL:
        character['provisions'] -= TRADE_PROVISIONS
    elif choice.endswith(f'({STARTING_POTION})'):
        character['potion_doses'] = 0
    else:
        adventure.pay(character, BOOK, items=[choice])
    character.setdefault('inventory', []).append(GOLDEN_FLOWER)
    state(character)['trade'] = choice
    return choice


# ----- Phase 3.4 : §301 à 400 ---------------------------------------------------
# §354 : le prêteur sur gages rachète ces seules familles, au prix imprimé.
# (libellé du livre, mots-clés acceptés, mots-clés exclus, prix)
PAWNBROKER = 354
PAWN_PRICES = (
    ('Gobelet d’argent', ('gobelet',), (), 8),
    ('Passe-partout', ('passe-partout',), (), 15),
    ('Broche scorpion', ('broche scorpion',), (), 10),
    ('Anneau magique', ('anneau',), (), 12),
    ('Bracelet d’argent', ('bracelet',), (), 5),
    ('Casque', ('casque',), (), 7),
    ('Flûte d’argent', ('flute',), (), 5),
    ('Bandeau pour l’œil', ('bandeau',), (), 1),
    ('Osselets', ('osselets',), (), 1),
    ('Miroir', ('miroir',), (), 1),
)


def pawn_price(name):
    """Prix offert pour un objet du sac, ou None s’il n’intéresse pas le prêteur."""
    folded = _fold(name)
    for _label, accepted, excluded, price in PAWN_PRICES:
        if any(_fold(k) in folded for k in accepted) and not any(_fold(k) in folded for k in excluded):
            return price
    return None


def pawn_choices(character):
    """Objets vendables (hors objets verrouillés), avec leur prix : [(nom, prix)]."""
    locked = set(character.get('locked_items', []))
    return [(name, pawn_price(name)) for name in character.get('inventory', [])
            if name not in locked and pawn_price(name) is not None]


def pawn_sell(character, items):
    """Vendre au §354 autant d’objets que voulu ; renvoie l’or reçu."""
    ensure_alive(character)
    items = list(items)
    choices = [name for name, _price in pawn_choices(character)]
    if not items:
        raise ValueError('Choisissez au moins un objet à vendre.')
    for name in items:
        if name not in choices:
            raise ValueError('Objet absent du sac ou que le prêteur ne rachète pas.')
        choices.remove(name)
    gold = sum(pawn_price(name) for name in items)
    adventure.pay(character, BOOK, items=items)
    character['gold'] = character.get('gold', 0) + gold
    state(character).setdefault('pawned', []).extend(items)
    return gold


# §378 : le boulet de canon. Chacun lance un dé à tour de rôle (vous d’abord)
# jusqu’au premier 1 ; celui qui l’obtient lâche le boulet et paie 5 Pièces d’Or.
CANNONBALL, CANNON_STAKE, CANNON_LIMIT = 378, 5, 200


def cannon_resolved(character):
    return 'cannon' in peek(character)


def cannonball(character, rolls):
    """Résoudre la partie à partir des dés alternés ; renvoie (perdu ?, variation d’or)."""
    ensure_alive(character)
    if cannon_resolved(character):
        raise ValueError('La partie de boulet est déjà jouée.')
    rolls = list(rolls)
    if not rolls or len(rolls) > CANNON_LIMIT:
        raise ValueError('Suite de dés invalide.')
    for die in rolls:
        dice(die, 1, 6)
    if rolls[-1] != 1 or 1 in rolls[:-1]:
        raise ValueError('La partie s’arrête au premier 1.')
    lost = len(rolls) % 2 == 1
    if lost:
        change = -min(CANNON_STAKE, character.get('gold', 0))
        adventure.pay(character, BOOK, gold=-change)
    else:
        change = CANNON_STAKE
        character['gold'] = character.get('gold', 0) + change
    state(character)['cannon'] = {'rolls': rolls, 'lost': lost, 'change': change}
    return lost, change
