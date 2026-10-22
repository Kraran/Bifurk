"""Variations visuelles des caractéristiques, sans effet sur le moteur de jeu.

Les valeurs sont déjà mises à jour lorsque ce module les observe. Une animation
ne tire aucun dé, n'attend aucun clic et n'altère ni sauvegarde ni historique.
Les rafraîchissements identiques sont ignorés ; les effets d'une même action se
cumulent dans un seul badge par caractéristique.
"""
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QTextCursor, QTextDocument
from PySide6.QtWidgets import QLabel


STAT_LABELS = {'habilete': 'Habileté', 'endurance': 'Endurance', 'chance': 'Chance'}


def rich_stat_anchor(widget, phrase):
    """Localiser une ligne du héros même si son nom occupe plusieurs lignes.

    Le document reproduit le texte riche du QLabel. Les positions de QTextCursor
    sont en UTF-16, conversion nécessaire pour les noms contenant des emoji.
    Le badge se place à droite, sans masquer le nombre courant à gauche.
    """
    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setDefaultFont(widget.font())
    document.setHtml(widget.text())
    document.setTextWidth(widget.contentsRect().width())
    text = document.toPlainText()
    index = text.rfind(phrase)
    if index < 0:
        return QPointF(widget.width() - 4, widget.height() / 2)
    cursor = QTextCursor(document)
    cursor.setPosition(len(text[:index].encode('utf-16-le')) // 2)
    document.documentLayout().documentSize()
    block = cursor.block()
    line = block.layout().lineForTextPosition(cursor.positionInBlock())
    y = document.documentLayout().blockBoundingRect(block).top() + line.y() + line.height() / 2
    spare = max(0, widget.contentsRect().height() - document.size().height())
    if widget.alignment() & Qt.AlignVCenter:
        y += spare / 2
    elif widget.alignment() & Qt.AlignBottom:
        y += spare
    return QPointF(widget.contentsRect().right() - 3, widget.contentsRect().top() + y)


class StatBadge(QLabel):
    """Petit cartouche de gain ou de perte ; totalement transparent aux clics."""
    DURATION_MS = 1800

    def __init__(self, owner, anchor, placement, theme_source, key, delta):
        super().__init__(owner)
        self.anchor, self.placement, self.theme_source = anchor, placement, theme_source
        self.key, self.delta, self.progress = key, delta, 0.0
        self.setObjectName('statChangeBadge')
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(self.DURATION_MS)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self._advance)
        self.animation.finished.connect(self.hide)
        self.set_delta(delta)

    def set_delta(self, delta):
        """Relancer le délai de lecture avec le bilan réel de l'action courante."""
        self.delta = delta
        self.setText(('+' if delta > 0 else '−') + str(abs(delta)))
        label = STAT_LABELS[self.key]
        self.setAccessibleName(f'{label} : {self.text()}')
        self.setAccessibleDescription(f'{label}, gain de {delta}' if delta > 0 else f'{label}, perte de {-delta}')
        self.animation.stop()
        self.progress = 0.0
        self._position()
        self.show()
        self.raise_()
        self.animation.start()

    def _font(self):
        font = QFont(self.font())
        font.setPixelSize(16)
        font.setBold(True)
        return font

    def _position(self):
        """Suivre le champ si la fenêtre bouge ou est redimensionnée pendant l'effet."""
        width = max(36, QFontMetrics(self._font()).horizontalAdvance(self.text()) + 18)
        local = (self.placement(self.anchor) if self.placement else
                 QPointF(self.anchor.width() / 2, self.anchor.height() / 2))
        point = QPointF(self.anchor.mapTo(self.parentWidget(), local.toPoint()))
        x = point.x() - (width if self.placement else width / 2)
        y = point.y() - 13 - self.progress * 10
        x = max(4, min(self.parentWidget().width() - width - 4, x))
        y = max(4, min(self.parentWidget().height() - 30, y))
        self.setGeometry(round(x), round(y), width, 26)

    def _advance(self, progress):
        self.progress = float(progress)
        self._position()
        self.update()

    def paintEvent(self, event):
        """Tenir le résultat lisible avant une disparition douce, avec signe explicite."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        opacity = min(1.0, self.progress / .08, (1 - self.progress) / .35)
        painter.setOpacity(max(0.0, opacity))
        theme = self.theme_source()
        gain = self.delta > 0
        painter.setBrush(QColor(theme.color('gold' if gain else 'rubric')))
        painter.setPen(QPen(QColor(theme.color('frame')), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)
        painter.setPen(QColor(theme.color('ink' if gain else 'page')))
        painter.setFont(self._font())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class StatFeedback(QObject):
    """Observer les trois caractéristiques et gérer au plus un badge pour chacune."""
    changed = Signal(str, int)

    def __init__(self, owner, targets, theme_source):
        super().__init__(owner)
        self.owner, self.targets, self.theme_source = owner, targets, theme_source
        self.previous = None
        self.active = {}

    def clear(self):
        """Arrêter les effets périmés, notamment lors d'une restauration ou d'un nouveau héros."""
        for badge, _ in self.active.values():
            badge.animation.stop()
            badge.hide()
            badge.deleteLater()
        self.active.clear()

    def observe(self, character, *, enabled, batch):
        """Comparer des valeurs réelles ; une synchronisation silencieuse change aussi la référence."""
        values = {key: int(character[key]) for key in self.targets}
        previous, self.previous = self.previous, values
        if not enabled or previous is None:
            self.clear()
            return
        for key, value in values.items():
            delta = value - previous[key]
            if not delta:
                continue
            anchor, placement = self.targets[key]
            if not anchor.isVisible() or anchor.visibleRegion().isEmpty():
                continue
            old = self.active.get(key)
            total = delta
            if old:
                badge, old_batch = old
                if old_batch == batch:
                    total += badge.delta
                badge.animation.stop()
                badge.hide()
                badge.deleteLater()
                del self.active[key]
            self.changed.emit(key, delta)
            if not total:
                continue
            badge = StatBadge(self.owner, anchor, placement, self.theme_source, key, total)
            self.active[key] = (badge, batch)
            badge.animation.finished.connect(lambda k=key, b=badge: self._finished(k, b))

    def _finished(self, key, badge):
        """Nettoyer le badge terminé sans effacer son éventuel remplaçant."""
        if key in self.active and self.active[key][0] is badge:
            del self.active[key]
        badge.deleteLater()
