"""Carte interactive de l'exploration, construite uniquement avec les souvenirs du joueur.

Le graphe suit les directions explicites des choix quand elles sont connues,
sans prétendre reconstruire les distances physiques du livre. La vue ne résout aucune règle : sélection, recherche, zoom
et recentrage ne modifient jamais la partie. Seule la commande explicite de
retour à un passage appelle la navigation existante du contrôleur.
"""
import copy
import html
import math
import re

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGraphicsObject,
                               QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QTextBrowser, QVBoxLayout, QWidget)

from book_events import verified_entry


def discovered_places(owner):
    """Copier les données découvertes sans lire les titres des sorties inconnues.

    Les renvois éditoriaux du catalogue sont prioritaires sur les liens extraits
    du PDF. Les monstres viennent exclusivement de l'historique de rencontre,
    jamais de la liste des adversaires qui pourraient attendre dans un lieu.
    """
    places = {}
    for number in owner.visited_paragraphs:
        entry = verified_entry(owner.book_event_catalogue, number) or {}
        routes = (entry['routes'] if 'routes' in entry else
                  owner._paragraph_choices(owner.paragraphs.get(number, '')))
        exits = [route['target'] for route in routes]
        places[number] = {'title': owner._paragraph_name(number) or 'Passage exploré',
                          'exits': list(dict.fromkeys(exits)),
                          'directions': {route['target']: route_direction(route.get('label', ''))
                                         for route in routes},
                          'monsters': copy.deepcopy(owner.encounter_history.get(str(number), []))}
    return places


def route_direction(label):
    """Lire uniquement une direction de déplacement dans le libellé du choix.

    Ne pas déduire une orientation d'un titre ou du récit environnant. Deux
    directions, une négation ou une orientation composée restent ambiguës.
    """
    label = label.casefold().replace('’', "'")
    names = re.findall(r"\b(nord|sud|est|ouest)\b", label)
    if len(set(names)) != 1 or re.search(r"\b(ne|pas|sans|apercevoir|regarder|observer)\b", label):
        return None
    if not re.search(r"(?:^\s*(?:vers|au|à|direction)\b|\b(?:suivre|aller|continuer|poursuivre|partir|repartir|prendre|marcher|avancer|tourner)\b)", label):
        return None
    return {'nord': (0, -1), 'sud': (0, 1),
            'est': (1, 0), 'ouest': (-1, 0)}[names[0]]


def place_positions(numbers, transitions, directions=None):
    """Placer les lieux sur une grille, selon les déplacements connus.

    La première arrivée fixe la position d'un lieu ; les retours ne le déplacent
    pas. Une collision décale latéralement dans le même demi-plan cardinal.
    Sans direction, privilégier une case proche dans une surface compacte.
    """
    numbers = list(numbers)
    known = set(numbers)
    positions, occupied = {}, set()
    directions = directions or {}

    def assign(number, source=None, direction=None):
        origin = positions.get(source, (0, 0))
        if direction:
            dx, dy = direction
            radius = 1
            while True:
                candidates = [(origin[0] + dx * radius - dy * offset,
                               origin[1] + dy * radius + dx * offset)
                              for offset in range(-radius + 1, radius)]
                candidates.sort(key=lambda point: (abs((point[0]-origin[0])*dy -
                                                        (point[1]-origin[1])*dx), point))
                free = [point for point in candidates if point not in occupied]
                if free:
                    point = free[0]
                    break
                radius += 1
        else:
            radius = math.ceil(math.sqrt(len(occupied))) + 1
            candidates = [(x, y) for x in range(-radius, radius + 1)
                          for y in range(-radius, radius + 1) if (x, y) not in occupied]
            point = min(candidates, key=lambda p: ((p[0]-origin[0])**2 + (p[1]-origin[1])**2
                                                  + 2*(p[0]**2+p[1]**2), p))
        positions[number] = point
        occupied.add(point)

    for source, target in transitions:
        if source not in known or target not in known:
            continue
        if source not in positions:
            assign(source)
        if target not in positions:
            assign(target, source, directions.get((source, target)))
    for number in numbers:
        if number not in positions:
            assign(number)
    return {number: QPointF(x * 330, y * 180) for number, (x, y) in positions.items()}


def encounter_summary(monsters):
    """Résumer les issues sans transformer un ennemi rencontré en ennemi vaincu."""
    labels = [('vaincu', 'vaincu', 'vaincus'), ('fui', 'fui', 'fuis'),
              ('rencontré', 'rencontré', 'rencontrés')]
    parts = []
    for status, singular, plural in labels:
        count = sum(monster['status'] == status for monster in monsters)
        if count:
            parts.append(f'{count} {singular if count == 1 else plural}')
    return ' · '.join(parts) or 'Lieu visité'


