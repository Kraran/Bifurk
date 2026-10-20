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
            if character.get("equipped_weapon") == effect["name"]:
                character["equipped_weapon"] = next(
                    (name for name in ("Épée magique", "Épée") if name in inventory), None)
        elif effect["kind"] == "locked_item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] not in inventory:
                inventory.append(effect["name"])
            locked = character.setdefault("locked_items", [])
            if effect["name"] not in locked:
                locked.append(effect["name"])
        elif effect["kind"] == "activate_magic_sword":
            character["equipped_weapon"] = "Épée magique"
            character["magic_sword_bonus_active"] = True
        elif effect["kind"] == "equip_weapon":
            # L'effet de changement d'arme doit être la dernière étape.
            equip_weapon(character, effect["name"])
        elif effect["kind"] == "item":
            inventory = character.setdefault("inventory", [])
            if effect["name"] not in inventory:
                inventory.append(effect["name"])
        else:
            raise ValueError("Effet inconnu : " + str(effect["kind"]))



WEAPON_BONUSES = {
    "Épée": 0,
    "Épée magique": 2,
    "Épée trouvée dans la rivière": 1,
}


def equipped_weapon(character):
    """Anciennes sauvegardes : choisir l'épée disponible la plus appropriée."""
    inventory = character.get("inventory", [])
    selected = character.get("equipped_weapon")
    if selected in inventory and selected in WEAPON_BONUSES:
        return selected
    return next((name for name in ("Épée magique", "Épée", "Épée trouvée dans la rivière")
                 if name in inventory), None)


def equip_weapon(character, name):
    """Change d'arme ; seul le bonus de l'épée magique altère la fiche.

    Le bonus de l'épée de la rivière n'agit que sur la force d'attaque.
    Aucun objet n'est créé par l'équipement et un objet absent est refusé.
    """
    if name not in WEAPON_BONUSES or name not in character.get("inventory", []):
        return False
    old = equipped_weapon(character)
    if old == name:
        character["equipped_weapon"] = name
        return False
    magic_active = bool(character.get("magic_sword_bonus_active", old == "Épée magique"))
    if magic_active and name != "Épée magique":
        character.setdefault("initial", {})["habilete"] = max(
            0, int(character["initial"]["habilete"]) - 2)
        character["habilete"] = max(0, int(character["habilete"]) - 2)
        character["magic_sword_bonus_active"] = False
    elif name == "Épée magique" and not magic_active:
        character.setdefault("initial", {})["habilete"] = int(
            character["initial"]["habilete"]) + 2
        character["habilete"] = min(
            character["initial"]["habilete"], int(character["habilete"]) + 2)
        character["magic_sword_bonus_active"] = True
    character["equipped_weapon"] = name
    return True


def combat_skill(character):
    """Habileté de combat effective, sans modifier l'Habileté de la fiche."""
    bonus = 1 if equipped_weapon(character) == "Épée trouvée dans la rivière" else 0
    return int(character["habilete"]) + bonus



SHIELD_NAME = "Bouclier au croissant"


def take_moon_shield(character, discarded_item):
    """Le §155 impose l'abandon d'un objet non maudit avant acquisition."""
    inventory = character.setdefault("inventory", [])
    if (SHIELD_NAME in inventory or discarded_item == SHIELD_NAME
            or discarded_item not in inventory
            or discarded_item in character.get("locked_items", [])):
        return False
    inventory.remove(discarded_item)
    if character.get("equipped_weapon") == discarded_item:
        if character.get("magic_sword_bonus_active") and discarded_item == "Épée magique":
            character["initial"]["habilete"] = max(0, character["initial"]["habilete"] - 2)
            character["habilete"] = max(0, character["habilete"] - 2)
            character["magic_sword_bonus_active"] = False
        character["equipped_weapon"] = None
    inventory.append(SHIELD_NAME)
    character["shield_equipped"] = True
    return True


def shield_damage(damage, shield_roll):
    """Le bouclier §155 réduit une blessure de 1 sur un 6 (2→1, 1→0)."""
    if not 1 <= shield_roll <= 6:
        raise ValueError("Le bouclier exige un dé à six faces")
    return max(0, damage - 1) if shield_roll == 6 else damage




def piranha_stamina(crocodile_wounded, die=None):
    """§350 : 5 Endurance si les Piranhas attaquent le héros, sinon 1.

    Un Crocodile blessé détourne toujours le gros du banc de Piranhas.
    S'il est indemne, les résultats 1–2 ciblent le héros, 3–6 le reptile.
    """
    if crocodile_wounded:
        return 1
    if die is None:
        raise ValueError("Le §350 demande un dé si le Crocodile est indemne")
    if not 1 <= die <= 6:
        raise ValueError("Le §350 exige un dé à six faces")
    return 5 if die <= 2 else 1


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
