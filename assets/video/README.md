# Introduction de Bifurk

`introduction.mp4` provient de `bifurk.mp4`, fourni par l'utilisateur dans
`bifurk.zip`. Seule la vidéo principale est conservée : ni piste sonore ni
image de couverture attachée.

- Durée : 6,041667 secondes, sans boucle.
- Format : H.264, YUV 4:2:0, 1280 × 720, 24 images/s.
- Taille : 1 935 806 octets, contre 5 495 624 pour l'original (−65 %).
- Index MP4 placé au début pour démarrer la lecture rapidement.

Commande de préparation (FFmpeg, uniquement pour reconstruire la ressource) :

```sh
ffmpeg -i bifurk.mp4 -map 0:v:0 -an -sn -dn -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -movflags +faststart -map_metadata -1 introduction.mp4
```

FFmpeg en ligne de commande n'est pas requis sur le PC du joueur : le film est
lu par Qt Multimedia, comme la musique d'accueil. Cette vidéo n'appartient pas
au pack d'effets sonores CC0.
