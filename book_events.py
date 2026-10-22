"""Règles déterministes du catalogue associé au SHA-256 exact du PDF.

Les fonctions prennent des dictionnaires d'état et ne dépendent pas de Qt.
Les fonctions apply_* et les échanges modifient character en place ; les filtres
et calculs retournent un résultat sans lancer de dés. L'appelant fournit les jets
et regroupe les mutations avec l'historique. Un catalogue absent ou une entrée
non vérifiée ne doit jamais devenir une règle automatique par déduction du texte.
Voir catalogues/README_evenements.md pour le vocabulaire des données."""
import re
# Réexporter les règles communes pour préserver les imports des outils et tests.
from grimoire_modules.fighting_fantasy.rules import flee_available, escape_damage
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "catalogues" / "evenements_sorcier_1982.json"


def load_book_events(pdf_path):
    """Ne jamais appliquer des événements à une édition différente."""
    from grimoire_modules.registry import module_for_pdf
    module = module_for_pdf(pdf_path)
    return module.catalogue('events') if module else None


def verified_entry(catalogue, paragraph):
    """Retourner uniquement une entrée marquée verifie, ou None sans catalogue utilisable."""
    if not catalogue:
        return None
    entry = catalogue["paragraphs"].get(str(paragraph))
    return entry if entry and entry["status"] == "verifie" else None


def apply_effects(character, effects):
    """Appliquer en place la liste ordonnée d’effets déclaratifs.

    Les effets manipulent caractéristiques, objets et faits du héros ; conserver
    l’ordre, notamment pour les plafonds initiaux et les changements d’équipement.
    Le catalogue est une donnée vérifiée, pas un langage Python à évaluer."""
    for effect in effects:
        if effect["kind"] == "fact":
            character.setdefault("book_facts", {})[effect["key"]] = effect.get("value", True)
        elif effect["kind"] == "meal":
            if character.get("provisions", 0) > 0:
                character["provisions"] -= 1
                apply_effects(character, [{"kind": "stat", "key": "endurance", "amount": 4}])
        elif effect["kind"] == "death":
            character["endurance"] = 0
        elif effect["kind"] == "stat":
            key = effect["key"]
            amount = int(effect["amount"])
            value = max(0, int(character.get(key, 0)) + amount)
            if key in ("endurance", "habilete", "chance"):
                cap = int(character.get("initial", {}).get(key, value))
                value = min(value, cap)
            character[key] = value
        elif effect["kind"] == "restore_initial":
            key = effect["key"]
            if key not in ("habilete", "endurance", "chance"):
                raise ValueError("Caractéristique non restaurable : " + str(key))
            initial = character.get("initial", {})
            if key not in initial:
                raise ValueError("Valeur initiale manquante : " + key)
            character[key] = max(0, int(initial[key]))
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
    "Épée enchantée": 0,  # Son bonus d’Habileté relève du contrôleur de la Forêt.
    "Épée": 0,
    "Épée magique": 2,
    "Épée trouvée dans la rivière": 1,
}


def equipped_weapon(character):
    """Retourner l’arme sélectionnée si elle est présente, sinon choisir une épée disponible.

    Ce repli déduit l’équipement de l’inventaire ; il ne migre pas un fichier de sauvegarde."""
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
    if ("Casque magique" in character.get("inventory", [])
            and character.get("book_facts", {}).get("magic_helmet_equipped")):
        bonus += 1
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



def throw_diversion_item(character, discarded_item=None):
    """§119 : le joueur choisit de jeter un objet OU une pièce d'or."""
    inventory = character.setdefault("inventory", [])
    if discarded_item is None:
        if int(character.get("gold", 0)) < 1:
            return False
        character["gold"] -= 1
        return True
    if (discarded_item not in inventory
            or discarded_item in character.get("locked_items", [])):
        return False
    if character.get("equipped_weapon") == discarded_item:
        if discarded_item == "Épée magique" and character.get("magic_sword_bonus_active"):
            initial = character.setdefault("initial", {})
            initial["habilete"] = max(0, int(initial["habilete"]) - 2)
            character["habilete"] = max(0, int(character["habilete"]) - 2)
            character["magic_sword_bonus_active"] = False
        character["equipped_weapon"] = None
    if discarded_item == SHIELD_NAME:
        character["shield_equipped"] = False
    inventory.remove(discarded_item)
    return True


def trade_inventory_item(character, new_item, discarded_item):
    """Un seul échange, sans abandonner un objet maudit ni créer un doublon."""
    inventory = character.setdefault("inventory", [])
    if (not new_item or new_item in inventory or discarded_item == new_item
            or discarded_item not in inventory
            or discarded_item in character.get("locked_items", [])):
        return False
    # Réutilise la procédure de retrait des armes et du bouclier.
    if character.get("equipped_weapon") == discarded_item:
        if discarded_item == "Épée magique" and character.get("magic_sword_bonus_active"):
            character.setdefault("initial", {})["habilete"] = max(
                0, int(character["initial"]["habilete"]) - 2)
            character["habilete"] = max(0, int(character["habilete"]) - 2)
            character["magic_sword_bonus_active"] = False
        character["equipped_weapon"] = None
    if discarded_item == SHIELD_NAME:
        character["shield_equipped"] = False
    inventory.remove(discarded_item)
    inventory.append(new_item)
    return True


