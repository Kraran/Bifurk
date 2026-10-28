"""Disposition : illustration, fiche en tiroir, mode lecture et densité selon la taille de la fenêtre.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

from adventurer_sheet import ALERT_THRESHOLD
from grimoire_ui import ChoiceCard
from illustrations import cover

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QLineEdit,
                               QPlainTextEdit, QSizePolicy, QTextEdit)

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class DispositionMixin:
    """Disposition : illustration, fiche en tiroir, mode lecture et densité selon la taille de la fenêtre."""

    def _toggle_scene_art(self, visible):
        """Afficher ou masquer la zone d’illustration sans changer le paragraphe."""
        self._apply_scene_art_visibility()
        self.art_toggle.setText("◈  Masquer l’image" if visible else "◈  Afficher l’image")

    AUTO_HIDE_ART_WIDTH = 1100

    def _apply_scene_art_visibility(self):
        """Masquer automatiquement l’illustration sur les fenêtres étroites (< 1100 px)."""
        if not hasattr(self, "scene_art"):
            return
        wanted = self.art_toggle.isChecked()
        narrow = self.width() < self.AUTO_HIDE_ART_WIDTH
        self.scene_art.setVisible(wanted and not narrow)
        self.art_toggle.setEnabled(not narrow)
        self.art_toggle.setToolTip("Fenêtre trop étroite : l’image est masquée automatiquement"
                                   if narrow else "Afficher ou masquer l’image pour agrandir la zone de lecture")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_scene_art_visibility()
        self._apply_layout_mode()
        self._apply_sheet_density()
        self._apply_auto_font_size()

    # ------------------------------------------------------------ petits écrans
    NARROW_SHEET_WIDTH = 1100   # en dessous : fiche en tiroir

    LOW_HEIGHT = 760            # en dessous : bandeau fin, en-tête de page sur une ligne

    DRAWER_WIDTH = 384

    def _apply_layout_mode(self):
        """Placer la fiche (colonne ou tiroir) et appliquer le mode lecture."""
        if not hasattr(self, 'sheet_strip'):
            return
        drawer = self.width() < self.NARROW_SHEET_WIDTH
        if drawer != self._sheet_in_drawer:
            self._sheet_in_drawer = drawer
            if drawer:
                self.side_scroll.setParent(self.centralWidget())
                self.side_scroll.setObjectName('sideScroll')
                self.side_scroll.setProperty('drawer', True)
            else:
                self._drawer_open = False
                self.side_scroll.setProperty('drawer', False)
                self.splitter.insertWidget(2, self.side_scroll)
                self.splitter.setStretchFactor(0, 2)
                self.splitter.setStretchFactor(1, 5)
                self.splitter.setStretchFactor(2, 1)
                margins = self.root_layout.contentsMargins()
                total = self.width() - margins.left() - margins.right() - 2 * self.splitter.handleWidth()
                side = max(365, min(420, total // 4))
                # Même partage 2:5 que le réglage initial entre l'image et la page.
                art = min(300, (total - side) * 2 // 7) if self.scene_art.isVisibleTo(self) else 0
                self.splitter.setSizes([art, max(300, total - side - art), side])
            self.side_scroll.style().unpolish(self.side_scroll)
            self.side_scroll.style().polish(self.side_scroll)
        reading = self.reading_mode
        if reading:
            self._drawer_open = False
        focus = QApplication.focusWidget()
        hiding = ((reading and self.header_frame.isAncestorOf(focus))
                  or ((reading or (drawer and not self._drawer_open)) and self.side_scroll.isAncestorOf(focus)))
        if hiding:
            self.reader.setFocus()
        self.header_frame.setVisible(not reading)
        self.sheet_strip.setVisible(drawer and not reading)
        self.sheet_strip.setChecked(self._drawer_open)
        self.sheet_strip._refresh_tooltip()
        if drawer:
            self.side_scroll.setVisible(self._drawer_open)
            self.drawer_scrim.setVisible(self._drawer_open)
            if self._drawer_open:
                self._place_sheet_drawer()
                self.drawer_scrim.raise_()
                self.side_scroll.raise_()
        else:
            self.drawer_scrim.hide()
            self.side_scroll.setVisible(not reading)
        self.reading_exit_button.setVisible(reading)
        self.reading_action.setChecked(reading)
        self.escape_shortcut.setEnabled(reading or self._drawer_open)
        self.sheet_shortcut.setEnabled(drawer and not reading)

    def _place_sheet_drawer(self):
        """Le tiroir sort de la bande, à sa gauche, sur toute la hauteur de la page."""
        if not getattr(self, '_sheet_in_drawer', False):
            return
        strip = self.sheet_strip.geometry()
        page = self.splitter.geometry()
        width = min(self.DRAWER_WIDTH, max(365, page.width() - 60))
        self.side_scroll.setGeometry(strip.left() - width - 2, strip.top(), width, strip.height())
        self.drawer_scrim.setGeometry(page.left(), page.top(), strip.left() - page.left(), page.height())

    def toggle_sheet_drawer(self, open_=None):
        """Déplier ou replier la fiche en tiroir (petites largeurs uniquement)."""
        open_ = (not self._drawer_open) if open_ is None else bool(open_)
        if not self._sheet_in_drawer or self.reading_mode:
            open_ = False
        if open_ != self._drawer_open:
            self._drawer_open = open_
            self._apply_layout_mode()
            if not open_ and self.side_scroll.isAncestorOf(QApplication.focusWidget()):
                self.reader.setFocus()
        else:
            self.sheet_strip.setChecked(open_)

    def _close_sheet_drawer(self, *_args):
        if getattr(self, '_drawer_open', False):
            self.toggle_sheet_drawer(False)

    def _tab_sheet_drawer(self):
        """Tab hors d'un champ de saisie : ouvrir/fermer la fiche ; sinon champ suivant."""
        focus = QApplication.focusWidget()
        editable = (isinstance(focus, QLineEdit) or
                    (isinstance(focus, QAbstractSpinBox) and not focus.isReadOnly()) or
                    (isinstance(focus, (QTextEdit, QPlainTextEdit)) and not focus.isReadOnly()) or
                    (isinstance(focus, QComboBox) and focus.isEditable()))
        if editable:
            self.focusNextChild()
            return
        self.toggle_sheet_drawer()

    def toggle_reading_mode(self, on=None):
        """Mode lecture (F10) : bandeau et fiche masqués, seule la page reste."""
        self.reading_mode = (not self.reading_mode) if on is None else bool(on)
        self._apply_layout_mode()
        self._apply_sheet_density()

    def _escape_layout_mode(self):
        if self._drawer_open:
            self._close_sheet_drawer()
        elif self.reading_mode:
            self.toggle_reading_mode(False)
        elif self.isFullScreen():
            self.showNormal()
            self._update_fullscreen_button()

    def _fit_compact_bag(self):
        """Sacoche compacte : l'onglet prend juste la hauteur de sa rangée d'icônes."""
        if not hasattr(self, 'sheet_bottom_spacer'):
            return
        if self.inventory_list.compact:
            content = self.inventory_list.parentWidget()
            height = content.layout().sizeHint().height() if content and content.layout() else 80
            bar = self.adventure_tabs.tabBar()
            if bar.isVisible() or not self.adventure_tabs.isVisible():
                height += bar.sizeHint().height() if bar.count() > 1 else 0
            height += 14
            self.adventure_tabs.setMaximumHeight(height)
        else:
            self.adventure_tabs.setMaximumHeight(16777215)

    def _refresh_sheet_strip(self):
        if not hasattr(self, 'sheet_strip'):
            return
        initial = self.character.get('initial', {})
        values = {key: (int(self._ff_stat_value(key)), initial.get(key))
                  for key in ('habilete', 'endurance', 'chance')}
        self.sheet_strip.set_state(**values, gold=self.stat_spins['gold'].value(),
                                   provisions=self.stat_spins['provisions'].value())
        self.sheet_strip.set_alerts(self._stat_alerts())

    def _stat_alerts(self):
        """Caractéristiques en péril (≤ ALERT_THRESHOLD) dont l'écu doit pulser.

        Rien ne pulse sans aventure en cours, une fois le héros mort (Endurance à 0)
        ou l'aventure close : l'alerte prévient d'un danger, la fin est déjà annoncée.
        Habileté ou Chance à 0 chez un héros vivant restent en alerte."""
        if (getattr(self, 'current_paragraph', None) is None
                or int(self.character.get('endurance', 0)) <= 0
                or self.character.get('book_facts', {}).get('adventure_ended')):
            return frozenset()
        return frozenset(key for key in ('habilete', 'endurance', 'chance')
                         if int(self._ff_stat_value(key)) <= ALERT_THRESHOLD)

    COMPACT_SHEET_HEIGHT = 860

    def _apply_sheet_density(self):
        """Resserrer la fiche peinte sur les fenêtres basses pour éviter le défilement."""
        if not hasattr(self, 'sheet_seals'):
            return
        compact = self.height() < self.COMPACT_SHEET_HEIGHT
        for widget in (*self.stat_medallions.values(), *self.sheet_seals, self.hero_emblem):
            widget.set_compact(compact)
        # Sacoche en une rangée d'icônes et sceaux sans légende : fiche en tiroir ou fenêtre basse.
        small = self._sheet_in_drawer or self.height() < self.LOW_HEIGHT
        for seal in self.sheet_seals:
            seal.set_mini(small)
        self.inventory_list.set_compact(small)
        self.adventure_tabs.setSizePolicy(QSizePolicy.Expanding,
                                          QSizePolicy.Maximum if small else QSizePolicy.Ignored)
        self.adventure_tabs.setMinimumHeight(60 if small else 110)
        layout = self.side_panel.layout()
        layout.setStretchFactor(self.adventure_tabs, 0 if small else 1)
        self.sheet_bottom_spacer.setVisible(small)
        self._fit_compact_bag()
        self.purse_heading.setVisible(not compact)
        # Très petite hauteur : le titre des caractéristiques cède sa place aux sceaux.
        self.stats_heading.setVisible(self.height() >= self.TIGHT_SHEET_HEIGHT)
        self.side_panel.layout().setSpacing(4 if compact else 8)
        margins = (14, 10, 14, 10) if compact else (18, 18, 18, 18)
        self.side_panel.layout().setContentsMargins(*margins)
        # L'emblème compact reste hors du fleuron d'angle de la fiche.
        self.hero_row.setContentsMargins(26 if compact else 0, 4 if compact else 0, 0, 0)
        self._apply_page_density(compact)
        self._apply_tight_layout(self.height() < self.LOW_HEIGHT)

    TIGHT_SHEET_HEIGHT = 720

    def _apply_page_density(self, compact):
        """Resserrer marges, titre et choix de la page pour garder les choix visibles."""
        self.reader_layout.setContentsMargins(*((32, 18, 30, 16) if compact else (40, 26, 38, 26)))
        self.reader_layout.setSpacing(3 if compact else 6)
        self.paragraph_title.setStyleSheet("font-size: 23px;" if compact else "")
        for group, layout in ((self.choice_group, self.choice_layout), (self.event_group, self.event_layout),
                              (self.condition_group, self.condition_layout)):
            group.set_compact(compact)
            layout.setContentsMargins(0, group.header_height(), 0, 2 if compact else 4)
            layout.setSpacing(5 if compact else 8)
        ChoiceCard.compact = compact
        tight = self.height() < self.LOW_HEIGHT
        ChoiceCard.tight = tight
        for card in self._visible_choice_cards():
            card.set_compact(compact, tight)

    def _apply_tight_layout(self, tight):
        """Fenêtres basses (< 760 px) : bandeau fin, en-tête de page sur une ligne."""
        self.reader_panel.set_compact(tight)
        if tight:
            self.reader_layout.setContentsMargins(24, 16, 22, 12)
            self.reader_layout.setSpacing(2)
            self.paragraph_title.setStyleSheet("font-size: 21px;")
            self.reader.setMinimumHeight(140)
        else:
            self.reader.setMinimumHeight(230)
        if tight == self._tight_layout:
            return
        self._tight_layout = tight
        for button in (self.undo_btn, self.redo_btn, self.rules_button, self.map_button,
                       self.open_btn, self.settings_button):
            button.set_slim(tight)
        self.subtitle_label.setVisible(not tight)
        self.header_layout.setContentsMargins(*((18, 7, 26, 6) if tight else (22, 12, 30, 10)))
        self.root_layout.setContentsMargins(*((10, 6, 10, 8) if tight else (16, 12, 16, 12)))
        self.root_layout.setSpacing(6 if tight else 12)
        # Titre du paragraphe dans la rangée d'outils, à côté du cartouche.
        title = self.paragraph_title
        if tight == getattr(self, '_title_in_row', False):
            return
        self._title_in_row = tight
        if tight:
            self.reader_layout.removeWidget(title)
            self.title_row.insertWidget(self.title_row.indexOf(self.paragraph_number), title)
            self.title_row.insertSpacing(self.title_row.indexOf(self.paragraph_number), 8)
            title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            title.setMinimumWidth(110)
        else:
            index = self.title_row.indexOf(self.paragraph_number)
            spacer = self.title_row.takeAt(index - 1)
            del spacer
            self.title_row.removeWidget(title)
            self.reader_layout.insertWidget(0, title)
            title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            title.setMinimumWidth(0)

    def _update_scene_art(self, prefer_cover=False):
        """Choisir couverture, illustration courante ou décor de repli selon l’écran affiché."""
        # La couverture est réservée à l'introduction. Pendant la lecture, le
        # décor fourni remplit la surface sans devenir une illustration active.
        background_name = bifurk.BOOK_BACKGROUNDS.get(getattr(self.book_module, 'engine', ''),
                                               'illustration-background.jpg')
        background = None if prefer_cover else QPixmap(str(bifurk.ASSET_DIR / background_name))
        self.scene_art.set_background_art(background)
        self.scene_entry = None
        self.scene_title = ''
        if self.illustration_catalogue and self.pdf_path:
            entries = bifurk.images_for_paragraph(self.illustration_catalogue, self.current_paragraph)
            book_cover = cover(self.illustration_catalogue)
            entry = (book_cover if prefer_cover and book_cover else
                     entries[0] if entries else None)
            if entry:
                try:
                    self.scene_art.set_book_art(self._illustration_pixmap(entry, scale=1))
                    self.scene_entry = entry
                    self.scene_title = (f"Illustration — paragraphe {self.current_paragraph}"
                                        if entry is not book_cover else "Couverture du grimoire")
                    self.scene_art.setAccessibleName(self.scene_title)
                except (ValueError, RuntimeError, OSError):
                    # L’agrandissement reste disponible si l’aperçu ne peut être calculé.
                    pass

    def _enlarge_scene_art(self):
        """Ouvrir l’illustration sélectionnée dans une fenêtre indépendante."""
        if self.scene_entry is not None:
            self._show_illustration(self.scene_entry, self.scene_title)
