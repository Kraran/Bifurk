"""Construction des widgets de la fenêtre principale (bandeau, page, fiche, champs du moteur).

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

from about_dialog import BrandButton
from adventurer_sheet import (HeroEmblem, HeroMarks, InventoryGrid, OrnateHeading, ResourceToken,
                              RibbonButton, SealButton, SheetPanel, SheetStrip, StatMedallion,
                              ValueLabel)
from grimoire_chrome import (BannerDivider, ChoiceGroup, DrawerScrim, LeatherBanner,
                             MedallionButton, PageToolButton, ParagraphCartouche)
from grimoire_modules.fighting_fantasy.rules import POTION_STATS
from grimoire_ui import GrimoireScene, IlluminatedPage, SingleLineTitle

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QPushButton, QScrollArea,
                               QSizePolicy, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget)

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class ConstructionMixin:
    """Construction des widgets de la fenêtre principale (bandeau, page, fiche, champs du moteur)."""

    def _build_ui(self):
        """Assembler les trois zones : illustration, lecture et panneau d’aventure.

        Conserver les widgets en attributs pour les rafraîchissements ; les connexions
        Qt appellent les actions du contrôleur, pas des mutations d’état cachées dans la vue."""
        central = QWidget()
        root = QVBoxLayout(central)
        self.root_layout = root
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # Bandeau de cuir et d'or : marque, livre courant puis médaillons dessinés.
        header_frame = LeatherBanner()
        header_frame.setObjectName("grimoireHeader")
        self.header_frame = header_frame
        header = QHBoxLayout(header_frame)
        self.header_layout = header
        header.setContentsMargins(22, 12, 30, 10)
        header.setSpacing(6)
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
        self.subtitle_label = subtitle
        brand.addWidget(subtitle)
        header.addWidget(self.about_button)
        header.addStretch()
        self.book_label = QLabel("Aucun livre chargé")
        self.book_label.setObjectName("bookName")
        self.book_label.setMaximumWidth(240)
        self.book_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        header.addWidget(self.book_label)
        header.addSpacing(10)
        self.undo_btn = MedallionButton("Annuler", "undo", text="↶ Annuler")
        self.redo_btn = MedallionButton("Rétablir", "redo", text="↷ Rétablir")
        self.undo_btn.clicked.connect(lambda: self.manual_history(False))
        self.redo_btn.clicked.connect(lambda: self.manual_history(True))
        header.addWidget(self.undo_btn)
        header.addWidget(self.redo_btn)
        # Le compteur devient une info-bulle d'Annuler : la barre reste lisible.
        self.history_label = QLabel("Historique : 0 action")
        self.history_label.hide()
        header.addWidget(BannerDivider())
        self.rules_button = MedallionButton("Règles", "scroll", text="📖 Règles")
        self.rules_button.setToolTip("Lire les règles du grimoire (F1)")
        self.rules_button.clicked.connect(self.show_rules)
        header.addWidget(self.rules_button)
        self.map_button = MedallionButton("Carte", "map", text="🗺 Carte d’exploration")
        self.map_button.setToolTip("Carte d’exploration des paragraphes visités")
        self.map_button.clicked.connect(self.show_map)
        header.addWidget(self.map_button)
        header.addWidget(BannerDivider())
        self.open_btn = MedallionButton("Grimoires", "books", primary=True, text="✦  Grimoires…")
        self.open_btn.setObjectName("goldButton")
        self.open_btn.setToolTip("Choisir un grimoire importé ou ajouter un livre PDF")
        self.open_btn.clicked.connect(self.show_library)
        header.addWidget(self.open_btn)
        # Proposition UI : les commandes rares quittent la barre et rejoignent ⚙.
        # fullscreen_btn reste un objet (masqué) pour conserver l'API existante.
        self.fullscreen_btn = QPushButton("⛶  Plein écran")
        self.fullscreen_btn.setToolTip("Plein écran (F11) — Échap pour quitter")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.hide()
        self.settings_button = MedallionButton("Réglages", "gear", text="⚙")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setToolTip("Réglages et commandes de la fenêtre")
        self.settings_button.setAccessibleName("Réglages")
        # Pictogrammes peints dans l'or du thème (menu_icon) : la colonne d'icônes
        # aligne les libellés, que la police ait ou non des symboles Unicode.
        settings_menu = bifurk.QMenu(self.settings_button)
        settings_menu.setObjectName('settingsMenu')
        self.settings_icons = {}
        def settings_action(kind, label, slot=None):
            action = settings_menu.addAction(label)
            if slot is not None:
                action.triggered.connect(slot)
            self.settings_icons[action] = kind
            return action
        settings_action('music', 'Ambiances…', self.show_ambience)
        settings_action('gamepad', 'Manette…', self.show_gamepad)
        settings_menu.addSeparator()
        # « \t » affiche la touche à droite ; les raccourcis eux-mêmes sont des QShortcut.
        self.fullscreen_action = settings_action('fullscreen', 'Plein écran\tF11', self.toggle_fullscreen)
        self.reading_action = settings_action('reading', 'Mode lecture\tF10')
        self.reading_action.setCheckable(True)
        self.reading_action.setToolTip("Masquer le bandeau et la fiche (F10 ou Échap pour revenir)")
        self.reading_action.triggered.connect(self.toggle_reading_mode)
        settings_menu.addSeparator()
        settings_action('scroll', 'Journal de la partie…', self.show_tracking)
        settings_action('info', 'À propos de Bifurk', self.show_about)
        settings_menu.addSeparator()
        settings_action('quit', 'Quitter le jeu…', self.confirm_quit)
        self.settings_button.setMenu(settings_menu)
        self._refresh_menu_icons()
        header.addWidget(self.settings_button)
        root.addWidget(header_frame)
        QShortcut(QKeySequence("F1"), self, activated=self.show_rules)
        for digit in range(1, 10):
            QShortcut(QKeySequence(str(digit)), self,
                      activated=lambda n=digit: self._activate_choice(n))
        self._update_history_controls()

        splitter = QSplitter(Qt.Horizontal)
        self.splitter = splitter
        reader_panel = IlluminatedPage(self.theme.assets["parchment"], theme=self.theme)
        reader_panel.setObjectName("readerPanel")
        self.reader_panel = reader_panel
        reader_layout = QVBoxLayout(reader_panel)
        # Marges de livre : le texte respire à l'intérieur du double filet.
        self.reader_layout = reader_layout
        reader_layout.setContentsMargins(40, 26, 38, 26)
        reader_layout.setSpacing(6)
        self.scene_art = GrimoireScene(self.theme.assets["scene"], theme=self.theme)
        self.scene_entry = None
        self.scene_title = ""
        self.scene_art.activated.connect(self._enlarge_scene_art)
        splitter.addWidget(self.scene_art)
        reader_panel.setMinimumWidth(0)
        self.art_toggle = PageToolButton("image", "Afficher ou masquer l’image",
                                         text="◈  Masquer l’image", checked_glyph="image_off")
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
        # Rangée d'outils de page : outils d'image, cartouche du paragraphe, taille du texte.
        self.paragraph_number = ParagraphCartouche()
        self.paragraph_number.setObjectName('paragraphNumber')
        self.paragraph_number.setAlignment(Qt.AlignCenter)
        self.paragraph_number.hide()
        self.paragraph_number.installEventFilter(self)
        self._init_carnet()
        title_row = QHBoxLayout()
        self.title_row = title_row
        title_row.setSpacing(4)
        cover_button = PageToolButton("cover", "Voir la couverture du livre", text="Couverture")
        cover_button.setAccessibleName("Voir la couverture")
        cover_button.clicked.connect(self.show_cover)
        title_row.addWidget(cover_button)
        title_row.addWidget(self.art_toggle)
        # Avec les outils de gauche : le cartouche du numéro reste centré.
        self.tts_button = PageToolButton("speaker", self.TTS_TOOLTIP, text="🔊")
        self.tts_button.setObjectName('ttsButton')
        self.tts_button.clicked.connect(self._speak_current_paragraph)
        title_row.addWidget(self.tts_button)
        title_row.addStretch(1)
        # Le ruban du marque-page équilibre une marge égale à gauche : le cartouche reste centré.
        title_row.addSpacing(self.bookmark_ribbon.width() + title_row.spacing())
        title_row.addWidget(self.paragraph_number)
        title_row.addWidget(self.bookmark_ribbon, 0, Qt.AlignTop)
        title_row.addStretch(1)
        minus_btn = PageToolButton("font_minus", "Réduire la taille du texte", text="A−")
        minus_btn.clicked.connect(lambda: self.change_reader_font_size(-2))
        title_row.addWidget(minus_btn)
        self.font_size_label = QLabel(f"{self.reader_font_size} pt")
        self.font_size_label.setObjectName("fontSizeLabel")
        self.font_size_label.setAlignment(Qt.AlignCenter)
        self.font_size_label.setMinimumWidth(38)
        title_row.addWidget(self.font_size_label)
        plus_btn = PageToolButton("font_plus", "Agrandir la taille du texte", text="A+")
        plus_btn.clicked.connect(lambda: self.change_reader_font_size(2))
        title_row.addWidget(plus_btn)
        self.reading_exit_button = PageToolButton("close", "Quitter le mode lecture (F10 ou Échap)",
                                                  text="Quitter le mode lecture")
        self.reading_exit_button.clicked.connect(lambda: self.toggle_reading_mode(False))
        self.reading_exit_button.hide()
        title_row.addWidget(self.reading_exit_button)
        reader_layout.addLayout(title_row)
        self.reader = bifurk.ReaderBrowser()
        # Les liens paragraph:NNN sont gérés par follow_link, jamais par QTextBrowser.
        self.reader.setOpenLinks(False)
        self.reader.setOpenExternalLinks(False)
        self.reader.anchorClicked.connect(self.follow_link)
        self.reader.setObjectName("reader")
        self.reader.setMinimumHeight(230)
        reader_layout.addWidget(self.reader, 1)
        # Alerte d'Endurance basse : rappel discret qu'un soin autorisé existe.
        self.endurance_alert = QFrame()
        self.endurance_alert.setObjectName("enduranceAlert")
        alert_row = QHBoxLayout(self.endurance_alert)
        alert_row.setContentsMargins(12, 6, 8, 6)
        self.endurance_alert_text = QLabel()
        self.endurance_alert_text.setObjectName("enduranceAlertText")
        self.endurance_alert_text.setWordWrap(True)
        self.endurance_alert_text.setTextFormat(Qt.PlainText)
        alert_row.addWidget(self.endurance_alert_text, 1)
        self.endurance_alert_button = QPushButton("✚  Soins")
        self.endurance_alert_button.setObjectName("alertCare")
        self.endurance_alert_button.setToolTip("Ouvrir le menu des soins")
        self.endurance_alert_button.clicked.connect(
            lambda: self.show_care_menu(anchor=self.endurance_alert_button))
        alert_row.addWidget(self.endurance_alert_button)
        self.endurance_alert.hide()
        reader_layout.addWidget(self.endurance_alert)
        # Cadre de messages : le dernier résultat de règle (jets, pertes, gains),
        # miroir visible du journal interne et vidé au changement de paragraphe.
        self.message_frame = QLabel()
        self.message_frame.setObjectName("messageFrame")
        self.message_frame.setWordWrap(True)
        self.message_frame.setTextFormat(Qt.PlainText)
        self.message_frame.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_frame.hide()
        reader_layout.addWidget(self.message_frame)

        self.choice_group = ChoiceGroup("⚜  QUELLE SERA VOTRE VOIE ?")
        self.choice_layout = QVBoxLayout(self.choice_group)
        self.choice_layout.setContentsMargins(0, ChoiceGroup.HEADER, 0, 4)
        self.choice_layout.setSpacing(8)
        self.choice_hint = QLabel("Les destinations détectées apparaîtront ici.")
        self.choice_hint.setWordWrap(True)
        self.choice_layout.addWidget(self.choice_hint)
        reader_layout.addWidget(self.choice_group)

        self.event_group = ChoiceGroup("✧  ÉVÉNEMENTS")
        self.event_layout = QVBoxLayout(self.event_group)
        self.event_layout.setContentsMargins(0, ChoiceGroup.HEADER, 0, 4)
        self.event_layout.setSpacing(8)
        self.event_hint = QLabel("Aucun événement automatique détecté.")
        self.event_hint.setWordWrap(True)
        self.event_layout.addWidget(self.event_hint)
        reader_layout.addWidget(self.event_group)
        self.condition_group = ChoiceGroup("✧  INDICES D’INVENTAIRE")
        self.condition_layout = QVBoxLayout(self.condition_group)
        self.condition_layout.setContentsMargins(0, ChoiceGroup.HEADER, 0, 4)
        self.condition_layout.setSpacing(8)
        reader_layout.addWidget(self.condition_group)

        reader_scroll = QScrollArea()
        reader_scroll.setObjectName("pageScroll")
        reader_scroll.setWidgetResizable(True)
        reader_scroll.setFrameShape(QFrame.NoFrame)
        reader_scroll.setWidget(reader_panel)
        splitter.addWidget(reader_scroll)

        side = SheetPanel()
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.setSpacing(8)

        # Fiche peinte (adventurer_sheet) : les QSpinBox restent les sources de vérité,
        # habillés en blasons-jauges (valeur / initiale) et en plaques.
        stats_group = QGroupBox("")
        stats_group.setObjectName("sheetStats")
        self.stats_group = stats_group
        stats_grid = QGridLayout(stats_group)
        stats_grid.setHorizontalSpacing(2)
        stats_grid.setVerticalSpacing(6)
        stats_grid.setContentsMargins(0, 0, 0, 0)
        self.stat_spins = {}
        self.stat_medallions = {}
        stats = [("HABILETÉ", "habilete"), ("ENDURANCE", "endurance"), ("CHANCE", "chance")]
        self.stats_heading = OrnateHeading("CARACTÉRISTIQUES")
        stats_grid.addWidget(self.stats_heading, 0, 0, 1, 3)
        for column, (label, key) in enumerate(stats):
            spin = QSpinBox()
            spin.setKeyboardTracking(False)
            spin.setRange(0, 999)
            spin.setAlignment(Qt.AlignCenter)
            spin.setButtonSymbols(QSpinBox.UpDownArrows)
            spin.setObjectName("heroValue")
            spin.setAccessibleName(label)
            spin.valueChanged.connect(lambda value, k=key: self.manual_set_stat(k, value))
            medallion = StatMedallion(key, label, spin)
            stats_grid.addWidget(medallion, 1, column)
            self.stat_medallions[key] = medallion
            self.stat_spins[key] = spin
        self.purse_heading = OrnateHeading("BOURSE & VIVRES")
        stats_grid.addWidget(self.purse_heading, 3, 0, 1, 3)
        resources = QHBoxLayout()
        resources.setSpacing(6)
        self.resource_tokens = {}
        for label, key in (("Or", "gold"), ("Provisions", "provisions")):
            spin = QSpinBox()
            spin.setKeyboardTracking(False)
            spin.setRange(0, 999)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(lambda value, k=key: self.manual_set_stat(k, value))
            # Lecture seule par défaut : le livre gère ces valeurs ; Actions… les déverrouille.
            spin.setReadOnly(True)
            spin.setObjectName("resourceValue")
            spin.setProperty("locked", True)
            spin.setAlignment(Qt.AlignCenter)
            spin.setFocusPolicy(Qt.NoFocus)
            spin.setMinimumWidth(40)
            token = ResourceToken(key, label.upper(), spin)
            self.resource_tokens[key] = token
            resources.addWidget(token, 1)
            self.stat_spins[key] = spin
        self.potion_value = ValueLabel()
        self.potion_token = ResourceToken("potion", "POTION", self.potion_value)
        resources.addWidget(self.potion_token, 1)
        stats_grid.addLayout(resources, 4, 0, 1, 3)
        self.potion_combo = QComboBox()
        self.potion_combo.addItems(["Aucune", *POTION_STATS])
        self.potion_combo.setAccessibleName("Potion choisie")
        # Le choix appartient à la création ; la feuille ne peut ni changer ni recharger la fiole.
        self.potion_combo.setEnabled(False)
        self.potion_combo.hide()
        stats_grid.addWidget(self.potion_combo, 5, 0, 1, 3)
        self.potion_doses_label = QLabel()
        self.potion_doses_label.hide()
        stats_grid.addWidget(self.potion_doses_label, 6, 0, 1, 3)
        self.initial_label = QLabel("Valeurs de départ : —")
        self.initial_label.setObjectName("initialStats")
        self.initial_label.setWordWrap(True)
        self.initial_label.hide()
        stats_grid.addWidget(self.initial_label, 7, 0, 1, 3)
        hero_row = self.hero_row = QHBoxLayout()
        hero_row.setSpacing(10)
        crest = self.hero_emblem = HeroEmblem(56)
        crest.setObjectName("heroCrest")
        hero_row.addWidget(crest)
        hero_title = QLabel("L’AVENTURIER\nVotre destin s’écrit ici")
        self.hero_title = hero_title
        hero_title.setTextFormat(Qt.PlainText)
        hero_title.setWordWrap(True)
        hero_title.setObjectName("heroTitle")
        hero_row.addWidget(hero_title)
        # Marques du corps exposées par le module (tatouage…), juste à droite du nom.
        self.hero_marks = HeroMarks()
        hero_row.addWidget(self.hero_marks, 0, Qt.AlignBottom)
        hero_row.addStretch(1)
        side_layout.addLayout(hero_row)
        self.tracking_badge = RibbonButton()
        self.tracking_badge.setObjectName('adventureTrackingBadge')
        self.tracking_badge.setCursor(Qt.PointingHandCursor)
        self.tracking_badge.clicked.connect(self.show_tracking)
        side_layout.addWidget(self.tracking_badge)
        self._update_tracking_badge()
        side_layout.addWidget(stats_group)
        self.adventure_tabs = QTabWidget()
        self.adventure_tabs.setObjectName("adventureTabs")
        self.adventure_tabs.setDocumentMode(True)
        self.adventure_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.adventure_tabs.setMinimumHeight(110)
        # En-tête repliable : la fiche tient sans défilement sur 900 px de haut.
        self.inventory_toggle = OrnateHeading("▾  SACOCHE && TRÉSORS", checkable=True)
        self.inventory_toggle.setObjectName("inventoryToggle")
        self.inventory_toggle.setToolTip("Replier ou déplier la sacoche")
        self.inventory_toggle.toggled.connect(self._toggle_inventory)
        side_layout.addWidget(self.inventory_toggle)
        side_layout.addWidget(self.adventure_tabs, 1)

        inv_group = QFrame()
        inv_group.setObjectName("inventoryPanel")
        inv_layout = QVBoxLayout(inv_group)
        inv_layout.setContentsMargins(0, 2, 0, 0)
        inv_layout.setSpacing(4)

        self.inventory_list = InventoryGrid()
        self.inventory_list.setObjectName("inventoryCards")
        self.inventory_list.setMinimumHeight(90)
        self.inventory_list.setIconSize(QSize(26, 26))
        self.inventory_list.setToolTip("Double-clic sur une arme : l’équiper • clic droit : retirer")
        self.inventory_list.itemDoubleClicked.connect(self._equip_from_grid)
        self.inventory_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.inventory_list.customContextMenuRequested.connect(self._inventory_context_menu)
        inv_layout.addWidget(self.inventory_list, 1)
        inv_row = QHBoxLayout()
        inv_row.setContentsMargins(0, 0, 0, 0)
        self.item_input = QLineEdit()
        self.item_input.setObjectName("sheetInput")
        self.item_input.setPlaceholderText("Ajouter un objet…")
        self.item_input.returnPressed.connect(lambda: self.manual_inventory(False))
        inv_row.addWidget(self.item_input)
        add_item_btn = QPushButton("+")
        add_item_btn.setObjectName("sheetLink")
        add_item_btn.clicked.connect(lambda: self.manual_inventory(False))
        inv_row.addWidget(add_item_btn)
        remove_item_btn = QPushButton("Retirer")
        remove_item_btn.setObjectName("sheetLink")
        remove_item_btn.clicked.connect(lambda: self.manual_inventory(True))
        inv_row.addWidget(remove_item_btn)
        inventory_tools = QWidget()
        inventory_tools.setLayout(inv_row)
        inventory_tools.hide()
        manage_inventory = QPushButton("✎ Gérer les objets…")
        manage_inventory.setObjectName("sheetLink")
        manage_inventory.setCursor(Qt.PointingHandCursor)
        manage_inventory.setCheckable(True)
        manage_inventory.toggled.connect(inventory_tools.setVisible)
        inv_layout.addWidget(manage_inventory, 0, Qt.AlignRight)
        inv_layout.addWidget(inventory_tools)
        self.equipment_label = QLabel("⚔  Arme : Épée     ◈  Protection : Armure de cuir")
        self.equipment_label.setWordWrap(True)
        self.equipment_label.setObjectName("equipment")
        self.equipment_label.hide()
        self.weapon_combo = QComboBox()
        self.weapon_combo.setObjectName("weaponBanner")
        self.weapon_combo.currentTextChanged.connect(self.change_weapon)
        self.weapon_combo.setToolTip("Arme équipée")
        inv_layout.insertWidget(0, self.weapon_combo)
        self.shield_check = QCheckBox("Utiliser le bouclier au croissant")
        self.shield_check.toggled.connect(self.change_shield_use)
        inv_layout.insertWidget(1, self.shield_check)
        self._add_adventure_tab(inv_group, "Sacoche")

        # Les widgets d'état du moteur ne constituent plus des panneaux visibles.
        # Leur remplacement par un modèle indépendant est distinct du transfert UI.
        self._build_engine_fields()
        self.adventure_tabs.tabBar().hide()
        controls = QGridLayout()
        self.combat_button = QPushButton("⚔  COMBATTRE  ⚔")
        self.combat_button.setObjectName("combatButton")
        self.combat_button.setToolTip("Combattre ou reprendre le combat de ce paragraphe")
        self.combat_button.clicked.connect(self.open_combat)
        controls.addWidget(self.combat_button, 0, 0, 1, 2)
        side_layout.insertLayout(side_layout.indexOf(self.inventory_toggle), controls)

        seals = QHBoxLayout()
        seals.setSpacing(2)
        self.care_button = SealButton("Soins", "cross")
        self.care_button.setToolTip("Manger une provision ou boire la potion")
        self.care_button.clicked.connect(self._close_sheet_drawer)
        self.care_button.clicked.connect(lambda: self.show_care_menu())
        self.tools_button = SealButton("Actions…", "dice")
        self.tools_button.setToolTip("Dés libres, aller à un paragraphe, prologue, corrections")
        # Menu hors du panneau peint pour garder le style des menus.
        tools = bifurk.QMenu(self)
        dice = tools.addMenu("Dés libres")
        for notation in ("1d6", "2d6", "3d6", "1d20"):
            dice.addAction(notation, lambda checked=False, n=notation: self.roll_free_dice(n))
        tools.addAction("Aller à un paragraphe…", self.choose_paragraph)
        self.prologue_action = tools.addAction('Prologue et carte du livre', self.show_prologue)
        self.edit_resources_action = tools.addAction('Corriger Provisions et Or')
        self.edit_resources_action.setCheckable(True)
        self.edit_resources_action.toggled.connect(self._set_resources_editable)
        self.tools_button.setMenu(tools)
        tools.triggered.connect(lambda _action: self._close_sheet_drawer())
        save_btn = SealButton("Sauvegarder", "quill")
        save_btn.setToolTip("Sauvegarder la partie")
        save_btn.clicked.connect(self._close_sheet_drawer)
        save_btn.clicked.connect(self.save_game)
        load_btn = SealButton("Charger", "book")
        load_btn.setToolTip("Charger une partie")
        load_btn.clicked.connect(self._close_sheet_drawer)
        load_btn.clicked.connect(self.load_game)
        self.carnet_button = SealButton("Carnet", "notebook")
        self.carnet_button.setToolTip("Carnet de notes et marque-pages (N)")
        self.carnet_button.clicked.connect(self._close_sheet_drawer)
        self.carnet_button.clicked.connect(lambda: self.open_carnet())
        self.sheet_seals = (self.care_button, self.tools_button, self.carnet_button, save_btn, load_btn)
        self.side_panel = side
        for seal in self.sheet_seals:
            seals.addWidget(seal)
        # Ressort repris par la sacoche compacte : les sceaux restent en bas de la fiche.
        self.sheet_bottom_spacer = QWidget()
        self.sheet_bottom_spacer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.sheet_bottom_spacer.hide()
        side_layout.addWidget(self.sheet_bottom_spacer, 1)
        side_layout.addLayout(seals)
        self.quit_button = QPushButton('Quitter le jeu')
        self.quit_button.setObjectName('quitGameButton')
        self.quit_button.setToolTip('Fermer Bifurk après confirmation')
        self.quit_button.clicked.connect(self.confirm_quit)
        # Quitter vit désormais dans le menu ⚙ ; le bouton reste pour l'API/tests.
        self.quit_button.hide()
        side_layout.addWidget(self.quit_button)
        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(side)
        self.side_scroll = scroll
        splitter.addWidget(scroll)
        scroll.setMinimumWidth(365)
        splitter.setSizes([300, 880, 340])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 1)
        splitter.setChildrenCollapsible(False)
        # Petites largeurs : la fiche se replie en bande verticale et s'ouvre en tiroir.
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        body.addWidget(splitter, 1)
        self.sheet_strip = SheetStrip()
        self.sheet_strip.clicked.connect(lambda: self.toggle_sheet_drawer())
        self.sheet_strip.installEventFilter(self)
        self.sheet_strip.hide()
        body.addWidget(self.sheet_strip)
        root.addLayout(body, 1)
        self.drawer_scrim = DrawerScrim(self._close_sheet_drawer, central)
        self.setCentralWidget(central)

    def _add_adventure_tab(self, content, title):
        """Placer un panneau dans un onglet défilable pour les petites hauteurs d’écran."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setMinimumHeight(100)
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
        for widget in (self.enemy_name, self.enemy_skill, self.enemy_endurance):
            widget.installEventFilter(self)
            widget.editingFinished.connect(self._finish_manual_enemy_edit)
        self.rules_log = bifurk.RulesLog('Préparez le combat lorsque le récit le demande.', fields, self)
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
        self.goto_button.clicked.connect(lambda: self.manual_travel(self.goto_spin.value()))
