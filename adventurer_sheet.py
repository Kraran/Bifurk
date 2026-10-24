"""Fiche d'aventurier illustrée : widgets peints au QPainter (cuir, or patiné, sceaux).

Les widgets de données existants (QSpinBox, QListWidget…) restent les
sources de vérité de la fenêtre ; ce module ne fait que les habiller ou les dessiner
autrement. Aucun état de partie n'est stocké ici."""
import math
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QRect
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QBrush, QFont, QPixmap,
                           QLinearGradient, QRadialGradient, QFontMetrics, QPolygonF)
from PySide6.QtWidgets import (QWidget, QPushButton, QAbstractButton, QListWidget,
                               QStyledItemDelegate, QStyle, QListView, QVBoxLayout, QHBoxLayout,
                               QSizePolicy, QLabel)

GOLD = QColor('#d8b46c')
GOLD_LIGHT = QColor('#f4dc9e')
GOLD_DARK = QColor('#8a6633')
BORDEAUX = QColor('#7a2632')
BORDEAUX_DARK = QColor('#3d1218')
IVORY = QColor('#f5e7c6')
INK = QColor('#1b100c')
FONTS = {'title': 'EB Garamond', 'ui': 'Lato'}
LEATHER = Path(__file__).resolve().parent / 'assets/themes/grimoire/sheet-leather.png'


def font(kind, px, bold=False, italic=False, spacing=0):
    f = QFont(FONTS.get(kind, kind))
    f.setPixelSize(px)
    f.setBold(bold)
    f.setItalic(italic)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def _gold_gradient(rect):
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0, GOLD_LIGHT)
    g.setColorAt(.45, GOLD)
    g.setColorAt(1, GOLD_DARK)
    return g


def draw_diamond(p, center, r, color=GOLD):
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([QPointF(center.x(), center.y() - r), QPointF(center.x() + r, center.y()),
                             QPointF(center.x(), center.y() + r), QPointF(center.x() - r, center.y())]))


def gauge_ratio(current, maximum):
    """Taux de remplissage d'une jauge, borné à [0, 1] ; plein si le maximum est inconnu."""
    try:
        current, maximum = float(current), float(maximum)
    except (TypeError, ValueError):
        return 1.0
    if maximum <= 0:
        return 1.0 if current > 0 else 0.0
    return max(0.0, min(1.0, current / maximum))


def paint_shield_gauge(p, shape, area, tint, ratio):
    """Intérieur d'écu servant de jauge : creux sombre, puis couleur de la caractéristique
    montant du bas jusqu'à `ratio` de la hauteur, découpée à la forme de l'écu."""
    p.save()
    p.setPen(Qt.NoPen)
    hollow = QRadialGradient(area.center() - QPointF(0, area.height() * .2), area.width() * .85)
    hollow.setColorAt(0, tint.darker(320))
    hollow.setColorAt(1, QColor('#0d0706'))
    p.setBrush(hollow)
    p.drawPath(shape)
    if ratio > 0:
        level = area.bottom() - area.height() * ratio
        p.setClipPath(shape)
        p.setClipRect(QRectF(area.left() - 2, level, area.width() + 4, area.bottom() - level + 2), Qt.IntersectClip)
        g = QRadialGradient(area.center() - QPointF(0, area.height() * .2), area.width() * .85)
        g.setColorAt(0, tint.lighter(150))
        g.setColorAt(.6, tint)
        g.setColorAt(1, tint.darker(220))
        p.setBrush(g)
        p.drawPath(shape)
        if ratio < 1:
            # Ligne de niveau claire : la surface du « liquide ».
            p.setPen(QPen(tint.lighter(185), 1.4))
            p.drawLine(QPointF(area.left(), level + .7), QPointF(area.right(), level + .7))
    p.restore()


