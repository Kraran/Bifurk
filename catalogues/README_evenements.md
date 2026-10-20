# Base d'événements — édition 1982

Cette base ne contient pas le texte du livre. Elle associe les numéros de paragraphes à des **métadonnées de règles** lues dans le PDF fourni. Son SHA-256 garantit qu'elle ne s'applique pas par erreur à une autre édition.

## État de la revue

- 400 paragraphes numérotés retrouvés dans le PDF.
- 69 paragraphes vérifiés ponctuellement ; 331 à étudier et valider individuellement.
- 28 paragraphes à effets d'entrée automatiques : 11, 25, 27, 28, 40, 49, 51, 56, 75, 109, 110, 145, 147, 153, 170, 185, 202, 203, 247, 259, 264, 342, 343, 344, 368, 376, 388, 390.
- 41 paragraphes conditionnels, jets de dés ou combats particuliers. 13 épreuves de dés cataloguées : 2, 18, 47, 53, 55, 71, 74, 82, 83, 91, 209, 243, 389.
- Le champ `review_pending` est **une file de revue**, pas une liste de paragraphes sans action.
- Les indications de détection par mots-clés ne sont jamais considérées comme une preuve d'action.

## Sécurité de l'automatisation

Seules les entrées `status=verifie` et `mode=automatique` déclenchent des effets. Elles ne se déclenchent qu'une fois par partie et sont enregistrées avec l'état utilisé par annuler/rétablir et sauvegarder/charger. Les effets positifs sur HABILETÉ, ENDURANCE et CHANCE respectent les plafonds initiaux. Les actions facultatives sont autorisées uniquement via un bouton explicite pour les §38, §50, §145, §203 et §390. Elles sont suivies séparément pour éviter les doubles prises et permettre l'annulation. Un compteur de pièces d'or est ajouté (1 pièce initiale conformément aux règles, gains §28/110/147/342 et récompense facultative §390). Les combats simples du §8 (Barbare) et §16 (Ogre) préparent automatiquement l'adversaire une seule fois, sans réinitialiser les points d'Endurance au retour dans le passage. Le combat en série du §20 prépare automatiquement les quatre Nains dans l'ordre : après chaque adversaire vaincu, le suivant est chargé ; après le dernier, départ au §376 si ce paragraphe est présent. L'ordre courant est sauvegardé et annulable. La fuite vers §291 et sa pénalité restent manuelles. Le combat §86 prépare le Crocodile et compte deux assauts (y compris les égalités) ; ensuite, le joueur choisit de continuer jusqu'à la victoire (§259) ou de jouer un dernier assaut avant le §350. La mort du héros bloque la progression. La décision, les assauts et les issues sont annulables et sauvegardés. Un retour ultérieur au §86 ne réinitialise pas ce combat terminé. Les passages §204 (mise d'au moins une pièce d'or) et §264 (possession de la clé du hangar) présentent des boutons d'itinéraire conditionnés à l'état actuel du personnage. L'eau sainte du §109 remonte Habileté et Endurance à des seuils dépendant des valeurs de départ sans jamais les diminuer. Les autres actions facultatives sont exclues de cette première tranche. Les jets des §2, §18, §47, §53, §55, §74, §82, §83, §91, §243 et §389 sont initiés par un bouton qui applique l'issue et la destination, sans relancer si le jet a déjà été effectué. Le §82 présente aussi la possibilité de ne pas tenter le vol. Les sept épreuves de Chance §2/18/74/82/83/91/389 soustraient un point après la comparaison du jet. Les liens hypertextes intégrés au récit sont également bloqués s'ils pointent vers une route cataloguée comme interdite selon l'état de la partie.

**Limite actuelle :** « une seule fois par partie » est une politique de protection provisoire. Certains événements narratifs peuvent être réexécutables lors d'une nouvelle visite ; déterminer les bonnes règles de répétition pour chaque paragraphe demande la revue complète du livre.


### Fuite et suites de combat

- La fuite est pilotée par les règles vérifiées des §8, §16 et §20. Le §16 exige deux assauts complets avant d'autoriser la fuite ; égalités comprises. Les autres la permettent durant l'affrontement.
- Pénalité de fuite : -2 Endurance, ou tentative volontaire de Chance donnant -1 si chanceux ou -3 si malchanceux ; la Chance est testée avant de dépenser un point. Une fuite mortelle n'ouvre pas le paragraphe de destination.
- Les boutons de fuite sans pénalité sont supprimés pour ces paragraphes ; les liens dans le texte passent par la même procédure contrôlée. Les commandes de navigation manuelle restent libres pour les usages avancés.
- §259 : victoire contre le Crocodile, +1 Habileté et +2 Chance automatisés. §350 : rencontre conditionnelle avec les Piranhas documentée, **non automatisée** (dépend des blessures infligées au Crocodile).
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
