"""Mécaniques de la Forêt, sans Qt, lecture du PDF ni tirage aléatoire.

Les dés sont fournis par l'appelant. L'état propre au livre reste sous book_state,
qui est déjà copié par l'historique et les sauvegardes. Les fonctions publiques
valident leurs paramètres avant mutation ; une erreur d'utilisation n'est jamais
une dépense partielle. Ces services ne déduisent aucune règle du texte narratif.
"""
from collections import Counter
from copy import deepcopy
from ..fighting_fantasy.rules import combat_damage, spend_luck

SHOP = (
    ('Potion de Guérison', 3), ('Potion de Contrôle des Plantes', 2),
    ('Potion de Tranquillité', 3), ('Potion de Contrôle des Insectes', 2),
    ('Potion Antipoison', 2), ('Eau Bénite', 3), ('Anneau de Lumière', 3),
    ('Bottes à Bondir', 2), ('Corde Magique', 3), ('Filet de Capture', 3),
    ('Brassard de Force', 3), ('Gant d’Adresse au Lancer', 2),
    ('Perche à Sonder', 2), ('Gousses d’Ail', 3),
    ('Bandeau de Concentration', 3), ('Capsules de Feu', 3), ('Filtres à Nez', 3),
)
PRICES = dict(SHOP)
ALIASES = {'Bottes de Saut':'Bottes à Bondir', 'Filet d’Enchevêtrement':'Filet de Capture',
           'Filet d\'Enchevêtrement':'Filet de Capture', "Gant d'Adresse au Lancer":'Gant d’Adresse au Lancer',
           "Gousses d'Ail":'Gousses d’Ail'}
EQUIPMENT = {'Casque magique':1, 'Bracelet d’Habileté':1,
             'Gantelet d’Adresse à Combattre':1, 'Anneau de Lenteur':-2,
             'Bouclier d’empereur':0, 'Œil d’Ambre':0}
DURABLE = {'Anneau de Lumière','Bottes à Bondir','Corde Magique','Brassard de Force',
           'Gant d’Adresse au Lancer','Perche à Sonder','Bandeau de Concentration'}
HAMMER_HEAD = 'Tête de marteau en bronze — G'
HAMMER_HANDLE = 'Manche de marteau en ébène — G'
ENCHANTED_SWORD = 'Épée enchantée'
ELVEN_BREAD = 'Pain elfique'
BELL = 'Petite clochette de cuivre'
GAS_PARAGRAPHS = {22,169,222}
# Statistique, réussite, échec, blessure immédiate de l’échec.
BRANCH_TESTS = {57:('chance',132,35,0),81:('chance',49,4,0),
                90:('chance',210,348,3),229:('chance',165,45,0),
                251:('habilete',63,260,4),256:('chance',122,295,0),
                376:('chance',74,310,0)}


def resolve_branch_test(character, paragraph, total):
    """Résoudre une épreuve relue ; ne pas anticiper les blessures du renvoi."""
    alive(character)
    dice(total)
    if paragraph not in BRANCH_TESTS:
        raise ValueError('Épreuve non intégrée.')
    stat, success, failure, damage = BRANCH_TESTS[paragraph]
    passed = spend_luck(character,total) if stat == 'chance' else total <= effective_skill(character)
    if passed:
        return success
    damage_hero(character,damage)
    return failure if character['endurance'] > 0 else None


def gas_resolved(character, paragraph):
    """Partager l’ouverture de la boîte entre ses variantes protégées et toxiques."""
    if paragraph not in GAS_PARAGRAPHS:
        return False
    identity = 'silver_box' if paragraph in (22,169) else 'purple_mushroom'
    return (identity in peek(character).get('hazards', [])
            or paragraph in (22,169) and entry_resolved(character,338))


