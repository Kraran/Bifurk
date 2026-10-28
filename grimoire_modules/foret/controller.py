"""Adaptateur de la Forêt : consultation et mécaniques explicitement intégrées.

La consultation conserve le héros et les sauvegardes, mais n'invente aucune règle
à partir du texte. Les 400 entrées sont analysées ; aucune action du Sorcier
n'est héritée. Les profils et actions intégrés sont séparés de l’analyse documentaire.
"""
import re
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QMessageBox
from grimoire_ui import ChoiceCard
from navigation import choice_caption
from .actions import ForetMechanicsActions
from . import rules, feedback


# Raisons affichées sur un choix grisé : elles nomment l’étape à franchir dans le
# passage en cours, jamais l’issue d’un jet, d’un combat ou d’une destination.
ENDED_REASON = 'l’aventure est terminée.'
COMBAT_REASON = 'terminez d’abord le combat de ce passage.'
PENDING_REASON = 'résolvez d’abord l’événement de ce passage.'
DECIDED_REASON = 'la suite de ce passage est déjà déterminée.'


class ForetController(ForetMechanicsActions):
    """Consulter la couverture, les règles, le prologue et les renvois explicites."""
    def _analysed_reading_entry(self):
        """Lire uniquement les métadonnées de consultation, jamais des effets de jeu."""
        entry = (self.book_event_catalogue or {}).get('paragraphs', {}).get(str(self.current_paragraph), {})
        return entry if entry.get('status') == 'analyse_verifiee' else {}

    def _reading_link_targets(self):
        """Un renvoi illisible ou supposé ne doit pas devenir un lien cliquable."""
        # Appel explicite : des adaptateurs de test appellent cette méthode sur un faux hôte.
        return ForetController._reading_link_gate(self)[0]

    def _reading_link_gate(self):
        """Renvois praticables et raison commune des autres (None : raison propre à chaque route).

        Seule source des règles de navigation de la Forêt : les liens, les cartes de
        choix et leurs infobulles en dérivent, sans recopier ces conditions."""
        paragraphs = set(self.paragraphs)
        number = self.current_paragraph
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return set(), ENDED_REASON
        if (str(number) in rules.peek(self.character).get('emergency_exits', {})
                and self._book_state(number).get('foret_target') is not None):
            return {self._book_state(number)['foret_target']} & paragraphs, DECIDED_REASON
        if self.combat_available():
            return set(), COMBAT_REASON
        if ForetMechanicsActions._ff_encounter_pacified(self):
            return {self._combat_entry(number)['combat']['victory_target']} & paragraphs, DECIDED_REASON
        if number in rules.BRANCH_TESTS and not self._book_state(number).get('foret_resolved'):
            return set(), PENDING_REASON
        if number in rules.GAS_PARAGRAPHS and not rules.gas_resolved(self.character, number):
            return set(), PENDING_REASON
        combat = self._foret_combat()
        if combat and (combat['finished'] or combat.get('escaped')):
            profile = self._combat_entry(number)['combat']
            key = 'escape_target' if combat.get('escaped') else 'victory_target'
            return {profile.get(key)} & paragraphs, DECIDED_REASON
        if number in rules.ENTRY_RULES and not rules.ENTRY_RULES[number].get('optional') and not rules.entry_resolved(self.character, number):
            return set(), PENDING_REASON
        if number in rules.PAYMENT_PARAGRAPHS and not rules.payment_resolved(self.character, number):
            return set(), PENDING_REASON
        if number == 204 and not self._book_state(204).get('foret_resolved'):
            if rules.hammer_complete(self.character):
                return set(), PENDING_REASON
            # Marteau incomplet : le retour au §400 garde sa condition imprimée.
            return {381} & paragraphs, None
        if number in rules.BLOCKING_EVENT_PARAGRAPHS and not self._book_state(number).get('foret_resolved'):
            return set(), PENDING_REASON
        if number == 372 and not self._book_state(372).get('foret_resolved'):
            return {288} & paragraphs, PENDING_REASON
        resolved_target = self._book_state(number).get('foret_target')
        if resolved_target is not None:
            return {resolved_target} & paragraphs, DECIDED_REASON
        return {route['target'] for route in self._analysed_reading_entry().get('routes', [])
                if route['target'] in paragraphs
                and rules.route_available(self.character, number, route['target'])}, None

    def _route_tooltip(self, route, targets, reason):
        """Infobulle d’une carte de renvoi, au format du Sorcier : « Indisponible : … » si grisée.

        La condition imprimée reste visible sur une carte praticable ; une carte grisée
        dit pourquoi, sans rien révéler au-delà du passage affiché."""
        target, condition = route['target'], route.get('condition_text')
        if target in targets:
            return f'Condition du livre : {condition}' if condition else ''
        if target not in self.paragraphs:
            return f'Indisponible : destination {target} non détectée dans le PDF importé.'
        if reason is None:
            reason = (f'condition du livre non remplie ({condition}).' if condition
                      else 'condition du livre non remplie.')
        return 'Indisponible : ' + reason

    def go_to(self, number):
        """Afficher le passage et préparer seulement les profils intégrés, sans déduction du texte."""
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
        arrival = (feedback.snapshot(self.character)
                   if not self._restoring and previous != number else None)
        if not self._restoring and previous != number:
            self.sounds.play('page')
            if previous is not None:
                self.transitions.append([previous, number])
        self.current_paragraph = number
        self._tts_follow_paragraph(number)
        self._ambience_follow_paragraph(number)
        if number in rules.TRANSFORMATION_ENDINGS:
            rules.finish_transformation(self.character,number)
            self._refresh_character()
        if number == 400 and rules.peek(self.character).get('won'):
            rules.finish_victory(self.character)
            self._refresh_character()
        if number == 2:
            self.character['endurance'] = 0
            self._refresh_character()
        if number == 98 and previous != number and not self._restoring:
            # Chaque nouvelle tentative de retour à Yaztromo traverse une nouvelle
            # embuscade ; une réussite ancienne ne doit pas ouvrir le chemin.
            self._book_state(number, True).pop('foret_resolved', None)
            self._book_state(number, True).pop('foret_target', None)
        if number == 215 and not self._restoring:
            rules.state(self.character)['barrel_examined'] = True
        if number not in self.visited_paragraphs:
            self.visited_paragraphs.append(number)
        self._foret_prepare_combat()
        if number == 156 and previous != number and not self._restoring:
            rules.damage_hero(self.character, 3)
            self._refresh_character()
        if arrival is not None:
            changes = feedback.describe_changes(arrival, feedback.snapshot(self.character))
            if changes:
                self.rules_log.setText(f'À l’arrivée au §{number} : ' + ', '.join(changes) + '.')
        self.goto_spin.setValue(number)
        self.paragraph_title.setText(self._paragraph_name(number) or 'La Forêt de la Malédiction')
        self.paragraph_number.setText(f'§ {number}')
        self.paragraph_number.show()
        self._render_paragraph_text(self.paragraphs[number])
        self.reader.moveCursor(QTextCursor.Start)
        self._render_choices_and_events(self.paragraphs[number])
        self._update_scene_art()
        self._refresh_action_controls()

    def _render_choices_and_events(self, text):
        """Proposer les renvois de consultation sans déclarer leurs conditions satisfaites."""
        self._clear_dynamic_layout(self.choice_layout)
        self._clear_dynamic_layout(self.event_layout)
        self._clear_dynamic_layout(self.condition_layout)
        ending = rules.peek(self.character).get('ending')
        victory = rules.peek(self.character).get('victory_closed')
        if ending or victory:
            outcome = 'Victoire — le marteau a été remis à Gillibran' if victory else rules.TRANSFORMATION_ENDINGS[ending]
            notice = QLabel('Aventure terminée — ' + outcome + '. Vous pouvez annuler la dernière action ou charger une partie.')
            notice.setWordWrap(True)
            self.event_layout.addWidget(notice)
            self.choice_group.hide()
            self.event_group.show()
            self.condition_group.hide()
            return
        self.choice_group.setTitle('⚜  CONSULTER LES PASSAGES')
        targets, reason = self._reading_link_gate()
        for choice in self._analysed_reading_entry().get('routes', []):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            button.setToolTip(self._route_tooltip(choice, targets, reason))
            button.setEnabled(target in targets)
            button.clicked.connect(lambda checked=False, n=target: self.follow_foret_route(n))
            self.choice_layout.addWidget(button)
        self._foret_mechanics_buttons()
        for route in self._analysed_reading_entry().get('unresolved_routes', []):
            button = ChoiceCard(route['label'])
            button.setEnabled(False)
            button.setToolTip('Indisponible : le renvoi imprimé doit être confirmé dans une autre source.')
            self.choice_layout.addWidget(button)
        for issue in self._analysed_reading_entry().get('source_issues', []):
            if issue['severity'] == 'blocking':
                warning = QLabel('Source à confirmer : ' + issue['details'])
                warning.setWordWrap(True)
                self.event_layout.addWidget(warning)
        if getattr(getattr(self, 'book_module', None), 'status', 'ready') == 'preview':
            notice = QLabel('Aventure en préparation : les mécaniques intégrées disposent de boutons dédiés ; les autres événements restent en cours d’intégration. '
                            'Les renvois permettent pour le moment de consulter le livre.')
            notice.setWordWrap(True)
            self.event_layout.addWidget(notice)
        self.choice_group.setVisible(self.choice_layout.count() > 0)
        # Sans commande (ex. un seul adversaire, donc rien à cibler), la page récupère la place.
        self.event_group.setVisible(self.event_layout.count() > 0)
        self.condition_group.hide()

    def follow_link(self, url):
        """Suivre seulement les liens de paragraphes internes du lecteur."""
        match = re.fullmatch(r'paragraph(?::|%3A)(\d+)', url.toString(), re.I)
        if match and int(match.group(1)) in self._reading_link_targets():
            self.follow_foret_route(int(match.group(1)))

    def follow_foret_route(self, target):
        """Revérifier la route et payer son éventuel coût dans la transaction de navigation."""
        if self._adventurer_draft is not None or target not in self._reading_link_targets():
            return
        before = feedback.snapshot(self.character)
        try:
            rules.pay_route(self.character,self.current_paragraph,target)
        except ValueError as error:
            self.rules_log.setText(str(error))
            return
        self._refresh_character()
        self.go_to(target)
        changes = feedback.describe_changes(before, feedback.snapshot(self.character))
        if changes and self.current_paragraph == target:
            self.rules_log.setText(f'Passage vers le §{target} : ' + ', '.join(changes) + '.')
