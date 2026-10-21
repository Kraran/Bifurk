# Reprise, sons et thèmes

## Utilisation

Après le premier import, Bifurk mémorise le grimoire **copié dans `donnees/grimoires`**.
Au démarrage suivant, il reprend la sauvegarde automatique si elle appartient à ce
livre ; sinon il affiche sa page de titre. Le PDF d’origine peut être déplacé ou
supprimé après import. Si la copie manque, l’accueil reste disponible pour ouvrir
un autre livre. Une sauvegarde d’un autre grimoire n’est jamais reprise automatiquement.

Le bouton **Ambiance** active ou coupe les sons et choisit le thème. Ces préférences
et le chemin relatif du dernier livre sont conservés dans
`donnees/parametres/preferences.json`, indépendamment des sauvegardes de partie.

Les effets accompagnent le changement de paragraphe, les lancers de dés et les
assauts. Un rafraîchissement du même paragraphe ou une restauration de sauvegarde
ne rejoue pas le bruit de page. Les sons sont coupés dans les plateformes Qt de
test `offscreen` et `minimal` ; l’écoute doit être vérifiée sur un poste avec sortie audio.

## Préparer un thème

Le seul thème fourni est **Le Grimoire**. Les thèmes sont découverts au lancement
dans `assets/themes/*/theme.json`. Pour en créer un, copier le dossier `grimoire`
dans un nouveau dossier et modifier :

- `id` (identifiant unique) et `name` (nom affiché dans Ambiance) ;
- `stylesheet`, chemin du fichier QSS relatif au manifeste ;
- `assets.parchment`, `assets.leather`, `assets.scene`, chemins des textures et du décor ;
- `colors`, palette des surfaces peintes, ornements, emblèmes et textes du lecteur ;
- éventuellement `fonts.reading` et `fonts.ui`, noms de polices installées ou déjà embarquées.

Le fichier QSS accepte les variables `${parchment}`, `${leather}`, `${scene}`,
`${reading_font}`, `${ui_font}` et les clés de `colors`. La palette du manifeste
décrit les éléments dessinés ; le QSS décrit les contrôles Qt. Un thème doit adapter
les deux pour garder des contrastes cohérents. Tous les champs du manifeste fourni
sont nécessaires, sauf `fonts`. Les thèmes incomplets sont ignorés ; Le Grimoire
sert de repli si le thème mémorisé n’existe plus.

Changer de thème ne modifie ni caractéristiques, ni inventaire, ni rencontres,
ni historique de partie. Aucun script Python de thème n’est exécuté.

## Sons

Les WAV PCM mono proviennent maintenant de packs **CC0**, principalement Kenney
(RPG Audio, Casino Audio, Impact Sounds et Music Jingles), complétés par des
ressources OpenGameArt CC0. Sources, auteurs, licences et fichiers précis :
[crédits audio](../assets/sounds/CREDITS.md). Les anciens effets synthétiques sont remplacés.

Les effets sont préchargés au démarrage. Le bruit de page démarre avant le rendu
du nouveau paragraphe, avec suppression de l’amorce faible de l’enregistrement.
Le choc métallique du combat démarre avant la boîte de résultat de l’assaut.
Objet, pièces, serrure, potion, blessure, victoire et mort ont chacun un effet.
Une seule indication de résultat est jouée par action pour limiter les superpositions.
Ni annulation ni chargement ne rejouent ces effets.

Dans **Ambiance**, une liste et le bouton **Écouter** permettent de tester chaque
son individuellement. L’**ambiance de fond : caverne** a sa propre commande,
indépendante des effets, et reste désactivée par défaut. La boucle joue à faible volume.

`scripts/prepare_sounds.py` convertit les archives créditées avec FFmpeg, uniquement
pour préparer les assets. FFmpeg n’est pas requis pour jouer. `QSoundEffect`
(QtMultimedia, inclus dans PySide6) assure la lecture locale, sans service externe
et sans toucher au générateur de hasard du jeu.

## Tester sous Windows

```powershell
git fetch origin
git switch feat/sons-libres-reactifs
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Importer un livre, commencer, changer de paragraphe, fermer puis relancer Bifurk :
le livre et la progression doivent être repris. Dans Ambiance, tester les effets avec **Écouter**, puis une page et un combat réel.
Vérifier le choc avant la boîte de résultat et la réaction immédiate de la page.
Activer puis couper la caverne séparément des effets. Relancer pour vérifier la mémorisation.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```
