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
    repair_foret_typography(paragraphs)
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


def repair_foret_typography(paragraphs):
    """Retoucher les coquilles repérées dans l'extraction de l'édition identifiée.

    Les remplacements sont bornés aux paragraphes et contextes constatés. Ne
    jamais remplacer globalement « Test », qui peut désigner un vrai test.
    Aucun numéro de renvoi, prix ni caractéristique n'est modifié.
    """
    for number in (51, 59, 61, 109, 112, 188, 267, 349, 359, 362, 363):
        if number in paragraphs:
            paragraphs[number] = re.sub(
                r'\b(vers|à|de)\s+Test\b', r"\1 l’est", paragraphs[number])
    for number in (92, 100, 158, 288):
        if number in paragraphs:
            paragraphs[number] = paragraphs[number].replace(' ŕ ', ' — ')
    if 261 in paragraphs:
        paragraphs[261] = re.sub(
            r'(?m)(Potion Antipoison|Eau Bénite|Corde Magique)\s+[Ŕŕ](?=\s+\d)',
            r'\1 —', paragraphs[261])
        paragraphs[261] = re.sub(r'(Brassard de Force)-(?=\s+3\s+pièces)',
                                 r'\1 —', paragraphs[261])
    if 400 in paragraphs:
        paragraphs[400] = paragraphs[400].replace('votre coips', 'votre corps')


# Renvois de la Cité dont le mot « au » a été mal reconnu : le numéro imprimé
# est intact, seule la préposition empêche la détection du lien.
CITE_BROKEN_ROUTES = {
    110: (r'(rendez-vous\s+)ai(\s+239\b)', 239),
    258: (r'(rendez-\s*vous\s+)an(\s+318\b)', 318),
    262: (r'(rendez-vous\s+)»u(\s+375\b)', 375),
}

# Renvois imprimés vers un paragraphe sans rapport. L’édition originale anglaise
# (VO), référence en cas de litige, donne le renvoi exact : la balle frappée
# par-dessus le mur (§359), le tatouage impayable (§354), la fuite vers le nord
# sous l’éclair (§304), la rue du nord jusqu’aux gardes (§334), le mur au bout
# de la rue vers l’est (§375) et la boutique à gauche vers l’ouest (§24).
CITE_ROUTE_ERRATA = {
    81: ('(rendez-vous au 392)', '(rendez-vous au 304)'),
    112: ('rendez-vous au 134.', 'rendez-vous au 334.'),
    113: ('rendez-vous au\n175.', 'rendez-vous au\n375.'),
    145: ('(rendez-vous au\n14).', '(rendez-vous au\n24).'),
    168: ('(rendez-vous au 159)', '(rendez-vous au 359)'),
    182: ('rendez-vous au 351', 'rendez-vous au 354'),
}

# Caractéristiques que la traduction donne autrement que la VO, référence en
# cas de litige : le texte affiché suit la règle appliquée. Aucun renvoi n’est
# touché ; le texte de remplacement ne contient pas le motif d’origine.
CITE_VO_ERRATA = {
    8: (('ajoutez 1 points de CHANCE', 'ajoutez 2 points de CHANCE'),),
    37: (('Ajoutez deux points\nD’ENDURANCE', 'Ajoutez deux points\nde CHANCE'),),
    137: (('également 2\npoints D’ENDURANCE', 'également 2\npoints de CHANCE'),),
}

