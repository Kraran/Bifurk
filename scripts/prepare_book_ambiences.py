"""Préparer les boucles d’ambiance propres aux livres (FFmpeg et NumPy requis).

Usage : python scripts/prepare_book_ambiences.py DOSSIER_DES_SOURCES [NOM ...]
Chaque enregistrement CC0 décrit dans assets/sounds/sources.json (« book_ambiences »)
est vérifié par SHA-256, filtré par FFmpeg (par défaut un passe-haut à 120 Hz contre
le grondement), réduit en mono PCM 16 bits à 22 050 Hz comme la caverne, puis bouclé
sans couture par un fondu à puissance constante de la fin dans le début. Le niveau
RMS visé est celui de l’entrée, sous le plafond de crête des effets (27 500).
La boucle est livrée en OGG Vorbis (encode_loop) : Vorbis conserve le nombre exact
d’échantillons, le raccord reste donc sans couture après décodage.
Sans NOM, toutes les boucles sont reconstruites."""
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOUNDS = ROOT/'assets/sounds'
RATE = 22050
DEFAULT_FILTERS = 'highpass=f=120'
VORBIS_QUALITY = '4'  # ≈ 10 fois plus léger que le WAV, sans perte audible à ce volume.


def encode_loop(wav, target):
    """Encoder un WAV préparé en OGG Vorbis reproductible, puis effacer le WAV intermédiaire."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-c:a', 'libvorbis',
                    '-q:a', VORBIS_QUALITY, '-map_metadata', '-1', '-fflags', '+bitexact',
                    '-flags:a', '+bitexact', str(target)], check=True)
    Path(wav).unlink()


def prepare_one(folder, name, spec):
    source = Path(folder)/spec['archive']
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError(f"Source différente de la source créditée : {spec['archive']}")
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-af', spec.get('filters', DEFAULT_FILTERS),
                          '-ac', '1', '-ar', str(RATE), '-f', 'f64le', '-'],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(raw, dtype='<f8')
    start, length, fade = (round(spec[key]*RATE) for key in ('start_seconds', 'loop_seconds', 'crossfade_seconds'))
    segment = samples[start:start+length+fade].copy()
    if len(segment) != length+fade:
        raise ValueError(f'Source trop courte pour la boucle demandée : {name}')
    # La fin (après la boucle) se fond dans le début : le dernier échantillon
    # précède alors exactement la suite naturelle de l’enregistrement.
    ramp = np.linspace(0, np.pi/2, fade)
    loop = segment[:length]
    loop[:fade] = segment[length:]*np.cos(ramp)+segment[:fade]*np.sin(ramp)
    loop -= loop.mean()
    gain = min(10**(spec['rms_dbfs']/20)/np.sqrt(np.mean(loop**2)), 27500/32768/abs(loop).max())
    loop *= gain
    wav, target = SOUNDS/f'{name}.wav', SOUNDS/f'{name}.ogg'
    with wave.open(str(wav), 'wb') as stream:
        stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(np.rint(loop*32767).astype('<i2').tobytes())
    encode_loop(wav, target)
    return {'file': target.name, 'seconds': len(loop)/RATE, 'bytes': target.stat().st_size,
            'rms_dbfs': round(float(20*np.log10(np.sqrt(np.mean(loop**2)))), 2),
            'peak_dbfs': round(float(20*np.log10(abs(loop).max())), 2),
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def prepare(folder, names=()):
    specs = json.loads((SOUNDS/'sources.json').read_text())['book_ambiences']
    unknown = set(names)-set(specs)
    if unknown:
        raise ValueError(f"Ambiance inconnue : {', '.join(sorted(unknown))}")
    return [prepare_one(folder, name, specs[name]) for name in (names or specs)]


if __name__ == '__main__':
    print(json.dumps(prepare(sys.argv[1], sys.argv[2:]), indent=2))
