"""Sélection des cadrages d'illustrations pour une édition exacte du PDF.

Le catalogue décrit des pages physiques (base 1) et rectangles PyMuPDF ; les pixels
restent dans le PDF privé. Le SHA-256 empêche d'appliquer ces coordonnées à une
autre édition. Les associations peuvent porter des degrés de certitude différents,
conservés pour l'affichage ; elles ne représentent pas des règles de jeu."""
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "catalogues" / "sorcier_montagne_feu_1982.json"

def catalogue_for_pdf(pdf_path):
    """Charger les cadrages seulement si le SHA-256 du PDF correspond au catalogue livré."""
    from grimoire_modules.registry import module_for_pdf
    module = module_for_pdf(pdf_path)
    return module.catalogue('illustrations') if module else None

def images_for_paragraph(catalogue, paragraph):
    """Sélectionner les associations du paragraphe avec les statuts d’illustration acceptés."""
    return [im for im in catalogue.get("illustrations", [])
            if im.get("statut") in ("verifie", "verifie_position", "verifie_utilisateur", "probable", "verifie_legende", "a_confirmer") and paragraph in im.get("paragraphes", [])]

def cover(catalogue):
    """Retourner la première entrée de type couverture, ou None en son absence."""
    return next((im for im in catalogue.get("illustrations", []) if im["type"] == "couverture"), None)
