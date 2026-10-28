"""Habillage peint du centre et du bandeau : cadres dorés, médaillons, cartouches, lettrines.

Même vocabulaire graphique que la fiche (adventurer_sheet) : cuir bordeaux, or vieilli,
ivoire, EB Garamond / Lato. Les widgets restent des QPushButton/QLabel/QGroupBox standard :
textes, menus, info-bulles, raccourcis et accessibilité ne changent pas, seul le dessin change."""
import math

from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QBrush, QImage,
                           QLinearGradient, QRadialGradient, QFontMetrics, QPolygonF)
from PySide6.QtWidgets import QFrame, QPushButton, QLabel, QGroupBox, QWidget, QSizePolicy

from adventurer_sheet import (GOLD, GOLD_LIGHT, GOLD_DARK, BORDEAUX, BORDEAUX_DARK,
                              LEATHER, font, draw_diamond, draw_glyph)
from theme_palette import pixmap as theme_pixmap, tint

RUBRIC = QColor('#7a2632')
PAGE_INK = QColor('#2e1d14')
BRONZE = QColor('#9c7440')


# --------------------------------------------------------------------------- ornements
def draw_corner_fleurons(p, outer, color=None, light=None, size=34):
    """Volutes d'angle de la fiche (réutilisées par la page, l'illustration et le bandeau)."""
    color = GOLD if color is None else color
    light = GOLD_LIGHT if light is None else light
    k = size / 34
    for cx, cy, sx, sy in ((outer.left(), outer.top(), 1, 1), (outer.right(), outer.top(), -1, 1),
                           (outer.left(), outer.bottom(), 1, -1), (outer.right(), outer.bottom(), -1, -1)):
        p.setPen(QPen(color, 1.6))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(cx + sx * 9 * k, cy + sy * 34 * k))
        path.cubicTo(cx + sx * 9 * k, cy + sy * 16 * k, cx + sx * 16 * k, cy + sy * 9 * k,
                     cx + sx * 34 * k, cy + sy * 9 * k)
        p.drawPath(path)
        p.drawEllipse(QPointF(cx + sx * 14 * k, cy + sy * 14 * k), 5 * k, 5 * k)
        draw_diamond(p, QPointF(cx + sx * 14 * k, cy + sy * 14 * k), 3.2 * k, light)


def draw_gold_frame(p, rect, radius=10, *, fleurons=True, diamonds=True, size=34):
    """Double filet doré (épais sombre + fin clair) à fleurons, comme la fiche."""
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(GOLD_DARK, 3))
    p.drawRoundedRect(rect, radius, radius)
    p.setPen(QPen(GOLD, 1.2))
    p.drawRoundedRect(rect.adjusted(5, 5, -5, -5), max(2, radius - 3), max(2, radius - 3))
    if fleurons:
        draw_corner_fleurons(p, rect, size=size)
    if diamonds:
        for y in (rect.top() + 2, rect.bottom() - 2):
            draw_diamond(p, QPointF(rect.center().x(), y), 5, GOLD)


def draw_leaf(p, c, s, angle, color):
    p.save()
    p.translate(c)
    p.rotate(angle)
    path = QPainterPath(QPointF(0, 0))
    path.cubicTo(s * .35, -s * .32, s * .8, -s * .22, s, 0)
    path.cubicTo(s * .8, s * .22, s * .35, s * .32, 0, 0)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)
    p.restore()


