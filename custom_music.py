"""Musique personnelle : lecture du dossier musique_perso et tirage sans remise.

Le dossier est lu à plat (pas de sous-dossiers) ; seules les extensions audio que
le moteur FFmpeg de Qt Multimedia décode sous Windows sont retenues. Le tirage
utilise son propre générateur : il ne consomme jamais le hasard des dés.
"""
import random
from pathlib import Path

# Formats décodés par le moteur FFmpeg de Qt Multimedia (Qt 6.5+), Windows compris.
AUDIO_EXTENSIONS = frozenset({'.mp3', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.wav', '.wma'})


def scan_tracks(folder):
    """Lister les morceaux lisibles par extension, triés ; [] si le dossier manque."""
    try:
        entries = list(Path(folder).iterdir())
    except OSError:
        return []
    return sorted((path for path in entries
                   if path.suffix.lower() in AUDIO_EXTENSIONS and not path.name.startswith('.')
                   and path.is_file()), key=lambda path: path.name.casefold())


class ShuffleBag:
    """Tirer chaque morceau une fois avant de remélanger, sans doublon à la jointure."""
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.bag = []
        self.last = None

    def reset(self):
        """Oublier le tirage en cours (option rebasculée, dossier relu)."""
        self.bag = []

    def next(self, refill):
        """Rendre le morceau suivant ; refill() fournit la liste lorsque le sac est vide.

        refill est appelé à chaque tour complet : les fichiers ajoutés ou retirés
        entre-temps sont pris en compte. None si aucun morceau n'est disponible."""
        if not self.bag:
            tracks = list(dict.fromkeys(refill()))
            if not tracks:
                return None
            self.rng.shuffle(tracks)
            # Le prochain tiré (fin de liste) ne doit pas rejouer le dernier entendu.
            if len(tracks) > 1 and tracks[-1] == self.last:
                swap = self.rng.randrange(len(tracks) - 1)
                tracks[-1], tracks[swap] = tracks[swap], tracks[-1]
            self.bag = tracks
        self.last = self.bag.pop()
        return self.last
