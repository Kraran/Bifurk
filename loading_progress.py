"""Barre de chargement du grimoire : voile sur la fenêtre et carte parchemin centrée.

Le travail lourd (empreinte SHA-256, extraction du texte PyMuPDF, lecture des
catalogues et de la sauvegarde) tourne dans un QThread sans toucher aux widgets ;
il annonce ses étapes par un signal reçu dans le thread de l'interface. Pendant
l'attente, une boucle locale continue de repeindre la fenêtre mais met en file
les clics et les touches : la partie ne peut pas changer sous le chargement.
La carte n'apparaît qu'après SHOW_DELAY_MS pour éviter tout flash sur un
chargement rapide, et reste alors visible au moins MIN_VISIBLE_MS.

Si la fenêtre se ferme pendant la lecture, la session est abandonnée : la boucle
locale rend aussitôt la main en levant LoadingCancelled, le travail est prié de
s'interrompre à sa prochaine étape et son résultat tardif n'est jamais livré.
Le thread reste référencé jusqu'à sa fin réelle (puis deleteLater) pour ne jamais
être détruit en cours d'exécution.
"""
import threading
import time
from pathlib import Path

import shiboken6
from PySide6.QtCore import QElapsedTimer, QEvent, QEventLoop, QRectF, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from adventurer_sheet import BORDEAUX_DARK, FONTS, GOLD, GOLD_DARK, GOLD_LIGHT, IVORY, INK

SHOW_DELAY_MS = 300
MIN_VISIBLE_MS = 250
YIELD_EVERY_S = .02   # rendre la main à l'interface au moins toutes les 20 ms…
YIELD_SLEEP_S = .002  # …le temps de peindre une image de la barre
PARCHMENT = Path(__file__).resolve().parent / 'assets/themes/grimoire/page-parchment.jpg'
QUIT_WAIT_MS = 3000   # attente bornée des lectures abandonnées à la sortie de l'application


class LoadingCancelled(BaseException):
    """Chargement abandonné (fenêtre fermée) : son résultat ne doit plus être appliqué.

    BaseException : ni le travail ni l'appelant ne l'avalent par un « except Exception »
    qui la prendrait pour une erreur de lecture à afficher."""


# Lectures abandonnées encore en cours : la référence garde le QThread vivant
# jusqu'à sa fin réelle, sans quoi Qt le détruirait en cours d'exécution.
_ABANDONED_WORKERS = set()
_QUIT_HOOKED = False


def _prune_abandoned():
    for worker in list(_ABANDONED_WORKERS):
        if not shiboken6.isValid(worker) or worker.isFinished():
            _ABANDONED_WORKERS.discard(worker)


def wait_for_abandoned_workers(timeout_ms=QUIT_WAIT_MS):
    """Attendre, au plus timeout_ms au total, la fin des lectures abandonnées."""
    deadline = time.monotonic() + max(0, timeout_ms) / 1000
    for worker in list(_ABANDONED_WORKERS):
        if shiboken6.isValid(worker) and not worker.isFinished():
            worker.wait(max(1, int((deadline - time.monotonic()) * 1000)))
    _prune_abandoned()
    return not _ABANDONED_WORKERS


def _keep_until_finished(worker):
    """Garder un thread abandonné jusqu'à sa fin puis le détruire dans le thread de l'interface."""
    global _QUIT_HOOKED
    _prune_abandoned()
    _ABANDONED_WORKERS.add(worker)
    worker.finished.connect(worker.deleteLater)  # slot du QThread : exécuté dans l'interface
    if worker.isFinished():  # fini avant la connexion : finished ne sera plus émis
        worker.deleteLater()
    app = QApplication.instance()
    if app is not None and not _QUIT_HOOKED:
        app.aboutToQuit.connect(wait_for_abandoned_workers)
        _QUIT_HOOKED = True