def inhale_gas(character, paragraph, die):
    """Un dé d’Endurance ; -2 Habileté seulement pour la boîte, butin si survie."""
    alive(character)
    if paragraph not in GAS_PARAGRAPHS:
        raise ValueError('Gaz non intégré pour ce passage.')
    dice(die,1,6)
    if gas_resolved(character,paragraph):
        return False
    if paragraph in (22,169):
        character['habilete'] = max(0,character['habilete']-2)
    damage_hero(character,die)
    identity = 'silver_box' if paragraph in (22,169) else 'purple_mushroom'
    state(character).setdefault('hazards', []).append(identity)
    if paragraph in (22,169) and character['endurance'] > 0:
        reward(character,'entry:silver_box_filters',items=['Boîte d’argent'])
    return True


def find_mushroom_filters(character, total):
    """§60 : chercher un achat utilisable ; la branche suivante consomme la charge."""
    alive(character)
    dice(total)
    if available(character,'Filtres à Nez') <= 0:
        raise ValueError('Aucun Filtre à Nez utilisable à chercher.')
    return 183 if spend_luck(character,total) else 44


def extract_stone_sword(character, total):
    """§182 : épreuve d’Habileté sans dépense de Chance ni blessure d’échec."""
    alive(character)
    dice(total)
    return 70 if total <= effective_skill(character) else 334


def effective_skill(character):
    """Bonus de +2 à l’arme équipée, indépendant du total initial et des soins."""
    active = (character.get('equipped_weapon') == ENCHANTED_SWORD
              and ENCHANTED_SWORD in character.get('inventory', [])
              and 'entry:70' in peek(character).get('rewards', []))
    return character['habilete'] + (2 if active else 0)


def canonical(name):
    """Ramener les variantes nommées dans le livre au même article acheté."""
    return ALIASES.get(name, name)


def state(character):
    """Accéder à l’état mutable sauvegardé ; les lectures utilisent peek()."""
    return character.setdefault('book_state', {}).setdefault('foret', {})


def peek(character):
    """Lire sans créer de marqueurs pendant un affichage ou un test d'autorisation."""
    return character.get('book_state', {}).get('foret', {})


def alive(character):
    """Refuser les actions après une perte létale, y compris par appel direct."""
    if character['endurance'] <= 0:
        raise ValueError('L’aventure est terminée.')


def dice(total, low=2, high=12):
    """Valider aussi le type : bool n’est pas un résultat de dé."""
    if type(total) is not int or not low <= total <= high:
        raise ValueError(f'Jet attendu entre {low} et {high}.')
    return total


def available(character, name):
    """Une charge achetée et son objet doivent exister ; un nom ajouté à la main ne suffit pas."""
    name = canonical(name)
    return min(peek(character).get('charges', {}).get(name, 0),
               character.get('inventory', []).count(name))


def buy(character, name, quantity=1):
    """Payer intégralement un achat avant d’ajouter autant de charges et d’objets."""
    alive(character)
    name = canonical(name)
    if name not in PRICES or type(quantity) is not int or not 1 <= quantity <= 99:
        raise ValueError('Achat inconnu ou quantité invalide.')
    cost = PRICES[name] * quantity
    if character.get('gold', 0) < cost:
        raise ValueError('Pas assez de pièces d’or.')
    character['gold'] -= cost
    character.setdefault('inventory', []).extend([name] * quantity)
    charges = state(character).setdefault('charges', {})
    charges[name] = charges.get(name, 0) + quantity


def consume(character, name):
    """Dépenser une charge ; garder les objets durables en tant que matériel épuisé.

    Un sachet de cinq Capsules de Feu constitue une seule charge. Le nom affiché
    d’un objet épuisé ne peut plus servir d’achat disponible ni renouveler sa magie.
    """
    alive(character)
    name = canonical(name)
    if available(character, name) <= 0:
        raise ValueError('Aucune charge utilisable de cet objet.')
    character['inventory'].remove(name)
    state(character)['charges'][name] -= 1
    if name in DURABLE:
        character['inventory'].append(name + ' (magie épuisée)')


