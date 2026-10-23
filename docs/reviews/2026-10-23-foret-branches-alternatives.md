# Forêt : contrôle des branches alternatives

Ce lot complète les deux parcours gagnants du marteau par neuf tests du
lecteur Qt. Les dés sont imposés pour explorer les issues, sans mesurer leurs
probabilités. Aucun objet de quête n’est réattribué lors d’un retour.

## Matrices contrôlées

| Famille | Cas vérifiés |
| --- | --- |
| 19 paires de routes d’achats magiques | Absence, ajout manuel sans charge, achat utilisable, objet épuisé : 76 configurations |
| 7 épreuves à embranchements | Réussite et échec, coûts, blessures immédiates, annulation et rechargement : 14 configurations |
| 11 fuites de combat | Sans Chance, Chance réussie, Chance ratée, blessure létale : 44 configurations |
| Porte du §73 | Les deux issues, un seul jet et aucun point de Chance dépensé |
| Fléchettes du §309 | Les quatre combinaisons de résultats, deux jets et deux points de Chance |
| Bras de fer du §266 | Échec à chacun des trois jets ou réussite complète ; arrêt au premier échec, une seule mise perdue |
| Fièvre du §259 | Réussite, échec survivant avec l’excision du §19, échec létal |
| Convalescence du §304 | Cinq rations disponibles ou famine |

La fuite de l’Homme-Singe comprend aussi les trois points de la chute.
La Créature des Rochers ne permet la fuite qu’après les trois assauts requis.
Une fuite ne marque pas l’adversaire comme tué. Les blessures létales
n’entraînent aucun déplacement vers une destination de survivant.

## Chaînes alternatives

- Coffre : échec au levage, sauvegarde, nouvelle tentative réussie, explosion
  létale de l’œuf, puis annulation de l’explosion.
- Quête incomplète : village → nouvelle tentative → embuscade → Yaztromo,
  sans nouveau héros, sans restitution de l’or et sans recharge des bottes.
  Un second retour raté tue ; l’annulation restaure la tentative en cours.
- Démon vaincu → couronne → transformation ; le choix terminal est annulable.
- Attaque de Yaztromo → persistance → transformation en grenouille.

Les matrices utilisent le catalogue du livre pour les routes du lecteur. Les
sauvegardes et les transactions sont celles de l’application. Les tests
ponctuels existants complètent ces scénarios pour les autres mécaniques
(paiements, lanterne, piège, équipement, soins et gaz).

## Portée

Un contrôle du graphe du catalogue retrouve les 400 paragraphes depuis le §1 :
aucun passage n’est isolé structurellement. Ce contrôle ignore les conditions
de jeu ; il ne démontre pas qu’un même héros peut emprunter toutes les routes.

Ce contrôle vise les branches des mécaniques intégrées. Il ne certifie pas
l’automatisation de toutes les conditions encore documentaires parmi les
641 renvois, ni la présentation visuelle Windows. Les illustrations ne sont
pas modifiées par ce lot. Aucun exécutable n’est compilé.

Validation locale : 154 tests de la Forêt réussis ; suite globale de 609 tests,
608 réussites et un test ignoré faute de PyInstaller. L’audit du PDF vérifie
les 400 paragraphes et 641 renvois sans blocage. L’arbre testé comprend les
corrections d’audit locales encore séparées de cette PR.
