# Bifurk 1.2.1 — Cuir, or et carnet de voyage

## Nouveautés depuis la 1.2.0

- Le grimoire change de reliure : page de parchemin au cadre de bronze, cartouche
  « § N » et lettrine enluminée, choix en plaques numérotées activables par les
  touches 1 à 9. Le bandeau de cuir et d’or réunit Annuler, Rétablir, Règles,
  Carte, Grimoires et le menu ⚙ Réglages (Ambiance sonore, Plein écran, Journal,
  À propos, Quitter le jeu).
- Fiche d’aventurier en cuir bordeaux : les boucliers d’Habileté, d’Endurance et
  de Chance se remplissent comme des jauges et pulsent doucement à 2 ou moins.
  La sacoche devient une grille où chaque objet connu des deux aventures a son
  icône et où les exemplaires identiques sont regroupés. Sur une petite fenêtre,
  la fiche se range en tiroir.
- Carnet de notes et marque-pages (touches N et B), enregistrés avec la partie.
  Les renvois §N deviennent cliquables dès la frappe ; un clic sur un marque-page
  y conduit, la plume ou F2 le renomme. Voyager par le carnet compte comme une
  intervention et marque la partie comme assistée.
- Cadre de messages qui détaille chaque événement : dés, score, réussite ou échec,
  gains et pertes. Les boutons d’événements disent ce qu’ils font, les jets de dés
  restent affichés, et une alerte signale une Endurance faible quand un soin est possible.
- Les choix indisponibles restent visibles mais grisés, avec leur raison dans
  l’infobulle, dans les deux aventures.
- Menu Soins expliquant chaque refus. Un seul repas par paragraphe : il faut
  avancer dans l’aventure pour reprendre un repas.
- Combat : « Cibler » n’apparaît qu’avec au moins deux adversaires encore debout.
- Rien n’est révélé avant son heure : boutique de Yaztromo aux descriptions
  neutres, objets durables achetables une seule fois et panier détaillé ; titres,
  libellés et infobulles des deux aventures purgés de ce qui trahissait la suite.
- Barre de chargement de parchemin et d’or à l’ouverture d’un grimoire ou d’une
  sauvegarde : l’interface ne se fige plus pendant la lecture du livre.
- Ambiance sonore : case « Garder la musique en fond pendant la partie » et dossier
  `musique_perso` pour jouer vos propres morceaux en ordre aléatoire avec
  « Jouer ma musique ». Les deux options sont décochées par défaut.

## Corrections

- Sorcier de la Montagne de Feu : les choix ne disparaissent plus après une
  victoire, le message « Aucune destination explicite » n’apparaît plus à tort,
  repas et ressources requises vérifiés sur le livre.
- Fermer la fenêtre pendant un chargement ne modifie plus ni la partie ni les
  sauvegardes ; le menu de démarrage résiste lui aussi à la fermeture.
- Copier un passage rend la vraie lettre de la lettrine.
- Plus de petite fenêtre « Supprimer » au démarrage, ni à l’ouverture de Charger
  ou Sauvegarder.

## Validation

850 tests automatisés réussis (12 ignorés) en mode offscreen, hors Windows.
Le ZIP Windows doit encore être extrait et vérifié avant publication : icône,
version 1.2.1 dans À propos, sons, combat, sauvegarde et dossier `musique_perso`.

## Installer ou mettre à jour

Distribution portable Windows x64 : extraire le ZIP complet puis lancer Bifurk.exe.
Conserver une copie du dossier `donnees`, et de `musique_perso` si vous y avez
déposé des morceaux, avant une mise à jour. Le format actuel des sauvegardes reste
identique ; les nouveaux champs (carnet, marque-pages, repas) sont facultatifs.
Aucun livre ni aucune sauvegarde personnelle n’est inclus : importer son propre PDF.

---

# Bifurk 1.2.0 — La Forêt de la Malédiction

## Nouveautés depuis la 1.1.2

- Suivi des parties avec badge et journal : les interventions manuelles et
  Annuler/Rétablir demandent confirmation et laissent une marque « Partie assistée »
  persistante dans les sauvegardes. Les sauvegardes antérieures au suivi portent
  la mention « Historique non vérifié ».

