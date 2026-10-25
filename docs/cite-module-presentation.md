# La Cité des Voleurs — module et présentation

Cette première phase ajoute l'identité du troisième livre et sa consultation. Elle
ne présente pas comme jouables des événements qui n'ont pas encore été vérifiés.

## Édition reconnue

- Module : `cite_voleurs_1983`, adaptateur `cite-1983`.
- Titre : **La Cité des Voleurs**.
- PDF privé fourni : 177 pages, 400 paragraphes retrouvés par l'extracteur.
- SHA-256 : `686607e4c9a86c72d39d3a101f2681df83d71ecba6d858a2f8e062d2f5357616`.
- Couverture : page physique 1 ; cadrage contrôlé dans les limites de la page.
- Règles : pages physiques 4–13.
- Prologue « Les terribles messagers de Zanbar Bone » : pages physiques 14–18.

La couverture, les règles et le prologue sont rendus depuis le PDF importé par
le joueur. Aucun PDF, texte narratif ou pixel extrait du livre n'est distribué.
Le décor neutre du thème est utilisé en attendant le décor propre à la Cité ;
l'annonce sonore du livre et ce décor sont livrés en phase 7.

## Parcours dans Bifurk

La bibliothèque **Grimoires…** affiche la couverture et l'état « En préparation ».
Sur la couverture, le joueur retrouve la création commune, l'avis de préparation
et le bouton **Lire le prologue**. Le bouton permanent **Règles** lit les pages
du module courant.

Le profil de départ ajoute les **30 pièces d'or** au matériel commun (épée, armure
de cuir, lanterne, 10 repas et la potion choisie). Le sac à dos est représenté par
la sacoche de la fiche, sans emplacement séparé ; les bijoux trouvés iront dans
l'inventaire. Un repas peut être pris à tout moment hors combat (règles, page
physique 9), un seul par passage tant que le héros ne s'est pas déplacé.

## État des règles de l'aventure

`catalogues/evenements_cite_1983.json` ne contient encore **aucune entrée** : les
400 paragraphes sont en attente de revue. L'adaptateur hérite du socle Défis
Fantastiques mais pas des contrôleurs du Sorcier ou de la Forêt, dont les numéros
de paragraphes désignent d'autres scènes. Les renvois textuels permettent la
consultation et la sauvegarde de la position, sans appliquer de condition ni
d'effet ; les combats restent fermés. Les événements seront intégrés en phase 3,
par tranches de 100 paragraphes.

## Fichiers et validation

- `catalogues/modules/cite_voleurs_1983.json` : manifeste, pages et ressources initiales.
- `catalogues/cite_voleurs_1983.json` : association de couverture.
- `catalogues/evenements_cite_1983.json` : squelette de revue des 400 paragraphes.
- `grimoire_modules/cite/controller.py` : navigation de consultation sans automatismes.
- `tests/test_cite_presentation.py` : reconnaissance, couverture, prologue, profil,
  repas, consultation sans effets, sauvegarde et changement de module.

Les scénarios d'interface utilisent des PDF synthétiques. Un contrôle conditionnel
reconnaît également le PDF privé s'il est présent et vérifie son cadrage. Le
contrôle de l'archive Windows exige les trois ressources de catalogue du module.
