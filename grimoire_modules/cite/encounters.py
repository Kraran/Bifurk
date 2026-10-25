"""Combats relus des §1 à 100 : un adversaire à la fois, dans l’ordre du livre.

Chaque groupe ne contient qu’un ennemi : le livre les fait combattre l’un après
l’autre. ``victory`` est le renvoi après le dernier adversaire ; les options
décrivent seulement ce que le passage imprime (fuite, limite d’assauts).
"""


def _enemy(name, skill, stamina):
    return {'name': name, 'skill': skill, 'stamina': stamina}


COMBATS = {
    5: {'groups': ((_enemy('Homme Orque', 8, 5),),), 'victory': 371},
    # Victoire en six assauts au plus (égalités comprises) : §212, sinon §130.
    10: {'groups': ((_enemy('Garde de la Ville', 8, 7),),), 'victory': 212,
         'quick': (6, 130)},
    22: {'groups': ((_enemy('Premier Lutin', 4, 5),), (_enemy('Deuxième Lutin', 5, 5),)),
         'victory': 198},
    23: {'groups': ((_enemy('Orfèvre', 4, 8),),), 'victory': 146},
    57: {'groups': ((_enemy('Chien Loup', 7, 7),), (_enemy('Chien Loup', 7, 5),)),
         'victory': 360},
    72: {'groups': ((_enemy('Lutin', 5, 4),),), 'victory': 208},
    # Fuite seulement une fois Grincheux tué : bouclier jeté, Habileté −1.
    73: {'groups': ((_enemy('Grincheux', 10, 11),), (_enemy('Grosnez', 9, 10),)),
         'victory': 110, 'escape': 239, 'escape_after_group': 1, 'escape_skill': 1},
    79: {'groups': ((_enemy('Reine Serpent', 9, 7),),), 'victory': 295},
    88: {'groups': ((_enemy('Reine Serpent', 9, 7),),), 'victory': 295,
         'escape': 333, 'escape_after_assaults': 3},
    99: {'groups': ((_enemy('Garde', 7, 4),), (_enemy('Garde', 6, 6),)), 'victory': 285},
}


def profile(number):
    """Profil JSON indépendant (listes) pour ``new_group_combat``."""
    data = COMBATS[number]
    return [[dict(enemy) for enemy in group] for group in data['groups']]


def victory_target(number, assaults):
    data = COMBATS[number]
    if 'quick' in data:
        limit, slow = data['quick']
        return data['victory'] if assaults <= limit else slow
    return data['victory']


def escape_status(number, combat):
    """(permis, raison) selon la seule condition imprimée dans le passage."""
    data = COMBATS.get(number, {})
    if 'escape' not in data:
        return False, 'Le livre ne prévoit pas de fuite dans ce combat.'
    after_group = data.get('escape_after_group')
    if after_group is not None and combat['group'] < after_group:
        name = data['groups'][after_group - 1][0]['name']
        return False, f'La fuite n’est possible qu’une fois {name} vaincu.'
    after = data.get('escape_after_assaults')
    if after is not None and combat['assaults'] < after:
        return False, f'La fuite n’est possible qu’après {after} assauts ({combat["assaults"]}/{after}).'
    tip = 'Fuir selon le livre : blessure de fuite de 2 points d’Endurance (Chance possible).'
    if data.get('escape_skill'):
        tip += f' Le bouclier est jeté : Habileté −{data["escape_skill"]}.'
    return True, tip
