"""Relier les règles relues des §1 à 200 de la Cité aux transactions et aux dés de Qt.

Comme les autres adaptateurs, les méthodes sont déléguées à MainWindow : appeler
explicitement le socle plutôt que super(). Les libellés et infobulles ne disent
jamais où mène une issue ni ce qui attend le héros ; ils reprennent seulement
ce que le passage affiché imprime (score à battre, prix, condition).
"""
from copy import deepcopy

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..fighting_fantasy.adventure import advance_group, damage_hero, new_group_combat
from ..fighting_fantasy.controller import FightingFantasyActions
from ..fighting_fantasy.rules import escape_damage
from . import feedback, rules
from .encounters import COMBATS, escape_status, profile, victory_target

CHANCE_COST = 'Tenter sa Chance coûte 1 point de Chance.'


def _coins(amount):
    return f'{amount} Pièce{"s" if amount > 1 else ""} d’Or'


class CiteMechanicsActions(FightingFantasyActions):
    def _ff_stat_value(self, key):
        return rules.effective_skill(self.character) if key == 'habilete' else self.character.get(key, 0)

    def _cite_analysed(self, number=None):
        number = self.current_paragraph if number is None else number
        return number in rules.ANALYSED

    # ----- Combats -------------------------------------------------------------
    def _combat_entry(self, number):
        """Profil intégré du passage ; seules les cibles de victoire et de fuite y figurent."""
        data = COMBATS.get(number)
        if data is None:
            return None
        combat = {'mode': 'paired', 'victory_target': data['victory']}
        if 'escape' in data:
            combat['escape_target'] = data['escape']
        return {'combat': combat}

    def _cite_combat(self):
        return rules.peek(self.character).get('combats', {}).get(str(self.current_paragraph))

    def _cite_prepare_combat(self):
        """Préparer une fois la rencontre ; relire ou charger conserve les blessures."""
        number = self.current_paragraph
        if number not in COMBATS or self._restoring or self.character['endurance'] <= 0:
            return
        unless = COMBATS[number].get('unless_item')
        if unless and rules.has_item(self.character, unless[0]):
            return
        combats = rules.state(self.character).setdefault('combats', {})
        if str(number) not in combats:
            combats[str(number)] = new_group_combat(profile(number))
        self._cite_sync_enemy()

    def _cite_sync_enemy(self):
        combat = self._cite_combat()
        if not combat or combat['finished'] or combat.get('escaped'):
            return
        self._set_book_enemy(combat['groups'][combat['group']][0])

    def _combat_roster(self):
        combat = self._cite_combat()
        if not combat:
            return None
        return [deepcopy(enemy) for group in combat['groups'] for enemy in group]

    def _complex_round_blocked(self):
        return not self.combat_available()

    def combat_available(self):
        combat = self._cite_combat()
        return bool(combat and not combat['finished'] and not combat.get('escaped')
                    and self.character['endurance'] > 0 and self._adventurer_draft is None
                    and not self.character.get('book_facts', {}).get('adventure_ended'))

    def combat_flee_status(self):
        if not self.combat_available():
            return False, 'Aucun combat en cours.'
        escape = COMBATS[self.current_paragraph].get('escape')
        if escape is not None and escape not in self.paragraphs:
            return False, 'Une destination nécessaire à la fuite est absente du livre chargé.'
        return escape_status(self.current_paragraph, self._cite_combat())

    def _ff_combat_profile(self):
        attack = COMBATS.get(self.current_paragraph, {}).get('attack', 0)
        return {'skill': rules.effective_skill(self.character), 'hit_damage': 2,
                'can_wound': True, 'attack_bonus': attack}

    def _ff_enemy_defeated(self):
        """L’adversaire suivant est préparé après l’assaut, par advance_group."""

    def _ff_after_hit(self):
        """La sortie du combat est résolue à la fin de l’assaut."""

    def combat_round(self):
        """Un assaut contre l’adversaire courant ; les égalités comptent comme assauts."""
        if self.current_paragraph not in COMBATS:
            self.rules_log.setText('Aucun combat n’est intégré à ce passage : il reste en préparation.')
            return
        if not self.combat_available():
            return
        combat = self._cite_combat()
        enemy = combat['groups'][combat['group']][0]
        FightingFantasyActions.combat_round(self)
        enemy['stamina'] = self.enemy_endurance.value()
        combat['assaults'] += 1
        if self.character['endurance'] > 0:
            advance_group(combat)
            if combat['finished']:
                number = self.current_paragraph
                combat['target_paragraph'] = victory_target(number, combat['assaults'])
                self.completed_book_events.add(number)
                self._cite_after_combat()
                if combat['target_paragraph'] in self.paragraphs:
                    self.go_to(combat['target_paragraph'])
            else:
                self._cite_sync_enemy()
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def _cite_after_combat(self):
        """Broche scorpion d’argent : 1 point d’Endurance après chaque combat survécu."""
        if rules.has_item(self.character, rules.SILVER_BROOCH) and self.character['endurance'] > 0:
            before = self.character['endurance']
            cap = self.character.get('initial', {}).get('endurance', before)
            self.character['endurance'] = max(before, min(cap, before + 1))
            if self.character['endurance'] > before:
                self._log_combat_detail('Broche scorpion d’argent : +1 Endurance.')

    def escape_scripted_combat(self, number):
        """Blessure de fuite des règles ; au §73, le bouclier est jeté (Habileté −1)."""
        if number != self.current_paragraph or not self.can_flee_combat():
            return
        total = None
        if self._ask_combat_question('Fuir', 'Tenter votre Chance pour la blessure de fuite ?') == QMessageBox.Yes:
            _, total = self._roll(2, context='Chance — fuite')
        damage, cost = escape_damage(self.character['chance'], total)
        self.character['chance'] = max(0, self.character['chance'] - cost)
        damage_hero(self.character, rules.BOOK, damage)
        data = COMBATS[number]
        if data.get('escape_skill'):
            self.character['habilete'] = max(0, self.character['habilete'] - data['escape_skill'])
            for name in rules.matching_items(self.character, 'bouclier')[:1]:
                self.character['inventory'].remove(name)
        combat = self._cite_combat()
        combat['escaped'] = True
        combat['target_paragraph'] = data['escape']
        self._remember_monster(self.enemy_name.text(), 'fui')
        self._cite_after_combat()
        self._refresh_character()
        if self.character['endurance'] > 0:
            self.go_to(data['escape'])

    # ----- Commandes du passage -------------------------------------------------
    def _cite_test_button(self, number):
        stat = rules.BRANCH_TESTS[number][0]
        if stat == 'chance':
            return f'Tenter votre Chance (2d6 ≤ {self.character.get("chance", 0)})', CHANCE_COST
        score = rules.effective_skill(self.character)
        return f'Épreuve d’Habileté (2d6 ≤ {score})', 'Réussite si le total des deux dés ne dépasse pas votre Habileté.'

    def _cite_mechanics_buttons(self):
        """Afficher les seules commandes implantées ; tout est revérifié au clic."""
        def add(label, action, enabled=True, tooltip=''):
            button = QPushButton(label)
            if tooltip:
                button.setToolTip(tooltip)
            button.setEnabled(enabled and self.character['endurance'] > 0)
            button.setProperty('combatAction', False)
            if action == 'shop':
                button.clicked.connect(lambda checked=False: self._cite_shop())
            elif action == 'theft':
                button.clicked.connect(lambda checked=False: self._cite_theft_dialog())
            elif action == 'pocket':
                button.clicked.connect(lambda checked=False: self._cite_pocket_dialog())
            else:
                button.clicked.connect(lambda checked=False: self.perform_cite_action(action))
            self.event_layout.addWidget(button)
        number = self.current_paragraph
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return
        if number in rules.BRANCH_TESTS and not rules.test_resolved(self.character, number):
            label, tip = self._cite_test_button(number)
            add(label, 'branch_test', tooltip=tip)
        if number == rules.DIE_HEAL and rules.peek(self.character).get('die_heal') is None:
            add('Lancer un dé — Endurance regagnée', 'die_heal',
                tooltip='Le total initial d’Endurance ne peut être dépassé.')
        if number == rules.THEFT and not rules.theft_resolved(self.character):
            count = rules.theft_required(self.character)
            add('Constater le larcin de l’Elfe…' if count else 'Constater le larcin de l’Elfe',
                'theft', tooltip=f'{count} objet(s) du sac à dos et jusqu’à {_coins(rules.THEFT_GOLD)}.')
        if number in rules.DOUBLE_TESTS and not rules.test_resolved(self.character, number):
            luck = self.character.get('chance', 0)
            add(f'Tenter deux fois votre Chance (2d6 ≤ {luck}, puis ≤ {max(0, luck - 1)})',
                'double_test', tooltip='Chaque tentative coûte 1 point de Chance.')
        if number == rules.VOLLEY and not rules.volley_resolved(self.character):
            add('Lancer un dé — flèches reçues', 'volley',
                tooltip=f'{rules.VOLLEY_HIT} points d’Endurance par flèche, '
                        f'puis {rules.VOLLEY_AFTER} points de plus, comme l’indique le livre.')
        if number == rules.POCKET and not rules.pocket_resolved(self.character):
            add('Constater le larcin…', 'pocket',
                tooltip='Une Pièce d’Or ou un objet de votre choix.')
        if number in rules.SHOPS:
            add('Faire ses achats…', 'shop', tooltip='Achats facultatifs, aux prix indiqués par le livre.')
        if rules.has_item(self.character, 'emplatre'):
            fighting = self.combat_available()
            add('Appliquer l’emplâtre d’herbes — un dé d’Endurance', 'poultice', enabled=not fighting,
                tooltip='Pas pendant un combat.' if fighting
                else 'Le total initial d’Endurance ne peut être dépassé ; l’emplâtre est utilisé.')

    def perform_cite_action(self, action, payload=None):
        """Commande transactionnelle, suivie d’un compte rendu dans le cadre de messages."""
        if self._adventurer_draft is not None or self.current_paragraph is None:
            return
        number = self.current_paragraph
        before = feedback.snapshot(self.character)
        self._roll_trace = []
        try:
            outcome = CiteMechanicsActions._cite_action_body(self, action, payload)
        finally:
            trace, self._roll_trace = self._roll_trace, None
        if outcome == 'error':
            return
        kind = ({'branch_test': rules.BRANCH_TESTS.get(number, ('',))[0], 'double_test': 'chance'}
                .get(action))
        moved = self.current_paragraph if self.current_paragraph != number else None
        message = feedback.summary(before, feedback.snapshot(self.character),
                                   kind=kind, trace=trace, destination=moved)
        if message:
            self.rules_log.setText(message)

    def _cite_action_body(self, action, payload=None):
        if self.character['endurance'] <= 0 or self.character.get('book_facts', {}).get('adventure_ended'):
            return
        number = self.current_paragraph
        target = None
        try:
            if action == 'branch_test':
                if number not in rules.BRANCH_TESTS or rules.test_resolved(self.character, number):
                    return
                stat = rules.BRANCH_TESTS[number][0]
                _, total = self._roll(2, context='Chance' if stat == 'chance' else 'Habileté')
                target = rules.resolve_test(self.character, number, total)
            elif action == 'die_heal':
                if number != rules.DIE_HEAL:
                    return
                _, die = self._roll(1, context='Endurance regagnée')
                rules.heal_die(self.character, die)
            elif action == 'theft':
                if number != rules.THEFT:
                    return
                rules.elf_theft(self.character, payload or ())
            elif action == 'buy':
                if number not in rules.SHOPS:
                    return
                rules.buy(self.character, number, payload)
            elif action == 'double_test':
                if number not in rules.DOUBLE_TESTS or rules.test_resolved(self.character, number):
                    return
                totals = [self._roll(2, context='Chance')[1] for _ in range(2)]
                trace = self._roll_trace if isinstance(self._roll_trace, list) else []
                if len(trace) >= 2 and trace[-2].get('chance') is not None:
                    # Le point de Chance du premier essai est dépensé avant le second.
                    trace[-1] = dict(trace[-1], chance=max(0, trace[-2]['chance'] - 1))
                target = rules.resolve_double(self.character, number, totals)
            elif action == 'volley':
                if number != rules.VOLLEY or rules.volley_resolved(self.character):
                    return
                _, die = self._roll(1, context='Flèches')
                rules.volley(self.character, die)
            elif action == 'pocket':
                if number != rules.POCKET or rules.pocket_resolved(self.character):
                    return
                rules.pick_pocket(self.character, payload)
            elif action == 'poultice':
                if not rules.has_item(self.character, 'emplatre') or self.combat_available():
                    return
                _, die = self._roll(1, context='Emplâtre')
                rules.use_poultice(self.character, die)
            else:
                return
        except ValueError as error:
            self.rules_log.setText(str(error))
            return 'error'
        self._refresh_character()
        if self.character['endurance'] > 0 and target in self.paragraphs:
            self.go_to(target)
        elif self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    # ----- Dialogues ---------------------------------------------------------------
    def _cite_shop(self):
        """Chaque achat est une transaction ; fermer le dialogue ne dépense rien."""
        number = self.current_paragraph
        shop = rules.SHOPS.get(number)
        if not shop:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Les achats du passage')
        layout = QVBoxLayout(dialog)
        header = QLabel('Un seul achat possible ici.' if shop['limit'] == 1
                        else 'Chaque article ne s’achète qu’une fois.')
        header.setWordWrap(True)
        layout.addWidget(header)
        selector = QComboBox()
        for name, _price in shop['items']:
            selector.addItem('', name)
        layout.addWidget(selector)
        balance = QLabel()
        balance.setObjectName('shopBalance')
        layout.addWidget(balance)
        buy = QPushButton('Acheter')
        layout.addWidget(buy)

        def refresh():
            bought = rules.shop_bought(self.character, number)
            for index, (name, price) in enumerate(shop['items']):
                selector.setItemText(index, f'{name} — {_coins(price)}'
                                     + (' — acheté' if name in bought else ''))
            reason = rules.can_buy(self.character, number, selector.currentData())
            balance.setText(f'Or disponible : {_coins(self.character.get("gold", 0))}')
            buy.setEnabled(reason is None and self.character['endurance'] > 0)
            buy.setToolTip(reason or '')

        def purchase():
            self.perform_cite_action('buy', selector.currentData())
            refresh()
        selector.currentIndexChanged.connect(refresh)
        buy.clicked.connect(purchase)
        close = QPushButton('Revenir au grimoire')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        refresh()
        dialog.exec()
        dialog.deleteLater()

    def _cite_pick_items(self, title, text, choices, count, confirm_label):
        """Choisir exactement count exemplaires ; None si le joueur annule."""
        if count == 0:
            return []
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        items = QListWidget()
        items.setSelectionMode(QAbstractItemView.MultiSelection)
        items.addItems(choices)
        layout.addWidget(items)
        confirm = QPushButton(confirm_label)
        confirm.setEnabled(False)
        items.itemSelectionChanged.connect(
            lambda: confirm.setEnabled(len(items.selectedItems()) == count))
        confirm.clicked.connect(dialog.accept)
        layout.addWidget(confirm)
        cancel = QPushButton('Annuler')
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(cancel)
        accepted = dialog.exec() == QDialog.Accepted
        selected = [item.text() for item in items.selectedItems()]
        dialog.deleteLater()
        return selected if accepted else None

    def _cite_pocket_dialog(self):
        if self.current_paragraph != rules.POCKET or rules.pocket_resolved(self.character):
            return
        choices = rules.pocket_choices(self.character)
        if not choices:
            self.perform_cite_action('pocket')
            return
        chosen = self._cite_pick_items('Le larcin', 'Choisissez ce qui vous est pris.',
                                       choices, 1, 'Valider')
        if chosen:
            self.perform_cite_action('pocket', chosen[0])

    def _cite_theft_dialog(self):
        if self.current_paragraph != rules.THEFT or rules.theft_resolved(self.character):
            return
        count = rules.theft_required(self.character)
        chosen = self._cite_pick_items(
            'Le larcin de l’Elfe', f'Choisissez {count} objet(s) de votre sac à dos.',
            rules.theft_choices(self.character), count, 'Valider')
        if chosen is not None:
            self.perform_cite_action('theft', chosen)
