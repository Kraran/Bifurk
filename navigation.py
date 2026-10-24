"""Renvois explicites des PDF français et production sûre de liens HTML.

Les positions retournées par destinations concernent le texte d'entrée inchangé.
Un nombre isolé n'est pas une destination. render_links échappe le texte narratif
avant de produire des ancres paragraph:N ; le contrôleur vérifie ensuite les règles
et droits de passage, ce module ne décide pas si une route est franchissable."""
import re
import html

# La coupure « rendez-\n vous » est fréquente dans les PDF de livres-jeux.
DESTINATION_RE = re.compile(
    r"(?i)(?:"
    r"rendez\s*[-‐‑–]?\s*vous(?:\s+(?:alors|ensuite|dans\s+ce\s+cas|directement|maintenant|après))?"
    r"|(?:vous\s+)?(?:irez|allez|allez-vous|aller)(?:\s+(?:alors|dans\s+ce\s+cas))?"
    r"|(?:vous\s+)?vous\s+rendrez(?:\s+(?:alors|ensuite))?"
    r"|reportez\s*[-‐‑–]?\s*vous(?:\s+alors)?"
    r"|(?:en\s+)?vous\s+rendant"
    r"|en\s+allant"
    r"|(?:vous\s+)?(?:rendre|rendez|aller|allez)(?:\s+(?:alors|dans\s+ce\s+cas))?"
    r")\s+(?:au|à|a)\s*(?:paragraphe\s*)?(?P<target>\d{1,3})(?!\d)"
)

def destinations(text):
    """Retourne (début, fin, numéro) pour chaque renvoi explicite."""
    return [(m.start(), m.end(), int(m.group('target'))) for m in DESTINATION_RE.finditer(text)]


def choice_caption(label, target):
    """Keep the action separate from the single destination reference."""
    label = ' '.join(label.split()).strip()
    if re.fullmatch(r'(?i)(?:continuer|aller|poursuivre)(?:\s+vers|\s+au)?\s*'
                    r'(?:le\s+)?(?:paragraphe\s*|§\s*)?\d+', label):
        label = 'Poursuivre le chemin'
    else:
        label = re.sub(r'\s*(?:[→—–-]\s*)?(?:§\s*|paragraphe\s+)\d+\s*$', '',
                       label, flags=re.I).strip()
    return f'{label or "Poursuivre le chemin"}  →  §{target}'

def render_links(text, available, link_color="#123f70"):
    """Échappe le texte avant de créer des liens uniquement vers les sections existantes."""
    pieces = []
    last = 0
    for m in DESTINATION_RE.finditer(text):
        pieces.append(html.escape(text[last:m.start()]))
        target = int(m.group('target'))
        if target in available:
            pieces.append(html.escape(text[m.start():m.start('target')]) +
                          f'<a href="paragraph:{target}" style="color:{link_color}; text-decoration:underline; font-weight:bold;">{target}</a>')
        else:
            pieces.append(html.escape(m.group(0)))
        last = m.end()
    pieces.append(html.escape(text[last:]))
    return ''.join(pieces).replace('\n', '</p><p>')
