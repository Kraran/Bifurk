"""Comptes rendus des mécaniques de la Cité : écarts de fiche et jets résolus."""
from collections import Counter

from . import rules

STATS = (('habilete', 'Habileté'), ('endurance', 'Endurance'), ('chance', 'Chance'),
         ('gold', 'Or'), ('provisions', 'Provisions'))


def snapshot(character):
    return {'stats': {key: character.get(key) for key, _ in STATS},
            'inventory': list(character.get('inventory', [])),
            'skill': rules.effective_skill(character) if 'habilete' in character else None}


def _items(counter):
    return ', '.join(name if count == 1 else f'{name} ×{count}' for name, count in counter.items())


def describe_changes(before, after):
    """« Endurance 13 → 10 », puis les objets obtenus ou retirés."""
    parts = [f'{label} {before["stats"][key]} → {after["stats"][key]}' for key, label in STATS
             if None not in (before['stats'].get(key), after['stats'].get(key))
             and before['stats'][key] != after['stats'][key]]
    gained = Counter(after['inventory']) - Counter(before['inventory'])
    lost = Counter(before['inventory']) - Counter(after['inventory'])
    if gained:
        parts.append('Obtenu : ' + _items(gained))
    if lost:
        parts.append('Retiré du sac : ' + _items(lost))
    return parts


def _faces(entry):
    return '+'.join(str(face) for face in entry['rolls']) + (
        f"={entry['total']}" if len(entry['rolls']) > 1 else '')


def describe_rolls(kind, trace, before):
    """« Chance : 7+4=11 > 6, raté » ; la Chance est lue avant sa dépense."""
    lines = []
    for entry in trace:
        if kind in ('chance', 'habilete'):
            score = entry['chance'] if kind == 'chance' else before['skill']
            ok = entry['total'] <= score
            label = 'Chance' if kind == 'chance' else 'Habileté'
            lines.append(f"{label} : {_faces(entry)} {'≤' if ok else '>'} {score}, "
                         + ('réussi' if ok else 'raté'))
        else:
            lines.append(f'Dé : {_faces(entry)}')
    return lines


def summary(before, after, *, kind=None, trace=(), destination=None):
    lines = describe_rolls(kind, list(trace), before)
    changes = describe_changes(before, after)
    if changes:
        lines.append(', '.join(changes))
    if destination is not None:
        lines.append(f'Vous voici au §{destination}')
    return '. '.join(lines) + '.' if lines else ''
