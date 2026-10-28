"""Dialogue des cinq sauvegardes manuelles et lecture de leur format actuel.

Chaque ligne lit ses métadonnées dans le JSON de l'emplacement, sans ouvrir le
PDF. Le dialogue retourne un chemin ou une demande de nouvelle partie ; le
contrôleur assure ensuite la restauration ou l'écriture atomique. Les fichiers
anciens/incomplets ne sont pas migrés. Un emplacement illisible reste supprimable.
L'autosave technique n'est pas un sixième emplacement de ce menu ; au démarrage,
« Continuer la dernière partie » reprend la plus récente des sauvegardes lisibles,
emplacements et autosave confondus (latest_save). cover_for, fourni par le contrôleur,
donne la miniature de couverture d'une sauvegarde (rendue depuis le PDF du joueur)."""
import json
from datetime import datetime
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
                               QDialogButtonBox, QMessageBox, QScrollArea, QSizePolicy,
                               QStyleOptionButton, QStyle)
from dialog_chrome import DialogHeading
from adventure_tracking import LABELS, read_tracking


def _is_int(value):
    """Entier JSON strict : ni booléen, ni flottant, ni texte."""
    return type(value) is int


def check_game_state(state, where='Sauvegarde'):
    """Contrôler un instantané de partie avant de le confier à MainWindow._restore.

    Sert à l'état principal comme à chaque entrée d'Annuler / Rétablir : une
    sauvegarde abîmée est refusée au chargement au lieu de planter au premier
    Annuler. Les clés facultatives des anciens formats ne sont contrôlées que
    si elles sont présentes."""
    def invalid(detail):
        return ValueError(f'{where} invalide : {detail}.')
    if not isinstance(state, dict):
        raise invalid('état absent')
    character = state.get('character')
    if not isinstance(character, dict):
        raise invalid('aventurier absent')
    for key in ('habilete', 'endurance', 'chance'):
        if not _is_int(character.get(key)):
            raise invalid('caractéristiques')
    if not isinstance(character.get('inventory', []), list):
        raise invalid('inventaire')
    if 'current_paragraph' not in state or not (
            state['current_paragraph'] is None or _is_int(state['current_paragraph'])):
        raise invalid('paragraphe courant')
    visited = state.get('visited_paragraphs')
    if not isinstance(visited, list) or not all(_is_int(n) for n in visited):
        raise invalid('paragraphes visités')
    transitions = state.get('transitions', [])
    if not isinstance(transitions, list) or not all(
            isinstance(t, list) and len(t) == 2 and all(_is_int(n) for n in t) for t in transitions):
        raise invalid('transitions')
    if not isinstance(state.get('encounter_history', {}), dict):
        raise invalid('rencontres')
    for key in ('completed_book_events', 'completed_optional_events', 'prepared_book_encounters'):
        if not isinstance(state.get(key, []), list):
            raise invalid('événements du livre')
    assaults = state.get('book_combat_assaults', {})
    if not isinstance(assaults, dict) or not all(
            str(k).lstrip('-').isdigit() and _is_int(v) for k, v in assaults.items()):
        raise invalid('assauts')
    for key in ('enemy_skill', 'enemy_endurance'):
        if key in state and not _is_int(state[key]):
            raise invalid('adversaire')
    if 'enemy_name' in state and not isinstance(state['enemy_name'], str):
        raise invalid('adversaire')


def _check_history(data):
    """Journal de libellés et piles [libellé, état] d'Annuler / Rétablir."""
    if not isinstance(data['action_history'], list) or not all(
            isinstance(label, str) for label in data['action_history']):
        raise ValueError('Journal des actions invalide.')
    for key, name in (('undo_stack', 'Annuler'), ('redo_stack', 'Rétablir')):
        stack = data[key]
        if not isinstance(stack, list):
            raise ValueError(f'Historique « {name} » invalide.')
        for index, entry in enumerate(stack, 1):
            if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str)):
                raise ValueError(f'Historique « {name} » invalide (entrée {index}).')
            check_game_state(entry[1], f'Historique « {name} » (entrée {index})')


def read_save(path):
    """Lire et contrôler les champs obligatoires du format actuel.

    Lever les erreurs JSON, disque ou ValueError pour laisser le menu marquer le
    slot illisible. Ce contrôle ne résout pas le PDF : MainWindow vérifie ensuite
    le chemin et son empreinte. Aucune migration de sauvegarde ancienne."""
    data = json.loads(path.read_text(encoding='utf-8'))
    required = {'saved_at', 'save_name', 'pdf_path', 'pdf_sha256', 'character',
                'encounter_history', 'completed_book_events', 'completed_optional_events',
                'prepared_book_encounters', 'book_combat_sequence', 'crocodile_combat',
                'piranha_source_wounded', 'piranha_combat', 'book_combat_assaults',
                'current_paragraph', 'visited_paragraphs', 'transitions',
                'enemy_skill', 'enemy_endurance', 'enemy_name',
                'action_history', 'undo_stack', 'redo_stack'}
    if not isinstance(data, dict) or not required <= data.keys():
        raise ValueError('Format de sauvegarde invalide.')
    if not isinstance(data['character'], dict) or not isinstance(data['save_name'], str) or not data['save_name'].strip():
        raise ValueError('Aventurier invalide.')
    for key in ('habilete', 'endurance', 'chance'):
        if type(data['character'].get(key)) is not int:
            raise ValueError('Caractéristiques invalides.')
    check_game_state(data)
    _check_history(data)
    if not isinstance(data.get('book_title', ''), str):
        raise ValueError('Titre du grimoire invalide.')
    read_tracking(data.get('adventure_tracking'))
    datetime.fromisoformat(data['saved_at'])
    return data


