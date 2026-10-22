"""Audit local du PDF privé et de ses illustrations, avec rapport dans audit-output.

Le script attend un PDF à la racine du dépôt. Les captures peuvent contenir des
pages du livre : les sorties sont privées et ignorées par Git. Cet audit complète
les tests unitaires sans remplacer la vérification humaine des cadrages et règles."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pymupdf as fitz
import main as b
from illustrations import catalogue_for_pdf, images_for_paragraph
from navigation import destinations
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication


def run():
    """Examiner le PDF et produire rapport et planches de contrôle privées sans modifier le livre."""
    app = QApplication.instance() or QApplication([])
    pdf = next(ROOT.glob('*.pdf'))
    out = ROOT / 'audit-output'
    out.mkdir(exist_ok=True)
    paragraphs = b.extract_paragraphs(pdf)
    cat = catalogue_for_pdf(pdf)
    result = {'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'paragraph_count': len(paragraphs),
              'missing': sorted(set(range(1, 401)) - paragraphs.keys()),
              'extra': sorted(paragraphs.keys() - set(range(1, 401))),
              'statuses': dict(Counter(e['statut'] for e in cat['illustrations'])),
              'paragraphs': [], 'images': []}
    for n, text in sorted(paragraphs.items()):
        targets = [target for _, _, target in destinations(text)]
        result['paragraphs'].append({'number': n, 'characters': len(text),
                                     'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                                     'destinations': targets,
                                     'invalid_destinations': [t for t in targets if t not in paragraphs],
                                     'illustrations': [e['id'] for e in images_for_paragraph(cat, n)]})
    with fitz.open(pdf) as doc:
        result['pages'] = len(doc)
        actual = [(i + 1, im) for i, page in enumerate(doc) for im in page.get_image_info()]
        result['raster_occurrences'] = len(actual)
        result['unmatched_rasters'] = []
        for page, im in actual:
            rect = fitz.Rect(im['bbox'])
            if not any(e['page_pdf'] == page and max(abs(a-z) for a,z in zip(e['rect'], rect)) < 3 for e in cat['illustrations']):
                result['unmatched_rasters'].append({'page': page, 'rect': list(rect)})
        for offset in range(0, len(cat['illustrations']), 28):
            sheet = QImage(1200, 1820, QImage.Format_RGB32)
            sheet.fill(QColor('white'))
            painter = QPainter(sheet)
            painter.setFont(QFont('Arial', 9))
            for j, e in enumerate(cat['illustrations'][offset:offset+28]):
                page = doc[e['page_pdf'] - 1]
                rect = fitz.Rect(e['rect'])
                pix = page.get_pixmap(matrix=fitz.Matrix(.35, .35), clip=rect, alpha=False)
                im = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                im = im.scaled(270, 215, b.Qt.KeepAspectRatio, b.Qt.SmoothTransformation)
                x, y = (j % 4)*300, (j // 4)*260
                painter.drawImage(x, y, im)
                painter.drawText(x, y+232, f"{e['id']} / §{','.join(map(str,e['paragraphes'])) or '-'}")
                painter.drawText(x, y+248, e['statut'])
                result['images'].append({'id': e['id'], 'page': e['page_pdf'],
                                         'inside_page': page.rect.contains(rect),
                                         'paragraphs': e['paragraphes'], 'status': e['statut']})
            painter.end()
            sheet.save(str(out / f'planches-privees-{offset//28+1}.png'))
    (out / 'pdf.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('paragraphs','images')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
