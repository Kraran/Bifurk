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

**⚙ Réglages → Ambiance sonore…** active ou coupe les sons, règle la musique d’accueil
et choisit le thème. Ces préférences
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

- `id` (identifiant unique) et `name` (nom affiché dans **Ambiance sonore…**) ;
- `stylesheet`, chemin du fichier QSS relatif au manifeste ;
- `assets.parchment`, `assets.leather`, `assets.scene`, chemins des textures et du décor ;
- `assets.checkmark`, dessin SVG de la coche des cases du thème fourni ;
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

Dans **⚙ → Ambiance sonore…**, une liste et le bouton **Écouter** permettent de tester chaque
son individuellement. L’**ambiance de fond : caverne** a sa propre commande,
indépendante des effets, et reste désactivée par défaut. La boucle joue à faible volume.

La musique d’accueil (`FantasyFair.m4a`, seul morceau) est lue par un `QMediaPlayer`
distinct du flux des effets. Par défaut, elle s’éteint en dix secondes à l’entrée dans
l’aventure. La case **Garder la musique en fond pendant la partie**, décochée par défaut
et mémorisée sous `music_persistent`, la laisse tourner en boucle toute la session,
chargements compris, au volume du curseur (0 % reste muet). La cinématique
d’ouverture n’a pas de piste son et ne l’interrompt donc pas. Les effets, dés et
combats se mélangent par-dessus sans atténuation : la musique plafonne à 0,45
(0,315 par défaut) quand les effets jouent entre 0,50 et 0,80. Cocher la case en cours de partie relance la
musique ; la décocher reprend le fondu habituel.

La case **Jouer ma musique (dossier musique_perso)** (`custom_music`, décochée par défaut)
remplace FantasyFair par les fichiers audio du dossier `musique_perso` (à côté de `main.py`
ou de `Bifurk.exe`, voir `APP_DIR`), lus à plat. `custom_music.py` filtre les extensions et
tire les morceaux « sans remise » (sac mélangé, sans doublon à la jointure de deux tirages) avec
son propre `random.Random` : le hasard des dés n’est pas consommé. Chaque morceau est joué une
fois (`setLoops(1)`) ; `EndOfMedia` enchaîne le suivant, `errorOccurred` écarte le fichier
pour la session et passe au suivant au tour de boucle suivant. Sans morceau lisible, la boucle
FantasyFair reprend sans dialogue. Le dossier est relu à chaque reprise, à chaque bascule et à
chaque nouveau tirage. Fondu, permanence, curseur et sourdine sont inchangés. Basculer la case
change de musique immédiatement dans les menus ou si la musique est permanente, sinon à la
prochaine reprise.

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
git switch master
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Importer un livre, commencer et sauvegarder dans un emplacement. Relancer Bifurk :
choisir la sauvegarde dans la fenêtre d’accueil, ou Nouvelle partie pour retrouver
l’introduction. Vérifier la suppression avec refus puis confirmation.
Dans **⚙ → Ambiance sonore…**, tester les effets avec **Écouter**, puis une page et un combat réel.
Vérifier le choc avant la boîte de résultat et la réaction immédiate de la page.
Activer puis couper la caverne séparément des effets. Cocher **Garder la musique en fond
pendant la partie**, commencer l’aventure : la musique continue. Relancer pour vérifier la mémorisation.
Déposer quelques MP3/M4A/OGG (et un fichier corrompu renommé en `.mp3`) dans `musique_perso`, cocher
**Jouer ma musique** : vérifier l’enchaînement aléatoire, le saut du fichier corrompu, puis le retour
à FantasyFair avec le dossier vidé.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

### Diagnostics Media Foundation sous Windows

Avant l'initialisation multimédia, `audio_configuration.configure_audio_backend`
ajoute `av1_mf`, `h264_mf` et `hevc_mf` à `QT_FFMPEG_EXCLUDE_ENCODERS` sous Windows.
Qt teste normalement ces encodeurs vidéo même pour créer le lecteur musical ;
leurs transformations MFT peuvent manquer, alors que le décodage AAC fonctionne.
Bifurk ne réalise aucun encodage vidéo : exclure ces sondes évite leurs erreurs
sans changer le son, le décodeur musical ou les règles de journalisation.
Les exclusions déjà présentes sont conservées. Aucun réglage système Windows ni
installation de codecs supplémentaires n'est nécessaire pour cette correction.

Cette option interne a été vérifiée dans Qt 6.12 ; sa prise en charge doit être
recontrôlée lors d'une mise à jour majeure de PySide6/Qt. Elle ne supprime pas les
véritables erreurs audio ni les autres avertissements indépendants, notamment ceux
concernant les polices.
