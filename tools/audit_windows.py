"""Lance le vrai point d'entrée et capture les dialogues Qt sous Windows.

Sorties privées ignorées par Git (peuvent montrer le livre). Aucun PDF copié.
"""
import hashlib
import json
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as b
from PySide6.QtCore import QTimer, QLibraryInfo
from PySide6.QtWidgets import QApplication, QDialog, QWidget, QMessageBox, QToolTip
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest

OUT = ROOT / 'audit-output'
OUT.mkdir(exist_ok=True)
results = {'platform': sys.platform, 'python': sys.version, 'captures': [], 'dialogs': {}, 'errors': []}
original_exec = QApplication.exec


def digest_files():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / 'donnees').rglob('*') if p.is_file()}


def capture(widget, name):
    QTest.qWait(200)
    path = OUT / (name + '.png')
    if not widget.grab().save(str(path)):
        raise RuntimeError('Capture impossible : ' + name)
    results['captures'].append(name)


def modal(action, name):
    errors = []
    def finish():
        dialog = QApplication.activeModalWidget()
        try:
            if not isinstance(dialog, QDialog):
                raise RuntimeError('Dialogue absent : ' + name)
            capture(dialog, name)
            results['dialogs'][name] = [
                {'class': type(w).__name__, 'name': w.objectName(),
                 'text': w.text() if hasattr(w, 'text') and callable(w.text) else '',
                 'tooltip': w.toolTip(), 'accessible': w.accessibleName()}
                for w in dialog.findChildren(QWidget)
                if w.isVisible() and (w.toolTip() or hasattr(w, 'text'))]
        except Exception:
            errors.append(traceback.format_exc())
        finally:
            if isinstance(dialog, QDialog):
                dialog.reject()
    QTimer.singleShot(650, finish)
    action()
    if errors:
        raise RuntimeError('\n'.join(errors))


def scenario():
    app = QApplication.instance()
    before = digest_files()
    try:
        w = next(x for x in app.topLevelWidgets() if isinstance(x, b.MainWindow))
        results['qt_platform'] = app.platformName()
        results['translators_loaded'] = len(app._bifurk_translators)
        results['translation_path'] = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
        capture(w, '01-accueil')
        modal(lambda: w._themed_file_dialog('pdf'), '02-ouvrir')
        modal(lambda: w._themed_save_dialog(True), '03-sauvegarder')
        modal(lambda: w._themed_save_dialog(False), '04-charger')
        modal(lambda: QMessageBox.question(w, 'Confirmation', 'Confirmer cette action ?', QMessageBox.Yes | QMessageBox.No), '05-confirmation')
        modal(w.show_map, '06-carte-vide')
        pdf = next(ROOT.glob('*.pdf'))
        w.pdf_path = str(pdf)
        w.paragraphs = b.extract_paragraphs(pdf)
        w.illustration_catalogue = b.catalogue_for_pdf(pdf)
        w.goto_spin.setMaximum(max(w.paragraphs))
        # Empêcher uniquement l'autosave de test d'écraser la partie du joueur.
        with patch.object(w, '_autosave'):
            modal(w.show_cover, '07-couverture-privee')
            modal(lambda: w.go_to(1), '08-illustration-privee')
            capture(w, '09-lecture-privee')
            modal(w.show_map, '10-carte')
            modal(lambda: w.prepare_encounter({'name': 'Adversaire de test', 'skill': 7, 'stamina': 6}), '11-rencontre')
            modal(lambda: w.apply_detected_event({'key': 'endurance', 'amount': -2, 'label': 'Perte d’Endurance'}), '12-evenement')
            modal(lambda: w.confirm_item('Objet de test'), '13-inventaire')
            with patch.object(w, '_roll', side_effect=[([1, 1], 2), ([6, 6], 12)]):
                modal(w.combat_round, '14-combat')
            w.toggle_fullscreen()
            app.processEvents()
            capture(w, '15-plein-ecran-prive')
            w.toggle_fullscreen()
            w.resize(930, 650)
            app.processEvents()
            capture(w, '16-petite-fenetre-privee')
        results['data_unchanged'] = before == digest_files()
    except Exception:
        results['errors'].append(traceback.format_exc())
    finally:
        (OUT / 'windows.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        app.exit(1 if results['errors'] else 0)


def run_loop(self):
    QTimer.singleShot(900, scenario)
    return original_exec()


if __name__ == '__main__':
    with patch.object(QApplication, 'exec', run_loop):
        b.main()