def draw_fleuron_rule(p, cx, cy, half, color=None, accent=None):
    """Filet de séparation à fleuron central : lignes fondues, volutes, feuilles et losange."""
    color = GOLD_DARK if color is None else color
    accent = RUBRIC if accent is None else accent
    fade = QColor(color)
    fade.setAlpha(0)
    for sgn in (-1, 1):
        g = QLinearGradient(QPointF(cx + sgn * half, cy), QPointF(cx + sgn * 30, cy))
        g.setColorAt(0, fade)
        g.setColorAt(1, color)
        p.setPen(QPen(QBrush(g), 1.3))
        p.drawLine(QPointF(cx + sgn * half, cy), QPointF(cx + sgn * 30, cy))
        p.setPen(QPen(QBrush(g), .8))
        p.drawLine(QPointF(cx + sgn * half * .7, cy + 4), QPointF(cx + sgn * 40, cy + 4))
        # Volute en S puis feuille.
        p.setPen(QPen(color, 1.4))
        p.setBrush(Qt.NoBrush)
        curl = QPainterPath(QPointF(cx + sgn * 30, cy))
        curl.cubicTo(cx + sgn * 22, cy - 9, cx + sgn * 12, cy - 6, cx + sgn * 14, cy)
        curl.cubicTo(cx + sgn * 16, cy + 5, cx + sgn * 22, cy + 3, cx + sgn * 20, cy - 1)
        p.drawPath(curl)
        draw_leaf(p, QPointF(cx + sgn * 30, cy), 9, -90 + sgn * 60 if sgn > 0 else 180 + 30, color)
        draw_diamond(p, QPointF(cx + sgn * 37, cy), 2.2, color)
    draw_diamond(p, QPointF(cx, cy), 5.5, accent)
    draw_diamond(p, QPointF(cx, cy), 2.2, GOLD_LIGHT)


def draw_wax_seal(p, c, r, *, color=None, ring=None, bumps=14):
    """Sceau de cire au bord festonné, reflet et anneau doré."""
    color = BORDEAUX if color is None else color
    ring = GOLD if ring is None else ring
    poly = QPolygonF()
    for i in range(bumps * 2):
        a = math.pi * i / bumps
        rr = r * (1.0 if i % 2 == 0 else .9)
        poly.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
    g = QRadialGradient(QPointF(c.x() - r * .35, c.y() - r * .4), r * 1.4)
    g.setColorAt(0, color.lighter(150))
    g.setColorAt(.55, color)
    g.setColorAt(1, color.darker(190))
    p.setPen(QPen(color.darker(220), 1))
    p.setBrush(g)
    p.drawPolygon(poly)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(ring, 1.4))
    p.drawEllipse(c, r * .72, r * .72)


