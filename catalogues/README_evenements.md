# Base d'événements — édition 1982

Cette base ne contient pas le texte du livre. Elle associe les numéros de paragraphes à des **métadonnées de règles** lues dans le PDF fourni. Son SHA-256 garantit qu'elle ne s'applique pas par erreur à une autre édition.

## État de la revue

- 400 paragraphes numérotés retrouvés dans le PDF.
- 400 paragraphes vérifiés ponctuellement ; aucune entrée restante dans `review_pending`. Cette couverture du catalogue ne remplace pas la validation de toutes les parties possibles.
- 53 paragraphes à effets d'entrée automatiques : 11, 25, 27, 28, 40, 44, 49, 51, 56, 64, 75, 109, 110, 118, 135, 145, 147, 153, 170, 181, 183, 185, 196, 202, 203, 216, 239, 241, 247, 258, 259, 263, 264, 266, 294, 296, 313, 325, 327, 330, 342, 343, 344, 352, 355, 368, 371, 374, 376, 387, 388, 390, 400.
- 347 autres paragraphes : routes, choix et combats. 25 épreuves déclaratives : 2, 18, 47, 53, 55, 71, 74, 82, 83, 91, 123, 144, 156, 159, 166, 195, 209, 213, 243, 275, 298, 316, 339, 361, 389. Les jets avec état sont décrits séparément.
- Le champ `review_pending` est **une file de revue**, pas une liste de paragraphes sans action.
- Les indications de détection par mots-clés ne sont jamais considérées comme une preuve d'action.

Les sections ci-dessous consignent les étapes historiques de la revue. Les mentions anciennes « en attente » sont remplacées par le dernier lot décrit en fin de document. La couverture ci-dessus et `review_pending` décrivent l’état actuel.

## Sécurité de l'automatisation

Seules les entrées `status=verifie` et `mode=automatique` déclenchent des effets. Elles ne se déclenchent qu'une fois par partie et sont enregistrées avec l'état utilisé par annuler/rétablir et sauvegarder/charger. Les effets positifs sur HABILETÉ, ENDURANCE et CHANCE respectent les plafonds initiaux. Les actions facultatives sont autorisées uniquement via un bouton explicite pour les §38, §50, §145, §203 et §390. Elles sont suivies séparément pour éviter les doubles prises et permettre l'annulation. Un compteur de pièces d'or est ajouté (1 pièce initiale conformément aux règles, gains §28/110/147/342 et récompense facultative §390). Les combats simples du §8 (Barbare) et §16 (Ogre) préparent automatiquement l'adversaire une seule fois, sans réinitialiser les points d'Endurance au retour dans le passage. Le combat en série du §20 prépare automatiquement les quatre Nains dans l'ordre : après chaque adversaire vaincu, le suivant est chargé ; après le dernier, départ au §376 si ce paragraphe est présent. L'ordre courant est sauvegardé et annulable. La fuite vers §291 et sa pénalité restent manuelles. Le combat §86 prépare le Crocodile et compte deux assauts (y compris les égalités) ; ensuite, le joueur choisit de continuer jusqu'à la victoire (§259) ou de jouer un dernier assaut avant le §350. La mort du héros bloque la progression. La décision, les assauts et les issues sont annulables et sauvegardés. Un retour ultérieur au §86 ne réinitialise pas ce combat terminé. Les passages §204 (mise d'au moins une pièce d'or) et §264 (possession de la clé du hangar) présentent des boutons d'itinéraire conditionnés à l'état actuel du personnage. L'eau sainte du §109 remonte Habileté et Endurance à des seuils dépendant des valeurs de départ sans jamais les diminuer. Les autres actions facultatives sont exclues de cette première tranche. Les jets des §2, §18, §47, §53, §55, §74, §82, §83, §91, §243 et §389 sont initiés par un bouton qui applique l'issue et la destination, sans relancer si le jet a déjà été effectué. Le §82 présente aussi la possibilité de ne pas tenter le vol. Les sept épreuves de Chance §2/18/74/82/83/91/389 soustraient un point après la comparaison du jet. Les liens hypertextes intégrés au récit sont également bloqués s'ils pointent vers une route cataloguée comme interdite selon l'état de la partie.

**Limite actuelle :** « une seule fois par partie » est une politique de protection provisoire. Certains événements narratifs peuvent être réexécutables lors d'une nouvelle visite ; déterminer les bonnes règles de répétition pour chaque paragraphe demande la revue complète du livre.


### Fuite et suites de combat

- La fuite est pilotée par les règles vérifiées des §8, §16 et §20. Le §16 exige deux assauts complets avant d'autoriser la fuite ; égalités comprises. Les autres la permettent durant l'affrontement.
- Pénalité de fuite : -2 Endurance, ou tentative volontaire de Chance donnant -1 si chanceux ou -3 si malchanceux ; la Chance est testée avant de dépenser un point. Une fuite mortelle n'ouvre pas le paragraphe de destination.
- Les boutons de fuite sans pénalité sont supprimés pour ces paragraphes ; les liens dans le texte passent par la même procédure contrôlée. Les commandes de navigation manuelle restent libres pour les usages avancés.
- §259 : victoire contre le Crocodile, +1 Habileté et +2 Chance automatisés. §350 : rencontre avec les Piranhas automatisée selon les blessures du Crocodile ; voir la section dédiée.
- La première version compte les assauts de fuite en fonction du paragraphe et conserve les compteurs en sauvegarde / annulation. Ce mécanisme reste à valider par des parties complètes sur Windows.


### Audit des renvois de navigation

Un balayage du PDF complet a mis en évidence 17 paragraphes où le détecteur de choix omettait au moins un renvoi grammaticalement explicite : §§36, 66, 67, 77, 78, 130, 151, 156, 177, 211, 213, 234, 291, 295, 306, 315 et 330. Les formulations « vous irez dans ce cas au », « en vous rendant au », « en allant au », « rendez-vous après au » et « rendez-vous maintenant au » sont maintenant détectées et rendues cliquables. Tests ciblés ajoutés, dont un essai sur les 17 paragraphes lorsque le PDF de référence est disponible.

Cet audit concerne **les destinations seulement**. Il ne change pas le nombre de paragraphes dont l'ensemble des événements a été manuellement vérifié (46/400). Les destinations conditionnelles ne remplacent pas une vérification de la logique des branches du livre.


### Choix et objets vérifiés aux §§27, 31 et 32

