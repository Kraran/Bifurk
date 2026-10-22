# Compiler, tester et publier Bifurk sous Windows

## Préparer le poste

La compilation du `.exe` doit se faire **sur Windows**. Le script cible Windows
10/11 x64 ; installer Python Windows **64 bits**, version 3.11 ou supérieure,
de préférence 3.13, avec Python Launcher. Git est nécessaire pour récupérer le
projet et identifier la révision de publication. Internet sert à installer les
dépendances. Le joueur n'a besoin ni de Python ni de Git.

Depuis PowerShell, après fusion de la PR :

```powershell
cd D:\Bifurk
git switch master
git pull --ff-only
.\BUILD_EXE.bat
```

On peut aussi double-cliquer sur `BUILD_EXE.bat`. Il travaille depuis son propre
dossier, même si le terminal est ailleurs ou si le chemin contient des espaces.
Il conserve l'environnement de jeu `.venv` et utilise `.venv-build` pour compiler.
Le premier lancement prend plus de temps à cause des téléchargements.

## Résultat de la compilation

```text
dist/
├── Bifurk/
│   ├── Bifurk.exe
│   └── _internal/
│       ├── assets/          # icônes, textures, thèmes, polices, sons et crédits
│       ├── catalogues/
│       └── ...              # Python, Qt, PyMuPDF, plugins et métadonnées
├── Bifurk-v1.1.2-windows-x64.zip
└── Bifurk-v1.1.2-windows-x64.zip.sha256
```

La version du nom d'archive et des propriétés Windows est lue dans `app_info.py`.
L'icône intégrée vient de `assets/bifurk.ico`. Le mode fenêtre masque la console ;
les erreurs Python au démarrage restent signalées par PyInstaller.
Les traductions Qt françaises et le backend multimédia sont embarqués par la
configuration et les hooks PyInstaller.

Le ZIP ajoute un `LISEZ-MOI.txt`, les informations sur les composants tiers et
`COMPILATION.json` (version, cible et révision Git de la source). Son empreinte
SHA-256 permet de vérifier le fichier téléchargé. Le script n'ajoute ni PDF ni
`donnees` ; il refuse une compilation incomplète ou contenant ces données.

**Conserver tout le dossier `_internal` avec l'exécutable.** Il s'agit d'une
distribution portable en dossier, comme PhenixRebirth. Le ZIP rassemble ce dossier
pour le téléchargement. Aucun installateur ni droit administrateur n'est requis.

## Tester l'archive avant publication

Extrayez le ZIP dans un dossier distinct, par exemple
`D:\Tests Bifurk\Bifurk`, et lancez `Bifurk.exe`. Cela teste la distribution réelle
sans utiliser les modules ni les ressources du dépôt Python.

Vérifier :

1. L'icône dans l'Explorateur, la fenêtre et la barre des tâches ; la version 1.1.2
   dans les propriétés du fichier et À propos.
2. Nouvelle partie, importation de votre PDF, couverture, nom et tirage du héros.
3. Lecture, illustrations, zoom et fenêtre des règles ; boutons français.
4. Sons de page et de dés, préécoute et **un véritable assaut de combat**.
   Les jets 1d6 / 2d6 doivent montrer le plateau animé, les faces et leur total ;
   tester aussi **Passer l'animation**, puis **Continuer**.
   Pendant le combat, vérifier les deux plateaux intégrés : dés rouges automatiques,
   dés blancs déclenchés par le joueur, Chance dans la même fenêtre, puis victoire
   ou défaite et mise à jour des caractéristiques.
5. Sauvegarde, fermeture, relance et chargement depuis un emplacement.
6. Déplacement du dossier complet après fermeture : les données restent portables.

Au premier lancement, `donnees` apparaît à côté de `Bifurk.exe`, **hors de
`_internal`**. Pour une vérification d'autonomie complète, essayer aussi le ZIP
sur un PC Windows sans Python installé.

