"""Consultation des pages de règles déclarées par le module, sans contenu embarqué.

La numérotation affichée est celle des pages physiques du PDF, pas des paragraphes.
Le rendu réutilise le zoom et le déplacement d'une illustration. Les pixels sont
copiés dans QImage avant fermeture du document PyMuPDF pour garder leur validité."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
from grimoire_ui import IllustrationDialog, GrimoireScene
from dialog_chrome import DialogHeading


class RulesDialog(IllustrationDialog):
    """Lecteur indépendant des pages de règles, avec navigation physique et image zoomable."""
    def __init__(self, pdf_path, parent=None, *, pages=(3, 14), title='Les règles de l’aventure', section='Règles'):
        """Borner les règles aux pages configurées disponibles et connecter précédent / suivant / sélection."""
        super().__init__(parent)
        import pymupdf as fitz
        self.pdf_path = str(pdf_path)
        self.section = section
        self.first_page, requested_last = pages
        if not 1 <= self.first_page <= requested_last:
            raise ValueError("Intervalle de pages de règles invalide.")
        with fitz.open(self.pdf_path) as document:
            self.last_page = min(requested_last, len(document))
        if self.last_page < self.first_page:
            raise ValueError("Ce PDF ne contient pas les pages de règles du module.")
        self.setWindowTitle(f"Bifurk — {section} du livre · pages PDF {self.first_page} à {self.last_page}")
        area = self.screen().availableGeometry()
        self.resize(min(800, area.width() - 60), min(850, area.height() - 70))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(DialogHeading(title, f'Pages {self.first_page} à {self.last_page} de votre grimoire.'))
        navigation = QHBoxLayout()
        self.previous = QPushButton("← Précédente")
        self.pages = QComboBox()
        self.pages.setAccessibleName("Page PDF des règles")
        self.pages.addItems([f"Page PDF {n}" for n in range(self.first_page, self.last_page + 1)])
        self.following = QPushButton("Suivante →")
        navigation.addWidget(self.previous)
        navigation.addWidget(self.pages, 1)
        navigation.addWidget(self.following)
        layout.addLayout(navigation)
        self.viewer = GrimoireScene("", theme=getattr(parent, "theme", None))
        layout.addWidget(self.viewer, 1)
        layout.addWidget(QLabel("Molette : zoom · Glisser : déplacer · Clic : recadrer"))
        self.previous.clicked.connect(lambda: self.pages.setCurrentIndex(self.pages.currentIndex()-1))
        self.following.clicked.connect(lambda: self.pages.setCurrentIndex(self.pages.currentIndex()+1))
        self.pages.currentIndexChanged.connect(self.render_page)
        self.render_page(0)

    def render_page(self, index):
        """Rendre l’index de liste (base zéro) vers la page physique first_page+index.

        Copier les pixels avant fermeture du document et borner les boutons de navigation."""
        import pymupdf as fitz
        if index < 0:
            return
        with fitz.open(self.pdf_path) as document:
            pix = document[index + self.first_page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            self.viewer.set_book_art(QPixmap.fromImage(image.copy()))
        self.previous.setEnabled(index > 0)
        self.following.setEnabled(index < self.pages.count()-1)
        self.viewer.setAccessibleName(f"{self.section} — page PDF {index + self.first_page}")
