# Partie jouée et corrections — 22 octobre 2026

## Conditions et résultat

La partie a été jouée sur les écrans Qt, par les boutons visibles, avec le PDF importé dans un espace de données isolé. Le pilote de rendu conserve les animations ; aucun jet aléatoire, caractéristique ou équipement n'a été remplacé. Aucun retour par Annuler, voyage manuel ou téléportation depuis la carte n'a été utilisé. Les résultats n'ont pas été rejoués après un échec.

Aldric a conservé son premier tirage complet : **Habileté 12, Endurance 21, Chance 12**, avec une Potion de Vigueur de deux doses. Un lancement technique préliminaire a été interrompu pendant la préparation du pilote, avant qu'une création complète et une aventure soient engagées.

Le parcours a couvert **143 paragraphes différents et 170 déplacements**, jusqu'au **Sorcier vaincu au §289**. État conservé : H10, E21, C11, 6 provisions, 55 pièces d'or et les deux doses de Vigueur. La version testée ne proposait alors aucune suite : il ne s'agit donc **pas d'une victoire finale**. Les contrôles effectués ensuite sur la version corrigée sont des validations de régression distinctes de cette partie.

Les décisions de parcours ont suivi les informations accessibles dans la lecture courante. Les sources et les autres branches ont ensuite été consultées pour analyser les défauts, sans modifier les décisions déjà prises. Le rendu et les interactions sont vérifiés sous Linux avec Qt sans écran ; l'écoute, les périphériques audio et les barres natives Windows restent à vérifier sur PC. Les captures et le journal contenant le livre restent privés et ne sont pas ajoutés au dépôt.

## Règles observées pendant la partie

- Les tests d'Habileté utilisent deux dés ; les tests de Chance comparent le jet à la valeur avant de retirer un point.
- La fosse retire un point d'Endurance. Les gains de Chance et les repas restent plafonnés.
- Une égalité en combat n'inflige aucun dégât. Une touche ordinaire retire deux points d'Endurance.
- Le bonus de force d'attaque contre les Farfadets ivres est bien ajouté à chaque assaut ; les adversaires successifs s'enchaînent avant la victoire finale.
- Deux tests de Chance offensifs réussis contre la Goule ont infligé quatre dégâts chacun et consommé un point de Chance chacun.
- La fuite du Minotaure est indisponible avant le troisième assaut. Les combats sans fuite annoncée gardent ce bouton grisé.
- Les repas des §§201, 90, 327 et 258 sont autorisés une seule fois et consomment une provision. Le repas partagé est indisponible quand les caractéristiques sont au maximum.
- Le choix unique du butin, les échanges contre un équipement et les restrictions liées à la possession des piquets et à la formule du Dragon ont été respectés.
- La carte conserve les adversaires vaincus. La prise de butin ne se renouvelle pas sur un simple rafraîchissement.

Les potions n'ont pas été consommées dans cette partie, et la paralysie de la Goule ne s'est pas produite : ces observations ne remplacent pas les tests automatisés correspondants. Une partie ne couvre pas tous les chemins des 400 paragraphes.

## Corrections livrées

| Constat | Correction |
| --- | --- |
| Victoire au §289 sans destination | Issue vers le §396 et choix de continuation après victoire. Il s'agit d'une **correction éditoriale**, documentée dans le catalogue : le duel alternatif du §142 indique cette issue, et les §§358/396 décrivent la même porte aux deux serrures. Le PDF ne contient pas littéralement ce renvoi au §289. |
| Fragment du §254 inséré au §253 dans le PDF lui-même | Déplacement dynamique du fragment extrait, seulement pour l'empreinte exacte de l'édition cataloguée, avec vérification des deux raccords. Aucun texte narratif ajouté au dépôt. Titre du §253 corrigé. |
| Bouton Combat actif sans rencontre ou avec le profil caché d'un ancien ennemi | Vérification commune dans le bouton et dans l'ouverture du dialogue. Les rencontres confirmées restent rattachées à leur lieu ; les préparations spéciales restent accessibles dans la fenêtre de combat. |
| Choix de potion après le bouton Commencer | Ordre nom → potion et explications → relance → validation finale. |
| Instructions d'épreuve au singulier pour deux dés | Libellé construit depuis le nombre de dés du catalogue. |
| « Avez vaincu » ou « avez eu de la chance » interprétés comme possessions | Pas d'heuristique d'inventaire en doublon des règles vérifiées ; filtrage des participes hors catalogue. |
| Choix tronqués ou répétant des effets déjà appliqués aux §§25, 49 et 147 | Actions nommées explicitement dans le catalogue. |
| Mention d'une autre clé encore inconnue dans la note du §258 | Mention retirée du texte affiché ; les règles de distinction des objets restent intactes. |
| « Or » collé au compteur de provisions | Espacement augmenté entre les ressources. |
| Renvois collés au mot suivant, absents de la carte | Reconnaissance de la frontière chiffre/lettre après un renvoi explicite, sans accepter les nombres de quatre chiffres. |
| Carte ouverte au début d'une très longue liste | Repère « Vous êtes ici » et défilement vers le lieu courant. Les renvois catalogués incluent l'issue rétablie du §289. |

## Validation

Suite complète : **385 tests, aucun échec imprévu**, un échec attendu déjà connu sur le cadrage de la couverture.

Les tests de régression couvrent le combat absent/présent, les rencontres confirmées et préparations spéciales, l'issue du Sorcier, le nombre de dés annoncé, l'ordre de création, les faux objets et les renvois collés. Le transfert du fragment est testé avec une fiction minimale, y compris son absence de double application.

Sur le PDF réel, les 400 paragraphes restent présents ; le fragment apparaît une fois au §254 et plus au §253. Une copie du checkpoint de la partie a été restaurée sans rejouer le duel ; la sortie du §289 vers le §396 est accessible, et le combat contre un Sorcier déjà vaincu est désactivé. Vérifications visuelles à 1280×720 et 930×650, avec les commandes dans leurs surfaces défilables. Aucune compilation Windows effectuée.

## Améliorations à prévoir

- Une carte graphique avec recherche et distinction des sorties connues, visitées et réellement empruntées serait plus utile dans le labyrinthe. Le repère courant livré ici réduit le problème sans refondre la carte.
- Les choix indisponibles pourraient rester visibles avec leur raison (par exemple, prix du passeur supérieur à la bourse), plutôt que disparaître.
- Certains passages, notamment le §8, contiennent un OCR dégradé dans le document. Une correction générale demanderait une comparaison systématique avec les pages, distincte de ce parcours.
- Les notes de règles affichées peuvent encore être allégées pour privilégier le récit ; leur réécriture doit éviter d'introduire de nouveaux indices ou de masquer une contrainte utile.
