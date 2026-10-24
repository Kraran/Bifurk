"""Génère assets/themes/grimoire/sheet-leather.png (cuir bordeaux grainé) pour la fiche.

Script reproductible (graine fixe) ; requiert numpy et Pillow, uniquement pour régénérer l'asset."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

W, H = 512, 1024
rng = np.random.default_rng(1982)

def octave(scale):
    small = rng.random((max(2, H // scale), max(2, W // scale)))
    img = Image.fromarray((small * 255).astype('uint8')).resize((W, H), Image.BICUBIC)
    return np.asarray(img, dtype=float) / 255

noise = sum(octave(s) * w for s, w in ((128, .35), (48, .3), (16, .2), (5, .1), (2, .05)))
noise = (noise - noise.min()) / (noise.max() - noise.min())
# Plis du cuir : bruit étiré puis seuillage doux.
crease = np.asarray(Image.fromarray((octave(24) * 255).astype('uint8')).filter(ImageFilter.FIND_EDGES), float) / 255
grain = rng.normal(0, 1, (H, W)) * .035
base = np.array([62, 30, 27], float)      # bordeaux brun
light = np.array([96, 50, 38], float)
t = np.clip(noise * .85 + grain - crease * .35, 0, 1)[..., None]
rgb = base * (1 - t) + light * t
out = Path(__file__).resolve().parents[1] / 'assets/themes/grimoire/sheet-leather.png'
Image.fromarray(np.clip(rgb, 0, 255).astype('uint8')).save(out, optimize=True)
print(out)
