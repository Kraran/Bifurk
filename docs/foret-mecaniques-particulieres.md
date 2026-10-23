# La Forêt — mécaniques particulières (étape 4)

Cette étape ajoute le moteur des exceptions et leur raccordement au lecteur, aux
dés, à la fenêtre de combat et aux sauvegardes. Le module reste `preview` :
l’automatisation complète des 400 passages n’est pas annoncée. Les analyses
`analyse_verifiee` restent des données documentaires ; elles ne sont jamais
converties globalement en événements exécutables.

## Ce qui est intégré

- **Yaztromo (§261)** : 17 articles, prix relus, quantités explicites, solde vérifié
  au clic. Un article acheté possède une charge. Les variantes « Bottes de Saut »
  et « Filet d’Enchevêtrement » retrouvent le même achat. Les cinq capsules du
  sachet constituent un usage, pas cinq rencontres. Un objet durable épuisé reste
  visible avec la mention « magie épuisée ». Un ajout manuel ne crée pas de charge.
- **Objets et butins** : 45 passages disposent d’un bouton d’effet vérifié. Les
  variantes d’un même butin utilisent une identité commune : bourse du Troll,
  tête du marteau, manche, poudre de Quin, boîte d’argent, quatre pièces de la
  tanière. Un retour ne rend ni les pièces ni les charges déjà dépensées.
- **Port** : casque, bracelet et gantelet donnent chacun +1 à la Force d’Attaque,
  sans changer l’Habileté initiale. L’Anneau de Lenteur inflige -2 et ne peut être
  retiré. L’Œil d’Ambre doit être porté pour questionner Arragon. Le retrait manuel
  d’un achat emporte sa charge ; le retrait d’un équipement enlève son port.
- **Épée enchantée (§70)** : acquisition et équipement explicites, une seule fois.
  Selon le choix confirmé par l’utilisateur, elle ajoute deux points d’Habileté
  tant qu’elle est équipée, au-delà du total initial. Le bonus agit sur les
  épreuves d’Habileté, les attaques et les parades, pas seulement sur la Force
  d’Attaque. Une autre arme équipée, une perte ou la transformation du Gnome
  désactivent immédiatement le bonus. La restitution réactive le même bonus.
- **Épreuves** : porte comparée simultanément à H et C sans dépense de Chance,
  deux fléchettes avec deux dépenses même après un échec, bras de fer arrêté au
  premier échec, Brassard sans dés, coffre retentable avec une blessure par échec,
  fosse au pieu, fièvre avec contrôle de survie avant les dés et embuscade du retour.
  Le §182 compare 2d6 à l’Habileté effective pour extraire l’épée du rocher :
  réussite vers le §70, échec sans blessure vers le §334, sans dépense de Chance.
  Les §§57, 81, 90, 229, 256 et 376 ont désormais leur test de Chance obligatoire ;
  le §251 utilise l’Habileté. Les flèches des §§90/251 blessent immédiatement en
  cas d’échec, tandis que les blessures des §§35/4/45 sont appliquées uniquement
  dans leur passage respectif. Une blessure mortelle interrompt le parcours.
- **Gaz toxiques (§§22, 169, 222, 60)** : un seul d6 de perte d’Endurance.
  La boîte d’argent enlève aussi deux points d’Habileté de base ; le champignon
  n’en enlève aucun. Les §§22/169 et les variantes protégées §§338/365 partagent
  la même ouverture : ni deuxième blessure, ni deuxième boîte, ni charge de filtre
  dépensée sur une ouverture déjà résolue. La boîte est récupérée seulement si
  le héros survit. Au §60, chercher les filtres exige une charge achetée et un
  test de Chance ; les §§183/44 consomment ensuite cette charge et appliquent
  leur propre effet. Les liens attendent la résolution des dés.
- **Soins et transformations** : cinq rations de convalescence sans restauration
  d’Endurance ; repas maudit qui enlève quatre points au lieu de soigner ; Potion
  de Force trouvée (+5 E) distincte de la fiole initiale à deux doses ; vœu du génie
  sur une seule caractéristique ; échange des valeurs courantes H/C sans échange
  des plafonds. La lanterne magique ne consomme pas la lanterne de voyage.
  Le pain elfique du §257 est récupéré avec +1 Chance, sans être mangé d’office.
  Une portion utile rend quatre points d’Endurance depuis Soins, hors combat,
  sous plafond, sans dépense de provisions. Au §184, le moine prend une clochette
  et sa potion est bue aussitôt (+4 Endurance sous plafond), sans recharge ni
  ajout d’une fiole ; l’échange a lieu une fois, même si le héros est déjà soigné.
  Le choix du §191 exige la présence de la clochette.
- **Paiements** : choix des exemplaires et des pièces aux §§12, 14, 32, 36, 218,
  279 et 297. Le tribut représente exactement cinq unités ; chaque pièce et chaque
  objet compte pour une unité. La valeur estimée d’un bijou ne crée pas des pièces.
  Annuler ou proposer un tarif invalide ne modifie rien. Le paiement de deux objets
  achetés exige leur provenance et leur charge disponible.
