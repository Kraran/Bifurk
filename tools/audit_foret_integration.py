"""Comparer la revue des 400 passages aux points d'entrée du moteur.

La présence d'un gestionnaire ne prouve pas sa complétude. Les conclusions
sémantiques sont relues et enregistrées séparément dans le fichier de revue.
Avec --pdf, comparer aussi les renvois extraits, sans exporter le texte privé.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grimoire_modules.foret import rules
from grimoire_modules.foret.encounters import COMBATS
from tools.audit_foret import audit as audit_catalogue

REVIEW = ROOT / 'catalogues/revue_integration_foret_1983.json'
CATALOGUE = ROOT / 'catalogues/evenements_foret_1983.json'
STATUSES = {'couvert', 'narratif', 'manquant', 'partiel', 'decision_source'}


def runtime_inventory():
    """Recenser tables, commandes déclarées et conditions explicites, sans jouer."""
    found = {}
    def add(numbers, label):
        for number in numbers:
            found.setdefault(number,set()).add(label)
    add(COMBATS,'combat')
    add(rules.ENTRY_RULES,'effet')
    add(rules.PAYMENT_PARAGRAPHS,'paiement')
    add(rules.BRANCH_TESTS,'epreuve')
    add(rules.GAS_PARAGRAPHS,'gaz')
    add(rules.OPTIONAL_FINDS,'option')
    add(rules.ITEM_BRANCHES,'condition')
    add((a for a,b in rules.OPTIONAL_ITEM_ROUTES),'condition')
    add((a for a,b in rules.ROUTE_COSTS),'cout_route')
    add((a for a,b in rules.FIXED_PAYMENT_ROUTES),'condition')
    # Effets automatiques relus dans ForetController.go_to, hors commandes.
    add((2,156,333,399,400),'automatique')
    # Commande affichée hors de la table commands (issue du Loup-Garou).
    add((388,),'commande')
    tree = ast.parse((ROOT/'grimoire_modules/foret/actions.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('commands','expected') for t in node.targets):
            value = ast.literal_eval(node.value)
            add(value if all(type(k) is int for k in value) else value.values(),'commande')
    tree = ast.parse((ROOT/'grimoire_modules/foret/rules.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='route_available')
    for node in ast.walk(function):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='physical' for t in node.targets):
            add(ast.literal_eval(node.value),'condition')
        if not isinstance(node,ast.Compare):
            continue
        try:
            value = ast.literal_eval(node.comparators[0])
        except (ValueError,TypeError):
            continue
        if isinstance(node.left,ast.Name) and node.left.id=='paragraph':
            add([value] if type(value) is int else value,'condition')
        elif (isinstance(node.left,ast.Tuple) and [getattr(t,'id',None) for t in node.left.elts]==['paragraph','target']):
            add([value[0]] if type(value[0]) is int else [pair[0] for pair in value],'condition')
    return {n:sorted(labels) for n,labels in sorted(found.items())}


def audit(review, catalogue, pdf=None):
    """Valider l'exhaustivité de la revue et signaler toute dérive du moteur."""
    source = audit_catalogue(catalogue,pdf)
    if review['pdf_sha256'] != catalogue['pdf_sha256']:
        raise ValueError('Revue et catalogue de deux éditions différentes.')
    rows = review['paragraphs']
    if set(rows) != {str(n) for n in range(1,401)}:
        raise ValueError('La revue doit classer exactement les 400 paragraphes.')
    inventory = runtime_inventory()
    findings = {f['id']:f for f in review['findings']}
    if len(findings) != len(review['findings']):
        raise ValueError('Identifiant de constat dupliqué.')
    for number,row in rows.items():
        if row['status'] not in STATUSES or not row['reason'].strip():
            raise ValueError('Classement ou justification absent : '+number)
        if row['runtime'] != inventory.get(int(number),[]):
            raise ValueError('Points d’entrée modifiés, relire le §'+number)
        if row['status'] in ('narratif','manquant') and row['runtime']:
            raise ValueError('Classement incompatible avec le moteur : '+number)
        if row['status']=='couvert' and not row['runtime']:
            raise ValueError('Couverture sans point d’entrée : '+number)
        if row['source_page_pdf'] != catalogue['paragraphs'][number]['analysis']['source_page_pdf']:
            raise ValueError('Provenance modifiée : '+number)
        for issue in row['findings']:
            if issue not in findings or int(number) not in findings[issue]['paragraphs']:
                raise ValueError('Constat incohérent : '+number)
    for finding in findings.values():
        for number in finding['paragraphs']:
            if finding['id'] not in rows[str(number)]['findings']:
                raise ValueError('Constat absent du passage : '+str(number))
    registered = {catalogue['mechanics_implementation']['shop_paragraph']}
    for value in catalogue['mechanics_implementation'].values():
        if isinstance(value,list):registered.update(n for n in value if type(n) is int)
    result = {'paragraphs':400,'routes':source['routes'],
              'classifications':dict(sorted(Counter(r['status'] for r in rows.values()).items())),
              'runtime_paragraphs':len(inventory),'registered_paragraphs':len(registered),
              'unregistered_runtime_paragraphs':sorted(set(inventory)-registered),
              'registered_without_runtime':sorted(registered-set(inventory)),
              'findings':len(findings),'pdf_checked':bool(pdf)}
    if pdf:
        from main import extract_paragraphs
        from navigation import destinations
        from grimoire_modules.registry import module_for_pdf
        texts = extract_paragraphs(pdf)
        module_for_pdf(pdf).repair_paragraphs(texts)
        differences = []
        for number,text in sorted(texts.items()):
            actual = {d for a,b,d in destinations(text)}
            expected = {r['target'] for r in catalogue['paragraphs'][str(number)]['routes']}
            if actual != expected:
                differences.append({'paragraph':number,'text_only':sorted(actual-expected),
                                    'catalogue_only':sorted(expected-actual)})
        result['text_route_differences'] = differences
    return result


