"""Lecture vocale des paragraphes avec les voix neurales Microsoft Edge (edge-tts).

Utilise le même service gratuit que « Lire à haute voix » de Edge. Les voix sont
en ligne (connexion Internet requise). La lecture passe par QMediaPlayer pour
s’intégrer au reste de l’audio de Bifurk.

Voix françaises proposées (identifiants techniques) :
- fr-FR-RemyMultilingualNeural   (Rémy Multilingue, recommandé)
- fr-FR-VivienneMultilingualNeural (Vivienne Multilingue)
- fr-FR-DeniseNeural
- fr-FR-HenriNeural
- fr-FR-EloiseNeural
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

# Voix françaises disponibles via edge-tts (ordre d’affichage prévu dans les réglages).
FRENCH_VOICES = {
    "fr-FR-RemyMultilingualNeural": "Rémy Multilingue",
    "fr-FR-VivienneMultilingualNeural": "Vivienne Multilingue",
    "fr-FR-DeniseNeural": "Denise",
    "fr-FR-HenriNeural": "Henri",
    "fr-FR-EloiseNeural": "Eloise",
}
DEFAULT_VOICE = "fr-FR-RemyMultilingualNeural"


class ParagraphReader(QObject):
    """Génère et joue le texte d’un paragraphe avec une voix Edge.

    Émet `finished` à la fin naturelle ou après `stop()`. `error` en cas de
    problème réseau ou de génération.
    """
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._player = None
        self._output = None
        self._temp_file: Optional[Path] = None
        self._voice = DEFAULT_VOICE
        self._rate = "+0%"
        self._volume = 0.8
        self._task: Optional[asyncio.Task] = None

    def set_voice(self, voice_id: str) -> None:
        """Choisir une voix parmi FRENCH_VOICES."""
        if voice_id in FRENCH_VOICES:
            self._voice = voice_id

    def set_rate(self, percent: int) -> None:
        """Vitesse relative (-50 à +100). 0 = normal."""
        percent = max(-50, min(100, int(percent)))
        self._rate = f"{percent:+d}%"

    def set_volume(self, volume: float) -> None:
        """Volume 0.0–1.0."""
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._output is not None:
            self._output.setVolume(self._volume)

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def stop(self) -> None:
        """Arrêter la lecture en cours et nettoyer."""
        if self._task and not self._task.done():
            self._task.cancel()
        if self._player is not None:
            self._player.stop()
        self._cleanup_temp()
        self.finished.emit()

    def speak(self, text: str) -> None:
        """Lancer la génération + lecture du texte (asynchrone)."""
        text = (text or "").strip()
        if not text:
            self.finished.emit()
            return
        if QGuiApplication.platformName() in ("offscreen", "minimal"):
            self.error.emit("Lecture vocale indisponible en mode sans écran.")
            return
        self.stop()  # annuler une éventuelle lecture précédente
        self._task = asyncio.create_task(self._generate_and_play(text))

    async def _generate_and_play(self, text: str) -> None:
        try:
            import edge_tts
        except ImportError:
            self.error.emit("Le paquet edge-tts n’est pas installé.")
            return

        try:
            communicate = edge_tts.Communicate(text, self._voice, rate=self._rate)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                self._temp_file = Path(tmp.name)
            await communicate.save(str(self._temp_file))

            if not self._temp_file.exists() or self._temp_file.stat().st_size == 0:
                raise RuntimeError("Fichier audio vide.")

            self._play_file(self._temp_file)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"Échec de la génération vocale : {exc}")
            self._cleanup_temp()
            self.finished.emit()

    def _play_file(self, path: Path) -> None:
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

    @Slot()
    def _on_media_status(self, status) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._cleanup_temp()
            self.finished.emit()

    @Slot()
    def _on_error(self, *_args) -> None:
        self.error.emit("Erreur de lecture audio.")
        self._cleanup_temp()
        self.finished.emit()

    def _cleanup_temp(self) -> None:
        if self._temp_file and self._temp_file.exists():
            try:
                self._temp_file.unlink()
            except OSError:
                pass
        self._temp_file = None


def available_french_voices() -> dict[str, str]:
    """Retourner le dictionnaire id → libellé pour l’interface des réglages."""
    return dict(FRENCH_VOICES)
