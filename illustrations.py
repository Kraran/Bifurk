"""Catalogue des illustrations: pas d'OCR au lancement, pas d'images distribuées."""
import hashlib
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "catalogues" / "sorcier_montagne_feu_1982.json"

def catalogue_for_pdf(pdf_path):
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    path = Path(pdf_path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return data if digest.hexdigest() == data["pdf_sha256"] else None

def images_for_paragraph(catalogue, paragraph):
    return [im for im in catalogue.get("illustrations", [])
            if im.get("statut") in ("verifie", "verifie_position", "verifie_utilisateur", "probable", "verifie_legende", "a_confirmer") and paragraph in im.get("paragraphes", [])]

def cover(catalogue):
    return next((im for im in catalogue.get("illustrations", []) if im["type"] == "couverture"), None)
