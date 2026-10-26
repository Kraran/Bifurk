"""Icônes dédiées des objets de la sacoche, peintes au QPainter (aucune image).

Chaque objet connu des grimoires reçoit un dessin propre, dans le style des
vignettes historiques de adventurer_sheet.draw_item_art : formes pleines en
dégradé, contour brun-noir de 1,2 px, éclairage venant du haut à gauche, or du
grimoire pour les métaux précieux. Les dessins sont originaux et tracés dans un
repère unitaire (centre 0, demi-taille 1) : ils restent nets à toutes les tailles
de case (pleine ou compacte) et ne pèsent rien dans le dépôt.

ITEM_ICONS associe le nom exact d'un objet (tel qu'enregistré dans la sacoche) à
un identifiant de dessin. item_icon_id() normalise les apostrophes, la casse et
le suffixe « (magie épuisée) » ; il renvoie None pour un nom inconnu, auquel cas
l'appelant garde l'icône générique par mots-clés.
"""
import math
import re

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QColor, QPainterPath, QPen, QBrush, QLinearGradient, QImage, QPainter,
                           QRadialGradient, QPolygonF, QFont, QFontMetricsF)

OUTLINE = QColor('#1a0f0a')
GOLD = QColor('#d8b46c')
GOLD_LIGHT = QColor('#f4dc9e')
GOLD_DARK = QColor('#8a6633')
IVORY = QColor('#f5e7c6')
BORDEAUX_DARK = QColor('#3d1218')
EXHAUSTED_SUFFIX = ' (magie épuisée)'

# Palettes de métal : (reflet, ton moyen, ombre).
METALS = {
    'gold': ('#f4dc9e', '#d8b46c', '#8a6633'),
    'steel': ('#f2f2ee', '#b7bcc2', '#5c6470'),
    'silver': ('#ffffff', '#d4d9e0', '#7d8794'),
    'iron': ('#b9b4ad', '#6f6a64', '#33302d'),
    'bronze': ('#f0c48a', '#b07a3a', '#5a3a17'),
    'copper': ('#f6b48a', '#c4683a', '#6a2e14'),
    'red': ('#ff9a8a', '#c0392b', '#5e1410'),
}


# --------------------------------------------------------------------------- outils
def _c(value, alpha=None):
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def _grad(x1, y1, x2, y2, *stops):
    g = QLinearGradient(QPointF(x1, y1), QPointF(x2, y2))
    n = len(stops)
    for i, stop in enumerate(stops):
        if isinstance(stop, tuple):
            g.setColorAt(stop[0], _c(stop[1]))
        else:
            g.setColorAt(i / max(1, n - 1), _c(stop))
    return g


def _metal(name, x1=-1, y1=-1, x2=1, y2=1):
    light, mid, dark = METALS[name]
    return _grad(x1, y1, x2, y2, (0, light), (.45, mid), (1, dark))


def _pen(color=OUTLINE, width=1.2, cosmetic=True, cap=Qt.RoundCap):
    pen = QPen(_c(color) if not isinstance(color, (QBrush, QLinearGradient, QRadialGradient)) else QBrush(color),
               width, Qt.SolidLine, cap, Qt.RoundJoin)
    pen.setCosmetic(cosmetic)
    return pen


def _outline(p):
    p.setPen(_pen())


def _poly(*points):
    return QPolygonF([QPointF(x, y) for x, y in points])


def _path(points, close=True):
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        if len(point) == 4:
            path.quadTo(*point)
        elif len(point) == 6:
            path.cubicTo(*point)
        else:
            path.lineTo(*point)
    if close:
        path.closeSubpath()
    return path


def _glow(p, x, y, r, color, alpha=170):
    g = QRadialGradient(QPointF(x, y), r)
    g.setColorAt(0, _c(color, alpha))
    g.setColorAt(1, _c(color, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(x, y), r, r)


def _sparkle(p, x, y, r, color='#ffffff'):
    p.setPen(Qt.NoPen)
    p.setBrush(_c(color, 230))
    p.drawPolygon(_poly((x, y - r), (x + r * .25, y - r * .25), (x + r, y), (x + r * .25, y + r * .25),
                        (x, y + r), (x - r * .25, y + r * .25), (x - r, y), (x - r * .25, y - r * .25)))


def _highlight(p, rect, alpha=110):
    p.setPen(Qt.NoPen)
    p.setBrush(_c('#ffffff', alpha))
    p.drawEllipse(rect)


def _stroke(p, brush, width, *points, cap=Qt.RoundCap):
    """Trait épais (largeur en unités du repère), sans contour."""
    pen = QPen(QBrush(brush) if not isinstance(brush, (str, QColor)) else _c(brush), width,
               Qt.SolidLine, cap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        if len(point) == 4:
            path.quadTo(*point)
        else:
            path.lineTo(*point)
    p.drawPath(path)


def _outlined_stroke(p, brush, width, *points, cap=Qt.RoundCap):
    """Trait épais cerné : contour sombre puis remplissage."""
    _outlined_strokes(p, brush, width, [points], cap=cap)


def _outlined_strokes(p, brush, width, segments, cap=Qt.RoundCap):
    """Plusieurs traits soudés : tous les contours d'abord, sans couture interne."""
    for points in segments:
        _stroke(p, OUTLINE, width + .11, *points, cap=cap)
    for points in segments:
        _stroke(p, brush, width, *points, cap=cap)


def _annulus(cx, cy, rx, ry, irx, iry, icx=None, icy=None):
    """Anneau lisse (règle pair-impair, sans polygonisation des opérations booléennes)."""
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    path.addEllipse(QPointF(cx, cy), rx, ry)
    path.addEllipse(QPointF(cx if icx is None else icx, cy if icy is None else icy), irx, iry)
    return path


# --------------------------------------------------------------- familles d'objets
def _sword(p, blade=('#f2f2ee', '#7d8590'), guard='gold', grip='#5b2a18', pommel=GOLD, glow=None,
           runes=None, length=1.0):
    if glow:
        p.save()
        p.setPen(QPen(_c(glow, 120), .34, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(.82 * length, -.82 * length), QPointF(-.3, .5))
        p.restore()
        _glow(p, .2, -.2, .95, glow, 90)
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, *blade))
    p.drawPolygon(_poly((.85 * length, -.85 * length), (.55, -.35), (-.3, .5), (-.45, .35), (.4, -.5)))
    if runes:
        p.setPen(_pen(runes, 1.3))
        for t in (.15, .35, .55):
            x, y = -.25 + t * 1.0, .35 - t * 1.0
            p.drawPoint(QPointF(x + .06, y + .02))
    _outline(p)
    p.setBrush(_metal(guard, -1, 0, 0, 1) if guard in METALS else _c(guard))
    p.drawPolygon(_poly((-.7, .15), (-.6, .05), (-.05, .6), (-.15, .7)))
    p.setBrush(_c(grip))
    p.drawPolygon(_poly((-.45, .55), (-.35, .45), (-.7, .8), (-.8, .7)))
    p.setBrush(_c(pommel) if not isinstance(pommel, QColor) else pommel)
    p.drawEllipse(QPointF(-.85, .85), .12, .12)


def _bottle(p, shape, liquid, emblem=None, level=.38, glass=(210, 235, 240, 90), cork='#8a5a2a',
            glass_outline=True):
    """Fioles de verre : rond (historique), fiole haute, bouteille, flasque plate."""
    _outline(p)
    if not glass_outline:
        dashed = QPen(_c('#d8e6ee', 170), 1.2, Qt.DashLine)
        dashed.setCosmetic(True)
        p.setPen(dashed)
    p.setBrush(QColor(*glass))
    if shape == 'round':
        neck, body = QRectF(-.16, -.8, .32, .4), QRectF(-.6, -.45, 1.2, 1.25)
        body_path = QPainterPath(); body_path.addEllipse(body)
        cork_rect = QRectF(-.22, -.95, .44, .2)
    elif shape == 'vial':
        neck, body = QRectF(-.13, -.78, .26, .25), QRectF(-.3, -.55, .6, 1.4)
        body_path = QPainterPath(); body_path.addRoundedRect(body, .28, .28)
        cork_rect = QRectF(-.19, -.95, .38, .2)
    elif shape == 'bottle':
        neck, body = QRectF(-.12, -.8, .24, .5), QRectF(-.45, -.3, .9, 1.15)
        body_path = _path([(-.12, -.32), (-.45, -.05, -.45, .1), (-.45, .85), (.45, .85), (.45, .1),
                           (.45, -.05, .12, -.32)])
        cork_rect = QRectF(-.17, -.95, .34, .2)
    else:  # flasque plate
        neck, body = QRectF(-.14, -.8, .28, .3), QRectF(-.62, -.5, 1.24, 1.3)
        body_path = QPainterPath(); body_path.addRoundedRect(body, .35, .35)
        cork_rect = QRectF(-.2, -.95, .4, .2)
    p.drawRect(neck)
    p.drawPath(body_path)
    if liquid:
        g = QLinearGradient(QPointF(0, body.top()), QPointF(0, body.bottom()))
        g.setColorAt(0, _c(liquid[0], liquid[2] if len(liquid) > 2 else 255))
        g.setColorAt(1, _c(liquid[1], liquid[2] if len(liquid) > 2 else 255))
        clip = QRectF(body.left() - .1, body.top() + body.height() * level, body.width() + .2, body.height())
        inner = QPainterPath()
        shrunk = body.adjusted(.06, .06, -.06, -.06)
        if shape == 'round':
            inner.addEllipse(shrunk)
        elif shape == 'bottle':
            inner = body_path
        else:
            inner.addRoundedRect(shrunk, .25, .25)
        p.save()
        p.setClipRect(clip, Qt.IntersectClip)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(inner)
        p.restore()
    if emblem:
        emblem(p, QPointF(0, body.center().y() + body.height() * .12))
    p.setPen(Qt.NoPen)
    p.setBrush(_c('#ffffff', 120))
    p.drawEllipse(QRectF(body.left() + body.width() * .18, body.top() + body.height() * .16,
                         body.width() * .17, body.height() * .26))
    _outline(p)
    p.setBrush(_c(cork))
    p.drawRect(cork_rect)


def _ring(p, band='gold', stone=None, stone_r=.27, rays=None, thickness=.2):
    if rays:
        _glow(p, 0, -.45, .75, rays, 150)
        p.setPen(QPen(_c(rays, 200), .07, Qt.SolidLine, Qt.RoundCap))
        for a in range(0, 360, 45):
            r = math.radians(a)
            p.drawLine(QPointF(math.cos(r) * .38, -.45 + math.sin(r) * .38),
                       QPointF(math.cos(r) * .62, -.45 + math.sin(r) * .62))
    _outline(p)
    p.setBrush(_metal(band, -.6, -.4, .6, .8))
    p.drawPath(_annulus(0, .2, .62, .55, .62 - thickness, .55 - thickness * .9))
    if stone:
        _gem(p, 0, -.42, stone_r, stone)


def _gem(p, x, y, r, color, facets=True):
    """Pierre taillée (vue de dessus en losange arrondi)."""
    base = _c(color)
    g = QLinearGradient(QPointF(x - r, y - r), QPointF(x + r, y + r))
    g.setColorAt(0, base.lighter(170))
    g.setColorAt(.5, base)
    g.setColorAt(1, base.darker(200))
    _outline(p)
    p.setBrush(g)
    pts = [(x, y - r), (x + r, y - r * .25), (x + r * .62, y + r), (x - r * .62, y + r), (x - r, y - r * .25)]
    p.drawPolygon(_poly(*pts))
    if facets:
        pen = QPen(_c('#ffffff', 110), 1); pen.setCosmetic(True); p.setPen(pen)
        p.drawLine(QPointF(x - r, y - r * .25), QPointF(x + r, y - r * .25))
        p.drawLine(QPointF(x - r * .45, y - r * .25), QPointF(x, y + r))
        p.drawLine(QPointF(x + r * .45, y - r * .25), QPointF(x, y + r))
    _sparkle(p, x - r * .35, y - r * .45, r * .32)


def _key(p, metal='gold', bow='ring', small=False):
    """Clé en diagonale : anneau en haut à gauche, panneton en bas à droite."""
    k = .8 if small else 1.0
    brush = _metal(metal)
    width = .2 * k
    cx, cy = -.42 * k, -.42 * k
    _outlined_strokes(p, brush, width, [((cx + .2 * k, cy + .2 * k), (.68 * k, .68 * k)),
                                        ((.44 * k, .44 * k), (.66 * k, .22 * k)),
                                        ((.22 * k, .22 * k), (.42 * k, .02 * k))])
    _outline(p)
    p.setBrush(brush)
    if bow == 'trefoil':  # anneau à trois lobes, cerné d'un seul tenant, œil évidé
        p.save()
        hole = QPainterPath()
        hole.setFillRule(Qt.OddEvenFill)
        hole.addRect(QRectF(-2, -2, 4, 4))
        hole.addEllipse(QPointF(cx, cy), .14 * k, .14 * k)
        p.setClipPath(hole, Qt.IntersectClip)
        lobes = ((-.2, -.06), (-.06, -.2))
        for dx, dy in lobes:
            p.drawEllipse(QPointF(cx + dx * k, cy + dy * k), .2 * k, .2 * k)
        p.setPen(Qt.NoPen)
        for dx, dy in lobes:
            p.drawEllipse(QPointF(cx + dx * k, cy + dy * k), .2 * k - .02, .2 * k - .02)
        p.drawEllipse(QPointF(cx, cy), .3 * k, .3 * k)
        _outline(p)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - .32 * k, cy - .32 * k, .64 * k, .64 * k), -110 * 16, 220 * 16)
        p.restore()
        _outline(p)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), .14 * k, .14 * k)
    else:
        p.drawPath(_annulus(cx, cy, .32 * k, .32 * k, .14 * k, .14 * k))


def _numbered_tag(p, text, color='#f5e7c6', ink='#3d1218'):
    """Étiquette de parchemin attachée, portant le numéro gravé de la clé."""
    p.save()
    # Repère en pixels : la police reste lisible quel que soit le facteur d'échelle.
    t = p.transform()
    scale = math.hypot(t.m11(), t.m12())
    center = t.map(QPointF(.38, -.5))
    p.resetTransform()
    size = max(6.0, scale * .5)
    font = QFont('Lato')
    font.setPixelSize(int(round(size)))
    font.setBold(True)
    p.setFont(font)
    metrics = QFontMetricsF(font)
    w = max(size * 1.05, metrics.horizontalAdvance(text) + size * .45)
    h = size * 1.15
    rect = QRectF(center.x() - w / 2, center.y() - h / 2, w, h)
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0, _c(color))
    g.setColorAt(1, _c(color).darker(125))
    pen = QPen(_c('#8a6633'), 1); pen.setCosmetic(True)
    p.setPen(pen)
    p.setBrush(g)
    p.drawRoundedRect(rect, h * .3, h * .3)
    p.setPen(_c(ink))
    p.drawText(rect.adjusted(0, -.5, 0, 0), Qt.AlignCenter, text)
    p.restore()


