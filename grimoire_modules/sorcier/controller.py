"""Contrôleur des combats et objets propres au Sorcier.

Mixin sans état indépendant : la fenêtre fournit widgets, jets, historique et
personnage. Les méthodes restent nommées comme avant afin que les transactions
et leurs tests couvrent exactement les mêmes points d'entrée.
Les numéros 86, 155, 179 et 350 sont propres à ce livre, pas au lecteur PDF.
"""
import re
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox, QInputDialog, QPushButton, QLabel
from navigation import choice_caption
from rules_engine import encounters, combat_hints, stat_events, item_hints
from grimoire_ui import ChoiceCard
from book_events import (verified_entry, apply_effects, apply_entry, available_routes, available_options, combat_skill, escape_damage,
                         piranha_stamina, shield_damage, SHIELD_NAME, take_moon_shield, flee_available, shared_meal,
                         enchanted_bench_meal, trade_inventory_item, throw_diversion_item)


class SorcierCombatActions:
    """Résoudre les particularités de ce livre avec les services du contrôleur hôte."""
    def take_enchanted_meal(self):
        """§15 : une seule restauration enchantée et une seule provision."""
        if self.current_paragraph != 15 or 15 in self.completed_book_events:
            return
        entry = verified_entry(self.book_event_catalogue, 15)
        if not entry or not entry.get("enchanted_meal"):
            return
        if not enchanted_bench_meal(self.character):
            self.rules_log.setText("Pas de Provisions pour le repas au banc.")
            return
        self.completed_book_events.add(15)
        self._refresh_character()
        self.rules_log.setText(
            "Repas au banc : une Provision utilisée ; Endurance +6 et Habileté +1 (plafonds respectés).")
        self._render_choices_and_events(self.paragraphs[15])

    def throw_book_diversion(self):
        """§119 : libre choix entre un objet transporté et une pièce d'or."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if not entry or not entry.get("diversion_discard") or 119 in self.completed_book_events:
            return
        candidates = [name for name in self.character.get("inventory", [])
                      if name not in self.character.get("locked_items", [])]
        gold_available = int(self.character.get("gold", 0)) >= 1
        if not candidates and not gold_available:
            QMessageBox.information(
                self, "Diversion impossible",
                "Il faut un objet abandonnable ou au moins une pièce d'or.")
            return
        if candidates:
            coin_label = "🪙 Jeter une pièce d'or"
            choices = ([coin_label] if gold_available else []) + candidates
            selected, accepted = QInputDialog.getItem(
                self, "Diversion contre l'Ogre", "Que souhaitez-vous jeter ?",
                choices, 0, False)
            if not accepted:
                return
            use_gold = gold_available and selected == coin_label
            discarded = None if use_gold else selected
        else:
            discarded = None
        if not throw_diversion_item(self.character, discarded):
            return
        self.completed_book_events.add(119)
        self._refresh_character()
        self._render_choices_and_events(self.paragraphs[119])
        message = ("Une pièce d'or jetée." if discarded is None
                   else f"Objet jeté : {discarded}.")
        self.rules_log.setText(message + " Vous pouvez repartir vers le §269.")

    def take_book_trade(self, item_id):
        """Échange facultatif : un seul choix par rencontre, abandon réel requis."""
        number = self.current_paragraph
        entry = verified_entry(self.book_event_catalogue, number)
        choice = next((c for c in entry.get("trade_choices", [])
                       if c["id"] == item_id), None) if entry else None
        marker = f"{number}:trade:{item_id}"
        if (choice is None or marker in self.completed_optional_events
                or self.character["endurance"] <= 0
                or any(k.startswith(f"{number}:trade:") for k in self.completed_optional_events)):
            return
        candidates = [name for name in self.character.get("inventory", [])
                      if name not in self.character.get("locked_items", [])
                      and name != choice["name"]]
        if not candidates:
            QMessageBox.information(self, "Échange impossible", "Aucun équipement à abandonner.")
            return
        discarded, accepted = QInputDialog.getItem(
            self, "Échange d'équipement", "Objet à abandonner :", candidates, 0, False)
        if accepted and trade_inventory_item(self.character, choice["name"], discarded):
            apply_effects(self.character, choice.get("extra_effects", []))
            self.completed_optional_events.add(marker)
            self._refresh_character()
            self._render_choices_and_events(self.paragraphs[number])
            self.rules_log.setText(
                f"Objet abandonné : {discarded}. Objet récupéré : {choice['name']}.")

    def _set_book_enemy(self, monster):
        """Initialise un adversaire vérifié sans changer les données du héros."""
        self._remember_monster(monster["name"])
        self.enemy_name.setText(monster["name"])
        self.enemy_skill.setValue(monster["skill"])
        self.enemy_endurance.setValue(monster["stamina"])
        self.combat_state.setText(
            f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")

    def _finish_single_book_combat(self, successful_hit=False):
        """Résout uniquement la sortie confirmée par le catalogue du livre."""
        number = self.current_paragraph
        entry = verified_entry(self.book_event_catalogue, number)
        combat = entry.get("combat", {}) if entry else {}
        if len(combat.get("enemies", [])) != 1 or self.character["endurance"] <= 0:
            return
        if combat.get("mode") == "first_hit":
            if not successful_hit:
                return
            target = combat.get("first_hit_target")
        elif combat.get("mode") in (None, "silver", "ghoul") and self.enemy_endurance.value() <= 0:
            target = combat.get("victory_target")
        elif combat.get("mode") == "fire_breath" and self.enemy_endurance.value() <= 0:
            self._finish_fire_dog(combat)
            return
        else:
            return
        if target is None:
            return
        if combat.get("victory_fact"):
            self.character.setdefault("book_facts", {})[combat["victory_fact"]] = True
        self.prepared_book_encounters.add(number)
        if target in self.paragraphs:
            self.go_to(target)
            self.rules_log.setText(
                f"Combat du §{number} terminé selon le livre : §{target}.")
        else:
            self.rules_log.setText(
                f"Combat du §{number} terminé : ouvrez le §{target}.")

    def _advance_scripted_sequence(self):
        """Après la victoire, prépare le suivant ; à la fin, va à la sortie prescrite."""
        state = self.book_combat_sequence
        if (not state or self.current_paragraph != state["paragraph"]
                or self.enemy_endurance.value() > 0):
            return
        entry = verified_entry(self.book_event_catalogue, state["paragraph"])
        if not entry:
            return
        combat = entry.get("combat", {})
        if combat.get("mode") != "sequence":
            return
        monsters = combat["enemies"]
        apply_effects(self.character, combat.get("stage_effects", {}).get(str(state["index"]), []))
        self._refresh_character()
        index = state["index"] + 1
        if index < len(monsters):
            state["index"] = index
            self._set_book_enemy(monsters[index])
            self.rules_log.setText(
                f"Adversaire vaincu. Combat suivant : {index+1}/{len(monsters)} — {monsters[index]['name']}.")
        else:
            target = combat.get("victory_target")
            self.book_combat_sequence = None
            self.prepared_book_encounters.add(state["paragraph"])
            if target in self.paragraphs:
                self.rules_log.setText(f"Tous les adversaires vaincus. Destination §{target}.")
                self.go_to(target)
            else:
                self.rules_log.setText(
                    f"Tous les adversaires vaincus. Ouvrez manuellement le §{target}.")

    def escape_scripted_combat(self, number):
        """Fuite vérifiée : restriction d'assauts, blessure, Chance puis navigation."""
        if number != self.current_paragraph:
            return
        entry = verified_entry(self.book_event_catalogue, number)
        rules = entry.get("combat", {}) if entry else {}
        target = rules.get("escape_target")
        if (rules.get("mode") == "fire_breath"
                and self.character.get("book_facts", {}).get(rules["victory_fact"])):
            if target in self.paragraphs and self.character["endurance"] > 0:
                self.go_to(target)
            return
        if number == 179 and self.character.get("book_facts", {}).get("minotaur_dead"):
            if target in self.paragraphs:
                self.go_to(target)
            return
        if not self.can_flee_combat():
            return
        if rules.get("escape_luck_interval"):
            self._vampire_escape(rules)
            return
        attempt = self._ask_combat_question(
            "Fuir le combat", "Tenter votre Chance pour la blessure de fuite ?\n"
            "Sans Chance : -2 Endurance. Chance réussie : -1. Échec : -3.")
        rolls = None
        if attempt == QMessageBox.Yes:
            rolls, total = self._roll(2)
        else:
            total = None
        damage, cost = escape_damage(self.character["chance"], total)
        self.character["chance"] = max(0, self.character["chance"] - cost)
        self.character["endurance"] = max(0, self.character["endurance"] - damage)
        if self.character["endurance"] > 0:
            lost = int(rules.get("escape_provisions_lost", 0))
            if lost > 0:
                self.character["provisions"] = max(
                    0, int(self.character.get("provisions", 0)) - lost)
        if self.book_combat_sequence and self.book_combat_sequence["paragraph"] == number:
            self.book_combat_sequence = None
        self._refresh_character()
        if self.character["endurance"] <= 0:
            self.rules_log.setText("La blessure de fuite est mortelle : Endurance à zéro.")
            self._render_choices_and_events(self.paragraphs[number])
            return
        self.go_to(target)
        self.rules_log.setText(
            f"Fuite du §{number} vers le §{target} : -{damage} Endurance"
            + (f", test de Chance {rolls} (Chance -1)." if rolls else "."))

    def choose_crocodile_strategy(self, phase):
        """Enregistrer la phase choisie pour poursuivre le combat limité du Crocodile."""
        state = self.crocodile_combat
        if (not state or self.current_paragraph != 86 or phase not in ("continue", "diversion")
                or state["phase"] != "initial" or state["assaults"] < 2
                or self.enemy_endurance.value() <= 0):
            return
        state["phase"] = phase
        self.rules_log.setText(
            "Continuez jusqu'à la victoire." if phase == "continue"
            else "Un seul assaut supplémentaire, puis destination §350.")
        self._render_choices_and_events(self.paragraphs[86])

    def _prepare_piranhas(self, stamina):
        """Initialiser le banc de Piranhas avec l’Endurance décidée par l’état du Crocodile."""
        if self.current_paragraph != 350 or 350 in self.prepared_book_encounters:
            return
        self.piranha_combat = {"status": "fighting", "stamina": stamina}
        self._set_book_enemy({"name": "Piranhas", "skill": 5, "stamina": stamina})
        self.combat_journal.clear()

    def roll_piranha_target(self):
        """§350 : ne lancer le dé que si le Crocodile est indemne."""
        if (self.current_paragraph != 350 or self.piranha_source_wounded is not False
                or not self.piranha_combat
                or self.piranha_combat.get("status") != "roll_pending"):
            return
        rolls, total = self._roll(1)
        stamina = piranha_stamina(False, total)
        self._prepare_piranhas(stamina)
        self._render_choices_and_events(self.paragraphs[350])
        self.rules_log.setText(
            f"§350 : dé {rolls[0]} ; Piranhas H5/E{stamina}.")

    def _finish_piranha_round(self):
        """Contrôler l’issue du combat des Piranhas et ses commandes après un assaut."""
        if (self.current_paragraph != 350 or not self.piranha_combat
                or self.piranha_combat.get("status") != "fighting"
                or self.enemy_endurance.value() > 0
                or self.character["endurance"] <= 0):
            return
        entry = verified_entry(self.book_event_catalogue, 350)
        combat = entry.get("combat", {}) if entry else {}
        if combat.get("mode") != "piranhas":
            return
        from book_events import apply_effects
        apply_effects(self.character, combat["victory_effects"])
        self.completed_book_events.add(350)
        self._refresh_character()
        self.piranha_combat = {"status": "victory"}
        self.prepared_book_encounters.add(350)
        target = combat["victory_target"]
        if target in self.paragraphs:
            self.go_to(target)
            self.rules_log.setText(
                "Piranhas vaincus : Chance +1 ; §7. Un repas reste facultatif.")
        else:
            self.rules_log.setText(f"Piranhas vaincus : Chance +1. Ouvrez le §{target}.")

    def _finish_crocodile_round(self):
        """Mettre à jour blessures, compteur et phase du combat limité du Crocodile."""
        state = self.crocodile_combat
        if not state or self.current_paragraph != state["paragraph"]:
            return
        entry = verified_entry(self.book_event_catalogue, 86)
        if not entry:
            return
        combat = entry["combat"]
        if self.character["endurance"] <= 0:
            self.rules_log.setText("Votre Endurance est à zéro : l'aventure est terminée.")
            return
        if state["phase"] == "diversion" and state["assaults"] >= 3:
            target = combat["diversion_target"]
        elif self.enemy_endurance.value() <= 0:
            target = combat["continue_target"]
        else:
            self._render_choices_and_events(self.paragraphs[86])
            return
        if target == 350:
            self.piranha_source_wounded = bool(state.get("wounded", False))
        self.crocodile_combat = None
        self.prepared_book_encounters.add(86)
        if target in self.paragraphs:
            self.go_to(target)
            self.rules_log.setText(f"Combat contre le Crocodile terminé : §{target}.")
        else:
            self.rules_log.setText(f"Combat terminé : ouvrez manuellement le §{target}.")

    def combat_round(self):
        """Résoudre un assaut : particularités du livre, jets, Chance éventuelle et dégâts.

        L’ordre souffle / attaques / défense / blessure est significatif. Les décisions
        modales appartiennent à la même action ; les sorties particulières sont terminées
        par le wrapper extérieur pour conserver un seul point d’annulation."""
        self._book_round_played = False
        if self._complex_round_blocked():
            return
        state = self.crocodile_combat
        if (state and self.current_paragraph == state["paragraph"]
                and state["phase"] == "initial" and state["assaults"] >= 2
                and self.enemy_endurance.value() > 0):
            self.rules_log.setText(
                "Après deux assauts contre le Crocodile, choisissez une stratégie dans les événements.")
            return
        if self.enemy_endurance.value() <= 0:
            self.rules_log.setText("Le monstre est déjà vaincu.")
            return
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        combat_rules = entry.get("combat", {}) if entry else {}
        if combat_rules.get("mode") == "fire_breath" and not self._resolve_fire_breath():
            return
        enemy_rolls, enemy_total = self._roll(2, context=f'Combat — {self.enemy_name.text() or "Adversaire"}', opponent=True)
        player_rolls, player_total = self._roll(2, context=f'Combat — {self.character.get("name") or "Votre aventurier"}')
        enemy_attack = self.enemy_skill.value() + enemy_total
        player_attack = combat_skill(self.character) + player_total + combat_rules.get("attack_bonus", 0)
        self.sounds.play("swords")
        if player_attack == enemy_attack:
            self.rules_log.setText(f"Égalité ({player_attack} contre {enemy_attack}) : aucun dégât. Relancez l'assaut.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, "Parade")
            return
        if player_attack > enemy_attack:
            entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
            if entry and entry.get("combat", {}).get("mode") == "invulnerable":
                self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack,
                                  "Arme ordinaire inefficace : aucune blessure au monstre")
                return
            base_damage = combat_rules.get("hit_damage", 2)
            answer = self._assault_luck_choice("Vous touchez !",
                f"Votre force d'attaque {player_attack} dépasse celle du monstre ({enemy_attack}).\nDégâts de base : {base_damage} Endurance au monstre.",
                "Voulez-vous tenter votre Chance pour aggraver la blessure ?")
            damage = base_damage
            if answer == QMessageBox.Yes:
                luck_rolls, luck_total = self._roll(2, context='Chance — Aggraver la blessure')
                was_lucky = luck_total <= self.character["chance"]
                self.character["chance"] = max(0, self.character["chance"] - 1)
                if was_lucky:
                    damage = base_damage + 2
                    luck_text = f"Chance réussie ({luck_total}) : {damage} dégâts au total."
                else:
                    damage = max(0, base_damage - 1)
                    luck_text = f"Chance ratée ({luck_total}) : {damage} dégât(s) au total."
            else:
                luck_text = ""
            self.enemy_endurance.setValue(max(0, self.enemy_endurance.value() - damage))
            if (self.crocodile_combat and self.current_paragraph == 86
                    and damage > 0):
                self.crocodile_combat["wounded"] = True
            self._refresh_character()
            self.rules_log.setText(f"Vous touchez ({player_attack} contre {enemy_attack}). {luck_text} {self.enemy_name.text()} : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Monstre -{damage} PV")
            if self.enemy_endurance.value() == 0:
                self._remember_monster(self.enemy_name.text(), "vaincu")
                self.rules_log.setText(self.rules_log.text() + "  ⚑ Victoire !")
                self._advance_scripted_sequence()
            self._finish_single_book_combat(successful_hit=True)
        else:
            base_damage = 2
            if combat_rules.get("defense_roll"):
                _, defense_die = self._roll(1, context='Combat — Protection d’invisibilité')
                base_damage = 2 if defense_die % 2 else 1 if defense_die in (2, 4) else 0
                if base_damage == 0:
                    self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack,
                                      "Invisibilité : coup paré (6), aucun dégât")
                    return
            answer = self._assault_luck_choice("Le monstre vous touche !",
                f"Force d'attaque du monstre {enemy_attack} contre la vôtre {player_attack}.\nVous perdez {base_damage} Endurance.",
                "Voulez-vous tenter votre Chance pour minimiser la blessure ?")
            damage = base_damage
            if answer == QMessageBox.Yes:
                luck_rolls, luck_total = self._roll(2, context='Chance — Réduire la blessure')
                was_lucky = luck_total <= self.character["chance"]
                self.character["chance"] = max(0, self.character["chance"] - 1)
                if was_lucky:
                    damage = max(0, base_damage - 1)
                    luck_text = f"Chance réussie ({luck_total}) : blessure réduite à {damage}."
                else:
                    damage = base_damage + 1
                    luck_text = f"Chance ratée ({luck_total}) : blessure aggravée à {damage}."
            else:
                luck_text = ""
            shield_note = ""
            if self.character.get("shield_equipped") and SHIELD_NAME in self.character.get("inventory", []):
                shield_rolls, shield_total = self._roll(1, context='Combat — Bouclier au croissant')
                reduced = shield_damage(damage, shield_total)
                shield_note = f" Bouclier {shield_rolls}: -{damage - reduced} dégât."
                damage = reduced
            self.character["endurance"] = max(0, self.character["endurance"] - damage)
            self._refresh_character()
            self.rules_log.setText(f"Le monstre vous touche ({enemy_attack} contre {player_attack}). {luck_text}{shield_note} Vous : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Héros -{damage} PV")
            if self.character['endurance'] == 0:
                self.rules_log.setText(self.rules_log.text() + "  ☠ Votre Endurance est à zéro.")
            self._book_wound(damage)

    def change_shield_use(self, active):
        """Équiper ou ranger le bouclier uniquement s’il est présent dans l’inventaire."""
        if SHIELD_NAME not in self.character.get("inventory", []):
            return
        self.character["shield_equipped"] = bool(active)
        self.rules_log.setText(
            "Bouclier équipé." if active else "Bouclier rangé dans le sac.")

    def take_book_shield(self):
        """Proposer l’objet à abandonner et appliquer l’acquisition vérifiée du bouclier au §155."""
        if self.current_paragraph != 155:
            return
        entry = verified_entry(self.book_event_catalogue, 155)
        if not entry or not entry.get("shield_pickup"):
            return
        candidates = [x for x in self.character.get("inventory", [])
                      if x not in self.character.get("locked_items", [])
                      and x != SHIELD_NAME]
        if not candidates:
            QMessageBox.information(self, "Bouclier", "Aucun objet abandonnable.")
            return
        item, ok = QInputDialog.getItem(
            self, "Bouclier au croissant", "Objet à abandonner :", candidates, 0, False)
        if ok and take_moon_shield(self.character, item):
            self._refresh_character()
            self._render_choices_and_events(self.paragraphs[155])
            self.rules_log.setText(f"Bouclier récupéré ; objet abandonné : {item}.")


    def combat_available(self):
        """Exiger une rencontre réelle ici, jamais le profil caché d'un ancien adversaire.

        Les rencontres vérifiées incluent les préparations spéciales (fuite avant
        combat, Piranhas). Les rencontres détectées doivent avoir été confirmées
        et enregistrées sur la carte à ce paragraphe.
        """
        if (self.current_paragraph is None or self._adventurer_draft is not None
                or self.character['endurance'] <= 0):
            return False
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
        combat = entry.get('combat', {})
        if combat.get('precombat_escape'):
            return True
        if combat.get('mode') == 'wandering' and not self._book_state(self.current_paragraph).get('monster'):
            return True  # Le tirage de la rencontre se fait aussi dans la fenêtre de combat.
        if (combat.get('mode') == 'piranhas'
                and (self.piranha_combat or {}).get('status') == 'roll_pending'):
            return True
        if self.enemy_endurance.value() <= 0:
            return False
        if combat.get('enemies'):
            return True
        return any(monster['name'] == self.enemy_name.text() and monster['status'] == 'rencontré'
                   for monster in self.encounter_history.get(str(self.current_paragraph), []))

    def care_options(self, *, in_combat=False):
        """Décrire les soins disponibles sans les appliquer : potion et repas autorisé par le livre.

        Les potions fonctionnent pendant un combat. Un repas exige un passage
        explicitement autorisé, une provision et une autorisation non consommée.
        La Potion de Bonne Fortune reste utile au maximum puisqu'elle augmente
        aussi le total initial de Chance.
        """
        char = self.character
        alive = char['endurance'] > 0 and self._adventurer_draft is None
        potion = char.get('potion', 'Aucune')
        doses = char.get('potion_doses', 0)
        key = {"Potion d'Adresse": 'habilete', 'Potion de Vigueur': 'endurance',
               'Potion de Bonne Fortune': 'chance'}.get(potion)
        useful = key and (key == 'chance' or char[key] < char.get('initial', {}).get(key, char[key]))
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
        meal = (entry.get('optional_meal') or entry.get('optional_meal_restore') == 2 or entry.get('enchanted_meal'))
        meal = meal or (self.current_paragraph == 7 and self.piranha_combat
                        and self.piranha_combat.get('status') == 'victory')
        meal_useful = char['endurance'] < char.get('initial', {}).get('endurance', char['endurance'])
        if entry.get('enchanted_meal'):
            meal_useful = meal_useful or char['habilete'] < char.get('initial', {}).get('habilete', char['habilete'])
        taken = self._book_state(self.current_paragraph).get('care_meal_taken')
        if entry.get('enchanted_meal') and self.current_paragraph in self.completed_book_events:
            taken = True
        return [
            {'id': 'potion', 'label': f'{potion} — {doses} dose(s)',
             'enabled': bool(alive and useful and doses > 0),
             'reason': 'Aucune dose utile disponible.'},
            {'id': 'meal', 'label': 'Prendre un repas',
             'enabled': bool(alive and not in_combat and meal and meal_useful and not taken and char.get('provisions', 0) > 0),
             'reason': 'Repas interdit pendant le combat, non autorisé ici, déjà pris ou provisions épuisées.'},
        ]

    def can_flee_combat(self):
        """Partager les restrictions de fuite entre le lecteur et le bouton permanent du combat."""
        return self.combat_flee_status()[0]

    def combat_flee_status(self):
        """Expliquer la disponibilité sans résoudre de jet ni modifier la partie.

        Le compteur représente les assauts terminés, parades comprises. Le
        Vampire remplace son seuil initial par la prochaine tentative autorisée
        après un échec. Toutes ses destinations doivent être chargées : sinon
        le bouton serait actif alors que le moteur refuse de résoudre le jet.
        """
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
        combat = entry.get('combat', {})
        target = combat.get('escape_target')
        if target is None:
            return False, 'Le livre ne permet pas de fuir ce combat.'
        if self.character['endurance'] <= 0:
            return False, 'Votre aventurier est mort.'
        if not combat.get('precombat_escape') and self.enemy_endurance.value() <= 0:
            return False, 'Ce combat est terminé.'
        destinations = [target]
        if combat.get('escape_luck_interval'):
            destinations.append(combat['hypnosis_target'])
        if any(number not in self.paragraphs for number in destinations):
            return False, 'Une destination nécessaire à la fuite est absente du livre chargé.'
        assaults = self.book_combat_assaults.get(self.current_paragraph, 0)
        threshold = combat.get('escape_after_assaults', 0)
        if combat.get('escape_luck_interval'):
            threshold = max(threshold, self._book_state(self.current_paragraph).get('escape_after', threshold))
        if assaults < threshold:
            remaining = threshold - assaults
            return False, f'Fuite possible après encore {remaining} assaut(s) terminé(s).'
        permitted = flee_available(combat, assaults,
            1 if combat.get('precombat_escape') else self.enemy_endurance.value(), self.character['endurance'])
        return bool(permitted), ('Tenter votre Chance pour fuir ; une blessure de fuite reste due.'
                                 if combat.get('escape_luck_interval') else
                                 'Fuir avec la blessure de fuite prévue par les règles.')

    def _roll_adventurer(self):
        """Tirer les valeurs initiales selon les règles : H=1d6+6, E=2d6+12, C=1d6+6."""
        _, skill_roll = self._roll(1, context='Création — Habileté : 1d6 + 6')
        _, endurance_roll = self._roll(2, context='Création — Endurance : 2d6 + 12')
        _, luck_roll = self._roll(1, context='Création — Chance : 1d6 + 6')
        return {'habilete': skill_roll + 6, 'endurance': endurance_roll + 12, 'chance': luck_roll + 6}

    def change_potion(self, value):
        """Choisir la fiole avant le départ uniquement ; aucun remplissage en cours de jeu."""
        if (self._adventurer_draft is None or self.current_paragraph is not None
                or value not in ("Potion d'Adresse", "Potion de Vigueur", "Potion de Bonne Fortune")):
            return
        self.character["potion"] = value
        self.character["potion_doses"] = 2
        self._refresh_character()

    def test_luck(self):
        """Comparer 2d6 à la Chance avant de dépenser un point, puis afficher le résultat."""
        rolls, total = self._roll(2, context='Tentez votre Chance')
        lucky = total <= self.character["chance"]
        self.character["chance"] = max(0, self.character["chance"] - 1)
        self._refresh_character()
        verdict = "chanceux" if lucky else "malchanceux"
        self.rules_log.setText(f"Test de Chance : {rolls[0]} + {rolls[1]} = {total}. Vous êtes {verdict}. Chance -1.")

    def eat_meal(self):
        """Consommer une provision et restaurer l’Endurance dans la limite autorisée."""
        if self.character.get("provisions", 0) <= 0:
            self.rules_log.setText("Vous n'avez plus de provisions.")
            return
        current = self.character["endurance"]
        cap = self.character.get("initial", {}).get("endurance", current)
        self.character["endurance"] = min(cap, current + 4)
        self.character["provisions"] -= 1
        self._refresh_character()
        self.rules_log.setText(f"Repas consommé : Endurance {current} → {self.character['endurance']} (maximum {cap}). Provisions -1.")
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if (entry and entry.get("optional_meal")
                and self.current_paragraph in self.paragraphs):
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def eat_shared_meal(self):
        """§131 : le repas se partage, la restauration n'est que de deux points."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if not entry or entry.get("optional_meal_restore") != 2:
            return
        if not shared_meal(self.character):
            self.rules_log.setText("Impossible de partager le repas sans provision.")
            return
        self._refresh_character()
        self.rules_log.setText("Repas partagé : Endurance +2 (plafonnée), Provisions -1.")
        self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def drink_potion(self):
        """Appliquer la potion choisie et consommer une dose selon les règles de la caractéristique."""
        # Revérifier aussi les appels directs : pas de dose après la mort,
        # pendant la création, à fiole vide ou sans effet utile.
        if not self.care_options()[0]['enabled']:
            self.rules_log.setText("Aucune dose de potion utilisable.")
            return
        potion = self.character.get("potion", "Aucune")
        doses = self.character.get("potion_doses", 0)
        if potion == "Aucune" or doses <= 0:
            self.rules_log.setText("Aucune dose de potion disponible.")
            return
        initial = self.character.get("initial", {})
        if potion == "Potion d'Adresse":
            key, label = "habilete", "Habileté"
            target = initial.get(key, self.character[key])
        elif potion == "Potion de Vigueur":
            key, label = "endurance", "Endurance"
            target = initial.get(key, self.character[key])
        else:
            key, label = "chance", "Chance"
            target = initial.get(key, self.character[key]) + 1
            initial[key] = target
            self.character["initial"] = initial
        old = self.character[key]
        self.character[key] = target
        self.character["potion_doses"] = doses - 1
        self._refresh_character()
        self.rules_log.setText(f"Potion utilisée : {label} {old} → {target}. Doses restantes : {doses-1}.")


    def _render_choices_and_events(self, text):
        """Reconstruire les commandes selon texte, catalogue vérifié et état réel du héros.

        Un affichage ne doit pas résoudre un jet ou octroyer un butin ; ces mutations
        passent par les actions connectées et leurs contrôles de disponibilité."""
        self.choice_group.setTitle("⚜  QUELLE SERA VOTRE VOIE ?")
        self._clear_dynamic_layout(self.choice_layout)
        choices = self._paragraph_choices(text)
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        escape_target = entry.get("combat", {}).get("escape_target") if entry else None
        combat = entry.get("combat", {}) if entry else {}
        if (combat.get("mode") == "fire_breath"
                and self.character.get("book_facts", {}).get(combat["victory_fact"])):
            escape_target = None
        if self.current_paragraph == 179 and self.character.get("book_facts", {}).get("minotaur_dead"):
            escape_target = None
        if entry and "routes" in entry:
            # Ne présenter que les chemins permis par les objets et ressources actuels.
            choices = [{"target": route["target"], "label": route["label"]}
                       for route in available_routes(self.character, entry)]
        choices = [choice for choice in choices
                   if not self._combat_exit_pending(choice["target"])
                   and not self._book_blocked(choice["target"])]
        # §212 : la bouteille ne peut être essayée qu'une fois dans une partie.
        if self.current_paragraph == 212 and 369 in self.visited_paragraphs:
            choices = [choice for choice in choices if choice["target"] != 369]
        if entry and entry.get("enchanted_meal") and self.current_paragraph not in self.completed_book_events:
            choices = []
        if (entry and entry.get("diversion_discard")
                and self.current_paragraph not in self.completed_book_events):
            choices = []
        if (self.current_paragraph == 350 and self.piranha_combat
                and self.piranha_combat.get("status") != "victory"):
            choices = [choice for choice in choices if choice["target"] != 7]
        if (entry and entry.get("mode") == "des"
                and self.current_paragraph not in self.completed_book_events
                and "roll" in entry):
            roll_targets = {branch.get("target") for branch in entry["roll"]["branches"]}
            choices = [choice for choice in choices if choice["target"] not in roll_targets]
        if escape_target is not None:
            # La sortie par la fuite est exclusivement proposée avec sa pénalité.
            choices = [c for c in choices if c["target"] != escape_target]
        if not choices:
            self.choice_layout.addWidget(QLabel("Aucune destination explicite détectée dans ce paragraphe."))
        else:
            for choice in choices:
                target = choice["target"]
                button = ChoiceCard(choice_caption(choice['label'], target))
                button.setObjectName("choiceCard")
                button.setMinimumHeight(44)
                button.setAccessibleName(f"{choice['label']}, paragraphe {target}")
                button.setToolTip(f"Ouvrir le paragraphe {target}")
                button.setEnabled(target in self.paragraphs)
                if entry and "routes" in entry:
                    button.clicked.connect(lambda checked=False, n=target: self.follow_catalogue_choice(n))
                else:
                    button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
                self.choice_layout.addWidget(button)
                if target not in self.paragraphs:
                    button.setToolTip(f"Destination {target} non détectée dans le PDF importé")
        self._render_conditions(text)
        self._clear_dynamic_layout(self.event_layout)
        scripted = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if scripted:
            plain_passage = (
                scripted['mode'] == 'conditionnel'
                and set(scripted) <= {'status', 'mode', 'note', 'routes', 'title'}
                and all(set(route) <= {'target', 'label'} for route in scripted.get('routes', [])))
            if not plain_passage:
                notice = QLabel("✦ Événement du livre vérifié : " + scripted["note"])
                notice.setWordWrap(True)
                self.event_layout.addWidget(notice)
            self._book_buttons(scripted)
            if scripted["mode"] == "automatique":
                self.event_layout.addWidget(QLabel("Effets obligatoires appliqués une fois par partie."))
            if (scripted.get("diversion_discard")
                    and self.current_paragraph not in self.completed_book_events):
                btn = QPushButton("Faire diversion : jeter un objet ou 1 pièce d'or")
                btn.clicked.connect(lambda checked=False: self.throw_book_diversion())
                self.event_layout.addWidget(btn)
            if scripted.get("optional_meal_restore") == 2:
                shared_btn = QPushButton("Partager un repas (+2 Endurance ; -1 Provision)")
                shared_btn.setEnabled(self.care_options()[1]['enabled'])
                shared_btn.clicked.connect(lambda checked=False: self.use_care('meal'))
                self.event_layout.addWidget(shared_btn)
            if scripted.get("optional_meal"):
                meal_btn = QPushButton("Prendre un repas (+4 Endurance ; -1 Provision)")
                meal_btn.setEnabled(self.care_options()[1]['enabled'])
                meal_btn.clicked.connect(lambda checked=False: self.use_care('meal'))
                self.event_layout.addWidget(meal_btn)
            if scripted.get("enchanted_meal") and self.current_paragraph not in self.completed_book_events:
                btn = QPushButton("Prendre le repas enchanté (1 Provision ; +6 E, +1 H)")
                btn.setEnabled(self.care_options()[1]['enabled'])
                btn.clicked.connect(lambda checked=False: self.use_care('meal'))
                self.event_layout.addWidget(btn)
            if scripted.get("trade_choices") and not any(
                    k.startswith(f"{self.current_paragraph}:trade:")
                    for k in self.completed_optional_events):
                for choice in scripted["trade_choices"]:
                    btn = QPushButton(f"Échanger un objet contre : {choice['name']}")
                    btn.clicked.connect(
                        lambda checked=False, item_id=choice["id"]: self.take_book_trade(item_id))
                    self.event_layout.addWidget(btn)
            if scripted.get("shield_pickup") and SHIELD_NAME not in self.character.get("inventory", []):
                btn = QPushButton("Prendre le bouclier (abandonner un objet)")
                btn.clicked.connect(lambda checked=False: self.take_book_shield())
                self.event_layout.addWidget(btn)
            for option in available_options(self.character, scripted,
                                            self.completed_optional_events,
                                            self.current_paragraph):
                button = QPushButton(option["label"])
                button.clicked.connect(lambda checked=False, n=self.current_paragraph, oid=option["id"]: self.apply_optional_book_event(n, oid))
                self.event_layout.addWidget(button)
            if scripted["mode"] in ("des", "des_optionnel") and "roll" in scripted:
                count = scripted['roll'].get('dice', 1)
                label = 'Lancer le dé' if count == 1 else f'Lancer les {count} dés'
                button = QPushButton(f'🎲 {label}')
                button.setEnabled(self.current_paragraph not in self.completed_book_events)
                button.clicked.connect(lambda checked=False, n=self.current_paragraph: self.resolve_book_roll(n))
                self.event_layout.addWidget(button)
                return
            if scripted["mode"] in ("automatique", "conditionnel") and (
                    scripted["mode"] == "automatique" or scripted.get("options")
                    or scripted.get("special") or scripted.get("trade_choices")
                    or scripted.get("loot_choices") or "routes" in scripted):
                return
            # Les commandes d'assaut et de fuite restent communes aux combats.
        state = self.crocodile_combat
        if (state and self.current_paragraph == 86 and state["phase"] == "initial"
                and state["assaults"] >= 2 and self.enemy_endurance.value() > 0):
            continue_btn = QPushButton("Continuer le combat contre le Crocodile")
            continue_btn.setProperty('combatAction', True)
            continue_btn.clicked.connect(lambda checked=False: self.choose_crocodile_strategy("continue"))
            self.event_layout.addWidget(continue_btn)
            diversion_btn = QPushButton("Faire un dernier assaut puis rejoindre le §350")
            diversion_btn.setProperty('combatAction', True)
            diversion_btn.clicked.connect(lambda checked=False: self.choose_crocodile_strategy("diversion"))
            self.event_layout.addWidget(diversion_btn)
        if escape_target is not None:
            combat_rules = entry["combat"]
            permitted = self.can_flee_combat()
            escape_label = ("Tenter sa Chance pour fuir (blessure de fuite)"
                            if combat_rules.get("escape_luck_interval")
                            else "Fuir le combat (pénalité obligatoire)")
            btn = QPushButton(f"{escape_label} → §{escape_target}")
            btn.setProperty('combatAction', True)
            btn.setProperty('combatEscape', True)
            popup = self._combat_dialog
            can_act = popup is None or (not popup.busy and not popup.outcome)
            btn.setEnabled(permitted and can_act)
            btn.setToolTip(self.combat_flee_status()[1] if can_act else
                           'Terminez l’assaut ou l’action en cours avant de fuir.')
            btn.clicked.connect(lambda checked=False, n=self.current_paragraph: self.escape_scripted_combat(n))
            self.event_layout.addWidget(btn)
        if self.current_paragraph == 350 and self.piranha_combat:
            if self.piranha_combat.get("status") == "roll_pending":
                dice_button = QPushButton("🎲 Déterminer qui subit l'attaque des Piranhas (1d6)")
                dice_button.setProperty('combatAction', True)
                dice_button.clicked.connect(lambda checked=False: self.roll_piranha_target())
                self.event_layout.addWidget(dice_button)
            elif self.piranha_combat.get("status") == "fighting":
                self.event_layout.addWidget(QLabel(
                    f"Piranhas préparés · H 5 / E {self.piranha_combat['stamina']}."
                    " Combattez-les avec les commandes d'assaut."))
        # Le §350 possède deux profils conditionnels : la détection générique
        # ne doit pas permettre de remplacer le profil obtenu par les règles.
        # Un combat préparé depuis le catalogue ne doit jamais pouvoir
        # être réinitialisé par le détecteur heuristique d'adversaires.
        scripted_combat = scripted.get("combat", {}) if scripted else {}
        if scripted_combat.get("enemies") or scripted_combat.get("precombat_escape"):
            # Les règles ci-dessus couvrent ces rencontres. Ne pas proposer en
            # parallèle des effets ou des adversaires déduits du texte brut.
            return
        monsters = ([] if scripted_combat.get("enemies") else encounters(text))
        if monsters:
            self.event_layout.addWidget(QLabel("⚔ Rencontres détectées (à confirmer)"))
            for monster in monsters:
                button = QPushButton(f"Préparer le combat : {monster['name']} · H {monster['skill']} / E {monster['stamina']}")
                button.clicked.connect(lambda checked=False, m=monster: self.prepare_encounter(m))
                self.event_layout.addWidget(button)
        combat = combat_hints(text)
        if combat['cues']:
            note = QLabel('⚔ Indices de combat : ' + ' · '.join(combat['cues']))
            note.setWordWrap(True)
            self.event_layout.addWidget(note)
        if len(monsters) > 1:
            note = QLabel('Plusieurs adversaires détectés : préparez-les séparément. L’ordre et les règles spéciales doivent être vérifiés dans le livre.')
            note.setWordWrap(True)
            self.event_layout.addWidget(note)
        for label, target in combat['exits']:
            if self._combat_exit_pending(target) or self._book_blocked(target):
                continue
            if (entry and entry.get("mode") == "des"
                    and self.current_paragraph not in self.completed_book_events
                    and "roll" in entry
                    and target in {branch.get("target") for branch in entry["roll"]["branches"]}):
                continue
            if (self.current_paragraph == 350 and target == 7
                    and self.piranha_combat
                    and self.piranha_combat.get("status") != "victory"):
                continue
            if target == escape_target:
                continue  # Ne pas créer un lien de fuite sans pénalité.
            button = QPushButton(f'Issue possible — {label} → §{target}')
            button.setEnabled(target in self.paragraphs)
            button.setToolTip('Vérifiez que cette issue est bien applicable avant de voyager.')
            button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
            self.event_layout.addWidget(button)
        for item in item_hints(text):
            button = QPushButton(f"Ajouter à l’inventaire (vérifier) : {item}")
            button.clicked.connect(lambda checked=False, name=item: self.confirm_item(name))
            self.event_layout.addWidget(button)
        events = self._paragraph_events(text) + stat_events(text)
        events = [e for i,e in enumerate(events) if not any(x['key']==e['key'] and x['amount']==e['amount'] for x in events[:i])]
        for event in events:
            amount = event["amount"]
            # Show an explicit confirmation before applying any extracted effect.
            button = QPushButton(f"Appliquer : {event['label']} ({amount:+d})")
            button.clicked.connect(lambda checked=False, e=event: self.apply_detected_event(e))
            self.event_layout.addWidget(button)

    def go_to(self, number):
        """Entrer dans un paragraphe et reconstruire les vues associées.

        Contrôler création, mort et sorties ; enregistrer ensuite la transition, les
        effets d’entrée et la préparation des combats avant d’afficher texte et commandes.
        En restauration, afficher l’état fourni sans rejouer effets, visites ni préparation.
        Les appels imbriqués font partie de l’action extérieure suivie par _track_action."""
        if self._adventurer_draft is not None and not self._restoring:
            return  # The map and manual navigation cannot skip character validation.
        if (self.character['endurance'] <= 0 and not self._restoring
                and getattr(self, '_action_depth', 0) <= 1):
            self._show_death_page()
            return
        if number not in self.paragraphs:
            QMessageBox.information(self, "Paragraphe absent", f"Le paragraphe {number} n'a pas été détecté dans le PDF chargé.")
            return
        previous = self.current_paragraph
        if previous != number and not self._restoring:
            self.sounds.play("page")
        if previous is not None and previous != number and not self._restoring:
            source = verified_entry(self.book_event_catalogue, previous)
            combat = source.get("combat", {}) if source else {}
            known = self.encounter_history.get(str(previous), [])
            if known and combat and self.character["endurance"] > 0:
                if self.enemy_endurance.value() <= 0:
                    self._remember_monster(self.enemy_name.text(), "vaincu")
                elif number in (combat.get("escape_target"), combat.get("diversion_target")):
                    self._remember_monster(self.enemy_name.text(), "fui")
                elif number == combat.get("first_hit_target"):
                    self._remember_monster(self.enemy_name.text(), "repoussé")
        if previous is not None and previous != number and not self._restoring:
            self.transitions.append([previous, number])
        self.current_paragraph = number
        if not self._restoring and self.book_event_catalogue:
            if number in (106, 279):
                self._remember_monster("Dragon" if number == 106 else "Vampire")
            if number == 371 and "106" in self.encounter_history:
                self._remember_monster("Dragon", "vaincu", 106)
            if number == 327 and "279" in self.encounter_history:
                self._remember_monster("Vampire", "vaincu", 279)
            if previous == 17 and number == 380 and "279" in self.encounter_history:
                self._remember_monster("Vampire", "fui", 279)
        if not self._restoring:
            self._enter_complex_book(number, previous)
        if not self._restoring and apply_entry(self.character, self.completed_book_events, number, self.book_event_catalogue):
            self._refresh_character()
            self.rules_log.setText(f"Effets vérifiés appliqués automatiquement au paragraphe {number}.")
        if not self._restoring:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            opponents = combat.get("enemies", [])
            if (len(opponents) == 1 and combat.get("mode") in (None, "first_hit", "fire_breath")
                    and not (number == 179 and self.character.get("book_facts", {}).get("minotaur_dead"))
                    and number not in self.prepared_book_encounters):
                opponent = opponents[0]
                self._set_book_enemy(opponent)
                self.prepared_book_encounters.add(number)
                self.combat_state.setText(
                    f"⚔ {opponent['name']} · H {opponent['skill']} · Endurance {opponent['stamina']}")
                self.combat_journal.clear()
        if not self._restoring and number == 86:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            if (combat.get("mode") == "limite_assauts" and self.crocodile_combat is None
                    and number not in self.prepared_book_encounters):
                self.crocodile_combat = {"paragraph": number, "assaults": 0,
                                         "phase": "initial", "wounded": False}
                self._set_book_enemy(combat["enemies"][0])
        if (not self._restoring and number == 350
                and self.piranha_source_wounded is not None
                and number not in self.prepared_book_encounters):
            if self.piranha_source_wounded:
                self._prepare_piranhas(1)
            else:
                self.piranha_combat = {"status": "roll_pending"}
        if not self._restoring:
            entry = verified_entry(self.book_event_catalogue, number)
            combat = entry.get("combat", {}) if entry else {}
            if (combat.get("mode") == "sequence" and len(combat.get("enemies", [])) > 1
                    and self.book_combat_sequence is None
                    and number not in self.prepared_book_encounters):
                self.book_combat_sequence = {"paragraph": number, "index": 0}
                self._set_book_enemy(combat["enemies"][0])
        if number not in self.visited_paragraphs:
            self.visited_paragraphs.append(number)
        self.goto_spin.setValue(number)
        title = self._paragraph_name(number)
        self.paragraph_title.setText(title or 'Paragraphe')
        self.paragraph_number.setText(f'§ {number}')
        self.paragraph_number.show()
        text = self.paragraphs[number]
        # Utiliser le même détecteur pour les boutons ET les liens dans le texte.
        self._render_paragraph_text(text)
        self.reader.moveCursor(QTextCursor.Start)
        self._render_choices_and_events(text)
        self.choice_group.setVisible(any(isinstance(self.choice_layout.itemAt(i).widget(), QPushButton)
                                        for i in range(self.choice_layout.count())))
        self.event_group.setVisible(self.event_layout.count() > 0)
        self.condition_group.setVisible(self.condition_layout.count() > 0)
        self._update_scene_art()
        self._refresh_action_controls()

    def follow_link(self, url):
        """Dispatcher les liens paragraph:N du lecteur vers la navigation contrôlée."""
        value = url.toString()
        match = re.search(r"paragraph(?::|%3A)(\d+)", value, re.I)
        if not match:
            return
        target = int(match.group(1))
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if self._book_blocked(target):
            QMessageBox.information(self, "Action du livre nécessaire",
                                    "Résolvez d’abord l’action vérifiée de ce passage.")
            return
        if self._combat_exit_pending(target):
            QMessageBox.information(
                self, "Combat obligatoire",
                "Terminez d'abord l'affrontement avant d'atteindre cette issue.")
            return
        if (self.current_paragraph == 212 and target == 369
                and 369 in self.visited_paragraphs):
            QMessageBox.information(
                self, "Bouteille déjà essayée",
                "Vous avez déjà essayé de boire ce liquide.")
            return
        if (entry and entry.get("diversion_discard")
                and self.current_paragraph not in self.completed_book_events
                and target == 269):
            QMessageBox.information(
                self, "Diversion nécessaire", "Jetez un objet avant de quitter l'Ogre.")
            return
        if (entry and entry.get("mode") == "des"
                and self.current_paragraph not in self.completed_book_events
                and "roll" in entry
                and target in {branch.get("target") for branch in entry["roll"]["branches"]}):
            QMessageBox.information(
                self, "Jet obligatoire",
                "Lancez d'abord les dés du livre avant de suivre cette destination.")
            return
        if (self.current_paragraph == 350 and target == 7
                and self.piranha_combat
                and self.piranha_combat.get("status") != "victory"):
            QMessageBox.information(
                self, "Piranhas", "Il faut vaincre les Piranhas avant de rejoindre le §7.")
            return
        if entry and target == entry.get("combat", {}).get("escape_target"):
            self.escape_scripted_combat(self.current_paragraph)
            return
        if entry and "routes" in entry:
            self.follow_catalogue_choice(target)
            return
        self.go_to(target)
