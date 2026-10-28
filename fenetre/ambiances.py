"""Sons de la partie : lecture vocale, ambiance par paragraphe, musique de victoire et fenêtre Ambiances.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

from ambience_map import AmbienceMap, KEEP
from dialog_chrome import DialogHeading
from sound_effects import EFFECT_LABELS, SCENES
from tts import DEFAULT_VOICE, available_french_voices

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSlider, QVBoxLayout, QWidget)

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class AmbiancesMixin:
    """Sons de la partie : lecture vocale, ambiance par paragraphe, musique de victoire et fenêtre Ambiances."""

    def _percent_preference(self, key, default=100, maximum=150):
        """Pourcentage mémorisé, borné ; une valeur illisible reprend la valeur par défaut."""
        try:
            return max(0, min(maximum, int(self.preferences.get(key, default))))
        except (TypeError, ValueError):
            return default

    def _volume_slider(self, name, value, apply, accessible, maximum=150):
        """Curseur de volume harmonisé (0–maximum %) et son libellé de valeur « Muet » à 0."""
        slider = QSlider(Qt.Horizontal)
        slider.setObjectName(name)
        slider.setProperty('volume', True)   # Même habillage QSS pour tous les volumes.
        slider.setAccessibleName(accessible)
        slider.setRange(0, maximum)
        slider.setSingleStep(5)
        slider.setPageStep(10)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(10)
        slider.setMinimumWidth(180)
        slider.setValue(value)
        shown = QLabel(f'{value} %' if value else 'Muet')
        shown.setObjectName(name + 'Value')
        shown.setMinimumWidth(56)

        def changed(percent):
            apply(percent)
            shown.setText(f'{percent} %' if percent else 'Muet')
        slider.valueChanged.connect(changed)
        return slider, shown

    def _speak_current_paragraph(self):
        """Lire à voix haute le paragraphe affiché ; un second clic arrête la lecture.

        L'arrêt au bouton retient la phrase en cours : le clic suivant, sur le même
        paragraphe, reprend au début de cette phrase."""
        if self.tts.is_busy():
            self.tts.fade_out(remember=True)
            return
        if self.current_paragraph in self.paragraphs:
            self.tts.speak(self.paragraphs[self.current_paragraph])

    def _tts_follow_paragraph(self, number):
        """En changeant de paragraphe, couper la lecture et enchaîner sur le nouveau si elle était lancée."""
        tts = getattr(self, 'tts', None)
        if tts is None or not tts.is_busy():
            return
        if self._restoring or number not in self.paragraphs:
            tts.fade_out()
        else:
            tts.speak(self.paragraphs[number])

    AMBIENT_MODES = (('paragraph', 'selon le paragraphe'), ('book', 'boucle du livre'))

    def _load_ambience_map(self):
        """Lire les scènes du livre ouvert ; un catalogue invalide laisse la boucle du livre."""
        try:
            self.ambience_map = AmbienceMap.from_module(self.book_module)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.ambience_map = None
            self.sounds.logger.error('ambience catalogue: %s', exc)
        self._ambience_follow_paragraph(None)

    def _ambience_follow_paragraph(self, number):
        """Jouer la scène du paragraphe (Réglages : « selon le paragraphe »).

        Sans catalogue, hors d'un paragraphe ou en mode « boucle du livre », la boucle
        du livre revient. Une exception « garder » laisse la scène en cours ; après un
        chargement, la scène du dernier paragraphe visité qui en a une est reprise."""
        self._victory_follow_paragraph(number)
        sounds = getattr(self, 'sounds', None)
        if sounds is None:
            return
        ambience = getattr(self, 'ambience_map', None)
        if (number is None or ambience is None
                or self.preferences.get('ambient_mode', 'paragraph') != 'paragraph'):
            sounds.set_scene(None)
            return
        scene = ambience.scene_for(number)
        if scene is KEEP:
            if sounds.scene is not None:
                return
            visited = getattr(self, 'visited_paragraphs', [])
            scene = next((found for found in map(ambience.scene_for, reversed(visited))
                          if found is not KEEP), None)
        sounds.set_scene(scene)

    VICTORY_PARAGRAPH = 400

    def _victory_follow_paragraph(self, number):
        """§400 d'un grimoire reconnu : boucler « Achievement » et baisser l'ambiance.

        Tout autre écran (paragraphe, accueil, chargement, annulation) arrête la boucle
        en fondu et rend la musique d'accueil ou l'ambiance comme avant."""
        music = getattr(self, 'intro_music', None)
        if music is None:
            return
        victory = (number is not None and getattr(self, 'book_module', None) is not None
                   and str(number) == str(self.VICTORY_PARAGRAPH))
        if victory == music.victory:
            return
        sounds = getattr(self, 'sounds', None)
        if victory:
            music.start_victory()
        else:
            music.stop_victory()
        if sounds is not None:
            sounds.duck_ambient(victory)

    def _fade_out_reading(self):
        """Éteindre en fondu une lecture vocale en cours quand son paragraphe quitte la page."""
        tts = getattr(self, 'tts', None)
        if tts is not None and tts.is_busy():
            tts.fade_out()

    TTS_TOOLTIP = "Lire le paragraphe à voix haute"

    TTS_RESUME_TOOLTIP = "Reprendre la lecture à la phrase interrompue"

    def _show_tts_state(self, busy):
        """Bouton 🔊 / ⏹ selon la lecture en cours."""
        if not hasattr(self, 'tts_button'):
            return
        self.tts_button.glyph = 'speaker_stop' if busy else 'speaker'
        self.tts_button.setText("⏹" if busy else "🔊")
        resume = getattr(getattr(self, 'tts', None), 'resume_point', lambda: None)()
        if busy:
            self.tts_button.setToolTip("Arrêter la lecture à voix haute")
        elif self.tts_button.toolTip() in ("Arrêter la lecture à voix haute", self.TTS_RESUME_TOOLTIP,
                                           self.TTS_TOOLTIP):
            self.tts_button.setToolTip(self.TTS_RESUME_TOOLTIP if resume else self.TTS_TOOLTIP)
        self.tts_button.update()

    def _show_tts_error(self, message):
        """Échec discret (réseau, paquet absent) : seule l’infobulle du bouton l’indique."""
        if hasattr(self, 'tts_button'):
            self.tts_button.setToolTip(f"{self.TTS_TOOLTIP}\n{message}")

    def show_ambience(self):
        """Fenêtre Ambiances : effets, ambiance de fond, musique, voix et thème, rangés par section.

        Chaque section suit la même grille « libellé | réglage | valeur ou bouton » ;
        les choix sont appliqués aussitôt, les curseurs mémorisés à la fermeture."""
        dialog = QDialog(self)
        dialog.setObjectName('ambienceDialog')
        dialog.setWindowTitle("Bifurk — Ambiances")
        dialog.setWindowIcon(self.windowIcon())
        area = dialog.screen().availableGeometry()
        # Deux colonnes dès que l'écran le permet, une seule colonne défilante sinon.
        two_columns = area.width() >= 1060
        dialog.resize(1000 if two_columns else min(560, area.width() - 40),
                      min(640 if two_columns else 900, area.height() - 80))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHeading('Les ambiances de votre aventure',
                                        'Sons, musique, voix et habillage du grimoire.'))
        scroll = QScrollArea()
        scroll.setObjectName('ambienceScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName('ambienceBody')
        columns = (QHBoxLayout if two_columns else QVBoxLayout)(body)
        columns.setContentsMargins(0, 0, 6, 0)
        columns.setSpacing(18 if two_columns else 14)
        left, right = QVBoxLayout(), QVBoxLayout()
        for column in (left, right):
            column.setSpacing(14)
            columns.addLayout(column, 1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        def section(column, title):
            box = QGroupBox(title)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(10)
            grid.setColumnMinimumWidth(0, 78)
            grid.setColumnStretch(1, 1)
            grid.setColumnMinimumWidth(2, 56)
            column.addWidget(box)
            return grid

        def row(grid, label, widget, trailing=None):
            """Ligne alignée : libellé à gauche, réglage, puis valeur ou bouton éventuels."""
            index = grid.rowCount()
            if label is None:   # Case à cocher : toute la largeur avant la dernière colonne.
                grid.addWidget(widget, index, 0, 1, 2 if trailing is not None else 3)
            else:
                caption = QLabel(label)
                caption.setObjectName('settingCaption')
                grid.addWidget(caption, index, 0)
                grid.addWidget(widget, index, 1, 1, 1 if trailing is not None else 2)
            if trailing is not None:
                grid.addWidget(trailing, index, 2)

        # Les curseurs émettent un signal à chaque cran : leurs valeurs ne sont
        # écrites qu'une fois, à la fermeture de la fenêtre (voir finally).
        volume_changed = []

        # --- Effets sonores --------------------------------------------------
        effects_grid = section(left, 'Effets sonores')
        sound = QCheckBox("Activer les effets sonores")
        sound.setObjectName('soundEnabled')
        sound.setChecked(self.sounds.enabled)
        def set_sound(enabled):
            """Appliquer et mémoriser l’interrupteur des effets ponctuels."""
            self.sounds.set_enabled(enabled)
            self.preferences["sound_enabled"] = enabled
            self._save_preferences()
        sound.toggled.connect(set_sound)
        row(effects_grid, None, sound)

        def set_effects_volume(percent):
            self.sounds.set_effects_volume(percent)
            self.preferences['effects_volume'] = percent
            volume_changed.append(True)
        row(effects_grid, 'Volume', *self._volume_slider(
            'effectsVolume', self._percent_preference('effects_volume'),
            set_effects_volume, 'Volume des effets sonores'))
        effects = QComboBox()
        effects.setObjectName('effectPreview')
        effects.setAccessibleName('Effet sonore à écouter')
        for name, label in EFFECT_LABELS.items():
            effects.addItem(label, name)
        listen = QPushButton("Écouter")
        listen.setObjectName('listenEffect')
        listen.setEnabled(self.sounds.enabled)
        sound.toggled.connect(listen.setEnabled)
        listen.clicked.connect(lambda: self.sounds.play(effects.currentData()))
        row(effects_grid, 'Essai', effects, listen)

        # --- Ambiance de fond ------------------------------------------------
        ambient_grid = section(left, 'Ambiance de fond')
        # Même réglage pour tous les livres ; le libellé nomme la boucle du livre ouvert.
        ambient = QCheckBox(f"Activer l’ambiance de fond ({self.sounds.ambient_label()})")
        ambient.setObjectName('ambientEnabled')
        ambient.setChecked(self.sounds.ambient_enabled)
        def set_ambient(enabled):
            """Appliquer et mémoriser l’interrupteur indépendant de l’ambiance."""
            self.sounds.set_ambient_enabled(enabled)
            self.preferences["ambient_enabled"] = enabled
            self._save_preferences()
        ambient.toggled.connect(set_ambient)
        row(ambient_grid, None, ambient)
        # Scène selon le paragraphe (livres qui livrent un catalogue d'ambiances).
        mode = QComboBox()
        mode.setObjectName('ambientMode')
        mode.setAccessibleName('Choix de l’ambiance de fond')
        for key, label in self.AMBIENT_MODES:
            mode.addItem(label[:1].upper() + label[1:], key)
        mode.setCurrentIndex(max(0, mode.findData(self.preferences.get('ambient_mode', 'paragraph'))))
        if self.ambience_map is None:
            mode.setToolTip('Ce livre n’a pas de scènes par paragraphe : '
                            'sa boucle est jouée dans les deux cas.')
        def set_mode(index):
            """Appliquer aussitôt et mémoriser le choix scène / boucle du livre."""
            self.preferences['ambient_mode'] = mode.itemData(index)
            self._save_preferences()
            self._ambience_follow_paragraph(self.current_paragraph)
        mode.currentIndexChanged.connect(set_mode)
        row(ambient_grid, 'Scène', mode)

        def set_ambient_volume(percent):
            self.sounds.set_ambient_volume(percent)
            self.preferences['ambient_volume'] = percent
            volume_changed.append(True)
        row(ambient_grid, 'Volume', *self._volume_slider(
            'ambientVolume', self._percent_preference('ambient_volume'),
            set_ambient_volume, 'Volume de l’ambiance de fond'))
        # Écoute d'essai des scènes : la scène d'avant revient à la fermeture.
        scene_before = self.sounds.scene
        scenes = QComboBox()
        scenes.setObjectName('scenePreview')
        scenes.setAccessibleName('Écouter une scène d’ambiance')
        scenes.addItem('Ambiance du livre', None)
        for key, scene in SCENES.items():
            scenes.addItem(scene['label'][:1].upper() + scene['label'][1:], key)
        scenes.setCurrentIndex(max(0, scenes.findData(self.sounds.scene)))
        # Comme pour les effets : choisir, puis « Écouter » joue la scène choisie
        # (« Ambiance du livre » rend la boucle du livre).
        listen_scene = QPushButton('Écouter')
        listen_scene.setObjectName('listenScene')
        listen_scene.setAccessibleName('Écouter la scène choisie')
        listen_scene.clicked.connect(lambda: self.sounds.set_scene(scenes.currentData()))
        row(ambient_grid, 'Essai', scenes, listen_scene)
        for control in (mode, scenes, listen_scene):
            control.setEnabled(self.sounds.ambient_enabled)
            ambient.toggled.connect(control.setEnabled)
        left.addStretch(1)

        # --- Musique d'accueil -----------------------------------------------
        music_grid = section(right, 'Musique d’accueil')
        def set_music_volume(percent):
            """Conserver le réglage même à zéro, indépendamment des autres canaux audio."""
            self.intro_music.set_volume(percent)
            self.preferences['music_volume'] = percent
            self.preferences['music_enabled'] = percent > 0
            volume_changed.append(True)
        row(music_grid, 'Volume', *self._volume_slider(
            'musicVolume', self.intro_music.volume_percent, set_music_volume,
            'Volume de la musique d’accueil', maximum=100))
        persistent = QCheckBox('Garder la musique en fond pendant la partie')
        persistent.setObjectName('musicPersistent')
        persistent.setToolTip('La musique d’accueil continue en boucle après le début de l’aventure, '
                              'au volume choisi ci-dessus, au lieu de s’éteindre en fondu.')
        persistent.setChecked(self.intro_music.persistent)
        def set_persistent(enabled):
            """Appliquer en direct et mémoriser l’option de musique permanente."""
            self.intro_music.set_persistent(enabled)
            self.preferences['music_persistent'] = enabled
            self._save_preferences()
        persistent.toggled.connect(set_persistent)
        row(music_grid, None, persistent)
        custom = QCheckBox('Jouer ma musique')
        custom.setObjectName('customMusic')
        custom.setToolTip('Remplace la musique d’accueil par les morceaux du dossier musique_perso, '
                          'à côté de Bifurk, enchaînés dans un ordre aléatoire (MP3, M4A, OGG, FLAC, WAV…).')
        custom.setChecked(self.intro_music.custom)
        open_folder = QPushButton('Ouvrir le dossier')
        open_folder.setObjectName('openCustomMusic')
        open_folder.setToolTip(str(bifurk.MUSIC_DIR))
        def open_music_folder():
            """Recréer le dossier s’il a été supprimé, puis l’ouvrir dans l’explorateur."""
            try:
                bifurk.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(bifurk.MUSIC_DIR)))
        open_folder.clicked.connect(open_music_folder)
        row(music_grid, None, custom, open_folder)
        custom_hint = QLabel('Aucun morceau lisible dans musique_perso : la musique habituelle est jouée.')
        custom_hint.setObjectName('customMusicHint')
        custom_hint.setWordWrap(True)
        row(music_grid, None, custom_hint)   # parent avant setVisible : pas de fenêtre isolée
        def refresh_custom_hint():
            """Signaler un dossier vide (ou sans format reconnu) tant que l’option est cochée."""
            custom_hint.setVisible(custom.isChecked() and not self.intro_music.playable_tracks())
        def set_custom(enabled):
            """Basculer en direct entre le dossier personnel et la musique d’accueil."""
            self.intro_music.set_custom(enabled)
            self.preferences['custom_music'] = enabled
            self._save_preferences()
            refresh_custom_hint()
        custom.toggled.connect(set_custom)
        refresh_custom_hint()

        # --- Lecture à voix haute --------------------------------------------
        voice_grid = section(right, 'Lecture à voix haute')
        # Voix Edge : liste en cache, jamais d’attente réseau.
        voice = QComboBox()
        voice.setObjectName('ttsVoice')
        voice.setAccessibleName('Voix de lecture à voix haute')
        current = self.preferences.get("tts_voice", DEFAULT_VOICE)
        voices = available_french_voices() or {DEFAULT_VOICE: DEFAULT_VOICE}
        if current not in voices:
            voices[current] = current
        for voice_id, label in voices.items():
            voice.addItem(label, voice_id)
        voice.setCurrentIndex(max(0, voice.findData(current)))
        def set_voice(index):
            """Appliquer et mémoriser la voix choisie."""
            voice_id = voice.itemData(index)
            if voice_id:
                self.tts.set_voice(voice_id)
                self.preferences["tts_voice"] = voice_id
                self._save_preferences()
        voice.currentIndexChanged.connect(set_voice)
        row(voice_grid, 'Voix', voice)
        def set_tts_volume(percent):
            """Appliquer aussitôt, même pendant une lecture ; mémoriser à la fermeture."""
            self.tts.set_volume(percent / 100)
            self.preferences['tts_volume'] = percent
            volume_changed.append(True)
        row(voice_grid, 'Volume', *self._volume_slider(
            'ttsVolume', int(self.preferences.get('tts_volume', 80)), set_tts_volume,
            'Volume de la lecture à voix haute'))

        # --- Habillage du grimoire -------------------------------------------
        theme_grid = section(right, 'Habillage du grimoire')
        themes = QComboBox()
        themes.setObjectName('themeChoice')
        themes.setAccessibleName('Thème du grimoire')
        def fill_themes():
            """« Selon le grimoire ouvert » nomme le thème appliqué au livre actuel."""
            themes.blockSignals(True)
            themes.clear()
            for key, label in self._theme_choices():
                if key == self.AUTO_THEME and self._theme_choice() == self.AUTO_THEME:
                    label = f'{label} — {self.theme.name}'
                themes.addItem(label, key)
            themes.setCurrentIndex(max(0, themes.findData(self._theme_choice())))
            themes.blockSignals(False)
        def set_theme(index):
            self.choose_theme(themes.itemData(index))
            fill_themes()
        fill_themes()
        themes.currentIndexChanged.connect(set_theme)
        row(theme_grid, 'Thème', themes)
        right.addStretch(1)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText('Fermer')
        close.button(QDialogButtonBox.Close).setProperty('dialogAction', 'primary')
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        try:
            dialog.exec()
        finally:
            if volume_changed:
                self._save_preferences()
            # Fin de l'écoute d'essai : la scène d'avant, puis celle du paragraphe
            # (le mode a pu changer pendant que la fenêtre était ouverte).
            self.sounds.set_scene(scene_before)
            self._ambience_follow_paragraph(self.current_paragraph)
            dialog.deleteLater()