class PlaceItem(QGraphicsObject):
    """Une vignette parchemin sélectionnable, avec position et bilan de combat."""
    activated = Signal(int)
    WIDTH, HEIGHT = 236, 114

    def __init__(self, number, place, current, theme):
        super().__init__()
        self.number, self.place, self.current, self.theme = number, place, current, theme
        self.setFlag(QGraphicsObject.ItemIsSelectable)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"§ {number} — {place['title']}\n{encounter_summary(place['monsters'])}")

    def boundingRect(self):
        """Inclure le filet extérieur dans la surface à repeindre."""
        return QRectF(-3, -3, self.WIDTH + 6, self.HEIGHT + 6)

    def paint(self, painter, option, widget=None):
        """Dessiner des états lisibles par leurs mots, sans dépendre de la couleur."""
        theme = self.theme
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(theme.color('page')))
        painter.setPen(QPen(QColor(theme.color('gold' if self.current or self.isSelected() else 'ornament')),
                            3 if self.current or self.isSelected() else 1.5))
        painter.drawRoundedRect(QRectF(0, 0, self.WIDTH, self.HEIGHT), 9, 9)
        painter.setPen(QPen(QColor(theme.color('ornament')), .7))
        painter.drawRoundedRect(QRectF(5, 5, self.WIDTH - 10, self.HEIGHT - 10), 5, 5)
        font = QFont(painter.font())
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        if self.current:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.color('accent')))
            painter.drawRoundedRect(QRectF(8, 7, self.WIDTH - 16, 23), 4, 4)
        painter.setPen(QColor(theme.color('gold' if self.current else 'rubric')))
        heading = f'§ {self.number}' + ('  ◆ VOUS ÊTES ICI' if self.current else '  · VISITÉ')
        painter.drawText(QRectF(13, 9, self.WIDTH - 26, 19), Qt.AlignLeft, heading)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.setPen(QColor(theme.color('ink')))
        painter.drawText(QRectF(13, 31, self.WIDTH - 26, 47), Qt.TextWordWrap, self.place['title'])
        font.setPixelSize(11)
        font.setBold(False)
        painter.setFont(font)
        summary = QFontMetrics(font).elidedText(encounter_summary(self.place['monsters']),
                                               Qt.ElideRight, self.WIDTH - 26)
        painter.drawText(QRectF(13, 87, self.WIDTH - 26, 17), Qt.AlignLeft, summary)

    def mouseReleaseEvent(self, event):
        """Sélectionner une vignette sans appeler la navigation du jeu."""
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and self.boundingRect().contains(event.pos()):
            self.activated.emit(self.number)


class ExplorationView(QGraphicsView):
    """Déplacement par glissement et zoom à la molette, sans dépendance OpenGL."""
    def __init__(self, scene, theme):
        super().__init__(scene)
        self.setObjectName('explorationCanvas')
        self.setAccessibleName('Carte des passages explorés')
        leather = QPixmap(str(theme.assets['leather']))
        self.setBackgroundBrush(QBrush(leather) if not leather.isNull()
                                else QBrush(QColor(theme.color('scene_background'))))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

    def zoom(self, factor):
        """Limiter le grossissement et conserver un déplacement fluide des grandes cartes."""
        current = self.transform().m11()
        target = max(.03, min(2.5, current * factor))
        self.scale(target / current, target / current)

    def wheelEvent(self, event):
        """Agrandir autour du pointeur plutôt que faire défiler verticalement le graphe."""
        if event.angleDelta().y():
            self.zoom(1.2 ** (event.angleDelta().y() / 120))
            event.accept()
        else:
            super().wheelEvent(event)


