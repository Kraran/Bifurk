"""Renvois §N du carnet : mis en forme pendant la frappe, cible toujours lue dans le texte."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QTextEdit

import main
from carnet import LinedNotes
from grimoire_chrome import RUBRIC
from save_slots import read_save


def type_text(widget, text):
    """Frappe réelle, caractère par caractère (« § » compris), comme au clavier."""
    for ch in text:
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.sendEvent(widget, QKeyEvent(kind, 0, Qt.NoModifier, ch))


def press(widget, key, modifiers=Qt.NoModifier):
    QTest.keyClick(widget, key, modifiers)


class EditorCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ed = LinedNotes()
        self.ed.resize(600, 400)
        self.addCleanup(self.ed.deleteLater)

    def load(self, text):
        self.ed.set_notes(text)
        self.ed.moveCursor(QTextCursor.End)

    def target(self, needle, nth=0):
        """Cible de chaque caractère de la n-ième occurrence ; un seul numéro attendu."""
        start = -1
        for _ in range(nth + 1):
            start = self.ed.toPlainText().index(needle, start + 1)
        targets = {self.ed.link_target(start + i) for i in range(len(needle))}
        self.assertEqual(len(targets), 1, f'{needle!r} à cibles mélangées : {targets}')
        return targets.pop()

    def glyph_point(self, needle):
        start = self.ed.toPlainText().index(needle)
        cursor = QTextCursor(self.ed.document())
        cursor.setPosition(start)
        left = self.ed.cursorRect(cursor)
        cursor.setPosition(start + len(needle))
        right = self.ed.cursorRect(cursor)
        return QPoint((left.left() + right.left()) // 2, left.center().y())


class TypingTests(EditorCase):
    def test_freely_typed_reference_is_immediately_a_link_to_its_number(self):
        self.load('Voir ')
        type_text(self.ed, '§3')
        self.assertEqual(self.target('§3'), 3)
        layout = self.ed.document().findBlock(5).layout()
        styled = [r for r in layout.formats() if r.start <= 5 < r.start + r.length]
        self.assertTrue(styled and styled[-1].format.foreground().color() == RUBRIC)

    def test_text_typed_after_an_existing_link_inherits_nothing(self):
        self.load('Voir §12')
        type_text(self.ed, ' puis §3')
        self.assertEqual(self.ed.toPlainText(), 'Voir §12 puis §3')
        self.assertEqual(self.target('§12'), 12)
        self.assertEqual(self.target('§3'), 3)
        self.assertIsNone(self.target(' puis '))
        # Collé au lien, sans espace : le chiffre prolonge le numéro, la lettre reste du texte.
        self.load('§12')
        type_text(self.ed, 'x')
        self.assertIsNone(self.target('x'))
        self.assertEqual(self.target('§12'), 12)
        # Le document ne stocke plus aucune ancre qui pourrait se propager.
        block = self.ed.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                self.assertFalse(it.fragment().charFormat().isAnchor())
                it += 1
            block = block.next()

    def test_editing_the_number_retargets_the_link(self):
        self.load('Aller au §12 vite')
        cursor = self.ed.textCursor()
        cursor.setPosition(self.ed.toPlainText().index('12') + 2)
        self.ed.setTextCursor(cursor)
        type_text(self.ed, '3')
        self.assertEqual(self.target('§123'), 123)
        press(self.ed, Qt.Key_Backspace)
        press(self.ed, Qt.Key_Backspace)
        self.assertEqual(self.target('§1'), 1)

    def test_deleting_the_section_sign_removes_the_link(self):
        self.load('Voir §12.')
        cursor = self.ed.textCursor()
        cursor.setPosition(self.ed.toPlainText().index('§') + 1)
        self.ed.setTextCursor(cursor)
        press(self.ed, Qt.Key_Backspace)
        self.assertEqual(self.ed.toPlainText(), 'Voir 12.')
        self.assertIsNone(self.target('12'))
        self.assertIsNone(self.ed.reference_at(self.glyph_point('12')))

    def test_cursor_and_selection_are_untouched_by_reformatting(self):
        self.load('Ligne une §4\nLigne deux')
        cursor = self.ed.textCursor()
        cursor.setPosition(3)
        self.ed.setTextCursor(cursor)
        type_text(self.ed, ' §7 ')
        self.assertEqual(self.ed.textCursor().position(), 7)
        self.assertFalse(self.ed.textCursor().hasSelection())
        self.assertEqual(self.target('§7'), 7)
        cursor = self.ed.textCursor()
        cursor.setPosition(2)
        cursor.setPosition(9, QTextCursor.KeepAnchor)
        self.ed.setTextCursor(cursor)
        other = QTextCursor(self.ed.document())
        other.movePosition(QTextCursor.End)
        other.insertText(' §8')
        kept = self.ed.textCursor()
        self.assertEqual((kept.anchor(), kept.position()), (2, 9))
        self.assertEqual(self.target('§8'), 8)

    def test_undo_restores_each_typing_action_in_one_step_and_redo_works(self):
        self.load('Voir §12')
        self.assertFalse(self.ed.document().isUndoAvailable())
        type_text(self.ed, ' puis §3')
        # Même nombre de pas qu'un QTextEdit nu : la mise en forme n'ajoute aucun pas.
        bare = QTextEdit()
        self.addCleanup(bare.deleteLater)
        bare.setPlainText('Voir §12')
        bare.document().clearUndoRedoStacks()
        bare.moveCursor(QTextCursor.End)
        type_text(bare, ' puis §3')
        self.assertEqual(self.ed.document().availableUndoSteps(),
                         bare.document().availableUndoSteps())
        press(self.ed, Qt.Key_Z, Qt.ControlModifier)
        self.assertEqual(self.ed.toPlainText(), 'Voir §12')
        self.assertFalse(self.ed.document().isUndoAvailable())
        self.assertEqual(self.target('§12'), 12)
        press(self.ed, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
        self.assertEqual(self.ed.toPlainText(), 'Voir §12 puis §3')
        self.assertEqual(self.target('§3'), 3)
        # Le bouton « insérer le renvoi » est lui aussi une seule action annulable.
        self.ed.insert_reference(5)
        self.assertEqual(self.ed.toPlainText(), 'Voir §12 puis §3 §5 ')
        self.ed.undo()
        self.assertEqual(self.ed.toPlainText(), 'Voir §12 puis §3')

    def test_click_on_a_typed_reference_emits_its_number_only_on_the_glyphs(self):
        self.ed.show()
        self.load('Voir §12 puis §3')
        type_text(self.ed, ' et rien')
        hits = []
        self.ed.referenceActivated.connect(hits.append)
        QTest.mouseClick(self.ed.viewport(), Qt.LeftButton, Qt.NoModifier, self.glyph_point('§3'))
        QTest.mouseClick(self.ed.viewport(), Qt.LeftButton, Qt.NoModifier, self.glyph_point('§12'))
        QTest.mouseClick(self.ed.viewport(), Qt.LeftButton, Qt.NoModifier, self.glyph_point('rien'))
        far = self.glyph_point('rien') + QPoint(300, 0)
        QTest.mouseClick(self.ed.viewport(), Qt.LeftButton, Qt.NoModifier, far)
        self.assertEqual(hits, [3, 12])

    def test_old_notes_load_verbatim_and_render_their_links(self):
        legacy = '✦ §1 — 24 octobre 2026, 20:05\nClé sous la statue (§ 3), puis §12.\n'
        self.ed.set_notes(legacy)
        self.assertEqual(self.ed.plain(), legacy)  # « § 3 » n'est plus réécrit en « §3 »
        self.assertEqual(self.target('§1'), 1)
        self.assertEqual(self.target('§ 3'), 3)
        self.assertEqual(self.target('§12'), 12)
        self.assertFalse(self.ed.document().isUndoAvailable())


class RoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for key in ('SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            replacement = patch.object(main, key, self.root/key)
            replacement.start()
            self.addCleanup(replacement.stop)
        main.init_portable_dirs()
        self.w = main.MainWindow()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)
        pdf = self.root/'livre.pdf'
        pdf.write_bytes(b'PDF prive de test')
        self.w.pdf_path = str(pdf)
        self.w.paragraphs = {n: f'Paragraphe {n}.' for n in (1, 3, 12)}
        self.w.character['name'] = 'Eldan'
        self.w.go_to(1)
        self.w.show()
        self.app.processEvents()

    def test_typed_links_survive_save_and_load_and_still_navigate(self):
        self.w.open_carnet()
        editor = self.w.carnet_overlay.book.editor
        editor.set_notes('Voir §12')
        editor.moveCursor(QTextCursor.End)
        type_text(editor, ' puis §3')
        self.assertEqual(self.w.notes, 'Voir §12 puis §3')
        path = main.SAVES_DIR/'emplacement-1.json'
        self.w._write_atomic(path, self.w._save_data())
        self.assertEqual(read_save(path)['notes'], 'Voir §12 puis §3')
        self.w.close_carnet()
        self.w._reset_carnet()
        self.assertTrue(self.w.load_game(path, announce=False))
        self.w.open_carnet()
        editor = self.w.carnet_overlay.book.editor
        self.app.processEvents()
        self.assertEqual(editor.plain(), 'Voir §12 puis §3')
        text = editor.toPlainText()
        self.assertEqual(editor.link_target(text.index('§3')), 3)
        self.assertEqual(editor.link_target(text.index('§12')), 12)
        cursor = QTextCursor(editor.document())
        cursor.setPosition(text.index('§3'))
        left = editor.cursorRect(cursor)
        cursor.setPosition(text.index('§3') + 2)
        point = QPoint((left.left() + editor.cursorRect(cursor).left()) // 2, left.center().y())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            QTest.mouseClick(editor.viewport(), Qt.LeftButton, Qt.NoModifier, point)
        self.assertEqual(self.w.current_paragraph, 3)
        self.assertFalse(self.w.carnet_is_open())


if __name__ == '__main__':
    unittest.main()
