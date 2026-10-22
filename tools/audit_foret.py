"""Contrôler le contrat du catalogue d’analyse sans exécuter les règles du livre.

Avec --pdf, vérifier également l’édition et les en-têtes centrés du document
privé. Aucun texte du livre ni aucune image ne sont exportés par cet outil.
"""
import argparse
import hashlib
import json
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parents[1] / 'catalogues/evenements_foret_1983.json'


def audit(catalogue, pdf=None):
    """Retourner des métriques ; lever ValueError si une garantie est violée."""
    entries = catalogue['paragraphs']
    expected = {str(n) for n in range(1, 401)}
    if set(entries) != expected or catalogue['reviewed_count'] != 400 or catalogue['review_pending']:
        raise ValueError('La revue doit couvrir exactement les 400 paragraphes.')
    if catalogue['automation_pending'] != list(range(1, 401)):
        raise ValueError('L’analyse ne doit pas annoncer une automatisation achevée.')
    route_count = 0
    for number, entry in entries.items():
        if entry['status'] != 'analyse_verifiee' or not entry['title'].strip():
            raise ValueError(f'Statut ou titre invalide : {number}')
        if not entry['analysis']['rules'].strip() or not 1 <= entry['analysis']['source_page_pdf'] <= 170:
            raise ValueError(f'Provenance ou analyse absente : {number}')
        targets = [route['target'] for route in entry['routes']]
        if len(targets) != len(set(targets)):
            raise ValueError(f'Renvoi dupliqué : {number}')
        for route in entry['routes']:
            if str(route['target']) not in expected or not route['label'].strip():
                raise ValueError(f'Renvoi invalide : {number}')
        route_count += len(targets)
    if pdf:
        pdf = Path(pdf)
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != catalogue['pdf_sha256']:
            raise ValueError('Cette analyse correspond à une autre édition du PDF.')
        import pymupdf
        # Les numéros de destination bleus ne sont pas des en-têtes. Seuls les
        # nombres noirs centrés, dans l’ordre continu, identifient les passages.
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
                    if (text == str(next_number) and abs((x0+x1)/2-page.rect.width/2) < 20
                            and all(span['color'] == 0 for span in spans)):
                        found[text] = page_number
                        next_number += 1
        if set(found) != expected:
            raise ValueError('Les 400 en-têtes du PDF ne sont pas retrouvés.')
        for number, page in found.items():
            if entries[number]['analysis']['source_page_pdf'] != page:
                raise ValueError(f'Page source incohérente : {number}')
    return {'paragraphs':len(entries), 'routes':route_count,
            'blocking_source_issues':[issue['paragraph'] for issue in catalogue['source_issues']
                                      if issue['severity'] == 'blocking'],
            'pdf_provenance_checked': bool(pdf), 'analysis_entries_are_executable':False,
            'implemented_combat_passages':len(catalogue.get('mechanics_implementation', {}).get('combat_paragraphs', []))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(CATALOGUE.read_text(encoding='utf-8')), args.pdf), ensure_ascii=False, indent=2))
