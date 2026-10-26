"""Marques de la fiche : ce qu'un module expose à côté du nom de l'aventurier.

Une marque n'est pas un objet : elle ne va pas dans le sac à dos. Le module
fournit sa description et son dessin ; la fiche ne fait que l'afficher.
"""
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SheetMark:
    """key : identifiant stable ; paint(painter, QRectF) dessine l'emblème dans le cadre."""
    key: str
    title: str
    tooltip: str
    paint: Callable
