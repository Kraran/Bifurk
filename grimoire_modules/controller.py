"""Pont entre les commandes Qt stables et le contrôleur du livre ouvert.

MainWindow conserve les transactions, les widgets et les jets ; le contrôleur
sélectionné fournit les règles particulières. Aucun état de partie n'est stocké
sur une classe du registre. Les commandes sont déléguées à chaque appel, donc
changer de livre ne laisse pas de méthodes liées à l'ancien module.
"""
from functools import wraps
from .sorcier.actions import BookActions
from .sorcier.controller import SorcierCombatActions


class SorcierController(BookActions, SorcierCombatActions):
    """Adaptateur du Sorcier : interactions spéciales, combats et objets de l'édition."""


CONTROLLERS = {'sorcier-1982': SorcierController}


class ModuleActions:
    """Interface des commandes de livre appelée par le lecteur et la fenêtre de combat."""


def _delegate(name, original):
    @wraps(original)
    def invoke(owner, *args, **kwargs):
        module = getattr(owner, 'book_module', None)
        # Le mode PDF non reconnu conserve les commandes manuelles existantes.
        # Les automatismes exigent toujours une entrée de catalogue vérifiée.
        engine = module.engine if module else 'sorcier-1982'
        controller = CONTROLLERS.get(engine)
        if controller is None:
            raise ValueError(f'Moteur de règles indisponible : {engine}.')
        return getattr(controller, name)(owner, *args, **kwargs)
    return invoke


# Les noms restent stables pour les signaux Qt, l'historique et les sauvegardes.
# Un nouvel adaptateur implémente cette interface ou hérite d'un socle compatible.
for _base in (BookActions, SorcierCombatActions):
    for _name, _method in vars(_base).items():
        if callable(_method) and not _name.startswith('__'):
            setattr(ModuleActions, _name, _delegate(_name, _method))
