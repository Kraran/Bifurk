"""Lancers de D6 et D20 en perspective, sans OpenGL ni moteur web.

Le contrôleur fournit des faces déjà tirées : ce module ne consomme aucun hasard
et ne décide jamais d'une règle. Les solides et leurs marques sont des coordonnées
3D projetées par QPainter ; la trajectoire interpolée se termine sur la face reçue.
Ce rendu logiciel fonctionne aussi dans la distribution PyInstaller et sans GPU.
"""
import math
from itertools import combinations

from PySide6.QtCore import QElapsedTimer, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from themes import default_theme


# (valeur, normale, axe horizontal, axe vertical) dans le repère du cube.
# Les faces opposées totalisent toujours sept, comme sur un dé physique.
FACES = (
    (1, (0, 0, 1), (1, 0, 0), (0, 1, 0)),
    (6, (0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    (3, (1, 0, 0), (0, 0, -1), (0, 1, 0)),
    (4, (-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    (2, (0, -1, 0), (1, 0, 0), (0, 0, 1)),
    (5, (0, 1, 0), (1, 0, 0), (0, 0, -1)),
)
PIPS = {
    1: ((0, 0),),
    2: ((-.44, -.44), (.44, .44)),
    3: ((-.44, -.44), (0, 0), (.44, .44)),
    4: ((-.44, -.44), (.44, -.44), (-.44, .44), (.44, .44)),
    5: ((-.44, -.44), (.44, -.44), (0, 0), (-.44, .44), (.44, .44)),
    6: ((-.44, -.44), (.44, -.44), (-.44, 0), (.44, 0), (-.44, .44), (.44, .44)),
}
# Rotation qui amène chaque normale vers la caméra avant l'inclinaison décorative.
LANDING = {1: (0, 0), 2: (-math.pi / 2, 0), 3: (0, -math.pi / 2),
           4: (0, math.pi / 2), 5: (math.pi / 2, 0), 6: (0, math.pi)}


def icosahedron_faces():
    """Construire les vingt triangles d'un véritable dé icosaédrique régulier.

    Les trois arêtes d'une face relient les sommets les plus proches. Chaque
    triangle conserve son centre et deux axes tangents pour projeter son numéro
    sur le même plan que sa surface. Les faces opposées totalisent vingt et un.
    Cette géométrie fixe est calculée une seule fois, sans tirage aléatoire.
    """
    phi = (1 + math.sqrt(5)) / 2
    scale = 1.55 / math.sqrt(1 + phi * phi)
    vertices = [tuple(c * scale for c in point)
                for a in (-1, 1) for b in (-phi, phi)
                for point in ((0, a, b), (a, b, 0), (b, 0, a))]
    triangles = [points for points in combinations(vertices, 3)
                 if all(math.isclose(math.dist(a, b), 2 * scale)
                        for a, b in combinations(points, 2))]
    faces = []
    while triangles:
        points = triangles.pop(0)
        opposite = tuple(tuple(-c for c in point) for point in points)
        other = next(t for t in triangles if set(t) == set(opposite))
        triangles.remove(other)
        value = len(faces) // 2 + 1
        for number, corners in ((value, points), (21 - value, other)):
            center = tuple(sum(p[k] for p in corners) / 3 for k in range(3))
            length = math.sqrt(sum(c * c for c in center))
            normal = tuple(c / length for c in center)
            edge = tuple(corners[1][k] - corners[0][k] for k in range(3))
            u = tuple(c / math.dist(corners[0], corners[1]) for c in edge)
            v = (normal[1]*u[2] - normal[2]*u[1],
                 normal[2]*u[0] - normal[0]*u[2],
                 normal[0]*u[1] - normal[1]*u[0])
            faces.append((number, center, u, v, corners))
    return tuple(faces)


D20_FACES = icosahedron_faces()


def rotate(point, angles):
    """Appliquer les rotations X, Y puis Z, sans dépendance à une bibliothèque 3D."""
    x, y, z = point
    ax, ay, az = angles
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    return x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az), z


def die_angles(value, progress, index=0, sides=6):
    """Décélérer la rotation jusqu'à la face demandée ; aucun résultat intermédiaire n'est un jet."""
    remaining = (1 - max(0, min(1, progress))) ** 3
    az = 0
    if sides == 20:
        _, normal, u, _, _ = next(face for face in D20_FACES if face[0] == value)
        ax = math.atan2(normal[1], normal[2])
        ay = math.atan2(-normal[0], math.hypot(normal[1], normal[2]))
        ux, uy, _ = rotate(u, (ax, ay, 0))
        az = -math.atan2(uy, ux)
    else:
        ax, ay = LANDING[value]
    direction = 1 if index % 2 == 0 else -1
    return (ax + direction * 5 * math.pi * remaining,
            ay + 4 * math.pi * remaining, az + direction * 3 * math.pi * remaining)


def transformed(point, value, progress, index=0, sides=6):
    """Orienter le cube puis incliner le plateau pour voir aussi les faces latérales."""
    tilt = (-.15, .18, -.10) if sides == 20 else (-.32, .38, -.10)
    return rotate(rotate(point, die_angles(value, progress, index, sides)), tilt)


class DiceCanvas(QWidget):
    """Plateau dessiné et chronométrage de l'animation, indépendant du moteur de jeu."""

    finished = Signal()
    DURATION_MS = 1250

    def __init__(self, rolls, theme=None, parent=None, *, color=None, pip_color=None, caption=True, sides=6):
        """Recevoir une copie immuable des faces pour 1–3 D6 ou un D20."""
        super().__init__(parent)
        if (type(sides) is not int or sides not in (6, 20)
                or len(rolls) not in ((1, 2, 3) if sides == 6 else (1,))
                or any(type(n) is not int or not 1 <= n <= sides for n in rolls)):
            raise ValueError('Un lancer animé utilise un à trois D6 ou un D20.')
        self.rolls = tuple(rolls)
        self.sides = sides
        self.theme = theme or default_theme()
        # Le combat réutilise exactement la même géométrie : seuls les dés
        # adverses changent de matière, sans toucher aux valeurs reçues.
        self.color = color or self.theme.color('page')
        self.pip_color = pip_color or self.theme.color('ink')
        self.caption = caption
        self.progress = 0.0
        self._finished = False
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.setMinimumSize(320, 230)
        self.setAccessibleName('Plateau de lancer de dés en trois dimensions')

    def start(self):
        """Démarrer après affichage ; utiliser le temps réel, sans dépendre du débit d'images."""
        if not self._finished and not self.timer.isActive():
            self.clock.start()
            self.timer.start()

    def _tick(self):
        """Avancer selon le temps écoulé ; une machine lente garde la même durée de lancer."""
        self.progress = min(1.0, self.clock.elapsed() / self.DURATION_MS)
        if self.progress >= 1:
            self.finish()
        else:
            self.update()

    def finish(self):
        """Figer les faces finales et notifier une seule fois, y compris après un saut d'animation."""
        if self._finished:
            return
        self.timer.stop()
        self.progress = 1.0
        self._finished = True
        self.setAccessibleDescription('Résultat : ' + ' + '.join(map(str, self.rolls)))
        self.update()
        self.finished.emit()

    def _draw_die(self, painter, value, index, center, size):
        """Trier les faces visibles par profondeur et projeter leurs points sur leur propre plan."""
        progress = self.progress

        def transform(point):
            return transformed(point, value, progress, index)

        def project(point):
            x, y, z = transform(point)
            # La caméra est à six demi-arêtes : pas de division proche de zéro.
            perspective = 6 / (6 - z)
            return QPointF(center.x() + x * size * perspective, center.y() + y * size * perspective)

        def on_face(normal, u, v, x, y):
            return tuple(normal[k] + u[k] * x + v[k] * y for k in range(3))

        faces = []
        for number, normal, u, v in FACES:
            nx, ny, nz = transform(normal)
            if nx * -nx + ny * -ny + nz * (6 - nz) > 0:
                faces.append((nz, number, normal, u, v))
        for depth, number, normal, u, v in sorted(faces):
            corners = [project(on_face(normal, u, v, x, y))
                       for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            brightness = .70 + max(0, depth) * .25
            base = QColor(self.color)
            base.setRedF(min(1, base.redF() * brightness))
            base.setGreenF(min(1, base.greenF() * brightness))
            base.setBlueF(min(1, base.blueF() * brightness))
            painter.setPen(QPen(QColor(self.theme.color('ornament')).darker(140), 1.4))
            painter.setBrush(base.darker(118))
            painter.drawPolygon(QPolygonF(corners))
            # Incrustation arrondie sur le plan 3D : le liseré extérieur évoque un
            # chanfrein. Les points utilisent la même projection que cette face.
            inset = []
            for cx, cy, start in ((.76, .76, 0), (-.76, .76, 90),
                                  (-.76, -.76, 180), (.76, -.76, 270)):
                for step in range(7):
                    angle = math.radians(start + step * 15)
                    inset.append(project(on_face(normal, u, v,
                        cx + .18 * math.cos(angle), cy + .18 * math.sin(angle))))
            painter.setPen(Qt.NoPen)
            painter.setBrush(base)
            painter.drawPolygon(QPolygonF(inset))
            for px, py in PIPS[number]:
                pip = [project(on_face(normal, u, v,
                        px + .125 * math.cos(a * math.tau / 16),
                        py + .125 * math.sin(a * math.tau / 16))) for a in range(16)]
                painter.setBrush(QColor(self.pip_color))
                painter.drawPolygon(QPolygonF(pip))

    def _draw_d20(self, painter, value, index, center, size):
        """Dessiner les facettes et leurs chiffres dans le même repère 3D.

        Le texte est un contour vectoriel : ses points subissent la projection
        perspective de la face, au lieu de flotter à plat devant le dé.
        """
        def project(point):
            x, y, z = transformed(point, value, self.progress, index, 20)
            perspective = 6 / (6 - z)
            return QPointF(center.x() + x * size * perspective,
                           center.y() + y * size * perspective)

        visible = []
        for number, origin, u, v, corners in D20_FACES:
            x, y, z = transformed(origin, value, self.progress, index, 20)
            if -x*x - y*y + z*(6-z) > 0:
                visible.append((z, number, origin, u, v, corners))
        font = QFont(self.font().family())
        font.setPixelSize(100)
        font.setBold(True)
        for depth, number, origin, u, v, corners in sorted(visible):
            painter.setPen(QPen(QColor(self.theme.color('ornament')).darker(140), 1.4))
            painter.setBrush(QColor(self.color).darker(max(100, int(150 - depth * 30))))
            painter.drawPolygon(QPolygonF([project(p) for p in corners]))
            path = QPainterPath()
            path.addText(0, 0, font, str(number))
            bounds = path.boundingRect()
            factor = min(.64 / bounds.width(), .43 / bounds.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.pip_color))
            # Le remplissage pair-impair conserve les trous des chiffres 6, 8, 9…
            projected = QPainterPath()
            for contour in path.toSubpathPolygons():
                points = []
                for point in contour:
                    px = (point.x() - bounds.center().x()) * factor
                    py = (point.y() - bounds.center().y()) * factor
                    points.append(project(tuple(origin[k] + u[k]*px + v[k]*py for k in range(3))))
                projected.addPolygon(QPolygonF(points))
            painter.drawPath(projected)

    def paintEvent(self, event):
        """Dessiner velours, filets dorés, ombres et dés rebondissant sur le plateau."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        gradient = QRadialGradient(QPointF(rect.center()), self.width() * .68)
        gradient.setColorAt(0, QColor(self.theme.color('accent')).lighter(125))
        gradient.setColorAt(1, QColor(self.theme.color('scene_background')))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(self.theme.color('gold')), 2))
        painter.drawRoundedRect(rect, 18, 18)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(self.theme.color('ornament')), .8))
        painter.drawRoundedRect(rect.adjusted(8, 8, -8, -8), 13, 13)
        count = len(self.rolls)
        size = min(self.width() / (count * 4.9), self.height() / 5.0)
        p = self.progress
        for index, value in enumerate(self.rolls):
            home_x = self.width() / 2 + (index - (count - 1) / 2) * size * 3.5
            drift = (1 - p) ** 2 * size * (1 if index == 0 else -1) * -1.2
            bounce = abs(math.sin(p * math.pi * 3.5)) * (1 - p) ** 1.5 * size * 1.25
            x = home_x + drift
            y = self.height() * .52 - bounce
            painter.setPen(Qt.NoPen)
            for radius in range(5, 0, -1):
                painter.setBrush(QColor(0, 0, 0, 12))
                painter.drawEllipse(QPointF(x, self.height() * .52 + size * 1.05),
                                    size * (1.1 + radius * .09), size * (.17 + radius * .04))
            draw = self._draw_d20 if self.sides == 20 else self._draw_die
            draw(painter, value, index, QPointF(x, y), size)
        painter.setPen(QColor(self.theme.color('gold')))
        painter.setFont(QFont(self.font().family(), 10))
        if self.caption:
            painter.drawText(rect.adjusted(16, 0, -16, -14), Qt.AlignBottom | Qt.AlignHCenter,
                             '✦  LE DESTIN EST ENTRE VOS MAINS  ✦')


class DiceDialog(QDialog):
    """Lancer modal : le résultat doit être visible avant que l'action de jeu continue.

Fermer ou Échap pendant le mouvement révèle les faces ; une seconde fermeture
continue avec ce résultat. Il n'existe ni annulation du tirage ni bouton relancer.
"""

    def __init__(self, rolls, context, theme=None, parent=None, *, sides=6):
        """Construire le plateau et les textes avec la palette du thème courant."""
        super().__init__(parent)
        self.setObjectName('diceDialog')
        self.setStyleSheet('QLabel#diceContext { font-size: 19px; font-weight: bold; }'
                          'QLabel#diceResult { font-size: 23px; font-weight: bold; }'
                          'QPushButton#diceContinue { min-width: 150px; padding: 10px 18px; }')
        self.setWindowTitle('Bifurk — Le lancer du destin')
        self.setWindowModality(Qt.ApplicationModal)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.resize(560, 430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        self.context = QLabel(context)
        self.context.setObjectName('diceContext')
        self.context.setTextFormat(Qt.PlainText)
        self.context.setWordWrap(True)
        self.context.setAlignment(Qt.AlignCenter)
        font = QFont(self.font())
        font.setPointSize(16)
        font.setBold(True)
        self.context.setFont(font)
        layout.addWidget(self.context)
        self.canvas = DiceCanvas(rolls, theme, self, sides=sides)
        layout.addWidget(self.canvas, 1)
        self.result = QLabel('Les dés roulent…')
        self.result.setObjectName('diceResult')
        self.result.setAlignment(Qt.AlignCenter)
        self.result.setFont(font)
        self.result.setAccessibleName('Résultat du lancer')
        layout.addWidget(self.result)
        self.proceed = QPushButton('Passer l’animation')
        self.proceed.setObjectName('diceContinue')
        self.proceed.setDefault(True)
        self.proceed.clicked.connect(self.accept)
        layout.addWidget(self.proceed, 0, Qt.AlignHCenter)
        self.canvas.finished.connect(self._reveal)

    def showEvent(self, event):
        """Démarrer la minuterie quand le plateau est effectivement affiché."""
        super().showEvent(event)
        self.canvas.start()

    def _reveal(self):
        """Afficher chaque face et le total, puis laisser le joueur continuer à son rythme."""
        faces = ' + '.join(map(str, self.canvas.rolls))
        total = sum(self.canvas.rolls)
        self.result.setText(f'Résultat : {faces}' + (f' = {total}' if len(self.canvas.rolls) > 1 else ''))
        self.result.setAccessibleName(self.result.text())
        self.proceed.setText('Continuer')
        self.proceed.setFocus()

    def accept(self):
        """Le premier clic saute les mouvements ; une fois les faces révélées, continuer."""
        if not self.canvas._finished:
            self.canvas.finish()
        else:
            super().accept()

    def reject(self):
        """Échap et la croix ne peuvent ni annuler ni remplacer un résultat déjà tiré."""
        self.accept()

    def done(self, result):
        """Arrêter les rappels Qt avant fermeture du dialogue."""
        self.canvas.timer.stop()
        super().done(result)
