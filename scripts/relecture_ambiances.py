"""Page de relecture des scènes d'ambiance d'un livre (HTML local, jamais publiée).

Usage : python scripts/relecture_ambiances.py LIVRE.pdf [SORTIE.html]
Le PDF est reconnu par son empreinte (catalogues/modules) ; son catalogue
« ambiences » est validé puis présenté zone par zone : chaque paragraphe avec le
début de son texte, la scène jouée et l'exception qui l'a choisie. Un lecteur audio
par scène permet d'écouter les boucles. La page contient des extraits du livre :
elle est écrite par défaut dans audit-output/ (ignoré par Git) et ne doit pas être
diffusée. Pour corriger une proposition, modifier catalogues/ambiances_<livre>.json
(scène, paragraphes, statut « proposé » → « vérifié ») puis régénérer la page."""
import html
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('BIFURK_DATA_ROOT', str(ROOT / 'audit-output' / 'donnees-relecture'))

EXCERPT = 230
SCENE_COLORS = {
    'caverne': '#6b5b4b', 'souterrain': '#3f6a73', 'crypte': '#5a4a6e', 'riviere': '#2f6fa3',
    'marais': '#5b6b2f', 'foret': '#3d7a3a', 'foret_nuit': '#24405e', 'vent': '#7d8a96',
    'rue': '#8a6a3a', 'marche': '#a3672f', 'port': '#2f7f86', 'taverne': '#9b4a2a',
    'foyer': '#b0582a', None: '#888888',
}


def excerpt(text):
    flat = ' '.join(text.split())
    return flat if len(flat) <= EXCERPT else flat[:EXCERPT].rsplit(' ', 1)[0] + ' …'


def chip(scene, scenes, extra=''):
    label = scenes[scene]['label'] if scene in scenes else 'garder la scène précédente'
    return (f'<span class="chip" data-scene="{scene or "garder"}" '
            f'style="background:{SCENE_COLORS.get(scene, "#888")}">{html.escape(label)}{extra}</span>')


def build(pdf_path, output=None):
    from main import extract_paragraphs
    from grimoire_modules.registry import module_for_pdf
    from ambience_map import AmbienceMap, KEEP
    from sound_effects import SCENES
    module = module_for_pdf(pdf_path)
    if module is None:
        raise SystemExit('PDF non reconnu : aucune édition cataloguée ne correspond à son empreinte.')
    ambience = AmbienceMap.from_module(module, SCENES)
    if ambience is None:
        raise SystemExit(f'Aucun catalogue d’ambiances pour « {module.title} ».')
    paragraphs = extract_paragraphs(pdf_path, module=module)
    output = Path(output or ROOT / 'audit-output' / f'relecture-ambiances-{module.id}.html')
    output.parent.mkdir(parents=True, exist_ok=True)
    sounds = os.path.relpath(ROOT / 'assets' / 'sounds', output.parent).replace(os.sep, '/')

    exception_of = {n: entry for entry, numbers in ambience.exceptions for n in numbers}
    played = Counter('garder' if ambience.scene_for(n) is KEEP else ambience.scene_for(n)
                     for n in range(1, module.paragraph_count + 1))
    statuses = Counter(entry['status'] for entry, _ in [*ambience.zones, *ambience.exceptions])

    legend = []
    for key, scene in SCENES.items():
        count = played.get(key, 0)
        legend.append(f'<li class="{"" if count else "unused"}">{chip(key, SCENES)} '
                      f'<b>{count}</b> §'
                      f'<audio controls loop preload="none" src="{sounds}/{scene["loop"]}.ogg"></audio></li>')
    sections = []
    for zone, numbers in ambience.zones:
        rows = []
        for n in sorted(numbers):
            scene = ambience.scene_for(n)
            entry = exception_of.get(n)
            note = (f'<div class="why">Exception : {html.escape(entry["label"])} '
                    f'<em>({entry["status"]})</em></div>') if entry else ''
            rows.append(f'<tr class="{"exc" if entry else ""}" data-scene="{"garder" if scene is KEEP else scene}">'
                        f'<td class="num">§{n}</td><td>{chip(None if scene is KEEP else scene, SCENES)}</td>'
                        f'<td>{note}{html.escape(excerpt(paragraphs.get(n, "(paragraphe absent du PDF)")))}</td></tr>')
        sections.append(
            f'<section><h2>{html.escape(zone["label"])}</h2>'
            f'<p class="meta">Zone <code>{zone["id"] if "id" in zone else ""}</code> · scène {chip(zone["scene"], SCENES)} · '
            f'{len(numbers)} paragraphes · statut <em>{zone["status"]}</em></p>'
            f'<table>{"".join(rows)}</table></section>')
    exceptions = ''.join(
        f'<li>{chip(None if entry["scene"] is None else entry["scene"], SCENES)} '
        f'{html.escape(entry["label"])} — §{", §".join(map(str, sorted(numbers)))} <em>({entry["status"]})</em></li>'
        for entry, numbers in ambience.exceptions)
    page = TEMPLATE.format(
        title=html.escape(module.title), legend=''.join(legend), exceptions=exceptions,
        sections=''.join(sections), count=module.paragraph_count,
        status=', '.join(f'{count} {name}' for name, count in statuses.items()),
        catalogue=html.escape(dict(module.catalogue_paths)['ambiences'].name))
    output.write_text(page, encoding='utf-8')
    return output


