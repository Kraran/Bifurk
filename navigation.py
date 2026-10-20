"""Repérage prudent des destinations de paragraphes dans les PDF français."""
import re
import html

# La coupure « rendez-\n vous » est fréquente dans les PDF de livres-jeux.
DESTINATION_RE = re.compile(
    r"(?i)(?:"
    r"rendez\s*[-‐‑–]?\s*vous(?:\s+(?:alors|dans\s+ce\s+cas|directement|maintenant|après))?"
    r"|(?:vous\s+)?(?:irez|allez|allez-vous|aller)(?:\s+(?:alors|dans\s+ce\s+cas))?"
    r"|reportez\s*[-‐‑–]?\s*vous(?:\s+alors)?"
    r"|(?:en\s+)?vous\s+rendant"
    r"|en\s+allant"
    r"|(?:vous\s+)?(?:rendre|rendez|aller|allez)(?:\s+(?:alors|dans\s+ce\s+cas))?"
    r")\s+(?:au|à|a)\s*(?:paragraphe\s*)?(?P<target>\d{1,3})\b"
)

def destinations(text):
    """Retourne (début, fin, numéro) pour chaque renvoi explicite."""
    return [(m.start(), m.end(), int(m.group('target'))) for m in DESTINATION_RE.finditer(text)]

def render_links(text, available):
    """Échappe le texte avant de créer des liens uniquement vers les sections existantes."""
    pieces = []
    last = 0
    for m in DESTINATION_RE.finditer(text):
        pieces.append(html.escape(text[last:m.start()]))
        target = int(m.group('target'))
        if target in available:
            pieces.append(html.escape(text[m.start():m.start('target')]) +
                          f'<a href="paragraph:{target}" style="color:#123f70; text-decoration:underline; font-weight:bold;">{target}</a>')
        else:
            pieces.append(html.escape(m.group(0)))
        last = m.end()
    pieces.append(html.escape(text[last:]))
    return ''.join(pieces).replace('\n', '</p><p>')
