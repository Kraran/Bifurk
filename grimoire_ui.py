"""Surfaces graphiques du grimoire, indépendantes des règles de l'aventure.

Les widgets dessinent texture, ornements et illustrations avec QPainter et les
couleurs du thème. Leurs états (zoom, déplacement, taille) sont visuels seulement.
GrimoireScene émet activated pour demander l'agrandissement ; seul le contrôleur
sait quel PDF ouvrir. Conserver les comportements clavier et le focus des boutons
natifs malgré le dessin personnalisé."""
from themes import default_theme
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette, QPainter, QPainterPath, QLinearGradient, QPixmap, QIcon, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QSizePolicy, QStyleOptionButton, QStyle, QDialog


class SingleLineTitle(QLabel):
    """Fit the whole heading on one line without widening the reader."""
    def minimumSizeHint(self):
        """Laisser le titre se réduire sans imposer sa largeur intégrale au panneau de lecture."""
        return QSize(0, super().minimumSizeHint().height())

    def fitted_font(self):
        """Calculer une copie de police réduite au besoin, en respectant unités pixels ou points."""
        font = QFont(self.font())
        width = QFontMetrics(font).horizontalAdvance(self.text())
        available = max(1, self.contentsRect().width() - 8)
        if width > available:
            scale = available / width
            if font.pixelSize() > 0:
                font.setPixelSize(max(1, int(font.pixelSize() * scale)))
            else:
                font.setPointSizeF(max(1, font.pointSizeF() * scale))
        return font

    def paintEvent(self, event):
        """Dessiner le titre centré sur une ligne avec la police adaptée à la largeur disponible."""
        painter = QPainter(self)
        painter.setFont(self.fitted_font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(self.contentsRect(), Qt.AlignCenter | Qt.TextSingleLine, self.text())


class IllustrationDialog(QDialog):
    """Resizable illustration window with native maximize and an explicit size reset."""

    def __init__(self, parent=None):
        """Préparer une fenêtre native redimensionnable avec F11 et taille normale mémorisée."""
        super().__init__(parent, Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                         | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.default_size = QSize(640, 600)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    def toggle_fullscreen(self):
        """Basculer la fenêtre d’illustration entre plein écran et affichage normal."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def restore_default_size(self):
        """Quitter le plein écran et rétablir la taille mémorisée à l’ouverture."""
        self.showNormal()
        self.resize(self.default_size)

    def keyPressEvent(self, event):
        """Sur Échap en plein écran, retrouver la taille normale ; déléguer les autres touches."""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.restore_default_size()
            event.accept()
        else:
            super().keyPressEvent(event)


class IlluminatedPage(QWidget):
    """A book page with painted corner flourishes, independent of native controls."""

    def __init__(self, texture_path=None, parent=None, theme=None):
        """Initialiser thème et texture ; une texture absente laisse apparaître la couleur de page."""
        super().__init__(parent)
        self.theme = theme or default_theme()
        self.texture = QPixmap(str(texture_path)) if texture_path else QPixmap()

    def set_theme(self, theme):
        """Mettre à jour les couleurs et textures de la surface puis demander un nouveau dessin."""
        self.theme = theme
        self.texture = QPixmap(str(theme.assets['parchment']))
        self.update()

    def paintEvent(self, event):
        """Dessiner le parchemin sous un clip arrondi puis les filets et quatre ornements tournés."""
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        page = QPainterPath()
        page.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.setClipPath(page)
        p.fillPath(page, QColor(self.theme.color("page")))
        if not self.texture.isNull():
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawPixmap(QRectF(self.rect()), self.texture, QRectF(self.texture.rect()))
        p.setPen(QPen(QColor(self.theme.color("ornament")), 1.2))
        p.drawRoundedRect(self.rect().adjusted(4, 4, -5, -5), 10, 10)
        p.drawRoundedRect(self.rect().adjusted(8, 8, -9, -9), 8, 8)
        for x, y, rotation in ((12, 12, 0), (self.width()-12, 12, 90),
                                (self.width()-12, self.height()-12, 180),
                                (12, self.height()-12, 270)):
            p.save()
            p.translate(x, y)
            p.rotate(rotation)
            flourish = QPainterPath()
            flourish.moveTo(0, 43)
            flourish.cubicTo(0, 10, 30, 29, 22, 10)
            flourish.cubicTo(12, -5, 10, 31, 43, 0)
            p.drawPath(flourish)
            p.setBrush(QColor(self.theme.color("rubric")))
            p.drawEllipse(QRectF(5, 5, 5, 5))
            p.restore()


class ChoiceCard(QPushButton):
    """Wrap long destinations while keeping native button focus and keyboard behaviour."""

    def __init__(self, text, parent=None):
        """Confier le retour à la ligne au label et les clics au bouton parent.

        Le label transparent aux événements souris empêche les zones de texte de
        masquer l’activation native ; le layout détermine la hauteur du contenu."""
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 14, 12)
        caption = QLabel(text)
        caption.setWordWrap(True)
        caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        caption.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(caption)

    def paintEvent(self, event):
        """Laisser Qt dessiner le bouton sans texte : le label enfant gère le retour à la ligne."""
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        painter = QPainter(self)
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)


def inventory_icon(name, theme=None):
    """Small vector emblems stay sharp and work without platform emoji fonts."""
    theme = theme or default_theme()
    canvas = QPixmap(48, 48)
    canvas.fill(Qt.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(theme.color("icon_border")), 1.5))
    p.setBrush(QColor(theme.color("icon_background")))
    p.drawRoundedRect(2, 2, 44, 44, 7, 7)
    p.setPen(QPen(QColor(theme.color("icon_ink")), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    text = str(name).casefold()
    if "clé" in text:
        p.drawEllipse(12, 10, 13, 13)
        p.drawLine(23, 22, 35, 35)
        p.drawLine(30, 30, 34, 26)
        p.drawLine(34, 34, 38, 30)
    elif "épée" in text or "hache" in text or "piquet" in text:
        p.drawLine(14, 35, 35, 12)
        p.drawLine(14, 26, 23, 35)
        p.drawLine(12, 36, 16, 39)
        p.drawLine(30, 14, 36, 11)
        p.drawLine(36, 11, 34, 18)
    elif "armure" in text or "bouclier" in text:
        path = QPainterPath()
        path.moveTo(12, 12); path.lineTo(36, 12); path.lineTo(34, 29)
        path.quadTo(31, 36, 24, 39); path.quadTo(17, 36, 14, 29); path.closeSubpath()
        p.drawPath(path)
        p.drawLine(24, 15, 24, 33)
    elif "potion" in text or "bouteille" in text:
        p.drawRect(20, 10, 8, 9)
        p.drawEllipse(14, 20, 20, 19)
        p.drawLine(18, 29, 30, 29)
    elif "lanterne" in text:
        p.drawArc(18, 8, 12, 12, 0, 180 * 16)
        p.drawRect(15, 19, 18, 18)
        p.drawLine(12, 17, 36, 17)
        p.drawLine(24, 23, 24, 32)
    else:
        path = QPainterPath()
        path.moveTo(24, 10); path.lineTo(37, 23); path.lineTo(24, 38)
        path.lineTo(11, 23); path.closeSubpath()
        p.drawPath(path)
        p.drawLine(11, 23, 37, 23)
        p.drawLine(24, 10, 24, 38)
    p.end()
    return QIcon(canvas)


class GrimoireScene(QWidget):
    """Paint an atmospheric banner, or fit a book illustration without cropping it."""

    activated = Signal()

    def __init__(self, image_path, parent=None, theme=None):
        """Charger le décor et initialiser zoom relatif, déplacement et suivi du glissement."""
        super().__init__(parent)
        self.theme = theme or default_theme()
        self.atmosphere = QPixmap(str(image_path))
        self.picture = self.atmosphere
        self.is_book_art = False
        self.zoom = 1.0
        self.pan = QPointF()
        self._press_position = None
        self._dragged = False
        self.setMinimumSize(160, 280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName("Bibliothèque du grimoire — décor d’ambiance")

    def set_theme(self, theme):
        """Mettre à jour les couleurs et textures de la surface puis demander un nouveau dessin."""
        self.theme = theme
        self.atmosphere = QPixmap(str(theme.assets['scene']))
        if not self.is_book_art:
            self.picture = self.atmosphere
        self.update()

    def sizeHint(self):
        """Proposer une taille verticale de référence sans imposer de largeur fixe à la mise en page."""
        return QSize(300, 640)

    def set_book_art(self, pixmap=None):
        """Choisir l’illustration ou le décor et réinitialiser zoom, déplacement et aide accessible."""
        self.is_book_art = pixmap is not None and not pixmap.isNull()
        self.picture = pixmap if self.is_book_art else self.atmosphere
        self.reset_view()
        self.setAccessibleName("Illustration du paragraphe" if self.is_book_art
                               else "Bibliothèque du grimoire — décor d’ambiance")
        self.setCursor(Qt.PointingHandCursor if self.is_book_art else Qt.ArrowCursor)
        self.setToolTip("Molette : zoom · Glisser : déplacer · Clic : recadrer · Double-clic : agrandir"
                        if self.is_book_art else "")
        self.update()

    def reset_view(self):
        """Revenir au cadrage entier centré (zoom relatif 1), sans changer l’image."""
        self.zoom = 1.0
        self.pan = QPointF()
        self.update()

    def _fit_scale(self):
        """Calculer le facteur qui fait tenir l’image entière dans la surface avec marge de deux pixels."""
        return min(max(1, self.width()-4) / max(1, self.picture.width()),
                   max(1, self.height()-4) / max(1, self.picture.height()))

    def _constrain_pan(self):
        """Limiter le déplacement au débordement de l’image ; centrer les axes qui ne débordent pas."""
        scale = self._fit_scale() * self.zoom
        limit_x = max(0, (self.picture.width() * scale - (self.width()-4)) / 2)
        limit_y = max(0, (self.picture.height() * scale - (self.height()-4)) / 2)
        self.pan = QPointF(max(-limit_x, min(limit_x, self.pan.x())),
                           max(-limit_y, min(limit_y, self.pan.y())))

    def wheelEvent(self, event):
        """Zoomer de 1 à 12 autour du pointeur puis borner le déplacement.

        La correction de pan conserve le point visé sous la souris pendant le zoom ;
        le décor seul n’intercepte pas la molette."""
        if not self.is_book_art:
            super().wheelEvent(event)
            return
        steps = event.angleDelta().y() / 120 or event.pixelDelta().y() / 120
        previous = self.zoom
        self.zoom = max(1.0, min(12.0, previous * 1.2 ** steps))
        # Exprimer le pointeur par rapport au centre du widget, puis compenser
        # le changement d'échelle pour garder le détail visé sous la souris.
        anchor = event.position() - QPointF(self.width()/2, self.height()/2)
        self.pan = anchor - (anchor - self.pan) * (self.zoom / previous)
        self._constrain_pan()
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        """Mémoriser le départ du glissement gauche sur une illustration et passer le curseur en croix."""
        if event.button() == Qt.LeftButton and self.is_book_art:
            self._press_position = event.position()
            self._initial_pan = QPointF(self.pan)
            self._dragged = False
            self.setCursor(Qt.CrossCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Déplacer depuis le pan initial après un seuil de quatre pixels pour distinguer clic et glissement."""
        if self._press_position is not None:
            delta = event.position() - self._press_position
            if delta.manhattanLength() > 4:
                self._dragged = True
            if self._dragged:
                self.pan = self._initial_pan + delta
                self._constrain_pan()
                self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Terminer le déplacement ; un clic sans glissement rétablit le cadrage entier."""
        if event.button() == Qt.LeftButton and self._press_position is not None:
            self._press_position = None
            self.setCursor(Qt.PointingHandCursor)
            if not self._dragged:
                self.reset_view()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """Reborner le déplacement après redimensionnement pour éviter les marges vides."""
        if self.is_book_art:
            self._constrain_pan()
        super().resizeEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Émettre activated sur double clic gauche ; le contrôleur ouvre la fenêtre indépendante."""
        if event.button() == Qt.LeftButton and self.is_book_art:
            self._press_position = None
            self.setCursor(Qt.PointingHandCursor)
            self.activated.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        """Dessiner illustration entière zoomée ou décor couvrant, puis cadre et ornements.

        L’illustration utilise min des rapports de taille pour ne pas être rognée ;
        le décor utilise max pour remplir la surface. Le clipping suit les coins arrondis."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        clip = QPainterPath()
        clip.addRoundedRect(box, 8, 8)
        painter.setClipPath(clip)
        painter.fillRect(box, QColor(self.theme.color("scene_background")))
        if not self.picture.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            scale = (self._fit_scale() * self.zoom if self.is_book_art else
                     max(self.width()/self.picture.width(), self.height()/self.picture.height()))
            width, height = self.picture.width()*scale, self.picture.height()*scale
            target = QRectF((self.width()-width)/2 + self.pan.x(),
                            (self.height()-height)/2 + self.pan.y(), width, height)
            painter.drawPixmap(target, self.picture, QRectF(self.picture.rect()))
        if not self.is_book_art:
            shade = QLinearGradient(0, self.height() / 2, 0, self.height())
            shade.setColorAt(0, QColor(20, 12, 8, 0))
            shade.setColorAt(1, QColor(20, 12, 8, 210))
            painter.fillRect(box, shade)
            painter.setPen(QColor(self.theme.color("gold")))
            painter.drawText(box.adjusted(18, 0, -18, -12),
                             Qt.AlignBottom | Qt.AlignLeft,
                             "✦  BIFURK")
        painter.setClipping(False)
        painter.setPen(QColor(self.theme.color("frame")))
        painter.drawRoundedRect(box, 8, 8)
        for x in (12, self.width() - 12):
            for y in (12, self.height() - 12):
                painter.save()
                painter.translate(x, y)
                painter.rotate(45)
                painter.fillRect(QRectF(-3, -3, 6, 6), QColor(self.theme.color("gold")))
                painter.restore()
