import sys, re, json, random, copy, os, tempfile, hashlib, shutil
from pathlib import Path
from rules_engine import encounters, combat_hints, stat_events, item_hints
from navigation import destinations, render_links
from illustrations import catalogue_for_pdf, images_for_paragraph, cover
from book_events import load_book_events, apply_entry, apply_option, verified_entry, apply_effects, resolve_roll, available_routes, flee_available, escape_damage, available_options, equipped_weapon, equip_weapon, combat_skill, take_moon_shield, shield_damage, SHIELD_NAME, piranha_stamina
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, QTranslator, QLibraryInfo, QLocale
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor, QPixmap, QImage, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTextBrowser, QSpinBox,
    QGroupBox, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QCheckBox, QSplitter, QComboBox, QDialog, QDialogButtonBox, QScrollArea, QFrame, QProgressBar)

APP_NAME = "Bifurk — 1.0.13"
# Répertoire portable : à côté de l'exécutable empaqueté ou du script.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets"
DATA_DIR = APP_DIR / "donnees"
SAVES_DIR = DATA_DIR / "sauvegardes"
BOOKS_DIR = DATA_DIR / "grimoires"
SETTINGS_DIR = DATA_DIR / "parametres"


def init_portable_dirs():
    for directory in (SAVES_DIR, BOOKS_DIR, SETTINGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def within_directory(path, directory):
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False


def import_book(source):
    """Copie le grimoire dans le dossier portable sans écrire à la source."""
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
    """Accepte les anciennes sauvegardes et migre les grimoires externes."""
    if not reference:
        return None
    candidate = Path(reference)
    if not candidate.is_absolute():
        candidate = APP_DIR / candidate
    if not candidate.is_file():
        # Une sauvegarde déplacée peut encore retrouver son livre via son nom.
        candidate = BOOKS_DIR / Path(reference).name
    if not candidate.is_file():
        return None
    return import_book(candidate)



def extract_paragraphs(pdf_path):
    """Extract numbered paragraphs from a text-based PDF using PyMuPDF."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF n'est pas installé. Lancez : pip install PyMuPDF") from exc
    doc = fitz.open(pdf_path)
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
    # Drop empty sections and likely front matter sections without content.
    return {n: t for n, t in paragraphs.items() if t}


def franciser_message(dialog):
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
    """Traduction de secours pour les infobulles du sélecteur Qt."""
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
    """Applique la barre bronze aux fenêtres secondaires Windows dès leur ouverture."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QDialog):
            QTimer.singleShot(0, lambda d=obj: set_bronze_titlebar(d) if d.isVisible() else None)
            if isinstance(obj, QMessageBox):
                QTimer.singleShot(0, lambda d=obj: franciser_message(d) if d.isVisible() else None)
        return False


def set_bronze_titlebar(widget):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        for attribute, value in ((35, 0x001B2D4B), (36, 0x00BEE1F2)):
            color = ctypes.c_uint32(value)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(color), ctypes.sizeof(color))
    except Exception:
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(ASSET_DIR / "bifurk.ico")))
        self._fullscreen = False
        self.resize(1380, 850)
        self.setMinimumSize(930, 650)
        self.pdf_path = None
        self.illustration_catalogue = None
        self.book_event_catalogue = None
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self.paragraphs = {}
        self.current_paragraph = None
        self.visited_paragraphs = []
        self.transitions = []
        self.character = {
            "habilete": 8, "endurance": 20, "chance": 8,
            "provisions": 10, "gold": 1, "inventory": ["Épée", "Armure de cuir", "Lanterne"],
            "locked_items": [],
            "potion": "Aucune", "potion_doses": 0,
            "initial": {"habilete": 8, "endurance": 20, "chance": 8}
        }
        self.undo_stack = []
        self.redo_stack = []
        self.action_history = []
        self._restoring = False
        self.reader_font_size = 20
        self._load_fonts()
        self._build_ui()
        self._set_theme()
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self._refresh_character()
        self._show_welcome()

    def toggle_fullscreen(self):
        """Basculer entre plein écran immersif et fenêtre normale."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._update_fullscreen_button()

    def _update_fullscreen_button(self):
        self._fullscreen = self.isFullScreen()
        if hasattr(self, "fullscreen_btn"):
            self.fullscreen_btn.setText("▣  Quitter plein écran" if self._fullscreen else "⛶  Plein écran")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self._update_fullscreen_button()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._update_fullscreen_button()

    def showEvent(self, event):
        super().showEvent(event)
        self._set_windows_titlebar_color()

    def _set_windows_titlebar_color(self):
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
        self.reader_font_size = max(14, min(34, self.reader_font_size + delta))
        if self.current_paragraph in self.paragraphs:
            scroll_position = self.reader.verticalScrollBar().value()
            self._render_paragraph_text(self.paragraphs[self.current_paragraph])
            self.reader.verticalScrollBar().setValue(scroll_position)
        else:
            self._show_welcome()
        self.font_size_label.setText(f"{self.reader_font_size} pt")

    def _render_paragraph_text(self, text):
        escaped = render_links(text, self.paragraphs)
        # Liens bleu nuit soulignés : contraste élevé sur le parchemin clair.
        content = (f'<div style="font-family: \'{self.reading_font_family}\'; '
                   f'font-size: {self.reader_font_size}pt; color: #30241b; line-height: 1.55;">'
                   f'<p>{escaped}</p></div>')
        self.reader.setHtml(content)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 15, 20, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("⚜  B I F U R K")
        title.setObjectName("appTitle")
        header.addWidget(title)
        subtitle = QLabel("CHRONIQUES D’AVENTURE")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle)
        header.addStretch()
        self.book_label = QLabel("Aucun livre chargé")
        self.book_label.setObjectName("muted")
        header.addWidget(self.book_label)
        self.open_btn = QPushButton("✦  Ouvrir un grimoire…")
        self.open_btn.setObjectName("goldButton")
        self.open_btn.clicked.connect(self.open_pdf)
        header.addWidget(self.open_btn)
        self.fullscreen_btn = QPushButton("⛶  Plein écran")
        self.fullscreen_btn.setToolTip("Plein écran (F11) — Échap pour quitter")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        header.addWidget(self.fullscreen_btn)
        root.addLayout(header)
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
        map_btn = QPushButton("🗺 Carte d’exploration")
        map_btn.clicked.connect(self.show_map)
        history_bar.addWidget(map_btn)
        root.addLayout(history_bar)
        self._update_history_controls()

        splitter = QSplitter(Qt.Horizontal)
        reader_panel = QWidget()
        reader_panel.setObjectName("readerPanel")
        reader_layout = QVBoxLayout(reader_panel)
        reader_layout.setContentsMargins(0, 0, 8, 0)
        self.paragraph_title = QLabel("Bienvenue")
        self.paragraph_title.setObjectName("sectionTitle")
        title_row = QHBoxLayout()
        title_row.addWidget(self.paragraph_title)
        title_row.addStretch()
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
        cover_button = QPushButton("◈  Couverture")
        cover_button.clicked.connect(self.show_cover)
        reader_layout.addWidget(cover_button)
        self.reader = QTextBrowser()
        self.reader.setOpenExternalLinks(False)
        self.reader.anchorClicked.connect(self.follow_link)
        self.reader.setObjectName("reader")
        reader_layout.addWidget(self.reader, 1)
        self.illustration_button = QPushButton("🖼  Voir l’illustration du paragraphe")
        self.illustration_button.clicked.connect(self.show_paragraph_illustration)
        self.illustration_button.hide()
        reader_layout.addWidget(self.illustration_button)

        self.choice_group = QGroupBox("⚜  LES VOIES DU DESTIN")
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

        nav = QHBoxLayout()
        nav.addWidget(QLabel("Aller au paragraphe"))
        self.goto_spin = QSpinBox()
        self.goto_spin.setRange(1, 999)
        nav.addWidget(self.goto_spin)
        go_btn = QPushButton("Voyager →")
        go_btn.clicked.connect(lambda: self.go_to(self.goto_spin.value()))
        nav.addWidget(go_btn)
        nav.addStretch()
        reader_layout.addLayout(nav)
        splitter.addWidget(reader_panel)

        side = QWidget()
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 8, 12, 12)
        side_layout.setSpacing(14)

        stats_group = QGroupBox("⚔  FEUILLE D’AVENTURIER")
        stats_grid = QGridLayout(stats_group)
        self.stat_spins = {}
        stats = [("HABILETÉ", "habilete"), ("ENDURANCE", "endurance"), ("CHANCE", "chance"), ("Provisions", "provisions"), ("Pièces d'or", "gold")]
        for row, (label, key) in enumerate(stats):
            stats_grid.addWidget(QLabel(label), row, 0)
            spin = QSpinBox()
            spin.setRange(0, 999)
            spin.valueChanged.connect(lambda value, k=key: self.set_stat(k, value))
            self.stat_spins[key] = spin
            stats_grid.addWidget(spin, row, 1)
        stats_grid.addWidget(QLabel("Potion"), 5, 0)
        self.potion_combo = QComboBox()
        self.potion_combo.addItems(["Aucune", "Potion d'Adresse", "Potion de Vigueur", "Potion de Bonne Fortune"])
        self.potion_combo.currentTextChanged.connect(self.change_potion)
        stats_grid.addWidget(self.potion_combo, 5, 1)
        self.stat_bars = {}
        for key, label in (("endurance", "Vitalité"), ("chance", "Fortune"), ("habilete", "Maîtrise")):
            bar = QProgressBar()
            bar.setObjectName("statBar")
            bar.setRange(0, 100)
            bar.setFormat(label + "  %v %")
            bar.setTextVisible(True)
            self.stat_bars[key] = bar
            stats_grid.addWidget(bar, stats_grid.rowCount(), 0, 1, 2)
        self.initial_label = QLabel("Valeurs de départ : —")
        self.initial_label.setObjectName("initialStats")
        self.initial_label.setWordWrap(True)
        stats_grid.addWidget(self.initial_label, stats_grid.rowCount(), 0, 1, 2)
        side_layout.addWidget(stats_group)

        inv_group = QGroupBox("✦  SACOCHE & TRÉSORS")
        inv_layout = QVBoxLayout(inv_group)
        self.inventory_list = QListWidget()
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
        inv_layout.addLayout(inv_row)
        self.equipment_label = QLabel("⚔  Arme : Épée     ◈  Protection : Armure de cuir")
        self.equipment_label.setWordWrap(True)
        self.equipment_label.setObjectName("equipment")
        inv_layout.insertWidget(0, self.equipment_label)
        self.weapon_combo = QComboBox()
        self.weapon_combo.currentTextChanged.connect(self.change_weapon)
        inv_layout.insertWidget(1, self.weapon_combo)
        self.shield_check = QCheckBox("Utiliser le bouclier au croissant")
        self.shield_check.toggled.connect(self.change_shield_use)
        inv_layout.insertWidget(2, self.shield_check)
        side_layout.addWidget(inv_group, 1)

        dice_group = QGroupBox("⚄  DÉS DU DESTIN")
        dice_layout = QVBoxLayout(dice_group)
        dice_row = QHBoxLayout()
        self.dice_combo = QComboBox()
        self.dice_combo.addItems(["1d6", "2d6", "3d6", "1d20"])
        dice_row.addWidget(self.dice_combo)
        roll_btn = QPushButton("Lancer")
        roll_btn.clicked.connect(self.roll_dice)
        dice_row.addWidget(roll_btn)
        dice_layout.addLayout(dice_row)
        self.dice_result = QLabel("Résultat : —")
        self.dice_result.setObjectName("diceResult")
        dice_layout.addWidget(self.dice_result)
        self.dice_faces = QLabel("⚀   ⚀")
        self.dice_faces.setAlignment(Qt.AlignCenter)
        self.dice_faces.setObjectName("diceFaces")
        dice_layout.addWidget(self.dice_faces)
        self.dice_history = QListWidget()
        self.dice_history.setMaximumHeight(110)
        dice_layout.addWidget(self.dice_history)
        side_layout.addWidget(dice_group)

        rules_group = QGroupBox("⚔  ÉPREUVES & COMBATS")
        rules_layout = QVBoxLayout(rules_group)
        create_btn = QPushButton("Créer / relancer le personnage (1d6+6, 2d6+12, 1d6+6)")
        create_btn.clicked.connect(self.create_character)
        rules_layout.addWidget(create_btn)

        luck_row = QHBoxLayout()
        luck_btn = QPushButton("Tenter sa Chance (2d6)")
        luck_btn.clicked.connect(self.test_luck)
        luck_row.addWidget(luck_btn)
        eat_btn = QPushButton("Prendre un repas (+4 Endurance)")
        eat_btn.clicked.connect(self.eat_meal)
        luck_row.addWidget(eat_btn)
        potion_btn = QPushButton("Boire une dose de potion")
        potion_btn.clicked.connect(self.drink_potion)
        luck_row.addWidget(potion_btn)
        rules_layout.addLayout(luck_row)

        combat_grid = QGridLayout()
        combat_grid.addWidget(QLabel("Monstre"), 0, 0, 1, 2)
        self.enemy_name = QLineEdit("Monstre")
        combat_grid.addWidget(self.enemy_name, 0, 2, 1, 2)
        combat_grid.addWidget(QLabel("Habileté"), 1, 0)
        self.enemy_skill = QSpinBox(); self.enemy_skill.setRange(0, 99); self.enemy_skill.setValue(7)
        combat_grid.addWidget(self.enemy_skill, 1, 1)
        combat_grid.addWidget(QLabel("Endurance"), 1, 2)
        self.enemy_endurance = QSpinBox(); self.enemy_endurance.setRange(0, 999); self.enemy_endurance.setValue(6)
        combat_grid.addWidget(self.enemy_endurance, 1, 3)
        rules_layout.addLayout(combat_grid)
        combat_btn = QPushButton("Résoudre un assaut")
        combat_btn.clicked.connect(self.combat_round)
        rules_layout.addWidget(combat_btn)
        self.rules_log = QLabel("Règles : créez un personnage, puis testez la Chance ou un combat.")
        self.rules_log.setWordWrap(True)
        self.rules_log.setObjectName("muted")
        rules_layout.addWidget(self.rules_log)
        self.combat_state = QLabel("⚔  Aucun combat engagé")
        self.combat_state.setObjectName("combatState")
        self.combat_state.setWordWrap(True)
        rules_layout.insertWidget(rules_layout.count()-1, self.combat_state)
        self.combat_journal = QListWidget()
        self.combat_journal.setObjectName("combatJournal")
        self.combat_journal.setMaximumHeight(135)
        rules_layout.addWidget(QLabel("CHRONIQUE DES ASSAUTS"))
        rules_layout.addWidget(self.combat_journal)
        side_layout.addWidget(rules_group)

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
        splitter.setSizes([810, 480])
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _set_theme(self):
        parchment = (ASSET_DIR / "parchment.jpg").as_posix()
        leather = (ASSET_DIR / "leather.jpg").as_posix()
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #241d18; color: #e9d6b3; font-family: 'Lato'; font-size: 13px; }
            QMainWindow { background-image: url('LEATHER'); }
            QLabel { background: transparent; }
            QLabel#appTitle { color: #edcb87; font-family: Lato; font-size: 29px; font-weight: bold; }
            QLabel#subtitle { color: #aa8b5a; font-size: 10px; letter-spacing: 2px; }
            QLabel#sectionTitle { color: #f0d39a; font-size: 25px; font-weight: bold; padding: 6px 2px; }
            QLabel#muted { color: #bca98b; }
            QWidget#readerPanel, QWidget#sidePanel { background: transparent; }
            QGroupBox { background-color: #30251d; border: 1px solid #79603b; border-radius: 7px;
                margin-top: 17px; padding: 13px 9px 9px; font-weight: bold; color: #e9c989; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; background: #30251d; }
            QPushButton { background-color: #4a3527; color: #f1dcaf; border: 1px solid #9b7948;
                border-radius: 5px; padding: 9px 12px; font-family: Lato; font-weight: bold; }
            QPushButton:hover { background-color: #705038; border-color: #e1bc75; }
            QPushButton:pressed { background-color: #38291f; }
            QPushButton:disabled { color: #897963; border-color: #514537; }
            QPushButton#goldButton { background-color: #a27a3f; color: #21170f; border: 1px solid #e0b975; }
            QPushButton#goldButton:hover { background-color: #c59a53; }
            QSpinBox, QLineEdit, QComboBox { background: #e6d0a5; color: #35251a; border: 1px solid #9d784b;
                border-radius: 4px; padding: 6px; selection-background-color: #9a723c; }
            QSpinBox::up-button, QSpinBox::down-button { width: 17px; }
            QListWidget { background-color: #e8d7b4; color: #3a291c; border: 1px solid #95744a;
                border-radius: 4px; padding: 4px; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background: #a47a42; color: #fff4d8; }
            QTextBrowser#reader { background-color: #e8d0a2; background-image: url('PARCHMENT');
                color: #34251b; border: 5px double #806039; border-radius: 3px;
                padding: 28px 33px; font-family: "EB Garamond"; font-size: 20px; }
            QTextBrowser#reader QScrollBar { background: #cfb383; }
            QLabel#diceResult { color: #f6d58d; font-size: 19px; font-weight: bold; }
            QLabel#diceFaces { font-size: 43px; color: #e9cb8b; padding: 5px; }
            QLabel#equipment { background: #4b3727; color: #e8c88d; padding: 11px; border: 1px solid #987648; border-radius: 5px; }
            QLabel#initialStats { color: #c9b08a; font-size: 11px; }
            QLabel#combatState { background: #49301f; color: #f1d59b; padding: 9px; border: 1px solid #aa7b43; border-radius: 5px; }
            QProgressBar#statBar { border: 1px solid #8b6b44; border-radius: 5px; background: #1f1915; color: #fff0ce; height: 20px; text-align: center; font-weight: bold; }
            QProgressBar#statBar::chunk { background: #a17c45; border-radius: 4px; }
            QListWidget#combatJournal { background: #d9c59e; color: #38271a; }

            QScrollArea#sideScroll { background: transparent; border: none; }
            QScrollBar:vertical { background: #30261f; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #82623d; border-radius: 5px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QSplitter::handle { background: #79603b; width: 3px; }
            QDialog, QMessageBox, QFileDialog { background-color: #2b211a; color: #f1d9ac; }
            QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel { color: #f0dbb6; background: transparent; }
            QDialog QPushButton, QMessageBox QPushButton { min-width: 85px; }
            QDialog QTextBrowser { background-color: #e8d0a2; background-image: url('PARCHMENT');
                color: #34251b; border: 3px double #806039; padding: 12px;
                font-family: 'EB Garamond'; font-size: 17px; }
            QDialog QScrollArea { background: #2b211a; border: none; }
            QDialog QDialogButtonBox { background: transparent; }
            QFileDialog QTreeView, QFileDialog QListView, QFileDialog QTableView {
                background-color: #e8d0a2; color: #30241b;
                alternate-background-color: #dcc39a; selection-background-color: #967044;
                selection-color: #fff2d8; border: 1px solid #947143;
            }
            QFileDialog QHeaderView::section { background: #4a3527; color: #f1dcaf;
                border: 1px solid #9b7948; padding: 5px; }
            QFileDialog QLineEdit, QFileDialog QComboBox { background: #e8d0a2; color: #30241b;
                border: 1px solid #9b7948; padding: 5px; }
            QFileDialog QToolButton { background: #4a3527; color: #f1dcaf;
                border: 1px solid #9b7948; border-radius: 4px; padding: 5px; }
            QFileDialog QToolButton:hover { background: #705038; }
            QFileDialog QScrollBar:horizontal { background: #30261f; height: 12px; }
            QFileDialog QScrollBar::handle:horizontal { background: #82623d; border-radius: 5px; }
            QFileDialog QSplitter::handle { background: #79603b; }
            QDialog#illustrationDialog { background-color: #30231a; }
            QDialog QLabel#illustrationImage { background: #e8d0a2; border: 5px double #a37a43; padding: 4px; }
            QDialog QLabel#illustrationStatus { color: #cdb58b; font-size: 11px; }
            QMessageBox QLabel#qt_msgbox_label { color: #f0dbb6; font-size: 14px; }
            QMessageBox QLabel#qt_msgboxex_icon_label { background: transparent; }
        """.replace('PARCHMENT', parchment).replace('LEATHER', leather).replace("EB Garamond", self.reading_font_family).replace("Lato", self.ui_font_family))

    def _show_welcome(self):
        self.reader.setHtml("<h2>Bienvenue, aventurier.</h2><p>Importez le PDF de votre livre pour commencer.</p><p>Bifurk affiche les destinations détectées sous forme de choix cliquables et propose des événements simples à confirmer. Les PDF scannés nécessitant de l'OCR ne sont pas pris en charge.</p>")

    def open_pdf(self):
        path = self._themed_file_dialog(kind="pdf")
        if not path:
            return
        try:
            paragraphs = extract_paragraphs(path)
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
        self.pdf_path = path
        self.illustration_catalogue = catalogue_for_pdf(path)
        self.book_event_catalogue = load_book_events(path)
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self.paragraphs = paragraphs
        if self.illustration_catalogue is None:
            QMessageBox.information(self, "Illustrations", "Ce PDF ne correspond pas exactement à l’édition cataloguée. Les illustrations automatiques sont désactivées pour éviter les mauvaises associations.")
        else:
            self.show_cover()
        self.book_label.setText(Path(path).name)
        self.goto_spin.setMaximum(max(paragraphs))
        first = 1 if 1 in paragraphs else min(paragraphs)
        self.transitions = []
        self.visited_paragraphs = []
        self.undo_stack.clear(); self.redo_stack.clear()
        self._update_history_controls()
        self.go_to(first)

    def _clear_dynamic_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
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
                clause = f"Continuer vers le paragraphe {target}"
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

    def _render_choices_and_events(self, text):
        self._clear_dynamic_layout(self.choice_layout)
        choices = self._paragraph_choices(text)
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        escape_target = entry.get("combat", {}).get("escape_target") if entry else None
        if entry and "routes" in entry:
            # Ne présenter que les chemins permis par les objets et ressources actuels.
            choices = [{"target": route["target"], "label": route["label"]}
                       for route in available_routes(self.character, entry)]
        if escape_target is not None:
            # La sortie par la fuite est exclusivement proposée avec sa pénalité.
            choices = [c for c in choices if c["target"] != escape_target]
        if not choices:
            self.choice_layout.addWidget(QLabel("Aucune destination explicite détectée dans ce paragraphe."))
        else:
            for choice in choices:
                target = choice["target"]
                button = QPushButton(f"{choice['label']}  →  §{target}")
                button.setToolTip(f"Ouvrir le paragraphe {target}")
                button.setEnabled(target in self.paragraphs)
                button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
                self.choice_layout.addWidget(button)
                if target not in self.paragraphs:
                    button.setToolTip(f"Destination {target} non détectée dans le PDF importé")
        self._render_conditions(text)
        self._clear_dynamic_layout(self.event_layout)
        scripted = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if scripted:
            notice = QLabel("✦ Événement du livre vérifié : " + scripted["note"])
            notice.setWordWrap(True)
            self.event_layout.addWidget(notice)
            if scripted["mode"] == "automatique":
                self.event_layout.addWidget(QLabel("Effets obligatoires appliqués une fois par partie."))
            if scripted.get("shield_pickup") and SHIELD_NAME not in self.character.get("inventory", []):
                btn = QPushButton("Prendre le bouclier (abandonner un objet)")
                btn.clicked.connect(lambda checked=False: self.take_book_shield())
                self.event_layout.addWidget(btn)
            for option in available_options(self.character, scripted,
                                            self.completed_optional_events,
                                            self.current_paragraph):
                button = QPushButton(option["label"])
                button.clicked.connect(lambda checked=False, n=self.current_paragraph, oid=option["id"]: self.apply_optional_book_event(n, oid))
                self.event_layout.addWidget(button)
            if scripted["mode"] in ("des", "des_optionnel") and "roll" in scripted:
                button = QPushButton("🎲 Lancer le dé et appliquer le résultat vérifié")
                button.setEnabled(self.current_paragraph not in self.completed_book_events)
                button.clicked.connect(lambda checked=False, n=self.current_paragraph: self.resolve_book_roll(n))
                self.event_layout.addWidget(button)
                return
            if scripted["mode"] in ("automatique", "conditionnel") and (
                    scripted["mode"] == "automatique" or scripted.get("options")):
                return
            # Les combats complexes conservent les commandes habituelles :
            # aucune prise en charge complète n'est encore garantie.
        state = self.crocodile_combat
        if (state and self.current_paragraph == 86 and state["phase"] == "initial"
                and state["assaults"] >= 2 and self.enemy_endurance.value() > 0):
            continue_btn = QPushButton("Continuer le combat contre le Crocodile")
            continue_btn.clicked.connect(lambda checked=False: self.choose_crocodile_strategy("continue"))
            self.event_layout.addWidget(continue_btn)
            diversion_btn = QPushButton("Faire un dernier assaut puis rejoindre le §350")
            diversion_btn.clicked.connect(lambda checked=False: self.choose_crocodile_strategy("diversion"))
            self.event_layout.addWidget(diversion_btn)
        if escape_target is not None:
            combat_rules = entry["combat"]
            permitted = flee_available(combat_rules, self.book_combat_assaults.get(self.current_paragraph, 0),
                                       self.enemy_endurance.value(), self.character["endurance"])
            btn = QPushButton(f"Fuir le combat (pénalité obligatoire) → §{escape_target}")
            btn.setEnabled(permitted and escape_target in self.paragraphs)
            btn.clicked.connect(lambda checked=False, n=self.current_paragraph: self.escape_scripted_combat(n))
            self.event_layout.addWidget(btn)
        monsters = encounters(text)
        if monsters:
            self.event_layout.addWidget(QLabel("⚔ Rencontres détectées (à confirmer)"))
            for monster in monsters:
                button = QPushButton(f"Préparer le combat : {monster['name']} · H {monster['skill']} / E {monster['stamina']}")
                button.clicked.connect(lambda checked=False, m=monster: self.prepare_encounter(m))
                self.event_layout.addWidget(button)
        combat = combat_hints(text)
        if combat['cues']:
            note = QLabel('⚔ Indices de combat : ' + ' · '.join(combat['cues']))
            note.setWordWrap(True)
            self.event_layout.addWidget(note)
        if len(monsters) > 1:
            note = QLabel('Plusieurs adversaires détectés : préparez-les séparément. L’ordre et les règles spéciales doivent être vérifiés dans le livre.')
            note.setWordWrap(True)
            self.event_layout.addWidget(note)
        for label, target in combat['exits']:
            if target == escape_target:
                continue  # Ne pas créer un lien de fuite sans pénalité.
            button = QPushButton(f'Issue possible — {label} → §{target}')
            button.setEnabled(target in self.paragraphs)
            button.setToolTip('Vérifiez que cette issue est bien applicable avant de voyager.')
            button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
            self.event_layout.addWidget(button)
        for item in item_hints(text):
            button = QPushButton(f"Ajouter à l’inventaire (vérifier) : {item}")
            button.clicked.connect(lambda checked=False, name=item: self.confirm_item(name))
            self.event_layout.addWidget(button)
        events = self._paragraph_events(text) + stat_events(text)
        events = [e for i,e in enumerate(events) if not any(x['key']==e['key'] and x['amount']==e['amount'] for x in events[:i])]
        if not events:
            self.event_layout.addWidget(QLabel("Aucun événement simple reconnu. Les effets conditionnels restent manuels."))
        for event in events:
            amount = event["amount"]
            # Show an explicit confirmation before applying any extracted effect.
            button = QPushButton(f"Appliquer : {event['label']} ({amount:+d})")
            button.clicked.connect(lambda checked=False, e=event: self.apply_detected_event(e))
            self.event_layout.addWidget(button)

    def _render_conditions(self, text):
        """Show hints, never automatically block a path based on uncertain prose."""
        self._clear_dynamic_layout(self.condition_layout)
        pattern = re.compile(r"(?i)\bsi vous (?:êtes )?(?:en possession d[eu'’]|possédez|avez|disposez d[eu'’])\s+([^,.\n;:]{2,90})")
        matches = pattern.findall(text)
        if not matches:
            self.condition_layout.addWidget(QLabel("Aucune condition d’objet reconnue."))
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

    def show_map(self):
        if not self.paragraphs:
            QMessageBox.information(self, "Carte", "Importez d’abord un PDF.")
            return
        dialog = QDialog(self)
        dialog.setWindowIcon(self.windowIcon())
        dialog.setWindowTitle("Bifurk — Carte d’exploration")
        dialog.resize(680, 530)
        layout = QVBoxLayout(dialog)
        info = QLabel(f"{len(self.visited_paragraphs)} paragraphes visités · {len(self.transitions)} déplacements enregistrés. Cliquez sur un paragraphe visité pour y retourner.")
        info.setWordWrap(True)
        layout.addWidget(info)
        view = QTextBrowser()
        import html
        rows = []
        for number in self.visited_paragraphs:
            targets = [c['target'] for c in self._paragraph_choices(self.paragraphs.get(number, ''))]
            target_text = ', '.join(('✓ ' if n in self.visited_paragraphs else '○ ') + str(n) for n in targets) or 'aucune sortie détectée'
            rows.append(f'<p><b><a style="color: #123f70; text-decoration: underline; font-weight: bold;" href="paragraph:{number}">§ {number}</a></b> → {html.escape(target_text)}</p>')
        # Même bleu nuit, soulignement et contraste que les liens du livre.
        view.document().setDefaultStyleSheet("a:link { color: #123f70; text-decoration: underline; font-weight: bold; }")
        view.setHtml('<h2>Parcours découvert</h2>' + ''.join(rows))
        def navigate(url):
            m = re.search(r'(?:paragraph:|paragraph%3A)(\d+)', url.toString(), re.I)
            if m:
                self.go_to(int(m.group(1)))
                dialog.accept()
        view.anchorClicked.connect(navigate)
        layout.addWidget(view)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def prepare_encounter(self, monster):
        answer = QMessageBox.question(self, "Préparer une rencontre",
            f"Utiliser les caractéristiques de {monster['name']} ?\n"
            f"Habileté : {monster['skill']} — Endurance : {monster['stamina']}\n"
            "Vérifiez le paragraphe : les règles spéciales restent manuelles.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        self.enemy_name.setText(monster['name'])
        self.enemy_skill.setValue(monster['skill'])
        self.enemy_endurance.setValue(monster['stamina'])
        self.rules_log.setText(f"Rencontre préparée : {monster['name']}.")
        self.combat_state.setText(f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")
        self.combat_journal.clear()

    def confirm_item(self, name):
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
        if number != self.current_paragraph:
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
                or "roll" not in entry or number in self.completed_book_events):
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
        apply_effects(self.character, extra_effects)
        self._refresh_character()
        self.rules_log.setText(
            f"Épreuve §{number} : dés {rolls} = {total}{extra_text} ; destination §{outcome['target']}.")
        self.go_to(outcome["target"])

    def go_to(self, number):
        if number not in self.paragraphs:
            QMessageBox.information(self, "Paragraphe absent", f"Le paragraphe {number} n'a pas été détecté dans le PDF chargé.")
            return
        previous = self.current_paragraph
        if previous is not None and previous != number and not self._restoring:
            self.transitions.append([previous, number])
        self.current_paragraph = number
        if not self._restoring and apply_entry(self.character, self.completed_book_events, number, self.book_event_catalogue):
            self._refresh_character()
            self.rules_log.setText(f"Effets vérifiés appliqués automatiquement au paragraphe {number}.")
        if not self._restoring:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            opponents = combat.get("enemies", [])
            if (len(opponents) == 1 and not combat.get("mode")
                    and number not in self.prepared_book_encounters):
                opponent = opponents[0]
                self.enemy_name.setText(opponent["name"])
                self.enemy_skill.setValue(opponent["skill"])
                self.enemy_endurance.setValue(opponent["stamina"])
                self.prepared_book_encounters.add(number)
                self.combat_state.setText(
                    f"⚔ {opponent['name']} · H {opponent['skill']} · Endurance {opponent['stamina']}")
                self.combat_journal.clear()
        if not self._restoring and number == 86:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            if (combat.get("mode") == "limite_assauts" and self.crocodile_combat is None
                    and number not in self.prepared_book_encounters):
                self.crocodile_combat = {"paragraph": number, "assaults": 0,
                                         "phase": "initial", "wounded": False}
                self._set_book_enemy(combat["enemies"][0])
        if not self._restoring and number == 20:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            if (combat.get("mode") == "sequence" and len(combat.get("enemies", [])) > 1
                    and self.book_combat_sequence is None):
                self.book_combat_sequence = {"paragraph": number, "index": 0}
                self._set_book_enemy(combat["enemies"][0])
        if number not in self.visited_paragraphs:
            self.visited_paragraphs.append(number)
        self.goto_spin.setValue(number)
        self.paragraph_title.setText(f"Paragraphe {number}")
        text = self.paragraphs[number]
        # Utiliser le même détecteur pour les boutons ET les liens dans le texte.
        self._render_paragraph_text(text)
        self.illustration_button.setVisible(bool(self.illustration_catalogue and images_for_paragraph(self.illustration_catalogue, number)))
        self.reader.moveCursor(QTextCursor.Start)
        self._render_choices_and_events(text)
        if self.illustration_catalogue and images_for_paragraph(self.illustration_catalogue, number):
            self.show_paragraph_illustration()

    def _illustration_pixmap(self, entry, scale=2):
        import fitz
        with fitz.open(self.pdf_path) as doc:
            page = doc[entry["page_pdf"] - 1]
            clip = fitz.Rect(entry["rect"])
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            return QPixmap.fromImage(image.copy())

    def _show_illustration(self, entry, title):
        try:
            pixmap = self._illustration_pixmap(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Illustration", str(exc))
            return
        dialog = QDialog(self)
        dialog.setObjectName("illustrationDialog")
        dialog.setWindowIcon(self.windowIcon())
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        # Respecter la surface utile de l'écran, sans défilement horizontal.
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        max_width = max(320, available.width() - 90)
        max_height = max(260, available.height() - 150)
        displayed = pixmap.scaled(max_width - 44, max_height - 110,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label = QLabel()
        label.setObjectName("illustrationImage")
        label.setAlignment(Qt.AlignCenter)
        label.setPixmap(displayed)
        label.setFixedSize(displayed.size())
        layout.addWidget(label, alignment=Qt.AlignCenter)
        status = "association probable" if entry.get("statut") == "probable" else "association vérifiée par position" if entry.get("statut") == "verifie_position" else "association vérifiée"
        status_label = QLabel(f"Page PDF {entry['page_pdf']} · {status}")
        status_label.setObjectName("illustrationStatus")
        layout.addWidget(status_label)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.setFixedSize(min(max_width, displayed.width() + 54),
                            min(max_height, displayed.height() + 125))
        dialog.exec()

    def show_cover(self):
        if self.illustration_catalogue:
            entry = cover(self.illustration_catalogue)
            if entry:
                self._show_illustration(entry, "Couverture — Le Sorcier de la Montagne de Feu")

    def show_paragraph_illustration(self):
        if not self.illustration_catalogue:
            return
        entries = images_for_paragraph(self.illustration_catalogue, self.current_paragraph)
        for index, entry in enumerate(entries, 1):
            suffix = f" ({index}/{len(entries)})" if len(entries) > 1 else ""
            self._show_illustration(entry, f"Illustration — paragraphe {self.current_paragraph}{suffix}")

    def follow_link(self, url):
        value = url.toString()
        match = re.search(r"paragraph(?::|%3A)(\d+)", value, re.I)
        if not match:
            return
        target = int(match.group(1))
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if entry and target == entry.get("combat", {}).get("escape_target"):
            self.escape_scripted_combat(self.current_paragraph)
            return
        if entry and "routes" in entry:
            allowed = {route["target"] for route in available_routes(self.character, entry)}
            if target not in allowed:
                QMessageBox.information(self, "Chemin inaccessible",
                    "Les conditions de ce passage ne sont pas remplies.")
                return
        self.go_to(target)

    def _refresh_character(self):
        for key, spin in self.stat_spins.items():
            spin.blockSignals(True)
            spin.setValue(int(self.character.get(key, 0)))
            spin.blockSignals(False)
        self.potion_combo.blockSignals(True)
        self.potion_combo.setCurrentText(self.character.get("potion", "Aucune"))
        self.potion_combo.blockSignals(False)
        self.inventory_list.clear()
        self.inventory_list.addItems(self.character.get("inventory", []))
        self.shield_check.blockSignals(True)
        self.shield_check.setVisible(SHIELD_NAME in self.character.get("inventory", []))
        self.shield_check.setChecked(bool(self.character.get("shield_equipped", False)))
        self.shield_check.blockSignals(False)
        weapon = equipped_weapon(self.character)
        self.weapon_combo.blockSignals(True)
        self.weapon_combo.clear()
        self.weapon_combo.addItems([name for name in ("Épée", "Épée magique", "Épée trouvée dans la rivière")
                                    if name in self.character.get("inventory", [])])
        if weapon:
            self.weapon_combo.setCurrentText(weapon)
        self.weapon_combo.blockSignals(False)
        self.equipment_label.setText(
            f"⚔ Arme : {weapon or 'Aucune'}"
            + (" (+1 en combat)" if weapon == "Épée trouvée dans la rivière" else "")
            + "     ◈ Protection : Armure de cuir")
        initial = self.character.get("initial", {})
        for key, bar in self.stat_bars.items():
            maximum = max(1, int(initial.get(key, self.character.get(key, 1))))
            current = max(0, int(self.character.get(key, 0)))
            bar.setValue(min(100, round(100 * current / maximum)))
            bar.setFormat(f"{current} / {maximum}  •  {bar.value()} %")
        self.initial_label.setText("Départ  •  Habileté {habilete}  |  Endurance {endurance}  |  Chance {chance}".format(
            **{key: initial.get(key, "—") for key in ("habilete", "endurance", "chance")}))
        items = [str(item).casefold() for item in self.character.get("inventory", [])]
        weapon = next((item for item in self.character.get("inventory", []) if "épée" in str(item).casefold() or "hache" in str(item).casefold()), "—")
        armor = next((item for item in self.character.get("inventory", []) if "armure" in str(item).casefold() or "bouclier" in str(item).casefold()), "—")
        self.equipment_label.setText(f"⚔  Arme : {weapon}     ◈  Protection : {armor}")


    def _roll(self, count=1, sides=6):
        rolls = [random.randint(1, sides) for _ in range(count)]
        return rolls, sum(rolls)

    def create_character(self):
        _, skill_roll = self._roll(1)
        _, endurance_roll = self._roll(2)
        _, luck_roll = self._roll(1)
        self.character["initial"] = {"habilete": skill_roll + 6, "endurance": endurance_roll + 12, "chance": luck_roll + 6}
        for key, value in self.character["initial"].items():
            self.character[key] = value
        self.character["provisions"] = 10
        self.character["gold"] = 1
        self.character["equipped_weapon"] = "Épée"
        self.character["magic_sword_bonus_active"] = False
        self._refresh_character()
        self.rules_log.setText(f"Personnage créé : Habileté {skill_roll+6}, Endurance {endurance_roll+12}, Chance {luck_roll+6}.")

    def change_potion(self, value):
        self.character["potion"] = value
        self.character["potion_doses"] = 2 if value != "Aucune" else 0

    def test_luck(self):
        rolls, total = self._roll(2)
        lucky = total <= self.character["chance"]
        self.character["chance"] = max(0, self.character["chance"] - 1)
        self._refresh_character()
        verdict = "chanceux" if lucky else "malchanceux"
        self.rules_log.setText(f"Test de Chance : {rolls[0]} + {rolls[1]} = {total}. Vous êtes {verdict}. Chance -1.")

    def eat_meal(self):
        if self.character.get("provisions", 0) <= 0:
            self.rules_log.setText("Vous n'avez plus de provisions.")
            return
        current = self.character["endurance"]
        cap = self.character.get("initial", {}).get("endurance", current)
        self.character["endurance"] = min(cap, current + 4)
        self.character["provisions"] -= 1
        self._refresh_character()
        self.rules_log.setText(f"Repas consommé : Endurance {current} → {self.character['endurance']} (maximum {cap}). Provisions -1.")

    def drink_potion(self):
        potion = self.character.get("potion", "Aucune")
        doses = self.character.get("potion_doses", 0)
        if potion == "Aucune" or doses <= 0:
            self.rules_log.setText("Aucune dose de potion disponible.")
            return
        initial = self.character.get("initial", {})
        if potion == "Potion d'Adresse":
            key, label = "habilete", "Habileté"
            target = initial.get(key, self.character[key])
        elif potion == "Potion de Vigueur":
            key, label = "endurance", "Endurance"
            target = initial.get(key, self.character[key])
        else:
            key, label = "chance", "Chance"
            target = initial.get(key, self.character[key]) + 1
            initial[key] = target
            self.character["initial"] = initial
        old = self.character[key]
        self.character[key] = target
        self.character["potion_doses"] = doses - 1
        self._refresh_character()
        self.rules_log.setText(f"Potion utilisée : {label} {old} → {target}. Doses restantes : {doses-1}.")

    def _log_assault(self, player_rolls, enemy_rolls, player_attack, enemy_attack, outcome):
        if (self.crocodile_combat
                and self.current_paragraph == self.crocodile_combat["paragraph"]):
            self.crocodile_combat["assaults"] += 1
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if entry and "escape_target" in entry.get("combat", {}):
            number = self.current_paragraph
            self.book_combat_assaults[number] = self.book_combat_assaults.get(number, 0) + 1
        self.combat_journal.insertItem(0, f"Vous {player_rolls} = {player_attack} | Ennemi {enemy_rolls} = {enemy_attack} | {outcome}")
        self.combat_state.setText(f"⚔  {self.enemy_name.text()} • Endurance {self.enemy_endurance.value()} | Héros {self.character['endurance']}")
        while self.combat_journal.count() > 60:
            self.combat_journal.takeItem(self.combat_journal.count() - 1)

    def _set_book_enemy(self, monster):
        """Initialise un adversaire vérifié sans changer les données du héros."""
        self.enemy_name.setText(monster["name"])
        self.enemy_skill.setValue(monster["skill"])
        self.enemy_endurance.setValue(monster["stamina"])
        self.combat_state.setText(
            f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")

    def _advance_scripted_sequence(self):
        """Après la victoire, prépare le suivant ; à la fin, va à la sortie prescrite."""
        state = self.book_combat_sequence
        if (not state or self.current_paragraph != state["paragraph"]
                or self.enemy_endurance.value() > 0):
            return
        entry = verified_entry(self.book_event_catalogue, state["paragraph"])
        if not entry:
            return
        combat = entry.get("combat", {})
        if combat.get("mode") != "sequence":
            return
        monsters = combat["enemies"]
        index = state["index"] + 1
        if index < len(monsters):
            state["index"] = index
            self._set_book_enemy(monsters[index])
            self.rules_log.setText(
                f"Adversaire vaincu. Combat suivant : {index+1}/{len(monsters)} — {monsters[index]['name']}.")
        else:
            target = combat.get("victory_target")
            self.book_combat_sequence = None
            if target in self.paragraphs:
                self.rules_log.setText(f"Tous les adversaires vaincus. Destination §{target}.")
                self.go_to(target)
            else:
                self.rules_log.setText(
                    f"Tous les adversaires vaincus. Ouvrez manuellement le §{target}.")

    def escape_scripted_combat(self, number):
        """Fuite vérifiée : restriction d'assauts, blessure, Chance puis navigation."""
        if number != self.current_paragraph:
            return
        entry = verified_entry(self.book_event_catalogue, number)
        rules = entry.get("combat", {}) if entry else {}
        target = rules.get("escape_target")
        if (target not in self.paragraphs or not flee_available(
                rules, self.book_combat_assaults.get(number, 0),
                self.enemy_endurance.value(), self.character["endurance"])):
            return
        attempt = QMessageBox.question(
            self, "Fuir le combat", "Tenter votre Chance pour la blessure de fuite ?\n"
            "Sans Chance : -2 Endurance. Chance réussie : -1. Échec : -3.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        rolls = None
        if attempt == QMessageBox.Yes:
            rolls, total = self._roll(2)
        else:
            total = None
        damage, cost = escape_damage(self.character["chance"], total)
        self.character["chance"] = max(0, self.character["chance"] - cost)
        self.character["endurance"] = max(0, self.character["endurance"] - damage)
        if number == 20:
            self.book_combat_sequence = None
        self._refresh_character()
        if self.character["endurance"] <= 0:
            self.rules_log.setText("La blessure de fuite est mortelle : Endurance à zéro.")
            self._render_choices_and_events(self.paragraphs[number])
            return
        self.go_to(target)
        self.rules_log.setText(
            f"Fuite du §{number} vers le §{target} : -{damage} Endurance"
            + (f", test de Chance {rolls} (Chance -1)." if rolls else "."))

    def choose_crocodile_strategy(self, phase):
        state = self.crocodile_combat
        if (not state or self.current_paragraph != 86 or phase not in ("continue", "diversion")
                or state["phase"] != "initial" or state["assaults"] < 2
                or self.enemy_endurance.value() <= 0):
            return
        state["phase"] = phase
        self.rules_log.setText(
            "Continuez jusqu'à la victoire." if phase == "continue"
            else "Un seul assaut supplémentaire, puis destination §350.")
        self._render_choices_and_events(self.paragraphs[86])

    def _finish_crocodile_round(self):
        state = self.crocodile_combat
        if not state or self.current_paragraph != state["paragraph"]:
            return
        entry = verified_entry(self.book_event_catalogue, 86)
        if not entry:
            return
        combat = entry["combat"]
        if self.character["endurance"] <= 0:
            self.rules_log.setText("Votre Endurance est à zéro : l'aventure est terminée.")
            return
        if state["phase"] == "diversion" and state["assaults"] >= 3:
            target = combat["diversion_target"]
        elif self.enemy_endurance.value() <= 0:
            target = combat["continue_target"]
        else:
            self._render_choices_and_events(self.paragraphs[86])
            return
        if target == 350:
            self.piranha_source_wounded = bool(state.get("wounded", False))
        self.crocodile_combat = None
        self.prepared_book_encounters.add(86)
        if target in self.paragraphs:
            self.go_to(target)
            self.rules_log.setText(f"Combat contre le Crocodile terminé : §{target}.")
        else:
            self.rules_log.setText(f"Combat terminé : ouvrez manuellement le §{target}.")

    def combat_round(self):
        state = self.crocodile_combat
        if (state and self.current_paragraph == state["paragraph"]
                and state["phase"] == "initial" and state["assaults"] >= 2
                and self.enemy_endurance.value() > 0):
            self.rules_log.setText(
                "Après deux assauts contre le Crocodile, choisissez une stratégie dans les événements.")
            return
        if self.enemy_endurance.value() <= 0:
            self.rules_log.setText("Le monstre est déjà vaincu.")
            return
        enemy_rolls, enemy_total = self._roll(2)
        player_rolls, player_total = self._roll(2)
        enemy_attack = self.enemy_skill.value() + enemy_total
        player_attack = combat_skill(self.character) + player_total
        if player_attack == enemy_attack:
            self.rules_log.setText(f"Égalité ({player_attack} contre {enemy_attack}) : aucun dégât. Relancez l'assaut.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, "Parade")
            return
        if player_attack > enemy_attack:
            outcome = QMessageBox(self)
            outcome.setWindowTitle("Vous touchez !")
            outcome.setText(f"Votre force d'attaque {player_attack} dépasse celle du monstre ({enemy_attack}).\nDégâts de base : 2 Endurance au monstre.")
            outcome.setInformativeText("Voulez-vous tenter votre Chance pour aggraver la blessure ?")
            outcome.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            outcome.button(QMessageBox.Yes).setText("Tenter ma Chance")
            outcome.button(QMessageBox.No).setText("Non")
            answer = outcome.exec()
            damage = 2
            if answer == QMessageBox.Yes:
                luck_rolls, luck_total = self._roll(2)
                was_lucky = luck_total <= self.character["chance"]
                self.character["chance"] = max(0, self.character["chance"] - 1)
                if was_lucky:
                    damage = 4
                    luck_text = f"Chance réussie ({luck_total}) : 4 dégâts au total."
                else:
                    damage = 1
                    luck_text = f"Chance ratée ({luck_total}) : seulement 1 dégât au total."
            else:
                luck_text = ""
            self.enemy_endurance.setValue(max(0, self.enemy_endurance.value() - damage))
            if (self.crocodile_combat and self.current_paragraph == 86
                    and damage > 0):
                self.crocodile_combat["wounded"] = True
            self._refresh_character()
            self.rules_log.setText(f"Vous touchez ({player_attack} contre {enemy_attack}). {luck_text} {self.enemy_name.text()} : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Monstre -{damage} PV")
            if self.enemy_endurance.value() == 0:
                self.rules_log.setText(self.rules_log.text() + "  ⚑ Victoire !")
                self._advance_scripted_sequence()
        else:
            outcome = QMessageBox(self)
            outcome.setWindowTitle("Le monstre vous touche !")
            outcome.setText(f"Force d'attaque du monstre {enemy_attack} contre la vôtre {player_attack}.\nVous perdez 2 Endurance.")
            outcome.setInformativeText("Voulez-vous tenter votre Chance pour minimiser la blessure ?")
            outcome.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            outcome.button(QMessageBox.Yes).setText("Tenter ma Chance")
            outcome.button(QMessageBox.No).setText("Non")
            answer = outcome.exec()
            damage = 2
            if answer == QMessageBox.Yes:
                luck_rolls, luck_total = self._roll(2)
                was_lucky = luck_total <= self.character["chance"]
                self.character["chance"] = max(0, self.character["chance"] - 1)
                if was_lucky:
                    damage = 1
                    luck_text = f"Chance réussie ({luck_total}) : blessure réduite à 1."
                else:
                    damage = 3
                    luck_text = f"Chance ratée ({luck_total}) : blessure aggravée à 3."
            else:
                luck_text = ""
            shield_note = ""
            if self.character.get("shield_equipped") and SHIELD_NAME in self.character.get("inventory", []):
                shield_rolls, shield_total = self._roll(1)
                reduced = shield_damage(damage, shield_total)
                shield_note = f" Bouclier {shield_rolls}: -{damage - reduced} dégât."
                damage = reduced
            self.character["endurance"] = max(0, self.character["endurance"] - damage)
            self._refresh_character()
            self.rules_log.setText(f"Le monstre vous touche ({enemy_attack} contre {player_attack}). {luck_text}{shield_note} Vous : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Héros -{damage} PV")
            if self.character['endurance'] == 0:
                self.rules_log.setText(self.rules_log.text() + "  ☠ Votre Endurance est à zéro.")

    def change_shield_use(self, active):
        if SHIELD_NAME not in self.character.get("inventory", []):
            return
        self.character["shield_equipped"] = bool(active)
        self.rules_log.setText(
            "Bouclier équipé." if active else "Bouclier rangé dans le sac.")

    def take_book_shield(self):
        if self.current_paragraph != 155:
            return
        entry = verified_entry(self.book_event_catalogue, 155)
        if not entry or not entry.get("shield_pickup"):
            return
        candidates = [x for x in self.character.get("inventory", [])
                      if x not in self.character.get("locked_items", [])
                      and x != SHIELD_NAME]
        if not candidates:
            QMessageBox.information(self, "Bouclier", "Aucun objet abandonnable.")
            return
        item, ok = QInputDialog.getItem(
            self, "Bouclier au croissant", "Objet à abandonner :", candidates, 0, False)
        if ok and take_moon_shield(self.character, item):
            self._refresh_character()
            self._render_choices_and_events(self.paragraphs[155])
            self.rules_log.setText(f"Bouclier récupéré ; objet abandonné : {item}.")

    def change_weapon(self, name):
        """Équiper une arme présente dans le sac ; opération annulable."""
        if not name:
            return
        if equip_weapon(self.character, name):
            self._refresh_character()
            self.rules_log.setText(
                f"Arme équipée : {name}. Habileté de combat : {combat_skill(self.character)}.")

    def add_item(self):
        item = self.item_input.text().strip()
        if item:
            self.character.setdefault("inventory", []).append(item)
            self._refresh_character()
            self.item_input.clear()

    def remove_item(self):
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
        notation = self.dice_combo.currentText()
        count, sides = notation.lower().split("d")
        rolls = [random.randint(1, int(sides)) for _ in range(int(count))]
        total = sum(rolls)
        result = f"{notation} : {' + '.join(map(str, rolls))} = {total}"
        self.dice_result.setText(result)
        faces = "⚀⚁⚂⚃⚄⚅"
        self.dice_faces.setText("  ".join((faces[n-1] if 1 <= n <= 6 else str(n)) for n in rolls) if rolls else "—")
        self.dice_history.insertItem(0, result)

    def _snapshot(self):
        return {"character": copy.deepcopy(self.character),
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
        if self._restoring or before == self._snapshot():
            return
        self.undo_stack.append((label, before))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.action_history.append(label)
        self.action_history = self.action_history[-200:]
        self._update_history_controls()
        self._autosave()

    def _update_history_controls(self):
        if not hasattr(self, "undo_btn"):
            return
        self.undo_btn.setEnabled(bool(self.undo_stack))
        self.redo_btn.setEnabled(bool(self.redo_stack))
        self.history_label.setText(f"Historique : {len(self.action_history)} actions · Annulables : {len(self.undo_stack)}")
        self.undo_btn.setToolTip(self.undo_stack[-1][0] if self.undo_stack else "")

    def _restore(self, state):
        self._restoring = True
        try:
            self.character = copy.deepcopy(state["character"])
            # Les anciennes sauvegardes n'enregistraient pas la pièce d'or initiale.
            self.character.setdefault("gold", 1)
            self.character.setdefault("locked_items", [])
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
            if target in self.paragraphs:
                self.go_to(target)
            else:
                self.current_paragraph = target
        finally:
            self._restoring = False

    def undo_action(self):
        if not self.undo_stack:
            return
        label, state = self.undo_stack.pop()
        self.redo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action annulée : {label}")
        self._update_history_controls()
        self._autosave()

    def redo_action(self):
        if not self.redo_stack:
            return
        label, state = self.redo_stack.pop()
        self.undo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action rétablie : {label}")
        self._update_history_controls()
        self._autosave()

    def set_stat(self, key, value):
        before = self._snapshot()
        self.character[key] = value
        self._record(f"Modifier {key}", before)

    def _save_data(self):
        return {"version": "1.0.13", "pdf_path": (str(Path(self.pdf_path).relative_to(APP_DIR)) if self.pdf_path and within_directory(self.pdf_path, APP_DIR) else None),
                "pdf_sha256": self._pdf_hash(),
                **self._snapshot(), "action_history": self.action_history,
                "undo_stack": self.undo_stack, "redo_stack": self.redo_stack}

    def _pdf_hash(self):
        if not self.pdf_path or not Path(self.pdf_path).is_file():
            return None
        h = hashlib.sha256()
        with open(self.pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _write_atomic(self, path, data):
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
        if not self.pdf_path or self._restoring:
            return
        try:
            directory = SAVES_DIR
            self._write_atomic(directory / "autosave.json", self._save_data())
        except OSError:
            pass  # La sauvegarde manuelle reste disponible.

    def _themed_file_dialog(self, kind="pdf", saving=False):
        """Sélecteur Qt français. Les sauvegardes restent dans donnees/sauvegardes."""
        titles = {
            "pdf": "Bifurk — Ouvrir un grimoire",
            "save": "Bifurk — Sauvegarder la partie",
            "load": "Bifurk — Charger une partie",
        }
        dialog = QFileDialog(self)
        dialog.setWindowTitle(titles[kind])
        dialog.setWindowIcon(self.windowIcon())
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptSave if saving else QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.AnyFile if saving else QFileDialog.ExistingFile)
        dialog.setLabelText(QFileDialog.LookIn, "Regarder dans :")
        dialog.setLabelText(QFileDialog.FileName, "Nom du fichier :")
        dialog.setLabelText(QFileDialog.FileType, "Type de fichier :")
        dialog.setLabelText(QFileDialog.Accept, "Enregistrer" if saving else "Ouvrir")
        dialog.setLabelText(QFileDialog.Reject, "Annuler")
        if kind == "pdf":
            dialog.setNameFilter("Grimoires PDF (*.pdf)")
            dialog.setDirectory(str(Path(self.pdf_path).parent if self.pdf_path else BOOKS_DIR))
        else:
            dialog.setNameFilter("Sauvegardes Bifurk (*.json)")
            dialog.setDefaultSuffix("json")
            dialog.setDirectory(str(SAVES_DIR))
            if saving:
                dialog.selectFile("bifurk-sauvegarde.json")
        dialog.resize(900, 600)
        # Libellés et infobulles des contrôles internes non natifs.
        QTimer.singleShot(0, lambda: franciser_selecteur(dialog))
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.selectedFiles()
            if not selected:
                return None
            result = Path(selected[0]).resolve()
            if kind != "pdf" and not within_directory(result, SAVES_DIR):
                QMessageBox.warning(self, "Dossier portable", "Les sauvegardes doivent rester dans le dossier donnees/sauvegardes de Bifurk.")
                return None
            return str(result)
        return None

    def _themed_save_dialog(self, saving):
        return self._themed_file_dialog(kind="save" if saving else "load", saving=saving)

    def save_game(self):
        path = self._themed_save_dialog(saving=True)
        if not path:
            return
        data = self._save_data()
        try:
            self._write_atomic(path, data)
            QMessageBox.information(self, "Sauvegarde", "Partie sauvegardée.")
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))

    def load_game(self):
        path = self._themed_save_dialog(saving=False)
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            pdf_reference = data.get("pdf_path")
            pdf = resolve_book_reference(pdf_reference)
            if pdf:
                expected = data.get("pdf_sha256")
                self.pdf_path = pdf
                if expected and expected != self._pdf_hash():
                    raise ValueError("Le PDF a changé depuis la sauvegarde.")
                paragraphs = extract_paragraphs(pdf)
                illustration_catalogue = catalogue_for_pdf(pdf)
                self.paragraphs = paragraphs
                self.illustration_catalogue = illustration_catalogue
                self.book_event_catalogue = load_book_events(pdf)
                self.book_label.setText(Path(pdf).name)
                if self.paragraphs:
                    self.goto_spin.setMaximum(max(self.paragraphs))
            elif pdf_reference:
                QMessageBox.warning(self, "PDF introuvable", "Le grimoire est absent du dossier portable. Réimportez-le pour naviguer.")
            self._restore({"character": data.get("character", self.character),
                           "completed_book_events": data.get("completed_book_events", []),
                           "completed_optional_events": data.get("completed_optional_events", []),
                           "prepared_book_encounters": data.get("prepared_book_encounters", []),
                           "book_combat_sequence": data.get("book_combat_sequence"),
                           "crocodile_combat": data.get("crocodile_combat"),
                           "piranha_source_wounded": data.get("piranha_source_wounded"),
                           "piranha_combat": data.get("piranha_combat"),
                           "book_combat_assaults": data.get("book_combat_assaults", {}),
                           "visited_paragraphs": data.get("visited_paragraphs", []),
                           "transitions": data.get("transitions", []),
                           "current_paragraph": data.get("current_paragraph")})
            self.action_history = data.get("action_history", [])
            self.undo_stack = [(label, state) for label, state in data.get("undo_stack", [])]
            self.redo_stack = [(label, state) for label, state in data.get("redo_stack", [])]
            self._update_history_controls()
            QMessageBox.information(self, "Chargement", "Partie chargée.")
        except Exception as exc:
            QMessageBox.critical(self, "Chargement impossible", str(exc))


def _track_action(method, label):
    def wrapped(self, *args, **kwargs):
        if self._restoring:
            return method(self, *args, **kwargs)
        depth = getattr(self, "_action_depth", 0)
        before = self._snapshot() if depth == 0 else None
        self._action_depth = depth + 1
        try:
            result = method(self, *args, **kwargs)
            if method.__name__ == "combat_round" and depth == 0:
                self._finish_crocodile_round()
                if self.current_paragraph in (8, 16, 20) and self.current_paragraph in self.paragraphs:
                    self._render_choices_and_events(self.paragraphs[self.current_paragraph])
            return result
        finally:
            self._action_depth -= 1
            if depth == 0:
                self._record(label, before)
    return wrapped

for _name, _label in {
    "go_to": "Changer de paragraphe", "apply_detected_event": "Appliquer un événement",
    "resolve_book_roll": "Résoudre une épreuve du livre",
    "escape_scripted_combat": "Fuir un combat du livre",
    "choose_crocodile_strategy": "Choisir une stratégie contre le Crocodile",
    "apply_optional_book_event": "Choisir une récompense du livre",
    "create_character": "Créer un personnage", "test_luck": "Tenter sa Chance",
    "eat_meal": "Prendre un repas", "drink_potion": "Boire une potion",
    "combat_round": "Assaut de combat", "add_item": "Ajouter un objet",
    "remove_item": "Retirer un objet", "change_potion": "Changer de potion",
    "change_weapon": "Changer d'arme",
    "change_shield_use": "Utiliser le bouclier",
    "take_book_shield": "Prendre le bouclier"
}.items():
    setattr(MainWindow, _name, _track_action(getattr(MainWindow, _name), _label))


def main():
    init_portable_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
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
    window = MainWindow()
    app.setStyleSheet(window.styleSheet())
    app._bifurk_dialog_filter = DialogThemeFilter(app)
    app.installEventFilter(app._bifurk_dialog_filter)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
