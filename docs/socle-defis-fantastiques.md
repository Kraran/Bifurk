# Socle commun de Défis Fantastiques

Cette première étape prépare La Forêt de la Malédiction sans enregistrer encore
son PDF ni ses paragraphes comme aventure jouable. Le Sorcier utilise maintenant
les mêmes commandes de base que pourra réutiliser le prochain adaptateur.

## Répartition des responsabilités

| Emplacement | Responsabilité |
| --- | --- |
| `grimoire_modules/fighting_fantasy/rules.py` | Calculs sans Qt, PDF ni hasard interne : création, Chance, dégâts, potions, repas et fuite |
| `grimoire_modules/fighting_fantasy/adventure.py` | Services d'aventure issus de la Forêt, sans Qt ni texte de livre : état sauvegardé par livre, fin d'aventure, récompenses uniques, paiements, blessures mémorisées, routes payantes, épreuves relues et combats par groupes |
| `grimoire_modules/fighting_fantasy/controller.py` | Déroulement commun, jets fournis par l'hôte, choix de Chance, soins et séquences d'adversaires |
| `grimoire_modules/sorcier/` | Règles particulières, objets, navigation et événements du Sorcier |
| `grimoire_modules/controller.py` | Délégation des commandes, y compris celles héritées du socle, vers l'adaptateur du module ouvert |
| `main.py`, `combat_dialog.py` | Widgets, animation, journal, transactions et affichage des valeurs calculées par l'adaptateur |

Les fonctions de `rules.py` reçoivent les totaux déjà tirés : elles ne relancent
aucun dé. Elles ne dépendent ni du nom d'un objet, ni d'un numéro de paragraphe.
Le dictionnaire du personnage et les instantanés gardent leur format existant.
`book_events.escape_damage` et `flee_available` réexportent les calculs communs
pour conserver les imports des outils et scénarios existants.

## Services d'aventure communs

`adventure.py` reprend, sans changement de comportement, les règles génériques
d'abord écrites pour la Forêt, afin que La Cité des Voleurs et les grimoires
suivants les réutilisent. Chaque fonction qui touche l'état sauvegardé reçoit la
clé du livre (`'foret'`, `'cite'`…) : `character['book_state'][clé]` reste propre à
chaque aventure. Les tables relues (coûts de route, épreuves, objets maudits) et
les messages propres au livre sont passés par l'appelant ; aucun numéro de
paragraphe ni nom d'objet n'y figure.

`foret/rules.py` garde ses noms publics (`state`, `peek`, `alive`, `dice`,
`reward`, `pay`, `damage_hero`, `route_paid`, `pay_route`, `new_group_combat`,
`advance_group`…) sous forme d'enveloppes fixant la clé `'foret'` et l'Anneau de
Lenteur : contrôleur, outils, tests et sauvegardes de la Forêt sont inchangés.
`tests/test_fighting_fantasy_adventure.py` vérifie ces services avec une autre
clé de livre et l'équivalence des enveloppes de la Forêt.

## Règles partagées

- Création : Habileté 1d6+6, Endurance 2d6+12, Chance 1d6+6. Les deux rerolls
  autorisés par Bifurk restent pilotés par le parcours de création existant.
- Chance : comparer 2d6 au score avant de dépenser un point, sans valeur négative.
- Assaut : 2d6 + Habileté pour chaque combattant ; une égalité ne blesse personne.
  Blessure normale de deux points. Chance offensive : quatre si réussite, un si
  échec ; Chance défensive : un si réussite, trois si échec.
- Potion : choix initial immuable en partie, deux doses. Adresse/Vigueur restaurent
  leur caractéristique initiale. Chaque dose de Bonne Fortune augmente le plafond
  de Chance de un et restaure à ce nouveau plafond. Pas de dose inutile ou après mort.
- Repas : une provision contre quatre points d'Endurance au maximum, sous le plafond
  initial. Le passage doit l'autoriser ; le menu interdit le repas pendant un combat
  et après sa consommation dans ce passage. Aucun soin ne ressuscite le personnage.
