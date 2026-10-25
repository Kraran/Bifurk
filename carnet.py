"""Carnet de l'aventurier et marque-pages.

Le carnet est une note libre (texte brut, les renvois « §N » deviennent des liens) ;
les marque-pages sont une courte liste {paragraph, label, at}. Les deux voyagent dans
la sauvegarde sous les clés optionnelles « notes » et « bookmarks » : une ancienne
sauvegarde sans ces clés se charge avec un carnet vide. Ils ne font pas partie de
l'état de jeu annulable : Annuler/Rétablir ne réécrit jamais une note.

Aller à un marque-page ou suivre un renvoi du carnet passe par manual_travel :
c'est un déplacement hors des choix du livre, donc confirmé, enregistré dans
l'historique (annulable) et marqué « Partie assistée » comme toute navigation libre.
"""
import re
from datetime import datetime

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QEvent, Signal, QTimer
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QPixmap, QLinearGradient,
                           QRadialGradient, QTextCursor, QTextCharFormat, QTextBlockFormat, QKeySequence,
                           QShortcut, QFontMetricsF, QSyntaxHighlighter)
from PySide6.QtWidgets import (QWidget, QAbstractButton, QPushButton, QTextEdit, QLabel,
                               QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QCheckBox,
                               QMenu, QInputDialog, QMessageBox, QSizePolicy)

from adventurer_sheet import (GOLD, GOLD_LIGHT, GOLD_DARK, BORDEAUX, BORDEAUX_DARK, IVORY,
                              font, draw_diamond)
from grimoire_chrome import RUBRIC, PAGE_INK, BRONZE, draw_corner_fleurons, draw_fleuron_rule

REFERENCE = re.compile(r'§\s?(\d{1,4})')
LABEL_MAX = 60
MONTHS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
          'septembre', 'octobre', 'novembre', 'décembre')


# --------------------------------------------------------------------------- données
def read_notes(raw):
    """Texte du carnet ; toute valeur absente ou invalide donne un carnet vide."""
    return raw if isinstance(raw, str) else ''


def read_bookmarks(raw):
    """Liste propre de marque-pages : un seul par paragraphe, libellé court, ordre conservé."""
    result, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        number = item.get('paragraph')
        if type(number) is not int or number <= 0 or number in seen:
            continue
        seen.add(number)
        label = item.get('label') if isinstance(item.get('label'), str) else ''
        at = item.get('at') if isinstance(item.get('at'), str) else ''
        result.append({'paragraph': number, 'label': label.strip()[:LABEL_MAX], 'at': at})
    return result


def references(text):
    """Numéros de paragraphe cités dans un texte (« §12 », « § 12 »)."""
    return [int(n) for n in REFERENCE.findall(text or '')]


def human_date(moment):
    return f'{moment.day} {MONTHS[moment.month - 1]}, {moment:%H} h {moment:%M}'


def entry_header(paragraph, moment=None, *, stamp=True):
    """Ligne d'en-tête d'une entrée : « ✦ §12 — 24 octobre, 14 h 32 »."""
    parts = [f'§{paragraph}'] if paragraph is not None else []
    if stamp:
        parts.append(human_date(moment or datetime.now()))
    return '✦ ' + ' — '.join(parts) if parts else '✦'


def split_references(line):
    """Découper une ligne en morceaux (texte, numéro ou None) pour poser les liens §N."""
    parts, last = [], 0
    for match in REFERENCE.finditer(line):
        if match.start() > last:
            parts.append((line[last:match.start()], None))
        parts.append((f'§{match.group(1)}', int(match.group(1))))
        last = match.end()
    if last < len(line):
        parts.append((line[last:], None))
    return parts


# --------------------------------------------------------------------------- dessin
def ribbon_path(r):
    """Ruban à queue d'aronde, accroché en haut du rectangle r."""
    notch = r.height() * .2
    path = QPainterPath(QPointF(r.left(), r.top()))
    path.lineTo(r.right(), r.top())
    path.lineTo(r.right(), r.bottom())
    path.lineTo(r.center().x(), r.bottom() - notch)
    path.lineTo(r.left(), r.bottom())
    path.closeSubpath()
    return path


