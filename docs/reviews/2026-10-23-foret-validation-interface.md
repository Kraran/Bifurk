# Forêt : validation du rendu Windows et des parcours réels

Contrôle effectué le 23 octobre 2026 avec le PDF exact reconnu par le module,
le moteur Qt `windows` et les polices de Windows. Les fenêtres sont rendues sans
être affichées sur le bureau ; le contrôle ne simule pas de clics utilisateur.
Aucun exécutable n’a été compilé.

## Correction trouvée

À 930 × 650, Qt réservait 112 pixels à chacun des trois champs de caractéristiques.
La largeur minimale du panneau atteignait 398 pixels pour une zone visible de
353 pixels : une barre horizontale apparaissait et la colonne Chance débordait.

Les champs peuvent désormais se réduire avec leurs colonnes, et les marges
latérales de la grille passent de 8 à 4 pixels. Les valeurs, les barres et leurs
libellés restent visibles. Le test de la fenêtre minimale est exécuté avec le
moteur natif Windows pour la Forêt et le Sorcier, qui partagent ce panneau.

## Écrans contrôlés

Dix-neuf captures privées couvrent :

- Couverture, création et départ, carte du prologue.
- Illustration de l’Œil d’Ambre et agrandissement.
- Épreuve du Bandeau à 930 × 650, 1280 × 800 et 1600 × 900 ; accès aux actions
  par défilement à la taille minimale et résultat de l’épreuve.
- Lingot et dialogue de choix de l’objet abandonné ; couronne avant/après prise.
- Sortie de secours de la fosse et arrivée à sa destination.
- Coffre après examen du tonneau : seul le départ est encore disponible.
- Victoire réelle à 1280 × 800 et 930 × 650, avec les commandes de jeu closes.

Les contrôles géométriques vérifient l’absence de défilement horizontal du panneau
à ces trois tailles. Les captures, textes et images restent dans `audit-output`,
ignoré par Git. Aucun pixel extrait du PDF n’est publié dans ce compte rendu.

## Parcours avec le PDF réel

Deux parcours partent de la création d’un héros légal aux maxima de tirage, puis
suivent les achats, renvois, combats et commandes de l’application : 59 passages
pour la variante Eau Bénite, 60 pour la variante combat contre la Goule. Les dés
sont imposés ; ces contrôles ne mesurent pas la difficulté ou la probabilité de gagner.

Dans chaque parcours, la partie est sauvegardée et rechargée après les §§232,
173 et 279. Le rechargement relit le PDF réel, sans remplacer son texte par un
catalogue synthétique. Les deux parties atteignent la remise du marteau au §400
et la clôture des commandes de jeu.

Les données de ces parties sont isolées dans un répertoire temporaire. Le rapport
compare les empreintes du PDF et de tous les fichiers existants de `donnees`
avant et après le contrôle. Aucun avertissement QFont n’a été relevé avec le
moteur natif Windows. Le pilote `offscreen` peut produire des avertissements de
répertoire de polices et des glyphes manquants ; il ne sert pas de preuve du rendu natif.

## Reproduction

Depuis le dépôt, avec le PDF privé exact disponible :

```powershell
.\.venv\Scripts\python.exe tools/audit_foret_ui.py --platform windows
```

Le rapport structuré et les captures sont écrits dans
`audit-output/foret-ui-validation`. Le script refuse un PDF d’une autre édition,
conserve les sauvegardes du joueur et coupe le son de sa session temporaire.
Il utilise la fenêtre et les dialogues de l’application sans lancer de compilation.

## Portée restante

Ce contrôle valide les écrans recensés et deux parcours déterministes avec le
PDF réel. Il ne remplace pas une partie libre pilotée à la souris, ni la vérification
sur d’autres résolutions, niveaux de zoom Windows ou configurations matérielles.
Le statut de préparation n’est pas changé par ce lot.
## Résultats automatisés du lot

- Suite générale : 630 tests exécutés en 173 secondes, 629 réussis et un ignoré
  faute de PyInstaller. Aucun compilateur n’a été lancé.
- Test de fenêtre minimale exécuté aussi avec `QT_QPA_PLATFORM=windows` : réussi
  pour les deux grimoires.
- Audit natif : 19 captures, deux parcours gagnants, aucun avertissement QFont,
  empreintes des données existantes et du PDF inchangées.

La suite locale comprend les correctifs d’audit préexistants du journal audio et
de trois fichiers de tests généraux ; ces changements restent séparés de ce lot.

## Complément souris et zoom

Le [contrôle complémentaire](2026-10-23-foret-souris-zoom.md) ajoute les événements
souris Qt, l’annulation/rétablissement et les échelles Qt 125 %, 150 % et 200 %.
Les limites de ce rapport initial sont ainsi précisées, sans prétendre simuler
une partie libre sur le bureau.
