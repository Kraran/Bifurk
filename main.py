"""Point d'entrée Qt et orchestration de l'aventure Bifurk.

MainWindow relie les vues, l'état sérialisable, le PDF privé et les règles du
catalogue. Les calculs réutilisables restent dans book_events ; ModuleActions
délègue les règles particulières au contrôleur du grimoire ouvert. Une action utilisateur
peut appeler plusieurs méthodes : _track_action les regroupe dans une seule
transaction d'historique. _restoring interdit de rejouer les effets à la restauration.

Les chemins portables dérivent du script ou de l'exécutable, jamais du répertoire
courant du terminal. Voir docs/maintenance.md avant de modifier les sauvegardes,
la navigation ou le cycle création / partie / mort."""
import sys, re, json, random, copy, os, tempfile, hashlib, shutil
from pathlib import Path
from navigation import destinations, render_links
from illustrations import images_for_paragraph, cover
from grimoire_modules.controller import ModuleActions
from grimoire_modules.registry import module_for_pdf
from rules_viewer import RulesDialog
from themes import available_themes
from sound_effects import SoundBank, EFFECT_LABELS
from intro_music import IntroMusic
from audio_configuration import configure_audio_backend
from save_slots import SaveSlotsDialog, read_save
from datetime import datetime
from app_info import APP_NAME, APP_VERSION
from about_dialog import AboutDialog, BrandButton
from dice_dialog import DiceDialog
from combat_dialog import CombatDialog
from dialog_chrome import DialogHeading, harmonize_standard_dialog
from stat_feedback import StatFeedback
from grimoire_ui import GrimoireScene, inventory_icon, ChoiceCard, IlluminatedPage, IllustrationDialog, SingleLineTitle, theme_message_box
from book_events import apply_option, verified_entry, apply_effects, resolve_roll, available_routes, equipped_weapon, equip_weapon, combat_skill, SHIELD_NAME, follow_catalogue_route
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, QSize, QTranslator, QLibraryInfo, QLocale
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor, QPixmap, QImage, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTextBrowser, QSpinBox,
    QGroupBox, QSlider, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QCheckBox, QSplitter, QComboBox, QDialog, QDialogButtonBox, QScrollArea, QFrame, QProgressBar, QTabWidget, QSizePolicy, QMenu)

# Répertoire portable : à côté de l'exécutable empaqueté ou du script.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
# PyInstaller place le code et les ressources dans _internal, mais les données
# portables restent à côté de Bifurk.exe. __file__ fonctionne aussi en mode source.
RESOURCE_DIR = Path(__file__).resolve().parent
ASSET_DIR = RESOURCE_DIR / "assets"
DATA_DIR = APP_DIR / "donnees"
SAVES_DIR = DATA_DIR / "sauvegardes"
BOOKS_DIR = DATA_DIR / "grimoires"
SETTINGS_DIR = DATA_DIR / "parametres"


def init_portable_dirs():
    """Créer les dossiers de données portables avant toute importation ou écriture."""
    for directory in (SAVES_DIR, BOOKS_DIR, SETTINGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def within_directory(path, directory):
    """Vérifier l’appartenance après résolution des chemins et liens symboliques.

    relative_to évite les faux préfixes de chemins voisins ; renvoie False hors dossier."""
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False


def import_book(source):
    """Importer un PDF par copie temporaire puis remplacement dans grimoires.

    La source reste intacte. Le nom combine son libellé et une empreinte de contenu
    pour distinguer les éditions ; un livre déjà importé n’est pas recopié."""
    source = Path(source).resolve()
    if not source.is_file() or source.suffix.lower() != '.pdf':
        raise ValueError("Sélectionnez un fichier PDF valide.")
    if within_directory(source, BOOKS_DIR):
        return str(source)
    digest = hashlib.sha256()
    with source.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    target = BOOKS_DIR / f"{source.stem[:75]}_{digest.hexdigest()[:12]}.pdf"
    if not target.exists():
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=BOOKS_DIR, suffix='.tmp', delete=False) as handle:
                temp = Path(handle.name)
                with source.open('rb') as original:
                    shutil.copyfileobj(original, handle)
            os.replace(temp, target)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
    return str(target)


def resolve_book_reference(reference):
    """Résoudre uniquement une référence relative vers un grimoire importé existant.

    Refuser les chemins absolus et les sorties du dossier grimoires ; ne pas chercher
    un ancien fichier ailleurs ni importer implicitement un livre pendant le chargement."""
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        return None
    candidate = (APP_DIR / reference).resolve()
    return str(candidate) if within_directory(candidate, BOOKS_DIR) and candidate.is_file() else None



def extract_paragraphs(pdf_path):
    """Extraire les sections numérotées d’un PDF textuel, sans OCR.

    Le tri PyMuPDF et la suppression des césures facilitent la lecture. Un numéro
    isolé après « rendez-vous au » reste une destination, pas un nouveau titre.
    Le dictionnaire retourné associe numéro entier et texte non vide."""
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF n'est pas installé. Lancez : pip install PyMuPDF") from exc
    with pymupdf.open(pdf_path) as doc:
        text = "\n".join(page.get_text("text", sort=True) for page in doc)
    # Normalize common PDF line-break artifacts while preserving paragraph boundaries.
    text = text.replace("\u00ad", "")
    lines = [line.strip() for line in text.splitlines()]
    paragraphs = {}
    current = None
    buffer = []
    for line in lines:
        if re.fullmatch(r"\d{1,3}", line) and buffer and re.search(r"(?i)(?:rendez[- ]?vous|allez|rendre|aller)\s+(?:alors\s+)?au\s*$", buffer[-1]):
            # A PDF line break can isolate a destination number; it is not a section heading.
            buffer.append(line)
        elif re.fullmatch(r"\d{1,3}", line):
            number = int(line)
            # Avoid treating page numbers as paragraph starts: only start a section
            if 1 <= number <= 999 and (current is None or buffer):
                if current is not None:
                    paragraphs[current] = "\n".join(buffer).strip()
                current, buffer = number, []
        elif current is not None and line:
            buffer.append(line)
    if current is not None:
        paragraphs[current] = "\n".join(buffer).strip()
    # Ne corriger le défaut éditorial que pour le PDF exact déjà catalogué.
    module = module_for_pdf(pdf_path)
    if module is not None:
        module.repair_paragraphs(paragraphs)
    # Drop empty sections and likely front matter sections without content.
    return {n: t for n, t in paragraphs.items() if t}


def franciser_message(dialog):
    """Traduire les boutons usuels d’une QMessageBox en complément des catalogues Qt."""
    noms = {
        QMessageBox.Yes: "Oui", QMessageBox.No: "Non",
        QMessageBox.Ok: "OK", QMessageBox.Cancel: "Annuler",
        QMessageBox.Save: "Enregistrer", QMessageBox.Open: "Ouvrir",
        QMessageBox.Close: "Fermer", QMessageBox.Retry: "Réessayer",
        QMessageBox.Discard: "Ignorer", QMessageBox.Abort: "Abandonner",
    }
    for button_type, label in noms.items():
        button = dialog.button(button_type)
        if button is not None and button.text().strip().lower() in {
            "&yes", "yes", "&no", "no", "&ok", "ok", "cancel", "&cancel",
            "&save", "save", "&open", "open", "&close", "close",
            "retry", "&retry", "discard", "&discard", "abort", "&abort",
        }:
            button.setText(label)


def franciser_selecteur(dialog):
    """Appliquer les libellés français de secours au sélecteur Qt non natif."""
    from PySide6.QtWidgets import QToolButton, QAbstractButton
    tooltips = {
        "Back": "Dossier précédent", "Forward": "Dossier suivant",
        "Parent Directory": "Dossier parent", "Go to parent directory": "Dossier parent",
        "Create New Folder": "Créer un dossier", "New Folder": "Créer un dossier",
        "List View": "Affichage en liste", "Detail View": "Affichage détaillé",
        "Show Hidden Files": "Afficher les fichiers cachés",
        "Go Back": "Retour", "Go Forward": "Suivant",
        "Look in": "Regarder dans", "File name": "Nom du fichier",
        "Files of type": "Type de fichier", "Open": "Ouvrir", "Save": "Enregistrer",
        "Cancel": "Annuler", "Computer": "Ordinateur", "Home": "Dossier personnel",
        "Recent Places": "Emplacements récents", "Desktop": "Bureau",
    }
    for widget in dialog.findChildren(QAbstractButton):
        if widget.text() in tooltips:
            widget.setText(tooltips[widget.text()])
        tip = widget.toolTip()
        if tip in tooltips:
            widget.setToolTip(tooltips[tip])
        accessible = widget.accessibleName()
        if accessible in tooltips:
            widget.setAccessibleName(tooltips[accessible])


class DialogThemeFilter(QObject):
    """Habiller les fenêtres secondaires et remplacer leurs pictogrammes système."""
    def eventFilter(self, obj, event):
        """Habiller à l'affichage et différer la barre native, sans consommer l'événement."""
        if event.type() == QEvent.Show and isinstance(obj, QDialog):
            harmonize_standard_dialog(obj)
            if isinstance(obj, QMessageBox):
                # Avant la première peinture : aucun flash de l'icône bleue
                # native, même pour les appels statiques information/question.
                theme_message_box(obj)
            # Une minuterie enfant disparaît avec la fenêtre : une fermeture
            # immédiate ne doit jamais rappeler un objet C++ déjà détruit.
            deferred = QTimer(obj)
            deferred.setSingleShot(True)
            def finish_dialog():
                if obj.isVisible():
                    set_bronze_titlebar(obj)
                    if isinstance(obj, QMessageBox):
                        franciser_message(obj)
                deferred.deleteLater()
            deferred.timeout.connect(finish_dialog)
            deferred.start(0)
        return False


