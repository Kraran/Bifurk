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


def available_routes(character, entry):
    """Retourne les itinéraires légitimes pour l'état actuel du personnage."""
    if not entry:
        return []
    available = []
    inventory = {str(x).casefold() for x in character.get("inventory", [])}
    for route in entry.get("routes", []):
        condition = route.get("when")
        if condition is None:
            allowed = True
        elif condition["kind"] == "has_item":
            allowed = condition["name"].casefold() in inventory
        elif condition["kind"] == "missing_item":
            allowed = condition["name"].casefold() not in inventory
        elif condition["kind"] == "min_stat":
            allowed = int(character.get(condition["key"], 0)) >= int(condition["value"])
        else:
            raise ValueError("Condition de route inconnue : " + str(condition["kind"]))
        if allowed:
            available.append(route)
    return available


def apply_option(character, completed_options, paragraph, option_id, catalogue):
    """Exécute au plus une fois un choix facultatif explicitement demandé."""
    entry = verified_entry(catalogue, paragraph)
    if entry is None:
        return False
    option = next((o for o in entry.get("options", []) if o["id"] == option_id), None)
    marker = f"{paragraph}:{option_id}"
    if option is None or marker in completed_options:
        return False
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
