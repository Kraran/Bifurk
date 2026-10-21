"""Identité de l'application, portrait et liens de la fenêtre À propos.

Ce module ne touche pas à la partie. BrandButton inclut ses labels dans sa taille
minimale. Le portrait utilise QAbstractButton pour garder activation clavier et
clic sans subir les tailles imposées par le QSS global aux QPushButton.
Son image est ajustée sans déformation ; le crédit de l'asset est dans assets."""
from datetime import date

from PySide6.QtCore import Qt, QUrl, QRectF, QSize
from PySide6.QtGui import QDesktopServices, QPixmap, QPainter, QColor, QLinearGradient, QPainterPath
from PySide6.QtWidgets import (QAbstractButton, QDialog, QFrame, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QLabel, QPushButton, QSizePolicy)

from app_info import APP_VERSION, APP_RELEASE_DATE, AUTHOR, AUTHOR_URL, REPOSITORY_URL


class BrandButton(QPushButton):
    """A button whose size includes its icon/title/subtitle labels."""
    def sizeHint(self):
        """Inclure la taille du layout enfant ; le texte natif vide ne fournit pas la bonne largeur."""
        return self.layout().sizeHint() + QSize(12, 10) if self.layout() else super().sizeHint()

    def minimumSizeHint(self):
        """Conserver l’en-tête cliquable entier même quand le panneau se resserre."""
        return self.sizeHint()


class AuthorPortrait(QAbstractButton):
    """Portrait au rapport conservé, cliquable vers le profil GitHub, sans cadre de focus dessiné."""
    def __init__(self, path, background, parent=None):
        """Charger le portrait et son fond ; garder l’activation native de QAbstractButton."""
        super().__init__(parent)
        self.setObjectName('aboutPortrait')
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Ouvrir le profil GitHub de Kraran')
        self.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(AUTHOR_URL)))
        self.pixmap = QPixmap(str(path))
        self.background = QColor(background)
        self.setFixedWidth(280)
        self.setMinimumHeight(380)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAccessibleName('Portrait de Kraran — ouvrir son profil GitHub')

    def image_rect(self):
        """Calculer un rectangle centré au rapport original de l’image, sans écrasement ni recadrage."""
        if self.pixmap.isNull():
            return QRectF()
        size = self.pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2,
                      (self.height() - size.height()) / 2, size.width(), size.height())

    def paintEvent(self, event):
        """Dessiner le portrait et son fondu sans le cadre de focus fourni par un bouton standard."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.setClipPath(path)
        painter.fillRect(rect, self.background)
        if not self.pixmap.isNull():
            image_rect = self.image_rect()
            scaled = self.pixmap.scaled(image_rect.size().toSize(), Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation)
            painter.drawPixmap(image_rect.topLeft().toPoint(), scaled)
        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        transparent = QColor(self.background)
        transparent.setAlpha(0)
        gradient.setColorAt(0, transparent)
        gradient.setColorAt(.95, transparent)
        gradient.setColorAt(1, self.background)
        painter.fillRect(rect, gradient)


class AboutDialog(QDialog):
    """Présentation modale de Bifurk, reprenant l’identité centralisée de app_info."""
    def __init__(self, assets, theme, parent=None):
        """Assembler portrait cliquable, métadonnées et liens ; la fermeture native remplace le X interne."""
        super().__init__(parent)
        self.setObjectName('aboutDialog')
        self.setWindowTitle('À propos de Bifurk')
        self.resize(820, 550)
        self.setMinimumWidth(760)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(12, 0, 4, 12)
        heading = QLabel('À propos')
        heading.setObjectName('aboutHeading')
        header.addWidget(heading)
        header.addStretch()
        root.addLayout(header)
        body = QFrame()
        body.setObjectName('aboutBody')
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(AuthorPortrait(assets/'about-author.jpg',
                                            theme.color('scene_background'), body))
        content = QVBoxLayout()
        content.setContentsMargins(20, 20, 20, 20)
        content.setSpacing(15)
        hero = QHBoxLayout()
        hero.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(QPixmap(str(assets/'bifurk.png')).scaled(
            56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setFixedSize(56, 56)
        icon.setAccessibleName('Emblème de Bifurk')
        hero.addWidget(icon)
        identity = QVBoxLayout()
        title = QLabel('Bifurk')
        title.setObjectName('aboutAppName')
        identity.addWidget(title)
        subtitle = QLabel(f'Chroniques d’aventure  ·  v{APP_VERSION}')
        subtitle.setObjectName('aboutVersion')
        identity.addWidget(subtitle)
        hero.addLayout(identity, 1)
        content.addLayout(hero)
        description = QLabel(
            'Ouvrez votre grimoire et devenez le héros de l’histoire. '
            'Bifurk accompagne vos livres-jeux : lecture illustrée, dés, combats, '
            'inventaire, carte d’exploration et sauvegardes de vos aventures.')
        description.setWordWrap(True)
        content.addWidget(description)
        details = QGridLayout()
        details.setHorizontalSpacing(18)
        details.setVerticalSpacing(7)
        link_color = theme.color('gold')
        rows = [
            ('Version', APP_VERSION),
            ('Date', date.fromisoformat(APP_RELEASE_DATE).strftime('%d/%m/%Y')),
            ('Auteur', f'{AUTHOR} (<a href="{AUTHOR_URL}" style="color:{link_color}">Kraran</a>)'),
            ('Dépôt', f'<a href="{REPOSITORY_URL}" style="color:{link_color}">github.com/Kraran/Bifurk</a>'),
            ('Ressources', 'Sons CC0 · Polices libres OFL'),
            ('Technologies', 'Python · PySide6 / Qt · PyMuPDF'),
        ]
        for row, (caption, value) in enumerate(rows):
            key = QLabel(caption)
            key.setObjectName('aboutKey')
            label = QLabel(value)
            label.setWordWrap(True)
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            details.addWidget(key, row, 0, Qt.AlignTop)
            details.addWidget(label, row, 1)
        details.setColumnStretch(1, 1)
        content.addLayout(details)
        note = QLabel('Aucun livre n’est inclus. Importez votre propre PDF pour commencer '
                      'l’aventure. Vos grimoires et vos sauvegardes restent sur votre ordinateur.')
        note.setObjectName('aboutNote')
        note.setWordWrap(True)
        content.addWidget(note)
        content.addStretch()
        body_layout.addLayout(content, 1)
        root.addWidget(body, 1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.setContentsMargins(0, 14, 0, 0)
        footer.addStretch()
        for text, url, name in [('Profil Kraran', AUTHOR_URL, 'aboutProfile'),
                                ('Dépôt GitHub', REPOSITORY_URL, 'aboutRepository')]:
            button = QPushButton(text)
            button.setObjectName(name)
            button.clicked.connect(lambda checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
            footer.addWidget(button)
        close = QPushButton('Fermer')
        close.setObjectName('goldButton')
        close.setDefault(True)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)