def _glove(p, fill, cuff, sheen='#ffffff', star=None):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, *fill))
    hand = _path([(-.42, .9), (-.5, .2), (-.78, -.1), (-.75, -.25, -.6, -.2), (-.42, -.02),
                  (-.42, -.7), (-.42, -.85, -.28, -.85), (-.18, -.85, -.18, -.7), (-.16, -.2),
                  (-.12, -.85), (-.12, -.98, .02, -.98), (.14, -.98, .14, -.85), (.12, -.2),
                  (.2, -.78), (.22, -.9, .34, -.88), (.46, -.86, .44, -.74), (.36, -.15),
                  (.5, -.6), (.53, -.7, .63, -.67), (.72, -.64, .7, -.54), (.55, .3), (.45, .9)])
    p.drawPath(hand)
    p.setBrush(_grad(-1, .5, 1, 1, *cuff))
    p.drawRoundedRect(QRectF(-.5, .55, 1.02, .38), .08, .08)
    p.setPen(QPen(_c(sheen, 90), .06, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(-.3, -.6), QPointF(-.3, .1))
    if star:
        _sparkle(p, .02, .1, .2, star)


def _helmet(p, metal='steel', crest=None, gem=None, aura=None, eyes=None):
    if aura:
        _glow(p, 0, 0, 1.05, aura, 150)
    _outline(p)
    p.setBrush(_metal(metal, -.8, -.8, .8, .8))
    dome = _path([(-.72, .55), (-.75, -.1), (-.7, -.75, 0, -.8), (.7, -.75, .75, -.1), (.72, .55),
                  (.45, .7), (.32, .1), (-.32, .1), (-.45, .7)])
    p.drawPath(dome)
    p.setBrush(_c('#1a0f0a'))
    p.drawRect(QRectF(-.5, -.12, 1.0, .16))  # visière
    p.setBrush(_metal(metal, -.1, -.8, .1, .6))
    p.drawRect(QRectF(-.07, -.05, .14, .55))  # nasal
    if eyes:
        p.setPen(Qt.NoPen)
        p.setBrush(_c(eyes))
        p.drawEllipse(QPointF(-.27, -.04), .07, .05)
        p.drawEllipse(QPointF(.27, -.04), .07, .05)
    if crest:
        _outline(p)
        p.setBrush(_c(crest))
        p.drawPath(_path([(-.12, -.78), (0, -1.0), (.12, -.78)]))
    if gem:
        _gem(p, 0, -.47, .17, gem, facets=False)


def _medallion(p, metal='gold', center=None, emblem=None, chain='gold', r=.52):
    pen = QPen(QBrush(_metal(chain)), .08, Qt.DotLine, Qt.RoundCap)
    p.setPen(pen); p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(-.6, -.6)); path.quadTo(-.55, .05, 0, .05)
    path2 = QPainterPath(QPointF(.6, -.6)); path2.quadTo(.55, .05, 0, .05)
    p.drawPath(path); p.drawPath(path2)
    _outline(p)
    p.setBrush(_metal(metal, -r, .3 - r, r, .3 + r))
    p.drawEllipse(QPointF(0, .35), r, r)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(_c(GOLD_DARK if metal == 'gold' else '#5c6470'), .05))
    p.drawEllipse(QPointF(0, .35), r * .72, r * .72)
    if center:
        _gem(p, 0, .35, r * .45, center, facets=False)
    if emblem:
        emblem(p, QPointF(0, .35), r)


# ---------------------------------------------------------------------- dessins
def _d_sword_magic(p):
    _sword(p, blade=('#ffffff', '#a8b8ff', '#5b4fb0'), guard='gold', grip='#2b1f5c', pommel='#9be7ff',
           glow='#8f7bff')
    _sparkle(p, .62, -.72, .2)
    _sparkle(p, -.05, .02, .14, '#e8e0ff')


def _d_sword_enchanted(p):
    _sword(p, blade=('#f6fbff', '#9fd8c4', '#2f6f63'), guard='gold', grip='#1f3d2c', pommel='#e35b5b',
           glow='#3fd1a4', runes='#fff3b0')
    _sparkle(p, .48, -.55, .15, '#f5ffd0')


def _d_sword_river(p):
    _sword(p, blade=('#e6efe9', '#8aa39a', '#3e5a55'), guard='bronze', grip='#3b2a1a', pommel='#b07a3a')
    p.setPen(QPen(_c('#5fb3d6', 220), .07, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    for dy in (.55, .78):
        path = QPainterPath(QPointF(.05, dy))
        path.quadTo(.2, dy - .12, .35, dy); path.quadTo(.5, dy + .12, .65, dy); path.quadTo(.8, dy - .12, .92, dy)
        p.drawPath(path)
    p.setPen(Qt.NoPen); p.setBrush(_c('#9fe0ff', 220))
    p.drawEllipse(QPointF(.2, -.08), .06, .09)


def _d_knife(p):
    _outline(p)
    p.setBrush(_metal('steel'))
    p.drawPath(_path([(.85, -.85), (.55, -.15, .05, .15), (-.1, 0), (.3, -.45, .85, -.85)]))
    p.setBrush(_c('#4a2a17'))
    p.drawPolygon(_poly((-.02, .1), (.08, .2), (-.45, .7), (-.55, .6)))
    p.setBrush(_metal('steel'))
    p.drawPolygon(_poly((-.18, -.1), (-.08, -.2), (.25, .2), (.15, .3)))
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen())
    p.drawEllipse(QPointF(-.62, .77), .14, .14)


def _d_bow(p):
    _outlined_stroke(p, _grad(-1, -1, 1, 1, '#c98a45', '#6b3a17'), .17, (-.45, -.9), (.75, -.6, .55, .05),
                     (.35, .7, -.45, .9))
    pen = QPen(_c('#efe6d0'), 1); pen.setCosmetic(True)
    p.setPen(pen)
    p.drawLine(QPointF(-.45, -.9), QPointF(-.45, .9))
    _outline(p)
    p.setBrush(_c('#5b2a18'))
    p.drawRoundedRect(QRectF(.45, -.12, .2, .32), .06, .06)


def _arrow(p, shaft='#c98a45', head='silver', feathers='#f5e7c6', length=1.0, dart=False):
    a, b = (-.8 * length, .8 * length), (.72 * length, -.72 * length)
    _outlined_stroke(p, shaft, .11 if not dart else .14, a, b)
    _outline(p)
    p.setBrush(_metal(head))
    tip = (.9 * length, -.9 * length)
    p.drawPolygon(_poly(tip, (b[0] - .22, b[1] + .02), (b[0] - .02, b[1] + .22)))
    p.setBrush(_c(feathers))
    for off in (0, .18):
        x, y = a[0] + .12 + off, a[1] - .12 - off
        p.drawPolygon(_poly((x, y), (x - .3, y - .05), (x - .15, y + .1)))
        p.drawPolygon(_poly((x, y), (x + .05, y + .3), (x - .1, y + .15)))


def _d_arrow_silver(p):
    _glow(p, .55, -.55, .5, '#e8f0ff', 110)
    _arrow(p, shaft='#d7dde5', head='silver', feathers='#ffffff')
    _sparkle(p, .78, -.78, .16)


def _d_dart_silver(p):
    _arrow(p, shaft='#8a8f99', head='silver', feathers='#c0392b', length=.75, dart=True)
    _sparkle(p, .62, -.62, .14)


def _d_spear(p):
    _outlined_stroke(p, _grad(-1, 1, 1, -1, '#5b3417', '#b98245'), .13, (-.9, .9), (.45, -.45))
    _outline(p)
    p.setBrush(_metal('iron'))
    p.drawPolygon(_poly((.92, -.92), (.38, -.6), (.28, -.4), (.48, -.3), (.6, -.38)))
    p.setBrush(_c('#8a5a2a'))
    p.drawPolygon(_poly((.25, -.35), (.35, -.25), (.45, -.35), (.35, -.45)))


def _d_stakes(p):
    for dx in (-.6, -.3, 0, .3, .6):
        top, bottom = -.85 + abs(dx) * .25, .85
        _outline(p)
        p.setBrush(_grad(dx - .12, 0, dx + .12, 0, '#e2b06d', '#8a5a2a'))
        p.drawPolygon(_poly((dx, top), (dx + .12, top + .3), (dx + .12, bottom), (dx - .12, bottom), (dx - .12, top + .3)))
    p.setPen(QPen(_c('#5b2a18'), .1))
    p.drawLine(QPointF(-.8, .35), QPointF(.8, .35))


def _d_chisel(p):
    _outline(p)
    p.setBrush(_grad(-1, 1, 0, 0, '#a86c34', '#5b3417'))
    p.drawRoundedRect(QRectF(-.2, -.12, .9, .24).translated(-.55, 0), .1, .1)
    p.setBrush(_metal('silver'))
    p.drawPolygon(_poly((.15, -.12), (.85, -.2), (.95, 0), (.85, .2), (.15, .12)))
    p.setBrush(_metal('iron'))
    p.drawRect(QRectF(.08, -.16, .1, .32))
    _sparkle(p, .7, -.05, .14)


def _d_mallet(p):
    _outlined_stroke(p, _grad(0, 0, 1, 1, '#c98a45', '#6b3a17'), .14, (-.05, -.05), (.8, .8))
    _outline(p)
    p.setBrush(_grad(-1, -1, 0, 0, '#d9a66a', '#7a4a20'))
    p.save()
    p.translate(-.25, -.25); p.rotate(-45)
    p.drawRoundedRect(QRectF(-.62, -.3, 1.24, .6), .12, .12)
    p.setPen(QPen(_c('#5b3417', 160), .04))
    p.drawLine(QPointF(-.4, -.25), QPointF(-.4, .25)); p.drawLine(QPointF(.4, -.25), QPointF(.4, .25))
    p.restore()


def _d_hammer_head(p):
    _outline(p)
    p.setBrush(_metal('bronze', -.9, -.6, .9, .6))
    p.drawPath(_path([(-.9, -.35), (-.25, -.42), (-.2, -.55), (.2, -.55), (.25, -.42), (.9, -.35),
                      (.9, .35), (.25, .42), (.2, .55), (-.2, .55), (-.25, .42), (-.9, .35)]))
    p.setBrush(_c('#2a170c'))
    p.drawEllipse(QPointF(0, 0), .14, .22)
    p.setPen(QPen(_c('#ffe0b0', 140), .05))
    p.drawLine(QPointF(-.82, -.25), QPointF(-.3, -.32))
    _gem(p, -.62, .02, .11, '#c0392b', facets=False)
    _gem(p, .62, .02, .11, '#c0392b', facets=False)


def _d_hammer_handle(p):
    _outlined_stroke(p, _grad(-1, -1, 1, 1, '#5a4a52', '#120c10'), .22, (-.75, .75), (.75, -.75))
    for t in (-.55, .1, .6):
        _outline(p)
        p.setBrush(_metal('gold'))
        p.save(); p.translate(t, -t); p.rotate(-45)
        p.drawRoundedRect(QRectF(-.07, -.16, .14, .32), .03, .03)
        p.restore()
    p.setPen(QPen(_c('#ffffff', 80), .04)); p.drawLine(QPointF(-.6, .52), QPointF(.52, -.6))


def _d_armor_found(p):
    _outline(p)
    path = _path([(-.75, -.7), (-.3, -.85), (0, -.55, .3, -.85), (.75, -.7), (.6, .2), (.5, .85), (-.5, .85), (-.6, .2)])
    p.setBrush(_metal('steel', -.8, -.8, .8, .8))
    p.drawPath(path)
    p.save()
    p.setClipPath(path)
    p.setPen(QPen(_c('#4a525c', 200), .035))
    p.setBrush(Qt.NoBrush)
    for row in range(9):
        for col in range(9):
            x = -.85 + col * .21 + (row % 2) * .1
            y = -.75 + row * .19
            p.drawArc(QRectF(x, y, .2, .2), 180 * 16, 180 * 16)
    p.restore()
    _outline(p)
    p.setBrush(_metal('bronze', -1, .3, 1, .5))
    p.drawRect(QRectF(-.55, .3, 1.1, .14))


def _d_helmet_magic(p):
    _helmet(p, 'steel', crest='#7a2632', gem='#5ec8ff')
    _sparkle(p, .55, -.65, .16, '#dff6ff')


def _d_helmet_cursed(p):
    _helmet(p, 'iron', crest='#3d1218', gem='#6b2a8a', aura='#7d3fb8', eyes='#ff4a3a')


def _shield_round(p, rim='iron', fill=('#c98a45', '#6b3a17'), planks=True):
    _outline(p)
    p.setBrush(_metal(rim, -.9, -.9, .9, .9))
    p.drawEllipse(QPointF(0, 0), .88, .88)
    p.setBrush(_grad(-.7, -.7, .7, .7, *fill))
    p.drawEllipse(QPointF(0, 0), .74, .74)
    if planks:
        p.save()
        clip = QPainterPath(); clip.addEllipse(QPointF(0, 0), .74, .74)
        p.setClipPath(clip)
        p.setPen(QPen(_c('#4a2a12', 200), .04))
        for x in (-.42, -.14, .14, .42):
            p.drawLine(QPointF(x, -.8), QPointF(x, .8))
        p.restore()


def _d_shield_wood(p):
    _shield_round(p)
    _outline(p)
    p.setBrush(_metal('iron'))
    p.drawEllipse(QPointF(0, 0), .24, .24)
    _highlight(p, QRectF(-.12, -.14, .1, .08), 140)


def _d_shield_crescent(p):
    _shield_round(p, rim='gold', fill=('#e4e8ee', '#6d7682'), planks=False)
    moon = QPainterPath(); moon.addEllipse(QPointF(0, 0), .46, .46)
    bite = QPainterPath(); bite.addEllipse(QPointF(.22, -.12), .38, .38)
    _outline(p)
    p.setBrush(_metal('gold', -.5, -.5, .5, .5))
    p.drawPath(moon.subtracted(bite))


def _d_shield_emperor(p):
    _outline(p)
    path = _path([(-.75, -.75), (.75, -.75), (.7, .1), (.5, .7, 0, .92), (-.5, .7, -.7, .1)])
    p.setBrush(_metal('gold', -.8, -.8, .8, .8))
    p.drawPath(path)
    inner = _path([(-.6, -.62), (.6, -.62), (.56, .08), (.4, .56, 0, .76), (-.4, .56, -.56, .08)])
    p.setBrush(_grad(-.6, -.6, .6, .6, '#a43a8f', '#3f1440'))
    p.drawPath(inner)
    # Couronne impériale stylisée.
    p.setBrush(_metal('gold', -.4, -.4, .4, .2))
    p.drawPolygon(_poly((-.35, .05), (-.35, -.3), (-.18, -.12), (0, -.38), (.18, -.12), (.35, -.3), (.35, .05)))
    p.setPen(Qt.NoPen); p.setBrush(_c('#f4dc9e'))
    for x, y in ((-.35, -.32), (0, -.4), (.35, -.32)):
        p.drawEllipse(QPointF(x, y), .06, .06)


def _d_bracer_strength(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#b4743c', '#4a2410'))
    p.drawPath(_path([(-.75, -.45), (.75, -.6), (.8, .45), (-.7, .6)]))
    p.setBrush(_metal('gold', -.8, -.2, .8, .2))
    p.drawPath(_path([(-.73, -.3), (.76, -.45), (.77, -.3), (-.72, -.15)]))
    p.drawPath(_path([(-.7, .3), (.79, .17), (.79, .32), (-.7, .45)]))
    for x in (-.5, -.15, .5):
        p.setBrush(_metal('gold')); p.drawEllipse(QPointF(x, .02 - x * .1), .07, .07)
    _gem(p, .18, -.02, .2, '#d6303a', facets=False)


def _d_bracelet_skill(p):
    _outline(p)
    p.setBrush(_metal('copper', -.8, -.5, .8, .5))
    p.drawPath(_annulus(0, .05, .82, .5, .62, .32, 0, .02))
    p.setPen(Qt.NoPen)
    p.setBrush(_c('#ffe2c4', 220))
    for i in range(5):
        a = math.radians(30 + i * 30)
        p.drawEllipse(QPointF(math.cos(a) * .72, .05 + math.sin(a) * .41), .04, .04)
    _sparkle(p, -.45, .38, .15, '#fff2dc')


def _d_gauntlet(p):
    _outline(p)
    p.setBrush(_metal('iron', -.8, -.8, .8, .8))
    fingers = _path([(-.5, .4), (-.6, -.3), (-.5, -.8), (-.32, -.8), (-.3, -.35), (-.2, -.9), (0, -.9),
                     (.02, -.35), (.12, -.85), (.32, -.82), (.26, -.3), (.42, -.65), (.6, -.6), (.48, -.05),
                     (.62, .15), (.45, .4)])
    p.drawPath(fingers)
    p.setPen(QPen(_c('#d7d2ca', 170), .04))
    for y in (-.55, -.3, -.05):
        p.drawLine(QPointF(-.5, y), QPointF(.4, y - .03))
    _outline(p)
    p.setBrush(_metal('steel', -.8, .3, .8, .9))
    p.drawPath(_path([(-.62, .35), (.6, .35), (.75, .9), (-.75, .9)]))
    p.setBrush(_metal('gold')); p.drawEllipse(QPointF(0, .62), .1, .1)


def _d_glove_throw(p):
    _glove(p, ('#c58ce0', '#5a2a7a'), ('#e0c070', '#8a6633'), star='#fff5c0')


def _d_glove_black(p):
    _glove(p, ('#5a5562', '#0e0b12'), ('#3a3540', '#0e0b12'), sheen='#d8d0ff')


def _d_boots(p):
    for dx, shade in ((.18, 1.0), (-.18, .85)):
        _outline(p)
        p.setBrush(_grad(-1, -1, 1, 1, '#b57a44', '#4f2810') if shade == 1 else _grad(-1, -1, 1, 1, '#9a6538', '#3f200c'))
        boot = _path([(-.35 + dx, -.75), (.15 + dx, -.75), (.12 + dx, .35), (.6 + dx, .5), (.62 + dx, .85),
                      (-.38 + dx, .85)])
        p.drawPath(boot)
        p.setBrush(_c('#2a170c'))
        p.drawRect(QRectF(-.38 + dx, .75, 1.0, .1))
    # Ailettes de bond.
    _outline(p)
    p.setBrush(_grad(0, -1, 0, 0, '#ffffff', '#c9d6e0'))
    p.drawPath(_path([(.3, -.45), (.75, -.75), (.62, -.55), (.88, -.55), (.62, -.35), (.3, -.25)]))
    p.drawPath(_path([(-.53, -.45), (-.88, -.7), (-.8, -.5), (-.98, -.45), (-.75, -.32), (-.53, -.28)]))


def _d_headband(p):
    _outline(p)
    p.setBrush(_grad(-1, -.5, 1, .5, '#e9e1f6', '#7a6aa8'))
    p.drawPath(_annulus(0, .1, .9, .5, .74, .34))
    p.setPen(QPen(_c('#d8b46c'), .05))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.82, -.33, 1.64, .84), 200 * 16, 140 * 16)
    p.drawPath(_path([(-.35, .5), (-.55, .95), (-.4, .92)], close=False))
    _outline(p)
    p.setBrush(_c('#f5e7c6'))
    p.drawEllipse(QPointF(0, .52), .26, .16)
    p.setBrush(_c('#3a6ed8'))
    p.drawEllipse(QPointF(0, .52), .11, .11)
    p.setPen(Qt.NoPen); p.setBrush(_c('#0b0b18')); p.drawEllipse(QPointF(0, .52), .05, .05)


