"""Génère assets/themes/grimoire/page-parchment.jpg (vélin ivoire) pour la page de récit.

Script reproductible (graine fixe) ; requiert numpy et Pillow, uniquement pour régénérer l'asset.
Le bord sombre et le pli de reliure sont peints par IlluminatedPage : la texture reste neutre
pour pouvoir être étirée sur toute la page sans motif visible."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

W, H = 1024, 1024
rng = np.random.default_rng(1347)


def octave(scale):
    small = rng.random((max(2, H // scale), max(2, W // scale)))
    img = Image.fromarray((small * 255).astype('uint8')).resize((W, H), Image.BICUBIC)
    return np.asarray(img, dtype=float) / 255


# Marbrures douces du vélin.
mottle = sum(octave(s) * w for s, w in ((256, .4), (96, .3), (32, .18), (8, .08), (3, .04)))
mottle = (mottle - mottle.min()) / (mottle.max() - mottle.min())
# Fibres : bruit fin étiré horizontalement.
fib = rng.normal(0, 1, (H // 2, W // 16))
fib = np.asarray(Image.fromarray(((fib - fib.min()) / np.ptp(fib) * 255).astype('uint8'))
                 .resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(.6)), float) / 255
grain = rng.normal(0, 1, (H, W)) * .025
# Quelques taches de rousseur (foxing) très légères.
spots = np.zeros((H, W))
for _ in range(38):
    cx, cy, r = rng.integers(0, W), rng.integers(0, H), rng.uniform(4, 22)
    yy, xx = np.ogrid[:H, :W]
    spots += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * rng.uniform(.15, .5)
spots = np.clip(spots, 0, 1)

light = np.array([247, 236, 210], float)    # ivoire
dark = np.array([226, 204, 160], float)     # vélin ambré
fox = np.array([196, 160, 112], float)
t = np.clip(mottle * .8 + (fib - .5) * .18 + grain, 0, 1)[..., None]
rgb = light * (1 - t) + dark * t
rgb = rgb * (1 - spots[..., None] * .35) + fox * spots[..., None] * .35
out = Path(__file__).resolve().parents[1] / 'assets/themes/grimoire/page-parchment.jpg'
Image.fromarray(np.clip(rgb, 0, 255).astype('uint8')).save(out, quality=90, optimize=True)
print(out)
