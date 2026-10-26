"""Préparer la boucle d’ambiance de ville de La Cité des Voleurs (FFmpeg et NumPy requis).

Usage : python scripts/prepare_cite_ambience.py DOSSIER_DES_SOURCES
Le FLAC CC0 décrit dans assets/sounds/sources.json (« book_ambiences ») est
vérifié par SHA-256, filtré sous 120 Hz pour retirer le grondement, réduit en mono
PCM 16 bits à 22 050 Hz comme la caverne, puis bouclé sans couture par un fondu
à puissance constante de la fin dans le début. Le niveau RMS reprend celui de la
caverne, sous le même plafond de crête (27 500)."""
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


def prepare(folder):
    spec = json.loads((SOUNDS/'sources.json').read_text())['book_ambiences']['ambient_cite']
    source = Path(folder)/spec['archive']
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError(f"Source différente de la source créditée : {spec['archive']}")
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-af', 'highpass=f=120',
                          '-ac', '1', '-ar', str(RATE), '-f', 'f64le', '-'],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(raw, dtype='<f8')
    start, length, fade = (round(spec[key]*RATE) for key in ('start_seconds', 'loop_seconds', 'crossfade_seconds'))
    segment = samples[start:start+length+fade].copy()
    if len(segment) != length+fade:
        raise ValueError('Source trop courte pour la boucle demandée.')
    # La fin (après la boucle) se fond dans le début : le dernier échantillon
    # précède alors exactement la suite naturelle de l’enregistrement.
    ramp = np.linspace(0, np.pi/2, fade)
    loop = segment[:length]
    loop[:fade] = segment[length:]*np.cos(ramp)+segment[:fade]*np.sin(ramp)
    loop -= loop.mean()
    gain = min(10**(spec['rms_dbfs']/20)/np.sqrt(np.mean(loop**2)), 27500/32768/abs(loop).max())
    loop *= gain
    target = SOUNDS/'ambient_cite.wav'
    with wave.open(str(target), 'wb') as stream:
        stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(np.rint(loop*32767).astype('<i2').tobytes())
    print(json.dumps({'seconds': len(loop)/RATE, 'bytes': target.stat().st_size,
                      'rms_dbfs': float(20*np.log10(np.sqrt(np.mean(loop**2)))),
                      'peak_dbfs': float(20*np.log10(abs(loop).max())),
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    prepare(sys.argv[1])
