"""Surfaces graphiques du grimoire, indépendantes des règles de l'aventure.

Les widgets dessinent texture, ornements et illustrations avec QPainter et les
couleurs du thème. Leurs états (zoom, déplacement, taille) sont visuels seulement.
GrimoireScene émet activated pour demander l'agrandissement ; seul le contrôleur
sait quel PDF ouvrir. Conserver les comportements clavier et le focus des boutons
natifs malgré le dessin personnalisé."""
from themes import default_theme
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette, QPainter, QPainterPath, QLinearGradient, QPixmap, QIcon, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QSizePolicy, QStyleOptionButton, QStyle, QDialog, QMessageBox
from PySide6.QtGui import QRadialGradient
import html
import adventurer_sheet
from adventurer_sheet import GOLD, GOLD_LIGHT, GOLD_DARK, BORDEAUX, draw_diamond
from grimoire_chrome import (draw_gold_frame, draw_corner_fleurons, draw_wax_seal, draw_icon,
                             RUBRIC, PAGE_INK, BRONZE)


def message_icon(kind, theme, device_pixel_ratio=1):
    """Dessiner un petit blason à la place des pictogrammes système colorés.

    Le symbole conserve le sens du message (information, question, avertissement
    ou erreur). Le thème fournit toutes les couleurs et le dessin est calculé
    à la résolution de l'écran pour rester net sous Windows avec mise à l'échelle.
    """
    size = 36
    pixmap = QPixmap(round(size * device_pixel_ratio), round(size * device_pixel_ratio))
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    shield = QPainterPath()
    shield.moveTo(18, 2)
    shield.lineTo(32, 7)
    shield.lineTo(31, 21)
    shield.cubicTo(30, 27, 24, 31, 18, 34)
    shield.cubicTo(12, 31, 6, 27, 5, 21)
    shield.lineTo(4, 7)
    shield.closeSubpath()
    painter.setPen(QPen(QColor(theme.color('icon_border')), 1.5))
    painter.setBrush(QColor(theme.color('rubric') if kind == QMessageBox.Critical
                            else theme.color('icon_background')))
    painter.drawPath(shield)
    painter.setPen(QPen(QColor(theme.color('gold')), .7))
    painter.drawLine(QPointF(8, 9), QPointF(18, 5))
    painter.drawLine(QPointF(18, 5), QPointF(28, 9))
    symbols = {QMessageBox.Information: 'i', QMessageBox.Question: '?',
               QMessageBox.Warning: '!', QMessageBox.Critical: '×'}
    font = QFont('serif')
    font.setPixelSize(25)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(theme.color('icon_ink')))
    painter.drawText(QRectF(5, 4, 26, 26), Qt.AlignCenter, symbols[kind])
    painter.end()
    return pixmap


