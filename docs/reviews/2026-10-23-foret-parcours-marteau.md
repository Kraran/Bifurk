# Forêt : parcours automatisés du marteau

Deux variantes sont vérifiées dans le lecteur Qt par
`test_complete_hammer_quest_by_holy_water_or_ghoul_combat`.
Le héros commence avec les maxima légaux (12 Habileté, 24 Endurance,
12 Chance), 30 Or et les provisions de départ. Les dés sont imposés ;
ce contrôle ne mesure pas les chances de réussite d’une partie.

Le parcours commun suit les paragraphes :

```
1 → 261 → 177 → 160 → 8 → 392 → 157 → 337 → 230 → 137 → 55 → 168
→ 117 → 232 → 358 → 40 → 274 → 109 → 124 → 180 → 361 → 86 → 208
→ 99 → 209 → 28 → 52 → 78 → 349 → 291 → 145 → 285 → 388 → 316
→ 198 → 87 → 90 → 210 → 43 → 50 → 188 → 221 → 378 → 67 → 113
→ 149 → 306 → 391 → 200 → 351 → 292 → 95 → 173
```

Il achète le Gant d’Adresse au Lancer et le Brassard de Force. La variante
protégée achète aussi l’Eau Bénite puis suit `173 → 58 → 112` ; l’autre
suit `173 → 227 → 312 → 112` en combattant la Goule.
Les deux se terminent par `112 → 103 → 360 → 279 → 246 → 204 → 400`.

Les interactions passent par les commandes de jeu : achats, combats,
épreuves, mise du bras de fer, effets d’entrée, paiement des Bandits et
remise du marteau. Les objets de quête ne sont pas ajoutés par le test.
Chaque déplacement doit être autorisé par le lecteur. Les combats et les
épreuves qui déplacent automatiquement le lecteur sont également contrôlés.

Des sauvegardes sont rechargées après l’acquisition du manche (§232),
l’emploi de la poudre (§173), le tribut (§279) et la victoire (§400).
La remise finale est annulée puis rétablie. Le bilan vérifie les charges
consommées, la clé conservée, les provisions perdues, les deux parties
authentiques et le solde final : 42 Or avec Eau Bénite, 45 Or sans.
La mise gagnante n’est pas perdue ; les bijoux ne sont pas convertis en or.

Le PDF synthétique fournit le support du lecteur ; les titres et routes
proviennent du catalogue vérifié. L’audit séparé compare les pages sources
au PDF privé. Ces scénarios ne remplacent pas une lecture visuelle sous
Windows, l’exploration des autres branches, ni un audit exhaustif des
conditions encore documentaires. Aucun exécutable n’est compilé.
