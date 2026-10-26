"""Combats relus des §1 à 400, dans l’ordre du livre.

Un groupe d’un seul ennemi se combat seul ; un groupe de plusieurs ennemis est
un combat simultané (§311, §326) : on choisit sa cible à chaque Assaut, les
autres attaquent et l’on ne fait que parer leurs coups. ``victory`` est le
renvoi après le dernier groupe ; les options décrivent seulement ce que le
passage imprime (fuite, limite d’assauts, malus de Force d’Attaque ``attack``,
combat évité par un objet ``unless_item``, blessure d’un assaut perdu
``wound``, adversaire tiré au dé ``creature_die``, souffle de feu ``fire`` :
un dé par Assaut, une brûlure d’un point sur les faces listées).
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
    130: {'groups': ((_enemy('Premier Garde de la Ville', 6, 6),),
                     (_enemy('Deuxième Garde de la Ville', 7, 5),)), 'victory': 74},
    140: {'groups': ((_enemy('Ogre', 8, 9),),), 'victory': 71,
          'escape': 282, 'escape_after_assaults': 3},
    144: {'groups': ((_enemy('Sorcière', 7, 7),),), 'victory': 303},
    # Force d’Attaque −2 (§152), −3 à mains nues (§157), pendant tout le combat.
    152: {'groups': ((_enemy('Pirate', 7, 5),),), 'victory': 20, 'attack': -2},
    157: {'groups': ((_enemy('Premier Garde de la Ville', 6, 6),),
                     (_enemy('Deuxième Garde de la Ville', 7, 5),)), 'victory': 54, 'attack': -3},
    166: {'groups': ((_enemy('Mille-Pattes Géant', 10, 5),),), 'victory': 272},
    170: {'groups': ((_enemy('Joaillier', 9, 8),),), 'victory': 114, 'escape': 196},
    177: {'groups': ((_enemy('Premier Voleur', 7, 8),), (_enemy('Deuxième Voleur', 8, 6),)),
          'victory': 51},
    191: {'groups': ((_enemy('Bêtes-Feuilles', 6, 6),),), 'victory': 133},
    # Avec un Anneau de Feu, le livre renvoie ailleurs : pas de combat à l’épée.
    193: {'groups': ((_enemy('Momie', 7, 12),),), 'victory': 163,
          'unless_item': ('anneau de feu', 286)},
    # §201 : la créature est désignée par un dé (rules.CREATURES) avant le combat.
    201: {'groups': (), 'victory': 138, 'creature_die': True},
    207: {'groups': ((_enemy('Premier Faucon de la Mort', 4, 5),),
                     (_enemy('Deuxième Faucon de la Mort', 4, 4),)), 'victory': 314},
    # Second Chien de Lune : « 1 1 9 » dans le PDF ; la VO donne Habileté 11, Endurance 9.
    217: {'groups': ((_enemy('Premier Chien de Lune', 9, 10),),
                     (_enemy('Deuxième Chien de Lune', 11, 9),)), 'victory': 259},
    225: {'groups': ((_enemy('Premier Vagabond', 7, 5),), (_enemy('Deuxième Vagabond', 6, 7),),
                     (_enemy('Troisième Vagabond', 5, 6),)), 'victory': 397},
    # Fuite permise à tout moment vers la rue du Port.
    226: {'groups': ((_enemy('Premier Pirate', 6, 6),), (_enemy('Deuxième Pirate', 5, 4),),
                     (_enemy('Troisième Pirate', 7, 4),)), 'victory': 111, 'escape': 78},
    230: {'groups': ((_enemy('Premier Garde de la Ville', 6, 6),),
                     (_enemy('Deuxième Garde de la Ville', 7, 5),)), 'victory': 54},
    249: {'groups': ((_enemy('Reine Serpent', 9, 7),),), 'victory': 295},
    # Une seule créature ; chaque morsure venimeuse coûte 4 points d’Endurance.
    253: {'groups': ((_enemy('Serpents', 5, 5),),), 'victory': 75, 'wound': 4},
    270: {'groups': ((_enemy('Troll', 8, 8),),), 'victory': 26},
    296: {'groups': ((_enemy('Premier Voleur', 7, 7),), (_enemy('Deuxième Voleur', 8, 6),)),
          'victory': 147},
    # ----- Phase 3.4 : §301 à 400 -----
    309: {'groups': ((_enemy('Loup', 5, 5),),), 'victory': 97},
    # Le premier garde seul, puis les deux autres à la fois (cible choisie à chaque Assaut).
    311: {'groups': ((_enemy('Garde de la Ville', 8, 7),),
                     (_enemy('Deuxième Garde de la Ville', 6, 6),
                      _enemy('Troisième Garde de la Ville', 7, 5))), 'victory': 74},
    # La barre incandescente : chaque blessure coûte 3 points d’Endurance.
    323: {'groups': ((_enemy('Forgeron', 9, 9),),), 'victory': 395, 'wound': 3},
    326: {'groups': ((_enemy('Premier Chien Sauvage', 4, 4), _enemy('Deuxième Chien Sauvage', 4, 3)),),
          'victory': 184, 'escape': 180},
    331: {'groups': ((_enemy('Le Dément', 5, 5),),), 'victory': 86},
    349: {'groups': ((_enemy('Lutin de Feu', 9, 4),),), 'victory': 258, 'escape': 192},
    351: {'groups': ((_enemy('Premier Garde de la Ville', 6, 6),),
                     (_enemy('Deuxième Garde de la Ville', 7, 5),)), 'victory': 54},
    356: {'groups': ((_enemy('Premier Rat', 4, 4),), (_enemy('Deuxième Rat', 5, 4),),
                     (_enemy('Troisième Rat', 5, 5),)), 'victory': 28},
    357: {'groups': ((_enemy('Ogre', 8, 9),),), 'victory': 71,
          'escape': 282, 'escape_after_assaults': 3},
    361: {'groups': ((_enemy('Premier Zombi', 6, 6),), (_enemy('Deuxième Zombi', 6, 7),)),
          'victory': 297},
    385: {'groups': ((_enemy('Premier Squelette', 6, 7),), (_enemy('Deuxième Squelette', 8, 6),),
                     (_enemy('Troisième Squelette', 7, 7),)), 'victory': 203},
    386: {'groups': ((_enemy('Pirate', 7, 5),),), 'victory': 20},
    # Souffle de feu : un dé par Assaut, 1 à 3 brûlent (1 point, Chance possible).
    392: {'groups': ((_enemy('Lézardine', 8, 8),),), 'victory': 186, 'escape': 334,
          'fire': (1, 2, 3)},
}


def profile(number, creature=None):
    """Profil JSON indépendant (listes) pour ``new_group_combat``.

    ``creature`` : (nom, habileté, endurance) tiré au dé pour un combat ``creature_die``."""
    data = COMBATS[number]
    if data.get('creature_die'):
        if creature is None:
            raise ValueError('La créature n’est pas encore désignée.')
        return [[_enemy(*creature)]]
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