def set_bronze_titlebar(widget):
    """Teinter la barre native avec DWM sous Windows ; ignorer les plateformes non prises en charge."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        for attribute, value in ((35, 0x001B2D4B), (36, 0x00BEE1F2)):
            # Attributs DWM : 35 = fond du titre, 36 = couleur du texte.
            # Windows attend un COLORREF (0x00BBGGRR), pas une couleur CSS RGB.
            color = ctypes.c_uint32(value)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(color), ctypes.sizeof(color))
    except Exception:
        pass


class MainWindow(QMainWindow, ModuleActions):
    """Contrôleur principal et propriétaire Qt des vues et services de l’aventure.

    État durable : character, progression, rencontres et instantanés d’historique.
    État temporaire : brouillon de création, widgets, PDF extrait et rendu du thème.
    Le contrôleur du module utilise ce même état ; il ne crée pas un second moteur indépendant."""
    def __init__(self, startup=False):
        """Initialiser état, préférences, services et widgets avant le parcours de démarrage.

        startup=False permet aux tests de construire une fenêtre sans dialogue modal.
        En production, le menu initial est différé pour laisser Qt afficher la fenêtre."""
        super().__init__()
        self.preferences_path = SETTINGS_DIR / "preferences.json"
        try:
            self.preferences = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            if not isinstance(self.preferences, dict):
                self.preferences = {}
        except (OSError, ValueError):
            self.preferences = {}
        self.themes = available_themes(ASSET_DIR / "themes")
        self.theme = self.themes.get(self.preferences.get("theme"), self.themes["grimoire"])
        configure_audio_backend()
        self.sounds = SoundBank(ASSET_DIR / "sounds", self.preferences.get("sound_enabled", True), self,
                            ambient_enabled=self.preferences.get("ambient_enabled", False),
                            diagnostic_path=SETTINGS_DIR / "audio.log")
        self.intro_music = IntroMusic(ASSET_DIR / 'sounds' / 'FantasyFair.m4a',
                                      self.preferences.get('music_enabled', True), self,
                                      volume_percent=self.preferences.get('music_volume', 70))
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(ASSET_DIR / "bifurk.ico")))
        self._fullscreen = False
        self.resize(1600, 900)
        self.setMinimumSize(930, 650)
        self.pdf_path = None
        self.book_module = None
        self.illustration_catalogue = None
        self.book_event_catalogue = None
        # Ces trois ensembles répondent à des questions différentes : effet déjà
        # reçu, option déjà choisie, adversaire déjà préparé. Les fusionner ferait
        # réapparaître du butin ou réinitialiserait des combats lors des retours.
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.encounter_history = {}
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self._combat_dialog = None  # Uniquement pendant l'exécution modale.
        self._combat_popup = None   # Chronique conservée si le combat est suspendu.
        self.paragraphs = {}
        self.current_paragraph = None
        self.visited_paragraphs = []
        self.transitions = []
        # Gabarit d'équipement et valeurs d'affichage hors partie. Les valeurs
        # H/E/C d'une nouvelle aventure sont remplacées par le tirage réglementaire.
        self.character = {
            "habilete": 8, "endurance": 20, "chance": 8,
            "provisions": 10, "gold": 1, "inventory": ["Épée", "Armure de cuir", "Lanterne"],
            "locked_items": [],
            "potion": "Aucune", "potion_doses": 0,
            "initial": {"habilete": 8, "endurance": 20, "chance": 8}
        }
        self._initial_character = copy.deepcopy(self.character)
        # Le brouillon appartient à l'introduction ; il ne doit pas être régénéré
        # quand on change le thème ou la taille des caractères.
        self._adventurer_draft = None
        self._creation_rerolls = 0
        self._creation_name = ''
        self.undo_stack = []
        self.redo_stack = []
        self.action_history = []
        self._restoring = False
        self._feedback_action_id = 0  # Identifiant visuel, hors sauvegardes et règles.
        self.reader_font_size = 20
        self._load_fonts()
        self._default_fonts = (self.reading_font_family, self.ui_font_family)
        self.reading_font_family = self.theme.data.get("fonts", {}).get("reading", self.reading_font_family)
        self.ui_font_family = self.theme.data.get("fonts", {}).get("ui", self.ui_font_family)
        self._build_ui()
        self.stat_feedback = StatFeedback(self, {key: (bar, None) for key, bar in self.stat_bars.items()},
                                          lambda: self.theme)
        self._set_theme()
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self._refresh_character()
        self._show_welcome()
        if startup:
            QTimer.singleShot(0, self._show_startup_menu)

    def _save_preferences(self):
        """Enregistrer les choix d’interface séparément de l’état des sauvegardes."""
        try:
            self._write_atomic(self.preferences_path, self.preferences)
        except OSError:
            self.rules_log.setText("Les préférences n’ont pas pu être enregistrées.")

    def _remember_book(self):
        """Mémoriser le grimoire importé pour les prochaines nouvelles parties."""
        if self.pdf_path and within_directory(self.pdf_path, BOOKS_DIR):
            self.preferences["last_book"] = str(Path(self.pdf_path).resolve().relative_to(BOOKS_DIR.resolve()))
            self._save_preferences()

    def _show_startup_menu(self):
        """Proposer les cinq emplacements ou une nouvelle aventure ; ne pas charger l’autosave."""
        self.intro_music.menu()
        while True:
            dialog = SaveSlotsDialog(SAVES_DIR, False, self, startup=True)
            accepted = dialog.exec() == QDialog.Accepted
            selected, new_game = dialog.selected_path, dialog.new_game_requested
            dialog.deleteLater()
            if not accepted:
                return
            if new_game:
                self._start_new_game()
                return
            if selected and self.load_game(selected):
                return

    def _start_new_game(self):
        """Reprendre le livre chargé, sinon le dernier importé, sinon demander un PDF.

        Cette étape ouvre la création ; les statistiques seront validées avant le §1."""
        if self.pdf_path and self.paragraphs:
            self._restart_adventure()
            return
        reference = self.preferences.get('last_book')
        path = (BOOKS_DIR / reference).resolve() if isinstance(reference, str) else None
        if path and within_directory(path, BOOKS_DIR) and path.is_file():
            self.open_pdf(path, startup=True)
        else:
            self.open_pdf()

    def show_ambience(self):
        """Construire les réglages de thème et sons, avec préécoute des effets disponibles."""
        dialog = QDialog(self)
        dialog.setObjectName('ambienceDialog')
        dialog.setWindowTitle("Bifurk — Ambiance")
        dialog.setWindowIcon(self.windowIcon())
        area = dialog.screen().availableGeometry()
        dialog.resize(min(620, area.width() - 60), min(540, area.height() - 80))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHeading('L’ambiance de votre aventure',
                                        'Musique, sons et habillage du grimoire.'))
        audio_group = QGroupBox('Le paysage sonore')
        audio_layout = QVBoxLayout(audio_group)
        audio_layout.setSpacing(14)
        layout.addWidget(audio_group)
        sound = QCheckBox("Activer les effets sonores")
        sound.setChecked(self.sounds.enabled)
        def set_sound(enabled):
            """Appliquer et mémoriser l’interrupteur des effets ponctuels."""
            self.sounds.set_enabled(enabled)
            self.preferences["sound_enabled"] = enabled
            self._save_preferences()
        sound.toggled.connect(set_sound)
        audio_layout.addWidget(sound)
        ambient = QCheckBox("Ambiance de fond : caverne")
        ambient.setChecked(self.sounds.ambient_enabled)
        def set_ambient(enabled):
            """Appliquer et mémoriser l’interrupteur indépendant de l’ambiance."""
            self.sounds.set_ambient_enabled(enabled)
            self.preferences["ambient_enabled"] = enabled
            self._save_preferences()
        ambient.toggled.connect(set_ambient)
        audio_layout.addWidget(ambient)
        music_row = QHBoxLayout()
        music_row.addWidget(QLabel('Musique d’accueil'))
        music = QSlider(Qt.Horizontal)
        music.setObjectName('musicVolume')
        music.setAccessibleName('Volume de la musique d’accueil')
        music.setRange(0, 100)
        music.setSingleStep(5)
        music.setPageStep(10)
        music.setTickPosition(QSlider.TicksBelow)
        music.setTickInterval(10)
        music.setMinimumWidth(220)
        # Rail de bois sombre, filet de laiton et poignée carrée : un curseur
        # rétro lisible, également utilisable au clavier (flèches, Début, Fin).
        music.setValue(self.intro_music.volume_percent)
        music_value = QLabel()
        music_value.setObjectName('musicVolumeValue')
        music_value.setMinimumWidth(70)
        def set_music_volume(percent):
            """Conserver le réglage même à zéro, indépendamment des autres canaux audio."""
            self.intro_music.set_volume(percent)
            music_value.setText(f'{percent} %' if percent else 'Muet')
            self.preferences['music_volume'] = percent
            self.preferences['music_enabled'] = percent > 0
            self._save_preferences()
        music_value.setText(f'{music.value()} %' if music.value() else 'Muet')
        music.valueChanged.connect(set_music_volume)
        music_row.addWidget(music, 1)
        music_row.addWidget(music_value)
        audio_layout.addLayout(music_row)
        preview = QHBoxLayout()
        effects = QComboBox()
        for name, label in EFFECT_LABELS.items():
            effects.addItem(label, name)
        listen = QPushButton("Écouter")
        listen.setEnabled(self.sounds.enabled)
        sound.toggled.connect(listen.setEnabled)
        listen.clicked.connect(lambda: self.sounds.play(effects.currentData()))
        preview.addWidget(effects, 1)
        preview.addWidget(listen)
        audio_layout.addLayout(preview)
        theme_group = QGroupBox('L’habillage du grimoire')
        theme_layout = QVBoxLayout(theme_group)
        layout.addWidget(theme_group)
        themes = QComboBox()
        for key, theme in self.themes.items():
            themes.addItem(theme.name, key)
        themes.setCurrentIndex(themes.findData(self.theme.id))
        themes.currentIndexChanged.connect(lambda index: self.apply_theme(themes.itemData(index)))
        theme_layout.addWidget(themes)
        layout.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText('Fermer')
        close.button(QDialogButtonBox.Close).setProperty('dialogAction', 'primary')
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def apply_theme(self, theme_id):
        """Appliquer un thème disponible et mémoriser ce choix sans modifier la progression."""
        self.theme = self.themes[theme_id]
        fonts = self.theme.data.get("fonts", {})
        self.reading_font_family = fonts.get("reading", self._default_fonts[0])
        self.ui_font_family = fonts.get("ui", self._default_fonts[1])
        self._set_theme()
        for page in self.findChildren(IlluminatedPage):
            page.set_theme(self.theme)
        for scene in self.findChildren(GrimoireScene):
            scene.set_theme(self.theme)
        self._refresh_character()
        if self.current_paragraph is not None and self.character['endurance'] <= 0:
            self._show_death_page()
        elif self.current_paragraph in self.paragraphs:
            self._render_paragraph_text(self.paragraphs[self.current_paragraph])
        elif self.pdf_path and self.paragraphs:
            self._show_book_title()
        else:
            self._show_welcome()
        self.preferences["theme"] = theme_id
        self._save_preferences()

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

    def showEvent(self, event):
        """Appliquer les ajustements natifs une fois la fenêtre effectivement créée."""
        super().showEvent(event)
        self._set_windows_titlebar_color()

    def _set_windows_titlebar_color(self):
        """Appliquer la teinte native au handle Windows de la fenêtre principale."""
        set_bronze_titlebar(self)

    def _load_fonts(self):
        """Charge les polices embarquées, sans dépendre des polices système."""
        self.reading_font_family = "EB Garamond"
        self.ui_font_family = "Lato"
        for filename in ("EBGaramond12-Regular.ttf", "EBGaramond12-Italic.ttf",
                         "Lato-Regular.ttf", "Lato-Bold.ttf"):
            font_path = ASSET_DIR / "fonts" / filename
            if font_path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id >= 0:
                    family = QFontDatabase.applicationFontFamilies(font_id)
                    if family:
                        if filename.startswith("EBGaramond"):
                            self.reading_font_family = family[0]
                        else:
                            self.ui_font_family = family[0]

    def change_reader_font_size(self, delta):
        """Ajuster la taille de lecture puis redessiner le texte sans rejouer les événements."""
        self.reader_font_size = max(14, min(34, self.reader_font_size + delta))
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
        escaped = render_links(text, self.paragraphs).replace("#123f70", self.theme.color("link"))
        # Liens bleu nuit soulignés : contraste élevé sur le parchemin clair.
        content = (f'<div style="font-family: \'{self.reading_font_family}\'; '
                   f'font-size: {self.reader_font_size}pt; color: {self.theme.color("ink")};">'
                   f'<p>{escaped}</p></div>')
        self.reader.setHtml(content)

    def _build_ui(self):
        """Assembler les trois zones : illustration, lecture et panneau d’aventure.

        Conserver les widgets en attributs pour les rafraîchissements ; les connexions
        Qt appellent les actions du contrôleur, pas des mutations d’état cachées dans la vue."""
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        header_frame = QFrame()
        header_frame.setObjectName("grimoireHeader")
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(16, 8, 16, 8)
        self.about_button = BrandButton()
        self.about_button.setObjectName('aboutBrand')
        self.about_button.setCursor(Qt.PointingHandCursor)
        self.about_button.setAccessibleName('Bifurk — Chroniques d’aventure — À propos')
        self.about_button.setToolTip('À propos de Bifurk')
        self.about_button.clicked.connect(self.show_about)
        brand = QHBoxLayout(self.about_button)
        brand.setContentsMargins(4, 0, 4, 0)
        brand.setSpacing(10)
        title = QLabel("⚜  B I F U R K")
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        brand.addWidget(title)
        subtitle = QLabel("CHRONIQUES D’AVENTURE")
        subtitle.setObjectName("subtitle")
        subtitle.setAttribute(Qt.WA_TransparentForMouseEvents)
        brand.addWidget(subtitle)
        header.addWidget(self.about_button)
        header.addStretch()
        self.book_label = QLabel("Aucun livre chargé")
        self.book_label.setObjectName("bookName")
        self.book_label.setMaximumWidth(240)
        self.book_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        header.addWidget(self.book_label)
        self.open_btn = QPushButton("✦  Ouvrir un grimoire…")
        self.open_btn.setObjectName("goldButton")
        self.open_btn.clicked.connect(self.open_pdf)
        header.addWidget(self.open_btn)
        self.fullscreen_btn = QPushButton("⛶  Plein écran")
        self.fullscreen_btn.setToolTip("Plein écran (F11) — Échap pour quitter")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        header.addWidget(self.fullscreen_btn)
        root.addWidget(header_frame)
        history_bar = QHBoxLayout()
        self.undo_btn = QPushButton("↶ Annuler")
        self.redo_btn = QPushButton("↷ Rétablir")
        self.undo_btn.clicked.connect(self.undo_action)
        self.redo_btn.clicked.connect(self.redo_action)
        history_bar.addWidget(self.undo_btn)
        history_bar.addWidget(self.redo_btn)
        self.history_label = QLabel("Historique : 0 action")
        history_bar.addWidget(self.history_label)
        history_bar.addStretch()
        ambience = QPushButton("♫ Ambiance")
        ambience.clicked.connect(self.show_ambience)
        history_bar.addWidget(ambience)
        map_btn = QPushButton("🗺 Carte d’exploration")
        map_btn.clicked.connect(self.show_map)
        self.rules_button = QPushButton("📖 Règles")
        self.rules_button.setToolTip("Lire les règles du grimoire (F1)")
        self.rules_button.clicked.connect(self.show_rules)
        history_bar.addWidget(self.rules_button)
        history_bar.addWidget(map_btn)
        QShortcut(QKeySequence("F1"), self, activated=self.show_rules)
        root.addLayout(history_bar)
        self._update_history_controls()

        splitter = QSplitter(Qt.Horizontal)
        reader_panel = IlluminatedPage(self.theme.assets["parchment"], theme=self.theme)
        reader_panel.setObjectName("readerPanel")
        reader_layout = QVBoxLayout(reader_panel)
        reader_layout.setContentsMargins(18, 20, 18, 20)
        reader_layout.setSpacing(8)
        self.scene_art = GrimoireScene(self.theme.assets["scene"], theme=self.theme)
        self.scene_entry = None
        self.scene_title = ""
        self.scene_art.activated.connect(self._enlarge_scene_art)
        splitter.addWidget(self.scene_art)
        reader_panel.setMinimumWidth(0)
        self.art_toggle = QPushButton("◈  Image")
        self.art_toggle.setCheckable(True)
        self.art_toggle.setChecked(True)
        self.art_toggle.setToolTip("Afficher ou masquer l’image pour agrandir la zone de lecture")
        self.art_toggle.toggled.connect(self._toggle_scene_art)
        self.paragraph_title = SingleLineTitle("Bienvenue")
        self.paragraph_title.setObjectName("sectionTitle")
        self.paragraph_title.setTextFormat(Qt.PlainText)
        self.paragraph_title.setAlignment(Qt.AlignCenter)
        self.paragraph_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        reader_layout.addWidget(self.paragraph_title)
        self.paragraph_number = QLabel()
        self.paragraph_number.setObjectName('paragraphNumber')
        self.paragraph_number.setAlignment(Qt.AlignCenter)
        reader_layout.addWidget(self.paragraph_number)
        self.paragraph_number.hide()
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addStretch()
        title_row.addWidget(self.art_toggle)
        minus_btn = QPushButton("A−")
        minus_btn.setToolTip("Réduire la taille du texte")
        minus_btn.clicked.connect(lambda: self.change_reader_font_size(-2))
        title_row.addWidget(minus_btn)
        self.font_size_label = QLabel(f"{self.reader_font_size} pt")
        title_row.addWidget(self.font_size_label)
        plus_btn = QPushButton("A+")
        plus_btn.setToolTip("Agrandir la taille du texte")
        plus_btn.clicked.connect(lambda: self.change_reader_font_size(2))
        title_row.addWidget(plus_btn)
        reader_layout.addLayout(title_row)
        cover_button = QPushButton("◈")
        cover_button.setToolTip("Voir la couverture du livre")
        cover_button.setAccessibleName("Voir la couverture")
        cover_button.clicked.connect(self.show_cover)
        title_row.insertWidget(1, cover_button)
        self.reader = QTextBrowser()
        # Les liens paragraph:NNN sont gérés par follow_link, jamais par QTextBrowser.
        self.reader.setOpenLinks(False)
        self.reader.setOpenExternalLinks(False)
        self.reader.anchorClicked.connect(self.follow_link)
        self.reader.setObjectName("reader")
        self.reader.setMinimumHeight(230)
        reader_layout.addWidget(self.reader, 1)

        self.choice_group = QGroupBox("⚜  QUELLE SERA VOTRE VOIE ?")
        self.choice_layout = QVBoxLayout(self.choice_group)
        self.choice_hint = QLabel("Les destinations détectées apparaîtront ici.")
        self.choice_hint.setWordWrap(True)
        self.choice_layout.addWidget(self.choice_hint)
        reader_layout.addWidget(self.choice_group)

        self.event_group = QGroupBox("✧  ÉVÉNEMENTS")
        self.event_layout = QVBoxLayout(self.event_group)
        self.event_hint = QLabel("Aucun événement automatique détecté.")
        self.event_hint.setWordWrap(True)
        self.event_layout.addWidget(self.event_hint)
        reader_layout.addWidget(self.event_group)
        self.condition_group = QGroupBox("✧  INDICES D’INVENTAIRE")
        self.condition_layout = QVBoxLayout(self.condition_group)
        reader_layout.addWidget(self.condition_group)

        reader_scroll = QScrollArea()
        reader_scroll.setObjectName("pageScroll")
        reader_scroll.setWidgetResizable(True)
        reader_scroll.setFrameShape(QFrame.NoFrame)
        reader_scroll.setWidget(reader_panel)
        splitter.addWidget(reader_scroll)

        side = QWidget()
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(10)

        stats_group = QGroupBox("✦  FEUILLE D’AVENTURIER")
        self.stats_group = stats_group
        stats_grid = QGridLayout(stats_group)
        stats_grid.setHorizontalSpacing(4)
        stats_grid.setContentsMargins(8, 10, 8, 8)
        self.stat_spins = {}
        self.stat_bars = {}
        stats = [("HABILETÉ", "habilete"), ("ENDURANCE", "endurance"), ("CHANCE", "chance")]
        for column, (label, key) in enumerate(stats):
            caption = QLabel(label)
            caption.setAlignment(Qt.AlignCenter)
            stats_grid.addWidget(caption, 0, column)
            spin = QSpinBox()
            spin.setRange(0, 999)
            spin.setAlignment(Qt.AlignCenter)
            spin.setButtonSymbols(QSpinBox.UpDownArrows)
            spin.setObjectName("heroValue")
            spin.setMinimumHeight(46)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(lambda value, k=key: self.set_stat(k, value))
            stats_grid.addWidget(spin, 1, column)
            self.stat_spins[key] = spin
            bar = QProgressBar()
            bar.setObjectName(key + "Bar")
            bar.setRange(0, 100)
            stats_grid.addWidget(bar, 2, column)
            self.stat_bars[key] = bar
        resources = QHBoxLayout()
        resources.setSpacing(10)
        for label, key in (("Provisions", "provisions"), ("Or", "gold")):
            if key == 'gold':
                resources.addSpacing(12)
            resources.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(0, 999)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(lambda value, k=key: self.set_stat(k, value))
            spin.setMinimumWidth(40)
            spin.setMaximumWidth(70)
            resources.addWidget(spin)
            self.stat_spins[key] = spin
        stats_grid.addLayout(resources, 3, 0, 1, 3)
        self.potion_combo = QComboBox()
        self.potion_combo.addItems(["Aucune", "Potion d'Adresse", "Potion de Vigueur", "Potion de Bonne Fortune"])
        self.potion_combo.setAccessibleName("Potion choisie")
        # Le choix appartient à la création ; la feuille ne peut ni changer ni recharger la fiole.
        self.potion_combo.setEnabled(False)
        stats_grid.addWidget(self.potion_combo, 4, 0, 1, 3)
        self.potion_doses_label = QLabel()
        stats_grid.addWidget(self.potion_doses_label, 5, 0, 1, 3)
        self.initial_label = QLabel("Valeurs de départ : —")
        self.initial_label.setObjectName("initialStats")
        self.initial_label.setWordWrap(True)
        self.initial_label.hide()
        stats_grid.addWidget(self.initial_label, 6, 0, 1, 3)
        hero_row = QHBoxLayout()
        crest = QLabel("⚔")
        crest.setObjectName("heroCrest")
        crest.setAlignment(Qt.AlignCenter)
        crest.setFixedSize(64, 64)
        hero_row.addWidget(crest)
        hero_title = QLabel("L’AVENTURIER\nVotre destin s’écrit ici")
        self.hero_title = hero_title
        hero_title.setTextFormat(Qt.PlainText)
        hero_title.setWordWrap(True)
        hero_title.setObjectName("heroTitle")
        hero_row.addWidget(hero_title, 1)
        side_layout.addLayout(hero_row)
        side_layout.addWidget(stats_group)
        self.adventure_tabs = QTabWidget()
        self.adventure_tabs.setObjectName("adventureTabs")
        self.adventure_tabs.setDocumentMode(True)
        self.adventure_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.adventure_tabs.setMinimumHeight(160)
        side_layout.addWidget(self.adventure_tabs, 1)

        inv_group = QFrame()
        inv_group.setObjectName("inventoryPanel")
        inv_layout = QVBoxLayout(inv_group)
        inv_layout.setContentsMargins(8, 14, 8, 10)
        inv_layout.setSpacing(8)
        inventory_heading = QLabel("✦  SACOCHE & TRÉSORS")
        inventory_heading.setObjectName("inventoryHeading")
        inv_layout.addWidget(inventory_heading)
        self.inventory_list = QListWidget()
        self.inventory_list.setObjectName("inventoryCards")
        self.inventory_list.setWordWrap(True)
        self.inventory_list.setMinimumHeight(150)
        self.inventory_list.setSpacing(0)
        self.inventory_list.setIconSize(QSize(26, 26))
        inv_layout.addWidget(self.inventory_list)
        inv_row = QHBoxLayout()
        self.item_input = QLineEdit()
        self.item_input.setPlaceholderText("Ajouter un objet…")
        inv_row.addWidget(self.item_input)
        add_item_btn = QPushButton("+")
        add_item_btn.clicked.connect(self.add_item)
        inv_row.addWidget(add_item_btn)
        remove_item_btn = QPushButton("Retirer")
        remove_item_btn.clicked.connect(self.remove_item)
        inv_row.addWidget(remove_item_btn)
        inventory_tools = QWidget()
        inventory_tools.setLayout(inv_row)
        inventory_tools.hide()
        manage_inventory = QPushButton("Gérer les objets…")
        manage_inventory.setCheckable(True)
        manage_inventory.toggled.connect(inventory_tools.setVisible)
        inv_layout.addWidget(manage_inventory)
        inv_layout.addWidget(inventory_tools)
        self.equipment_label = QLabel("⚔  Arme : Épée     ◈  Protection : Armure de cuir")
        self.equipment_label.setWordWrap(True)
        self.equipment_label.setObjectName("equipment")
        self.equipment_label.hide()
        self.weapon_combo = QComboBox()
        self.weapon_combo.currentTextChanged.connect(self.change_weapon)
        self.weapon_combo.setToolTip("Arme équipée")
        inv_layout.insertWidget(1, self.weapon_combo)
        self.shield_check = QCheckBox("Utiliser le bouclier au croissant")
        self.shield_check.toggled.connect(self.change_shield_use)
        inv_layout.insertWidget(2, self.shield_check)
        self._add_adventure_tab(inv_group, "Sacoche")

        # Les widgets d'état du moteur ne constituent plus des panneaux visibles.
        # Leur remplacement par un modèle indépendant est distinct du transfert UI.
        self._build_engine_fields()
        self.adventure_tabs.tabBar().hide()
        controls = QGridLayout()
        self.combat_button = QPushButton("⚔  Combattre / Reprendre")
        self.combat_button.setObjectName("combatButton")
        self.combat_button.clicked.connect(self.open_combat)
        controls.addWidget(self.combat_button, 0, 0, 1, 2)
        self.care_button = QPushButton("Soins")
        self.care_button.clicked.connect(self.show_care_menu)
        controls.addWidget(self.care_button, 1, 0)
        self.tools_button = QPushButton("Actions…")
        tools = QMenu(self.tools_button)
        dice = tools.addMenu("Dés libres")
        for notation in ("1d6", "2d6", "3d6", "1d20"):
            dice.addAction(notation, lambda checked=False, n=notation: self.roll_free_dice(n))
        tools.addAction("Aller à un paragraphe…", self.choose_paragraph)
        self.tools_button.setMenu(tools)
        controls.addWidget(self.tools_button, 1, 1)
        side_layout.insertLayout(side_layout.indexOf(self.adventure_tabs), controls)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Sauvegarder")
        save_btn.clicked.connect(self.save_game)
        load_btn = QPushButton("Charger")
        load_btn.clicked.connect(self.load_game)
        save_row.addWidget(save_btn)
        save_row.addWidget(load_btn)
        side_layout.addLayout(save_row)
        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(side)
        splitter.addWidget(scroll)
        scroll.setMinimumWidth(365)
        splitter.setSizes([300, 880, 340])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 1)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _add_adventure_tab(self, content, title):
        """Placer un panneau dans un onglet défilable pour les petites hauteurs d’écran."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setMinimumHeight(150)
        page.setWidget(content)
        self.adventure_tabs.addTab(page, title)

    def _build_engine_fields(self):
        """Conserver les champs lus par les instantanés, hors de l'interface du lecteur.

        Les combattants sont préparés par le catalogue / les rencontres détectées.
        Les commandes visibles vivent dans CombatDialog ; aucun ancien onglet
        Combat ou Dés n'est créé par cette réserve de widgets non affichée.
        """
        fields = self._engine_fields = QWidget(self)
        fields.hide()
        self.enemy_name = QLineEdit('Monstre', fields)
        self.enemy_skill = QSpinBox(fields)
        self.enemy_skill.setRange(0, 99)
        self.enemy_skill.setValue(7)
        self.enemy_endurance = QSpinBox(fields)
        self.enemy_endurance.setRange(0, 999)
        self.enemy_endurance.setValue(6)
        self.rules_log = QLabel('Préparez le combat lorsque le récit le demande.', fields)
        self.combat_state = QLabel('Aucun combat engagé', fields)
        self.combat_journal = QListWidget(fields)
        self.dice_combo = QComboBox(fields)
        self.dice_combo.addItems(['1d6', '2d6', '3d6', '1d20'])
        self.dice_result = QLabel('Résultat : —', fields)
        self.dice_faces = QLabel('⚀  ⚀', fields)
        self.dice_history = QListWidget(fields)
        self.goto_spin = QSpinBox(fields)
        self.goto_spin.setRange(1, 999)
        self.goto_button = QPushButton('Voyager', fields)
        self.goto_button.clicked.connect(lambda: self.go_to(self.goto_spin.value()))

    def _refresh_action_controls(self):
        """Actualiser les commandes permanentes sans dépendre d'anciens onglets."""
        if not hasattr(self, 'combat_button'):
            return
        playing = self.current_paragraph is not None and self._adventurer_draft is None and self.character['endurance'] > 0
        self.combat_button.setEnabled(playing and self.combat_available())
        self.tools_button.setEnabled(playing)
        self.care_button.setEnabled(playing and any(option['enabled'] for option in self.care_options()))


    def choose_paragraph(self):
        """Ouvrir la navigation manuelle depuis le menu Actions, avec les mêmes contrôles de route."""
        number, accepted = QInputDialog.getInt(self, 'Voyager', 'Numéro de paragraphe :',
                                              self.current_paragraph or 1, 1, self.goto_spin.maximum())
        if accepted:
            self.go_to(number)

    def roll_free_dice(self, notation):
        """Présenter tous les jets libres sur le même plateau animé."""
        self.dice_combo.setCurrentText(notation)
        self.roll_dice()


    def use_care(self, kind):
        """Revérifier un soin au clic et l'appliquer dans une transaction annulable."""
        in_combat = self._combat_dialog is not None and not self._combat_dialog.outcome
        option = next((o for o in self.care_options(in_combat=in_combat) if o['id'] == kind), None)
        if not option or not option['enabled']:
            return
        if kind == 'potion':
            self.drink_potion()
        else:
            entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
            if entry.get('enchanted_meal'):
                self.take_enchanted_meal()
            elif entry.get('optional_meal_restore') == 2:
                self.eat_shared_meal()
            else:
                self.eat_meal()
            self._book_state(self.current_paragraph, True)['care_meal_taken'] = True
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def show_care_menu(self):
        """Offrir les soins hors combat sans réintroduire un onglet de commandes."""
        menu = QMenu(self)
        for option in self.care_options():
            action = menu.addAction(option['label'])
            action.setEnabled(option['enabled'])
            action.setToolTip(option['reason'] if not option['enabled'] else '')
            action.triggered.connect(lambda checked=False, kind=option['id']: self.use_care(kind))
        menu.exec(self.care_button.mapToGlobal(self.care_button.rect().bottomLeft()))
        menu.deleteLater()



    def _set_theme(self):
        """Distribuer le QSS, les polices et les surfaces dessinées aux widgets existants."""
        self.setStyleSheet(self.theme.stylesheet(self.reading_font_family, self.ui_font_family))

    def _toggle_scene_art(self, visible):
        """Afficher ou masquer la zone d’illustration sans changer le paragraphe."""
        self.scene_art.setVisible(visible)
        self.art_toggle.setText("◈  Image" if visible else "◈  Image")

    def _update_scene_art(self, prefer_cover=False):
        """Choisir couverture, illustration courante ou décor de repli selon l’écran affiché."""
        # La couverture est réservée à l'introduction. Pendant la lecture, le
        # décor fourni remplit la surface sans devenir une illustration active.
        background = None if prefer_cover else QPixmap(str(ASSET_DIR / 'illustration-background.jpg'))
        self.scene_art.set_background_art(background)
        self.scene_entry = None
        self.scene_title = ''
        if self.illustration_catalogue and self.pdf_path:
            entries = images_for_paragraph(self.illustration_catalogue, self.current_paragraph)
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

    def _show_welcome(self):
        """Afficher l’accueil sans livre et désactiver les commandes réservées à une partie."""
        self.paragraph_number.hide()
        self.choice_group.hide()
        self.event_group.hide()
        self.condition_group.hide()
        self.reader.setHtml("<h1>Ouvrez le grimoire.</h1><p>Une porte oubliée. Un trésor légendaire. Et vos décisions pour seule boussole.</p><p>Choisissez votre livre avec <b>Ouvrir un grimoire</b>, puis découvrez votre nouvel aventurier sur la page d’introduction.</p><p>Explorez, lancez les dés et écrivez votre propre histoire.</p>")

    def _show_book_title(self):
        """Afficher la couverture, le titre et le formulaire de création avant le §1.

        Un simple rafraîchissement conserve le tirage, le nom et le compteur de relances."""
        self.intro_music.menu()
        if self._adventurer_draft is None:
            self._prepare_adventurer()
        self.paragraph_number.hide()
        self.current_paragraph = None
        self.paragraph_title.setText("✦  Votre aventure commence ici  ✦")
        self._render_creation_preview()
        self._clear_dynamic_layout(self.choice_layout)
        first = 1 if 1 in self.paragraphs else min(self.paragraphs)
        label = QLabel('Sous quel nom entrerez-vous dans la légende ?')
        self.choice_layout.addWidget(label)
        name = QLineEdit(self._creation_name)
        name.setObjectName('adventurerName')
        name.setPlaceholderText('Nom de votre aventurier')
        name.setMaxLength(60)
        name.setAccessibleName('Nom de l’aventurier')
        self.choice_layout.addWidget(name)
        self.creation_name_field = name
        self.choice_layout.addWidget(QLabel('Votre potion de départ — une fiole, deux doses'))
        potion = QComboBox()
        potion.setObjectName('startingPotion')
        potion.setAccessibleName('Choisir la potion de départ')
        potion.addItems(["Potion d'Adresse", "Potion de Vigueur", "Potion de Bonne Fortune"])
        potion.setCurrentText(self.character['potion'])
        potion.currentTextChanged.connect(self.change_potion)
        self.choice_layout.addWidget(potion)
        description = QLabel("Adresse : restaure l’Habileté initiale. Vigueur : restaure l’Endurance initiale. "
                             "Bonne Fortune : augmente la Chance initiale de 1 puis la restaure. "
                             "Chaque dose peut être bue via Soins, même en combat.")
        description.setWordWrap(True)
        self.choice_layout.addWidget(description)
        verb = 'Commencer avec cet aventurier' if self._creation_rerolls == 2 else 'Valider cet aventurier et commencer'
        start = ChoiceCard(f'{verb}  →  §{first}')
        start.setObjectName("choiceCard")
        start.setEnabled(bool(name.text().strip()))
        def change_name(text):
            """Conserver la saisie du nom dans le brouillon entre deux rendus de l’introduction."""
            self._creation_name = text
            self.character['name'] = text.strip()
            self.hero_title.setText('L’AVENTURIER\n' + (text.strip() or 'Votre futur héros'))
            start.setEnabled(bool(text.strip()))
        name.textChanged.connect(change_name)
        start.clicked.connect(lambda checked=False: self._begin_adventure(name.text()))
        name.returnPressed.connect(start.click)
        self.choice_group.setTitle("⚜  L’AVENTURE VOUS ATTEND")
        self.creation_start_button = start
        remaining = 2 - self._creation_rerolls
        reroll_text = ('2 relances restantes' if remaining == 2 else
                       '1 relance restante' if remaining == 1 else 'aucune relance restante')
        reroll = ChoiceCard(f'🎲  Reroll — {reroll_text}')
        reroll.setObjectName('rerollAdventurer')
        reroll.setEnabled(self._creation_rerolls < 2)
        reroll.clicked.connect(self._reroll_adventurer)
        self.choice_layout.addWidget(reroll)
        self.creation_reroll_button = reroll
        self.choice_layout.addWidget(start)
        self.choice_group.show()
        self.event_group.hide()
        self.condition_group.hide()
        self._update_scene_art(prefer_cover=True)
        self.adventure_tabs.setEnabled(False)
        self.stats_group.setEnabled(False)
        self.goto_spin.setEnabled(False)
        self.goto_button.setEnabled(False)

    def _prepare_adventurer(self):
        """Créer le premier tirage et son équipement de départ ; remettre les relances à zéro."""
        self._creation_name = self.character.get('name', '')
        self._creation_rerolls = 0
        self._adventurer_draft = self._roll_adventurer()
        self.character = copy.deepcopy(self._initial_character)
        self.character.update(potion='Potion de Vigueur', potion_doses=2)
        self._apply_adventurer_draft()

    def _apply_adventurer_draft(self):
        """Recopier le tirage en attente dans les caractéristiques affichées."""
        self.character['initial'] = copy.deepcopy(self._adventurer_draft)
        self.character.update(self._adventurer_draft)
        if self._creation_name.strip():
            self.character['name'] = self._creation_name.strip()
        self._refresh_character()

    def _render_creation_preview(self):
        """Présenter les caractéristiques tirées sans valider ni consommer un nouveau jet."""
        import html
        title = ((self.illustration_catalogue or {}).get('title') or Path(self.pdf_path).stem)
        stats = self._adventurer_draft
        remaining = 2 - self._creation_rerolls
        instruction = (f'Vous pouvez garder ce tirage ou le relancer encore {remaining} fois.'
                       if remaining else 'Dernier tirage validé automatiquement. Inscrivez votre nom pour partir.')
        self.reader.setHtml(
            f'<div style="text-align:center; color:{self.theme.color("accent")}; font-family:\'{self.reading_font_family}\';">'
            '<p style="font-size:16pt">✦ LIVRE D’AVENTURE ✦</p>'
            f'<h1 style="font-size:38pt">{html.escape(title)}</h1>'
            '<h2>✦ Votre nouvel aventurier ✦</h2>'
            f'<p style="font-size:22pt"><b>Habileté {stats["habilete"]} &nbsp; · &nbsp; '
            f'Endurance {stats["endurance"]} &nbsp; · &nbsp; Chance {stats["chance"]}</b></p>'
            '<p>Habileté : 1d6 + 6 · Endurance : 2d6 + 12 · Chance : 1d6 + 6</p>'
            f'<p>{instruction}</p><p>Le deuxième reroll est définitif.</p></div>')

    def _reroll_adventurer(self):
        """Relancer au plus deux fois après le tirage initial.

        Le dernier tirage est validé automatiquement si le nom est renseigné ; sinon
        il reste figé jusqu’à la saisie du nom et à la validation."""
        if self.current_paragraph is not None or self._adventurer_draft is None or self._creation_rerolls >= 2:
            return
        self._creation_rerolls += 1
        self._adventurer_draft = self._roll_adventurer()
        self._apply_adventurer_draft()
        if self._creation_rerolls == 2 and self._creation_name.strip():
            self._begin_adventure(self._creation_name)
        else:
            self._show_book_title()

    def _restart_adventure(self):
        """Préparer une nouvelle création sur le même livre ; préserver les emplacements manuels."""
        self._adventurer_draft = None
        self._show_book_title()

    def _begin_adventure(self, name):
        """Valider le nom et le tirage exact, réinitialiser la progression puis entrer au §1.

        Ne pas lancer de dés ici : la validation ne doit jamais remplacer le héros affiché.
        Effacer le brouillon avant go_to pour lever le verrou de création."""
        name = name.strip()[:60]
        if not name or not self.paragraphs or self._adventurer_draft is None or self.current_paragraph is not None:
            return
        self._discard_combat_popup()
        potion = self.character['potion']
        self.character = copy.deepcopy(self._initial_character)
        self.character.update(potion=potion, potion_doses=2)
        self.character['name'] = name
        self.character['initial'] = copy.deepcopy(self._adventurer_draft)
        self.character.update(self._adventurer_draft)
        self.character['equipped_weapon'] = 'Épée'
        self.character['magic_sword_bonus_active'] = False
        self._adventurer_draft = None
        self.completed_book_events.clear()
        self.completed_optional_events.clear()
        self.prepared_book_encounters.clear()
        self.encounter_history = {}
        self.book_combat_sequence = self.crocodile_combat = self.piranha_combat = None
        self.piranha_source_wounded = None
        self.book_combat_assaults = {}
        self.current_paragraph = None
        self.visited_paragraphs = []
        self.transitions = []
        self.adventure_tabs.setEnabled(True)
        self.stats_group.setEnabled(True)
        self.goto_spin.setEnabled(True)
        self.goto_button.setEnabled(True)
        self._refresh_character()
        self.enemy_name.setText('Monstre')
        self.enemy_skill.setValue(7)
        self.enemy_endurance.setValue(6)
        self.combat_journal.clear()
        self.combat_state.setText('⚔  Aucun combat engagé')
        self.dice_history.clear()
        self.dice_result.setText('Résultat : —')
        self.dice_faces.setText('⚀   ⚀')
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.action_history.clear()
        self.go_to(1 if 1 in self.paragraphs else min(self.paragraphs))
        self.intro_music.fade_out()

    def _show_death_page(self):
        """Afficher la fin d’aventure et proposer recommencer ou charger ; bloquer les actions de jeu."""
        import html
        self.paragraph_number.hide()
        self._refresh_character()
        name = html.escape(self.character.get('name') or 'Aventurier')
        self.paragraph_title.setText('✦  Fin de l’aventure  ✦')
        self.reader.setHtml(
            f'<div style="text-align:center"><p style="font-size:36pt">⚔</p>'
            f'<h1>La légende de {name} s’achève ici.</h1>'
            '<p>Votre Endurance est épuisée. La montagne garde ses secrets…</p>'
            '<p>Un nouveau destin vous attend entre les pages du grimoire.</p></div>')
        self.event_group.hide()
        self.condition_group.hide()
        self._clear_dynamic_layout(self.choice_layout)
        self.choice_group.setTitle('⚜  UNE NOUVELLE CHRONIQUE')
        restart = ChoiceCard('✦  Recommencer l’aventure')
        restart.setObjectName('restartAdventure')
        restart.clicked.connect(self._restart_adventure)
        self.choice_layout.addWidget(restart)
        load = ChoiceCard('Ouvrir une chronique sauvegardée')
        load.clicked.connect(lambda: self.load_game())
        self.choice_layout.addWidget(load)
        self.choice_group.show()
        self.adventure_tabs.setEnabled(False)
        self.stats_group.setEnabled(False)
        self.goto_spin.setEnabled(False)
        self.goto_button.setEnabled(False)

    def open_pdf(self, path=None, *, startup=False):
        """Importer ou ouvrir le PDF, charger ses catalogues puis présenter la création.

        Le livre source n’est pas modifié ; les erreurs de lecture sont présentées en dialogue."""
        if not isinstance(path, (str, Path)):
            path = self._themed_file_dialog(kind="pdf")
        if not path:
            return
        try:
            paragraphs = extract_paragraphs(path)
            book_module = module_for_pdf(path)
            illustrations = book_module.catalogue('illustrations') if book_module else None
            events = book_module.catalogue('events') if book_module else None
        except Exception as exc:
            QMessageBox.critical(self, "Import impossible", str(exc))
            return
        if not paragraphs:
            QMessageBox.warning(self, "Aucun paragraphe", "Aucun paragraphe numéroté n'a été détecté. Le PDF est peut-être scanné ou sa mise en page n'est pas compatible.")
            return
        try:
            path = import_book(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import impossible", str(exc))
            return
        self.book_module = book_module
        self.pdf_path = path
        self.illustration_catalogue = illustrations
        self.book_event_catalogue = events
        for key in ("book_state", "book_visits", "book_facts"):
            self.character.pop(key, None)
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.encounter_history = {}
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self.paragraphs = paragraphs
        if self.illustration_catalogue is None and not startup:
            QMessageBox.information(self, "Illustrations", "Ce PDF ne correspond pas exactement à l’édition cataloguée. Les illustrations automatiques sont désactivées pour éviter les mauvaises associations.")
        self.book_label.setText(Path(path).name)
        self.goto_spin.setMaximum(max(paragraphs))
        first = 1 if 1 in paragraphs else min(paragraphs)
        self.transitions = []
        self.visited_paragraphs = []
        self.undo_stack.clear(); self.redo_stack.clear()
        self._update_history_controls()
        self._adventurer_draft = None
        self._show_book_title()
        self._remember_book()
        self._autosave()

    def _clear_dynamic_layout(self, layout):
        """Retirer et détruire plus tard les widgets des choix avant de reconstruire la liste."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _paragraph_choices(self, text):
        """Return conservative destination choices from explicit French references."""
        choices = []
        # Keep each explicit destination as a separate clickable choice. The label
        # is inferred from the text immediately preceding the reference.
        for start, end, target in destinations(text):
            match_start = start
            prefix = text[:match_start]
            # Start at the latest sentence/choice boundary, then trim common prose.
            boundary = max(prefix.rfind("."), prefix.rfind("?"), prefix.rfind("!"), prefix.rfind("\n"))
            # The book frequently puts the destination in parentheses after a choice.
            clause = prefix[boundary + 1:].strip(" \t,;:-()")
            clause = re.sub(r"(?i)\b(ou|et|puis)\s*$", "", clause).strip()
            if not clause:
                clause = 'Poursuivre le chemin'
            if len(clause) > 105:
                clause = clause[-105:].strip()
            # Avoid duplicate destinations in a single paragraph.
            if not any(c["target"] == target for c in choices):
                choices.append({"label": clause, "target": target})
        return choices

    def _paragraph_events(self, text):
        """Detect only explicit, simple Endurance/Provision changes; always confirm."""
        events = []
        patterns = [
            (r"(?i)\b(?:vous\s+)?perdez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", -1, "Perte d’Endurance"),
            (r"(?i)\b(?:vous\s+)?gagnez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", 1, "Gain d’Endurance"),
            (r"(?i)\b(?:vous\s+)?récupérez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", 1, "Récupération d’Endurance"),
            (r"(?i)\b(?:vous\s+)?perdez\s+(\d+)\s+provisions?\b", "provisions", -1, "Perte de provisions"),
        ]
        for pattern, key, sign, label in patterns:
            for match in re.finditer(pattern, text):
                amount = int(match.group(1)) * sign
                if not any(e["key"] == key and e["amount"] == amount for e in events):
                    events.append({"key": key, "amount": amount, "label": label})
        return events


    def _render_conditions(self, text):
        """Show hints, never automatically block a path based on uncertain prose."""
        self._clear_dynamic_layout(self.condition_layout)
        pattern = re.compile(r"(?i)\bsi vous (?:êtes )?(?:en possession d[eu'’]|possédez|avez|disposez d[eu'’])\s+([^,.\n;:]{2,90})")
        # Le catalogue vérifié gère déjà objets, faits et victoires : ne pas
        # lui superposer des hypothèses (« avez vaincu » n'est pas un objet).
        if verified_entry(self.book_event_catalogue, self.current_paragraph):
            return
        matches = [raw for raw in pattern.findall(text)
                   if not re.match(r"(?i)(?:(?:déjà|encore|bien)\s+)*(?:vaincu|tué|eu|réussi|perdu|gagné|visité|trouvé|été)\b", raw)]
        if not matches:
            return
        inventory = [x.casefold() for x in self.character.get("inventory", [])]
        for raw in matches[:8]:
            item = re.sub(r"^(?:la |le |les |l['’]|un |une |des |du |de la )", "", raw.strip(), flags=re.I)
            # A substring match is only an indication, not a proof of possession.
            found = any(item.casefold() in owned or owned in item.casefold() for owned in inventory if len(owned) >= 4)
            label = QLabel(f"{'✓ Objet possiblement présent' if found else '? Objet non reconnu'} : {raw.strip()}")
            label.setWordWrap(True)
            self.condition_layout.addWidget(label)
        self.condition_layout.addWidget(QLabel("Vérifiez le texte original : aucun choix n’est bloqué automatiquement."))

    def show_about(self):
        """Ouvrir la fenêtre d’identité avec les assets et couleurs du thème actif."""
        dialog = AboutDialog(ASSET_DIR, self.theme, self)
        dialog.exec()
        dialog.deleteLater()

    def show_rules(self):
        """Ouvrir les pages de règles du PDF courant dans une fenêtre indépendante."""
        if not self.pdf_path:
            QMessageBox.information(self, "Règles", "Ouvrez un livre pour lire ses règles.")
            return
        existing = getattr(self, "rules_dialog", None)
        if existing is not None and existing.isVisible() and existing.pdf_path == str(self.pdf_path):
            existing.raise_()
            existing.activateWindow()
            return
        try:
            pages = self.book_module.rules_pages if self.book_module else (3, 14)
            dialog = RulesDialog(self.pdf_path, self, pages=pages)
        except Exception as exc:
            QMessageBox.warning(self, "Règles indisponibles", str(exc))
            return
        if existing is not None:
            existing.close()
            existing.deleteLater()
        self.rules_dialog = dialog
        dialog.show()

    def _remember_monster(self, name, status="rencontré", number=None):
        """Enregistrer l’adversaire et son statut sous la clé du paragraphe pour la carte."""
        number = self.current_paragraph if number is None else number
        if self._restoring or number is None:
            return
        entry = verified_entry(self.book_event_catalogue, number)
        state = self._book_state(number)
        if ((entry or {}).get("combat", {}).get("mode") == "paired"
                and state.get("pair", -1) >= 0 and name != "Chef Squelette"):
            name = f"{name} (paire {state['pair'] + 1})"
        monsters = self.encounter_history.setdefault(str(number), [])
        monster = next((m for m in monsters if m["name"] == name), None)
        if monster is None:
            monsters.append({"name": name, "status": status})
        elif status != "rencontré":
            monster["status"] = status

    def _map_monsters_html(self, number):
        """Échapper les noms et formater les rencontres mémorisées d’un lieu exploré."""
        import html
        monsters = self.encounter_history.get(str(number), [])
        return "".join(f'<br>⚔ {html.escape(m["name"])} — {html.escape(m["status"])}' for m in monsters)

    def show_map(self):
        """Afficher seulement les lieux explorés, leurs transitions et l’issue des rencontres."""
        if not self.paragraphs:
            QMessageBox.information(self, "Carte", "Importez d’abord un PDF.")
            return
        from exploration_map import ExplorationMapDialog
        dialog = ExplorationMapDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _paragraph_name(self, number):
        """Lire le titre catalogué d’un lieu, avec repli si le livre n’est pas reconnu."""
        entry = verified_entry(self.book_event_catalogue, number)
        return entry.get('title', '') if entry else ''

    def prepare_encounter(self, monster):
        """Proposer une rencontre détectée et renseigner le combat après confirmation."""
        answer = QMessageBox.question(self, "Préparer une rencontre",
            f"Utiliser les caractéristiques de {monster['name']} ?\n"
            f"Habileté : {monster['skill']} — Endurance : {monster['stamina']}\n"
            "Vérifiez le paragraphe : les règles spéciales restent manuelles.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        self._discard_combat_popup()
        self._remember_monster(monster['name'])
        self.enemy_name.setText(monster['name'])
        self.enemy_skill.setValue(monster['skill'])
        self.enemy_endurance.setValue(monster['stamina'])
        self.rules_log.setText(f"Rencontre préparée : {monster['name']}.")
        self.combat_state.setText(f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")
        self.combat_journal.clear()
        self._refresh_action_controls()

    def confirm_item(self, name):
        """Demander confirmation avant d’ajouter un objet suggéré par le texte."""
        if QMessageBox.question(self, "Objet détecté",
                f"Ajouter « {name} » à l’inventaire ?\nVérifiez que vous avez réellement récupéré cet objet.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if name.casefold() in [x.casefold() for x in self.character.get('inventory', [])]:
            QMessageBox.information(self, "Inventaire", "Cet objet est déjà présent.")
            return
        self.character.setdefault('inventory', []).append(name)
        self._refresh_character()
        self.rules_log.setText(f"Objet ajouté : {name}")

    def apply_detected_event(self, event):
        """Confirmer un effet heuristique avant de modifier les caractéristiques."""
        key = event["key"]
        before = int(self.character.get(key, 0))
        after = max(0, before + int(event["amount"]))
        if key in ("endurance", "habilete", "chance"):
            cap = int(self.character.get("initial", {}).get(key, after))
            after = min(after, cap)
        label = {"endurance":"Endurance", "provisions":"Provisions", "habilete":"Habileté", "chance":"Chance"}.get(key, key)
        answer = QMessageBox.question(self, "Confirmer l’événement",
            f"Appliquer {event['label'].lower()} ?\n{label} : {before} → {after}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        self.character[key] = after
        self._refresh_character()
        self.rules_log.setText(f"Événement appliqué : {label} {before} → {after}.")

    def apply_optional_book_event(self, number, option_id):
        """Appliquer un choix catalogué encore disponible et rafraîchir les commandes."""
        if number != self.current_paragraph or self.character["endurance"] <= 0:
            return
        if apply_option(self.character, self.completed_optional_events, number,
                        option_id, self.book_event_catalogue):
            self._refresh_character()
            self.rules_log.setText(f"Objet ou ressource récupéré au paragraphe {number}.")
            self._render_choices_and_events(self.paragraphs[number])

    def resolve_book_roll(self, number):
        """Effectue une seule fois un jet spécial, puis applique son issue."""
        entry = verified_entry(self.book_event_catalogue, number)
        if (number != self.current_paragraph or not entry or entry["mode"] not in ("des", "des_optionnel")
                or "roll" not in entry or number in self.completed_book_events
                or self.character["endurance"] <= 0):
            return
        dice = entry["roll"]["dice"]
        rolls, total = self._roll(dice)
        outcome = resolve_roll(entry["roll"], total, self.character)
        if outcome["target"] not in self.paragraphs:
            QMessageBox.warning(self, "Paragraphe absent",
                                f"Impossible de résoudre l'épreuve : §{outcome['target']} non chargé.")
            return
        followup = outcome.get("followup")
        extra_text = ""
        extra_effects = []
        if followup:
            if followup["kind"] != "stat" or followup["key"] != "gold" or followup["dice"] not in (1, 2):
                raise ValueError("Deuxième tirage non pris en charge")
            extra_rolls, extra_total = self._roll(followup["dice"])
            extra_effects = [{"kind": "stat", "key": "gold", "amount": extra_total}]
            extra_text = f" ; gains : {extra_rolls} = {extra_total} pièces d'or"
        self.completed_book_events.add(number)
        # Le seuil de Chance est évalué AVANT de consommer un point.
        apply_effects(self.character, entry["roll"].get("pre_effects", []))
        apply_effects(self.character, outcome.get("effects", []))
        apply_effects(self.character, [
            {"kind": "stat", "key": effect["key"], "amount": total * effect["multiplier"]}
            for effect in entry["roll"].get("roll_effects", [])])
        apply_effects(self.character, extra_effects)
        self._refresh_character()
        self.rules_log.setText(
            f"Épreuve §{number} : dés {rolls} = {total}{extra_text} ; destination §{outcome['target']}.")
        if self.character["endurance"] > 0:
            self.go_to(outcome["target"])
        else:
            self._render_choices_and_events(self.paragraphs[number])


    def _illustration_pixmap(self, entry, scale=2):
        """Rendre le rectangle catalogué, avec page PDF base 1 et pixels copiés.

        QImage peut référencer la mémoire PyMuPDF : copy est nécessaire avant fermeture
        du document pour que le QPixmap survive à cette méthode."""
        import pymupdf as fitz
        with fitz.open(self.pdf_path) as doc:
            page = doc[entry["page_pdf"] - 1]
            clip = fitz.Rect(entry["rect"])
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            return QPixmap.fromImage(image.copy())

    def _show_illustration(self, entry, title):
        """Créer une vue zoomable indépendante dimensionnée selon la surface utile de l’écran."""
        try:
            pixmap = self._illustration_pixmap(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Illustration", str(exc))
            return
        dialog = IllustrationDialog(self)
        dialog.setObjectName("illustrationDialog")
        dialog.setWindowIcon(self.windowIcon())
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        # Respecter la surface utile de l'écran, sans défilement horizontal.
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        max_width = max(320, available.width() - 90)
        max_height = max(260, available.height() - 150)
        displayed = pixmap.scaled(max_width - 44, max_height - 160,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
        viewer = GrimoireScene(self.theme.assets["scene"], theme=self.theme)
        viewer.setMinimumSize(200, 180)
        viewer.set_book_art(pixmap)
        viewer.setAccessibleName(title)
        layout.addWidget(viewer, 1)
        layout.addWidget(QLabel("Molette : zoom · Glisser : déplacer · Clic : recadrer"))
        status = "association probable" if entry.get("statut") == "probable" else "association vérifiée par position" if entry.get("statut") == "verifie_position" else "association vérifiée"
        status_label = QLabel(f"Page PDF {entry['page_pdf']} · {status}")
        status_label.setObjectName("illustrationStatus")
        layout.addWidget(status_label)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.default_size = QSize(min(max_width, max(440, displayed.width() + 54)),
                                    min(max_height, displayed.height() + 175))
        dialog.setMinimumSize(400, 300)
        dialog.resize(dialog.default_size)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def show_cover(self):
        """Afficher le cadrage de couverture s’il existe dans le catalogue associé au PDF."""
        if self.illustration_catalogue:
            entry = cover(self.illustration_catalogue)
            if entry:
                self._show_illustration(entry, "Couverture — Le Sorcier de la Montagne de Feu")

    def show_paragraph_illustration(self):
        """Ouvrir successivement les illustrations associées au paragraphe courant."""
        if not self.illustration_catalogue:
            return
        entries = images_for_paragraph(self.illustration_catalogue, self.current_paragraph)
        for index, entry in enumerate(entries, 1):
            suffix = f" ({index}/{len(entries)})" if len(entries) > 1 else ""
            self._show_illustration(entry, f"Illustration — paragraphe {self.current_paragraph}{suffix}")

    def _combat_exit_pending(self, target):
        """La destination d'un combat reste inaccessible tant qu'il n'est pas résolu."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        combat = entry.get("combat", {}) if entry else {}
        expected = (combat.get("first_hit_target") if combat.get("mode") == "first_hit"
                    else combat.get("victory_target") if len(combat.get("enemies", [])) == 1
                    else None)
        if (combat.get("mode") == "sequence"
                and target == combat.get("victory_target")):
            return self.current_paragraph not in self.prepared_book_encounters
        return (expected == target and (
            combat.get("mode") == "first_hit"
            or self.enemy_endurance.value() > 0))


    def follow_catalogue_choice(self, target):
        """Toutes les issues vérifiées passent par le même contrôle de ressources."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if (not entry or target not in self.paragraphs
                or self._combat_exit_pending(target) or self._book_blocked(target)
                or (self.current_paragraph == 212 and target == 369
                    and 369 in self.visited_paragraphs)
                or (entry.get("diversion_discard")
                    and self.current_paragraph not in self.completed_book_events)
                or (entry.get("enchanted_meal")
                    and self.current_paragraph not in self.completed_book_events)
                or not follow_catalogue_route(self.character, entry, target)):
            QMessageBox.information(
                self, "Chemin inaccessible", "Les conditions de ce passage ne sont pas remplies.")
            return
        self._refresh_character()
        if self.character["endurance"] > 0:
            self.go_to(target)
        else:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])




    def _refresh_character(self):
        """Synchroniser statistiques, équipement et inventaire sans déclencher de nouvelle action."""
        self.hero_title.setText('L’AVENTURIER\n' +
                                (self.character.get('name') or 'Votre destin s’écrit ici'))
        for key, spin in self.stat_spins.items():
            spin.blockSignals(True)
            spin.setValue(int(self.character.get(key, 0)))
            spin.blockSignals(False)
        self.potion_combo.blockSignals(True)
        self.potion_combo.setCurrentText(self.character.get("potion", "Aucune"))
        self.potion_combo.blockSignals(False)
        doses = self.character.get('potion_doses', 0)
        self.potion_doses_label.setText(f'Doses restantes : {doses} / 2' if self.character.get('potion') != 'Aucune'
                                       else 'Aucune potion')
        # Un assaut ne modifie généralement pas le sac : conserver ses items,
        # leur sélection et leur défilement tant que son contenu reste identique.
        inventory = tuple(str(name) for name in self.character.get('inventory', []))
        weapon = equipped_weapon(self.character)
        inventory_signature = (inventory, weapon, *(self.theme.color(key) for key in
                               ('icon_background', 'icon_border', 'icon_ink')))
        if inventory_signature != getattr(self, '_inventory_signature', None):
            self.inventory_list.clear()
            for name in inventory:
                item = QListWidgetItem(inventory_icon(name, self.theme), name)
                item.setToolTip(name + (' — Arme équipée' if name == weapon else ''))
                self.inventory_list.addItem(item)
            self._inventory_signature = inventory_signature
        self.shield_check.blockSignals(True)
        self.shield_check.setVisible(SHIELD_NAME in self.character.get("inventory", []))
        self.shield_check.setChecked(bool(self.character.get("shield_equipped", False)))
        self.shield_check.blockSignals(False)
        self.weapon_combo.blockSignals(True)
        weapons = [name for name in ('Épée', 'Épée magique', 'Épée trouvée dans la rivière') if name in inventory]
        if weapons != [self.weapon_combo.itemText(index) for index in range(self.weapon_combo.count())]:
            self.weapon_combo.clear()
            self.weapon_combo.addItems(weapons)
        if weapon:
            self.weapon_combo.setCurrentText(weapon)
        self.weapon_combo.blockSignals(False)
        initial = self.character.get("initial", {})
        for key, bar in self.stat_bars.items():
            maximum = max(1, int(initial.get(key, self.character.get(key, 1))))
            current = max(0, int(self.character.get(key, 0)))
            bar.setValue(min(100, round(100 * current / maximum)))
            bar.setFormat(f"{current} / {maximum}")
        self.initial_label.setText("Départ  •  Habileté {habilete}  |  Endurance {endurance}  |  Chance {chance}".format(
            **{key: initial.get(key, "—") for key in ("habilete", "endurance", "chance")}))
        weapon = weapon or "—"
        armor = next((item for item in self.character.get("inventory", []) if "armure" in str(item).casefold() or "bouclier" in str(item).casefold()), "—")
        self.equipment_label.setText(f"⚔  Arme : {weapon}     ◈  Protection : {armor}")
        self._refresh_action_controls()
        if self._combat_dialog is not None:
            self._combat_dialog.refresh_stats()

        self.stat_feedback.observe(self.character,
            enabled=(self.isVisible() and self.current_paragraph is not None
                     and self._adventurer_draft is None and not self._restoring),
            batch=self._feedback_action_id)


    def _roll(self, count=1, sides=6, *, context=None, opponent=False):
        """Tirer une seule fois, présenter le résultat animé puis retourner (faces, somme).

        L'animation ne consomme aucun hasard. Les jets 1d6, 2d6, 3d6 et 1d20
        utilisent le même plateau, y compris les combats particuliers."""
        if self._combat_dialog is None:
            self.sounds.play("dice")
        rolls = [random.randint(1, sides) for _ in range(count)]
        if (sides == 6 and count in (1, 2, 3)) or (sides == 20 and count == 1):
            label = context or (f'Épreuve — § {self.current_paragraph}'
                                if self.current_paragraph is not None else 'Création de l’aventurier')
            if self._combat_dialog is not None:
                self._combat_dialog.present_roll(rolls, label, opponent=opponent,
                                                **({'sides': sides} if sides != 6 else {}))
            else:
                self._show_dice_roll(rolls, label, **({'sides': sides} if sides != 6 else {}))
        return rolls, sum(rolls)

    def _show_dice_roll(self, rolls, context, *, sides=6):
        """Présenter les faces tirées sans mutation de partie ni écriture d'historique.

        Les plateformes Qt de test ne lancent pas de boucle modale ; le dialogue
        et sa géométrie restent testables directement en offscreen.
        """
        if QApplication.platformName() in ('offscreen', 'minimal'):
            return
        dialog = DiceDialog(rolls, context, self.theme, self, sides=sides)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()







    def _log_assault(self, player_rolls, enemy_rolls, player_attack, enemy_attack, outcome):
        """Ajouter au journal les dés, forces d’attaque et résultat du dernier assaut."""
        self._book_round_played = True
        if (self.crocodile_combat
                and self.current_paragraph == self.crocodile_combat["paragraph"]):
            self.crocodile_combat["assaults"] += 1
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if entry and "escape_target" in entry.get("combat", {}):
            number = self.current_paragraph
            self.book_combat_assaults[number] = self.book_combat_assaults.get(number, 0) + 1
        self.combat_journal.insertItem(0, f"Vous {player_rolls} = {player_attack} | Ennemi {enemy_rolls} = {enemy_attack} | {outcome}")
        self.combat_state.setText(f"⚔  {self.enemy_name.text()} • Endurance {self.enemy_endurance.value()} | Héros {self.character['endurance']}")
        if self._combat_dialog is not None:
            self._combat_dialog.note_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, outcome)
        while self.combat_journal.count() > 60:
            self.combat_journal.takeItem(self.combat_journal.count() - 1)

    def _log_combat_detail(self, text):
        """Journaliser une phase spéciale sans la compter comme un nouvel assaut."""
        self.combat_journal.insertItem(0, text)
        if self._combat_dialog is not None:
            self._combat_dialog.log(text)

    def open_combat(self):
        """Ouvrir ou reprendre le combat ; l'entrée dans la fenêtre ne modifie pas ses adversaires.

        Le dialogue appelle la méthode d'assaut déjà suivie par l'historique.
        Ne pas envelopper open_combat dans _track_action : chaque assaut conserve
        sa propre transaction, ses effets spéciaux et son autosave.
        """
        if self._combat_dialog is not None or self._adventurer_draft is not None:
            return
        if self.character['endurance'] <= 0:
            self._show_death_page()
            return
        if not self.combat_available():
            return
        popup = self._combat_popup
        if (popup is None or popup.outcome or self.current_paragraph not in popup.paragraphs
                or self.enemy_name.text() not in [e['name'] for e in popup.roster]):
            if popup is not None:
                popup.deleteLater()
            popup = self._combat_popup = CombatDialog(self)
        popup.refresh_stats()
        self._combat_dialog = popup
        try:
            popup.exec()
        finally:
            self._combat_dialog = None

    def _discard_combat_popup(self):
        """Abandonner la chronique visuelle après restauration, nouvelle partie ou nouvelle rencontre."""
        if self._combat_dialog is None and self._combat_popup is not None:
            self._combat_popup.deleteLater()
            self._combat_popup = None

    def _ask_combat_question(self, title, text):
        """Poser une question du livre dans le combat actif, ou garder le dialogue standard hors combat."""
        if self._combat_dialog is not None:
            return QMessageBox.Yes if self._combat_dialog.choose_luck(title + '\n' + text) else QMessageBox.No
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

    def _assault_luck_choice(self, title, text, information):
        """Partager la décision de Chance entre le plateau et les appels directs du moteur."""
        if self._combat_dialog is not None:
            return QMessageBox.Yes if self._combat_dialog.choose_luck(text + '\n' + information) else QMessageBox.No
        outcome = QMessageBox(self)
        outcome.setWindowTitle(title)
        outcome.setText(text)
        outcome.setInformativeText(information)
        outcome.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        outcome.button(QMessageBox.Yes).setText('Tenter ma Chance')
        outcome.button(QMessageBox.No).setText('Non')
        return outcome.exec()













    def change_weapon(self, name):
        """Équiper une arme présente dans le sac ; opération annulable."""
        if not name:
            return
        if equip_weapon(self.character, name):
            self._refresh_character()
            self.rules_log.setText(
                f"Arme équipée : {name}. Habileté de combat : {combat_skill(self.character)}.")

    def add_item(self):
        """Ajouter le nom saisi à l’inventaire et actualiser la sacoche."""
        item = self.item_input.text().strip()
        if item:
            self.character.setdefault("inventory", []).append(item)
            self._refresh_character()
            self.item_input.clear()

    def remove_item(self):
        """Retirer l’objet sélectionné sauf malédiction et annuler ses effets d’équipement.

        Le retrait d’une épée magique doit retirer son bonus courant et initial ; un
        bouclier absent ne doit pas rester équipé dans l’état."""
        row = self.inventory_list.currentRow()
        if row >= 0:
            item = self.character["inventory"][row]
            if item in self.character.get("locked_items", []):
                QMessageBox.information(
                    self, "Objet maudit",
                    f"Vous ne pouvez pas retirer {item} : cet objet est ensorcelé.")
                return
            if equipped_weapon(self.character) == item:
                other = next((name for name in ("Épée", "Épée magique", "Épée trouvée dans la rivière")
                              if name != item and name in self.character["inventory"]), None)
                if other:
                    equip_weapon(self.character, other)
                elif item == "Épée magique" and self.character.get("magic_sword_bonus_active"):
                    self.character["initial"]["habilete"] = max(
                        0, self.character["initial"]["habilete"] - 2)
                    self.character["habilete"] = max(0, self.character["habilete"] - 2)
                    self.character["magic_sword_bonus_active"] = False
            self.character["inventory"].pop(row)
            if item == SHIELD_NAME:
                self.character["shield_equipped"] = False
            if self.character.get("equipped_weapon") == item:
                self.character["equipped_weapon"] = None
            self._refresh_character()

    def roll_dice(self):
        """Effectuer le jet libre demandé et afficher faces et historique visuel."""
        notation = self.dice_combo.currentText()
        count, sides = notation.lower().split("d")
        rolls, total = self._roll(int(count), int(sides))
        result = f"{notation} : {' + '.join(map(str, rolls))} = {total}"
        self.dice_result.setText(result)
        faces = "⚀⚁⚂⚃⚄⚅"
        self.dice_faces.setText("  ".join((faces[n-1] if 1 <= n <= 6 else str(n)) for n in rolls) if rolls else "—")
        self.dice_history.insertItem(0, result)

    def _snapshot(self):
        """Copier l’état de jeu sérialisable, y compris l’adversaire affiché et les marqueurs.

        Exclure les objets Qt, le PDF et les préférences. Les listes remplacent les sets
        pour JSON ; les copies profondes empêchent une action de modifier les anciens états."""
        return {"character": copy.deepcopy(self.character),
                "encounter_history": copy.deepcopy(self.encounter_history),
                "completed_book_events": sorted(self.completed_book_events),
                "completed_optional_events": sorted(self.completed_optional_events),
                "prepared_book_encounters": sorted(self.prepared_book_encounters),
                "book_combat_sequence": copy.deepcopy(self.book_combat_sequence),
                "crocodile_combat": copy.deepcopy(self.crocodile_combat),
                "piranha_source_wounded": self.piranha_source_wounded,
                "piranha_combat": copy.deepcopy(self.piranha_combat),
                "book_combat_assaults": copy.deepcopy(self.book_combat_assaults),
                "current_paragraph": self.current_paragraph,
                "visited_paragraphs": list(self.visited_paragraphs),
                "transitions": copy.deepcopy(self.transitions),
                "enemy_skill": self.enemy_skill.value(),
                "enemy_endurance": self.enemy_endurance.value(),
                "enemy_name": self.enemy_name.text()}

    def _record(self, label, before):
        """Enregistrer seulement une mutation effective de l’action extérieure.

        Borner Undo à 100 états et le journal à 200 libellés ; invalider Redo, jouer le
        signal de résultat, afficher la mort si nécessaire puis écrire l’autosave."""
        if self._restoring or before == self._snapshot():
            return
        if label != 'Changer de potion':
            self._play_state_sounds(before)
        self.undo_stack.append((label, before))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.action_history.append(label)
        self.action_history = self.action_history[-200:]
        self._update_history_controls()
        if self.character['endurance'] <= 0:
            self._show_death_page()
        self._autosave()

    def _play_state_sounds(self, before):
        """One outcome cue per action; no replay on refresh, Undo or loading."""
        from collections import Counter
        old = before["character"]
        new = self.character
        if old.get("endurance", 0) > 0 and new.get("endurance", 0) <= 0:
            self.sounds.play("death")
            return
        old_wins = {(p, m["name"]) for p, monsters in before.get("encounter_history", {}).items()
                    for m in monsters if m["status"] in ("vaincu", "repoussé")}
        wins = {(p, m["name"]) for p, monsters in self.encounter_history.items()
                for m in monsters if m["status"] in ("vaincu", "repoussé")}
        if (wins - old_wins or
                (new.get("book_facts", {}).get("adventure_won")
                 and not old.get("book_facts", {}).get("adventure_won"))):
            self.sounds.play("victory")
            return
        if new.get("potion_doses", 0) < old.get("potion_doses", 0):
            self.sounds.play("potion")
            return
        source = before["current_paragraph"]
        if source != self.current_paragraph:
            entry = verified_entry(self.book_event_catalogue, source)
            if entry:
                keyed = entry.get("special") == "keys" or any(
                    r["target"] == self.current_paragraph and "clé" in r["label"].casefold()
                    for r in available_routes(old, entry))
                if keyed:
                    self.sounds.play("key")
                    return
        if new.get("endurance", 0) < old.get("endurance", 0):
            self.sounds.play("hit")
        elif new.get("gold", 0) != old.get("gold", 0):
            self.sounds.play("coins")
        elif Counter(new.get("inventory", [])) - Counter(old.get("inventory", [])):
            self.sounds.play("item")

    def _update_history_controls(self):
        """Mettre à jour les boutons et compteurs à partir des piles Undo / Redo."""
        if not hasattr(self, "undo_btn"):
            return
        self.undo_btn.setEnabled(bool(self.undo_stack))
        self.redo_btn.setEnabled(bool(self.redo_stack))
        self.history_label.setText(f"Historique : {len(self.action_history)} actions · Annulables : {len(self.undo_stack)}")
        self.undo_btn.setToolTip(self.undo_stack[-1][0] if self.undo_stack else "")

    def _restore(self, state):
        """Restaurer une copie d’état et les widgets sans effets de navigation supplémentaires.

        _restoring est toujours relâché dans finally. Un héros déjà accepté revenant à
        l’introduction par Undo ne récupère pas de relances de création."""
        self._discard_combat_popup()
        self._restoring = True
        try:
            self.character = copy.deepcopy(state["character"])
            self.encounter_history = copy.deepcopy(state.get("encounter_history", {}))
            self.completed_book_events = set(state.get("completed_book_events", []))
            self.completed_optional_events = set(state.get("completed_optional_events", []))
            self.prepared_book_encounters = set(state.get("prepared_book_encounters", []))
            self.book_combat_sequence = copy.deepcopy(state.get("book_combat_sequence"))
            self.crocodile_combat = copy.deepcopy(state.get("crocodile_combat"))
            self.piranha_source_wounded = state.get("piranha_source_wounded")
            self.piranha_combat = copy.deepcopy(state.get("piranha_combat"))
            self.book_combat_assaults = {int(k): int(v) for k, v in state.get("book_combat_assaults", {}).items()}
            self.visited_paragraphs = list(state["visited_paragraphs"])
            self.transitions = copy.deepcopy(state.get("transitions", []))
            self._refresh_character()
            if "enemy_skill" in state:
                self.enemy_skill.setValue(state["enemy_skill"])
            if "enemy_endurance" in state:
                self.enemy_endurance.setValue(state["enemy_endurance"])
            if "enemy_name" in state:
                self.enemy_name.setText(state["enemy_name"])
            target = state["current_paragraph"]
            self._adventurer_draft = None
            if target is None and self.character.get('name'):
                self._adventurer_draft = copy.deepcopy(self.character['initial'])
                self._creation_name = self.character['name']
                self._creation_rerolls = 2  # An accepted character cannot be rerolled through Undo.
            if target in self.paragraphs:
                self.go_to(target)
            else:
                self.current_paragraph = target
                if target is None and self.pdf_path and self.paragraphs:
                    self._show_book_title()
        finally:
            self._restoring = False
        alive = self.character['endurance'] > 0
        playing = alive and self.current_paragraph is not None
        self.adventure_tabs.setEnabled(playing)
        self.stats_group.setEnabled(playing)
        self.goto_spin.setEnabled(playing)
        self.goto_button.setEnabled(playing)
        if not alive:
            self._show_death_page()

    def undo_action(self):
        """Empiler l’état courant dans Redo puis restaurer le dernier état antérieur."""
        if not self.undo_stack:
            return
        label, state = self.undo_stack.pop()
        self.redo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action annulée : {label}")
        self._update_history_controls()
        self._autosave()

    def redo_action(self):
        """Empiler l’état courant dans Undo puis réappliquer l’état annulé."""
        if not self.redo_stack:
            return
        label, state = self.redo_stack.pop()
        self.undo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action rétablie : {label}")
        self._update_history_controls()
        self._autosave()

    def set_stat(self, key, value):
        """Appliquer une édition manuelle de caractéristique et rafraîchir sa représentation."""
        before = self._snapshot()
        self.character[key] = value
        self._feedback_action_id += 1
        self._refresh_character()
        self._record(f"Modifier {key}", before)

    def _save_data(self):
        """Construire le JSON courant : instantané, historique, date, version et identité du PDF.

        Le chemin relatif permet de déplacer Bifurk ; le SHA-256 vérifie le livre au
        chargement. Ni texte narratif ni widgets ne sont inclus."""
        return {"version": APP_VERSION, "pdf_path": (str(Path(self.pdf_path).relative_to(APP_DIR)) if self.pdf_path and within_directory(self.pdf_path, APP_DIR) else None),
                "saved_at": datetime.now().astimezone().isoformat(),
                "save_name": self.character.get('name') or 'Aventurier sans nom',
                "pdf_sha256": self._pdf_hash(),
                "module_id": self.book_module.id if self.book_module else None,
                **self._snapshot(), "action_history": self.action_history,
                "undo_stack": self.undo_stack, "redo_stack": self.redo_stack}

    def _pdf_hash(self, path=None):
        """Calculer le SHA-256 par blocs ; un chemin candidat permet de valider avant chargement."""
        path = path or self.pdf_path
        if not path or not Path(path).is_file():
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _write_atomic(self, path, data):
        """Écrire un JSON temporaire dans le même dossier, fsync puis os.replace.

        L’ancien fichier reste intact si l’écriture échoue avant remplacement ; nettoyer
        le temporaire dans finally. Le même dossier permet le remplacement atomique."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as f:
                tmp = Path(f.name)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if tmp and tmp.exists():
                tmp.unlink()

    def _autosave(self):
        """Écrire l’état technique séparé des cinq emplacements ; tolérer une erreur disque."""
        if not self.pdf_path or self._restoring:
            return
        try:
            directory = SAVES_DIR
            self._write_atomic(directory / "autosave.json", self._save_data())
        except OSError:
            pass  # La sauvegarde manuelle reste disponible.

    def _themed_file_dialog(self, kind="pdf"):
        """Sélecteur Qt français réservé à l’import d’un grimoire."""
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Bifurk — Ouvrir un grimoire')
        dialog.setWindowIcon(self.windowIcon())
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setLabelText(QFileDialog.LookIn, "Regarder dans :")
        dialog.setLabelText(QFileDialog.FileName, "Nom du fichier :")
        dialog.setLabelText(QFileDialog.FileType, "Type de fichier :")
        dialog.setLabelText(QFileDialog.Accept, "Ouvrir")
        dialog.setLabelText(QFileDialog.Reject, "Annuler")
        dialog.setNameFilter("Grimoires PDF (*.pdf)")
        harmonize_standard_dialog(dialog)
        dialog.setDirectory(str(Path(self.pdf_path).parent if self.pdf_path else BOOKS_DIR))
        area = dialog.screen().availableGeometry()
        dialog.resize(min(900, area.width() - 60), min(600, area.height() - 80))
        # Une fermeture immédiate doit arrêter aussi le rappel de traduction.
        translate = QTimer(dialog)
        translate.setSingleShot(True)
        translate.timeout.connect(lambda: franciser_selecteur(dialog))
        translate.start(0)
        try:
            if dialog.exec() == QDialog.Accepted:
                selected = dialog.selectedFiles()
                if selected:
                    return str(Path(selected[0]).resolve())
            return None
        finally:
            translate.stop()
            dialog.deleteLater()

    def _themed_save_dialog(self, saving):
        """Ouvrir le menu des emplacements et retourner le chemin choisi ou lancer une création."""
        dialog = SaveSlotsDialog(SAVES_DIR, saving, self)
        accepted = dialog.exec() == QDialog.Accepted
        path = dialog.selected_path if accepted else None
        new_game = accepted and dialog.new_game_requested
        dialog.deleteLater()
        if new_game:
            self._start_new_game()
        return path

    def save_game(self):
        """Choisir un emplacement puis écrire atomiquement la partie ou signaler l’erreur."""
        if self.current_paragraph is None:
            QMessageBox.information(self, 'Aventure à commencer',
                                    'Inscrivez le nom de votre aventurier et commencez l’aventure avant de sauvegarder.')
            return
        path = self._themed_save_dialog(saving=True)
        if not path:
            return
        data = self._save_data()
        try:
            self._write_atomic(path, data)
            QMessageBox.information(self, "Sauvegarde", "Partie sauvegardée.")
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))

    def load_game(self, path=None, *, announce=True):
        """Valider le format, le chemin portable et l’empreinte du PDF avant restauration.

        Recharger texte et catalogues depuis le livre puis restaurer l’état et les piles
        d’historique sans rejouer ses effets. announce contrôle l’affichage des erreurs."""
        self.intro_music.menu()
        if not isinstance(path, (str, Path)):
            path = self._themed_save_dialog(saving=False)
        if not path:
            if self.current_paragraph is not None:
                self.intro_music.fade_out()
            return
        try:
            data = read_save(Path(path))
            pdf_reference = data['pdf_path']
            pdf = resolve_book_reference(pdf_reference)
            if pdf:
                expected = data['pdf_sha256']
                if expected and expected != self._pdf_hash(pdf):
                    raise ValueError("Le PDF a changé depuis la sauvegarde.")
                book_module = module_for_pdf(pdf)
                saved_module = data.get('module_id')
                if saved_module is not None and (book_module is None or saved_module != book_module.id):
                    raise ValueError("Le module de cette sauvegarde ne correspond pas au grimoire.")
                paragraphs = extract_paragraphs(pdf)
                illustration_catalogue = book_module.catalogue('illustrations') if book_module else None
                self.pdf_path = pdf
                self.paragraphs = paragraphs
                self.illustration_catalogue = illustration_catalogue
                self.book_module = book_module
                self.book_event_catalogue = book_module.catalogue('events') if book_module else None
                self.book_label.setText(Path(pdf).name)
                if self.paragraphs:
                    self.goto_spin.setMaximum(max(self.paragraphs))
            elif pdf_reference:
                raise ValueError('Le grimoire de cette sauvegarde est introuvable dans donnees/grimoires.')
            self._restore(data)
            self.action_history = data['action_history']
            self.undo_stack = [(label, state) for label, state in data['undo_stack']]
            self.redo_stack = [(label, state) for label, state in data['redo_stack']]
            self._update_history_controls()
            self._remember_book()
            self.intro_music.fade_out()
            if announce:
                QMessageBox.information(self, "Chargement", "Partie chargée.")
            return True
        except Exception as exc:
            if self.current_paragraph is not None:
                self.intro_music.fade_out()
            if announce:
                QMessageBox.critical(self, "Chargement impossible", str(exc))
            return False


