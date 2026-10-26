"""Relier les règles relues des §1 à 400 de la Cité aux transactions et aux dés de Qt.

Comme les autres adaptateurs, les méthodes sont déléguées à MainWindow : appeler
explicitement le socle plutôt que super(). Les libellés et infobulles ne disent
jamais où mène une issue ni ce qui attend le héros ; ils reprennent seulement
ce que le passage affiché imprime (score à battre, prix, condition).
"""
from copy import deepcopy

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from item_icons import item_qicon

from ..fighting_fantasy.adventure import advance_group, damage_hero, new_group_combat
from ..fighting_fantasy.controller import FightingFantasyActions
from ..fighting_fantasy.rules import combat_damage, escape_damage, spend_luck
from . import feedback, rules
from .encounters import COMBATS, escape_status, profile, victory_target

GAMBLE_TIP = (f'Mise de {rules.GAMBLE_STAKE} Pièces d’Or : deux dés pour chacun des trois Nains, '
              'puis deux dés pour vous, selon la règle du livre.')

CHANCE_COST = 'Tenter sa Chance coûte 1 point de Chance.'


def _coins(amount):
    return f'{amount} Pièce{"s" if amount > 1 else ""} d’Or'


class CiteMechanicsActions(FightingFantasyActions):
    def _ff_stat_value(self, key):
        return rules.effective_skill(self.character) if key == 'habilete' else self.character.get(key, 0)

    def _cite_analysed(self, number=None):
        number = self.current_paragraph if number is None else number
        return number in rules.ANALYSED

    # ----- Combats -------------------------------------------------------------
    def _combat_entry(self, number):
        """Profil intégré du passage ; seules les cibles de victoire et de fuite y figurent."""
        data = COMBATS.get(number)
        if data is None:
            return None
        combat = {'mode': 'paired', 'victory_target': data['victory']}
        if 'escape' in data:
            combat['escape_target'] = data['escape']
        return {'combat': combat}

    def _cite_combat(self):
        return rules.peek(self.character).get('combats', {}).get(str(self.current_paragraph))

    def _cite_prepare_combat(self):
        """Préparer une fois la rencontre ; relire ou charger conserve les blessures."""
        number = self.current_paragraph
        if number not in COMBATS or self._restoring or self.character['endurance'] <= 0:
            return
        unless = COMBATS[number].get('unless_item')
        if unless and rules.has_item(self.character, unless[0]):
            return
        creature = None
        if COMBATS[number].get('creature_die'):
            die = rules.peek(self.character).get('creature')
            if die is None:
                return
            creature = rules.CREATURES[die]
        combats = rules.state(self.character).setdefault('combats', {})
        if str(number) not in combats:
            combats[str(number)] = new_group_combat(profile(number, creature))
        self._cite_sync_enemy()

    def _cite_sync_enemy(self):
        """Raccorder la cible (combat simultané : choisie, sinon le premier debout)."""
        combat = self._cite_combat()
        if not combat or combat['finished'] or combat.get('escaped'):
            return
        group = combat['groups'][combat['group']]
        living = [index for index, enemy in enumerate(group) if enemy['stamina'] > 0]
        if combat.get('target', 0) not in living:
            combat['target'] = living[0] if living else 0
        self._set_book_enemy(group[combat['target']])

    def _combat_roster(self):
        combat = self._cite_combat()
        if not combat:
            return None
        return [deepcopy(enemy) for group in combat['groups'] for enemy in group]

    def _complex_round_blocked(self):
        return not self.combat_available()

    def combat_available(self):
        combat = self._cite_combat()
        return bool(combat and not combat['finished'] and not combat.get('escaped')
                    and self.character['endurance'] > 0 and self._adventurer_draft is None
                    and not self.character.get('book_facts', {}).get('adventure_ended'))

    def combat_flee_status(self):
        if not self.combat_available():
            return False, 'Aucun combat en cours.'
        escape = COMBATS[self.current_paragraph].get('escape')
        if escape is not None and escape not in self.paragraphs:
            return False, 'Une destination nécessaire à la fuite est absente du livre chargé.'
        return escape_status(self.current_paragraph, self._cite_combat())

    def _ff_combat_profile(self):
        attack = COMBATS.get(self.current_paragraph, {}).get('attack', 0) + rules.attack_bonus(self.character)
        return {'skill': rules.effective_skill(self.character), 'hit_damage': 2,
                'can_wound': True, 'attack_bonus': attack}

    def _ff_defend_hit(self):
        """Blessure imprimée d’un assaut perdu (§253 : 4 points), sinon 2."""
        return COMBATS.get(self.current_paragraph, {}).get('wound', 2), ''

    def _ff_after_attack_rolls(self):
        """§392 : un dé par Assaut pour le souffle de feu ; 1 à 3 brûlent d’un point.

        La Chance s’applique comme pour une blessure : réussie 0, ratée 2."""
        faces = COMBATS.get(self.current_paragraph, {}).get('fire')
        if not faces:
            return True
        _, die = self._roll(1, context='Souffle de feu')
        if die not in faces:
            self._log_combat_detail(f'Souffle de feu : {die}, jet évité.')
            return True
        lucky = None
        if self._assault_luck_choice('Le souffle de feu vous brûle',
                                     f'Dé {die} : vous perdez 1 point d’Endurance.',
                                     'Tenter votre Chance contre le feu ?') == QMessageBox.Yes:
            _, total = self._roll(2, context='Chance — contre le feu')
            lucky = spend_luck(self.character, total)
        damage = combat_damage(1, attacking=False, lucky=lucky)
        damage_hero(self.character, rules.BOOK, damage)
        self._refresh_character()
        self._log_combat_detail(f'Souffle de feu : {die}, brûlure −{damage} Endurance.')
        return self.character['endurance'] > 0

    def _ff_enemy_defeated(self):
        """L’adversaire suivant est préparé après l’assaut, par advance_group."""

    def _ff_after_hit(self):
        """La sortie du combat est résolue à la fin de l’assaut."""

    def combat_round(self):
        """Un assaut contre l’adversaire courant ; les égalités comptent comme assauts."""
        if self.current_paragraph not in COMBATS:
            self.rules_log.setText('Aucun combat n’est intégré à ce passage : il reste en préparation.')
            return
        if not self.combat_available():
            return
        combat = self._cite_combat()
        group = combat['groups'][combat['group']]
        target = combat.get('target', 0)
        enemy = group[target]
        # Combat simultané (§311, §326) : les autres adversaires debout attaquent aussi ;
        # contre eux, on ne fait que parer (aucune blessure infligée).
        defenders = [other for index, other in enumerate(group) if index != target and other['stamina'] > 0]
        FightingFantasyActions.combat_round(self)
        enemy['stamina'] = self.enemy_endurance.value()
        for defender in defenders:
            if self.character['endurance'] <= 0:
                break
            self._cite_parry(defender)
        combat['assaults'] += 1
        if self.character['endurance'] > 0:
            advance_group(combat)
            if combat['finished']:
                number = self.current_paragraph
                combat['target_paragraph'] = victory_target(number, combat['assaults'])
                self.completed_book_events.add(number)
                self._cite_after_combat()
                if combat['target_paragraph'] in self.paragraphs:
                    self.go_to(combat['target_paragraph'])
            else:
                self._cite_sync_enemy()
        self._refresh_character()
        if self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    def _cite_parry(self, defender):
        """Jet d’attaque contre un adversaire non ciblé : il blesse s’il l’emporte."""
        enemy_rolls, enemy_total = self._roll(2, context='Combat — ' + defender['name'], opponent=True)
        hero_rolls, hero_total = self._roll(2, context='Combat — parade contre ' + defender['name'])
        hero_attack = rules.effective_skill(self.character) + hero_total + self._ff_combat_profile()['attack_bonus']
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
            damage_hero(self.character, rules.BOOK, damage)
        self._log_combat_detail(f'{defender["name"]} : {enemy_rolls} → {enemy_attack} ; '
                                f'parade {hero_rolls} → {hero_attack}. Héros −{damage} Endurance.')

    def _cite_after_combat(self):
        """Broche scorpion d’argent : 1 point d’Endurance après chaque combat survécu."""
        if rules.has_item(self.character, rules.SILVER_BROOCH) and self.character['endurance'] > 0:
            before = self.character['endurance']
            cap = self.character.get('initial', {}).get('endurance', before)
            self.character['endurance'] = max(before, min(cap, before + 1))
            if self.character['endurance'] > before:
                self._log_combat_detail('Broche scorpion d’argent : +1 Endurance.')

    def escape_scripted_combat(self, number):
        """Blessure de fuite des règles ; au §73, le bouclier est jeté (Habileté −1)."""
        if number != self.current_paragraph or not self.can_flee_combat():
            return
        total = None
        if self._ask_combat_question('Fuir', 'Tenter votre Chance pour la blessure de fuite ?') == QMessageBox.Yes:
            _, total = self._roll(2, context='Chance — fuite')
        damage, cost = escape_damage(self.character['chance'], total)
        self.character['chance'] = max(0, self.character['chance'] - cost)
        damage_hero(self.character, rules.BOOK, damage)
        data = COMBATS[number]
        if data.get('escape_skill'):
            self.character['habilete'] = max(0, self.character['habilete'] - data['escape_skill'])
            for name in rules.matching_items(self.character, 'bouclier')[:1]:
                self.character['inventory'].remove(name)
        combat = self._cite_combat()
        combat['escaped'] = True
        combat['target_paragraph'] = data['escape']
        self._remember_monster(self.enemy_name.text(), 'fui')
        self._cite_after_combat()
        self._refresh_character()
        if self.character['endurance'] > 0:
            self.go_to(data['escape'])

    # ----- Commandes du passage -------------------------------------------------
    def _cite_test_button(self, number):
        stat = rules.BRANCH_TESTS[number][0]
        if stat == 'chance':
            return f'Tenter votre Chance (2d6 ≤ {self.character.get("chance", 0)})', CHANCE_COST
        score = rules.effective_skill(self.character)
        return f'Épreuve d’Habileté (2d6 ≤ {score})', 'Réussite si le total des deux dés ne dépasse pas votre Habileté.'

    def _cite_mechanics_buttons(self):
        """Afficher les seules commandes implantées ; tout est revérifié au clic."""
        def add(label, action, enabled=True, tooltip='', payload=None, combat=False):
            button = QPushButton(label)
            if tooltip:
                button.setToolTip(tooltip)
            button.setEnabled(enabled and self.character['endurance'] > 0)
            button.setProperty('combatAction', combat)
            if action == 'shop':
                button.clicked.connect(lambda checked=False: self._cite_shop())
            elif action == 'theft':
                button.clicked.connect(lambda checked=False: self._cite_theft_dialog())
            elif action == 'pocket':
                button.clicked.connect(lambda checked=False: self._cite_pocket_dialog())
            elif action == 'mixture':
                button.clicked.connect(lambda checked=False: self._cite_mixture_dialog())
            elif action == 'brawl':
                button.clicked.connect(lambda checked=False: self._cite_brawl_dialog())
            elif action == 'loot':
                button.clicked.connect(lambda checked=False: self._cite_loot_dialog())
            elif action == 'trade':
                button.clicked.connect(lambda checked=False: self._cite_trade_dialog())
            elif action == 'pawn':
                button.clicked.connect(lambda checked=False: self._cite_pawn_dialog())
            elif payload is not None:
                button.clicked.connect(lambda checked=False: self.perform_cite_action(action, payload))
            else:
                button.clicked.connect(lambda checked=False: self.perform_cite_action(action))
            self.event_layout.addWidget(button)
        number = self.current_paragraph
        if self.character.get('book_facts', {}).get('adventure_ended'):
            return
        if number in rules.BRANCH_TESTS and not rules.test_resolved(self.character, number):
            label, tip = self._cite_test_button(number)
            add(label, 'branch_test', tooltip=tip)
        if number == rules.DIE_HEAL and rules.peek(self.character).get('die_heal') is None:
            add('Lancer un dé — Endurance regagnée', 'die_heal',
                tooltip='Le total initial d’Endurance ne peut être dépassé.')
        if number == rules.THEFT and not rules.theft_resolved(self.character):
            count = rules.theft_required(self.character)
            add('Constater le larcin de l’Elfe…' if count else 'Constater le larcin de l’Elfe',
                'theft', tooltip=f'{count} objet(s) du sac à dos et jusqu’à {_coins(rules.THEFT_GOLD)}.')
        if number in rules.DOUBLE_TESTS and not rules.test_resolved(self.character, number):
            luck = self.character.get('chance', 0)
            add(f'Tenter deux fois votre Chance (2d6 ≤ {luck}, puis ≤ {max(0, luck - 1)})',
                'double_test', tooltip='Chaque tentative coûte 1 point de Chance.')
        if number == rules.VOLLEY and not rules.volley_resolved(self.character):
            add('Lancer un dé — flèches reçues', 'volley',
                tooltip=f'{rules.VOLLEY_HIT} points d’Endurance par flèche, '
                        f'puis {rules.VOLLEY_AFTER} points de Chance si vous survivez.')
        if number == rules.POCKET and not rules.pocket_resolved(self.character):
            add('Constater le larcin…', 'pocket',
                tooltip='Une Pièce d’Or ou un objet de votre choix.')
        if number in rules.DIE_TESTS and not rules.test_resolved(self.character, number):
            add('Lancer un dé', 'die_test', tooltip='Un dé, comme l’indique le livre.')
        if number == rules.MIXTURE and not rules.mixture_ready(self.character):
            add('Choisir les deux ingrédients du mélange…', 'mixture',
                tooltip='Deux des trois ingrédients, broyés ensemble.')
        if number == rules.CREATURE and not rules.creature_rolled(self.character):
            ready = rules.mixture_ready(self.character)
            add('Lancer un dé — la créature', 'creature', enabled=ready,
                tooltip='Le tableau du livre désigne l’adversaire.' if ready
                else 'Préparez d’abord le mélange.')
        if number == rules.GAMBLE:
            played = len(rules.gamble_rounds(self.character))
            if played < rules.GAMBLE_ROUNDS:
                reason = rules.can_gamble(self.character)
                add(f'Jouer une partie — mise de {_coins(rules.GAMBLE_STAKE)} '
                    f'({played}/{rules.GAMBLE_ROUNDS})', 'gamble', enabled=reason is None,
                    tooltip=reason or GAMBLE_TIP)
        if number == rules.BRAWL and not rules.brawl_resolved(self.character):
            count = rules.brawl_required(self.character)
            add('Constater la perte…' if count else 'Constater la perte', 'brawl',
                tooltip=f'{count} objet(s) du sac à dos, au choix.')
        if number in rules.LOOTS and not rules.loot_taken(self.character, number):
            add('Garder ce que vous voulez…', 'loot', tooltip='Prenez ce que vous voulez, en une fois.')
        if number == rules.HOT_MEAL and not rules.hot_meal_eaten(self.character):
            enough = self.character.get('gold', 0) >= rules.HOT_MEAL_PRICE
            add(f'Manger chaud — {_coins(rules.HOT_MEAL_PRICE)}', 'hot_meal', enabled=enough,
                tooltip=f'Endurance +{rules.HOT_MEAL_GAIN}, sans dépasser le total initial.' if enough
                else 'Pas assez de Pièces d’Or.')
        if number == rules.TRADE and not rules.traded(self.character):
            choices = rules.trade_choices(self.character)
            add('Échanger contre la fleur dorée…', 'trade', enabled=bool(choices),
                tooltip='Un objet magique, une pièce d’armure ou deux portions de Provisions.' if choices
                else 'Rien de ce que demande le livre dans votre sac.')
        if number in rules.SHOPS:
            add('Faire ses achats…', 'shop', tooltip='Achats facultatifs, aux prix indiqués par le livre.')
        if number == rules.PAWNBROKER:
            choices = rules.pawn_choices(self.character)
            add('Vendre au prêteur sur gages…', 'pawn', enabled=bool(choices),
                tooltip='Ventes facultatives, aux prix indiqués par le livre.' if choices
                else 'Rien de ce que rachète le prêteur dans votre sac.')
        if number == rules.CANNONBALL and not rules.cannon_resolved(self.character):
            add('Jouer au boulet de canon — un dé chacun', 'cannon',
                tooltip=f'Un dé à tour de rôle jusqu’au premier 1 ; le perdant paie {_coins(rules.CANNON_STAKE)}.')
        if self.combat_available():
            combat = self._cite_combat()
            group = combat['groups'][combat['group']]
            living = [index for index, enemy in enumerate(group) if enemy['stamina'] > 0]
            # « Cibler » seulement à deux adversaires debout : seul, le dernier est la cible.
            if len(living) >= 2:
                for index in living:
                    add(('⚔ ' if index == combat.get('target', 0) else '') + 'Cibler ' + group[index]['name'],
                        'target', payload=index, combat=True,
                        tooltip='Adversaire attaqué à cet Assaut ; les autres sont seulement parés.')
        if rules.has_item(self.character, 'emplatre'):
            fighting = self.combat_available()
            add('Appliquer l’emplâtre d’herbes — un dé d’Endurance', 'poultice', enabled=not fighting,
                tooltip='Pas pendant un combat.' if fighting
                else 'Le total initial d’Endurance ne peut être dépassé ; l’emplâtre est utilisé.')

    def perform_cite_action(self, action, payload=None):
        """Commande transactionnelle, suivie d’un compte rendu dans le cadre de messages."""
        if self._adventurer_draft is not None or self.current_paragraph is None:
            return
        number = self.current_paragraph
        before = feedback.snapshot(self.character)
        self._roll_trace = []
        try:
            outcome = CiteMechanicsActions._cite_action_body(self, action, payload)
        finally:
            trace, self._roll_trace = self._roll_trace, None
        if outcome == 'error':
            return
        kind = ({'branch_test': rules.BRANCH_TESTS.get(number, ('',))[0], 'double_test': 'chance',
                 'gamble': 'gamble', 'creature': 'creature', 'cannon': 'cannon'}.get(action))
        moved = self.current_paragraph if self.current_paragraph != number else None
        message = feedback.summary(before, feedback.snapshot(self.character),
                                   kind=kind, trace=trace, destination=moved)
        if message:
            self.rules_log.setText(message)

    def _cite_action_body(self, action, payload=None):
        if self.character['endurance'] <= 0 or self.character.get('book_facts', {}).get('adventure_ended'):
            return
        number = self.current_paragraph
        target = None
        try:
            if action == 'branch_test':
                if number not in rules.BRANCH_TESTS or rules.test_resolved(self.character, number):
                    return
                stat = rules.BRANCH_TESTS[number][0]
                _, total = self._roll(2, context='Chance' if stat == 'chance' else 'Habileté')
                target = rules.resolve_test(self.character, number, total)
            elif action == 'die_heal':
                if number != rules.DIE_HEAL:
                    return
                _, die = self._roll(1, context='Endurance regagnée')
                rules.heal_die(self.character, die)
            elif action == 'theft':
                if number != rules.THEFT:
                    return
                rules.elf_theft(self.character, payload or ())
            elif action == 'buy':
                if number not in rules.SHOPS:
                    return
                name, count = payload if isinstance(payload, (tuple, list)) else (payload, 1)
                rules.buy(self.character, number, name, count)
            elif action == 'double_test':
                if number not in rules.DOUBLE_TESTS or rules.test_resolved(self.character, number):
                    return
                totals = [self._roll(2, context='Chance')[1] for _ in range(2)]
                trace = self._roll_trace if isinstance(self._roll_trace, list) else []
                if len(trace) >= 2 and trace[-2].get('chance') is not None:
                    # Le point de Chance du premier essai est dépensé avant le second.
                    trace[-1] = dict(trace[-1], chance=max(0, trace[-2]['chance'] - 1))
                target = rules.resolve_double(self.character, number, totals)
            elif action == 'volley':
                if number != rules.VOLLEY or rules.volley_resolved(self.character):
                    return
                _, die = self._roll(1, context='Flèches')
                rules.volley(self.character, die)
            elif action == 'pocket':
                if number != rules.POCKET or rules.pocket_resolved(self.character):
                    return
                rules.pick_pocket(self.character, payload)
            elif action == 'die_test':
                if number not in rules.DIE_TESTS or rules.test_resolved(self.character, number):
                    return
                _, die = self._roll(1, context='Dé')
                target = rules.resolve_die_test(self.character, number, die)
            elif action == 'mixture':
                if number != rules.MIXTURE:
                    return
                rules.choose_mixture(self.character, payload)
            elif action == 'creature':
                if (number != rules.CREATURE or rules.creature_rolled(self.character)
                        or not rules.mixture_ready(self.character)):
                    return
                _, die = self._roll(1, context='Créature')
                rules.roll_creature(self.character, die)
                self._cite_prepare_combat()
            elif action == 'gamble':
                if number != rules.GAMBLE or rules.can_gamble(self.character):
                    return
                dwarves = [self._roll(2, context=f'Nain {i + 1}', opponent=True)[1]
                           for i in range(rules.GAMBLE_DWARVES)]
                _, own = self._roll(2, context='Vous')
                rules.gamble(self.character, dwarves, own)
            elif action == 'brawl':
                if number != rules.BRAWL:
                    return
                rules.brawl_loss(self.character, payload or ())
            elif action == 'loot':
                if number not in rules.LOOTS:
                    return
                rules.take_loot(self.character, number, payload or ())
            elif action == 'hot_meal':
                if number != rules.HOT_MEAL:
                    return
                rules.hot_meal(self.character)
            elif action == 'trade':
                if number != rules.TRADE:
                    return
                rules.trade_flower(self.character, payload)
            elif action == 'pawn':
                if number != rules.PAWNBROKER:
                    return
                rules.pawn_sell(self.character, payload or ())
            elif action == 'cannon':
                if number != rules.CANNONBALL or rules.cannon_resolved(self.character):
                    return
                rolls = []
                while not rolls or rolls[-1] != 1:
                    if len(rolls) >= rules.CANNON_LIMIT:
                        raise ValueError('Partie interrompue : trop de lancers sans 1.')
                    mine = len(rolls) % 2 == 0
                    _, die = self._roll(1, context='Vous' if mine else 'L’homme à la poitrine nue',
                                        opponent=not mine)
                    rolls.append(die)
                rules.cannonball(self.character, rolls)
            elif action == 'target':
                combat = self._cite_combat()
                if not self.combat_available() or type(payload) is not int:
                    return
                group = combat['groups'][combat['group']]
                if not 0 <= payload < len(group) or group[payload]['stamina'] <= 0:
                    return
                combat['target'] = payload
                self._cite_sync_enemy()
            elif action == 'poultice':
                if not rules.has_item(self.character, 'emplatre') or self.combat_available():
                    return
                _, die = self._roll(1, context='Emplâtre')
                rules.use_poultice(self.character, die)
            else:
                return
        except ValueError as error:
            self.rules_log.setText(str(error))
            return 'error'
        self._refresh_character()
        if self.character['endurance'] > 0 and target in self.paragraphs:
            self.go_to(target)
        elif self.current_paragraph in self.paragraphs:
            self._render_choices_and_events(self.paragraphs[self.current_paragraph])

    # ----- Dialogues ---------------------------------------------------------------
    def _cite_shop(self):
        """Boutique sans révélation : prix, solde et règle d’achat imprimée, jamais l’usage.

        Le choix seul ne dépense rien ; chaque achat est une transaction annulable."""
        number = self.current_paragraph
        shop = rules.SHOPS.get(number)
        if not shop:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Les achats du passage')
        layout = QVBoxLayout(dialog)
        header = QLabel(rules.shop_rule(number))
        header.setWordWrap(True)
        layout.addWidget(header)
        selector = QComboBox()
        selector.setIconSize(QSize(28, 28))
        for name, _price in shop['items']:
            selector.addItem(item_qicon(name), '', name)
        layout.addWidget(selector)
        description = QLabel()
        description.setObjectName('shopDescription')
        description.setWordWrap(True)
        layout.addWidget(description)
        quantity = QSpinBox()
        quantity.setRange(1, 99)
        quantity.setPrefix('Quantité : ')
        quantity.setVisible(bool(shop.get('repeat')))
        layout.addWidget(quantity)
        balance = QLabel()
        balance.setObjectName('shopBalance')
        layout.addWidget(balance)
        buy = QPushButton('Acheter')
        layout.addWidget(buy)
        prices = dict(shop['items'])

        def label_items():
            bought = rules.shop_bought(self.character, number)
            model = selector.model()
            for index, (name, price) in enumerate(shop['items']):
                count = bought.count(name)
                selector.setItemText(index, f'{name} — {_coins(price)}' + (
                    '' if not count else f' — acheté ×{count}' if shop.get('repeat') else ' — acheté'))
                reason = rules.can_buy(self.character, number, name)
                closed = reason in ('Article déjà acheté.', 'Le livre ne permet qu’un seul achat ici.')
                selector.setItemData(index, f'{_coins(price)}.' + (f' {reason}' if closed else ''),
                                     Qt.ToolTipRole)
                item = model.item(index) if hasattr(model, 'item') else None
                if item is not None:
                    item.setEnabled(not closed or name == selector.currentData())

        def refresh():
            name = selector.currentData()
            count = quantity.value() if shop.get('repeat') else 1
            unit = prices[name]
            gold = self.character.get('gold', 0)
            description.setText(rules.shop_description(self.character, number, name))
            balance.setText(f'Or disponible : {_coins(gold)} — total : {count} × {unit} = {_coins(unit * count)}'
                            if shop.get('repeat') else
                            f'Or disponible : {_coins(gold)} — prix : {_coins(unit)}')
            reason = rules.can_buy(self.character, number, name, count)
            buy.setEnabled(reason is None and self.character['endurance'] > 0)
            buy.setToolTip(reason or '')

        def purchase():
            count = quantity.value() if shop.get('repeat') else 1
            self.perform_cite_action('buy', (selector.currentData(), count))
            label_items()
            refresh()
        selector.currentIndexChanged.connect(lambda _index: (label_items(), refresh()))
        quantity.valueChanged.connect(refresh)
        buy.clicked.connect(purchase)
        close = QPushButton('Revenir au grimoire')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        label_items()
        refresh()
        dialog.exec()
        dialog.deleteLater()

    def _cite_pick_items(self, title, text, choices, count, confirm_label):
        """Choisir exactement count exemplaires (None : autant que voulu) ; None si annulé."""
        if count == 0:
            return []
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        items = QListWidget()
        items.setSelectionMode(QAbstractItemView.MultiSelection)
        items.addItems(choices)
        layout.addWidget(items)
        confirm = QPushButton(confirm_label)
        confirm.setEnabled(False)
        items.itemSelectionChanged.connect(
            lambda: confirm.setEnabled(count is None or len(items.selectedItems()) == count))
        confirm.setEnabled(count is None)
        confirm.clicked.connect(dialog.accept)
        layout.addWidget(confirm)
        cancel = QPushButton('Annuler')
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(cancel)
        accepted = dialog.exec() == QDialog.Accepted
        selected = [item.text() for item in items.selectedItems()]
        dialog.deleteLater()
        return selected if accepted else None

    def _cite_pocket_dialog(self):
        if self.current_paragraph != rules.POCKET or rules.pocket_resolved(self.character):
            return
        choices = rules.pocket_choices(self.character)
        if not choices:
            self.perform_cite_action('pocket')
            return
        chosen = self._cite_pick_items('Le larcin', 'Choisissez ce qui vous est pris.',
                                       choices, 1, 'Valider')
        if chosen:
            self.perform_cite_action('pocket', chosen[0])

    def _cite_theft_dialog(self):
        if self.current_paragraph != rules.THEFT or rules.theft_resolved(self.character):
            return
        count = rules.theft_required(self.character)
        chosen = self._cite_pick_items(
            'Le larcin de l’Elfe', f'Choisissez {count} objet(s) de votre sac à dos.',
            rules.theft_choices(self.character), count, 'Valider')
        if chosen is not None:
            self.perform_cite_action('theft', chosen)

    def _cite_mixture_dialog(self):
        if self.current_paragraph != rules.MIXTURE or rules.mixture_ready(self.character):
            return
        names = [name for name, _target in rules.MIXTURES]
        name, accepted = QInputDialog.getItem(self, 'Le mélange', 'Ingrédients broyés ensemble :',
                                              names, 0, False)
        if accepted:
            self.perform_cite_action('mixture', dict(rules.MIXTURES)[name])

    def _cite_brawl_dialog(self):
        if self.current_paragraph != rules.BRAWL or rules.brawl_resolved(self.character):
            return
        count = rules.brawl_required(self.character)
        chosen = self._cite_pick_items(
            'La bousculade', f'Choisissez {count} objet(s) de votre sac à dos.',
            rules.theft_choices(self.character), count, 'Valider')
        if chosen is not None:
            self.perform_cite_action('brawl', chosen)

    def _cite_loot_dialog(self):
        number = self.current_paragraph
        if number not in rules.LOOTS or rules.loot_taken(self.character, number):
            return
        chosen = self._cite_pick_items(
            'Le butin', 'Sélectionnez ce que vous gardez (rien, une partie ou tout).',
            rules.loot_choices(number), None, 'Garder la sélection')
        if chosen is not None:
            self.perform_cite_action('loot', chosen)

    def _cite_pawn_dialog(self):
        """§354 : le bouton du prêteur ouvre la fenêtre de vente."""
        if self.current_paragraph == rules.PAWNBROKER:
            self._cite_sale_dialog()

    def _cite_sale_dialog(self):
        """Vente symétrique de l’achat : prix offerts par le livre, solde, total, puis confirmation.

        Autant de ventes que voulu ; chaque vente confirmée est une transaction annulable
        et la pièce sonne quand l’or change."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Le prêteur sur gages')
        layout = QVBoxLayout(dialog)
        header = QLabel('Sélectionnez ce que vous vendez, au prix offert. '
                        'Rien n’est vendu avant votre confirmation.')
        header.setWordWrap(True)
        layout.addWidget(header)
        items = QListWidget()
        items.setObjectName('saleItems')
        items.setIconSize(QSize(28, 28))
        items.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(items)
        balance = QLabel()
        balance.setObjectName('saleBalance')
        layout.addWidget(balance)
        sell = QPushButton('Vendre…')
        layout.addWidget(sell)

        def fill():
            items.clear()
            for name, price in rules.pawn_choices(self.character):
                item = QListWidgetItem(item_qicon(name), f'{name} — {_coins(price)}')
                item.setData(Qt.UserRole, (name, price))
                item.setToolTip(f'Prix offert : {_coins(price)}.')
                items.addItem(item)

        def selection():
            return [item.data(Qt.UserRole) for item in items.selectedItems()]

        def refresh():
            chosen = selection()
            total = sum(price for _name, price in chosen)
            gold = self.character.get('gold', 0)
            balance.setText(f'Or disponible : {_coins(gold)} — vous recevrez {_coins(total)}' if chosen
                            else f'Or disponible : {_coins(gold)} — rien de sélectionné')
            sell.setEnabled(bool(chosen) and self.character['endurance'] > 0)
            sell.setToolTip('' if chosen else 'Sélectionnez au moins un objet.')

        def confirm_and_sell():
            chosen = selection()
            names = [name for name, _price in chosen]
            if names and self._cite_confirm_sale(names, sum(price for _name, price in chosen)):
                self.perform_cite_action('pawn', names)
                fill()
            refresh()
        items.itemSelectionChanged.connect(refresh)
        sell.clicked.connect(confirm_and_sell)
        close = QPushButton('Revenir au grimoire')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        fill()
        refresh()
        dialog.exec()
        dialog.deleteLater()

    def _cite_confirm_sale(self, names, total):
        """Dernière étape de la vente : True si le joueur confirme."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle('Confirmer la vente')
        listed = ', '.join(names[:-1]) + ' et ' + names[-1] if len(names) > 1 else names[0]
        box.setText(f'Vendre {listed} pour {_coins(total)} ?')
        box.setInformativeText('Les objets vendus quittent votre sac à dos.')
        accept = box.addButton('Vendre', QMessageBox.AcceptRole)
        box.addButton('Garder', QMessageBox.RejectRole)
        box.setDefaultButton(accept)
        box.exec()
        chosen = box.clickedButton() is accept
        box.deleteLater()
        return chosen

    def _cite_trade_dialog(self):
        if self.current_paragraph != rules.TRADE or rules.traded(self.character):
            return
        chosen = self._cite_pick_items('L’échange', 'Choisissez ce que vous donnez en échange.',
                                       rules.trade_choices(self.character), 1, 'Échanger')
        if chosen:
            self.perform_cite_action('trade', chosen[0])
