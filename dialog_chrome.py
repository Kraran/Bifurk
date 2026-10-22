"""Habillage commun des fenêtres secondaires, indépendant de l'état du jeu.

Les contrôles restent ceux de Qt : focus, clavier, boutons par défaut et retours
modaux sont conservés. Les bandeaux et les icônes réutilisent la palette active,
sans titre doublé d'une croix de fermeture dans le contenu.
"""
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QDialogButtonBox, QFileDialog, QFileIconProvider,
                               QFrame, QGridLayout, QInputDialog, QLabel,
                               QMessageBox, QVBoxLayout)

from themes import default_theme


class DialogHeading(QFrame):
    """Bandeau de cuir à titre doré, avec une indication courte facultative."""
    def __init__(self, title, subtitle='', parent=None):
        super().__init__(parent)
        self.setObjectName('dialogHeading')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(3)
        heading = QLabel(title)
        heading.setObjectName('dialogTitle')
        heading.setWordWrap(True)
        layout.addWidget(heading)
        if subtitle:
            note = QLabel(subtitle)
            note.setObjectName('dialogSubtitle')
            note.setWordWrap(True)
            layout.addWidget(note)


def dialog_theme(dialog):
    """Retrouver le thème du contrôleur même pour les confirmations imbriquées."""
    owner = dialog
    while owner is not None:
        if hasattr(owner, 'theme'):
            return owner.theme
        owner = owner.parentWidget()
    return default_theme()


def add_dialog_heading(dialog, title, subtitle=''):
    """Insérer une seule fois un bandeau en conservant les contrôles du dialogue.

    QFileDialog expose une grille publique : les éléments et leurs étirements
    sont décalés d'une ligne, sans dépendre du nom des widgets internes de Qt.
    QInputDialog utilise une disposition verticale et permet une insertion simple.
    """
    if dialog.property('headingAdded'):
        return
    layout = dialog.layout()
    heading = DialogHeading(title, subtitle, dialog)
    if isinstance(layout, QGridLayout):
        columns = max(1, layout.columnCount())
        rows = layout.rowCount()
        stretches = [(layout.rowStretch(row), layout.rowMinimumHeight(row)) for row in range(rows)]
        items = []
        while layout.count():
            position = layout.getItemPosition(0)
            item = layout.takeAt(0)
            items.append((item, position))
        for row in range(rows + 1):
            layout.setRowStretch(row, 0)
            layout.setRowMinimumHeight(row, 0)
        layout.addWidget(heading, 0, 0, 1, columns)
        for item, (row, column, row_span, column_span) in items:
            layout.addItem(item, row + 1, column, row_span, column_span, item.alignment())
        for row, (stretch, minimum) in enumerate(stretches):
            layout.setRowStretch(row + 1, stretch)
            layout.setRowMinimumHeight(row + 1, minimum)
    elif isinstance(layout, QVBoxLayout):
        layout.insertWidget(0, heading)
    else:
        heading.deleteLater()
        return
    dialog.setProperty('headingAdded', True)