# Coquilles de reconnaissance relevées paragraphe par paragraphe dans l’édition
# identifiée. Chaque remplacement est borné à son passage et ne touche ni un
# renvoi, ni une caractéristique ; le seul nombre rétabli (§342) est un prix
# lu « I » au lieu de « 1 ». Le texte de remplacement ne contient jamais le
# motif d’origine : une seconde passe ne modifie rien.
CITE_TYPOGRAPHY = {
    1: (('.moindre', 'rejoindre'), ('célebre', 'célèbre'), ('l\'échiné', 'l\'échine'),
        ('collines;', 'collines ;'), ('le- groupe', 'le groupe'), ('affronter du garde', 'affronter un garde')),
    3: (('lu somme', 'la somme'),),
    5: (('lirant votre', 'Tirant votre'),),
    8: (('dfl votre', 'de votre'),),
    9: (('dfl Zanbar', 'de Zanbar'), ('sa poi\ntrine', 'sa\npoitrine'),
        ('Hypnotis par', 'Hypnotisé par'), ('vous fui rapidement', 'vous fuit rapidement')),
    11: (('en train de luire', 'en train de faire'),
         ('contraint il abandonner', 'contraint d\'abandonner')),
    12: (('un nomme', 'un homme'),),
    17: (('homme! vêtu', 'homme vêtu'),),
    19: (('poison.Vous', 'poison. Vous'),),
    20: (('d\'entre-  j prendre', 'd\'entreprendre'),),
    22: (('les ! LUTINS', 'les LUTINS'), ('de | haine', 'de haine')),
    25: (('votre epée', 'votre épée'),),
    33: (('l e garde', 'le garde'),),
    37: (('pouvoir île vous', 'pouvoir de vous'),),
    41: (('vous j pénétrez', 'vous pénétrez'),),
    45: (('I a boule', 'La boule'), ('la l\'orme', 'la forme')),
    62: (('gestes lipides', 'gestes rapides'),),
    63: (('I \'Elfe', 'L\'Elfe'),),
    66: (('vers I ouest', 'vers l\'ouest'),),
    70: (('yeux vert( ', 'yeux verts '),),
    71: (('de rébut', 'de rebut'), ('désire!', 'désirez')),
    74: (('vous constaté', 'vous constatez'), ('sol étroites', 'sont étroites'),
         ('If autres', 'les autres')),
    77: (('uni porte', 'une porte'),),
    78: (('rue lu Sabot', 'rue du Sabot'),),
    81: (('I homme', 'L\'homme'), ('en murant', 'en courant'),
         ('êtes chanceux,', 'êtes Chanceux,')),
    82: (('excité â l', 'excité à l'),),
    88: (('rue de lécurie', 'rue de l\'Écurie'),),
    91: (('rue. 11 est', 'rue. Il est'),),
    99: (('arrestation.\'A votre', 'arrestation. À votre'),),
    101: (('II sourit', 'Il sourit'),),
    108: (('eu dehors', 'au dehors'),),
    109: (('laissez» passer', 'laissez-passer'), ('pour ramas: 5', 'pour ramasser 5')),
    112: (('rue «ont', 'rue sont'), ('et .ombres', 'et sombres'), ('Mors que', 'Alors que')),
    113: (('ne «ont pas', 'ne sont pas'), ('à lait', 'à fait'),
          ('vieilles liâmes', 'vieilles dames')),
    115: (('hommes urinés', 'hommes armés'),),
    116: (('à lu\nporte', 'à la\nporte'),),
    118: (('sorte île cliquetis', 'sorte de cliquetis'),),
    119: (('11 petit garçon', 'Le petit garçon'), ('Il en route 3', 'Il en coûte 3')),
    120: (('pirate ne retourne', 'pirate se retourne'),),
    121: (('I \'Ogre', 'L\'Ogre'), ('II se pourlèche', 'Il se pourlèche')),
    122: (('ha il Ions', 'haillons'),),
    126: (('l,a petite', 'La petite'), ('peau île mouton', 'peau de mouton')),
    130: (('corps île garde', 'corps de garde'),),
    131: (('d\'en lace', 'd\'en face'), ('lors-\ni|n\'une', 'lors-\nqu\'une')),
    132: (('I a créature', 'La créature'), ('quittez lu maison', 'quittez la maison'),
          ('survécu  il\nn\'importe', 'survécu à\nn\'importe')),
    134: (('uni-grosse', 'une grosse'),),
    141: (('d\'etre', 'd\'être'),),
    143: (('continuer  il\nfeindre', 'continuer à\nfeindre'),),
    146: (('Si vous avec', 'Si vous avez'),),
    147: (('ver le\nnord', 'vers le\nnord'),),
    148: (('de» étals', 'des étals'), ('sa m que', 'sans que'), ('de lu foule', 'de la foule')),
    150: (('Si voua', 'Si vous'),),
    151: (('que le vous délivre', 'que je vous délivre'), ('et le vous fais', 'et je vous fais'),
          ('minutes. » le\nvieil', 'minutes. » Le\nvieil'), ('à l extérieur', 'à l\'extérieur'),
          ('les bar-u-aux', 'les barreaux')),
    152: (('luit froid', 'fait froid'),),
    153: (('en lia vers', 'en travers'),),
    156: (('Price de la Nuit', 'Prince de la Nuit'),),
    157: (('lire son épée', 'tire son épée'),),
    158: (('direction.Si', 'direction. Si'),),
    161: (('prêterez', 'préférez'),),
    169: (('colla de mailles', 'cotte de mailles'),),
    170: (('se battra avec', 'se battre avec'), ('ENDURANCH', 'ENDURANCE')),
    176: (('la i ue du', 'la rue du'),),
    180: (('grondement île roues', 'grondement de roues'),
          ('passer II voiture', 'passer la voiture'), ('sur  loi pavés', 'sur les pavés')),
    182: (('de nom veau', 'de nouveau'),),
    189: (('dans M poitrine', 'dans sa poitrine'), ('souffrant» qui', 'souffrance qui'),
          ('de femme» aux', 'de femmes aux'), ('qui la flèche', 'que la flèche')),
    190: (('Losrque', 'Lorsque'),),
    191: (('rue il l\'Écurie', 'rue de l\'Écurie'),),
    195: (('comme is.int envoyé', 'comme ayant envoyé'),),
    198: (('impressionner par', 'impressionnés par'),),
    201: (('pat-les', 'pattes'),),
    203: (('loucher', 'toucher'),),
    239: (('vieillard île tout', 'vieillard de tout'),),
    241: (('pointues el aux', 'pointues et aux'), ('Le fabri quant', 'Le fabricant')),
    250: (('le  résultai d', 'le  résultat d'), ('arnica lement', 'amicalement')),
    254: (('odeur acre', 'odeur âcre'),),
    259: (('vous ave/ un', 'vous avez un'),),
    260: (('nu cas', 'au cas'),),
    261: (('« titrer dans la\nville', 'entrer dans la\nville'),),
    262: (('I )\'un revers', 'D\'un revers'),),
    265: (('sang do Rats', 'sang des Rats'),),
    267: (('troisième <ln regard', 'troisième du regard'),),
    270: (('d\'un I ROLL', 'd\'un TROLL'),),
    271: (('refermer lu porte', 'refermer la porte'),),
    272: (('préféréz', 'préférez'),),
    273: (('Qu\'ai\nlez-vous', 'Qu\'al\nlez-vous'),),
    274: (('par lu rue', 'par la rue'),),
    276: (('entre  i dans', 'entrer dans'),),
    294: (('vous désire/', 'vous désirez'),),
    316: (('Vitte-tin', 'Vittetin'),),
    326: (('vous entende/', 'vous entendez'),),
    329: (('Bonc.', 'Bone.'), ('Nico-dème', 'Nicodème'),
          ('marches el traversez', 'marches et traversez')),
    334: (('vous cl demandent', 'vous et demandent'),),
    339: (('clef cl vous', 'clef et vous'),),
    342: (('moyennant I Pièce', 'moyennant 1 Pièce'),),
    345: (('du poinj1,', 'du poing'),),
    348: (('vous\ndistingue/', 'vous\ndistinguez'),),
    376: (('d\'Aï-taque', 'd\'Attaque'),),
}


def repair_cite_ocr(paragraphs):
    """Corriger les renvois et coquilles de reconnaissance de la Cité des Voleurs.

    Le registre réserve cette opération au SHA-256 du PDF catalogué. Seuls des
    caractères mal reconnus sont remplacés ; aucun passage n'est ajouté. Un
    paragraphe déjà corrigé ou absent reste inchangé.
    """
    for number, (pattern, _target) in CITE_BROKEN_ROUTES.items():
        if number in paragraphs:
            paragraphs[number] = re.sub(pattern, r'\1au\2', paragraphs[number])
    for number, (old, new) in CITE_ROUTE_ERRATA.items():
        if number in paragraphs:
            paragraphs[number] = paragraphs[number].replace(old, new)
    for number, text in paragraphs.items():
        # « ŕ » n'existe pas en français : c'est le tiret long de l'édition.
        text = text.replace('ŕ', '—').replace('HABiLETÉ', 'HABILETÉ')
        for old, new in CITE_TYPOGRAPHY.get(number, ()) + CITE_VO_ERRATA.get(number, ()):
            text = text.replace(old, new)
        paragraphs[number] = text
