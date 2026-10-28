"""Ambiance sonore selon le paragraphe : zones avec exceptions, livre par livre.

Le catalogue « ambiences » d'un module (catalogues/ambiances_<livre>.json) répartit
tous les paragraphes en zones : chaque paragraphe appartient à exactement une zone,
qui lui donne une scène de sound_effects.SCENES. Une exception remplace la scène de
sa zone pour quelques paragraphes (une taverne dans les galeries…) ; une exception
sans scène (null) garde celle du paragraphe d'où l'on vient (monstre errant,
renvoi « notez ce numéro »…). Statut « proposé » (déduit du texte, pas encore relu)
ou « vérifié » (relu) : les deux sont joués, la page de relecture les distingue.

Ce module ne dépend pas de Qt ; il ne décide que de la scène, jamais de la partie."""

KEEP = object()        # Scène du paragraphe précédent conservée.
STATUSES = ('proposé', 'vérifié')


def parse_paragraphs(spec, count):
    """Liste de numéros et d'intervalles « a-b » → ensemble, bornes 1..count vérifiées."""
    if not isinstance(spec, list) or not spec:
        raise ValueError('Liste de paragraphes vide ou invalide.')
    numbers = set()
    for item in spec:
        if type(item) is int:
            low = high = item
        elif isinstance(item, str) and item.count('-') == 1:
            low, high = (int(part) for part in item.split('-'))
        else:
            raise ValueError(f'Paragraphe invalide : {item!r}.')
        if not 1 <= low <= high <= count:
            raise ValueError(f'Paragraphe hors du livre : {item!r}.')
        span = set(range(low, high + 1))
        if numbers & span:
            raise ValueError(f'Paragraphe répété : {item!r}.')
        numbers |= span
    return numbers


class AmbienceMap:
    """Scène de chaque paragraphe d'un livre, validée à la construction."""

    def __init__(self, data, paragraph_count, scenes):
        if data.get('schema_version') != 1:
            raise ValueError('Schéma de catalogue d’ambiances non pris en charge.')
        self.zones, self.exceptions = [], []
        self._scene = {}
        self._zone = {}
        for zone in data['zones']:
            self._check(zone, scenes, allow_keep=False)
            numbers = parse_paragraphs(zone['paragraphs'], paragraph_count)
            if numbers & self._zone.keys():
                raise ValueError(f"Paragraphes dans deux zones : {zone['label']}.")
            self.zones.append((zone, numbers))
            for number in numbers:
                self._zone[number] = zone
                self._scene[number] = zone['scene']
        if len(self._zone) != paragraph_count:
            missing = sorted(set(range(1, paragraph_count + 1)) - self._zone.keys())
            raise ValueError(f'Paragraphes sans zone : {missing[:10]}.')
        changed = set()
        for exception in data.get('exceptions', []):
            self._check(exception, scenes, allow_keep=True)
            numbers = parse_paragraphs(exception['paragraphs'], paragraph_count)
            if numbers & changed:
                raise ValueError(f"Paragraphes dans deux exceptions : {exception['label']}.")
            changed |= numbers
            self.exceptions.append((exception, numbers))
            for number in numbers:
                self._scene[number] = KEEP if exception['scene'] is None else exception['scene']

    @staticmethod
    def _check(entry, scenes, *, allow_keep):
        label = entry.get('label')
        if not isinstance(label, str) or not label.strip():
            raise ValueError('Zone ou exception sans libellé.')
        scene = entry.get('scene')
        if not (scene in scenes or (allow_keep and scene is None and 'scene' in entry)):
            raise ValueError(f'Scène inconnue pour « {label} » : {scene!r}.')
        if entry.get('status') not in STATUSES:
            raise ValueError(f'Statut inconnu pour « {label} ».')

    @classmethod
    def from_module(cls, module, scenes=None):
        """Carte du module, ou None s'il ne livre pas de catalogue d'ambiances."""
        data = module.catalogue('ambiences') if module is not None else None
        if data is None:
            return None
        if scenes is None:
            from sound_effects import SCENES as scenes
        return cls(data, module.paragraph_count, scenes)

    def scene_for(self, number):
        """Scène du paragraphe, KEEP pour garder la précédente, None hors du livre."""
        return self._scene.get(number)

    def zone_for(self, number):
        return self._zone.get(number)