- Annonce sonore propre à chaque livre à l’affichage de sa couverture et au
  chargement réussi d’une sauvegarde ; fichiers fournis harmonisés pour le jeu.

- Bouton « Quitter le jeu » avec confirmation et arrêt des fenêtres et de l’audio.

- La Forêt de la Malédiction devient une aventure complète : mécaniques spéciales,
  boutique, équipements, combats, épreuves, fins et cas limites validés.
- Illustrations de la Forêt et fond dédié après la couverture.
- Repas ordinaires de la Forêt disponibles à tout passage hors combat, avec une
  ration pour 4 points d’Endurance et respect des repas spéciaux aux §§304 et 328.
- Carte d’exploration en deux dimensions guidée par les directions des choix,
  commune aux deux aventures, avec placement compact sans direction explicite.
- Corrections des renvois, des coquilles du texte extrait et de l’avertissement
  QFont au démarrage ; améliorations de l’affichage sur les petites fenêtres.
- Sauvegardes conservées au format actuel ; importer son propre PDF de l’édition reconnue.

Le [bilan de clôture](https://github.com/Kraran/Bifurk/blob/v1.2.0/docs/reviews/2026-10-23-foret-cloture.md) distingue l’audit,
les tests de branches, les contrôles Qt et la partie interne sans triche.
Distribution portable Windows x64 : extraire le ZIP complet puis lancer Bifurk.exe.
Conserver une copie du dossier donnees avant une mise à jour.

---

# Bifurk 1.1.2 — Le grimoire prend vie

## Nouveautés depuis la 1.1.1

- Carte d’exploration graphique avec les lieux visités, les déplacements, la
  position actuelle et l’état des monstres. Recherche, zoom, déplacement de la
  carte et boutons « Ma position », « Lieu précédent » et « Tout voir ».
- Animations des lancers libres **3d6** et **1d20**, sur le même plateau que les
  dés des événements et des combats. Le D20 possède vingt faces numérotées.
- Cartouches animés pour les gains et pertes d’Habileté, d’Endurance et de Chance
  du héros, et pour les caractéristiques des monstres. Les ennemis vaincus
  passent en gris ; les combats successifs ne produisent pas de faux soins.
- Fenêtres de sauvegarde, d’import, d’ambiance, de règles et de confirmation
  harmonisées avec le cuir, le parchemin et les blasons du grimoire.
- Illustration de fond fixe pour les paragraphes sans image après l’introduction.

## Corrections et optimisation

- Boutons Fuir synchronisés entre lecteur et combat, avec explication des
  restrictions. Seuils d’assauts et nouvelle tentative face au Vampire vérifiés.
- Suppression des sondages d’encodeurs vidéo Windows inutiles à la musique.
- Cadrage de couverture corrigé : son test de régression réussit normalement.
- Inventaire, sélection des armes et liste des adversaires actualisés sans
  reconstruction inutile, pour préserver sélection et défilement.
- Fenêtres temporaires libérées après fermeture ; les retouches différées
  sont annulées avec leur fenêtre pour éviter un rappel sur un objet détruit.
- Contrôle des nouvelles ressources avant création du ZIP et présence de ces
  notes dans l’archive sous `NOUVEAUTES.md`.
- Dépendance PyMuPDF alignée sur les imports modernes ; outils et tests
  utilisent également le nom `pymupdf` plutôt que l’ancienne entrée dépréciée.

## Installer ou mettre à jour

Distribution portable pour Windows 10/11 x64 : télécharger le ZIP, l’extraire
entièrement dans un dossier personnel puis lancer `Bifurk.exe`. Python n’est pas
nécessaire. `_internal` doit rester à côté de l’exécutable.

Fermer le jeu et conserver une copie du dossier `donnees` avant une mise à jour,
puis le recopier dans le dossier de la nouvelle version. Le format actuel des
sauvegardes reste identique. Aucun livre ni aucune sauvegarde personnelle n’est
inclus : importer son propre PDF.

Le ZIP est accompagné de son empreinte SHA-256 et des informations sur les
composants tiers. L’exécutable n’est pas signé numériquement.
