# Introduction de Bifurk

Deux versions du même film, générées le 26 octobre 2026 d'après l'introduction
d'origine (`bifurk.mp4`, fournie par l'utilisateur) et validées par lui :

- `introduction.mp4` : 16:9, 1280 × 720, pour les écrans classiques ;
- `introduction_21x9.mp4` : 21:9, 1680 × 720, même film recadré en haut et en bas
  puis agrandi, joué quand l'écran est au moins deux fois plus large que haut.

Communs : 6,041667 secondes, sans boucle, H.264, YUV 4:2:0, 24 images/s, sans piste
sonore, index MP4 au début pour démarrer la lecture rapidement.

Commandes de préparation (FFmpeg, uniquement pour reconstruire les ressources) :

```sh
ffmpeg -i source.mp4 -map 0:v:0 -an -sn -dn -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -r 24 -movflags +faststart -map_metadata -1 introduction.mp4
ffmpeg -i source.mp4 -map 0:v:0 -an -sn -dn -vf "crop=1280:548:0:96,scale=1680:720:flags=lanczos,setsar=1" -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -r 24 -movflags +faststart -map_metadata -1 introduction_21x9.mp4
```

FFmpeg en ligne de commande n'est pas requis sur le PC du joueur : le film est
lu par Qt Multimedia, comme la musique d'accueil. Ces vidéos n'appartiennent pas
au pack d'effets sonores CC0.
