# Sons libres — CC0 1.0

Tous les sons livrés dans ce dossier proviennent de ressources publiées sous
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
