"""Chargement des thèmes déclaratifs JSON / QSS, sans état de partie.

Chaque manifeste résout ses assets depuis son propre répertoire. Le QSS utilise
string.Template pour les couleurs, chemins et polices. Un thème incomplet est
écarté de la liste ; le thème actif (Standard par défaut) sert de repli aux
fenêtres indépendantes. Un thème dérivé (« base ») reprend le QSS, les couleurs et
les assets de son thème de base, recolorés par sa section « recolor »
(theme_palette), et ne déclare que ses propres textures.
Voir docs/themes-et-ambiance.md avant d'ajouter une couleur ou un asset obligatoire."""
import json
from pathlib import Path
from string import Template

from theme_palette import parse_spec, tint_css, tint_hex


class Theme:
    """Manifeste chargé et chemins d’assets résolus, sans dépendance aux widgets Qt."""
    def __init__(self, manifest):
        """Charger JSON et QSS depuis le manifeste ; remonter les erreurs au validateur de thèmes."""
        self.root = Path(manifest).parent
        data = json.loads(Path(manifest).read_text(encoding='utf-8'))
        self.recolor = parse_spec(data.get('recolor'))
        own_assets = {key: (self.root / path).resolve() for key, path in data.get('assets', {}).items()}
        if data.get('base'):
            base = Theme(self.root.parent / data['base'] / 'theme.json')
            if base.recolor is not None:
                raise ValueError('Un thème de base ne peut pas être lui-même dérivé.')
            self.data = {**base.data, **data}
            self.assets = {**base.assets, **own_assets}
            # Le QSS reçoit les couleurs d'origine puis est recoloré en une fois.
            self._css_colors = dict(base.colors)
            self.colors = {key: tint_hex(value, self.recolor) for key, value in base.colors.items()}
            self.css = base.css
        else:
            self.data = data
            self.assets = own_assets
            self.colors = self._css_colors = data['colors']
            self.css = (self.root / data['stylesheet']).read_text(encoding='utf-8')
        self.id = self.data['id']
        self.name = self.data['name']

    def color(self, key):
        """Lire une couleur obligatoire ; une clé absente signale un thème incomplet."""
        return self.colors[key]

    def stylesheet(self, reading_font, ui_font):
        """Substituer chemins POSIX, polices et couleurs dans le QSS sans exécuter de code."""
        css = Template(self.css).substitute(
            {**{k: p.as_posix() for k, p in self.assets.items()},
             'reading_font': reading_font, 'ui_font': ui_font, **self._css_colors})
        return tint_css(css, self.recolor)


def available_themes(root):
    """Indexer les manifestes valides par identifiant après contrôle des couleurs, assets et QSS."""
    themes = {}
    for manifest in sorted(Path(root).glob('*/theme.json')):
        try:
            theme = Theme(manifest)
            # Un thème décrit toutes les surfaces peintes, pas seulement les contrôles QSS.
            for key in ('page','ink','accent','ornament','rubric','scene_background',
                        'frame','gold','icon_background','icon_border','icon_ink','link'):
                theme.color(key)
            for key in ('parchment','leather','scene'):
                if not theme.assets[key].is_file():
                    raise ValueError('Missing theme asset')
            theme.stylesheet('serif', 'sans-serif')
            themes[theme.id] = theme
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return themes


_active = None


def set_active_theme(theme):
    """Mémoriser le thème affiché pour les vues autonomes ouvertes ensuite."""
    global _active
    _active = theme


def default_theme():
    """Thème actif, sinon le thème Standard livré, pour les vues créées sans contrôleur.

    Lu seulement quand une vue autonome (règles, illustration) en a besoin."""
    if _active is not None:
        return _active
    return Theme(Path(__file__).resolve().parent / 'assets/themes/grimoire/theme.json')
