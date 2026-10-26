"""Adaptateur de la Cité des Voleurs : §1 à 200 analysés, le reste en consultation.

Les 400 renvois sont relus et catalogués (titre neutre, libellé, condition
imprimée résumée). Pour les passages analysés (§1 à 200), les conditions
imprimées sont appliquées ici, en Python, à partir de ``rules`` et
``encounters`` : combats, épreuves, effets d’arrivée, achats et prix des
renvois. Les autres passages restent consultables : leurs conditions sont
informatives, sauf les prix des renvois qui mènent dans la tranche analysée.
Aucune action du Sorcier ni de la Forêt n’est héritée, car leurs numéros de
paragraphes désignent d’autres scènes.
"""
import re

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QInputDialog, QLabel, QMessageBox

from grimoire_ui import ChoiceCard
from navigation import choice_caption

from . import feedback, rules
from .actions import CiteMechanicsActions, _coins

TITLE = 'La Cité des Voleurs'
CATALOGUED = 'renvois_verifies'
ANALYSED = 'analyse_verifiee'
PREVIEW_NOTICE = ('Aventure en préparation : les événements et combats de ce passage ne sont pas encore '
                  'automatisés. Les renvois permettent pour le moment de consulter le livre.')
ANALYSED_NOTICE = ('Aventure en préparation : les mécaniques intégrées disposent de boutons dédiés ; '
                   'les autres événements restent en cours d’intégration. '
                   'Les renvois permettent pour le moment de consulter le livre.')
ENDED_REASON = 'l’aventure est terminée.'
COMBAT_REASON = 'terminez d’abord le combat de ce passage.'
PENDING_REASON = 'résolvez d’abord l’événement de ce passage.'
DECIDED_REASON = 'la suite de ce passage est déjà déterminée.'