def theme_message_box(dialog):
    """Habiller les icônes standard sans modifier boutons, texte ni résultat.

    Les messages statiques de Qt et les fenêtres construites explicitement passent
    par le même filtre d'affichage. Une icône personnalisée ou absente est
    conservée ; le type d'origine est mémorisé pour un éventuel réaffichage.
    """
    kind = getattr(dialog, '_bifurk_message_kind', dialog.icon())
    if kind == QMessageBox.NoIcon:
        return
    dialog._bifurk_message_kind = kind
    owner = dialog.parentWidget()
    while owner is not None and not hasattr(owner, 'theme'):
        owner = owner.parentWidget()
    theme = owner.theme if owner is not None else default_theme()
    dialog.setIconPixmap(message_icon(kind, theme, dialog.devicePixelRatioF()))


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
    """Page de livre peinte : vélin texturé, pli de reliure, tranche, double filet et volutes."""

    def __init__(self, texture_path=None, parent=None, theme=None):
        """Initialiser thème et texture ; une texture absente laisse apparaître la couleur de page."""
        super().__init__(parent)
        self.theme = theme or default_theme()
        self.texture = QPixmap(str(self._page_texture(texture_path)))
        self.compact = False

    def set_compact(self, compact):
        """Petites hauteurs : filets rapprochés du bord et volutes réduites."""
        if bool(compact) != self.compact:
            self.compact = bool(compact)
            self.update()

    def _page_texture(self, fallback):
        page = getattr(self.theme, 'assets', {}).get('page')
        return page if page else (fallback or '')

    def set_theme(self, theme):
        """Mettre à jour les couleurs et textures de la surface puis demander un nouveau dessin."""
        self.theme = theme
        self.texture = QPixmap(str(self._page_texture(theme.assets['parchment'])))
        self.update()

    def paintEvent(self, event):
        """Dessiner tranche, vélin, ombre de reliure, vieillissement des bords puis ornements."""
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        full = QRectF(self.rect())
        page = full.adjusted(2, 2, -7, -7)
        # Ombre portée et tranche des feuillets (côté droit et bas).
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(page.translated(5, 6), 8, 8)
        for k, shade in ((4, '#c9ad7c'), (2, '#dcc39a')):
            p.setBrush(QColor(shade))
            p.setPen(QPen(QColor('#8f6e45'), .6))
            p.drawRoundedRect(page.translated(k, k), 8, 8)
        clip = QPainterPath()
        clip.addRoundedRect(page, 8, 8)
        p.setClipPath(clip)
        p.fillPath(clip, QColor(self.theme.color("page")))
        if not self.texture.isNull():
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawPixmap(page, self.texture, QRectF(self.texture.rect()))
        # Pli de reliure à gauche : la page est la belle page d'un livre ouvert.
        gutter = QLinearGradient(page.topLeft(), QPointF(page.left() + 46, page.top()))
        gutter.setColorAt(0, QColor(70, 40, 15, 120))
        gutter.setColorAt(.35, QColor(70, 40, 15, 40))
        gutter.setColorAt(1, QColor(70, 40, 15, 0))
        p.fillRect(page, gutter)
        aged = QRadialGradient(page.center(), max(page.width(), page.height()) * .72)
        aged.setColorAt(.62, QColor(120, 80, 30, 0))
        aged.setColorAt(1, QColor(120, 80, 30, 70))
        p.fillRect(page, aged)
        p.setClipping(False)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor('#7d5a2e'), 1))
        p.drawRoundedRect(page, 8, 8)
        inset = 7 if self.compact else 11
        frame = page.adjusted(inset, inset, -inset, -inset)
        p.setPen(QPen(BRONZE, 1.6))
        p.drawRoundedRect(frame, 5, 5)
        p.setPen(QPen(QColor(122, 38, 50, 150), .8))
        p.drawRoundedRect(frame.adjusted(4, 4, -4, -4), 3, 3)
        draw_corner_fleurons(p, frame.adjusted(-4, -4, 4, 4), color=BRONZE, light=RUBRIC,
                             size=20 if self.compact else 30)
        for y in (frame.top(), frame.bottom()):
            draw_diamond(p, QPointF(frame.center().x(), y), 4.5, BRONZE)
            draw_diamond(p, QPointF(frame.center().x(), y), 1.8, RUBRIC)