def _emblem_heart(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        _outline(p)
        p.setBrush(_c(color))
        p.drawPath(_path([(x, y + .22), (x - .3, y - .02, x - .2, y - .17), (x - .08, y - .25, x, y - .1),
                          (x + .08, y - .25, x + .2, y - .17), (x + .3, y - .02, x, y + .22)]))
    return draw


def _emblem_leaf(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        _outline(p)
        p.setBrush(_c(color))
        p.drawPath(_path([(x - .24, y + .2), (x - .25, y - .2, x + .24, y - .22), (x + .2, y + .18, x - .24, y + .2)]))
        p.setPen(QPen(_c('#1f4a1a'), .03)); p.drawLine(QPointF(x - .22, y + .18), QPointF(x + .15, y - .15))
    return draw


def _emblem_wave(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        p.setPen(QPen(_c(color), .07, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
        for dy in (-.08, .1):
            path = QPainterPath(QPointF(x - .3, y + dy))
            path.quadTo(x - .15, y + dy - .12, x, y + dy); path.quadTo(x + .15, y + dy + .12, x + .3, y + dy)
            p.drawPath(path)
    return draw


def _emblem_bug(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        p.setPen(QPen(_c('#1a0f0a'), .035))
        for dy in (-.08, 0, .08):
            p.drawLine(QPointF(x - .22, y + dy - .04), QPointF(x + .22, y + dy + .04))
            p.drawLine(QPointF(x + .22, y + dy - .04), QPointF(x - .22, y + dy + .04))
        _outline(p); p.setBrush(_c(color))
        p.drawEllipse(QPointF(x, y + .02), .1, .16)
        p.drawEllipse(QPointF(x, y - .17), .07, .06)
    return draw


def _emblem_snake(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        _outlined_stroke(p, color, .08, (x - .2, y + .2), (x + .25, y + .12, x, y), (x - .25, y - .12, x + .15, y - .22))
        p.setPen(Qt.NoPen); p.setBrush(_c(color)); p.drawEllipse(QPointF(x + .17, y - .22), .07, .05)
    return draw


def _emblem_cross(color, small=False):
    def draw(p, c):
        x, y = c.x(), c.y()
        k = .8 if small else 1
        _outline(p)
        p.setBrush(_metal(color) if color in METALS else _c(color))
        p.drawPath(_path([(x - .06 * k, y - .3 * k), (x + .06 * k, y - .3 * k), (x + .06 * k, y - .12 * k),
                          (x + .2 * k, y - .12 * k), (x + .2 * k, y), (x + .06 * k, y), (x + .06 * k, y + .3 * k),
                          (x - .06 * k, y + .3 * k), (x - .06 * k, y), (x - .2 * k, y), (x - .2 * k, y - .12 * k),
                          (x - .06 * k, y - .12 * k)]))
    return draw


def _emblem_bolt(color):
    def draw(p, c):
        x, y = c.x(), c.y()
        _outline(p); p.setBrush(_c(color))
        p.drawPolygon(_poly((x + .08, y - .3), (x - .16, y + .04), (x, y + .04), (x - .08, y + .3),
                            (x + .18, y - .06), (x + .02, y - .06)))
    return draw


def _d_potion_healing(p):
    _bottle(p, 'round', ('#ff6a6a', '#7a0f1c'), _emblem_heart('#ffe3e3'))


def _d_potion_plants(p):
    _bottle(p, 'flat', ('#8fe07a', '#1f5a1a'), _emblem_leaf('#c8f5a0'), cork='#5b3a1a')


def _d_potion_tranquil(p):
    _bottle(p, 'vial', ('#a8d8ff', '#2a5aa8'), _emblem_wave('#ffffff'), level=.3)


def _d_potion_insects(p):
    _bottle(p, 'round', ('#ffd36a', '#a8610c'), _emblem_bug('#3a2410'), cork='#4a3424')


def _d_potion_antidote(p):
    _bottle(p, 'bottle', ('#c58ce0', '#4a1a6a'), _emblem_snake('#d8ffb0'), level=.25)


def _d_holy_water_foret(p):
    _glow(p, 0, .1, 1.0, '#cfe8ff', 120)
    _bottle(p, 'vial', ('#e8f6ff', '#7fb4e0', 200), _emblem_cross('gold'), level=.2, cork='#d8b46c')


def _d_holy_water_sorcier(p):
    _glow(p, 0, .15, 1.0, '#e8f2ff', 110)
    _bottle(p, 'bottle', ('#eef7ff', '#8fb8d8', 190), _emblem_cross('silver', small=True), level=.3, cork='#7a5a3a')


def _d_potion_force(p):
    _bottle(p, 'vial', ('#ffb04a', '#a8360c'), _emblem_bolt('#fff3b0'), level=.25, cork='#5b2a18')


def _d_potion_invisible(p):
    _bottle(p, 'round', ('#f4fbff', '#cfe0ea', 70), None, glass=(230, 240, 248, 40), glass_outline=False)
    for x, y, r in ((.3, -.1, .14), (-.2, .35, .1), (.05, .1, .08)):
        _sparkle(p, x, y, r, '#ffffff')


def _d_ring_light(p):
    _ring(p, 'gold', '#fff7c2', rays='#ffe680')


def _d_ring_slow(p):
    _ring(p, 'iron', None, thickness=.18)
    _outline(p)
    p.setBrush(_grad(-.3, -.8, .3, -.1, '#9a9aa0', '#3a3a40'))
    p.drawEllipse(QPointF(0, -.42), .28, .24)
    p.setPen(QPen(_c('#d0d0d8'), .04)); p.setBrush(Qt.NoBrush)
    spiral = QPainterPath(QPointF(0, -.42))
    for i in range(1, 16):
        a = i * .7
        r = .012 * i
        spiral.lineTo(math.cos(a) * r, -.42 + math.sin(a) * r * .85)
    p.drawPath(spiral)


def _d_ring_gold(p):
    _ring(p, 'gold', None, thickness=.24)
    _sparkle(p, -.42, -.12, .16)


def _d_ring_emerald(p):
    _ring(p, 'gold', '#2ecc71', stone_r=.3)


def _d_earring_gold(p):
    p.setPen(QPen(QBrush(_metal('gold')), .1, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    _outline(p)
    p.setBrush(_metal('gold')); p.drawPath(_annulus(0, -.3, .45, .45, .33, .33))
    p.drawPath(_path([(0, .1), (.22, .45, 0, .9), (-.22, .45, 0, .1)]))
    _sparkle(p, -.25, -.5, .12)


def _d_earrings(p):
    for dx, dy in ((-.38, -.1), (.38, .1)):
        _outline(p)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(_metal('gold')), .07, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(dx - .2, dy - .85, .4, .4), 0, 300 * 16)
        p.drawLine(QPointF(dx, dy - .45), QPointF(dx, dy - .2))
        _gem(p, dx, dy + .15, .26, '#3a7bd5', facets=False)


def _value_medallion(star):
    def draw(p, c, r):
        if star:
            _outline(p); p.setBrush(_metal('gold', -.3, 0, .3, .7))
            pts = []
            for i in range(10):
                a = math.radians(-90 + i * 36)
                rr = r * (.45 if i % 2 == 0 else .2)
                pts.append((c.x() + math.cos(a) * rr, c.y() + math.sin(a) * rr))
            p.drawPolygon(_poly(*pts))
    return draw


def _d_medallion_9(p):
    _medallion(p, 'gold', center='#c0392b', r=.56)


def _d_medallion_5(p):
    _medallion(p, 'gold', emblem=_value_medallion(True), r=.48)


def _d_collar_leather(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#a8693a', '#3f1f0c'))
    p.drawPath(_annulus(0, 0, .85, .7, .62, .48, 0, -.05))
    for i in range(9):
        a = math.radians(20 + i * 17.5)
        _outline(p); p.setBrush(_metal('gold'))
        p.drawEllipse(QPointF(math.cos(a) * .74, math.sin(a) * .6), .07, .07)
    _outline(p); p.setBrush(_metal('gold')); p.drawRect(QRectF(-.12, -.82, .24, .2))


def _d_collar_skulls(p):
    p.setPen(QPen(_c('#d9bf8a'), .06)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(0, -.15), .8, .8)
    for i in range(5):
        a = math.radians(205 + i * 32.5)
        x, y = math.cos(a) * .8, -.15 - math.sin(a) * .8
        _outline(p); p.setBrush(_grad(x, y - .2, x, y + .2, '#fbf6e8', '#b7ab8c'))
        p.drawEllipse(QPointF(x, y), .17, .15)
        p.drawRect(QRectF(x - .09, y + .08, .18, .1))
        p.setPen(Qt.NoPen); p.setBrush(_c('#1a0f0a'))
        p.drawEllipse(QPointF(x - .06, y), .04, .04); p.drawEllipse(QPointF(x + .06, y), .04, .04)


def _d_amber_eye(p):
    p.setPen(QPen(QBrush(_metal('gold')), .06)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.6, -1.0, 1.2, 1.0), 200 * 16, 140 * 16)
    p.drawLine(QPointF(-.57, -.6), QPointF(-.15, -.18)); p.drawLine(QPointF(.57, -.6), QPointF(.15, -.18))
    _glow(p, 0, .3, .8, '#ffb43a', 120)
    _outline(p)
    p.setBrush(_metal('gold')); p.drawEllipse(QPointF(0, .3), .56, .5)
    g = QRadialGradient(QPointF(-.12, .18), .5); g.setColorAt(0, _c('#ffe08a')); g.setColorAt(1, _c('#b0520c'))
    p.setBrush(g); p.drawEllipse(QPointF(0, .3), .45, .39)
    p.setBrush(_c('#4a1f05')); p.drawEllipse(QPointF(0, .3), .08, .26)
    _sparkle(p, -.2, .13, .1, '#fff8e0')


def _d_crown(p):
    for x in (-.5, 0, .5):
        _glow(p, x, -.65, .32, '#ff7a1a', 150)
    _outline(p)
    p.setBrush(_metal('gold', -.8, -.6, .8, .7))
    p.drawPolygon(_poly((-.8, .6), (-.85, -.35), (-.48, -.05), (-.25, -.6), (0, -.12), (.25, -.6),
                        (.48, -.05), (.85, -.35), (.8, .6)))
    p.setBrush(_metal('gold', -.8, .4, .8, .8)); p.drawRect(QRectF(-.82, .4, 1.64, .24))
    for x in (-.45, 0, .45):
        _gem(p, x, .2, .12, '#e0301a', facets=False)
    p.setPen(Qt.NoPen)
    for x, y in ((-.85, -.35), (-.25, -.6), (.25, -.6), (.85, -.35)):
        p.setBrush(_c('#ffb02e', 230))
        p.drawPath(_path([(x, y - .28), (x + .1, y - .08, x, y + .02), (x - .1, y - .08, x, y - .28)]))


def _d_crucifix(p):
    _outline(p)
    p.setBrush(_metal('silver', -.5, -.9, .5, .9))
    p.drawPath(_path([(-.12, -.9), (.12, -.9), (.12, -.42), (.48, -.42), (.48, -.18), (.12, -.18),
                      (.12, .9), (-.12, .9), (-.12, -.18), (-.48, -.18), (-.48, -.42), (-.12, -.42)]))
    p.setPen(QPen(_c('#ffffff', 170), .04)); p.drawLine(QPointF(-.05, -.82), QPointF(-.05, .8))
    _sparkle(p, .3, -.65, .15)


def _d_gem_statue(p):
    _glow(p, 0, 0, .95, '#ff5050', 90)
    _gem(p, 0, 0, .78, '#c8102e')


def _d_gold_ingot(p):
    _outline(p)
    p.setBrush(_metal('gold', -.8, -.4, .8, .7))
    p.drawPolygon(_poly((-.9, .5), (-.55, -.25), (.55, -.25), (.9, .5)))
    p.setBrush(_c(GOLD_LIGHT))
    p.drawPolygon(_poly((-.55, -.25), (-.4, -.5), (.4, -.5), (.55, -.25)))
    p.setPen(QPen(_c(GOLD_DARK), .05)); p.drawLine(QPointF(-.3, .15), QPointF(.3, .15))
    _sparkle(p, -.25, -.37, .14)


def _key_with(metal, number, small=False, tag='#f5e7c6', bow='ring'):
    def draw(p):
        _key(p, metal, bow=bow, small=small)
        if number:
            _numbered_tag(p, number, tag)
    return draw


def _d_key_boathouse(p):
    _key(p, 'iron', bow='trefoil')
    # Médaille d'ancre : la clé du hangar à bateaux.
    _outline(p)
    p.setBrush(_grad(.1, -.9, .7, -.2, '#d8ecf5', '#4f7d96'))
    p.drawEllipse(QPointF(.42, -.52), .3, .3)
    p.setPen(QPen(_c('#1a2a36'), .055, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(.42, -.7), QPointF(.42, -.34))
    p.drawLine(QPointF(.32, -.62), QPointF(.52, -.62))
    p.drawArc(QRectF(.27, -.55, .3, .25), 200 * 16, 140 * 16)


def _d_key_silver_small(p):
    _glow(p, -.2, -.2, .7, '#eef4ff', 90)
    _key(p, 'silver', small=True)
    _sparkle(p, -.45, -.6, .14)


def _d_map(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#f5e7c6', '#c9a86a'))
    p.drawPath(_path([(-.85, -.6), (-.3, -.75), (.3, -.6), (.85, -.75), (.85, .6), (.3, .75), (-.3, .6), (-.85, .75)]))
    p.setPen(QPen(_c('#8a6633', 150), .03))
    p.drawLine(QPointF(-.3, -.75), QPointF(-.3, .6)); p.drawLine(QPointF(.3, -.6), QPointF(.3, .75))
    # Forêt et chemin.
    p.setPen(Qt.NoPen); p.setBrush(_c('#3f7a3a'))
    for x, y in ((-.6, -.3), (-.45, -.1), (-.65, .15), (.5, .25), (.62, .45)):
        p.drawPolygon(_poly((x, y - .14), (x + .1, y + .07), (x - .1, y + .07)))
    p.setPen(QPen(_c('#7a2632'), .045, Qt.DashLine)); p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(-.7, .5)); path.quadTo(-.1, .45, 0, 0); path.quadTo(.1, -.4, .55, -.35)
    p.drawPath(path)
    p.setPen(QPen(_c('#7a2632'), .07))
    p.drawLine(QPointF(.47, -.43), QPointF(.63, -.27)); p.drawLine(QPointF(.63, -.43), QPointF(.47, -.27))


def _d_rope(p):
    _glow(p, 0, 0, .95, '#ffe9a8', 80)
    brush = _grad(-1, -1, 1, 1, '#e8c98a', '#8a5a2a')
    for r in (.72, .52, .32):
        _outline(p); p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_c(OUTLINE), .17)); p.drawEllipse(QPointF(0, .05), r, r * .75)
        p.setPen(QPen(QBrush(brush), .12)); p.drawEllipse(QPointF(0, .05), r, r * .75)
    p.setPen(QPen(_c('#6b4a20'), .025))
    for i in range(16):
        a = math.radians(i * 22.5)
        p.drawLine(QPointF(math.cos(a) * .67, .05 + math.sin(a) * .5), QPointF(math.cos(a) * .77, .05 + math.sin(a) * .58))
    _outlined_stroke(p, brush, .12, (.6, .45), (.85, .85))
    _sparkle(p, -.55, -.55, .16, '#fff7d0')


def _d_net(p):
    _outline(p)
    shape = _path([(-.8, -.7), (.8, -.7), (.6, .1, 0, .85), (-.6, .1, -.8, -.7)])
    p.setBrush(_c('#6b4a2a', 60)); p.drawPath(shape)
    p.save(); p.setClipPath(shape)
    p.setPen(QPen(_c('#d9bf8a'), .05)); p.setBrush(Qt.NoBrush)
    for i in range(-6, 7):
        p.drawLine(QPointF(i * .22 - 1, -1), QPointF(i * .22 + 1, 1))
        p.drawLine(QPointF(i * .22 + 1, -1), QPointF(i * .22 - 1, 1))
    p.restore()
    _outlined_stroke(p, '#8a5a2a', .1, (-.85, -.72), (.85, -.72))
    _outline(p); p.setBrush(_metal('iron'))
    for x in (-.85, .85):
        p.drawEllipse(QPointF(x, -.72), .1, .1)


def _d_pole(p):
    _outlined_stroke(p, _grad(-1, 1, 1, -1, '#7a4a20', '#d7a464'), .14, (-.88, .88), (.8, -.8))
    _outline(p); p.setBrush(_metal('iron'))
    p.save(); p.translate(.78, -.78); p.rotate(-45)
    p.drawPath(_path([(-.1, -.1), (.22, 0), (-.1, .1)]))
    p.restore()
    for t in (-.55, -.25, .05, .35):
        p.setPen(QPen(_c('#f5e7c6'), .05, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(t - .07, -t - .07), QPointF(t + .07, -t + .07))
    _sparkle(p, -.2, -.5, .14, '#fff7d0')


def _d_garlic(p):
    for dx, dy, k in ((-.38, .15, .85), (.38, .18, .85), (0, 0, 1.0)):
        _outline(p)
        p.setBrush(_grad(dx - .5, dy - .5, dx + .5, dy + .6, '#ffffff', '#e8d9c0', '#b8a07a'))
        p.drawPath(_path([(dx, dy - .75 * k), (dx + .1 * k, dy - .4 * k, dx + .45 * k, dy - .15 * k),
                          (dx + .6 * k, dy + .2 * k, dx + .35 * k, dy + .55 * k), (dx, dy + .65 * k, dx - .35 * k, dy + .55 * k),
                          (dx - .6 * k, dy + .2 * k, dx - .45 * k, dy - .15 * k), (dx - .1 * k, dy - .4 * k, dx, dy - .75 * k)]))
        p.setPen(QPen(_c('#b39a74'), .03)); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(dx, dy - .45 * k), QPointF(dx, dy + .55 * k))
        p.drawArc(QRectF(dx - .3 * k, dy - .4 * k, .3 * k, .95 * k), 90 * 16, 120 * 16)


def _d_fire_capsules(p):
    _outline(p)
    p.setBrush(_grad(-1, 0, 1, 1, '#b4743c', '#4a2410'))
    p.drawPath(_path([(-.75, -.05), (.75, -.05), (.85, .7, .0, .85), (-.85, .7, -.75, -.05)]))
    for x, y in ((-.5, -.25), (-.17, -.38), (.17, -.38), (.5, -.25), (0, -.65)):
        _glow(p, x, y, .28, '#ff8a1a', 120)
        _outline(p)
        g = QRadialGradient(QPointF(x - .05, y - .06), .2); g.setColorAt(0, _c('#ffe08a')); g.setColorAt(1, _c('#c0300c'))
        p.setBrush(g); p.drawEllipse(QPointF(x, y), .17, .17)
    p.setPen(QPen(_c('#e0c070'), .05)); p.drawLine(QPointF(-.7, .1), QPointF(.7, .1))


def _d_nose_filters(p):
    p.setPen(QPen(_c('#c9a86a'), .05)); p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(-.35, -.2)); path.quadTo(0, .7, .35, -.2); p.drawPath(path)
    for dx in (-.35, .35):
        _outline(p)
        p.setBrush(_grad(dx - .2, -.8, dx + .2, -.1, '#f4f6f8', '#9aa6b2'))
        p.drawPath(_path([(dx - .14, -.2), (dx - .2, -.65), (dx - .2, -.82, dx, -.82), (dx + .2, -.82, dx + .2, -.65), (dx + .14, -.2)]))
        p.setPen(QPen(_c('#5c6470'), .03))
        for y in (-.6, -.45, -.3):
            p.drawLine(QPointF(dx - .15, y), QPointF(dx + .15, y))
    _sparkle(p, .0, .55, .14, '#e8f8ff')


def _d_elven_bread(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#9be07a', '#2f6a22'))
    p.drawPath(_path([(-.9, .25), (-.4, -.75, .6, -.6), (.9, -.2), (.4, .75, -.9, .25)]))
    p.setBrush(_grad(-.6, -.4, .6, .5, '#f6d79a', '#b0732e'))
    p.drawRoundedRect(QRectF(-.55, -.3, 1.1, .6), .25, .25)
    p.setPen(QPen(_c('#8a5420'), .045))
    for x in (-.25, 0, .25):
        p.drawLine(QPointF(x - .06, -.2), QPointF(x + .06, .2))
    p.setPen(QPen(_c('#1f4a1a'), .04))
    p.drawLine(QPointF(-.85, .22), QPointF(.85, -.18))


def _d_biscuits_worms(p):
    for x, y in ((-.3, .2), (.3, -.05)):
        _outline(p)
        p.setBrush(_grad(x - .4, y - .4, x + .4, y + .4, '#d9b27a', '#7a5428'))
        p.drawEllipse(QPointF(x, y), .5, .45)
        p.setPen(Qt.NoPen); p.setBrush(_c('#5b3a1a'))
        for ox, oy in ((-.18, -.1), (.12, -.15), (0, .15), (.2, .12)):
            p.drawEllipse(QPointF(x + ox, y + oy), .04, .04)
    for x1, y1, x2, y2 in ((-.6, .45, -.2, .6), (.2, -.3, .7, -.35), (.05, .35, .3, .5)):
        _outlined_stroke(p, '#e58aa0', .09, (x1, y1), ((x1 + x2) / 2, y1 - .18, x2, y2))


def _flute(p, metal, holes='#2a170c'):
    p.save(); p.rotate(-35)
    _outline(p)
    p.setBrush(_metal(metal, 0, -.15, 0, .15))
    p.drawRoundedRect(QRectF(-.92, -.12, 1.84, .24), .1, .1)
    p.setBrush(_metal(metal, 0, -.18, 0, .18))
    p.drawRect(QRectF(-.92, -.15, .22, .3))
    p.setPen(Qt.NoPen); p.setBrush(_c(holes))
    for x in (-.35, -.12, .1, .32, .55):
        p.drawEllipse(QPointF(x, 0), .05, .05)
    p.restore()


def _d_flute_copper(p):
    _flute(p, 'copper')


def _d_flute_dragon(p):
    _glow(p, 0, 0, .9, '#6ee09a', 110)
    _flute(p, 'copper')
    p.setPen(QPen(_c('#c8ffd8'), .06)); p.setBrush(Qt.NoBrush)
    for x, y in ((.35, -.65), (-.55, .55)):
        p.drawLine(QPointF(x, y), QPointF(x, y - .28))
        p.setPen(Qt.NoPen); p.setBrush(_c('#c8ffd8')); p.drawEllipse(QPointF(x - .07, y), .08, .06)
        p.setPen(QPen(_c('#c8ffd8'), .06)); p.setBrush(Qt.NoBrush)


def _d_whistle(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#e2b06d', '#7a4a20'))
    p.drawPath(_path([(-.85, -.18), (.25, -.18), (.25, -.45), (.85, -.45, .85, .1), (.85, .5, .3, .5),
                      (-.85, .18)]))
    p.setBrush(_c('#2a170c')); p.drawRect(QRectF(-.35, -.2, .2, .12))
    p.setPen(QPen(_c('#5b3417'), .03))
    p.drawLine(QPointF(-.6, -.12), QPointF(-.6, .12)); p.drawLine(QPointF(.1, -.15), QPointF(.1, .4))
    p.setPen(QPen(_c('#e8c98a'), .04)); p.setBrush(Qt.NoBrush); p.drawEllipse(QPointF(.55, .03), .14, .14)


def _d_bell(p):
    _outline(p)
    p.setBrush(_metal('copper', -.6, -.6, .6, .7))
    p.drawPath(_path([(-.7, .55), (-.55, .4, -.5, -.1), (-.45, -.7, 0, -.7), (.45, -.7, .5, -.1), (.55, .4, .7, .55)]))
    p.drawEllipse(QPointF(0, .82), .14, .14)
    p.setBrush(_metal('copper', -.8, .5, .8, .7)); p.drawRoundedRect(QRectF(-.75, .5, 1.5, .18), .08, .08)
    p.setBrush(Qt.NoBrush); p.setPen(QPen(QBrush(_metal('copper')), .09)); p.drawArc(QRectF(-.15, -.95, .3, .3), 0, 180 * 16)
    p.setPen(QPen(_c('#ffd7b0', 150), .05)); p.drawLine(QPointF(-.28, -.4), QPointF(-.35, .3))


def _d_dragon_tooth(p):
    _outline(p)
    p.setBrush(_grad(-.6, -.9, .6, .9, '#fffaf0', '#e8dcc0', '#9a8a68'))
    p.drawPath(_path([(-.5, -.75), (.45, -.85), (.35, -.3, .1, .2), (-.05, .55, -.3, .95), (-.25, .4, -.45, -.1),
                      (-.6, -.5, -.5, -.75)]))
    p.setBrush(_grad(-.5, -.9, .5, -.6, '#c88a6a', '#7a3a2a'))
    p.drawPath(_path([(-.5, -.75), (.45, -.85), (.42, -.65), (-.47, -.55)]))
    p.setPen(QPen(_c('#ffffff', 170), .04)); p.drawLine(QPointF(-.25, -.35), QPointF(-.15, .25))


def _d_rock_shard(p):
    _outline(p)
    p.setBrush(_grad(-.8, -.8, .8, .8, '#b5aea4', '#6e675e', '#3a352f'))
    p.drawPolygon(_poly((-.75, .15), (-.45, -.6), (.15, -.8), (.75, -.3), (.65, .45), (.05, .8), (-.6, .6)))
    p.setPen(QPen(_c('#2a2520'), .04)); p.setBrush(Qt.NoBrush)
    p.drawPolyline(_poly((-.45, -.6), (-.1, -.1), (.05, .8)))
    p.drawPolyline(_poly((-.1, -.1), (.65, -.05)))
    p.setPen(Qt.NoPen); p.setBrush(_c('#5a7a3a', 200))
    p.drawEllipse(QPointF(.35, .3), .14, .1); p.drawEllipse(QPointF(-.4, .3), .1, .08)


def _d_clay_hand(p):
    _outline(p)
    p.setBrush(_grad(-.8, -.8, .8, .8, '#e0785a', '#9a3418', '#5a1a0c'))
    hand = _path([(-.45, .9), (-.5, .2), (-.8, -.1), (-.78, -.28, -.6, -.22), (-.38, -.02), (-.4, -.72),
                  (-.38, -.86, -.25, -.86), (-.14, -.86, -.15, -.72), (-.13, -.2), (-.1, -.88),
                  (-.08, -1.0, .05, -1.0), (.17, -1.0, .16, -.88), (.13, -.2), (.22, -.8), (.24, -.92, .36, -.9),
                  (.48, -.88, .46, -.76), (.36, -.12), (.5, -.6), (.53, -.72, .64, -.68), (.73, -.64, .7, -.54),
                  (.52, .3), (.42, .9)])
    p.drawPath(hand)
    p.setPen(QPen(_c('#5a1a0c', 160), .035))
    p.drawLine(QPointF(-.2, .35), QPointF(.25, .2)); p.drawLine(QPointF(-.15, -.05), QPointF(.05, .15))


def _d_silver_box(p):
    _outline(p)
    p.setBrush(_metal('silver', -.8, -.2, .8, .8))
    p.drawRect(QRectF(-.75, -.15, 1.5, .85))
    p.setBrush(_metal('silver', -.8, -.7, .8, -.1))
    p.drawPath(_path([(-.82, -.15), (-.82, -.4), (-.6, -.7, 0, -.7), (.6, -.7, .82, -.4), (.82, -.15)]))
    p.setBrush(_metal('gold')); p.drawRect(QRectF(-.1, -.22, .2, .28))
    p.setPen(QPen(_c('#7d8794'), .04)); p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(-.6, .02, 1.2, .52))
    _sparkle(p, -.5, -.45, .14)


def _d_powder(p):
    _bottle(p, 'vial', ('#e8f0ff', '#9ab0e0', 230), None, level=.45, cork='#7a5a3a')
    for x, y, r in ((-.08, .25, .1), (.1, .55, .08), (-.05, .7, .07), (.4, -.6, .14), (-.45, -.35, .1)):
        _sparkle(p, x, y, r, '#ffffff')
    # Plume de lévitation.
    _outline(p)
    p.setBrush(_grad(.4, -.2, .9, .6, '#ffffff', '#c9d6e0'))
    p.drawPath(_path([(.45, .85), (.55, .2, .85, -.15), (.9, .4, .45, .85)]))


def _d_belladonna(p):
    _outlined_stroke(p, '#3f6a2a', .07, (0, .9), (0, -.1))
    for sx in (-1, 1):
        _outline(p); p.setBrush(_grad(-1, -1, 1, 1, '#6fb04a', '#1f4a1a'))
        p.drawPath(_path([(0, .45), (sx * .3, .05, sx * .82, .15), (sx * .55, .6, 0, .45)]))
    _outline(p); p.setBrush(_grad(-.4, -.8, .4, 0, '#8c5bb0', '#3a1f5a'))
    p.drawPath(_path([(0, -.1), (-.38, -.25, -.28, -.6), (0, -.45), (.28, -.6), (.38, -.25, 0, -.1)]))
    for x, y in ((-.55, -.35), (.55, -.4), (.42, -.75)):
        g = QRadialGradient(QPointF(x - .04, y - .05), .16); g.setColorAt(0, _c('#7a6a9a')); g.setColorAt(1, _c('#0e0a18'))
        _outline(p); p.setBrush(g); p.drawEllipse(QPointF(x, y), .13, .13)


def _d_candle_blue(p):
    _glow(p, 0, -.6, .55, '#ffd27a', 160)
    _outline(p)
    p.setBrush(_grad(-.3, 0, .3, 0, '#9fc4ff', '#2a4fa8'))
    p.drawPath(_path([(-.25, -.35), (.25, -.35), (.25, .6), (-.25, .6)]))
    p.setBrush(_grad(-.25, -.45, .25, -.25, '#cfe0ff', '#6f8fd8'))
    p.drawPath(_path([(-.25, -.35), (-.1, -.42), (.05, -.3), (.25, -.38), (.25, -.2), (-.25, -.2)]))
    p.setBrush(_metal('bronze', -.7, .5, .7, .9))
    p.drawEllipse(QRectF(-.62, .55, 1.24, .3))
    p.setPen(Qt.NoPen); p.setBrush(_c('#ff9a2e'))
    p.drawPath(_path([(0, -.9), (.18, -.6, 0, -.42), (-.18, -.6, 0, -.9)]))
    p.setBrush(_c('#fff3c0')); p.drawEllipse(QPointF(0, -.55), .05, .08)


def _d_cheese(p):
    _outline(p)
    p.setBrush(_grad(-.8, -.5, .8, .7, '#ffe07a', '#d9a02a'))
    p.drawPolygon(_poly((-.85, .1), (.8, -.55), (.85, .55), (-.85, .65)))
    p.setBrush(_grad(-.8, -.6, .8, .1, '#fff0b0', '#f0c050'))
    p.drawPolygon(_poly((-.85, .1), (.8, -.55), (.85, -.35)))
    p.setPen(Qt.NoPen); p.setBrush(_c('#b07a1a'))
    for x, y, r in ((-.4, .38, .1), (.15, .2, .13), (.55, .35, .08), (.4, -.05, .07)):
        p.drawEllipse(QPointF(x, y), r, r)


def _d_case(p):
    _outline(p)
    p.setBrush(Qt.NoBrush); p.setPen(QPen(_c('#3f1f0c'), .1)); p.drawArc(QRectF(-.3, -.75, .6, .5), 0, 180 * 16)
    _outline(p)
    p.setBrush(_grad(-1, -.5, 1, .9, '#b57a44', '#4f2810'))
    p.drawRoundedRect(QRectF(-.88, -.5, 1.76, 1.25), .14, .14)
    p.setPen(QPen(_c('#e8c98a', 160), .03, Qt.DashLine))
    p.drawRoundedRect(QRectF(-.78, -.4, 1.56, 1.05), .1, .1)
    _outline(p); p.setBrush(_metal('gold'))
    for x in (-.5, .5):
        p.drawRect(QRectF(x - .1, -.55, .2, .22))


def _d_y_stick(p, count=1):
    sticks = ((0, 0, 0),) if count == 1 else ((-.28, .05, -10), (.28, -.05, 12))
    for dx, dy, angle in sticks:
        p.save(); p.translate(dx, dy); p.rotate(angle)
        k = 1 if count == 1 else .78
        brush = _grad(-1, -1, 1, 1, '#c98a45', '#5b3417')
        _outlined_strokes(p, brush, .15 * k, [((0, .9 * k), (0, -.05 * k)),
                                             ((0, 0), (-.08 * k, -.45 * k, -.5 * k, -.85 * k)),
                                             ((0, 0), (.08 * k, -.45 * k, .5 * k, -.85 * k))])
        p.restore()


def _d_y_sticks(p):
    _d_y_stick(p, 2)


def _d_scroll(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#f5e7c6', '#b8955a'))
    p.drawRect(QRectF(-.62, -.62, 1.24, 1.24))
    for y in (-.7, .7):
        p.setBrush(_grad(0, y - .15, 0, y + .15, '#f5e7c6', '#9a7a48'))
        p.drawRoundedRect(QRectF(-.8, y - .15, 1.6, .3), .15, .15)
    p.setPen(QPen(_c('#6b4a2a', 150), .035))
    for y in (-.35, -.18, -.01, .16):
        p.drawLine(QPointF(-.45, y), QPointF(.45 if y < .1 else .1, y))
    _outline(p); p.setBrush(_grad(.1, .2, .5, .6, '#d0404a', '#6c1f2a'))
    p.drawEllipse(QPointF(.32, .35), .17, .17)


def _d_vampire_book(p):
    _outline(p)
    p.setBrush(_c('#f0e2c0')); p.drawRect(QRectF(-.6, -.78, 1.38, 1.58))
    p.setBrush(_grad(-1, -1, 1, 1, '#8a1f2a', '#2a0a10'))
    p.drawRoundedRect(QRectF(-.75, -.85, 1.4, 1.65), .06, .06)
    p.setBrush(_grad(-.8, 0, -.5, 0, '#5a1018', '#1a0508')); p.drawRect(QRectF(-.75, -.85, .22, 1.65))
    p.setPen(Qt.NoPen); p.setBrush(_metal('silver', -.5, -.3, .5, .3))
    p.drawPath(_path([(.0, -.3), (.1, -.42), (.18, -.3), (.55, -.42), (.42, -.1), (.3, -.15), (.18, .05),
                      (.0, -.08), (-.18, .05), (-.3, -.15), (-.42, -.1), (-.55, -.42), (-.18, -.3), (-.1, -.42)]).translated(.06, .05))
    p.setPen(QPen(_c('#d8b46c'), .03)); p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(-.45, -.7, 1.0, 1.35))


def _d_lantern_magic(p):
    glow = QRadialGradient(QPointF(0, .15), 1.1)
    glow.setColorAt(0, _c('#9ad8ff', 210)); glow.setColorAt(1, _c('#6a4aff', 0))
    p.setPen(Qt.NoPen); p.setBrush(glow); p.drawEllipse(QPointF(0, .15), 1.1, 1.1)
    p.setPen(QPen(_c('#2a1a10'), .09)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.25, -.95, .5, .45), 0, 180 * 16)
    _outline(p); p.setBrush(_metal('gold', -.5, -.7, .5, -.4))
    p.drawRect(QRectF(-.5, -.6, 1.0, .18)); p.drawRect(QRectF(-.5, .7, 1.0, .18))
    p.setBrush(_c('#c8ecff', 220)); p.drawRect(QRectF(-.4, -.42, .8, 1.12))
    p.setPen(Qt.NoPen); p.setBrush(_c('#5a7cff'))
    flame = _path([(0, -.2), (.22, .2, 0, .4), (-.22, .2, 0, -.2)])
    p.drawPath(flame)
    _sparkle(p, .55, -.3, .16, '#e8f6ff')


# ------------------------------------------------- La Cité des Voleurs (phase 5)
# Mêmes familles et même éclairage que les dessins des deux premiers grimoires :
# rien n'illustre ce que fait l'objet, seulement ce qu'il est.
def _d_ring_fire(p):
    _glow(p, 0, -.5, .62, '#ff7a1a', 150)
    _ring(p, 'gold', '#e8401a', stone_r=.25)
    p.setPen(Qt.NoPen)
    for x, h in ((-.22, .32), (0, .42), (.22, .3)):
        p.setBrush(_c('#ffb02e', 220))
        p.drawPath(_path([(x, -.62 - h), (x + .1, -.72, x, -.66), (x - .1, -.72, x, -.62 - h)]))


def _d_ring_ice(p):
    _ring(p, 'silver', '#9fe3ff', stone_r=.28)
    p.setPen(QPen(_c('#e8fbff', 230), .05, Qt.SolidLine, Qt.RoundCap))
    for a in range(0, 180, 60):
        r = math.radians(a)
        p.drawLine(QPointF(.62 + math.cos(r) * .18, -.62 + math.sin(r) * .18),
                   QPointF(.62 - math.cos(r) * .18, -.62 - math.sin(r) * .18))
    _sparkle(p, -.62, -.45, .13, '#e8fbff')


def _d_ring_invisible(p):
    p.save()
    p.setOpacity(.5)
    _ring(p, 'silver', '#f4fbff', stone_r=.24)
    p.restore()
    for x, y, r in ((.55, -.55, .16), (-.6, -.2, .12), (.2, .62, .1)):
        _sparkle(p, x, y, r)


def _d_ring_eye(p):
    _ring(p, 'gold', None, thickness=.22)
    _outline(p)
    p.setBrush(_metal('gold', -.5, -.8, .5, -.1))
    p.drawEllipse(QPointF(0, -.48), .5, .32)
    p.setBrush(_c(IVORY))
    p.drawPath(_path([(-.4, -.48), (0, -.78, .4, -.48), (0, -.18, -.4, -.48)]))
    g = QRadialGradient(QPointF(-.05, -.53), .2)
    g.setColorAt(0, _c('#fff0a8')); g.setColorAt(1, _c('#b07a1a'))
    p.setBrush(g)
    p.drawEllipse(QPointF(0, -.48), .17, .17)
    p.setPen(Qt.NoPen); p.setBrush(_c('#1a0f0a'))
    p.drawEllipse(QPointF(0, -.48), .05, .13)


def _d_ring_jewels(p):
    _ring(p, 'gold', None, thickness=.24)
    for x, y, color in ((-.32, -.32, '#2e86de'), (.32, -.32, '#2ecc71'), (0, -.5, '#d6303a')):
        _gem(p, x, y, .17, color, facets=False)


def _brooch_scorpion(metal):
    def draw(p):
        brush = _metal(metal, -.8, -.8, .8, .8)
        # Queue recourbée au-dessus du corps, dard au bout.
        _outlined_stroke(p, brush, .12, (0, .2), (.05, .65, .45, .55), (.75, .4, .62, -.05))
        _outline(p); p.setBrush(brush)
        p.drawPolygon(_poly((.62, -.05), (.48, -.22), (.72, -.2)))
        # Pinces.
        for sx in (-1, 1):
            _outlined_stroke(p, brush, .09, (sx * .18, -.35), (sx * .5, -.5, sx * .55, -.8))
            _outline(p); p.setBrush(brush)
            p.drawEllipse(QPointF(sx * .58, -.82), .14, .1)
        # Pattes.
        p.setPen(QPen(_c(METALS[metal][2]), .05, Qt.SolidLine, Qt.RoundCap))
        for dy in (-.15, 0, .15):
            p.drawLine(QPointF(-.18, dy), QPointF(-.5, dy + .12))
            p.drawLine(QPointF(.18, dy), QPointF(.5, dy + .12))
        _outline(p); p.setBrush(brush)
        p.drawEllipse(QPointF(0, -.02), .22, .36)
        p.drawEllipse(QPointF(0, -.42), .13, .1)
        p.setPen(QPen(_c(METALS[metal][2]), .03))
        for dy in (-.12, .05, .2):
            p.drawLine(QPointF(-.18, dy), QPointF(.18, dy))
        _sparkle(p, -.08, -.18, .1)
    return draw


def _d_bracelet_insect(p):
    _outline(p)
    p.setBrush(_metal('silver', -.8, -.5, .8, .5))
    p.drawPath(_annulus(0, .1, .85, .52, .66, .34, 0, .07))
    _outline(p)
    p.setBrush(_grad(-.3, .1, .3, .7, '#9fe0b0', '#1f6a4a'))
    p.drawEllipse(QPointF(0, .52), .3, .24)
    _emblem_bug('#d4d9e0')(p, QPointF(0, .52))


def _d_pearls_black(p):
    p.setPen(QPen(_c('#d4d9e0'), .04)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.82, -.7, 1.64, 1.4), 200 * 16, 140 * 16)
    for i in range(6):
        a = math.radians(205 + i * 26)
        x, y = math.cos(a) * .78, -math.sin(a) * .66
        g = QRadialGradient(QPointF(x - .06, y - .07), .22)
        g.setColorAt(0, _c('#8a8aa0')); g.setColorAt(.5, _c('#2a2a38')); g.setColorAt(1, _c('#0a0a10'))
        _outline(p); p.setBrush(g)
        p.drawEllipse(QPointF(x, y), .18, .18)
        _highlight(p, QRectF(x - .1, y - .11, .07, .05), 170)


def _d_skeleton_key(p):
    """Passe-partout : un anneau d'acier portant trois crochets fins."""
    _outline(p)
    p.setBrush(_metal('iron'))
    p.drawPath(_annulus(-.5, -.5, .3, .3, .17, .17))
    for angle, length, bit in ((-8, 1.25, (.12, .1)), (8, 1.15, (.1, -.12)), (0, 1.35, (.14, 0))):
        p.save(); p.translate(-.5, -.5); p.rotate(45 + angle)
        _outlined_stroke(p, _metal('steel'), .07, (.3, 0), (length, 0))
        _outlined_stroke(p, _metal('steel'), .07, (length, 0), (length + bit[0], bit[1]))
        p.restore()


def _d_key_iron(p):
    _key(p, 'iron')
    p.setPen(QPen(_c('#b9b4ad', 150), .04)); p.drawLine(QPointF(-.1, -.06), QPointF(.4, .44))


def _d_key_dwarf(p):
    _key(p, 'bronze', bow='trefoil')
    _gem(p, -.42, -.42, .12, '#3fd1a4', facets=False)
    p.setPen(QPen(_c('#5a3a17'), .035))
    for t in (.05, .2, .35):
        p.drawLine(QPointF(t - .05, t + .05), QPointF(t + .05, t - .05))


def _d_keyring(p):
    _outline(p); p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(_metal('iron')), .1))
    p.drawEllipse(QPointF(0, -.55), .3, .3)
    for angle, metal in ((-35, 'iron'), (0, 'bronze'), (35, 'steel')):
        p.save(); p.translate(0, -.3); p.rotate(angle)
        brush = _metal(metal)
        _outlined_stroke(p, brush, .12, (0, 0), (0, 1.0))
        _outlined_stroke(p, brush, .1, (0, .85), (.2, .85))
        _outlined_stroke(p, brush, .1, (0, .68), (.16, .68))
        _outline(p); p.setBrush(brush); p.drawEllipse(QPointF(0, .05), .12, .12)
        p.restore()


def _d_poultice(p):
    for sx in (-1, 1):
        _outline(p); p.setBrush(_grad(-1, -1, 1, 1, '#8fd06a', '#2f6a22'))
        p.drawPath(_path([(0, -.2), (sx * .35, -.95, sx * .85, -.7), (sx * .6, -.15, 0, -.2)]))
    _outline(p)
    p.setBrush(_grad(-.8, -.4, .8, .8, '#f5ecd6', '#c9b48a'))
    p.drawRoundedRect(QRectF(-.75, -.35, 1.5, 1.1), .18, .18)
    p.setBrush(_grad(-.2, -.4, .2, .8, '#8a5a2a', '#5b3417'))
    p.drawRect(QRectF(-.12, -.38, .24, 1.16))
    p.setPen(QPen(_c('#5a8a3a', 170), .05))
    for x in (-.5, .45):
        p.drawLine(QPointF(x - .1, .1), QPointF(x + .12, .45))


def _d_shield_tower(p):
    _glow(p, 0, 0, 1.0, '#7d3fb8', 90)
    _outline(p)
    body = QRectF(-.6, -.92, 1.2, 1.84)
    p.setBrush(_metal('iron', -.6, -.9, .6, .9))
    p.drawRoundedRect(body, .14, .14)
    p.setBrush(_grad(-.5, -.8, .5, .8, '#4a3a5a', '#1a1222'))
    p.drawRoundedRect(body.adjusted(.12, .12, -.12, -.12), .08, .08)
    p.setPen(QPen(_c('#8a7a9a'), .05))
    p.drawLine(QPointF(0, -.75), QPointF(0, .75))
    _outline(p); p.setBrush(_metal('iron'))
    for y in (-.6, .6):
        for x in (-.38, .38):
            p.drawEllipse(QPointF(x, y), .06, .06)


def _d_shield_magnificent(p):
    _outline(p)
    outer = _path([(-.78, -.78), (.78, -.78), (.72, .05), (.5, .62, 0, .95), (-.5, .62, -.72, .05)])
    p.setBrush(_metal('gold', -.8, -.8, .8, .8))
    p.drawPath(outer)
    inner = _path([(-.62, -.64), (.62, -.64), (.57, .03), (.4, .5, 0, .76), (-.4, .5, -.57, .03)])
    p.setBrush(_metal('silver', -.6, -.6, .6, .6))
    p.drawPath(inner)
    p.setPen(QPen(_c(GOLD_DARK), .05)); p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(-.55, -.2), QPointF(.55, -.2))
    _gem(p, 0, .12, .2, '#2e86de')
    for x in (-.4, .4):
        _gem(p, x, -.45, .1, '#d6303a', facets=False)


def _d_shield_knight(p):
    _outline(p)
    path = _path([(-.75, -.8), (.75, -.8), (.72, -.05), (.48, .6, 0, .92), (-.48, .6, -.72, -.05)])
    p.setBrush(_metal('steel', -.8, -.8, .8, .8))
    p.drawPath(path)
    inner = _path([(-.62, -.68), (.62, -.68), (.6, -.06), (.4, .5, 0, .78), (-.4, .5, -.6, -.06)])
    p.setBrush(_grad(-.6, -.6, .6, .6, '#d0404a', '#5e1410'))
    p.drawPath(inner)
    _emblem_cross('silver')(p, QPointF(0, -.02))


def _petal_flower(p, x, y, r, petals, fill, center, outline=True):
    for i in range(petals):
        a = math.radians(i * 360 / petals - 90)
        px, py = x + math.cos(a) * r * .55, y + math.sin(a) * r * .55
        p.save(); p.translate(px, py); p.rotate(i * 360 / petals)
        if outline:
            _outline(p)
        else:
            p.setPen(Qt.NoPen)
        p.setBrush(_grad(0, -r * .4, 0, r * .4, *fill))
        p.drawEllipse(QPointF(0, 0), r * .22, r * .45)
        p.restore()
    _outline(p); p.setBrush(_c(center))
    p.drawEllipse(QPointF(x, y), r * .26, r * .26)


def _d_flower_golden(p):
    _glow(p, 0, -.15, .95, '#ffe680', 120)
    _outlined_stroke(p, '#6a8a2a', .08, (0, .25), (-.05, .6, .1, .95))
    _petal_flower(p, 0, -.15, .8, 10, ('#fff3b0', '#c8961e'), '#b0520c')


def _d_lotus(p):
    _outline(p)
    p.setBrush(_grad(-1, .4, 1, .9, '#6fb04a', '#1f4a1a'))
    p.drawEllipse(QRectF(-.9, .45, 1.8, .4))
    for angle, scale in ((-55, .8), (55, .8), (-25, .95), (25, .95), (0, 1.0)):
        p.save(); p.translate(0, .5); p.rotate(angle)
        _outline(p)
        p.setBrush(_grad(0, -1, 0, 0, '#fff0f6', '#e86aa0'))
        p.drawPath(_path([(0, 0), (-.28 * scale, -.45 * scale, 0, -1.0 * scale), (.28 * scale, -.45 * scale, 0, 0)]))
        p.restore()
    p.setPen(Qt.NoPen); p.setBrush(_c('#ffd84a')); p.drawEllipse(QPointF(0, .38), .12, .07)


def _d_bouquet(p):
    for x1, x2 in ((-.1, -.45), (0, 0), (.1, .45)):
        _outlined_stroke(p, '#4f7a2a', .07, (0, .9), (x1, .3, x2, -.2))
    for x, y, fill, petals in ((-.45, -.3, ('#ffe0ec', '#d6406a'), 5), (.45, -.3, ('#f0e8ff', '#7a5ad8'), 5),
                               (0, -.55, ('#fff8d0', '#e8a81e'), 6)):
        _petal_flower(p, x, y, .5, petals, fill, '#fff3b0')
    _outline(p); p.setBrush(_grad(-.3, .3, .3, .6, '#e86a6a', '#7a1f2a'))
    p.drawPolygon(_poly((-.22, .35), (.22, .35), (.3, .55), (-.3, .55)))


def _d_pass_merchant(p):
    _outline(p)
    p.setBrush(_grad(-1, -1, 1, 1, '#f5e7c6', '#c9a86a'))
    p.drawPolygon(_poly((-.8, -.65), (.8, -.65), (.8, .65), (-.8, .65)))
    p.setPen(QPen(_c('#8a6633', 140), .03))
    p.drawLine(QPointF(-.8, -.1), QPointF(.8, -.1))
    p.setPen(QPen(_c('#5b3417', 150), .035))
    for y in (-.48, -.32):
        p.drawLine(QPointF(-.6, y), QPointF(.6, y))
    p.drawLine(QPointF(-.6, .1), QPointF(.05, .1))
    _outlined_stroke(p, '#c0392b', .07, (.2, .35), (.35, .9))
    _outlined_stroke(p, '#c0392b', .07, (.45, .35), (.5, .92))
    _outline(p); p.setBrush(_grad(.1, .1, .7, .7, '#d0404a', '#6c1f2a'))
    p.drawEllipse(QPointF(.35, .32), .22, .22)
    p.setPen(QPen(_c('#f0a0a0', 180), .04)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(.35, .32), .11, .11)


def _d_witch_hair(p):
    """Mèche grise nouée d'un ruban : une boucle effilée en S."""
    lock = _path([(-.18, -.6), (-.55, -.1, -.2, .2), (.2, .5, -.15, .92), (.05, .55, .32, .28),
                  (.62, -.05, .2, -.6)])
    _outline(p)
    p.setBrush(_grad(-.6, -.6, .6, .9, '#c8c8d0', '#6a6a74', '#2e2e36'))
    p.drawPath(lock)
    p.setPen(QPen(_c('#e8e8f0', 150), .03)); p.setBrush(Qt.NoBrush)
    for dx in (-.08, .04, .14):
        path = QPainterPath(QPointF(dx, -.55))
        path.quadTo(dx - .35, -.1, dx * .5, .2); path.quadTo(dx + .25, .45, -.08 + dx * .4, .8)
        p.drawPath(path)
    _outline(p); p.setBrush(_grad(-.4, -.8, .4, -.5, '#e0505a', '#7a1f2a'))
    p.drawPath(_path([(0, -.62), (-.42, -.9), (-.5, -.5)]))
    p.drawPath(_path([(0, -.62), (.42, -.9), (.5, -.5)]))
    p.drawEllipse(QPointF(0, -.62), .11, .09)


def _d_mirror(p):
    _outlined_stroke(p, _metal('silver'), .2, (.3, .3), (.85, .85))
    _outline(p)
    p.setBrush(_metal('silver', -.8, -.8, .4, .4))
    p.drawEllipse(QPointF(-.2, -.2), .68, .68)
    g = QLinearGradient(QPointF(-.7, -.7), QPointF(.3, .3))
    g.setColorAt(0, _c('#f4fbff')); g.setColorAt(.6, _c('#9ec4dc')); g.setColorAt(1, _c('#5a7a94'))
    p.setBrush(g)
    p.drawEllipse(QPointF(-.2, -.2), .54, .54)
    p.setPen(QPen(_c('#ffffff', 200), .06, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(-.5, -.25), QPointF(-.25, -.5))


def _d_glass_ball(p):
    _outline(p)
    p.setBrush(_grad(-.6, .4, .6, .9, '#b57a44', '#4f2810'))
    p.drawPolygon(_poly((-.5, .9), (.5, .9), (.32, .5), (-.32, .5)))
    g = QRadialGradient(QPointF(-.2, -.35), .9)
    g.setColorAt(0, _c('#ffffff', 230)); g.setColorAt(.4, _c('#b8d8f0', 170)); g.setColorAt(1, _c('#4a6a94', 210))
    _outline(p); p.setBrush(g)
    p.drawEllipse(QPointF(0, -.12), .68, .68)
    _highlight(p, QRectF(-.42, -.55, .22, .16), 200)


def _d_skull_ivory(p):
    p.setPen(QPen(QBrush(_metal('silver')), .06, Qt.DotLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.75, -.95, 1.5, 1.1), 0, 180 * 16)
    _outline(p)
    p.setBrush(_grad(-.5, -.6, .5, .7, '#fffaf0', '#e8dcc0', '#a89a78'))
    p.drawPath(_path([(-.5, .1), (-.55, -.45, 0, -.55), (.55, -.45, .5, .1), (.35, .3), (.3, .65),
                      (-.3, .65), (-.35, .3)]))
    p.setPen(Qt.NoPen); p.setBrush(_c('#3a2a1a'))
    p.drawEllipse(QPointF(-.2, -.08), .14, .12); p.drawEllipse(QPointF(.2, -.08), .14, .12)
    p.drawPolygon(_poly((0, .08), (-.07, .22), (.07, .22)))
    p.setPen(QPen(_c('#8a7a58'), .03))
    for x in (-.15, 0, .15):
        p.drawLine(QPointF(x, .45), QPointF(x, .62))


def _d_owl_gold(p):
    _outline(p)
    p.setBrush(_metal('gold', -.6, -.8, .6, .8))
    p.drawPath(_path([(-.5, .85), (-.62, .1, -.48, -.45), (-.55, -.85), (-.25, -.62), (0, -.68), (.25, -.62),
                      (.55, -.85), (.48, -.45), (.62, .1, .5, .85)]))
    p.setBrush(_c(GOLD_LIGHT))
    for x in (-.22, .22):
        p.drawEllipse(QPointF(x, -.3), .2, .2)
    p.setPen(Qt.NoPen); p.setBrush(_c('#3a2a10'))
    for x in (-.22, .22):
        p.drawEllipse(QPointF(x, -.3), .08, .08)
    _outline(p); p.setBrush(_metal('bronze'))
    p.drawPolygon(_poly((-.07, -.15), (.07, -.15), (0, .02)))
    p.setPen(QPen(_c(GOLD_DARK), .04)); p.setBrush(Qt.NoBrush)
    for y in (.25, .45, .65):
        p.drawArc(QRectF(-.3, y - .1, .6, .2), 200 * 16, 140 * 16)


def _d_gems_two(p):
    _gem(p, -.35, .1, .45, '#d6303a')
    _gem(p, .38, -.15, .4, '#2e86de')


def _emblem_spiral(color):
    def draw(p, c):
        p.setPen(QPen(_c(color), .05, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(c.x(), c.y()))
        for i in range(1, 30):
            a = i * .45
            r = .009 * i
            path.lineTo(c.x() + math.cos(a) * r, c.y() + math.sin(a) * r)
        p.drawPath(path)
    return draw


def _d_potion_mind(p):
    _bottle(p, 'bottle', ('#f0a8ff', '#6a1a8a'), _emblem_spiral('#fff0ff'), level=.3, cork='#3a2410')


def _d_flute_silver(p):
    _flute(p, 'silver')
    _sparkle(p, .45, -.55, .14)


def _d_chalk(p):
    p.save(); p.rotate(-30)
    _outline(p)
    p.setBrush(_grad(0, -.2, 0, .2, '#ffffff', '#d8d4cc'))
    p.drawPolygon(_poly((-.75, -.2), (.55, -.2), (.75, -.05), (.7, .2), (-.75, .2)))
    p.setPen(QPen(_c('#b8b2a8'), .03))
    p.drawLine(QPointF(-.4, -.18), QPointF(-.45, .18))
    p.restore()
    p.setPen(QPen(_c('#f5f2ea', 200), .06, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(-.85, .75)); path.quadTo(-.4, .45, 0, .75); path.quadTo(.4, .95, .85, .7)
    p.drawPath(path)


def _d_eyepatch(p):
    p.setPen(QPen(_c('#3a2a1a'), .06)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-.9, -.75, 1.8, .9), 10 * 16, 160 * 16)
    p.drawLine(QPointF(-.82, -.2), QPointF(-.9, .3)); p.drawLine(QPointF(.82, -.2), QPointF(.9, .3))
    _outline(p)
    p.setBrush(_grad(-.5, -.3, .5, .6, '#4a4048', '#0e0b10'))
    p.drawPath(_path([(-.55, -.2), (.55, -.2), (.5, .3, 0, .6), (-.5, .3, -.55, -.2)]))
    p.setPen(QPen(_c('#8a8090', 140), .04))
    p.drawLine(QPointF(-.35, -.08), QPointF(-.15, .25))


def _d_goblet_silver(p):
    _outline(p)
    p.setBrush(_metal('silver', -.6, -.8, .6, .2))
    p.drawPath(_path([(-.6, -.8), (.6, -.8), (.55, -.2, .1, .05), (-.1, .05), (-.55, -.2, -.6, -.8)]))
    p.setBrush(_metal('silver', -.2, 0, .2, .8))
    p.drawRect(QRectF(-.08, .02, .16, .6))
    p.drawEllipse(QRectF(-.45, .55, .9, .3))
    p.setPen(QPen(_c('#ffffff', 170), .05)); p.drawLine(QPointF(-.38, -.68), QPointF(-.3, -.25))


def _d_chalice_silver(p):
    _outline(p)
    p.setBrush(_metal('silver', -.7, -.9, .7, -.1))
    p.drawPath(_path([(-.7, -.85), (.7, -.85), (.7, -.4, 0, -.15), (-.7, -.4, -.7, -.85)]))
    p.setBrush(_metal('gold', -.2, -.2, .2, .6))
    p.drawPath(_path([(-.1, -.15), (.1, -.15), (.06, .2), (.18, .3), (.06, .4), (.12, .6), (-.12, .6),
                      (-.06, .4), (-.18, .3), (-.06, .2)]))
    p.setBrush(_metal('silver', -.6, .5, .6, .9))
    p.drawPath(_path([(-.12, .55), (.12, .55), (.6, .85), (-.6, .85)]))
    _gem(p, 0, -.55, .12, '#d6303a', facets=False)


def _d_spoon_silver(p):
    p.save(); p.rotate(40)
    _outline(p)
    p.setBrush(_metal('silver', -.3, -.9, .3, -.2))
    p.drawEllipse(QPointF(0, -.55), .3, .4)
    _outlined_stroke(p, _metal('silver', -.1, 0, .1, 1), .11, (0, -.15), (0, .9))
    _outline(p); p.setBrush(_metal('silver'))
    p.drawEllipse(QPointF(0, .88), .1, .1)
    p.setPen(QPen(_c('#ffffff', 180), .05)); p.drawLine(QPointF(-.12, -.75), QPointF(-.15, -.45))
    p.restore()


def _d_knucklebones(p):
    for x, y, angle in ((-.45, -.3, -20), (.4, -.35, 25), (-.25, .4, 60), (.42, .38, -10)):
        p.save(); p.translate(x, y); p.rotate(angle)
        _outline(p)
        p.setBrush(_grad(-.3, -.2, .3, .2, '#fffaf0', '#d8c8a0', '#9a8a68'))
        p.drawPath(_path([(-.3, -.12), (-.38, -.2, -.3, -.24), (0, -.14), (.3, -.24), (.38, -.2, .3, -.12),
                          (.3, .12), (.38, .2, .3, .24), (0, .14), (-.3, .24), (-.38, .2, -.3, .12)]))
        p.restore()


def _d_bread_stale(p):
    _outline(p)
    p.setBrush(_grad(-.8, -.5, .8, .6, '#d0a868', '#8a6030', '#5a3a18'))
    p.drawPath(_path([(-.85, .3), (-.8, -.35, -.2, -.45), (.6, -.5, .85, .0), (.75, .45), (.1, .55),
                      (-.5, .5, -.85, .3)]))
    p.setBrush(_c('#e8d6a8'))
    p.drawPolygon(_poly((.6, -.42), (.85, .0), (.75, .45), (.5, .2)))
    p.setPen(QPen(_c('#4a2e10'), .04)); p.setBrush(Qt.NoBrush)
    p.drawPolyline(_poly((-.5, -.2), (-.35, 0), (-.45, .15)))
    p.drawPolyline(_poly((0, -.3), (.1, -.05), (.0, .2)))
    p.setPen(Qt.NoPen); p.setBrush(_c('#5a7a3a', 200))
    p.drawEllipse(QPointF(-.2, .3), .1, .07); p.drawEllipse(QPointF(.3, .32), .07, .05)


def _d_candle_coloured(p):
    _glow(p, 0, -.6, .55, '#ffd27a', 160)
    _outline(p)
    p.setBrush(_grad(-.3, 0, .3, 0, '#ff9ab8', '#a8204a'))
    p.drawPath(_path([(-.22, -.3), (.22, -.3), (.22, .6), (-.22, .6)]))
    p.setPen(QPen(_c('#ffe0a0', 200), .06))
    for y in (-.05, .2, .45):
        p.drawLine(QPointF(-.2, y), QPointF(.2, y - .08))
    _outline(p)
    p.setBrush(_metal('iron', -.7, .5, .7, .9))
    p.drawEllipse(QRectF(-.55, .55, 1.1, .28))
    p.setPen(Qt.NoPen); p.setBrush(_c('#ff9a2e'))
    p.drawPath(_path([(0, -.85), (.16, -.56, 0, -.38), (-.16, -.56, 0, -.85)]))
    p.setBrush(_c('#fff3c0')); p.drawEllipse(QPointF(0, -.5), .05, .07)


def _d_butcher_hook(p):
    _outline(p)
    p.setBrush(_grad(-.4, -.95, .4, -.5, '#a86c34', '#5b3417'))
    p.drawRoundedRect(QRectF(-.45, -.95, .9, .3), .1, .1)
    _outlined_stroke(p, _metal('steel', -.5, -.6, .5, .9), .13, (0, -.66), (0, .1), (0, .78, -.4, .72),
                     (-.7, .65, -.62, .3))
    _outline(p); p.setBrush(_metal('steel'))
    p.drawPolygon(_poly((-.7, .32), (-.52, .32), (-.62, .12)))


def _d_rope_plain(p):
    brush = _grad(-1, -1, 1, 1, '#d8b47a', '#7a4a1a')
    for r in (.72, .52, .32):
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_c(OUTLINE), .17)); p.drawEllipse(QPointF(0, .05), r, r * .75)
        p.setPen(QPen(QBrush(brush), .12)); p.drawEllipse(QPointF(0, .05), r, r * .75)
    p.setPen(QPen(_c('#5b3417'), .025))
    for i in range(16):
        a = math.radians(i * 22.5)
        p.drawLine(QPointF(math.cos(a) * .67, .05 + math.sin(a) * .5), QPointF(math.cos(a) * .77, .05 + math.sin(a) * .58))
    _outlined_stroke(p, brush, .12, (.6, .45), (.85, .85))
    _outline(p); p.setBrush(_metal('iron'))
    p.drawPolygon(_poly((.78, .78), (.98, .7), (.9, .98)))


def _d_boots_magic(p):
    _glow(p, 0, .2, 1.0, '#7ad8ff', 110)
    for dx, light, dark in ((.18, '#5a7ab0', '#1a2a50'), (-.18, '#4a6698', '#14203e')):
        _outline(p)
        p.setBrush(_grad(-1, -1, 1, 1, light, dark))
        p.drawPath(_path([(-.35 + dx, -.75), (.15 + dx, -.75), (.12 + dx, .35), (.6 + dx, .5), (.62 + dx, .85),
                          (-.38 + dx, .85)]))
        p.setBrush(_metal('gold', -1, -.8, 1, -.6))
        p.drawRect(QRectF(-.37 + dx, -.78, .54, .14))
    for x, y in ((.55, -.6), (-.7, -.2), (.7, .1)):
        _sparkle(p, x, y, .15, '#dff6ff')


class _Legacy(str):
    """Tracé historique de adventurer_sheet.draw_item_art, peint en pixels."""


def _legacy(kind):
    return _Legacy(kind)


DRAWINGS = {
    # Départ commun : tracés historiques conservés.
    'sword': _legacy('sword'), 'armor': _legacy('armor'), 'lantern': _legacy('lantern'),
    # Armes.
    'sword_magic': _d_sword_magic, 'sword_enchanted': _d_sword_enchanted, 'sword_river': _d_sword_river,
    'knife': _d_knife, 'bow': _d_bow, 'arrow_silver': _d_arrow_silver, 'dart_silver': _d_dart_silver,
    'spear': _d_spear, 'stakes': _d_stakes, 'chisel_silver': _d_chisel, 'mallet': _d_mallet,
    'hammer_head': _d_hammer_head, 'hammer_handle': _d_hammer_handle,
    # Protections et équipement porté.
    'armor_chain': _d_armor_found, 'helmet_magic': _d_helmet_magic, 'helmet_cursed': _d_helmet_cursed,
    'shield_wood': _d_shield_wood, 'shield_crescent': _d_shield_crescent, 'shield_emperor': _d_shield_emperor,
    'bracer_strength': _d_bracer_strength, 'bracelet_skill': _d_bracelet_skill, 'gauntlet': _d_gauntlet,
    'glove_throw': _d_glove_throw, 'glove_black': _d_glove_black, 'boots_leap': _d_boots,
    'headband': _d_headband,
    # Potions et liquides.
    'potion_healing': _d_potion_healing, 'potion_plants': _d_potion_plants,
    'potion_tranquil': _d_potion_tranquil, 'potion_insects': _d_potion_insects,
    'potion_antidote': _d_potion_antidote, 'holy_water_vial': _d_holy_water_foret,
    'holy_water_bottle': _d_holy_water_sorcier, 'potion_force': _d_potion_force,
    'potion_invisibility': _d_potion_invisible, 'powder_levitation': _d_powder,
    # Bijoux et trésors.
    'ring_light': _d_ring_light, 'ring_slow': _d_ring_slow, 'ring_gold': _d_ring_gold,
    'ring_emerald': _d_ring_emerald, 'earring_gold': _d_earring_gold, 'earrings_blue': _d_earrings,
    'medallion_ruby': _d_medallion_9, 'medallion_star': _d_medallion_5, 'collar_leather': _d_collar_leather,
    'collar_skulls': _d_collar_skulls, 'amber_eye': _d_amber_eye, 'crown_fire': _d_crown,
    'crucifix': _d_crucifix, 'gem_statue': _d_gem_statue, 'gold_ingot': _d_gold_ingot,
    # Clés.
    'key_111': _key_with('iron', '111'), 'key_125': _key_with('iron', '125', bow='trefoil'),
    'key_bronze_9': _key_with('bronze', '9'), 'key_bronze_99': _key_with('bronze', '99', bow='trefoil'),
    'key_red_111': _key_with('red', '111', tag='#ffd8d0'), 'key_copper_66': _key_with('copper', '66'),
    'key_boathouse': _d_key_boathouse, 'key_silver_small': _d_key_silver_small,
    # Outils, vivres, curiosités.
    'map_yaztromo': _d_map, 'rope_magic': _d_rope, 'net_capture': _d_net, 'pole_probe': _d_pole,
    'garlic': _d_garlic, 'fire_capsules': _d_fire_capsules, 'nose_filters': _d_nose_filters,
    'elven_bread': _d_elven_bread, 'biscuits_worms': _d_biscuits_worms, 'flute_copper': _d_flute_copper,
    'flute_dragon': _d_flute_dragon, 'whistle_wood': _d_whistle, 'bell_copper': _d_bell,
    'dragon_tooth': _d_dragon_tooth, 'rock_shard': _d_rock_shard, 'clay_hand': _d_clay_hand,
    'silver_box': _d_silver_box, 'belladonna': _d_belladonna, 'candle_blue': _d_candle_blue,
    'cheese': _d_cheese, 'leather_case': _d_case, 'y_stick': _d_y_stick, 'y_sticks': _d_y_sticks,
    'scroll_old': _d_scroll, 'vampire_book': _d_vampire_book, 'lantern_magic': _d_lantern_magic,
    # La Cité des Voleurs : bijoux, clés, armures, curiosités et marchandises.
    'ring_fire': _d_ring_fire, 'ring_ice': _d_ring_ice, 'ring_invisible': _d_ring_invisible,
    'ring_eye': _d_ring_eye, 'ring_jewels': _d_ring_jewels,
    'brooch_scorpion_gold': _brooch_scorpion('gold'), 'brooch_scorpion_silver': _brooch_scorpion('silver'),
    'brooch_scorpion_copper': _brooch_scorpion('copper'), 'bracelet_insect': _d_bracelet_insect,
    'pearls_black': _d_pearls_black, 'gems_two': _d_gems_two, 'owl_gold': _d_owl_gold,
    'skull_ivory': _d_skull_ivory, 'key_skeleton': _d_skeleton_key, 'key_iron': _d_key_iron,
    'key_dwarf': _d_key_dwarf, 'keyring': _d_keyring, 'shield_tower': _d_shield_tower,
    'shield_magnificent': _d_shield_magnificent, 'shield_knight': _d_shield_knight,
    'boots_magic': _d_boots_magic, 'eyepatch': _d_eyepatch, 'poultice': _d_poultice,
    'potion_mind': _d_potion_mind, 'flower_golden': _d_flower_golden, 'lotus': _d_lotus,
    'bouquet': _d_bouquet, 'witch_hair': _d_witch_hair, 'pass_merchant': _d_pass_merchant,
    'mirror': _d_mirror, 'glass_ball': _d_glass_ball, 'flute_silver': _d_flute_silver,
    'chalk': _d_chalk, 'goblet_silver': _d_goblet_silver, 'chalice_silver': _d_chalice_silver,
    'spoon_silver': _d_spoon_silver, 'knucklebones': _d_knucklebones, 'bread_stale': _d_bread_stale,
    'candle_coloured': _d_candle_coloured, 'butcher_hook': _d_butcher_hook, 'rope_plain': _d_rope_plain,
}

# Nom exact de l'objet dans la sacoche → dessin. Les variantes d'apostrophe et
# de casse sont absorbées par item_icon_id ; les alias de la boutique aussi.
ITEM_ICONS = {
    # Équipement de départ (gabarit commun aux deux grimoires).
    'Épée': 'sword', 'Armure de cuir': 'armor', 'Lanterne': 'lantern',
    # La Forêt de la Malédiction — départ et boutique de Yaztromo.
    'Carte de Yaztromo': 'map_yaztromo',
    'Potion de Guérison': 'potion_healing', 'Potion de Contrôle des Plantes': 'potion_plants',
    'Potion de Tranquillité': 'potion_tranquil', 'Potion de Contrôle des Insectes': 'potion_insects',
    'Potion Antipoison': 'potion_antidote', 'Eau Bénite': 'holy_water_vial',
    'Anneau de Lumière': 'ring_light', 'Bottes à Bondir': 'boots_leap', 'Bottes de Saut': 'boots_leap',
    'Corde Magique': 'rope_magic', 'Filet de Capture': 'net_capture', 'Filet d’Enchevêtrement': 'net_capture',
    'Brassard de Force': 'bracer_strength', 'Gant d’Adresse au Lancer': 'glove_throw',
    'Perche à Sonder': 'pole_probe', 'Gousses d’Ail': 'garlic', 'Bandeau de Concentration': 'headband',
    'Capsules de Feu': 'fire_capsules', 'Filtres à Nez': 'nose_filters',
    # La Forêt — équipement porté, trouvailles et butins.
    'Casque magique': 'helmet_magic', 'Bracelet d’Habileté': 'bracelet_skill',
    'Gantelet d’Adresse à Combattre': 'gauntlet', 'Anneau de Lenteur': 'ring_slow',
    'Bouclier d’empereur': 'shield_emperor', 'Œil d’Ambre': 'amber_eye',
    'Tête de marteau en bronze — G': 'hammer_head', 'Manche de marteau en ébène — G': 'hammer_handle',
    'Épée enchantée': 'sword_enchanted', 'Pain elfique': 'elven_bread',
    'Petite clochette de cuivre': 'bell_copper', 'Fléchette d’argent (valeur 5 Or)': 'dart_silver',
    'Petite flûte de cuivre': 'flute_copper', 'Flûte à Endormir les Dragons': 'flute_dragon',
    'Biscuits infestés de vers': 'biscuits_worms', 'Collier de crânes de souris': 'collar_skulls',
    'Médaillon d’or (valeur 9 Or)': 'medallion_ruby', 'Médaillon d’or (valeur 5 Or)': 'medallion_star',
    'Petit sifflet de bois': 'whistle_wood', 'Boucle d’oreille en or (valeur 5 Or)': 'earring_gold',
    'Petite clé d’argent': 'key_silver_small',
    'Collier de cuir incrusté d’or (valeur 15 Or)': 'collar_leather', 'Couteau à lancer': 'knife',
    'Morceau de pierre de la Bête Rocheuse': 'rock_shard', 'Couronne du Démon de Feu': 'crown_fire',
    'Bague d’or à émeraude (valeur 15 Or)': 'ring_emerald', 'Anneau d’or (valeur 10 Or)': 'ring_gold',
    'Boîte d’argent': 'silver_box', 'Lanterne magique': 'lantern_magic',
    'Poudre de Lévitation': 'powder_levitation', 'Belladone': 'belladonna', 'Dent de dragon': 'dragon_tooth',
    'Potion de Force': 'potion_force', 'Main d’argile rouge': 'clay_hand',
    'Lingot d’or (valeur 28 Or)': 'gold_ingot',
    # Le Sorcier de la Montagne de Feu.
    'Épée magique': 'sword_magic', 'Épée trouvée dans la rivière': 'sword_river',
    'Arc': 'bow', 'Flèche d’argent': 'arrow_silver', 'Épieu': 'spear', 'Cinq piquets de bois': 'stakes',
    'Ciseau à lame d’argent': 'chisel_silver', 'Maillet en bois dur': 'mallet',
    'Armure trouvée': 'armor_chain', 'Casque ensorcelé': 'helmet_cursed',
    'Bouclier de bois': 'shield_wood', 'Bouclier au croissant': 'shield_crescent',
    'Gant de soie noire': 'glove_black', 'Bouteille d’eau sainte': 'holy_water_bottle',
    'Potion d’Invisibilité': 'potion_invisibility', 'Boucles d’oreilles': 'earrings_blue',
    'Crucifix en argent': 'crucifix', 'Crucifix en argent (valeur 4 PO)': 'crucifix',
    'Pierre précieuse de la statue': 'gem_statue',
    'Clé 111': 'key_111', 'Clé 125': 'key_125', 'Clé de bronze 9': 'key_bronze_9',
    'Clé de bronze 99': 'key_bronze_99', 'Clé rouge 111': 'key_red_111', 'Clé de cuivre 66': 'key_copper_66',
    'Clé du Hangar à Bateaux': 'key_boathouse',
    'Chandelle bleue': 'candle_blue', 'Fromage': 'cheese', 'Mallette': 'leather_case',
    'Morceau de bois en Y': 'y_stick', 'Deux morceaux de bois en Y': 'y_sticks',
    'Vieux parchemin': 'scroll_old', 'Livre du Vampire': 'vampire_book',
    # La Cité des Voleurs — boutiques, butins, trouvailles et objets de la mission.
    'Anneau de Feu': 'ring_fire', 'Anneau de Glace': 'ring_ice', 'Anneau d’Invisibilité': 'ring_invisible',
    'Anneau de l’Œil d’Or': 'ring_eye', 'Bague ornée de pierreries': 'ring_jewels',
    'Broche scorpion d’or': 'brooch_scorpion_gold', 'Broche scorpion d’argent': 'brooch_scorpion_silver',
    'Broche scorpion de cuivre': 'brooch_scorpion_copper', 'Bracelet-insecte d’argent': 'bracelet_insect',
    'Six perles noires': 'pearls_black', 'Perles noires': 'pearls_black',
    'Deux pierres précieuses': 'gems_two', 'Chouette en or': 'owl_gold',
    'Crâne d’ivoire à chaîne d’argent': 'skull_ivory',
    'Passe-partout': 'key_skeleton', 'Clef en fer': 'key_iron', 'Clef spéciale du Nain': 'key_dwarf',
    'Trousseau de clefs': 'keyring',
    'Bouclier': 'shield_wood', 'Bouclier à la tour': 'shield_tower', 'Bouclier magnifique': 'shield_magnificent',
    'Bouclier du chevalier': 'shield_knight', 'Cotte de mailles': 'armor_chain',
    'Épée de combat ordinaire': 'sword', 'Arc en bois d’if': 'bow', 'Poignard de Jet': 'knife',
    'Lance en Fer': 'spear', 'Bottes magiques': 'boots_magic', 'Bandeau pour l’œil': 'eyepatch',
    'Emplâtre d’herbes': 'poultice', 'Potion de Contrôle de l’esprit': 'potion_mind',
    'Gousse d’ail': 'garlic',
    'Fleur dorée à dix pétales': 'flower_golden', 'Fleurs d’or': 'flower_golden',
    'Fleur de lotus': 'lotus', 'Bouquet de fleurs': 'bouquet',
    'Mèche de cheveux de Sorcière': 'witch_hair', 'Cheveux de Sorcière': 'witch_hair',
    'Laissez-passer de marchand': 'pass_merchant', 'Miroir': 'mirror', 'Boule de verre': 'glass_ball',
    'Flûte en argent': 'flute_silver', 'Morceau de craie': 'chalk',
    'Gobelet en argent': 'goblet_silver', 'Calice en argent': 'chalice_silver',
    'Cuillère en argent': 'spoon_silver', 'Vieux osselets': 'knucklebones',
    'Morceau de pain rassis': 'bread_stale', 'Bougie de couleur': 'candle_coloured',
    'Croc de Boucher': 'butcher_hook', 'Corde d’Escalade': 'rope_plain',
}


def _normalise(name):
    return ' '.join(str(name).replace("'", '’').split()).casefold()


_LOOKUP = {_normalise(name): icon for name, icon in ITEM_ICONS.items()}


def is_exhausted(name):
    return str(name).endswith(EXHAUSTED_SUFFIX)


def item_icon_id(name):
    """Identifiant du dessin dédié, ou None si l'objet n'est pas répertorié."""
    text = str(name)
    if is_exhausted(text):
        text = text[:-len(EXHAUSTED_SUFFIX)]
    return _LOOKUP.get(_normalise(text))


def generic_key_number(name):
    """Numéro d'une clé non répertoriée (« Clé 12 ») pour l'étiqueter malgré tout."""
    match = re.match(r'(?i)^cl[ée]\b.*?\b(\d{1,4})\b', str(name).strip())
    return match[1] if match else None


def draw_item_icon(p, icon_id, center, half_size, *, exhausted=False):
    """Peindre le dessin icon_id centré sur center, demi-taille half_size (px)."""
    drawing = DRAWINGS[icon_id]
    if exhausted:
        _draw_exhausted(p, icon_id, QPointF(center), half_size)
        return
    p.save()
    if isinstance(drawing, _Legacy):
        from adventurer_sheet import draw_item_art
        draw_item_art(p, str(drawing), QPointF(center), half_size)
    else:
        p.translate(center)
        p.scale(half_size, half_size)
        drawing(p)
    p.restore()


def _draw_exhausted(p, icon_id, center, half_size):
    """Magie épuisée : même dessin, terni d'un voile gris et à demi effacé."""
    t = p.transform()
    zoom = max(1.0, math.hypot(t.m11(), t.m12())) * p.device().devicePixelRatioF()
    box = QRectF(center.x() - half_size * 1.25, center.y() - half_size * 1.25, half_size * 2.5, half_size * 2.5)
    size = max(1, math.ceil(box.width() * zoom))
    layer = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    layer.fill(0)
    q = QPainter(layer)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(zoom, zoom)
    draw_item_icon(q, icon_id, QPointF(half_size * 1.25, half_size * 1.25), half_size)
    q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    q.fillRect(QRectF(0, 0, box.width(), box.height()), _c('#6f655c', 150))
    q.end()
    p.save()
    p.setOpacity(p.opacity() * .55)
    p.drawImage(box, layer)
    p.restore()


def draw_generic_key_number(p, number, center, half_size):
    """Étiquette numérotée posée sur la clé générique d'une clé non répertoriée."""
    p.save()
    p.translate(center)
    p.scale(half_size, half_size)
    _numbered_tag(p, number)
    p.restore()


def item_qicon(name, size=28):
    """Icône Qt d'un objet (boutiques, ventes) : le même dessin que la sacoche, net à 100–200 %."""
    from PySide6.QtGui import QIcon, QPixmap

    from adventurer_sheet import paint_item
    icon = QIcon()
    for ratio in (1, 1.25, 1.5, 2):
        side = max(1, round(size * ratio))
        pixmap = QPixmap(side, side)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        paint_item(p, name, QPointF(side / 2, side / 2), side * .42)
        p.end()
        pixmap.setDevicePixelRatio(ratio)
        icon.addPixmap(pixmap)
    return icon