AUTOSAVE_NAME = 'autosave.json'


def _saved_at(data):
    """Date comparable : une date sans fuseau est lue à l'heure locale."""
    date = datetime.fromisoformat(data['saved_at'])
    return date if date.tzinfo else date.astimezone()


def latest_save(folder):
    """(chemin, données, origine) de la sauvegarde lisible la plus récente, ou None.

    Les cinq emplacements et l'autosave sont comparés par leur date ; un fichier
    illisible est ignoré sans erreur."""
    found = []
    candidates = [(folder / f'emplacement-{n}.json', f'emplacement {n}') for n in range(1, 6)]
    candidates.append((folder / AUTOSAVE_NAME, 'sauvegarde automatique'))
    for path, origin in candidates:
        if not path.exists():
            continue
        try:
            data = read_save(path)
            found.append((_saved_at(data), path, data, origin))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not found:
        return None
    _, path, data, origin = max(found, key=lambda entry: entry[0])
    return path, data, origin


class SaveSlotButton(QPushButton):
    """Garder les longues chroniques dans leur carte, avec le texte complet accessible."""
    def __init__(self, text):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)

    def minimumSizeHint(self):
        if self.property('emptySlot'):
            return QSize(220, self.fontMetrics().lineSpacing() + 22)
        cover = self.iconSize().height() + 20 if not self.icon().isNull() else 0
        return QSize(220, max(82, cover, self.fontMetrics().lineSpacing() *
                              len(self.text().splitlines()) + 32))

    def sizeHint(self):
        return super().sizeHint().expandedTo(self.minimumSizeHint())

    def paintEvent(self, event):
        """Écourter uniquement le dessin ; text(), lecteur d'écran et infobulle restent complets."""
        option = QStyleOptionButton()
        self.initStyleOption(option)
        room = self.width() - 42 - (self.iconSize().width() + 10 if not self.icon().isNull() else 0)
        option.text = '\n'.join(option.fontMetrics.elidedText(line, Qt.ElideRight, max(1, room))
                                for line in self.text().split('\n'))
        painter = QPainter(self)
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)


