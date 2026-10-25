"""Adaptateur de présentation de la Cité des Voleurs, sans automatismes de paragraphes.

La consultation conserve le héros et les sauvegardes, mais n'invente aucune règle
à partir du texte. Les 400 renvois sont relus et catalogués (titre neutre, libellé,
condition imprimée résumée) ; ces conditions restent informatives. Aucune action
du Sorcier ni de la Forêt n'est héritée, car leurs numéros de paragraphes
désignent d'autres scènes. Les événements et combats viendront avec l'analyse.
"""
import re

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QMessageBox

from grimoire_modules.fighting_fantasy.controller import FightingFantasyActions
from grimoire_ui import ChoiceCard
from navigation import choice_caption

TITLE = 'La Cité des Voleurs'
CATALOGUED = 'renvois_verifies'
PREVIEW_NOTICE = ('Aventure en préparation : les événements et combats ne sont pas encore automatisés. '
                  'Les renvois permettent pour le moment de consulter le livre.')


class CiteController(FightingFantasyActions):
    """Consulter la couverture, les règles, le prologue et les renvois catalogués."""
    def _cite_entry(self):
        """Lire l'entrée de renvois du passage affiché, jamais des effets de jeu."""
        entry = (self.book_event_catalogue or {}).get('paragraphs', {}).get(str(self.current_paragraph), {})
        return entry if entry.get('status') == CATALOGUED else {}

    def _cite_routes(self):
        """Routes relues du catalogue ; à défaut, les renvois explicites du texte."""
        entry = CiteController._cite_entry(self)
        if entry:
            return entry['routes']
        return self._paragraph_choices(self.paragraphs.get(self.current_paragraph, ''))

    def _reading_link_targets(self):
        """Seuls les renvois relus deviennent des liens ; un nombre du récit reste du texte."""
        return {route['target'] for route in CiteController._cite_routes(self)} & set(self.paragraphs)

    def combat_available(self):
        """Les combats de la Cité ne sont pas encore vérifiés ni automatisés."""
        return False

    def combat_round(self):
        """Refuser aussi un appel direct tant que les rencontres ne sont pas intégrées."""
        self.rules_log.setText('Les combats de cette aventure sont encore en préparation.')

    def _complex_round_blocked(self):
        """Aucun assaut particulier n'existe avant l'intégration des combats."""
        return False

    def _ff_meal_status(self):
        """Les règles de la Cité (page PDF 9) autorisent un repas à tout moment hors combat.

        Comme dans la Forêt, le socle refuse un second repas tant que le héros ne
        s'est pas déplacé ; aucune autorisation de paragraphe n'est exigée.
        """
        char = self.character
        allowed = self.current_paragraph in self.paragraphs and not self.combat_available()
        useful = char['endurance'] < char.get('initial', {}).get('endurance', char['endurance'])
        return bool(allowed), useful, False

    def _ff_meal_not_allowed_reason(self):
        """Nommer la règle de la Cité qui interdit le repas ici."""
        if self.combat_available():
            return 'Pas de repas pendant un combat.'
        return 'Ouvrez d’abord un paragraphe de l’aventure.'

    def eat_meal(self):
        """Revérifier les restrictions même pour un appel direct à la commande."""
        in_combat = self._combat_dialog is not None and not self._combat_dialog.outcome
        if next(option for option in self.care_options(in_combat=in_combat)
                if option['id'] == 'meal')['enabled']:
            FightingFantasyActions.eat_meal(self)

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
        self.paragraph_title.setText(self._paragraph_name(number) or TITLE)
        self.paragraph_number.setText(f'§ {number}')
        self.paragraph_number.show()
        self._render_paragraph_text(self.paragraphs[number])
        self.reader.moveCursor(QTextCursor.Start)
        self._render_choices_and_events(self.paragraphs[number])
        self._update_scene_art()
        self._refresh_action_controls()

    def _render_choices_and_events(self, text):
        """Proposer les renvois de consultation sans déclarer leurs conditions satisfaites.

        La condition imprimée, résumée, reste une information : elle n'est ni
        vérifiée ni appliquée tant que l'analyse du passage n'est pas intégrée."""
        self._clear_dynamic_layout(self.choice_layout)
        self._clear_dynamic_layout(self.event_layout)
        self._clear_dynamic_layout(self.condition_layout)
        self.choice_group.setTitle('⚜  CONSULTER LES PASSAGES')
        for choice in CiteController._cite_routes(self):
            target = choice['target']
            button = ChoiceCard(choice_caption(choice['label'], target))
            button.setObjectName('choiceCard')
            button.setEnabled(target in self.paragraphs)
            if target not in self.paragraphs:
                button.setToolTip(f'Indisponible : destination {target} non détectée dans le PDF importé.')
            elif choice.get('condition_text'):
                button.setToolTip(f'Condition du livre : {choice["condition_text"]}')
            button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
            self.choice_layout.addWidget(button)
        notice = QLabel(PREVIEW_NOTICE)
        notice.setWordWrap(True)
        self.event_layout.addWidget(notice)
        self.choice_group.setVisible(self.choice_layout.count() > 0)
        self.event_group.show()
        self.condition_group.hide()

    def follow_link(self, url):
        """Suivre seulement les liens de paragraphes internes du lecteur."""
        match = re.fullmatch(r'paragraph(?::|%3A)(\d+)', url.toString(), re.IGNORECASE)
        if match and int(match.group(1)) in self._reading_link_targets():
            self.go_to(int(match.group(1)))
