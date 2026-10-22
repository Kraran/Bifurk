"""Commandes communes de Défis Fantastiques, avec extensions explicites par livre.

Les services Qt, jets et transactions sont fournis par la fenêtre hôte. Les hooks
_ff_* sont des méthodes ordinaires déléguées vers l'adaptateur ouvert : aucune
exception du Sorcier ni import de son module n'est nécessaire à ce socle.
"""
from PySide6.QtWidgets import QMessageBox
from book_events import verified_entry, apply_effects
from .rules import (POTION_STATS, POTION_DOSES, adventurer_stats, spend_luck,
                    combat_damage, potion_useful, drink_potion, eat_meal,
                    flee_available, escape_damage)


class FightingFantasyActions:
    """Fournir création, soins, assauts et fuite ; le livre étend seulement les exceptions."""
    def _ff_item_removed(self, name):
        """Notifier un retrait manuel ; le socle n’attribue aucun pouvoir aux objets."""

    def _combat_entry(self, number):
        """Lire une rencontre vérifiée ; le module peut valider ses profils séparément."""
        return verified_entry(self.book_event_catalogue, number)

    def _combat_roster(self):
        """None conserve le suivi historique du dialogue de combat."""
        return None

    def _ff_after_attack_rolls(self):
        """Autoriser la résolution après les jets ; une aventure peut intercaler un danger."""
        return True

    def _reading_link_targets(self):
        """Limiter les liens du lecteur ; chaque module peut filtrer ses renvois."""
        return self.paragraphs

    def _book_state(self, number, create=False):
        """Lire l’état local d’un paragraphe ; create=True crée les dictionnaires persistants.

        Les clés sont des chaînes pour survivre au passage JSON ; sans create, une lecture
        d’un état absent ne doit pas modifier le personnage."""
        if create:
            return self.character.setdefault('book_state', {}).setdefault(str(number), {})
        return self.character.get('book_state', {}).get(str(number), {})

    def use_care(self, kind):
        """Revérifier un soin au clic et l'appliquer dans une transaction annulable."""
        in_combat = self._combat_dialog is not None and not self._combat_dialog.outcome
        option = next((o for o in self.care_options(in_combat=in_combat) if o['id'] == kind), None)
        if not option or not option['enabled']:
            return
        if kind == 'potion':
            self.drink_potion()
        else:
            self._ff_take_meal()
            self._book_state(self.current_paragraph, True)['care_meal_taken'] = True
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def _set_book_enemy(self, monster):
        """Initialise un adversaire vérifié sans changer les données du héros."""
        self._remember_monster(monster["name"])
        self.enemy_name.setText(monster["name"])
        self.enemy_skill.setValue(monster["skill"])
        self.enemy_endurance.setValue(monster["stamina"])
        self.combat_state.setText(
            f"⚔ {monster['name']} · H {monster['skill']} · Endurance {monster['stamina']}")

    def _advance_scripted_sequence(self):
        """Après la victoire, prépare le suivant ; à la fin, va à la sortie prescrite."""
        state = self.book_combat_sequence
        if (not state or self.current_paragraph != state["paragraph"]
                or self.enemy_endurance.value() > 0):
            return
        entry = self._combat_entry(state["paragraph"])
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
        entry = self._combat_entry(number)
        rules = entry.get("combat", {}) if entry else {}
        target = rules.get("escape_target")
        if self._ff_escape_override(number, rules):
            return
        if not self.can_flee_combat():
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

    def combat_available(self):
        """Exiger une rencontre réelle ici, jamais le profil caché d'un ancien adversaire.

        Les rencontres vérifiées incluent les préparations prévues par le livre (dont la fuite avant
        combat). Les rencontres détectées doivent avoir été confirmées
        et enregistrées sur la carte à ce paragraphe.
        """
        if (self.current_paragraph is None or self._adventurer_draft is not None
                or self.character['endurance'] <= 0):
            return False
        entry = self._combat_entry(self.current_paragraph) or {}
        combat = entry.get('combat', {})
        if combat.get('precombat_escape'):
            return True
        if self._ff_pending_combat(combat):
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
        useful = potion_useful(char)
        meal, meal_useful, taken = self._ff_meal_status()
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
        livre peut fournir une restriction supplémentaire. Toutes les destinations
        nécessaires doivent être chargées : sinon
        le bouton serait actif alors que le moteur refuse de résoudre le jet.
        """
        entry = self._combat_entry(self.current_paragraph) or {}
        combat = entry.get('combat', {})
        target = combat.get('escape_target')
        if target is None:
            return False, 'Le livre ne permet pas de fuir ce combat.'
        if self.character['endurance'] <= 0:
            return False, 'Votre aventurier est mort.'
        if not combat.get('precombat_escape') and self.enemy_endurance.value() <= 0:
            return False, 'Ce combat est terminé.'
        destinations, threshold, hint = self._ff_escape_details(combat)
        if any(number not in self.paragraphs for number in destinations):
            return False, 'Une destination nécessaire à la fuite est absente du livre chargé.'
        assaults = self.book_combat_assaults.get(self.current_paragraph, 0)
        if assaults < threshold:
            remaining = threshold - assaults
            return False, f'Fuite possible après encore {remaining} assaut(s) terminé(s).'
        permitted = flee_available(combat, assaults,
            1 if combat.get('precombat_escape') else self.enemy_endurance.value(), self.character['endurance'])
        return bool(permitted), hint

    def _roll_adventurer(self):
        """Tirer les valeurs initiales selon les règles : H=1d6+6, E=2d6+12, C=1d6+6."""
        _, skill_roll = self._roll(1, context='Création — Habileté : 1d6 + 6')
        _, endurance_roll = self._roll(2, context='Création — Endurance : 2d6 + 12')
        _, luck_roll = self._roll(1, context='Création — Chance : 1d6 + 6')
        return adventurer_stats(skill_roll, endurance_roll, luck_roll)

    def change_potion(self, value):
        """Choisir la fiole avant le départ uniquement ; aucun remplissage en cours de jeu."""
        if (self._adventurer_draft is None or self.current_paragraph is not None
                or value not in POTION_STATS):
            return
        self.character["potion"] = value
        self.character["potion_doses"] = POTION_DOSES
        self._refresh_character()

    def test_luck(self):
        """Comparer 2d6 à la Chance avant de dépenser un point, puis afficher le résultat."""
        rolls, total = self._roll(2, context='Tentez votre Chance')
        lucky = spend_luck(self.character, total)
        self._refresh_character()
        verdict = "chanceux" if lucky else "malchanceux"
        self.rules_log.setText(f"Test de Chance : {rolls[0]} + {rolls[1]} = {total}. Vous êtes {verdict}. Chance -1.")

    def eat_meal(self):
        """Consommer une provision et restaurer l’Endurance dans la limite autorisée."""
        result = eat_meal(self.character)
        if result is None:
            self.rules_log.setText("Aucune provision utilisable.")
            return
        current = result.before
        cap = self.character.get("initial", {}).get("endurance", current)
        self._refresh_character()
        self.rules_log.setText(f"Repas consommé : Endurance {current} → {self.character['endurance']} (maximum {cap}). Provisions -1.")
        entry = self._combat_entry(self.current_paragraph)
        if (entry and entry.get("optional_meal")
                and self.current_paragraph in self.paragraphs):
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def drink_potion(self):
        """Appliquer la potion choisie et consommer une dose selon les règles de la caractéristique."""
        # Revérifier aussi les appels directs : pas de dose après la mort,
        # pendant la création, à fiole vide ou sans effet utile.
        if not self.care_options()[0]['enabled']:
            self.rules_log.setText("Aucune dose de potion utilisable.")
            return
        result = drink_potion(self.character)
        if result is None:
            return
        label = {'habilete': 'Habileté', 'endurance': 'Endurance', 'chance': 'Chance'}[result.stat]
        old, target, doses = result.before, result.after, result.remaining + 1
        self._refresh_character()
        self.rules_log.setText(f"Potion utilisée : {label} {old} → {target}. Doses restantes : {doses-1}.")

    def combat_round(self):
        """Résoudre un assaut commun avec les extensions explicites de l'aventure.

        L'ordre avant-assaut / attaques / défense / blessure est conservé. Les
        décisions de Chance font partie de la même transaction d'historique.
        Les hooks par défaut ne donnent aucun pouvoir spécial aux objets."""
        self._book_round_played = False
        if self.character['endurance'] <= 0 or not self._ff_before_assault():
            return
        if self.enemy_endurance.value() <= 0:
            self.rules_log.setText("Le monstre est déjà vaincu.")
            return
        if not self._ff_before_attack():
            return
        combat_rules = self._ff_combat_profile()
        enemy_rolls, enemy_total = self._roll(2, context=f'Combat — {self.enemy_name.text() or "Adversaire"}', opponent=True)
        player_rolls, player_total = self._roll(2, context=f'Combat — {self.character.get("name") or "Votre aventurier"}')
        enemy_attack = self.enemy_skill.value() + enemy_total
        player_attack = combat_rules.get("skill", self.character["habilete"]) + player_total + combat_rules.get("attack_bonus", 0)
        self.sounds.play("swords")
        if not self._ff_after_attack_rolls():
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack,
                              'Assaut interrompu par le danger spécial')
            return
        if player_attack == enemy_attack:
            self.rules_log.setText(f"Égalité ({player_attack} contre {enemy_attack}) : aucun dégât. Relancez l'assaut.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, "Parade")
            return
        if player_attack > enemy_attack:
            if not combat_rules.get('can_wound', True):
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
                was_lucky = spend_luck(self.character, luck_total)
                if was_lucky:
                    damage = combat_damage(base_damage, attacking=True, lucky=True)
                    luck_text = f"Chance réussie ({luck_total}) : {damage} dégâts au total."
                else:
                    damage = combat_damage(base_damage, attacking=True, lucky=False)
                    luck_text = f"Chance ratée ({luck_total}) : {damage} dégât(s) au total."
            else:
                luck_text = ""
            self.enemy_endurance.setValue(max(0, self.enemy_endurance.value() - damage))
            self._ff_after_enemy_damage(damage)
            self._refresh_character()
            self.rules_log.setText(f"Vous touchez ({player_attack} contre {enemy_attack}). {luck_text} {self.enemy_name.text()} : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Monstre -{damage} PV")
            if self.enemy_endurance.value() == 0:
                self._remember_monster(self.enemy_name.text(), "vaincu")
                self.rules_log.setText(self.rules_log.text() + "  ⚑ Victoire !")
                self._ff_enemy_defeated()
            self._ff_after_hit()
        else:
            base_damage, defense_note = self._ff_defend_hit()
            if base_damage == 0:
                self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, defense_note)
                return
            answer = self._assault_luck_choice("Le monstre vous touche !",
                f"Force d'attaque du monstre {enemy_attack} contre la vôtre {player_attack}.\nVous perdez {base_damage} Endurance.",
                "Voulez-vous tenter votre Chance pour minimiser la blessure ?")
            damage = base_damage
            if answer == QMessageBox.Yes:
                luck_rolls, luck_total = self._roll(2, context='Chance — Réduire la blessure')
                was_lucky = spend_luck(self.character, luck_total)
                if was_lucky:
                    damage = combat_damage(base_damage, attacking=False, lucky=True)
                    luck_text = f"Chance réussie ({luck_total}) : blessure réduite à {damage}."
                else:
                    damage = combat_damage(base_damage, attacking=False, lucky=False)
                    luck_text = f"Chance ratée ({luck_total}) : blessure aggravée à {damage}."
            else:
                luck_text = ""
            damage, shield_note = self._ff_reduce_damage(damage)
            self.character["endurance"] = max(0, self.character["endurance"] - damage)
            self._refresh_character()
            self.rules_log.setText(f"Le monstre vous touche ({enemy_attack} contre {player_attack}). {luck_text}{shield_note} Vous : -{damage} Endurance.")
            self._log_assault(player_rolls, enemy_rolls, player_attack, enemy_attack, f"Héros -{damage} PV")
            if self.character['endurance'] == 0:
                self.rules_log.setText(self.rules_log.text() + "  ☠ Votre Endurance est à zéro.")
            self._ff_after_player_damage(damage)

    def _ff_before_assault(self):
        """Autoriser l'assaut ordinaire ; l'aventure peut résoudre un préambule spécial."""
        return True

    def _ff_before_attack(self):
        """Autoriser les jets après validation d'un ennemi encore vivant."""
        return True

    def _ff_combat_profile(self):
        """L'Habileté de la fiche s'applique, sans bonus d'objet implicite."""
        return {'skill': self.character['habilete'], 'hit_damage': 2, 'attack_bonus': 0, 'can_wound': True}

    def _ff_defend_hit(self):
        """Une blessure ordinaire coûte deux points d'Endurance, avant la Chance."""
        return 2, ''

    def _ff_reduce_damage(self, damage):
        """Aucune protection particulière dans le socle ; le livre peut en fournir une."""
        return damage, ''

    def _ff_after_enemy_damage(self, damage):
        """Point d'extension des effets d'une blessure à l'ennemi, sans effet par défaut."""

    def _ff_enemy_defeated(self):
        """Passer au prochain adversaire d'une séquence explicitement cataloguée."""
        self._advance_scripted_sequence()

    def _ff_after_hit(self):
        """Suivre une victoire ordinaire seulement si le catalogue donne sa destination."""
        combat = (self._combat_entry(self.current_paragraph) or {}).get('combat', {})
        if self.enemy_endurance.value() <= 0 and self.character['endurance'] > 0:
            target = combat.get('victory_target')
            if target in self.paragraphs:
                self.prepared_book_encounters.add(self.current_paragraph)
                self.go_to(target)

    def _ff_after_player_damage(self, damage):
        """Point d'extension des conséquences d'une blessure, sans poison implicite."""

    def _ff_pending_combat(self, combat):
        """Aucun tirage de rencontre ou préparation particulière dans le socle."""
        return False

    def _ff_escape_details(self, combat):
        """Fuite ordinaire : destination et éventuel nombre minimal d'assauts."""
        return ([combat['escape_target']], combat.get('escape_after_assaults', 0),
                'Fuir avec la blessure de fuite prévue par les règles.')

    def _ff_escape_override(self, number, rules):
        """False laisse résoudre la fuite ordinaire ; True signale un traitement par le livre."""
        return False

    def _ff_meal_status(self):
        """Un repas ordinaire exige une autorisation du passage, sans exception de lieu."""
        entry = self._combat_entry(self.current_paragraph) or {}
        char = self.character
        useful = char['endurance'] < char.get('initial', {}).get('endurance', char['endurance'])
        taken = self._book_state(self.current_paragraph).get('care_meal_taken')
        return bool(entry.get('optional_meal')), useful, taken

    def _ff_take_meal(self):
        """Le repas commun restaure quatre points ; l'aventure peut remplacer cet effet."""
        self.eat_meal()

    def _ff_record_assault(self):
        """Compter l'assaut pour le délai de fuite, sans compteur propre à un monstre."""
        entry = self._combat_entry(self.current_paragraph) or {}
        if 'escape_target' in entry.get('combat', {}):
            number = self.current_paragraph
            self.book_combat_assaults[number] = self.book_combat_assaults.get(number, 0) + 1

    def _ff_finish_assault(self, number):
        """Rafraîchir les commandes de fuite après l'assaut, dans la transaction courante."""
        current = self._combat_entry(self.current_paragraph)
        if (current and 'escape_target' in current.get('combat', {})
                and self.current_paragraph in self.paragraphs):
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])
