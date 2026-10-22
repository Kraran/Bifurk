# Cinématique d'accueil

Au lancement depuis `main()`, la fenêtre du jeu est construite mais reste masquée.
`_play_startup_intro` lance le lecteur musical existant, puis la vidéo muette dans
une fenêtre sans bordure maximisée. Le film garde ses proportions et se termine
automatiquement ; un clic ou une touche permet de le passer immédiatement.

Le filtre d'événements de `IntroVideoDialog` consomme cette entrée, y compris pour
la surface vidéo native : le clic ne doit pas valider un emplacement de sauvegarde
ou déclencher une commande du jeu. La fenêtre principale ne s'affiche qu'à la fin, en plein écran,
puis ouvre son menu initial habituel. F11 ou le bouton dédié permettent de revenir
en fenêtre normale. Le démarrage sans vidéo suit le même affichage plein écran.

La vidéo possède son propre QMediaPlayer **sans QAudioOutput**. La musique reste
pilotée par l'unique `IntroMusic` de la fenêtre principale : aucune pause, remise
à zéro ou transition de volume n'a lieu à la fin de la vidéo. Le démarrage de
l'aventure ou le chargement d'une sauvegarde conserve le fondu de dix secondes
existant et le volume mémorisé par le joueur.

La fin naturelle, une erreur média, la fermeture et le passage volontaire nettoient
le filtre, le lecteur et sa source. Un délai de secours de vingt secondes évite
un blocage du menu en cas de backend défaillant. Une vidéo absente et les plateformes
de test sans écran accèdent directement au menu. `MainWindow(startup=True)` garde
son parcours de menu direct pour les tests de session ; la cinématique de production
est lancée explicitement par `main()`.

La ressource et sa commande d'optimisation sont décrites dans
`assets/video/README.md`. Le dossier assets est déjà embarqué par le spec PyInstaller ;
le contrôle de distribution exige aussi le film. Aucune compilation Windows n'est
nécessaire pour les tests de cycle de vie, regroupés dans `tests/test_intro_video.py`.
