"""Écran de fin : carte « chronique » sur la page finale, fenêtre de bilan, musique de la mort.

Mixin de MainWindow (voir main.py), sans état propre ni __init__. La carte apparaît au
§400 d'un grimoire reconnu (victoire), sur la page de mort et sur les autres fins
imprimées (adventure_ended). La mort du héros (page de mort ou fin mortelle imprimée)
lance « Towards the Horizon » en boucle, comme « Achievement » accompagne la victoire ;
la chronique elle-même ne change pas la musique."""
from adventure_tracking import LABELS
from chronicle import ChronicleDialog, adventure_summary
from grimoire_ui import ChoiceCard


class EpilogueMixin:
    """Écran de fin : carte « chronique » sur la page finale, fenêtre de bilan, musique de la mort."""

    def _adventure_outcome(self):
        """'victory', 'death', 'ending' ou None tant que la partie continue."""
        character = getattr(self, 'character', None) or {}
        if getattr(self, '_adventurer_draft', None) is not None or not character.get('name'):
            return None
        if character.get('endurance', 1) <= 0:
            return 'death'
        if (getattr(self, 'book_module', None) is not None
                and self.current_paragraph == self.VICTORY_PARAGRAPH):   # voir AmbiancesMixin
            return 'victory'
        if character.get('book_facts', {}).get('adventure_ended'):
            return 'ending'
        return None

    def _add_epilogue_card(self, first=False):
        """Ajouter (une seule fois) la carte qui ouvre la chronique de fin."""
        outcome = self._adventure_outcome()
        if outcome == 'death':
            self._start_death_music()
        layout = self.choice_layout
        if outcome is None or any(getattr(layout.itemAt(i).widget(), 'objectName', lambda: '')()
                                  == 'epilogueCard' for i in range(layout.count())):
            return None
        card = ChoiceCard('✦  Conclure la chronique' if outcome == 'victory'
                          else '✦  Lire la chronique de l’aventure')
        card.setObjectName('epilogueCard')
        card.setToolTip('Bilan de la partie : paragraphes visités, combats gagnés, état final')
        card.clicked.connect(self.show_epilogue)
        if first:
            layout.insertWidget(0, card)
        else:
            layout.addWidget(card)
        self.choice_group.show()
        return card

    def _start_death_music(self):
        """Mort du héros : « Towards the Horizon » remplace la musique et baisse l'ambiance."""
        music = getattr(self, 'intro_music', None)
        if music is None or music.special == 'epilogue':
            return
        music.start_epilogue()
        if getattr(self, 'sounds', None) is not None:
            self.sounds.duck_ambient(True)

    def _death_music_follow(self, number):
        """Appelé à chaque changement d'écran : hors de la mort, la musique de la mort s'arrête.

        Accueil, page de titre, chargement (number None) ou héros de nouveau en vie
        (annulation) : fondu, puis la musique d'accueil ou l'ambiance reprennent."""
        music = getattr(self, 'intro_music', None)
        if music is None or music.special != 'epilogue':
            return
        if number is None or self._adventure_outcome() != 'death':
            music.stop_epilogue()
            if getattr(self, 'sounds', None) is not None:
                self.sounds.duck_ambient(False)

    def epilogue_summary(self):
        return adventure_summary(self.character, self.visited_paragraphs, self.transitions,
                                 self.encounter_history)

    def show_epilogue(self):
        """Bilan de la partie ; la musique de la page (victoire ou mort) continue dessous."""
        outcome = self._adventure_outcome()
        if outcome is None:
            return None
        book = self.book_module.title if getattr(self, 'book_module', None) else ''
        dialog = ChronicleDialog(outcome, self.epilogue_summary(),
                                 hero=self.character.get('name') or 'Aventurier', book=book,
                                 tracking=LABELS.get(self.adventure_tracking.get('status'), ''),
                                 parent=self)
        try:
            dialog.exec()
        finally:
            choice = dialog.choice
            dialog.deleteLater()
        if choice == 'restart':
            self._restart_adventure()
        elif choice == 'load':
            self.load_game()
        return choice
