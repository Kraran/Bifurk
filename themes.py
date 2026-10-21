"""Theme manifests and QSS are data, independent of gameplay and saved games."""
import json
from pathlib import Path
from string import Template


class Theme:
    def __init__(self, manifest):
        self.root = Path(manifest).parent
        self.data = json.loads(Path(manifest).read_text(encoding='utf-8'))
        self.id = self.data['id']
        self.name = self.data['name']
        self.assets = {key: (self.root / path).resolve() for key, path in self.data['assets'].items()}
        self.colors = self.data['colors']
        self.css = (self.root / self.data['stylesheet']).read_text(encoding='utf-8')

    def color(self, key):
        return self.colors[key]

    def stylesheet(self, reading_font, ui_font):
        return Template(self.css).substitute(
            {**{k: p.as_posix() for k, p in self.assets.items()},
             'reading_font': reading_font, 'ui_font': ui_font, **self.colors})


def available_themes(root):
    themes = {}
    for manifest in sorted(Path(root).glob('*/theme.json')):
        try:
            theme = Theme(manifest)
            # A theme must describe every painted surface, not just QSS controls.
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
    # Read only when a view needs a standalone fallback (rules/illustration windows).
    return Theme(Path(__file__).resolve().parent / 'assets/themes/grimoire/theme.json')