def _validate_payment(character, gold, items, *, magic_only=False, units=None):
    """Compter les exemplaires, pas seulement les noms, avant toute dépense."""
    alive(character)
    if type(gold) is not int or gold < 0 or gold > character.get('gold', 0):
        raise ValueError('Paiement en or impossible.')
    selected = Counter(items)
    inventory = Counter(character.get('inventory', []))
    if any(not isinstance(name, str) or count > inventory[name] for name, count in selected.items()):
        raise ValueError('Objet de paiement absent ou sélectionné trop souvent.')
    if selected.get('Anneau de Lenteur') or any(selected.get(name) for name in character.get('locked_items', [])):
        raise ValueError('Un objet verrouillé ou l’anneau maudit ne peut pas être retiré.')
    if magic_only and any(count > available(character, name) for name, count in selected.items()):
        raise ValueError('Le paiement exige des objets achetés et encore utilisables.')
    if units is not None and gold + sum(selected.values()) != units:
        raise ValueError(f'Le tribut exige exactement {units} unités (une pièce ou un objet).')
    return selected


def pay(character, *, gold=0, items=(), magic_only=False, units=None):
    """Payer un choix déjà validé sans convertir la valeur des trésors en monnaie."""
    selected = _validate_payment(character, gold, items, magic_only=magic_only, units=units)
    character['gold'] -= gold
    for name, count in selected.items():
        for _ in range(count):
            character['inventory'].remove(name)
        data = state(character)
        if name in data.get('charges', {}):
            # Vendre/donner une acquisition emporte aussi sa charge éventuelle.
            data['charges'][name] = max(0, data['charges'][name] - count)
        if name in data.get('worn', []):
            data['worn'].remove(name)


def reward(character, identity, *, gold=0, items=(), luck=0):
    """Accorder une source physique une seule fois, malgré ses variantes de renvoi.

    identity est commun aux variantes du coffre/de la récompense ; ce n’est pas
    le numéro du passage. Ne jamais l’utiliser pour une épreuve répétable.
    """
    alive(character)
    if not isinstance(identity, str) or not identity or type(gold) is not int or gold < 0:
        raise ValueError('Source de récompense invalide.')
    items = list(items)
    if not all(isinstance(name, str) and name for name in items) or type(luck) is not int:
        raise ValueError('Récompense invalide.')
    if identity in peek(character).get('rewards', []):
        return False
    character['gold'] = character.get('gold', 0) + gold
    character.setdefault('inventory', []).extend(items)
    cap = character.get('initial', {}).get('chance', character['chance'])
    if luck:
        character['chance'] = min(cap, max(0, character['chance'] + luck))
    state(character).setdefault('rewards', []).append(identity)
    return True


def wear(character, name, enabled=True):
    """Un bonus existe seulement pendant le port effectif ; l’anneau est irrévocable."""
    alive(character)
    if name not in EQUIPMENT or name not in character.get('inventory', []):
        raise ValueError('Équipement absent ou inconnu.')
    if name == 'Anneau de Lenteur' and not enabled:
        raise ValueError('Impossible de retirer l’anneau maudit.')
    worn = state(character).setdefault('worn', [])
    if enabled and name not in worn:
        worn.append(name)
        if name == 'Anneau de Lenteur' and name not in character.get('locked_items', []):
            character.setdefault('locked_items', []).append(name)
    elif not enabled and name in worn:
        worn.remove(name)


def attack_bonus(character, paragraph=None, encounter=None):
    """Additionner les objets portés sans modifier l’Habileté ni son plafond initial."""
    data = peek(character)
    inventory = character.get('inventory', [])
    bonus = sum(EQUIPMENT.get(name, 0) for name in set(data.get('worn', [])) if name in inventory)
    # La malédiction reste même si un outil manuel efface l’objet de l’inventaire.
    if 'Anneau de Lenteur' in data.get('worn', []) and 'Anneau de Lenteur' not in inventory:
        bonus -= 2
    if encounter is not None and data.get('potion_encounters', {}).get(encounter):
        bonus += 1
    if paragraph in (49,71,165,193):
        bonus -= 3
    if paragraph == 352:
        bonus -= 2
    return bonus