class CiteController(CiteMechanicsActions):
    """Consulter le livre et jouer les mécaniques relues des §1 à 200."""
    def _cite_entry(self):
        """Lire l'entrée de renvois du passage affiché (consultée ou analysée)."""
        entry = (self.book_event_catalogue or {}).get('paragraphs', {}).get(str(self.current_paragraph), {})
        return entry if entry.get('status') in (CATALOGUED, ANALYSED) else {}

    def _cite_routes(self):
        """Routes relues du catalogue ; à défaut, les renvois explicites du texte."""
        entry = CiteController._cite_entry(self)
        if entry:
            routes = [dict(route) for route in entry['routes']]
            for route in routes:
                label = rules.COST_LABELS.get((self.current_paragraph, route['target']))
                if label and not route.get('condition_text'):
                    route['condition_text'] = label
            return routes
        return self._paragraph_choices(self.paragraphs.get(self.current_paragraph, ''))

    def _reading_link_gate(self):
        """Renvois praticables et raison commune des autres (None : raison propre à chaque route).

        Seule source des règles de navigation : liens, cartes et infobulles en dérivent."""
        paragraphs = set(self.paragraphs)
        number = self.current_paragraph
        character = self.character
        routes = CiteController._cite_routes(self)
        if character.get('book_facts', {}).get('adventure_ended'):
            return set(), ENDED_REASON
        visited = getattr(self, 'visited_paragraphs', [])
        available = {route['target'] for route in routes if route['target'] in paragraphs
                     and rules.route_available(character, number, route['target'],
                                               visited if number in rules.ANALYSED else ())}
        if number not in rules.ANALYSED or CiteController._cite_entry(self).get('status') != ANALYSED:
            return available, None
        if self.combat_available():
            return set(), COMBAT_REASON
        combat = self._cite_combat()
        if combat and combat.get('target_paragraph') is not None:
            return {combat['target_paragraph']} & paragraphs, DECIDED_REASON
        if number in rules.BRANCH_TESTS or number in rules.DOUBLE_TESTS:
            if not rules.test_resolved(character, number):
                return set(), PENDING_REASON
            return {rules.test_target(character, number)} & paragraphs, DECIDED_REASON
        if number == rules.DIE_HEAL and rules.peek(character).get('die_heal') is None:
            return set(), PENDING_REASON
        if number == rules.THEFT and not rules.theft_resolved(character):
            return set(), PENDING_REASON
        if number == rules.VOLLEY and not rules.volley_resolved(character):
            return set(), PENDING_REASON
        if number == rules.POCKET and not rules.pocket_resolved(character):
            return set(), PENDING_REASON
        return available, None

    def _reading_link_targets(self):
        """Seuls les renvois praticables deviennent des liens ; un nombre du récit reste du texte."""
        return CiteController._reading_link_gate(self)[0]

    def _route_tooltip(self, route, targets, reason):
        """« Condition du livre : … » si praticable, sinon « Indisponible : … », sans rien révéler."""
        target, condition = route['target'], route.get('condition_text')
        cost = rules.route_cost(self.current_paragraph, target)
        if target in targets:
            tip = f'Condition du livre : {condition}' if condition else ''
            key = (self.current_paragraph, target)
            if not rules.adventure.route_paid(self.character, rules.BOOK, *key):
                if cost:
                    tip += (' — ' if tip else '') + f'{_coins(cost)} payée{"s" if cost > 1 else ""} en choisissant ce renvoi.'
                elif key in rules.ALL_GOLD_ROUTES:
                    tip += (' — ' if tip else '') + 'Tout votre or est remis en choisissant ce renvoi.'
                elif key in rules.ITEM_PAYMENTS:
                    tip += (' — ' if tip else '') + 'Un objet est remis en choisissant ce renvoi.'
            return tip
        if target not in self.paragraphs:
            return f'Indisponible : destination {target} non détectée dans le PDF importé.'
        if reason is None:
            reason = (f'condition du livre non remplie ({condition}).' if condition
                      else 'condition du livre non remplie.')
        return 'Indisponible : ' + reason

    def _ff_meal_status(self):
        """Les règles de la Cité (page PDF 9) autorisent un repas à tout moment hors combat."""
        char = self.character
        allowed = self.current_paragraph in self.paragraphs and not self.combat_available()
        useful = char['endurance'] < char.get('initial', {}).get('endurance', char['endurance'])
        return bool(allowed), useful, False

    def _ff_meal_not_allowed_reason(self):
        if self.combat_available():
            return 'Pas de repas pendant un combat.'
        return 'Ouvrez d’abord un paragraphe de l’aventure.'

    def eat_meal(self):
        """Revérifier les restrictions même pour un appel direct à la commande."""
        in_combat = self._combat_dialog is not None and not self._combat_dialog.outcome
        if next(option for option in self.care_options(in_combat=in_combat)
                if option['id'] == 'meal')['enabled']:
            CiteMechanicsActions.eat_meal(self)

    def go_to(self, number):
        """Afficher le passage, appliquer une fois ses effets relus et préparer son combat."""
        if self._adventurer_draft is not None and not self._restoring:
            return
        if self.character['endurance'] <= 0 and not self._restoring:
            self._show_death_page()
            return
        if number not in self.paragraphs:
            QMessageBox.information(self, 'Paragraphe absent', f'Le paragraphe {number} est introuvable.')
            return
        previous = self.current_paragraph
        self._ff_note_move(number)
        arrival = feedback.snapshot(self.character) if not self._restoring and previous != number else None
        if not self._restoring and previous != number:
            self.sounds.play('page')
            if previous is not None:
                self.transitions.append([previous, number])
        self.current_paragraph = number
        if number not in self.visited_paragraphs:
            self.visited_paragraphs.append(number)
        if not self._restoring and number in rules.ANALYSED:
            rules.apply_entry(self.character, number)
            rules.finish_ending(self.character, number)
            self._cite_prepare_combat()
            self._refresh_character()
        if arrival is not None:
            changes = feedback.describe_changes(arrival, feedback.snapshot(self.character))
            if changes:
                self.rules_log.setText(f'À l’arrivée au §{number} : ' + ', '.join(changes) + '.')
        self.goto_spin.setValue(number)
        self.paragraph_title.setText(self._paragraph_name(number) or TITLE)
        self.paragraph_number.setText(f'§ {number}')
        self.paragraph_number.show()
        self._render_paragraph_text(self.paragraphs[number])
        self.reader.moveCursor(QTextCursor.Start)
        self._render_choices_and_events(self.paragraphs[number])
        self._update_scene_art()
        self._refresh_action_controls()

    def _render_choices_and_events(self, text):
        """Cartes de renvoi, commandes intégrées, puis l’avis de préparation."""
        self._clear_dynamic_layout(self.choice_layout)
        self._clear_dynamic_layout(self.event_layout)
        self._clear_dynamic_layout(self.condition_layout)
        if rules.peek(self.character).get('ending'):
            notice = QLabel('Aventure terminée — votre mission s’arrête ici. '
                            'Vous pouvez annuler la dernière action ou charger une partie.')
            notice.setWordWrap(True)
            self.event_layout.addWidget(notice)
            self.choice_group.hide()
            self.event_group.show()
            self.condition_group.hide()
            return
        self.choice_group.setTitle('⚜  CONSULTER LES PASSAGES')
        targets, reason = CiteController._reading_link_gate(self)
        for choice in CiteController._cite_routes(self):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            button.setEnabled(target in targets)
            tip = CiteController._route_tooltip(self, choice, targets, reason)
            if tip:
                button.setToolTip(tip)
            button.clicked.connect(lambda checked=False, n=target: self.follow_cite_route(n))
            self.choice_layout.addWidget(button)
        self._cite_mechanics_buttons()
        analysed = CiteController._cite_entry(self).get('status') == ANALYSED
        if getattr(getattr(self, 'book_module', None), 'status', 'ready') == 'preview':
            notice = QLabel(ANALYSED_NOTICE if analysed else PREVIEW_NOTICE)
            notice.setWordWrap(True)
            self.event_layout.addWidget(notice)
        self.choice_group.setVisible(self.choice_layout.count() > 0)
        self.event_group.setVisible(self.event_layout.count() > 0)
        self.condition_group.hide()

    def follow_link(self, url):
        """Suivre seulement les liens de paragraphes internes du lecteur."""
        match = re.fullmatch(r'paragraph(?::|%3A)(\d+)', url.toString(), re.IGNORECASE)
        if match and int(match.group(1)) in self._reading_link_targets():
            self.follow_cite_route(int(match.group(1)))

    def _cite_arrow_payment(self):
        """§248 : 10 Pièces d’Or ou deux objets ; None si le joueur renonce."""
        options = []
        if self.character.get('gold', 0) >= rules.ARROW_PRICE:
            options.append(_coins(rules.ARROW_PRICE))
        choices = rules.magic_payment_choices(self.character)
        if len(choices) >= rules.ARROW_ITEMS:
            options.append('Deux objets du sac…')
        if not options:
            return None
        choice = options[0]
        if len(options) > 1:
            choice, accepted = QInputDialog.getItem(self, 'Le prix demandé', 'Payer avec :', options, 0, False)
            if not accepted:
                return None
        if choice.startswith('Deux'):
            return self._cite_pick_items('Le prix demandé', 'Choisissez deux objets de votre sac.',
                                         choices, rules.ARROW_ITEMS, 'Payer')
        return []

    def follow_cite_route(self, target):
        """Revérifier la route et payer son éventuel prix dans la transaction de navigation."""
        if self._adventurer_draft is not None or target not in self._reading_link_targets():
            return
        source = self.current_paragraph
        before = feedback.snapshot(self.character)
        items = ()
        if ((source, target) == rules.ARROW_OFFER
                and not rules.adventure.route_paid(self.character, rules.BOOK, source, target)):
            items = CiteController._cite_arrow_payment(self)
            if items is None:
                return
        if ((source, target) in rules.ITEM_PAYMENTS
                and not rules.adventure.route_paid(self.character, rules.BOOK, source, target)):
            items = self._cite_pick_items('Un objet à remettre', 'Choisissez l’objet que vous remettez.',
                                          rules.item_payment_choices(self.character, (source, target)),
                                          1, 'Remettre')
            if items is None:
                return
        try:
            paid = rules.pay_route(self.character, source, target, items)
        except ValueError as error:
            self.rules_log.setText(str(error))
            return
        self._refresh_character()
        self.go_to(target)
        changes = feedback.describe_changes(before, feedback.snapshot(self.character))
        if paid and changes and self.current_paragraph == target:
            self.rules_log.setText(f'Passage vers le §{target} : ' + ', '.join(changes) + '.')