class SaveSlotsDialog(QDialog):
    """Menu modal renvoyant selected_path ou new_game_requested après acceptation."""
    COVER_SIZE = QSize(50, 76)

    def __init__(self, folder, saving, parent=None, *, startup=False, cover_for=None):
        """Créer cinq lignes ; saving autorise les cases libres, startup supprime la confirmation
        de reprise et propose de continuer la dernière partie."""
        super().__init__(parent)
        self.cover_for = cover_for
        self.selected_path = None
        self.new_game_requested = False
        self.confirm_new_game = not startup
        self.folder, self.saving = folder, saving
        self.setObjectName('saveSlotsDialog')
        self.setWindowTitle('Bifurk — ' + ('Commencer une aventure' if startup else
                            'Sauvegarder l’aventure' if saving else 'Charger une aventure'))
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(600)
        area = self.screen().availableGeometry()
        self.resize(min(720, area.width() - 60), min(780, area.height() - 80))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(DialogHeading('Les chroniques des aventuriers',
                                      'Cinq emplacements pour conserver votre histoire.'))
        latest = latest_save(folder) if startup and not saving else None
        if latest is not None:
            path, data, origin = latest
            date = _saved_at(data)
            place = (f"  ·  §{data['current_paragraph']}"
                     if isinstance(data.get('current_paragraph'), int) else '')
            title = data.get('book_title') or 'Grimoire'
            resume = SaveSlotButton(f'Continuer la dernière partie\n'
                                    f'{data["save_name"]}  ·  {title}{place}\n'
                                    f'{date:%d/%m/%Y à %H:%M}  ·  {origin}')
            resume.setObjectName('continueAdventure')
            resume.setProperty('saveSlot', True)
            resume.setProperty('continueSlot', True)
            resume.setToolTip(resume.text())
            self._set_cover(resume, data)
            resume.clicked.connect(lambda checked=False, p=path: self.choose(p, False))
            layout.addWidget(resume)
            resume.ensurePolished()
            resume.setMinimumHeight(resume.minimumSizeHint().height())
        if not saving:
            new_game = QPushButton('✦  Nouvelle partie')
            new_game.setObjectName('newAdventure')
            # La reprise devient l'action principale quand elle existe.
            new_game.setProperty('dialogAction', 'secondary' if latest is not None else 'primary')
            new_game.setMinimumHeight(48)
            new_game.clicked.connect(self.start_new_game)
            layout.addWidget(new_game)
        layout.addWidget(QLabel('Charger une aventure ou commencer une nouvelle partie.' if not saving
                                else 'Choisissez un emplacement.'))
        # Les cinq emplacements restent accessibles sur les petits écrans ou
        # avec une mise à l'échelle Windows élevée, sans agrandir hors écran.
        scroll = QScrollArea()
        scroll.setObjectName('saveSlotsScroll')
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName('saveSlotsBody')
        self.slots = QVBoxLayout(body)
        self.slots.setContentsMargins(0, 0, 6, 0)
        self.slots.setSpacing(10)
        self.slots.setAlignment(Qt.AlignTop)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.refresh_slots()
        close = QDialogButtonBox(QDialogButtonBox.Cancel)
        close.button(QDialogButtonBox.Cancel).setText('Annuler')
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _set_cover(self, button, data):
        """Miniature de la couverture du grimoire de la sauvegarde, si elle est disponible."""
        if self.cover_for is None:
            return
        try:
            icon = self.cover_for(data)
        except Exception:  # noqa: BLE001 - une couverture manquante n'empêche jamais de charger
            return
        if icon is not None and not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(self.COVER_SIZE)

    def start_new_game(self):
        """Confirmer l’abandon de la progression courante hors démarrage, puis accepter le menu.

        Un refus laisse le dialogue ouvert et le drapeau inchangé ; les fichiers de
        sauvegarde existants ne sont jamais supprimés par une nouvelle partie."""
        if self.confirm_new_game and QMessageBox.question(
                self, 'Commencer une nouvelle partie',
                'Recommencer une nouvelle aventure ?\n'
                'La progression non sauvegardée sera abandonnée. '
                'Vos emplacements sauvegardés seront conservés.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.new_game_requested = True
        self.accept()

    def refresh_slots(self):
        """Recréer les lignes à partir des fichiers, y compris les emplacements illisibles.

        Détacher les anciennes lignes avant deleteLater pour éviter des widgets encore
        repérables pendant la boucle Qt. Capturer les chemins dans les lambdas de boutons."""
        while self.slots.count():
            widget = self.slots.takeAt(0).widget()
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        for number in range(1, 6):
            path = self.folder / f'emplacement-{number}.json'
            exists = path.exists()
            valid = False
            description = 'Emplacement libre'
            if exists:
                try:
                    data = read_save(path)
                    character = data['character']
                    date = datetime.fromisoformat(data['saved_at'])
                    description = (
                        f'{data["save_name"]}  ·  {date:%d/%m/%Y à %H:%M}\n'
                        f"{LABELS[read_tracking(data.get('adventure_tracking'))['status']]}\n"
                        f'Habileté {character["habilete"]}   ·   '
                        f'Endurance {character["endurance"]}   ·   Chance {character["chance"]}')
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    description = 'Sauvegarde illisible'
            title = data.get('book_title', '') if exists and valid else ''
            heading = f'⚜  Emplacement {number}' + (f' · {title}' if title else '')
            button = SaveSlotButton(f'{heading}\n{description}')
            if exists and valid:
                self._set_cover(button, data)
            button.setObjectName(f'saveSlot{number}')
            button.setProperty('saveSlot', True)
            button.setToolTip((title + '\n' if title else '') + description)
            button.setEnabled(self.saving or valid)
            if not exists:
                # Emplacement libre : une seule ligne discrète, sans bouton Supprimer.
                button.setText(f'⚜  Emplacement {number}  —  libre')
                button.setProperty('emptySlot', True)
            button.clicked.connect(lambda checked=False, p=path, occupied=exists:
                                   self.choose(p, self.saving and occupied))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(button, 1)
            delete = QPushButton('Supprimer')
            delete.setObjectName(f'deleteSlot{number}')
            delete.setProperty('dialogAction', 'danger')
            delete.setAccessibleName(f'Supprimer la sauvegarde de l’emplacement {number}')
            delete.setEnabled(exists)
            delete.clicked.connect(lambda checked=False, p=path: self.delete_save(p))
            row_layout.addWidget(delete)
            # Seulement après l'ajout à la ligne : rendu visible sans parent, le
            # bouton deviendrait une petite fenêtre Windows le temps de la construction.
            delete.setVisible(exists)
            self.slots.addWidget(row)
            button.ensurePolished()
            button.setMinimumHeight(button.minimumSizeHint().height())

    def delete_save(self, path):
        """Demander confirmation, supprimer le fichier choisi puis rafraîchir sans fermer le menu."""
        if QMessageBox.question(self, 'Supprimer la chronique',
                'Supprimer définitivement la sauvegarde de cet emplacement ?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.critical(self, 'Suppression impossible', str(exc))
        self.refresh_slots()

    def choose(self, path, confirm):
        """Confirmer l’écrasement si nécessaire puis retourner le chemin de l’emplacement."""
        if confirm and QMessageBox.question(
                self, 'Remplacer la chronique',
                'Remplacer la sauvegarde de cet emplacement ?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.selected_path = str(path)
        self.accept()