def begin_encounter(character, identity):
    """La potion couvre deux rencontres complètes, groupes et séquences inclus.

    Politique explicite : une rencontre = un obstacle de combat identifié. Une
    pause, un rechargement, un changement de cible ou une nouvelle paire ne
    consomme pas un troisième combat. Une fuite consomme la rencontre engagée.
    """
    alive(character)
    data = state(character)
    ledger = data.setdefault('potion_encounters', {})
    if identity not in ledger:
        remaining = data.get('combat_potion_remaining', 0)
        ledger[identity] = remaining > 0
        if remaining:
            data['combat_potion_remaining'] = remaining - 1
    return ledger[identity]


def drink_combat_potion(character):
    """Boire la fiole trouvée chez la créature, une fois pour cette source."""
    if reward(character, 'combat_potion_drank'):
        state(character)['combat_potion_remaining'] = 2
        return True
    return False


def shield_damage(character, damage, die, *, lucky=None):
    """Bouclier d’empereur : 4–6 réduit une blessure normale de 2 à 1.

    Ordre retenu et documenté : protection sur la blessure normale, puis Chance
    commune sur cette base. Le fouet, les pièges et la fuite n’utilisent pas cette
    protection. L’appelant n’appelle ce service que pour une blessure de combat.
    """
    dice(die, 1, 6)
    worn = peek(character).get('worn', [])
    if ('Bouclier d’empereur' in worn and 'Bouclier d’empereur' in character.get('inventory', [])
            and damage == 2 and die >= 4):
        damage = 1
    return combat_damage(damage, attacking=False, lucky=lucky)


def damage_hero(character, amount, encounter=None):
    """Appliquer une perte et mémoriser une blessure effective même après des soins."""
    if type(amount) is not int or amount < 0:
        raise ValueError('Blessure invalide.')
    before = character['endurance']
    character['endurance'] = max(0, before - amount)
    if encounter is not None and before > character['endurance']:
        wounds = state(character).setdefault('wounds', {})
        wounds[encounter] = wounds.get(encounter, 0) + 1
    return before - character['endurance']


def ghoul_paralysed(character, encounter):
    """Quatre coups blessants, pas quatre points d’Endurance perdus."""
    return peek(character).get('wounds', {}).get(encounter, 0) >= 4


def werewolf_wounded(character, encounter):
    """La morsure ne disparaît pas lorsque l’Endurance a été restaurée."""
    return peek(character).get('wounds', {}).get(encounter, 0) > 0


def whip(character, die, luck_total=None):
    """Le Démon frappe sur 1–2 ; la Chance est facultative et sans jet si le fouet rate."""
    alive(character)
    dice(die, 1, 6)
    if luck_total is not None:
        dice(luck_total)
        if die > 2:
            raise ValueError('Pas d’épreuve de Chance lorsque le fouet manque.')
    amount = 0 if die > 2 else 1
    if amount and luck_total is not None:
        amount = combat_damage(1, attacking=False, lucky=spend_luck(character, luck_total))
    return damage_hero(character, amount)


def combined_door(character, total):
    """§73 : un jet comparé à H ET C, sans coût de Chance."""
    alive(character)
    dice(total)
    return 327 if total <= min(effective_skill(character), character['chance']) else 112


def darts(character, totals):
    """§309 : deux épreuves distinctes, même après l’échec de la première."""
    alive(character)
    totals = list(totals)
    if len(totals) != 2:
        raise ValueError('Deux jets sont nécessaires.')
    for total in totals:
        dice(total)
    results = [spend_luck(character, total) for total in totals]
    return 77 if all(results) else 197


def lift_chest(character, total):
    """§372 : chaque tentative compte ; un échec mortel interdit le prochain essai."""
    alive(character)
    dice(total)
    if total <= effective_skill(character):
        return 48
    damage_hero(character, 1)
    return 372 if character['endurance'] > 0 else None