# --------------------------------------------------------------------------- pictogrammes
def draw_icon(p, kind, c, s, color=None):
    """Pictogrammes du bandeau et des outils de page ; repli sur ceux de la fiche."""
    color = GOLD_LIGHT if color is None else color
    pen = QPen(color, max(1.5, s * .15), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    x, y = c.x(), c.y()
    if kind in ('undo', 'redo'):
        sgn = 1 if kind == 'undo' else -1
        path = QPainterPath(QPointF(x - sgn * s * .55, y - s * .25))
        path.cubicTo(x - sgn * s * .1, y - s * .75, x + sgn * s * .85, y - s * .55, x + sgn * s * .75, y + s * .15)
        path.cubicTo(x + sgn * s * .65, y + s * .65, x + sgn * s * .1, y + s * .8, x - sgn * s * .35, y + s * .6)
        p.drawPath(path)
        head = QPolygonF([QPointF(x - sgn * s * .85, y - s * .55), QPointF(x - sgn * s * .45, y + s * .1),
                          QPointF(x - sgn * s * .1, y - s * .5)])
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPolygon(head)
    elif kind == 'map':
        pts = [QPointF(x - s * .9, y - s * .55), QPointF(x - s * .3, y - s * .8), QPointF(x + s * .3, y - s * .55),
               QPointF(x + s * .9, y - s * .8), QPointF(x + s * .9, y + s * .55), QPointF(x + s * .3, y + s * .8),
               QPointF(x - s * .3, y + s * .55), QPointF(x - s * .9, y + s * .8)]
        p.drawPolygon(QPolygonF(pts))
        p.setPen(QPen(color, max(1, s * .08)))
        p.drawLine(pts[1], pts[6])
        p.drawLine(pts[2], pts[5])
        dash = QPen(color, max(1.2, s * .1), Qt.DotLine, Qt.RoundCap)
        p.setPen(dash)
        route = QPainterPath(QPointF(x - s * .65, y + s * .35))
        route.cubicTo(x - s * .3, y - s * .1, x + s * .1, y + s * .4, x + s * .45, y - s * .2)
        p.drawPath(route)
        p.setPen(QPen(color, max(1.4, s * .13), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x + s * .45, y - s * .45), QPointF(x + s * .7, y - s * .2))
        p.drawLine(QPointF(x + s * .7, y - s * .45), QPointF(x + s * .45, y - s * .2))
    elif kind == 'scroll':
        body = QRectF(x - s * .6, y - s * .6, s * 1.2, s * 1.2)
        p.drawRect(body)
        p.drawEllipse(QRectF(x - s * .85, y - s * .85, s * 1.7, s * .4))
        p.drawEllipse(QRectF(x - s * .85, y + s * .45, s * 1.7, s * .4))
        p.setPen(QPen(color, max(1, s * .09)))
        for k in (-.25, 0, .25):
            p.drawLine(QPointF(x - s * .35, y + k * s), QPointF(x + s * .35, y + k * s))
    elif kind == 'books':
        draw_glyph(p, 'book', QPointF(x, y + s * .15), s * .95, color)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        star = QPainterPath()
        sx, sy, r = x, y - s * .72, s * .32
        for i in range(8):
            a = math.pi * i / 4 - math.pi / 2
            rr = r if i % 2 == 0 else r * .35
            pt = QPointF(sx + rr * math.cos(a), sy + rr * math.sin(a))
            star.moveTo(pt) if i == 0 else star.lineTo(pt)
        star.closeSubpath()
        p.drawPath(star)
    elif kind == 'gear':
        teeth = 8
        poly = QPolygonF()
        for i in range(teeth * 4):
            a = 2 * math.pi * i / (teeth * 4)
            rr = s * (.92 if (i % 4) in (0, 1) else .66)
            poly.append(QPointF(x + rr * math.cos(a), y + rr * math.sin(a)))
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addPolygon(poly)
        hole = QPainterPath()
        hole.addEllipse(c, s * .3, s * .3)
        p.drawPath(path.subtracted(hole))
    elif kind in ('image', 'image_off'):
        frame = QRectF(x - s * .85, y - s * .65, s * 1.7, s * 1.3)
        p.drawRoundedRect(frame, s * .12, s * .12)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(x + s * .4, y - s * .25), s * .15, s * .15)
        p.drawPolygon(QPolygonF([QPointF(x - s * .7, y + s * .5), QPointF(x - s * .2, y - s * .15),
                                 QPointF(x + s * .15, y + s * .25), QPointF(x + s * .35, y + s * .05),
                                 QPointF(x + s * .7, y + s * .5)]))
        if kind == 'image_off':
            p.setPen(QPen(color, max(1.8, s * .17), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x - s * .95, y + s * .85), QPointF(x + s * .95, y - s * .85))
    elif kind == 'cover':
        body = QRectF(x - s * .62, y - s * .82, s * 1.3, s * 1.64)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body, s * .1, s * .1)
        p.drawLine(QPointF(body.left() + s * .25, body.top()), QPointF(body.left() + s * .25, body.bottom()))
        draw_diamond(p, QPointF(x + s * .12, y - s * .1), s * .3, color)
        p.setPen(pen)
        p.drawLine(QPointF(x - s * .15, y + s * .45), QPointF(x + s * .4, y + s * .45))
    elif kind in ('font_minus', 'font_plus'):
        f = font('title', int(s * 1.55), bold=True)
        p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(x - s * 1.05, y - s, s * 1.4, s * 2), Qt.AlignCenter, 'A')
        p.setPen(QPen(color, max(1.5, s * .15), Qt.SolidLine, Qt.RoundCap))
        hx, hy, hw = x + s * .6, y - s * .25, s * .3
        p.drawLine(QPointF(hx - hw, hy), QPointF(hx + hw, hy))
        if kind == 'font_plus':
            p.drawLine(QPointF(hx, hy - hw), QPointF(hx, hy + hw))
    elif kind == 'close':
        p.drawLine(QPointF(x - s * .6, y - s * .6), QPointF(x + s * .6, y + s * .6))
        p.drawLine(QPointF(x - s * .6, y + s * .6), QPointF(x + s * .6, y - s * .6))
    elif kind == 'arrow':
        p.drawLine(QPointF(x - s, y), QPointF(x + s * .7, y))
        head = QPolygonF([QPointF(x + s, y), QPointF(x + s * .35, y - s * .45), QPointF(x + s * .5, y),
                          QPointF(x + s * .35, y + s * .45)])
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPolygon(head)
        # Empennage façon plume.
        p.setPen(QPen(color, max(1, s * .1), Qt.SolidLine, Qt.RoundCap))
        for k in (0, .28):
            p.drawLine(QPointF(x - s + k * s, y), QPointF(x - s * 1.2 + k * s, y - s * .35))
            p.drawLine(QPointF(x - s + k * s, y), QPointF(x - s * 1.2 + k * s, y + s * .35))
    elif kind == 'speaker':
        # Haut-parleur et deux ondes : lecture vocale du paragraphe.
        body = QPolygonF([QPointF(x - s * .95, y - s * .3), QPointF(x - s * .55, y - s * .3),
                          QPointF(x - s * .05, y - s * .75), QPointF(x - s * .05, y + s * .75),
                          QPointF(x - s * .55, y + s * .3), QPointF(x - s * .95, y + s * .3)])
        p.drawPolygon(body)
        for k in (.45, .85):
            p.drawArc(QRectF(x - s * .05 - s * k, y - s * k, s * k * 2, s * k * 2), -50 * 16, 100 * 16)
    elif kind == 'speaker_stop':
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(x - s * .55, y - s * .55, s * 1.1, s * 1.1), s * .12, s * .12)
    elif kind == 'music':
        # Deux croches liées : réglages des ambiances (sons, musique, voix).
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        for hx in (x - s * .55, x + s * .45):
            p.drawEllipse(QPointF(hx, y + s * .55), s * .3, s * .22)
        p.setPen(QPen(color, max(1.4, s * .13), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x - s * .27, y + s * .5), QPointF(x - s * .27, y - s * .65))
        p.drawLine(QPointF(x + s * .73, y + s * .5), QPointF(x + s * .73, y - s * .85))
        beam = QPolygonF([QPointF(x - s * .27, y - s * .65), QPointF(x + s * .73, y - s * .85),
                          QPointF(x + s * .73, y - s * .55), QPointF(x - s * .27, y - s * .35)])
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPolygon(beam)
    elif kind == 'fullscreen':
        k = s * .38
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cx, cy = x + sx * s * .85, y + sy * s * .7
            p.drawLine(QPointF(cx, cy), QPointF(cx - sx * k, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy - sy * k))
    elif kind == 'reading':
        draw_glyph(p, 'book', c, s, color)
    elif kind == 'info':
        p.drawEllipse(c, s * .85, s * .85)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(x, y - s * .42), s * .12, s * .12)
        p.setPen(QPen(color, max(1.5, s * .16), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x, y - s * .12), QPointF(x, y + s * .48))
    elif kind == 'quit':
        p.drawArc(QRectF(x - s * .8, y - s * .7, s * 1.6, s * 1.6), 120 * 16, 300 * 16)
        p.drawLine(QPointF(x, y - s * .95), QPointF(x, y - s * .05))
    else:
        draw_glyph(p, kind, c, s, color)


