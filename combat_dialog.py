"""Fenêtre de combat : présentation interactive du moteur existant.

Les assauts restent résolus par MainWindow.combat_round et ses règles de livre.
Seule l'attente utilisateur utilise une boucle Qt imbriquée : elle laisse le rendu
et la fiche se rafraîchir sans dupliquer dégâts, jets ou historique d'annulation.
Le contrôleur ne peut démarrer deux actions pendant ces attentes.
"""
import copy
import html
from string import Template

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QTextBrowser, QVBoxLayout, QScrollArea,
                               QWidget, QSizePolicy, QLayout, QComboBox, QCheckBox)

from book_events import verified_entry
from dice_dialog import DiceCanvas
from grimoire_ui import ChoiceCard
from stat_feedback import STAT_LABELS, StatFeedback, monster_stat_anchor, rich_stat_anchor


class CombatDialog(QDialog):
    """Deux combattants, leurs dés et une chronique conservée jusqu'à l'issue finale.

Revenir au livre suspend la fenêtre, pas les règles : un assaut déjà commencé
est d'abord terminé avec les dés tirés, sans dépense de Chance facultative.
Le même objet peut être rouvert pour conserver sa chronique dans cette session.
"""

    def __init__(self, owner):
        """Lire le combat préparé ; aucune caractéristique n'est réinitialisée."""
        super().__init__(owner)
        self.owner = owner
        self.setObjectName('combatDialog')
        self.setWindowTitle('Bifurk — Le champ de bataille')
        self.setWindowIcon(owner.windowIcon())
        area = owner.screen().availableGeometry()
        self.resize(min(1100, max(780, area.width() - 60)), min(720, max(560, area.height() - 70)))
        self.setMinimumSize(780, 560)
        self.origin = owner.current_paragraph
        self.paragraphs = {self.origin}
        self.roster = self._initial_roster()
        self.phase = 'idle'
        self.busy = False
        self.outcome = None
        self.closing = False
        self._wait_loop = None
        self._choice = False
        self._canvas = None
        self._last_enemy_dead = False
        self._round_number = 0
        self._scheduled = False
        self._launch_requested = False
        self._care_open = False
        # Des minuteries filles sont annulées avec la fenêtre. Des singleShot
        # sans contexte peuvent rappeler un objet Python dont Qt a détruit le C++.
        self._begin_timer = QTimer(self)
        self._begin_timer.setSingleShot(True)
        self._begin_timer.timeout.connect(self._begin_round)
        self._dice_timer = QTimer(self)
        self._dice_timer.setSingleShot(True)
        self._dice_timer.timeout.connect(self._start_dice)
        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self.accept)
        self.setStyleSheet(Template('''
            QDialog#combatDialog { background: $scene_background; }
            QFrame#combatCard { background: $icon_background; border: 1px solid $ornament; border-radius: 12px; }
            QLabel#combatHeading { font-size: 18px; font-weight: bold; color: $gold; }
            QLabel#combatStats { font-size: 18px; color: $page; }
            QTextBrowser#opponentStats { background: transparent; color: $page;
                border: none; font-family: '$ui_font'; font-size: 18px; }
            QLabel#combatBanner { font-size: 34px; font-weight: bold; color: $gold; padding: 12px; }
            QLabel#combatPrompt { font-size: 16px; color: $page; }
            QTextBrowser#battleHistory { background: $scene_background; color: $page;
                border: 1px solid $ornament; border-radius: 8px; padding: 10px;
                font-family: '$ui_font'; font-size: 15px; }
            QPushButton#heroRoll { background: $page; color: $ink;
                font-size: 17px; font-weight: bold; padding: 13px; min-width: 170px; }
            QPushButton#heroRoll:disabled { background: $scene_background; color: $ornament; }
        ''').substitute({**owner.theme.colors, 'ui_font': owner.ui_font_family}))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 3)
        self.enemy_card, enemy_layout = self._card('LES ADVERSAIRES')
        self.enemies = QTextBrowser()
        self.enemies.setObjectName('opponentStats')
        self.enemies.setMinimumHeight(115)
        enemy_layout.addWidget(self.enemies, 1)
        grid.addWidget(self.enemy_card, 0, 0)
        self.hero_card, hero_layout = self._card('L’AVENTURIER')
        self.hero = QLabel()
        self.hero.setWordWrap(True)
        self.hero.setObjectName('combatStats')
        hero_layout.addWidget(self.hero)
        self.weapon = QComboBox()
        self.weapon.setAccessibleName('Arme utilisée pendant le combat')
        self.weapon.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.weapon.currentTextChanged.connect(self._change_weapon)
        hero_layout.addWidget(self.weapon)
        self.shield = QCheckBox('Utiliser le bouclier')
        self.shield.toggled.connect(self._change_shield)
        hero_layout.addWidget(self.shield)
        hero_layout.addStretch()
        grid.addWidget(self.hero_card, 0, 2)
        center, center_layout = self._card('CHRONIQUE DU COMBAT')
        self.banner = QLabel('⚔  Face au danger')
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setWordWrap(True)
        self.banner.setObjectName('combatBanner')
        center_layout.addWidget(self.banner)
        self.history = QTextBrowser()
        self.history.setObjectName('battleHistory')
        self.history.setMinimumSize(0, 100)
        self.history.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        center_layout.addWidget(self.history, 1)
        self.action_scroll = QScrollArea()
        self.action_scroll.setObjectName('combatActions')
        self.action_scroll.setWidgetResizable(True)
        self.action_scroll.setFrameShape(QFrame.NoFrame)
        self.action_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.action_scroll.setMaximumHeight(145)
        self.action_scroll.setMinimumHeight(0)
        actions_host = QWidget()
        self.actions = QVBoxLayout(actions_host)
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.action_scroll.setWidget(actions_host)
        self.action_scroll.hide()
        center_layout.addWidget(self.action_scroll)
        grid.addWidget(center, 0, 1, 2, 1)
        self.enemy_tray, self.enemy_tray_layout = self._card('DÉS ADVERSES — AUTOMATIQUES')
        self.enemy_placeholder = QLabel('Le monstre prépare son attaque…')
        self.enemy_placeholder.setWordWrap(True)
        self.enemy_tray_layout.addWidget(self.enemy_placeholder)
        grid.addWidget(self.enemy_tray, 1, 0)
        self.hero_tray, self.hero_tray_layout = self._card('VOS DÉS')
        self.hero_placeholder = QLabel('À vous de lancer les dés.')
        self.hero_placeholder.setWordWrap(True)
        self.hero_tray_layout.addWidget(self.hero_placeholder)
        grid.addWidget(self.hero_tray, 1, 2)
        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 3)
        layout.addLayout(grid, 1)
        self.prompt = QLabel('')
        self.prompt.setWordWrap(True)
        self.prompt.setTextFormat(Qt.PlainText)
        self.prompt.setObjectName('combatPrompt')
        self.prompt.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.prompt)
        controls = QHBoxLayout()
        self.pause = QPushButton('Revenir au livre')
        self.pause.setToolTip('Un assaut commencé est terminé avant de revenir au livre.')
        self.pause.clicked.connect(self.reject)
        controls.addWidget(self.pause)
        self.flee = QPushButton('Fuir')
        self.flee.setObjectName('fleeCombat')
        self.flee.clicked.connect(self._flee)
        controls.addWidget(self.flee)
        self.care = QPushButton('Soins')
        self.care.setObjectName('combatCare')
        self.care.setCheckable(True)
        self.care.clicked.connect(self._toggle_care)
        controls.addWidget(self.care)
        controls.addStretch()
        self.secondary = QPushButton('Tenter ma Chance')
        self.secondary.setAutoDefault(False)
        self.secondary.clicked.connect(lambda: self._answer(True))
        self.secondary.hide()
        controls.addWidget(self.secondary)
        self.primary = QPushButton('Lancer mes dés')
        self.primary.setObjectName('heroRoll')
        self.primary.clicked.connect(self._primary_clicked)
        self.primary.setEnabled(False)
        controls.addWidget(self.primary)
        layout.addLayout(controls)
        self._trays = {}
        self.monster_feedback = {}
        self.stat_feedback = StatFeedback(self, {
            key: (self.hero, lambda widget, k=key: rich_stat_anchor(widget,
                  f'{STAT_LABELS[k]} {self.owner.character[k]}')) for key in STAT_LABELS
        }, lambda: self.owner.theme)
        self.refresh_stats()

    def _card(self, heading):
        """Construire une surface lisible avec titre distinct de son contenu."""
        frame = QFrame()
        frame.setObjectName('combatCard')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel(heading)
        title.setWordWrap(True)
        title.setObjectName('combatHeading')
        layout.addWidget(title)
        return frame, layout

    def _initial_roster(self):
        """Afficher les seuls ennemis du combat courant, sans dévoiler d'autres lieux."""
        entry = verified_entry(self.owner.book_event_catalogue, self.origin) or {}
        combat = entry.get('combat', {})
        if combat.get('mode') == 'sequence':
            roster = copy.deepcopy(combat['enemies'])
            index = (self.owner.book_combat_sequence or {}).get('index', 0)
            for enemy in roster[:index]:
                enemy['stamina'] = 0
        elif combat.get('mode') == 'paired':
            roster = copy.deepcopy(combat.get('enemies', []))
            state = self.owner._book_state(self.origin)
            if state.get('pair', -1) >= 0:
                for enemy in roster:
                    enemy['stamina'] = 0
            for index, pair in enumerate(combat.get('pairs', [])):
                for enemy in copy.deepcopy(pair):
                    enemy['group'] = index
                    roster.append(enemy)
        elif combat.get('mode') == 'wandering':
            monster = self.owner._book_state(self.origin).get('monster')
            roster = [copy.deepcopy(monster)] if monster else []
        elif combat.get('mode') == 'piranhas':
            pending = (self.owner.piranha_combat or {}).get('status') == 'roll_pending'
            roster = [{'name': 'Piranhas', 'skill': 5,
                       'stamina': self.owner.enemy_endurance.value() if not pending else 0,
                       'pending': pending}]
        else:
            roster = [{'name': self.owner.enemy_name.text(), 'skill': self.owner.enemy_skill.value(),
                       'stamina': self.owner.enemy_endurance.value()}]
        return roster

    def refresh_stats(self):
        """Lire le même état que la fiche principale ; ne pas conserver un second héros."""
        owner = self.owner
        current = owner.enemy_name.text()
        sequence_index = None
        if owner.current_paragraph in self.paragraphs and not self.outcome:
            entry = verified_entry(owner.book_event_catalogue, owner.current_paragraph) or {}
            mode = entry.get('combat', {}).get('mode')
            if mode == 'wandering' and not self.roster:
                monster = owner._book_state(owner.current_paragraph).get('monster')
                if monster:
                    self.roster.append(copy.deepcopy(monster))
            group = owner._book_state(owner.current_paragraph).get('pair')
            sequence = owner.book_combat_sequence
            if mode == 'sequence' and sequence and sequence['paragraph'] == owner.current_paragraph:
                # Le moteur conserve encore la cible à zéro avant de préparer
                # la suivante. Son indice évite de modifier un homonyme vivant.
                sequence_index = sequence['index']
                active = self.roster[sequence_index] if 0 <= sequence_index < len(self.roster) else None
            else:
                active = next((e for e in self.roster if e['name'] == current and (e['stamina'] > 0 or e.get('pending'))
                               and ('group' not in e or e['group'] == group)), None)
            if active:
                if mode != 'piranhas' or (owner.piranha_combat or {}).get('status') != 'roll_pending':
                    active['stamina'] = owner.enemy_endurance.value()
                    active['skill'] = owner.enemy_skill.value()
                    active.pop('pending', None)
        parts = []
        active_anchor = None
        for index, enemy in enumerate(self.roster):
            is_current = index == sequence_index if sequence_index is not None else enemy['name'] == current
            status = 'Vaincu' if enemy['stamina'] <= 0 else 'Au combat' if is_current else 'En attente'
            if 'group' in enemy:
                group = owner._book_state(self.origin).get('pair', -1)
                if enemy['group'] < group and enemy['stamina'] > 0:
                    status = 'Groupe terminé'
                elif enemy['group'] > group:
                    status = 'En attente'
            if self.outcome:
                status = 'Vaincu' if enemy['stamina'] <= 0 else 'Combat terminé'
            stamina = 'à déterminer' if enemy.get('pending') else enemy['stamina']
            if enemy.get('pending'):
                status = 'Jet préalable nécessaire'
            if status == 'Au combat':
                active_anchor = f'enemy-{index}'
            # Griser toute la fiche vaincue, en conservant le même paragraphe
            # pour les ancres de défilement et les animations des derniers dégâts.
            color = owner.theme.colors.get('defeated_enemy', '#aaa39b')
            muted = f' style="color:{color}"' if status == 'Vaincu' else ''
            parts.append(f"<p><a name='enemy-{index}'></a><span{muted}><b>{html.escape(enemy['name'])}</b><br>"
                         f"Habileté {enemy['skill']}<br>Endurance {stamina}<br><small>{status}</small></span></p>")
        roster_html = ''.join(parts) or 'Adversaire à déterminer selon le livre.'
        if roster_html != getattr(self, '_roster_html', None):
            # Ne pas reconstruire le document ni déplacer sa lecture quand
            # seul le héros change : ses badges restent indépendants de la liste.
            previous_scroll = self.enemies.verticalScrollBar().value()
            self.enemies.setText(roster_html)
            if active_anchor:
                self.enemies.scrollToAnchor(active_anchor)
            else:
                # Le coup mortel reste visible sans ancre d'ennemi vivant.
                self.enemies.verticalScrollBar().setValue(previous_scroll)
            self._roster_html = roster_html
        char = owner.character
        self.hero.setText(f"<b>{html.escape(char.get('name') or 'Votre aventurier')}</b><br>"
                          f"Habileté {char['habilete']}<br>Endurance {char['endurance']}<br>Chance {char['chance']}"
                          f"<br><small>Habileté de combat : {owner._ff_combat_profile()['skill']}</small>")
        self.weapon.blockSignals(True)
        weapons = [self.owner.weapon_combo.itemText(i) for i in range(self.owner.weapon_combo.count())]
        if weapons != [self.weapon.itemText(i) for i in range(self.weapon.count())]:
            self.weapon.clear()
            self.weapon.addItems(weapons)
        self.weapon.setCurrentText(self.owner.weapon_combo.currentText())
        self.weapon.blockSignals(False)
        self.shield.blockSignals(True)
        self.shield.setVisible(self.owner.shield_check.isVisible() or
                               'Bouclier au croissant' in char.get('inventory', []))
        self.shield.setChecked(bool(char.get('shield_equipped')))
        self.shield.blockSignals(False)
        self._refresh_footer()
        self.stat_feedback.observe(char,
            enabled=self.isVisible() and not self.owner._restoring,
            batch=self.owner._feedback_action_id)
        self._refresh_monster_feedback()

    def _refresh_monster_feedback(self):
        """Comparer chaque adversaire à ses propres valeurs, y compris après sa mort.

        L'indice dans la liste reste stable lors des combats successifs ou par
        paires. L'arrivée du suivant n'est donc jamais interprétée comme un soin.
        Les valeurs provisoires des Piranhas ne servent pas de référence.
        """
        for index, enemy in enumerate(self.roster):
            feedback = self.monster_feedback.get(index)
            if enemy.get('pending'):
                if feedback is not None:
                    feedback.clear()
                    feedback.previous = None
                continue
            if feedback is None:
                viewport = self.enemies.viewport()
                feedback = StatFeedback(viewport, {
                    key: (viewport, lambda widget, i=index, k=key: monster_stat_anchor(
                        self.enemies, i, f'{STAT_LABELS[k]} {self.roster[i]["skill" if k == "habilete" else "stamina"]}'))
                    for key in ('habilete', 'endurance')
                }, lambda: self.owner.theme)
                self.monster_feedback[index] = feedback
            feedback.observe({'habilete': enemy['skill'], 'endurance': enemy['stamina']},
                enabled=self.isVisible() and not self.owner._restoring,
                batch=self.owner._feedback_action_id)

    def _refresh_footer(self):
        """Stabiliser Fuir / Soins en bas, sans autoriser une action concurrente au lancer."""
        if not hasattr(self, 'flee'):
            return
        can_act = not self.busy and not self.outcome
        permitted, reason = self.owner.combat_flee_status()
        self.flee.setEnabled(can_act and permitted)
        if self.outcome:
            reason = 'Ce combat est terminé.'
        elif self.busy:
            reason = 'Terminez l’assaut ou l’action en cours avant de fuir.'
        self.flee.setToolTip(reason)
        # Le lecteur existe derrière cette fenêtre modale. Garder son bouton
        # cohérent aussi lors des pauses imbriquées (dés, Chance et soins).
        for index in range(self.owner.event_layout.count()):
            source = self.owner.event_layout.itemAt(index).widget()
            if source is not None and source.property('combatEscape'):
                source.setEnabled(self.flee.isEnabled())
                source.setToolTip(reason)
        # Une potion peut être bue dans les pauses de décision de l'assaut. Elle
        # appartient alors à la même transaction que cet assaut, sans second jet.
        care_pause = not self.busy or self.phase in ('player', 'luck')
        options = self.owner.care_options(in_combat=not bool(self.outcome))
        self.care.setEnabled(care_pause and self.outcome != 'Défaite' and any(o['enabled'] for o in options))
        self.care.setToolTip('Choisir un soin autorisé.' if self.care.isEnabled()
                             else 'Aucun soin utilisable ou lancer en cours.')
        self.weapon.setEnabled(can_act)
        self.shield.setEnabled(can_act)

    def _flee(self):
        """Revérifier la fuite au clic et déléguer coûts, Chance et destination au moteur."""
        if not self.busy and not self.outcome and self.owner.can_flee_combat():
            self._run(lambda: self.owner.escape_scripted_combat(self.owner.current_paragraph))

    def _toggle_care(self):
        """Ouvrir les soins dans la zone défilante, sans masquer le journal ni lancer un assaut."""
        self._care_open = self.care.isChecked()
        self._pause_preparation()
        self._refresh_actions()

    def _apply_care(self, kind):
        """Appliquer une potion ou un repas autorisé sans remplacer le résultat de l'assaut."""
        if self.busy and self.phase not in ('player', 'luck'):
            return
        self._pause_preparation()
        self.owner.use_care(kind)
        self.log(self.owner.rules_log.text())
        self._care_open = False
        self.care.setChecked(False)
        self.refresh_stats()
        self._refresh_actions()

    def _change_weapon(self, name):
        """Réutiliser la commande annulable de la sacoche entre deux assauts."""
        if name and not self.busy and not self.outcome:
            self._pause_preparation()
            self.owner.change_weapon(name)
            self.log(self.owner.rules_log.text())

    def _change_shield(self, checked):
        """Mettre à jour le même équipement que la fiche sans dupliquer son bonus."""
        if not self.busy and not self.outcome:
            self._pause_preparation()
            self.owner.change_shield_use(checked)
            self.owner._refresh_character()
            self.log(self.owner.rules_log.text())

    def _pause_preparation(self):
        """Laisser finir les préparatifs avant un assaut pas encore commencé."""
        if not self.busy and not self.outcome:
            self._begin_timer.stop()
            self._scheduled = False
            self._launch_requested = False
            self.phase = 'next'
            self.primary.setText('Assaut suivant')
            self.primary.setEnabled(self._round_available())

    def log(self, text, *, bold=False):
        """Conserver toute la chronique de cette fenêtre, sans limite de soixante coups."""
        # Chaque entrée fixe sa graisse pour ne pas propager celle du titre au récit.
        escaped = html.escape(text).replace('\n', '<br>')
        weight = 'bold' if bold else 'normal'
        self.history.append(f'<span style="font-weight: {weight};">{escaped}</span>')
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    def note_assault(self, player, enemy, player_attack, enemy_attack, outcome):
        """Capturer l'ennemi avant que le moteur prépare l'adversaire suivant."""
        self._last_enemy_dead = self.owner.enemy_endurance.value() <= 0
        self.refresh_stats()
        self.log(f'{self.owner.enemy_name.text()} : {enemy} → {enemy_attack} | '
                 f'Aventurier : {player} → {player_attack}\n{outcome}')

    def showEvent(self, event):
        """À l'ouverture ou reprise, laisser Qt afficher la fenêtre avant l'attaque automatique."""
        super().showEvent(event)
        self.closing = False
        self._schedule_round()

    def _schedule_round(self):
        """Ne programmer qu'un seul assaut, même si le dialogue est réaffiché."""
        if not self._scheduled and not self.busy and not self.outcome and not self.closing:
            self._scheduled = True
            self._begin_timer.start(0)

    def _begin_round(self):
        """Lancer automatiquement les dés adverses ; le moteur attendra ensuite le joueur."""
        self._scheduled = False
        if not self.isVisible() or self.closing or self.busy or self.outcome:
            return
        self._refresh_actions()
        owner = self.owner
        if not self._round_available():
            self.prompt.setText(owner.rules_log.text())
            return
        if owner.can_flee_combat() and not self._launch_requested:
            self.phase = 'next'
            self.primary.setText('Engager l’assaut' if self._round_number == 0 else 'Assaut suivant')
            self.primary.setEnabled(True)
            self.prompt.setText('Vous pouvez fuir selon le livre ou engager le prochain assaut.')
            self._refresh_footer()
            return
        self._launch_requested = False
        self._round_number += 1
        self.log(f'— Assaut {self._round_number} —', bold=True)
        self._run(owner.combat_round)

    def _round_available(self):
        """Respecter les préconditions du livre avant toute préparation d'assaut."""
        owner = self.owner
        entry = verified_entry(owner.book_event_catalogue, owner.current_paragraph) or {}
        if entry.get('combat', {}).get('precombat_escape'):
            return False
        crocodile = owner.crocodile_combat
        blocked = (owner._complex_round_blocked()
                   or (owner.current_paragraph == 350 and owner.piranha_combat
                       and owner.piranha_combat.get('status') == 'roll_pending')
                   or (crocodile and crocodile['phase'] == 'initial' and crocodile['assaults'] >= 2))
        return not blocked and owner.enemy_endurance.value() > 0 and owner.character['endurance'] > 0

    def _run(self, action):
        """Exécuter une seule action suivie du moteur et observer son issue après ses hooks."""
        if self.busy or self.outcome:
            return
        self._care_open = False
        self.care.setChecked(False)
        self.busy = True
        self._refresh_footer()
        for index in range(self.actions.count()):
            self.actions.itemAt(index).widget().setEnabled(False)
        self._last_enemy_dead = False
        before = self.owner.current_paragraph
        entry = verified_entry(self.owner.book_event_catalogue, before) or {}
        mode = entry.get('combat', {}).get('mode')
        try:
            action()
        finally:
            self.busy = False
            self.phase = 'idle'
            self.secondary.hide()
            self.primary.setEnabled(False)
        owner = self.owner
        after = owner.current_paragraph
        next_entry = verified_entry(owner.book_event_catalogue, after) or {}
        continuation = mode in ('silver', 'invulnerable') and next_entry.get('combat', {}).get('mode') == 'silver'
        if continuation:
            self.paragraphs.add(after)
        self.refresh_stats()
        if owner.character['endurance'] <= 0:
            self._finish('Défaite')
        elif mode == 'paired' and before in owner.completed_book_events:
            self._finish('Victoire')
        elif mode == 'sequence' and not owner.book_combat_sequence and self._last_enemy_dead:
            self._finish('Victoire')
        elif mode not in ('paired', 'sequence') and (self._last_enemy_dead or owner.enemy_endurance.value() <= 0):
            self._finish('Victoire')
        elif after != before and not continuation:
            # Le livre peut interrompre un combat sans tuer l'adversaire : fuite,
            # premier coup réussi, paralysie, limite d'assauts. Ne pas inventer un décès.
            won = entry.get('combat', {}).get('first_hit_target') == after
            self._finish('Victoire' if won else 'Combat terminé')
        elif self.closing:
            super().accept()
        else:
            self._refresh_actions()
            # Entre les coups, le joueur peut lire le journal, fuir ou se soigner.
            # Le prochain assaut déclenche à nouveau les dés rouges automatiquement.
            self.phase = 'next'
            allowed = self._round_available()
            self.primary.setText('Assaut suivant' if allowed else 'Choisissez une action')
            self.primary.setEnabled(allowed)
            self.prompt.setText(owner.rules_log.text())
        self._refresh_footer()

    def _refresh_actions(self):
        """Réutiliser les boutons du livre et leurs contrôles plutôt que dupliquer ses règles."""
        while self.actions.count():
            widget = self.actions.takeAt(0).widget()
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        layout = self.owner.event_layout
        for index in range(layout.count()):
            source = layout.itemAt(index).widget()
            if (isinstance(source, QPushButton) and source.property('combatAction')
                    and not source.property('combatEscape')):
                button = ChoiceCard(source.text())
                button.setEnabled(source.isEnabled() and not self.busy)
                button.clicked.connect(lambda checked=False, source=source: self._run(source.click))
                self.actions.addWidget(button)
        if self._care_open:
            for option in self.owner.care_options(in_combat=not bool(self.outcome)):
                button = ChoiceCard(option['label'])
                button.setEnabled(option['enabled'])
                button.setToolTip(option['reason'] if not option['enabled'] else '')
                button.clicked.connect(lambda checked=False, kind=option['id']: self._apply_care(kind))
                self.actions.addWidget(button)
        self.action_scroll.setVisible(self.actions.count() > 0)
        self._refresh_footer()

    def present_roll(self, rolls, context, *, opponent=False, sides=6):
        """Attendre le clic du joueur ou démarrer le dé rouge automatiquement, sans relancer."""
        layout = self.enemy_tray_layout if opponent else self.hero_tray_layout
        placeholder = self.enemy_placeholder if opponent else self.hero_placeholder
        placeholder.setVisible(not opponent)
        previous = self._trays.get(opponent)
        if previous:
            layout.removeWidget(previous)
            previous.hide()
            previous.deleteLater()
        canvas = DiceCanvas(rolls, self.owner.theme, self,
                            color='#b52c39' if opponent else None,
                            pip_color='#fff1d4' if opponent else None, caption=False, sides=sides)
        canvas.setMinimumSize(160, 125)
        canvas.hide()
        layout.addWidget(canvas, 1)
        self._trays[opponent] = canvas
        self._canvas = canvas
        self.prompt.setText(context)
        self.phase = 'opponent' if opponent else 'player'
        self._refresh_footer()
        self.primary.setText('Lancer mes dés')
        self.primary.setEnabled(not opponent)
        self.secondary.hide()
        self._wait_loop = QEventLoop(self)
        canvas.finished.connect(self._release_wait)
        if self.closing:
            canvas.finish()
        else:
            if opponent:
                self._dice_timer.start(0)
            else:
                self.primary.setFocus()
            self._wait_loop.exec()
        self._wait_loop.deleteLater()
        self._wait_loop = None
        self._canvas = None
        self.primary.setEnabled(False)
        self.log(f'{context} : ' + ' + '.join(map(str, rolls)) + f' = {sum(rolls)}')

    def _start_dice(self):
        """Le mouvement commence seulement quand le bon camp est autorisé à lancer."""
        if self._canvas:
            if self._canvas is self._trays.get(True):
                self.enemy_placeholder.hide()
            else:
                self.hero_placeholder.hide()
            self.owner.sounds.play('dice')
            self.phase = 'animating'
            self._refresh_footer()
            self.primary.setEnabled(False)
            self._canvas.show()
            self._canvas.start()

    def choose_luck(self, text):
        """Présenter la décision de Chance au centre du combat, sans ouvrir une autre fenêtre."""
        if self.closing:
            return False
        self.refresh_stats()
        self.log(text)
        self.prompt.setText(text)
        self.phase = 'luck'
        self._refresh_footer()
        self._choice = False
        self.primary.setText('Sans Chance')
        self.primary.setEnabled(True)
        self.primary.setDefault(True)
        self.primary.setFocus()
        self.secondary.show()
        self._wait_loop = QEventLoop(self)
        self._wait_loop.exec()
        self._wait_loop.deleteLater()
        self._wait_loop = None
        self.secondary.hide()
        return self._choice

    def _primary_clicked(self):
        """Un bouton unique lance les dés, refuse la Chance ou poursuit après l'issue."""
        if self.outcome:
            super().accept()
        elif self.phase == 'player':
            self._start_dice()
        elif self.phase == 'luck':
            self._answer(False)
        elif self.phase == 'next':
            self.primary.setEnabled(False)
            self._launch_requested = True
            self._schedule_round()

    def _answer(self, lucky):
        """Répondre une fois à la décision attendue, en laissant le moteur dépenser la Chance."""
        if self.phase == 'luck':
            self._choice = lucky
            self.primary.setEnabled(False)
            self.secondary.hide()
            self._release_wait()

    def _release_wait(self):
        """Sortir uniquement de l'attente courante ; les règles reprennent sur la même pile d'appel."""
        if self._wait_loop:
            self._wait_loop.quit()

    def _finish(self, outcome):
        """Annoncer la victoire finale ou laisser voir la défaite avant l'écran de fin de partie."""
        self.outcome = outcome
        self.refresh_stats()
        self.banner.setText(outcome.upper())
        self.log(self.owner.rules_log.text())
        self.prompt.setText('La rencontre est remportée.' if outcome == 'Victoire'
                            else 'Votre aventure est terminée.' if outcome == 'Défaite'
                            else self.owner.rules_log.text())
        self.primary.setText('Fin de l’aventure' if outcome == 'Défaite' else 'Continuer l’aventure')
        self.primary.setEnabled(True)
        self.secondary.hide()
        self.pause.hide()
        self._refresh_actions()
        for index in range(self.actions.count()):
            self.actions.itemAt(index).widget().setEnabled(False)
        if outcome == 'Défaite':
            self._exit_timer.start(1800)
        elif self.closing:
            self._exit_timer.start(600)

    def reject(self):
        """Ne pas abandonner un jet déjà tiré ni conserver une transaction ouverte en quittant."""
        if not self.busy:
            super().reject()
            return
        self.closing = True
        self.prompt.setText('Fin de l’assaut en cours, puis retour au livre…')
        if self._canvas:
            self._canvas.finish()
        else:
            self._choice = False
            self._release_wait()

    def accept(self):
        """Une fermeture externe suit la même règle de fin d'assaut que la croix native."""
        if self.busy:
            self.reject()
        else:
            super().accept()

    def done(self, result):
        """Suspendre les rappels de la vue avant fermeture, y compris entre deux assauts."""
        for timer in (self._begin_timer, self._dice_timer, self._exit_timer):
            timer.stop()
        self._scheduled = False
        super().done(result)
