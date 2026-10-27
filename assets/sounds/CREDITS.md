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
| page_2.wav, page_3.wav | bookFlip2.ogg, bookFlip3.ogg | Kenney — RPG Audio |
| dice_2.wav, dice_3.wav | dice-throw-1.ogg, dice-throw-3.ogg | Kenney — Casino Audio |
| swords_2.wav, swords_3.wav | impactMetal_medium_001.ogg, impactMetal_heavy_002.ogg | Kenney — Impact Sounds |
| item_2.wav, item_3.wav | handleSmallLeather2.ogg, beltHandle1.ogg | Kenney — RPG Audio |
| coins_2.wav | handleCoins.ogg | Kenney — RPG Audio |
| key_2.wav | metalClick.ogg | Kenney — RPG Audio |
| hit_2.wav à hit_4.wav | impactPunch_medium_001 à 003.ogg | Kenney — Impact Sounds |
| door.wav, door_2.wav | doorOpen_1.ogg, doorOpen_2.ogg | Kenney — RPG Audio |
| flee.wav | footstep00/02/04/06.ogg enchaînés | Kenney — RPG Audio |
| meal.wav, meal_2.wav | metalPot1.ogg, metalPot2.ogg | Kenney — RPG Audio |
| growl.wav à growl_3.wav | NPC/gutteral beast/mnstr1, 4, 7.wav | artisticdude — RPG Sound Pack |
| growl_giant.wav, growl_giant_2.wav | NPC/ogre/ogre1.wav, NPC/giant/giant1.wav | artisticdude — RPG Sound Pack |
| growl_shade.wav, growl_shade_2.wav | NPC/shade/shade1.wav, shade5.wav | artisticdude — RPG Sound Pack |
| growl_slime.wav, growl_slime_2.wav | NPC/slime/slime1.wav, slime4.wav | artisticdude — RPG Sound Pack |
| magic.wav, magic_2.wav | battle/magic1.wav, battle/spell.wav | artisticdude — RPG Sound Pack |
| ambient.ogg | dungeon_ambient_1_0.ogg | [JaggedStone — Loopable Dungeon Ambience](https://opengameart.org/content/loopable-dungeon-ambience) |
| ambient_cite.ogg | 2729.flac « Outdoor market #2 » | [Joseph SARDIN — BigSoundBank](https://bigsoundbank.com/outdoor-market-2-s2729.html) |
| ambient_foret.ogg | 2749.flac « Forest #4 » | [Joseph SARDIN — BigSoundBank](https://bigsoundbank.com/forest-4-s2749.html) |

Les licences Kenney d’origine sont conservées dans les fichiers `LICENSE-Kenney-*`.
Les pages OpenGameArt des deux autres ressources indiquent également **CC0**.
Les pages BigSoundBank de `ambient_cite.ogg` et `ambient_foret.ogg` indiquent « CC0 (public domain) »
([licences BigSoundBank](https://bigsoundbank.com/licences.html)).

Préparation : conversion en PCM mono 16 bits, normalisation des crêtes à 27 500,
suppression du silence de début des effets courts (seuil −45 dB),
retrait de l’amorce faible du bruit de page jusqu’à l’attaque perceptible (5 ms RMS,
seuil 2,5 % de la crête, avec 10 ms conservées avant l’attaque), concaténation
du flacon et des bulles pour la potion, abaissement de hauteur du jingle de défaite.
L’ambiance conserve la boucle complète de 94 secondes à 22 050 Hz, livrée en
OGG Vorbis (qualité 4). Les autres effets sont des WAV à 44 100 Hz. Le son de combat est un impact métallique enregistré.

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

## Ambiances des livres (ville et forêt) — CC0 1.0

Deux enregistrements de Joseph SARDIN (BigSoundBank), publiés sous
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (pages indiquant
« CC0 (public domain) ») ; archives non incluses, URL et SHA-256 dans `sources.json`
(`book_ambiences`) :

- `ambient_cite.ogg` (La Cité des Voleurs) : « Outdoor market #2 », place du marché
  de Nogent-le-Rotrou, <https://bigsoundbank.com/outdoor-market-2-s2729.html>.
  Archive <https://bigsoundbank.com/UPLOAD/flac/2729.flac> (FLAC stéréo 48 kHz,
  24 bits, 129,65 s). Extrait de 45 s à partir de 20 s, passe-haut à 120 Hz.
  Des voix lointaines en français restent audibles dans le brouhaha.
- `ambient_foret.ogg` (La Forêt de la Malédiction) : « Forest #4 » (oiseaux, vent),
  <https://bigsoundbank.com/forest-4-s2749.html>. Archive
  <https://bigsoundbank.com/UPLOAD/flac/2749.flac> (FLAC stéréo 48 kHz, 24 bits,
  225,87 s). Extrait de 45 s à partir de 104 s, passe-haut à 120 Hz et aigus
  adoucis de 4 dB au-dessus de 5 kHz pour un sous-bois moins vif.

Préparation commune (`scripts/prepare_book_ambiences.py`, FFmpeg et NumPy, outil
seulement) : filtres indiqués dans `sources.json`, mono 22 050 Hz, fondu enchaîné à
puissance constante de 3 s de la fin vers le début pour une boucle sans couture,
retrait du décalage continu, niveau RMS de −31,7 dBFS (4 dB sous la caverne) sous le
plafond de crête des effets (27 500), PCM mono 16 bits, puis encodage OGG Vorbis
(qualité 4), qui garde le nombre exact d’échantillons. Chaque boucle dure 45 s et
pèse environ 250 Ko (1 984 544 octets en WAV). La boucle du livre ouvert remplace la caverne dans la même
case « Ambiance de fond », au même volume de lecture ; le Sorcier garde la caverne.
