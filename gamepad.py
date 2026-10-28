"""Jouer à la manette : lecture XInput, navigation spatiale et halo de sélection.

GamepadPoller lit la manette toutes les 16 ms (XInput, l'API native de Windows :
manettes Xbox et compatibles ; une manette PlayStation passe par Steam ou DS4Windows),
traduit croix et stick gauche en directions répétées et émet des noms de boutons.
GamepadNavigator applique ces boutons à la fenêtre active, sans connaître le jeu :
- directions : d'abord à l'intérieur du contrôle (grille de la sacoche, curseur,
  liste déroulante, onglets), puis vers le contrôle le plus proche dans ce sens ;
- A valide (clic, case à cocher, liste, menu contextuel d'un objet), B annule ou
  ferme (Échap) ; dans un menu ou une liste ouverte, directions, A et B y sont envoyés ;
- stick droit : défilement de la zone qui contient la sélection (ou du texte).
La fenêtre principale peut fournir des crochets facultatifs : gamepad_command(nom),
gamepad_scope(), gamepad_default(scope), gamepad_zones() et gamepad_scroll_area().
Les champs de saisie (nom de l'aventurier, notes) ne sont jamais sélectionnés.
Un halo aux couleurs du thème entoure la sélection ; il disparaît dès que la souris
ou le clavier reprennent la main.
"""
import ctypes
import sys
import time

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractScrollArea,
                               QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox,
                               QDialog, QMenu, QScrollArea, QScrollBar, QTabBar, QWidget)
from shiboken6 import isValid

DIRECTIONS = ('up', 'down', 'left', 'right')
ARROWS = {'up': Qt.Key_Up, 'down': Qt.Key_Down, 'left': Qt.Key_Left, 'right': Qt.Key_Right}
XINPUT_BUTTONS = {0x0001: 'up', 0x0002: 'down', 0x0004: 'left', 0x0008: 'right',
                  0x0010: 'start', 0x0020: 'back', 0x0040: 'ls', 0x0080: 'rs',
                  0x0100: 'lb', 0x0200: 'rb', 0x1000: 'a', 0x2000: 'b', 0x4000: 'x', 0x8000: 'y'}


class PadState:
    """Boutons enfoncés (noms) et axes normalisés : sticks dans [-1, 1], gâchettes dans [0, 1]."""
    def __init__(self, buttons=(), lx=0.0, ly=0.0, rx=0.0, ry=0.0, lt=0.0, rt=0.0):
        self.buttons = frozenset(buttons)
        self.lx, self.ly, self.rx, self.ry, self.lt, self.rt = lx, ly, rx, ry, lt, rt


class XInputBackend:
    """Lire la première manette XInput branchée ; None sous Linux/macOS ou sans DLL."""
    RESCAN_S = 1.5   # interroger un emplacement vide est lent : recherche espacée

    class _Pad(ctypes.Structure):
        _fields_ = [('wButtons', ctypes.c_ushort), ('bLeftTrigger', ctypes.c_ubyte),
                    ('bRightTrigger', ctypes.c_ubyte), ('sThumbLX', ctypes.c_short),
                    ('sThumbLY', ctypes.c_short), ('sThumbRX', ctypes.c_short),
                    ('sThumbRY', ctypes.c_short)]

    class _State(ctypes.Structure):
        pass

    _State._fields_ = [('dwPacketNumber', ctypes.c_uint32), ('Gamepad', _Pad)]

    def __init__(self, function):
        self._get_state = function
        self.slot = None
        self.next_scan = 0.0

    @classmethod
    def create(cls):
        if sys.platform != 'win32':
            return None
        for name in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
            try:
                dll = ctypes.WinDLL(name)
            except OSError:
                continue
            function = dll.XInputGetState
            function.argtypes = (ctypes.c_uint32, ctypes.POINTER(cls._State))
            function.restype = ctypes.c_uint32
            return cls(function)
        return None

    def _read(self, slot):
        state = self._State()
        if self._get_state(slot, ctypes.byref(state)) != 0:
            return None
        pad = state.Gamepad
        stick = lambda value, dead: 0.0 if abs(value) < dead else max(-1.0, value / 32767)
        trigger = lambda value: 0.0 if value < 30 else value / 255
        return PadState([name for bit, name in XINPUT_BUTTONS.items() if pad.wButtons & bit],
                        stick(pad.sThumbLX, 7849), stick(pad.sThumbLY, 7849),
                        stick(pad.sThumbRX, 8689), stick(pad.sThumbRY, 8689),
                        trigger(pad.bLeftTrigger), trigger(pad.bRightTrigger))

    def poll(self, now):
        if self.slot is not None:
            state = self._read(self.slot)
            if state is not None:
                return state
            self.slot = None
        if now < self.next_scan:
            return None
        self.next_scan = now + self.RESCAN_S
        for slot in range(4):
            state = self._read(slot)
            if state is not None:
                self.slot = slot
                return state
        return None