class ExplorationMapDialog(QDialog):
    """Graphe, index consultable au clavier et détails d'un lieu sélectionné."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.theme = owner.theme
        self.places = discovered_places(owner)
        self.transitions = [tuple(pair) for pair in owner.transitions]
        self.current = owner.current_paragraph
        self.selected = None
        self.nodes = {}
        self.setWindowTitle('Bifurk — Carte d’exploration')
        self.setWindowIcon(owner.windowIcon())
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        area = owner.screen().availableGeometry()
        self.resize(min(1180, area.width() - 40), min(760, area.height() - 60))
        self.setMinimumSize(780, 540)
        layout = QVBoxLayout(self)
        title = QLabel('✦ LES CHEMINS DE VOTRE AVENTURE ✦')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-family: '{owner.reading_font_family}'; font-size: 22px; "
                           f"font-weight: bold; color: {self.theme.color('gold')}; padding: 4px;")
        layout.addWidget(title)
        self.info = QLabel(f'{len(self.places)} lieux visités · {len(self.transitions)} déplacements enregistrés')
        self.info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info)
        toolbar = QHBoxLayout()
        self.position_button = QPushButton('◆ Ma position')
        self.position_button.setEnabled(self.current in self.places)
        self.position_button.clicked.connect(self.focus_current)
        toolbar.addWidget(self.position_button)
        self.previous_button = QPushButton('Lieu précédent')
        self.previous = next((source for source, target in reversed(self.transitions)
                              if target == self.current and source in self.places and source != self.current), None)
        self.previous_button.setEnabled(self.previous is not None)
        self.previous_button.clicked.connect(lambda: self.select_place(self.previous, focus=True))
        toolbar.addWidget(self.previous_button)
        toolbar.addStretch()
        self.overview_button = QPushButton('Tout voir')
        self.overview_button.clicked.connect(self.overview)
        toolbar.addWidget(self.overview_button)
        for label, factor in [('−', 1 / 1.2), ('+', 1.2)]:
            button = QPushButton(label)
            button.setFixedWidth(40)
            button.setStyleSheet('min-width: 24px; max-width: 24px; padding-left: 6px; padding-right: 6px;')
            button.setAccessibleName('Réduire la carte' if factor < 1 else 'Agrandir la carte')
            button.clicked.connect(lambda checked=False, value=factor: self.view.zoom(value))
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)
        self.scene = QGraphicsScene(self)
        self.view = ExplorationView(self.scene, self.theme)
        splitter.addWidget(self.view)
        panel = QWidget()
        side = QVBoxLayout(panel)
        side.setContentsMargins(8, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Chercher un lieu visité ou son numéro…')
        self.search.setAccessibleName('Rechercher parmi les lieux visités')
        self.search.textChanged.connect(self.filter_places)
        side.addWidget(self.search)
        self.index = QListWidget()
        self.index.setAccessibleName('Index des lieux explorés')
        for number, place in self.places.items():
            item = QListWidgetItem(f"§ {number} — {place['title']}")
            item.setData(Qt.UserRole, number)
            self.index.addItem(item)
        self.index.currentItemChanged.connect(self._index_selected)
        side.addWidget(self.index, 1)
        self.details = QTextBrowser()
        self.details.setAccessibleName('Détails du lieu sélectionné')
        self.details.setOpenLinks(False)
        self.details.anchorClicked.connect(self._select_link)
        side.addWidget(self.details, 1)
        # L'ancien retour par clic reste disponible, mais devient explicite :
        # consulter le graphe ou son index ne téléporte plus accidentellement.
        self.travel_button = QPushButton('Revenir à ce passage')
        self.travel_button.setEnabled(False)
        self.travel_button.clicked.connect(self.travel)
        side.addWidget(self.travel_button)
        splitter.addWidget(panel)
        splitter.setSizes([780, 340])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        hint = QLabel('Glisser pour déplacer · Molette pour zoomer · Flèches : déplacements parcourus\n'
                      '◆ Position actuelle · Visité : passage découvert · Vaincu / fui / rencontré : état des adversaires')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText('Fermer')
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self._build_graph()
        if self.current in self.places:
            self.select_place(self.current)
        elif self.places:
            self.select_place(next(iter(self.places)))
        else:
            self.details.setPlainText('Votre carte se dessinera dès votre entrée dans l’aventure.')
        QTimer.singleShot(0, self.focus_current)

    def _build_graph(self):
        """Relier seulement les lieux connus par les déplacements réellement effectués."""
        directions = {(source, target): direction
                      for source, place in self.places.items()
                      for target, direction in place['directions'].items() if direction}
        positions = place_positions(self.places, self.transitions, directions)
        edges = list(dict.fromkeys((source, target) for source, target in self.transitions
                                   if source in positions and target in positions and source != target))
        for index, (source, target) in enumerate(edges):
            delta = positions[target] - positions[source]
            if abs(delta.x()) / 330 >= abs(delta.y()) / 180:
                sign = 1 if delta.x() > 0 else -1
                start = positions[source] + QPointF(PlaceItem.WIDTH if sign > 0 else 0, PlaceItem.HEIGHT / 2)
                end = positions[target] + QPointF(0 if sign > 0 else PlaceItem.WIDTH, PlaceItem.HEIGHT / 2)
                offset = QPointF(sign * max(45, abs(end.x() - start.x()) / 2), 0)
            else:
                sign = 1 if delta.y() > 0 else -1
                start = positions[source] + QPointF(PlaceItem.WIDTH / 2, PlaceItem.HEIGHT if sign > 0 else 0)
                end = positions[target] + QPointF(PlaceItem.WIDTH / 2, 0 if sign > 0 else PlaceItem.HEIGHT)
                offset = QPointF(0, sign * max(30, abs(end.y() - start.y()) / 2))
            path = QPainterPath(start)
            control1, control2 = start + offset, end - offset
            path.cubicTo(control1, control2, end)
            color = QColor(self.theme.color('gold' if (source, target) == (self.transitions[-1] if self.transitions else None)
                                             else 'ornament'))
            edge = self.scene.addPath(path, QPen(color, 2))
            edge.setZValue(-1)
            angle = math.atan2(end.y() - control2.y(), end.x() - control2.x())
            arrow = QPolygonF([end, end - QPointF(math.cos(angle - .45) * 11, math.sin(angle - .45) * 11),
                              end - QPointF(math.cos(angle + .45) * 11, math.sin(angle + .45) * 11)])
            self.scene.addPolygon(arrow, QPen(color), color).setZValue(-1)
        for number, place in self.places.items():
            node = PlaceItem(number, place, number == self.current, self.theme)
            node.setPos(positions[number])
            node.activated.connect(self.select_place)
            self.scene.addItem(node)
            self.nodes[number] = node
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-180, -180, 180, 180))

    def _index_selected(self, current, previous):
        """Suivre la sélection clavier ou souris de l'index sans changer de paragraphe."""
        if current is not None:
            self.select_place(current.data(Qt.UserRole), focus=True)

    def select_place(self, number, *, focus=False):
        """Actualiser vignette et détail ; refuser toute référence à un lieu inconnu."""
        if number not in self.places:
            return
        self.selected = number
        self.scene.clearSelection()
        self.nodes[number].setSelected(True)
        self.index.blockSignals(True)
        for row in range(self.index.count()):
            item = self.index.item(row)
            if item.data(Qt.UserRole) == number:
                self.index.setCurrentItem(item)
                break
        self.index.blockSignals(False)
        place = self.places[number]
        marker = '<p><b>◆ Vous êtes ici</b></p>' if number == self.current else '<p>Lieu visité</p>'
        monsters = ''.join(f"<li>{html.escape(m['name'])} — <b>{html.escape(m['status'])}</b></li>"
                           for m in place['monsters'])
        exits = []
        for target in place['exits']:
            if target in self.places:
                exits.append(f'<li><a href="place:{target}">§ {target} — {html.escape(self.places[target]["title"])}</a> · visité</li>')
            else:
                exits.append(f'<li>§ {target} · non exploré</li>')
        self.details.setHtml(f'<h3>{html.escape(place["title"])}</h3><p>§ {number}</p>{marker}'
                             + ('<h4>Adversaires rencontrés</h4><ul>' + monsters + '</ul>' if monsters else '')
                             + '<h4>Sorties repérées</h4>' + ('<ul>' + ''.join(exits) + '</ul>' if exits else '<p>Aucune sortie repérée.</p>'))
        self.travel_button.setEnabled(number != self.current and self.owner.character['endurance'] > 0
                                      and self.owner._adventurer_draft is None)
        if focus:
            self.view.resetTransform()
            self.view.centerOn(self.nodes[number])

    def _select_link(self, url):
        """Un lien du détail consulte un autre lieu connu, sans suivre un lien externe."""
        if url.scheme() == 'place' and url.path().isdigit():
            self.select_place(int(url.path()), focus=True)

    def filter_places(self, text):
        """Filtrer seulement l'index ; garder la carte et le lieu courant visibles."""
        query = text.casefold().strip()
        for row in range(self.index.count()):
            item = self.index.item(row)
            item.setHidden(query not in item.text().casefold())

    def focus_current(self):
        """Recentrer à taille lisible sans déplacer le personnage ni effacer la recherche."""
        self.select_place(self.current, focus=True)

    def overview(self):
        """Ajuster toute l'exploration dans la vue ; Ma position retrouve ensuite une taille lisible."""
        if self.nodes:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30), Qt.KeepAspectRatio)
            if self.view.transform().m11() > 1:
                self.view.resetTransform()

    def travel(self):
        """Conserver la navigation explicite déjà offerte par l'ancienne carte."""
        if self.selected in self.places and self.travel_button.isEnabled():
            self.owner.go_to(self.selected)
            self.accept()
