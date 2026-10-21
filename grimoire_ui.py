"""Illustrated, resizable surfaces for the Grimoire desktop theme."""
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPixmap, QIcon, QPen
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QSizePolicy, QStyleOptionButton, QStyle


class IlluminatedPage(QWidget):
    """A book page with painted corner flourishes, independent of native controls."""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        page = QPainterPath()
        page.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.setClipPath(page)
        p.fillPath(page, QColor("#ead9b8"))
        p.setPen(QPen(QColor("#ad8950"), 1.2))
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
            p.setBrush(QColor("#79313b"))
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


def inventory_icon(name):
    """Small vector emblems stay sharp and work without platform emoji fonts."""
    canvas = QPixmap(48, 48)
    canvas.fill(Qt.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#ba9459"), 1.5))
    p.setBrush(QColor("#4b2925"))
    p.drawRoundedRect(2, 2, 44, 44, 7, 7)
    p.setPen(QPen(QColor("#f5d89c"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
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

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
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
        painter.fillRect(box, QColor("#201811"))
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
            painter.setPen(QColor("#f5db9e"))
            painter.drawText(box.adjusted(18, 0, -18, -12),
                             Qt.AlignBottom | Qt.AlignLeft,
                             "✦  BIFURK")
        painter.setClipping(False)
        painter.setPen(QColor("#bb9455"))
        painter.drawRoundedRect(box, 8, 8)
        for x in (12, self.width() - 12):
            for y in (12, self.height() - 12):
                painter.save()
                painter.translate(x, y)
                painter.rotate(45)
                painter.fillRect(QRectF(-3, -3, 6, 6), QColor("#dfbf7c"))
                painter.restore()


GRIMOIRE_STYLE = """
QSpinBox#heroValue { background: #4e2925; color: #ffe4a7; border: 1px solid #a7804d;
    font-size: 28px; font-family: 'EB Garamond'; padding: 5px; }
QSpinBox#heroValue QLineEdit { background: transparent; color: #ffe4a7; border: none; padding: 0; }
QScrollArea#pageScroll { background: transparent; border: none; }
QWidget#readerPanel { background: #ead9b8; border: 1px solid #b49360; border-radius: 9px; }
QWidget#sidePanel { background: #281b17; border: 1px solid #89653d; border-radius: 9px; }
QFrame#grimoireHeader { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #642a2e,stop:1 #35151c);
    border: 1px solid #b18a4e; border-bottom: 3px double #d6ad69; border-radius: 6px; }
QLabel#appTitle { font-family: 'EB Garamond'; font-size: 31px; color: #ffe2a3; }
QLabel#sectionTitle { font-family: 'EB Garamond'; color: #642a2e; font-size: 27px; }
QLabel#subtitle { color: #ddbd83; }
QLabel#bookName { color: #efd9b2; }
QTextBrowser#reader { background: #f6ecd6; background-image: none; color: #30241b;
    border: 1px solid #c9ac7c; border-left: 4px double #b49360; border-radius: 3px; padding: 18px 24px; }
QWidget#readerPanel QGroupBox { background: #f3e6ca; color: #642a2e;
    border: 1px solid #b49360; margin-top: 14px; padding-top: 12px; }
QWidget#readerPanel QGroupBox::title { background: #f3e6ca; color: #642a2e; }
QWidget#readerPanel QLabel { color: #4c3528; }
QWidget#readerPanel QPushButton { background: #e9d4ab; color: #442a1e; border: 1px solid #a67e45; }
QWidget#readerPanel QPushButton:hover { background: #fcecc9; border: 1px solid #71313a; }
QWidget#readerPanel QPushButton#choiceCard { text-align: left; padding: 13px 16px;
    border-left: 4px solid #843741; font-size: 14px; }
QPushButton:focus { border: 2px solid #efc568; }
QWidget#readerPanel QPushButton:focus { border: 2px solid #74313a; }
QWidget#readerPanel QPushButton:disabled { color: #8a7963; border-color: #c5b89f; }
QTabWidget#adventureTabs::pane { border: 1px solid #87633b; background: #30211a; border-radius: 4px; }
QTabBar::tab { background: #35231d; color: #cbb18b; padding: 10px 12px; border: 1px solid #795536; }
QTabBar::tab:selected { background: #6c2f36; color: #ffe7b1; border-bottom: 2px solid #d9b16b; }
QTabBar::tab:hover { color: #fff0cb; background: #51312a; }
QLabel#heroCrest { background: #55262c; border: 3px double #d1ad69; border-radius: 30px;
    color: #f9dda0; font-size: 30px; min-width: 60px; min-height: 60px; }
QLabel#heroTitle { font-family: 'EB Garamond'; font-size: 23px; color: #f6d99f; }
QProgressBar#enduranceBar::chunk { background: #963c46; }
QProgressBar#chanceBar::chunk { background: #52705b; }
QProgressBar#habileteBar::chunk { background: #a7803e; }
QListWidget#inventoryCards { background: #35251c; border: none; padding: 4px; }
QListWidget#inventoryCards::item { background: #eeddbc; color: #432d20; border: 1px solid #ad8953;
    border-radius: 5px; margin: 3px; padding: 12px; }
QListWidget#inventoryCards::item:selected { background: #76343c; color: #fff0cd; border-color: #e7bf78; }
QPushButton#combatButton { background: #7c303b; color: #fff0cd; padding: 15px; border: 2px solid #bd9154; }
QPushButton#combatButton:hover { background: #9a414d; }
"""

# The margins belong to the frame, not to the text: titles cannot touch controls.
GRIMOIRE_STYLE += """
QGroupBox { margin-top: 22px; padding: 22px 10px 10px; }
QGroupBox::title { top: 3px; left: 14px; padding: 2px 8px; }
QWidget#readerPanel QGroupBox { margin-top: 22px; padding: 22px 10px 10px; }
QLabel#inventoryHeading { color: #f1d49a; padding: 6px 0 10px; font-weight: bold; }
QFrame#inventoryPanel { background: #30221a; border: none; }
QListWidget#inventoryCards { padding: 0; background: #30221a; }
QListWidget#inventoryCards::item { margin: 1px 0; padding: 4px 6px; border: 1px solid #8d6d44; }
QWidget#readerPanel { border: 4px double #a68149; border-radius: 2px; }
QTextBrowser#reader { border: none; background: #f5e8ce; padding: 12px 16px; }
QWidget#readerPanel QPushButton#choiceCard { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #f9edce, stop:1 #dfc08c); border: 3px double #9d743c; border-left: 5px solid #823842; }
QWidget#readerPanel QPushButton#choiceCard:hover { background: #fff1c8; border-color: #6f2933; }
QSpinBox#heroValue { font-size: 24px; background: #55252c; border: 3px double #c6a064; }
QSpinBox#heroValue::up-button, QSpinBox#heroValue::down-button { width: 0; height: 0; border: none; }
QWidget#sidePanel QSpinBox { background: #422a23; color: #f9e2b2; border: 1px solid #a88652; }
QWidget#sidePanel QSpinBox QLineEdit { background: transparent; color: #f9e2b2; border: none; }
QWidget#sidePanel QComboBox { background: #422a23; color: #f9e2b2; padding: 7px; }
QTabBar::tab { padding: 12px 10px; }
QWidget#readerPanel { border-radius: 12px; }
QTextBrowser#reader { border-radius: 10px; }
QWidget#readerPanel QPushButton#choiceCard { border-radius: 8px; }
QFrame#inventoryPanel, QListWidget#inventoryCards { border-radius: 8px; }
QWidget#sidePanel QSpinBox, QWidget#sidePanel QComboBox { border-radius: 7px; }
QTabWidget#adventureTabs::pane { border-radius: 8px; }
QTabBar::tab { border-top-left-radius: 8px; border-top-right-radius: 8px; }
"""
