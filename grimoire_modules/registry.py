"""Reconnaître une édition et charger ensemble ses ressources vérifiées.

Les manifestes JSON sont livrés dans catalogues/modules, déjà inclus dans le
paquet Windows. Ils ne contiennent ni PDF ni code exécutable. Aucun nom de livre,
nom de fichier PDF ou numéro de paragraphe ne suffit à reconnaître une édition.
Une instance est créée par ouverture : aucun catalogue mutable n'est partagé
entre deux parties et aucun cache de chemin ne masque le remplacement d'un PDF.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

CATALOGUES = Path(__file__).resolve().parent.parent / 'catalogues'
SUPPORTED_ENGINES = {'sorcier-1982', 'foret-1983', 'cite-1983'}
SUPPORTED_REPAIRS = {'misplaced-fragment-253', 'foret-confirmed-186-267', 'cite-ocr-1983'}


def pdf_digest(path):
    """Calculer l'empreinte en flux, sans conserver le livre en mémoire."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@dataclass(frozen=True)
class GrimoireModule:
    """Identité d'édition et configuration ; les catalogues sont lus à la demande."""
    id: str
    title: str
    engine: str
    pdf_sha256: str
    paragraph_count: int
    rules_pages: tuple
    catalogue_paths: tuple
    text_repairs: tuple
    intro_pages: tuple = ()
    intro_title: str = ''
    status: str = 'ready'
    starting_gold: int | None = None
    starting_items: tuple = ()

    def catalogue(self, kind):
        """Refuser un catalogue d'une autre édition, même si le manifeste le désigne."""
        path = dict(self.catalogue_paths).get(kind)
        if path is None:
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('pdf_sha256') != self.pdf_sha256:
            raise ValueError(f'Catalogue {kind} incompatible avec le module {self.id}.')
        return data

    def repair_paragraphs(self, paragraphs):
        """Appliquer uniquement les réparations explicitement prévues pour cette édition."""
        if 'misplaced-fragment-253' in self.text_repairs:
            from pdf_text_repairs import repair_misplaced_fragment
            repair_misplaced_fragment(paragraphs)
        if 'foret-confirmed-186-267' in self.text_repairs:
            from pdf_text_repairs import repair_foret_confirmed_errata
            repair_foret_confirmed_errata(paragraphs)
        if 'cite-ocr-1983' in self.text_repairs:
            from pdf_text_repairs import repair_cite_ocr
            repair_cite_ocr(paragraphs)


# Registres déjà validés, indexés par dossier et par signature (nom, taille, date)
# de chaque JSON du dossier : modifier, ajouter ou retirer un manifeste ou un
# catalogue invalide l'entrée. Les modules sont immuables et relisent leurs
# catalogues à la demande : partager le tuple ne partage aucun état de partie.
_MODULES_CACHE = {}


def _catalogue_signature(root):
    """Empreinte légère des JSON du registre, sans relire leur contenu."""
    signature = []
    for path in sorted(root.rglob('*.json')):
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def available_modules(catalogue_root=None):
    """Registre validé, relu seulement si un JSON du dossier a changé.

    La validation complète (manifestes et catalogues) ne tourne qu'une fois par
    état du dossier ; une erreur n'est jamais mise en cache."""
    root = Path(catalogue_root or CATALOGUES).resolve()
    signature = _catalogue_signature(root)
    cached = _MODULES_CACHE.get(root)
    if cached is not None and cached[0] == signature:
        return cached[1]
    modules = _read_modules(root)
    _MODULES_CACHE[root] = (signature, modules)
    return modules


def _read_modules(root):
    """Lire et valider le registre ; les doublons sont des erreurs de distribution.

    Le moteur est une capacité du programme, jamais un import Python arbitraire
    issu du JSON. Un prochain livre doit livrer son adaptateur et ses tests avant
    d'être déclaré compatible. Le dossier injecté facilite les tests hors PDF privé.
    """
    modules, ids, digests = [], set(), set()
    for path in sorted((root / 'modules').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1:
            raise ValueError(f'Schéma de module non pris en charge : {path.name}.')
        identity, digest = data['id'], data['pdf_sha256']
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError('Identifiant de module vide ou dupliqué.')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or digest in digests:
            raise ValueError('Empreinte PDF invalide ou dupliquée.')
        if data['engine'] not in SUPPORTED_ENGINES:
            raise ValueError(f"Moteur de règles non pris en charge : {data['engine']}.")
        pages = data['rules_pages']
        if not isinstance(pages, list) or len(pages) != 2 or any(type(n) is not int for n in pages) or not 1 <= pages[0] <= pages[1]:
            raise ValueError('Intervalle de pages de règles invalide.')
        if type(data['paragraph_count']) is not int or data['paragraph_count'] < 1:
            raise ValueError('Nombre de paragraphes invalide.')
        repairs = data.get('text_repairs', [])
        if not isinstance(repairs, list) or any(r not in SUPPORTED_REPAIRS for r in repairs):
            raise ValueError('Réparation de texte inconnue.')
        paths = []
        for kind, reference in data['catalogues'].items():
            candidate = (root / reference).resolve()
            if Path(reference).is_absolute() or not candidate.is_relative_to(root) or not candidate.is_file():
                raise ValueError(f'Ressource de module introuvable ou hors catalogues : {reference}.')
            paths.append((kind, candidate))
        if not {'events', 'illustrations'} <= dict(paths).keys():
            raise ValueError('Catalogues événements et illustrations requis.')
        intro = data.get('intro_pages', [])
        if not isinstance(intro, list) or (intro and (len(intro) != 2
                      or any(type(n) is not int for n in intro) or not 1 <= intro[0] <= intro[1])):
            raise ValueError('Intervalle de prologue invalide.')
        title, intro_title = data.get('title'), data.get('intro_title', '')
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Titre du grimoire invalide.')
        if not isinstance(intro_title, str) or (intro and not intro_title.strip()):
            raise ValueError('Titre du prologue invalide.')
        status = data.get('status', 'ready')
        if status not in ('ready', 'preview'):
            raise ValueError('État de module inconnu.')
        gold = data.get('starting_gold')
        items = data.get('starting_items', [])
        if gold is not None and (type(gold) is not int or gold < 0):
            raise ValueError('Or initial invalide.')
        if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError('Objets initiaux invalides.')
        module = GrimoireModule(identity, data['title'], data['engine'], digest,
                                data['paragraph_count'], tuple(pages), tuple(paths), tuple(repairs),
                                tuple(intro), data.get('intro_title', ''), status, gold, tuple(items))
        # Contrôler toutes les associations avant de publier le module au lecteur.
        module.catalogue('events')
        module.catalogue('illustrations')
        modules.append(module)
        ids.add(identity)
        digests.add(digest)
    return tuple(modules)


def module_for_pdf(pdf_path, *, catalogue_root=None, digest=None):
    """Retourner le module exact ou None : un livre inconnu ne reçoit aucune base connue.

    digest évite de relire le PDF quand l'appelant vient d'en calculer l'empreinte."""
    if not pdf_path or not Path(pdf_path).is_file():
        return None
    if digest is None:
        digest = pdf_digest(pdf_path)
    return next((module for module in available_modules(catalogue_root)
                 if module.pdf_sha256 == digest), None)
