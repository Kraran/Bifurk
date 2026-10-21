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

Les trois WAV PCM mono sont originaux, générés par `scripts/generate_sounds.py`
avec la bibliothèque standard. Ce script utilise son propre générateur de hasard,
indépendant de celui du jeu. Les sons sont joués par `QSoundEffect` (QtMultimedia,
inclus dans PySide6). Aucun téléchargement ni service audio externe n’est utilisé.

## Tester sous Windows

```powershell
git fetch origin
git switch feat/reprise-sons-themes
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Importer un livre, commencer, changer de paragraphe, fermer puis relancer Bifurk :
le livre et la progression doivent être repris. Écouter une page, un lancer et un
assaut, puis couper les sons dans Ambiance. Relancer pour vérifier la mémorisation.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```
