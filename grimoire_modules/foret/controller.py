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
from . import rules


class ForetController(ForetMechanicsActions):
    """Consulter la couverture, les règles, le prologue et les renvois explicites."""
    def _analysed_reading_entry(self):
        """Lire uniquement les métadonnées de consultation, jamais des effets de jeu."""
        entry = (self.book_event_catalogue or {}).get('paragraphs', {}).get(str(self.current_paragraph), {})
        return entry if entry.get('status') == 'analyse_verifiee' else {}

    def _reading_link_targets(self):
        """Un renvoi illisible ou supposé ne doit pas devenir un lien cliquable."""
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return set()
        if (str(self.current_paragraph) in rules.peek(self.character).get('emergency_exits', {})
                and self._book_state(self.current_paragraph).get('foret_target') is not None):
            return {self._book_state(self.current_paragraph)['foret_target']} & set(self.paragraphs)
        if self.combat_available():
            return set()
        if ForetMechanicsActions._ff_encounter_pacified(self):
            return {self._combat_entry(self.current_paragraph)['combat']['victory_target']} & set(self.paragraphs)
        if self.current_paragraph in rules.BRANCH_TESTS and not self._book_state(self.current_paragraph).get('foret_resolved'):
            return set()
        if self.current_paragraph in rules.GAS_PARAGRAPHS and not rules.gas_resolved(self.character,self.current_paragraph):
            return set()
        combat = self._foret_combat()
        if combat and (combat['finished'] or combat.get('escaped')):
            profile = self._combat_entry(self.current_paragraph)['combat']
            key = 'escape_target' if combat.get('escaped') else 'victory_target'
            return {profile.get(key)} & set(self.paragraphs)
        if self.current_paragraph in rules.ENTRY_RULES and not rules.ENTRY_RULES[self.current_paragraph].get('optional') and not rules.entry_resolved(self.character, self.current_paragraph):
            return set()
        if self.current_paragraph in rules.PAYMENT_PARAGRAPHS and not rules.payment_resolved(self.character, self.current_paragraph):
            return set()
        if self.current_paragraph == 204 and not self._book_state(204).get('foret_resolved'):
            return ({381} & set(self.paragraphs)) if not rules.hammer_complete(self.character) else set()
        if self.current_paragraph in (48,73,309,52,266,304,328,262,204,388,98,259,278,34,308,395,154,370,192,60,182,358,178) and not self._book_state(self.current_paragraph).get('foret_resolved'):
            return set()
        if self.current_paragraph == 372 and not self._book_state(372).get('foret_resolved'):
            return {288} & set(self.paragraphs)
        resolved_target = self._book_state(self.current_paragraph).get('foret_target')
        if resolved_target is not None:
            return {resolved_target} & set(self.paragraphs)
        return {route['target'] for route in self._analysed_reading_entry().get('routes', [])
                if route['target'] in self.paragraphs
                and rules.route_available(self.character, self.current_paragraph, route['target'])}

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
        if not self._restoring and previous != number:
            self.sounds.play('page')
            if previous is not None:
                self.transitions.append([previous, number])
        self.current_paragraph = number
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
        for choice in self._analysed_reading_entry().get('routes', []):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            if choice.get('condition_text'):
                button.setToolTip('Condition du livre : ' + choice['condition_text'])
            button.setEnabled(target in self._reading_link_targets())
            button.clicked.connect(lambda checked=False, n=target: self.follow_foret_route(n))
            self.choice_layout.addWidget(button)
        self._foret_mechanics_buttons()
        for route in self._analysed_reading_entry().get('unresolved_routes', []):
            button = ChoiceCard(route['label'])
            button.setEnabled(False)
            button.setToolTip('Le renvoi imprimé doit être confirmé dans une autre source.')
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
        self.event_group.show()
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
        try:
            rules.pay_route(self.character,self.current_paragraph,target)
        except ValueError as error:
            self.rules_log.setText(str(error))
            return
        self._refresh_character()
        self.go_to(target)
