"""Recoloration des thèmes de grimoire : une teinte de cuir, une de cire, un parchemin.

Les thèmes de livre (Sorcier, Forêt, Cité) dérivent du thème Standard par une
transformation de couleur déclarée dans leur manifeste (« recolor ») :

- famille cramoisie / cuir rouge (teintes 322°–28°) : les rouges profonds (cire,
  rubriques, rubans) prennent la teinte « seal », les bruns (cuir, encres sombres)
  la teinte « leather » ; saturation et luminosité sont mises à l'échelle ;
- parchemin (teintes 24°–66°, peu saturées, claires) : teinte, saturation et
  luminosité ajustées par « page » ;
- fonds presque noirs : légère teinte « ground ».

Les ors, aciers, bleus des liens et couleurs sémantiques (écus H/E/C, objets) ne
sont pas touchés. Les mêmes règles ont servi à préparer les textures livrées dans
chaque dossier de thème : peintures QPainter, QSS et images restent accordées.
Le thème Standard n'a pas de « recolor » : tint() rend alors la couleur d'origine.
"""
import colorsys
import re
import sys

from PySide6.QtGui import QColor, QPixmap, QTransform

# Constantes de couleur de module retintées à chaque changement de thème. Les écus
# (StatMedallion.TINTS) et les dessins d'objets n'en font pas partie.
CHROME_MODULES = ('adventurer_sheet', 'grimoire_chrome', 'grimoire_ui', 'carnet',
                  'loading_progress', 'grimoire_modules.cite.sheet')
CHROME_NAMES = frozenset({'GOLD', 'GOLD_LIGHT', 'GOLD_DARK', 'BORDEAUX', 'BORDEAUX_DARK',
                          'IVORY', 'INK', 'RUBRIC', 'PAGE_INK', 'BRONZE', 'OUTLINE'})

_spec = None          # Spécification « recolor » du thème actif, ou None (Standard).
_assets = {}          # Textures du thème actif : clé -> chemin.
_colors = {}          # Cache rgb -> rgb transformé.
_pixmaps = {}         # Cache (clé, rotation) -> QPixmap.
_originals = {}       # (module, nom) -> QColor d'origine.


def _smooth(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _hue(value):
    """Teinte 0–1 depuis '#rrggbb' ou un nombre de degrés."""
    if isinstance(value, str):
        color = QColor(value)
        return colorsys.rgb_to_hsv(color.redF(), color.greenF(), color.blueF())[0]
    return (float(value) / 360) % 1


def parse_spec(raw):
    """Valider la section « recolor » d'un manifeste ; None si absente."""
    if raw is None:
        return None
    leather, seal, page, ground = raw['leather'], raw['seal'], raw['page'], raw['ground']
    return {'leather': (_hue(leather[0]), float(leather[1]), float(leather[2])),
            'seal': (_hue(seal[0]), float(seal[1]), float(seal[2])),
            'page': (_hue(page[0]), float(page[1]), float(page[2]), float(page[3])),
            'ground': (_hue(ground[0]), float(ground[1]))}


def map_rgb(r, g, b, spec):
    """Transformer une couleur (composantes 0–1) selon une spécification de thème."""
    if spec is None:
        return r, g, b
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    deg = h * 360
    red = (_smooth(deg, 322, 338) if deg > 180 else 1 - _smooth(deg, 18, 28)) * _smooth(s, .18, .32)
    # Rouges francs (cire, rubriques) : teinte de sceau ; bruns rouges : teinte de cuir.
    crimson = deg >= 325 or deg <= 12
    th, ss, vs = spec['seal'] if crimson else spec['leather']
    mapped = colorsys.hsv_to_rgb(th, min(1, s * ss), min(1, v * vs))
    page = (_smooth(deg, 24, 32) * (1 - _smooth(deg, 58, 66)) * (1 - _smooth(s, .42, .55))
            * _smooth(v, .62, .75))
    ph, pmix, ps, pv = spec['page']
    page_rgb = colorsys.hsv_to_rgb(h * (1 - pmix) + ph * pmix, min(1, s * ps), min(1, v * pv))
    dark = (1 - _smooth(v, .16, .26)) * (1 - red)
    gh, gs = spec['ground']
    dark_rgb = colorsys.hsv_to_rgb(gh, min(1, max(s, .25) * gs), v)
    out = [r, g, b]
    for weight, target in ((red, mapped), (page, page_rgb), (dark, dark_rgb)):
        out = [o * (1 - weight) + t * weight for o, t in zip(out, target)]
    return tuple(min(1.0, max(0.0, c)) for c in out)


def tint(color, spec=False):
    """QColor accordé au thème actif (ou à `spec`), alpha conservé."""
    color = QColor(color)
    spec = _spec if spec is False else spec
    if spec is None:
        return color
    key = (color.rgb(), id(spec))
    if key not in _colors:
        _colors[key] = map_rgb(color.redF(), color.greenF(), color.blueF(), spec)
    r, g, b = _colors[key]
    result = QColor.fromRgbF(r, g, b)
    result.setAlpha(color.alpha())
    return result


def tint_hex(value, spec=False):
    """Version texte de tint() pour le HTML et les feuilles de style."""
    return tint(value, spec).name()


_CSS_HEX = re.compile(r'#[0-9a-fA-F]{6}\b')
_CSS_RGB = re.compile(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)')


def tint_css(text, spec=False):
    """Accorder les couleurs #rrggbb et rgb()/rgba() d'une feuille de style."""
    spec = _spec if spec is False else spec
    if spec is None:
        return text

    def rgb(match):
        color = tint(QColor(int(match[1]), int(match[2]), int(match[3])), spec)
        if match[4] is None:
            return f'rgb({color.red()}, {color.green()}, {color.blue()})'
        return f'rgba({color.red()}, {color.green()}, {color.blue()}, {match[4]})'
    text = _CSS_HEX.sub(lambda m: tint_hex(m.group(0), spec), text)
    return _CSS_RGB.sub(rgb, text)


def pixmap(key, fallback, rotate=0):
    """Texture du thème actif (« sheet », « page »…), sinon celle du thème Standard."""
    path = _assets.get(key, fallback)
    cache = (str(path), rotate)
    if cache not in _pixmaps:
        image = QPixmap(str(path))
        if image.isNull() and str(path) != str(fallback):
            image = QPixmap(str(fallback))
        if rotate and not image.isNull():
            image = image.transformed(QTransform().rotate(rotate))
        _pixmaps[cache] = image
    return _pixmaps[cache]


def active_spec():
    return _spec


def configure(spec, assets=None):
    """Activer la recoloration d'un thème et retinter les constantes de couleur des modules."""
    global _spec, _assets
    _spec = spec
    _assets = dict(assets or {})
    _colors.clear()
    for name in CHROME_MODULES:
        module = sys.modules.get(name)
        if module is None:
            continue
        for attr in CHROME_NAMES:
            value = getattr(module, attr, None)
            if not isinstance(value, QColor):
                continue
            original = _originals.setdefault((name, attr), QColor(value))
            setattr(module, attr, tint(original))