Si vous avez lancé directement `dist\Bifurk\Bifurk.exe`, le prochain build
refusera d'écraser le dossier qui contient désormais `donnees`. Fermez le jeu et
déplacez ce dossier complet ailleurs avant de relancer la compilation.
Le script ne supprime jamais toutes les sorties de `dist` ni les données du dépôt.

Les tests automatisés restent disponibles :

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-build\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

Le mode offscreen ne vérifie ni l'audibilité, ni la barre Windows, ni l'exécutable
sur un poste sans Python. Ces points exigent le contrôle du ZIP sur Windows.

## Préparer la release GitHub

La compilation ne téléverse rien. Après avoir testé le ZIP, deux possibilités :

- Sur GitHub, ouvrir **Releases → Draft a new release**, créer le tag `v1.1.2`
  sur la révision compilée, copier les notes de `RELEASE_NOTES.md`, joindre le ZIP
  et son fichier `.sha256` puis publier quand les contrôles sont terminés.
- Avec le script, installer GitHub CLI, s'authentifier puis lancer :

```powershell
winget install --id GitHub.cli -e
# Rouvrir PowerShell si gh n'est pas encore reconnu.
gh auth login
.\PUBLISH_RELEASE.bat
```

Ce script crée uniquement un **brouillon** sur `Kraran/Bifurk`. Il téléverse le ZIP
déjà testé et son empreinte, sans recompiler ; sa cible est la révision Git
enregistrée lors de l'archivage. Il refuse une archive modifiée, une version
différente ou une compilation sans révision propre. Il faut donc compiler depuis
une révision commitée et poussée, de préférence `master` après fusion.
Il ne remplace pas une release existante : GitHub signale l'erreur si le tag a
déjà une release. Réviser le brouillon sur GitHub avant **Publish release**.

Les notes fournies sont un modèle : compléter les changements propres à la
version. Le binaire n'est pas signé ; une signature Authenticode nécessiterait
votre certificat et n'est pas ajoutée par ces scripts.

## Mettre à jour une installation

Fermer le jeu, conserver une copie de `donnees`, extraire la nouvelle distribution
dans un dossier neuf puis recopier `donnees` à côté du nouvel exécutable.
Ne pas mélanger les bibliothèques `_internal` de deux versions. La compilation
n'ajoute aucune compatibilité avec les anciens formats de sauvegarde.

## Maintenance de la chaîne de compilation

- `Bifurk.spec` sélectionne explicitement les ressources et conserve les
  métadonnées des dépendances. Les hooks PyInstaller gèrent leurs bibliothèques natives.
  Les données PyMuPDF sont également collectées : certaines versions chargent dès
  l'import les configurations YAML et modèles ONNX de leur analyseur de mise en
  page. Sans ces fichiers, l'accueil fonctionne mais l'import du livre échoue.
- `requirements-build.txt` ajoute PyInstaller aux dépendances de l'application.
  Ces dépendances utilisent des plages de versions : deux builds à des dates
  différentes peuvent embarquer des versions différentes. Les métadonnées livrées
  permettent de les identifier.
- `scripts/package_release.py` valide et archive les sorties, puis prépare
  éventuellement le brouillon. Les tests isolent le réseau avec des doublures.
- `main.py` distingue `RESOURCE_DIR` (ressources embarquées) de `APP_DIR`
  (données portables à côté de l'exécutable). Les catalogues et le thème de repli
  restent relatifs au code embarqué via `__file__`.
- Les fichiers `.bat` sont conservés en CRLF par `.gitattributes`.

Si la compilation échoue, lire l'erreur dans la console et les fichiers
`build\Bifurk\warn-Bifurk.txt` / `xref-Bifurk.html`. Pour repartir avec d'autres
versions de dépendances, recréer uniquement `.venv-build`, pas `.venv` ni `donnees`.

Consulter [COMPOSANTS-TIERS.md](COMPOSANTS-TIERS.md) avant la publication : les
conditions PyMuPDF / MuPDF (AGPL ou commerciale), Qt et les assets accompagnent
la distribution. La préparation du binaire n'attribue pas une nouvelle licence
au code Bifurk et ne signe pas l'exécutable.