- **§27** : Chance +2 dès la lecture du passage, même si le joueur refuse l'épée magique. Si le joueur l'accepte, l'épée précédente est retirée du sac, l'épée magique est ajoutée et l'Habileté maximale **ainsi que** l'Habileté actuelle augmentent de 2 ; ce choix n'est jamais appliqué automatiquement.
- **§31** : le bonus de +2 Habileté exige la **Pierre précieuse de la statue** obtenue au §75. Sans la pierre, aucun bouton de bonus n'apparaît ; la pierre reste dans le sac après avoir été présentée.
- **§32** : le bonus de +2 Chance n'est proposé que si le héros possède le **Fromage**. Le choix retire effectivement le Fromage du sac et empêche une deuxième utilisation.
- Les conditions des boutons d'objets sont vérifiées **une seconde fois au clic** ; modifier l'inventaire après l'affichage ne permet pas d'exécuter un choix devenu impossible. Ces changements sont couverts par des tests d'annulation et de non-répétition.


### Casque ensorcelé et épée de la rivière (édition vérifiée)

- **§202** : perte automatique d'un point d'Habileté et ajout du « Casque ensorcelé » dans le sac. Le casque figure aussi dans `character.locked_items`, ce qui empêche le bouton « Retirer » de contourner la malédiction. Ce verrouillage est enregistré avec la fiche, donc restauré lors d'une sauvegarde ou d'une annulation.
- **§344** : acquisition de l'épée trouvée dans la rivière ; les deux suites §56 et §153 restent disponibles. Le livre lui attribue **+1 Habileté lorsqu'elle est utilisée au combat**, ce qui n'est pas encore automatique, faute de suivi fiable de l'arme maniée.
- **§153** : perte automatique d'un point d'Endurance et abandon de l'épée trouvée dans la rivière si elle est dans le sac ; l'ancienne arme et les autres objets ne sont pas retirés. Le cas est réversible par annulation.
- Quatre nouveaux tests assurent le verrouillage, la non-répétition des malédictions, l'acquisition et la destruction de l'épée, et les deux destinations du §344.


### Arme effectivement maniée — §§27, 56, 153 et 344

Le champ `equipped_weapon` distingue les armes dans le sac de celle effectivement utilisée. Un sélecteur dans la sacoche permet de changer d'arme ; le changement est annulable. `combat_skill(character)` calcule la force d'attaque effective :

- Épée ordinaire : Habileté courante, sans bonus.
- Épée trouvée dans la rivière (§344) : **+1 uniquement sur la force d'attaque** lorsque cette épée est équipée. Le score d'Habileté indiqué sur la fiche ne change pas. Au §56, l'épée d'origine est jetée et celle de la rivière devient l'arme équipée ; au §153, l'épée de la rivière est abandonnée.
- Épée magique (§27) : son bonus de +2 sur Habileté actuelle et maximale n'est actif **que lorsqu'elle est équipée**. Changer d'arme retire ces deux points des valeurs, puis les remet lorsque l'épée est rééquipée ; aucun cumul supplémentaire n'est permis. Le gain de Chance du §27 reste indépendant de ce choix.

Ces changements affectent également les combats particuliers qui utilisent `combat_round` et l'état sauvegardé. Quatre tests supplémentaires couvrent la comparaison des forces d'attaque, le changement d'arme, le §56 et l'annulation. Le port d'une arme ne prétend pas résoudre les autres règles de combat qui ne sont pas encore cataloguées.


### Bouclier au croissant du §155

Le bouclier est **facultatif**, mais sa prise oblige à abandonner une pièce d'équipement. Un dialogue propose uniquement les objets présents dans le sac qui ne sont pas verrouillés par une malédiction. Si le joueur ne choisit aucun objet, aucune prise n'a lieu. Le bouclier entre alors dans le sac, utilisable via une case à cocher ; son activation est enregistrée dans la partie.

Lorsqu'un monstre blesse le héros pendant un combat où le bouclier est utilisé, un dé supplémentaire est lancé : sur **6**, la blessure est réduite d'un point (2→1 ; 1→0) ; les cinq autres faces laissent les dégâts inchangés. La réduction intervient après un éventuel test de Chance, et seulement lors d'une blessure reçue, jamais lors d'un coup porté par le joueur. Le bouclier retiré de l'inventaire se désactive.

Le §155 fait passer les **paragraphes individuellement revus à 49/400** et **65 méthodes de test** couvrent désormais les mécanismes documentés, dont quatre nouvelles sur le bouclier. Les combats avec des règles ne passant pas par `combat_round` restent à examiner.


### Piranhas (§350) : dépendance réelle avec le Crocodile (§86)

À chaque blessure infligée au Crocodile, l'état du §86 retient `wounded=True`. Ce fait est transmis au §350 **uniquement lors de la diversion** choisie après les deux premiers assauts et l'assaut supplémentaire. Les états sont persistés dans la sauvegarde et dans annuler/rétablir.

- Crocodile blessé : les Piranhas s'attaquent surtout au reptile, donc le héros combat **Piranhas H5/E1**, sans jet supplémentaire.
- Crocodile indemne : **1d6** obligatoire. Résultat 1 ou 2 : **H5/E5** ; 3 à 6 : **H5/E1**. Le bouton de jet est affiché au §350, et le combat n'est préparé qu'après son résultat.
- Si les Piranhas sont vaincus et le héros survit : **Chance +1**, puis §7. Le repas permis une fois sur la rive est **facultatif** et n'est pas déclenché automatiquement.
- Le lien direct vers §7 est bloqué tant que ce combat n'est pas gagné. Le détecteur général de rencontres ne propose pas de préparation qui écraserait les caractéristiques issues du dé.

Une ouverture directe et isolée du §350 sans arriver du combat du §86 ne donne pas assez de contexte pour automatiser les Piranhas : il faut alors rejouer la chaîne §86 → §350. Les tests ciblent les six issues du dé, les deux profils, le gain de Chance, les liens et l'annulation.

## Suite

Examiner chaque paragraphe restant, notamment les combats en série, les tests de Chance, les inventaires conditionnels, les objets consommables, les pertes et gains de maximum de caractéristiques et les issues de combat. Écrire un scénario de test par événement vérifié avant de l'activer. Ne pas déclarer la base exhaustive avant que les 400 paragraphes soient qualifiés.

### Quatre nouveaux paragraphes vérifiés : §§170, 209, 273 et 376

- **§170** : crucifix en argent inscrit comme **objet valant 4 pièces d'or**, sans ajouter immédiatement 4 pièces à la bourse. Le passage mène au §319.
- **§209** : pont branlant, lancer **1d6 obligatoire** ; un résultat de 6 entraîne la chute au §158, tout autre résultat conduit au §47. Le système d'issue garantit la navigation et son annulation.
- **§273** : les cinq piquets de bois peuvent être pris **facultativement** après la victoire contre le Barbare, avant de poursuivre au §189.
- **§376** : les trois points de Chance gagnés après les quatre Nains sont **automatiques**, tandis que la collecte des pièces de cuivre valant 4 pièces d'or est **facultative**. Le repas est également facultatif ; la suite est §291.

