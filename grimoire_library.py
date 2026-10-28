"""Bibliothèque des PDF privés importés ; aucune copie de leur contenu n'est distribuée."""
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton

from dialog_chrome import DialogHeading
from grimoire_modules.registry import module_for_pdf
from illustrations import cover


@dataclass(frozen=True)
class ImportedGrimoire:
    path: Path
    title: str
    module: object = None


def imported_grimoires(folder):
    """Lister uniquement les PDF du dossier privé, sans suivre un lien vers l'extérieur."""
    folder = Path(folder).resolve()
    if not folder.is_dir():
        return []
    books = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if path.suffix.lower() != '.pdf' or not path.is_file() or not path.resolve().is_relative_to(folder):
            continue
        try:
            module = module_for_pdf(path)
        except OSError:
            continue
        books.append(ImportedGrimoire(path.resolve(), module.title if module else path.stem, module))
    return sorted(books, key=lambda book: book.title.casefold())


def cover_icon(book):
    """Créer une miniature temporaire depuis le PDF privé, jamais un fichier de cache."""
    if book.module is None:
        return QIcon()
    entry = cover(book.module.catalogue('illustrations'))
    if not entry:
        return QIcon()
    import pymupdf
    try:
        with pymupdf.open(book.path) as document:
            page = document[entry['page_pdf'] - 1]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(.2, .2),
                                  clip=pymupdf.Rect(entry['rect']) & page.rect, alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            return QIcon(QPixmap.fromImage(image))
    except (OSError, ValueError, RuntimeError):
        return QIcon()


class GrimoireLibraryDialog(QDialog):
    """Retourner un PDF choisi ou une demande d'import ; annuler ne modifie rien."""
    def __init__(self, books, selected_path=None, parent=None):
        super().__init__(parent)
        self.selected_path = None
        self.import_requested = False
        self.setWindowTitle('Bifurk — Vos grimoires')
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        area = self.screen().availableGeometry()
        self.resize(min(820, area.width() - 60), min(640, area.height() - 60))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHeading('Choisissez votre aventure',
            'Retrouvez vos grimoires ou importez un nouveau livre PDF.'))
        self.books = QListWidget()
        self.books.setAccessibleName('Grimoires importés')
        self.books.setIconSize(QSize(84, 132))
        selected = Path(selected_path).resolve() if selected_path else None
        for book in books:
            status = ('Aventure complète' if book.module and book.module.status == 'ready' else
                      'En préparation — couverture, prologue et consultation' if book.module else
                      'PDF non reconnu — lecture manuelle')
            item = QListWidgetItem(cover_icon(book), f'{book.title}\n{status}')
            item.setData(Qt.UserRole, str(book.path))
            item.setToolTip(f'{book.title}\n{status}\n{book.path.name}')
            item.setSizeHint(QSize(400, 150))
            self.books.addItem(item)
            if selected and selected == book.path:
                self.books.setCurrentItem(item)
        if self.books.currentRow() < 0 and self.books.count():
            self.books.setCurrentRow(0)
        layout.addWidget(self.books, 1)
        buttons = QHBoxLayout()
        importer = QPushButton('Importer un PDF…')
        importer.clicked.connect(self.request_import)
        buttons.addWidget(importer)
        buttons.addStretch()
        cancel = QPushButton('Annuler')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.open_button = QPushButton('Ouvrir ce grimoire')
        self.open_button.setProperty('dialogAction', 'primary')
        self.open_button.setDefault(True)
        self.open_button.setEnabled(bool(self.books.count()))
        self.open_button.clicked.connect(self.choose)
        buttons.addWidget(self.open_button)
        self.books.itemDoubleClicked.connect(lambda _: self.choose())
        layout.addLayout(buttons)

    def choose(self):
        item = self.books.currentItem()
        if item is not None:
            self.selected_path = item.data(Qt.UserRole)
            self.accept()

    def request_import(self):
        self.import_requested = True
        self.accept()