TEMPLATE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relecture des ambiances — {title}</title>
<style>
:root {{ --bg:#f4ecd8; --ink:#2b2118; --muted:#6d5d4b; --line:#d8c8a8; --card:#fbf6ea; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1d1813; --ink:#eadfc9; --muted:#b3a38a; --line:#3d3326; --card:#26201a; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 Georgia, 'EB Garamond', serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 80px; }}
h1 {{ margin:.2em 0; }} h2 {{ margin:1.6em 0 .2em; border-bottom:1px solid var(--line); }}
.meta, .hint {{ color:var(--muted); }}
.chip {{ display:inline-block; color:#fff; border-radius:999px; padding:1px 10px; font:12px/1.6 sans-serif; white-space:nowrap; }}
ul.legend {{ list-style:none; padding:0; display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:6px 16px; }}
ul.legend li {{ display:flex; align-items:center; gap:8px; }} ul.legend li.unused {{ opacity:.55; }}
audio {{ height:28px; max-width:170px; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); }}
td {{ border-top:1px solid var(--line); padding:6px 8px; vertical-align:top; }}
td.num {{ font-weight:bold; white-space:nowrap; width:3.5em; }}
tr.exc {{ box-shadow: inset 4px 0 0 #b0582a; }}
.why {{ font:13px sans-serif; color:var(--muted); }}
.filters {{ position:sticky; top:0; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--line); z-index:1; }}
.filters button {{ font:13px sans-serif; margin:2px; padding:3px 10px; border-radius:6px; border:1px solid var(--line); background:var(--card); color:var(--ink); cursor:pointer; }}
.filters button.on {{ outline:2px solid #b0582a; }}
@media (max-width:600px) {{ td.num {{ width:auto; }} audio {{ max-width:120px; }} }}
</style></head><body><main>
<h1>Ambiances — {title}</h1>
<p class="hint">Page locale de relecture : elle contient des extraits du livre, ne la diffuse pas.
Catalogue : <code>catalogues/{catalogue}</code> · {count} paragraphes · entrées : {status}.</p>
<h2>Scènes</h2>
<ul class="legend">{legend}</ul>
<h2>Exceptions</h2>
<ul>{exceptions}</ul>
<div class="filters" id="filters"><button data-f="tout" class="on">Tout</button><button data-f="exc">Exceptions seulement</button></div>
{sections}
</main>
<script>
document.getElementById('filters').addEventListener('click', function (event) {{
  var f = event.target.getAttribute('data-f'); if (!f) return;
  document.querySelectorAll('#filters button').forEach(function (b) {{ b.classList.toggle('on', b === event.target); }});
  document.querySelectorAll('tr[data-scene]').forEach(function (row) {{
    row.style.display = (f === 'tout' || (f === 'exc' && row.classList.contains('exc'))
                         || row.getAttribute('data-scene') === f) ? '' : 'none';
  }});
}});
document.querySelectorAll('.legend .chip').forEach(function (c) {{
  var b = document.createElement('button'); b.textContent = c.textContent; b.setAttribute('data-f', c.getAttribute('data-scene'));
  document.getElementById('filters').appendChild(b);
}});
</script></body></html>
"""

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    print(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