def arm_wrestling(character, totals, *, gold=0, items=(), bracelet=False):
    """§266 : valider la mise avant les dés ; la retirer seulement en cas de défaite.

    Le fournisseur de jets s’arrête au premier échec ; ce service reçoit exactement
    les jets réellement nécessaires. Le Brassard remplace les trois jets (§52).
    """
    totals, items = list(totals), list(items)
    if not ((gold == 10 and not items) or (gold == 0 and len(items) == 1)):
        raise ValueError('Misez dix pièces ou un objet.')
    _validate_payment(character, gold, items)
    if bracelet:
        if totals or not available(character, 'Brassard de Force'):
            raise ValueError('Le Brassard doit être disponible et dispense des jets.')
        consume(character, 'Brassard de Force')
        return 78
    if not 1 <= len(totals) <= 3:
        raise ValueError('Un à trois jets sont nécessaires.')
    for total in totals:
        dice(total)
    failure = next((index for index, total in enumerate(totals) if total > effective_skill(character)), None)
    if failure is None and len(totals) != 3 or failure is not None and failure != len(totals)-1:
        raise ValueError('Arrêter au premier échec ; sinon fournir trois réussites.')
    if failure is not None:
        pay(character, gold=gold, items=items)
        return 129
    return 354


def convalescence(character):
    """§304 : cinq rations sans soin automatique, sinon mort de faim."""
    alive(character)
    if character.get('provisions', 0) < 5:
        character['endurance'] = 0
        return None
    character['provisions'] -= 5
    character['habilete'] = max(0, character['habilete'] - 2)
    return 69


def cursed_meal(character):
    """§328 : consommer un repas mais perdre quatre points, sans restauration.

    Sans provision, ne pas inventer une prise alimentaire ; cette ambiguïté de
    source est laissée à confirmer et l’opération est refusée sans mutation.
    """
    alive(character)
    if character.get('provisions', 0) < 1:
        raise ValueError('Le passage ne précise pas le cas sans provision.')
    character['provisions'] -= 1
    damage_hero(character, 4)
    return 118 if character['endurance'] > 0 else None


def heal_found_potion(character):
    """La Potion de Force trouvée restaure cinq points, pas une dose de la fiole initiale."""
    alive(character)
    name = 'Potion de Force'
    if name not in character.get('inventory', []):
        raise ValueError('Potion absente.')
    character['inventory'].remove(name)
    character['endurance'] = min(character['initial']['endurance'], character['endurance'] + 5)


def eat_elven_bread(character, *, in_combat=False):
    """Consommer un seul pain utile, hors combat, sans dépenser de provision."""
    alive(character)
    if in_combat:
        raise ValueError('Le pain elfique ne peut pas être mangé en combat.')
    if ELVEN_BREAD not in character.get('inventory', []):
        raise ValueError('Aucun pain elfique dans le sac.')
    maximum = character['initial']['endurance']
    if character['endurance'] >= maximum:
        raise ValueError('L’Endurance est déjà à son maximum.')
    character['inventory'].remove(ELVEN_BREAD)
    character['endurance'] = min(maximum,character['endurance']+4)


def hammer_complete(character):
    """Un manche quelconque, une fausse pièce ou deux têtes ne suffisent pas."""
    inventory = character.get('inventory', [])
    return HAMMER_HEAD in inventory and HAMMER_HANDLE in inventory


def hand_over_hammer(character):
    """Consommer les deux parties authentiques et terminer la quête une seule fois."""
    alive(character)
    if peek(character).get('won'):
        return False
    if not hammer_complete(character):
        raise ValueError('Les deux parties marquées G sont nécessaires.')
    character['inventory'].remove(HAMMER_HEAD)
    character['inventory'].remove(HAMMER_HANDLE)
    state(character)['won'] = True
    character.setdefault('book_facts', {})['adventure_won'] = True
    return True


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