def draw_ribbon(p, r, filled=True, hover=False):
    path = ribbon_path(r)
    p.setRenderHint(QPainter.Antialiasing)
    if filled:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawPath(path.translated(1.2, 1.5))
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor('#5a1a24'))
        g.setColorAt(.45, QColor('#a33545') if hover else QColor('#8e2c3a'))
        g.setColorAt(1, QColor('#4a141c'))
        p.setBrush(g)
        p.setPen(QPen(GOLD_DARK, 1))
        p.drawPath(path)
        inner = r.adjusted(r.width() * .22, 0, -r.width() * .22, -r.height() * .1)
        p.setPen(QPen(GOLD, .9))
        p.drawLine(QPointF(inner.left(), r.top()), QPointF(inner.left(), inner.bottom() - r.height() * .12))
        p.drawLine(QPointF(inner.right(), r.top()), QPointF(inner.right(), inner.bottom() - r.height() * .12))
        draw_diamond(p, QPointF(r.center().x(), r.top() + r.height() * .42), r.width() * .2, GOLD_LIGHT)
        p.setBrush(Qt.NoBrush)
    else:
        p.setBrush(QColor(122, 38, 50, 40 if hover else 14))
        p.setPen(QPen(RUBRIC if hover else BRONZE, 1.3, Qt.DashLine))
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        c = QPointF(r.center().x(), r.top() + r.height() * .42)
        p.setPen(QPen(RUBRIC if hover else BRONZE, 1.4))
        p.drawLine(QPointF(c.x() - 3.5, c.y()), QPointF(c.x() + 3.5, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 3.5), QPointF(c.x(), c.y() + 3.5))


def page_texture(theme):
    assets = getattr(theme, 'assets', {}) or {}
    path = assets.get('page') or assets.get('parchment')
    return QPixmap(str(path)) if path else QPixmap()


def paint_parchment(p, page, texture, *, gutter=None):
    """Feuillet de vélin : texture, vieillissement et pli de reliure du côté donné."""
    clip = QPainterPath()
    clip.addRoundedRect(page, 4, 4)
    p.save()
    p.setClipPath(clip)
    p.fillPath(clip, QColor('#ead9b8'))
    if not texture.isNull():
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(page, texture, QRectF(texture.rect()))
    if gutter:
        edge = page.right() if gutter == 'right' else page.left()
        step = -60 if gutter == 'right' else 60
        g = QLinearGradient(QPointF(edge, 0), QPointF(edge + step, 0))
        g.setColorAt(0, QColor(70, 40, 15, 140))
        g.setColorAt(.3, QColor(70, 40, 15, 45))
        g.setColorAt(1, QColor(70, 40, 15, 0))
        p.fillRect(page, g)
    aged = QRadialGradient(page.center(), max(page.width(), page.height()) * .75)
    aged.setColorAt(.6, QColor(120, 80, 30, 0))
    aged.setColorAt(1, QColor(120, 80, 30, 60))
    p.fillRect(page, aged)
    p.restore()