def _track_action(method, label):
    """Envelopper une méthode pour regrouper ses mutations imbriquées en une action.

    Seul le niveau extérieur capture et enregistre l’état ; _action_depth est remis
    en place dans finally. La restauration court-circuite cet enregistrement."""
    def wrapped(self, *args, **kwargs):
        """Capturer l’action extérieure et terminer ses règles de combat avant enregistrement.

        Le finally rétablit la profondeur même en cas d’erreur et enregistre l’état
        effectivement atteint ; ce mécanisme est un historique, pas un rollback sur exception."""
        if self._restoring:
            return method(self, *args, **kwargs)
        depth = getattr(self, "_action_depth", 0)
        if depth == 0:
            self._feedback_action_id += 1
        before = self._snapshot() if depth == 0 else None
        combat_paragraph = self.current_paragraph
        self._action_depth = depth + 1
        try:
            result = method(self, *args, **kwargs)
            if method.__name__ == "combat_round" and depth == 0:
                if self._book_round_played:
                    self._finish_complex_round(combat_paragraph)
                self._finish_crocodile_round()
                self._finish_piranha_round()
                current = verified_entry(self.book_event_catalogue, self.current_paragraph)
                if (current and "escape_target" in current.get("combat", {})
                        and self.current_paragraph in self.paragraphs):
                    self._render_choices_and_events(self.paragraphs[self.current_paragraph])
            return result
        finally:
            self._action_depth -= 1
            if depth == 0:
                self._record(label, before)
    return wrapped