def markdown(review, result):
    """Produire le relevé public sans le texte ou les images du PDF."""
    lines = ['# Forêt : audit final de l’intégration', '',
             'Revue des 400 analyses du catalogue, rapprochées du moteur ; relecture du PDF et',
             'reproduction Qt ciblées sur les écarts. La présence d’un gestionnaire ne prouve',
             'pas que toutes les règles du passage sont exécutées. Aucun correctif du moteur',
             'n’est inclus dans cet audit.', '', '## Bilan', '',
             f"- {result['paragraphs']} paragraphes classés ; {result['routes']} renvois recensés.",
             f"- PDF exact contrôlé : {'oui' if result['pdf_checked'] else 'non, contrôle du registre seulement'}.",
             f"- {result['runtime_paragraphs']} paragraphes ont un point d’entrée dans le moteur, contre {result['registered_paragraphs']} dans le registre historique.",
             '- Les classes portent sur les règles connues de chaque analyse, pas sur un pourcentage d’achèvement.', '']
    lines += [f'- {key} : {value}.' for key,value in result['classifications'].items()]
    lines += ['', '## Constats à traiter', '']
    for f in review['findings']:
        lines += [f"### {f['id']} — {f['title']}",'',
                  'Paragraphes : '+', '.join('§'+str(n) for n in f['paragraphs'])+'.', '',
                  f['observation'],'',f['next_step'],'']
    lines += ['## Registre sous-estimé', '',
              ', '.join('§'+str(n) for n in result['unregistered_runtime_paragraphs'])+'.', '',
              'Ces ajouts de décompte ne représentent pas de nouvelles mécaniques à programmer.', '']
    if 'text_route_differences' in result:
        lines += ['## Comparaison des liens extraits', '',
                  'Le catalogue conserve les destinations, mais certains renvois ne deviennent pas des liens dans le texte :', '']
        for row in result['text_route_differences']:
            lines += [f"- §{row['paragraph']} : catalogue seulement {row['catalogue_only']}, texte seulement {row['text_only']}."]
        lines += ['']
    lines += ['## Relevé des 400 paragraphes', '',
              '| § | Page PDF | Classe | Points d’entrée | Constats |',
              '| --- | --- | --- | --- | --- |']
    for number,row in review['paragraphs'].items():
        lines += [f"| {number} | {row['source_page_pdf']} | {row['status']} | {', '.join(row['runtime']) or '—'} | {', '.join(row['findings']) or '—'} |"]
    lines += ['', 'Reproduction :', '', '```powershell',
              '.\\.venv\\Scripts\\python.exe tools/audit_foret_integration.py --pdf "03. La Foret de la Malediction (1983).pdf"',
              '```', '', 'Le [JSON de revue](../../catalogues/revue_integration_foret_1983.json) contient la justification de chaque classement. Les observations',
              'Qt et les extraits de travail restent privés dans audit-output. Aucune compilation.']
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path)
    parser.add_argument('--markdown',type=Path)
    args = parser.parse_args()
    review = json.loads(REVIEW.read_text(encoding='utf-8'))
    result = audit(review,json.loads(CATALOGUE.read_text(encoding='utf-8')),args.pdf)
    if args.markdown:args.markdown.write_text(markdown(review,result),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
