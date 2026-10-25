"""Services d’aventure communs aux livres Défis Fantastiques, sans Qt ni texte de livre.

Ces règles viennent de la Forêt de l’Ombre et servent de socle aux grimoires
suivants. Chaque livre range son état sauvegardé sous sa propre clé de
``character['book_state']`` (``'foret'``, ``'cite'``…) : la clé est toujours passée
explicitement, pour que deux livres ne partagent jamais leurs marqueurs.

Comme dans ``rules`` : l’appelant fournit les dés déjà tirés et les tables relues
du livre (coûts, renvois, objets maudits) ; rien ici ne connaît un paragraphe.
Les messages d’erreur sont ceux affichés par la Forêt : ne pas les reformuler
sans mettre à jour ses tests.
"""
from collections import Counter
from copy import deepcopy

from .rules import spend_luck


def dice(total, low=2, high=12):
    """Valider aussi le type : bool n’est pas un résultat de dé."""
    if type(total) is not int or not low <= total <= high:
        raise ValueError(f'Jet attendu entre {low} et {high}.')
    return total


def book_state(character, book):
    """Accéder à l’état mutable sauvegardé du livre ; les lectures utilisent peek_state()."""
    return character.setdefault('book_state', {}).setdefault(book, {})


def peek_state(character, book):
    """Lire sans créer de marqueurs pendant un affichage ou un test d'autorisation."""
    return character.get('book_state', {}).get(book, {})


def ensure_alive(character):
    """Refuser les actions après une perte létale, y compris par appel direct."""
    if character['endurance'] <= 0 or character.get('book_facts', {}).get('adventure_ended'):
        raise ValueError('L’aventure est terminée.')


def damage_hero(character, book, amount, encounter=None):
    """Appliquer une perte et mémoriser une blessure effective même après des soins."""
    if type(amount) is not int or amount < 0:
        raise ValueError('Blessure invalide.')
    before = character['endurance']
    character['endurance'] = max(0, before - amount)
    if encounter is not None and before > character['endurance']:
        wounds = book_state(character, book).setdefault('wounds', {})
        wounds[encounter] = wounds.get(encounter, 0) + 1
    return before - character['endurance']


def grant_reward(character, book, identity, *, gold=0, items=(), luck=0):
    """Accorder une source physique une seule fois, malgré ses variantes de renvoi.

    identity est commun aux variantes du coffre/de la récompense ; ce n’est pas
    le numéro du passage. Ne jamais l’utiliser pour une épreuve répétable.
    La Chance gagnée reste plafonnée à sa valeur initiale.
    """
    ensure_alive(character)
    if not isinstance(identity, str) or not identity or type(gold) is not int or gold < 0:
        raise ValueError('Source de récompense invalide.')
    items = list(items)
    if not all(isinstance(name, str) and name for name in items) or type(luck) is not int:
        raise ValueError('Récompense invalide.')
    if identity in peek_state(character, book).get('rewards', []):
        return False
    character['gold'] = character.get('gold', 0) + gold
    character.setdefault('inventory', []).extend(items)
    cap = character.get('initial', {}).get('chance', character['chance'])
    if luck:
        character['chance'] = min(cap, max(0, character['chance'] + luck))
    book_state(character, book).setdefault('rewards', []).append(identity)
    return True


LOCKED_MESSAGE = 'Un objet verrouillé ne peut pas être retiré.'


def validate_payment(character, gold, items, *, cursed=(), usable=None, units=None,
                     locked_message=LOCKED_MESSAGE):
    """Compter les exemplaires, pas seulement les noms, avant toute dépense.

    cursed : objets du livre qui ne quittent jamais le sac (en plus de
    ``locked_items``). usable : si fourni, nombre d’exemplaires encore utilisables
    d’un nom ; le paiement exige alors des objets achetés et utilisables.
    units : nombre exact de pièces + objets exigé par un tribut.
    """
    ensure_alive(character)
    if type(gold) is not int or gold < 0 or gold > character.get('gold', 0):
        raise ValueError('Paiement en or impossible.')
    selected = Counter(items)
    inventory = Counter(character.get('inventory', []))
    if any(not isinstance(name, str) or count > inventory[name] for name, count in selected.items()):
        raise ValueError('Objet de paiement absent ou sélectionné trop souvent.')
    if (any(selected.get(name) for name in cursed)
            or any(selected.get(name) for name in character.get('locked_items', []))):
        raise ValueError(locked_message)
    if usable is not None and any(count > usable(name) for name, count in selected.items()):
        raise ValueError('Le paiement exige des objets achetés et encore utilisables.')
    if units is not None and gold + sum(selected.values()) != units:
        raise ValueError(f'Le tribut exige exactement {units} unités (une pièce ou un objet).')
    return selected