# Registre des mutations suivies. Ajouter ici une nouvelle commande de jeu
# publique si elle doit être annulable et autosauvegardée. Ne pas y ajouter les
# simples rafraîchissements visuels ni Undo/Redo, qui gèrent leurs propres piles.
for _name, _label in {
    'use_care': 'Utiliser un soin',
    "go_to": "Changer de paragraphe", "apply_detected_event": "Appliquer un événement",
    "perform_book_action": "Résoudre une action du livre",
    "resolve_book_roll": "Résoudre une épreuve du livre",
    "escape_scripted_combat": "Fuir un combat du livre",
    "choose_crocodile_strategy": "Choisir une stratégie contre le Crocodile",
    "roll_piranha_target": "Déterminer la cible des Piranhas",
    "apply_optional_book_event": "Choisir une récompense du livre",
    "test_luck": "Tenter sa Chance",
    "eat_meal": "Prendre un repas", "eat_shared_meal": "Partager un repas",
    "drink_potion": "Boire une potion",
    "combat_round": "Assaut de combat", "add_item": "Ajouter un objet",
    "remove_item": "Retirer un objet",
    "change_weapon": "Changer d'arme",
    "change_shield_use": "Utiliser le bouclier",
    "take_book_shield": "Prendre le bouclier",
    "take_book_trade": "Échanger un équipement du livre",
    "throw_book_diversion": "Jeter un objet pour détourner l'Ogre",
    "take_enchanted_meal": "Manger au banc enchanté",
    "follow_catalogue_choice": "Suivre un itinéraire vérifié"
}.items():
    setattr(MainWindow, _name, _track_action(getattr(MainWindow, _name), _label))


def main():
    """Créer QApplication, les traductions et la fenêtre puis lancer la boucle Qt.

    Les répertoires portables et l’identité sont préparés avant l’affichage ; garder
    les traducteurs et le filtre de dialogues vivants pendant toute la session."""
    init_portable_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Bifurk")
    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    app._bifurk_translators = []
    for catalog in ("qtbase_fr", "qt_fr"):
        translator = QTranslator(app)
        search_paths = [APP_DIR / "translations", Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))]
        for folder in search_paths:
            if translator.load(catalog, str(folder)):
                app.installTranslator(translator)
                app._bifurk_translators.append(translator)
                break
    app.setWindowIcon(QIcon(str(ASSET_DIR / "bifurk.ico")))
    window = MainWindow(startup=True)
    app.setStyleSheet(window.styleSheet())
    app._bifurk_dialog_filter = DialogThemeFilter(app)
    app.installEventFilter(app._bifurk_dialog_filter)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
