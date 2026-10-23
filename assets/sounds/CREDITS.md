# Effets sonores — CC0 1.0

Les effets WAV recensés ci-dessous proviennent de ressources publiées sous
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), utilisables et
redistribuables, y compris commercialement. Aucun compte ou téléchargement n’est
nécessaire au lancement du jeu.

| Fichier | Source originale | Auteur / pack |
|---|---|---|
| page.wav | bookFlip1.ogg | [Kenney — RPG Audio](https://kenney.nl/assets/rpg-audio) |
| dice.wav | dice-throw-2.ogg | [Kenney — Casino Audio](https://kenney.nl/assets/casino-audio) |
| swords.wav | metal-ringing.wav | [artisticdude — RPG Sound Pack](https://opengameart.org/content/rpg-sound-pack) |
| item.wav | handleSmallLeather.ogg | Kenney — RPG Audio |
| coins.wav | handleCoins2.ogg | Kenney — RPG Audio |
| key.wav | metalLatch.ogg | Kenney — RPG Audio |
| potion.wav | bottle.wav + bubble.wav | [artisticdude — RPG Sound Pack](https://opengameart.org/content/rpg-sound-pack) |
| hit.wav | impactPunch_medium_000.ogg | [Kenney — Impact Sounds](https://kenney.nl/assets/impact-sounds) |
| victory.wav | jingles_PIZZI00.ogg | [Kenney — Music Jingles](https://kenney.nl/assets/music-jingles) |
| death.wav | jingles_PIZZI16.ogg | Kenney — Music Jingles |
| ambient.wav | dungeon_ambient_1_0.ogg | [JaggedStone — Loopable Dungeon Ambience](https://opengameart.org/content/loopable-dungeon-ambience) |

Les licences Kenney d’origine sont conservées dans les fichiers `LICENSE-Kenney-*`.
Les pages OpenGameArt des deux autres ressources indiquent également **CC0**.

Préparation : conversion en PCM mono 16 bits, normalisation des crêtes à 27 500,
suppression du silence de début des effets courts (seuil −45 dB),
retrait de l’amorce faible du bruit de page jusqu’à l’attaque perceptible (5 ms RMS,
seuil 2,5 % de la crête, avec 10 ms conservées avant l’attaque), concaténation
du flacon et des bulles pour la potion, abaissement de hauteur du jingle de défaite.
L’ambiance conserve la boucle complète de 94 secondes à 22 050 Hz. Les autres
effets sont à 44 100 Hz. Le son de combat est un impact métallique enregistré.

Les URL de téléchargement, fichiers exacts et empreintes SHA-256 des archives sont
dans `sources.json`. `scripts/prepare_sounds.py` reconstruit les WAV à partir de ces
archives avec FFmpeg. Les anciens effets synthétiques ne sont plus utilisés.

## Musique d’accueil distincte des effets CC0

`FantasyFair.m4a` a été fourni par l’utilisateur. Ses métadonnées indiquent
« Tavern Loop One », Alexander Nakarada, album « Fantasy Fair ».
Le classement CC0 des effets ci-dessus ne concerne pas ce fichier musical.


## Annonces des livres fournies par l’utilisateur

`book_sorcier.wav` et `book_foret.wav` proviennent respectivement de
« Le Sorcier.wav » et « La foret.wav », fournis pour leur diffusion dans Bifurk.
Leur licence n’est pas assimilée au CC0 des autres effets ; aucune autre provenance
ou licence n’a été fournie. Les originaux ne sont ni modifiés ni inclus.

Préparation : retrait du décalage continu, coupe des silences avec marges de
60 ms avant et 120 ms après, niveau RMS cible de -21 dBFS sous un plafond de crête
à -2 dBFS, fondus de 5 ms et 20 ms, conversion sinc en mono PCM 16 bits à 22 050 Hz.
Les fichiers finaux durent 1,60 s et 1,86 s et pèsent environ 69 et 80 Kio.
`scripts/prepare_book_sounds.py` permet de les reconstruire avec NumPy, requis
uniquement pour cet outil. `book_sounds.json` contient les empreintes et mesures.
Les annonces suivent le réglage des effets sonores, sans boucle ni superposition.
