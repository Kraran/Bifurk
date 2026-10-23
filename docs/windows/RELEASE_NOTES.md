# Bifurk 1.2.0 — La Forêt de la Malédiction

## Nouveautés depuis la 1.1.2

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

Le [bilan de clôture](../reviews/2026-10-23-foret-cloture.md) distingue l’audit,
les tests de branches, les contrôles Qt et la partie interne sans triche.
Cette mise à jour des sources ne produit ni exécutable ni archive Windows.

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
