# La Forêt de la Malédiction — clôture en Bifurk 1.2.0

Le 23 octobre 2026, l’intégration fonctionnelle de l’édition reconnue par son
empreinte PDF est déclarée complète. Le manifeste passe de `preview` à `ready` ;
la bibliothèque affiche « Aventure complète » et les avis de préparation sont retirés.

## Validation réalisée

- Audit des 400 paragraphes et 641 renvois : 222 paragraphes disposent d’un point
  d’entrée dans le moteur et 178 sont narratifs. Les huit constats ont été corrigés
  ou documentés : [audit détaillé](2026-10-23-foret-audit-final.md).
- Branches alternatives, échecs, fuites, charges, équipements et fins :
  [contrôles ciblés](2026-10-23-foret-branches-alternatives.md).
- Deux variantes de quête du marteau : [parcours contrôlés](2026-10-23-foret-parcours-marteau.md).
- Contrôles natifs Qt Windows, dimensions de fenêtre, souris et échelles Qt :
  [interface](2026-10-23-foret-validation-interface.md) et
  [souris et zoom](2026-10-23-foret-souris-zoom.md).
- Partie interne sans triche : victoire au §400 après 63 lieux et 62 déplacements,
  sans tirages imposés, relance des caractéristiques ou annulation des échecs.
  Sauvegarde et rechargement vérifiés. Les observations privées restent dans
  `audit-output/run-interne-libre` et ne sont pas nécessaires au fonctionnement.
- Carte 2D et corrections typographiques intégrées par les PR #84 et #85.
  Les achats clavier sont confirmés fonctionnels par l’utilisateur ; la justification
  du texte a été examinée puis abandonnée. L’alignement reste inchangé.

## Règles de projet et portée

Les arbitrages validés restent documentés dans le catalogue : épée du §70 avec
bonus équipé au-delà du total initial, adversaires successifs aux §§29 et 317,
et sorties de secours adaptées aux sept cas indéfinis. Une charge magique n’est
pas rétablie automatiquement lorsque le livre ne précise pas sa récupération.

Le statut complet ne signifie pas que toutes les combinaisons ont été jouées
manuellement. La partie libre a été pilotée en interne via Qt ; les configurations
physiques Windows et tous les dispositifs audio n’ont pas été testés exhaustivement.
Les analyses documentaires restent séparées des règles exécutables du moteur.

Bifurk passe en 1.2.0, datée du 23 octobre 2026. Le format des sauvegardes ne
change pas. Aucune compilation ni publication d’un exécutable n’est effectuée.

## Contrôles de clôture

Les 110 tests ciblés (identité, registre, analyse, audit d’intégration, présentation
de la Forêt et contrat de distribution) donnent 109 réussites et un test ignoré.
L’audit du PDF exact ne relève aucun écart de renvoi ni de point d’entrée.
La fixture de présentation ferme explicitement le journal audio avant le nettoyage
des fichiers temporaires Windows ; les assertions de jeu ne sont pas modifiées.
