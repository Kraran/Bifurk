"""Point d'entrée Qt et orchestration de l'aventure Bifurk.

MainWindow relie les vues, l'état sérialisable, le PDF privé et les règles du
catalogue. Les calculs réutilisables restent dans book_events ; ModuleActions
délègue les règles particulières au contrôleur du grimoire ouvert. Une action utilisateur
peut appeler plusieurs méthodes : _track_action les regroupe dans une seule
transaction d'historique. _restoring interdit de rejouer les effets à la restauration.

Les chemins portables dérivent du script ou de l'exécutable, jamais du répertoire
courant du terminal. Voir docs/maintenance.md avant de modifier les sauvegardes,
la navigation ou le cycle création / partie / mort.

Les groupes de méthodes autonomes (construction, sauvegardes, démarrage, ambiances,
apparence, disposition, manette) sont des mixins rangés dans fenetre/."""
import sys, re, json, random, copy, os, tempfile, shutil, html
import shiboken6
from collections import Counter
from pathlib import Path, PureWindowsPath
from navigation import destinations, render_links
from illustrations import images_for_paragraph, cover
from grimoire_modules.controller import ModuleActions, sheet_marks
from carnet import CarnetMixin
from grimoire_modules.fighting_fantasy.rules import POTION_STATS, POTION_DOSES
from grimoire_modules.registry import available_modules, module_for_pdf, pdf_digest
from rules_viewer import RulesDialog
from grimoire_library import imported_grimoires, GrimoireLibraryDialog, ImportedGrimoire, cover_icon
from themes import available_themes, default_theme, set_active_theme
import theme_palette
from sound_effects import SoundBank, EFFECT_LABELS, SCENES, creature_sound
from ambience_map import AmbienceMap, KEEP
from intro_music import IntroMusic
from gamepad import Gamepad
from tts import DEFAULT_VOICE, ParagraphReader, available_french_voices
from audio_configuration import configure_audio_backend
from adventure_tracking import LABELS, new_tracking, read_tracking, mark_assisted
from save_slots import SaveSlotsDialog, read_save
from datetime import datetime
from app_info import APP_NAME, APP_VERSION
from about_dialog import AboutDialog, BrandButton
from dice_dialog import DiceDialog
from combat_dialog import CombatDialog
from dialog_chrome import DialogHeading, harmonize_standard_dialog
from stat_feedback import StatFeedback
from loading_progress import LoadingCancelled, LoadingSession
import adventurer_sheet
from adventurer_sheet import (SheetPanel, OrnateHeading, HeroEmblem, HeroMarks, StatMedallion,
                              ResourceToken, ValueLabel, SealButton, RibbonButton, InventoryGrid,
                              SheetStrip, INVENTORY_QUANTITY_ROLE, ALERT_THRESHOLD)
from grimoire_chrome import (LeatherBanner, BannerDivider, MedallionButton, PageToolButton,
                             ParagraphCartouche, ChoiceGroup, illuminated_initial, DrawerScrim,
                             menu_icon)
from grimoire_ui import GrimoireScene, inventory_icon, ChoiceCard, IlluminatedPage, IllustrationDialog, SingleLineTitle, theme_message_box
from book_events import apply_option, verified_entry, apply_effects, resolve_roll, available_routes, equipped_weapon, equip_weapon, SHIELD_NAME, follow_catalogue_route, WEAPON_BONUSES
# Lancé comme script, ce fichier est le module « __main__ » : l’enregistrer aussi sous
# « main » pour que fenetre/* (import main) partage ce module au lieu d’en recharger un second.
if __name__ == '__main__':
    sys.modules.setdefault('main', sys.modules[__name__])
from fenetre.manette import ManetteMixin
from fenetre.ambiances import AmbiancesMixin
from fenetre.apparence import ApparenceMixin
from fenetre.disposition import DispositionMixin
from fenetre.construction import ConstructionMixin
from fenetre.sauvegardes import SauvegardesMixin
from fenetre.demarrage import DemarrageMixin
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, QSize, QTranslator, QLibraryInfo, QLocale, QUrl
from PySide6.QtGui import QActionGroup, QColor, QDesktopServices, QFontDatabase, QTextCursor, QPixmap, QImage, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QAbstractSpinBox, QTextEdit, QPlainTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTextBrowser, QSpinBox,
    QGroupBox, QSlider, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QCheckBox, QSplitter, QComboBox, QDialog, QDialogButtonBox, QScrollArea, QFrame, QTabWidget, QSizePolicy, QMenu)

def _running_tests():
    """Vrai sous un lanceur de tests (python -m unittest, pytest, fichier test_*.py).

    unittest/__main__.py remplace sys.argv[0] par « python -m unittest ». Un autre lanceur
    qui a déjà chargé unittest (sélection de tests maison…) est aussi reconnu. Les outils
    d'audit (tools/, qui utilisent unittest.mock sur les vraies données) et le programme
    compilé ne sont jamais concernés."""
    if getattr(sys, "frozen", False) or not sys.argv:
        return False
    launcher = sys.argv[0]
    name = Path(launcher).name
    if launcher == 'python -m unittest' or name.startswith('test_') or 'pytest' in launcher:
        return True
    return 'unittest.runner' in sys.modules and Path(launcher).resolve().parent.name != 'tools'


def _portable_root():
    """Dossier qui contient donnees/ et musique_perso/.

    À côté de l'exécutable empaqueté ou du script, sauf deux cas :
    - BIFURK_DATA_ROOT désigne un autre dossier (essais, captures, plusieurs profils) ;
    - sous un lanceur de tests, un dossier temporaire neuf, effacé à la fin : les tests
      n'écrivent jamais dans les vraies sauvegardes, préférences ou grimoires du joueur."""
    override = os.environ.get('BIFURK_DATA_ROOT')
    if override:
        return Path(override).resolve()
    if _running_tests():
        import atexit
        root = Path(tempfile.mkdtemp(prefix='bifurk-tests-')).resolve()
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        return root
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


# Répertoire portable : à côté de l'exécutable empaqueté ou du script (voir _portable_root).
APP_DIR = _portable_root()
# PyInstaller place le code et les ressources dans _internal, mais les données
# portables restent à côté de Bifurk.exe. __file__ fonctionne aussi en mode source.
RESOURCE_DIR = Path(__file__).resolve().parent
ASSET_DIR = RESOURCE_DIR / "assets"
# Décors de lecture fournis pour chaque livre ; les autres gardent le décor neutre.
BOOK_BACKGROUNDS = {'foret-1983': 'foret.jpg', 'cite-1983': 'cite.jpg'}
DATA_DIR = APP_DIR / "donnees"
SAVES_DIR = DATA_DIR / "sauvegardes"
BOOKS_DIR = DATA_DIR / "grimoires"
SETTINGS_DIR = DATA_DIR / "parametres"
# Morceaux du joueur, lus en fond sonore si l'option « Jouer ma musique » est cochée :
# à la racine (à côté de main.py en développement, de Bifurk.exe une fois compilé).
MUSIC_DIR = APP_DIR / "musique_perso"


def init_portable_dirs():
    """Créer les dossiers de données portables avant toute importation ou écriture."""
    for directory in (SAVES_DIR, BOOKS_DIR, SETTINGS_DIR, MUSIC_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def within_directory(path, directory):
    """Vérifier l’appartenance après résolution des chemins et liens symboliques.

    relative_to évite les faux préfixes de chemins voisins ; renvoie False hors dossier."""
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False


def import_book(source, digest=None):
    """Importer un PDF par copie temporaire puis remplacement dans grimoires.

    La source reste intacte. Le nom combine son libellé et une empreinte de contenu
    pour distinguer les éditions ; un livre déjà importé n’est pas recopié.
    digest (SHA-256 hexadécimal déjà calculé) évite une seconde lecture du livre."""
    source = Path(source).resolve()
    if not source.is_file() or source.suffix.lower() != '.pdf':
        raise ValueError("Sélectionnez un fichier PDF valide.")
    if within_directory(source, BOOKS_DIR):
        return str(source)
    if digest is None:
        digest = pdf_digest(source)
    target = BOOKS_DIR / f"{source.stem[:75]}_{digest[:12]}.pdf"
    if not target.exists():
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=BOOKS_DIR, suffix='.tmp', delete=False) as handle:
                temp = Path(handle.name)
                with source.open('rb') as original:
                    shutil.copyfileobj(original, handle)
            os.replace(temp, target)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
    return str(target)


def portable_reference(reference):
    """Chemin relatif écrit avec « / » : lisible sous Windows comme ailleurs."""
    return PureWindowsPath(reference).as_posix() if '\\' in reference else reference


def resolve_book_reference(reference):
    """Résoudre uniquement une référence relative vers un grimoire importé existant.

    Refuser les chemins absolus et les sorties du dossier grimoires ; ne pas chercher
    un ancien fichier ailleurs ni importer implicitement un livre pendant le chargement.
    Les « \\ » des anciennes sauvegardes écrites sous Windows sont acceptés
    partout ; un chemin absolu Windows (C:\\…, \\\\serveur\\…) est refusé comme un autre."""
    if (not isinstance(reference, str) or not reference or Path(reference).is_absolute()
            or PureWindowsPath(reference).is_absolute() or PureWindowsPath(reference).drive):
        return None
    candidate = (APP_DIR / portable_reference(reference)).resolve()
    return str(candidate) if within_directory(candidate, BOOKS_DIR) and candidate.is_file() else None


_UNKNOWN_MODULE = object()


def extract_paragraphs(pdf_path, *, module=_UNKNOWN_MODULE, progress=None):
    """Extraire les sections numérotées d’un PDF textuel, sans OCR.

    Le tri PyMuPDF et la suppression des césures facilitent la lecture. Un numéro
    isolé après « rendez-vous au » reste une destination, pas un nouveau titre.
    Le dictionnaire retourné associe numéro entier et texte non vide.
    module évite de recalculer l’empreinte quand l’appelant a déjà reconnu le
    livre ; progress(pages_lues, pages_totales) suit la lecture page à page et
    peut être appelé hors du thread de l’interface (aucun widget touché ici)."""
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF n'est pas installé. Lancez : pip install PyMuPDF") from exc
    with pymupdf.open(pdf_path) as doc:
        total = doc.page_count
        pages = []
        for index, page in enumerate(doc):
            pages.append(page.get_text("text", sort=True))
            if progress is not None:
                progress(index + 1, total)
        text = "\n".join(pages)
    # Normalize common PDF line-break artifacts while preserving paragraph boundaries.
    text = text.replace("\u00ad", "")
    lines = [line.strip() for line in text.splitlines()]
    paragraphs = {}
    current = None
    buffer = []
    for line in lines:
        if re.fullmatch(r"\d{1,3}", line) and buffer and re.search(r"(?i)(?:rendez[- ]?vous|allez|rendre|aller)\s+(?:alors\s+)?au\s*$", buffer[-1]):
            # Un saut de ligne du PDF peut isoler un numéro de destination : ce n'est pas un en-tête.
            buffer.append(line)
        elif re.fullmatch(r"\d{1,3}", line):
            number = int(line)
            # Un numéro de page n'ouvre pas de paragraphe : une section ne commence que si
            # aucune n'est en cours ou si la précédente a déjà du contenu.
            if 1 <= number <= 999 and (current is None or buffer):
                if current is not None:
                    paragraphs[current] = "\n".join(buffer).strip()
                current, buffer = number, []
        elif current is not None and line:
            buffer.append(line)
    if current is not None:
        paragraphs[current] = "\n".join(buffer).strip()
    # Ne corriger le défaut éditorial que pour le PDF exact déjà catalogué.
    if module is _UNKNOWN_MODULE:
        module = module_for_pdf(pdf_path)
    if module is not None:
        module.repair_paragraphs(paragraphs)
    # Écarter les sections vides, notamment les pages liminaires sans contenu.
    return {n: t for n, t in paragraphs.items() if t}


def _extraction_reporter(report, start, end):
    """Traduire les pages lues en progression réelle entre start et end."""
    def pages(done, total):
        report(start + (end - start) * done / max(1, total), "Extraction des paragraphes",
               f"page {done} / {total}")
    return pages


def read_book_for_opening(path, report):
    """Travail d’ouverture sans widget, exécutable hors du thread de l’interface.

    L’empreinte n’est calculée qu’une fois pour reconnaître l’édition, puis transmise
    à l’extraction. Le livre n’est importé que s’il contient des paragraphes."""
    report(.02, "Lecture du livre")
    # Une seule lecture complète : l'empreinte sert à reconnaître l'édition, à
    # nommer la copie importée et à identifier le livre dans les autosauvegardes.
    digest = pdf_digest(path) if Path(path).is_file() else None
    book_module = module_for_pdf(path, digest=digest)
    report(.08, "Extraction des paragraphes")
    paragraphs = extract_paragraphs(path, module=book_module,
                                    progress=_extraction_reporter(report, .08, .85))
    report(.86, "Préparation des catalogues")
    illustrations = book_module.catalogue('illustrations') if book_module else None
    events = book_module.catalogue('events') if book_module else None
    if paragraphs:
        report(.9, "Rangement dans la bibliothèque")
        path = import_book(path, digest=digest)
    return paragraphs, book_module, illustrations, events, path, digest


