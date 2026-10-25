"""Chargement des thèmes déclaratifs JSON / QSS, sans état de partie.

Chaque manifeste résout ses assets depuis son propre répertoire. Le QSS utilise
string.Template pour les couleurs, chemins et polices. Un thème incomplet est
écarté de la liste ; le thème livré sert de repli aux fenêtres indépendantes.
Voir docs/themes-et-ambiance.md avant d'ajouter une couleur ou un asset obligatoire."""
import json
from pathlib import Path
from string import Template


class Theme:
    """Manifeste chargé et chemins d’assets résolus, sans dépendance aux widgets Qt."""
    def __init__(self, manifest):
        """Charger JSON et QSS depuis le manifeste ; remonter les erreurs au validateur de thèmes."""
        self.root = Path(manifest).parent
        self.data = json.loads(Path(manifest).read_text(encoding='utf-8'))
        self.id = self.data['id']
        self.name = self.data['name']
        self.assets = {key: (self.root / path).resolve() for key, path in self.data['assets'].items()}
        self.colors = self.data['colors']
        self.css = (self.root / self.data['stylesheet']).read_text(encoding='utf-8')

    def color(self, key):
        """Lire une couleur obligatoire ; une clé absente signale un thème incomplet."""
        return self.colors[key]

    def stylesheet(self, reading_font, ui_font):
        """Substituer chemins POSIX, polices et couleurs dans le QSS sans exécuter de code."""
        return Template(self.css).substitute(
            {**{k: p.as_posix() for k, p in self.assets.items()},
             'reading_font': reading_font, 'ui_font': ui_font, **self.colors})


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


def default_theme():
    """Charger paresseusement le thème livré pour les vues créées sans contrôleur.

    Lu seulement quand une vue autonome (règles, illustration) en a besoin."""
    return Theme(Path(__file__).resolve().parent / 'assets/themes/grimoire/theme.json')
