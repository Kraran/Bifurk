"""Libellés et infobulles des boutons d’événement de la Forêt.

Tout est déduit des données de rules.py (ENTRY_RULES, BRANCH_TESTS, EQUIPMENT)
ou des services qui résolvent les commandes : aucun effet n’est ajouté ici.
Quand un montant dépend d’un dé, le libellé le dit (« 1d6 ») au lieu de l’inventer.
"""
import re
from collections import Counter
from . import rules

MINUS = '−'


def signed(value):
    return f'+{value}' if value >= 0 else f'{MINUS}{-value}'


def clean(name):
    """Retirer la « (valeur n Or) » des libellés ; l’infobulle garde le nom complet."""
    return re.sub(r'\s*\(valeur [^)]*\)', '', name)


def _items(names, *, full=False):
    counts = Counter(names)
    return ', '.join((name if full else clean(name)) + (f' ×{count}' if count > 1 else '')
                     for name, count in counts.items())


def entry_effects(rule, character):
    """Énumérer les effets codés d’une règle d’arrivée, dans l’ordre de resolve_entry."""
    effects = []
    if rule.get('remove'):
        effects.append('Retiré du sac : ' + _items(rule['remove'], full=True))
    if rule.get('use'):
        effects.append(rule['use'] + (' employé : sa magie s’épuise' if rule['use'] in rules.DURABLE
                                      else ' : une charge dépensée'))
    if rule.get('gold'):
        effects.append(f"{signed(rule['gold'])} pièce{'s' if abs(rule['gold']) > 1 else ''} d’or")
    if rule.get('items'):
        effects.append('Obtenu : ' + _items(rule['items'], full=True))
    if rule.get('luck'):
        effects.append(f"Chance {signed(rule['luck'])}")
    if rule.get('wear'):
        effects.append(rule['wear'] + ' porté')
    if rule.get('equip'):
        effects.append(rule['equip'] + ' en main')
    if rule.get('damage'):
        effects.append(f"Endurance {MINUS}{rule['damage']}")
    if rule.get('heal'):
        effects.append(f"Endurance +{rule['heal']} (sans dépasser le total initial)")
    for key in rule.get('empty_resources', ()):
        amount = character.get(key, 0)
        effects.append(('Provisions' if key == 'provisions' else 'Or') + f' {amount} → 0')
    return effects


def entry_button(rule, character):
    """(libellé, infobulle) d’un effet d’arrivée, montant compris quand il est fixe."""
    effects = entry_effects(rule, character)
    tooltip = ('Effets : ' + ' ; '.join(effects) + '.') if effects else ''
    if rule.get('requires'):
        tooltip = ('Nécessite : ' + ', '.join(rule['requires']) + '. ' + tooltip).strip()
    if rule.get('requires_any'):
        tooltip = ('Nécessite l’un de ces objets : ' + ', '.join(rule['requires_any']) + '. ' + tooltip).strip()
    gains = []
    if rule.get('gold'):
        gains.append(f"{rule['gold']} Or")
    if rule.get('items'):
        gains.append(_items(rule['items']))
    if rule.get('luck', 0) > 0:
        gains.append(f"+{rule['luck']} Chance")
    if rule.get('label'):
        label = rule['label']
    elif rule.get('use'):
        label = 'Utiliser ' + rule['use']
        extra = ([f"{MINUS}{rule['damage']} Endurance"] if rule.get('damage') else []) + gains
        if extra:
            label += ' — ' + ', '.join(extra)
    elif rule.get('remove'):
        label = 'Employer ' + ', '.join(rule['remove'])
        if rule.get('damage'):
            label += f" — {MINUS}{rule['damage']} Endurance"
    elif rule.get('empty_resources'):
        parts = []
        for key in rule['empty_resources']:
            amount = character.get(key, 0)
            noun = 'Provisions' if key == 'provisions' else 'pièces d’or'
            parts.append(f'Perdre vos {amount} {noun}' if amount else f'Perdre vos {noun} (aucune)')
        label = ' et '.join(parts)
    elif rule.get('damage') and not gains:
        label = f"Blessure : {MINUS}{rule['damage']} Endurance"
    elif rule.get('luck', 0) < 0 and not gains:
        label = f"Perte de Chance : {MINUS}{-rule['luck']}"
    else:
        label = 'Recueillir : ' + ', '.join(gains) if gains else 'Recueillir la trouvaille'
    return label, tooltip


def branch_button(number, character):
    """Épreuve à deux issues : nommer le score à battre et les renvois codés."""
    stat, success, failure, damage = rules.BRANCH_TESTS[number]
    if stat == 'chance':
        score = character.get('chance', 0)
        label = f'Tenter votre Chance (2d6 ≤ {score})'
        if number == 158:
            label = f'Utiliser le Bandeau et tenter votre Chance (2d6 ≤ {score})'
        tip = (f'Réussite : §{success}. Échec : §{failure}'
               + (f', après une perte de {damage} Endurance' if damage else '')
               + '. Tenter sa Chance coûte 1 point de Chance.')
        if number == 158:
            tip += ' Le Bandeau de Concentration est employé.'
    else:
        score = rules.effective_skill(character)
        label = f'Épreuve d’Habileté (2d6 ≤ {score})'
        tip = (f'Réussite : §{success}. Échec : §{failure}'
               + (f', après une perte de {damage} Endurance' if damage else '') + '.')
    return label, tip


def equipment_tip(name):
    bonus = rules.EQUIPMENT.get(name, 0)
    tip = (f'Habileté {signed(bonus)} tant qu’il est porté.' if bonus
           else 'Aucun bonus d’Habileté codé ; le port est mémorisé pour les passages qui le demandent.')
    if name == 'Anneau de Lenteur':
        tip += ' Une fois passé, il ne peut plus être retiré.'
    return tip


