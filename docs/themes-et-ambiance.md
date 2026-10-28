# Reprise, sons et thèmes

## Utilisation

Après le premier import, Bifurk mémorise le grimoire **copié dans `donnees/grimoires`**.
Au démarrage, la fenêtre des chroniques propose **Continuer la dernière partie** (la plus
récente des sauvegardes lisibles, autosave comprise : `save_slots.latest_save`),
**Nouvelle partie** et les cinq emplacements à charger, chacun avec la miniature de la
couverture de son grimoire (rendue en mémoire depuis le PDF du joueur, `MainWindow._save_cover`). Ce même bouton **Nouvelle partie** reste disponible dans
le menu **Charger** pendant le jeu, pour recommencer avec un nouveau tirage et
deux relances, sans supprimer les emplacements. Une confirmation est demandée
depuis Charger ; refuser conserve la partie et laisse le menu ouvert.
Au démarrage, il ouvre directement l’introduction du dernier grimoire
importé ; s’il manque, le sélecteur permet d’en importer un. Le PDF d’origine peut
être déplacé ou supprimé après import. La progression n’est pas reprise automatiquement.

**⚙ Réglages → Ambiances…** range les réglages en cinq sections alignées sur la même
grille (libellé, réglage, valeur ou bouton) : **Effets sonores**, **Ambiance de fond**,
**Musique d’accueil**, **Lecture à voix haute** et **Habillage du grimoire** (le thème).
Deux colonnes sur un écran large, une seule colonne défilante sinon ; tous les curseurs de
volume partagent le même habillage (`QSlider[volume="true"]`). Le menu Réglages n’a plus de
sous-menu : ses pictogrammes sont peints dans l’or du thème (`grimoire_chrome.menu_icon`)
et repeints à chaque changement de thème. Ces préférences
et le chemin relatif du dernier livre sont conservés dans
`donnees/parametres/preferences.json`, indépendamment des sauvegardes de partie.

**Lecture à voix haute.** Le bouton 🔊 lit le paragraphe ; un second clic l’arrête et
retient la phrase en cours. Relancer la lecture sur le même paragraphe reprend au début de
cette phrase (infobulle « Reprendre la lecture à la phrase interrompue »). La phrase est
retrouvée par les repères de phrase que le service de voix envoie avec l’audio
(`SentenceBoundary`), à défaut par la position dans le morceau. Changer de paragraphe,
charger une partie ou finir la lecture oublie ce point de reprise (`tts.ParagraphReader`).

Chaque effet peut avoir des variantes (`page_2.wav`, `page_3.wav`…) : une lecture en
tire une, jamais la même deux fois de suite, avec un léger écart de volume, par un
générateur propre à la banque de sons (le hasard des dés n’est pas touché). S’ajoutent :
**porte** quand le choix suivi ouvre ou franchit une porte, une grille ou une trappe
(« ne pas franchir la porte » reste une page tournée) ; **repas** ; **fuite** quand on
quitte un combat par sa sortie de fuite ; **cri** de l’adversaire à l’ouverture d’un
nouveau combat (bête, ogre ou géant, spectre, créature visqueuse, d’après son nom) ;
**magie** et tout autre effet désigné par la clé `sound` d’une entrée vérifiée du
catalogue d’événements. Pendant la fenêtre de combat, l’ambiance baisse en douceur.
`scripts/prepare_sounds.py ARCHIVES [NOM ...]` reconstruit tout ou partie des effets ;
licences et remerciements : `LICENCES-ET-REMERCIEMENTS.txt`.

Les effets accompagnent le changement de paragraphe, les lancers de dés et les
assauts. Un rafraîchissement du même paragraphe ou une restauration de sauvegarde
ne rejoue pas le bruit de page. Les sons sont coupés dans les plateformes Qt de
test `offscreen` et `minimal` ; l’écoute doit être vérifiée sur un poste avec sortie audio.

## Thèmes des grimoires

La barre de titre Windows de chaque fenêtre suit le thème : fond cuir
(`icon_background`), texte or (`gold`) et bordure (`frame`), envoyés à DWM
(`main.set_native_titlebar`) à l’affichage, à la sortie du plein écran et à chaque
changement de thème. Windows 11 applique ces couleurs ; Windows 10 n’offre que la
barre sombre, demandée d’abord. Un refus est noté dans `donnees/parametres/fenetres.log`.

