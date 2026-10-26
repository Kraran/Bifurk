"""Cité des Voleurs : marques montrées sur la fiche.

Le tatouage reprend l'illustration de Franck (assets/marks/cite-tattoo.png) ; le
dessin au QPainter ne sert plus que de secours si le fichier manque."""
import math
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF, QRadialGradient

from ..marks import SheetMark
from . import rules

TATTOO_IMAGE = Path(__file__).resolve().parents[2] / 'assets' / 'marks' / 'cite-tattoo.png'

SUN = QColor('#f2c037')
SUN_DARK = QColor('#b9831c')
UNICORN = QColor('#fbf6ea')
OUTLINE = QColor('#3d1218')

TATTOO_TIP = ('<b>Tatouage au front</b><br>'
              '<i>Un soleil jaune, une licorne blanche en son milieu, piqués à l’aiguille '
              'et aux encres indélébiles.</i><br>'
              'Une marque sur le corps : elle ne quitte plus l’aventurier.')


def paint_tattoo(p, rect):
    """Secours sans illustration : soleil jaune à douze rayons, tête de licorne blanche."""
    p.save()
    c, s = rect.center(), min(rect.width(), rect.height()) / 2
    rays = QPolygonF()
    for index in range(24):
        angle = math.pi * index / 12 - math.pi / 2
        radius = s * (.98 if index % 2 == 0 else .62)
        rays.append(QPointF(c.x() + radius * math.cos(angle), c.y() + radius * math.sin(angle)))
    p.setPen(QPen(SUN_DARK, max(.8, s * .05)))
    p.setBrush(SUN)
    p.drawPolygon(rays)
    disc = QRadialGradient(c - QPointF(s * .15, s * .2), s * .7)
    disc.setColorAt(0, QColor('#ffe08a'))
    disc.setColorAt(1, SUN)
    p.setBrush(QBrush(disc))
    p.drawEllipse(c, s * .56, s * .56)
    # Tête de licorne tournée vers la gauche : encolure, chanfrein, oreille, corne.
    u = s * .5
    head = QPainterPath(QPointF(c.x() + .55 * u, c.y() + .85 * u))
    head.lineTo(c.x() + .35 * u, c.y() + .05 * u)
    head.lineTo(c.x() - .55 * u, c.y() + .35 * u)
    head.quadTo(c.x() - .78 * u, c.y() + .18 * u, c.x() - .55 * u, c.y() - .05 * u)
    head.lineTo(c.x() - .05 * u, c.y() - .45 * u)
    head.lineTo(c.x() + .12 * u, c.y() - .78 * u)
    head.lineTo(c.x() + .25 * u, c.y() - .45 * u)
    head.quadTo(c.x() + .75 * u, c.y() - .2 * u, c.x() + .8 * u, c.y() + .85 * u)
    head.closeSubpath()
    p.setPen(QPen(OUTLINE, max(.6, s * .04)))
    p.setBrush(UNICORN)
    p.drawPath(head)
    p.setPen(QPen(UNICORN, max(1.0, s * .08), Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(c.x() - .1 * u, c.y() - .42 * u), QPointF(c.x() - .55 * u, c.y() - 1.0 * u))
    p.restore()


MARKS = {rules.TATTOO: SheetMark('cite-tattoo', rules.TATTOO, TATTOO_TIP, paint_tattoo,
                                    TATTOO_IMAGE)}


def sheet_marks(character):
    """Marques acquises, dans l'ordre d'acquisition ; une ancienne sauvegarde où le
    tatouage est encore dans le sac l'affiche aussi, sans rien modifier."""
    names = rules.marks(character)
    names += [name for name in rules.MARKS
              if name in character.get('inventory', ()) and name not in names]
    return [MARKS[name] for name in names if name in MARKS]

