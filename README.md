# Bifurk 1.1.2 — Français et mode portable

## Interface Le Grimoire

Page ivoire, bibliothèque illustrée, choix sous forme de cartes et sacoche avec emblèmes.
Les illustrations du livre sont affichées à gauche du récit et peuvent être masquées ou agrandies.
La sacoche présente les objets en lignes compactes ; **Gérer les objets…** déplie les commandes d’ajout et de retrait.
La sacoche reste dans le panneau latéral. Les combats possèdent leur fenêtre ;
les soins et les outils ponctuels sont accessibles par **Soins** et **Actions…**.

[Captures et instructions de test](docs/design/grimoire.md).

Le démarrage propose une nouvelle partie ou le chargement d’un des cinq emplacements.
Le titre **Bifurk — Chroniques d’aventure**, icône comprise, ouvre la fenêtre **À propos** :
version, auteur, présentation et liens GitHub.
Le bouton **Ambiance** permet de couper les effets sonores et de choisir le thème.
[Reprise, sons et préparation de thèmes](docs/themes-et-ambiance.md).

Hors combat, les jets de **1d6, 2d6, 3d6 et 1d20** ouvrent un plateau de dés en 3D animés,
y compris pendant la création de l'aventurier. Les faces et leur
total restent visibles jusqu'à **Continuer**. **Passer l'animation** révèle
immédiatement le résultat déjà tiré. [Présentation et contrôles](docs/design/des-animes.md).

Le bouton **Combattre / Reprendre** ouvre une fenêtre dédiée : adversaires
et dés rouges automatiques à gauche, aventurier et dés blancs à lancer à droite,
chronique des coups et décisions de Chance au centre. La fiche du héros se met
à jour pendant le combat. **Fuir** et **Soins** restent en bas, grisés lorsque
les règles les interdisent ; le journal défile sans déborder de son cadre.
[Présentation des combats](docs/design/combat-popup.md).

La **Carte d’exploration** relie les lieux visités sur un graphe zoomable :
position actuelle, recherche, adversaires vaincus ou fuis et accès rapide au lieu
précédent. [Présentation et commandes](docs/design/carte-exploration.md).

Les [fenêtres secondaires](docs/design/fenetres-secondaires.md) partagent les
bandeaux et les couleurs du grimoire, des sauvegardes au sélecteur de PDF.

Les [variations des caractéristiques](docs/design/variations-caracteristiques.md)
s’animent près des valeurs sur la feuille et dans le combat, sans ralentir la partie.

## Démarrage

```bash
pip install -r requirements.txt
python main.py
```

## Compiler et distribuer sous Windows

Double-cliquez sur **`BUILD_EXE.bat`** depuis une copie du dépôt, avec Python
Windows 64 bits installé (3.13 recommandé). Le script prépare son environnement
`.venv-build`, installe les dépendances et produit :

- `dist/Bifurk/Bifurk.exe`, avec l'icône existante et sans console ;
- `dist/Bifurk-v1.1.2-windows-x64.zip`, contenant le programme et ses dépendances ;
- l'empreinte `.zip.sha256` correspondante.

Extrayez le ZIP dans un autre dossier pour le tester. Il faut distribuer **tout
le ZIP**, pas l'exécutable seul ; Python n'est pas nécessaire chez le joueur.
Après validation, `PUBLISH_RELEASE.bat` peut joindre l'archive à une **release
GitHub brouillon** (GitHub CLI requis). La publication publique reste manuelle.

Voir [Compiler, tester et publier sous Windows](docs/windows/compilation.md)
pour le parcours complet, les mises à jour et les composants distribués.

## Dossiers portables

