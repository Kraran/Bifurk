# Base d'événements — édition 1982

Cette base ne contient pas le texte du livre. Elle associe les numéros de paragraphes à des **métadonnées de règles** lues dans le PDF fourni. Son SHA-256 garantit qu'elle ne s'applique pas par erreur à une autre édition.

## État de la revue

- 400 paragraphes numérotés retrouvés dans le PDF.
- 49 paragraphes vérifiés ponctuellement ; 351 à étudier et valider individuellement.
- 25 paragraphes avec effets obligatoires automatisés : 11, 25, 28, 40, 49, 51, 56, 75, 109, 110, 145, 147, 153, 185, 202, 203, 247, 259, 264, 342, 343, 344, 368, 388 et 390.
- 23 autres paragraphes classés comme conditionnels, jets de dés ou combats particuliers. Onze épreuves sont désormais exécutables : 2, 18, 47, 53, 55, 74, 82 (facultatif), 83, 91, 243 et 389. Au §91, un test de Chance est suivi, uniquement en cas de réussite, d'un second lancer de deux dés déterminant les pièces d'or gagnées. Les autres restent documentés sans application automatique.
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

## Suite

Examiner chaque paragraphe restant, notamment les combats en série, les tests de Chance, les inventaires conditionnels, les objets consommables, les pertes et gains de maximum de caractéristiques et les issues de combat. Écrire un scénario de test par événement vérifié avant de l'activer. Ne pas déclarer la base exhaustive avant que les 400 paragraphes soient qualifiés.
