"""Fermeture pendant un chargement : le résultat tardif n'est plus appliqué.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_chargement_fermeture.
Le travail d'arrière-plan est simulé par une lecture bloquée sur un threading.Event ;
aucun texte de livre n'est embarqué."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QEvent, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import main
import loading_progress


def fake_module(title='Grimoire de test'):
    return SimpleNamespace(id='test', title=title, engine='sorcier-1982', rules_pages=(3, 14),
                           repair_paragraphs=lambda p: p,
                           catalogue=lambda kind: None)


class BlockedRead:
    """Lecture d'arrière-plan qui attend le feu vert du test avant de rendre son résultat."""

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.started, self.release, self.done = threading.Event(), threading.Event(), threading.Event()

    def __call__(self, *args, **kwargs):
        self.started.set()
        try:
            if not self.release.wait(5):
                raise TimeoutError('le test n’a jamais libéré la lecture')
            if self.error is not None:
                raise self.error
            return self.result
        finally:
            self.done.set()


class ClosingDuringLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        for key in ('APP_DIR', 'SAVES_DIR', 'SETTINGS_DIR', 'BOOKS_DIR'):
            p = patch.object(main, key, self.root if key == 'APP_DIR' else self.root / key)
            p.start()
            self.addCleanup(p.stop)
        main.init_portable_dirs()
        self.pdf = main.BOOKS_DIR / 'livre.pdf'
        self.pdf.write_bytes(b'%PDF-1.4 factice')
        self.qt_messages = []
        previous = qInstallMessageHandler(lambda mode, context, message: self.qt_messages.append(message))
        self.addCleanup(qInstallMessageHandler, previous)
        self.boxes = []
        for name in ('critical', 'warning', 'information', 'question'):
            p = patch.object(QMessageBox, name, side_effect=lambda *a, _n=name, **k: self.boxes.append((_n, a[1:2])))
            p.start()
            self.addCleanup(p.stop)
        self.w = main.MainWindow()
        self.w.show()
        self.app.processEvents()
        self.autosave = main.SAVES_DIR / 'autosave.json'
        self.preferences_before = self.read_preferences()

    def tearDown(self):
        if shiboken6.isValid(self.w):
            self.w.close()
            self.w.deleteLater()
        self.settle()

    # --- outils ---------------------------------------------------------------
    def read_preferences(self):
        path = self.w.preferences_path
        return path.read_bytes() if Path(path).exists() else None

    def settle(self, until=None, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            if until is not None and until():
                return True
            time.sleep(.005)
        return until is None

    def wait_background(self, read):
        """Libérer la lecture puis attendre la fin réelle du thread de chargement."""
        read.release.set()
        self.assertTrue(read.done.wait(5))
        waiter = getattr(loading_progress, 'wait_for_abandoned_workers', None)
        if waiter is not None:
            waiter(3000)
        self.settle(timeout=.2)

    def close_once_started(self, read, *, release_after_ms=30):
        """Fermer la fenêtre dès que la lecture tourne, puis la libérer un peu plus tard."""
        def poll():
            if not read.started.is_set():
                QTimer.singleShot(5, poll)
                return
            self.w.close()
            QTimer.singleShot(release_after_ms, read.release.set)
        QTimer.singleShot(5, poll)

    def book_patches(self, read):
        return (patch('main.extract_paragraphs', side_effect=read),
                patch('main.import_book', return_value=str(self.pdf)),
                patch('main.module_for_pdf', return_value=fake_module()))

    def assert_untouched(self):
        self.assertFalse(self.autosave.exists(), 'aucune autosauvegarde après fermeture')
        self.assertEqual(self.read_preferences(), self.preferences_before, 'préférences inchangées')
        self.assertEqual(self.boxes, [], 'aucun dialogue après fermeture')
        overlay = getattr(self.w, 'loading_overlay', None)
        if overlay is not None and shiboken6.isValid(overlay):
            self.assertFalse(overlay.isVisible())

    # --- grimoire ---------------------------------------------------------------
    def test_late_book_result_after_close_is_ignored(self):
        read = BlockedRead(result={1: 'Une porte.', 2: 'Une salle.'})
        a, b, c = self.book_patches(read)
        with a, b, c, patch.object(main.MainWindow, '_install_opened_book') as install:
            self.close_once_started(read)
            self.w.open_pdf(str(self.pdf))
            self.wait_background(read)
        install.assert_not_called()
        self.assertFalse(self.w.paragraphs)
        self.assertIsNone(self.w.pdf_path)
        self.assert_untouched()

    def test_late_book_result_writes_no_autosave_nor_preferences(self):
        read = BlockedRead(result={1: 'Une porte.', 2: 'Une salle.'})
        a, b, c = self.book_patches(read)
        with a, b as import_book, c:
            self.close_once_started(read)
            self.w.open_pdf(str(self.pdf))
            self.wait_background(read)
        import_book.assert_not_called()  # le travail interrompu ne range plus le livre
        self.assertNotIn('last_book', self.w.preferences)
        self.assert_untouched()

    def test_late_book_error_after_close_shows_no_dialog(self):
        read = BlockedRead(error=ValueError('page illisible'))
        a, b, c = self.book_patches(read)
        with a, b, c:
            self.close_once_started(read)
            self.w.open_pdf(str(self.pdf))
            self.wait_background(read)
        self.assert_untouched()

    def test_normal_book_load_still_installs_and_autosaves(self):
        read = BlockedRead(result={1: 'Une porte.', 2: 'Une salle.'})
        read.release.set()
        a, b, c = self.book_patches(read)
        with a, b, c:
            self.w.open_pdf(str(self.pdf))
        self.assertEqual(self.w.paragraphs, {1: 'Une porte.', 2: 'Une salle.'})
        self.assertEqual(self.w.book_label.text(), 'Grimoire de test')
        self.assertTrue(self.autosave.exists())
        self.assertNotIn('critical', [name for name, _ in self.boxes])

    # --- sauvegarde -------------------------------------------------------------
    def test_late_save_result_after_close_is_ignored(self):
        read = BlockedRead(result=({'fausse': True}, None))
        save = main.SAVES_DIR / 'emplacement-1.json'
        with patch('main.read_save', side_effect=read), \
                patch('main.resolve_book_reference', return_value=None), \
                patch.object(main.MainWindow, '_apply_loaded_save') as apply, \
                patch.object(main.MainWindow, '_play_book_intro') as intro:
            read.result = {'pdf_path': None}
            self.close_once_started(read)
            self.assertFalse(self.w.load_game(save))
            self.wait_background(read)
        apply.assert_not_called()
        intro.assert_not_called()
        self.assert_untouched()

    def test_late_save_error_after_close_shows_no_dialog_nor_new_menu(self):
        read = BlockedRead(error=ValueError('sauvegarde abîmée'))
        save = main.SAVES_DIR / 'emplacement-1.json'
        menus = []

        class FakeSlots:
            def __init__(self, *args, **kwargs):
                menus.append(self)
                self.selected_path, self.new_game_requested = save, False

            def exec(self):
                return QDialog.Accepted

            def deleteLater(self):
                pass

        with patch('main.read_save', side_effect=read), \
                patch('main.SaveSlotsDialog', FakeSlots), \
                patch('main.shiboken6.isValid', side_effect=lambda o: not isinstance(o, FakeSlots)):
            self.close_once_started(read)
            self.w._show_startup_menu()
            self.wait_background(read)
        self.assertEqual(len(menus), 1, 'le menu de démarrage ne se rouvre pas après fermeture')
        self.assert_untouched()

    # --- thread ---------------------------------------------------------------
    def test_close_and_destroy_during_load_does_not_crash_or_warn(self):
        read = BlockedRead(result={1: 'Une porte.'})
        a, b, c = self.book_patches(read)
        with a, b, c:
            def poll():
                if not read.started.is_set():
                    QTimer.singleShot(5, poll)
                    return
                self.w.close()
            QTimer.singleShot(5, poll)
            # Libération tardive : en l'absence de correctif, open_pdf ne rend la main
            # qu'à ce moment-là.
            QTimer.singleShot(400, read.release.set)
            started = time.monotonic()
            self.w.open_pdf(str(self.pdf))
            returned_after = time.monotonic() - started
            self.w.deleteLater()
            self.settle(timeout=.05)
            self.assertLess(returned_after, .3, 'la fermeture rend la main sans attendre la lecture')
            self.wait_background(read)
        self.assertFalse([m for m in self.qt_messages if 'QThread' in m], self.qt_messages)

    def test_reopened_window_loads_normally_after_cancelled_load(self):
        read = BlockedRead(result={1: 'Une porte.'})
        a, b, c = self.book_patches(read)
        with a, b, c:
            self.close_once_started(read)
            self.w.open_pdf(str(self.pdf))
            self.wait_background(read)
        self.w.show()
        self.app.processEvents()
        second = BlockedRead(result={1: 'Une porte.', 2: 'Une salle.'})
        second.release.set()
        a, b, c = self.book_patches(second)
        with a, b, c:
            self.w.open_pdf(str(self.pdf))
        self.assertEqual(self.w.paragraphs, {1: 'Une porte.', 2: 'Une salle.'})
        self.assertTrue(self.autosave.exists())


if __name__ == '__main__':
    unittest.main()
