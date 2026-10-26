"""Lecture vocale des paragraphes avec les voix neurales Microsoft Edge (edge-tts).

Même service que « Lire à haute voix » d’Edge : une connexion Internet est requise.
La synthèse tourne dans un fil secondaire (``asyncio.run``) vers un MP3 temporaire ;
la lecture est confiée au fil principal par ``QMetaObject.invokeMethod`` et passe par
QMediaPlayer. Toute erreur (réseau absent, paquet manquant) reste silencieuse pour
l’interface : seul le signal ``error`` porte un message court.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QUrl, Signal, Slot

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


class ParagraphReader(QObject):
    """Synthétise puis lit un paragraphe ; un nouvel appel arrête le précédent."""

    started = Signal()
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player = None
        self._output = None
        self._voice = DEFAULT_VOICE
        self._rate = "+0%"
        self._volume = 0.8
        self._pending = False
        self._request = 0  # Numéro de la demande en cours ; les synthèses périmées sont ignorées.
        self._temp_file: Path | None = None

    @property
    def voice(self) -> str:
        return self._voice

    def set_voice(self, voice_id: str) -> None:
        if voice_id and (voice_id in _voice_cache or voice_id.startswith("fr-")):
            self._voice = voice_id

    def set_rate(self, percent: int) -> None:
        percent = max(-50, min(100, int(percent)))
        self._rate = f"{percent:+d}%"

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._output is not None:
            self._output.setVolume(self._volume)

    def is_busy(self) -> bool:
        """Synthèse en attente ou lecture en cours."""
        return self._pending or self.is_playing()

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def stop(self) -> None:
        """Arrêter la lecture et rendre caduque toute synthèse en cours."""
        self._request += 1
        was_busy = self._pending or self.is_playing()
        self._pending = False
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
        self._cleanup_temp()
        if was_busy:
            self.finished.emit()

    def speak(self, text: str) -> None:
        self.stop()
        text = prepare_speech_text(text)
        if not text:
            return
        request, voice, rate = self._request, self._voice, self._rate
        self._pending = True
        self.started.emit()
        threading.Thread(target=self._synthesize, args=(request, text, voice, rate), daemon=True).start()

    # --- Fil secondaire ---------------------------------------------------------
    def _synthesize(self, request: int, text: str, voice: str, rate: str) -> None:
        path = None
        try:
            import edge_tts
            with tempfile.NamedTemporaryFile(prefix="bifurk-tts-", suffix=".mp3", delete=False) as tmp:
                path = Path(tmp.name)
            asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(path)))
            if path.stat().st_size == 0:
                raise RuntimeError("fichier audio vide")
        except Exception as exc:  # noqa: BLE001 - aucune exception ne doit sortir du fil
            if path is not None:
                with contextlib.suppress(OSError):
                    path.unlink()
            message = "Lecture vocale indisponible (paquet edge-tts absent)." if isinstance(exc, ImportError) \
                else "Lecture vocale indisponible (connexion au service de voix impossible)."
            QMetaObject.invokeMethod(self, "_fail", Qt.QueuedConnection, Q_ARG(int, request), Q_ARG(str, message))
            return
        QMetaObject.invokeMethod(self, "_play", Qt.QueuedConnection, Q_ARG(int, request), Q_ARG(str, str(path)))

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
        path = Path(filename)
        if request != self._request:  # Demande remplacée ou arrêtée entre-temps.
            with contextlib.suppress(OSError):
                path.unlink()
            return
        self._pending = False
        self._temp_file = path
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        if self._player is None:
            self._output = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._output)
            self._player.mediaStatusChanged.connect(self._on_media_status)
            self._player.errorOccurred.connect(self._on_error)
        self._output.setVolume(self._volume)
        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._player.play()

    def _on_media_status(self, status) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._player.setSource(QUrl())
            self._cleanup_temp()
            self.finished.emit()

    def _on_error(self, *_args) -> None:
        self._player.setSource(QUrl())
        self._cleanup_temp()
        self.error.emit("Erreur de lecture audio.")
        self.finished.emit()

    def _cleanup_temp(self) -> None:
        if self._temp_file is not None:
            with contextlib.suppress(OSError):
                self._temp_file.unlink()
        self._temp_file = None
