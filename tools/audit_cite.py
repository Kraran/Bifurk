"""Contrôler le catalogue des renvois de la Cité des Voleurs.

Sans PDF, vérifier la couverture des 400 paragraphes, les renvois, les
paragraphes orphelins, l’accessibilité depuis le §1 et la concordance des
fins du catalogue avec celles du moteur. Avec --pdf, vérifier
aussi l’édition, la page source de chaque en-tête et la concordance entre les
routes cataloguées et les renvois du texte réparé. Seules des métriques sont
affichées : aucun texte du livre ni aucune image ne sont exportés.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / 'catalogues/evenements_cite_1983.json'
FIRST_PAGE, LAST_PAGE = 20, 177
MODES = {'choix', 'suite', 'fin'}


def _headers(pdf):
    """Associer chaque en-tête noir centré, dans l’ordre continu, à sa page."""
    import pymupdf
    found = {}
    with pymupdf.open(pdf) as document:
        next_number = 1
        for page_number, page in enumerate(document, 1):
            lines = [line for block in page.get_text('dict')['blocks']
                     for line in block.get('lines', [])]
            for line in sorted(lines, key=lambda item: item['bbox'][1]):
                spans = line['spans']
                text = ''.join(span['text'] for span in spans).strip()
                x0, _, x1, _ = line['bbox']
                if (text == str(next_number) and abs((x0 + x1) / 2 - page.rect.width / 2) < 20
                        and all(span['color'] == 0 for span in spans)):
                    found[text] = page_number
                    next_number += 1
    return found


def _text_targets(pdf):
    """Lire les renvois du texte réparé, dans l’ordre d’apparition."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from grimoire_modules.registry import module_for_pdf
    from main import extract_paragraphs
    from navigation import destinations
    module = module_for_pdf(pdf)
    if module is None or 'cite-ocr-1983' not in module.text_repairs:
        raise ValueError('Le PDF n’est pas reconnu comme la Cité des Voleurs cataloguée.')
    paragraphs = extract_paragraphs(pdf, module=module)
    result = {}
    for number, text in paragraphs.items():
        targets = []
        for _start, _end, target in destinations(text):
            if target not in targets:
                targets.append(target)
        result[str(number)] = targets
    return result


def _endings():
    """Fins (morts et victoire) déclarées par le moteur Python du module."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from grimoire_modules.cite import rules
    return sorted(rules.ENDINGS)


def audit(catalogue, pdf=None):
    """Retourner des métriques ; lever ValueError si une garantie est violée."""
    entries = catalogue['paragraphs']
    expected = {str(n) for n in range(1, 401)}
    if (set(entries) != expected or catalogue['total_paragraphs'] != 400
            or catalogue['reviewed_count'] != 400 or catalogue['review_pending']):
        raise ValueError('Le catalogue doit couvrir exactement les 400 paragraphes.')
    contract = catalogue['analysis_contract']
    if contract['conditions_are_executable'] or contract['runtime_effects_enabled']:
        raise ValueError('Les conditions du catalogue ne doivent pas être exécutables.')
    first, last = contract.get('analysed_range', (0, 0))
    analysed = {str(n) for n in range(first, last + 1)} if first else set()
    incoming = {number: 0 for number in expected}
    route_count = 0
    for number, entry in entries.items():
        status = 'analyse_verifiee' if number in analysed else 'renvois_verifies'
        if entry['status'] != status or not entry['title'].strip():
            raise ValueError(f'Statut ou titre invalide : {number}')
        if (number in analysed) != bool(str(entry.get('analysis', '')).strip()):
            raise ValueError(f'Analyse manquante ou hors tranche : {number}')
        if not FIRST_PAGE <= entry['source_page_pdf'] <= LAST_PAGE:
            raise ValueError(f'Page source hors du livre : {number}')
        routes = entry['routes']
        targets = [route['target'] for route in routes]
        if len(targets) != len(set(targets)):
            raise ValueError(f'Renvoi dupliqué : {number}')
        expected_mode = 'fin' if not routes else 'suite' if len(routes) == 1 else 'choix'
        if entry['mode'] not in MODES or entry['mode'] != expected_mode:
            raise ValueError(f'Mode incohérent : {number}')
        for route in routes:
            if str(route['target']) not in expected or not route['label'].strip():
                raise ValueError(f'Renvoi invalide : {number}')
            if 'condition_text' in route and not route['condition_text'].strip():
                raise ValueError(f'Condition vide : {number}')
            incoming[str(route['target'])] += 1
        route_count += len(routes)
    orphans = sorted(int(number) for number, count in incoming.items() if not count and number != '1')
    if orphans:
        raise ValueError(f'Paragraphes sans renvoi entrant : {orphans}')
    reached, pending = {1}, [1]
    while pending:
        for route in entries[str(pending.pop())]['routes']:
            if route['target'] not in reached:
                reached.add(route['target'])
                pending.append(route['target'])
    unreachable = sorted(set(range(1, 401)) - reached)
    if unreachable:
        raise ValueError(f'Paragraphes inaccessibles depuis le §1 : {unreachable}')
    terminals = sorted(int(n) for n, e in entries.items() if not e['routes'])
    endings = _endings()
    if len(analysed) == 400 and terminals != endings:
        raise ValueError(f'Fins du catalogue différentes des fins du moteur : {terminals} / {endings}')
    if set(endings) - reached:
        raise ValueError(f'Fins inaccessibles depuis le §1 : {sorted(set(endings) - reached)}')
    if pdf:
        pdf = Path(pdf)
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != catalogue['pdf_sha256']:
            raise ValueError('Ce catalogue correspond à une autre édition du PDF.')
        found = _headers(pdf)
        if set(found) != expected:
            raise ValueError('Les 400 en-têtes du PDF ne sont pas retrouvés.')
        for number, page in found.items():
            if entries[number]['source_page_pdf'] != page:
                raise ValueError(f'Page source incohérente : {number}')
        text_targets = _text_targets(pdf)
        for number in sorted(expected, key=int):
            catalogued = [route['target'] for route in entries[number]['routes']]
            if text_targets.get(number) != catalogued:
                raise ValueError(f'Routes différentes des renvois du texte : {number}')
    issues = catalogue['source_issues']
    return {'paragraphs': len(entries), 'routes': route_count,
            'terminal_paragraphs': terminals, 'endings_reachable': len(set(endings) & reached),
            'orphans': orphans, 'unreachable': unreachable,
            'blocking_source_issues': [i['paragraph'] for i in issues if i['severity'] == 'blocking'],
            'open_source_issues': [i['paragraph'] for i in issues if i.get('status') != 'resolved'],
            'analysed': len(analysed),
            'pdf_provenance_checked': bool(pdf), 'conditions_are_executable': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(CATALOGUE.read_text(encoding='utf-8')), args.pdf),
                     ensure_ascii=False, indent=2))
