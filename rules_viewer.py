"""Read the rule pages directly from the user's PDF; no book content is shipped."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
from grimoire_ui import IllustrationDialog, GrimoireScene


class RulesDialog(IllustrationDialog):
    def __init__(self, pdf_path, parent=None):
        super().__init__(parent)
        import fitz
        self.pdf_path = str(pdf_path)
        with fitz.open(self.pdf_path) as document:
            self.last_page = min(14, len(document))
        if self.last_page < 3:
            raise ValueError("Ce PDF ne contient pas les pages de règles 3 à 14.")
        self.setWindowTitle("Bifurk — Règles du livre · pages PDF 3 à 14")
        self.resize(800, 850)
        layout = QVBoxLayout(self)
        navigation = QHBoxLayout()
        self.previous = QPushButton("← Précédente")
        self.pages = QComboBox()
        self.pages.setAccessibleName("Page PDF des règles")
        self.pages.addItems([f"Page PDF {n}" for n in range(3, self.last_page + 1)])
        self.following = QPushButton("Suivante →")
        navigation.addWidget(self.previous)
        navigation.addWidget(self.pages, 1)
        navigation.addWidget(self.following)
        layout.addLayout(navigation)
        self.viewer = GrimoireScene("")
        layout.addWidget(self.viewer, 1)
        layout.addWidget(QLabel("Molette : zoom · Glisser : déplacer · Clic : recadrer"))
        self.previous.clicked.connect(lambda: self.pages.setCurrentIndex(self.pages.currentIndex()-1))
        self.following.clicked.connect(lambda: self.pages.setCurrentIndex(self.pages.currentIndex()+1))
        self.pages.currentIndexChanged.connect(self.render_page)
        self.render_page(0)

    def render_page(self, index):
        import fitz
        if index < 0:
            return
        with fitz.open(self.pdf_path) as document:
            pix = document[index + 2].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            self.viewer.set_book_art(QPixmap.fromImage(image.copy()))
        self.previous.setEnabled(index > 0)
        self.following.setEnabled(index < self.pages.count()-1)
        self.viewer.setAccessibleName(f"Règles — page PDF {index + 3}")