# Les variantes partagent un identifiant physique. La table ne contient que des
# effets relus : aucun motif de texte ne peut créer une récompense ou une charge.
ENTRY_RULES = {
    257:{'items':[ELVEN_BREAD], 'luck':1},
    184:{'remove':[BELL], 'heal':4, 'label':'Rendre la clochette et boire la potion du moine'},
    4:{'damage':4},35:{'damage':4},45:{'damage':2},30:{'damage':2},
    70:{'items':[ENCHANTED_SWORD], 'equip':ENCHANTED_SWORD},
    46:{'luck':-2},
    21:{'use':'Potion Antipoison'}, 24:{'use':'Potion Antipoison'},
    39:{'use':'Filet de Capture'},
    44:{'identity':'mushroom_filters','use':'Filtres à Nez','damage':2},
    183:{'identity':'mushroom_filters','use':'Filtres à Nez'},
    55:{'use':'Gant d’Adresse au Lancer'},
    58:{'identity':'ghoul_loot','use':'Eau Bénite','gold':25,'items':[HAMMER_HEAD]},
    312:{'identity':'ghoul_loot','gold':25,'items':[HAMMER_HEAD]},
    64:{'use':'Potion de Contrôle des Plantes'}, 94:{'use':'Corde Magique'},
    100:{'use':'Potion de Contrôle des Insectes'},
    158:{'use':'Bandeau de Concentration'},
    211:{'use':'Potion Antipoison'}, 214:{'use':'Potion de Guérison'},
    228:{'use':'Bottes à Bondir'}, 235:{'use':'Potion de Tranquillité','luck':1},
    268:{'use':'Gousses d’Ail'},
    322:{'use':'Anneau de Lumière','items':['Médaillon d’or (valeur 5 Or)']},
    338:{'identity':'silver_box_filters','use':'Filtres à Nez','items':['Boîte d’argent']},
    365:{'identity':'silver_box_filters','use':'Filtres à Nez','items':['Boîte d’argent']},
    350:{'use':'Capsules de Feu'},
    179:{'items':['Casque magique'],'wear':'Casque magique'},
    302:{'items':['Bracelet d’Habileté'],'wear':'Bracelet d’Habileté'},
    374:{'items':['Gantelet d’Adresse à Combattre'],'wear':'Gantelet d’Adresse à Combattre'},
    133:{'items':['Anneau de Lenteur'],'wear':'Anneau de Lenteur'},
    248:{'items':['Bouclier d’empereur'],'wear':'Bouclier d’empereur','luck':1},
    74:{'identity':'troll_bag','gold':5,'items':['Petite clochette de cuivre']},
    101:{'identity':'troll_bag','gold':5,'items':['Petite clochette de cuivre']},
    287:{'identity':'troll_bag','gold':5,'items':['Petite clochette de cuivre']},
    176:{'identity':'hammer_handle','items':[HAMMER_HANDLE]},
    232:{'identity':'hammer_handle','items':[HAMMER_HANDLE],'luck':1},
    217:{'identity':'cave_four_gold','gold':4},
    262:{'identity':'cave_four_gold','gold':4},
    356:{'items':['Lanterne magique'],'optional':True},
    389:{'gold':8,'luck':1},
    205:{'gold':6},
    78:{'identity':'quin_powder','items':['Poudre de Lévitation']},
    354:{'identity':'quin_powder','items':['Poudre de Lévitation']},
    91:{'items':['Œil d’Ambre'],'wear':'Œil d’Ambre','luck':1},
    194:{'items':['Belladone']},
    83:{'remove':['Belladone'],'damage':2},
    173:{'remove':['Poudre de Lévitation']},
    111:{'identity':'arragon_truth','gold':5},
    223:{'identity':'arragon_truth','gold':5},
    341:{'gold':5,'luck':1,'items':['Dent de dragon','Potion de Force']},
}


def entry_resolved(character, paragraph):
    """Lire le marqueur commun à toutes les variantes d’un effet physique."""
    rule = ENTRY_RULES.get(paragraph)
    return bool(rule and 'entry:' + str(rule.get('identity', paragraph)) in peek(character).get('rewards', []))


def resolve_entry(character, paragraph):
    """Appliquer atomiquement un usage/butin identifié ; refuser les objets inexistants.

    La copie de travail garantit qu’un paiement/usage impossible n’applique pas
    un bonus partiel. Les mécanismes non encore catalogués ne passent jamais ici.
    """
    alive(character)
    if paragraph not in ENTRY_RULES:
        raise ValueError('Ce passage ne dispose pas d’un effet intégré.')
    if entry_resolved(character, paragraph):
        return False
    rule = ENTRY_RULES[paragraph]
    working = deepcopy(character)
    for name in rule.get('remove', []):
        if name not in working.get('inventory', []):
            raise ValueError('Objet nécessaire absent : ' + name)
        working['inventory'].remove(name)
    if rule.get('use'):
        consume(working, rule['use'])
    reward(working, 'entry:' + str(rule.get('identity', paragraph)),
           gold=rule.get('gold',0), items=rule.get('items',()), luck=rule.get('luck',0))
    if rule.get('wear'):
        wear(working, rule['wear'])
    if rule.get('equip'):
        working['equipped_weapon'] = rule['equip']
    damage_hero(working, rule.get('damage',0))
    if rule.get('heal'):
        working['endurance'] = min(working['initial']['endurance'],working['endurance']+rule['heal'])
    character.clear()
    character.update(working)
    return True

