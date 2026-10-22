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
        if self.combat_available():
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
        if self.current_paragraph in (73,309,52,266,304,328,262,204,388,98,259,278,34,308,395,154,370) and not self._book_state(self.current_paragraph).get('foret_resolved'):
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
        if number == 98 and previous != number and not self._restoring:
            # Chaque nouvelle tentative de retour à Yaztromo traverse une nouvelle
            # embuscade ; une réussite ancienne ne doit pas ouvrir le chemin.
            self._book_state(number, True).pop('foret_resolved', None)
            self._book_state(number, True).pop('foret_target', None)
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
        self.choice_group.setTitle('⚜  CONSULTER LES PASSAGES')
        for choice in self._analysed_reading_entry().get('routes', []):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            if choice.get('condition_text'):
                button.setToolTip('Condition du livre : ' + choice['condition_text'])
            button.setEnabled(target in self._reading_link_targets())
            button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
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
            self.go_to(int(match.group(1)))
