"""Suggestions heuristiques extraites du texte d'un livre-jeu français.

Ces expressions régulières reconnaissent adversaires, caractéristiques, objets
et indices de combat. Elles peuvent manquer une formulation ou une condition :
leurs résultats sont des aides à confirmer, pas les règles vérifiées du catalogue.
La normalisation des césures PDF ne modifie jamais le fichier source."""
import re
import unicodedata

STAT = {"HABILETÉ":"habilete", "HABILITÉ":"habilete", "ENDURANCE":"endurance", "CHANCE":"chance"}

def _clean(text):
    """Normaliser espaces, césures et apostrophes pour stabiliser les expressions régulières."""
    text = text.replace("\u00ad", "").replace("\xa0", " ")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return text.replace("’", "'")

def _name(value):
    """Normaliser la casse et les espaces d’un nom détecté pour l’affichage."""
    return re.sub(r"\s+", " ", value).strip(" :-—\n\t").title()

def encounters(text):
    """Repérer les blocs nom / Habileté / Endurance et éliminer en-têtes ou doublons.

    Les bornes rejettent les chiffres manifestement étrangers à un adversaire ;
    le résultat reste une suggestion dont le contexte doit être confirmé."""
    text = _clean(text)
    found=[]; seen=set()
    # Nom / HABILETÉ 7 / ENDURANCE 8, including OCR-like column line wraps.
    patterns = [
        re.compile(r"(?im)^\s*(?P<name>[A-ZÀ-Ÿ][A-ZÀ-Ÿ' -]{2,48}?)\s+(?:HABILETÉ|HABILITÉ)\s*[:：]?\s*(?P<skill>\d{1,2})\s+ENDURANCE\s*[:：]?\s*(?P<stamina>\d{1,3})\b"),
        re.compile(r"(?im)^\s*(?P<name>[A-ZÀ-Ÿ][A-ZÀ-Ÿ' -]{2,48}?)\s*\n\s*(?:HABILETÉ|HABILITÉ)\s*[:：]?\s*(?P<skill>\d{1,2})\s*\n\s*ENDURANCE\s*[:：]?\s*(?P<stamina>\d{1,3})\b"),
        re.compile(r"(?im)^\s*(?P<name>[A-ZÀ-Ÿ][A-ZÀ-Ÿ' -]{2,48}?)\s+(?:HABILETÉ|HABILITÉ)\s*[:：]?\s*(?P<skill>\d{1,2})\s*\n\s*ENDURANCE\s*[:：]?\s*(?P<stamina>\d{1,3})\b"),
        re.compile(r"(?im)^\s*(?P<name>[A-ZÀ-Ÿ][A-ZÀ-Ÿ' -]{2,48}?)\s*\n\s*(?:HABILETÉ|HABILITÉ)\s*[:：]?\s*(?P<skill>\d{1,2})\s+ENDURANCE\s*[:：]?\s*(?P<stamina>\d{1,3})\b"),
        re.compile(r"(?im)^\s*(?P<name>[A-ZÀ-Ÿ][A-ZÀ-Ÿ' -]{2,48}?)\s*\n\s*(?:HABILETÉ|HABILITÉ)\s+ENDURANCE\s*\n\s*(?P<skill>\d{1,2})\s+(?P<stamina>\d{1,3})\s*$"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            name=_name(match.group('name'))
            skill=int(match.group('skill')); stamina=int(match.group('stamina'))
            if name.upper() in ('VOUS','VOTRE','HABILETÉ','HABILITÉ','ENDURANCE') or not 1<=skill<=24 or not 1<=stamina<=99:
                continue
            key=(name.casefold(),skill,stamina)
            if key not in seen:
                seen.add(key); found.append({'name':name,'skill':skill,'stamina':stamina})
    return found

def combat_hints(text):
    """Repérer indices de combat et renvois proches sans appliquer automatiquement une issue."""
    text=_clean(text)
    cues=[]
    for label,pattern in [
        ('Combat annoncé',r"(?i)\b(?:combattez|combat|attaquez|vous attaque|vous devez affronter|vous affrontez|vous battez|livrer bataille)\b"),
        ('Combat successif ou multiple',r"(?i)\b(?:l'un après l'autre|un par un|tour à tour|simultanément|ensemble|deux adversaires|trois adversaires)\b"),
        ('Fuite possible',r"(?i)\b(?:prendre la fuite|vous enfuir|vous pouvez fuir|fuir le combat|prendre vos jambes à votre cou)\b"),
    ]:
        if re.search(pattern,text): cues.append(label)
    exits=[]
    for label,pattern in [
        ('Victoire',r"(?i)(?:si vous (?:êtes )?(?:vainqueur|victorieux)|si vous (?:le|la|les) tuez|si vous remportez le combat|une fois (?:le|la|les) (?:monstre|adversaire)s? vaincu[s]?)\b[^.!?]{0,170}?\b(?:au|à)\s+(\d{1,3})\b"),
        ('Fuite',r"(?i)(?:si vous (?:prenez la fuite|fuyez|vous enfuyez)|pour fuir)\b[^.!?]{0,170}?\b(?:au|à)\s+(\d{1,3})\b"),
    ]:
        for m in re.finditer(pattern,text):
            target=int(m.group(1))
            if (label,target) not in exits: exits.append((label,target))
    return {'cues':cues,'exits':exits}

def stat_events(text):
    """Suggérer gains et pertes explicites en excluant les contextes conditionnels détectés."""
    results=[]
    pattern=re.compile(r"(?i)\b(?:vous\s+)?(perdez|gagnez|prenez|récupérez|ôtez|ajoutez)\s+(\d{1,2})\s+(?:points?\s+d[’']?|points?\s+de\s+)(habileté|habilité|endurance|chance)\b")
    for match in pattern.finditer(text):
        context=text[max(0,match.start()-100):match.start()]
        if re.search(r"(?i)\b(si|lorsque|quand|après|sinon)\b[^.!?\n]{0,100}$",context): continue
        sign=-1 if match.group(1).lower() in ('perdez','ôtez') else 1
        event={'key':STAT[match.group(3).upper()],'amount':sign*int(match.group(2)),'label':f'{match.group(1).capitalize()} {match.group(2)} {match.group(3)}'}
        if event not in results: results.append(event)
    return results

def item_hints(text):
    """Proposer une liste courte de noms d’objets possibles, sans modifier l’inventaire."""
    matches=[]
    for m in re.finditer(r"(?i)\b(?:vous pouvez (?:prendre|ramasser)|vous trouvez|vous découvrez|vous ramassez)\s+((?:une?|la|le|l[’'])\s+[^.,;\n]{2,65})",text):
        name=m.group(1).strip()
        if name not in matches: matches.append(name)
    return matches[:6]
