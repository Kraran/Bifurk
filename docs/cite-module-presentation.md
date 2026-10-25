# La Cité des Voleurs — module et présentation

Les phases 1 et 2 ajoutent l'identité du troisième livre, sa consultation et le
catalogue des renvois relus. Rien n'est présenté comme jouable avant vérification.

## Édition reconnue

- Module : `cite_voleurs_1983`, adaptateur `cite-1983`.
- Titre : **La Cité des Voleurs**.
- PDF privé fourni : 177 pages, 400 paragraphes retrouvés par l'extracteur.
- SHA-256 : `686607e4c9a86c72d39d3a101f2681df83d71ecba6d858a2f8e062d2f5357616`.
- Couverture : page physique 1 ; cadrage contrôlé dans les limites de la page.
- Règles : pages physiques 4–13.
- Prologue « Les terribles messagers de Zanbar Bone » : pages physiques 14–18.

La couverture, les règles et le prologue sont rendus depuis le PDF importé par
le joueur. Aucun PDF, texte narratif ou pixel extrait du livre n'est distribué.
Le décor neutre du thème est utilisé en attendant le décor propre à la Cité ;
l'annonce sonore du livre et ce décor sont livrés en phase 7.

## Parcours dans Bifurk

La bibliothèque **Grimoires…** affiche la couverture et l'état « En préparation ».
Sur la couverture, le joueur retrouve la création commune, l'avis de préparation
et le bouton **Lire le prologue**. Le bouton permanent **Règles** lit les pages
du module courant.

Le profil de départ ajoute les **30 pièces d'or** au matériel commun (épée, armure
de cuir, lanterne, 10 repas et la potion choisie). Le sac à dos est représenté par
la sacoche de la fiche, sans emplacement séparé ; les bijoux trouvés iront dans
l'inventaire. Un repas peut être pris à tout moment hors combat (règles, page
physique 9), un seul par passage tant que le héros ne s'est pas déplacé.

## État des règles de l'aventure

Phase 2 : `catalogues/evenements_cite_1983.json` catalogue les **400 paragraphes**
(statut `renvois_verifies`) avec un titre neutre, le mode (`choix`, `suite` ou
`fin`), la page source du PDF et les **671 renvois** relus, chacun avec un libellé
rédigé et, le cas échéant, la condition imprimée résumée dans `condition_text`.
Ces conditions sont descriptives : `analysis_contract` interdit toute exécution.

Le lecteur affiche le titre du passage et une carte par renvoi du catalogue ; la
condition apparaît en infobulle « Condition du livre : … ». Un nombre du récit qui
n'est pas un renvoi catalogué n'est jamais un lien, et une destination absente du
PDF importé est grisée. L'adaptateur hérite du socle Défis Fantastiques mais pas
des contrôleurs du Sorcier ou de la Forêt, dont les numéros de paragraphes
désignent d'autres scènes. Aucune condition ni aucun effet n'est appliqué ; les
combats restent fermés. Les événements seront intégrés en phase 3, par tranches de
100 paragraphes.

### Réparations du texte extrait (`cite-ocr-1983`)

Réservées au SHA-256 de l'édition, elles ne remplacent que des caractères mal
reconnus et ne citent aucun passage :

- mots de renvoi illisibles aux §110, §258 et §262 (« ai », « an », « »u » → « au ») ;
- deux chiffres mal lus, déduits de paragraphes autrement inaccessibles et de
  l'enchaînement exact du récit : §168 → 359 et §182 → 354 — **à confirmer sur un
  exemplaire papier** ;
- coquilles typographiques (tirets « ŕ », mots coupés ou mal reconnus).

Les conjectures OCR restantes (§1, §73, §119, §180, §342) et les valeurs illisibles
ou ambiguës (§109, §217) sont listées dans `source_issues` pour la phase 3.

### Audit

`python tools/audit_cite.py [--pdf chemin]` vérifie la couverture, les modes, les
libellés, l'absence de doublon, d'orphelin et de paragraphe inaccessible depuis le
§1. Avec `--pdf`, il contrôle aussi l'empreinte, la page de chaque en-tête et
l'égalité des renvois du texte réparé avec le catalogue. Sa sortie ne contient que
des numéros.

## Fichiers et validation

- `catalogues/modules/cite_voleurs_1983.json` : manifeste, pages et ressources initiales.
- `catalogues/cite_voleurs_1983.json` : association de couverture.
- `catalogues/evenements_cite_1983.json` : catalogue des 400 paragraphes et de leurs renvois.
- `grimoire_modules/cite/controller.py` : navigation de consultation sans automatismes.
- `pdf_text_repairs.py` : réparations `cite-ocr-1983`.
- `tools/audit_cite.py` : audit du catalogue, avec contrôle optionnel du PDF privé.
- `tests/test_cite_errata.py`, `tests/test_cite_analysis.py` : réparations, audit
  et liens de lecture.
- `tests/test_cite_presentation.py` : reconnaissance, couverture, prologue, profil,
  repas, consultation sans effets, sauvegarde et changement de module.

Les scénarios d'interface utilisent des PDF synthétiques. Un contrôle conditionnel
reconnaît également le PDF privé s'il est présent et vérifie son cadrage. Le
contrôle de l'archive Windows exige les trois ressources de catalogue du module.
