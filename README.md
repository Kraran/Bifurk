# Bifurk 1.3.0 — La Cité des Voleurs

## Interface Le Grimoire

Bifurk est un lecteur-compagnon pour livres-jeux : il lit **votre propre PDF**
du livre, suit l’aventurier et applique les règles cataloguées. Aucun livre
n’est fourni avec le programme ; le bouton **Grimoires…** permet d’en ajouter un.

Page ivoire, bibliothèque illustrée, choix sous forme de cartes et fiche
d’aventurier en cuir. Les illustrations du livre sont affichées à gauche du
récit et peuvent être masquées ou agrandies ; **A−** / **A+** règlent la taille du texte.

[Captures et instructions de test](docs/design/grimoire.md).

### Barre du haut

- **↶ Annuler** et **↷ Rétablir** parcourent l’historique des actions.
- **📖 Règles** (F1) affiche les pages de règles du PDF ouvert.
- **🗺 Carte d’exploration** ouvre la carte des passages visités.
- **✦ Grimoires…** choisit un grimoire déjà importé ou ajoute un livre PDF.
- **⚙ Réglages** regroupe **Ambiance sonore…**, **Plein écran** (F11),
  **Mode lecture** (F10), **Journal de la partie…**, **À propos de Bifurk**
  et **Quitter le jeu…**, qui demande confirmation puis ferme les fenêtres et
  arrête l’audio. Sauvegardez votre progression avant de quitter.

Le titre **Bifurk — Chroniques d’aventure**, icône comprise, ouvre aussi la
fenêtre **À propos** : version, auteur, présentation et liens GitHub.

### Fiche de l’aventurier

- Les caractéristiques sont présentées sur des écus-jauges ; à **2 ou moins**,
  l’écu pulse lentement en rouge jusqu’à ce que la valeur remonte. Les
  [variations des caractéristiques](docs/design/variations-caracteristiques.md)
  s’animent près des valeurs sur la feuille et dans le combat, sans ralentir la partie.
- **Bourse & Vivres** affiche l’Or, les Provisions et la potion de départ avec
  ses doses. Ces valeurs sont gérées par le livre ; **Actions… → Corriger
  Provisions et Or** les déverrouille pour une correction manuelle.
- **Sacoche & Trésors** range les objets dans une grille de cases avec icônes
  et badges de quantité ; l’en-tête replie ou déplie la sacoche. Un double-clic
  sur une arme l’équipe, un clic droit retire un objet, et **Gérer les objets…**
  déplie les commandes d’ajout et de retrait.
- **⚔ Combattre ⚔** n’apparaît que lorsqu’un combat est disponible dans le paragraphe.
- En bas, les sceaux **Soins** (manger une Provision ou boire la potion),
  **Actions…** (dés libres 1d6/2d6/3d6/1d20, aller à un paragraphe, prologue,
  corrections), **Carnet**, **Sauvegarder** et **Charger**.
- Un seul repas est possible par paragraphe : **Soins** l’indique en grisant
  « Prendre un repas — déjà mangé ici » jusqu’au prochain déplacement.
- Dans une fenêtre étroite, la fiche se replie en bande verticale et s’ouvre en
  tiroir (clic sur la bande ou **Tab**).

Un badge indique **Partie suivie**, **Partie assistée** ou **Historique non vérifié**.
Les voyages manuels, éditions de valeurs ou d’inventaire et commandes Annuler /
Rétablir demandent confirmation avant de marquer la partie comme assistée.
La marque reste dans les sauvegardes et ne s’annule pas avec l’historique.
Cliquer sur le badge affiche le journal ; les anciennes sauvegardes ont un
historique non vérifié. Les choix du récit et les effets normaux restent neutres.
Ce suivi ne protège pas contre la modification externe des fichiers de sauvegarde.

### Récit, choix et messages

- Les choix sont des cartes numérotées : les touches **1** à **9** activent le
  choix correspondant. Un choix indisponible reste visible mais grisé ; dans
  Le Sorcier de la Montagne de Feu, l’infobulle précise ce qui manque.
- Dans la page, un cadre de messages rappelle le dernier résultat de règle
  (jets, pertes, gains) ; il est vidé au changement de paragraphe.
- Lorsque l’Endurance tombe à 4 ou moins et qu’un soin est utilisable, une
  alerte apparaît dans la page de lecture avec un bouton **✚ Soins**, et le sceau
  **Soins** est mis en avant.
- Les jets de **1d6, 2d6, 3d6 et 1d20** ouvrent un plateau de dés en 3D animés,
  y compris pendant la création de l’aventurier. Les faces et leur total restent
  visibles jusqu’à **Continuer** ; **Passer l’animation** révèle immédiatement le
  résultat déjà tiré. [Présentation et contrôles](docs/design/des-animes.md).