def menu_icon(kind, color, size=20):
    """Pictogramme de menu peint dans la couleur du thème, net sur écran haute densité."""
    from PySide6.QtGui import QIcon, QPixmap
    scale = 3
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)
    draw_icon(p, kind, QPointF(size / 2, size / 2), size * .4, QColor(color))
    p.end()
    pix.setDevicePixelRatio(scale)
    return QIcon(pix)


# --------------------------------------------------------------------------- bandeau
class LeatherBanner(QFrame):
    """Bandeau du haut : cuir de la fiche, filet doré double, fleurons et ombre portée."""

    def __init__(self, parent=None):
        super().__init__(parent)

    @property
    def _leather(self):
        """Cuir du thème actif, tourné : le grain suit la longueur du bandeau."""
        return theme_pixmap('sheet', LEATHER, rotate=90)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(r, 9, 9)
        p.setClipPath(clip)
        if not self._leather.isNull():
            # Le cuir est étiré dans sa largeur pour garder le grain horizontal.
            p.drawPixmap(r.toRect(), self._leather)
        else:
            p.fillRect(r, tint('#3e1e1b'))
        shade = QLinearGradient(r.topLeft(), r.bottomLeft())
        shade.setColorAt(0, QColor(255, 220, 160, 26))
        shade.setColorAt(.5, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, 120))
        p.fillRect(r, shade)
        vignette = QLinearGradient(r.topLeft(), r.topRight())
        vignette.setColorAt(0, QColor(0, 0, 0, 110))
        vignette.setColorAt(.12, QColor(0, 0, 0, 0))
        vignette.setColorAt(.88, QColor(0, 0, 0, 0))
        vignette.setColorAt(1, QColor(0, 0, 0, 110))
        p.fillRect(r, vignette)
        p.setClipping(False)
        outer = r.adjusted(2, 2, -2, -2)
        p.setPen(QPen(GOLD_DARK, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer, 8, 8)
        p.setPen(QPen(GOLD, 1.1))
        p.drawRoundedRect(outer.adjusted(5, 5, -5, -5), 5, 5)
        draw_corner_fleurons(p, outer, size=22)
        draw_diamond(p, QPointF(outer.center().x(), outer.bottom() - 2), 5, GOLD)


class DrawerScrim(QWidget):
    """Voile posé sur la page quand la fiche est ouverte en tiroir : un clic le referme."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self.setObjectName('drawerScrim')
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Refermer la fiche')
        self.hide()

    def mousePressEvent(self, event):
        event.accept()
        self._on_click()

    def paintEvent(self, event):
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(14, 8, 6, 120))
        # Ombre douce portée par le tiroir sur le bord droit.
        shadow = QLinearGradient(QPointF(r.right() - 40, 0), r.topRight())
        shadow.setColorAt(0, QColor(0, 0, 0, 0))
        shadow.setColorAt(1, QColor(0, 0, 0, 150))
        p.fillRect(QRectF(r.right() - 40, 0, 40, r.height()), shadow)


class BannerDivider(QWidget):
    """Séparateur vertical du bandeau : filet doré fondu et losange."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(14)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, h = self.width() / 2, self.height()
        g = QLinearGradient(QPointF(cx, 6), QPointF(cx, h - 6))
        g.setColorAt(0, QColor(216, 180, 108, 0))
        g.setColorAt(.5, GOLD)
        g.setColorAt(1, QColor(216, 180, 108, 0))
        p.setPen(QPen(QBrush(g), 1.2))
        p.drawLine(QPointF(cx, 8), QPointF(cx, h - 8))
        draw_diamond(p, QPointF(cx, h / 2 - 6), 3.2, GOLD)


class MedallionButton(QPushButton):
    """Bouton-icône du bandeau : médaillon bordeaux cerclé d'or, légende sous l'icône.

    Reste un QPushButton : clicked, menu (⚙), info-bulle, raccourcis et accessibilité intacts.
    `primary` donne un médaillon d'or (action principale « Grimoires »)."""
    DISC = 40

    def __init__(self, caption, glyph, parent=None, *, primary=False, text=None):
        super().__init__(text or caption, parent)
        self.caption, self.glyph, self.primary = caption, glyph, primary
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAccessibleName(caption)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.slim = False
        self.setFixedSize(self.sizeHint())

    def set_slim(self, slim):
        """Bandeau fin (petite hauteur) : médaillon réduit, légende masquée (l'info-bulle reste)."""
        slim = bool(slim)
        if slim != self.slim:
            self.slim = slim
            self.setFixedSize(self.sizeHint())
            self.update()

    def _disc(self):
        return 34 if self.slim else self.DISC

    def sizeHint(self):
        if getattr(self, 'slim', False):
            return QSize(self._disc() + 10, self._disc() + 6)
        w = max(self.DISC + 14, QFontMetrics(font('ui', 11, bold=True, spacing=.8)).horizontalAdvance(self.caption) + 10)
        return QSize(w, self.DISC + 22)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        hover = enabled and self.underMouse()
        down = self.isDown() or (self.menu() is not None and self.menu().isVisible())
        d = self._disc()
        c = QPointF(self.width() / 2, (3 if self.slim else 4) + d / 2 + (1 if down else 0))
        r = d / 2 - 2
        if hover or down:
            glow = QRadialGradient(c, r + 9)
            glow.setColorAt(.6, QColor(244, 220, 158, 120))
            glow.setColorAt(1, QColor(244, 220, 158, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(c, r + 9, r + 9)
        # Ombre.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawEllipse(c + QPointF(0, 2), r + 1, r + 1)
        g = QRadialGradient(QPointF(c.x() - r * .35, c.y() - r * .45), r * 1.5)
        if not enabled:
            g.setColorAt(0, tint('#5b4a40'))
            g.setColorAt(1, tint('#2a211c'))
        elif self.primary:
            g.setColorAt(0, tint('#fff1c4'))
            g.setColorAt(.45, tint('#d8b46c'))
            g.setColorAt(1, tint('#7d5a2a'))
        else:
            g.setColorAt(0, tint('#a8404e') if hover else tint('#8f3140'))
            g.setColorAt(.6, BORDEAUX)
            g.setColorAt(1, BORDEAUX_DARK)
        p.setBrush(g)
        ring = QLinearGradient(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))
        ring.setColorAt(0, GOLD_LIGHT if enabled else tint('#8d7d6c'))
        ring.setColorAt(1, GOLD_DARK if enabled else tint('#4f443a'))
        p.setPen(QPen(QBrush(ring), 2.4))
        p.drawEllipse(c, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 90) if self.primary else QColor(216, 180, 108, 110), 1))
        p.drawEllipse(c, r - 4, r - 4)
        if self.hasFocus():
            p.setPen(QPen(GOLD_LIGHT, 1.4, Qt.DotLine))
            p.drawEllipse(c, r + 4, r + 4)
        color = (tint('#4a141c') if self.primary else (GOLD_LIGHT if hover else GOLD)) if enabled \
            else tint('#9b8b78')
        draw_icon(p, self.glyph, c, r * .5, color)
        if self.slim:
            return
        p.setFont(font('ui', 11, bold=True, spacing=.8))
        p.setPen(GOLD_LIGHT if hover else (GOLD if enabled else tint('#8d7d6c')))
        p.drawText(QRectF(0, d + 5, self.width(), 16), Qt.AlignHCenter | Qt.AlignTop, self.caption)