# --------------------------------------------------------------------------- widgets
class BookmarkRibbon(QAbstractButton):
    """Ruban du paragraphe courant : creux = non marqué, plein = marqué."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedSize(24, 34)
        self.setFocusPolicy(Qt.TabFocus)
        self._sync_tip()
        self.toggled.connect(lambda _=False: self._sync_tip())

    def _sync_tip(self):
        tip = ('Paragraphe marqué — gérer le marque-page (B)' if self.isChecked()
               else 'Marquer ce paragraphe (B)')
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def sizeHint(self):
        return QSize(24, 34)

    def nextCheckState(self):
        pass  # L'état suit les données du carnet, pas le clic.

    def paintEvent(self, event):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(4, 0, -5, -2)
        draw_ribbon(p, r, self.isChecked(), self.underMouse())
        if self.hasFocus():
            p.setPen(QPen(RUBRIC, 1, Qt.DotLine))
            p.drawRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5))


class ReferenceHighlighter(QSyntaxHighlighter):
    """Mise en forme vivante du carnet : en-têtes « ✦ » à la rubrique, renvois §N en lien.

    Les formats d'un QSyntaxHighlighter vivent dans la mise en page, pas dans le document :
    ils ne passent ni par la pile Annuler/Rétablir ni par contentsChange, et Qt ne recalcule
    que les blocs touchés par une modification. Le document lui-même ne contient que du
    texte à l'encre ordinaire : aucun format d'ancre ne peut donc « déborder » sur le texte
    tapé juste après un lien.
    """

    def highlightBlock(self, text):
        if text.startswith('✦'):
            header = QTextCharFormat()
            header.setForeground(RUBRIC)
            header.setFontItalic(True)
            self.setFormat(0, len(text), header)
        for match in REFERENCE.finditer(text):
            link = QTextCharFormat(self.format(match.start()))
            link.setForeground(RUBRIC)
            link.setFontWeight(600)
            self.setFormat(match.start(), match.end() - match.start(), link)


class LinedNotes(QTextEdit):
    """Feuille lignée : texte libre, renvois §N cliquables sans quitter l'édition.

    La cible d'un renvoi se lit toujours dans le texte (« §12 » mène au 12) au moment du
    survol ou du clic ; elle ne dépend d'aucun format stocké, donc éditer §12 en §123,
    effacer le « § » ou taper après un lien donne immédiatement la bonne cible.
    """
    referenceActivated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QTextEdit { background: transparent; border: none; "
                           "font-family: 'EB Garamond'; font-size: 18px; "
                           "color: #2e1d14; selection-background-color: #c9a46a; }")
        self.setFont(font('title', 17))
        self.document().setDocumentMargin(4)
        self.setPlaceholderText('Vos notes de voyage : indices, mots de passe, objets à retrouver…')
        self.viewport().setMouseTracking(True)
        self._press = None
        self._keep_margin()
        self.highlighter = ReferenceHighlighter(self.document())

    def line_pitch(self):
        return QFontMetricsF(self.font()).height() * 1.18

    def paintEvent(self, event):
        """Une ligne sous chaque ligne de texte réelle, puis au pas courant jusqu'en bas."""
        p = QPainter(self.viewport())
        width, height = self.viewport().width(), self.viewport().height()
        scroll = self.verticalScrollBar().value()
        pitch = self.line_pitch()
        p.setPen(QPen(QColor(122, 38, 50, 70), 1))
        p.drawLine(QPointF(self.MARGIN - 6, 0), QPointF(self.MARGIN - 6, height))
        p.drawLine(QPointF(self.MARGIN - 9, 0), QPointF(self.MARGIN - 9, height))
        p.setPen(QPen(QColor(90, 110, 140, 60), 1))
        layout = self.document().documentLayout()
        y = self.document().documentMargin() - scroll
        block = self.document().begin()
        last = rule = y
        block_seen = False
        while block.isValid():
            origin = layout.blockBoundingRect(block).top() - scroll
            lines = block.layout()
            for i in range(lines.lineCount()):
                line = lines.lineAt(i)
                last = origin + line.y() + line.height()
                block_seen = True
                rule = origin + line.y() + line.height() - line.descent() * .35
                if 0 < rule < height:
                    p.drawLine(QPointF(0, rule), QPointF(width, rule))
            block = block.next()
        y = rule + pitch if block_seen else last + pitch
        while y < height:
            if y > 0:
                p.drawLine(QPointF(0, y), QPointF(width, y))
            y += pitch
        p.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        number = self.reference_at(event.position().toPoint())
        self.viewport().setCursor(Qt.PointingHandCursor if number else Qt.IBeamCursor)
        self.viewport().setToolTip(f'Aller au §{number}' if number else '')
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        pos = event.position().toPoint()
        number = self.reference_at(pos)
        moved = self._press is not None and (self._press - pos).manhattanLength() > 4
        if number and not moved and not self.textCursor().hasSelection():
            self.referenceActivated.emit(number)

    def reference_span(self, position):
        """(début, fin, N) du renvoi qui couvre le caractère à cette position du document."""
        block = self.document().findBlock(position)
        if not block.isValid():
            return None
        offset = position - block.position()
        for match in REFERENCE.finditer(block.text()):
            if match.start() <= offset < match.end():
                return (block.position() + match.start(), block.position() + match.end(),
                        int(match.group(1)))
        return None

    def link_target(self, position):
        """Paragraphe visé par le caractère à cette position, ou None hors d'un renvoi."""
        span = self.reference_span(position)
        return span[2] if span else None

    def reference_at(self, point):
        """Paragraphe du renvoi réellement sous ce point du viewport (pas seulement le plus proche)."""
        cursor = self.cursorForPosition(point)
        for position in (cursor.position(), cursor.position() - 1):
            span = self.reference_span(position) if position >= 0 else None
            if not span:
                continue
            probe = QTextCursor(self.document())
            for i in range(span[0], span[1]):
                probe.setPosition(i)
                left = self.cursorRect(probe)
                probe.setPosition(i + 1)
                right = self.cursorRect(probe)
                if left.top() == right.top() and left.left() <= point.x() <= right.left() \
                        and left.top() <= point.y() <= left.bottom():
                    return span[2]
        return None


    def plain(self):
        return self.toPlainText()

    MARGIN = 34

    def _keep_margin(self):
        root = self.document().rootFrame()
        fmt = root.frameFormat()
        if fmt.leftMargin() != self.MARGIN:
            fmt.setLeftMargin(self.MARGIN)
            root.setFrameFormat(fmt)

    def _ink(self):
        """Le seul format stocké dans le document : l'encre ordinaire, sans ancre."""
        plain = QTextCharFormat()
        plain.setForeground(PAGE_INK)
        return plain

    def _write_line(self, cursor, line):
        cursor.insertText(line, self._ink())
        cursor.setCharFormat(self._ink())

    def _block_format(self):
        fmt = QTextBlockFormat()
        fmt.setLineHeight(118, QTextBlockFormat.ProportionalHeight.value)
        return fmt

    def set_notes(self, text):
        """Reconstruire la feuille depuis le texte brut : en-têtes à la rubrique, liens §N."""
        self.clear()
        self._keep_margin()
        cursor = QTextCursor(self.document())
        cursor.setBlockFormat(self._block_format())
        for i, line in enumerate((text or '').split('\n')):
            if i:
                cursor.insertBlock(self._block_format(), self._ink())
            self._write_line(cursor, line)
        self.document().clearUndoRedoStacks()
        self.moveCursor(QTextCursor.End)
        self.setCurrentCharFormat(self._ink())

    def insert_reference(self, number):
        cursor = self.textCursor()
        before = cursor.block().text()[:cursor.positionInBlock()]
        cursor.beginEditBlock()
        if before and not before.endswith((' ', '(')):
            cursor.insertText(' ', self._ink())
        cursor.insertText(f'§{number} ', self._ink())
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setFocus()

    def insert_entry(self, number, stamp=True):
        """Nouvelle entrée en fin de carnet : « ✦ §N — date » puis une ligne vierge à remplir."""
        self.moveCursor(QTextCursor.End)
        cursor = self.textCursor()
        if self.toPlainText().strip():
            if cursor.block().text().strip():
                cursor.insertBlock(self._block_format(), self._ink())
            cursor.insertBlock(self._block_format(), self._ink())
        self._write_line(cursor, entry_header(number, stamp=stamp))
        cursor.insertBlock(self._block_format(), self._ink())
        self.setTextCursor(cursor)
        self.setCurrentCharFormat(self._ink())
        self.setFocus()