class GrimoireFileIcons(QFileIconProvider):
    """Dossiers de laiton et documents parchemin, à la place des icônes système."""
    def __init__(self, theme, ratio=1):
        super().__init__()
        self.theme, self.ratio = theme, ratio
        self.icons = {}

    def icon(self, source):
        """Conserver les icônes spéciales des lecteurs ; habiller dossiers et fichiers."""
        if isinstance(source, QFileInfo):
            kind = 'folder' if source.isDir() else 'pdf' if source.suffix().lower() == 'pdf' else 'file'
        elif source == QFileIconProvider.Folder:
            kind = 'folder'
        elif source == QFileIconProvider.File:
            kind = 'file'
        else:
            return super().icon(source)
        if kind not in self.icons:
            self.icons[kind] = self._draw(kind)
        return self.icons[kind]

    def _draw(self, kind):
        """Tracer les emblèmes à la densité de l'écran sans image supplémentaire."""
        pixmap = QPixmap(round(32 * self.ratio), round(32 * self.ratio))
        pixmap.setDevicePixelRatio(self.ratio)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(self.theme.color('ornament')), 1.4))
        painter.setBrush(QColor(self.theme.color('gold' if kind == 'folder' else 'page')))
        path = QPainterPath()
        if kind == 'folder':
            path.moveTo(3, 8); path.lineTo(13, 8); path.lineTo(16, 11)
            path.lineTo(29, 11); path.lineTo(29, 27); path.lineTo(3, 27); path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(4, 14, 28, 14)
        else:
            path.moveTo(7, 3); path.lineTo(20, 3); path.lineTo(26, 9)
            path.lineTo(26, 29); path.lineTo(7, 29); path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(20, 3, 20, 9); painter.drawLine(20, 9, 26, 9)
            painter.setPen(QColor(self.theme.color('rubric')))
            if kind == 'pdf':
                font = QFont('serif'); font.setPixelSize(9); font.setBold(True)
                painter.setFont(font)
                painter.drawText(8, 22, 'PDF')
            else:
                for y in (14, 18, 22):
                    painter.drawLine(11, y, 22, y)
        painter.end()
        return QIcon(pixmap)


def harmonize_standard_dialog(dialog):
    """Ajuster les dialogues Qt usuels sans modifier leur choix par défaut.

    Cette fonction est rappelable : elle ne duplique pas les bandeaux et garde
    les labels personnalisés. Elle ne s'applique pas aux plateaux de dés ou de
    combat qui disposent déjà de leur propre composition.
    """
    if not isinstance(dialog, (QFileDialog, QInputDialog, QMessageBox)):
        return
    title = dialog.windowTitle()
    if not title.startswith('Bifurk'):
        dialog.setWindowTitle('Bifurk — ' + title)
    layout = dialog.layout()
    if layout is not None:
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
    if isinstance(dialog, QFileDialog):
        add_dialog_heading(dialog, 'Ouvrir un grimoire', 'Choisissez le PDF de votre livre-jeu.')
        # Le fournisseur doit survivre au modèle de fichiers du sélecteur.
        theme = dialog_theme(dialog)
        if not hasattr(dialog, '_grimoire_file_icons') or dialog._grimoire_file_icons.theme is not theme:
            dialog._grimoire_file_icons = GrimoireFileIcons(theme, dialog.devicePixelRatioF())
            dialog.setIconProvider(dialog._grimoire_file_icons)
    elif isinstance(dialog, QInputDialog):
        add_dialog_heading(dialog, title.removeprefix('Bifurk — '))
        dialog.setMinimumWidth(430)
    labels = {QDialogButtonBox.Ok: 'OK', QDialogButtonBox.Cancel: 'Annuler',
              QDialogButtonBox.Close: 'Fermer', QDialogButtonBox.Open: 'Ouvrir',
              QDialogButtonBox.Save: 'Enregistrer', QDialogButtonBox.Yes: 'Oui',
              QDialogButtonBox.No: 'Non'}
    standard_labels = {'ok', 'cancel', 'close', 'open', 'save', 'yes', 'no'}
    for box in dialog.findChildren(QDialogButtonBox):
        for button in box.buttons():
            standard = box.standardButton(button)
            if standard in labels and button.text().replace('&', '').lower() in standard_labels:
                button.setText(labels[standard])
            if isinstance(dialog, QMessageBox):
                primary = (button is dialog.defaultButton()
                           or (dialog.defaultButton() is None and len(box.buttons()) == 1))
            else:
                primary = box.buttonRole(button) == QDialogButtonBox.AcceptRole
            role = 'primary' if primary else 'secondary'
            if button.property('dialogAction') != role:
                button.setProperty('dialogAction', role)
                button.style().unpolish(button)
                button.style().polish(button)