def follow_catalogue_route(character, entry, target):
    """Vérifie et paie une route cataloguée avant toute navigation."""
    route = next((r for r in available_routes(character, entry)
                  if r["target"] == target), None)
    if route is None:
        return False
    for effect in route.get("effects", []):
        if effect["kind"] == "remove_item" and (
                effect["name"] not in character.get("inventory", [])
                or effect["name"] in character.get("locked_items", [])):
            return False
    cost = route.get("cost")
    if cost is not None:
        key, amount = cost["key"], int(cost["amount"])
        if amount < 0 or int(character.get(key, 0)) < amount:
            return False
        character[key] -= amount
    apply_effects(character, route.get("effects", []))
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



def shared_meal(character, restore=2):
    """Repas partagé au §131 : une provision, deux points d'Endurance maximum."""
    if restore != 2 or int(character.get("provisions", 0)) < 1:
        return False
    character["provisions"] -= 1
    apply_effects(character, [
        {"kind": "stat", "key": "endurance", "amount": restore}
    ])
    return True


def enchanted_bench_meal(character):
    """§15 : un repas normal (+4 E), le banc (+2 E et +1 H) et 1 Provision."""
    if int(character.get("provisions", 0)) < 1:
        return False
    character["provisions"] -= 1
    apply_effects(character, [
        {"kind": "stat", "key": "endurance", "amount": 6},
        {"kind": "stat", "key": "habilete", "amount": 1},
    ])
    return True


def resolve_roll(roll, total, character):
    """Choisir la première branche compatible avec le total fourni, sans modifier le héros.

    Valider le domaine des dés avant comparaison. L’appelant applique ensuite les
    effets : un test de Chance doit comparer la valeur avant sa dépense."""
    if not 1 <= roll["dice"] <= 2 or not roll["dice"] <= total <= 6 * roll["dice"]:
        raise ValueError("Jet de dés hors limites")
    for branch in roll["branches"]:
        # L'ordre du JSON est prioritaire : une branche générale « otherwise »
        # doit rester après les cas particuliers, comme dans une suite de if/elif.
        condition = branch["when"]
        matched = (
            condition == "otherwise"
            or condition == "eq" and total == branch["value"]
            or condition == "lte" and total <= branch["value"]
            or condition == "even" and total % 2 == 0
            or condition == "odd" and total % 2 == 1
            or condition == "lte_stat" and total <= character[branch["key"]]
            or condition == "lte_both" and all(total <= character[k] for k in branch["keys"])
        )
        if matched:
            return branch
    raise ValueError("Aucune issue définie pour ce jet")


def condition_met(character, condition):
    """Évaluer sans mutation le vocabulaire des conditions du catalogue.

    None est vrai ; all / any / not composent les tests. Les objets sont comparés
    sans casse et les visites utilisent des clés chaînes. Un type inconnu lève
    ValueError pour révéler une erreur de catalogue plutôt que permettre la route."""
    if condition is None:
        return True
    kind = condition["kind"]
    if kind == "has_weapon":
        return equipped_weapon(character) is not None
    if kind == "min_keys":
        keys = {name.casefold() for name in character.get("inventory", [])
                if re.match(r"^cl[ée]s?\b", name, re.I)}
        return len(keys) >= int(condition["count"])
    if kind in ("all", "any"):
        results = (condition_met(character, c) for c in condition["conditions"])
        return all(results) if kind == "all" else any(results)
    if kind == "not":
        return not condition_met(character, condition["condition"])
    if kind == "fact":
        return character.get("book_facts", {}).get(condition["key"]) == condition.get("value", True)
    if kind == "visit_count":
        count = character.get("book_visits", {}).get(str(condition["paragraph"]), 0)
        return condition.get("min", 0) <= count <= condition.get("max", float("inf"))
    if kind == "silver_weapon":
        return any(name in character.get("inventory", []) for name in (
            "Ciseau à lame d'argent", "Ciseau à lame d’argent", "Arme en argent"))
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
    """Filtrer les itinéraires sur leurs conditions sans payer leurs coûts.

    La validation et le paiement effectifs restent dans follow_catalogue_route ;
    afficher un bouton ne doit pas débiter de ressources."""
    if not entry:
        return []
    available = []
    for route in entry.get("routes", []):
        if condition_met(character, route.get("when")):
            available.append(route)
    return available






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
    if condition_met(character, entry.get("when")):
        apply_effects(character, entry["effects"])
    # L'entrée automatique est résolue même si sa condition n'était pas remplie.
    # Ne pas déplacer ce marqueur dans le if : un retour ne doit pas transformer
    # cet effet d'entrée en récompense réessayable à volonté.
    completed.add(paragraph)
    return True
