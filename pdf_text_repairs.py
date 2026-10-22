"""Retouches d'une édition identifiée, sans embarquer son texte sous droits.

Le PDF fourni place un fragment du §254 au milieu du §253 (page physique 113).
On déplace uniquement les caractères déjà extraits du livre de l'utilisateur.
L'appelant vérifie l'empreinte via le catalogue avant toute correction.
"""
import re


def repair_misplaced_fragment(paragraphs):
    """Réunir le passage de la crypte, uniquement si les deux raccords sont présents.

    Les bornes courtes identifient le défaut d'édition ; aucun contenu n'est inventé.
    Si le PDF est déjà réparé ou incomplet, conserver intégralement l'extraction.
    """
    source, target = paragraphs.get(253, ''), paragraphs.get(254, '')
    fragment = re.search(r"bruit d['’]eau\b.*?train de s['’]ouvrir\s*!", source, re.S | re.I)
    seam = re.search(r"entendant un\s*(?=Tandis)", target)
    if fragment is None or seam is None:
        return
    before = source[:fragment.start()].rstrip()
    # Le même raccord contient un point d'interrogation OCRisé comme le chiffre 1.
    before = re.sub(r'(Qu[\'’]allez-vous faire)\s*1$', r'\1 ?', before)
    paragraphs[253] = before + '\n' + source[fragment.end():].lstrip()
    paragraphs[254] = (target[:seam.end()].rstrip() + ' ' + fragment.group().strip()
                       + '\n' + target[seam.end():])