def read_save_for_loading(path, pdf_hash, report):
    """Lire et valider une sauvegarde sans widget, exécutable hors du thread de l’interface.

    Renvoie (données, livre) où livre vaut None si la sauvegarde ne référence aucun
    grimoire, sinon (pdf, paragraphes, module, illustrations, événements, empreinte). Toute
    incohérence lève une erreur avant que la partie en cours ne soit modifiée."""
    report(.02, "Lecture de la sauvegarde")
    data = read_save(Path(path))
    pdf_reference = data['pdf_path']
    pdf = resolve_book_reference(pdf_reference)
    if not pdf:
        if pdf_reference:
            raise ValueError('Le grimoire de cette sauvegarde est introuvable dans donnees/grimoires.')
        return data, None
    report(.05, "Vérification du grimoire")
    expected = data['pdf_sha256']
    actual = pdf_hash(pdf)
    if expected and expected != actual:
        raise ValueError("Le PDF a changé depuis la sauvegarde.")
    book_module = module_for_pdf(pdf, digest=actual)
    saved_module = data.get('module_id')
    if saved_module is not None and (book_module is None or saved_module != book_module.id):
        raise ValueError("Le module de cette sauvegarde ne correspond pas au grimoire.")
    report(.14, "Extraction des paragraphes")
    paragraphs = extract_paragraphs(pdf, module=book_module,
                                    progress=_extraction_reporter(report, .14, .86))
    report(.87, "Préparation des catalogues")
    illustrations = book_module.catalogue('illustrations') if book_module else None
    events = book_module.catalogue('events') if book_module else None
    return data, (pdf, paragraphs, book_module, illustrations, events, actual)


def franciser_message(dialog):
    """Traduire les boutons usuels d’une QMessageBox en complément des catalogues Qt."""
    noms = {
        QMessageBox.Yes: "Oui", QMessageBox.No: "Non",
        QMessageBox.Ok: "OK", QMessageBox.Cancel: "Annuler",
        QMessageBox.Save: "Enregistrer", QMessageBox.Open: "Ouvrir",
        QMessageBox.Close: "Fermer", QMessageBox.Retry: "Réessayer",
        QMessageBox.Discard: "Ignorer", QMessageBox.Abort: "Abandonner",
    }
    for button_type, label in noms.items():
        button = dialog.button(button_type)
        if button is not None and button.text().strip().lower() in {
            "&yes", "yes", "&no", "no", "&ok", "ok", "cancel", "&cancel",
            "&save", "save", "&open", "open", "&close", "close",
            "retry", "&retry", "discard", "&discard", "abort", "&abort",
        }:
            button.setText(label)


def franciser_selecteur(dialog):
    """Appliquer les libellés français de secours au sélecteur Qt non natif."""
    from PySide6.QtWidgets import QAbstractButton
    tooltips = {
        "Back": "Dossier précédent", "Forward": "Dossier suivant",
        "Parent Directory": "Dossier parent", "Go to parent directory": "Dossier parent",
        "Create New Folder": "Créer un dossier", "New Folder": "Créer un dossier",
        "List View": "Affichage en liste", "Detail View": "Affichage détaillé",
        "Show Hidden Files": "Afficher les fichiers cachés",
        "Go Back": "Retour", "Go Forward": "Suivant",
        "Look in": "Regarder dans", "File name": "Nom du fichier",
        "Files of type": "Type de fichier", "Open": "Ouvrir", "Save": "Enregistrer",
        "Cancel": "Annuler", "Computer": "Ordinateur", "Home": "Dossier personnel",
        "Recent Places": "Emplacements récents", "Desktop": "Bureau",
    }
    for widget in dialog.findChildren(QAbstractButton):
        if widget.text() in tooltips:
            widget.setText(tooltips[widget.text()])
        tip = widget.toolTip()
        if tip in tooltips:
            widget.setToolTip(tooltips[tip])
        accessible = widget.accessibleName()
        if accessible in tooltips:
            widget.setAccessibleName(tooltips[accessible])


def _has_native_titlebar(widget):
    """Fenêtre de premier niveau avec une barre de titre Windows (ni menu, ni bulle, ni cadre absent)."""
    return (isinstance(widget, QWidget) and widget.isWindow()
            and widget.windowType() in (Qt.Window, Qt.Dialog)
            and not widget.windowFlags() & Qt.FramelessWindowHint)


class DialogThemeFilter(QObject):
    """Habiller les fenêtres secondaires et remplacer leurs pictogrammes système.

    Toute fenêtre avec une barre de titre (dialogue, prologue, carte, illustration…)
    reçoit aussi la barre native aux couleurs du thème dès son affichage."""
    def eventFilter(self, obj, event):
        """Habiller à l'affichage et différer la barre native, sans consommer l'événement."""
        if event.type() == QEvent.Show and _has_native_titlebar(obj):
            if isinstance(obj, QDialog):
                harmonize_standard_dialog(obj)
            if isinstance(obj, QMessageBox):
                # Avant la première peinture : aucun flash de l'icône bleue
                # native, même pour les appels statiques information/question.
                theme_message_box(obj)
            # Une minuterie enfant disparaît avec la fenêtre : une fermeture
            # immédiate ne doit jamais rappeler un objet C++ déjà détruit.
            deferred = QTimer(obj)
            deferred.setSingleShot(True)
            def finish_dialog():
                if obj.isVisible():
                    set_native_titlebar(obj)
                    if isinstance(obj, QMessageBox):
                        franciser_message(obj)
                deferred.deleteLater()
            deferred.timeout.connect(finish_dialog)
            deferred.start(0)
        return False


# Attributs DWM (dwmapi.h). Windows 11 : couleurs de la bordure, du fond et du texte
# de la barre ; Windows 10 n'a que le mode sombre (20, ou 19 avant la version 20H1).
DWMWA_USE_IMMERSIVE_DARK_MODE = (20, 19)
DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR = 34, 35, 36
_dwm_set_attribute = None
_titlebar_failures = set()


def _dwm():
    """DwmSetWindowAttribute avec des types explicites (HWND 64 bits sous Windows x64)."""
    global _dwm_set_attribute
    if _dwm_set_attribute is None:
        import ctypes
        from ctypes import wintypes
        function = ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        function.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        function.restype = ctypes.c_long   # HRESULT : 0 si accepté.
        _dwm_set_attribute = function
    return _dwm_set_attribute


def _colorref(color):
    """QColor ou « #rrggbb » → COLORREF Windows (0x00BBGGRR)."""
    color = QColor(color)
    return color.red() | color.green() << 8 | color.blue() << 16


def titlebar_colors(theme):
    """(fond, texte, bordure) de la barre native : le cuir, l'or et le cadre du thème."""
    return (theme.color('icon_background'), theme.color('gold'), theme.color('frame'))