class BookmarkRow(QAbstractButton):
    """Ligne de la liste : ruban, cartouche §N, libellé et date ; clic = y aller."""
    removeRequested = Signal(int)
    renameRequested = Signal(int)

    def __init__(self, bookmark, title='', current=False, cited=0, parent=None):
        super().__init__(parent)
        self.bookmark, self.title, self.current, self.cited = bookmark, title, current, cited
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        n = bookmark['paragraph']
        self.setToolTip(f'Aller au §{n}' + (' (vous y êtes)' if current else ''))
        self.setAccessibleName(f'Marque-page §{n} {bookmark["label"]}')
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.close_button = QPushButton('✕', self)
        self.close_button.setObjectName('carnetRowRemove')
        self.close_button.setToolTip('Retirer ce marque-page')
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(lambda: self.removeRequested.emit(n))

    def _menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Aller au paragraphe', self.click)
        menu.addAction('Renommer…', lambda: self.renameRequested.emit(self.bookmark['paragraph']))
        menu.addAction('Retirer', lambda: self.removeRequested.emit(self.bookmark['paragraph']))
        menu.exec(self.mapToGlobal(pos))

    def resizeEvent(self, event):
        self.close_button.move(self.width() - 32, (self.height() - 24) // 2)

    def mouseDoubleClickEvent(self, event):
        self.renameRequested.emit(self.bookmark['paragraph'])

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hover = self.underMouse()
        r = QRectF(self.rect()).adjusted(1, 3, -1, -3)
        p.setPen(QPen(QColor(156, 116, 64, 170 if hover else 110), 1))
        p.setBrush(QColor(255, 248, 230, 150 if hover else 85) if not self.current
                   else QColor(122, 38, 50, 28))
        p.drawRoundedRect(r, 6, 6)
        draw_ribbon(p, QRectF(r.left() + 12, r.top() - 3, 14, 30), True, hover)
        # Cartouche §N
        tag = QRectF(r.left() + 38, r.center().y() - 13, 62, 26)
        p.setPen(QPen(GOLD, 1))
        p.setBrush(RUBRIC)
        p.drawRoundedRect(tag, 5, 5)
        p.setPen(QColor(IVORY))
        p.setFont(font('title', 15, True))
        p.drawText(tag, Qt.AlignCenter, f'§ {self.bookmark["paragraph"]}')
        text_left = tag.right() + 14
        text = QRectF(text_left, r.top() + 6, r.right() - text_left - 40, r.height() - 12)
        label = self.bookmark['label'] or self.title or 'Sans libellé'
        p.setPen(PAGE_INK if self.bookmark['label'] else QColor('#7d6a52'))
        p.setFont(font('title', 17, False, not self.bookmark['label']))
        top = text.adjusted(0, 0, 0, -text.height() / 2)
        p.drawText(top, Qt.AlignLeft | Qt.AlignBottom,
                   p.fontMetrics().elidedText(label, Qt.ElideRight, int(top.width())))
        meta = []
        if self.current:
            meta.append('vous êtes ici')
        elif self.title and self.bookmark['label']:
            meta.append(self.title)
        if self.cited:
            meta.append(f'cité {self.cited} fois dans le carnet' if self.cited > 1 else 'cité dans le carnet')
        if self.bookmark['at']:
            try:
                meta.append('marqué le ' + human_date(datetime.fromisoformat(self.bookmark['at'])))
            except ValueError:
                pass
        p.setPen(QColor('#8a6a45'))
        p.setFont(font('title', 13, False, True))
        bottom = text.adjusted(0, text.height() / 2 + 1, 0, 0)
        p.drawText(bottom, Qt.AlignLeft | Qt.AlignTop,
                   p.fontMetrics().elidedText(' · '.join(meta), Qt.ElideRight, int(bottom.width())))


class CarnetPage(QWidget):
    """Feuillet du livre ouvert, avec titre orné ; le contenu est fourni par l'appelant."""

    def __init__(self, title, subtitle, texture, gutter, parent=None):
        super().__init__(parent)
        self.texture, self.gutter = texture, gutter
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(34, 22, 34, 22)
        self.layout_.setSpacing(6)
        self.title = QLabel(title)
        self.title.setObjectName('carnetPageTitle')
        self.title.setAlignment(Qt.AlignCenter)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName('carnetPageSubtitle')
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.layout_.addWidget(self.title)
        self.layout_.addWidget(self.subtitle)
        self.layout_.addSpacing(18)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        page = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        paint_parchment(p, page, self.texture, gutter=self.gutter)
        frame = page.adjusted(12, 10, -12, -10)
        p.setPen(QPen(QColor(156, 116, 64, 150), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(frame, 3, 3)
        draw_corner_fleurons(p, frame.adjusted(-3, -3, 3, 3), color=BRONZE, light=RUBRIC, size=20)
        y = self.subtitle.geometry().bottom() + 10
        draw_fleuron_rule(p, page.center().x(), y, min(150, page.width() * .3))


class CarnetBook(QWidget):
    """Livre ouvert : notes à gauche, marque-pages à droite ; une page à la fois si étroit."""
    WIDE = 900

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        texture = page_texture(owner.theme)
        self.setObjectName('carnetBook')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 16, 22, 20)
        outer.setSpacing(8)
        bar = QHBoxLayout()
        self.cover_title = QLabel('✦  CARNET DE L’AVENTURIER  ✦')
        self.cover_title.setObjectName('carnetCoverTitle')
        bar.addWidget(self.cover_title)
        bar.addStretch()
        self.notes_tab = QPushButton('Notes')
        self.marks_tab = QPushButton('Marque-pages')
        for tab in (self.notes_tab, self.marks_tab):
            tab.setObjectName('carnetTab')
            tab.setCheckable(True)
            tab.setCursor(Qt.PointingHandCursor)
            bar.addWidget(tab)
        self.notes_tab.clicked.connect(lambda: self.show_page('notes'))
        self.marks_tab.clicked.connect(lambda: self.show_page('bookmarks'))
        bar.addSpacing(10)
        self.hint = QLabel('N ou Échap pour refermer')
        self.hint.setObjectName('carnetHint')
        bar.addWidget(self.hint)
        self.close_button = QPushButton('✕')
        self.close_button.setObjectName('carnetClose')
        self.close_button.setToolTip('Refermer le carnet (N, Échap)')
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(owner.close_carnet)
        bar.addWidget(self.close_button)
        outer.addLayout(bar)
        spread = QHBoxLayout()
        spread.setSpacing(0)
        outer.addLayout(spread, 1)

        # Page de gauche : notes.
        self.notes_page = CarnetPage('Notes de voyage', '', texture, 'right')
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.entry_button = QPushButton('✦  Nouvelle entrée')
        self.insert_button = QPushButton('§  Insérer § courant')
        self.stamp_box = QCheckBox('Dater les entrées')
        self.stamp_box.setChecked(True)
        for b in (self.entry_button, self.insert_button):
            b.setObjectName('carnetTool')
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(30)
            tools.addWidget(b)
        self.entry_button.setToolTip('Ajouter une entrée « ✦ §N — date » en fin de carnet')
        self.insert_button.setToolTip('Insérer un renvoi cliquable vers le paragraphe courant')
        self.stamp_box.setObjectName('carnetStamp')
        tools.addStretch()
        tools.addWidget(self.stamp_box)
        self.notes_page.layout_.addLayout(tools)
        self.editor = LinedNotes()
        self.notes_page.layout_.addWidget(self.editor, 1)
        self.entry_button.clicked.connect(
            lambda: self.editor.insert_entry(owner.current_paragraph, self.stamp_box.isChecked()))
        self.insert_button.clicked.connect(lambda: self.editor.insert_reference(owner.current_paragraph))
        self.editor.textChanged.connect(self._notes_changed)
        self.editor.referenceActivated.connect(owner.go_to_bookmark)

        # Page de droite : marque-pages.
        self.marks_page = CarnetPage('Marque-pages', '', texture, 'left')
        self.marks_list = QVBoxLayout()
        self.marks_list.setContentsMargins(0, 0, 6, 0)
        self.marks_list.setSpacing(6)
        holder = QWidget()
        holder.setObjectName('carnetMarksHolder')
        holder.setLayout(self.marks_list)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('carnetScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidget(holder)
        self.marks_page.layout_.addWidget(self.scroll, 1)
        self.mark_button = QPushButton()
        self.mark_button.setObjectName('carnetTool')
        self.mark_button.setCursor(Qt.PointingHandCursor)
        self.mark_button.setFixedHeight(30)
        self.mark_button.clicked.connect(owner.toggle_bookmark)
        foot = QHBoxLayout()
        foot.addWidget(self.mark_button)
        foot.addStretch()
        self.marks_hint = QLabel('Clic : y aller · double-clic : renommer')
        self.marks_hint.setObjectName('carnetFootHint')
        foot.addWidget(self.marks_hint)
        self.marks_page.layout_.addLayout(foot)
        spread.addWidget(self.notes_page, 1)
        spread.addWidget(self.marks_page, 1)
        self.page = 'notes'
        self._style()

    def _style(self):
        self.setStyleSheet("""
            QLabel#carnetCoverTitle { color: #f4dc9e; font-family: 'EB Garamond'; font-size: 19px;
                font-weight: bold; letter-spacing: 3px; background: transparent; }
            QLabel#carnetHint { color: #c9a46a; font-family: 'EB Garamond'; font-style: italic;
                font-size: 14px; background: transparent; }
            QPushButton#carnetClose { background: #3d1218; color: #f4dc9e; border: 1px solid #d8b46c;
                border-radius: 14px; font-size: 14px; padding: 0; min-width: 28px; max-width: 28px;
                min-height: 28px; max-height: 28px; }
            QPushButton#carnetClose:hover { background: #7a2632; }
            QPushButton#carnetTab { background: transparent; color: #d8b46c; border: 1px solid #8a6633;
                border-radius: 13px; padding: 3px 14px; font-family: 'EB Garamond'; font-size: 15px;
                min-width: 0; min-height: 0; }
            QPushButton#carnetTab:checked { background: #7a2632; color: #f4dc9e; border-color: #d8b46c; }
            QLabel#carnetPageTitle { color: #7a2632; font-family: 'EB Garamond'; font-size: 27px;
                font-weight: bold; background: transparent; }
            QLabel#carnetPageSubtitle { color: #8a6a45; font-family: 'EB Garamond'; font-style: italic;
                font-size: 15px; background: transparent; }
            QLabel#carnetFootHint, QCheckBox#carnetStamp { color: #8a6a45; font-family: 'EB Garamond';
                font-style: italic; font-size: 14px; background: transparent; }
            QPushButton#carnetTool { background: rgba(255,248,230,150); color: #7a2632;
                border: 1px solid #9c7440; border-radius: 14px; padding: 4px 14px;
                font-family: 'EB Garamond'; font-size: 15px; font-weight: 600; min-width: 0;
                min-height: 20px; max-height: 20px; }
            QPushButton#carnetTool:hover { background: #7a2632; color: #f5e7c6; border-color: #d8b46c; }
            QPushButton#carnetTool:disabled { color: #a9957a; border-color: #c9b48f; }
            QPushButton#carnetRowRemove { background: transparent; color: #9c7440; border: none;
                font-size: 13px; padding: 0; min-width: 0; min-height: 0; }
            QPushButton#carnetRowRemove:hover { color: #7a2632; }
            QScrollArea#carnetScroll, QWidget#carnetMarksHolder { background: transparent; }
            QLabel#carnetEmpty { color: #7d6a52; font-family: 'EB Garamond'; font-style: italic;
                font-size: 16px; background: transparent; }
        """)
        self.scroll.viewport().setAutoFillBackground(False)

    def _notes_changed(self):
        self.owner.notes = self.editor.plain()
        self._update_counts()

    def _update_counts(self):
        entries = sum(1 for line in self.owner.notes.split('\n') if line.startswith('✦'))
        refs = len(set(references(self.owner.notes)))
        self.notes_page.subtitle.setText(
            f'{entries} entrée{"s" * (entries > 1)} · {refs} renvoi{"s" * (refs > 1)}' if self.owner.notes.strip()
            else 'Le carnet est vierge')
        n = len(self.owner.bookmarks)
        self.marks_page.subtitle.setText(f'{n} page{"s" * (n > 1)} marquée{"s" * (n > 1)}' if n
                                         else 'Aucune page marquée')

    def wide(self):
        return self.width() >= self.WIDE

    def show_page(self, page):
        self.page = page
        self._layout_pages()

    def _layout_pages(self):
        wide = self.wide()
        self.notes_tab.setVisible(not wide)
        self.marks_tab.setVisible(not wide)
        self.hint.setVisible(wide)
        self.notes_tab.setChecked(self.page == 'notes')
        self.marks_tab.setChecked(self.page == 'bookmarks')
        self.notes_page.setVisible(wide or self.page == 'notes')
        self.marks_page.setVisible(wide or self.page == 'bookmarks')
        self.notes_page.gutter = 'right' if wide else None
        self.marks_page.gutter = 'left' if wide else None

    def resizeEvent(self, event):
        self._layout_pages()
        super().resizeEvent(event)

    def refresh(self, reload_notes=False):
        owner = self.owner
        if reload_notes:
            self.editor.blockSignals(True)
            self.editor.set_notes(owner.notes)
            self.editor.blockSignals(False)
        playing = owner.current_paragraph is not None
        self.insert_button.setEnabled(playing)
        self.insert_button.setText(f'§  Insérer §{owner.current_paragraph}' if playing else '§  Insérer § courant')
        self.mark_button.setEnabled(playing)
        marked = playing and owner.is_bookmarked(owner.current_paragraph)
        self.mark_button.setText(f'Retirer le §{owner.current_paragraph}' if marked
                                 else f'＋  Marquer le §{owner.current_paragraph}' if playing
                                 else 'Marquer le § courant')
        while self.marks_list.count():
            item = self.marks_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for mark in owner.bookmarks:
            cited = references(owner.notes).count(mark['paragraph'])
            row = BookmarkRow(mark, owner._paragraph_name(mark['paragraph']) or '',
                              mark['paragraph'] == owner.current_paragraph, cited)
            row.clicked.connect(lambda checked=False, n=mark['paragraph']: owner.go_to_bookmark(n))
            row.removeRequested.connect(owner.remove_bookmark)
            row.renameRequested.connect(owner.rename_bookmark)
            self.marks_list.addWidget(row)
        if not owner.bookmarks:
            empty = QLabel('Aucun marque-page pour l’instant.\nAppuyez sur B, ou cliquez sur le ruban '
                           'à côté du numéro de paragraphe, pour marquer une page.')
            empty.setObjectName('carnetEmpty')
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            self.marks_list.addWidget(empty)
        else:
            tip = QLabel('✦  B marque la page en cours · un §N du carnet y renvoie aussi  ✦')
            tip.setObjectName('carnetFootHint')
            tip.setAlignment(Qt.AlignCenter)
            tip.setWordWrap(True)
            self.marks_list.addSpacing(10)
            self.marks_list.addWidget(tip)
        self.marks_list.addStretch()
        self._update_counts()

    def paintEvent(self, event):
        """Couverture de cuir bordeaux à double filet doré, sous les deux feuillets."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(r.translated(3, 5), 14, 14)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor('#5a1d24'))
        g.setColorAt(.5, QColor('#47151b'))
        g.setColorAt(1, QColor('#2c0d11'))
        p.setBrush(g)
        p.setPen(QPen(GOLD_DARK, 2))
        p.drawRoundedRect(r, 14, 14)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(216, 180, 108, 150), 1))
        p.drawRoundedRect(r.adjusted(6, 6, -6, -6), 10, 10)
        if self.wide() and self.notes_page.isVisible():
            x = self.notes_page.geometry().right() + .5
            top, bottom = self.notes_page.geometry().top(), self.notes_page.geometry().bottom()
            shade = QLinearGradient(QPointF(x - 8, 0), QPointF(x + 8, 0))
            shade.setColorAt(0, QColor(0, 0, 0, 0))
            shade.setColorAt(.5, QColor(0, 0, 0, 90))
            shade.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(QRectF(x - 8, top, 16, bottom - top), shade)


class CarnetOverlay(QWidget):
    """Voile sombre sur la fenêtre et livre ouvert centré ; clic hors du livre = refermer."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.book = CarnetBook(owner, self)
        owner.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self.owner and event.type() == QEvent.Resize and self.isVisible():
            self.place()
        return False

    def place(self):
        area = self.owner.centralWidget().geometry() if self.owner.centralWidget() else self.owner.rect()
        self.setGeometry(area)
        w = min(1240, self.width() - 60)
        h = min(760, self.height() - 40)
        self.book.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(18, 9, 5, 165))

    def mousePressEvent(self, event):
        if not self.book.geometry().contains(event.position().toPoint()):
            self.owner.close_carnet()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.owner.close_carnet()
            return
        super().keyPressEvent(event)


class CarnetMixin:
    """Branchement du carnet et des marque-pages dans MainWindow."""

    def _init_carnet(self):
        self.notes = ''
        self.bookmarks = []
        self.carnet_overlay = None
        self.bookmark_ribbon = BookmarkRibbon()
        self.bookmark_ribbon.hide()
        self.bookmark_ribbon.clicked.connect(self._ribbon_clicked)
        self.bookmark_shortcut = QShortcut(QKeySequence('B'), self, activated=self.toggle_bookmark)
        self.carnet_shortcut = QShortcut(QKeySequence('N'), self, activated=self.toggle_carnet)

    # --- données ---------------------------------------------------------------
    def _carnet_save_fields(self):
        return {'notes': self.notes, 'bookmarks': [dict(b) for b in self.bookmarks]}

    def _load_carnet(self, data):
        self.notes = read_notes(data.get('notes'))
        self.bookmarks = read_bookmarks(data.get('bookmarks'))
        self._carnet_changed(reload_notes=True)

    def _reset_carnet(self):
        self.notes, self.bookmarks = '', []
        self._carnet_changed(reload_notes=True)

    def is_bookmarked(self, number):
        return any(b['paragraph'] == number for b in self.bookmarks)

    def add_bookmark(self, number, label=''):
        if number is None or self.is_bookmarked(number):
            return False
        self.bookmarks.append({'paragraph': number, 'label': (label or '').strip()[:LABEL_MAX],
                               'at': datetime.now().isoformat(timespec='minutes')})
        self._carnet_changed(save=True)
        return True

    def remove_bookmark(self, number):
        before = len(self.bookmarks)
        self.bookmarks = [b for b in self.bookmarks if b['paragraph'] != number]
        if len(self.bookmarks) != before:
            self._carnet_changed(save=True)
            return True
        return False

    def set_bookmark_label(self, number, label):
        for b in self.bookmarks:
            if b['paragraph'] == number:
                b['label'] = (label or '').strip()[:LABEL_MAX]
                self._carnet_changed(save=True)
                return True
        return False

    def _carnet_changed(self, *, save=False, reload_notes=False):
        self._update_bookmark_ribbon()
        if self.carnet_overlay is not None:
            self.carnet_overlay.book.refresh(reload_notes)
        if save:
            self._autosave()

    # --- interactions ----------------------------------------------------------
    def _carnet_blocked(self):
        from PySide6.QtWidgets import QApplication
        return (QApplication.activeModalWidget() is not None
                or self.current_paragraph is None or not self.paragraphs)

    def _ask_label(self, number, current=''):
        title = self._paragraph_name(number) or ''
        label, ok = QInputDialog.getText(
            self, 'Marque-page', f'Libellé du marque-page au §{number} (facultatif) :',
            text=current or '')
        return label.strip()[:LABEL_MAX] if ok else None

    def toggle_bookmark(self):
        """B / ruban : marquer le paragraphe courant (libellé facultatif) ou le démarquer."""
        if self._carnet_blocked():
            return
        number = self.current_paragraph
        if self.is_bookmarked(number):
            self.remove_bookmark(number)
            return
        label = self._ask_label(number)
        if label is not None:
            self.add_bookmark(number, label)

    def _ribbon_clicked(self):
        number = self.current_paragraph
        if number is None:
            return
        if not self.is_bookmarked(number):
            self.toggle_bookmark()
            return
        menu = QMenu(self)
        menu.addAction('Renommer le marque-page…', lambda: self.rename_bookmark(number))
        menu.addAction('Retirer le marque-page', lambda: self.remove_bookmark(number))
        menu.addSeparator()
        menu.addAction('Ouvrir les marque-pages', lambda: self.open_carnet('bookmarks'))
        menu.exec(self.bookmark_ribbon.mapToGlobal(self.bookmark_ribbon.rect().bottomLeft()))

    def rename_bookmark(self, number):
        current = next((b['label'] for b in self.bookmarks if b['paragraph'] == number), None)
        if current is None:
            return
        label = self._ask_label(number, current)
        if label is not None:
            self.set_bookmark_label(number, label)

    def go_to_bookmark(self, number):
        """Renvoi du carnet ou marque-page : navigation libre confirmée, donc annulable."""
        if number == self.current_paragraph:
            self.close_carnet()
            return False
        if number not in self.paragraphs:
            QMessageBox.information(self, 'Marque-page', f'Le §{number} n’existe pas dans ce grimoire.')
            return False
        moved = self.manual_travel(number)
        if moved:
            self.close_carnet()
        return moved

    def _update_bookmark_ribbon(self):
        ribbon = getattr(self, 'bookmark_ribbon', None)
        if ribbon is None:
            return
        shown = self.current_paragraph is not None and self.paragraph_number.isVisibleTo(self)
        ribbon.setVisible(shown)
        ribbon.setChecked(shown and self.is_bookmarked(self.current_paragraph))

    def carnet_is_open(self):
        return self.carnet_overlay is not None and self.carnet_overlay.isVisible()

    def toggle_carnet(self):
        if self.carnet_is_open():
            self.close_carnet()
        else:
            self.open_carnet()

    def open_carnet(self, page='notes'):
        from PySide6.QtWidgets import QApplication
        if QApplication.activeModalWidget() is not None:
            return
        if self.carnet_overlay is None:
            self.carnet_overlay = CarnetOverlay(self)
        overlay = self.carnet_overlay
        overlay.book.show_page(page)
        overlay.book.refresh(reload_notes=True)
        self._carnet_saved_shortcuts = [(s, s.isEnabled()) for s in (
            getattr(self, 'escape_shortcut', None), getattr(self, 'sheet_shortcut', None)) if s]
        for shortcut, _ in self._carnet_saved_shortcuts:
            shortcut.setEnabled(False)
        overlay.place()
        overlay.show()
        overlay.raise_()
        if page == 'notes':
            overlay.book.editor.setFocus()
        else:
            overlay.setFocus()

    def close_carnet(self):
        overlay = self.carnet_overlay
        if overlay is None or not overlay.isVisible():
            return
        self.notes = overlay.book.editor.plain()
        self.reader.setFocus()
        overlay.hide()
        for shortcut, enabled in getattr(self, '_carnet_saved_shortcuts', []):
            shortcut.setEnabled(enabled)
        self._carnet_saved_shortcuts = []
        self._autosave()