PAYMENT_PARAGRAPHS = {12,14,32,36,218,279,297}


def pay_paragraph(character, paragraph, *, gold=0, items=()):
    """Valider le tarif du passage, puis enregistrer le règlement une seule fois."""
    alive(character)
    items = list(items)
    identity = 'payment:' + str(paragraph)
    if paragraph not in PAYMENT_PARAGRAPHS:
        raise ValueError('Tarif non intégré.')
    if identity in peek(character).get('payments', []):
        return False
    magic_only = False
    units = None
    if paragraph == 12:
        valid = (gold == 10 and not items) or (gold == 0 and len(items) == 2)
    elif paragraph == 32:
        valid = gold == 10 and len(items) == 2
    elif paragraph == 36:
        valid = (gold == character.get('gold',0) and not items) or (gold == 0 and len(items) == 2)
        magic_only = bool(items)
    elif paragraph == 279:
        valid = gold + len(items) == 5
        units = 5
    else:
        price = 3 if paragraph == 14 else 5
        valid = (gold == price and not items) or (gold == 0 and len(items) == 1)
        if paragraph in (14,218) and items:
            magical = set(PRICES) | set(EQUIPMENT) | {'Poudre de Lévitation','Œil d’Ambre','Potion de Force'}
            valid = valid and items[0] in magical
        if paragraph == 14 and items and character.get('gold',0) >= 3:
            valid = False
    if not valid:
        raise ValueError('La sélection ne correspond pas au tarif de ce passage.')
    pay(character, gold=gold, items=items, magic_only=magic_only, units=units)
    if paragraph == 12:
        sword = state(character).pop('gnome_sword', None)
        if sword is not None:
            character.setdefault('inventory', []).append(sword)
            character['equipped_weapon'] = sword
    if paragraph == 32:
        character['chance'] = max(0, character['chance'] - 1)
    state(character).setdefault('payments', []).append(identity)
    return True


def transform_gnome_sword(character):
    """§192 : conserver l’identité de l’arme transformée jusqu’au paiement du §12."""
    alive(character)
    if 'gnome_sword' in peek(character) or payment_resolved(character, 12):
        return False
    name = character.get('equipped_weapon') or 'Épée'
    if name not in character.get('inventory', []):
        raise ValueError('Aucune arme équipée à transformer.')
    pay(character, items=[name])
    character['equipped_weapon'] = None
    state(character)['gnome_sword'] = name
    return True


def payment_resolved(character, paragraph):
    return 'payment:' + str(paragraph) in peek(character).get('payments', [])

# Restrictions explicites de possession/charge. Ne pas interpréter le texte libre
# condition_text en code : les conditions non recensées restent de consultation.
ITEM_BRANCHES = {
    3:('Anneau de Lumière',322,120),16:('Potion Antipoison',211,345),
    28:('Brassard de Force',52,266),82:('Potion de Tranquillité',235,13),
    114:('Capsules de Feu',350,123),120:('Corde Magique',94,380),
    126:('Filtres à Nez',365,22),137:('Gant d’Adresse au Lancer',55,10),
    138:('Potion de Contrôle des Plantes',64,159),173:('Eau Bénite',58,227),
    197:('Potion Antipoison',24,53),237:('Potion de Guérison',214,304),
    240:('Filtres à Nez',338,169),319:('Bottes à Bondir',228,14),
    322:('Corde Magique',94,380),325:('Gousses d’Ail',268,79),
    336:('Potion Antipoison',21,108),342:('Bandeau de Concentration',158,11),
    367:('Filtres à Nez',60,222),
}
OPTIONAL_ITEM_ROUTES = {(92,100):'Potion de Contrôle des Insectes', (196,39):'Filet de Capture'}


