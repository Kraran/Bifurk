# Reprise, sons et thèmes

## Utilisation

Après le premier import, Bifurk mémorise le grimoire **copié dans `donnees/grimoires`**.
Au démarrage, la fenêtre des chroniques propose **Nouvelle partie** et les cinq
emplacements à charger. Ce même bouton **Nouvelle partie** reste disponible dans
le menu **Charger** pendant le jeu, pour recommencer avec un nouveau tirage et
deux relances, sans supprimer les emplacements. Une confirmation est demandée
depuis Charger ; refuser conserve la partie et laisse le menu ouvert.
Au démarrage, il ouvre directement l’introduction du dernier grimoire
importé ; s’il manque, le sélecteur permet d’en importer un. Le PDF d’origine peut
être déplacé ou supprimé après import. La progression n’est pas reprise automatiquement.

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

## Aventuriers et chroniques

La page d’ouverture tire automatiquement un aventurier selon les règles :
Habileté **1d6 + 6**, Endurance **2d6 + 12**, Chance **1d6 + 6**. Le résultat
apparaît dans le récit et sur la fiche. Le joueur inscrit son nom et peut valider
ce tirage, ou utiliser **Reroll** au maximum deux fois (trois tirages au total).
Le deuxième reroll est validé automatiquement et commence l’aventure si le nom
est renseigné ; sinon, le tirage est verrouillé jusqu’à la saisie du nom et au départ.
Valider ne lance aucun nouveau dé. Changer de thème, de taille de texte ou annuler
le départ ne rend pas de relances. L’équipement initial est préparé pour le nouveau
personnage ; il n’y a plus de bouton de création pendant la partie.
Lorsque son Endurance tombe à zéro, une page de fin propose de recommencer
(nom prérempli, nouveau tirage et deux relances disponibles, progression remise à zéro) ou de charger
une chronique. Le chargement d’un personnage mort retrouve cette page.

**Sauvegarder** et **Charger** présentent les mêmes cinq emplacements manuels,
avec le nom de l’aventurier, la date, l’Habileté, l’Endurance et la Chance.
Remplacer ou supprimer un emplacement demande confirmation. **Supprimer** libère
immédiatement l’emplacement ; un emplacement vide ne peut être ni chargé ni supprimé.
L’autosauvegarde technique reste séparée des cinq emplacements et n’est pas chargée
au démarrage. Recommencer ne supprime pas les sauvegardes manuelles.
Les emplacements sont stockés dans `donnees/sauvegardes/emplacement-1.json`
à `emplacement-5.json`. Le nom est conservé dans chaque chronique et sert de
titre de sauvegarde. Seul le format actuel est lu ; aucun import ou conversion
d’anciennes sauvegardes n’est proposé.

Le titre de scène occupe une seule ligne sur toute la largeur du récit ; sa taille
s’adapte aux fenêtres étroites. Le numéro du paragraphe est affiché sur la ligne suivante.

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
pour préparer les assets. FFmpeg n’est pas requis pour jouer. Un flux PCM stéréo
continu via `QAudioSink` (QtMultimedia, inclus dans PySide6) mélange les effets et
la caverne. Il transmet du silence entre les actions pour garder la sortie ouverte,
plutôt que de démarrer un lecteur pour chaque effet très court. La lecture reste
locale et ne touche pas au générateur de hasard du jeu.

Le journal `donnees/parametres/audio.log` indique les demandes, les lectures et le
périphérique de sortie. Il est limité à deux fichiers de 128 Ko.

## Tester sous Windows

```powershell
git fetch origin
git switch fix/confirmation-nouvelle-partie
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Importer un livre, commencer et sauvegarder dans un emplacement. Relancer Bifurk :
choisir la sauvegarde dans la fenêtre d’accueil, ou Nouvelle partie pour retrouver
l’introduction. Vérifier la suppression avec refus puis confirmation.
Dans Ambiance, tester les effets avec **Écouter**, puis une page et un combat réel.
Vérifier le choc avant la boîte de résultat et la réaction immédiate de la page.
Activer puis couper la caverne séparément des effets. Relancer pour vérifier la mémorisation.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```