def draw_glyph(p, kind, c, s, color=IVORY):
    """Petits pictogrammes vectoriels (centre c, demi-taille s)."""
    pen = QPen(color, max(1.6, s * .16), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    x, y = c.x(), c.y()
    if kind == 'sword':
        p.drawLine(QPointF(x - s * .7, y + s * .7), QPointF(x + s * .75, y - s * .75))
        p.drawLine(QPointF(x - s * .55, y + s * .1), QPointF(x - s * .1, y + s * .55))
        p.drawLine(QPointF(x - s * .85, y + s * .85), QPointF(x - s * .65, y + s * .65))
    elif kind == 'swords':
        for sgn in (1, -1):
            p.drawLine(QPointF(x - s * .75 * sgn, y + s * .75), QPointF(x + s * .7 * sgn, y - s * .7))
            p.drawLine(QPointF(x - s * .6 * sgn, y + s * .2), QPointF(x - s * .2 * sgn, y + s * .6))
    elif kind == 'heart':
        path = QPainterPath(QPointF(x, y + s * .8))
        path.cubicTo(x - s * 1.2, y - s * .1, x - s * .55, y - s * 1.0, x, y - s * .35)
        path.cubicTo(x + s * .55, y - s * 1.0, x + s * 1.2, y - s * .1, x, y + s * .8)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPath(path)
    elif kind == 'clover':
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        r = s * .38
        for dx, dy in ((0, -.42), (.42, 0), (0, .42), (-.42, 0)):
            p.drawEllipse(QPointF(x + dx * s, y + dy * s), r, r)
        p.setPen(pen)
        p.drawLine(QPointF(x, y), QPointF(x + s * .5, y + s * .95))
    elif kind == 'cross':          # soins
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        w = s * .42
        p.drawRoundedRect(QRectF(x - w / 2, y - s * .8, w, s * 1.6), 2, 2)
        p.drawRoundedRect(QRectF(x - s * .8, y - w / 2, s * 1.6, w), 2, 2)
    elif kind == 'dice':
        p.drawRoundedRect(QRectF(x - s * .7, y - s * .7, s * 1.4, s * 1.4), s * .25, s * .25)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        for dx, dy in ((-.35, -.35), (.35, .35), (0, 0), (.35, -.35), (-.35, .35)):
            p.drawEllipse(QPointF(x + dx * s, y + dy * s), s * .12, s * .12)
    elif kind == 'quill':
        path = QPainterPath(QPointF(x - s * .8, y + s * .85))
        path.cubicTo(x - s * .2, y + s * .1, x + s * .2, y - s * .5, x + s * .85, y - s * .9)
        path.cubicTo(x + s * .5, y - s * .1, x + s * .1, y + s * .3, x - s * .8, y + s * .85)
        p.setBrush(color)
        p.drawPath(path)
        p.drawLine(QPointF(x - s * .9, y + s * .9), QPointF(x + s * .2, y - s * .15))
    elif kind == 'book':
        path = QPainterPath(QPointF(x, y - s * .45))
        path.cubicTo(x - s * .4, y - s * .75, x - s * .8, y - s * .7, x - s * .95, y - s * .55)
        path.lineTo(x - s * .95, y + s * .65)
        path.cubicTo(x - s * .6, y + s * .5, x - s * .3, y + s * .55, x, y + s * .8)
        path.cubicTo(x + s * .3, y + s * .55, x + s * .6, y + s * .5, x + s * .95, y + s * .65)
        path.lineTo(x + s * .95, y - s * .55)
        path.cubicTo(x + s * .8, y - s * .7, x + s * .4, y - s * .75, x, y - s * .45)
        p.drawPath(path)
        p.drawLine(QPointF(x, y - s * .45), QPointF(x, y + s * .8))
    elif kind == 'notebook':
        # Carnet fermé : couverture, dos, fermoir et ruban qui dépasse.
        body = QRectF(x - s * .7, y - s * .9, s * 1.4, s * 1.6)
        p.drawRoundedRect(body, s * .12, s * .12)
        p.drawLine(QPointF(x - s * .45, y - s * .9), QPointF(x - s * .45, y + s * .7))
        p.drawLine(QPointF(x - s * .2, y - s * .45), QPointF(x + s * .45, y - s * .45))
        p.drawLine(QPointF(x - s * .2, y - s * .15), QPointF(x + s * .45, y - s * .15))
        ribbon = QPainterPath(QPointF(x + s * .15, y + s * .7))
        ribbon.lineTo(x + s * .15, y + s * 1.05)
        ribbon.lineTo(x + s * .27, y + s * .93)
        ribbon.lineTo(x + s * .39, y + s * 1.05)
        ribbon.lineTo(x + s * .39, y + s * .7)
        p.setBrush(color)
        p.drawPath(ribbon)
        p.setBrush(Qt.NoBrush)
    else:
        draw_diamond(p, c, s * .6, color)


class SheetPanel(QWidget):
    """Fond de la fiche : cuir grainé, vignettage et double filet doré à fleurons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._leather = QPixmap(str(LEATHER))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        if not self._leather.isNull():
            p.drawPixmap(r.toRect(), self._leather)
        else:
            p.fillRect(r, QColor('#3e1e1b'))
        vignette = QRadialGradient(r.center(), max(r.width(), r.height()) * .75)
        vignette.setColorAt(.55, QColor(0, 0, 0, 0))
        vignette.setColorAt(1, QColor(0, 0, 0, 170))
        p.fillRect(r, vignette)
        outer = r.adjusted(3, 3, -3, -3)
        p.setPen(QPen(GOLD_DARK, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer, 10, 10)
        p.setPen(QPen(GOLD, 1.2))
        p.drawRoundedRect(outer.adjusted(5, 5, -5, -5), 7, 7)
        # Fleurons d'angle.
        for cx, cy, sx, sy in ((outer.left(), outer.top(), 1, 1), (outer.right(), outer.top(), -1, 1),
                               (outer.left(), outer.bottom(), 1, -1), (outer.right(), outer.bottom(), -1, -1)):
            p.setPen(QPen(GOLD, 1.6))
            p.setBrush(Qt.NoBrush)
            path = QPainterPath(QPointF(cx + sx * 9, cy + sy * 34))
            path.cubicTo(cx + sx * 9, cy + sy * 16, cx + sx * 16, cy + sy * 9, cx + sx * 34, cy + sy * 9)
            p.drawPath(path)
            p.drawArc(QRectF(cx + sx * 14 - 5, cy + sy * 14 - 5, 10, 10), 0, 360 * 16)
            draw_diamond(p, QPointF(cx + sx * 14, cy + sy * 14), 3.2, GOLD_LIGHT)
        # Fleuron central haut et bas.
        for y in (outer.top() + 2, outer.bottom() - 2):
            draw_diamond(p, QPointF(r.center().x(), y), 5, GOLD)


class OrnateHeading(QAbstractButton):
    """Titre de section en capitales : filets dorés, losanges ; cliquable si checkable."""

    def __init__(self, text, parent=None, *, checkable=False):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(checkable)
        if checkable:
            self.setChecked(True)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setFocusPolicy(Qt.NoFocus)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(200, 26)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        text = self.text().replace('&&', '&')
        f = font('title', 15, bold=True, spacing=2.2)
        p.setFont(f)
        w = QFontMetrics(f).horizontalAdvance(text)
        r = QRectF(self.rect())
        cy = r.center().y()
        cx = r.center().x()
        color = GOLD_LIGHT if self.underMouse() and self.isCheckable() else GOLD
        p.setPen(color)
        p.drawText(r, Qt.AlignCenter, text)
        left, right = cx - w / 2 - 12, cx + w / 2 + 12
        g = QLinearGradient(QPointF(10, cy), QPointF(left, cy))
        g.setColorAt(0, QColor(216, 180, 108, 0))
        g.setColorAt(1, GOLD)
        p.setPen(QPen(QBrush(g), 1.2))
        p.drawLine(QPointF(12, cy), QPointF(left - 4, cy))
        g2 = QLinearGradient(QPointF(right, cy), QPointF(r.right() - 10, cy))
        g2.setColorAt(0, GOLD)
        g2.setColorAt(1, QColor(216, 180, 108, 0))
        p.setPen(QPen(QBrush(g2), 1.2))
        p.drawLine(QPointF(right + 4, cy), QPointF(r.right() - 12, cy))
        draw_diamond(p, QPointF(left, cy), 3.5, color)
        draw_diamond(p, QPointF(right, cy), 3.5, color)


class HeroEmblem(QWidget):
    """Médaillon rond du héros : épées croisées sur fond bordeaux, anneau doré."""

    def __init__(self, size=58, parent=None):
        super().__init__(parent)
        self.full_size = size
        self.setFixedSize(size, size)

    def set_compact(self, compact):
        size = 42 if compact else self.full_size
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_gold_gradient(r)))
        p.drawEllipse(r)
        inner = r.adjusted(4, 4, -4, -4)
        g = QRadialGradient(inner.center() - QPointF(6, 8), inner.width() * .7)
        g.setColorAt(0, QColor('#a33a46'))
        g.setColorAt(1, BORDEAUX_DARK)
        p.setBrush(g)
        p.drawEllipse(inner)
        p.setPen(QPen(GOLD_DARK, 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(inner.adjusted(3, 3, -3, -3))
        draw_glyph(p, 'swords', inner.center(), inner.width() * .3, GOLD_LIGHT)


class StatMedallion(QWidget):
    """Blason (écu) contenant le QSpinBox de la caractéristique, rendu sans cadre.

    Le chiffre reste éditable (clavier / molette) ; la valeur initiale est peinte et
    l'intérieur de l'écu sert de jauge : sa couleur monte jusqu'à valeur / initiale."""

    GLYPHS = {'habilete': 'sword', 'endurance': 'heart', 'chance': 'clover'}
    TINTS = {'habilete': QColor('#7b5a22'), 'endurance': QColor('#8e2633'), 'chance': QColor('#2f5a43')}

    def __init__(self, key, label, spin, parent=None):
        super().__init__(parent)
        self.key, self.label, self.initial, self.compact = key, label, None, None
        self.current, self.maximum = None, None
        self.spin = spin
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(spin, 0, Qt.AlignCenter)
        self.set_compact(False)
        spin.setToolTip(f'{label.capitalize()} — molette ou clavier pour corriger')

    def set_compact(self, compact):
        """Version resserrée pour les fenêtres basses (≤ 720 px de haut)."""
        if compact == self.compact:
            return
        self.compact = compact
        self.setFixedHeight(110 if compact else 128)
        self.setMinimumWidth(92)
        self._layout.setContentsMargins(10, 33, 10, 37) if compact else self._layout.setContentsMargins(10, 44, 10, 30)
        self.spin.setFixedSize(68, 40 if compact else 44)
        self.updateGeometry()
        self.update()

    def set_initial(self, value):
        if value != self.initial:
            self.initial = value
            self.update()

    def set_gauge(self, current, maximum):
        """Niveau de la jauge : valeur courante sur valeur de départ."""
        if (current, maximum) != (self.current, self.maximum):
            self.current, self.maximum = current, maximum
            tip = f'{self.label.capitalize()} : {self.gauge_text()}'
            self.setToolTip(tip)
            self.spin.setToolTip(f'{tip} — molette ou clavier pour corriger')
            self.update()

    def ratio(self):
        return gauge_ratio(self.current, self.maximum) if self.current is not None else 1.0

    def gauge_text(self):
        return f'{self.current} / {self.maximum}' if self.current is not None else ''

    def sizeHint(self):
        return QSize(100, 128)

    def _shield(self, r):
        path = QPainterPath(QPointF(r.left(), r.top() + 6))
        path.quadTo(r.center().x(), r.top() - 6, r.right(), r.top() + 6)
        path.lineTo(r.right(), r.top() + r.height() * .5)
        path.cubicTo(r.right(), r.top() + r.height() * .8, r.center().x() + r.width() * .2,
                     r.bottom() - 6, r.center().x(), r.bottom())
        path.cubicTo(r.center().x() - r.width() * .2, r.bottom() - 6, r.left(),
                     r.top() + r.height() * .8, r.left(), r.top() + r.height() * .5)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = min(self.width() - 6, 96)
        r = QRectF((self.width() - w) / 2, 22, w, self.height() - 24)
        # Ombre portée.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawPath(self._shield(r.translated(0, 3)))
        p.setBrush(QBrush(_gold_gradient(r)))
        p.drawPath(self._shield(r))
        inner = r.adjusted(4, 4, -4, -5)
        tint = self.TINTS[self.key] if self.isEnabled() else QColor('#4a3f38')
        paint_shield_gauge(p, self._shield(inner), inner, tint, self.ratio())
        p.setPen(QPen(QColor(244, 220, 158, 120), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(self._shield(inner.adjusted(4, 4, -4, -5)))
        # Pictogramme en tête d'écu.
        if not self.compact:
            draw_glyph(p, self.GLYPHS[self.key], QPointF(inner.center().x(), inner.top() + 14), 7,
                       QColor(244, 220, 158, 230))
        # Nom de la caractéristique au-dessus.
        p.setFont(font('ui', 11, bold=True, spacing=1.6))
        p.setPen(GOLD)
        label = self.label
        if self.compact:   # pictogramme reporté à côté du nom
            fm = QFontMetrics(p.font())
            x = (self.width() - fm.horizontalAdvance(label)) / 2 - 10
            draw_glyph(p, self.GLYPHS[self.key], QPointF(x, 10), 5, GOLD)
            p.setPen(GOLD)
            p.setFont(font('ui', 11, bold=True, spacing=1.6))
        p.drawText(QRectF(0, 0, self.width(), 20), Qt.AlignCenter, label)
        # Valeur de départ.
        if self.initial is not None:
            p.setFont(font('title', 13, italic=True))
            p.setPen(QColor(244, 220, 158, 210))
            p.drawText(QRectF(inner.left(), inner.bottom() - (30 if self.compact else 34), inner.width(), 16), Qt.AlignCenter,
                       f'sur {self.initial}')


class ResourceToken(QWidget):
    """Plaque de ressource : pictogramme peint (pièces, pain, fiole) et gros chiffre."""

    def __init__(self, kind, caption, value_widget, parent=None):
        super().__init__(parent)
        self.kind, self.caption = kind, caption
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(46, 4, 6, 16)
        layout.addWidget(value_widget, 1, Qt.AlignVCenter)

    def sizeHint(self):
        return QSize(104, 58)

    def set_caption(self, caption):
        if caption != self.caption:
            self.caption = caption
            self.update()

    def _icon(self, p, c):
        if self.kind == 'gold':
            for i, dy in enumerate((9, 3, -3)):
                rect = QRectF(c.x() - 13 + (i % 2) * 2, c.y() + dy - 5, 26, 10)
                p.setPen(QPen(GOLD_DARK, 1))
                p.setBrush(QBrush(_gold_gradient(rect)))
                p.drawEllipse(rect)
            top = QRectF(c.x() - 11, c.y() - 15, 22, 22)
            p.setBrush(QBrush(_gold_gradient(top)))
            p.drawEllipse(top)
            p.setPen(QPen(GOLD_DARK, 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(top.adjusted(4, 4, -4, -4))
            draw_diamond(p, top.center(), 3, GOLD_DARK)
        elif self.kind == 'provisions':
            loaf = QRectF(c.x() - 15, c.y() - 9, 30, 20)
            g = QLinearGradient(loaf.topLeft(), loaf.bottomLeft())
            g.setColorAt(0, QColor('#e6b26a'))
            g.setColorAt(1, QColor('#8a4f22'))
            p.setPen(QPen(QColor('#5a3014'), 1.2))
            p.setBrush(g)
            p.drawRoundedRect(loaf, 10, 9)
            p.setPen(QPen(QColor('#fbe0a8'), 1.6, Qt.SolidLine, Qt.RoundCap))
            for dx in (-7, 0, 7):
                p.drawLine(QPointF(c.x() + dx - 3, c.y() - 4), QPointF(c.x() + dx + 3, c.y() + 2))
        else:  # potion
            neck = QRectF(c.x() - 3.5, c.y() - 16, 7, 9)
            body = QRectF(c.x() - 11, c.y() - 9, 22, 22)
            p.setPen(QPen(QColor('#cfe3e6'), 1.2))
            p.setBrush(QColor(200, 230, 235, 60))
            p.drawRect(neck)
            p.drawEllipse(body)
            liquid = QPainterPath()
            liquid.addEllipse(body.adjusted(2, 2, -2, -2))
            clip = QPainterPath()
            clip.addRect(QRectF(body.left(), body.center().y() - 1, body.width(), body.height()))
            g = QLinearGradient(body.topLeft(), body.bottomLeft())
            g.setColorAt(0, QColor('#e05a8a'))
            g.setColorAt(1, QColor('#6a1a4a'))
            p.setPen(Qt.NoPen)
            p.setBrush(g if self.isEnabled() and self.caption != 'AUCUNE POTION' else QColor('#4a3a38'))
            p.drawPath(liquid.intersected(clip))
            p.setBrush(QColor('#8a5a2a'))
            p.drawRect(QRectF(c.x() - 4.5, c.y() - 19, 9, 4))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor('#2a1410'))
        g.setColorAt(1, QColor('#170b09'))
        p.setPen(QPen(GOLD_DARK, 1.4))
        p.setBrush(g)
        p.drawRoundedRect(r, 9, 9)
        p.setPen(QPen(QColor(244, 220, 158, 50), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(3, 3, -3, -3), 7, 7)
        self._icon(p, QPointF(r.left() + 24, r.center().y() - 4))
        p.setFont(font('ui', 9, bold=True, spacing=1.2))
        p.setPen(GOLD)
        p.drawText(QRectF(r.left() + 4, r.bottom() - 16, r.width() - 8, 13), Qt.AlignCenter, self.caption)


class ValueLabel(QLabel):
    """Gros chiffre doré pour la plaque de potion (texte uniquement)."""

    def __init__(self, text='—', parent=None):
        super().__init__(text, parent)
        self.setObjectName('tokenValue')
        self.setAlignment(Qt.AlignCenter)


class SealButton(QPushButton):
    """Bouton-sceau : cachet de cire bordeaux cerclé d'or, pictogramme et légende."""

    def __init__(self, text, glyph, parent=None):
        super().__init__(text, parent)
        self.glyph = glyph
        self.compact = False
        self.mini = False
        self.urgent = False
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(82)

    def _height(self):
        return 46 if self.mini else (64 if self.compact else 82)

    def set_compact(self, compact):
        if compact != self.compact:
            self.compact = compact
            self.setFixedHeight(self._height())
            self.update()

    def set_mini(self, mini):
        """Sceau seul, sans légende (petits écrans) : le nom passe dans l'info-bulle."""
        mini = bool(mini)
        if mini != self.mini:
            self.mini = mini
            if mini and not self.toolTip():
                self.setToolTip(self.text().replace('&&', '&'))
                self._auto_tip = True
            elif not mini and getattr(self, '_auto_tip', False):
                self.setToolTip('')
                self._auto_tip = False
            self.setFixedHeight(self._height())
            self.update()

    def set_urgent(self, urgent):
        """Mettre le sceau en avant (halo et double anneau d'or) sans changer son action."""
        urgent = bool(urgent)
        if urgent != self.urgent:
            self.urgent = urgent
            self.update()

    def sizeHint(self):
        return QSize(52 if self.mini else 76, self.height())

    def minimumSizeHint(self):
        return QSize(44 if self.mini else 64, self._height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        hover = enabled and self.underMouse()
        down = self.isDown()
        if self.mini:
            c = QPointF(self.width() / 2, self.height() / 2 - 1 + (1 if down else 0))
            R = 17
        else:
            c = QPointF(self.width() / 2, (23 if self.compact else 30) + (1 if down else 0))
            R = 19 if self.compact else 25
        urgent = self.urgent and enabled
        if hover or self.hasFocus() or urgent:
            glow = QRadialGradient(c, R + 12)
            glow.setColorAt(.6, QColor(244, 210, 130, 170 if urgent else 110))
            glow.setColorAt(1, QColor(244, 210, 130, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(c, R + 12, R + 12)
        # Bord de cire irrégulier.
        poly = QPolygonF()
        for i in range(36):
            a = i / 36 * 2 * math.pi
            rr = R + 2.2 * math.sin(a * 7) + 1.3 * math.cos(a * 11)
            poly.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
        wax = QColor('#8f2534') if enabled else QColor('#4b403a')
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawPolygon(poly.translated(0, 3))
        g = QRadialGradient(c - QPointF(7, 9), R * 1.4)
        g.setColorAt(0, wax.lighter(150 if hover else 130))
        g.setColorAt(.6, wax)
        g.setColorAt(1, wax.darker(210))
        p.setBrush(g)
        p.drawPolygon(poly)
        ring = QRectF(c.x() - R + 6, c.y() - R + 6, 2 * R - 12, 2 * R - 12)
        p.setPen(QPen(GOLD if enabled else QColor('#8a7a66'), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ring)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawEllipse(ring.adjusted(3, 3, -3, -3))
        if urgent:
            p.setPen(QPen(GOLD_LIGHT, 2))
            p.drawEllipse(c, R + 5, R + 5)
        draw_glyph(p, self.glyph, c, 7 if self.mini else (8 if self.compact else 10),
                   GOLD_LIGHT if enabled else QColor('#a09080'))
        if self.mini:
            return
        caption = self.text().replace('&&', '&').replace('…', '')
        # Légende resserrée plutôt que tronquée quand cinq sceaux partagent la rangée.
        size, spacing = (10 if self.compact else 11), .6
        while size > 8 and QFontMetrics(font('ui', size, bold=True, spacing=spacing)).horizontalAdvance(caption) > self.width() - 2:
            size, spacing = size - 1, 0
        p.setFont(font('ui', size, bold=True, spacing=spacing))
        p.setPen(GOLD_LIGHT if hover else (GOLD if enabled else QColor('#8f826f')))
        p.drawText(QRectF(0, self.height() - 21, self.width(), 20), Qt.AlignCenter,
                   QFontMetrics(p.font()).elidedText(caption, Qt.ElideRight, self.width()))


class RibbonButton(QPushButton):
    """Bannière à queues d'aronde pour l'état de suivi de la partie."""

    def sizeHint(self):
        return QSize(220, 28)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 3, -4, -3)
        notch = 10
        path = QPainterPath(QPointF(r.left(), r.top()))
        path.lineTo(r.right(), r.top())
        path.lineTo(r.right() - notch, r.center().y())
        path.lineTo(r.right(), r.bottom())
        path.lineTo(r.left(), r.bottom())
        path.lineTo(r.left() + notch, r.center().y())
        path.closeSubpath()
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        base = QColor('#8a2a36') if self.underMouse() else QColor('#6c1f2a')
        g.setColorAt(0, base.lighter(130))
        g.setColorAt(1, base.darker(150))
        p.setPen(QPen(GOLD_DARK, 1.2))
        p.setBrush(g)
        p.drawPath(path)
        p.setFont(font('title', 14, italic=True, bold=True))
        p.setPen(GOLD_LIGHT)
        p.drawText(r, Qt.AlignCenter, f'❧  {self.text()}  ❧')


def _item_kind(name):
    text = str(name).casefold()
    for kind, words in (('key', ('clé',)), ('sword', ('épée', 'hache', 'piquet', 'dague', 'arme')),
                        ('armor', ('armure', 'cuirasse')), ('shield', ('bouclier',)),
                        ('potion', ('potion', 'bouteille', 'fiole')), ('lantern', ('lanterne', 'torche')),
                        ('food', ('provision', 'pain', 'repas')), ('coin', ('pièce', 'or '))):
        if any(word in text for word in words):
            return kind
    return 'gem'


def draw_item_art(p, kind, c, s):
    """Vignettes d'objets en couleurs (centre c, demi-taille s)."""
    steel = QLinearGradient(c - QPointF(s, s), c + QPointF(s, s))
    steel.setColorAt(0, QColor('#f2f2ee'))
    steel.setColorAt(1, QColor('#7d8590'))
    outline = QPen(QColor('#1a0f0a'), 1.2)
    p.setPen(outline)
    x, y = c.x(), c.y()
    if kind == 'sword':
        blade = QPolygonF([QPointF(x + s * .85, y - s * .85), QPointF(x + s * .55, y - s * .35),
                           QPointF(x - s * .3, y + s * .5), QPointF(x - s * .45, y + s * .35),
                           QPointF(x + s * .4, y - s * .5)])
        p.setBrush(steel)
        p.drawPolygon(blade)
        p.setBrush(QBrush(_gold_gradient(QRectF(x - s, y, s, s))))
        p.drawPolygon(QPolygonF([QPointF(x - s * .7, y + s * .15), QPointF(x - s * .6, y + s * .05),
                                 QPointF(x - s * .05, y + s * .6), QPointF(x - s * .15, y + s * .7)]))
        p.setBrush(QColor('#5b2a18'))
        p.drawPolygon(QPolygonF([QPointF(x - s * .45, y + s * .55), QPointF(x - s * .35, y + s * .45),
                                 QPointF(x - s * .7, y + s * .8), QPointF(x - s * .8, y + s * .7)]))
        p.setBrush(GOLD)
        p.drawEllipse(QPointF(x - s * .85, y + s * .85), s * .12, s * .12)
    elif kind in ('armor', 'shield'):
        path = QPainterPath(QPointF(x - s * .75, y - s * .7))
        if kind == 'armor':
            path.lineTo(x - s * .3, y - s * .85)
            path.quadTo(x, y - s * .55, x + s * .3, y - s * .85)
            path.lineTo(x + s * .75, y - s * .7)
            path.lineTo(x + s * .6, y + s * .2)
            path.lineTo(x + s * .5, y + s * .85)
            path.lineTo(x - s * .5, y + s * .85)
            path.lineTo(x - s * .6, y + s * .2)
        else:
            path.lineTo(x + s * .75, y - s * .7)
            path.lineTo(x + s * .7, y + s * .1)
            path.quadTo(x + s * .5, y + s * .7, x, y + s * .9)
            path.quadTo(x - s * .5, y + s * .7, x - s * .7, y + s * .1)
        path.closeSubpath()
        g = QLinearGradient(c - QPointF(s, s), c + QPointF(s, s))
        g.setColorAt(0, QColor('#b77942') if kind == 'armor' else QColor('#c9ccd0'))
        g.setColorAt(1, QColor('#5a3017') if kind == 'armor' else QColor('#5c6470'))
        p.setBrush(g)
        p.drawPath(path)
        p.setPen(QPen(QColor('#f2c98a') if kind == 'armor' else GOLD, 1.2, Qt.DashLine if kind == 'armor' else Qt.SolidLine))
        p.drawLine(QPointF(x, y - s * .55), QPointF(x, y + s * .7))
        if kind == 'shield':
            p.drawArc(QRectF(x - s * .35, y - s * .35, s * .7, s * .5), 200 * 16, 140 * 16)
    elif kind == 'lantern':
        glow = QRadialGradient(QPointF(x, y + s * .15), s * 1.1)
        glow.setColorAt(0, QColor(255, 214, 120, 200))
        glow.setColorAt(1, QColor(255, 180, 80, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(x, y + s * .15), s * 1.1, s * 1.1)
        p.setPen(QPen(QColor('#2a1a10'), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(x - s * .25, y - s * .95, s * .5, s * .45), 0, 180 * 16)
        p.setBrush(QColor('#4a3424'))
        p.drawRect(QRectF(x - s * .5, y - s * .6, s, s * .18))
        p.drawRect(QRectF(x - s * .5, y + s * .7, s, s * .18))
        p.setBrush(QColor(255, 226, 150, 220))
        p.drawRect(QRectF(x - s * .4, y - s * .42, s * .8, s * 1.12))
        p.setBrush(QColor('#ff9a2e'))
        p.setPen(Qt.NoPen)
        flame = QPainterPath(QPointF(x, y - s * .2))
        flame.quadTo(x + s * .22, y + s * .2, x, y + s * .4)
        flame.quadTo(x - s * .22, y + s * .2, x, y - s * .2)
        p.drawPath(flame)
    elif kind == 'potion':
        p.setBrush(QColor(210, 235, 240, 90))
        p.drawRect(QRectF(x - s * .16, y - s * .8, s * .32, s * .4))
        body = QRectF(x - s * .6, y - s * .45, s * 1.2, s * 1.25)
        p.drawEllipse(body)
        g = QLinearGradient(body.topLeft(), body.bottomLeft())
        g.setColorAt(0, QColor('#f06a9a'))
        g.setColorAt(1, QColor('#6e1546'))
        p.setBrush(g)
        p.setPen(Qt.NoPen)
        liquid = QPainterPath()
        liquid.addEllipse(body.adjusted(2, 2, -2, -2))
        clip = QPainterPath()
        clip.addRect(QRectF(body.left(), body.top() + body.height() * .38, body.width(), body.height()))
        p.drawPath(liquid.intersected(clip))
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(QRectF(x - s * .35, y - s * .25, s * .2, s * .32))
        p.setBrush(QColor('#8a5a2a'))
        p.drawRect(QRectF(x - s * .22, y - s * .95, s * .44, s * .2))
    elif kind == 'key':
        p.setPen(QPen(QBrush(_gold_gradient(QRectF(x - s, y - s, 2 * s, 2 * s))), s * .2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(x - s * .4, y - s * .4), s * .3, s * .3)
        p.drawLine(QPointF(x - s * .2, y - s * .2), QPointF(x + s * .7, y + s * .7))
        p.drawLine(QPointF(x + s * .45, y + s * .45), QPointF(x + s * .65, y + s * .25))
        p.drawLine(QPointF(x + s * .25, y + s * .25), QPointF(x + s * .45, y + s * .05))
    elif kind == 'food':
        p.setBrush(QColor('#c98a45'))
        p.drawRoundedRect(QRectF(x - s * .8, y - s * .4, s * 1.6, s * .9), s * .4, s * .4)
    elif kind == 'coin':
        p.setBrush(QBrush(_gold_gradient(QRectF(x - s * .6, y - s * .6, s * 1.2, s * 1.2))))
        p.drawEllipse(c, s * .6, s * .6)
    else:
        g = QLinearGradient(c - QPointF(s, s), c + QPointF(s, s))
        g.setColorAt(0, QColor('#9fd8c4'))
        g.setColorAt(1, QColor('#1f5a4a'))
        p.setBrush(g)
        p.drawPolygon(QPolygonF([QPointF(x, y - s * .8), QPointF(x + s * .7, y - s * .2), QPointF(x, y + s * .85),
                                 QPointF(x - s * .7, y - s * .2)]))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawLine(QPointF(x - s * .7, y - s * .2), QPointF(x + s * .7, y - s * .2))


SLOT = QSize(74, 90)
# Nombre d'exemplaires regroupés dans une même case de la sacoche.
INVENTORY_QUANTITY_ROLE = Qt.UserRole + 1


def _paint_quantity(p, r, quantity, compact=False):
    """Pastille de parchemin cerclée d'or, coin haut gauche : nombre d'exemplaires.

    Le coin haut droit reste à la marque de l'arme équipée."""
    if not quantity or int(quantity) < 2:
        return
    text = str(int(quantity)) if int(quantity) < 100 else '99+'
    size = 13 if compact else 17
    p.save()
    p.setFont(font('title', 10 if compact else 13, bold=True))
    width = max(size, QFontMetrics(p.font()).horizontalAdvance(text) + (5 if compact else 7))
    badge = QRectF(r.left() + (1 if compact else 2), r.top() + (1 if compact else 2), width, size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 120))
    p.drawRoundedRect(badge.translated(0, 1), size / 2, size / 2)
    fill = QLinearGradient(badge.topLeft(), badge.bottomLeft())
    fill.setColorAt(0, IVORY)
    fill.setColorAt(1, QColor('#d9c08a'))
    p.setBrush(QBrush(fill))
    p.setPen(QPen(GOLD_DARK, 1.2))
    p.drawRoundedRect(badge, size / 2, size / 2)
    p.setPen(BORDEAUX_DARK)
    p.drawText(badge.adjusted(0, -1 if compact else 0, 0, 0), Qt.AlignCenter, text)
    p.restore()


def _paint_slot(p, rect, filled, selected=False, equipped=False):
    r = QRectF(rect).adjusted(3, 3, -3, -3)
    g = QRadialGradient(r.center(), r.width() * .8)
    g.setColorAt(0, QColor('#3a2219') if filled else QColor('#24140f'))
    g.setColorAt(1, QColor('#140a07'))
    p.setBrush(g)
    p.setPen(QPen(GOLD_LIGHT if selected else (GOLD if equipped else QColor(138, 102, 51, 200 if filled else 120)),
                  2 if selected or equipped else 1.2))
    p.drawRoundedRect(r, 7, 7)
    p.setPen(QPen(QColor(0, 0, 0, 140), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r.adjusted(3, 3, -3, -3), 5, 5)
    if not filled:
        draw_diamond(p, r.center(), 3, QColor(138, 102, 51, 90))


class InventoryDelegate(QStyledItemDelegate):
    """Case d'inventaire : vignette colorée, nom abrégé, liseré doré si équipée."""

    def sizeHint(self, option, index):
        grid = self.parent().gridSize() if isinstance(self.parent(), QListView) else QSize()
        return grid if grid.isValid() else SLOT

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        name = index.data(Qt.DisplayRole) or ''
        equipped = 'Arme équipée' in (index.data(Qt.ToolTipRole) or '')
        selected = bool(option.state & QStyle.State_Selected)
        _paint_slot(p, option.rect, True, selected, equipped)
        r = QRectF(option.rect).adjusted(3, 3, -3, -3)
        if getattr(self.parent(), 'compact', False):
            # Case icône seule : le nom complet reste dans l'info-bulle de l'objet.
            draw_item_art(p, _item_kind(name), r.center(), 12)
            if equipped:
                badge = QRectF(r.right() - 12, r.top() + 2, 10, 10)
                p.setPen(Qt.NoPen)
                p.setBrush(BORDEAUX)
                p.drawEllipse(badge)
                draw_glyph(p, 'sword', badge.center(), 3.2, GOLD_LIGHT)
            _paint_quantity(p, r, index.data(INVENTORY_QUANTITY_ROLE), compact=True)
            p.restore()
            return
        draw_item_art(p, _item_kind(name), QPointF(r.center().x(), r.top() + 25), 17)
        p.setFont(font('ui', 10, bold=True))
        p.setPen(IVORY)
        box = QRectF(r.left() + 3, r.top() + 47, r.width() - 6, r.bottom() - r.top() - 50)
        metrics = QFontMetrics(p.font())
        if metrics.boundingRect(box.toRect(), Qt.AlignHCenter | Qt.TextWordWrap, name).height() > box.height():
            words, first = name.split(), ''
            while words and metrics.horizontalAdvance((first + ' ' + words[0]).strip()) <= box.width():
                first = (first + ' ' + words.pop(0)).strip()
            name = first + '\n' + metrics.elidedText(' '.join(words), Qt.ElideRight, int(box.width()))
        p.drawText(box, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, name)
        if equipped:
            badge = QRectF(r.right() - 17, r.top() + 3, 14, 14)
            p.setPen(Qt.NoPen)
            p.setBrush(BORDEAUX)
            p.drawEllipse(badge)
            draw_glyph(p, 'sword', badge.center(), 4.5, GOLD_LIGHT)
        _paint_quantity(p, r, index.data(INVENTORY_QUANTITY_ROLE))
        p.restore()


class InventoryGrid(QListWidget):
    """QListWidget en mode grille : cases vides peintes derrière les objets."""

    MIN_SLOTS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(SLOT)
        self.setSpacing(0)
        self.setFrameShape(QListWidget.NoFrame)
        self.setItemDelegate(InventoryDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.compact = False

    COMPACT_SLOT = 46

    def set_compact(self, compact):
        """Petits écrans : une rangée de petites cases icône seule (nom en info-bulle)."""
        compact = bool(compact)
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.setFixedHeight(self.COMPACT_SLOT + 4)
        else:
            self.setMinimumHeight(90)
            self.setMaximumHeight(16777215)
        self.setGridSize(self._slot_size()[0])
        self.doItemsLayout()
        self.viewport().update()

    def _slot_size(self):
        width = max(1, self.viewport().width() - (2 if self.compact else 10))
        if self.compact:
            cols = max(4, width // self.COMPACT_SLOT)
            return QSize(width // cols, self.COMPACT_SLOT), cols
        cols = max(3, width // SLOT.width())
        return QSize(width // cols, SLOT.height()), cols

    def resizeEvent(self, event):
        size, _ = self._slot_size()
        if size != self.gridSize():
            self.setGridSize(size)
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        size, cols = self._slot_size()
        rows = max(math.ceil(max(self.count(), 1 if self.compact else self.MIN_SLOTS) / cols),
                   math.ceil(self.viewport().height() / size.height()))
        offset = self.verticalOffset()
        for index in range(self.count(), rows * cols):
            row, col = divmod(index, cols)
            _paint_slot(p, QRect(col * size.width(), row * size.height() - offset, size.width(), size.height()), False)
        p.end()
        super().paintEvent(event)


class SheetStrip(QAbstractButton):
    """Fiche repliée en tiroir : bande verticale de cuir avec mini-blasons-jauges H/E/C,
    or et provisions. Un clic (ou Tab) déplie la fiche complète."""

    WIDTH = 78
    STATS = (('habilete', 'H'), ('endurance', 'E'), ('chance', 'C'))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sheetStrip')
        self._leather = QPixmap(str(LEATHER))
        self.state = {}
        self.setCheckable(True)
        self.setFixedWidth(self.WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self.setAccessibleName('Fiche d’aventurier')
        self._refresh_tooltip()

    def sizeHint(self):
        return QSize(self.WIDTH, 420)

    def minimumSizeHint(self):
        return QSize(self.WIDTH, 300)

    def set_state(self, **values):
        """values : habilete/endurance/chance = (valeur, initiale), gold, provisions."""
        if values != self.state:
            self.state = values
            self._refresh_tooltip()
            self.update()

    def _refresh_tooltip(self):
        st = self.state
        parts = []
        for key, name in (('habilete', 'Habileté'), ('endurance', 'Endurance'), ('chance', 'Chance')):
            value, initial = st.get(key, ('—', None))
            parts.append(f"{name} {value}" + (f"/{initial}" if initial is not None else ''))
        parts.append(f"Or {st.get('gold', '—')}")
        parts.append(f"Provisions {st.get('provisions', '—')}")
        action = 'Refermer' if self.isChecked() else 'Ouvrir'
        self.setToolTip(f"{action} la fiche d’aventurier (Tab)\n" + ' · '.join(parts))

    def nextCheckState(self):
        super().nextCheckState()
        self._refresh_tooltip()

    def checkStateSet(self):
        self._refresh_tooltip()

    def _mini_shield(self, p, r, key, value, initial):
        path = StatMedallion._shield(None, r)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawPath(StatMedallion._shield(None, r.translated(0, 2)))
        p.setBrush(QBrush(_gold_gradient(r)))
        p.drawPath(path)
        inner = r.adjusted(3, 3, -3, -4)
        tint = StatMedallion.TINTS[key] if self.isEnabled() else QColor('#4a3f38')
        ratio = gauge_ratio(value, initial) if initial is not None else 1.0
        paint_shield_gauge(p, StatMedallion._shield(None, inner), inner, tint, ratio)
        p.setPen(QPen(QColor(244, 220, 158, 110), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(StatMedallion._shield(None, inner.adjusted(3, 3, -3, -4)))
        draw_glyph(p, StatMedallion.GLYPHS[key], QPointF(inner.center().x(), inner.top() + 9), 4.2,
                   QColor(244, 220, 158, 230))
        p.setFont(font('title', 19, bold=True))
        p.setPen(QColor(0, 0, 0, 150))
        box = QRectF(inner.left(), inner.top() + 12, inner.width(), inner.height() - 20)
        p.drawText(box.translated(1, 1), Qt.AlignCenter, str(value))
        p.setPen(IVORY)
        p.drawText(box, Qt.AlignCenter, str(value))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 0, -1, 0)
        clip = QPainterPath()
        clip.addRoundedRect(r, 9, 9)
        p.setClipPath(clip)
        if not self._leather.isNull():
            p.drawPixmap(r.toRect(), self._leather)
        else:
            p.fillRect(r, QColor('#3e1e1b'))
        shade = QLinearGradient(r.topLeft(), r.topRight())
        shade.setColorAt(0, QColor(0, 0, 0, 150))
        shade.setColorAt(.25, QColor(0, 0, 0, 30))
        shade.setColorAt(1, QColor(0, 0, 0, 90))
        p.fillRect(r, shade)
        hover = self.underMouse()
        if hover:
            p.fillRect(r, QColor(244, 220, 158, 18))
        p.setClipping(False)
        outer = r.adjusted(2, 2, -2, -2)
        p.setPen(QPen(GOLD_DARK, 2.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer, 8, 8)
        p.setPen(QPen(GOLD if not hover else GOLD_LIGHT, 1))
        p.drawRoundedRect(outer.adjusted(4, 4, -4, -4), 5, 5)
        cx = r.center().x()
        # Languette : chevron d'ouverture dans un médaillon.
        c = QPointF(cx, outer.top() + 24)
        p.setPen(QPen(GOLD_LIGHT if hover else GOLD, 1.6))
        p.setBrush(BORDEAUX_DARK)
        p.drawEllipse(c, 13, 13)
        p.setPen(QPen(GOLD_LIGHT, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        k = -1 if self.isChecked() else 1   # ‹ pour ouvrir (la fiche sort vers la gauche)
        p.drawPolyline(QPolygonF([QPointF(c.x() + 3 * k, c.y() - 6), QPointF(c.x() - 3 * k, c.y()),
                                  QPointF(c.x() + 3 * k, c.y() + 6)]))
        y = c.y() + 22
        draw_diamond(p, QPointF(cx, y), 3, GOLD)
        y += 10
        st = self.state
        sw, sh = 48, 54
        for key, _letter in self.STATS:
            value, initial = st.get(key, ('—', None))
            self._mini_shield(p, QRectF(cx - sw / 2, y, sw, sh), key, value, initial)
            y += sh + 2
            if initial is not None:
                p.setFont(font('title', 12, italic=True))
                p.setPen(QColor(244, 220, 158, 200))
                p.drawText(QRectF(r.left(), y, r.width(), 15), Qt.AlignCenter, f'sur {initial}')
            y += 19
        y += 4
        # Or et provisions.
        for kind in ('gold', 'provisions'):
            if y + 36 > outer.bottom() - 6:
                break
            box = QRectF(outer.left() + 7, y, outer.width() - 14, 34)
            p.setPen(QPen(GOLD_DARK, 1))
            p.setBrush(QColor(20, 10, 8, 170))
            p.drawRoundedRect(box, 7, 7)
            p.save()
            p.translate(box.left() + 17, box.center().y() + 1)
            p.scale(.62, .62)
            _paint_resource_icon(p, kind)
            p.restore()
            p.setFont(font('title', 17, bold=True))
            p.setPen(GOLD_LIGHT)
            p.drawText(box.adjusted(30, 0, -4, 0), Qt.AlignVCenter | Qt.AlignHCenter, str(st.get(kind, '—')))
            y += 40
        # Titre vertical si la place le permet.
        free = outer.bottom() - 14 - y
        if free > 70:
            p.save()
            p.translate(cx, y + free / 2)
            p.rotate(-90)
            p.setFont(font('title', 13, bold=True, spacing=3))
            p.setPen(GOLD)
            p.drawText(QRectF(-free / 2, -10, free, 20), Qt.AlignCenter, 'FICHE')
            p.restore()
            draw_diamond(p, QPointF(cx, outer.bottom() - 4), 3, GOLD)


def _paint_resource_icon(p, kind):
    """Dessiner l'icône de ressource (pièces ou pain) centrée sur l'origine."""
    class _Fake:
        pass
    fake = _Fake()
    fake.kind, fake.caption = kind, ''
    fake.isEnabled = lambda: True
    ResourceToken._icon(fake, p, QPointF(0, 0))
