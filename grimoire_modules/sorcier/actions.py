"""Interactions particulières de l'édition vérifiée, sans texte narratif embarqué.

BookActions est un mixin de MainWindow : il utilise son personnage, ses widgets,
_roll, go_to et les marqueurs de progression. Il ne possède pas de constructeur.
Les données persistantes spécifiques à un paragraphe sont dans character.book_state
avec des clés chaînes, compatibles JSON. Ne pas conserver une décision de jeu
uniquement dans un widget : sauvegarde et annulation doivent la restaurer aussi."""
import copy
import re

from PySide6.QtWidgets import QPushButton, QMessageBox, QInputDialog
from book_events import (apply_effects, condition_met,
                         verified_entry, combat_skill, shield_damage, SHIELD_NAME,
                         equipped_weapon, throw_diversion_item)


from grimoire_modules.fighting_fantasy.controller import FightingFantasyActions


class BookActions(FightingFantasyActions):
    """Mélange de contrôleur pour les règles particulières, utilisant les services de MainWindow."""

    def _book_blocked(self, target):
        """Refuser les sorties résolues exclusivement par une action spéciale ou un combat en cours."""
        entry = verified_entry(self.book_event_catalogue, self.current_paragraph)
        if not entry:
            return False
        if self.character['endurance'] <= 0:
            return True
        number = self.current_paragraph
        special = entry.get('special')
        state = self._book_state(number)
        if special in ('rope', 'three_luck', 'cards', 'keys', 'key_trap',
                       'identify_loot', 'identify_next', 'wandering', 'stake_luck', 'armor_choice', 'chest_luck'):
            return True  # Ces sorties sont résolues exclusivement par leur action.
        if entry.get('mode') == 'des' and number not in self.completed_book_events:
            return True
        if special == 'paired_combat':
            return number not in self.completed_book_events
        combat = entry.get('combat', {})
        if number in (212, 393) and target == 369 and 369 in self.visited_paragraphs:
            return True
        if number == 173 and target == 24:
            return True  # La troisième blessure déclenche elle-même cette sortie.
        if (special == 'opening_luck' and not state.get('opening_done')):
            return True
        if (number == 179 and self.character.get('book_facts', {}).get('minotaur_dead')):
            return target != 54
        if target == combat.get('defeat_target'):
            return not state.get('defeated')
        return False

    def _book_buttons(self, entry):
        """Créer les commandes spéciales autorisées par le catalogue et leur progression locale."""
        number = self.current_paragraph
        special = entry.get('special')
        state = self._book_state(number)

        def button(label, action, payload=None, enabled=True):
            """Créer une commande locale en capturant action et payload pour éviter la capture tardive."""
            b = QPushButton(label)
            b.setProperty('combatAction', action in ('pair_target', 'opening_luck', 'silver_arrow', 'wandering'))
            b.setEnabled(enabled and self.character['endurance'] > 0)
            b.clicked.connect(lambda checked=False, a=action, p=payload:
                              self.perform_book_action(a, p))
            self.event_layout.addWidget(b)

        actions = {
            'rope': [('Tenter sa Chance pour couper la corde', 'rope')],
            'three_luck': [(f"Tenter sa Chance ({state.get('successes', 0)}/3 réussites)", 'three_luck')],
            'cards': [('Jouer les cartes avec 2d6', 'cards'),
                      ('Jouer les cartes en tentant sa Chance', 'cards_luck')],
            'wager': [('Parier de 1 à 20 pièces d’or', 'wager')],
            'keys': [('Essayer trois clés numérotées', 'keys')],
            'key_trap': [('Éviter les fléchettes : tenter sa Chance', 'key_trap')]
                if not state.get('trap_resolved') else [('Essayer trois autres clés', 'keys')],
            'wandering': [('Tirer le monstre errant (1d6)', 'wandering')]
                if not state.get('monster') else [],
            'identify_loot': [('Identifier la première trouvaille', 'identify')],
            'identify_next': [('Identifier la trouvaille suivante / repartir', 'identify_next')],
            'stake_luck': [('Projeter l’épieu : tenter sa Chance', 'stake_luck')]
                if not state.get('resolved') else [('Fuir par la porte ouest', 'stake_escape'),
                                                    ('Continuer contre le Vampire', 'stake_continue')],
            'opening_luck': [('Éviter la carcasse : tenter sa Chance', 'opening_luck')]
                if not state.get('opening_done') else [],
            'chest_luck': [('Frapper le coffre : tenter sa Chance', 'chest_luck')],
            'armor_choice': [('Conserver mon armure et jeter celle trouvée', 'armor_old'),
                             ('Conserver l’armure trouvée et jeter l’ancienne', 'armor_new')],
        }
        if number in self.completed_book_events and state.get('target') in self.paragraphs:
            button('Reprendre l’issue déjà résolue', 'resolved_exit')
        if number not in self.completed_book_events or special in ('wager', 'keys', 'key_trap', 'identify_next'):
            for label, action in actions.get(special, []):
                button(label, action)
        if special == 'silver_arrow' and all(name in self.character.get('inventory', [])
                                           for name in ('Arc', 'Flèche d’argent')):
            button('Tirer la flèche d’argent : tenter sa Chance', 'silver_arrow')
        if special == 'paired_combat' and state.get('choose_pair'):
            pair = entry['combat']['pairs'][state['pair']]
            for index, enemy in enumerate(pair):
                button(f"Affronter {enemy['name']} H{enemy['skill']}/E{enemy['stamina']}", 'pair_target', index)
        selected = state.get('loot', [])
        if len(selected) < entry.get('loot_limit', 0):
            for choice in entry.get('loot_choices', []):
                if choice['id'] not in selected:
                    button(choice['label'], 'loot', choice['id'])
        if number == 161 and state.get('monster') and state.get('won'):
            button('Reprendre le passage après le monstre errant', 'wandering_exit')

    def _book_refresh(self):
        """Rafraîchir héros et actions après mutation, sans refaire une entrée dans le paragraphe."""
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def _resolve_fire_breath(self):
        """§249 : une esquive par assaut, indépendante des coups ordinaires."""
        use_luck = self._ask_combat_question(
            'Souffle de feu du chien',
            'Tenter votre Chance pour esquiver la flamme ?\n'
            'Sans Chance : 1d6, blessure de 1 Endurance sur 1 ou 2.\n'
            'Avec Chance : 2d6, blessure de 1 Endurance uniquement en cas d’échec.')
        if use_luck == QMessageBox.Yes:
            rolls, total = self._roll(2)
            hit = total > self.character['chance']
            self.character['chance'] = max(0, self.character['chance'] - 1)
            detail = f'Chance {rolls} = {total} (Chance -1)'
        else:
            rolls, total = self._roll(1)
            hit = total <= 2
            detail = f'1d6 {rolls} = {total}'
        damage = int(hit)
        self.character['endurance'] = max(0, self.character['endurance'] - damage)
        self._refresh_character()
        note = f'Souffle : {detail}, {damage} dégât.'
        self._log_combat_detail(note)
        if self.character['endurance'] <= 0:
            self._log_assault([], [], 0, 0, 'Souffle mortel avant les attaques')
            self.rules_log.setText(note + ' Votre Endurance est à zéro.')
            self._book_refresh()
            return False
        return True

    def _finish_fire_dog(self, combat):
        """La victoire donne le bonus une fois ; le joueur choisit sa sortie."""
        key = combat['victory_fact']
        if not self.character.get('book_facts', {}).get(key):
            apply_effects(self.character, combat.get('victory_effects', []))
            self.character.setdefault('book_facts', {})[key] = True
        self._book_refresh()

    def _enter_complex_book(self, number, previous):
        """Appliquer les effets uniques / de visite et préparer les états particuliers.

        Distinguer une nouvelle visite d’un simple rafraîchissement ; conserver la bonne
        source de retour des monstres errants et la continuité des adversaires multi-paragraphes."""
        entry = verified_entry(self.book_event_catalogue, number)
        if not entry:
            return
        if entry.get('entry_effects') and not self._book_state(number).get('entry_effects_applied'):
            apply_effects(self.character, entry['entry_effects'])
            self._book_state(number, True)['entry_effects_applied'] = True
        if previous != number:
            visits = self.character.setdefault('book_visits', {})
            before = visits.get(str(number), 0)
            visits[str(number)] = before + 1
            apply_effects(self.character, entry.get('visit_effects', []))
            if entry.get('special') == 'key_trap':
                self._book_state(number, True)['trap_resolved'] = False
        if entry.get('encounter_return') is not None:
            self._book_state(161, True)['return_target'] = entry['encounter_return']
        source = verified_entry(self.book_event_catalogue, previous)
        if number == 161 and source and source.get('encounter_return') is not None:
            state = self._book_state(161, True)
            state['source'] = previous
            state['return_target'] = source['encounter_return']
            state.pop('monster', None)
            state.pop('won', None)
            self.completed_book_events.discard(161)
        if (number == 161 and not (source and source.get('encounter_return') is not None)
                and not self._book_state(161).get('monster')):
            # Aucun numéro de retour ne peut être déduit d'une entrée isolée.
            self._book_state(161, True).pop('return_target', None)
        mode = entry.get('combat', {}).get('mode')
        if mode in ('ghoul', 'silver', 'invulnerable', 'paired'):
            state = self._book_state(number, True)
            if number not in self.prepared_book_encounters:
                # Les §§211, 173 et 24 décrivent le même adversaire.
                if number in (173, 24) and previous in (211, 173, 24, 310):
                    if number == 24:
                        apply_effects(self.character, [{'kind':'stat', 'key':'habilete', 'amount':-1}])
                else:
                    self._set_book_enemy(entry['combat']['enemies'][0])
                self.prepared_book_encounters.add(number)
                state['started'] = True
        if number == 17 and previous == 279:
            self._book_state(17, True).clear()
        self._refresh_character()

    def perform_book_action(self, action, payload=None):
        """Dispatcher les identifiants d’actions du catalogue vers leur résolution.

        Appelé par les boutons ; l’enveloppe de MainWindow assure historique et autosave.
        Les payloads désignent un choix ou adversaire, jamais du code à exécuter."""
        number = self.current_paragraph
        entry = verified_entry(self.book_event_catalogue, number)
        if not entry or self.character['endurance'] <= 0:
            return
        if action == 'resolved_exit':
            target = self._book_state(number).get('target')
            if number in self.completed_book_events and target in self.paragraphs:
                self.go_to(target)
            return
        special = entry.get('special')
        permitted = {
            'rope': {'rope'}, 'three_luck': {'three_luck'},
            'cards': {'cards', 'cards_luck'}, 'wager': {'wager'},
            'keys': {'keys'}, 'key_trap': {'keys', 'key_trap'},
            'wandering': {'wandering', 'wandering_exit'},
            'identify_loot': {'identify'}, 'identify_next': {'identify_next'},
            'stake_luck': {'stake_luck', 'stake_escape', 'stake_continue'},
            'silver_arrow': {'silver_arrow'}, 'paired_combat': {'pair_target'},
            'opening_luck': {'opening_luck'}, 'armor_choice': {'armor_old', 'armor_new'},
            'chest_luck': {'chest_luck'},
        }
        if action != 'loot' and action not in permitted.get(special, set()):
            return
        state = self._book_state(number)
        if action != 'loot' and number in self.completed_book_events and special not in ('wager', 'keys', 'key_trap', 'identify_next', 'wandering'):
            return
        if action == 'loot':
            choices = entry.get('loot_choices', [])
            choice = next((c for c in choices if c['id'] == payload), None)
            chosen = state.get('loot', [])
            if not choice or payload in chosen or len(chosen) >= entry.get('loot_limit', 0):
                return
            state = self._book_state(number, True)
            state.setdefault('loot', []).append(payload)
            apply_effects(self.character, choice['effects'])
        elif action in ('rope', 'three_luck', 'key_trap', 'stake_luck', 'silver_arrow', 'opening_luck', 'chest_luck'):
            self._resolve_complex_luck(action, entry)
        elif action in ('cards', 'cards_luck', 'wager'):
            self._play_book_game(action)
        elif action == 'keys':
            if special == 'key_trap' and not state.get('trap_resolved'):
                return
            self._try_book_keys()
        elif action in ('identify', 'identify_next'):
            self._identify_book_loot(action == 'identify_next')
        elif action == 'wandering':
            if state.get('monster') or state.get('return_target') not in self.paragraphs:
                self.rules_log.setText('Il faut arriver du §295 ou §306 avec une destination de retour chargée.')
                return
            _, face = self._roll(1)
            monster = entry['combat']['enemies'][face - 1]
            self._book_state(161, True)['monster'] = copy.deepcopy(monster)
            self._set_book_enemy(monster)
        elif action == 'wandering_exit':
            if state.get('won') and state.get('return_target') in self.paragraphs:
                self.go_to(state['return_target'])
        elif action in ('stake_escape', 'stake_continue'):
            if state.get('resolved') and not state.get('won'):
                target = 380 if action == 'stake_escape' else 144
                if target in self.paragraphs:
                    self.go_to(target)
        elif action == 'pair_target':
            if not state.get('choose_pair') or payload not in (0, 1):
                return
            state = self._book_state(number, True)
            pair = entry['combat']['pairs'][state['pair']]
            state['defender'] = copy.deepcopy(pair[1-payload])
            self._remember_monster(state['defender']['name'])
            state['choose_pair'] = False
            self._set_book_enemy(pair[payload])
        elif action in ('armor_old', 'armor_new'):
            discarded = 'Armure trouvée' if action == 'armor_old' else 'Armure de cuir'
            retained = 'Armure de cuir' if action == 'armor_old' else 'Armure trouvée'
            inventory = self.character.get('inventory', [])
            if retained not in inventory or discarded in self.character.get('locked_items', []) or 319 not in self.paragraphs:
                return
            if discarded in inventory:
                inventory.remove(discarded)
            self.completed_book_events.add(number)
            self._book_state(number, True)['target'] = 319
            self.go_to(319)
        self._book_refresh()

    def _resolve_complex_luck(self, action, entry):
        """Résoudre le test de Chance propre à l’action et mémoriser son issue et sa destination."""
        number = self.current_paragraph
        state = self._book_state(number)
        target = {'rope':73, 'three_luck':162, 'stake_luck':327, 'silver_arrow':135, 'chest_luck':139}.get(action)
        needed = {'rope':[73], 'three_luck':[108,162], 'stake_luck':[327,380,144],
                  'silver_arrow':[135], 'chest_luck':[139]}.get(action, [])
        if any(t not in self.paragraphs for t in needed):
            self.rules_log.setText('Une destination nécessaire à cette épreuve n’est pas chargée.')
            return
        if action == 'key_trap' and state.get('trap_resolved'):
            return
        if action == 'stake_luck' and state.get('resolved'):
            return
        if action == 'opening_luck' and state.get('opening_done'):
            return
        if action == 'chest_luck':
            sword = equipped_weapon(self.character)
            if sword is None or sword in self.character.get('locked_items', []):
                self.rules_log.setText('Il faut une épée utilisable pour frapper le coffre.')
                return
        if action == 'silver_arrow' and not all(name in self.character.get('inventory', [])
                                              for name in ('Arc', 'Flèche d’argent')):
            return
        _, total = self._roll(2)
        lucky = total <= self.character['chance']
        self.character['chance'] = max(0, self.character['chance'] - 1)
        state = self._book_state(number, True)
        if action == 'rope':
            if lucky:
                self.completed_book_events.add(number)
                state['target'] = target
                self.go_to(target)
            else:
                self.character['endurance'] = max(0, self.character['endurance']-1)
        elif action == 'three_luck':
            if lucky:
                state['successes'] = state.get('successes', 0) + 1
            if not lucky or state['successes'] == 3:
                self.completed_book_events.add(number)
                state['target'] = target if lucky else 108
                self.go_to(target if lucky else 108)
        elif action == 'key_trap':
            state['trap_resolved'] = True
            if lucky:
                self.character['endurance'] = max(0, self.character['endurance'] - 2)
            else:
                self.character['endurance'] = 0
        elif action == 'stake_luck':
            state.update(resolved=True, won=lucky)
            if lucky:
                self.completed_book_events.add(number)
                state['target'] = target
                self.go_to(target)
            else:
                state['vampire_stamina'] = 7
        elif action == 'silver_arrow':
            self.character['inventory'].remove('Flèche d’argent')
            if lucky:
                self.enemy_endurance.setValue(0)
                self.completed_book_events.add(number)
                self.go_to(target)
        elif action == 'opening_luck':
            state['opening_done'] = True
            if not lucky:
                self.character['endurance'] = max(0, self.character['endurance']-1)
        elif action == 'chest_luck':
            self.completed_book_events.add(number)
            if lucky:
                throw_diversion_item(self.character, sword)
                state['target'] = target
                self.go_to(target)
            else:
                self.character['endurance'] = 0
        self.rules_log.setText(f'Épreuve §{number} : {total}, Chance -1 ; ' + ('réussite.' if lucky else 'échec.'))

    def _play_book_game(self, action):
        """Résoudre cartes ou pari avec mise contrôlée et jets fournis par le contrôleur."""
        number = self.current_paragraph
        if action == 'wager':
            maximum = min(20, int(self.character.get('gold', 0)))
            if maximum < 1:
                return
            stake, accepted = QInputDialog.getInt(self, 'Pari', 'Mise en pièces d’or :', 1, 1, maximum)
            if not accepted or not 1 <= stake <= min(20, self.character.get('gold', 0)):
                return
            _, player = self._roll(2)
            _, opponent = self._roll(2)
            delta = stake if player > opponent else -stake if player < opponent else 0
            if delta > 0:
                apply_effects(self.character, [{'kind':'stat','key':k,'amount':2}
                                              for k in ('habilete','endurance','chance')])
        else:
            if number in self.completed_book_events or 131 not in self.paragraphs:
                return
            _, total = self._roll(2)
            if action == 'cards_luck':
                lucky = total <= self.character['chance']
                self.character['chance'] = max(0, self.character['chance']-1)
                if lucky:
                    _, total = self._roll(2)
                    delta = total
                else:
                    delta = -total
            else:
                delta = total if total % 2 else -total
            if delta > 0:
                apply_effects(self.character, [{'kind':'stat','key':'chance','amount':2}])
            self.completed_book_events.add(number)
            self._book_state(number, True)['target'] = 131
        apply_effects(self.character, [{'kind':'stat','key':'gold','amount':delta}])
        if action != 'wager':
            self.go_to(131)
        self.rules_log.setText(f'Jeu du §{number} : {delta:+} pièces d’or (perte limitée à la bourse).')

    def _try_book_keys(self):
        """Demander trois clés possédées, calculer leur combinaison et suivre l’issue autorisée."""
        keys = {}
        for name in self.character.get('inventory', []):
            if re.match(r'(?i)^cl[ée]\b', name):
                match = re.search(r'\b(\d+)\b', name)
                if match:
                    keys.setdefault(name.casefold(), (name, int(match[1])))
        if len(keys) < 3:
            self.rules_log.setText('Trois clés numérotées distinctes sont nécessaires ; aventure sans issue ici.')
            return
        selected = []
        for index in range(3):
            names = [name for name, number in keys.values() if name not in selected]
            chosen, accepted = QInputDialog.getItem(self, 'Serrures du coffre',
                f'Clé {index+1}/3 :', names, 0, False)
            if not accepted or chosen not in names:
                return
            selected.append(chosen)
        combination = sorted(keys[name.casefold()][1] for name in selected)
        state = self._book_state(139)
        target = sum(combination)
        if combination in state.get('tried', []) or target not in self.paragraphs:
            self.rules_log.setText('Combinaison déjà essayée ou destination absente ; aucune clé consommée.')
            return
        self._book_state(139, True).setdefault('tried', []).append(combination)
        if target == self.current_paragraph:
            if target == 198:
                self._book_state(198, True)['trap_resolved'] = False
            elif target == 182:
                apply_effects(self.character, [{'kind':'stat','key':'endurance','amount':-2}])
        self.go_to(target)

    def _identify_book_loot(self, next_item):
        """Faire progresser l’identification des trouvailles sans dépasser le butin autorisé."""
        state = self._book_state(313)
        selected = state.get('loot', [])
        index = self._book_state(319).get('index', 0) if next_item else 0
        if next_item:
            index += 1
        catalogue = verified_entry(self.book_event_catalogue, 313)
        if not catalogue:
            return
        choices = {c['id']:c for c in catalogue['loot_choices']}
        if index < len(selected):
            target = choices[selected[index]]['identify_target']
        else:
            target = 81
        if target not in self.paragraphs:
            return
        self._book_state(319, True)['index'] = index
        self.go_to(target)

    def _vampire_escape(self, rules):
        """Résoudre la sortie particulière du Vampire selon les règles cataloguées."""
        number = self.current_paragraph
        assaults = self.book_combat_assaults.get(number, 0)
        state = self._book_state(number)
        earliest = state.get('escape_after', rules['escape_after_assaults'])
        if assaults < earliest or any(t not in self.paragraphs for t in (rules['escape_target'], rules['hypnosis_target'])):
            return
        _, total = self._roll(2)
        lucky = total <= self.character['chance']
        self.character['chance'] = max(0, self.character['chance']-1)
        state = self._book_state(number, True)
        if lucky:
            # La blessure normale de fuite reste due ; le jet obligatoire vérifie
            # le droit de fuir, il ne réduit pas cette blessure.
            self.character['endurance'] = max(0, self.character['endurance']-2)
            if self.character['endurance'] > 0:
                self.go_to(rules['escape_target'])
        elif total >= 11:
            self.go_to(rules['hypnosis_target'])
        else:
            state['escape_after'] = assaults + rules['escape_luck_interval']
        self._book_refresh()

    def _complex_round_blocked(self):
        """Traiter les préconditions spéciales d’assaut et indiquer si l’assaut ordinaire est bloqué."""
        number = self.current_paragraph
        entry = verified_entry(self.book_event_catalogue, number)
        if not entry:
            return False
        if self.character['endurance'] <= 0:
            return True
        mode = entry.get('combat', {}).get('mode')
        if mode == 'wandering':
            return not self._book_state(number).get('monster')
        if mode == 'paired':
            return bool(self._book_state(number).get('choose_pair')) or number in self.completed_book_events
        if mode == 'silver' and not condition_met(self.character, {'kind':'silver_weapon'}):
            self.rules_log.setText('Une arme en argent est nécessaire pour ce combat.')
            return True
        if entry.get('special') == 'opening_luck' and not self._book_state(number).get('opening_done'):
            self.rules_log.setText('Tentez d’abord votre Chance pour éviter la carcasse.')
            return True
        if number == 179 and self.character.get('book_facts', {}).get('minotaur_dead'):
            return True
        return False

    def _book_wound(self, damage):
        """Mettre à jour les conséquences particulières d’une blessure effectivement reçue."""
        number = self.current_paragraph
        entry = verified_entry(self.book_event_catalogue, number)
        mode = entry.get('combat', {}).get('mode') if entry else None
        if mode not in ('ghoul', 'silver') or damage <= 0:
            return
        if mode == 'silver' and self.character['endurance'] <= 0:
            return
        state = self._book_state(173 if mode == 'silver' else number, True)
        state['wounds'] = state.get('wounds', 0) + 1
        if mode == 'ghoul' and (state['wounds'] >= 4 or self.character['endurance'] <= 0):
            self._book_state(number, True)['defeated'] = True
            self.completed_book_events.add(number)
            if 64 in self.paragraphs:
                self.go_to(64)
        if mode == 'silver' and state['wounds'] % 3 == 0:
            if number == 173 and 24 in self.paragraphs:
                self.go_to(24)
            else:
                apply_effects(self.character, [{'kind':'stat','key':'habilete','amount':-1}])

    def _finish_complex_round(self, number):
        """Terminer la logique spécifique au paragraphe après l’assaut suivi par le contrôleur."""
        entry = verified_entry(self.book_event_catalogue, number)
        if not entry or self.current_paragraph != number:
            return
        mode = entry.get('combat', {}).get('mode')
        if mode == 'paired':
            state = self._book_state(number, True)
            defender = state.get('defender')
            if defender and self.character['endurance'] > 0:
                # Deuxième attaque : le héros ne peut que parer ce Squelette.
                _, enemy_roll = self._roll(2, context='Combat — Deuxième Squelette', opponent=True)
                _, hero_roll = self._roll(2, context='Combat — Votre parade')
                if defender['skill'] + enemy_roll > combat_skill(self.character) + hero_roll:
                    damage = 2
                    answer = self._ask_combat_question('Deuxième Squelette',
                        'Tenter votre Chance pour réduire cette blessure ?')
                    if answer == QMessageBox.Yes:
                        _, total = self._roll(2)
                        damage = 1 if total <= self.character['chance'] else 3
                        self.character['chance'] = max(0, self.character['chance']-1)
                    if self.character.get('shield_equipped') and SHIELD_NAME in self.character.get('inventory', []):
                        _, die = self._roll(1)
                        damage = shield_damage(damage, die)
                    self.character['endurance'] = max(0, self.character['endurance']-damage)
                    self._log_combat_detail(f"{defender['name']} : attaque {defender['skill'] + enemy_roll} ; "
                        f"votre parade {combat_skill(self.character) + hero_roll}. Héros -{damage} Endurance.")
                else:
                    self._log_combat_detail(f"{defender['name']} : deuxième attaque parée.")
            if self.enemy_endurance.value() <= 0 and self.character['endurance'] > 0:
                pair = state.get('pair', -1) + 1
                if pair >= len(entry['combat']['pairs']):
                    self.completed_book_events.add(number)
                    state['target'] = entry['combat']['victory_target']
                    if 395 in self.paragraphs:
                        self.go_to(395)
                else:
                    state.update(pair=pair, choose_pair=True)
                    state.pop('defender', None)
        elif mode == 'wandering' and self.enemy_endurance.value() <= 0 and self.character['endurance'] > 0:
            state = self._book_state(number, True)
            state['won'] = True
            target = state.get('return_target')
            if state.get('source') == 12:
                self.character.setdefault('book_facts', {})['alarm12_done'] = True
            if target in self.paragraphs:
                self.go_to(target)
        self._book_refresh()
