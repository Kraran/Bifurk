"""Apparence : thèmes, plein écran, barre de titre, polices et rendu du texte du livre.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

import adventurer_sheet
import html
import theme_palette

from grimoire_chrome import illuminated_initial, menu_icon
from grimoire_ui import GrimoireScene, IlluminatedPage
from navigation import render_links
from themes import set_active_theme

from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtGui import QFontDatabase, QTextDocument
from PySide6.QtWidgets import QApplication, QWidget

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class ApparenceMixin:
    """Apparence : thèmes, plein écran, barre de titre, polices et rendu du texte du livre."""

    AUTO_THEME = 'auto'

    def _ordered_themes(self):
        """Standard d'abord, puis les thèmes de livre dans l'ordre de la collection."""
        return sorted(self.themes.items(),
                      key=lambda item: (item[0] != 'grimoire', item[1].data.get('order', 99), item[1].name))

    def _theme_choices(self):
        """(clé, libellé) proposés dans Réglages : automatique puis chaque thème."""
        return [(self.AUTO_THEME, 'Selon le grimoire ouvert')] + [
            (key, theme.name) for key, theme in self._ordered_themes()]

    def _theme_choice(self):
        """Thème choisi explicitement, ou « auto » si aucun choix valide n'est mémorisé."""
        choice = self.preferences.get('theme')
        return choice if choice in self.themes else self.AUTO_THEME

    def _book_theme_id(self):
        """Thème associé au module du livre ouvert (« book » du manifeste), sinon Standard."""
        engine = getattr(self.book_module, 'engine', None)
        return next((key for key, theme in self.themes.items()
                     if engine and theme.data.get('book') == engine), 'grimoire')

    def _apply_book_theme(self, *, rerender=False):
        """Sans choix mémorisé, prendre le thème du livre ouvert (ouverture ou chargement)."""
        if self._theme_choice() != self.AUTO_THEME:
            return
        target = self._book_theme_id()
        if target != self.theme.id:
            self._activate_theme(target, rerender=rerender)

    def _refresh_menu_icons(self):
        """Repeindre les pictogrammes du menu Réglages dans l'or du thème affiché."""
        color = self.theme.color('gold')
        for action, kind in getattr(self, 'settings_icons', {}).items():
            action.setIcon(menu_icon(kind, color))

    def choose_theme(self, choice):
        """Choix de Réglages : « auto » efface la préférence, un thème la mémorise."""
        if choice == self.AUTO_THEME:
            if self.preferences.pop('theme', None) is not None:
                self._save_preferences()
            target = self._book_theme_id()
            if target != self.theme.id:
                self._activate_theme(target)
        elif choice in self.themes:
            self.apply_theme(choice)

    def apply_theme(self, theme_id):
        """Appliquer un thème choisi et le mémoriser : il prime alors sur celui de chaque livre."""
        self._activate_theme(theme_id)
        self.preferences["theme"] = theme_id
        self._save_preferences()

    def _activate_theme(self, theme_id, *, rerender=True):
        """Afficher un thème sans rien mémoriser ni modifier la progression.

        rerender=False laisse l'appelant (ouverture, chargement) redessiner la page."""
        self.theme = self.themes[theme_id]
        theme_palette.configure(self.theme.recolor, self.theme.assets)
        set_active_theme(self.theme)
        fonts = self.theme.data.get("fonts", {})
        self.reading_font_family = fonts.get("reading", self._default_fonts[0])
        self.ui_font_family = fonts.get("ui", self._default_fonts[1])
        adventurer_sheet.FONTS.update(title=self.reading_font_family, ui=self.ui_font_family)
        self._set_theme()
        for page in self.findChildren(IlluminatedPage):
            page.set_theme(self.theme)
        for scene in self.findChildren(GrimoireScene):
            scene.set_theme(self.theme)
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'restyle_theme'):
                widget.restyle_theme()
        self._refresh_character()
        self._refresh_menu_icons()
        bifurk.refresh_native_titlebars(self.theme)
        if rerender:
            if self.current_paragraph is not None and self.character['endurance'] <= 0:
                self._show_death_page()
            elif self.current_paragraph in self.paragraphs:
                self._render_paragraph_text(self.paragraphs[self.current_paragraph])
            elif self.pdf_path and self.paragraphs:
                self._show_book_title()
            else:
                self._show_welcome()
        # Couleurs peintes (cuir, sceaux, cartes) : tout redessiner.
        for widget in self.findChildren(QWidget):
            widget.update()

    def toggle_fullscreen(self):
        """Basculer entre plein écran immersif et fenêtre normale."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._update_fullscreen_button()

    def _update_fullscreen_button(self):
        """Synchroniser le libellé du bouton avec l’état plein écran réel de Qt."""
        self._fullscreen = self.isFullScreen()
        if hasattr(self, "fullscreen_btn"):
            self.fullscreen_btn.setText("▣  Quitter plein écran" if self._fullscreen else "⛶  Plein écran")
        if hasattr(self, "fullscreen_action"):
            self.fullscreen_action.setText("Quitter le plein écran\tF11" if self._fullscreen else "Plein écran\tF11")

    def keyPressEvent(self, event):
        """Traiter les raccourcis de fenêtre puis déléguer les autres touches à Qt."""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self._update_fullscreen_button()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        """Réagir aux changements d’état de fenêtre pour garder les contrôles cohérents."""
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._update_fullscreen_button()
            # Sortie du plein écran : la barre réapparaît, la redemander au thème.
            if not self.isFullScreen():
                self._set_windows_titlebar_color()

    def showEvent(self, event):
        """Appliquer les ajustements natifs une fois la fenêtre effectivement créée."""
        self._closing = False  # fenêtre réaffichée après une fermeture : de nouveau active
        if self._quit_fade_state == 'done':  # Réaffichée après un fondu de fermeture.
            self._quit_fade_state = None
            self.setWindowOpacity(1.0)
            self.centralWidget().setEnabled(True)
            mixer = getattr(self.sounds, '_pcm_mixer', None)
            if mixer is not None:
                mixer.gain = 1.0
        super().showEvent(event)
        self._set_windows_titlebar_color()

    def _set_windows_titlebar_color(self):
        """Appliquer la teinte native du thème au handle Windows de la fenêtre principale."""
        bifurk.set_native_titlebar(self, getattr(self, 'theme', None))

    def _load_fonts(self):
        """Charge les polices embarquées, sans dépendre des polices système."""
        self.reading_font_family = "EB Garamond"
        self.ui_font_family = "Lato"
        for filename in ("EBGaramond12-Regular.ttf", "EBGaramond12-Italic.ttf",
                         "Lato-Regular.ttf", "Lato-Bold.ttf"):
            font_path = bifurk.ASSET_DIR / "fonts" / filename
            if font_path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id >= 0:
                    family = QFontDatabase.applicationFontFamilies(font_id)
                    if family:
                        if filename.startswith("EBGaramond"):
                            self.reading_font_family = family[0]
                        else:
                            self.ui_font_family = family[0]

    DEFAULT_READER_FONT_SIZE = 20

    def _auto_reader_font_size(self):
        """Taille de lecture par défaut selon la hauteur de fenêtre (petits écrans)."""
        height = self.height()
        if height < 690:
            return 16
        if height < self.LOW_HEIGHT:
            return 17
        return self.DEFAULT_READER_FONT_SIZE

    def _apply_auto_font_size(self):
        """Suivre la taille automatique tant que le joueur n'a pas choisi la sienne."""
        if self._user_font_size is not None:
            return
        size = self._auto_reader_font_size()
        if size != self.reader_font_size:
            self.reader_font_size = size
            self._rerender_reader()

    def change_reader_font_size(self, delta):
        """Ajuster la taille de lecture puis redessiner le texte sans rejouer les événements."""
        self.reader_font_size = max(14, min(34, self.reader_font_size + delta))
        self._user_font_size = self.reader_font_size
        self._rerender_reader()

    def _rerender_reader(self):
        """Redessiner la page courante à la taille de lecture courante."""
        if not hasattr(self, 'reader'):
            return
        if self.current_paragraph is not None and self.character['endurance'] <= 0:
            self._show_death_page()
        elif self.current_paragraph in self.paragraphs:
            scroll_position = self.reader.verticalScrollBar().value()
            self._render_paragraph_text(self.paragraphs[self.current_paragraph])
            self.reader.verticalScrollBar().setValue(scroll_position)
        else:
            if self.pdf_path and self.paragraphs:
                self._show_book_title()
            else:
                self._show_welcome()
        self.font_size_label.setText(f"{self.reader_font_size} pt")

    def _render_paragraph_text(self, text):
        """Composer le HTML de lecture avec liens échappés et police courante.

        Ne pas rétablir line-height sur le div : Qt ne l’applique qu’au premier bloc,
        ce qui crée un espacement anormal après la première ligne (test dédié)."""
        lead = self._drop_cap(text)
        if lead:
            text = text.lstrip()[1:]
        escaped = render_links(text, self._reading_link_targets(), link_color=self.theme.color("link"))
        # Liens bleu nuit soulignés : contraste élevé sur le parchemin clair.
        content = (f'<div style="font-family: \'{self.reading_font_family}\'; '
                   f'font-size: {self.reader_font_size}pt; color: {self.theme.color("ink")};">'
                   f'<p>{lead}{escaped}</p></div>')
        self.reader.setHtml(content)

    DROP_CAP_MIN_LENGTH = 120

    def _drop_cap(self, text):
        """Lettrine enluminée flottante pour un récit commençant par une lettre.

        L'image est une ressource du document (bifurk-initial:<code>-<px>) : ReaderBrowser
        relit la lettre dans ce nom à la copie (Qt ignore alt), et les textes courts
        restent sobres."""
        stripped = text.lstrip()
        if len(stripped) < self.DROP_CAP_MIN_LENGTH or not stripped[0].isalpha():
            return ''
        letter = stripped[0]
        px = round(self.reader_font_size * 1.333 * 2.05)
        image = illuminated_initial(letter.upper(), px)
        url = QUrl(f'{bifurk.DROP_CAP_SCHEME}:{ord(letter)}-{px}')
        self.reader.document().addResource(QTextDocument.ImageResource, url, image)
        width = round(image.width() / image.devicePixelRatio())
        height = round(image.height() / image.devicePixelRatio())
        return (f'<img src="{url.toString()}" alt="{html.escape(letter)}" width="{width}" '
                f'height="{height}" style="float: left; margin-right: 8px;">')

    def _set_theme(self):
        """Distribuer le QSS, les polices et les surfaces dessinées aux widgets existants."""
        css = self.theme.stylesheet(self.reading_font_family, self.ui_font_family)
        self.setStyleSheet(css)
        app = QApplication.instance()
        if app is not None and app.styleSheet():
            app.setStyleSheet(css)  # Dialogues et messages suivent le thème affiché.