- **Gnome (§§192, 46, 12)** : l’identité de l’arme transformée est conservée
  hors de l’inventaire jusqu’à sa restitution. Le projectile du §46 coûte deux
  points de Chance une seule fois. Le §12 exige exactement dix pièces OU deux
  exemplaires choisis, puis restitue la même épée sans en fabriquer une nouvelle.
  Un passage consulté directement sans arme transformée ne crée pas d’épée.
- **Nœud coulant (§§358, 218)** : un test de Chance décide si l’épée reste dans
  le fourreau. En cas d’échec, la même arme devient inaccessible et son bonus
  cesse. Le paiement existant du §218 (5 Or OU un objet magique) la restitue et
  la rééquipe une seule fois. Elle ne peut pas elle-même servir de paiement
  tant qu’elle est au sol. La libération n’invente aucun dégât de chute.
- **Quête** : seules la tête et le manche marqués G valident le marteau. Les
  fausses pièces ne conviennent pas. La remise retire les deux pièces authentiques
  et marque la victoire sans inventer une valeur d’or pour les récompenses finales.
- **Effets ordinaires** : les pertes de Chance des §§13/42/129/134/141/237,
  la bénédiction du §166, les bijoux des §§106/174 et la pièce du §387 ont leur
  commande explicite. La mise du bras de fer n’est pas retirée une seconde fois
  au §129, ni le don du moine au §166. Les §§145/299/353 vident seulement les
  provisions ; le §53 vide seulement l’or. Le §163 retire trois points d’Endurance sans
  jet de Chance. Chaque effet physique est mémorisé pour ne pas être rejoué.
  Au §219, le point de Chance de la trouvaille est séparé du choix facultatif
  de prendre la fléchette d’argent. Les valeurs des bijoux restent descriptives
  et ne créent pas de pièces d’or.
- **Lanterne magique (§§395, 154, 370)** : test obligatoire de Chance avec une
  dépense, perte de trois points d’Endurance seulement en cas d’échec, puis choix
  d’un exemplaire à perdre si le héros survit. Le §154 abandonne la lanterne
  magique, sans retirer la lanterne de voyage. Les sorties attendent la résolution
  et les marqueurs sauvegardés empêchent de rejouer l’éclair ou la perte d’objet.
  Annuler le choix ne dépense rien. Une perte retire aussi la charge ou le bonus
  de port de l’exemplaire choisi ; les autres exemplaires restent disponibles.

Les effets sont des commandes explicites. Les boutons et les liens du lecteur
attendent leur résolution lorsqu’elle est nécessaire ; les routes conditionnelles
implantées vérifient la charge ou le port effectif. Les conditions des passages
encore en consultation ne sont pas interprétées à partir de leur texte libre.

## Combats raccordés

| Paragraphes | Règle |
| --- | --- |
| 96 et 276 | Même rencontre persistante : chien initial, paire de chiens, puis chien et maître. |
| 104 | Chef bandit puis deux paires de bandits. |
| 377 | Deux Pygmées, cible changeable à chaque assaut et fuite possible. |
| 123 | Deux branches successives de l’Homme-Arbre. |
| 107 | Fouet du Démon entre les forces d’attaque et les blessures ordinaires. |
| 227 | Quatre coups blessants de la Goule provoquent la paralysie et la fin. |
| 186 | Anguille Carnivore H5/E4 ; victoire vers le §131, sans fuite. |
| 231 | Trois Faucons de la Mort successifs H4/E4, H4/E3, H5/E4 ; victoire au §224, fuite réglementaire au §332. |
| 310 | Troll des Cavernes H8/E9, réveillé après échec au §376 ; victoire au §101, butin commun au §74. |
| 285 | La blessure du Loup-Garou reste mémorisée malgré les soins (§388). |
| 84 | Fuite après exactement trois assauts terminés, égalités comprises. |
| 49, 71, 165 et 193 | Force d’Attaque -3 sous plafond bas. |
| 352 | Force d’Attaque -2 sur la plate-forme ; fuite puis chute. |

Chaque membre d’une paire possède ses propres jets. Le héros ne peut blesser que
la cible offensive ; il doit parer l’autre. Un survivant termine le combat seul.
Le choix de cible revient entre chaque assaut. La chronique n’ajoute pas un nouvel
assaut pour la seconde attaque et le grand bandeau de victoire attend la dernière
paire. Une blessure létale interrompt les jets et coups suivants.

## Interprétations explicites

La source n’explicite pas toutes les interactions. Ces choix sont isolés dans
`rules.py` et couverts par des scénarios, pour pouvoir les réviser sans toucher au
Sorcier :

- **Potion des deux combats** : une rencontre complète compte pour un combat,
  groupes et séquences compris. Suspendre, sauvegarder, changer de cible ou passer
  à la paire suivante ne consomme pas un autre combat. Une fuite compte comme une
  rencontre engagée. Le bonus reste actif pendant toute la rencontre concernée.