# --------------------------------------------------------------------------- page
class PageToolButton(QPushButton):
    """Petit médaillon d'encre sur le parchemin (couverture, image, taille du texte)."""
    D = 32

    def __init__(self, glyph, tooltip, parent=None, *, text='', checked_glyph=None):
        super().__init__(text, parent)
        self.glyph, self.checked_glyph = glyph, checked_glyph
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.D + 4, self.D + 4)

    def sizeHint(self):
        return QSize(self.D + 4, self.D + 4)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled, hover = self.isEnabled(), self.isEnabled() and self.underMouse()
        c = QPointF(self.width() / 2, self.height() / 2 + (1 if self.isDown() else 0))
        r = self.D / 2 - 1
        if hover:
            glow = QRadialGradient(c, r + 3)
            glow.setColorAt(.75, QColor(122, 38, 50, 70))
            glow.setColorAt(1, QColor(122, 38, 50, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(c, r + 3, r + 3)
        g = QRadialGradient(QPointF(c.x() - r * .3, c.y() - r * .4), r * 1.6)
        g.setColorAt(0, tint('#fff8e6'))
        g.setColorAt(1, tint('#e2c891'))
        p.setBrush(g)
        p.setPen(QPen(RUBRIC if hover else GOLD_DARK, 1.6))
        p.drawEllipse(c, r, r)
        p.setPen(QPen(QColor(138, 102, 51, 120), .8))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, r - 3, r - 3)
        if self.hasFocus():
            p.setPen(QPen(RUBRIC, 1.2, Qt.DotLine))
            p.drawEllipse(c, r + 1.5, r + 1.5)
        glyph = self.glyph
        if self.isCheckable() and not self.isChecked() and self.checked_glyph:
            glyph = self.checked_glyph
        color = RUBRIC if enabled else tint('#b3a081')
        draw_icon(p, glyph, c, r * .5, color)


class ParagraphCartouche(QLabel):
    """Numéro de paragraphe dans un cartouche bordeaux et or (texte « § N » inchangé)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        f = font('title', 18, bold=True, spacing=1)
        return QSize(QFontMetrics(f).horizontalAdvance(self.text() or '§ 000') + 64, 34)

    def minimumSizeHint(self):
        return self.sizeHint()

    def setText(self, text):
        super().setText(text)
        self.setFixedSize(self.sizeHint())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(12, 3, -12, -3)
        h = r.height()
        path = QPainterPath(QPointF(r.left() - 8, r.center().y()))
        path.cubicTo(r.left(), r.top() + h * .1, r.left() + 4, r.top(), r.left() + 12, r.top())
        path.lineTo(r.right() - 12, r.top())
        path.cubicTo(r.right() - 4, r.top(), r.right(), r.top() + h * .1, r.right() + 8, r.center().y())
        path.cubicTo(r.right(), r.bottom() - h * .1, r.right() - 4, r.bottom(), r.right() - 12, r.bottom())
        path.lineTo(r.left() + 12, r.bottom())
        path.cubicTo(r.left() + 4, r.bottom(), r.left(), r.bottom() - h * .1, r.left() - 8, r.center().y())
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, tint('#9a3442'))
        g.setColorAt(.55, BORDEAUX)
        g.setColorAt(1, BORDEAUX_DARK)
        p.setPen(QPen(QColor(60, 30, 10, 70), 3))
        p.drawPath(path.translated(0, 1.5))
        p.setBrush(g)
        p.setPen(QPen(GOLD_DARK, 2))
        p.drawPath(path)
        p.setPen(QPen(GOLD, .9))
        p.setBrush(Qt.NoBrush)
        inner = QRectF(r.left() + 6, r.top() + 4, r.width() - 12, h - 8)
        p.drawRoundedRect(inner, 3, 3)
        for x in (r.left() - 8, r.right() + 8):
            draw_diamond(p, QPointF(x, r.center().y()), 3, GOLD_LIGHT)
        p.setFont(font('title', 18, bold=True, spacing=1))
        p.setPen(GOLD_LIGHT)
        p.drawText(r, Qt.AlignCenter, self.text())


class ChoiceGroup(QGroupBox):
    """Bloc des choix : filet à fleuron puis titre en capitales rubriquées, sans boîte grise."""
    HEADER = 48

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setFlat(True)
        self._compact = False

    def set_compact(self, compact):
        self._compact = compact
        self.update()

    def header_height(self):
        return 38 if self._compact else self.HEADER

    def clean_title(self):
        return self.title().lstrip('⚜✧✦ ').strip()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        top = 6 if self._compact else 10
        draw_fleuron_rule(p, w / 2, top, min(w * .42, 300))
        p.setFont(font('title', 14 if self._compact else 15, bold=True, spacing=3))
        p.setPen(RUBRIC)
        p.drawText(QRectF(0, top + 9, w, 22), Qt.AlignCenter, self.clean_title())


# --------------------------------------------------------------------------- lettrine
def illuminated_initial(letter, px, *, family=None, scale=2):
    """Lettrine enluminée : champ bordeaux, filet d'or, rinceaux, lettre ivoire et or.

    Retourne une QImage carrée de `px` (points logiques) × scale, avec une marge droite
    transparente pour l'habillage du texte flottant."""
    margin_r, margin_b = 10, 4
    size = px * scale
    img = QImage((px + margin_r) * scale, (px + margin_b) * scale, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    r = QRectF(1.5 * scale, 1.5 * scale, size - 3 * scale, size - 3 * scale)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, tint('#9a3442'))
    g.setColorAt(.6, BORDEAUX)
    g.setColorAt(1, BORDEAUX_DARK)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(r, 3 * scale, 3 * scale)
    # Rinceaux dorés discrets dans le fond.
    vine = QColor(216, 180, 108, 95)
    p.setPen(QPen(vine, 1.1 * scale))
    p.setBrush(Qt.NoBrush)
    for sx, sy in ((1, 1), (-1, -1)):
        cx = r.center().x() - sx * r.width() * .28
        cy = r.center().y() - sy * r.height() * .28
        path = QPainterPath(QPointF(cx - sx * r.width() * .2, cy + sy * r.height() * .2))
        path.cubicTo(cx - sx * r.width() * .2, cy - sy * r.height() * .1, cx + sx * r.width() * .1,
                     cy - sy * r.height() * .2, cx + sx * r.width() * .05, cy)
        p.drawPath(path)
        draw_leaf(p, QPointF(cx + sx * r.width() * .05, cy), r.width() * .12, 45 if sx > 0 else 225, vine)
    for dx, dy in ((.18, .82), (.82, .18), (.82, .82), (.18, .18)):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(216, 180, 108, 80))
        p.drawEllipse(QPointF(r.left() + r.width() * dx, r.top() + r.height() * dy), 1.4 * scale, 1.4 * scale)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(GOLD_DARK, 2.2 * scale))
    p.drawRoundedRect(r, 3 * scale, 3 * scale)
    p.setPen(QPen(GOLD, .9 * scale))
    p.drawRoundedRect(r.adjusted(3.5 * scale, 3.5 * scale, -3.5 * scale, -3.5 * scale), 2 * scale, 2 * scale)
    for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
        draw_diamond(p, pt, 3 * scale, GOLD_LIGHT)
    f = font('title', int(size * .74), bold=True)
    if family:
        f.setFamily(family)
    p.setFont(f)
    text_rect = r.adjusted(0, -size * .02, 0, 0)
    p.setPen(QColor(0, 0, 0, 120))
    p.drawText(text_rect.translated(1.2 * scale, 1.6 * scale), Qt.AlignCenter, letter)
    tg = QLinearGradient(r.topLeft(), r.bottomLeft())
    tg.setColorAt(0, tint('#fff6d8'))
    tg.setColorAt(.5, GOLD_LIGHT)
    tg.setColorAt(1, GOLD)
    p.setPen(QPen(QBrush(tg), 1))
    path = QPainterPath()
    fm = QFontMetrics(f)
    adv = fm.horizontalAdvance(letter)
    base_x = text_rect.center().x() - adv / 2
    base_y = text_rect.center().y() + (fm.ascent() - fm.descent()) / 2
    path.addText(QPointF(base_x, base_y), f, letter)
    p.setBrush(QBrush(tg))
    p.setPen(QPen(tint('#5a3a12'), .6 * scale))
    p.drawPath(path)
    p.end()
    img.setDevicePixelRatio(scale)
    return img
