"""Illustrated, resizable surfaces for the Grimoire desktop theme."""
from themes import default_theme
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPixmap, QIcon, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QSizePolicy, QStyleOptionButton, QStyle, QDialog


class IllustrationDialog(QDialog):
    """Resizable illustration window with native maximize and an explicit size reset."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                         | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.default_size = QSize(640, 600)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def restore_default_size(self):
        self.showNormal()
        self.resize(self.default_size)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.restore_default_size()
            event.accept()
        else:
            super().keyPressEvent(event)


class IlluminatedPage(QWidget):
    """A book page with painted corner flourishes, independent of native controls."""

    def __init__(self, texture_path=None, parent=None, theme=None):
        super().__init__(parent)
        self.theme = theme or default_theme()
        self.texture = QPixmap(str(texture_path)) if texture_path else QPixmap()

    def set_theme(self, theme):
        self.theme = theme
        self.texture = QPixmap(str(theme.assets['parchment']))
        self.update()

    def paintEvent(self, event):
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
        self.theme = theme
        self.atmosphere = QPixmap(str(theme.assets['scene']))
        if not self.is_book_art:
            self.picture = self.atmosphere
        self.update()

    def sizeHint(self):
        return QSize(300, 640)

    def set_book_art(self, pixmap=None):
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
        self.zoom = 1.0
        self.pan = QPointF()
        self.update()

    def _fit_scale(self):
        return min(max(1, self.width()-4) / max(1, self.picture.width()),
                   max(1, self.height()-4) / max(1, self.picture.height()))

    def _constrain_pan(self):
        scale = self._fit_scale() * self.zoom
        limit_x = max(0, (self.picture.width() * scale - (self.width()-4)) / 2)
        limit_y = max(0, (self.picture.height() * scale - (self.height()-4)) / 2)
        self.pan = QPointF(max(-limit_x, min(limit_x, self.pan.x())),
                           max(-limit_y, min(limit_y, self.pan.y())))

    def wheelEvent(self, event):
        if not self.is_book_art:
            super().wheelEvent(event)
            return
        steps = event.angleDelta().y() / 120 or event.pixelDelta().y() / 120
        previous = self.zoom
        self.zoom = max(1.0, min(12.0, previous * 1.2 ** steps))
        anchor = event.position() - QPointF(self.width()/2, self.height()/2)
        self.pan = anchor - (anchor - self.pan) * (self.zoom / previous)
        self._constrain_pan()
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_book_art:
            self._press_position = event.position()
            self._initial_pan = QPointF(self.pan)
            self._dragged = False
            self.setCursor(Qt.CrossCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
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
        if event.button() == Qt.LeftButton and self._press_position is not None:
            self._press_position = None
            self.setCursor(Qt.PointingHandCursor)
            if not self._dragged:
                self.reset_view()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        if self.is_book_art:
            self._constrain_pan()
        super().resizeEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_book_art:
            self._press_position = None
            self.setCursor(Qt.PointingHandCursor)
            self.activated.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
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