- **Bouclier d’empereur et Chance** : la protection sur 4–6 ramène d’abord la
  blessure normale à un point ; le choix facultatif de Chance agit sur cette base.
  Le bouclier n’intervient ni sur le fouet, ni sur la fuite, ni sur les pièges.
- **Fuite de la plate-forme** : blessure de fuite réglementaire, puis perte de trois
  points au §156 si le joueur a survécu. Un chargement n’applique pas de nouvelle chute.
- **Chaise sans provisions** : cas non décrit ; le bouton ne résout pas une prise
  de repas imaginaire. L’erreur est expliquée sans changer les caractéristiques.
- **Champignons Brouilleurs** : seuls les scores courants sont échangés. Les soins
  ultérieurs utilisent les plafonds initiaux conservés.
- **Lanterne après l’échec (§370)** : la source ne précise pas son abandon.
  Elle reste dans le sac, sauf si le joueur la choisit comme objet perdu. Le cas
  sans objet susceptible d’être retiré n’est pas décrit : la commande explique
  ce blocage et laisse le passage non résolu, sans inventer de paiement de remplacement.
  L’Anneau de Lenteur et les objets verrouillés ne peuvent pas être choisis.
- **Objets précieux du Gnome (§12)** : aucun inventaire fermé ni seuil de valeur
  n’est défini par la source. Le joueur choisit explicitement les deux objets
  qu’il accepte de donner comme précieux ; le moteur vérifie les exemplaires
  présents et refuse les objets verrouillés. Il ne convertit pas les bijoux en
  monnaie. Sans paiement valide, les sorties restent bloquées ; aucune issue
  gratuite n’est ajoutée au cas d’insolvabilité non décrit.
- **Piège sans arme ou sans paiement** : le cas sans épée disponible au §358
  est expliqué sans dépenser de Chance ni inventer une libération. Au §218,
  un paiement invalide laisse l’épée au sol ; aucune dette ni blessure de
  remplacement n’est ajoutée. Consulter ce passage sans arme tombée ne crée
  pas d’épée lors d’un paiement.
- **Habileté et épée enchantée** : l’Habileté de base et son total initial sont
  conservés séparément du bonus calculé. La feuille et le combat affichent la
  valeur effective (par exemple 10 pour une base de 8). Les potions et le vœu
  restaurent la base ; ils ne font pas perdre ni cumuler le bonus. L’échange
  Habileté/Chance du §308 porte sur les scores de base : le bonus attaché à
  l’arme reste sur l’Habileté. Le champ de sauvegarde `habilete` conserve la base ;
  la sélection d’arme et la source du §70 permettent de recalculer le bonus.

## Organisation et persistance

`grimoire_modules/foret/rules.py` contient les calculs et validations sans Qt et
sans hasard. `encounters.py` décrit les groupes et sorties relus. `actions.py`
relie ces services aux dés animés et aux transactions. `controller.py` garde la
navigation et la présentation. Aucune exception du Sorcier n’est héritée.

L’état est dans `character.book_state.foret` : charges, objets portés, butins,
paiements, blessures, rencontres et consommation de potion. Les marqueurs locaux
d’issue sont conservés sous la clé du paragraphe. Les instantanés existants
copient ces données : sauvegarde, chargement et annulation ne recréent pas les
adversaires et ne réattribuent pas les récompenses. Les achats successifs ont
chacun leur transaction, sans regrouper toute la visite de la boutique.

Le dialogue de combat lit les profils via `_combat_entry` et les adversaires via
`_combat_roster`. Par défaut ces extensions reprennent le catalogue vérifié
existant : le Sorcier conserve son moteur et ses règles.

## Périmètre restant

`mechanics_implementation` dans le catalogue énumère les passages raccordés ;
`automation_pending` conserve la liste des passages qui n’ont pas encore une
intégration complète. Les autres effets ordinaires et rencontres restent à relier,
ainsi que les illustrations. Le §70 utilise désormais la règle de bonus confirmée
par l’utilisateur, sans modifier les règles de l’épée magique du Sorcier.
Les §§29/317 demandent encore de confirmer le mode des deux adversaires.
Les corrections fournies par l’utilisateur le 22 octobre 2026 lèvent les deux
blocages de source : §186 complété par Anguille Carnivore H5/E4 et victoire au
§131 ; §267 corrigé vers le §196 pour entrer dans la caverne (retour au §25).
La réparation du texte est limitée à l’édition reconnue et appliquée une seule fois.

## Vérification locale

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tools\audit_foret.py
.\.venv\Scripts\python.exe main.py
```

Après import du PDF exact, créer un héros et suivre le départ vers Yaztromo :
achats possibles dans la limite des 30 pièces. Pour vérifier une mécanique isolée
en mode préparation, le menu Actions permet de consulter son paragraphe (par
exemple 377 pour les Pygmées ou 84 pour le délai de fuite). Cela constitue un test
de moteur, pas une partie complète validée. Aucun PDF ni illustration n’est livré.
