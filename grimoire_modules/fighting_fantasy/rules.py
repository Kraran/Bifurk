"""Calculs communs de Défis Fantastiques, indépendants de Qt et des livres.

L'appelant fournit les dés déjà tirés : ces fonctions ne consomment aucun hasard.
Les mutations portent uniquement sur le personnage reçu. Les autorisations de
repas, de fuite et les effets d'objets particuliers restent définis par l'aventure.
"""
from dataclasses import dataclass

# Les libellés restent ceux du format de sauvegarde existant.
POTION_STATS = {"Potion d'Adresse": 'habilete', 'Potion de Vigueur': 'endurance',
                'Potion de Bonne Fortune': 'chance'}
POTION_DOSES = 2
MEAL_RESTORE = 4


def _dice_total(value, low, high):
    """Refuser un jet impossible avant de dépenser une ressource."""
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Total de dés attendu entre {low} et {high}.')
    return value


def adventurer_stats(skill_die, endurance_total, luck_die):
    """H=1d6+6, E=2d6+12, C=1d6+6 ; aucune dépendance à l'équipement de départ."""
    return {'habilete': _dice_total(skill_die, 1, 6) + 6,
            'endurance': _dice_total(endurance_total, 2, 12) + 12,
            'chance': _dice_total(luck_die, 1, 6) + 6}


def spend_luck(character, total):
    """Comparer au score AVANT de dépenser un point, sans descendre sous zéro."""
    _dice_total(total, 2, 12)
    lucky = total <= character['chance']
    character['chance'] = max(0, character['chance'] - 1)
    return lucky


def combat_damage(base_damage=2, *, attacking, lucky=None):
    """Blessure normale 2 ; Chance : infliger 4/1 ou recevoir 1/3.

    None indique qu'aucun test de Chance n'a été choisi. Le dommage de base est
    paramétrable pour les exceptions ; décider de ces exceptions n'est pas ici.
    """
    if type(base_damage) is not int or base_damage < 0:
        raise ValueError('Les dégâts de base doivent être un entier positif ou nul.')
    if lucky is None:
        return base_damage
    delta = (2 if lucky else -1) if attacking else (-1 if lucky else 1)
    return max(0, base_damage + delta)


def flee_available(combat, assaults, enemy_endurance, hero_endurance):
    """N'autoriser une fuite que si le passage la prévoit et son délai est écoulé."""
    return bool(combat and 'escape_target' in combat
                and assaults >= combat.get('escape_after_assaults', 0)
                and enemy_endurance > 0 and hero_endurance > 0)


def escape_damage(chance, dice_total=None):
    """Renvoyer blessure et coût en Chance : 2/0 sans test, 1/1 ou 3/1 avec test.

    Ce calcul ne dépense rien ; l'appelant applique les deux coûts ensemble après
    validation de la destination. Garder cette interface pour les outils existants.
    """
    if dice_total is None:
        return 2, 0
    _dice_total(dice_total, 2, 12)
    return (1 if dice_total <= chance else 3), 1


@dataclass(frozen=True)
class Restoration:
    """Résultat d'un soin, exploitable par l'interface sans recalculer ses effets."""
    stat: str
    before: int
    after: int
    remaining: int


def potion_useful(character):
    """La Bonne Fortune reste utile au maximum : elle augmente aussi le plafond."""
    key = POTION_STATS.get(character.get('potion'))
    return bool(key and character.get('potion_doses', 0) > 0
                and character['endurance'] > 0
                and (key == 'chance' or character[key] < character.get('initial', {}).get(key, character[key])))


def drink_potion(character):
    """Consommer UNE des deux doses ; refuser une fiole vide, inconnue ou inutile.

    La création et les autorisations d'interface sont contrôlées par l'appelant.
    Les plafonds H/E restent inchangés ; chaque dose de Bonne Fortune augmente
    le plafond de Chance de un, puis restaure la Chance à ce nouveau plafond.
    """
    if not potion_useful(character):
        return None
    key = POTION_STATS[character['potion']]
    before = character[key]
    target = character.get('initial', {}).get(key, before)
    if key == 'chance':
        target += 1
        character.setdefault('initial', {})[key] = target
    character[key] = target
    character['potion_doses'] -= 1
    return Restoration(key, before, target, character['potion_doses'])


def eat_meal(character, restore=MEAL_RESTORE):
    """Consommer une provision et restaurer l'Endurance sous son plafond initial.

    L'aventure doit avoir autorisé le repas avant cet appel. Aucun objet spécial,
    lieu particulier ou numéro de paragraphe n'intervient dans ce calcul.
    """
    if character.get('provisions', 0) <= 0 or character['endurance'] <= 0:
        return None
    before = character['endurance']
    cap = character.get('initial', {}).get('endurance', before)
    character['endurance'] = min(cap, before + restore)
    character['provisions'] -= 1
    return Restoration('endurance', before, character['endurance'], character['provisions'])
