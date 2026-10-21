# Le champ de bataille

![Combat et plateaux intégrés](combat-popup.png)

**Combattre / Reprendre le combat**, dans l'onglet Combat & soins, ouvre une
fenêtre dédiée sans réinitialiser l'adversaire préparé par le livre.

- À gauche : les monstres de la rencontre, leurs Habileté et Endurance, leur
  statut et le plateau de dés rouges à points clairs.
- À droite : nom du héros, Habileté, Endurance, Chance et Habileté effective de
  combat, puis les mêmes dés ivoire que ceux des événements.
- Au centre : chronique chronologique des jets, forces d'attaque, dégâts et
  décisions, conservée pendant toute la rencontre, même à plusieurs adversaires.

## Déroulement

Les dés adverses partent automatiquement au début de l'assaut. **Lancer mes dés**
déclenche ceux du héros. Les forces d'attaque et blessures sont calculées par le
moteur existant avec les faces affichées. Si une décision de Chance est possible,
**Tenter ma Chance** et **Sans Chance** apparaissent dans cette même fenêtre.
Les jets de Chance et de protection utilisent le plateau du héros.

La fiche du personnage et les valeurs du combat utilisent le même état : les
blessures, soins ou dépenses de Chance sont répercutés dès leur application.
Le nombre d'assauts, les équipements et les règles particulières restent ceux
du livre. Les actions de fuite, choix de cible ou stratégie sont accessibles
dans le cadre central lorsqu'elles sont autorisées. Si une telle action est
disponible entre deux assauts, **Assaut suivant** permet de reprendre les dés
adverses sans faire disparaître cette possibilité trop rapidement.

Les séquences continuent dans la même fenêtre. **VICTOIRE** est affiché une fois
toute la rencontre gagnée, puis **Continuer l'aventure** rend la main au récit.
Une fuite ou une interruption imposée par le livre ne devient pas artificiellement
une victoire. Si l'Endurance du héros tombe à zéro, **DÉFAITE** s'affiche, puis
la fenêtre laisse place à la page de fin d'aventure après environ 1,8 seconde.

![Victoire finale](combat-victoire.png)

## Revenir au livre

**Revenir au livre**, Échap ou la croix suspendent la fenêtre. Si un assaut est
déjà commencé, il est d'abord terminé avec les dés déjà tirés, sans dépense de
Chance facultative : fermer ne permet pas d'éviter une blessure ou de relancer.
La fenêtre peut ensuite être rouverte et garde sa chronique dans la session
courante. La suspension visuelle n'est pas une fuite et n'affranchit pas des
restrictions de passage du livre.

Une nouvelle partie, une autre rencontre ou une restauration par Undo / chargement
abandonnent cette chronique visuelle pour ne pas conserver des coups qui ne
correspondent plus à l'état restauré. Les sauvegardes de jeu gardent leur format.

## Maintenance et tests

`CombatDialog` ne remplace pas le moteur. Il appelle `MainWindow.combat_round`,
toujours suivi par `_track_action` : un assaut complet, y compris ses phases
particulières, reste une seule action annulable et autosauvegardée.

`_combat_dialog` désigne la vue active uniquement pendant son `exec`. `_roll`
y présente les jets au lieu d'ouvrir `DiceDialog`. Un `QEventLoop` local attend
la fin du mouvement ou le clic requis, tout en laissant Qt afficher les changements.
Le hasard est consommé uniquement par le contrôleur ; la vue reçoit les faces.
La couleur et la légende optionnelles de `DiceCanvas` permettent de réutiliser
la même géométrie et les mêmes trajectoires pour les deux camps.

`busy` interdit une deuxième action pendant ces attentes. Les minuteries sont
des enfants Qt du dialogue, arrêtés à la fermeture ; elles ne rappellent pas un
objet C++ détruit. Les actions du livre sont des copies de ses boutons marqués
`combatAction`, reliées à leurs contrôles d'origine. Les règles de coût ou de
disponibilité ne sont donc pas réimplémentées dans la vue.

Les tests couvrent les combats simples, la Chance, la synchronisation de fiche,
les séquences, les groupes de squelettes, le Crocodile, les Piranhas, les monstres
errants, la créature aux paragraphes successifs, le souffle mortel, la fuite,
la fermeture au milieu d'un jet et la reprise de la chronique. Les captures de
cette page utilisent exclusivement une rencontre synthétique, sans texte du PDF.
