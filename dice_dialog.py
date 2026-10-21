"""Lancers de D6 en perspective, sans OpenGL ni moteur web.

Le contrôleur fournit des faces déjà tirées : ce module ne consomme aucun hasard
et ne décide jamais d'une règle. Les cubes et leurs points sont des coordonnées
3D projetées par QPainter ; la trajectoire interpolée se termine sur la face reçue.
Ce rendu logiciel fonctionne aussi dans la distribution PyInstaller et sans GPU.
"""
import math

from PySide6.QtCore import QElapsedTimer, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QRadialGradient
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


def rotate(point, angles):
    """Appliquer les rotations X, Y puis Z, sans dépendance à une bibliothèque 3D."""
    x, y, z = point
    ax, ay, az = angles
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    return x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az), z


def die_angles(value, progress, index=0):
    """Décélérer la rotation jusqu'à la face demandée ; aucun résultat intermédiaire n'est un jet."""
    remaining = (1 - max(0, min(1, progress))) ** 3
    ax, ay = LANDING[value]
    direction = 1 if index % 2 == 0 else -1
    return (ax + direction * 5 * math.pi * remaining,
            ay + 4 * math.pi * remaining, direction * 3 * math.pi * remaining)


def transformed(point, value, progress, index=0):
    """Orienter le cube puis incliner le plateau pour voir aussi les faces latérales."""
    return rotate(rotate(point, die_angles(value, progress, index)), (-.32, .38, -.10))


class DiceCanvas(QWidget):
    """Plateau dessiné et chronométrage de l'animation, indépendant du moteur de jeu."""

    finished = Signal()
    DURATION_MS = 1250

    def __init__(self, rolls, theme=None, parent=None, *, color=None, pip_color=None, caption=True):
        """Recevoir une copie immuable des faces pour un ou deux D6."""
        super().__init__(parent)
        if len(rolls) not in (1, 2) or any(type(n) is not int or not 1 <= n <= 6 for n in rolls):
            raise ValueError('Un lancer animé utilise un ou deux dés à six faces.')
        self.rolls = tuple(rolls)
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

    def paintEvent(self, event):
        """Dessiner velours, filets dorés, ombres et cubes qui rebondissent sur le plateau."""
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
            self._draw_die(painter, value, index, QPointF(x, y), size)
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

    def __init__(self, rolls, context, theme=None, parent=None):
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
        self.canvas = DiceCanvas(rolls, theme, self)
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
