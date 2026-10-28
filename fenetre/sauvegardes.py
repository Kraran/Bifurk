"""Préférences, sauvegardes, autosauvegarde et chargement transactionnel d'une partie.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

import copy
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from adventure_tracking import read_tracking
from app_info import APP_VERSION
from dialog_chrome import harmonize_standard_dialog
from grimoire_library import ImportedGrimoire
from grimoire_modules.registry import available_modules, pdf_digest
from loading_progress import LoadingCancelled, LoadingSession

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class SauvegardesMixin:
    """Préférences, sauvegardes, autosauvegarde et chargement transactionnel d'une partie."""

    def _save_preferences(self):
        """Enregistrer les choix d’interface séparément de l’état des sauvegardes."""
        try:
            self._write_atomic(self.preferences_path, self.preferences)
        except OSError:
            self.rules_log.setText("Les préférences n’ont pas pu être enregistrées.")

    def _remember_book(self):
        """Mémoriser le grimoire importé pour les prochaines nouvelles parties."""
        if self.pdf_path and bifurk.within_directory(self.pdf_path, bifurk.BOOKS_DIR):
            self.preferences["last_book"] = Path(self.pdf_path).resolve().relative_to(bifurk.BOOKS_DIR.resolve()).as_posix()
            self._save_preferences()

    def _save_data(self):
        """Construire le JSON courant : instantané, historique, date, version et identité du PDF.

        Le chemin relatif permet de déplacer Bifurk ; le SHA-256 vérifie le livre au
        chargement. Ni texte narratif ni widgets ne sont inclus."""
        return {"adventure_tracking": copy.deepcopy(self.adventure_tracking),
                "version": APP_VERSION, "pdf_path": (Path(self.pdf_path).relative_to(bifurk.APP_DIR).as_posix() if self.pdf_path and bifurk.within_directory(self.pdf_path, bifurk.APP_DIR) else None),
                "saved_at": datetime.now().astimezone().isoformat(),
                "save_name": self.character.get('name') or 'Aventurier sans nom',
                "pdf_sha256": self._pdf_hash(),
                "module_id": self.book_module.id if self.book_module else None,
                "book_title": self.book_module.title if self.book_module else (Path(self.pdf_path).stem if self.pdf_path else ""),
                **self._snapshot(), "action_history": self.action_history,
                "undo_stack": self.undo_stack, "redo_stack": self.redo_stack,
                **self._carnet_save_fields()}

    def _pdf_hash(self, path=None):
        """SHA-256 d'un PDF ; sans chemin, celui du livre ouvert.

        Un chemin explicite (validation avant chargement) est toujours relu : un
        livre remplacé sur le disque doit être détecté. Le livre ouvert garde
        l'empreinte calculée à son ouverture, celle du texte réellement extrait."""
        if path is not None:
            return pdf_digest(path) if Path(path).is_file() else None
        if not self.pdf_path:
            return None
        cached = self._book_digest
        if cached and cached[0] == str(self.pdf_path):
            return cached[1]
        digest = self._pdf_hash(self.pdf_path)
        if digest:
            self._book_digest = (str(self.pdf_path), digest)
        return digest

    def _write_atomic(self, path, data, *, compact=False, durable=True):
        """Écrire un JSON temporaire dans le même dossier, fsync puis os.replace.

        L’ancien fichier reste intact si l’écriture échoue avant remplacement ; nettoyer
        le temporaire dans finally. Le même dossier permet le remplacement atomique.
        compact retire l'indentation ; durable=False saute le fsync (le remplacement
        reste atomique face à un plantage du programme, pas à une coupure de courant)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as f:
                tmp = Path(f.name)
                if compact:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
                else:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                if durable:
                    os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if tmp and tmp.exists():
                tmp.unlink()

    def _autosave(self):
        """Écrire l’état technique séparé des cinq emplacements ; tolérer une erreur disque.

        Écrite après chaque action, l'autosauvegarde reste compacte et sans fsync :
        les cinq emplacements manuels gardent le JSON indenté et l'écriture durable."""
        if not self.pdf_path or self._restoring:
            return
        try:
            directory = bifurk.SAVES_DIR
            self._write_atomic(directory / "autosave.json", self._save_data(),
                               compact=True, durable=False)
        except OSError:
            pass  # La sauvegarde manuelle reste disponible.

    def _themed_file_dialog(self, kind="pdf"):
        """Sélecteur Qt français réservé à l’import d’un grimoire."""
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Bifurk — Ouvrir un grimoire')
        dialog.setWindowIcon(self.windowIcon())
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setLabelText(QFileDialog.LookIn, "Regarder dans :")
        dialog.setLabelText(QFileDialog.FileName, "Nom du fichier :")
        dialog.setLabelText(QFileDialog.FileType, "Type de fichier :")
        dialog.setLabelText(QFileDialog.Accept, "Ouvrir")
        dialog.setLabelText(QFileDialog.Reject, "Annuler")
        dialog.setNameFilter("Grimoires PDF (*.pdf)")
        harmonize_standard_dialog(dialog)
        dialog.setDirectory(str(Path(self.pdf_path).parent if self.pdf_path else bifurk.BOOKS_DIR))
        area = dialog.screen().availableGeometry()
        dialog.resize(min(900, area.width() - 60), min(600, area.height() - 80))
        # Une fermeture immédiate doit arrêter aussi le rappel de traduction.
        translate = QTimer(dialog)
        translate.setSingleShot(True)
        translate.timeout.connect(lambda: bifurk.franciser_selecteur(dialog))
        translate.start(0)
        try:
            if dialog.exec() == QDialog.Accepted:
                selected = dialog.selectedFiles()
                if selected:
                    return str(Path(selected[0]).resolve())
            return None
        finally:
            translate.stop()
            dialog.deleteLater()

    def _save_cover(self, data):
        """Miniature de la couverture du grimoire d'une sauvegarde, sans relire son empreinte.

        Le livre est retrouvé par son chemin relatif et son module ; la miniature est
        gardée en mémoire pour la session (jamais écrite sur le disque)."""
        pdf = bifurk.resolve_book_reference(data.get('pdf_path'))
        if not pdf:
            return QIcon()
        key = (pdf, data.get('module_id'), data.get('pdf_sha256'))
        cache = self.__dict__.setdefault('_cover_cache', {})
        if key not in cache:
            module = next((m for m in available_modules()
                           if m.id == key[1] or (key[1] is None and m.pdf_sha256 == key[2])), None)
            cache[key] = (bifurk.cover_icon(ImportedGrimoire(Path(pdf), module.title, module))
                          if module else QIcon())
        return cache[key]

    def _themed_save_dialog(self, saving):
        """Ouvrir le menu des emplacements et retourner le chemin choisi ou lancer une création."""
        dialog = bifurk.SaveSlotsDialog(bifurk.SAVES_DIR, saving, self, cover_for=self._save_cover)
        accepted = dialog.exec() == QDialog.Accepted
        path = dialog.selected_path if accepted else None
        new_game = accepted and dialog.new_game_requested
        dialog.deleteLater()
        if new_game:
            self._start_new_game()
        return path

    def save_game(self):
        """Choisir un emplacement puis écrire atomiquement la partie ou signaler l’erreur."""
        if self.current_paragraph is None:
            QMessageBox.information(self, 'Aventure à commencer',
                                    'Inscrivez le nom de votre aventurier et commencez l’aventure avant de sauvegarder.')
            return
        path = self._themed_save_dialog(saving=True)
        if not path:
            return
        data = self._save_data()
        try:
            self._write_atomic(path, data)
            QMessageBox.information(self, "Sauvegarde", "Partie sauvegardée.")
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))

    def load_game(self, path=None, *, announce=True):
        """Valider le format, le chemin portable et l’empreinte du PDF avant restauration.

        Recharger texte et catalogues depuis le livre puis restaurer l’état et les piles
        d’historique sans rejouer ses effets. announce contrôle l’affichage des erreurs."""
        self.intro_music.menu()
        if not isinstance(path, (str, Path)):
            path = self._themed_save_dialog(saving=False)
        if not path:
            if self.current_paragraph is not None:
                self.intro_music.fade_out()
            return
        session = LoadingSession(self, "Chargement de la sauvegarde…")
        self.last_loading = session
        error = None
        with session:
            try:
                data, book = session.run(lambda report: bifurk.read_save_for_loading(path, self._pdf_hash, report))
                if not self._accepts_loading_result(session):
                    raise LoadingCancelled()
                session.step(.93, "Restauration de l’aventure")
                self._apply_loaded_save(data, book)
                session.step(1.0, "Restauration de l’aventure")
            except LoadingCancelled:
                return False  # fenêtre fermée pendant la lecture : rien n'est appliqué
            except Exception as exc:
                error = exc
        if not self._accepts_loading_result(session):
            return False  # ni musique, ni introduction, ni dialogue après la fermeture
        if error is not None:
            if self.current_paragraph is not None:
                self.intro_music.fade_out()
            if announce:
                QMessageBox.critical(self, "Chargement impossible", str(error))
            return False
        self.intro_music.fade_out()
        self._play_book_intro()
        if announce:
            QMessageBox.information(self, "Chargement", "Partie chargée.")
        return True

    def _apply_loaded_save(self, data, book):
        """Restaurer dans le thread de l’interface une sauvegarde validée par read_save_for_loading.

        Tout ou rien : si la restauration échoue en cours de route, la partie précédente
        (livre, aventurier, historique, carnet) est remise en place avant de relancer
        l’erreur, qui sera présentée par load_game."""
        previous = self._capture_session()
        try:
            self._install_loaded_save(data, book)
        except Exception:
            try:
                self._rollback_session(previous)
            except Exception:  # noqa: BLE001 - l'erreur d'origine reste celle à signaler
                pass
            raise

    def _capture_session(self):
        """Copier tout ce qu'un chargement remplace, pour pouvoir l'annuler."""
        return {
            'book': (self.pdf_path, self._book_digest, self.paragraphs, self.book_module,
                     self.illustration_catalogue, self.book_event_catalogue),
            'label': (self.book_label.text(), self.book_label.toolTip()),
            'goto_maximum': self.goto_spin.maximum(),
            'state': self._snapshot(),
            'history': (list(self.action_history), list(self.undo_stack), list(self.redo_stack)),
            'tracking': copy.deepcopy(self.adventure_tracking),
            'carnet': copy.deepcopy(self._carnet_save_fields()),
            'creation': (copy.deepcopy(self._adventurer_draft), self._creation_name,
                         self._creation_rerolls),
        }

    def _rollback_session(self, previous):
        """Remettre la partie copiée par _capture_session après un chargement manqué."""
        (self.pdf_path, self._book_digest, self.paragraphs, self.book_module,
         self.illustration_catalogue, self.book_event_catalogue) = previous['book']
        self.sounds.set_ambient_track(getattr(self.book_module, 'engine', None))
        self._load_ambience_map()
        self._apply_book_theme()
        self.book_label.setText(previous['label'][0])
        self.book_label.setToolTip(previous['label'][1])
        self.goto_spin.setMaximum(previous['goto_maximum'])
        self._restore(previous['state'])
        # À l'introduction, _restore peut préparer un nouveau tirage : rétablir
        # exactement l'aventurier, le brouillon et le suivi d'avant le chargement.
        self.character = copy.deepcopy(previous['state']['character'])
        draft, self._creation_name, self._creation_rerolls = previous['creation']
        self._adventurer_draft = copy.deepcopy(draft)
        self.action_history, self.undo_stack, self.redo_stack = (
            list(items) for items in previous['history'])
        self.adventure_tracking = previous['tracking']
        self._update_tracking_badge()
        self._load_carnet(previous['carnet'])
        if self.current_paragraph is None:
            if self.pdf_path and self.paragraphs and self._adventurer_draft is not None:
                self._show_book_title()
            elif not self.pdf_path:
                self._show_welcome()
        self._refresh_character()
        self._update_history_controls()

    def _install_loaded_save(self, data, book):
        """Appliquer une sauvegarde validée ; _apply_loaded_save garantit le tout ou rien."""
        if book is not None:
            pdf, paragraphs, book_module, illustration_catalogue, events, digest = book
            self._close_book_dialogs()
            self.pdf_path = pdf
            self._book_digest = (str(pdf), digest) if digest else None
            self.paragraphs = paragraphs
            self.illustration_catalogue = illustration_catalogue
            self.book_module = book_module
            self.sounds.set_ambient_track(getattr(book_module, 'engine', None))
            self._load_ambience_map()
            self._apply_book_theme()  # _restore redessine la page ensuite.
            self.book_event_catalogue = events
            self.book_label.setText(book_module.title if book_module else Path(pdf).name)
            self.book_label.setToolTip(self.book_label.text())
            if self.paragraphs:
                self.goto_spin.setMaximum(max(self.paragraphs))
        self._restore(data)
        self.adventure_tracking = read_tracking(data.get("adventure_tracking"))
        self._update_tracking_badge()
        self.action_history = data['action_history']
        self.undo_stack = [(label, state) for label, state in data['undo_stack']]
        self.redo_stack = [(label, state) for label, state in data['redo_stack']]
        # Champs facultatifs : une sauvegarde antérieure au carnet se charge carnet vide.
        self._load_carnet(data)
        self._update_history_controls()
        self._remember_book()
