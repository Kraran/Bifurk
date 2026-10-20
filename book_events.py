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


def apply_entry(character, completed, paragraph, catalogue):
    """Applique une seule fois les effets obligatoires vérifiés.

    completed et character font partie de l'état de partie : annuler / sauvegarder
    doit donc les restaurer ensemble. Ne traite pas les choix et combats spéciaux.
    """
    entry = verified_entry(catalogue, paragraph)
    if not entry or entry["mode"] != "automatique" or paragraph in completed:
        return False
    for effect in entry["effects"]:
        if effect["kind"] == "stat":
            key = effect["key"]
            amount = int(effect["amount"])
            value = max(0, int(character.get(key, 0)) + amount)
            if key in ("endurance", "habilete", "chance"):
                cap = int(character.get("initial", {}).get(key, value))
                value = min(value, cap)
            character[key] = value
        elif effect["kind"] == "item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] not in inventory:
                inventory.append(effect["name"])
        else:
            raise ValueError("Effet inconnu : " + str(effect["kind"]))
    completed.add(paragraph)
    return True
