"""Captures privées du lecteur Qt avec le PDF exact, sans utiliser les données du joueur.

Les fenêtres utilisent le moteur natif mais ne sont pas affichées sur le bureau.
Ce contrôle de rendu et de parcours déterministe ne simule pas les entrées de la souris.
"""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprints(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def run(pdf, output, platform):
    os.environ['QT_QPA_PLATFORM'] = platform
    from PySide6.QtCore import (QEvent, QObject, Qt, QLocale, QTimer, QTranslator,
                               QLibraryInfo, qInstallMessageHandler)
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QScrollArea
    from PySide6.QtTest import QTest
    import main
    from grimoire_modules.foret import rules
    from grimoire_modules.registry import module_for_pdf

    module = module_for_pdf(pdf)
    if module is None or module.engine != 'foret-1983':
        raise ValueError('Le PDF exact de la Forêt de 1983 est requis.')
    output.mkdir(parents=True, exist_ok=True)
    before = fingerprints(ROOT / 'donnees')
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    messages = []
    previous_handler = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    app = QApplication.instance() or QApplication([])
    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    translators = []
    for catalogue in ('qtbase_fr', 'qt_fr'):
        translator = QTranslator(app)
        for folder in (ROOT/'translations', Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))):
            if translator.load(catalogue, str(folder)):
                app.installTranslator(translator)
                translators.append(translator)
                break

    class HiddenWindows(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Polish and hasattr(obj, 'isWindow') and obj.isWindow():
                obj.setAttribute(Qt.WA_DontShowOnScreen, True)
            return False

    hidden = HiddenWindows()
    app.installEventFilter(hidden)
    result = {'platform': app.platformName(), 'captures': [], 'quests': [], 'errors': []}
    try:
        with tempfile.TemporaryDirectory(prefix='session-', dir=output) as temporary, ExitStack() as stack:
            root = Path(temporary)
            for key, path in {'APP_DIR': root, 'BOOKS_DIR': root/'livres',
                              'SAVES_DIR': root/'sauvegardes', 'SETTINGS_DIR': root/'parametres'}.items():
                stack.enter_context(patch.object(main, key, path))
            main.init_portable_dirs()
            (main.SETTINGS_DIR/'preferences.json').write_text(json.dumps({
                'sound_enabled': False, 'ambient_enabled': False, 'music_enabled': False}), encoding='utf-8')
            window = main.MainWindow()
            app.setStyleSheet(window.styleSheet())
            theme_filter = main.DialogThemeFilter(app)
            app.installEventFilter(theme_filter)
            try:
                def shot(widget, name):
                    app.processEvents()
                    QTest.qWait(120)
                    if not widget.grab().save(str(output/(name+'.png'))):
                        raise RuntimeError('Capture impossible : '+name)
                    result['captures'].append(name)

                def modal(action, name):
                    errors = []
                    def capture():
                        dialog = app.activeModalWidget()
                        try:
                            if not isinstance(dialog, QDialog):
                                raise RuntimeError('Dialogue absent : '+name)
                            shot(dialog, name)
                        except Exception as error:
                            errors.append(str(error))
                        finally:
                            if isinstance(dialog, QDialog):
                                dialog.reject()
                    timer = QTimer()
                    timer.setSingleShot(True)
                    timer.timeout.connect(capture)
                    timer.start(300)
                    action()
                    still_pending = timer.isActive()
                    timer.stop()
                    if errors or still_pending:
                        raise RuntimeError(str(errors) if errors else 'Action non modale : '+name)

                # Les erreurs inattendues ne doivent pas ouvrir un dialogue bloquant.
                def fail(*args, **kwargs):
                    raise RuntimeError(str(args[1:]))
                for name in ('critical', 'warning'):
                    stack.enter_context(patch.object(QMessageBox, name, side_effect=fail))
                stack.enter_context(patch.object(window, '_roll', side_effect=lambda count, **kw: ([3]*count,3*count)))
                window.open_pdf(pdf, startup=True)
                window.show()
                window.resize(1280,800)
                shot(window,'01-couverture')
                window._adventurer_draft = {'habilete':12,'endurance':24,'chance':12}
                window._begin_adventure('Eldan')
                base = deepcopy(window._snapshot())
                shot(window,'02-depart')
                window.show_prologue()
                window.prologue_dialog.pages.setCurrentIndex(3)
                shot(window.prologue_dialog,'03-carte')
                window.prologue_dialog.close()
                window.go_to(91)
                shot(window,'04-oeil-ambre')
                modal(window._enlarge_scene_art,'05-oeil-agrandi')
                window._restore(base)
                window.go_to(261)
                window.perform_foret_action('buy',('Bandeau de Concentration',1))
                window.go_to(158)
                for width,height in ((1280,800),(930,650),(1600,900)):
                    window.resize(width,height)
                    shot(window,f'06-bandeau-{width}')
                    side = window.findChild(QScrollArea,'sideScroll')
                    if side.horizontalScrollBar().maximum():
                        raise AssertionError('Panneau d’aventurier débordant à '+str(width))
                    if width == 930:
                        for area in window.findChildren(QScrollArea):
                            if area.widget() and area.widget().isAncestorOf(window.event_group):
                                area.ensureWidgetVisible(window.event_group)
                        shot(window,'07-bandeau-actions-930')
                window.resize(1280,800)
                window.perform_foret_action('branch_test')
                assert window.current_paragraph == 47
                shot(window,'08-bandeau-reussi')
                window._restore(base)
                window.go_to(242)
                shot(window,'09-lingot')
                modal(lambda: window.perform_foret_action('gold_ingot'),'10-choix-objet')
                window.go_to(152)
                shot(window,'11-couronne-avant')
                window.perform_foret_action('entry')
                shot(window,'12-couronne-apres')
                window._restore(base)
                window.character.update(gold=0,provisions=0,inventory=[],equipped_weapon=None)
                window._refresh_character()
                window.go_to(14)
                shot(window,'13-secours-fosse')
                window.perform_foret_action('emergency_exit')
                assert window.current_paragraph == 255
                shot(window,'14-secours-suite')
                window._restore(base)
                for number in (293,215,201,389):
                    if number == 293: window.go_to(number)
                    else: window.follow_foret_route(number)
                window.perform_foret_action('entry')
                assert window._reading_link_targets() == {88}
                shot(window,'15-coffre-tonneau')

                # Deux parcours du catalogue avec le texte et les images du PDF réel.
                prefix = [261,177,160,8,392,157,337,230,137,55,168,117,232,358,40,
                          274,109,124,180,361,86,208,99,209,28,52,78,349,291,145,
                          285,388,316,198,87,90,210,43,50,188,221,378,67,113,149,
                          306,391,200,351,292,95,173]
                for holy_water in (True,False):
                    window._restore(base)
                    window.follow_foret_route(261)
                    purchases = ['Gant d’Adresse au Lancer','Brassard de Force'] + (['Eau Bénite'] if holy_water else [])
                    for item in purchases: window.perform_foret_action('buy',(item,1))
                    path = prefix + ([58] if holy_water else [227,312]) + [112,103,360,279,246,204]
                    with patch.object(window,'_assault_luck_choice',return_value=QMessageBox.No), patch(
                            'grimoire_modules.foret.actions.QInputDialog.getItem',return_value=('10 pièces d’or',True)):
                        for index,number in enumerate(path):
                            assert window.current_paragraph == number, (number,window.current_paragraph)
                            if window.combat_available():
                                for _ in range(30):
                                    if not window.combat_available(): break
                                    window.combat_round()
                                assert not window.combat_available()
                            elif number in rules.ENTRY_RULES: window.perform_foret_action('entry')
                            elif number in (358,52,388,90):
                                window.perform_foret_action({358:'snare',52:'bracelet',388:'werewolf_exit',90:'branch_test'}[number])
                            elif number == 279: window.perform_foret_action('payment',(5,[]))
                            if number in (232,173,279):
                                saved = deepcopy(window.character)
                                file = main.SAVES_DIR/'parcours.json'
                                window._write_atomic(file,window._save_data())
                                assert window.load_game(file,announce=False)
                                assert window.character == saved
                            assert window.character['endurance'] > 0
                            if index+1 < len(path) and window.current_paragraph != path[index+1]:
                                window.follow_foret_route(path[index+1])
                    assert rules.hammer_complete(window.character)
                    window.perform_foret_action('hammer')
                    assert window.current_paragraph == 400
                    assert window.character['book_facts']['adventure_ended']
                    result['quests'].append({'holy_water':holy_water,'passages':len(path),'ending':400})
                for width,height in ((1280,800),(930,650)):
                    window.resize(width,height)
                    shot(window,f'16-victoire-{width}')
            finally:
                window.close()
                window.sounds._close_log()
                app.removeEventFilter(theme_filter)
                window.deleteLater()
                app.sendPostedEvents(None, QEvent.DeferredDelete)
    except Exception as error:
        result['errors'].append(str(error))
        raise
    finally:
        app.removeEventFilter(hidden)
        for translator in translators:
            app.removeTranslator(translator)
        qInstallMessageHandler(previous_handler)
        result['font_warnings'] = [m for m in messages if 'QFont' in m]
        result['data_unchanged'] = before == fingerprints(ROOT/'donnees')
        result['source_unchanged'] = source_hash == hashlib.sha256(pdf.read_bytes()).hexdigest()
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not result['data_unchanged'] or not result['source_unchanged']:
        raise RuntimeError('Les empreintes avant/après ne correspondent pas ; voir result.json.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,default=ROOT/'03. La Foret de la Malediction (1983).pdf')
    parser.add_argument('--platform',choices=('windows','offscreen'),default='windows' if sys.platform=='win32' else 'offscreen')
    args = parser.parse_args()
    print(json.dumps(run(args.pdf.resolve(),ROOT/'audit-output/foret-ui-validation',args.platform),ensure_ascii=False,indent=2))