def equipment_label(name, wearing):
    bonus = rules.EQUIPMENT.get(name, 0)
    suffix = f' ({signed(bonus)} Habileté)' if bonus else ''
    return ('Porter ' if wearing else 'Retirer ') + name + suffix


def command_button(number, character):
    """(libellé, infobulle) des commandes de passage ; None si le passage n’en a pas."""
    skill = rules.effective_skill(character) if 'habilete' in character else 0
    luck = character.get('chance', 0)
    provisions = character.get('provisions', 0)
    chance_cost = ' Tenter sa Chance coûte 1 point de Chance.'
    table = {
        242: ('Prendre le lingot en abandonnant un objet (facultatif)…',
              'Le lingot d’or prend la place d’un objet de votre choix.'),
        34: ('Choisir le vœu du génie…',
             'Une caractéristique au choix (Habileté, Endurance ou Chance) revient à son total '
             'initial ; la Lanterne magique est remise. Puis §231.'),
        308: (f'Intervertir Habileté ({character.get("habilete", 0)}) et Chance ({luck})',
              'Seuls les scores actuels sont échangés, pas les totaux initiaux. Puis §148.'),
        98: (f'Échapper à l’embuscade — tenter votre Chance (2d6 ≤ {luck})',
             'Réussite : retour à la tour (§1). Échec : la mort.' + chance_cost),
        259: (f'Affronter la fièvre : {MINUS}3 Endurance, puis Chance (2d6 ≤ {luck})',
              'Perte immédiate de 3 Endurance. Si vous survivez : réussite §244 ; '
              f'échec {MINUS}2 Endurance et §19.' + chance_cost),
        278: (f'Tomber dans la fosse : Chance (2d6 ≤ {luck}), {MINUS}2 ou {MINUS}4 Endurance',
              f'Chance réussie : {MINUS}2 Endurance ; ratée : {MINUS}4 Endurance. Puis §319.' + chance_cost),
        73: (f'Éprouver la porte : 2d6 ≤ {min(skill, luck)}',
             'Un seul jet comparé à l’Habileté et à la Chance (la plus faible des deux), '
             'sans dépenser de Chance. Réussite : §327 ; échec : §112.'),
        309: ('Éviter les deux fléchettes : deux tests de Chance',
              'Deux tests de Chance successifs, chacun coûte 1 point. Les deux réussis : §77 ; '
              'sinon §197.'),
        372: (f'Soulever le coffre : 2d6 ≤ {skill}',
              f'Réussite : §48. Échec : {MINUS}1 Endurance, et vous pouvez réessayer.'),
        266: ('Choisir la mise du bras de fer…',
              f'Mise : 10 pièces d’or ou un objet, perdue seulement en cas d’échec. '
              f'Trois épreuves d’Habileté (2d6 ≤ {skill}) : trois réussites §354, '
              'un échec arrête et mène au §129.'),
        52: ('Choisir la mise — utiliser le Brassard…',
             'Le Brassard de Force dispense des trois jets du bras de fer : il est employé '
             '(sa magie s’épuise) et la mise n’est pas perdue. Puis §78.'),
        304: (f'Attendre la guérison : {MINUS}5 Provisions, {MINUS}2 Habileté',
              f'Il faut 5 Provisions (vous en avez {provisions}) ; sinon, la mort de faim. Puis §69.'),
        328: (f'Prendre le repas sur la chaise : {MINUS}1 Provision, {MINUS}4 Endurance',
              'Le repas ne rend aucune Endurance. Puis §118.'),
        262: ('Boire la potion des deux combats',
              'Recueille d’abord les 4 pièces d’or du passage, puis la potion agit pendant les deux combats suivants. Puis §337.'),
        204: ('Remettre les deux parties du marteau',
              'La tête et le manche du marteau sont remis : quête accomplie (§400).'),
        395: (f'Résister à l’éclair de la lanterne : Chance (2d6 ≤ {luck})',
              f'Réussite : §154. Échec : {MINUS}3 Endurance, puis §370.' + chance_cost),
        154: ('Abandonner la lanterne noircie', 'La Lanterne magique est retirée du sac. Puis §231.'),
        370: ('Choisir l’objet perdu…', 'Un objet du sac, au choix, est perdu (avec sa charge ou son bonus). Puis §231.'),
        192: ('Constater la transformation de l’épée', 'Votre arme en main vous est retirée.'),
        60: (f'Chercher les Filtres à Nez : Chance (2d6 ≤ {luck})',
             'Réussite : §183 ; échec : §44.' + chance_cost),
        182: (f'Dégager l’épée du rocher : 2d6 ≤ {skill}',
              'Réussite : §70 ; échec : §334. Aucune perte en cas d’échec.'),
        358: (f'Se libérer du nœud coulant : Chance (2d6 ≤ {luck})',
              'Réussite : §40. Échec : votre arme tombe, puis §218.' + chance_cost),
        178: (f'Utiliser le sel d’une ration : {MINUS}1 Provision', f'Une Provision est dépensée pour le sel ({MINUS}1, vous en avez {provisions}). Puis §298.'),
        48: (f'Explosion de l’œuf : {MINUS}1d6 Endurance',
             'Un dé, retranché de l’Endurance, sans test de Chance.'),
    }
    return table.get(number)


def gas_button(number):
    if number in (22, 169):
        return (f'Gaz toxique : {MINUS}1d6 Endurance, {MINUS}2 Habileté',
                'Un dé retranché de l’Endurance, et 2 points d’Habileté perdus (boîte d’argent).')
    return (f'Gaz toxique : {MINUS}1d6 Endurance', 'Un dé retranché de l’Endurance.')
