"""Manette : crochets lus par gamepad.GamepadNavigator et fenêtre Réglages → Manette.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

from dialog_chrome import DialogHeading

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QVBoxLayout


class ManetteMixin:
    """Manette : crochets lus par gamepad.GamepadNavigator et fenêtre Réglages → Manette."""

    # ------------------------------------------------------------------ manette
    GAMEPAD_HELP = (('Croix ou stick gauche', 'Se déplacer entre les boutons, les choix et les objets'),
                    ('A', 'Valider (choix, bouton, objet de la sacoche)'),
                    ('B', 'Retour : fermer une fenêtre, un menu, le carnet ou le mode lecture'),
                    ('X', 'Lire le paragraphe à voix haute'),
                    ('Y', 'Annuler la dernière action'),
                    ('LB / RB', 'Passer au bandeau, à la page ou à la fiche'),
                    ('LT / RT', 'Réduire ou agrandir le texte'),
                    ('Stick droit', 'Faire défiler le texte (clic : ouvrir le carnet)'),
                    ('Menu', 'Réglages'),
                    ('Affichage', 'Mode lecture'))

    def gamepad_halo_color(self):
        return self.theme.color('gold')

    def gamepad_scope(self):
        """Carnet ouvert ou fiche en tiroir : la manette reste dans ce panneau."""
        if self.carnet_is_open():
            return self.carnet_overlay
        if getattr(self, '_drawer_open', False):
            return self.side_scroll
        return None

    def gamepad_default(self, scope):
        """Première sélection : le premier choix du paragraphe, sinon Grimoires sans livre."""
        if scope is None or scope is self.reader_panel:
            cards = [card for card in self._visible_choice_cards() if card.isVisible() and card.isEnabled()]
            if cards:
                return cards[0]
            if scope is None and self.pdf_path is None and self.open_btn.isVisible():
                return self.open_btn
        return None

    def gamepad_zones(self):
        return [self.header_frame, self.reader_panel, self.side_scroll]

    def gamepad_scroll_area(self):
        return self.reader

    def gamepad_command(self, name):
        """Boutons propres au jeu ; False laisse la navigation générique s'en charger."""
        if name == 'b':
            if self.carnet_is_open():
                self.close_carnet()
            elif getattr(self, '_drawer_open', False) or self.reading_mode:
                self._escape_layout_mode()
            return True
        if name == 'rs':
            self.toggle_carnet()
            return True
        if self.carnet_is_open():
            return False
        if name == 'x':
            if self.tts_button.isVisible() and self.tts_button.isEnabled():
                self.tts_button.click()
        elif name == 'y':
            if self.undo_btn.isEnabled():
                self.undo_btn.click()
        elif name == 'start':
            if self.settings_button.isVisible():
                self.settings_button.click()
            else:
                self.settings_button.menu().exec(self.mapToGlobal(self.rect().center()))
        elif name == 'back':
            self.toggle_reading_mode()
        elif name in ('lt', 'rt'):
            self.change_reader_font_size(-2 if name == 'lt' else 2)
        else:
            return False
        return True

    def show_gamepad(self):
        """Fenêtre Manette : état de la détection, activation et rappel des commandes."""
        dialog = QDialog(self)
        dialog.setObjectName('gamepadDialog')
        dialog.setWindowTitle('Bifurk — Manette')
        dialog.setWindowIcon(self.windowIcon())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        if not self.gamepad.available:
            status = 'Les manettes sont prises en charge sous Windows (XInput).'
        elif self.gamepad.backend.slot is not None:
            status = 'Manette détectée.'
        else:
            status = 'Aucune manette détectée : branchez-la, elle sera reconnue aussitôt.'
        layout.addWidget(DialogHeading('Jouer à la manette', status))
        enabled = QCheckBox('Utiliser la manette')
        enabled.setObjectName('gamepadEnabled')
        enabled.setChecked(self.gamepad.enabled)
        def set_enabled(on):
            self.gamepad.set_enabled(on)
            self.preferences['gamepad_enabled'] = bool(on)
            self._save_preferences()
        enabled.toggled.connect(set_enabled)
        layout.addWidget(enabled)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        for row, (button, action) in enumerate(self.GAMEPAD_HELP):
            key = QLabel(button)
            key.setObjectName('settingCaption')
            grid.addWidget(key, row, 0)
            grid.addWidget(QLabel(action), row, 1)
        layout.addLayout(grid)
        note = QLabel('Manettes Xbox et compatibles ; une manette PlayStation fonctionne avec '
                      'Steam ou DS4Windows. Le nom de l’aventurier se saisit au clavier.')
        note.setObjectName('customMusicHint')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('Fermer')
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()
