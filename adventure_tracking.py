"""Suivi déclaratif des interventions ; indépendant de l'historique annulable."""
from copy import deepcopy
from datetime import datetime

LABELS = {'tracked': 'Partie suivie', 'assisted': 'Partie assistée',
          'unverified': 'Partie non suivie'}


def new_tracking():
    return {'version': 1, 'status': 'tracked', 'events': []}


def read_tracking(value):
    if value is None:
        return {'version': 1, 'status': 'unverified', 'events': []}
    if (not isinstance(value, dict) or value.get('version') != 1
            or value.get('status') not in LABELS or not isinstance(value.get('events'), list)):
        raise ValueError('Suivi de partie invalide.')
    for event in value['events']:
        if not isinstance(event, dict) or not isinstance(event.get('reason'), str) or not event['reason']:
            raise ValueError('Intervention invalide.')
        if not isinstance(event.get('at'), str):
            raise ValueError('Date d’intervention invalide.')
        datetime.fromisoformat(event['at'])
    if value['status'] == 'assisted' and not value['events']:
        raise ValueError('Partie assistée sans intervention.')
    if value['status'] != 'assisted' and value['events']:
        raise ValueError('Interventions incompatibles avec le statut.')
    return deepcopy(value)


def mark_assisted(tracking, reason):
    tracking['status'] = 'assisted'
    tracking['events'].append({'at': datetime.now().astimezone().isoformat(), 'reason': reason})