Pour les entrées en mode `des`, Bifurk masque les boutons de destination conditionnés par un jet tant que le lancer obligatoire n'a pas été résolu. Les liens correspondants dans le texte sont également bloqués avec un message, sans interdire le saut manuel de débogage.

Les métadonnées de ce catalogue sont propres au PDF de référence ; aucune page du livre n'est recopiée dans le dépôt.


### Passeur du §3 et outils du §34

- **§3** : la traversée payée demande **3 pièces d'or**, débitées au moment où le joueur choisit le §272 (bouton ou lien du texte) ; le §127 (« menacer ») reste possible sans payer. Si le héros a moins de 3 pièces, le chemin payant n'est pas proposé et son activation directe est refusée. Le débit et la navigation constituent une seule action annulable.
- **§34** : le maillet en bois dur et le ciseau à lame d'argent sont **mutuellement exclusifs**. En choisir un demande d'abandonner un objet réel du sac, à l'exception des objets verrouillés par une malédiction. Aucun échange n'a lieu si le joueur annule le dialogue. La perte éventuelle d'une arme équipée actualise son état et son bonus. Après l'échange, la suite est le §96.
- Quatre tests garantissent les refus sans modification, le paiement unique par trajet, l'échange exclusif et l'annulation. Les actions sont pilotées par les données du catalogue plutôt que par une détection heuristique des mots du texte.


### Combats particuliers : Farfadet §33 et Être §41

- **§33** : combat contre le **Farfadet H6/E4**. Une fuite vers §320 entraîne la pénalité réglementaire ; après sa défaite, §147 est ouvert automatiquement, avec l'or et la Chance accordés **une fois** par la boîte du §147. Annuler un assaut restaure l'Endurance du Farfadet, la position et les récompenses.
- **§41** : combat contre **l'Être H9/E6**. À la première blessure *réellement infligée au monstre*, l'affrontement s'arrête immédiatement et Bifurk conduit au §310. Il ne faut **pas** attendre la mort de l'adversaire. Ce passage explique l'invulnérabilité de l'Être aux armes ordinaires.
- Les liens et choix génériques vers §147/§310 ne peuvent plus contourner les objectifs du combat ; les commandes de navigation manuelle restent libres pour le débogage.
- Aucun monstre préparé par le catalogue ne peut être remis à son Endurance initiale par un bouton heuristique « Préparer le combat » ; sa progression reste enregistrée et annulable.
- Quatre nouveaux tests contrôlent la victoire du §33, sa fuite, le premier coup du §41 et la protection de sa destination.


### Nouveaux passages : Araignée géante §61, Lutin §71 et Être §310

- **§61** : Araignée géante H7/E8, victoire → §29. La fuite vers §375 n'est proposée qu'après **deux assauts** comptabilisés, égalités comprises, et applique la blessure de fuite avec Chance facultative. L'ennemi ne peut pas être réinitialisé depuis une détection heuristique ; les sorties de combat sont protégées contre le contournement.
- **§71** : le Lutin endormi impose un **test de Chance à deux dés**. Comparer le total à la Chance *avant* de dépenser un point : réussite → §301, échec → §248. Résultat et dépense sont annulables ensemble.
- **§310** : suite vérifiée de l'Être du §41 ; le héros constate l'inefficacité de son attaque, peut choisir une autre arme et poursuit au §211. Aucun bonus de caractéristique n'est inventé.
- Cinq tests ciblent les deux assauts de fuite, les conséquences de victoire, le seuil de Chance, les deux issues de l'épreuve et l'annulation.


### Banc enchanté et provisions — §§15, 38 et 58

- **§38** : récupération *facultative* d'œufs de caille donnant **deux repas supplémentaires**, soit +2 Provisions, une seule fois. Puis §66.
- **§58** : deux itinéraires explicites : continuer vers §367 sans manger ou s'arrêter au §15 pour un repas, à condition de disposer d'au moins une provision. Le contrôle de disponibilité s'applique aux liens du texte aussi bien qu'aux boutons.
- **§15** : pour manger au banc enchanté, le joueur lance l'action dédiée une seule fois. Elle consomme **1 Provision**, rend jusqu'à **6 Endurance** (+4 du repas et +2 du banc) et jusqu'à **1 Habileté**, sans dépasser les totaux initiaux. Le passage vers §367 est bloqué tant que cette action n'a pas été résolue. La progression, les ressources et les statistiques sont annulables ensemble.

Les tests vérifient l'absence de provisions, les limites des caractéristiques, le caractère facultatif du butin et la non-répétition des effets. **La base s'applique exclusivement au PDF dont l'empreinte est enregistrée**, sans reprise de son texte.

### Deux Lutins successifs §19 et Fromage facultatif §317

- **§19** : deux Lutins attaquent **l'un après l'autre** : premier H5/E5, puis second H5/E6. Le mécanisme de `combat.mode=sequence`, initialement réservé au §20 (quatre Nains), fonctionne désormais sur tout paragraphe du catalogue possédant une liste d'adversaires. Le second Lutin n'est préparé qu'après la défaite du premier ; les dégâts et l'ordre des combats se restaurent par annulation.
- **Victoire au §19** : passage au §317 uniquement après la défaite des deux Lutins. Les liens ou boutons du PDF ne permettent pas d'ignorer un combat séquentiel en cours. La fin de la série est enregistrée dans les rencontres préparées pour ne pas redémarrer le combat en revisitant l'ancien passage.
- **§317** : le morceau de **Fromage** est facultatif, acquis au plus une fois, avant de continuer au §303. Le nom de l'objet est exactement celui attendu par le §32 ; le jeter aux rats retire le Fromage du sac et donne le bonus de Chance correspondant.
- Quatre nouveaux tests couvrent la progression de la série, la victoire, le blocage du renvoi, le Fromage et l'annulation. La suite compte **96 méthodes de test** sur cette branche.


### Itinéraires contrôlés §§35, 36, 57, 84 et repas du §77

- **§35** : gaz dans la chambre ; soit fuite au §136, soit tentative de récupérer la clé au §361. Aucun dégât n'est supposé avant le paragraphe suivant.
- **§36** : face au vieil homme, calmer au §263 ou attaquer au §353.
- **§57** : devant l'Ogre, attaque au §16, fuite discrète au §2 ou diversion au §119. Choisir §16 prépare le combat déjà catalogué H8/E10.
- **§84** : à la rencontre du vieil homme et de son familier ailé, s'asseoir au §204, repartir au §280 ou attaquer au §377.
- **§77** : abri sûr avec repas **facultatif** ; le bouton de repas réutilise la règle existante (+4 Endurance plafonnée, -1 Provision), uniquement si des provisions restent. L'entrée au §77 ne consomme rien ; on peut directement partir à l'est vers §345 ou à l'ouest vers §18. L'utilisation du repas est annulable.