def route_available(character, paragraph, target):
    """Autoriser les seules conditions intégrées ; ne jamais renouveler une charge épuisée."""
    if paragraph == 191 and target == 184:
        return BELL in character.get('inventory', [])
    if paragraph == 295:
        helmet = ('Casque magique' in peek(character).get('worn', [])
                  and 'Casque magique' in character.get('inventory', []))
        return target == (225 if helmet else 30)
    if paragraph == 356 and target in (34,395):
        return 'Lanterne magique' in character.get('inventory', [])
    if paragraph in ITEM_BRANCHES:
        name, present, absent = ITEM_BRANCHES[paragraph]
        has_item = available(character,name) > 0
        if target == present:
            return has_item
        if target == absent:
            return not has_item
    item = OPTIONAL_ITEM_ROUTES.get((paragraph,target))
    if item:
        return available(character,item) > 0
    if paragraph == 170:
        worn = 'Œil d’Ambre' in peek(character).get('worn', []) and 'Œil d’Ambre' in character.get('inventory', [])
        return target == (223 if worn else 346)
    if paragraph == 155:
        return target == (83 if 'Belladone' in character.get('inventory', []) else 259)
    if paragraph == 132:
        return target == (258 if 'Flûte à Endormir les Dragons' in character.get('inventory', []) else 167)
    return True


def spiked_pit(character, total):
    """§278 : deux ou quatre points perdus, la même sortie si le héros survit."""
    alive(character)
    dice(total)
    lost = 2 if spend_luck(character,total) else 4
    damage_hero(character,lost)
    return 319 if character['endurance'] > 0 else None


def fever_test(character, total):
    """§259 : appeler après la perte initiale de trois points et le contrôle de survie."""
    alive(character)
    dice(total)
    if spend_luck(character,total):
        return 244
    damage_hero(character,2)
    return 19 if character['endurance'] > 0 else None


def return_ambush(character, total):
    """§98 : l’échec tue ; la réussite revient à la tour sans recréer le héros."""
    alive(character)
    dice(total)
    if spend_luck(character,total):
        return 1
    character['endurance'] = 0
    return None


def make_wish(character, stat):
    """§34 : une seule caractéristique revient à son total initial, contre la lampe magique."""
    alive(character)
    if stat not in ('habilete','endurance','chance'):
        raise ValueError('Choisir Habileté, Endurance ou Chance.')
    if 'Lanterne magique' not in character.get('inventory', []):
        raise ValueError('La lanterne magique manque (la lanterne de voyage ne convient pas).')
    character['inventory'].remove('Lanterne magique')
    character[stat] = character['initial'][stat]


def lantern_flash(character, total):
    """§395 : Chance obligatoire, puis trois blessures en cas d’échec seulement."""
    alive(character)
    dice(total)
    if 'Lanterne magique' not in character.get('inventory', []):
        raise ValueError('La lanterne magique manque.')
    if spend_luck(character, total):
        return 154
    damage_hero(character, 3)
    return 370 if character['endurance'] > 0 else None


def discard_lantern(character):
    """§154 : abandonner une lanterne magique, sans toucher à celle de voyage."""
    alive(character)
    if 'Lanterne magique' not in character.get('inventory', []):
        raise ValueError('La lanterne magique manque.')
    pay(character, items=['Lanterne magique'])
    return 231


def lose_backpack_item(character, name):
    """§370 : perdre un exemplaire choisi et sa charge ou son bonus éventuel."""
    alive(character)
    if not isinstance(name, str) or name in character.get('locked_items', []):
        raise ValueError('Choisir un objet du sac qui peut être retiré.')
    pay(character, items=[name])
    return 231


def swap_skill_luck(character):
    """§308 : échanger seulement les scores courants ; les plafonds ne sont pas échangés."""
    alive(character)
    character['habilete'], character['chance'] = character['chance'], character['habilete']
