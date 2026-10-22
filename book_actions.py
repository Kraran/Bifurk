"""Point d'import historique ; les interactions du Sorcier vivent dans son module.

Conservé pour les outils utilisant BookActions. Le lecteur principal passe par
ModuleActions pour sélectionner le contrôleur de l'aventure ouverte.
"""
from grimoire_modules.sorcier.actions import BookActions

__all__ = ['BookActions']
