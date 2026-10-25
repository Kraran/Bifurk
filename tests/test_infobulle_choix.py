"""Infobulles des cartes de choix : la raison d'un choix grisé n'est jamais écrasée.

La numérotation des touches 1–9 s'ajoute à l'infobulle posée par le module
(« Indisponible : … · touche N », comme dans le Sorcier depuis #104). Les raisons
de la Forêt nomment l'étape à franchir, jamais l'issue d'un jet ou d'un combat.
Aucun texte du PDF n'est embarqué : les PDF et paragraphes sont factices."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

import main
from book_events import DATA_PATH
from grimoire_ui import ChoiceCard
from grimoire_modules.registry import available_modules
from grimoire_modules.foret import rules
from grimoire_modules.foret.encounters import COMBATS

KEY_SUFFIX = re.compile(r' · touche [1-9]$')


def choice_cards(window):
    return [w for w in window._visible_choice_cards() if w.objectName() == 'choiceCard']


class ChoiceCardTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_key_hint_is_added_to_the_module_tooltip(self):
        card = ChoiceCard('Explorer  →  §12')
        card.setToolTip('Condition du livre : Anneau de Lumière')
        card.set_shortcut_number(2)
        self.assertEqual(card.toolTip(), 'Condition du livre : Anneau de Lumière · touche 2')

    def test_renumbering_replaces_only_the_key_hint(self):
        card = ChoiceCard('Payer  →  §5')
        card.setToolTip('Indisponible : Il vous faut 3 pièces d’or (vous en avez 2).')
        card.set_shortcut_number(1)
        card.set_shortcut_number(4)
        self.assertEqual(card.toolTip(),
                         'Indisponible : Il vous faut 3 pièces d’or (vous en avez 2). · touche 4')
        bare = ChoiceCard('Continuer  →  §6')
        bare.set_shortcut_number(3)
        bare.set_shortcut_number(5)
        self.assertEqual(bare.toolTip(), 'Touche 5')


class ForetTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.module = next(m for m in available_modules() if m.engine == 'foret-1983')

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for key, path in {'APP_DIR': root, 'BOOKS_DIR': root / 'donnees/grimoires',
                          'SAVES_DIR': root / 'donnees/sauvegardes',
                          'SETTINGS_DIR': root / 'donnees/parametres'}.items():
            mock = patch.object(main, key, path)
            mock.start()
            self.addCleanup(mock.stop)
        main.init_portable_dirs()
        pdf = root / 'foret.pdf'
        with pymupdf.open() as document:
            for index in range(170):
                page = document.new_page(width=504.6, height=842)
                if index == 18:
                    page.insert_text((30, 40), '1\nUne foret. Rendez-vous au 2.\n2\nUne clairiere.')
            document.save(pdf)
        for target in ('main.module_for_pdf', 'grimoire_library.module_for_pdf'):
            mock = patch(target, return_value=self.module)
            mock.start()
            self.addCleanup(mock.stop)
        for kind in ('information', 'warning', 'critical'):
            mock = patch.object(QMessageBox, kind)
            mock.start()
            self.addCleanup(mock.stop)
        self.w = main.MainWindow()
        self.addCleanup(self.w.sounds._close_log)
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        mock = patch.object(self.w, '_roll', side_effect=lambda count, *a, **k: ([3] * count, 3 * count))
        mock.start()
        self.addCleanup(mock.stop)
        self.w.open_pdf(pdf, startup=True)
        self.w._begin_adventure('Eldan')
        entries = self.w.book_event_catalogue['paragraphs']
        self.w.paragraphs.update({int(n): f'Passage factice {n}.' for n in entries})
        self.titles = {int(n): e.get('title', '') for n, e in entries.items()}

    def card_to(self, target):
        return next(c for c in choice_cards(self.w) if c.text().endswith(f'§{target}'))

    def test_missing_ring_keeps_its_reason_with_the_key(self):
        self.w.go_to(3)
        ring = self.card_to(322)
        self.assertFalse(ring.isEnabled())
        self.assertEqual(ring.toolTip(), 'Indisponible : condition du livre non remplie '
                                         '(Anneau de Lumière). · touche 1')
        other = self.card_to(120)
        self.assertTrue(other.isEnabled())
        self.assertEqual(other.toolTip(), 'Condition du livre : Pas d\'Anneau de Lumière · touche 2')

    def test_cards_are_numbered_when_the_window_is_shown(self):
        """Fenêtre affichée : les cartes neuves, montrées au tour Qt suivant, sont numérotées."""
        self.w.show()
        self.addCleanup(self.w.hide)
        QApplication.processEvents()
        self.w.go_to(3)
        self.assertEqual([c.toolTip().rsplit(' · ', 1)[-1] for c in choice_cards(self.w)],
                         ['touche 1', 'touche 2'])
        self.assertTrue(self.card_to(322).toolTip().startswith('Indisponible : condition du livre'))

    def test_pending_combat_names_the_step_not_the_outcome(self):
        self.w.go_to(15)
        self.assertTrue(self.w.combat_available())
        card = self.card_to(COMBATS[15]['victory_target'])
        self.assertFalse(card.isEnabled())
        self.assertEqual(card.toolTip(),
                         'Indisponible : terminez d’abord le combat de ce passage. · touche 1')
        self.assertNotIn('vaincu', card.toolTip())

    def test_pending_luck_test_does_not_reveal_which_branch_wins(self):
        self.w.go_to(57)
        for card in choice_cards(self.w):
            with self.subTest(card=card.text()):
                self.assertFalse(card.isEnabled())
                self.assertRegex(card.toolTip(),
                                 r'^Indisponible : résolvez d’abord l’événement de ce passage\. · touche \d$')

    def test_every_greyed_card_explains_itself_without_spoiler(self):
        """Parcours des 400 passages : raison au format du Sorcier, touche conservée."""
        base = self.w._snapshot()
        checked = 0
        for number in sorted(self.titles):
            self.w._restore(base)
            self.w.go_to(number)
            if self.w.current_paragraph != number or self.w.character['endurance'] <= 0:
                continue
            for index, card in enumerate(choice_cards(self.w)[:9], 1):
                with self.subTest(paragraph=number, card=card.text()):
                    tip = card.toolTip()
                    self.assertTrue(tip.endswith(f'ouche {index}'), tip)
                    reason = KEY_SUFFIX.sub('', tip)
                    if not card.isEnabled():
                        checked += 1
                        self.assertTrue(reason.startswith('Indisponible : '), tip)
                    # Ni numéro ni titre d'un autre passage dans la raison.
                    self.assertNotRegex(reason, r'§\s*\d')
                    for target, title in self.titles.items():
                        if target != number and len(title) > 12:
                            self.assertNotIn(title, reason)
        self.assertGreater(checked, 50)

    def test_combat_window_keeps_the_action_tooltip(self):
        from combat_dialog import CombatDialog
        self.w.go_to(29)
        self.assertTrue(self.w.combat_available())
        source = QPushButton('Cibler le second adversaire')
        source.setProperty('combatAction', True)
        source.setToolTip('Indisponible : un seul adversaire debout.')
        source.setEnabled(False)
        self.w.event_layout.addWidget(source)
        dialog = CombatDialog(self.w)
        self.addCleanup(dialog.deleteLater)
        dialog._refresh_actions()
        copies = [c for c in dialog.findChildren(ChoiceCard) if c.text() == source.text()]
        self.assertTrue(copies)
        self.assertEqual(copies[0].toolTip(), source.toolTip())


class SorcierTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalogue = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.w.book_event_catalogue = copy.deepcopy(self.catalogue)
        self.w.paragraphs = {n: f'Passage de test {n}.' for n in range(1, 401)}
        for name, value in [('information', QMessageBox.Ok), ('warning', QMessageBox.Ok),
                            ('question', QMessageBox.No)]:
            mock = patch.object(QMessageBox, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_greyed_and_open_choices_keep_their_text(self):
        self.w.character['gold'] = 2
        self.w.go_to(3)
        cards = choice_cards(self.w)
        pay = next(c for c in cards if 'Payer' in c.text())
        self.assertFalse(pay.isEnabled())
        self.assertRegex(pay.toolTip(), r'^Indisponible : .*3 pièces d’or \(vous en avez 2\)\. · touche \d$')
        for card in cards:
            if card.isEnabled():
                self.assertRegex(card.toolTip(), r'^Ouvrir le paragraphe \d+ · touche \d$')


if __name__ == '__main__':
    unittest.main()
