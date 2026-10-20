"""Actions vérifiées pour une édition précise ; aucun texte du livre n'est embarqué."""
import hashlib
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "catalogues" / "evenements_sorcier_1982.json"


def load_book_events(pdf_path):
    """Ne jamais appliquer des événements à une édition différente."""
    if not pdf_path or not Path(pdf_path).is_file() or not DATA_PATH.is_file():
        return None
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    with Path(pdf_path).open("rb") as book:
        for block in iter(lambda: book.read(1024 * 1024), b""):
            digest.update(block)
    return data if digest.hexdigest() == data["pdf_sha256"] else None


def verified_entry(catalogue, paragraph):
    if not catalogue:
        return None
    entry = catalogue["paragraphs"].get(str(paragraph))
    return entry if entry and entry["status"] == "verifie" else None


def apply_effects(character, effects):
    """Applique des changements de caractéristiques bornés et des objets uniques."""
    for effect in effects:
        if effect["kind"] == "stat":
            key = effect["key"]
            amount = int(effect["amount"])
            value = max(0, int(character.get(key, 0)) + amount)
            if key in ("endurance", "habilete", "chance"):
                cap = int(character.get("initial", {}).get(key, value))
                value = min(value, cap)
            character[key] = value
        elif effect["kind"] == "restore_floor":
            key = effect["key"]
            initial = int(character.get("initial", {}).get(key, character.get(key, 0)))
            target = max(0, initial - int(effect["below_initial"]))
            # Restauration sans diminution si le personnage est déjà en meilleure forme.
            character[key] = max(int(character.get(key, 0)), target)
        elif effect["kind"] == "initial_stat":
            key = effect["key"]
            delta = int(effect["amount"])
            current_max = int(character.setdefault("initial", {}).get(key, character.get(key, 0)))
            character["initial"][key] = max(0, current_max + delta)
        elif effect["kind"] == "remove_item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] in character.get("locked_items", []):
                raise ValueError("Objet maudit impossible à retirer : " + effect["name"])
            if effect["name"] not in inventory:
                raise ValueError("Objet requis absent : " + effect["name"])
            inventory.remove(effect["name"])
        elif effect["kind"] == "discard_if_present":
            inventory = character.setdefault("inventory", [])
            if effect["name"] in inventory and effect["name"] not in character.get("locked_items", []):
                inventory.remove(effect["name"])
        elif effect["kind"] == "locked_item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] not in inventory:
                inventory.append(effect["name"])
            locked = character.setdefault("locked_items", [])
            if effect["name"] not in locked:
                locked.append(effect["name"])
        elif effect["kind"] == "item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] not in inventory:
                inventory.append(effect["name"])
        else:
            raise ValueError("Effet inconnu : " + str(effect["kind"]))


def resolve_roll(roll, total, character):
    """Résultat déterministe d'un jet défini dans le catalogue."""
    if not 1 <= roll["dice"] <= 2 or not roll["dice"] <= total <= 6 * roll["dice"]:
        raise ValueError("Jet de dés hors limites")
    for branch in roll["branches"]:
        condition = branch["when"]
        matched = (
            condition == "otherwise"
            or condition == "eq" and total == branch["value"]
            or condition == "even" and total % 2 == 0
            or condition == "lte_stat" and total <= character[branch["key"]]
            or condition == "lte_both" and all(total <= character[k] for k in branch["keys"])
        )
        if matched:
            return branch
    raise ValueError("Aucune issue définie pour ce jet")


def condition_met(character, condition):
    """Condition vérifiée sur les données réelles de l'aventurier."""
    if condition is None:
        return True
    kind = condition["kind"]
    if kind in ("has_item", "missing_item"):
        inventory = {str(item).casefold() for item in character.get("inventory", [])}
        present = condition["name"].casefold() in inventory
        return present if kind == "has_item" else not present
    if kind == "min_stat":
        return int(character.get(condition["key"], 0)) >= int(condition["value"])
    raise ValueError("Condition inconnue : " + str(kind))


def available_options(character, entry, completed_options, paragraph):
    """N'affiche que les actions réellement réalisables et encore disponibles."""
    if not entry:
        return []
    return [o for o in entry.get("options", [])
            if f"{paragraph}:{o['id']}" not in completed_options
            and condition_met(character, o.get("when"))]


def available_routes(character, entry):
    """Retourne les itinéraires légitimes pour l'état actuel du personnage."""
    if not entry:
        return []
    available = []
    for route in entry.get("routes", []):
        if condition_met(character, route.get("when")):
            available.append(route)
    return available


def flee_available(combat, assaults, enemy_endurance, hero_endurance):
    """La fuite n'existe que si le livre la permet et le combat se poursuit."""
    return bool(combat and "escape_target" in combat
                and assaults >= combat.get("escape_after_assaults", 0)
                and enemy_endurance > 0 and hero_endurance > 0)


def escape_damage(chance, dice_total=None):
    """Pénalité normale 2 ; avec Chance : 1 si réussite, 3 si échec.

    Renvoie (dégâts, points de Chance dépensés). La comparaison précède
    la dépense, comme dans les règles de l'édition fournie.
    """
    if dice_total is None:
        return 2, 0
    if not 2 <= dice_total <= 12:
        raise ValueError("Un test de Chance utilise deux dés à six faces")
    return (1 if dice_total <= chance else 3), 1


def apply_option(character, completed_options, paragraph, option_id, catalogue):
    """Exécute au plus une fois un choix facultatif explicitement demandé."""
    entry = verified_entry(catalogue, paragraph)
    if entry is None:
        return False
    option = next((o for o in entry.get("options", []) if o["id"] == option_id), None)
    marker = f"{paragraph}:{option_id}"
    if (option is None or marker in completed_options
            or not condition_met(character, option.get("when"))):
        return False
    # Validation préalable pour ne pas appliquer une fraction d'un choix.
    inventory = list(character.get("inventory", []))
    for effect in option["effects"]:
        if effect["kind"] == "remove_item":
            if (effect["name"] not in inventory
                    or effect["name"] in character.get("locked_items", [])):
                return False
            inventory.remove(effect["name"])
    apply_effects(character, option["effects"])
    completed_options.add(marker)
    return True


def apply_entry(character, completed, paragraph, catalogue):
    """Applique une seule fois les effets obligatoires vérifiés.

    completed et character font partie de l'état de partie : annuler / sauvegarder
    doit donc les restaurer ensemble. Ne traite pas les choix et combats spéciaux.
    """
    entry = verified_entry(catalogue, paragraph)
    if not entry or entry["mode"] != "automatique" or paragraph in completed:
        return False
    apply_effects(character, entry["effects"])
    completed.add(paragraph)
    return True
