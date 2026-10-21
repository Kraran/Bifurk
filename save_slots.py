"""Dialogue des cinq sauvegardes manuelles et lecture de leur format actuel.

Chaque ligne lit ses métadonnées dans le JSON de l'emplacement, sans ouvrir le
PDF. Le dialogue retourne un chemin ou une demande de nouvelle partie ; le
contrôleur assure ensuite la restauration ou l'écriture atomique. Les fichiers
anciens/incomplets ne sont pas migrés. Un emplacement illisible reste supprimable.
L'autosave technique n'est pas un sixième emplacement de ce menu."""
import json
from datetime import datetime
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
                               QDialogButtonBox, QMessageBox)


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
    datetime.fromisoformat(data['saved_at'])
    return data


class SaveSlotsDialog(QDialog):
    """Menu modal renvoyant selected_path ou new_game_requested après acceptation."""
    def __init__(self, folder, saving, parent=None, *, startup=False):
        """Créer cinq lignes ; saving autorise les cases libres, startup supprime la confirmation de reprise."""
        super().__init__(parent)
        self.selected_path = None
        self.new_game_requested = False
        self.confirm_new_game = not startup
        self.folder, self.saving = folder, saving
        self.setWindowTitle('Commencer une aventure' if startup else
                            'Sauvegarder l’aventure' if saving else 'Charger une aventure')
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        heading = QLabel('✦  LES CHRONIQUES DES AVENTURIERS  ✦')
        heading.setObjectName('saveHeading')
        heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(heading)
        if not saving:
            new_game = QPushButton('✦  Nouvelle partie')
            new_game.setObjectName('newAdventure')
            new_game.setMinimumHeight(48)
            new_game.clicked.connect(self.start_new_game)
            layout.addWidget(new_game)
        layout.addWidget(QLabel('Charger une aventure ou commencer une nouvelle partie.' if not saving
                                else 'Choisissez un emplacement.'))
        self.slots = QVBoxLayout()
        layout.addLayout(self.slots)
        self.refresh_slots()
        close = QDialogButtonBox(QDialogButtonBox.Cancel)
        close.button(QDialogButtonBox.Cancel).setText('Annuler')
        close.rejected.connect(self.reject)
        layout.addWidget(close)

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
                        f'Habileté {character["habilete"]}   ·   '
                        f'Endurance {character["endurance"]}   ·   Chance {character["chance"]}')
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    description = 'Sauvegarde illisible'
            button = QPushButton(f'⚜  Emplacement {number}\n{description}')
            button.setObjectName(f'saveSlot{number}')
            button.setProperty('saveSlot', True)
            button.setMinimumHeight(82)
            button.setEnabled(self.saving or valid)
            button.clicked.connect(lambda checked=False, p=path, occupied=exists:
                                   self.choose(p, self.saving and occupied))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(button, 1)
            delete = QPushButton('Supprimer')
            delete.setObjectName(f'deleteSlot{number}')
            delete.setAccessibleName(f'Supprimer la sauvegarde de l’emplacement {number}')
            delete.setEnabled(exists)
            delete.clicked.connect(lambda checked=False, p=path: self.delete_save(p))
            row_layout.addWidget(delete)
            self.slots.addWidget(row)

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
