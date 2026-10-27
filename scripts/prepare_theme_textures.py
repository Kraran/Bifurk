"""Préparer les textures recolorées des thèmes de grimoire (NumPy et Pillow, outil seulement).

Usage : python scripts/prepare_theme_textures.py [RACINE]
Pour chaque assets/themes/*/theme.json doté d'une section « recolor », recolore le
cuir (bandeau, fiche) et les parchemins du thème Standard avec les mêmes règles que
theme_palette (cuir -> teinte « leather », cire -> « seal », parchemin -> « page »,
fonds sombres -> « ground ») et écrit les JPEG dans le dossier du thème."""
import colorsys, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
THEMES = ROOT / 'assets/themes'


def hue(v):
    if isinstance(v, str):
        v = v.lstrip('#'); return colorsys.rgb_to_hsv(*(int(v[i:i+2], 16)/255 for i in (0, 2, 4)))[0]
    return (v / 360) % 1


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def rgb_to_hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1); d = mx - mn; m = d > 1e-6; dd = np.where(m, d, 1)
    rc, gc, bc = (mx - r) / dd, (mx - g) / dd, (mx - b) / dd
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2 + rc - bc, 4 + gc - rc))
    h = np.where(m, (h / 6) % 1, 0)
    s = np.where(mx > 0, d / np.where(mx > 0, mx, 1), 0)
    return h, s, mx


def hsv_to_rgb(h, s, v):
    i = np.floor(h * 6).astype(int) % 6; f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.zeros(h.shape + (3,))
    for k, (r, g, b) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
        sel = i == k; out[sel, 0], out[sel, 1], out[sel, 2] = r[sel], g[sel], b[sel]
    return out


def recolor(img, spec, role):
    a = np.asarray(img.convert('RGB')).astype(float) / 255
    h, s, v = rgb_to_hsv(a); deg = h * 360
    red = np.where(deg > 180, smooth(deg, 322, 338), 1 - smooth(deg, 18, 28)) * smooth(s, .18, .32)
    if role == 'leather':
        bright = np.zeros_like(v)
    else:
        local = np.asarray(Image.fromarray((v * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(4))) / 255
        bright = smooth(local, .30, .42)
    lh, ls, lv = hue(spec['leather'][0]), *spec['leather'][1:]
    sh, ss, sv = hue(spec['seal'][0]), *spec['seal'][1:]
    nh = np.where(bright > .5, sh, lh)
    recol = hsv_to_rgb(nh, np.clip(s * (ls * (1 - bright) + ss * bright), 0, 1),
                       np.clip(v * (lv * (1 - bright) + sv * bright), 0, 1))
    page = smooth(deg, 24, 32) * (1 - smooth(deg, 58, 66)) * (1 - smooth(s, .42, .55)) * smooth(v, .62, .75)
    ph, pmix, ps, pv = hue(spec['page'][0]), *spec['page'][1:]
    page_rgb = hsv_to_rgb(h * (1 - pmix) + ph * pmix, np.clip(s * ps, 0, 1), np.clip(v * pv, 0, 1))
    dark = (1 - smooth(v, .16, .26)) * (1 - red)
    gh, gs = hue(spec['ground'][0]), spec['ground'][1]
    dark_rgb = hsv_to_rgb(np.full_like(h, gh), np.clip(np.maximum(s, .25) * gs, 0, 1), v)
    out = a
    for w, t in ((red, recol), (page, page_rgb), (dark, dark_rgb)):
        out = out * (1 - w[..., None]) + t * w[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).round().astype('uint8'))


SOURCES = {'leather': (ROOT / 'assets/leather.jpg', 'leather.jpg', 'leather'),
           'sheet': (THEMES / 'grimoire/sheet-leather.png', 'sheet-leather.jpg', 'leather'),
           'parchment': (ROOT / 'assets/parchment.jpg', 'parchment.jpg', 'page'),
           'page': (THEMES / 'grimoire/page-parchment.jpg', 'page-parchment.jpg', 'page')}

for manifest in sorted(THEMES.glob('*/theme.json')):
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if 'recolor' not in data:
        continue
    for key, (source, name, role) in SOURCES.items():
        target = manifest.parent / name
        recolor(Image.open(source), data['recolor'], role).save(target, quality=90, optimize=True)
        print(data['id'], target.name, target.stat().st_size)