class LoadingOverlay(QWidget):
    """Voile sombre et carte parchemin/or : titre, étape en cours et barre dorée."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.title = ''
        self.step = ''
        self.detail = ''        # précision mesurée, ex. « page 34 / 170 »
        self.target = 0.0      # progression annoncée par le travail
        self.shown_value = 0.0  # valeur peinte, qui rattrape la cible en douceur
        self.phase = 0.0        # reflet qui glisse sur la barre : l'interface vit
        self.frozen = False     # captures et tests : pas d'animation
        self._parchment = QPixmap(str(PARCHMENT)) if PARCHMENT.is_file() else QPixmap()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._static = None     # fenêtre figée + voile + carte : peinte une fois par présentation
        # La carte est opaque (fond figé) : Qt ne repeint jamais la fenêtre dessous.
        # Sans cela chaque image animée repeignait toute l'interface et disputait le
        # verrou Python au travail en arrière-plan, au point de geler l'écran ~1 s.
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Chargement en cours')
        owner.installEventFilter(self)
        self.hide()

    # --- état ---------------------------------------------------------------
    def set_title(self, title):
        if title != self.title:
            self.title = title
            self._static = None
        self.update()

    def set_progress(self, fraction, step=None, detail=''):
        if fraction is not None:
            self.target = max(self.target, min(1.0, max(0.0, float(fraction))))
        if step:
            if step != self.step:
                self.detail = ''
            self.step = step
            self.setAccessibleDescription(step)
        if detail:
            self.detail = detail
        if self.frozen:
            self.shown_value = self.target
        self._update_dynamic()

    def percent(self):
        return int(round(self.target * 100))

    def _tick(self):
        if self.frozen:
            return
        self.shown_value += (self.target - self.shown_value) * .25
        if abs(self.target - self.shown_value) < .002:
            self.shown_value = self.target
        self.phase = (self.phase + .033) % 1.0
        self._update_dynamic()

    def _update_dynamic(self):
        """Ne repeindre que la barre et les lignes de texte, jamais la carte figée."""
        if self._static is None:
            self.update()
        else:
            self.update(self._dynamic_rect().toAlignedRect())

    # --- placement ----------------------------------------------------------
    def present(self):
        self.place()
        self._static = None
        self._backdrop = self.owner.grab()  # interface telle qu'elle est, figée sous le voile
        self.show()
        self.raise_()
        focused = QApplication.focusWidget()
        if focused is not self:
            self._previous_focus = focused
        self.setFocus(Qt.OtherFocusReason)
        self._timer.start()

    def dismiss(self):
        self._timer.stop()
        self.hide()
        self._static = self._backdrop = None
        previous, self._previous_focus = getattr(self, '_previous_focus', None), None
        if previous is not None:
            try:
                previous.setFocus(Qt.OtherFocusReason)
            except RuntimeError:  # widget détruit pendant le chargement
                pass

    def eventFilter(self, obj, event):
        if obj is self.owner and event.type() == QEvent.Resize and self.isVisible():
            self.hide()
            self._backdrop = self.owner.grab()
            self._static = None
            self.place()
            self.show()
        return False

    def place(self):
        self.setGeometry(self.owner.rect())
        self.raise_()

    def compact(self):
        return self.width() < 700 or self.height() < 520

    def card_rect(self):
        compact = self.compact()
        w = min(460 if not compact else 380, self.width() - 32)
        h = 178 if not compact else 150
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    # --- rendu --------------------------------------------------------------
    def _font(self, family, size, weight=QFont.Normal, italic=False, spacing=None):
        font = QFont(family)
        font.setPixelSize(size)
        font.setWeight(weight)
        font.setItalic(italic)
        if spacing is not None:
            font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
        return font

    def _layout(self):
        """Rectangles de la carte : titre, filet, barre, étape et détail."""
        card = self.card_rect()
        compact = self.compact()
        top = card.top() + (18 if compact else 24)
        title_box = QRectF(card.left() + 20, top, card.width() - 40, 34)
        line_y = title_box.bottom() + 6
        bar = QRectF(card.left() + 34, line_y + (18 if compact else 22), card.width() - 68, 16 if compact else 18)
        step_box = QRectF(card.left() + 24, bar.bottom() + 10, card.width() - 48, 26)
        detail_box = QRectF(card.left() + 12, step_box.bottom() - 2, card.width() - 24, 18)
        return card, compact, title_box, line_y, bar, step_box, detail_box

    def _dynamic_rect(self):
        _, _, _, _, bar, _, detail_box = self._layout()
        return bar.united(detail_box).adjusted(-2, -2, 2, 2)

    def _static_pixmap(self):
        """Fond figé (fenêtre + voile) et carte sans la barre, mis en cache."""
        dpr = self.devicePixelRatioF()
        if self._static is not None and self._static.size() == self.size() * dpr:
            return self._static
        pix = QPixmap(self.size() * dpr)
        pix.setDevicePixelRatio(dpr)
        pix.fill(QColor(18, 9, 5))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        backdrop = getattr(self, '_backdrop', None)
        if backdrop is not None and not backdrop.isNull():
            p.drawPixmap(0, 0, backdrop)
        p.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(18, 9, 5, 170))
        self._paint_card(p)
        p.end()
        self._static = pix
        return pix

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(event.rect(), self._static_pixmap(), self._source_rect(event.rect()))
        p.setRenderHint(QPainter.Antialiasing)
        _, compact, _, _, bar, step_box, detail_box = self._layout()
        self._bar(p, bar)
        # Étape en cours et progression mesurée.
        p.setFont(self._font(FONTS['title'], 15 if compact else 17, italic=True))
        p.setPen(INK)
        metrics = QFontMetrics(p.font())
        p.drawText(step_box, Qt.AlignHCenter | Qt.AlignTop,
                   metrics.elidedText(self.step, Qt.ElideRight, int(step_box.width())))
        p.setFont(self._font(FONTS['ui'], 11 if compact else 12, QFont.Bold, spacing=1.2))
        p.setPen(GOLD_DARK)
        p.drawText(detail_box, Qt.AlignHCenter | Qt.AlignTop,
                   ' · '.join(filter(None, (self.detail, f'{int(round(self.shown_value * 100))} %'))))

    def _source_rect(self, rect):
        dpr = self._static.devicePixelRatio() if self._static is not None else 1.0
        return QRectF(rect.x() * dpr, rect.y() * dpr, rect.width() * dpr, rect.height() * dpr).toRect()

    def _paint_card(self, p):
        card, compact, title_box, line_y, _, _, _ = self._layout()
        # Ombre portée puis parchemin.
        for i, alpha in ((10, 30), (6, 45), (3, 70)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, alpha))
            p.drawRoundedRect(card.adjusted(-i, -i + 4, i, i + 4), 10 + i, 10 + i)
        path = QPainterPath()
        path.addRoundedRect(card, 9, 9)
        p.save()
        p.setClipPath(path)
        if not self._parchment.isNull():
            p.drawPixmap(card.toRect(), self._parchment)
        else:
            p.fillRect(card, IVORY)
        wash = QLinearGradient(card.topLeft(), card.bottomLeft())
        wash.setColorAt(0, QColor(245, 231, 198, 120))
        wash.setColorAt(1, QColor(216, 186, 130, 120))
        p.fillRect(card, wash)
        p.restore()
        # Double filet d'or.
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(GOLD_DARK, 3))
        p.drawRoundedRect(card.adjusted(1.5, 1.5, -1.5, -1.5), 8, 8)
        p.setPen(QPen(GOLD, 1.2))
        p.drawRoundedRect(card.adjusted(7, 7, -7, -7), 5, 5)
        # Titre et fleurons.
        title_font = self._font(FONTS['title'], 22 if compact else 26, QFont.DemiBold)
        p.setFont(title_font)
        p.setPen(BORDEAUX_DARK)
        p.drawText(title_box, Qt.AlignCenter, self.title)
        advance = QFontMetrics(title_font).horizontalAdvance(self.title)
        y = title_box.center().y() + 1
        for side in (-1, 1):
            x = card.center().x() + side * (advance / 2 + 16)
            self._diamond(p, x, y, 4)
        # Filet décoratif sous le titre.
        grad = QLinearGradient(card.left() + 40, 0, card.right() - 40, 0)
        grad.setColorAt(0, QColor(138, 102, 51, 0))
        grad.setColorAt(.5, GOLD_DARK)
        grad.setColorAt(1, QColor(138, 102, 51, 0))
        p.setPen(QPen(grad, 1.2))
        p.drawLine(int(card.left() + 40), int(line_y), int(card.right() - 40), int(line_y))
        self._diamond(p, card.center().x(), line_y, 3.5)

    def _diamond(self, p, x, y, r):
        shape = QPainterPath()
        shape.moveTo(x, y - r); shape.lineTo(x + r, y); shape.lineTo(x, y + r); shape.lineTo(x - r, y)
        shape.closeSubpath()
        p.setPen(QPen(GOLD_DARK, 1))
        p.setBrush(GOLD)
        p.drawPath(shape)

    def _bar(self, p, bar):
        radius = bar.height() / 2
        # Gorge de cuir sombre.
        groove = QLinearGradient(bar.topLeft(), bar.bottomLeft())
        groove.setColorAt(0, QColor('#2a120c'))
        groove.setColorAt(1, QColor('#4a2418'))
        p.setPen(QPen(GOLD_DARK, 1.6))
        p.setBrush(groove)
        p.drawRoundedRect(bar, radius, radius)
        inner = bar.adjusted(3, 3, -3, -3)
        width = inner.width() * self.shown_value
        if width >= 1:
            fill = QRectF(inner.left(), inner.top(), max(width, inner.height()), inner.height())
            gold = QLinearGradient(fill.topLeft(), fill.bottomLeft())
            gold.setColorAt(0, GOLD_LIGHT)
            gold.setColorAt(.45, GOLD)
            gold.setColorAt(1, GOLD_DARK)
            p.setPen(Qt.NoPen)
            p.setBrush(gold)
            r = inner.height() / 2
            p.drawRoundedRect(fill, r, r)
            # Reflet qui glisse : signe visible que l'interface ne gèle pas.
            if not self.frozen:
                sheen_x = fill.left() + (fill.width() + 60) * self.phase - 30
                sheen = QLinearGradient(sheen_x - 30, 0, sheen_x + 30, 0)
                sheen.setColorAt(0, QColor(255, 250, 230, 0))
                sheen.setColorAt(.5, QColor(255, 250, 230, 120))
                sheen.setColorAt(1, QColor(255, 250, 230, 0))
                clip = QPainterPath()
                clip.addRoundedRect(fill, r, r)
                p.save()
                p.setClipPath(clip)
                p.fillRect(fill, sheen)
                p.restore()
        # Graduations discrètes, comme sur une règle d'arpenteur.
        p.setPen(QPen(QColor(216, 180, 108, 70), 1))
        for i in range(1, 10):
            x = inner.left() + inner.width() * i / 10
            p.drawLine(int(x), int(inner.top() + 2), int(x), int(inner.bottom() - 2))

    # Le voile absorbe la souris et le clavier tant qu'il est affiché.
    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.accept()


class _Worker(QThread):
    """Exécuter job(report) hors du thread de l'interface ; aucun widget n'y est touché."""
    progress = Signal(float, str, str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.result = None
        self.error = None
        self._last_yield = time.monotonic()
        self.gate = threading.Event()  # levé : le travail avance ; baissé : il attend l'interface
        self.gate.set()

    def run(self):
        try:
            self.result = self.job(self.report)
        except BaseException as exc:  # renvoyée telle quelle dans le thread de l'interface
            self.error = exc

    def report(self, fraction, step='', detail=''):
        # Chaque étape est un point d'interruption : une lecture abandonnée s'arrête
        # là, avant ses effets suivants (copie du livre dans la bibliothèque…).
        if self.isInterruptionRequested():
            raise LoadingCancelled()
        self.progress.emit(-1.0 if fraction is None else float(fraction), step or '', detail or '')
        # PyMuPDF garde le verrou global de Python pendant la lecture : sans pause,
        # le thread de l'interface n'obtient plus la main et l'écran gèle ~1 s.
        # Une courte pause au plus toutes les YIELD_EVERY_S lui rend la parole.
        self.gate.wait()
        if self.isInterruptionRequested():
            raise LoadingCancelled()
        now = time.monotonic()
        if now - self._last_yield >= YIELD_EVERY_S:
            time.sleep(YIELD_SLEEP_S)
            self._last_yield = time.monotonic()


class LoadingSession:
    """Encadrer un chargement : travail en thread, étapes, apparition différée, fermeture sûre.

    Utilisation :
        with LoadingSession(window, 'Ouverture du grimoire…') as session:
            data = session.run(job)          # job(report) en arrière-plan
            session.step(.95, 'Préparation de l’aventure')
            ...                              # application dans le thread de l'interface
    La carte est toujours refermée en sortie, y compris sur exception, avant que
    l'appelant n'affiche son message d'erreur.
    """
    threaded = True  # repli synchrone possible (diagnostic), les étapes restent émises

    def __init__(self, owner, title, *, delay_ms=None, min_visible_ms=None):
        self.owner = owner
        self.title = title
        self.delay_ms = SHOW_DELAY_MS if delay_ms is None else delay_ms
        self.min_visible_ms = MIN_VISIBLE_MS if min_visible_ms is None else min_visible_ms
        self.steps = []  # (fraction, étape) dans l'ordre reçu : diagnostic et tests
        self.last_fraction = 0.0
        self.last_detail = ''
        self.overlay = None
        self.clock = QElapsedTimer()
        self.visible_clock = QElapsedTimer()
        self._show_timer = None
        self._worker = None
        self._loop = None
        self.was_shown = False
        self.abandoned = False  # fenêtre fermée : plus rien ne doit être appliqué

    # --- cycle de vie -------------------------------------------------------
    def __enter__(self):
        sessions = getattr(self.owner, '_loading_sessions', None)
        if sessions is None:
            sessions = []
            setattr(self.owner, '_loading_sessions', sessions)
        sessions.append(self)  # closeEvent les abandonne
        self.clock.start()
        overlay = getattr(self.owner, 'loading_overlay', None)
        if overlay is None:
            overlay = LoadingOverlay(self.owner)
            self.owner.loading_overlay = overlay
        overlay.set_title(self.title)
        overlay.step = overlay.detail = ''
        overlay.target = overlay.shown_value = 0.0
        self.overlay = overlay
        self._show_timer = QTimer()
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._present)
        self._show_timer.start(max(0, self.delay_ms))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close(wait=exc_type is None)
        return False

    def close(self, *, wait=True):
        self._unregister()
        if self._show_timer is not None:
            self._show_timer.stop()
        overlay = self.overlay
        if overlay is not None and not shiboken6.isValid(overlay):
            overlay = self.overlay = None
        if overlay is not None and overlay.isVisible():
            if wait and self.min_visible_ms > 0:
                remaining = self.min_visible_ms - self.visible_clock.elapsed()
                if remaining > 0:
                    self._wait(remaining)
            if self.overlay is overlay and shiboken6.isValid(overlay):
                overlay.dismiss()
        self.overlay = None

    def _unregister(self):
        sessions = getattr(self.owner, '_loading_sessions', None) if shiboken6.isValid(self.owner) else None
        if sessions and self in sessions:
            sessions.remove(self)

    def abandon(self):
        """Fenêtre en fermeture : rendre la main tout de suite et ignorer le résultat.

        Le travail est prié de s'interrompre, ses signaux sont déconnectés, la carte est
        retirée ; run() lèvera LoadingCancelled au lieu de livrer le résultat tardif."""
        if self.abandoned:
            return
        self.abandoned = True
        self._unregister()
        if self._show_timer is not None:
            self._show_timer.stop()
        worker = self._worker
        if worker is not None and shiboken6.isValid(worker):
            worker.requestInterruption()
            try:
                worker.progress.disconnect()
            except (RuntimeError, TypeError):
                pass
            worker.gate.set()  # ne jamais laisser un travail suspendu à la carte
        if self._loop is not None:
            self._loop.quit()
        overlay, self.overlay = self.overlay, None
        if overlay is not None and shiboken6.isValid(overlay) and overlay.isVisible():
            overlay.dismiss()

    def _present(self):
        if self.overlay is None or self.abandoned or not shiboken6.isValid(self.overlay):
            return
        self.was_shown = True
        self.visible_clock.start()
        # Figer la fenêtre sous le voile demande de la repeindre en entier : le travail
        # s'arrête à sa prochaine étape le temps de cette unique capture.
        worker = self._worker
        if worker is not None:
            worker.gate.clear()
        try:
            self.overlay.present()
            self.overlay.repaint()
        finally:
            if worker is not None:
                worker.gate.set()

    def _wait(self, ms):
        loop = QEventLoop()
        QTimer.singleShot(int(ms), loop.quit)
        loop.exec(QEventLoop.ExcludeUserInputEvents)

    # --- étapes -------------------------------------------------------------
    def step(self, fraction, text='', detail=''):
        """Annoncer une étape depuis le thread de l'interface et la peindre tout de suite."""
        if self.abandoned:
            return
        self._record(fraction, text, detail)
        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.repaint()

    def _record(self, fraction, text, detail=''):
        fraction = None if fraction is None or fraction < 0 else fraction
        if text and (not self.steps or self.steps[-1][1] != text):
            self.steps.append((fraction, text))
        if fraction is not None:
            self.last_fraction = fraction
        if detail:
            self.last_detail = detail
        if self.overlay is not None and not shiboken6.isValid(self.overlay):
            self.overlay = None
        if self.overlay is not None:
            self.overlay.set_progress(fraction, text, detail)
        # Un chargement qui a dépassé le délai sans repasser par la boucle
        # (repli synchrone) affiche quand même la carte.
        if (self.overlay is not None and not self.overlay.isVisible()
                and self.clock.isValid() and self.clock.elapsed() >= self.delay_ms):
            self._present()

    def step_names(self):
        return [text for _, text in self.steps]

    def run(self, job):
        """Exécuter job(report) en arrière-plan ; renvoyer son résultat ou relever son erreur."""
        if self.abandoned:
            raise LoadingCancelled()
        if not self.threaded:
            result = job(lambda fraction, text='', detail='': self.step(fraction, text, detail))
            if self.abandoned:
                raise LoadingCancelled()
            return result
        worker = _Worker(job)
        self._worker = worker
        worker.progress.connect(lambda fraction, text, detail: self._record(fraction, text, detail))
        loop = QEventLoop()
        self._loop = loop
        worker.finished.connect(loop.quit)
        worker.start()
        if not worker.isFinished() and not self.abandoned:
            loop.exec(QEventLoop.ExcludeUserInputEvents)
        self._loop = None
        self._worker = None
        if self.abandoned:
            # Pas d'attente bloquante : le thread finit seul et sera détruit ensuite.
            worker.requestInterruption()
            worker.gate.set()
            _keep_until_finished(worker)
            raise LoadingCancelled()
        worker.wait()
        # Livrer les dernières étapes encore en file avant de conclure.
        QApplication.sendPostedEvents(None, QEvent.MetaCall)
        worker.deleteLater()
        if self.abandoned:  # fermeture survenue en livrant les dernières étapes
            raise LoadingCancelled()
        if worker.error is not None:
            raise worker.error
        return worker.result