class GamepadPoller(QObject):
    """Transformer l'état de la manette en appuis : directions répétées, stick droit continu."""
    pressed = Signal(str)
    scrolled = Signal(float, float)
    INTERVAL_MS = 16
    REPEAT_DELAY_S = .38
    REPEAT_S = .11
    STICK = .55

    def __init__(self, backend, parent=None, require_active=True):
        super().__init__(parent)
        self.backend = backend
        self.require_active = require_active
        self.held = set()
        self.repeat_at = {}
        self.timer = QTimer(self)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.tick)

    def start(self):
        if self.backend is not None:
            self.timer.start()

    def stop(self):
        self.timer.stop()
        self.held.clear()

    def logical(self, state):
        names = set(state.buttons)
        names.update(name for name, on in (('up', state.ly > self.STICK), ('down', state.ly < -self.STICK),
                                           ('right', state.lx > self.STICK), ('left', state.lx < -self.STICK),
                                           ('lt', state.lt > .5), ('rt', state.rt > .5)) if on)
        return names

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if self.require_active and QApplication.applicationState() != Qt.ApplicationActive:
            self.held.clear()       # autre application au premier plan : rien n'est envoyé
            return
        state = self.backend.poll(now) if self.backend is not None else None
        names = self.logical(state) if state is not None else set()
        events = []
        for name in sorted(names - self.held):
            events.append(name)
            if name in DIRECTIONS:
                self.repeat_at[name] = now + self.REPEAT_DELAY_S
        for name in DIRECTIONS:
            if name in names and name in self.held and now >= self.repeat_at.get(name, now + 1):
                events.append(name)
                self.repeat_at[name] = now + self.REPEAT_S
        self.held = names
        for name in events:
            self.pressed.emit(name)
        if state is not None and (state.rx or state.ry):
            self.scrolled.emit(state.rx, state.ry)


class FocusHalo(QWidget):
    """Cadre lumineux dessiné par-dessus la fenêtre, transparent pour la souris.

    Une lueur dorée large, un liseré sombre et un trait vif : lisible sur le
    parchemin clair comme sur le cuir sombre de la fiche."""
    MARGIN = 9

    def __init__(self, window, color):
        super().__init__(window)
        self.setObjectName('gamepadHalo')
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.color = QColor(color)

    def place(self, rect):
        self.setGeometry(rect.adjusted(-self.MARGIN, -self.MARGIN, self.MARGIN, self.MARGIN))
        self.show()
        self.raise_()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        glow = QColor(self.color)
        for width, alpha in ((12, 45), (8, 90), (5, 150)):
            glow.setAlpha(alpha)
            p.setPen(QPen(glow, width))
            p.drawRoundedRect(frame, 9, 9)
        p.setPen(QPen(QColor(30, 18, 10, 200), 5))
        p.drawRoundedRect(frame, 9, 9)
        p.setPen(QPen(self.color.lighter(135), 3))
        p.drawRoundedRect(frame, 9, 9)


def _alive(widget):
    return widget is not None and isValid(widget)


