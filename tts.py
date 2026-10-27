"""Lecture vocale des paragraphes avec les voix neurales Microsoft Edge (edge-tts).

Même service que « Lire à haute voix » d’Edge : une connexion Internet est requise.
La synthèse tourne dans un fil secondaire (``asyncio.run``) vers un MP3 temporaire ;
la lecture est confiée au fil principal par ``QMetaObject.invokeMethod`` et passe par
QMediaPlayer. Toute erreur (réseau absent, paquet manquant) reste silencieuse pour
l’interface : seul le signal ``error`` porte un message court.

Une lecture interrompue (nouveau paragraphe, bouton ⏹) s’éteint en un court fondu
(``fade_out``) ; ``shutdown`` coupe net et efface tout, pour la fermeture du programme.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import (Q_ARG, QEasingCurve, QMetaObject, QObject, Qt, QUrl, QVariantAnimation,
                            Signal, Slot)

# Liste de secours, affichée immédiatement et sans réseau.
FRENCH_VOICES = {
    "fr-FR-RemyMultilingualNeural": "Rémy Multilingue",
    "fr-FR-VivienneMultilingualNeural": "Vivienne Multilingue",
    "fr-FR-DeniseNeural": "Denise",
    "fr-FR-HenriNeural": "Henri",
    "fr-FR-EloiseNeural": "Eloise",
}
DEFAULT_VOICE = "fr-FR-RemyMultilingualNeural"
_voice_cache: dict[str, str] = dict(FRENCH_VOICES)
_voice_refresh: threading.Thread | None = None


def _voice_label(voice: dict) -> str:
    """« fr-CA-SylvieNeural » → « Sylvie (fr-CA) », en gardant les libellés connus."""
    short = voice.get("ShortName", "")
    if short in FRENCH_VOICES:
        return FRENCH_VOICES[short]
    name = short.split("-", 2)[-1].removesuffix("Neural").replace("Multilingual", " Multilingue").strip()
    return f"{name} ({voice.get('Locale', short[:5])})"


def _refresh_voices() -> None:
    """Interroger le service une fois, en arrière-plan ; garder la liste de secours sinon."""
    try:
        import edge_tts
        voices = asyncio.run(edge_tts.list_voices())
    except Exception:  # noqa: BLE001 - toute panne réseau ou de service garde le secours
        return
    found = {v["ShortName"]: _voice_label(v) for v in voices
             if str(v.get("Locale", "")).startswith("fr-") and v.get("ShortName")}
    if found:
        _voice_cache.update(found)


def available_french_voices(refresh: bool = True) -> dict[str, str]:
    """Voix françaises connues, sans jamais attendre le réseau.

    Renvoie aussitôt le cache (liste de secours au départ) ; le premier appel lance une
    seule mise à jour en arrière-plan qui enrichira les appels suivants.
    """
    global _voice_refresh
    if refresh and _voice_refresh is None:
        _voice_refresh = threading.Thread(target=_refresh_voices, daemon=True)
        _voice_refresh.start()
    return dict(_voice_cache) or dict(FRENCH_VOICES)


def prepare_speech_text(text: str) -> str:
    """Recoller les lignes du PDF pour une lecture fluide.

    Les retours à la ligne de mise en page deviennent des espaces, les mots coupés
    en fin de ligne (« aven-\nturier ») sont recollés, et seules les vraies fins de
    paragraphe (ligne vide ou ligne terminée par une ponctuation forte) gardent une pause.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    text = re.sub(r"(\w)-[ \t]*\n[ \t]*(?=[a-zàâäçéèêëîïôöùûüÿœæ])", r"\1", text)
    text = re.sub(r"(\w-)[ \t]*\n[ \t]*(?=\w)", r"\1", text)
    blocks = []
    for block in re.split(r"\n[ \t]*\n+", text):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        merged = lines[0]
        for line in lines[1:]:
            merged += ("\n" if merged[-1] in ".!?:»…" and line[0].isupper() else " ") + line
        blocks.append(merged)
    text = "\n\n".join(blocks)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def split_speech_chunks(text: str, first_limit: int = 160, limit: int = 300) -> list[str]:
    """Découper en phrases regroupées : un premier morceau court pour démarrer vite."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?…»])\s+|\n+", text or "") if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        cap = first_limit if not chunks else limit
        if current and len(current) + 1 + len(sentence) > cap:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


class ParagraphReader(QObject):
    """Synthétise et lit un paragraphe par morceaux ; un nouvel appel arrête le précédent."""

    started = Signal()
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player = None   # Lecteur actif.
        self._output = None
        self._spare = None    # Second lecteur : le morceau suivant y est préchargé.
        self._spare_output = None
        self._spare_file: Path | None = None
        self._gain = "+0%"   # Renfort demandé au service au-delà de 100 % (figé à chaque speak()).
        self._voice = DEFAULT_VOICE
        self._rate = "+0%"
        self._volume = 0.8
        self._pending = False
        self._request = 0  # Numéro de la demande en cours ; les synthèses périmées sont ignorées.
        self._temp_file: Path | None = None
        self._queue: list[Path] = []
        self._synth_done = True
        # Fondu de sortie : une seule animation, réutilisée, et le lecteur qu’elle éteint.
        self._fade: QVariantAnimation | None = None
        self._fading = None  # (lecteur, sortie, fichier) retirés de la lecture.
        self._idle: list = []  # Lecteurs éteints, réutilisés plutôt que détruits.

    @property
    def voice(self) -> str:
        return self._voice

    def set_voice(self, voice_id: str) -> None:
        if voice_id and (voice_id in _voice_cache or voice_id.startswith("fr-")):
            self._voice = voice_id

    def set_rate(self, percent: int) -> None:
        percent = max(-50, min(100, int(percent)))
        self._rate = f"{percent:+d}%"

    MAX_VOLUME = 1.5
    FADE_MS = 250  # Durée du fondu de sortie d’une lecture interrompue.

    def set_volume(self, volume: float) -> None:
        """0 à 1 : volume du lecteur, appliqué aussitôt ; 1 à 1,5 : voix renforcée par le service.

        Le renfort est demandé à la synthèse : le paragraphe en cours, déjà synthétisé
        à son lancement, le garde inchangé ; il s’applique à partir de la prochaine lecture."""
        volume = max(0.0, min(self.MAX_VOLUME, float(volume)))
        self._volume = min(1.0, volume)
        self._gain = f"{round((volume - 1.0) * 100):+d}%" if volume > 1.0 else "+0%"
        for output in (self._output, self._spare_output):
            if output is not None:
                output.setVolume(self._volume)

    def is_busy(self) -> bool:
        """Synthèse en attente ou lecture en cours."""
        return self._pending or self.is_playing()

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def fade_out(self) -> None:
        """Arrêter la lecture par un court fondu ; la synthèse en cours devient caduque."""
        self.stop(fade_ms=self.FADE_MS)

    def shutdown(self) -> None:
        """Fermeture du programme : couper net, terminer les fondus et effacer les MP3."""
        self.stop()
        self._finish_fade()

    def stop(self, fade_ms: int = 0) -> None:
        """Arrêter la lecture et rendre caduque toute synthèse en cours.

        fade_ms > 0 : le morceau audible s’éteint en fondu sur son propre lecteur, retiré
        du lecteur actif ; une nouvelle lecture peut démarrer aussitôt sur un autre."""
        self._request += 1
        was_busy = self._pending or self.is_playing()
        self._pending = False
        self._synth_done = True
        if fade_ms > 0 and self.is_playing():
            self._detach_and_fade(fade_ms)
        for player in (self._player, self._spare):
            if player is not None:
                player.stop()
                player.setSource(QUrl())
        self._cleanup_temp()
        self._drop_spare()
        while self._queue:
            with contextlib.suppress(OSError):
                self._queue.pop(0).unlink()
        if was_busy:
            self.finished.emit()

    def is_fading(self) -> bool:
        """Un morceau interrompu est encore en train de s’éteindre."""
        return self._fading is not None

    def _detach_and_fade(self, duration: int) -> None:
        """Retirer le lecteur audible de la lecture et baisser son volume jusqu’au silence.

        Un fondu précédent encore en cours se termine net : un seul lecteur s’éteint à la fois."""
        self._finish_fade()
        player, output, path = self._player, self._output, self._temp_file
        self._player = self._output = None
        self._temp_file = None
        # Plus actif ni de réserve : _on_media_status et _on_error l’ignorent désormais,
        # il n’enchaîne donc plus aucun morceau.
        self._fading = (player, output, path)
        if self._fade is None:
            self._fade = QVariantAnimation(self)
            self._fade.setEndValue(0.0)
            self._fade.setEasingCurve(QEasingCurve.Type.InQuad)
            self._fade.valueChanged.connect(self._fade_step)
            self._fade.finished.connect(self._finish_fade)
        self._fade.setStartValue(float(output.volume()))
        self._fade.setDuration(duration)
        self._fade.start()

    def _fade_step(self, value) -> None:
        if self._fading is not None:
            self._fading[1].setVolume(float(value))

    def _finish_fade(self) -> None:
        """Arrêter le lecteur éteint, effacer son MP3 et le remettre en réserve."""
        fading, self._fading = self._fading, None
        if fading is None:
            return
        if self._fade is not None:
            self._fade.stop()  # Sans effet si l’animation vient de se terminer.
        player, output, path = fading
        player.stop()
        player.setSource(QUrl())
        if path is not None:
            with contextlib.suppress(OSError):
                path.unlink()
        # Pas de deleteLater : il reste enfant du lecteur vocal et sert à la prochaine lecture.
        self._idle.append((player, output))

    def speak(self, text: str) -> None:
        self.fade_out()  # L’ancienne lecture s’éteint pendant la synthèse de la nouvelle.
        chunks = split_speech_chunks(prepare_speech_text(text))
        if not chunks:
            return
        request, voice, rate = self._request, self._voice, (self._rate, self._gain)
        self._pending = True
        self._synth_done = False
        self.started.emit()
        threading.Thread(target=self._synthesize, args=(request, chunks, voice, rate), daemon=True).start()

    # --- Fil secondaire ---------------------------------------------------------
    def _synthesize(self, request: int, chunks: list[str] | str, voice: str, rate) -> None:
        """Préparer tous les morceaux en parallèle et les livrer dans l’ordre : pas de blanc entre eux."""
        if isinstance(chunks, str):
            chunks = [chunks]
        try:
            import edge_tts
        except ImportError:
            QMetaObject.invokeMethod(self, "_fail", Qt.QueuedConnection, Q_ARG(int, request),
                                     Q_ARG(str, "Lecture vocale indisponible (paquet edge-tts absent)."))
            return
        asyncio.run(self._synthesize_all(edge_tts, request, chunks, voice, rate))

    async def _synthesize_all(self, edge_tts, request: int, chunks: list[str], voice: str, rate) -> None:
        rate, gain = rate if isinstance(rate, tuple) else (rate, "+0%")
        extra = {"volume": gain} if gain != "+0%" else {}
        limit = asyncio.Semaphore(3)

        async def one(chunk: str) -> Path | None:
            async with limit:
                if request != self._request:
                    return None
                with tempfile.NamedTemporaryFile(prefix="bifurk-tts-", suffix=".mp3", delete=False) as tmp:
                    path = Path(tmp.name)
                try:
                    await edge_tts.Communicate(chunk, voice, rate=rate, **extra).save(str(path))
                    if path.stat().st_size == 0:
                        raise RuntimeError("fichier audio vide")
                except Exception:
                    with contextlib.suppress(OSError):
                        path.unlink()
                    raise
                return path

        tasks = [asyncio.ensure_future(one(chunk)) for chunk in chunks]
        delivered = 0
        for index, task in enumerate(tasks):
            try:
                path = await task
            except Exception:  # noqa: BLE001 - aucune exception ne doit sortir du fil
                if index == 0:
                    QMetaObject.invokeMethod(self, "_fail", Qt.QueuedConnection, Q_ARG(int, request), Q_ARG(
                        str, "Lecture vocale indisponible (connexion au service de voix impossible)."))
                    delivered = -1
                break  # Coupure en cours de route : on lit ce qui est déjà prêt.
            if path is None or request != self._request:
                if path is not None:
                    with contextlib.suppress(OSError):
                        path.unlink()
                break
            QMetaObject.invokeMethod(self, "_play", Qt.QueuedConnection, Q_ARG(int, request), Q_ARG(str, str(path)))
            delivered = index + 1
        for task in tasks[max(delivered, 0):]:  # Morceaux jamais livrés : les attendre puis les effacer.
            try:
                leftover = await task
            except Exception:  # noqa: BLE001, S112 - morceau en échec, rien à effacer
                continue
            if leftover is not None:
                with contextlib.suppress(OSError):
                    leftover.unlink()
        if delivered >= 0:
            QMetaObject.invokeMethod(self, "_done", Qt.QueuedConnection, Q_ARG(int, request))

    # --- Fil principal ----------------------------------------------------------
    @Slot(int, str)
    def _fail(self, request: int, message: str) -> None:
        if request != self._request:
            return
        self._pending = False
        self.error.emit(message)
        self.finished.emit()

    @Slot(int, str)
    def _play(self, request: int, filename: str) -> None:
        """Ajouter un morceau prêt à la file ; le jouer aussitôt si rien n’est en cours."""
        path = Path(filename)
        if request != self._request:  # Demande remplacée ou arrêtée entre-temps.
            with contextlib.suppress(OSError):
                path.unlink()
            return
        self._queue.append(path)
        if self._temp_file is None:
            self._play_next()
        else:
            self._preload()

    @Slot(int)
    def _done(self, request: int) -> None:
        if request != self._request:
            return
        self._synth_done = True
        if self._temp_file is None and not self._queue and self._spare_file is None and self._pending:
            self._pending = False
            self.finished.emit()

    def _make_player(self):
        if self._idle:  # Lecteur éteint par un fondu, déjà relié à ce lecteur vocal.
            return self._idle.pop()
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        output = QAudioOutput(self)
        player = QMediaPlayer(self)
        player.setAudioOutput(output)
        player.mediaStatusChanged.connect(lambda status, p=player: self._on_media_status(status, p))
        player.errorOccurred.connect(lambda *_a, p=player: self._on_error(p))
        return player, output

    def _preload(self) -> None:
        """Charger le prochain morceau dans le second lecteur pour l’enchaîner sans blanc."""
        if self._spare_file is not None or not self._queue or self._player is None:
            return
        if self._spare is None:
            self._spare, self._spare_output = self._make_player()
        self._spare_file = self._queue.pop(0)
        self._spare_output.setVolume(self._volume)
        self._spare.setSource(QUrl.fromLocalFile(str(self._spare_file.resolve())))

    def _drop_spare(self) -> None:
        if self._spare_file is not None:
            if self._spare is not None:
                self._spare.setSource(QUrl())
            with contextlib.suppress(OSError):
                self._spare_file.unlink()
        self._spare_file = None

    def _play_next(self) -> None:
        self._cleanup_temp()
        if self._spare_file is not None:  # Morceau déjà chargé : on échange les lecteurs.
            self._player, self._spare = self._spare, self._player
            self._output, self._spare_output = self._spare_output, self._output
            self._temp_file, self._spare_file = self._spare_file, None
            self._output.setVolume(self._volume)
            self._player.play()
            if self._spare is not None:
                self._spare.setSource(QUrl())
            self._preload()
            return
        if not self._queue:
            if self._synth_done and self._pending:
                self._pending = False
                self.finished.emit()
            return
        path = self._queue.pop(0)
        self._temp_file = path
        if self._player is None:
            self._player, self._output = self._make_player()
        self._output.setVolume(self._volume)
        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._player.play()
        self._preload()

    def _on_media_status(self, status, player=None) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if player is not None and player is not self._player:
            return  # Le lecteur de réserve ne fait que précharger.
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._play_next()

    def _on_error(self, player=None) -> None:
        if player is not None and player is not self._player and player is not self._spare:
            return  # Lecteur en fondu ou déjà retiré.
        if player is not None and player is not self._player:
            self._drop_spare()
            return
        self._player.setSource(QUrl())
        self.error.emit("Erreur de lecture audio.")
        self._play_next()

    def _cleanup_temp(self) -> None:
        if self._temp_file is not None:
            with contextlib.suppress(OSError):
                self._temp_file.unlink()
        self._temp_file = None
