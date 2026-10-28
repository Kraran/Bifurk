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
from book_events import (verified_entry, apply_effects, apply_entry, routes_with_requirements, options_with_requirements, combat_skill, piranha_stamina, shield_damage, SHIELD_NAME, take_moon_shield, shared_meal, enchanted_bench_meal, trade_inventory_item, throw_diversion_item)


from grimoire_modules.fighting_fantasy.controller import FightingFantasyActions


class SorcierCombatActions(FightingFantasyActions):
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


    def _render_choices_and_events(self, text):
        """Reconstruire les commandes puis recalculer la visibilité de leurs cadres.

        Le recalcul est fait ici, et non seulement à l'entrée dans le paragraphe :
        une victoire sans saut automatique (§249) ou un soin pris dans la fenêtre
        de combat font apparaître des sorties après coup."""
        self._render_choices_and_events_body(text)
        self._sync_paragraph_groups()

    def _sync_paragraph_groups(self):
        """Montrer les cadres de choix, d'événements et de conditions s'ils ont un contenu."""
        self.choice_group.setVisible(any(isinstance(self.choice_layout.itemAt(i).widget(), QPushButton)
                                        for i in range(self.choice_layout.count())))
        self.event_group.setVisible(self.event_layout.count() > 0)
        self.condition_group.setVisible(self.condition_layout.count() > 0)

    def _render_choices_and_events_body(self, text):
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
            # Un manque de ressource (or, objet) reste visible, grisé, avec sa raison.
            choices = [{"target": route["target"], "label": route["label"], "missing": reason}
                       for route, reason in routes_with_requirements(self.character, entry)]
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
            pending = bool(entry and (entry.get("combat") or entry.get("roll") or entry.get("special")
                                      or entry.get("enchanted_meal") or entry.get("diversion_discard")))
            self.choice_layout.addWidget(QLabel(
                "La suite dépend de l’événement ci-dessous." if pending
                else "Aucune destination explicite détectée dans ce paragraphe."))
        else:
            for choice in choices:
                target = choice["target"]
                missing = choice.get("missing")
                label = choice['label'] + (f" — {missing[0].lower()}{missing[1:]}" if missing else "")
                button = ChoiceCard(choice_caption(label, target))
                button.setObjectName("choiceCard")
                button.setMinimumHeight(44)
                button.setAccessibleName(f"{label}, paragraphe {target}")
                button.setToolTip(f"Indisponible : {missing}" if missing else f"Ouvrir le paragraphe {target}")
                button.setEnabled(target in self.paragraphs and not missing)
                if entry and "routes" in entry:
                    button.clicked.connect(lambda checked=False, n=target: self.follow_catalogue_choice(n))
                else:
                    button.clicked.connect(lambda checked=False, n=target: self.go_to(n))
                self.choice_layout.addWidget(button)
                if target not in self.paragraphs and not missing:
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
            if scripted.get("optional_meal") or self._arrival_meal(scripted):
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
            for option, missing in options_with_requirements(self.character, scripted,
                                                             self.completed_optional_events,
                                                             self.current_paragraph):
                button = QPushButton(option["label"])
                if missing:
                    button.setEnabled(False)
                    button.setToolTip(f"Indisponible : {missing}")
                    button.setText(f"{option['label']} — {missing[0].lower()}{missing[1:]}")
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
            # Un bouton explicite : aucun effet extrait du texte n'est appliqué sans confirmation.
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
            return  # La carte et la navigation manuelle ne contournent pas la validation du héros.
        if (self.character['endurance'] <= 0 and not self._restoring
                and getattr(self, '_action_depth', 0) <= 1):
            self._show_death_page()
            return
        if number not in self.paragraphs:
            QMessageBox.information(self, "Paragraphe absent", f"Le paragraphe {number} n'a pas été détecté dans le PDF chargé.")
            return
        previous = self.current_paragraph
        self._ff_note_move(number)
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
        self._tts_follow_paragraph(number)
        self._ambience_follow_paragraph(number)
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
            # Ne pas effacer le jet (Chance, dés) qui a provoqué ce saut dans la même action.
            self.rules_log.append(f"Effets vérifiés appliqués automatiquement au paragraphe {number}.")
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

    def _ff_before_assault(self):
        """Préambules du Sorcier : rencontres complexes, choix du Crocodile et souffle."""
        if self._complex_round_blocked():
            return False
        state = self.crocodile_combat
        if (state and self.current_paragraph == state['paragraph']
                and state['phase'] == 'initial' and state['assaults'] >= 2
                and self.enemy_endurance.value() > 0):
            self.rules_log.setText('Après deux assauts contre le Crocodile, choisissez une stratégie dans les événements.')
            return False
        return True

    def _ff_before_attack(self):
        """Le souffle précède les dés d'attaque, seulement tant que le Chien vit."""
        combat = (verified_entry(self.book_event_catalogue, self.current_paragraph) or {}).get('combat', {})
        return combat.get('mode') != 'fire_breath' or self._resolve_fire_breath()

    def _ff_combat_profile(self):
        """Appliquer les armes, le casque et les particularités vérifiées de ce livre."""
        combat = (verified_entry(self.book_event_catalogue, self.current_paragraph) or {}).get('combat', {})
        return {'skill': combat_skill(self.character), 'attack_bonus': combat.get('attack_bonus', 0),
                'hit_damage': combat.get('hit_damage', 2), 'can_wound': combat.get('mode') != 'invulnerable'}

    def _ff_defend_hit(self):
        """La potion d'invisibilité peut réduire ou annuler le coup avant la Chance."""
        combat = (verified_entry(self.book_event_catalogue, self.current_paragraph) or {}).get('combat', {})
        if combat.get('defense_roll'):
            _, die = self._roll(1, context='Combat — Protection d’invisibilité')
            return (2 if die % 2 else 1 if die in (2, 4) else 0,
                    'Invisibilité : coup paré (6), aucun dégât')
        return 2, ''

    def _ff_reduce_damage(self, damage):
        """Le bouclier au croissant est un objet du Sorcier, pas une protection universelle."""
        if self.character.get('shield_equipped') and SHIELD_NAME in self.character.get('inventory', []):
            rolls, total = self._roll(1, context='Combat — Bouclier au croissant')
            reduced = shield_damage(damage, total)
            return reduced, f' Bouclier {rolls}: -{damage - reduced} dégât.'
        return damage, ''

    def _ff_after_enemy_damage(self, damage):
        """Conserver la blessure du Crocodile pour la rencontre des Piranhas."""
        if self.crocodile_combat and self.current_paragraph == 86 and damage > 0:
            self.crocodile_combat['wounded'] = True

    def _ff_after_hit(self):
        """Résoudre les sorties spéciales : premier coup, Chien et combat ordinaire."""
        self._finish_single_book_combat(successful_hit=True)

    def _ff_after_player_damage(self, damage):
        """Appliquer les compteurs de blessures de la Goule et du Loup-Garou."""
        self._book_wound(damage)

    def _ff_pending_combat(self, combat):
        """Le Sorcier possède des rencontres errantes et un tirage initial de Piranhas."""
        return bool((combat.get('mode') == 'wandering' and not self._book_state(self.current_paragraph).get('monster'))
                    or (combat.get('mode') == 'piranhas' and (self.piranha_combat or {}).get('status') == 'roll_pending'))

    def _ff_escape_details(self, combat):
        """Le Vampire exige une autre destination et un délai renouvelé après un échec."""
        destinations = [combat['escape_target']]
        threshold = combat.get('escape_after_assaults', 0)
        hint = 'Fuir avec la blessure de fuite prévue par les règles.'
        if combat.get('escape_luck_interval'):
            destinations.append(combat['hypnosis_target'])
            threshold = max(threshold, self._book_state(self.current_paragraph).get('escape_after', threshold))
            hint = 'Tenter votre Chance pour fuir ; une blessure de fuite reste due.'
        return destinations, threshold, hint

    def _ff_escape_override(self, number, rules):
        """Traiter les sorties après victoire et la fuite particulière du Vampire."""
        target = rules.get('escape_target')
        if (rules.get('mode') == 'fire_breath'
                and self.character.get('book_facts', {}).get(rules['victory_fact'])):
            if target in self.paragraphs and self.character['endurance'] > 0:
                self.go_to(target)
            return True
        if number == 179 and self.character.get('book_facts', {}).get('minotaur_dead'):
            if target in self.paragraphs:
                self.go_to(target)
            return True
        if rules.get('escape_luck_interval'):
            if self.can_flee_combat():
                self._vampire_escape(rules)
            return True
        return False

    def _arrival_meal(self, entry):
        """Repas promis par le paragraphe précédent (§158 et §316 vers la berge §218)."""
        sources = (entry or {}).get('optional_meal_from')
        if not sources or not self.transitions:
            return False
        previous, number = self.transitions[-1]
        return number == self.current_paragraph and previous in sources

    def _ff_meal_status(self):
        """Étendre les repas ordinaires : partage, banc enchanté et retour des Piranhas."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
        char = self.character
        meal = (entry.get('optional_meal') or entry.get('optional_meal_restore') == 2
                or entry.get('enchanted_meal') or self._arrival_meal(entry))
        meal = meal or (self.current_paragraph == 7 and self.piranha_combat and self.piranha_combat.get('status') == 'victory')
        useful = char['endurance'] < char.get('initial', {}).get('endurance', char['endurance'])
        if entry.get('enchanted_meal'):
            useful = useful or char['habilete'] < char.get('initial', {}).get('habilete', char['habilete'])
        taken = self._book_state(self.current_paragraph).get('care_meal_taken')
        if entry.get('enchanted_meal') and self.current_paragraph in self.completed_book_events:
            taken = True
        return bool(meal), useful, taken

    def _ff_take_meal(self):
        """Conserver les effets particuliers des repas du Sorcier."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph) or {}
        if entry.get('enchanted_meal'):
            self.take_enchanted_meal()
        elif entry.get('optional_meal_restore') == 2:
            self.eat_shared_meal()
        else:
            self.eat_meal()

    def _ff_record_assault(self):
        """Ajouter le compteur du Crocodile au compteur de fuite commun."""
        if self.crocodile_combat and self.current_paragraph == self.crocodile_combat['paragraph']:
            self.crocodile_combat['assaults'] += 1
        FightingFantasyActions._ff_record_assault(self)

    def _ff_finish_assault(self, number):
        """Terminer les phases propres au Sorcier avant d'enregistrer la transaction."""
        if self._book_round_played:
            self._finish_complex_round(number)
        self._finish_crocodile_round()
        self._finish_piranha_round()
        FightingFantasyActions._ff_finish_assault(self, number)