Bifurk crée à côté de `main.py` (ou de l'exécutable Windows empaqueté) :

```
Bifurk/
├── main.py
├── assets/
├── catalogues/
└── donnees/
    ├── grimoires/       # copies locales des PDF importés
    ├── sauvegardes/     # sauvegardes manuelles et autosave.json
    └── parametres/      # préférences et diagnostic audio
```

- Les sélecteurs Qt utilisent les libellés français ; les catalogues `qtbase_fr.qm` / `qt_fr.qm` sont chargés automatiquement depuis `translations/` ou les traductions de Qt si elles sont installées. Les commandes courantes et leurs infobulles disposent également d'une traduction de secours.
- Les PDF choisis en dehors de Bifurk sont **copiés** dans `donnees/grimoires/`. Le fichier d'origine n'est pas modifié.
- Le démarrage propose Nouvelle partie ou le chargement d’un des cinq emplacements. Chaque emplacement affiche l’aventurier, la date et ses trois caractéristiques ; son remplacement ou sa suppression demande confirmation.
- Les sauvegardes sont dans `donnees/sauvegardes/`. Seul le format actuel est accepté. Les références PDF restent relatives au dossier Bifurk et pointent vers les grimoires importés.
- Les répertoires de données sont créés au démarrage. Bifurk doit donc être installé dans un dossier **accessible en écriture**, par exemple une clé USB ou un dossier personnel, et non dans `Program Files` protégé.
- Les dépendances Python restent nécessaires en mode source. La distribution compilée les inclut dans `_internal` et fonctionne sans installation de Python.

## Limites

Les dialogues Qt peuvent contenir des libellés propres à une version de Qt qui ne sont traduits intégralement que si les fichiers `.qm` correspondants sont présents. Les traductions de secours couvrent les libellés usuels du sélecteur, mais leur exhaustivité visuelle reste à vérifier sur Windows.

Le mode portable concerne les **données de Bifurk**. Windows, Python et Qt peuvent créer leurs propres caches ou fichiers temporaires hors du dossier de l'application ; une garantie absolue « aucune écriture extérieure par aucun composant » nécessite une validation spécifique de l'exécutable empaqueté.

## Tests de développement sur Windows

Depuis le dossier du projet, dans PowerShell (créer `.venv` seulement s’il n’existe pas) :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

Le PDF privé de référence, placé à la racine du projet, active les tests d’extraction et de rendu. Sans ce fichier, ces contrôles sont ignorés. Le cadrage de la couverture est également vérifié. Le PDF ne doit pas être ajouté à Git.

Pour tester visuellement après les tests :

```powershell
.\.venv\Scripts\python.exe main.py
```

Le catalogue couvre les 400 paragraphes de l’édition vérifiée. La logique du dernier lot et les scénarios de validation sont détaillés dans [la documentation des événements](catalogues/README_evenements.md).

## Comprendre et maintenir le code

Le [guide de maintenance](docs/maintenance.md) présente les modules, le cycle d'une
partie, les règles du catalogue, les sauvegardes, le rendu Qt et le flux audio.
Les modules et fonctions du code applicatif sont documentés en français ; les
suites de tests et outils précisent également leur rôle et leurs contraintes.

### Potion de départ

À la création, choisissez Adresse, Vigueur ou Bonne Fortune dans la liste (Vigueur est présélectionnée).
Le choix est conservé lors des relances. Une fois la partie commencée, la fiole ne peut plus être changée :
elle contient deux doses, affichées sur la feuille et dans Soins, utilisables également en combat.
Adresse et Vigueur restaurent leur caractéristique initiale ; chaque dose de Bonne Fortune augmente
la Chance initiale de 1, puis restaure la Chance à ce nouveau maximum. Les doses sont conservées
dans les sauvegardes. Une dose sans effet n'est pas consommée.

### Musique d’accueil

`FantasyFair.m4a`, fourni par l’utilisateur, accompagne en boucle l’accueil, la
création du personnage et le choix d’une sauvegarde. À l’entrée dans l’aventure,
le volume diminue sur dix secondes puis la musique s’arrête. Le curseur rétro
**Musique d’accueil** dans Ambiance règle et mémorise le volume indépendamment des effets et
de l’ambiance de caverne (0 % = muet). Par défaut, 70 % du niveau précédent est utilisé.
Le M4A audio est diffusé en continu par Qt Multimedia
et inclus automatiquement dans la distribution Windows avec les autres assets.
La pochette intégrée a été retirée sans réencoder ni modifier le son, afin de ne pas
solliciter les décodeurs vidéo. La licence des packs CC0 d’effets sonores ne s’applique pas à ce fichier musical.

Le [compte rendu de la partie et des corrections du 22 octobre 2026](docs/reviews/2026-10-22-partie-et-corrections.md) détaille les règles observées, les corrections éditoriales et les limites de validation.

### Modules de grimoires

Le Sorcier dispose de son manifeste et de son contrôleur de règles. La reconnaissance
des éditions, les bases et les pages de règles sont sélectionnées par module.
Voir [le guide d’intégration](docs/modules-grimoires.md) pour préparer un autre livre.

Les règles communes (création, Chance, soins, combats et fuite) sont regroupées
dans un [socle Défis Fantastiques](docs/socle-defis-fantastiques.md),
réutilisable par les prochains modules sans les exceptions du Sorcier.

### La Forêt de la Malédiction — présentation

Le deuxième module propose sa couverture, son prologue et ses règles. Le bouton
**Grimoires…** permet de choisir parmi les livres importés ou d'importer un PDF.
La Forêt est **en préparation** : consultation et sauvegarde sont disponibles,
mais ses événements et combats seront intégrés après leur revue.
Voir [le détail de cette étape](docs/foret-module-presentation.md).

La revue des **400 paragraphes de la Forêt** est terminée : titres, choix et mécaniques sont catalogués. Les événements restent à programmer ; deux anomalies du PDF (§§186 et 267) nécessitent confirmation. Voir [le bilan et les contrôles](docs/reviews/foret-400-paragraphes.md).