- À l’ouverture d’un livre ou d’une sauvegarde, une barre de progression
  (« Ouverture du grimoire… », « Chargement de la sauvegarde… ») n’apparaît que
  si la lecture dure plus d’un instant ; l’interface reste réactive.

### Combats

**⚔ Combattre ⚔** ouvre une fenêtre dédiée, sans réinitialiser l’adversaire
préparé par le livre : adversaires et dés rouges automatiques à gauche,
aventurier et dés blancs à lancer à droite, chronique des coups et décisions de
Chance au centre. La fiche du héros se met à jour pendant le combat. **Fuir** et
**Soins** restent en bas, grisés lorsque les règles les interdisent. Dans
La Forêt de la Malédiction, les commandes **Cibler** n’apparaissent que si au
moins deux adversaires sont encore debout. [Présentation des combats](docs/design/combat-popup.md).

### Carnet et marque-pages

**Carnet** (touche **N**) ouvre un carnet de notes libre. **✦ Nouvelle entrée**
ajoute une rubrique pour le paragraphe courant et **§ Insérer § courant** le numéro du paragraphe actuel ;
les renvois **§N** deviennent des liens cliquables dès la frappe. L’onglet
**Marque-pages** liste les paragraphes marqués (touche **B** ou ruban du
paragraphe) : un clic y conduit, la plume ou **F2** renomme le marque-page.
Sur un paragraphe déjà marqué, le ruban propose de renommer, retirer ou ouvrir
les marque-pages. Suivre un renvoi ou un
marque-page est un voyage manuel : il est confirmé et marque la partie comme
assistée. Le carnet est enregistré dans les sauvegardes mais n’est pas concerné
par Annuler / Rétablir. Échap le referme.

### Carte d’exploration

La **Carte d’exploration** relie les lieux visités sur un graphe zoomable,
construit uniquement à partir de ce que le joueur a découvert : position
actuelle, recherche, adversaires vaincus ou fuis, **Lieu précédent** et
**Revenir à ce passage**. Consulter la carte ne modifie pas la partie.
[Présentation et commandes](docs/design/carte-exploration.md).

### Démarrage, sauvegardes et ambiance

Le démarrage ouvre le menu **Commencer une aventure** : **Nouvelle partie** ou
chargement d’un des cinq emplacements. Une sauvegarde automatique technique
(`autosave.json`) est écrite après les actions, mais elle n’est pas proposée
comme sixième emplacement et n’est pas reprise automatiquement.

**⚙ → Ambiance sonore…** permet de couper les effets sonores, d’activer
l’ambiance de fond (caverne, ville dans la Cité, forêt dans la Forêt), de régler la musique d’accueil ou de la garder pendant la partie, de jouer sa propre musique
(dossier `musique_perso`), d’écouter chaque effet et
de choisir l’habillage du grimoire. Une annonce propre au livre accompagne sa
couverture et le chargement d’une sauvegarde ; elle suit le réglage des effets
sonores. [Reprise, sons et préparation de thèmes](docs/themes-et-ambiance.md).

Les [fenêtres secondaires](docs/design/fenetres-secondaires.md) partagent les
bandeaux et les couleurs du grimoire, des sauvegardes au sélecteur de PDF.

### Raccourcis clavier

| Touche | Action |
| --- | --- |
| **1** à **9** | Choisir la carte de choix correspondante |
| **F1** | Règles du grimoire |
| **F10** | Mode lecture (masque le bandeau et la fiche) |
| **F11** | Plein écran |
| **Échap** | Quitter le mode lecture, le plein écran, le tiroir de la fiche ou le carnet |
| **Tab** | Ouvrir ou fermer la fiche repliée (fenêtre étroite, hors champ de saisie) |
| **N** | Ouvrir ou fermer le carnet |
| **B** | Marquer ou démarquer le paragraphe courant |
| **F2** | Renommer le marque-page qui a le focus dans le carnet |

### Livres pris en charge

Trois éditions sont reconnues par l’empreinte SHA-256 de leur PDF :
**Le Sorcier de la Montagne de Feu** (édition 1982), **La Forêt de la
Malédiction** (édition 1983) et **La Cité des Voleurs** (édition 1983, en
préparation : consultation seulement). Le PDF doit être fourni par l’utilisateur ; il
n’est pas distribué avec Bifurk et ne doit pas être ajouté au dépôt.

## Démarrage

```bash
pip install -r requirements.txt
python main.py
```

Au premier lancement, ouvrez **✦ Grimoires…** pour ajouter le PDF de votre
propre exemplaire du livre.