def set_native_titlebar(widget, theme=None):
    """Teinter la barre de titre Windows aux couleurs du thème ; sans effet ailleurs.

    Le mode sombre est demandé d'abord (seul réglage de Windows 10), puis les
    couleurs exactes (Windows 11). Un refus est noté une fois dans le journal
    donnees/parametres/fenetres.log, pour diagnostiquer une version compilée."""
    if sys.platform != "win32":
        return False
    import ctypes
    try:
        function = _dwm()
        hwnd = ctypes.c_void_p(int(widget.winId()))
        dark = ctypes.c_int(1)
        results = {}
        for attribute in DWMWA_USE_IMMERSIVE_DARK_MODE:
            results[attribute] = function(hwnd, attribute, ctypes.byref(dark), ctypes.sizeof(dark))
            if results[attribute] == 0:
                break
        caption, text, border = titlebar_colors(theme or default_theme())
        for attribute, color in ((DWMWA_CAPTION_COLOR, caption), (DWMWA_TEXT_COLOR, text),
                                 (DWMWA_BORDER_COLOR, border)):
            value = ctypes.c_uint32(_colorref(color))
            results[attribute] = function(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as exc:  # noqa: BLE001 - la barre native ne doit jamais bloquer le jeu
        _note_titlebar_failure(f'exception {exc!r}')
        return False
    refused = {attribute: result for attribute, result in results.items() if result != 0}
    if results.get(DWMWA_CAPTION_COLOR) != 0:
        _note_titlebar_failure(f'DWM refus {refused}')
    return results.get(DWMWA_CAPTION_COLOR) == 0


def _note_titlebar_failure(message):
    """Journaliser un refus DWM une seule fois par session ; ne jamais lever."""
    if message in _titlebar_failures:
        return
    _titlebar_failures.add(message)
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with (SETTINGS_DIR / 'fenetres.log').open('a', encoding='utf-8') as log:
            log.write(f'{datetime.now():%Y-%m-%d %H:%M:%S} barre de titre : {message} '
                      f'(Windows {sys.getwindowsversion().build if hasattr(sys, "getwindowsversion") else "?"}, '
                      f'{"compilé" if getattr(sys, "frozen", False) else "source"})\n')
    except OSError:
        pass


def refresh_native_titlebars(theme=None):
    """Repeindre la barre de toutes les fenêtres visibles (changement de thème)."""
    for widget in QApplication.topLevelWidgets():
        if widget.isVisible() and _has_native_titlebar(widget):
            set_native_titlebar(widget, theme)


class RulesLog(QLabel):
    """Journal de règles daté par l'action qui l'écrit, recopié dans le cadre visible.

    Le cachet permet de vider au changement de paragraphe un message laissé par
    une action antérieure (« Victoire ! »), sans effacer celui de l'action qui
    provoque elle-même le déplacement."""

    def __init__(self, text, parent, window):
        super().__init__(text, parent)
        self._window = window
        self.action_stamp = None

    def setText(self, text):
        super().setText(text)
        self.action_stamp = getattr(self._window, '_feedback_action_id', 0)
        frame = getattr(self._window, 'message_frame', None)
        if frame is not None:
            frame.setText(text)
            frame.setVisible(bool(text.strip()))

    def append(self, text):
        """Ajouter une ligne au message de l'action en cours, sinon le remplacer.

        Un jet suivi d'un saut automatique reste ainsi lisible à côté des effets
        appliqués à l'arrivée."""
        earlier = self.text().strip()
        if earlier and self.action_stamp == getattr(self._window, '_feedback_action_id', 0):
            text = f"{earlier} {text}"
        self.setText(text)

    def clear_if_stale(self):
        """Vider un message qui n'appartient pas à l'action en cours."""
        if self.action_stamp != getattr(self._window, '_feedback_action_id', 0) and self.text():
            self.setText('')


DROP_CAP_SCHEME = 'bifurk-initial'


def drop_cap_letter(name):
    """Lettre d'une lettrine d'après le nom de son image (bifurk-initial:<code>-<px>), sinon None."""
    prefix = DROP_CAP_SCHEME + ':'
    if not name.startswith(prefix):
        return None
    code = name[len(prefix):].split('-', 1)[0]
    try:
        return chr(int(code))
    except (ValueError, OverflowError):
        return None


class ReaderBrowser(QTextBrowser):
    """Zone de lecture dont la copie rend la vraie lettre de la lettrine.

    Le texte brut de Qt remplace toute image par U+FFFC (l'attribut alt est ignoré) :
    « Votre » se copiait U+FFFC puis « otre ». Copier (Ctrl+C, menu contextuel) et glisser
    passent tous par createMimeDataFromSelection ; l'affichage n'est pas touché."""

    def createMimeDataFromSelection(self):
        mime = super().createMimeDataFromSelection()
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return mime
        copy = QTextDocument()
        copy.setDefaultFont(self.document().defaultFont())
        QTextCursor(copy).insertFragment(cursor.selection())
        caps = []  # (position, lettre) des images de lettrine dans la copie
        block = copy.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                if fmt.isImageFormat():
                    letter = drop_cap_letter(fmt.toImageFormat().name())
                    if letter:
                        caps.extend((fragment.position() + i, letter) for i in range(fragment.length()))
                it += 1
            block = block.next()
        if not caps:
            return mime
        edit = QTextCursor(copy)
        for position, letter in caps:  # une image = un caractère : les positions ne bougent pas
            # La lettre prend la mise en forme du texte qui la suit (police, couleur).
            text_format = QTextCharFormat()
            if position + 2 <= copy.characterCount() - 1:
                edit.setPosition(position + 2)
                if not edit.charFormat().isImageFormat():
                    text_format = edit.charFormat()
            edit.setPosition(position)
            edit.setPosition(position + 1, QTextCursor.KeepAnchor)
            edit.insertText(letter, text_format)
        # Les données sont produites par Qt à partir de la copie corrigée : un QMimeData
        # créé en Python, cédé au presse-papiers, fait planter la sortie du programme.
        return _MimeExporter().mime_for(copy)


class _MimeExporter(QTextEdit):
    """Fabrique Qt de QMimeData (texte brut, HTML…) pour un document entier."""

    def mime_for(self, document):
        self.setDocument(document)
        self.selectAll()
        return super().createMimeDataFromSelection()


class MainWindow(ManetteMixin, AmbiancesMixin, ApparenceMixin, DispositionMixin, ConstructionMixin, SauvegardesMixin, DemarrageMixin,
                 QMainWindow, ModuleActions, CarnetMixin):
    """Contrôleur principal et propriétaire Qt des vues et services de l’aventure.

    État durable : character, progression, rencontres et instantanés d’historique.
    État temporaire : brouillon de création, widgets, PDF extrait et rendu du thème.
    Le contrôleur du module utilise ce même état ; il ne crée pas un second moteur indépendant."""
    def __init__(self, startup=False):
        """Initialiser état, préférences, services et widgets avant le parcours de démarrage.

        startup=False permet aux tests de construire une fenêtre sans dialogue modal.
        En production, le menu initial est différé pour laisser Qt afficher la fenêtre."""
        super().__init__()
        self.preferences_path = SETTINGS_DIR / "preferences.json"
        try:
            self.preferences = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            if not isinstance(self.preferences, dict):
                self.preferences = {}
        except (OSError, ValueError):
            self.preferences = {}
        self.themes = available_themes(ASSET_DIR / "themes")
        # Sans choix mémorisé (« theme »), chaque livre ouvre son propre thème ;
        # avant tout livre, le thème Standard.
        self.theme = self.themes.get(self.preferences.get("theme"), self.themes["grimoire"])
        theme_palette.configure(self.theme.recolor, self.theme.assets)
        set_active_theme(self.theme)
        configure_audio_backend()
        self.sounds = SoundBank(ASSET_DIR / "sounds", self.preferences.get("sound_enabled", True), self,
                            ambient_enabled=self.preferences.get("ambient_enabled", False),
                            diagnostic_path=SETTINGS_DIR / "audio.log")
        self.sounds.set_effects_volume(self._percent_preference('effects_volume'))
        self.sounds.set_ambient_volume(self._percent_preference('ambient_volume'))
        self.ambience_map = None   # Scènes selon le paragraphe du livre ouvert (s'il en livre).
        # Lecture vocale (voix Edge) : synthèse en arrière-plan, jamais bloquante.
        self.tts = ParagraphReader(self)
        self.tts.set_voice(self.preferences.get("tts_voice", DEFAULT_VOICE))
        self.tts.set_volume(int(self.preferences.get("tts_volume", 80)) / 100)
        self.tts.started.connect(lambda: self._show_tts_state(True))
        self.tts.finished.connect(lambda: self._show_tts_state(False))
        self.tts.error.connect(self._show_tts_error)

        self.intro_music = IntroMusic(ASSET_DIR / 'sounds' / 'FantasyFair.m4a',
                                      self.preferences.get('music_enabled', True), self,
                                      volume_percent=self.preferences.get('music_volume', 70),
                                      persistent=self.preferences.get('music_persistent', False) is True,
                                      custom_folder=MUSIC_DIR,
                                      custom=self.preferences.get('custom_music', False) is True,
                                      victory_path=ASSET_DIR / 'sounds' / 'Achievement.ogg')
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(ASSET_DIR / "bifurk.ico")))
        self._fullscreen = False
        self.resize(1600, 900)
        self.setMinimumSize(930, 650)
        self.pdf_path = None
        # (chemin, SHA-256) du livre ouvert, calculé à l'ouverture ou au chargement :
        # l'autosauvegarde ne relit plus tout le PDF à chaque action.
        self._book_digest = None
        self.book_module = None
        self.illustration_catalogue = None
        self.book_event_catalogue = None
        # Ces trois ensembles répondent à des questions différentes : effet déjà
        # reçu, option déjà choisie, adversaire déjà préparé. Les fusionner ferait
        # réapparaître du butin ou réinitialiserait des combats lors des retours.
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.encounter_history = {}
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self._combat_dialog = None  # Uniquement pendant l'exécution modale.
        self._combat_popup = None   # Chronique conservée si le combat est suspendu.
        self._last_growl = None     # Combat dont le cri d'ouverture a déjà retenti.
        self.paragraphs = {}
        self.current_paragraph = None
        self.visited_paragraphs = []
        self.transitions = []
        # Gabarit d'équipement et valeurs d'affichage hors partie. Les valeurs
        # H/E/C d'une nouvelle aventure sont remplacées par le tirage réglementaire.
        self.character = {
            "habilete": 8, "endurance": 20, "chance": 8,
            "provisions": 10, "gold": 1, "inventory": ["Épée", "Armure de cuir", "Lanterne"],
            "locked_items": [],
            "potion": "Aucune", "potion_doses": 0,
            "initial": {"habilete": 8, "endurance": 20, "chance": 8}
        }
        self._initial_character = copy.deepcopy(self.character)
        # Le brouillon appartient à l'introduction ; il ne doit pas être régénéré
        # quand on change le thème ou la taille des caractères.
        self._adventurer_draft = None
        self._creation_rerolls = 0
        self._creation_name = ''
        self.undo_stack = []
        self.redo_stack = []
        self.action_history = []
        self._restoring = False
        self.adventure_tracking = read_tracking(None)
        self._feedback_action_id = 0  # Identifiant visuel, hors sauvegardes et règles.
        self.reader_font_size = self.DEFAULT_READER_FONT_SIZE
        # Taille choisie avec A−/A+ (session) : prime sur la taille automatique.
        self._user_font_size = None
        self.reading_mode = False
        self._drawer_open = False
        self._sheet_in_drawer = False
        self._tight_layout = None
        self._load_fonts()
        self._default_fonts = (self.reading_font_family, self.ui_font_family)
        self.reading_font_family = self.theme.data.get("fonts", {}).get("reading", self.reading_font_family)
        self.ui_font_family = self.theme.data.get("fonts", {}).get("ui", self.ui_font_family)
        adventurer_sheet.FONTS.update(title=self.reading_font_family, ui=self.ui_font_family)
        self._build_ui()
        # Les variations s'affichent sur le blason-jauge de chaque caractéristique.
        self.stat_feedback = StatFeedback(self, {key: (medallion, None)
                                                 for key, medallion in self.stat_medallions.items()},
                                          lambda: self.theme)
        self._set_theme()
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("F10"), self, activated=self.toggle_reading_mode)
        # Échap ne sert qu'à refermer le tiroir ou quitter le mode lecture ;
        # le plein écran garde son traitement dans keyPressEvent.
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self,
                                         activated=self._escape_layout_mode)
        self.escape_shortcut.setEnabled(False)
        self.sheet_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self, activated=self._tab_sheet_drawer)
        self.sheet_shortcut.setEnabled(False)
        # Manette (XInput sous Windows) : sans effet tant qu'aucune n'est branchée.
        self.gamepad = Gamepad(self, enabled=self.preferences.get('gamepad_enabled', True) is not False)
        self._refresh_character()
        self._show_welcome()
        # Le focus initial va au texte, pas au premier bouton du bandeau.
        self.reader.setFocus()
        if startup:
            QTimer.singleShot(0, self._show_startup_menu)

    def _new_character_template(self):
        """Appliquer les ressources de départ du module à une copie neuve, jamais au héros chargé."""
        character = copy.deepcopy(self._initial_character)
        gold = getattr(self.book_module, 'starting_gold', None)
        if gold is not None:
            character['gold'] = gold
        for item in getattr(self.book_module, 'starting_items', ()):
            if item not in character['inventory']:
                character['inventory'].append(item)
        return character

    def show_prologue(self):
        """Consulter les pages privées du prologue sans appliquer d'effet ni lancer de dés."""
        pages = getattr(self.book_module, 'intro_pages', ())
        if not self.pdf_path or not pages:
            return
        existing = getattr(self, 'prologue_dialog', None)
        if existing is not None and existing.isVisible() and existing.pdf_path == str(self.pdf_path):
            existing.raise_()
            existing.activateWindow()
            return
        if existing is not None:
            existing.close()
            existing.deleteLater()
            self.prologue_dialog = None
        try:
            dialog = RulesDialog(self.pdf_path, self, pages=pages,
                                 title=self.book_module.intro_title, section='Prologue')
        except Exception as exc:
            QMessageBox.warning(self, 'Prologue indisponible', str(exc))
            return
        self.prologue_dialog = dialog
        dialog.show()

    def _refresh_action_controls(self):
        """Actualiser les commandes permanentes sans dépendre d'anciens onglets."""
        if not hasattr(self, 'combat_button'):
            return
        playing = (self.current_paragraph is not None and self._adventurer_draft is None
                   and self.character['endurance'] > 0 and not self.character.get('book_facts', {}).get('adventure_ended'))
        self.combat_button.setEnabled(playing and self.combat_available())
        self.combat_button.setVisible(self.combat_button.isEnabled())
        self._update_tracking_badge()
        self.tools_button.setEnabled(playing)
        self.care_button.setEnabled(playing and any(option['enabled'] for option in self.care_options()))
        meal = next((o for o in self.care_options() if o['id'] == 'meal'), {}) if playing else {}
        self.care_button.setToolTip(meal['reason'] if meal.get('already_ate')
                                    else "Manger une provision ou boire la potion")
        self._refresh_endurance_alert()
        self.prologue_action.setVisible(bool(getattr(self.book_module, 'intro_pages', ())))
        self.carnet_button.setEnabled(self.current_paragraph is not None)
        self._update_bookmark_ribbon()
        if getattr(self, 'carnet_overlay', None) is not None and self.carnet_is_open():
            self.carnet_overlay.book.refresh()


    def _refresh_endurance_alert(self):
        """Mettre en avant le sceau Soins et l'alerte de page si l'Endurance est basse."""
        if not hasattr(self, 'endurance_alert'):
            return
        alert = ''
        if self.care_button.isEnabled() and hasattr(self, 'low_endurance_alert'):
            alert = self.low_endurance_alert()
        self.care_button.set_urgent(bool(alert))
        if alert:
            self.care_button.setToolTip(alert)
        self.endurance_alert_text.setText(alert)
        self.endurance_alert.setVisible(bool(alert))

    def _toggle_inventory(self, expanded):
        """Replier la sacoche pour que la fiche tienne sans défilement."""
        self.adventure_tabs.setVisible(expanded)
        count = len(self.character.get('inventory', []))   # exemplaires, non cases
        noun = 'objet' if count == 1 else 'objets'
        self.inventory_toggle.setText(("▾" if expanded else "▸") + "  SACOCHE && TRÉSORS"
                                      + ("" if expanded else f"  ({count} {noun})"))

    def _selected_inventory_index(self):
        """Position dans l'inventaire du dernier exemplaire de la case choisie, ou -1.

        Une case regroupe les exemplaires identiques : retirer ou employer l'objet
        n'en ôte qu'un, ce qui décrémente le nombre affiché."""
        item = self.inventory_list.currentItem()
        items = self.character.get('inventory', [])
        if item is None or self.inventory_list.currentRow() < 0 or item.text() not in items:
            return -1
        return len(items) - 1 - items[::-1].index(item.text())

    def _equip_from_grid(self, item):
        """Double-clic sur une case de la sacoche : équiper l'arme correspondante."""
        name = item.text() if item is not None else ''
        if name in WEAPON_BONUSES and name != equipped_weapon(self.character):
            self.weapon_combo.setCurrentText(name)

    def _inventory_context_menu(self, pos):
        item = self.inventory_list.itemAt(pos)
        if item is None:
            return
        self.inventory_list.setCurrentItem(item)
        menu = QMenu(self)
        name = item.text()
        if name in WEAPON_BONUSES and name != equipped_weapon(self.character):
            menu.addAction(f'Équiper « {name} »', lambda: self.weapon_combo.setCurrentText(name))
        menu.addAction(f'Retirer « {name} »', lambda: self.manual_inventory(True))
        menu.exec(self.inventory_list.viewport().mapToGlobal(pos))

    def _set_resources_editable(self, editable):
        """Déverrouiller ponctuellement Provisions et Or pour une correction manuelle."""
        for key in ("provisions", "gold"):
            spin = self.stat_spins[key]
            spin.setReadOnly(not editable)
            spin.setProperty("locked", not editable)
            spin.style().unpolish(spin)
            spin.style().polish(spin)
            spin.setFocusPolicy(Qt.StrongFocus if editable else Qt.NoFocus)

    def _render_choices_and_events(self, text):
        """Déléguer au module puis numéroter les choix (raccourcis clavier 1–9)."""
        result = ModuleActions._render_choices_and_events(self, text)
        self._number_choice_cards()
        return result

    def _visible_choice_cards(self):
        cards = []
        layout = getattr(self, 'choice_layout', None)
        if layout is None:
            return cards
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            # Une carte ajoutée à un groupe déjà affiché n'est montrée qu'au tour
            # suivant de la boucle Qt : seule une carte masquée explicitement est exclue.
            if isinstance(widget, ChoiceCard) and not (
                    widget.isHidden() and widget.testAttribute(Qt.WA_WState_ExplicitShowHide)):
                cards.append(widget)
        return cards

    def _number_choice_cards(self):
        for number, card in enumerate(self._visible_choice_cards()[:9], 1):
            card.set_shortcut_number(number)

    def _activate_choice(self, number):
        """Cliquer le n-ième choix visible si aucune boîte de dialogue n'est ouverte."""
        if QApplication.activeModalWidget() is not None or self.carnet_is_open():
            return
        cards = self._visible_choice_cards()
        if 0 < number <= len(cards) and cards[number - 1].isEnabled():
            cards[number - 1].click()

    def _update_tracking_badge(self):
        if hasattr(self, 'tracking_badge'):
            tracking = self.adventure_tracking
            self.tracking_badge.setText(LABELS[tracking['status']])
            self.tracking_badge.setVisible(getattr(self, 'current_paragraph', None) is not None)
            first = tracking['events'][0]['reason'] if tracking['events'] else (
                'Aucune intervention enregistrée.' if tracking['status'] == 'tracked'
                else 'Cette sauvegarde précède le suivi des interventions.')
            self.tracking_badge.setToolTip(first + '\nCliquer pour consulter le journal.')

    def eventFilter(self, obj, event):
        if obj is getattr(self, 'sheet_strip', None) and event.type() in (QEvent.Resize, QEvent.Move):
            self._place_sheet_drawer()
        if obj is getattr(self, 'paragraph_number', None) and event.type() in (QEvent.Show, QEvent.Hide):
            QTimer.singleShot(0, self._update_bookmark_ribbon)
        if event.type() == QEvent.FocusIn and obj in (
                getattr(self, 'enemy_name', None), getattr(self, 'enemy_skill', None),
                getattr(self, 'enemy_endurance', None)):
            self._enemy_edit_before = self._snapshot()
        return super().eventFilter(obj, event)

    def _finish_manual_enemy_edit(self):
        before = getattr(self, '_enemy_edit_before', None)
        self._enemy_edit_before = None
        if before is None or self._restoring:
            return
        values = (self.enemy_name.text(), self.enemy_skill.value(), self.enemy_endurance.value())
        old = (before['enemy_name'], before['enemy_skill'], before['enemy_endurance'])
        if values == old:
            return
        def apply(values):
            for widget, value in zip((self.enemy_name, self.enemy_skill, self.enemy_endurance), values):
                widget.blockSignals(True)
                (widget.setText if isinstance(widget, QLineEdit) else widget.setValue)(value)
                widget.blockSignals(False)
        apply(old)
        def change():
            state = self._snapshot()
            apply(values)
            self._record('Modifier manuellement un adversaire', state)
        self._run_assisted(f'Modification manuelle de l’adversaire : {old} → {values}', change)

    def show_tracking(self):
        tracking = self.adventure_tracking
        entries = '\n'.join(f"{e['at']} — {e['reason']}" for e in tracking['events'])
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowTitle(LABELS[tracking['status']])
        dialog.resize(650, 400)
        layout = QVBoxLayout(dialog)
        journal = QTextBrowser()
        journal.setPlainText(entries or 'Aucune intervention enregistrée.\n'
                             'Ce suivi ne vérifie pas les modifications externes des fichiers.')
        layout.addWidget(journal)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.show()

    def _run_assisted(self, reason, action, *, allow_draft=False):
        """Confirmer à la frontière UI ; les règles normales ne passent pas ici."""
        if ((self._adventurer_draft is not None and not allow_draft)
                or (self.current_paragraph is None and not self.character.get('name'))):
            return False
        if QMessageBox.question(
                self, 'Confirmer une intervention',
                reason + '\n\nCette intervention marquera définitivement cette partie et ses futures '
                'sauvegardes « Partie assistée », même après Annuler. Continuer ?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return False
        before = self._snapshot()
        try:
            action()
        finally:
            if before != self._snapshot():
                mark_assisted(self.adventure_tracking, reason)
                self._update_tracking_badge()
                self._autosave()
        return before != self._snapshot()

    def manual_set_stat(self, key, value):
        old = self._ff_stat_value(key)
        if value != old:
            self._run_assisted(f'Modification manuelle de {key} : {old} → {value}',
                               lambda: self.set_stat(key, value))
            self._refresh_character()  # Restaurer aussi le widget après un refus.

    def manual_inventory(self, removing):
        if removing:
            row = self._selected_inventory_index()
            items = self.character.get('inventory', [])
            if row < 0:
                return False
            if items[row] in self.character.get('locked_items', []):
                self.remove_item()
                return False
            reason, action = 'Retrait manuel : ' + items[row], self.remove_item
        else:
            item = self.item_input.text().strip()
            if not item:
                return False
            reason, action = 'Ajout manuel : ' + item, self.add_item
        return self._run_assisted(reason, action)

    def manual_travel(self, number):
        if (number not in self.paragraphs or number == self.current_paragraph
                or self.character['endurance'] <= 0
                or self.character.get('book_facts', {}).get('adventure_ended')):
            return False
        return self._run_assisted(f'Déplacement manuel du §{self.current_paragraph} au §{number}',
                                  lambda: self.go_to(number))

    def manual_history(self, redo):
        if not (self.redo_stack if redo else self.undo_stack):
            return False
        return self._run_assisted('Rétablir une action' if redo else 'Annuler une action',
                                  self.redo_action if redo else self.undo_action, allow_draft=True)

    def choose_paragraph(self):
        """Ouvrir la navigation manuelle depuis le menu Actions, avec les mêmes contrôles de route."""
        number, accepted = QInputDialog.getInt(self, 'Voyager', 'Numéro de paragraphe :',
                                              self.current_paragraph or 1, 1, self.goto_spin.maximum())
        if accepted:
            self.manual_travel(number)

    def roll_free_dice(self, notation):
        """Présenter tous les jets libres sur le même plateau animé."""
        self.dice_combo.setCurrentText(notation)
        self.roll_dice()


    def show_care_menu(self, anchor=None):
        """Offrir les soins hors combat sans réintroduire un onglet de commandes."""
        anchor = anchor if anchor is not None and anchor.isVisible() else self.care_button
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        for option in self.care_options():
            if option.get('hidden'):
                continue
            action = menu.addAction(option['label'])
            action.setEnabled(option['enabled'])
            action.setToolTip(option['reason'] if not option['enabled'] else '')
            action.triggered.connect(lambda checked=False, kind=option['id']: self.use_care(kind))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        menu.deleteLater()

    def _show_welcome(self):
        """Afficher l’accueil sans livre et désactiver les commandes réservées à une partie."""
        self._ambience_follow_paragraph(None)
        self.paragraph_number.hide()
        self.choice_group.hide()
        self.event_group.hide()
        self.condition_group.hide()
        self.reader.setHtml("<h1>Ouvrez le grimoire.</h1><p>Une porte oubliée. Un trésor légendaire. Et vos décisions pour seule boussole.</p><p>Choisissez votre livre avec <b>Grimoires…</b>, puis découvrez votre nouvel aventurier sur la page d’introduction.</p><p>Explorez, lancez les dés et écrivez votre propre histoire.</p>")

    def _play_book_intro(self):
        """Identifier l’annonce par le module vérifié, jamais par le nom du PDF."""
        self.sounds.play_book_intro(getattr(self.book_module, 'engine', None))

    def _show_book_title(self, *, play_sound=False):
        """Afficher la couverture, le titre et le formulaire de création avant le §1.

        Un simple rafraîchissement conserve le tirage, le nom et le compteur de relances."""
        self._ambience_follow_paragraph(None)
        self.intro_music.menu()
        self._fade_out_reading()  # Le paragraphe lu quitte la page.
        if self._adventurer_draft is None:
            self._prepare_adventurer()
        self.paragraph_number.hide()
        self.current_paragraph = None
        self.paragraph_title.setText("✦  Votre aventure commence ici  ✦")
        self._render_creation_preview()
        if play_sound:
            self._play_book_intro()
        self._clear_dynamic_layout(self.choice_layout)
        first = 1 if 1 in self.paragraphs else min(self.paragraphs)
        label = QLabel('Sous quel nom entrerez-vous dans la légende ?')
        if getattr(self.book_module, 'intro_pages', ()):
            prologue = QPushButton(f'Lire le prologue — {self.book_module.intro_title}')
            prologue.setObjectName('readPrologue')
            prologue.clicked.connect(self.show_prologue)
            self.choice_layout.addWidget(prologue)
        self.choice_layout.addWidget(label)
        name = QLineEdit(self._creation_name)
        name.setObjectName('adventurerName')
        name.setPlaceholderText('Nom de votre aventurier')
        name.setMaxLength(60)
        name.setAccessibleName('Nom de l’aventurier')
        self.choice_layout.addWidget(name)
        self.creation_name_field = name
        self.choice_layout.addWidget(QLabel('Votre potion de départ — une fiole, deux doses'))
        potion = QComboBox()
        potion.setObjectName('startingPotion')
        potion.setAccessibleName('Choisir la potion de départ')
        potion.addItems(list(POTION_STATS))
        potion.setCurrentText(self.character['potion'])
        potion.currentTextChanged.connect(self.change_potion)
        self.choice_layout.addWidget(potion)
        description = QLabel("Adresse : restaure l’Habileté initiale. Vigueur : restaure l’Endurance initiale. "
                             "Bonne Fortune : augmente la Chance initiale de 1 puis la restaure. "
                             "Chaque dose peut être bue via Soins, même en combat.")
        description.setWordWrap(True)
        self.choice_layout.addWidget(description)
        verb = 'Commencer avec cet aventurier' if self._creation_rerolls == 2 else 'Valider cet aventurier et commencer'
        start = ChoiceCard(f'{verb}  →  §{first}')
        start.setObjectName("choiceCard")
        start.setEnabled(bool(name.text().strip()))
        def change_name(text):
            """Conserver la saisie du nom dans le brouillon entre deux rendus de l’introduction."""
            self._creation_name = text
            self.character['name'] = text.strip()
            self.hero_title.setText('L’AVENTURIER\n' + (text.strip() or 'Votre futur héros'))
            start.setEnabled(bool(text.strip()))
        name.textChanged.connect(change_name)
        start.clicked.connect(lambda checked=False: self._begin_adventure(name.text()))
        name.returnPressed.connect(start.click)
        self.choice_group.setTitle("⚜  L’AVENTURE VOUS ATTEND")
        self.creation_start_button = start
        remaining = 2 - self._creation_rerolls
        reroll_text = ('2 relances restantes' if remaining == 2 else
                       '1 relance restante' if remaining == 1 else 'aucune relance restante')
        reroll = ChoiceCard(f'🎲  Reroll — {reroll_text}')
        reroll.setObjectName('rerollAdventurer')
        reroll.setEnabled(self._creation_rerolls < 2)
        reroll.clicked.connect(self._reroll_adventurer)
        self.choice_layout.addWidget(reroll)
        self.creation_reroll_button = reroll
        self.choice_layout.addWidget(start)
        self.choice_group.show()
        self.event_group.hide()
        self.condition_group.hide()
        self._update_scene_art(prefer_cover=True)
        self.adventure_tabs.setEnabled(False)
        self.stats_group.setEnabled(False)
        self.goto_spin.setEnabled(False)
        self.goto_button.setEnabled(False)

    def _prepare_adventurer(self):
        """Créer le premier tirage et son équipement de départ ; remettre les relances à zéro."""
        self.adventure_tracking = new_tracking()
        self._update_tracking_badge()
        self._creation_name = self.character.get('name', '')
        self._creation_rerolls = 0
        self._adventurer_draft = self._roll_adventurer()
        self.character = self._new_character_template()
        self.character.update(potion='Potion de Vigueur', potion_doses=POTION_DOSES)
        self._apply_adventurer_draft()

    def _apply_adventurer_draft(self):
        """Recopier le tirage en attente dans les caractéristiques affichées."""
        self.character['initial'] = copy.deepcopy(self._adventurer_draft)
        self.character.update(self._adventurer_draft)
        if self._creation_name.strip():
            self.character['name'] = self._creation_name.strip()
        self._refresh_character()

    def _render_creation_preview(self):
        """Présenter les caractéristiques tirées sans valider ni consommer un nouveau jet."""
        import html
        title = ((self.illustration_catalogue or {}).get('title') or Path(self.pdf_path).stem)
        stats = self._adventurer_draft
        remaining = 2 - self._creation_rerolls
        instruction = (f'Vous pouvez garder ce tirage ou le relancer encore {remaining} fois.'
                       if remaining else 'Dernier tirage validé automatiquement. Inscrivez votre nom pour partir.')
        preparation = ('<p>Aventure en préparation : l’intégration des événements et des combats est en cours.</p>'
                       if getattr(self.book_module, 'status', 'ready') == 'preview' else '')
        self.reader.setHtml(
            f'<div style="text-align:center; color:{self.theme.color("accent")}; font-family:\'{self.reading_font_family}\';">'
            '<p style="font-size:16pt">✦ LIVRE D’AVENTURE ✦</p>'
            f'<h1 style="font-size:38pt">{html.escape(title)}</h1>{preparation}'
            '<h2>✦ Votre nouvel aventurier ✦</h2>'
            f'<p style="font-size:22pt"><b>Habileté {stats["habilete"]} &nbsp; · &nbsp; '
            f'Endurance {stats["endurance"]} &nbsp; · &nbsp; Chance {stats["chance"]}</b></p>'
            '<p>Habileté : 1d6 + 6 · Endurance : 2d6 + 12 · Chance : 1d6 + 6</p>'
            f'<p>{instruction}</p><p>Le deuxième reroll est définitif.</p></div>')

    def _reroll_adventurer(self):
        """Relancer au plus deux fois après le tirage initial.

        Le dernier tirage est validé automatiquement si le nom est renseigné ; sinon
        il reste figé jusqu’à la saisie du nom et à la validation."""
        if self.current_paragraph is not None or self._adventurer_draft is None or self._creation_rerolls >= 2:
            return
        self._creation_rerolls += 1
        self._adventurer_draft = self._roll_adventurer()
        self._apply_adventurer_draft()
        if self._creation_rerolls == 2 and self._creation_name.strip():
            self._begin_adventure(self._creation_name)
        else:
            self._show_book_title()

    def _restart_adventure(self):
        """Préparer une nouvelle création sur le même livre ; préserver les emplacements manuels."""
        self._adventurer_draft = None
        self._show_book_title(play_sound=True)

    def _begin_adventure(self, name):
        """Valider le nom et le tirage exact, réinitialiser la progression puis entrer au §1.

        Ne pas lancer de dés ici : la validation ne doit jamais remplacer le héros affiché.
        Effacer le brouillon avant go_to pour lever le verrou de création."""
        name = name.strip()[:60]
        if not name or not self.paragraphs or self._adventurer_draft is None or self.current_paragraph is not None:
            return
        self._discard_combat_popup()
        potion = self.character['potion']
        self.character = self._new_character_template()
        self.character.update(potion=potion, potion_doses=POTION_DOSES)
        self.character['name'] = name
        self.character['initial'] = copy.deepcopy(self._adventurer_draft)
        self.character.update(self._adventurer_draft)
        self.character['equipped_weapon'] = 'Épée'
        self.character['magic_sword_bonus_active'] = False
        self._adventurer_draft = None
        self.completed_book_events.clear()
        self.completed_optional_events.clear()
        self.prepared_book_encounters.clear()
        self.encounter_history = {}
        self.book_combat_sequence = self.crocodile_combat = self.piranha_combat = None
        self.piranha_source_wounded = None
        self.book_combat_assaults = {}
        self.current_paragraph = None
        self.visited_paragraphs = []
        self.transitions = []
        self.adventure_tabs.setEnabled(True)
        self.stats_group.setEnabled(True)
        self.goto_spin.setEnabled(True)
        self.goto_button.setEnabled(True)
        self._refresh_character()
        self.enemy_name.setText('Monstre')
        self.enemy_skill.setValue(7)
        self.enemy_endurance.setValue(6)
        self.combat_journal.clear()
        self.combat_state.setText('⚔  Aucun combat engagé')
        self.dice_history.clear()
        self.dice_result.setText('Résultat : —')
        self.dice_faces.setText('⚀   ⚀')
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.action_history.clear()
        self._reset_carnet()
        self.go_to(1 if 1 in self.paragraphs else min(self.paragraphs))
        self.intro_music.fade_out()

    def _show_death_page(self):
        """Afficher la fin d’aventure et proposer recommencer ou charger ; bloquer les actions de jeu."""
        import html
        self._fade_out_reading()  # La page de fin remplace le paragraphe lu.
        self.paragraph_number.hide()
        self._refresh_character()
        name = html.escape(self.character.get('name') or 'Aventurier')
        self.paragraph_title.setText('✦  Fin de l’aventure  ✦')
        self.reader.setHtml(
            f'<div style="text-align:center"><p style="font-size:36pt">⚔</p>'
            f'<h1>La légende de {name} s’achève ici.</h1>'
            '<p>Votre Endurance est épuisée. Le grimoire garde ses secrets…</p>'
            '<p>Un nouveau destin vous attend entre les pages du grimoire.</p></div>')
        self.event_group.hide()
        self.condition_group.hide()
        self._clear_dynamic_layout(self.choice_layout)
        self.choice_group.setTitle('⚜  UNE NOUVELLE CHRONIQUE')
        restart = ChoiceCard('✦  Recommencer l’aventure')
        restart.setObjectName('restartAdventure')
        restart.clicked.connect(self._restart_adventure)
        self.choice_layout.addWidget(restart)
        load = ChoiceCard('Ouvrir une chronique sauvegardée')
        load.clicked.connect(lambda: self.load_game())
        self.choice_layout.addWidget(load)
        self.choice_group.show()
        self.adventure_tabs.setEnabled(False)
        self.stats_group.setEnabled(False)
        self.goto_spin.setEnabled(False)
        self.goto_button.setEnabled(False)

    def open_pdf(self, path=None, *, startup=False):
        """Importer ou ouvrir le PDF, charger ses catalogues puis présenter la création.

        Le livre source n’est pas modifié ; les erreurs de lecture sont présentées en dialogue.
        La lecture (empreinte, texte, catalogues, copie) tourne hors du thread de
        l’interface derrière la barre de chargement ; les widgets ne sont touchés qu’ensuite."""
        if not isinstance(path, (str, Path)):
            path = self._themed_file_dialog(kind="pdf")
        if not path:
            return
        error = None
        session = LoadingSession(self, "Ouverture du grimoire…")
        self.last_loading = session
        with session:
            try:
                paragraphs, book_module, illustrations, events, path, digest = session.run(
                    lambda report: read_book_for_opening(path, report))
            except LoadingCancelled:
                return  # fenêtre fermée pendant la lecture : rien n'est appliqué
            except Exception as exc:
                error = exc
            else:
                if paragraphs and self._accepts_loading_result(session):
                    session.step(.95, "Préparation de l’aventure")
                    self._install_opened_book(path, paragraphs, book_module, illustrations, events,
                                              digest=digest)
                    session.step(1.0, "Préparation de l’aventure")
        if not self._accepts_loading_result(session):
            return  # ni dialogue ni message après la fermeture
        if error is not None:
            QMessageBox.critical(self, "Import impossible", str(error))
            return
        if not paragraphs:
            QMessageBox.warning(self, "Aucun paragraphe", "Aucun paragraphe numéroté n'a été détecté. Le PDF est peut-être scanné ou sa mise en page n'est pas compatible.")
            return
        if self.illustration_catalogue is None and not startup:
            QMessageBox.information(self, "Illustrations", "Ce PDF ne correspond pas exactement à l’édition cataloguée. Les illustrations automatiques sont désactivées pour éviter les mauvaises associations.")

    def _install_opened_book(self, path, paragraphs, book_module, illustrations, events, *, digest=None):
        """Appliquer dans le thread de l’interface un livre lu et importé par read_book_for_opening."""
        self._discard_combat_popup()
        self._close_book_dialogs()
        self.adventure_tracking = read_tracking(None)
        self._update_tracking_badge()
        self.book_module = book_module
        self.sounds.set_ambient_track(getattr(book_module, 'engine', None))
        self._load_ambience_map()
        self._apply_book_theme()  # La page de titre est dessinée plus bas.
        self.pdf_path = path
        self._book_digest = (str(path), digest) if digest else None
        self.illustration_catalogue = illustrations
        self.book_event_catalogue = events
        for key in ("book_state", "book_visits", "book_facts"):
            self.character.pop(key, None)
        self.completed_book_events = set()
        self.completed_optional_events = set()
        self.prepared_book_encounters = set()
        self.encounter_history = {}
        self.book_combat_sequence = None
        self.crocodile_combat = None
        self.piranha_source_wounded = None
        self.piranha_combat = None
        self.book_combat_assaults = {}
        self.paragraphs = paragraphs
        self.book_label.setText(book_module.title if book_module else Path(path).name)
        self.book_label.setToolTip(self.book_label.text())
        self.goto_spin.setMaximum(max(paragraphs))
        self.transitions = []
        self.visited_paragraphs = []
        self.undo_stack.clear(); self.redo_stack.clear()
        self._reset_carnet()
        self._update_history_controls()
        self._adventurer_draft = None
        self._show_book_title(play_sound=True)
        self._remember_book()
        self._autosave()

    def _clear_dynamic_layout(self, layout):
        """Retirer et détruire plus tard les widgets des choix avant de reconstruire la liste."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _paragraph_choices(self, text):
        """Choix de destination prudents, tirés des seuls renvois explicites (« rendez-vous au N »)."""
        choices = []
        # Chaque destination explicite devient un choix cliquable distinct ; son libellé
        # est déduit du texte qui précède immédiatement le renvoi.
        for start, _end, target in destinations(text):
            match_start = start
            prefix = text[:match_start]
            # Partir de la dernière fin de phrase ou de choix, puis retirer les liaisons courantes.
            boundary = max(prefix.rfind("."), prefix.rfind("?"), prefix.rfind("!"), prefix.rfind("\n"))
            # Le livre met souvent la destination entre parenthèses après le choix.
            clause = prefix[boundary + 1:].strip(" \t,;:-()")
            clause = re.sub(r"(?i)\b(ou|et|puis)\s*$", "", clause).strip()
            if not clause:
                clause = 'Poursuivre le chemin'
            if len(clause) > 105:
                clause = clause[-105:].strip()
            # Une même destination n'apparaît qu'une fois par paragraphe.
            if not any(c["target"] == target for c in choices):
                choices.append({"label": clause, "target": target})
        return choices

    def _paragraph_events(self, text):
        """Detect only explicit, simple Endurance/Provision changes; always confirm."""
        events = []
        patterns = [
            (r"(?i)\b(?:vous\s+)?perdez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", -1, "Perte d’Endurance"),
            (r"(?i)\b(?:vous\s+)?gagnez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", 1, "Gain d’Endurance"),
            (r"(?i)\b(?:vous\s+)?récupérez\s+(\d+)\s+points?\s+d['’]endurance\b", "endurance", 1, "Récupération d’Endurance"),
            (r"(?i)\b(?:vous\s+)?perdez\s+(\d+)\s+provisions?\b", "provisions", -1, "Perte de provisions"),
        ]
        for pattern, key, sign, label in patterns:
            for match in re.finditer(pattern, text):
                amount = int(match.group(1)) * sign
                if not any(e["key"] == key and e["amount"] == amount for e in events):
                    events.append({"key": key, "amount": amount, "label": label})
        return events


    def _render_conditions(self, text):
        """Afficher des indices, sans jamais bloquer un chemin d’après une prose incertaine."""
        self._clear_dynamic_layout(self.condition_layout)
        pattern = re.compile(r"(?i)\bsi vous (?:êtes )?(?:en possession d[eu'’]|possédez|avez|disposez d[eu'’])\s+([^,.\n;:]{2,90})")
        # Le catalogue vérifié gère déjà objets, faits et victoires : ne pas
        # lui superposer des hypothèses (« avez vaincu » n'est pas un objet).
        if verified_entry(self.book_event_catalogue, self.current_paragraph):
            return
        matches = [raw for raw in pattern.findall(text)
                   if not re.match(r"(?i)(?:(?:déjà|encore|bien)\s+)*(?:vaincu|tué|eu|réussi|perdu|gagné|visité|trouvé|été)\b", raw)]
        if not matches:
            return
        inventory = [x.casefold() for x in self.character.get("inventory", [])]
        for raw in matches[:8]:
            item = re.sub(r"^(?:la |le |les |l['’]|un |une |des |du |de la )", "", raw.strip(), flags=re.I)
            # Une correspondance partielle est un indice, pas une preuve de possession.
            found = any(item.casefold() in owned or owned in item.casefold() for owned in inventory if len(owned) >= 4)
            label = QLabel(f"{'✓ Objet possiblement présent' if found else '? Objet non reconnu'} : {raw.strip()}")
            label.setWordWrap(True)
            self.condition_layout.addWidget(label)
        self.condition_layout.addWidget(QLabel("Vérifiez le texte original : aucun choix n’est bloqué automatiquement."))

    def show_about(self):
        """Ouvrir la fenêtre d’identité avec les assets et couleurs du thème actif."""
        dialog = AboutDialog(ASSET_DIR, self.theme, self)
        dialog.exec()
        dialog.deleteLater()

    def show_rules(self):
        """Ouvrir les pages de règles du PDF courant dans une fenêtre indépendante."""
        if not self.pdf_path:
            QMessageBox.information(self, "Règles", "Ouvrez un livre pour lire ses règles.")
            return
        existing = getattr(self, "rules_dialog", None)
        if existing is not None and existing.isVisible() and existing.pdf_path == str(self.pdf_path):
            existing.raise_()
            existing.activateWindow()
            return
        try:
            pages = self.book_module.rules_pages if self.book_module else (3, 14)
            dialog = RulesDialog(self.pdf_path, self, pages=pages)
        except Exception as exc:
            QMessageBox.warning(self, "Règles indisponibles", str(exc))
            return
        if existing is not None:
            existing.close()
            existing.deleteLater()
        self.rules_dialog = dialog
        dialog.show()

    def _remember_monster(self, name, status="rencontré", number=None):
        """Enregistrer l’adversaire et son statut sous la clé du paragraphe pour la carte."""
        number = self.current_paragraph if number is None else number
        if self._restoring or number is None:
            return
        entry = verified_entry(self.book_event_catalogue, number)
        state = self._book_state(number)
        if ((entry or {}).get("combat", {}).get("mode") == "paired"
                and state.get("pair", -1) >= 0 and name != "Chef Squelette"):
            name = f"{name} (paire {state['pair'] + 1})"
        monsters = self.encounter_history.setdefault(str(number), [])
        monster = next((m for m in monsters if m["name"] == name), None)
        if monster is None:
            monsters.append({"name": name, "status": status})
        elif status != "rencontré":
            monster["status"] = status

    def _map_monsters_html(self, number):
        """Échapper les noms et formater les rencontres mémorisées d’un lieu exploré."""
        import html
        monsters = self.encounter_history.get(str(number), [])
        return "".join(f'<br>⚔ {html.escape(m["name"])} — {html.escape(m["status"])}' for m in monsters)

    def show_map(self):
        """Afficher seulement les lieux explorés, leurs transitions et l’issue des rencontres."""
        if not self.paragraphs:
            QMessageBox.information(self, "Carte", "Importez d’abord un PDF.")
            return
        from exploration_map import ExplorationMapDialog
        dialog = ExplorationMapDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _paragraph_name(self, number):
        """Lire le titre catalogué d’un lieu, avec repli si le livre n’est pas reconnu."""
        entry = verified_entry(self.book_event_catalogue, number)
        if not entry:
            candidate = (self.book_event_catalogue or {}).get('paragraphs', {}).get(str(number), {})
            # Un titre analysé ou un catalogue de renvois relus est présentable sans
            # autoriser ses règles à s’exécuter.
            if candidate.get('status') in ('analyse_verifiee', 'renvois_verifies'):
                entry = candidate
        return entry.get('title', '') if entry else ''

    def prepare_encounter(self, monster):
        """Proposer une rencontre détectée et renseigner le combat après confirmation."""
        answer = QMessageBox.question(self, "Préparer une rencontre",
            f"Utiliser les caractéristiques de {monster['name']} ?\n"
            f"Habileté : {monster['skill']} — Endurance : {monster['stamina']}\n"
            "Vérifiez le paragraphe : les règles spéciales restent manuelles.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        self._discard_combat_popup()
        self._remember_monster(monster['name'])
        self.enemy_name.setText(monster['name'])
        self.enemy_skill.setValue(monster['skill'])
        self.enemy_endurance.setValue(monster['stamina'])
        self.rules_log.setText(f"Rencontre préparée : {monster['name']}.")
        self.combat_state.setText(f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")
        self.combat_journal.clear()
        self._refresh_action_controls()

    def confirm_item(self, name):
        """Demander confirmation avant d’ajouter un objet suggéré par le texte."""
        if QMessageBox.question(self, "Objet détecté",
                f"Ajouter « {name} » à l’inventaire ?\nVérifiez que vous avez réellement récupéré cet objet.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if name.casefold() in [x.casefold() for x in self.character.get('inventory', [])]:
            QMessageBox.information(self, "Inventaire", "Cet objet est déjà présent.")
            return
        self.character.setdefault('inventory', []).append(name)
        self._refresh_character()
        self.rules_log.setText(f"Objet ajouté : {name}")

    def apply_detected_event(self, event):
        """Confirmer un effet heuristique avant de modifier les caractéristiques."""
        key = event["key"]
        before = int(self.character.get(key, 0))
        after = max(0, before + int(event["amount"]))
        if key in ("endurance", "habilete", "chance"):
            cap = int(self.character.get("initial", {}).get(key, after))
            after = min(after, cap)
        label = {"endurance":"Endurance", "provisions":"Provisions", "habilete":"Habileté", "chance":"Chance"}.get(key, key)
        answer = QMessageBox.question(self, "Confirmer l’événement",
            f"Appliquer {event['label'].lower()} ?\n{label} : {before} → {after}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        self.character[key] = after
        self._refresh_character()
        self.rules_log.setText(f"Événement appliqué : {label} {before} → {after}.")

    def apply_optional_book_event(self, number, option_id):
        """Appliquer un choix catalogué encore disponible et rafraîchir les commandes."""
        if number != self.current_paragraph or self.character["endurance"] <= 0:
            return
        if apply_option(self.character, self.completed_optional_events, number,
                        option_id, self.book_event_catalogue):
            self._refresh_character()
            self.rules_log.setText(f"Objet ou ressource récupéré au paragraphe {number}.")
            self._render_choices_and_events(self.paragraphs[number])

    def resolve_book_roll(self, number):
        """Effectue une seule fois un jet spécial, puis applique son issue."""
        entry = verified_entry(self.book_event_catalogue, number)
        if (number != self.current_paragraph or not entry or entry["mode"] not in ("des", "des_optionnel")
                or "roll" not in entry or number in self.completed_book_events
                or self.character["endurance"] <= 0):
            return
        dice = entry["roll"]["dice"]
        rolls, total = self._roll(dice)
        # Valeur comparée lue avant toute dépense, pour l'afficher avec le jet.
        tested = next((b["key"] for b in entry["roll"]["branches"] if b.get("when") == "lte_stat"), None)
        tested_value = self.character.get(tested) if tested else None
        outcome = resolve_roll(entry["roll"], total, self.character)
        if outcome["target"] not in self.paragraphs:
            QMessageBox.warning(self, "Paragraphe absent",
                                f"Impossible de résoudre l'épreuve : §{outcome['target']} non chargé.")
            return
        followup = outcome.get("followup")
        extra_text = ""
        extra_effects = []
        if followup:
            if followup["kind"] != "stat" or followup["key"] != "gold" or followup["dice"] not in (1, 2):
                raise ValueError("Deuxième tirage non pris en charge")
            extra_rolls, extra_total = self._roll(followup["dice"])
            extra_effects = [{"kind": "stat", "key": "gold", "amount": extra_total}]
            extra_text = f" ; gains : {extra_rolls} = {extra_total} pièces d'or"
        self.completed_book_events.add(number)
        # Le seuil de Chance est évalué AVANT de consommer un point.
        apply_effects(self.character, entry["roll"].get("pre_effects", []))
        apply_effects(self.character, outcome.get("effects", []))
        apply_effects(self.character, [
            {"kind": "stat", "key": effect["key"], "amount": total * effect["multiplier"]}
            for effect in entry["roll"].get("roll_effects", [])])
        apply_effects(self.character, extra_effects)
        self._refresh_character()
        comparison = ""
        if tested:
            names = {"chance": "Chance", "habilete": "Habileté", "endurance": "Endurance"}
            verdict = "réussite" if total <= tested_value else "échec"
            comparison = f" contre {names.get(tested, tested)} {tested_value} : {verdict}"
        self.rules_log.setText(
            f"Épreuve §{number} : dés {rolls} = {total}{comparison}{extra_text} ; destination §{outcome['target']}.")
        if self.character["endurance"] > 0:
            self.go_to(outcome["target"])
        else:
            self._render_choices_and_events(self.paragraphs[number])


    def _illustration_pixmap(self, entry, scale=2):
        """Rendre le rectangle catalogué, avec page PDF base 1 et pixels copiés.

        QImage peut référencer la mémoire PyMuPDF : copy est nécessaire avant fermeture
        du document pour que le QPixmap survive à cette méthode."""
        import pymupdf as fitz
        with fitz.open(self.pdf_path) as doc:
            page = doc[entry["page_pdf"] - 1]
            clip = fitz.Rect(entry["rect"])
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            return QPixmap.fromImage(image.copy())

    def _show_illustration(self, entry, title):
        """Créer une vue zoomable indépendante dimensionnée selon la surface utile de l’écran."""
        try:
            pixmap = self._illustration_pixmap(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Illustration", str(exc))
            return
        if entry.get('type') == 'couverture':
            self._play_book_intro()
        dialog = IllustrationDialog(self)
        dialog.setObjectName("illustrationDialog")
        dialog.setWindowIcon(self.windowIcon())
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        # Respecter la surface utile de l'écran, sans défilement horizontal.
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        max_width = max(320, available.width() - 90)
        max_height = max(260, available.height() - 150)
        displayed = pixmap.scaled(max_width - 44, max_height - 160,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
        viewer = GrimoireScene(self.theme.assets["scene"], theme=self.theme)
        viewer.setMinimumSize(200, 180)
        viewer.set_book_art(pixmap)
        viewer.setAccessibleName(title)
        layout.addWidget(viewer, 1)
        layout.addWidget(QLabel("Molette : zoom · Glisser : déplacer · Clic : recadrer"))
        status = "association probable" if entry.get("statut") == "probable" else "association vérifiée par position" if entry.get("statut") == "verifie_position" else "association vérifiée"
        status_label = QLabel(f"Page PDF {entry['page_pdf']} · {status}")
        status_label.setObjectName("illustrationStatus")
        layout.addWidget(status_label)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.default_size = QSize(min(max_width, max(440, displayed.width() + 54)),
                                    min(max_height, displayed.height() + 175))
        dialog.setMinimumSize(400, 300)
        dialog.resize(dialog.default_size)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def show_cover(self):
        """Afficher le cadrage de couverture s’il existe dans le catalogue associé au PDF."""
        if self.illustration_catalogue:
            entry = cover(self.illustration_catalogue)
            if entry:
                title = self.illustration_catalogue.get('title', 'Grimoire')
                self._show_illustration(entry, 'Couverture — ' + title)

    def show_paragraph_illustration(self):
        """Ouvrir successivement les illustrations associées au paragraphe courant."""
        if not self.illustration_catalogue:
            return
        entries = images_for_paragraph(self.illustration_catalogue, self.current_paragraph)
        for index, entry in enumerate(entries, 1):
            suffix = f" ({index}/{len(entries)})" if len(entries) > 1 else ""
            self._show_illustration(entry, f"Illustration — paragraphe {self.current_paragraph}{suffix}")

    def _combat_exit_pending(self, target):
        """La destination d'un combat reste inaccessible tant qu'il n'est pas résolu."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        combat = entry.get("combat", {}) if entry else {}
        expected = (combat.get("first_hit_target") if combat.get("mode") == "first_hit"
                    else combat.get("victory_target") if len(combat.get("enemies", [])) == 1
                    else None)
        if (combat.get("mode") == "sequence"
                and target == combat.get("victory_target")):
            return self.current_paragraph not in self.prepared_book_encounters
        return (expected == target and (
            combat.get("mode") == "first_hit"
            or self.enemy_endurance.value() > 0))


    def follow_catalogue_choice(self, target):
        """Toutes les issues vérifiées passent par le même contrôle de ressources."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if (not entry or target not in self.paragraphs
                or self._combat_exit_pending(target) or self._book_blocked(target)
                or (self.current_paragraph == 212 and target == 369
                    and 369 in self.visited_paragraphs)
                or (entry.get("diversion_discard")
                    and self.current_paragraph not in self.completed_book_events)
                or (entry.get("enchanted_meal")
                    and self.current_paragraph not in self.completed_book_events)
                or not follow_catalogue_route(self.character, entry, target)):
            QMessageBox.information(
                self, "Chemin inaccessible", "Les conditions de ce passage ne sont pas remplies.")
            return
        self._refresh_character()
        if self.character["endurance"] > 0:
            self.go_to(target)
        else:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])


    def _announce_marks(self, keys):
        """Faire battre une marque à sa mise en place (jamais au rechargement)."""
        self.hero_marks.blink(keys)

    def _refresh_character(self):
        """Synchroniser statistiques, équipement et inventaire sans déclencher de nouvelle action."""
        self.hero_title.setText('L’AVENTURIER\n' +
                                (self.character.get('name') or 'Votre destin s’écrit ici'))
        self.hero_marks.set_marks(sheet_marks(self))
        for key, spin in self.stat_spins.items():
            spin.setEnabled(not self.character.get('book_facts', {}).get('adventure_ended'))
            spin.blockSignals(True)
            spin.setValue(int(self._ff_stat_value(key)))
            spin.blockSignals(False)
        self.potion_combo.blockSignals(True)
        self.potion_combo.setCurrentText(self.character.get("potion", "Aucune"))
        self.potion_combo.blockSignals(False)
        doses = self.character.get('potion_doses', 0)
        has_potion = self.character.get('potion', 'Aucune') != 'Aucune'
        self.potion_doses_label.setText(f'Doses restantes : {doses} / {POTION_DOSES}' if has_potion
                                       else 'Aucune potion')
        self.potion_value.setText(f'{doses}/{POTION_DOSES}' if has_potion else '—')
        self.potion_token.set_caption(re.sub(r"^Potion d(e |')", '', str(self.character.get('potion'))).upper()
                                      if has_potion else 'AUCUNE POTION')
        self.potion_token.setToolTip(f"Potion {self.character.get('potion')} — {self.potion_doses_label.text()}"
                                     if has_potion else 'Aucune potion')
        # Un assaut ne modifie généralement pas le sac : conserver ses items,
        # leur sélection et leur défilement tant que son contenu reste identique.
        inventory = tuple(str(name) for name in self.character.get('inventory', []))
        weapon = equipped_weapon(self.character)
        inventory_signature = (inventory, weapon, *(self.theme.color(key) for key in
                               ('icon_background', 'icon_border', 'icon_ink')))
        if inventory_signature != getattr(self, '_inventory_signature', None):
            self.inventory_list.clear()
            # Exemplaires identiques regroupés dans une seule case, avec leur nombre.
            counts = Counter(inventory)
            for name in dict.fromkeys(inventory):
                item = QListWidgetItem(inventory_icon(name, self.theme), name)
                quantity = counts[name]
                item.setData(INVENTORY_QUANTITY_ROLE, quantity)
                item.setToolTip(name + (f' — {quantity} exemplaires' if quantity > 1 else '')
                                + (' — Arme équipée' if name == weapon else ''))
                self.inventory_list.addItem(item)
            self._inventory_signature = inventory_signature
            if not self.inventory_toggle.isChecked():
                self._toggle_inventory(False)
        self.shield_check.blockSignals(True)
        self.shield_check.setVisible(SHIELD_NAME in self.character.get("inventory", []))
        self.shield_check.setChecked(bool(self.character.get("shield_equipped", False)))
        self.shield_check.blockSignals(False)
        self.weapon_combo.blockSignals(True)
        weapons = [name for name in WEAPON_BONUSES if name in inventory]
        if weapons != [self.weapon_combo.itemText(index) for index in range(self.weapon_combo.count())]:
            self.weapon_combo.clear()
            self.weapon_combo.addItems(weapons)
        if weapon:
            self.weapon_combo.setCurrentText(weapon)
        # Bannière de choix d'arme seulement s'il y a vraiment un choix à faire.
        self.weapon_combo.setVisible(len(weapons) > 1)
        self.weapon_combo.blockSignals(False)
        initial = self.character.get("initial", {})
        for key, medallion in self.stat_medallions.items():
            medallion.set_initial(initial.get(key))
            medallion.setEnabled(not self.character.get('book_facts', {}).get('adventure_ended'))
        for key, medallion in self.stat_medallions.items():
            maximum = max(1, int(initial.get(key, self.character.get(key, 1))))
            current = max(0, int(self._ff_stat_value(key)))
            medallion.set_gauge(current, maximum)
        alerts = self._stat_alerts()
        for key, medallion in self.stat_medallions.items():
            medallion.set_alert(key in alerts)
        self.initial_label.setText("Départ  •  Habileté {habilete}  |  Endurance {endurance}  |  Chance {chance}".format(
            **{key: initial.get(key, "—") for key in ("habilete", "endurance", "chance")}))
        weapon = weapon or "—"
        armor = next((item for item in self.character.get("inventory", []) if "armure" in str(item).casefold() or "bouclier" in str(item).casefold()), "—")
        self.equipment_label.setText(f"⚔  Arme : {weapon}     ◈  Protection : {armor}")
        self._refresh_sheet_strip()
        self._fit_compact_bag()
        self._refresh_action_controls()
        if self._combat_dialog is not None:
            self._combat_dialog.refresh_stats()

        self.stat_feedback.observe({**self.character, 'habilete': self._ff_stat_value('habilete')},
            enabled=(self.isVisible() and self.current_paragraph is not None
                     and self._adventurer_draft is None and not self._restoring),
            batch=self._feedback_action_id)


    def _roll(self, count=1, sides=6, *, context=None, opponent=False):
        """Tirer une seule fois, présenter le résultat animé puis retourner (faces, somme).

        L'animation ne consomme aucun hasard. Les jets 1d6, 2d6, 3d6 et 1d20
        utilisent le même plateau, y compris les combats particuliers."""
        if self._combat_dialog is None:
            self.sounds.play("dice")
        rolls = [random.randint(1, sides) for _ in range(count)]
        trace = getattr(self, '_roll_trace', None)
        if isinstance(trace, list):
            # Relevé pour le cadre de messages : la Chance lue avant sa dépense.
            trace.append({'rolls': list(rolls), 'total': sum(rolls),
                          'chance': self.character.get('chance')})
        if (sides == 6 and count in (1, 2, 3)) or (sides == 20 and count == 1):
            label = context or (f'Épreuve — § {self.current_paragraph}'
                                if self.current_paragraph is not None else 'Création de l’aventurier')
            if self._combat_dialog is not None:
                self._combat_dialog.present_roll(rolls, label, opponent=opponent,
                                                **({'sides': sides} if sides != 6 else {}))
            else:
                self._show_dice_roll(rolls, label, **({'sides': sides} if sides != 6 else {}))
        return rolls, sum(rolls)

    def _show_dice_roll(self, rolls, context, *, sides=6):
        """Présenter les faces tirées sans mutation de partie ni écriture d'historique.

        Les plateformes Qt de test ne lancent pas de boucle modale ; le dialogue
        et sa géométrie restent testables directement en offscreen.
        """
        if QApplication.platformName() in ('offscreen', 'minimal'):
            return
        dialog = DiceDialog(rolls, context, self.theme, self, sides=sides)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()


    def _log_assault(self, player_rolls, enemy_rolls, player_attack, enemy_attack, outcome):
        """Ajouter au journal les dés, forces d’attaque et résultat du dernier assaut."""
        self._book_round_played = True
        self._ff_record_assault()
        self.combat_journal.insertItem(0, f"Vous {player_rolls} = {player_attack} | Ennemi {enemy_rolls} = {enemy_attack} | {outcome}")
        self.combat_state.setText(f"⚔  {self.enemy_name.text()} • Endurance {self.enemy_endurance.value()} | Héros {self.character['endurance']}")
        if self._combat_dialog is not None:
            self._combat_dialog.note_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, outcome)
        while self.combat_journal.count() > 60:
            self.combat_journal.takeItem(self.combat_journal.count() - 1)

    def _log_combat_detail(self, text):
        """Journaliser une phase spéciale sans la compter comme un nouvel assaut."""
        self.combat_journal.insertItem(0, text)
        if self._combat_dialog is not None:
            self._combat_dialog.log(text)

    def open_combat(self):
        """Ouvrir ou reprendre le combat ; l'entrée dans la fenêtre ne modifie pas ses adversaires.

        Le dialogue appelle la méthode d'assaut déjà suivie par l'historique.
        Ne pas envelopper open_combat dans _track_action : chaque assaut conserve
        sa propre transaction, ses effets spéciaux et son autosave.
        """
        if self._combat_dialog is not None or self._adventurer_draft is not None:
            return
        if self.character['endurance'] <= 0:
            self._show_death_page()
            return
        if not self.combat_available():
            return
        popup = self._combat_popup
        if (popup is None or popup.outcome or self.current_paragraph not in popup.paragraphs
                or self.enemy_name.text() not in [e['name'] for e in popup.roster]):
            if popup is not None:
                popup.deleteLater()
            popup = self._combat_popup = CombatDialog(self)
        popup.refresh_stats()
        if popup is not self._last_growl:
            # Cri de l'adversaire à l'ouverture d'un nouveau combat (pas à la reprise).
            self._last_growl = popup
            self.sounds.play(creature_sound(self.enemy_name.text()))
        self._combat_dialog = popup
        self.sounds.duck_ambient(True)
        try:
            popup.exec()
        finally:
            self._combat_dialog = None
            self.sounds.duck_ambient(False)
            self._refresh_after_combat_dialog()

    def _refresh_after_combat_dialog(self):
        """Reconstruire choix et commandes une fois la fenêtre de combat fermée.

        Pendant le combat, les sorties de victoire sont masquées (_combat_exit_pending) ;
        un soin ou une victoire sans saut automatique (§249) laissait sinon la page
        sans aucun choix visible ni bouton Combattre."""
        if (self.current_paragraph in self.paragraphs and self._adventurer_draft is None
                and self.character['endurance'] > 0
                and not self.character.get('book_facts', {}).get('adventure_ended')):
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])
        self._refresh_action_controls()

    def _discard_combat_popup(self):
        """Abandonner la chronique visuelle après restauration, nouvelle partie ou nouvelle rencontre."""
        if self._combat_dialog is None and self._combat_popup is not None:
            self._combat_popup.deleteLater()
            self._combat_popup = None

    def _ask_combat_question(self, title, text):
        """Poser une question du livre dans le combat actif, ou garder le dialogue standard hors combat."""
        if self._combat_dialog is not None:
            return QMessageBox.Yes if self._combat_dialog.choose_luck(title + '\n' + text) else QMessageBox.No
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

    def _assault_luck_choice(self, title, text, information):
        """Partager la décision de Chance entre le plateau et les appels directs du moteur."""
        if self._combat_dialog is not None:
            return QMessageBox.Yes if self._combat_dialog.choose_luck(text + '\n' + information) else QMessageBox.No
        outcome = QMessageBox(self)
        outcome.setWindowTitle(title)
        outcome.setText(text)
        outcome.setInformativeText(information)
        outcome.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        outcome.button(QMessageBox.Yes).setText('Tenter ma Chance')
        outcome.button(QMessageBox.No).setText('Non')
        return outcome.exec()


    def change_weapon(self, name):
        """Équiper une arme présente dans le sac ; opération annulable."""
        if not name:
            return
        if equip_weapon(self.character, name):
            self._refresh_character()
            self.rules_log.setText(
                f"Arme équipée : {name}. Habileté de combat : {self._ff_combat_profile()['skill']}.")

    def add_item(self):
        """Ajouter le nom saisi à l’inventaire et actualiser la sacoche."""
        item = self.item_input.text().strip()
        if item:
            self.character.setdefault("inventory", []).append(item)
            self._refresh_character()
            self.item_input.clear()

    def remove_item(self):
        """Retirer l’objet sélectionné sauf malédiction et annuler ses effets d’équipement.

        Le retrait d’une épée magique doit retirer son bonus courant et initial ; un
        bouclier absent ne doit pas rester équipé dans l’état."""
        row = self._selected_inventory_index()
        if row >= 0:
            item = self.character["inventory"][row]
            if item in self.character.get("locked_items", []):
                QMessageBox.information(
                    self, "Objet maudit",
                    f"Vous ne pouvez pas retirer {item} : cet objet est ensorcelé.")
                return
            if equipped_weapon(self.character) == item and self.character["inventory"].count(item) == 1:
                other = next((name for name in WEAPON_BONUSES
                              if name != item and name in self.character["inventory"]), None)
                if other:
                    equip_weapon(self.character, other)
                elif item == "Épée magique" and self.character.get("magic_sword_bonus_active"):
                    self.character["initial"]["habilete"] = max(
                        0, self.character["initial"]["habilete"] - 2)
                    self.character["habilete"] = max(0, self.character["habilete"] - 2)
                    self.character["magic_sword_bonus_active"] = False
            self.character["inventory"].pop(row)
            self._ff_item_removed(item)
            # Un autre exemplaire resté dans la sacoche garde l'équipement en place.
            remaining = item in self.character["inventory"]
            if item == SHIELD_NAME and not remaining:
                self.character["shield_equipped"] = False
            if self.character.get("equipped_weapon") == item and not remaining:
                self.character["equipped_weapon"] = None
            self._refresh_character()

    def roll_dice(self):
        """Effectuer le jet libre demandé et afficher faces et historique visuel."""
        notation = self.dice_combo.currentText()
        count, sides = notation.lower().split("d")
        rolls, total = self._roll(int(count), int(sides))
        result = f"{notation} : {' + '.join(map(str, rolls))} = {total}"
        self.dice_result.setText(result)
        faces = "⚀⚁⚂⚃⚄⚅"
        self.dice_faces.setText("  ".join((faces[n-1] if 1 <= n <= 6 else str(n)) for n in rolls) if rolls else "—")
        self.dice_history.insertItem(0, result)

    def _snapshot(self):
        """Copier l’état de jeu sérialisable, y compris l’adversaire affiché et les marqueurs.

        Exclure les objets Qt, le PDF et les préférences. Les listes remplacent les sets
        pour JSON ; les copies profondes empêchent une action de modifier les anciens états."""
        return {"character": copy.deepcopy(self.character),
                "encounter_history": copy.deepcopy(self.encounter_history),
                "completed_book_events": sorted(self.completed_book_events),
                "completed_optional_events": sorted(self.completed_optional_events),
                "prepared_book_encounters": sorted(self.prepared_book_encounters),
                "book_combat_sequence": copy.deepcopy(self.book_combat_sequence),
                "crocodile_combat": copy.deepcopy(self.crocodile_combat),
                "piranha_source_wounded": self.piranha_source_wounded,
                "piranha_combat": copy.deepcopy(self.piranha_combat),
                "book_combat_assaults": copy.deepcopy(self.book_combat_assaults),
                "current_paragraph": self.current_paragraph,
                "visited_paragraphs": list(self.visited_paragraphs),
                "transitions": copy.deepcopy(self.transitions),
                "enemy_skill": self.enemy_skill.value(),
                "enemy_endurance": self.enemy_endurance.value(),
                "enemy_name": self.enemy_name.text()}

    def _record(self, label, before):
        """Enregistrer seulement une mutation effective de l’action extérieure.

        Borner Undo à 100 états et le journal à 200 libellés ; invalider Redo, jouer le
        signal de résultat, afficher la mort si nécessaire puis écrire l’autosave."""
        if self._restoring or before == self._snapshot():
            return
        if label != 'Changer de potion':
            self._play_state_sounds(before)
        self.undo_stack.append((label, before))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.action_history.append(label)
        self.action_history = self.action_history[-200:]
        self._update_history_controls()
        if self.character['endurance'] <= 0:
            self._show_death_page()
        self._autosave()

    def _play_state_sounds(self, before):
        """Un seul son d’issue par action ; rien n’est rejoué au rafraîchissement, à l’annulation ni au chargement."""
        from collections import Counter
        old = before["character"]
        new = self.character
        if old.get("endurance", 0) > 0 and new.get("endurance", 0) <= 0:
            self.sounds.play("death")
            return
        old_wins = {(p, m["name"]) for p, monsters in before.get("encounter_history", {}).items()
                    for m in monsters if m["status"] in ("vaincu", "repoussé")}
        wins = {(p, m["name"]) for p, monsters in self.encounter_history.items()
                for m in monsters if m["status"] in ("vaincu", "repoussé")}
        if (wins - old_wins or
                (new.get("book_facts", {}).get("adventure_won")
                 and not old.get("book_facts", {}).get("adventure_won"))):
            self.sounds.play("victory")
            return
        if new.get("potion_doses", 0) < old.get("potion_doses", 0):
            self.sounds.play("potion")
            return
        if (new.get("provisions", 0) < old.get("provisions", 0)
                and new.get("endurance", 0) > old.get("endurance", 0)):
            self.sounds.play("meal")
            return
        source = before["current_paragraph"]
        if source != self.current_paragraph:
            entry = verified_entry(self.book_event_catalogue, source)
            if entry:
                keyed = entry.get("special") == "keys" or any(
                    r["target"] == self.current_paragraph and "clé" in r["label"].casefold()
                    for r in available_routes(old, entry))
                if keyed:
                    self.sounds.play("key")
                    return
                if entry.get("combat", {}).get("escape_target") == self.current_paragraph \
                        and new.get("endurance", 0) < old.get("endurance", 0):
                    self.sounds.play("flee")
                    return
            arrival = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
            # Bruits de passage (catalogue, porte) : ils accompagnent la page tournée et
            # n'empêchent pas le son d'issue (blessure, pièces, objet) de la même action.
            if arrival.get("sound") in EFFECT_LABELS:
                self.sounds.play(arrival["sound"])
            elif self._route_through_door(source, self.current_paragraph):
                self.sounds.play("door")
        if new.get("endurance", 0) < old.get("endurance", 0):
            self.sounds.play("hit")
        elif new.get("gold", 0) != old.get("gold", 0):
            self.sounds.play("coins")
        elif Counter(new.get("inventory", [])) - Counter(old.get("inventory", [])):
            self.sounds.play("item")

    DOOR_WORDS = re.compile(r"(?i)\b(?:porte|portail|grille|trappe|herse)s?\b")
    DOOR_VERBS = re.compile(r"(?i)\b(?:ouvr|pouss|franchi|enfonc|défonc|forc|essay|entr|frapp|déverrouill)\w*")
    DOOR_REFUSAL = re.compile(r"(?i)\bne\s+pas\b|\bsans\b|\bignor\w*|\bplutôt que\b")

    def _route_through_door(self, source, target):
        """Vrai si le choix suivi passe une porte : « ouvrir la porte », « franchir la grille »…

        Le libellé du choix doit nommer l'ouverture et le geste, sans le refuser
        (« ne pas franchir la porte » reste une page tournée)."""
        text = self.paragraphs.get(source)
        if not text:
            return False
        return any(choice["target"] == target and self.DOOR_WORDS.search(choice["label"])
                   and self.DOOR_VERBS.search(choice["label"])
                   and not self.DOOR_REFUSAL.search(choice["label"])
                   for choice in self._paragraph_choices(text))

    def _update_history_controls(self):
        """Mettre à jour les boutons et compteurs à partir des piles Undo / Redo."""
        if not hasattr(self, "undo_btn"):
            return
        self.undo_btn.setEnabled(bool(self.undo_stack))
        self.redo_btn.setEnabled(bool(self.redo_stack))
        self.history_label.setText(f"Historique : {len(self.action_history)} actions · Annulables : {len(self.undo_stack)}")
        summary = f"Historique : {len(self.action_history)} actions · Annulables : {len(self.undo_stack)}"
        self.undo_btn.setToolTip((f"Annuler : {self.undo_stack[-1][0]}\n" if self.undo_stack else "") + summary)
        self.redo_btn.setToolTip(f"Rétablir : {self.redo_stack[-1][0]}" if self.redo_stack else "Rien à rétablir")

    def _restore(self, state):
        """Restaurer une copie d’état et les widgets sans effets de navigation supplémentaires.

        _restoring est toujours relâché dans finally. Un héros déjà accepté revenant à
        l’introduction par Undo ne récupère pas de relances de création."""
        self._discard_combat_popup()
        self._restoring = True
        try:
            self.character = copy.deepcopy(state["character"])
            self.encounter_history = copy.deepcopy(state.get("encounter_history", {}))
            self.completed_book_events = set(state.get("completed_book_events", []))
            self.completed_optional_events = set(state.get("completed_optional_events", []))
            self.prepared_book_encounters = set(state.get("prepared_book_encounters", []))
            self.book_combat_sequence = copy.deepcopy(state.get("book_combat_sequence"))
            self.crocodile_combat = copy.deepcopy(state.get("crocodile_combat"))
            self.piranha_source_wounded = state.get("piranha_source_wounded")
            self.piranha_combat = copy.deepcopy(state.get("piranha_combat"))
            self.book_combat_assaults = {int(k): int(v) for k, v in state.get("book_combat_assaults", {}).items()}
            self.visited_paragraphs = list(state["visited_paragraphs"])
            self.transitions = copy.deepcopy(state.get("transitions", []))
            self.hero_marks.calm()   # une marque rechargée ne clignote jamais
            self._refresh_character()
            if "enemy_skill" in state:
                self.enemy_skill.setValue(state["enemy_skill"])
            if "enemy_endurance" in state:
                self.enemy_endurance.setValue(state["enemy_endurance"])
            if "enemy_name" in state:
                self.enemy_name.setText(state["enemy_name"])
            target = state["current_paragraph"]
            self._adventurer_draft = None
            if target is None and self.character.get('name'):
                self._adventurer_draft = copy.deepcopy(self.character['initial'])
                self._creation_name = self.character['name']
                self._creation_rerolls = 2  # Un héros validé ne peut pas être retiré par Annuler.
            if target in self.paragraphs:
                self.go_to(target)
            else:
                self.current_paragraph = target
                if hasattr(self, 'tts'):
                    self.tts.fade_out()
                if target is None and self.pdf_path and self.paragraphs:
                    self._show_book_title()
        finally:
            self._restoring = False
        alive = self.character['endurance'] > 0
        playing = alive and self.current_paragraph is not None
        self.adventure_tabs.setEnabled(playing)
        self.stats_group.setEnabled(playing)
        self.goto_spin.setEnabled(playing)
        self.goto_button.setEnabled(playing)
        if not alive:
            self._show_death_page()

    def undo_action(self):
        """Empiler l’état courant dans Redo puis restaurer le dernier état antérieur."""
        if not self.undo_stack:
            return
        label, state = self.undo_stack.pop()
        self.redo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action annulée : {label}")
        self._update_history_controls()
        self._autosave()

    def redo_action(self):
        """Empiler l’état courant dans Undo puis réappliquer l’état annulé."""
        if not self.redo_stack:
            return
        label, state = self.redo_stack.pop()
        self.undo_stack.append((label, self._snapshot()))
        self._restore(state)
        self.rules_log.setText(f"Action rétablie : {label}")
        self._update_history_controls()
        self._autosave()

    def set_stat(self, key, value):
        """Appliquer une édition manuelle de caractéristique et rafraîchir sa représentation."""
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return
        before = self._snapshot()
        bonus = self._ff_stat_value(key) - self.character.get(key, 0)
        self.character[key] = max(0, value - bonus)
        self._feedback_action_id += 1
        self._refresh_character()
        self._record(f"Modifier {key}", before)

def _track_action(method, label):
    """Envelopper une méthode pour regrouper ses mutations imbriquées en une action.

    Seul le niveau extérieur capture et enregistre l’état ; _action_depth est remis
    en place dans finally. La restauration court-circuite cet enregistrement."""
    def wrapped(self, *args, **kwargs):
        """Capturer l’action extérieure et terminer ses règles de combat avant enregistrement.

        Le finally rétablit la profondeur même en cas d’erreur et enregistre l’état
        effectivement atteint ; ce mécanisme est un historique, pas un rollback sur exception."""
        if self._restoring:
            return method(self, *args, **kwargs)
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return
        depth = getattr(self, "_action_depth", 0)
        if depth == 0:
            self._feedback_action_id += 1
        before = self._snapshot() if depth == 0 else None
        combat_paragraph = self.current_paragraph
        self._action_depth = depth + 1
        try:
            result = method(self, *args, **kwargs)
            if method.__name__ == "combat_round" and depth == 0:
                self._ff_finish_assault(combat_paragraph)
            return result
        finally:
            self._action_depth -= 1
            if depth == 0:
                self._record(label, before)
                # Fiche en tiroir : elle se replie d'elle-même après une action de jeu.
                self._close_sheet_drawer()
    return wrapped

# Registre des mutations suivies. Ajouter ici une nouvelle commande de jeu
# publique si elle doit être annulable et autosauvegardée. Ne pas y ajouter les
# simples rafraîchissements visuels ni Undo/Redo, qui gèrent leurs propres piles.
for _name, _label in {
    'perform_foret_action': 'Résoudre une mécanique de la Forêt',
    'follow_foret_route': 'Choisir un chemin dans la Forêt',
    'perform_cite_action': 'Résoudre une mécanique de la Cité',
    'follow_cite_route': 'Choisir un chemin dans la Cité',
    'use_care': 'Utiliser un soin',
    "go_to": "Changer de paragraphe", "apply_detected_event": "Appliquer un événement",
    "perform_book_action": "Résoudre une action du livre",
    "resolve_book_roll": "Résoudre une épreuve du livre",
    "escape_scripted_combat": "Fuir un combat du livre",
    "choose_crocodile_strategy": "Choisir une stratégie contre le Crocodile",
    "roll_piranha_target": "Déterminer la cible des Piranhas",
    "apply_optional_book_event": "Choisir une récompense du livre",
    "test_luck": "Tenter sa Chance",
    "eat_meal": "Prendre un repas", "eat_shared_meal": "Partager un repas",
    "drink_potion": "Boire une potion",
    "combat_round": "Assaut de combat", "add_item": "Ajouter un objet",
    "remove_item": "Retirer un objet",
    "change_weapon": "Changer d'arme",
    "change_shield_use": "Utiliser le bouclier",
    "take_book_shield": "Prendre le bouclier",
    "take_book_trade": "Échanger un équipement du livre",
    "throw_book_diversion": "Jeter un objet pour détourner l'Ogre",
    "take_enchanted_meal": "Manger au banc enchanté",
    "follow_catalogue_choice": "Suivre un itinéraire vérifié"
}.items():
    setattr(MainWindow, _name, _track_action(getattr(MainWindow, _name), _label))


def main():
    """Créer QApplication, les traductions et la fenêtre puis lancer la boucle Qt.

    Les répertoires portables et l’identité sont préparés avant l’affichage ; garder
    les traducteurs et le filtre de dialogues vivants pendant toute la session."""
    init_portable_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Bifurk")
    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    app._bifurk_translators = []
    for catalog in ("qtbase_fr", "qt_fr"):
        translator = QTranslator(app)
        search_paths = [APP_DIR / "translations", Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))]
        for folder in search_paths:
            if translator.load(catalog, str(folder)):
                app.installTranslator(translator)
                app._bifurk_translators.append(translator)
                break
    app.setWindowIcon(QIcon(str(ASSET_DIR / "bifurk.ico")))
    window = MainWindow()
    app.setStyleSheet(window.styleSheet())
    app._bifurk_dialog_filter = DialogThemeFilter(app)
    app.installEventFilter(app._bifurk_dialog_filter)
    QTimer.singleShot(0, window._play_startup_intro)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
