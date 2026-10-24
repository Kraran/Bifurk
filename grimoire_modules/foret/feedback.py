"""Comptes rendus lisibles des mécaniques de la Forêt, sans Qt ni hasard.

Ces fonctions comparent deux relevés de la fiche et décrivent les jets déjà
résolus. Elles n’appliquent aucune règle : le verdict affiché reprend seulement
la comparaison faite par rules.py (total ≤ score, Chance lue avant sa dépense).
"""
from collections import Counter
from . import rules

STATS = (('habilete', 'Habileté'), ('endurance', 'Endurance'), ('chance', 'Chance'),
         ('gold', 'Or'), ('provisions', 'Provisions'), ('potion_doses', 'Doses de potion'))

# Nature du jet de chaque commande : sert uniquement à formuler le verdict.
ROLL_KINDS = {'snare': 'chance', 'find_filters': 'chance', 'fever': 'chance',
              'ambush': 'chance', 'spiked_pit': 'chance', 'lantern_flash': 'chance',
              'darts': 'chance', 'stone_sword': 'habilete', 'lift': 'habilete',
              'wrestle': 'habilete', 'door': 'door', 'egg_explosion': 'd6', 'gas': 'd6'}


def snapshot(character):
    """Relever ce que le joueur voit sur sa fiche, sans référence partagée."""
    return {'stats': {key: character.get(key) for key, _ in STATS},
            'inventory': list(character.get('inventory', [])),
            'worn': list(rules.peek(character).get('worn', [])),
            'weapon': character.get('equipped_weapon'),
            'skill': rules.effective_skill(character) if 'habilete' in character else None}


def _items(counter):
    return ', '.join(name if count == 1 else f'{name} ×{count}'
                     for name, count in counter.items())


def describe_changes(before, after):
    """Lister les écarts visibles : « Endurance 13 → 10 », objets gagnés ou retirés."""
    parts = []
    for key, label in STATS:
        old, new = before['stats'].get(key), after['stats'].get(key)
        if old is not None and new is not None and old != new:
            parts.append(f'{label} {old} → {new}')
    gained = Counter(after['inventory']) - Counter(before['inventory'])
    lost = Counter(before['inventory']) - Counter(after['inventory'])
    if gained:
        parts.append('Obtenu : ' + _items(gained))
    if lost:
        parts.append('Retiré du sac : ' + _items(lost))
    for name in after['worn']:
        if name not in before['worn']:
            parts.append(f'{name} porté')
    for name in before['worn']:
        if name not in after['worn']:
            parts.append(f'{name} retiré')
    if before['weapon'] != after['weapon']:
        parts.append(f"Arme en main : {after['weapon'] or 'aucune'}")
    return parts


def _faces(entry):
    return '+'.join(str(face) for face in entry['rolls']) + (
        f"={entry['total']}" if len(entry['rolls']) > 1 else '')


def describe_rolls(kind, trace, before):
    """Formuler chaque jet : « Chance : 7+4=11 > 6, raté »."""
    if not trace:
        return []
    lines = []
    if kind == 'chance':
        # Plusieurs jets d’une même épreuve (fléchettes) dépensent la Chance
        # l’un après l’autre : le second se compare au score déjà diminué.
        score = trace[0]['chance']
        for entry in trace:
            score = min(score, entry['chance'])
            lucky = entry['total'] <= score
            lines.append(f"Chance : {_faces(entry)} {'≤' if lucky else '>'} {score}, "
                         + ('réussi' if lucky else 'raté'))
            score = max(0, score - 1)
    elif kind == 'habilete':
        skill = before['skill']
        for entry in trace:
            ok = entry['total'] <= skill
            lines.append(f"Habileté : {_faces(entry)} {'≤' if ok else '>'} {skill}, "
                         + ('réussi' if ok else 'raté'))
    elif kind == 'door':
        entry = trace[0]
        score = min(before['skill'], entry['chance'])
        ok = entry['total'] <= score
        lines.append(f"Habileté et Chance : {_faces(entry)} {'≤' if ok else '>'} {score}, "
                     + ('réussi' if ok else 'raté') + ' (sans dépense de Chance)')
    else:
        lines.extend(f"Dé : {_faces(entry)}" for entry in trace)
    return lines


def summary(before, after, *, kind=None, trace=(), destination=None):
    """Assembler le compte rendu ; chaîne vide si rien de visible n’a changé."""
    lines = describe_rolls(kind, list(trace), before)
    changes = describe_changes(before, after)
    if changes:
        lines.append(', '.join(changes))
    if destination is not None:
        lines.append(f'Vous voici au §{destination}')
    return '. '.join(lines) + '.' if lines else ''
