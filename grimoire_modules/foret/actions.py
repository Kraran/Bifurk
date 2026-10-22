"""Relier les services déterministes de la Forêt aux transactions et dés de Qt.

Comme les autres adaptateurs, les méthodes sont déléguées à MainWindow. Appeler
explicitement le socle plutôt que super(), puisque self n’est pas une instance
physique de ce mixin. Aucune décision persistante n’est conservée dans un widget.
"""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, QSpinBox,
                               QPushButton, QInputDialog, QMessageBox, QListWidget, QAbstractItemView)
from . import rules
from .encounters import COMBATS
from ..fighting_fantasy.controller import FightingFantasyActions
from ..fighting_fantasy.rules import spend_luck, combat_damage, escape_damage


class ForetMechanicsActions(FightingFantasyActions):
    def _ff_weapon_choices(self):
        return [name for name in rules.FOREST_WEAPONS if name in self.character.get('inventory', [])]

    def _ff_equipped_weapon(self):
        return rules.forest_weapon(self.character)

    def _ff_equip_weapon(self, name):
        return rules.equip_forest_weapon(self.character,name)

    def _ff_meal_status(self):
        """Règles page PDF 9 : repas répétés permis hors combat, sans autorisation de lieu.

        Les repas imposés par la chaise/convalescence passent par leur action
        spécifique ; les remplacer par un repas ordinaire contournerait leur effet.
        """
        useful = self.character['endurance'] < self.character['initial']['endurance']
        forced = self.current_paragraph in (304,328) and not self._book_state(self.current_paragraph).get('foret_resolved')
        return not self.combat_available() and not forced, useful, False

    def _ff_item_removed(self, name):
        """Un retrait manuel emporte sa charge et son bonus de port, sans charge fantôme."""
        data = rules.state(self.character)
        if name in data.get('charges', {}):
            data['charges'][name] = max(0,data['charges'][name]-1)
        if name in data.get('worn', []):
            data['worn'].remove(name)
        if self.character.get('equipped_weapon') == name:
            self.character['equipped_weapon'] = None

    def _combat_entry(self, number):
        """Valider les seuls profils intégrés, sans valider toutes les règles du passage."""
        profile = COMBATS.get(number)
        if profile is None:
            return None
        return {'combat':{'mode':'paired', **profile}}

    def _foret_combat(self):
        """Lire le combat courant, éventuellement partagé entre deux renvois."""
        profile = COMBATS.get(self.current_paragraph)
        if not profile:
            return None
        return rules.peek(self.character).get('combats', {}).get(profile['identity'])

    def _foret_prepare_combat(self):
        """Préparer une fois la rencontre ; relecture et chargement conservent les blessures."""
        profile = COMBATS.get(self.current_paragraph)
        if not profile or self._restoring:
            return
        encounters = rules.state(self.character).setdefault('combats', {})
        identity = profile['identity']
        if identity not in encounters:
            encounters[identity] = rules.new_group_combat(profile['groups'])
            rules.begin_encounter(self.character, identity)
        self._foret_sync_enemy()

    def _foret_sync_enemy(self):
        """Raccorder la cible sauvegardée aux widgets utilisés par les dés et le dialogue."""
        combat = self._foret_combat()
        if not combat or combat['finished'] or combat.get('escaped'):
            return
        group = combat['groups'][combat['group']]
        living = [index for index, enemy in enumerate(group) if enemy['stamina'] > 0]
        if combat['target'] not in living:
            combat['target'] = living[0]
        self._set_book_enemy(group[combat['target']])

    def _combat_roster(self):
        """Le dialogue relit tous les ennemis persistants, y compris les cibles non actives."""
        combat = self._foret_combat()
        if not combat:
            return None
        return [deepcopy(enemy) for group in combat['groups'] for enemy in group]

    def _complex_round_blocked(self):
        """Pas de précondition cachée : une cible vivante suffit à préparer l’assaut."""
        return not self.combat_available()

    def combat_available(self):
        combat = self._foret_combat()
        return bool(combat and not combat['finished'] and not combat.get('escaped')
                    and self.character['endurance'] > 0 and self._adventurer_draft is None)

    def combat_flee_status(self):
        if not self.combat_available():
            return False, 'Aucun combat en cours.'
        return FightingFantasyActions.combat_flee_status(self)

    def _ff_combat_profile(self):
        profile = COMBATS.get(self.current_paragraph, {})
        return {'skill':rules.forest_combat_skill(self.character), 'hit_damage':2,
                'can_wound':rules.forest_weapon(self.character) is not None,
                'attack_bonus':rules.attack_bonus(self.character, self.current_paragraph, profile.get('identity'))}

    def _ff_defend_hit(self):
        """Protection de l’empereur AVANT le choix facultatif de Chance."""
        if 'Bouclier d’empereur' in rules.peek(self.character).get('worn', []):
            _, die = self._roll(1, context='Bouclier d’empereur — protection sur 4, 5 ou 6')
            return rules.shield_damage(self.character, 2, die), ''
        return 2, ''

    def _ff_after_attack_rolls(self):
        """Intercaler le fouet après les forces d’attaque, avant les blessures ordinaires."""
        if self.current_paragraph != 107:
            return True
        _, die = self._roll(1, context='Démon de Feu — fouet')
        total = None
        if die <= 2 and self._ask_combat_question('Le fouet vous atteint',
                'Tenter votre Chance pour éviter cette blessure ?') == QMessageBox.Yes:
            _, total = self._roll(2, context='Chance — esquiver le fouet')
        lost = rules.whip(self.character, die, total)
        self._log_combat_detail(f'Fouet : dé {die}, -{lost} Endurance.')
        self._refresh_character()
        return self.character['endurance'] > 0

    def _ff_enemy_defeated(self):
        """La fin du groupe attend la seconde attaque, même si la cible offensive meurt."""

    def _ff_after_hit(self):
        """La sortie de rencontre est résolue après les attaques restantes du groupe."""

    def _ff_after_player_damage(self, damage):
        """Compter les coups réellement blessants pour la Goule et la lycanthropie."""
        profile = COMBATS.get(self.current_paragraph)
        if not profile or damage <= 0:
            return
        wounds = rules.state(self.character).setdefault('wounds', {})
        identity = profile['identity']
        wounds[identity] = wounds.get(identity, 0) + 1
        if identity == 'ghoul' and rules.ghoul_paralysed(self.character, identity):
            self.character['endurance'] = 0
            self._log_combat_detail('Quatrième blessure de la Goule : paralysie et fin de l’aventure.')

    def combat_round(self):
        """Un jet offensif, puis une parade distincte contre chaque autre ennemi vivant."""
        if not self.combat_available():
            return
        combat = self._foret_combat()
        group = combat['groups'][combat['group']]
        target = combat['target']
        defenders = [enemy for index, enemy in enumerate(group) if index != target and enemy['stamina'] > 0]
        FightingFantasyActions.combat_round(self)
        group[target]['stamina'] = self.enemy_endurance.value()
        for defender in defenders:
            if self.character['endurance'] <= 0:
                break
            enemy_rolls, enemy_total = self._roll(2, context='Combat — ' + defender['name'], opponent=True)
            hero_rolls, hero_total = self._roll(2, context='Combat — parade contre ' + defender['name'])
            hero_attack = self._ff_combat_profile()['skill'] + hero_total + self._ff_combat_profile()['attack_bonus']
            enemy_attack = defender['skill'] + enemy_total
            damage = 0
            if enemy_attack > hero_attack:
                base, _ = self._ff_defend_hit()
                lucky = None
                if self._assault_luck_choice('Une seconde attaque vous touche',
                        f'{defender["name"]} : attaque {enemy_attack}, votre parade {hero_attack}.',
                        'Tenter votre Chance pour réduire la blessure ?') == QMessageBox.Yes:
                    _, total = self._roll(2, context='Chance — réduire la seconde blessure')
                    lucky = spend_luck(self.character, total)
                damage = combat_damage(base, attacking=False, lucky=lucky)
                rules.damage_hero(self.character, damage)
                self._ff_after_player_damage(damage)
            self._log_combat_detail(f'{defender["name"]} : {enemy_rolls} → {enemy_attack} ; '
                                    f'parade {hero_rolls} → {hero_attack}. Héros -{damage} Endurance.')
        combat['assaults'] += 1
        if self.character['endurance'] > 0:
            rules.advance_group(combat)
            if combat['finished']:
                self.completed_book_events.add(self.current_paragraph)
                profile = COMBATS[self.current_paragraph]
                target = profile['victory_target']
                if target in self.paragraphs:
                    self.go_to(target)
            else:
                self._foret_sync_enemy()
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def escape_scripted_combat(self, number):
        """Appliquer le même délai et la même blessure depuis le lecteur et la popup."""
        if number != self.current_paragraph or not self.can_flee_combat():
            return
        _, total = (None, None)
        if self._ask_combat_question('Fuir', 'Tenter votre Chance pour la blessure de fuite ?') == QMessageBox.Yes:
            _, total = self._roll(2, context='Chance — fuite')
        damage, cost = escape_damage(self.character['chance'], total)
        self.character['chance'] = max(0, self.character['chance'] - cost)
        rules.damage_hero(self.character, damage)
        self._foret_combat()['escaped'] = True
        self._remember_monster(self.enemy_name.text(), 'fui')
        self._refresh_character()
        if self.character['endurance'] > 0:
            self.go_to(COMBATS[number]['escape_target'])

    def _foret_mechanics_buttons(self):
        """Afficher les seules commandes implantées, en revérifiant tout au clic."""
        def add(label, action, payload=None, enabled=True, combat=False):
            button = QPushButton(label)
            button.setEnabled(enabled and self.character['endurance'] > 0)
            button.setProperty('combatAction', combat)
            if action == 'shop':
                button.clicked.connect(lambda checked=False: self._foret_shop())
            elif action == 'payment_dialog':
                button.clicked.connect(lambda checked=False: self._foret_payment_dialog())
            else:
                button.clicked.connect(lambda checked=False: self.perform_foret_action(action, payload))
            self.event_layout.addWidget(button)
        number = self.current_paragraph
        if number in rules.ENTRY_RULES and not rules.entry_resolved(self.character, number):
            rule = rules.ENTRY_RULES[number]
            label = ('Utiliser ' + rule['use'] if rule.get('use') else
                     'Employer ' + ', '.join(rule['remove']) if rule.get('remove') else 'Recueillir la trouvaille')
            label = rule.get('label',label)
            add(label, 'entry', enabled=(not rule.get('use') or rules.available(self.character, rule['use']) > 0)
                and all(name in self.character.get('inventory', []) for name in rule.get('remove', [])))
        if number in rules.PAYMENT_PARAGRAPHS and not rules.payment_resolved(self.character, number):
            add('Choisir le paiement…', 'payment_dialog')
        if number == 388 and not self._book_state(number).get('foret_resolved'):
            add('Vérifier les blessures du Loup-Garou', 'werewolf_exit')
        if number == 261:
            add('Acheter chez Yaztromo…', 'shop')
        if self.combat_available():
            combat = self._foret_combat()
            group = combat['groups'][combat['group']]
            for index, enemy in enumerate(group):
                if enemy['stamina'] > 0:
                    add(('⚔ ' if index == combat['target'] else '') + 'Cibler ' + enemy['name'],
                        'target', index, combat=True)
        for name in rules.peek(self.character).get('worn', []):
            if name != 'Anneau de Lenteur':
                add('Retirer ' + name, 'unwear', name)
        for name in rules.EQUIPMENT:
            if name in self.character.get('inventory', []) and name not in rules.peek(self.character).get('worn', []):
                add('Porter ' + name, 'wear', name)
        if 'Potion de Force' in self.character.get('inventory', []):
            add('Boire la Potion de Force (+5 Endurance)', 'force_potion')
        if number == 219 and 'silver_dart' not in rules.peek(self.character).get('rewards', []):
            add('Emporter la fléchette d’argent', 'take_dart')
        if number == 242 and 'heavy_ingot' not in rules.peek(self.character).get('rewards', []):
            add('Prendre le lingot contre un objet…', 'ingot')
        commands = {70:('Prendre et utiliser l’épée enchantée', 'enchanted_sword'),
                    192:('Résoudre la métamorphose de l’épée', 'gnome_sword'),
                    46:('Jeter la carotte (Chance −2)', 'carrot'),
                    395:('Allumer la lanterne — Chance', 'lantern'),
                    370:('Choisir l’objet perdu…', 'lost_item'),34:('Choisir le vœu du génie…', 'wish'),308:('Intervertir Habileté et Chance', 'swap'),98:('Échapper à l’embuscade — Chance', 'ambush'),
                    259:('Affronter la fièvre — perte de 3 Endurance puis Chance', 'fever'),
                    278:('Tomber dans la fosse — Chance', 'spiked_pit'),73:('Éprouver la porte (2d6)', 'door'),309:('Éviter les deux fléchettes', 'darts'),
                    372:('Soulever le coffre (2d6)', 'lift'),266:('Choisir la mise du bras de fer…', 'wrestle'),
                    52:('Choisir la mise — utiliser le Brassard…', 'bracelet'),
                    304:('Attendre la guérison — cinq rations', 'convalescence'),
                    328:('Prendre le repas sur la chaise', 'cursed_meal'),
                    262:('Boire la potion des deux combats', 'combat_potion'),
                    204:('Remettre les deux parties du marteau', 'hammer')}
        if number in commands and not self._book_state(number).get('foret_resolved'):
            label, action = commands[number]
            add(label, action)

    def _foret_shop(self):
        """Panier explicite : le choix seul ne dépense rien ; chaque achat est une transaction."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Yaztromo — objets magiques')
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Chaque article acheté ne peut servir qu’une fois.'))
        selector = QComboBox()
        for name, price in rules.SHOP:
            selector.addItem(f'{name} — {price} pièces d’or', name)
        layout.addWidget(selector)
        quantity = QSpinBox()
        quantity.setRange(1,99)
        quantity.setPrefix('Quantité : ')
        layout.addWidget(quantity)
        balance = QLabel()
        layout.addWidget(balance)
        buy = QPushButton('Acheter')
        layout.addWidget(buy)
        def refresh():
            price = rules.PRICES[selector.currentData()] * quantity.value()
            balance.setText(f'Or disponible : {self.character.get("gold",0)} — total : {price}')
            buy.setEnabled(self.character.get('gold',0) >= price)
        def purchase():
            self.perform_foret_action('buy', (selector.currentData(), quantity.value()))
            refresh()
        selector.currentIndexChanged.connect(refresh)
        quantity.valueChanged.connect(refresh)
        buy.clicked.connect(purchase)
        close = QPushButton('Revenir au grimoire')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        refresh()
        dialog.exec()
        dialog.deleteLater()

    def _foret_payment_dialog(self):
        """Choisir chaque exemplaire et chaque pièce ; Annuler ne modifie pas la fiche."""
        number = self.current_paragraph
        if number not in rules.PAYMENT_PARAGRAPHS:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Le prix du passage')
        layout = QVBoxLayout(dialog)
        tariffs = {12:'10 Or OU deux objets précieux (bijoux, trésors ou objets magiques).',14:'3 Or, ou un objet magique si vous ne pouvez payer en or.',
                   32:'10 Or ET deux objets.',36:'Tout votre or OU deux achats magiques utilisables.',
                   218:'5 Or OU un objet magique.',279:'Cinq unités : chaque objet et chaque pièce compte pour une unité.',
                   297:'5 Or OU un objet.'}
        layout.addWidget(QLabel(tariffs[number]))
        gold = QSpinBox()
        gold.setRange(0,self.character.get('gold',0))
        gold.setPrefix('Pièces d’or : ')
        layout.addWidget(gold)
        items = QListWidget()
        items.setSelectionMode(QAbstractItemView.MultiSelection)
        items.addItems(self.character.get('inventory', []))
        layout.addWidget(items)
        note = QLabel('Sélectionnez les exemplaires que vous acceptez de donner.')
        layout.addWidget(note)
        confirm = QPushButton('Payer')
        layout.addWidget(confirm)
        def submit():
            self.perform_foret_action('payment', (gold.value(), [item.text() for item in items.selectedItems()]))
            if rules.payment_resolved(self.character, number):
                dialog.accept()
            else:
                note.setText(self.rules_log.text())
        confirm.clicked.connect(submit)
        cancel = QPushButton('Annuler')
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(cancel)
        dialog.exec()
        dialog.deleteLater()

    def care_options(self, *, in_combat=False):
        options = FightingFantasyActions.care_options(self, in_combat=in_combat)
        options.append({'id':'force_potion', 'label':'Potion de Force (+5 Endurance)',
                        'enabled':self.character['endurance'] > 0 and self._adventurer_draft is None
                                  and 'Potion de Force' in self.character.get('inventory', [])
                                  and self.character['endurance'] < self.character['initial']['endurance'],
                        'reason':'Aucune Potion de Force utile disponible.'})
        return options

    def use_care(self, kind):
        if kind == 'force_potion':
            option = self.care_options()[-1]
            if option['enabled']:
                self.perform_foret_action('force_potion')
        else:
            FightingFantasyActions.use_care(self, kind)

    def perform_foret_action(self, action, payload=None):
        """Commande transactionnelle : ne jamais faire confiance au bouton ou à un ancien signal."""
        if self._adventurer_draft is not None or self.current_paragraph is None:
            return
        # Le dialogue d’achat ne doit pas envelopper plusieurs achats dans une
        # transaction longue : chacun s’enregistre au clic sur Acheter.
        if action == 'shop':
            return
        if self.character['endurance'] <= 0:
            return
        number = self.current_paragraph
        expected = {'take_dart':219,'enchanted_sword':70,'gnome_sword':192,'carrot':46,'lantern':395,'lost_item':370,'ingot':242,'wish':34,'swap':308,'ambush':98,'fever':259,'spiked_pit':278,'buy':261,'door':73,'darts':309,'lift':372,'wrestle':266,'bracelet':52,
                    'convalescence':304,'cursed_meal':328,'combat_potion':262,'hammer':204}
        if action in expected and number != expected[action]:
            return
        if self._book_state(number).get('foret_resolved') and action in expected and action != 'buy':
            return
        target = None
        try:
            if action == 'payment':
                if number not in rules.PAYMENT_PARAGRAPHS:
                    return
                rules.pay_paragraph(self.character, number, gold=payload[0], items=payload[1])
            elif action == 'werewolf_exit':
                if number != 388 or self._book_state(number).get('foret_resolved'):
                    return
                wounded = rules.werewolf_wounded(self.character, 'werewolf')
                target = 155 if wounded else 316
                if not wounded:
                    rules.reward(self.character, 'werewolf_unharmed', luck=1)
                self._book_state(number,True)['foret_resolved'] = True
            elif action == 'take_dart':
                rules.reward(self.character,'silver_dart',items=['Fléchette d’argent (valeur 5 Or)'])
            elif action == 'enchanted_sword':
                rules.take_enchanted_sword(self.character)
                target = 334
            elif action == 'gnome_sword':
                rules.confiscate_sword(self.character)
            elif action == 'carrot':
                self.character['chance'] = max(0,self.character['chance']-2)
                target = 12
            elif action == 'lantern':
                if 'Lanterne magique' not in self.character.get('inventory', []) or rules.peek(self.character).get('lantern_used'):
                    raise ValueError('La lanterne magique n’est plus utilisable.')
                _, total = self._roll(2,context='Chance — éclair de la lanterne')
                target = rules.light_lantern(self.character,total)
            elif action in ('lost_item','ingot'):
                choices = [name for name in self.character.get('inventory', []) if name not in self.character.get('locked_items', [])]
                if not choices:
                    raise ValueError('Aucun objet du sac ne peut être retiré pour ce choix.')
                choice, accepted = QInputDialog.getItem(self,'Choisir un objet','Objet à abandonner :',choices,0,False)
                if not accepted:
                    return
                if action == 'lost_item':
                    rules.lose_backpack_item(self.character,choice)
                    target = 231
                else:
                    rules.take_ingot(self.character,choice)
            elif action == 'entry':
                rules.resolve_entry(self.character, number)
            elif action == 'buy':
                rules.buy(self.character, *payload)
            elif action == 'target':
                combat = self._foret_combat()
                if not self.combat_available() or type(payload) is not int:
                    return
                group = combat['groups'][combat['group']]
                if not 0 <= payload < len(group) or group[payload]['stamina'] <= 0:
                    return
                combat['target'] = payload
                self._foret_sync_enemy()
            elif action in ('wear','unwear'):
                rules.wear(self.character, payload, enabled=action == 'wear')
            elif action == 'force_potion':
                rules.heal_found_potion(self.character)
            elif action == 'fever':
                rules.damage_hero(self.character, 3)
                self._refresh_character()
                if self.character['endurance'] > 0:
                    _, total = self._roll(2, context='Chance — résister à la fièvre')
                    target = rules.fever_test(self.character, total)
            elif action in ('ambush','spiked_pit'):
                _, total = self._roll(2, context='Chance — embuscade' if action == 'ambush' else 'Chance — fosse au pieu')
                target = rules.return_ambush(self.character, total) if action == 'ambush' else rules.spiked_pit(self.character, total)
            elif action == 'wish':
                labels = {'Habileté':'habilete','Endurance':'endurance','Chance':'chance'}
                choice, accepted = QInputDialog.getItem(self,'Le vœu du génie','Caractéristique à restaurer :',list(labels),0,False)
                if not accepted:
                    return
                rules.make_wish(self.character,labels[choice])
                target = 231
            elif action == 'swap':
                rules.swap_skill_luck(self.character)
                target = 148
            elif action == 'door':
                _, total = self._roll(2, context='Porte — Habileté et Chance, sans dépense de Chance')
                target = rules.combined_door(self.character, total)
            elif action == 'darts':
                totals = [self._roll(2, context=f'Chance — fléchette {index+1}')[1] for index in range(2)]
                target = rules.darts(self.character, totals)
            elif action == 'lift':
                _, total = self._roll(2, context='Soulever le coffre — Habileté')
                target = rules.lift_chest(self.character, total)
            elif action in ('wrestle','bracelet'):
                choices = (['10 pièces d’or'] if self.character.get('gold',0) >= 10 else [])
                choices += [name for name in self.character.get('inventory', []) if name != 'Anneau de Lenteur']
                if not choices:
                    raise ValueError('Aucune mise disponible.')
                choice, accepted = QInputDialog.getItem(self, 'Le bras de fer', 'Votre mise (perdue seulement en cas d’échec) :', choices, 0, False)
                if not accepted:
                    return
                gold, items = (10,[]) if choice == '10 pièces d’or' else (0,[choice])
                totals = []
                if action == 'wrestle':
                    for index in range(3):
                        _, total = self._roll(2, context=f'Bras de fer — épreuve {index+1}/3')
                        totals.append(total)
                        if total > self.character['habilete']:
                            break
                target = rules.arm_wrestling(self.character, totals, gold=gold, items=items, bracelet=action == 'bracelet')
            elif action == 'convalescence':
                target = rules.convalescence(self.character)
            elif action == 'cursed_meal':
                target = rules.cursed_meal(self.character)
            elif action == 'combat_potion':
                rules.resolve_entry(self.character, 262)
                rules.drink_combat_potion(self.character)
                target = 337
            elif action == 'hammer':
                rules.hand_over_hammer(self.character)
                target = 400
            else:
                return
        except ValueError as error:
            self.rules_log.setText(str(error))
            return
        if action in expected and action != 'buy' and not (action == 'lift' and target == 372):
            self._book_state(number, True)['foret_resolved'] = True
        if target is not None and not (action == 'lift' and target == 372):
            self._book_state(number, True)['foret_target'] = target
        self._refresh_character()
        if self.character['endurance'] > 0 and target in self.paragraphs:
            self.go_to(target)
        elif self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])