def pay(character, book, *, gold=0, items=(), cursed=(), usable=None, units=None,
        locked_message=LOCKED_MESSAGE):
    """Payer un choix déjà validé sans convertir la valeur des trésors en monnaie.

    Un objet donné emporte sa charge éventuelle et cesse d’être porté.
    """
    selected = validate_payment(character, gold, items, cursed=cursed, usable=usable, units=units,
                                locked_message=locked_message)
    character['gold'] -= gold
    for name, count in selected.items():
        for _ in range(count):
            character['inventory'].remove(name)
        data = book_state(character, book)
        if name in data.get('charges', {}):
            # Vendre/donner une acquisition emporte aussi sa charge éventuelle.
            data['charges'][name] = max(0, data['charges'][name] - count)
        if name in data.get('worn', []):
            data['worn'].remove(name)
    return selected


def route_paid(character, book, paragraph, target):
    """Vrai si le coût de ce renvoi a déjà été payé (lecture seule)."""
    return f'{paragraph}:{target}' in peek_state(character, book).get('paid_routes', [])


def pay_route(character, book, paragraph, target, cost, *, pay_gold):
    """Payer au choix de la route, jamais lors de son affichage ou de sa restauration.

    cost vaut None (route gratuite) ou (ressource, montant) ; l’or passe par
    pay_gold(montant) pour garder les règles de paiement du livre.
    """
    ensure_alive(character)
    if cost is None or route_paid(character, book, paragraph, target):
        return False
    resource, amount = cost
    if resource == 'gold':
        pay_gold(amount)
    else:
        character[resource] = max(0, character[resource] - amount)
    book_state(character, book).setdefault('paid_routes', []).append(f'{paragraph}:{target}')
    return True


def stat_test(character, stat, total, skill):
    """Tentez votre Chance (dépense un point) ou épreuve d’Habileté contre skill."""
    return spend_luck(character, total) if stat == 'chance' else total <= skill


def branch_test(character, book, test, total, skill):
    """Résoudre une épreuve relue (stat, réussite, échec, blessure d’échec).

    Renvoyer le paragraphe atteint, ou None si la blessure d’échec est mortelle.
    Les blessures du renvoi lui-même ne sont pas anticipées.
    """
    stat, success, failure, damage = test
    if stat_test(character, stat, total, skill):
        return success
    damage_hero(character, book, damage)
    return failure if character['endurance'] > 0 else None


def new_group_combat(groups):
    """Créer un état JSON indépendant des profils, sans réinitialiser une sauvegarde."""
    if not groups or any(not group for group in groups):
        raise ValueError('Une rencontre doit comporter des groupes non vides.')
    for group in groups:
        for enemy in group:
            if (not enemy.get('name') or type(enemy.get('skill')) is not int or enemy['skill'] < 0
                    or type(enemy.get('stamina')) is not int or enemy['stamina'] <= 0):
                raise ValueError('Profil de monstre invalide.')
    return {'groups':deepcopy(groups), 'group':0, 'assaults':0, 'target':0, 'finished':False}


def advance_group(combat):
    """Passer à la paire suivante seulement après la mort de tous les membres."""
    if combat['finished']:
        return False
    if any(enemy['stamina'] > 0 for enemy in combat['groups'][combat['group']]):
        return False
    if combat['group'] + 1 == len(combat['groups']):
        combat['finished'] = True
    else:
        combat['group'] += 1
        combat['target'] = 0
    return True
