"""Five portable save slots, with metadata read from the saves themselves."""
import json
from datetime import datetime
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                               QDialogButtonBox, QMessageBox)


class SaveSlotsDialog(QDialog):
    def __init__(self, folder, saving, parent=None):
        super().__init__(parent)
        self.selected_path = None
        self.setWindowTitle('Sauvegarder l’aventure' if saving else 'Charger une aventure')
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        heading = QLabel('✦  LES CHRONIQUES DES AVENTURIERS  ✦')
        heading.setObjectName('saveHeading')
        heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(heading)
        layout.addWidget(QLabel('Choisissez un emplacement.'))
        for number in range(1, 6):
            path = folder / f'emplacement-{number}.json'
            exists = path.exists()
            valid = False
            description = 'Emplacement libre'
            if exists:
                try:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(data, dict) or not isinstance(data.get('character'), dict):
                        raise ValueError('Invalid save')
                    character = data['character']
                    date = (datetime.fromisoformat(data['saved_at']) if data.get('saved_at')
                            else datetime.fromtimestamp(path.stat().st_mtime).astimezone())
                    description = (
                        f'{character.get("name") or "Aventurier sans nom"}  ·  {date:%d/%m/%Y à %H:%M}\n'
                        f'Habileté {character["habilete"]}   ·   '
                        f'Endurance {character["endurance"]}   ·   Chance {character["chance"]}')
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    description = 'Sauvegarde illisible'
            button = QPushButton(f'⚜  Emplacement {number}\n{description}')
            button.setObjectName(f'saveSlot{number}')
            button.setProperty('saveSlot', True)
            button.setMinimumHeight(82)
            button.setEnabled(saving or valid)
            button.clicked.connect(lambda checked=False, p=path, occupied=exists:
                                   self.choose(p, saving and occupied))
            layout.addWidget(button)
        close = QDialogButtonBox(QDialogButtonBox.Cancel)
        close.button(QDialogButtonBox.Cancel).setText('Annuler')
        if not saving and parent is not None:
            legacy = QPushButton('Ouvrir une ancienne sauvegarde…')
            legacy.clicked.connect(self.open_legacy)
            layout.addWidget(legacy)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def open_legacy(self):
        path = self.parent()._themed_file_dialog(kind='load')
        if path:
            self.selected_path = path
            self.accept()

    def choose(self, path, confirm):
        if confirm and QMessageBox.question(
                self, 'Remplacer la chronique',
                'Remplacer la sauvegarde de cet emplacement ?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.selected_path = str(path)
        self.accept()
