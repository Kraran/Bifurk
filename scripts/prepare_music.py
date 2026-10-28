"""Préparer les musiques de victoire et de mort à partir des MP3 fournis (FFmpeg requis).

Usage : python scripts/prepare_music.py Achievement.mp3 Towards_the_Horizon.mp3
Morceaux d'Alexander Nakarada sous CC BY 4.0 (voir LICENCES-ET-REMERCIEMENTS.txt) :
- « Achievement » → assets/sounds/Achievement.ogg, boucle de la victoire (§400) ;
- « Towards the Horizon » → assets/sounds/TowardsTheHorizon.ogg, boucle de la mort du héros.
Chaque source est reconnue par l'empreinte SHA-256 de son audio (étiquette ID3 exclue :
pochette et tags varient selon les copies), puis : silence de tête retiré, traîne finale
arrêtée quand la réverbération s'éteint avec un fondu de 0,8 s, niveau aligné sur la
musique d'accueil (−14 LUFS), pochette et métadonnées retirées, OGG Vorbis stéréo
44,1 kHz qualité 4. Le morceau entier forme la boucle."""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FADE = .8
# Empreinte de l'audio -> (fichier produit, début, fin, gain en dB, titre).
TRACKS = {
    'cf95e00597bfe105bd041e0cb0a957255294de7ed67c4fd7446d5d23f0304bd8':
        ('assets/sounds/Achievement.ogg', 1.25, 115.4, -2.1, 'Achievement'),         # −12,0 → −14,1 LUFS
    '0e290b69ed978ef18f3913a1dd1850340ada201cadbc1a90ac7bd357447c1b99':
        ('assets/sounds/TowardsTheHorizon.ogg', 1.05, 224.0, -2.4, 'Towards the Horizon'),  # −11,7 LUFS
}


def audio_digest(data):
    if data[:3] == b'ID3':
        data = data[10 + (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9]):]
    return hashlib.sha256(data).hexdigest()


def prepare(source):
    source = Path(source)
    track = TRACKS.get(audio_digest(source.read_bytes()))
    if track is None:
        raise ValueError(f'{source.name} n’est pas une des versions créditées.')
    target, start, end, gain, _title = track
    target = ROOT / target
    length = end - start
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-to', str(end), '-i', str(source),
                    '-map', '0:a', '-af', f'volume={gain}dB,afade=t=in:st=0:d=0.05,'
                                          f'afade=t=out:st={length - FADE:.2f}:d={FADE}',
                    '-ac', '2', '-ar', '44100', '-c:a', 'libvorbis', '-q:a', '4',
                    '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact',
                    str(target)], check=True)
    return target


if __name__ == '__main__':
    for argument in sys.argv[1:]:
        path = prepare(argument)
        print(path, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
