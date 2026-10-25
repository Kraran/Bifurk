"""Préparation reproductible des assets CC0 ; FFmpeg requis seulement pour cet outil.

Usage : python scripts/prepare_sounds.py /chemin/vers/les/archives
Les archives sont téléchargées séparément, puis vérifiées avec les SHA-256 de
assets/sounds/sources.json. Extraction temporaire, conversion mono PCM 16 bits,
normalisation et retrait de l'amorce faible précèdent l'écriture des WAV livrés.
Lancer cet outil modifie assets/sounds ; conserver licences et crédits des sources."""
import array
import json
import math
import hashlib
import subprocess
import sys
import tempfile
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/sounds'


def normalize(path, trim_attack=False):
    """Normaliser le pic à 27500 et, si demandé, retirer l’amorce faible détectée par RMS.

    Préserver les paramètres WAV ; gérer explicitement le boutisme des entiers
    16 bits. Le retrait conserve 10 ms d’attaque pour ne pas tronquer le son de page."""
    with wave.open(str(path), 'rb') as f:
        params = f.getparams()
        samples = array.array('h', f.readframes(f.getnframes()))
    if sys.byteorder != 'little': samples.byteswap()
    peak = max(map(abs, samples)) or 1
    if trim_attack:
        # Fenêtre de 5 ms comptée en trames : les échantillons sont entrelacés par
        # canal, et un multiple de nchannels garde chaque coupe alignée sur une trame.
        window = max(1, int(params.framerate * .005)) * params.nchannels
        for index in range(0, len(samples)-window, window):
            rms = math.sqrt(sum(v*v for v in samples[index:index+window]) / window)
            if rms >= peak * .025:
                # Garder 10 ms avant l'attaque et couper le faible bruit de manipulation qui la précède.
                samples = samples[max(0, index-window*2):]
                break
    samples = array.array('h', (round(v * 27500 / peak) for v in samples))
    if sys.byteorder != 'little': samples.byteswap()
    with wave.open(str(path), 'wb') as f:
        f.setparams(params); f.writeframes(samples.tobytes())


def prepare(folder):
    """Vérifier les archives créditées puis reconstruire chaque WAV du manifeste avec FFmpeg.

    Les intermédiaires sont temporaires. L’ambiance reste à 22,05 kHz ; les effets
    sont à 44,1 kHz, avec concaténation ou changement de hauteur si spécifié ici."""
    manifest = json.loads((OUT/'sources.json').read_text())
    for pack in manifest['packs'].values():
        if hashlib.sha256((folder/pack['archive']).read_bytes()).hexdigest() != pack['sha256']:
            raise ValueError(f"Archive différente de la source créditée : {pack['archive']}")
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        for name, spec in manifest['effects'].items():
            inputs = []
            for index, member in enumerate(spec['files']):
                pack = manifest['packs'][spec['pack']]
                if pack['archive'].endswith('.zip'):
                    with zipfile.ZipFile(folder/pack['archive']) as archive:
                        data = archive.read(member)
                else:
                    data = (folder/pack['archive']).read_bytes()
                path = temporary/(str(index)+Path(member).suffix)
                path.write_bytes(data)
                inputs += ['-i', str(path)]
            command = ['ffmpeg','-v','error','-y',*inputs]
            if len(spec['files']) > 1:
                command += ['-filter_complex','[0:a][1:a]concat=n=2:v=0:a=1[out]','-map','[out]']
            filters = []
            if name != 'ambient':
                filters += ['silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.003']
            if name == 'death': filters += ['asetrate=33075','aresample=44100']
            if filters:
                if len(spec['files']) > 1:
                    position = command.index('-filter_complex') + 1
                    command[position] = command[position].replace('[out]', ',' + ','.join(filters) + '[out]')
                else:
                    command += ['-af', ','.join(filters)]
            command += ['-ac','1','-ar','22050' if name=='ambient' else '44100',
                        '-c:a','pcm_s16le',str(OUT/f'{name}.wav')]
            subprocess.run(command, check=True)
            normalize(OUT/f'{name}.wav', trim_attack=name == 'page')


if __name__ == '__main__':
    prepare(Path(sys.argv[1]))
