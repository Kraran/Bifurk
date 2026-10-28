"""Préparer la musique de victoire (§400) à partir du MP3 fourni (FFmpeg requis).

Usage : python scripts/prepare_victory_music.py Achievement.mp3
« Achievement », Alexander Nakarada (CC BY 4.0, voir LICENCES-ET-REMERCIEMENTS.txt).
La source est vérifiée (SHA-256 de l’audio) puis : silence de tête retiré (1,25 s), traîne
finale arrêtée quand la réverbération s'éteint (115,4 s) avec un fondu de 0,8 s,
niveau abaissé de 2,1 dB pour égaler la musique d'accueil (−14 LUFS), pochette et
métadonnées retirées, OGG Vorbis stéréo 44,1 kHz qualité 4 (≈ 4,8 Mo → ≈ 1,8 Mo).
Le morceau entier forme la boucle : intro douce, thème, accord final, puis reprise."""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'assets/sounds/Achievement.ogg'
# Empreinte des trames audio, étiquette ID3 exclue (pochette et tags varient selon les copies).
AUDIO_SHA256 = 'cf95e00597bfe105bd041e0cb0a957255294de7ed67c4fd7446d5d23f0304bd8'
START, END, FADE, GAIN_DB = 1.25, 115.4, .8, -2.1


def audio_digest(data):
    if data[:3] == b'ID3':
        data = data[10 + (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9]):]
    return hashlib.sha256(data).hexdigest()


def prepare(source):
    source = Path(source)
    if audio_digest(source.read_bytes()) != AUDIO_SHA256:
        raise ValueError('Ce MP3 n’est pas la version créditée de « Achievement ».')
    length = END - START
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(START), '-to', str(END), '-i', str(source),
                    '-map', '0:a', '-af', f'volume={GAIN_DB}dB,afade=t=in:st=0:d=0.05,'
                                          f'afade=t=out:st={length - FADE:.2f}:d={FADE}',
                    '-ac', '2', '-ar', '44100', '-c:a', 'libvorbis', '-q:a', '4',
                    '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact',
                    str(TARGET)], check=True)
    return TARGET


if __name__ == '__main__':
    path = prepare(sys.argv[1])
    print(path, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