Quatre tests supplémentaires couvrent les choix exacts, le repas volontaire et non disponible sans provisions, puis la préparation de l'Ogre et l'annulation. Les options déjà cataloguées conservent leurs identifiants historiques.

### Revue des embranchements et repos au §90

19 paragraphes supplémentaires ont été examinés à partir du PDF de l'édition française de 1982 : **9, 21, 23, 30, 37, 42, 43, 46, 48, 52, 54, 62, 63, 66, 67, 78, 79, 85 et 90**. Les itinéraires sont inscrits explicitement dans `routes` plutôt que déduits d'une expression régulière potentiellement incomplète. Ces paragraphes ne créent aucun objet, ne modifient aucune statistique et n'impliquent aucune dépense implicite à l'arrivée (à l'exception du repas facultatif au §90).

- **§52** : cinq possibilités distinctes — aller au sud §391, chercher vers le sud §362, aller au nord §354, chercher vers le nord §234, partir à l'est §291. Aucun chemin n'est omis.
- **§85** : quatre directions — nord §106, sud §373, est §318, ouest §59.
- **§90** : possibilité de consommer un repas ordinaire en faisant halte, sans obligation ; départ vers §253 quel que soit le choix. Le bouton de repas s'actualise quand la provision restante tombe à zéro, sans réinitialiser l'action. Annuler restaure le repas et l'état du bouton.

Cinq nouveaux tests contrôlent tous ces renvois, l'absence de destinations en double, le nombre de boutons dans l'interface, le repos volontaire et le mécanisme d'annulation. Le catalogue ne contient pas le texte protégé du livre.

### Revue de la tranche §§92 à 115 — 19 passages supplémentaires

Les paragraphes **92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 107, 108, 111, 113, 114 et 115** ont été relus dans le PDF 1982. Les renvois des 18 paragraphes de navigation sont reproduits dans le catalogue en métadonnées `routes`, sans aucun texte long du livre ni récompense inventée.

- **§97** : trois approches du vieil homme (discuter §334, attaquer §247, repartir §292).
- **§102** : trois stratégies devant les tortionnaires du Nain (quitter §303, attaquer §19, tenter la feinte §68). Le choix §19 prépare bien les deux Lutins successifs déjà catalogués.
- **§100** : partie de jeu honnête §346 ou tricherie §91, qui possède déjà sa propre épreuve de dés.
- **§103** : tirer le levier §252 ou repartir §359 ; **§115** : inspecter les armes §95, un corps §313 ou les tonneaux §330.
- **§108** : combat vérifié contre une **Main H6/E4** ; victoire au §185, dont les effets existants sont conservés. Impossible de cliquer le renvoi de victoire avant la fin du combat.

Cinq nouveaux tests couvrent les renvois exacts, les trois choix du §97, les trois choix du §102 et son combat séquentiel, la Main, la protection du lien et les retours via annuler.

Le §105, dont les itinéraires nécessitent un objet spécifique, reste volontairement dans la file de revue jusqu'à ce que les noms exacts des objets soient harmonisés ; aucun trajet inventé n'y est ajouté.

### Nouveaux passages §§117 à 142

Quatorze passages supplémentaires sont catalogués : **117, 120, 121, 123, 124, 127, 128, 129, 133, 134, 136, 137, 141 et 142**. Onze paragraphes contiennent uniquement des renvois confirmés, sans récompense fictive.

- **§123** : jet obligatoire d'un dé pour tromper les Squelettes : 1 à 3 → §184 et Chance +2, 4 ou 5 → §164, 6 → §140. Le moteur de dés prend désormais en charge les conditions numériques `lte` et applique le bonus uniquement sur la première branche.
- **§127** : payer le passeur transformé coûte **5 pièces d'or** et donne accès au §272. Sans les fonds, seul le §188 (combattre) est proposé. Le débit s'effectue en même temps que la navigation, y compris pour les liens du texte.
- **§134** : choix de casque bronze → §202, fer → §325, ou retour → §87. Le casque en bronze est traité dans son propre paragraphe (§202), où la malédiction est déjà cataloguée.
- **§142** : Sorcier **Habileté 11 / Endurance 18**, sans fuite. Victoire → §396. Le renvoi n'est pas cliquable avant la défaite de l'adversaire.

Cinq tests supplémentaires couvrent les destinations, les six faces du dé, la Chance et l'annulation, le paiement et le combat final. Les paragraphes §§119, 125, 130, 131, 135, 139, 140 et 143 comportent des interactions plus complexes et restent volontairement à examiner plus profondément.

### Repas partagé §131, trésor après l'Être §135 et salle §122

Le PDF français de 1982 confirme trois nouvelles entrées :

- **§122** : face aux quatre êtres gris-verts, essayer de leur parler → §268, les attaquer → §282, s'enfuir par la porte sud → §13. Aucun effet préalable n'est inventé.
- **§131** : chez les personnages amicaux, le repas est **facultatif** et **partagé**. Il coûte 1 Provision mais ne restitue que **2 Endurance** (au lieu des 4 ordinaires), jusqu'au plafond initial. Une commande distincte enregistre cette restauration et permet d'annuler le repas ; partir sans manger conduit au §291.
- **§135** : après la victoire sur l'Être, le héros reçoit **automatiquement +2 Chance** une seule fois. Ramasser les **18 pièces d'or** est facultatif et ne se produit que sur commande, une fois ; le repas normal est également facultatif. La sortie mène au §360.

Cinq tests supplémentaires couvrent la liste des issues du §122, le partage du repas et ses plafonds, la disponibilité des provisions, la récompense facultative et l'annulation de plusieurs actions. Les anciens identifiants d'options du catalogue ne changent pas.

Les passages §§119, 125, 130, 139, 140 et 143 demandent des contraintes plus complexes (objet jeté, boucle de Chance, mises, clés et combats simultanés) et restent dans la file de revue ; ne pas les simuler par une simple route sans effets.

### Diversion contre l'Ogre §119 et fuite devant le Ver marin géant §143

- **§119** : la diversion exige de **rayer un objet transporté du sac**. Le joueur peut choisir **une pièce d'or même si le sac contient des objets** ; sans pièce disponible, il peut jeter un objet abandonnable. Sans objet utilisable ni or, l'action est impossible. Les objets verrouillés ne peuvent pas être abandonnés. Jeter une épée magique équipée retire aussi son bonus actif, et jeter le bouclier le déséquipe. Le §269 ne s'ouvre qu'après ce sacrifice ; un lien direct ne peut pas l'ignorer. Le choix de l'objet passe par la boîte de dialogue existante, avec Undo.
- **§143** : combat contre le **Ver marin géant H7/E7** ; victoire §44. Fuite au §399 seulement **après trois assauts** ; sa pénalité d'Endurance et la Chance éventuelle suivent les règles normales de fuite, auxquelles s'ajoute **une provision perdue** (repas commencé puis abandonné). Si la fuite est mortelle, la destination n'est pas atteinte. L'annulation restaure les provisions, Endurance et progression.

Cinq tests supplémentaires contrôlent le sacrifice d'objet et d'or, les objets maudits, le blocage du passage, la victoire contre le Ver marin, les trois assauts de fuite, la perte du repas et l'annulation. Les anciennes options du catalogue conservent leurs identifiants.

**Correctif §119 (retour utilisateur)** : le lancer d'une pièce d'or ne dépend désormais plus de la présence d'objets dans le sac. Le sélecteur propose la pièce d'or dès que la bourse contient au moins 1 PO, en parallèle des objets jetables. Deux tests supplémentaires couvrent le choix avec inventaire rempli, l'absence d'option or à 0 PO et l'annulation.

### Revue §§145 à 156 : Dragon, clé n°99 et épreuve de porte

Sept nouveaux paragraphes ont été vérifiés dans le PDF de 1982 : **146, 148, 149, 150, 152, 154 et 156**. Le §145, déjà vérifié, a reçu sa destination explicite §363, **sans changement de son identifiant historique d'option `cle99`**.

- **§145** : après le Serpent, +1 Chance à l'entrée une seule fois ; récupérer la **Clé de bronze 99** reste facultatif. Puis §363.
- **§146** : aller au nord §366 ou à l'ouest §11 après une recherche de passage secret infructueuse.
- **§148** : une créature se relève durant la fouille, suite imposée §230 ; aucun dégât supposé.
- **§149** : après extinction de la chandelle, ramper vers l'est §181, le nord §265 ou l'ouest §355.
- **§150** : croisée de trois chemins : nord §222, est §297, sud §133.
- **§152** : Dragon H10/E12, victoire §371. Combat préparé automatiquement et lien de victoire protégé, sans fuite inventée.
- **§154** : réveil de la créature, combat obligatoire au §41, qui est déjà catalogué et s'interrompt à la première blessure infligée.
- **§156** : jet obligatoire de deux dés sous Habileté ; réussite §343, échec §92 sans seconde tentative. Le jet ne diminue pas l'Habileté.

Cinq tests supplémentaires vérifient les routes, la clé, la victoire contre le Dragon et son annulation, les onze totaux de deux dés et le blocage de la porte avant l'épreuve.

Les passages complexes §125 (tests de Chance répétés), §130 (pari), §139 (trois clés) et §140 (plusieurs attaques dans le même assaut) restent en attente d'une modélisation complète.

### Traversée de rivière §§166, 158 et 218 ; parcours §§157–180

- **§166** : le héros regagne la rive sud en nageant. Un dé obligatoire décide de la suite : **1 à 4 → §218**, **5 ou 6 → §158** (Piranhas). Aucun effet automatique sur la Chance ou l'Endurance ne figure à ce stade.
- **§158** : combat jusqu'à la victoire contre les **Piranhas H5/E5**, considérés comme une seule créature ; destination §218. Le moteur prépare cet adversaire et bloque l'accès au §218 par le lien de victoire avant sa défaite. Le repas après combat reste volontaire : la commande générale « Prendre un repas » est disponible.
- **§218** : les quatre moyens de traverser sont proposés : bac §3, radeau §386, pont §209 ou nage §316. Le coût du bac n'est pas facturé au §218, puisqu'il est proposé au §3 ; les éventuelles autres épreuves sont gérées par leurs propres paragraphes.
- **Itinéraires vérifiés** : §§157, 160, 162, 164, 167, 168, 169, 171, 174, 175, 176, 177, 178 et 180. Le §168 propose trois stratégies devant le Chef des Farfadets ; le §177 offre trois chemins distincts. Aucune dépense ou récompense non mentionnée n'est créée.

Six nouveaux tests couvrent les routes, les six faces du dé §166, la préparation et la victoire contre les Piranhas, le blocage des renvois prématurés, les quatre choix du §218 et Undo. Les autres passages exigeant des combats spécifiques ou des règles de ressources sont laissés en attente.

### Revues §§181–210 : Rat-garou, mensonge aux Squelettes et caractéristiques

- **§181** : Habileté -1 automatiquement (douleur), puis mur ouest §355 ou nord §265.
- **§183** : après les Farfadets, Habileté +1 et Endurance +5, chacune plafonnée au maximum initial ; choix facultatif d'ouvrir la mallette §266 ou de partir §237.
- **§184** : tiroirs §322 ou outils §34. **§185** : après le bonus de Chance +2 déjà enregistré, sortie §162.
- **§188** : Rat-garou H8/E5, victoire §342 ou fuite immédiate §209 avec le coût normal de fuite, réversible par Undo. La sortie victoire est inaccessible avant la défaite.
- **§195** : un dé obligatoire ; 1–2 → §140 ; 3–4 → §164 ; 5–6 → §9 et Chance +2. Le gain n'est appliqué qu'à cette dernière branche, une fois.
- **§196** : 5 pièces d'or acquises automatiquement dans le tiroir, une seule fois ; retour §280.
- **Autres embranchements** : §§187, 190, 191, 193, 194, 197, 200, 205, 207, 208 et 210. Les renvois §§203 et 185 ont été complétés sans modifier leurs récompenses déjà enregistrées.

Six tests supplémentaires couvrent les routes, les six faces du jet §195, la Chance et Undo, le Rat-garou (fuite et victoire), les sorties bloquées ainsi que les plafonds des récompenses automatiques. Les paragraphes §§182, 198, 199, 201 et 206 restent à examiner en profondeur, car ils demandent des mécaniques plus complexes.

### Fontaine §216, porte verrouillée §213 et passages §§212–235

Dix-neuf paragraphes supplémentaires ont été examinés et catalogués : **212, 213, 214, 215, 216, 217, 219, 220, 222, 223, 224, 225, 226, 228, 229, 231, 232, 233 et 235**.

- **§213** : jet **obligatoire de deux dés** sous l'Habileté ; réussite → §36. Échec → **Endurance -1**, puis §314. Le joueur ne peut pas sélectionner un résultat sans résoudre le jet ; la perte et la navigation peuvent être annulées.
- **§216** : eau régénérante, **+4 Endurance**, **Habileté et Chance restaurées exactement à leur valeur initiale**, une seule fois. Un repas normal supplémentaire reste **facultatif** (1 Provision pour +4 Endurance plafonnée), puis sortie §384. Nouvel effet `restore_initial` avec validation de la caractéristique et des maxima.
- **§214** : trois chemins (nord-ouest §271, porte nord §104, rivière est §99). **§225** : nord §77 ou ouest §63. **§223** : porte à forcer §53 ou passage §300. D'autres destinations simples sont cataloguées explicitement sans effet inventé.
- **Attention §212** : boire le liquide est possible uniquement si le personnage n'a pas déjà essayé. Le catalogue conserve les deux renvois §369/§120 mais ne suit pas encore ce choix passé pour masquer le premier ; cette restriction doit être implémentée avant de considérer l'action totalement automatisée.
- **Non traités** : §211 (arme d'argent et fuite avec blessure), §221 (choix du premier équipement inscrit), §227 (pièce vide à la revisite), §230 (Goule et paralysie après quatre blessures). Ces règles exigent une mémoire d'état ou un traitement de combat spécifique.

Cinq nouveaux tests couvrent les itinéraires, les onze totaux possibles au §213, l'échec et Undo, la restauration exacte de la fontaine, le repas facultatif et Undo. 

### Édition 1982 : §§237 à 260 et correction de la revisite §212

Dix-neuf passages sont désormais vérifiés : **237, 238, 239, 240, 241, 242, 244, 245, 246, 248, 249, 250, 251, 252, 254, 255, 256, 257 et 260**. Les §§243, 247 et 259 avaient déjà leurs effets correctement catalogués ; ils sont conservés sans réécriture. Les sorties §§247 → 292 et 259 → 7 sont ajoutées.

- **§212** : une tentative antérieure de boire le liquide (visite du §369) rend cette action indisponible. L'interface masque le bouton §369 lors des passages suivants au §212 et interdit la destination aussi bien en cliquant sur le texte qu'en invoquant une route. Le §120 reste accessible. Le suivi utilise l'historique `visited_paragraphs`, enregistré et restauré avec la partie.
- **§239** : la chandelle permet **Chance +1** une fois, sortie §88 ou examen des peintures §149.
- **§240** : Serpent H5/E2, victoire §145. La clé n°99 du §145 reste un ramassage facultatif indépendant.
- **§241** : malus **Habileté -1** une seule fois, puis §90.
- **§242** : attaquer le coffre §379 ou vérifier les trois clés §139 ; **§254** : quatre choix possibles devant le Vampire (§352, §333, §279, §380).
- **§243** : piège du levier déjà catalogué, pair → H-1/E-2, impair → H-3/E-1, destination §128. Le résolveur de dés accepte désormais également la condition explicite `odd`, testée indépendamment ; les branches existantes de §243 restent inchangées.
- **§248** : Farfadet H6/E5, victoire §301.
- **§251** : trois Chauves-souris géantes attaquent comme **une seule créature H6/E6**, victoire §344, fuite vers §399 avec la pénalité normale.
- **§244** : repos avec repas proposé par §143 ou nage vers §399. Les coûts sont à gérer au paragraphe de destination, jamais débités en double à l'arrivée au §244.

Six tests supplémentaires vérifient les routes, les effets automatiques, les six issues du dé, le Serpent et les Chauves-souris, ainsi que le §212 après revisite, boutons et liens compris. Les paragraphes §253 et §258 demandent encore une analyse des objets facultatifs et de la scène complète avant modélisation.

### Correctif Qt/PyMuPDF : lien `paragraph:369`

Le message `QTextBrowser: No document for paragraph:369` provenait du comportement natif de `QTextBrowser`, qui tentait de résoudre les liens `paragraph:` en documents Qt malgré la connexion de `anchorClicked` à `MainWindow.follow_link`. La configuration applique maintenant **`setOpenLinks(False)`** en plus de `setOpenExternalLinks(False)` : Bifurk intercepte tous les liens internes, ce qui conserve les contrôles de routes (dont la bouteille §212/§369).

L'extraction utilise désormais **`import pymupdf`** et **`pymupdf.open`**, évitant l'avertissement de dépréciation du module `fitz` avec les versions récentes de PyMuPDF. Deux tests de non-régression vérifient la configuration Qt, l'émission de `anchorClicked`, la navigation et l'interdiction de reboire au §212.

### Revue de 21 passages §§261 à 290 — carrefour et Rats géants

Les passages **261, 262, 265, 267, 268, 269, 270, 271, 272, 274, 276, 277, 278, 280, 281, 283, 284, 285, 287, 288 et 290** ont été relus dans le PDF français de 1982, sans recopier le texte du livre.

- **§267** : quatre sorties explicites : nord §312, sud §246, ouest §79 et est §349. L'interface conserve les quatre boutons, et Annuler ramène au carrefour.
- **§287** : face aux trois Rats géants, **avec du Fromage** → §32, **sans Fromage** → §309. Les boutons et les liens directs appliquent la même condition d'inventaire. Le Fromage n'est pas consommé lors de la navigation §287 → §32 : sa consommation facultative n'intervient qu'au §32 via l'option existante `jeter_fromage` (identifiant inchangé).
- **§270** : trois choix dans la caverne (§61 exploration, §394 essayer les bottes, §375 repartir), sans prendre les bottes automatiquement.
- **§274** : entrer en attaquant §324, saluer courtoisement §356 ou entrer discrètement §98.
- **§277** : chercher un passage secret §146, sinon retour au carrefour puis nord §366 ou ouest §11.
- **§272** : après la traversée en bac, direction §7. Aucun nouveau débit d'or au §272, car l'éventuel prix est traité au départ (notamment au §127).

Les autres itinéraires relus sont transcrits explicitement. Les règles complexes des §§263, 266, 275, 279, 282, 286 et 289 ne sont pas encore considérées comme vérifiées : les interactions avec le dialogue, les objets, la Chance, les combats successifs ou l'issue finale doivent être modélisées entièrement.

Cinq nouveaux tests couvrent les itinéraires exacts, les quatre boutons du §267, la bifurcation selon l'inventaire au §287, la protection des liens, le Fromage conservé avant son utilisation et l'absence de double paiement au §272.

### Pont, nage et Loup-garou — §§291 à 320

**18 paragraphes** examinés et catalogués à partir du PDF français de 1982 : **291, 293, 297, 298, 299, 300, 301, 302, 303, 304, 307, 308, 312, 314, 315, 316, 318 et 320**. Les §§310 et 317 existaient déjà et n'ont pas été modifiés.

- **§298** : sur le pont glissant, un seul dé ; **6 → §86** (chute dans l'eau), **1 à 5 → §7** (berge nord), sans pénalité supplémentaire au moment du jet. La scène d'arrivée décide des suites.
- **§316** : nage depuis la berge sud, **deux dés ≤ Endurance** → §151, sinon retour §218 où un repas est possible. Aucune Chance dépensée et aucun malus d'Endurance arbitraire au §316.
- **§304** : Loup-garou **H8/E8** ; victoire §203, fuite possible à tout moment par la porte sud §66 avec le coût de fuite ordinaire. Le lien de victoire demeure bloqué pendant le combat et l'annulation restaure son état.
- **§303** : herse fermée et deux leviers, droit → §128, gauche → §243, où les blessures pair/impair déjà cataloguées restent inchangées.
- **§308** : quatre directions (ouest §187, nord §54, sud §160, est §354), avec quatre boutons distincts ; aucun trajet déduit du texte n'est perdu.
- **§291** : cul-de-sac est §315, bifurcation ouest §52 ou porte nord §227. Les autres itinéraires des §§293, 297, 299, 300, 301, 302, 307, 312, 314, 315, 318 et 320 sont explicites et sans effets inventés.

Les §§292 (possession de chandelle bleue), 294 (fouille et récompense), 295/306 (combat d'un monstre commun avec reprise contextuelle), 296 (ouvrage sur les Dragons), 305 (trois tests de Chance successifs), 309 (Rats successifs), 311 (dalles et équipement), 313 (deux objets parmi quatre) et 319 (objet découvert) sont volontairement laissés en attente d'une modélisation complète.

**Six tests supplémentaires** contrôlent les itinéraires, les six résultats du dé du pont, les onze totaux de nage, la navigation et Undo, la fuite face au Loup-garou et les quatre choix du carrefour.

### Reprise PR6 : §§321–350 et résolution du reliquat antérieur

Le PDF fourni a été contrôlé contre l’empreinte SHA-256 du catalogue. **112 entrées nouvelles** portent la couverture de 244 à **356/400**. Tous les §§1–350 sont répertoriés ; le §372, lié à la poursuite du combat du §65, a également été vérifié. Aucun texte narratif du livre n’est ajouté au dépôt.

- **§322** : clé de cuivre 66 facultative contre un équipement non maudit. **§328** : deux bois en Y avec le même coût. **§327** : butin groupé (30 PO, livre et bois en Y) contre un équipement ; Chance +3 et repas facultatif. Le dialogue annulé ne modifie rien ; les échanges se font au plus une fois.
- **§325** : casque magique, +1 à la Force d’Attaque tant qu’il est équipé et possédé ; l’Habileté de la fiche ne change pas. **§330** : +6 Endurance et +1 Chance, plafonnés.
- **§334/292** : chandelle bleue facultative à 20 PO, achat contrôlé au clic ; l’itinéraire dans les ténèbres dépend de sa possession.
- **§331** : Troll H8/E8, victoire §287. **§338** : Cyclope de Fer H10/E10, victoire §75 ou fuite §93. **§333** : Troll Vampire H10/E10, victoire §327 ; fuite seulement après six assauts et un test de Chance réussi. Un échec ordinaire impose six nouveaux assauts ; un échec sur 11 ou 12 mène au §224. Le test d’autorisation de fuite ne remplace pas la blessure normale de fuite.
- **§339** : fléchette, 1d6 Endurance perdu ; le §201 ne s’ouvre que si le héros survit. **§340/348** : les objets conditionnent réellement les routes ; Fromage jeté et Potion bue sont retirés du sac, avec navigation annulable.
- **§346** : choix explicite entre le hasard (2d6 : pair perd, impair gagne) et la Chance. La réussite de Chance exige un second 2d6 pour le gain ; l’échec utilise le premier total pour la perte. Les pertes sont limitées à l’or disponible ; un gain ajoute 2 Chance, plafonnées. La partie est résolue une seule fois avant le §131.

#### Cas complexes antérieurs

- **§125** : tests de Chance répétés jusqu’à la libération ou la mort ; chaque échec coûte 1 Endurance et chaque test 1 Chance. **§305** : trois tests successifs, seuil actualisé après chaque dépense, arrêt au premier échec. L’avancement se sauvegarde et s’annule.
- **§130** : mise de 1 à 20 PO sans dépasser la bourse, 2d6 pour chacun, égalité sans transfert, partie répétable ; chaque victoire accorde +2 H/E/C plafonnés. Le départ au §280 reste libre.
- **§139/182/198** : sélection de trois clés numérotées distinctes réellement possédées, destination égale à leur somme, clés conservées. Une combinaison déjà tentée ne peut être réutilisée. Chaque nouvel essai infructueux au §182 coûte 2 Endurance ; au §198, un test de Chance précède tout nouvel essai (réussite : -2 Endurance, échec : mort). Sans trois clés, aucune issue ne peut être inventée.
- **§313/221/319** : jusqu’à deux trouvailles parmi cinq, identification dans l’ordre choisi, puis sortie §81. L’or est identifié au §110 (8 PO, puis les 2 PO de la botte), le crucifix au §170 et l’épée au §27 ; aucun double gain n’est créé. Le §72 impose le choix d’une seule armure ; le bouclier du §132 peut être abandonné. **§201** : un seul butin parmi 25 PO, Potion d’Invisibilité ou gant.
- **§206/227** : le nombre de visites détermine le chemin ; charger ou annuler ne crée pas une nouvelle visite. **§179/258** : Minotaure, fuite après trois assauts ; après sa mort, le retour traverse une pièce vide sans pénalité ni nouveau combat. Récompenses facultatives et Chance séparées.
- **§199/236/282/309/372** : combats successifs ; les 2 Chance du §282 sont attribués après le premier Zombie, pas après la série entière. **§140** : chef, puis deux paires de Squelettes ; une cible choisie par paire peut être blessée, l’autre attaque en défense sans subir de dégâts. Chaque assaut complet et le choix de cible sont annulables.
- **§230** : quatre blessures distinctes de la Goule causent la paralysie ; un dégât nul après protection ne compte pas. Mort ou paralysie mène au §64. **§211/173/24** : armes ordinaires inefficaces, arme d’argent nécessaire pour blesser, flèche d’argent avec arc facultative et consommée ; trois blessures déclenchent la suite et la perte d’Habileté, puis chaque troisième blessure supplémentaire retire 1 Habileté.
- **§12/14/234/295/306 → §161** : un dé choisit l’un des six monstres ; la destination après victoire est mémorisée. Le §12 revient à l’alarme puis propose ses deux sorties ; une entrée isolée au §161 ne crée pas de destination.
- **§17/144/279** : routes selon crucifix ou épieu, jets de Chance pour l’épieu et issues du Vampire. **§296/126/26** : la formule du Dragon est mémorisée indépendamment de l’inventaire.
- **§39** : combat sous invisibilité enfin automatisé (+2 attaque, 3 dégâts infligés, dé de défense sur les six faces), sans modifier l’Habileté de base. **§116** : bonus d’attaque +1 propre aux deux Farfadets ivres. **§163** : test de Chance obligatoire avant le premier assaut. **§44** : fin du repas interrompu au §143, sans deuxième repas automatique à la revisite.

#### État, contrôles et validation

`book_actions.py` regroupe les interactions avec état. `character.book_state`, `book_visits` et `book_facts` sont inclus dans les instantanés existants ; les anciennes sauvegardes n’ont pas besoin de ces champs. Le chargement restaure aussi le nom, l’Habileté et l’Endurance de l’adversaire. Les actions et les navigations forment une seule entrée d’Annuler/Rétablir ; les ressources sont revérifiées au clic. Les boutons heuristiques ne doublent plus les effets des combats pris en charge.

Les tests synthétiques couvrent les issues des dés, les seuils, les pertes mortelles, les annulations de dialogue, la consommation des objets, les plafonds, les routes interdites, les combats et le chargement d’un état intermédiaire. Un contrôle avec le PDF compare les renvois réels des §§321–350 au catalogue, en complément de l’extraction et du rendu des 400 paragraphes.

**Limites conservées :** la plupart des événements restent protégés « une fois par partie », sauf répétition explicitement modélisée. La commande de saut manuel de paragraphe reste un outil avancé ; les contrôles portent sur les choix et liens du récit. Le §289 ne donne aucun renvoi explicite après son combat dans ce PDF : Bifurk n’en invente pas. Le défaut connu de cadrage de l’illustration de couverture reste un échec attendu distinct de ce travail. Les 44 passages encore dans `review_pending` appartiennent aux §§351–400.

Validation locale avec le PDF de référence présent : **220 tests exécutés, 219 réussis, 1 échec attendu** (cadrage connu de la couverture), aucun test ignoré. Le nouveau fichier `tests/test_complex_events.py` ajoute 52 tests.

```bash
QT_QPA_PLATFORM=offscreen XDG_CACHE_HOME=/workspace/.cache/bifurk .venv/bin/python -m unittest discover -s tests -v
```

### Dernier lot PR6 : §§351–400 et parcours jusqu’à la victoire

Les **44 dernières entrées** ont été relues dans le même PDF. Le catalogue couvre maintenant **400/400 paragraphes**, avec `review_pending=[]`. Les six entrées déjà présentes dans ce lot ont aussi été contrôlées et complétées lorsque nécessaire. Le texte narratif et le PDF restent hors du suivi Git.

- **§352/355** : pertes obligatoires d’Endurance ou d’Habileté, sans les appliquer deux fois à la simple réouverture du passage.
- **§361** : la clé 125 est acquise dès l’entrée. L’épreuve est un **2d6 ≤ Habileté**, sans dépense de Chance. L’échec retire **2 Habileté et 3 Endurance** ; le §136 n’est ouvert que si le héros survit. Clé, jet et conséquences sont restaurés correctement par Annuler/Rétablir et chargement.
- **§365** : cinq Farfadets successifs, profils **H6/E5, H6/E5, H4/E4, H3/E4, H2/E4** ; victoire §183, fuite payante §237. **§377** : Diablotin ailé **H5/E7**, victoire §196.
- **§371/374** : Chance **+3/+2** plafonnée, repas facultatif, puis §274/207. Les champs de repas et de sortie du §376 ont été complétés.
- **§379** : le coffre exige un test de Chance. La réussite détruit seulement l’épée utilisée et mène au §139 ; l’échec tue le héros. Détruire l’épée magique retire aussi son bonus de caractéristiques ; les autres armes sont conservées. Le §242 ne propose plus de frapper si aucune épée n’est disponible.
- **§383** : la route vers §80 exige la clé du Hangar ; tentative de forcer §264 et retour §129 restent possibles. **§387** : combinaison mortelle, aucune sortie narrative.
- **§390/294** : les cinq pièces du premier cadavre constituent un butin partagé. Les récupérer par un chemin interdit de les reprendre par l’autre. Les anciennes sauvegardes sont reconnues à partir de leurs marqueurs de fouille. Les boucles d’oreilles restent un objet, sans conversion automatique en or.
- **§393/369/212** : huit pièces, parchemin et bouteille facultatifs. La bouteille est consommée à la première gorgée au §369 ; on ne peut plus la reprendre ni la boire à nouveau par l’autre itinéraire. Lire le parchemin sur place reste possible sans emporter son exemplaire. La disponibilité du reste du butin ne dépend pas de la consommation de la bouteille.
- **§394** : Araignée **H7/E8**, **-2 à la Force d’Attaque** durant ce combat seulement ; l’Habileté de la fiche reste intacte. Victoire §232, où les bottes sont déchirées pour repartir.
- **§396** : deux clés distinctes ouvrent la porte sans être consommées. À défaut, la forcer coûte **5 Endurance** ; une blessure mortelle ne permet pas de rejoindre §242. **§400** : victoire enregistrée, sans inventer un montant exact d’or à partir d’un trésor décrit comme valant « au moins » mille pièces.

#### Correction indispensable : les deux clés 111

Le PDF donne une clé portant **111 au §75** et une autre, **rouge, portant 111 au §258**. Malgré la formulation générale du §139, ce sont deux objets distincts. Les fusionner, ou imposer trois numéros différents, rendait la bonne combinaison impossible.

La clé de la statue conserve son nom `Clé 111` pour compatibilité ; la seconde devient `Clé rouge 111`. La sélection exige trois objets distincts, mais autorise deux numéros identiques. La combinaison **99 + 111 + 111 = 321** mène maintenant par **§321 → §169 → §400**, vérifiée par un test qui collecte les clés dans leurs véritables passages. La même clé ne peut pas être sélectionnée deux fois.

Les anciennes sauvegardes dans lesquelles les deux clés ont déjà été fusionnées ne permettent pas de reconstruire leur provenance de manière certaine. Aucun objet n’est recréé silencieusement : pour tester ce parcours, commencer une nouvelle partie ou ajouter manuellement `Clé rouge 111` uniquement si les deux clés avaient effectivement été récupérées.

Les tests de `tests/test_final_events.py` contrôlent également les renvois du PDF sur les 50 paragraphes du lot, les onze résultats de l’épreuve du gaz, les morts, les objets détruits, le coût de la porte, les sauvegardes et l’absence de double butin. Les limites générales (politique de répétition conservatrice, saut manuel avancé et absence de renvoi explicite après le combat §289) restent documentées ; le défaut connu de cadrage de couverture reste hors de ce lot.

Validation du dernier lot avec le PDF présent : **251 tests exécutés, 250 réussis, 1 échec attendu** pour le cadrage connu de la couverture ; aucun test ignoré. Le fichier `tests/test_final_events.py` ajoute 31 tests.