class GamepadNavigator(QObject):
    """Appliquer les boutons à la fenêtre active : sélection, validation, retour, défilement."""
    SCROLL_PX = 30

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.active = False         # mode manette : halo visible
        self.current = None
        self.memory = {}            # fenêtre -> dernière sélection (retour après un dialogue)
        self._sending = False
        self._mouse_anchor = None
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------ cibles
    def target(self):
        """Fenêtre qui reçoit la manette : menu ouvert, dialogue modal ou fenêtre active."""
        return (QApplication.activePopupWidget() or QApplication.activeModalWidget()
                or QApplication.activeWindow() or self.main)

    def _hooks(self, target):
        return target if target is self.main else None

    def scope(self, target):
        hooks = self._hooks(target)
        scope = hooks.gamepad_scope() if hooks is not None and hasattr(hooks, 'gamepad_scope') else None
        return scope or target

    def navigable(self, widget, window):
        """Contrôles que la manette sait activer ; jamais un champ de saisie de texte.

        Les compteurs de la fenêtre principale (corrections manuelles de la fiche,
        qui marquent la partie « assistée ») restent réservés à la souris et au clavier."""
        if not widget.isEnabled() or not widget.isVisible() or widget.window() is not window:
            return False
        if widget.testAttribute(Qt.WA_TransparentForMouseEvents) or isinstance(widget, (QScrollBar, FocusHalo)):
            return False
        if isinstance(widget, QAbstractButton):
            return not isinstance(widget.parent(), (QTabBar, QAbstractScrollArea))
        if isinstance(widget, QComboBox):
            return not widget.isEditable()
        if isinstance(widget, QAbstractSlider):
            return True
        if isinstance(widget, QAbstractSpinBox):
            return (window is not self.main and not widget.isReadOnly()
                    and widget.focusPolicy() != Qt.NoFocus)
        if isinstance(widget, QAbstractItemView):
            model = widget.model()
            return (widget.focusPolicy() != Qt.NoFocus and model is not None and model.rowCount() > 0
                    and not isinstance(widget.window(), QComboBox))
        if isinstance(widget, QTabBar):
            return widget.count() > 1
        return False

    def candidates(self, scope, window):
        found = []
        for widget in scope.findChildren(QWidget):
            if not self.navigable(widget, window):
                continue
            if widget.visibleRegion().isEmpty() and self._scroll_area(widget) is None:
                continue
            found.append(widget)
        return found

    def _scroll_area(self, widget):
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea) and parent.widget() is not None \
                    and parent.widget().isAncestorOf(widget):
                return parent
            parent = parent.parentWidget()
        return None

    @staticmethod
    def rect_in(widget, window):
        return QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())

    def _in_scope(self, widget, scope, window):
        return (_alive(widget) and (scope is widget or scope.isAncestorOf(widget))
                and self.navigable(widget, window))

    def valid_current(self, scope, window):
        if self._in_scope(self.current, scope, window):
            return self.current
        remembered = self.memory.get(id(window))
        if self._in_scope(remembered, scope, window):
            self.current = remembered
            return remembered
        return None

    def default(self, target, scope):
        hooks = self._hooks(target)
        if hooks is not None and hasattr(hooks, 'gamepad_default'):
            widget = hooks.gamepad_default(None if scope is target else scope)
            if widget is not None and self.navigable(widget, target):
                return widget
        focus = target.focusWidget()
        if _alive(focus) and self._in_scope(focus, scope, target):
            return focus
        candidates = self.candidates(scope, target)
        defaults = [w for w in candidates if getattr(w, 'isDefault', lambda: False)()]
        if defaults:
            return defaults[0]
        return min(candidates, key=lambda w: (self.rect_in(w, target).top() // 12,
                                              self.rect_in(w, target).left()), default=None)

    # ------------------------------------------------------------------ sélection
    def select(self, widget):
        if widget is None:
            return
        self.current = widget
        window = widget.window()
        self.memory[id(window)] = widget
        if widget.focusPolicy() & Qt.TabFocus:
            widget.setFocus(Qt.TabFocusReason)
        area = self._scroll_area(widget)
        if area is not None:
            area.ensureWidgetVisible(widget, 16, 24)
        if isinstance(widget, QAbstractItemView) and not widget.currentIndex().isValid():
            widget.setCurrentIndex(widget.model().index(0, 0))
        self.refresh()

    def _inner_move(self, widget, direction):
        """Déplacement dans le contrôle ; False au bord pour laisser la navigation spatiale."""
        horizontal = direction in ('left', 'right')
        step = 1 if direction in ('right', 'down') else -1
        if isinstance(widget, QAbstractItemView):
            before = widget.currentIndex()
            self._send_key(widget, ARROWS[direction])
            after = widget.currentIndex()
            if after.isValid() and after != before:
                widget.scrollTo(after)
                return True
            return False
        if isinstance(widget, QAbstractSlider) and horizontal and widget.orientation() == Qt.Horizontal:
            widget.triggerAction(QAbstractSlider.SliderSingleStepAdd if step > 0
                                 else QAbstractSlider.SliderSingleStepSub)
            return True
        if isinstance(widget, QAbstractSpinBox) and horizontal:
            widget.stepBy(step)
            return True
        if isinstance(widget, (QComboBox, QTabBar)) and horizontal:
            index = widget.currentIndex() + step
            if 0 <= index < widget.count():
                widget.setCurrentIndex(index)
                return True
        return False

    def nearest(self, current, candidates, direction, window):
        """Contrôle le plus proche dans la direction, en préférant ceux alignés."""
        origin = self.rect_in(current, window)
        center = origin.center()
        best, best_score = None, None
        for widget in candidates:
            if widget is current or widget.isAncestorOf(current) or current.isAncestorOf(widget):
                continue
            rect = self.rect_in(widget, window)
            point = rect.center()
            if direction in ('up', 'down'):
                advance = (point.y() - center.y()) * (1 if direction == 'down' else -1)
                gap = (rect.top() - origin.bottom()) if direction == 'down' else (origin.top() - rect.bottom())
                side = max(0, rect.left() - origin.right(), origin.left() - rect.right())
                drift = abs(point.x() - center.x())
            else:
                advance = (point.x() - center.x()) * (1 if direction == 'right' else -1)
                gap = (rect.left() - origin.right()) if direction == 'right' else (origin.left() - rect.right())
                side = max(0, rect.top() - origin.bottom(), origin.top() - rect.bottom())
                drift = abs(point.y() - center.y())
            # Cône de 50° environ, sauf pour les contrôles alignés dans ce sens.
            if advance <= 4 or (side > 0 and drift > advance * 1.2):
                continue
            score = max(0, gap) + side * 4 + drift * .25
            if best_score is None or score < best_score:
                best, best_score = widget, score
        return best

    # ------------------------------------------------------------------ boutons
    def handle(self, name):
        """Point d'entrée des appuis (déjà reportés hors du minuteur de lecture)."""
        self._set_active(True)
        target = self.target()
        if isinstance(target, QMenu) or (target is QApplication.activePopupWidget()):
            self._popup(name)
            return
        hooks = self._hooks(target)
        if hooks is not None and name not in DIRECTIONS + ('a',) and hasattr(hooks, 'gamepad_command'):
            if hooks.gamepad_command(name):
                self.refresh()
                return
        if name in ('lb', 'rb'):
            self.switch_zone(target, 1 if name == 'rb' else -1)
        elif name in DIRECTIONS:
            self.move(target, name)
        elif name == 'a':
            self.activate(target)
        elif name == 'b':
            self.back(target)
        self.refresh()

    def _popup(self, name):
        keys = dict(ARROWS, a=Qt.Key_Return, b=Qt.Key_Escape)
        if name in keys:
            receiver = QApplication.focusWidget() or QApplication.activePopupWidget()
            popup = QApplication.activePopupWidget()
            if isinstance(popup, QMenu):
                receiver = popup
            self._send_key(receiver, keys[name])
        self.refresh()

    def move(self, target, direction):
        scope = self.scope(target)
        current = self.valid_current(scope, target)
        if current is None:
            self.select(self.default(target, scope))
            return
        if self._inner_move(current, direction):
            return
        self.select(self.nearest(current, self.candidates(scope, target), direction, target))

    def activate(self, target):
        scope = self.scope(target)
        widget = self.valid_current(scope, target)
        if widget is None:
            widget = self.default(target, scope)
            if widget is None:
                self._send_key(target.focusWidget() or target, Qt.Key_Return)
                return
            self.select(widget)
            return
        if isinstance(widget, QAbstractButton):
            widget.click()
        elif isinstance(widget, QComboBox):
            widget.showPopup()
        elif isinstance(widget, QAbstractItemView):
            index = widget.currentIndex()
            if not index.isValid():
                return
            if widget.contextMenuPolicy() == Qt.CustomContextMenu:
                widget.customContextMenuRequested.emit(widget.visualRect(index).center())
            else:
                widget.activated.emit(index)

    def back(self, target):
        if target is self.main:
            return
        self._send_key(target.focusWidget() or target, Qt.Key_Escape)

    def switch_zone(self, target, step):
        hooks = self._hooks(target)
        zones = [zone for zone in (hooks.gamepad_zones() if hooks is not None and hasattr(hooks, 'gamepad_zones')
                                   else []) if zone is not None and zone.isVisible()]
        if not zones or self.scope(target) is not target:
            return
        current = self.valid_current(target, target)
        index = next((i for i, zone in enumerate(zones) if current is not None and zone.isAncestorOf(current)), -1)
        for offset in range(1, len(zones) + 1):
            zone = zones[(index + step * offset) % len(zones)]
            choice = self.default(target, zone) if zone is not None else None
            if choice is not None and zone.isAncestorOf(choice):
                self.select(choice)
                return

    def scroll(self, dx, dy=None):
        """Stick droit : faire défiler la zone de la sélection, sinon le texte du livre.

        Un seul argument : défilement vertical (compatibilité)."""
        if dy is None:
            dx, dy = 0.0, dx
        self._set_active(True)
        target = self.target()
        if isinstance(target, QMenu):
            return
        area = None
        widget = self.current if _alive(self.current) and self.current.window() is target else None
        scrollable = lambda w: (w.verticalScrollBar().maximum() > 0 if dy
                                else w.horizontalScrollBar().maximum() > 0)
        while widget is not None and area is None:
            if isinstance(widget, QAbstractScrollArea) and scrollable(widget):
                area = widget
            widget = widget.parentWidget()
        hooks = self._hooks(target)
        if area is None and hooks is not None and hasattr(hooks, 'gamepad_scroll_area'):
            area = hooks.gamepad_scroll_area()
        if area is None:
            area = next((w for w in target.findChildren(QAbstractScrollArea)
                         if w.isVisible() and scrollable(w)), None)
        if area is None:
            return
        for bar, value in ((area.verticalScrollBar(), -dy), (area.horizontalScrollBar(), dx)):
            if value:
                bar.setValue(bar.value() + round(self.SCROLL_PX * value * abs(value)))
        self.refresh()

    # ------------------------------------------------------------------ halo
    def refresh(self):
        """Replacer le halo (appelé à chaque lecture de la manette quand elle est active)."""
        if not self.active:
            return
        target = self.target()
        for halo in self._halos():
            halo.hide()
        if isinstance(target, QMenu) or target is QApplication.activePopupWidget():
            return
        scope = self.scope(target)
        current = self.valid_current(scope, target)
        if current is None:
            current = self.default(target, scope)
            if current is None:
                return
            self.select(current)
            return
        rect = self.rect_in(current, target)
        if isinstance(current, QAbstractItemView) and current.currentIndex().isValid():
            item = current.visualRect(current.currentIndex())
            rect = QRect(current.viewport().mapTo(target, item.topLeft()), item.size())
        visible = current.visibleRegion().boundingRect()
        if not visible.isEmpty() and not isinstance(current, QAbstractItemView):
            rect = QRect(current.mapTo(target, visible.topLeft()), visible.size())
        halo = target.findChild(FocusHalo, 'gamepadHalo', Qt.FindDirectChildrenOnly)
        if halo is None:
            halo = FocusHalo(target, self._color(target))
        halo.color = QColor(self._color(target))
        halo.place(rect)

    def _halos(self):
        return [halo for window in QApplication.topLevelWidgets()
                for halo in window.findChildren(FocusHalo, 'gamepadHalo', Qt.FindDirectChildrenOnly)]

    def _color(self, target):
        color = getattr(self.main, 'gamepad_halo_color', None)
        return color() if callable(color) else target.palette().highlight().color()

    def _set_active(self, active):
        if active == self.active:
            return
        self.active = active
        self._mouse_anchor = None
        if not active:
            for halo in self._halos():
                halo.hide()

    def _send_key(self, receiver, key):
        if receiver is None:
            return
        self._sending = True
        try:
            for kind in (QEvent.KeyPress, QEvent.KeyRelease):
                QApplication.sendEvent(receiver, QKeyEvent(kind, key, Qt.NoModifier))
        finally:
            self._sending = False

    def eventFilter(self, watched, event):
        """La souris ou le clavier reprennent la main : le halo s'efface."""
        if self.active and not self._sending:
            kind = event.type()
            if kind in (QEvent.MouseButtonPress, QEvent.Wheel, QEvent.KeyPress):
                self._set_active(False)
            elif kind == QEvent.MouseMove:
                position = event.globalPosition().toPoint()
                if self._mouse_anchor is None:
                    self._mouse_anchor = position
                elif (position - self._mouse_anchor).manhattanLength() > 12:
                    self._set_active(False)
        return False


class Gamepad(QObject):
    """Assembler lecture et navigation ; les appuis sont traités hors du minuteur."""
    def __init__(self, main_window, backend=None, enabled=True, require_active=True):
        super().__init__(main_window)
        self.backend = backend if backend is not None else XInputBackend.create()
        self.navigator = GamepadNavigator(main_window, self)
        self.poller = GamepadPoller(self.backend, self, require_active=require_active)
        # Report d'un tour de boucle : un clic peut ouvrir un dialogue modal (exec)
        # sans bloquer la lecture de la manette, qui pilote alors ce dialogue.
        self.poller.pressed.connect(lambda name: QTimer.singleShot(0, lambda: self.navigator.handle(name)))
        self.poller.scrolled.connect(self.navigator.scroll)
        self.poller.timer.timeout.connect(self.navigator.refresh)
        self.enabled = False
        self.set_enabled(enabled)

    @property
    def available(self):
        return self.backend is not None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if self.enabled:
            self.poller.start()
        else:
            self.poller.stop()
            self.navigator._set_active(False)
