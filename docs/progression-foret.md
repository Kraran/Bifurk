# La Forêt de la Malédiction — progression au 23 octobre 2026

Les 400 paragraphes ont été analysés et leurs 641 renvois catalogués.
Le module reste en préparation : analyse du livre, intégration d’une mécanique
et validation d’une partie complète sont trois étapes distinctes.

## Fait

Le registre `mechanics_implementation` recense **110 paragraphes distincts avec
au moins une mécanique intégrée**. Ce nombre n’est ni un pourcentage de travail
terminé, ni une affirmation d’automatisation complète de ces paragraphes.
Les catégories se recoupent et n’énumèrent pas tous les liens conditionnels existants.

| Catégorie du registre | Paragraphes |
| --- | ---: |
| Boutique de Yaztromo | 1 |
| Profils de combat | 17 |
| Effets d’entrée et usages d’objets | 53 |
| Paiements | 7 |
| Actions et épreuves spéciales | 31 |
| Conditions de route recensées séparément | 2 (§§191, 295) |

Sont intégrés : achats et charges, équipement et malédiction, paiements choisis,
combats en groupes et successifs, fouet du Démon, paralysie de la Goule,
blessures du Loup-Garou, potion des deux rencontres, bouclier, épreuves particulières,
convalescence, repas maudit, échange des caractéristiques et remise du marteau.

Les derniers lots ajoutent la lanterne et ses conséquences, les Faucons, le Gnome
et la restitution de l’arme, l’épée enchantée avec son bonus équipé de +2 Habileté,
les gaz et filtres, puis les sept épreuves des §§57/81/90/229/251/256/376,
leurs blessures associées et le Troll du §310. Le casque doit être réellement porté
pour éviter la blessure de la chute au §295 ; le §30 enlève deux points une fois.

Le pain elfique du §257 est désormais récupéré avec son point de Chance puis
consommable séparément depuis Soins, hors combat, pour +4 Endurance sous plafond.
Le §184 échange une clochette contre une potion immédiatement bue (+4 Endurance),
sans modifier les doses de départ. Le §191 vérifie la présence de la clochette.

Les commandes intégrées sont raccordées aux sauvegardes et à l’historique.
Les tests vérifient notamment les coûts, la survie, les variantes d’un même butin,
l’absence de répétition, la restauration et l’annulation/rétablissement.

## Reste à faire

- **Autres rencontres** : raccorder leurs profils, issues et restrictions ;
  les 17 passages actuels ne couvrent pas tous les combats du livre.
- **Autres effets** : variations de caractéristiques et de provisions, dons et
  trouvailles encore documentés sans commande. Exemples : §§13, 42, 106, 129,
  145, 166, 174, 219, 237, 243, 299, 301, 353 et 387.
- **Équipement et autres soins** : perte temporaire de l’épée (§358) et sa
  récupération, puis les autres interactions de soins encore documentaires.
- **Choix et parcours** : compléter les conditions d’inventaire et de progression
  encore consultables, puis vérifier les chaînes de passages de bout en bout.
- **Fins et présentation** : compléter les issues finales, retirer le colophon
  du récit au §400 et intégrer les illustrations de cette édition.
- **Validation complète** : jouer des parcours représentatifs, vérifier les
  fenêtres sous Windows et auditer le comportement des sauvegardes en partie.

## Points à clarifier

Le mode de résolution des deux adversaires aux §§29 et 317 doit encore être
confirmé. Aucun mode simultané ou successif n’est automatisé par supposition.
Les cas non décrits par la source restent explicites : sac sans objet retirable
au §370, insolvabilité au §12, et interprétations documentées de certaines interactions.

Les corrections des §§186 et 267 sont confirmées et intégrées. Le choix de bonus
de l’épée du §70 est également confirmé : +2 tant qu’elle est équipée, même
au-delà du total initial.

Le détail des mécaniques, leurs limites et les commandes de test figurent dans
[les mécaniques particulières](foret-mecaniques-particulieres.md).
