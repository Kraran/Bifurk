"""Démarrage et fermeture : film, menu de départ, bibliothèque, nouvelle partie, fondu de sortie.

Mixin de MainWindow (voir main.py), sans état propre ni __init__ : les méthodes
lisent et écrivent les attributs de la fenêtre. Les noms définis dans main.py, et
ceux que les tests y remplacent, sont lus à travers le module (`bifurk.NOM`)."""

import shiboken6

from grimoire_library import GrimoireLibraryDialog, imported_grimoires

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import main as bifurk  # module partiellement chargé à l’import : lu à l’exécution


class DemarrageMixin:
    """Démarrage et fermeture : film, menu de départ, bibliothèque, nouvelle partie, fondu de sortie."""

    def _intro_video_path(self):
        """Choisir le film 21:9 sur un écran ultra-large, le 16:9 partout ailleurs."""
        video = bifurk.ASSET_DIR / 'video'
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            size = screen.size()
            if size.height() > 0 and size.width() / size.height() >= 2.0 \
                    and (video / 'introduction_21x9.mp4').is_file():
                return video / 'introduction_21x9.mp4'
        return video / 'introduction.mp4'

    def _play_startup_intro(self):
        """Jouer le film puis afficher le jeu en plein écran, avec la même musique."""
        self.intro_music.menu()
        path = self._intro_video_path()
        if QApplication.platformName() in ('offscreen', 'minimal') or not path.is_file():
            self.showFullScreen()
            self._show_startup_menu()
            return
        from intro_video import IntroVideoDialog
        dialog = IntroVideoDialog(path, self)
        self._intro_dialog = dialog  # Garder le lecteur vivant pendant la cinématique.
        done = []

        def continue_to_game():
            # finished peut être réémis (closeEvent rejette encore le dialogue
            # avant sa destruction différée) : l'enchaînement ne vaut qu'une fois.
            if done:
                return
            done.append(True)
            try:
                dialog.finished.disconnect(continue_to_game)
            except (RuntimeError, TypeError):  # dialogue déjà détruit ou déjà déconnecté
                pass
            self._intro_dialog = None
            if shiboken6.isValid(dialog):
                dialog.deleteLater()
            if not self._can_open_startup_menu():
                return  # fenêtre en cours de fermeture : ne rien relancer
            self.showFullScreen()
            # Attendre le retrait de la vidéo avant d'ouvrir le menu modal.
            QTimer.singleShot(0, self._show_startup_menu)

        dialog.finished.connect(continue_to_game)
        dialog.showMaximized()
        dialog.start()

    # Fermeture demandée (closeEvent) : plus aucun menu de démarrage ne s'ouvre.
    _closing = False

    # Menu de démarrage affiché : un second déclenchement n'en ouvre pas un autre.
    _startup_menu_open = False

    def _can_open_startup_menu(self):
        """Vrai tant que la fenêtre vit et n'est pas en train de se fermer."""
        return shiboken6.isValid(self) and not self._closing

    def _accepts_loading_result(self, session):
        """Vrai si le résultat d'un chargement peut encore être appliqué à cette fenêtre."""
        return not session.abandoned and self._can_open_startup_menu()

    def _show_startup_menu(self):
        """Proposer de continuer la dernière partie, les cinq emplacements ou une nouvelle aventure.

        Rien n'est chargé sans choix du joueur, autosave comprise.

        Appelé par minuterie : la fenêtre peut s'être fermée entre-temps, voire être
        détruite pendant exec() (destruction différée traitée par la boucle locale).
        Le résultat est lu avant toute destruction et plus rien n'est touché ensuite."""
        if not self._can_open_startup_menu() or self._startup_menu_open:
            return
        self._startup_menu_open = True
        try:
            self._run_startup_menu()
        finally:
            if shiboken6.isValid(self):
                self._startup_menu_open = False

    def _run_startup_menu(self):
        self.intro_music.menu()
        while True:
            if not self._can_open_startup_menu():
                return  # fermeture pendant un chargement : ne pas rouvrir le menu
            dialog = bifurk.SaveSlotsDialog(bifurk.SAVES_DIR, False, self, startup=True, cover_for=self._save_cover)
            accepted = dialog.exec() == QDialog.Accepted
            selected, new_game = dialog.selected_path, dialog.new_game_requested
            if shiboken6.isValid(dialog):
                dialog.deleteLater()
            if not accepted or not self._can_open_startup_menu():
                return
            if new_game:
                self._start_new_game()
                return
            if selected and self.load_game(selected):
                return

    def _select_grimoire(self, books):
        """Ne renvoyer une intention qu'après validation du sélecteur, sans changer la partie."""
        reference = self.preferences.get('last_book')
        last = bifurk.BOOKS_DIR / bifurk.portable_reference(reference) if isinstance(reference, str) else None
        dialog = GrimoireLibraryDialog(books, self.pdf_path or last, self)
        try:
            if dialog.exec() != QDialog.Accepted:
                return None
            return ('import', None) if dialog.import_requested else ('open', dialog.selected_path)
        finally:
            dialog.deleteLater()

    def _imported_grimoires(self):
        """Présenter une erreur de bibliothèque sans abandonner la partie en cours."""
        try:
            return imported_grimoires(bifurk.BOOKS_DIR)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Bibliothèque indisponible', str(exc))
            return None

    def show_library(self):
        """Choisir une aventure ou importer un livre, avec confirmation si une partie est en cours."""
        books = self._imported_grimoires()
        if books is None:
            return
        if not books:
            self.open_pdf()
            return
        choice = self._select_grimoire(books)
        if choice is None:
            return
        if self.current_paragraph is not None and QMessageBox.question(
                self, 'Ouvrir un grimoire',
                'Commencer une nouvelle aventure ? La progression non sauvegardée sera abandonnée.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.open_pdf(choice[1] if choice[0] == 'open' else None)

    def _start_new_game(self):
        """Choisir parmi plusieurs livres ; avec un seul, conserver le démarrage direct."""
        books = self._imported_grimoires()
        if books is None:
            return
        if len(books) > 1:
            choice = self._select_grimoire(books)
            if choice is not None:
                self.open_pdf(choice[1] if choice[0] == 'open' else None, startup=True)
            return
        if self.pdf_path and self.paragraphs:
            self._restart_adventure()
            return
        reference = self.preferences.get('last_book')
        path = (bifurk.BOOKS_DIR / bifurk.portable_reference(reference)).resolve() if isinstance(reference, str) else None
        if path and bifurk.within_directory(path, bifurk.BOOKS_DIR) and path.is_file():
            self.open_pdf(path, startup=True)
        elif books:
            self.open_pdf(books[0].path, startup=True)
        else:
            self.open_pdf()

    def confirm_quit(self):
        """Demander confirmation avant de quitter depuis le bouton dédié."""
        answer = QMessageBox.question(
            self, 'Quitter le jeu',
            'Voulez-vous quitter Bifurk ?\n\n'
            'La progression non sauvegardée sera perdue.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.close()

    QUIT_FADE_MS = 600

    # Fondu de fermeture : None (pas commencé), 'running' ou 'done'.
    _quit_fade_state = None

    def _audio_audible(self):
        """Vrai si musique, voix, ambiance ou effet sont en train de jouer."""
        music = self.intro_music
        player, output = getattr(music, 'player', None), getattr(music, 'output', None)
        if player is not None and output is not None and output.volume() > 0:
            from PySide6.QtMultimedia import QMediaPlayer
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                return True
        if self.tts.is_busy() or self.tts.is_fading():
            return True
        mixer = getattr(self.sounds, '_pcm_mixer', None)
        return bool(mixer and any(voice.isPlaying() for voice in mixer.voices))

    def _start_quit_fade(self):
        """Baisser ensemble musique, ambiance, effets, voix et fenêtre, puis fermer pour de bon."""
        from PySide6.QtCore import QVariantAnimation
        self._quit_fade_state = 'running'
        music = self.intro_music
        if getattr(music, 'fade', None) is not None:
            music.fade.stop()  # Le fondu lent de l'accueil cède la place à celui-ci.
        music_output = getattr(music, 'output', None)
        music_start = music_output.volume() if music_output is not None else 0.0
        mixer = getattr(self.sounds, '_pcm_mixer', None)
        opacity = self.windowOpacity()
        self.centralWidget().setEnabled(False)  # Plus aucun clic pendant le fondu.

        def step(value):
            value = float(value)
            if music_output is not None:
                music_output.setVolume(music_start * value)
            if mixer is not None:
                mixer.gain = value
            self.tts.duck(value)
            self.setWindowOpacity(opacity * value)

        def finished():
            self._quit_fade_state = 'done'
            self.close()

        animation = self._quit_fade = QVariantAnimation(self)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setDuration(self.QUIT_FADE_MS)
        animation.valueChanged.connect(step)
        animation.finished.connect(finished)
        animation.start()

    def closeEvent(self, event):
        """Fermer les vues et arrêter les flux avant la fermeture native Qt.

        Si du son joue dans une fenêtre affichée, la fermeture est d'abord différée
        le temps d'un court fondu (QUIT_FADE_MS) ; une seconde demande la termine net.
        Fenêtre cachée ou plateforme sans écran (tests) : fermeture immédiate."""
        if self._quit_fade_state == 'running':
            self._quit_fade.stop()
            self._quit_fade_state = 'done'  # Deuxième demande : fermer sans attendre.
        elif (self._quit_fade_state is None and self.isVisible()
              and QApplication.platformName() not in ('offscreen', 'minimal')
              and self._audio_audible()):
            event.ignore()
            self._start_quit_fade()
            return
        # Avant de rejeter les dialogues : leur signal finished ne doit plus rien relancer.
        self._closing = True
        # Chargements en cours : rendre la main sans attendre et ignorer leur résultat.
        for session in list(getattr(self, '_loading_sessions', ())):
            session.abandon()
        for dialog in self.findChildren(QDialog):
            dialog.reject()
        # Couper net la voix et effacer ses MP3 temporaires (%TEMP%\\bifurk-tts-*).
        self.tts.shutdown()
        self.intro_music.set_enabled(False)
        self.sounds.set_enabled(False)
        self.sounds.set_ambient_enabled(False, fade=False)  # Le fondu de fermeture a déjà eu lieu.
        sink = getattr(self.sounds, '_pcm_sink', None)
        if sink is not None:
            sink.stop()
        self.sounds._close_log()
        super().closeEvent(event)

    def _close_book_dialogs(self):
        """Retirer les vues liées à l'ancien PDF avant de changer d'aventure."""
        for name in ('rules_dialog', 'prologue_dialog'):
            dialog = getattr(self, name, None)
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
                setattr(self, name, None)
