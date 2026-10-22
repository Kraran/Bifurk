# La Forêt de la Malédiction — revue des 400 paragraphes

La revue couvre les 400 passages de l’édition privée identifiée par le SHA-256
`0abac11c0e88ce244c5513bf4b1537fa46159df5606d3e3c8c28b83e6614f6e1`.
Chaque entrée du catalogue contient un titre local, des libellés de choix,
les conditions exprimées par le livre, une note de mécanique et la page physique
PDF de son en-tête. Les formulations sont des annotations de travail, sans
reproduction du récit. Les 639 routes recensées conservent les numéros du livre.

## Contrat de données

Le statut `analyse_verifiee` désigne une analyse documentaire, pas une règle
exécutable. `verified_entry` continue à refuser ces entrées. Les 400 passages sont
retirés de `review_pending`, mais restent dans `automation_pending`. Aucun effet,
combat, paiement ou dénouement n’est automatisé à cette étape. Le module reste
« en préparation ». Les conditions des choix sont des indications de consultation,
jamais une validation d’inventaire. Les titres ne révèlent que le lieu consulté ;
les boutons décrivent une action, sans emprunter le titre du lieu futur.

## Lots de revue

| Lot | Points à préserver lors de l’implémentation |
| --- | --- |
| 1–50 | Boutique, alternatives de paiement, embranchements, Orques et pénalités sous plafond bas. |
| 51–100 | Tête du marteau, équipement porté, épreuve combinée Habileté/Chance sans dépense de Chance (§73), fuite après trois assauts (§84). |
| 101–150 | Groupes simultanés, fouet du Démon, deux branches de l’Homme-Arbre, objets maudits, ambiguïté de direction (§150). |
| 151–200 | Manche du marteau, bonus d’équipement, Anguille sans données complètes (§186), alternatives au combat du Troll. |
| 201–250 | Paiements et butins partagés, quatre blessures de Goule, malédictions, bouclier et variantes d’accès aux mêmes objets. |
| 251–300 | Achats à usage unique, potion pour deux combats, épreuve de force, renvoi illisible (§267), Pygmées, fièvre après morsure. |
| 301–350 | Flûte, convalescence, double épreuve de Chance, substitution des caractéristiques, repas maudit et capsules de feu. |
| 351–400 | Tribut de cinq unités, échanges, épreuves répétables, retours et coffres persistants, transformations et victoire. |

## Anomalies de source

- **§186, page PDF 87 : blocage.** Le passage s’arrête avant les caractéristiques
  de l’Anguille et sans renvoi de sortie. Contrôle visuel effectué. Ce n’est pas
  une fin d’aventure. Une autre source est nécessaire avant son automatisation.
- **§267, page PDF 116 : blocage.** La référence imprimée est « 1% ».
  Le §196 est une hypothèse plausible, sans confirmation. Ni §1 ni §196 ne sont
  proposés comme correction ; seule l’autre sortie, §25, est navigable.
- **§150 :** les deux directions sont nommées ouest. Les choix sont neutralisés
  lexicalement sans modifier leurs destinations, §357 et §171.
- **§152 :** une phrase est interrompue ; les choix restent lisibles.
- **§91 :** le pouvoir de vérité de l’Œil d’Ambre figure dans une illustration,
  contrôlée visuellement, et serait perdu par une analyse du texte seul.
- **§400 :** l’extraction ajoute le colophon d’impression après la victoire.
  Il faudra l’écarter du récit au moment d’intégrer les fins.

## Décisions de mécanique à implémenter

Les notes par passage constituent la référence détaillée. Les achats et prix
sont aussi recensés dans `shop_analysis` : 17 articles, chacun à usage magique
unique selon le §261. Conserver physiquement un objet ne renouvelle pas sa charge.
Les objets trouvés, les objets portés et les achats doivent rester distincts.
La Perche à Sonder n’a pas de branche d’utilisation identifiée dans les passages.

Les combats groupés §§96/276, 104 et 377 imposent des attaques et parades contre
plusieurs adversaires. Le choix de cible doit pouvoir changer à chaque assaut.
Les §§29 et 317 nécessitent encore de préciser le mode de traitement des deux
adversaires avant de le coder. La Goule compte les blessures reçues, le Loup-Garou
mémorise une blessure même après des soins, et le fouet du Démon ajoute un jet.
Le bouclier du §248 ne reprend pas la règle du bouclier du Sorcier.

Le §309 impose deux épreuves de Chance, même si la première échoue ; le §73
compare un même résultat aux deux caractéristiques sans dépenser de Chance.
Le §372 permet de retenter, avec perte d’Endurance à chaque échec. Les pertes
létales doivent interrompre les choix et épreuves suivants.

Les variantes de butin partagent une identité persistante : coffre, objets de
quête et récompenses ne doivent pas être recrédités en revisitant les lieux.
Le faux manche ne doit jamais valider la quête. La victoire exige les deux
parties gravées G. Les trésors évalués en or ne deviennent pas automatiquement
des pièces. Les paiements alternatifs exigent un choix explicite du joueur.

Restent à préciser lors de l’intégration : la potion de deux combats pour les
séquences/groupes, l’interaction Chance/bouclier, les plafonds d’Habileté de
l’épée, et les cas sans provisions ou sans moyens de paiement. Les notes
signalent ces interprétations plutôt que d’inventer des règles.

## Reproduire les contrôles

```powershell
.\.venv\Scripts\python.exe tools\audit_foret.py
.\.venv\Scripts\python.exe tools\audit_foret.py --pdf "donnees\grimoires\03. La Foret de la Malediction (1983).pdf"
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Le second contrôle exige le PDF privé exact. Il vérifie l’empreinte et les 400
en-têtes/pages sources ; il ne prétend pas vérifier automatiquement le sens des
règles ni résoudre les anomalies imprimées. Aucun PDF ou extrait n’est exporté.