Quatre thèmes sont fournis : **Standard** (`grimoire`, le cuir bordeaux d’origine)
et un thème par livre, déclaré par la clé `book` de son manifeste :
**L’Antre de Zagor** (`sorcier`, Sorcier), **Le Sous-bois de Darkwood** (`foret`,
Forêt) et **Le Port du Sable Noir** (`cite`, Cité). Sans thème mémorisé (choix
**Selon le grimoire ouvert**), l’ouverture d’un livre ou d’une de ses sauvegardes
affiche son thème ; un livre non reconnu et l’accueil gardent Standard. Choisir un
thème dans **Réglages → Ambiances…** le mémorise (`theme` dans `preferences.json`) : il
s’applique alors à tous les livres, jusqu’au retour à **Selon le grimoire ouvert**.

Les thèmes de livre dérivent de Standard (`"base": "grimoire"`) : ils reprennent son
QSS, ses couleurs et son décor d’accueil, recolorés par la section `recolor`
(`theme_palette.py`) :

- `leather` : teinte (`#rrggbb`), facteurs de saturation et de luminosité des bruns
  rouges (cuir, encres sombres) ;
- `seal` : idem pour les rouges francs (cire, rubriques, rubans) ;
- `page` : teinte visée en degrés, part de cette teinte, facteurs de saturation et de
  luminosité du parchemin ;
- `ground` : teinte et saturation des fonds presque noirs.

Les ors, les liens bleus, les écus Habileté / Endurance / Chance et les dessins
d’objets ne changent pas. Les peintures QPainter passent par `theme_palette.tint()`
(constantes de couleur des modules comprises, retintées au changement de thème) ;
les textures recolorées (`leather.jpg`, `sheet-leather.jpg`, `parchment.jpg`,
`page-parchment.jpg`) sont préparées par `scripts/prepare_theme_textures.py` avec
les mêmes règles.

## Préparer un thème

Les thèmes sont découverts au lancement dans `assets/themes/*/theme.json`. Le plus
simple est de dériver Standard comme les thèmes de livre ci-dessus. Pour un thème
entièrement nouveau, copier le dossier `grimoire` dans un nouveau dossier et modifier :

- `id` (identifiant unique) et `name` (nom affiché dans **Ambiances…**) ;
- `stylesheet`, chemin du fichier QSS relatif au manifeste ;
- `assets.parchment`, `assets.leather`, `assets.scene`, chemins des textures et du décor ;
- `assets.checkmark`, dessin SVG de la coche des cases du thème fourni ;
- `colors`, palette des surfaces peintes, ornements, emblèmes et textes du lecteur ;
- éventuellement `fonts.reading` et `fonts.ui`, noms de polices installées ou déjà embarquées.

Le fichier QSS accepte les variables `${parchment}`, `${leather}`, `${scene}`,
`${reading_font}`, `${ui_font}` et les clés de `colors`. La palette du manifeste
décrit les éléments dessinés ; le QSS décrit les contrôles Qt. Un thème doit adapter
les deux pour garder des contrastes cohérents. Tous les champs du manifeste fourni
sont nécessaires, sauf `fonts`. Les thèmes incomplets sont ignorés ; Standard
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

Dans **⚙ → Ambiances…**, une liste et le bouton **Écouter** permettent de tester chaque
son individuellement. L’**ambiance de fond** a sa propre commande,
indépendante des effets, et reste désactivée par défaut. La boucle joue à faible volume :
la caverne, la ville quand La Cité des Voleurs est ouverte, la forêt pour La Forêt de la Malédiction
(le libellé nomme la boucle). `scripts/prepare_book_ambiences.py` reconstruit les boucles des livres.

**Scènes d’ambiance.** `SCENES` (dans `sound_effects.py`) décrit treize scènes partagées
entre les livres : caverne, souterrain humide, crypte, rivière, marais, forêt, forêt la nuit,
lande venteuse, rue de la ville, marché, port, taverne et intérieur au coin du feu. Chacune a
une boucle de fond (`scene_*.ogg`, ou la boucle d’un livre) et, pour certaines, un son ponctuel
(`spot_goutte`, `spot_hibou`, `spot_grenouille`, avec variantes) joué au hasard toutes les
`every` secondes, tiré par le générateur privé de la banque. `SoundBank.set_scene(clé)` passe
à la scène en fondu enchaîné ; `set_scene(None)` rend la boucle du livre. Les sons ponctuels
suivent l’interrupteur et le curseur de l’ambiance, et la baisse pendant un combat.
Dans la fenêtre Ambiances, la ligne **Essai** de l’ambiance de fond et son bouton **Écouter** jouent la scène choisie (case d’ambiance cochée) ;
la scène d’avant revient à la fermeture. Les fichiers sont reconstruits par
`scripts/prepare_book_ambiences.py` à partir des sections `scene_sources`, `scene_ambiences`
et `scene_spots` de `assets/sounds/sources.json` (sources BigSoundBank CC0, empreintes SHA-256).

