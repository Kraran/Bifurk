"""Préparer les annonces fournies par l’utilisateur (NumPy requis pour cet outil seul).

Usage : python scripts/prepare_book_sounds.py DOSSIER_DES_SOURCES
Les originaux restent intacts ; les annonces sont distinctes des effets CC0.
Seules les sources présentes dans le dossier sont préparées ; les autres
annonces gardent leur fichier et leur entrée du manifeste.
"""
import hashlib
import json
from pathlib import Path
import sys
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {'book_foret': 'La foret.wav', 'book_sorcier': 'Le Sorcier.wav',
           'book_cite': 'La Cite des Voleurs.wav'}


def prepare(folder):
    manifest = ROOT/'assets/sounds/book_sounds.json'
    report = json.loads(manifest.read_text(encoding='utf-8'))['sounds'] if manifest.is_file() else {}
    present = {name: filename for name, filename in SOURCES.items() if (Path(folder)/filename).is_file()}
    if not present:
        raise ValueError('Aucune source attendue dans le dossier.')
    for name, filename in present.items():
        source = Path(folder)/filename
        with wave.open(str(source)) as stream:
            if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
                raise ValueError('Source attendue : WAV mono PCM 16 bits.')
            rate = stream.getframerate()
            samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(float)/32768
        duration = len(samples)/rate
        samples -= samples.mean()  # Supprimer le décalage continu.
        # Détecter les silences par fenêtres de 10 ms ; conserver les respirations.
        window = max(1, round(rate*.01))
        levels = np.array([np.sqrt(np.mean(samples[i:i+window]**2))
                           for i in range(0, len(samples), window)])
        active = np.flatnonzero(levels > max(levels.max()*.025, .001))
        if not len(active):
            raise ValueError('Source silencieuse.')
        samples = samples[max(0, active[0]*window-round(rate*.06)):
                          min(len(samples), (active[-1]+1)*window+round(rate*.12))]
        # Interpolation sinc fenêtrée : conversion 16 kHz -> 22,05 kHz compatible PCM.
        positions = np.arange(round(len(samples)*22050/rate))*rate/22050
        indices = np.floor(positions).astype(int)[:, None]+np.arange(-16, 17)
        distances = positions[:, None]-indices
        weights = np.sinc(distances)*np.where(abs(distances)<17, .5+.5*np.cos(np.pi*distances/17), 0)
        weights /= weights.sum(axis=1)[:, None]
        samples = (samples[np.clip(indices, 0, len(samples)-1)]*weights).sum(axis=1)
        # Même niveau RMS, avec marge de crête de 2 dB, sans compression destructive.
        gain = min(10**(-21/20)/np.sqrt(np.mean(samples**2)),
                   10**(-2/20)/max(abs(samples)))
        samples *= gain
        attack, release = round(22050*.005), round(22050*.02)
        samples[:attack] *= np.linspace(0, 1, attack)
        samples[-release:] *= np.linspace(1, 0, release)
        target = ROOT/'assets/sounds'/f'{name}.wav'
        with wave.open(str(target), 'wb') as stream:
            stream.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            stream.writeframes(np.rint(samples*32767).astype('<i2').tobytes())
        report[name] = {'source': filename, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                        'source_seconds': duration, 'output_seconds': len(samples)/22050,
                        'gain_db': float(20*np.log10(gain)), 'peak_dbfs': float(20*np.log10(max(abs(samples)))),
                        'rms_dbfs': float(20*np.log10(np.sqrt(np.mean(samples**2)))), 'bytes': target.stat().st_size}
    manifest.write_text(
        json.dumps({'provenance':'Fichiers fournis par l’utilisateur ; non couverts par les licences CC0 des autres effets.',
                    'format':'WAV mono PCM 16 bits 22050 Hz',
                    'sounds':{name: report[name] for name in SOURCES if name in report}}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({name: report[name] for name in present}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    prepare(sys.argv[1])
