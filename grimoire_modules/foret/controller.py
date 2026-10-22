"""Adaptateur de présentation de la Forêt, sans automatismes de paragraphes.

La consultation conserve le héros et les sauvegardes, mais n'invente aucune règle
à partir du texte. Les 400 entrées restent à revoir ; aucune action du Sorcier
n'est héritée. Les événements seront ajoutés lors des étapes suivantes.
"""
import re
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton
from grimoire_ui import ChoiceCard
from navigation import choice_caption
from grimoire_modules.fighting_fantasy.controller import FightingFantasyActions


class ForetController(FightingFantasyActions):
    """Consulter la couverture, les règles, le prologue et les renvois explicites."""
    def combat_available(self):
        """Les combats de la Forêt ne sont pas encore vérifiés ni automatisés."""
        return False

    def combat_round(self):
        """Refuser aussi un appel direct tant que les rencontres ne sont pas intégrées."""
        self.rules_log.setText('Les combats de cette aventure sont encore en préparation.')

    def go_to(self, number):
        """Afficher un passage sans appliquer d'effet ni préparer un combat par déduction."""
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
        if number not in self.visited_paragraphs:
            self.visited_paragraphs.append(number)
        self.goto_spin.setValue(number)
        self.paragraph_title.setText('La Forêt de la Malédiction')
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
        for choice in self._paragraph_choices(text):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            button.setEnabled(target in self.paragraphs)
            button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
            self.choice_layout.addWidget(button)
        notice = QLabel('Aventure en préparation : les événements et combats ne sont pas encore automatisés. '
                        'Les renvois permettent pour le moment de consulter le livre.')
        notice.setWordWrap(True)
        self.event_layout.addWidget(notice)
        self.choice_group.setVisible(self.choice_layout.count() > 0)
        self.event_group.show()
        self.condition_group.hide()

    def follow_link(self, url):
        """Suivre seulement les liens de paragraphes internes du lecteur."""
        match = re.fullmatch(r'paragraph(?::|%3A)(\d+)', url.toString(), re.I)
        if match:
            self.go_to(int(match.group(1)))
