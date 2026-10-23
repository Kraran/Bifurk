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


def repair_foret_confirmed_errata(paragraphs):
    """Corriger les lacunes confirmées de la Forêt et retirer le colophon final.

    Le registre réserve cette opération au SHA-256 du PDF catalogué. Préserver
    le récit extrait et rester idempotent : une seconde passe n’ajoute jamais une
    seconde Anguille et un texte déjà corrigé reste inchangé.
    """
    text = paragraphs.get(186)
    if text and not re.search(r'(?i)rendez\s*[-‐‑–]?\s*vous\s+au\s+131\b', text):
        paragraphs[186] = (text.rstrip() + '\n\nANGUILLE CARNIVORE\n'
                           'HABILETÉ : 5 — ENDURANCE : 4\n'
                           'Si vous êtes vainqueur, rendez-vous au 131.')
    text = paragraphs.get(267)
    if text:
        paragraphs[267] = re.sub(r'(?i)(rendez\s*[-‐‑–]?\s*vous\s+au\s+)1%',
                                 r'\g<1>196', text)
    text = paragraphs.get(400)
    if text:
        colophon = re.search(r"(?im)^\s*Achevé\s+d['’]imprimer\b",text)
        if colophon:
            paragraphs[400] = text[:colophon.start()].rstrip()
