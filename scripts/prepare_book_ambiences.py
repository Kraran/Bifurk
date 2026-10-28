"""Préparer les boucles d’ambiance et les sons ponctuels des scènes (FFmpeg et NumPy requis).

Usage : python scripts/prepare_book_ambiences.py DOSSIER_DES_SOURCES [NOM ...]
Trois sections de assets/sounds/sources.json sont préparées :

- « book_ambiences » : la boucle propre à chaque livre (ville, forêt) ;
- « scene_ambiences » : les boucles des scènes (souterrain, rivière, taverne…),
  éventuellement superposées à d’autres enregistrements (« layers ») ;
- « scene_spots » : les sons ponctuels joués au hasard pendant une scène (goutte,
  hibou, grenouille), découpés dans un enregistrement : « nom.wav », « nom_2.wav »…

Les enregistrements des scènes sont décrits une seule fois dans « scene_sources »
(page, licence, empreinte). Chaque fichier source est vérifié par SHA-256, filtré par
FFmpeg (par défaut un passe-haut à 120 Hz contre le grondement) et réduit en mono
PCM 16 bits à 22 050 Hz comme la caverne. Une boucle est rendue sans couture par un
fondu à puissance constante de la fin dans le début, au niveau RMS indiqué, sous le
plafond de crête des effets (27 500), puis livrée en OGG Vorbis (encode_loop) : Vorbis
conserve le nombre exact d’échantillons, le raccord reste donc sans couture après
décodage. Un son ponctuel est livré en WAV, crête normalisée, entrée et sortie en fondu.
Sans NOM, tout est reconstruit."""
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
PEAK_LIMIT = 27500/32768
LOOP_SECTIONS = ('book_ambiences', 'scene_ambiences')


def encode_loop(wav, target):
    """Encoder un WAV préparé en OGG Vorbis reproductible, puis effacer le WAV intermédiaire."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-c:a', 'libvorbis',
                    '-q:a', VORBIS_QUALITY, '-map_metadata', '-1', '-fflags', '+bitexact',
                    '-flags:a', '+bitexact', str(target)], check=True)
    Path(wav).unlink()


def decode(folder, archive, sha256, filters):
    """Vérifier l’empreinte d’un enregistrement puis le décoder en mono flottant à 22 050 Hz."""
    source = Path(folder)/archive
    if hashlib.sha256(source.read_bytes()).hexdigest() != sha256:
        raise ValueError(f'Source différente de la source créditée : {archive}')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-af', filters or DEFAULT_FILTERS,
                          '-ac', '1', '-ar', str(RATE), '-f', 'f64le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype='<f8')


def excerpt(samples, start_seconds, frames, name):
    """Extraire un passage exact ; refuser un enregistrement trop court."""
    start = round(start_seconds*RATE)
    segment = samples[start:start+frames].copy()
    if len(segment) != frames:
        raise ValueError(f'Source trop courte pour la boucle demandée : {name}')
    return segment


def rms(samples):
    return float(np.sqrt(np.mean(samples**2)))


def write_wav(path, samples):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(np.rint(samples*32767).astype('<i2').tobytes())


def describe(path, samples):
    return {'file': path.name, 'seconds': len(samples)/RATE, 'bytes': path.stat().st_size,
            'rms_dbfs': round(20*np.log10(rms(samples)), 2),
            'peak_dbfs': round(float(20*np.log10(abs(samples).max())), 2),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare_one(folder, name, spec, sources=None):
    """Préparer une boucle : extrait principal, couches éventuelles, raccord puis niveau."""
    def origin(entry):
        # Les boucles de livre portent leur source ; celles des scènes renvoient à scene_sources.
        known = (sources or {}).get(entry['archive'], entry)
        return entry['archive'], entry.get('sha256', known.get('sha256'))

    length, fade = (round(spec[key]*RATE) for key in ('loop_seconds', 'crossfade_seconds'))
    segment = excerpt(decode(folder, *origin(spec), spec.get('filters')),
                      spec['start_seconds'], length+fade, name)
    level = rms(segment)
    for layer in spec.get('layers', ()):
        # Chaque couche est posée à un niveau relatif à l’extrait principal.
        extra = excerpt(decode(folder, *origin(layer), layer.get('filters')),
                        layer['start_seconds'], length+fade, name)
        segment += extra*(level*10**(layer['relative_db']/20)/rms(extra))
    # La fin (après la boucle) se fond dans le début : le dernier échantillon
    # précède alors exactement la suite naturelle de l’enregistrement.
    ramp = np.linspace(0, np.pi/2, fade)
    loop = segment[:length]
    loop[:fade] = segment[length:]*np.cos(ramp)+segment[:fade]*np.sin(ramp)
    loop -= loop.mean()
    loop *= min(10**(spec['rms_dbfs']/20)/rms(loop), PEAK_LIMIT/abs(loop).max())
    wav, target = SOUNDS/f'{name}.wav', SOUNDS/f'{name}.ogg'
    write_wav(wav, loop)
    encode_loop(wav, target)
    return describe(target, loop)


def prepare_spot(folder, name, spec, sources):
    """Découper les sons ponctuels d’une scène : « nom.wav », puis « nom_2.wav »…"""
    results = []
    fade_in, fade_out = (round(spec[key]*RATE) for key in ('fade_in_seconds', 'fade_out_seconds'))
    for index, cut in enumerate(spec['cuts'], start=1):
        source = sources[cut['archive']]
        samples = excerpt(decode(folder, cut['archive'], source['sha256'], spec.get('filters')),
                          cut['start_seconds'], round(cut['seconds']*RATE), name)
        samples -= samples.mean()
        samples[:fade_in] *= np.linspace(0, 1, fade_in)
        samples[-fade_out:] *= np.linspace(1, 0, fade_out)**2
        samples *= min(10**(spec['peak_dbfs']/20), PEAK_LIMIT)/abs(samples).max()
        path = SOUNDS/(f'{name}.wav' if index == 1 else f'{name}_{index}.wav')
        write_wav(path, samples)
        results.append(describe(path, samples))
    return results


def prepare(folder, names=()):
    manifest = json.loads((SOUNDS/'sources.json').read_text(encoding='utf-8'))
    sources = manifest.get('scene_sources', {})
    loops = {name: spec for section in LOOP_SECTIONS for name, spec in manifest.get(section, {}).items()}
    spots = manifest.get('scene_spots', {})
    unknown = set(names)-set(loops)-set(spots)
    if unknown:
        raise ValueError(f"Ambiance inconnue : {', '.join(sorted(unknown))}")
    results = [prepare_one(folder, name, spec, sources)
               for name, spec in loops.items() if not names or name in names]
    for name, spec in spots.items():
        if not names or name in names:
            results.extend(prepare_spot(folder, name, spec, sources))
    return results


if __name__ == '__main__':
    print(json.dumps(prepare(sys.argv[1], sys.argv[2:]), indent=2))