## Compiler et distribuer sous Windows

Double-cliquez sur **`BUILD_EXE.bat`** depuis une copie du dépôt, avec Python
Windows 64 bits installé (3.13 recommandé). Le script prépare son environnement
`.venv-build`, installe les dépendances et produit :

- `dist/Bifurk/Bifurk.exe`, avec l'icône existante et sans console ;
- `dist/Bifurk-v1.3.0-windows-x64.zip`, contenant le programme et ses dépendances ;
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
├── musique_perso/       # vos morceaux, lus en ordre aléatoire si l’option est cochée
└── donnees/
    ├── grimoires/       # copies locales des PDF importés
    ├── sauvegardes/     # cinq emplacements manuels et autosave.json
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

Les catalogues d’événements couvrent les 400 paragraphes de chacune des deux éditions vérifiées. La logique du dernier lot et les scénarios de validation sont détaillés dans [la documentation des événements](catalogues/README_evenements.md).

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
le volume diminue sur dix secondes puis la musique s’arrête, sauf si la case
**Garder la musique en fond pendant la partie** est cochée (décochée par défaut) :
la boucle continue alors toute la session, sous les effets, les dés et les combats. Le curseur rétro
**Musique d’accueil** de **⚙ → Ambiance sonore…** règle et mémorise le volume indépendamment des effets et
de l’ambiance de caverne (0 % = muet). Par défaut, 70 % du niveau précédent est utilisé.
Le M4A audio est diffusé en continu par Qt Multimedia
et inclus automatiquement dans la distribution Windows avec les autres assets.
La pochette intégrée a été retirée sans réencoder ni modifier le son, afin de ne pas
solliciter les décodeurs vidéo. La licence des packs CC0 d’effets sonores ne s’applique pas à ce fichier musical.

**Ma musique.** Le dossier `musique_perso`, à côté de `main.py` (ou de `Bifurk.exe`) et créé
au démarrage s’il manque, accueille vos propres morceaux (MP3, M4A, AAC, OGG, OGA, OPUS, FLAC,
WAV, WMA ; sous-dossiers ignorés). La case **Jouer ma musique (dossier musique_perso)**, décochée
par défaut, les fait enchaîner en ordre aléatoire à la place de FantasyFair : chaque morceau
passe une fois avant un nouveau tirage, jamais deux fois de suite. Le bouton **Ouvrir le dossier**
l’affiche dans l’explorateur. Le dossier est relu à chaque reprise et à chaque tour complet ; un
fichier illisible est sauté et, sans morceau lisible, la musique habituelle est jouée (un court
message le signale dans la fenêtre). Le volume, la sourdine et la musique permanente s’appliquent
de la même façon. Seul `musique_perso/LISEZMOI.txt` est versionné et livré dans le ZIP : les
morceaux personnels sont ignorés par Git.

Le [compte rendu de la partie et des corrections du 22 octobre 2026](docs/reviews/2026-10-22-partie-et-corrections.md) détaille les règles observées, les corrections éditoriales et les limites de validation.

### Modules de grimoires

Le Sorcier dispose de son manifeste et de son contrôleur de règles. La reconnaissance
des éditions, les bases et les pages de règles sont sélectionnées par module.
Voir [le guide d’intégration](docs/modules-grimoires.md) pour préparer un autre livre.

Les règles communes (création, Chance, soins, combats et fuite) sont regroupées
dans un [socle Défis Fantastiques](docs/socle-defis-fantastiques.md),
réutilisable par les prochains modules sans les exceptions du Sorcier.

### La Forêt de la Malédiction — aventure complète

Le deuxième module est intégré : couverture, prologue, règles, illustrations,
boutique, équipements, épreuves, combats et fins. Le bouton **Grimoires…** permet
de choisir parmi les PDF importés. Les sauvegardes et le format de données restent compatibles.

Les 400 paragraphes et 641 renvois ont été audités. Les cas limites suivent les
règles de projet validées ; une partie interne sans triche a atteint la victoire.
Voir le [bilan de clôture](docs/reviews/2026-10-23-foret-cloture.md) et les
[mécaniques particulières](docs/foret-mecaniques-particulieres.md).

### La Cité des Voleurs — en préparation

Le troisième module est reconnu : couverture, prologue « Les terribles messagers
de Zanbar Bone », règles et profil de départ (30 pièces d'or, potion au choix,
10 repas pris à tout moment hors combat). Les renvois permettent de consulter le
livre ; les événements et combats seront intégrés par tranches de 100 paragraphes.
La Cité a son annonce sonore, son décor de lecture et ses illustrations pleine page.
Voir [La Cité — présentation](docs/cite-module-presentation.md).
