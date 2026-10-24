"""Barre de chargement : étapes annoncées, travail hors interface, fermeture sûre.

Exécution : QT_QPA_PLATFORM=offscreen python -m unittest tests.test_barre_chargement.
Les PDF sont générés à la volée ; aucun texte de livre privé n'est embarqué."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

import main
import loading_progress
from loading_progress import LoadingOverlay, LoadingSession


def fake_module(title='Grimoire de test'):
    return SimpleNamespace(id='test', title=title, engine='sorcier-1982', rules_pages=(3, 14),
                           repair_paragraphs=lambda p: p,
                           catalogue=lambda kind: {'title': title, 'illustrations': []}
                           if kind == 'illustrations' else None)


class LoadingBarTests(unittest.TestCase):
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
        with pymupdf.open() as document:
            for number in range(1, 4):
                document.new_page().insert_text((72, 72), f'{number}\nUne salle numéro {number}.')
            document.save(self.pdf)
        self.w = main.MainWindow()
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def overlay_visible(self):
        overlay = getattr(self.w, 'loading_overlay', None)
        return overlay is not None and overlay.isVisible()

    # --- ouverture d'un grimoire --------------------------------------------
    def test_opening_announces_steps_in_order_and_skips_bar_when_fast(self):
        paragraphs = {1: 'Une porte.', 2: 'Une salle.'}
        with patch('main.extract_paragraphs', return_value=paragraphs), \
                patch('main.import_book', return_value=str(self.pdf)), \
                patch('main.module_for_pdf', return_value=fake_module()):
            self.w.open_pdf(str(self.pdf))
        session = self.w.last_loading
        self.assertEqual(session.title, 'Ouverture du grimoire…')
        self.assertEqual(session.step_names(), [
            'Lecture du livre', 'Extraction des paragraphes', 'Préparation des catalogues',
            'Rangement dans la bibliothèque', 'Préparation de l’aventure'])
        fractions = [f for f, _ in session.steps]
        self.assertEqual(fractions, sorted(fractions))
        self.assertFalse(session.was_shown, 'un chargement rapide ne doit pas faire clignoter la barre')
        self.assertFalse(self.overlay_visible())
        self.assertEqual(self.w.paragraphs, paragraphs)
        self.assertEqual(self.w.book_label.text(), 'Grimoire de test')

    def test_real_pdf_is_read_in_a_worker_thread_with_page_progress(self):
        threads = []
        real_extract = main.extract_paragraphs

        def spy(path, **kwargs):
            threads.append(threading.current_thread())
            return real_extract(path, **kwargs)

        with patch('main.extract_paragraphs', side_effect=spy), \
                patch('main.import_book', side_effect=lambda path: path), \
                patch.object(QMessageBox, 'information'):
            self.w.open_pdf(str(self.pdf))
        self.assertEqual(len(threads), 1)
        self.assertIsNot(threads[0], threading.main_thread())
        self.assertEqual(sorted(self.w.paragraphs), [1, 2, 3])
        self.assertEqual(self.w.last_loading.last_detail, 'page 3 / 3')

    def test_slow_opening_shows_bar_then_closes_it(self):
        seen = []

        def slow_extract(path, *, module=None, progress=None):
            for page in range(1, 6):
                time.sleep(.06)
                progress(page, 5)
            seen.append(self.overlay_visible())
            return {1: 'Une porte.'}

        with patch.object(loading_progress, 'SHOW_DELAY_MS', 40), \
                patch('main.extract_paragraphs', side_effect=slow_extract), \
                patch('main.import_book', return_value=str(self.pdf)), \
                patch('main.module_for_pdf', return_value=fake_module()):
            self.w.open_pdf(str(self.pdf))
        session = self.w.last_loading
        self.assertTrue(session.was_shown)
        self.assertEqual(seen, [True])
        self.assertEqual(session.last_detail, 'page 5 / 5')
        self.assertFalse(self.overlay_visible())
        self.assertEqual(self.w.paragraphs, {1: 'Une porte.'})

    def test_unreadable_pdf_closes_bar_before_message(self):
        broken = self.root / 'abime.pdf'
        broken.write_bytes(b'ceci n est pas un pdf')
        visible_during_message = []
        before = dict(self.w.paragraphs)
        with patch.object(loading_progress, 'SHOW_DELAY_MS', 0), \
                patch.object(QMessageBox, 'critical',
                             side_effect=lambda *a: visible_during_message.append(self.overlay_visible())) as critical:
            self.w.open_pdf(str(broken))
        critical.assert_called_once()
        self.assertEqual(critical.call_args.args[1], 'Import impossible')
        self.assertEqual(visible_during_message, [False])
        self.assertEqual(self.w.paragraphs, before)
        self.assertNotEqual(self.w.pdf_path, str(broken))

    # --- sauvegardes ---------------------------------------------------------
    def saved_game(self):
        self.w.paragraphs = {1: 'Une porte.', 2: 'Une salle.'}
        self.w.pdf_path = str(self.pdf)
        self.w._show_book_title()
        self.w.creation_name_field.setText('Éléanor')
        self.w.creation_start_button.click()
        path = main.SAVES_DIR / 'emplacement-1.json'
        path.parent.mkdir(exist_ok=True)
        self.w._write_atomic(path, self.w._save_data())
        return path

    def test_loading_save_announces_steps_and_restores(self):
        path = self.saved_game()
        self.w.character['name'] = 'Autre'
        self.assertTrue(self.w.load_game(path, announce=False))
        session = self.w.last_loading
        self.assertEqual(session.title, 'Chargement de la sauvegarde…')
        self.assertEqual(session.step_names(), [
            'Lecture de la sauvegarde', 'Vérification du grimoire', 'Extraction des paragraphes',
            'Préparation des catalogues', 'Restauration de l’aventure'])
        self.assertEqual(self.w.character['name'], 'Éléanor')
        self.assertFalse(session.was_shown)
        self.assertFalse(self.overlay_visible())

    def test_corrupt_save_closes_bar_and_shows_clear_message(self):
        path = self.saved_game()
        path.write_text('{abîmée', encoding='utf-8')
        before = self.w._snapshot()
        visible_during_message = []
        with patch.object(loading_progress, 'SHOW_DELAY_MS', 0), \
                patch.object(QMessageBox, 'critical',
                             side_effect=lambda *a: visible_during_message.append(self.overlay_visible())) as critical:
            self.assertFalse(self.w.load_game(path))
        self.assertEqual(critical.call_args.args[1], 'Chargement impossible')
        self.assertEqual(visible_during_message, [False])
        self.assertEqual(self.w._snapshot(), before)
        self.assertEqual(self.w.last_loading.step_names(), ['Lecture de la sauvegarde'])

    def test_changed_pdf_stops_before_extraction(self):
        path = self.saved_game()
        data = json.loads(path.read_text(encoding='utf-8'))
        data['pdf_sha256'] = '0' * 64
        path.write_text(json.dumps(data), encoding='utf-8')
        with patch('main.extract_paragraphs') as extract:
            self.assertFalse(self.w.load_game(path, announce=False))
        extract.assert_not_called()
        self.assertFalse(self.overlay_visible())

    # --- session et carte ----------------------------------------------------
    def test_session_reports_worker_error_and_hides_shown_overlay(self):
        def failing(report):
            report(.3, 'Lecture du livre')
            time.sleep(.12)
            raise ValueError('page illisible')

        with self.assertRaises(ValueError):
            with LoadingSession(self.w, 'Ouverture du grimoire…', delay_ms=10) as session:
                session.run(failing)
        self.assertTrue(session.was_shown)
        self.assertFalse(self.overlay_visible())
        self.assertEqual(session.step_names(), ['Lecture du livre'])

    def test_interface_keeps_painting_during_work(self):
        ticks = []
        with LoadingSession(self.w, 'Ouverture du grimoire…', delay_ms=0) as session:
            self.w.loading_overlay._timer.timeout.connect(lambda: ticks.append(1))
            session.run(lambda report: time.sleep(.25))
        self.assertGreater(len(ticks), 2, "l'animation doit tourner pendant le travail")

    def test_small_window_uses_compact_card_inside_window(self):
        # La fenêtre principale impose sa taille minimale : un hôte nu simule l'écran réduit.
        host = QWidget()
        self.addCleanup(host.deleteLater)
        host.resize(640, 480)
        host.show()
        overlay = LoadingOverlay(host)
        overlay.set_title('Chargement de la sauvegarde…')
        overlay.set_progress(.4, 'Extraction des paragraphes', 'page 68 / 170')
        overlay.present()
        self.app.processEvents()
        card = overlay.card_rect()
        self.assertTrue(overlay.compact())
        self.assertEqual(overlay.geometry(), host.rect())
        self.assertTrue(overlay.rect().contains(card.toRect()))
        self.assertEqual(overlay.percent(), 40)
        overlay.dismiss()
        self.assertFalse(overlay.isVisible())


if __name__ == '__main__':
    unittest.main()