class ChoiceCard(QPushButton):
    compact = False  # suivi de la densité de la fenêtre principale (petites hauteurs)
    tight = False    # très petites hauteurs : plaque basse, « → §N » en fin de texte

    """Plaque de choix ornementée : sceau numéroté, destination en cartouche, survol lumineux.

    Le texte du bouton (text()) reste le libellé complet ; le label enfant, transparent aux
    clics, affiche l'action et le dessin ajoute numéro et destination « §N »."""

    def __init__(self, text, parent=None):
        """Confier le retour à la ligne au label et les clics au bouton parent.

        Le label transparent aux événements souris empêche les zones de texte de
        masquer l’activation native ; le layout détermine la hauteur du contenu."""
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self._number = None
        action, destination = text, ''
        if '→' in text:
            head, tail = text.rsplit('→', 1)
            if tail.strip().startswith('§'):
                action, destination = head.strip(), tail.strip().replace('§ ', '§')
        self._destination = destination
        layout = QVBoxLayout(self)
        self._right = 92 if destination else 22
        layout.setContentsMargins(70, 15, self._right, 16)
        caption = QLabel(action)
        caption.setWordWrap(True)
        caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        caption.setObjectName("choiceCaption")
        caption.setStyleSheet(
            "background: transparent; border: none; color: #2e1d14; "
            f"font-family: '{adventurer_sheet.FONTS['title']}'; font-size: 21px;")
        layout.addWidget(caption)
        self._caption, self._base_text, self._action = caption, text, action
        self._tight = None
        self.set_compact(ChoiceCard.compact, ChoiceCard.tight)

    def set_compact(self, compact, tight=False):
        """Plaque plus basse sur les petites fenêtres ; le sceau reste lisible.

        En mode serré, la destination quitte sa colonne et suit le texte (« … → §N »)
        pour que chaque plaque tienne sur une ligne de plus au même encombrement."""
        self._compact = compact
        tight = bool(tight)
        if tight:
            self.layout().setContentsMargins(52, 6, 16, 7)
        else:
            self.layout().setContentsMargins(70, 10 if compact else 15, self._right, 11 if compact else 16)
        if tight != self._tight:
            self._tight = tight
            style = self._caption.styleSheet()
            style = style.replace('font-size: 21px', 'font-size: 18px') if tight else \
                style.replace('font-size: 18px', 'font-size: 21px')
            self._caption.setStyleSheet(style)
            if tight and self._destination:
                self._caption.setTextFormat(Qt.RichText)
                self._caption.setText(
                    f"{html.escape(self._action)}&nbsp;&nbsp;<span style=\"color:#7a2632; font-style:italic; "
                    f"font-weight:600; white-space:nowrap;\">→&nbsp;{html.escape(self._destination)}</span>")
            else:
                self._caption.setTextFormat(Qt.PlainText)
                self._caption.setText(self._action)
            self.update()

    def set_shortcut_number(self, number):
        """Afficher le numéro dans le sceau ; la touche correspondante active le choix."""
        self._number = number
        # Un choix grisé garde sa raison (ressource manquante) dans l'infobulle.
        reason = self.toolTip().split(" · touche ")[0]
        self.setToolTip(f"{reason} · touche {number}" if reason.startswith("Indisponible")
                        else f"Touche {number}")
        self.setAccessibleName(f"Choix {number} : {self._base_text}")
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self._caption.setStyleSheet(self._caption.styleSheet().replace(
                '#2e1d14', '#8a7a64') if not self.isEnabled() else
                self._caption.styleSheet().replace('#8a7a64', '#2e1d14'))

    def paintEvent(self, event):
        """Plaque de parchemin, double filet doré, sceau numéroté et flèche-plume vers §N."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        hover = enabled and (self.underMouse() or self.hasFocus())
        r = QRectF(self.rect()).adjusted(3, 2, -3, -4)
        if self.isDown():
            r.translate(0, 1)
        if hover:
            for k, alpha in ((5, 40), (3, 70)):
                p.setPen(QPen(QColor(232, 190, 100, alpha), k * 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r, 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 35, 12, 70))
        p.drawRoundedRect(r.translated(0, 2.5), 8, 8)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        if not enabled:
            g.setColorAt(0, QColor('#ece2cc'))
            g.setColorAt(1, QColor('#d6c7a8'))
        elif hover:
            g.setColorAt(0, QColor('#fffaea'))
            g.setColorAt(1, QColor('#f3dca9'))
        else:
            g.setColorAt(0, QColor('#fbf1d8'))
            g.setColorAt(1, QColor('#e8cf9c'))
        p.setBrush(g)
        p.setPen(QPen(RUBRIC if hover else GOLD_DARK, 1.8))
        p.drawRoundedRect(r, 8, 8)
        inner = r.adjusted(4, 4, -4, -4)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(GOLD) if enabled else QColor('#c8b48e'), 1))
        p.drawRoundedRect(inner, 5, 5)
        for pt in (inner.topLeft(), inner.topRight(), inner.bottomLeft(), inner.bottomRight()):
            draw_diamond(p, pt, 2.6, GOLD_DARK if enabled else QColor('#b7a37f'))
        # Sceau numéroté.
        tight = bool(self._tight)
        c = QPointF(r.left() + (24 if tight else 31), r.center().y())
        seal = BORDEAUX if enabled else QColor('#8b7d70')
        radius = 13 if tight else (16 if self._compact else 18)
        draw_wax_seal(p, c, radius + (1 if hover else 0), color=seal, ring=GOLD_LIGHT if hover else GOLD)
        if self._number is not None:
            p.setFont(adventurer_sheet.font('title', 15 if tight else (18 if self._compact else 20), bold=True))
            p.setPen(GOLD_LIGHT if enabled else QColor('#e2d6c2'))
            p.drawText(QRectF(c.x() - 18, c.y() - 19, 36, 36), Qt.AlignCenter, str(self._number))
        else:
            draw_diamond(p, c, 6, GOLD_LIGHT)
        p.setPen(QPen(QColor(138, 102, 51, 110), 1))
        sep = r.left() + (44 if tight else 60)
        p.drawLine(QPointF(sep, inner.top() + (5 if tight else 9)), QPointF(sep, inner.bottom() - (5 if tight else 9)))
        if self._destination and not tight:
            x0 = r.right() - 84
            p.setPen(QPen(QColor(138, 102, 51, 110), 1))
            p.drawLine(QPointF(x0, inner.top() + 8), QPointF(x0, inner.bottom() - 8))
            color = RUBRIC if enabled else QColor('#a8987e')
            dx = 4 if hover else 0
            draw_icon(p, 'arrow', QPointF(x0 + 22 + dx, r.center().y()), 9, color)
            p.setFont(adventurer_sheet.font('title', 18, bold=True, italic=True))
            p.setPen(color)
            p.drawText(QRectF(x0 + 34, r.top(), 52, r.height()), Qt.AlignVCenter | Qt.AlignLeft,
                       self._destination)


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
        self.background_art = QPixmap()
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
            self.picture = self.background_art if not self.background_art.isNull() else self.atmosphere
        self.update()

    def sizeHint(self):
        """Proposer une taille verticale de référence sans imposer de largeur fixe à la mise en page."""
        return QSize(300, 640)

    def set_background_art(self, pixmap=None):
        """Choisir un fond fixe sans lui donner les interactions d'une illustration.

        Un fond fourni reste indépendant du thème et ne reçoit ni ombrage ni
        inscription. Une image absente revient au décor du thème.
        """
        self.background_art = pixmap if pixmap is not None else QPixmap()
        self.set_book_art()

    def set_book_art(self, pixmap=None):
        """Choisir l’illustration ou le décor et réinitialiser zoom, déplacement et aide accessible."""
        self.is_book_art = pixmap is not None and not pixmap.isNull()
        self.picture = (pixmap if self.is_book_art else
                        self.background_art if not self.background_art.isNull() else self.atmosphere)
        self.reset_view()
        self._press_position = None
        self._dragged = False
        self.setAccessibleName("Illustration du paragraphe" if self.is_book_art
                               else "Décor fixe de la fenêtre d’illustration")
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
        return min(max(1, self.width()-22) / max(1, self.picture.width()),
                   max(1, self.height()-22) / max(1, self.picture.height()))

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
        outer = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        # Passe-partout de cuir sombre puis illustration dans le filet doré de la fiche.
        matte = QPainterPath()
        matte.addRoundedRect(outer, 10, 10)
        painter.fillPath(matte, QColor('#1e120e'))
        box = outer.adjusted(8, 8, -8, -8)
        clip = QPainterPath()
        clip.addRoundedRect(box, 6, 6)
        painter.setClipPath(clip)
        painter.fillRect(box, QColor(self.theme.color("scene_background")))
        if not self.picture.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            scale = (self._fit_scale() * self.zoom if self.is_book_art else
                     max(box.width()/self.picture.width(), box.height()/self.picture.height()))
            width, height = self.picture.width()*scale, self.picture.height()*scale
            target = QRectF(box.center().x() - width/2 + self.pan.x(),
                            box.center().y() - height/2 + self.pan.y(), width, height)
            painter.drawPixmap(target, self.picture, QRectF(self.picture.rect()))
        inner_shadow = QRadialGradient(box.center(), max(box.width(), box.height()) * .75)
        inner_shadow.setColorAt(.7, QColor(0, 0, 0, 0))
        inner_shadow.setColorAt(1, QColor(0, 0, 0, 120))
        painter.fillRect(box, inner_shadow)
        if not self.is_book_art and self.background_art.isNull():
            shade = QLinearGradient(0, self.height() / 2, 0, self.height())
            shade.setColorAt(0, QColor(20, 12, 8, 0))
            shade.setColorAt(1, QColor(20, 12, 8, 210))
            painter.fillRect(box, shade)
            painter.setPen(QColor(self.theme.color("gold")))
            painter.drawText(box.adjusted(18, 0, -18, -12),
                             Qt.AlignBottom | Qt.AlignLeft,
                             "✦  BIFURK")
        painter.setClipping(False)
        draw_gold_frame(painter, outer, 10)
