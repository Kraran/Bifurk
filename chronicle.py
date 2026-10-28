"""Écran de fin : la chronique d'une partie terminée (victoire, mort ou autre fin).

adventure_summary() ne dépend pas de Qt : il compte, à partir de l'état sauvegardé,
les paragraphes visités, le chemin parcouru, les combats gagnés et l'état final de
l'aventurier. ChronicleDialog présente ce bilan aux couleurs du thème et propose de
recommencer ou de charger une partie ; la fenêtre principale lit `choice` à la fermeture.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from dialog_chrome import DialogHeading

WON = ('vaincu', 'repoussé')
OUTCOMES = {
    'victory': ('Victoire !', 'Votre quête est accomplie : le grimoire se referme sur une légende.'),
    'death': ('Fin de l’aventure', 'Votre Endurance est épuisée, mais la chronique garde la trace '
                                  'de vos exploits.'),
    'ending': ('L’aventure s’achève', 'Le destin en a décidé ainsi : votre chronique s’arrête ici.'),
}
STATS = (('habilete', 'Habileté'), ('endurance', 'Endurance'), ('chance', 'Chance'))
LISTED = 12   # adversaires nommés ; au-delà, « et N autres »


def adventure_summary(character, visited, transitions, encounters, total=400):
    """Bilan chiffré d'une partie ; aucune donnée n'est modifiée."""
    monsters = [monster for paragraph in encounters.values() for monster in paragraph]
    won = [monster['name'] for monster in monsters if monster.get('status') in WON]
    initial = character.get('initial') or {}
    return {
        'visited': len(set(visited)),
        'total': total,
        'steps': len(transitions),
        'won': won,
        'met': len(monsters),
        'fled': sum(monster.get('status') == 'fui' for monster in monsters),
        'stats': [(label, character.get(key, 0), initial.get(key, character.get(key, 0)))
                  for key, label in STATS],
        'gold': character.get('gold', 0),
        'items': len(character.get('inventory', [])),
    }


def plural(count, singular, plural_form=None):
    return f'{count} {singular if count < 2 else (plural_form or singular + "s")}'


def defeated_line(names):
    if not names:
        return 'Aucun adversaire vaincu.'
    shown = ', '.join(names[:LISTED])
    rest = len(names) - LISTED
    return 'Adversaires vaincus : ' + shown + (f' et {plural(rest, "autre")}.' if rest > 0 else '.')


class ChronicleDialog(QDialog):
    """Bilan de fin de partie ; `choice` vaut 'restart', 'load' ou None (fermer)."""

    def __init__(self, outcome, summary, *, hero, book, tracking='', parent=None):
        super().__init__(parent)
        self.choice = None
        self.setObjectName('chronicleDialog')
        self.setWindowTitle('Bifurk — Chronique de l’aventure')
        self.setMinimumWidth(720)
        title, verdict = OUTCOMES[outcome]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHeading(title, f'{book} — la chronique de {hero}' if book
                                       else f'La chronique de {hero}'))
        text = QLabel(verdict)
        text.setObjectName('chronicleVerdict')
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignCenter)
        layout.addWidget(text)

        visited, total = summary['visited'], summary['total']
        share = round(100 * visited / total) if total else 0
        # Deux rangées de quatre : le parcours puis l'état final de l'aventurier.
        tiles = [
            ('Paragraphes visités', str(visited), f'sur {total} ({share} %)'),
            ('Chemin parcouru', str(summary['steps']), 'passages'),
            ('Combats gagnés', str(len(summary['won'])),
             f'sur {plural(summary["met"], "adversaire")}'
             + (f', {summary["fled"]} fui{"s" if summary["fled"] > 1 else ""}' if summary['fled'] else '')),
            ('Bourse', str(summary['gold']), 'pièces d’or'),
        ] + [(label, str(final), f'sur {initial} au départ') for label, final, initial in summary['stats']] + [
            ('Sacoche', str(summary['items']), 'objets' if summary['items'] != 1 else 'objet'),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.tiles = {}
        for index, (caption, value, detail) in enumerate(tiles):
            tile = QFrame()
            tile.setObjectName('chronicleTile')
            box = QVBoxLayout(tile)
            box.setContentsMargins(12, 8, 12, 9)
            box.setSpacing(1)
            for text_, name in ((caption.upper(), 'chronicleCaption'), (value, 'chronicleValue'),
                                (detail, 'chronicleDetail')):
                label = QLabel(text_)
                label.setObjectName(name)
                label.setAlignment(Qt.AlignCenter)
                box.addWidget(label)
            grid.addWidget(tile, index // 4, index % 4)
            self.tiles[caption] = (value, detail)
        layout.addLayout(grid)
        foes = QLabel(defeated_line(summary['won']))
        foes.setObjectName('chronicleFoes')
        foes.setWordWrap(True)
        layout.addWidget(foes)
        if tracking:
            badge = QLabel(tracking)
            badge.setObjectName('customMusicHint')
            badge.setAlignment(Qt.AlignCenter)
            layout.addWidget(badge)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        for label, choice, name in (('✦  Recommencer l’aventure', 'restart', 'chronicleRestart'),
                                    ('Charger une partie', 'load', 'chronicleLoad'),
                                    ('Fermer', None, 'chronicleClose')):
            button = QPushButton(label)
            button.setObjectName(name)
            button.clicked.connect(lambda checked=False, c=choice: self._choose(c))
            buttons.addWidget(button)
            if choice == 'restart':
                button.setDefault(True)
        layout.addLayout(buttons)

    def _choose(self, choice):
        self.choice = choice
        self.accept() if choice else self.reject()