**Ambiance selon le paragraphe.** Un livre peut livrer un catalogue `ambiences`
(`catalogues/ambiances_<livre>.json`, déclaré dans son manifeste et lié à l’empreinte du PDF).
Il répartit tous les paragraphes en **zones** (une scène chacune) et ajoute des **exceptions**
(une salle, une taverne…) ; une exception sans scène (`null`) garde celle du paragraphe d’où
l’on vient (monstre errant). Chaque entrée a un statut `proposé` (déduit du texte) ou
`vérifié` (relu). `ambience_map.py` valide le catalogue : chaque paragraphe dans une seule
zone, scènes connues, statuts permis ; un catalogue invalide laisse la boucle du livre.
À chaque déplacement, les contrôleurs appellent `_ambience_follow_paragraph` : la scène suit
le paragraphe, y compris après un chargement ou une annulation ; la page de titre et
l’accueil rendent la boucle du livre. Dans la fenêtre d’ambiance, **Ambiance : selon le
paragraphe / boucle du livre** (`ambient_mode`, « selon le paragraphe » par défaut) choisit.
Les trois livres ont un catalogue : le Sorcier par zones déduites des renvois entre paragraphes
(galeries du sud, rivière, rive nord, Labyrinthe, repaire de Zagor), relu et `vérifié` ; la Forêt
par lieux (forêt et vallée, plaines et collines, rivières, nuits au campement, cabanes, cavernes,
souterrains, crypte, étang, Pont-de-Pierre) et la Cité (rues, maisons, tour de Zanbar Bone,
égouts et cellules, port, marché, tavernes, hors les murs, jardin, pont), encore `proposé`.

Relecture : `python scripts/relecture_ambiances.py LIVRE.pdf` écrit
`audit-output/relecture-ambiances-<livre>.html`, une page locale (extraits du livre, à ne pas
diffuser) qui présente chaque zone, chaque paragraphe, sa scène et l’exception qui l’a
choisie, avec un lecteur pour écouter chaque boucle. Après relecture, passer les entrées
validées à `vérifié` dans le catalogue.

La musique d’accueil (`FantasyFair.m4a`, seul morceau) est lue par un `QMediaPlayer`
distinct du flux des effets. Par défaut, elle s’éteint en dix secondes à l’entrée dans
l’aventure. La case **Garder la musique en fond pendant la partie**, décochée par défaut
et mémorisée sous `music_persistent`, la laisse tourner en boucle toute la session,
chargements compris, au volume du curseur (0 % reste muet). La cinématique
d’ouverture n’a pas de piste son et ne l’interrompt donc pas. Les effets, dés et
combats se mélangent par-dessus sans atténuation : la musique plafonne à 0,45
(0,315 par défaut) quand les effets jouent entre 0,50 et 0,80. Cocher la case en cours de partie relance la
musique ; la décocher reprend le fondu habituel.

La case **Jouer ma musique** (dossier `musique_perso`) (`custom_music`, décochée par défaut)
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

**Musique de victoire.** Arriver au §400 d’un grimoire reconnu (les trois livres finissent
là) lance `Achievement.ogg` en boucle (« Achievement », Alexander Nakarada, CC BY 4.0) sur
un second `QMediaPlayer` de `IntroMusic` : `start_victory()` éteint la musique en cours en
1,5 s (accueil, permanente ou personnelle), boucle le morceau au volume du curseur
**Musique d’accueil** (0 % reste muet) et l’ambiance est baissée comme pendant un combat.
Quitter le §400 (annulation, chargement, nouvelle partie, accueil) appelle `stop_victory()` :
fondu de 1,5 s, puis reprise de la musique d’accueil si elle doit jouer. Le déclenchement est
centralisé dans `_victory_follow_paragraph()`, appelé par `_ambience_follow_paragraph()`.
Le fichier est produit par `scripts/prepare_victory_music.py` depuis le MP3 d’origine
(empreinte de l’audio vérifiée) : silence de tête et fin de traîne retirés, −2,1 dB pour
s’aligner sur FantasyFair (−14 LUFS), sans pochette ni métadonnées, OGG Vorbis q4 (≈ 1,8 Mo).

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
Dans **⚙ → Ambiances…**, tester les effets avec **Écouter**, puis une page et un combat réel.
Vérifier le choc avant la boîte de résultat et la réaction immédiate de la page.
Activer puis couper la caverne séparément des effets ; ouvrir la Cité puis la Forêt : la ville puis la forêt la remplacent. Cocher **Garder la musique en fond
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