- Fuite : uniquement si le passage la prévoit, avec son éventuel délai en assauts.
  La blessure normale vaut deux ; avec Chance elle vaut un ou trois. Une fuite
  mortelle ne conduit pas à la destination. Les parades comptent comme assauts.
- Séquence : préparer le prochain adversaire après sa défaite, puis suivre la sortie
  finale explicitement indiquée par les données.

Les caractéristiques initiales sont communes, mais **pas l'équipement, l'or ou les
faits de quête** : les 30 pièces et la carte de la Forêt seront intégrées avec son
module, pas ajoutées à toutes les aventures.

## Extensions de l'adaptateur

Les méthodes `_ff_*` sont les points d'extension. Leurs valeurs par défaut ne
confèrent aucun pouvoir aux objets et ne connaissent aucune rencontre du Sorcier.

| Méthode | Rôle |
| --- | --- |
| `_ff_before_assault`, `_ff_before_attack` | Bloquer une action incomplète, puis résoudre un préambule avant les jets contre un ennemi vivant |
| `_ff_combat_profile` | Fournir Habileté effective, bonus d'attaque, dommages de base et possibilité de blesser |
| `_ff_defend_hit`, `_ff_reduce_damage` | Déterminer la blessure avant Chance, puis appliquer une protection après Chance |
| `_ff_after_enemy_damage`, `_ff_after_player_damage` | Conserver les conséquences particulières d'une blessure |
| `_ff_enemy_defeated`, `_ff_after_hit` | Préparer l'adversaire suivant ou résoudre une issue particulière |
| `_ff_pending_combat` | Signaler une préparation spéciale encore nécessaire |
| `_ff_escape_details`, `_ff_escape_override` | Fournir les destinations/délais supplémentaires ou remplacer la fuite ordinaire |
| `_ff_meal_status`, `_ff_take_meal` | Autoriser et résoudre un repas particulier |
| `_ff_record_assault`, `_ff_finish_assault` | Comptabiliser et terminer les effets dans la transaction d'historique courante |

Le Sorcier conserve notamment dans ses extensions le souffle du Chien, le Crocodile,
les Piranhas, le Vampire, les effets de blessures de la Goule/Loup-Garou, le bouclier,
les armes, le casque, l'invisibilité et les repas particuliers. Le socle ne déduit
pas ces pouvoirs du seul nom d'un objet. La fenêtre de combat demande aussi son
Habileté effective au module, pour que l'affichage corresponde aux calculs.

Les contrôleurs sont des classes de méthodes, **pas des instances possédant un état**.
Le `self` reçu est l'hôte MainWindow, via ModuleActions. Pour réutiliser une méthode
de base depuis une extension, appeler explicitement
`FightingFantasyActions._ff_record_assault(self)` par exemple : `super()` ne convient
pas à ce mécanisme de délégation. Les jets, rafraîchissements et changements de
paragraphe se demandent aux services de l'hôte ; les décisions ne restent pas
uniquement dans un widget.

## Validation et suite

`tests/test_fighting_fantasy.py` exerce les règles et les commandes avec un hôte
sans contrôleur du Sorcier, puis vérifie la délégation, l'affichage de l'Habileté
et l'instantané d'annulation dans une vraie MainWindow. Des objets du Sorcier et
un mode de rencontre particulier sont volontairement présents dans un scénario :
ils ne doivent ajouter ni bonus, ni protection, ni jet au socle commun.

Les tests existants continuent de couvrir les exceptions du Sorcier, les combats,
soins, sauvegardes et annulations. Exécution :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Le manifeste, la présentation et l'adaptateur de consultation de la Forêt sont
maintenant décrits dans [l'étape 2](foret-module-presentation.md). Sa navigation et
ses événements seront vérifiés séparément ; hériter de
`FightingFantasyActions` ne signifie pas recopier le contrôleur du Sorcier.
Les vues d'équipement et les présentations des rencontres particulières encore
spécifiques au premier livre seront adaptées à mesure de l'intégration du second.
