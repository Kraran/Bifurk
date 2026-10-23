# Forêt : événements souris et échelles Qt

Complément du contrôle natif du 23 octobre 2026. Le pilote Qt `windows` a été
exécuté dans trois processus distincts, avec `QT_SCALE_FACTOR` à `1.25`, `1.5`
et `2`. Les réglages d’affichage de Windows lui-même n’ont pas été modifiés.
Les fenêtres sont rendues sans être affichées sur le bureau.

## Résultats

| Échelle Qt | Captures | Actions souris contrôlées | Avertissements QFont | Empreintes PDF et données |
| --- | ---: | ---: | ---: | --- |
| 125 % | 17 | 9 | 0 | Inchangées |
| 150 % | 17 | 9 | 0 | Inchangées |
| 200 % | 17 | 9 | 0 | Inchangées |

Les captures reprennent la couverture, le départ, la carte, l’Œil d’Ambre,
son agrandissement, le Bandeau aux trois tailles de fenêtre, le lingot,
la couronne, le secours de la fosse et l’état coffre/tonneau. Les caractéristiques
restent entièrement visibles à 930 × 650, 1280 × 800 et 1600 × 900 pixels logiques.
Le défilement permet d’atteindre l’action du Bandeau en petite fenêtre.

Les neuf vérifications par événements souris Qt sont :

- Valider le nom et commencer la partie.
- Suivre le choix vers Yaztromo.
- Fermer l’agrandissement de l’illustration par son bouton.
- Cliquer un renvoi désactivé, sans effet sur l’état ni l’historique.
- Résoudre l’épreuve du Bandeau par son bouton.
- Ouvrir le dialogue du lingot et le fermer par Annuler : inventaire inchangé.
- Recueillir la couronne par son bouton.
- Emprunter la sortie de secours par son bouton.

La ligne « lingot » comporte deux actions souris, d’où neuf au total. Le journal
structuré conserve les actions et les résultats pour chaque échelle.
Un test de régression supplémentaire vérifie les clics de création, de route et
d’épreuve, puis Annuler/Rétablir par les boutons de l’interface : un seul jet,
un seul coût et restauration exacte de l’état. Ce test passe avec les pilotes
`windows` et `offscreen`.

## Reproduction

```powershell
$env:QT_SCALE_FACTOR='1.25'
.\.venv\Scripts\python.exe tools/audit_foret_ui.py --platform windows --display-only
```

Recommencer dans un nouveau processus avec `1.5`, puis `2`. Les captures et le
rapport sont enregistrés dans `audit-output/foret-ui-validation-zoom-<facteur>`,
ignoré par Git. Sans `--display-only`, l’outil conserve son contrôle complet des
deux parcours du marteau.

Ce lot ne modifie aucune règle du livre ni le statut de préparation. Aucun
correctif du moteur n’a été nécessaire. Les échelles Qt ne remplacent pas un
contrôle de la taille physique disponible sur chaque écran, une configuration
à plusieurs moniteurs ou une partie libre avec les événements du bureau.
Les dés restent imposés et les actions de souris sont injectées dans les widgets
par QTest, après défilement pour les rendre visibles. Aucun exécutable compilé.

Le mode complet modifié a aussi été exécuté à 100 % : les neuf vérifications
souris passent, les 19 captures sont produites et les deux parcours de 59/60
passages atteignent toujours le §400. Aucun avertissement QFont ; empreintes
inchangées. La suite générale de 630 tests du lot précédent n’a pas été répétée :
ce complément ne change ni l’interface du jeu ni son moteur, seulement l’outil,
sa documentation et le test supplémentaire, exécuté avec les deux pilotes.
