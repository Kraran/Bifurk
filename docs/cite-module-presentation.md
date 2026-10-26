# La Cité des Voleurs — module et présentation

Les phases 1 et 2 ajoutent l'identité du troisième livre, sa consultation et le
catalogue des renvois relus ; les phases 3.1, 3.2 et 3.3 rendent jouables les
événements des §1 à 300. Rien n'est présenté comme jouable avant vérification.

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

Les conjectures OCR restantes (§119, §180, §342 ; les §1 et §73 sont résolus en
phase 3.1) et les valeurs illisibles
ou ambiguës (§109, §217) sont listées dans `source_issues` pour la phase 3.

### Audit

`python tools/audit_cite.py [--pdf chemin]` vérifie la couverture, les modes, les
libellés, l'absence de doublon, d'orphelin et de paragraphe inaccessible depuis le
§1. Avec `--pdf`, il contrôle aussi l'empreinte, la page de chaque en-tête et
l'égalité des renvois du texte réparé avec le catalogue. Sa sortie ne contient que
des numéros.

## Phase 3.1 : événements des §1 à 100

Les §1 à 100 passent au statut `analyse_verifiee`, avec une note `analysis`
rédigée (combat, épreuve, effet d'arrivée, achats, événement, renvoi conditionnel,
fin ou récit). Le catalogue reste descriptif : les règles vivent dans
`grimoire_modules/cite/` et `analysis_contract.analysed_range` borne la tranche.

- **Effets d'arrivée** (`rules.ENTRY_EFFECTS`) : appliqués une seule fois par
  partie, gains plafonnés au total initial ; objets gagnés ou perdus dans
  l'inventaire (pas d'emplacement Bijoux). La cotte de mailles donne +2 en
  Habileté tant qu'elle est portée.
- **Épreuves** de Chance ou d'Habileté : bouton « Tenter votre Chance (2d6 ≤ X) » ou
  « Épreuve d'Habileté (2d6 ≤ X) » ; les renvois restent grisés jusqu'au jet, puis
  le héros suit le résultat. Aucune destination n'est annoncée.
- **Combats** (`encounters.COMBATS`) : adversaires un à un, renvois fermés jusqu'à
  l'issue ; le garde du §10 change d'issue selon le nombre d'assauts ; fuites des
  §73 et §88 seulement lorsque le livre les autorise (blessure de fuite, Chance
  possible). La broche scorpion d'argent rend 1 point d'Endurance après une victoire.
- **Achats** (§36, §52, §66) aux prix du texte, avec leurs limites ; **renvois
  payants** débités au choix du renvoi, une seule fois ; offre du §248 en or ou en
  objets.
- **Événements** : dé d'Endurance du §83, larcin de l'Elfe au §63 (le joueur
  désigne les objets du sac ; l'équipement porté n'est pas pris).
- **Renvois conditionnels** : objet possédé ou paragraphe déjà visité ; une carte
  grisée n'affiche que la condition imprimée.
- **Fins** (§9, §56, §59, §70) : l'aventure est close ; « Annuler » reste possible.

Chaque action passe par l'historique (Annuler / Rétablir) et laisse un compte rendu
des jets et changements dans le cadre de messages. Hors de la tranche, la lecture
reste en consultation.

## Phase 3.2 : événements des §101 à 200

La tranche analysée s'étend aux §1 à 200 (`analysed_range` [1, 200]), avec les
mêmes principes : fidélité au livre, prix du texte, tout dans l'inventaire, aucune
destination ni événement à venir affiché.

- **Effets d'arrivée** : pertes et trouvailles (lanterne brisée, perles noires,
  passe-partout, anneau de l'Œil d'Or, emplâtre d'herbes, crâne d'ivoire…), or
  confisqué au §134, bouclier maudit verrouillé au §125 (Habileté −1), soins du
  §126 à raison de 2 points par flèche reçue au §137 et échange de l'épée.
- **Épreuves** : §120, §162, §168, §175, §190 (pari au couteau : 5 Pièces d'Or
  perdues en cas d'échec) et §192 (Habileté −1 en cas d'échec) ; double épreuve
  de Chance du §128, issue selon le nombre d'échecs.
- **Événements** : volée de flèches du §137 (un dé, 3 points par flèche puis 2) ;
  larcin du §148 (une Pièce d'Or ou un objet, au choix du joueur) ; tiroir du
  joaillier au §114 (VO « Take what you will » : les 13 Pièces d'Or et les trois
  bagues se gardent au choix, en une fouille) ;
  emplâtre d'herbes utilisable hors combat (un dé d'Endurance, puis consommé).
- **Combats** : §130, §140 (fuite après 3 assauts), §144, §152 et §157 (Force
  d'Attaque −2 et −3), §166, §170 (fuite possible), §177, §191, §193 (pas de
  combat à l'épée avec un Anneau de Feu).
- **Renvois** : prix du texte (herboriste du §183, tatouage du §182, amende du §150
  égale à tout l'or, §315→132 reporté de la phase 3.1…) ; renvois payés par un
  objet (§113 : un objet du sac ; §187 : un anneau, une armure magique ou la potion
  de départ) ; conditions d'objets (§118, §146, §184, §193) ; préparatifs du §108
  et du §156 (quatre objets et le tatouage du §279) : la carte grisée n'affiche
  que la condition imprimée.
- **Fins** : §129 et §142.

Reportés hors tranche : le prêteur sur gages du §354 et les effets des §370 et
§387 (phase 3.4) ; les dés du §206, la créature du §201 et les §279 et §293 sont
traités en phase 3.3.

## Phase 3.3 : événements des §201 à 300

La tranche analysée s'étend aux §1 à 300 (`analysed_range` [1, 300]), avec les
mêmes principes.

- **Effets d'arrivée** : nuit de repos et arc en bois d'if du §201, or trouvé
  (§209, §274, §295), amende de tout l'or et Chance −2 au §221, pierres précieuses
  vendues 9 Pièces d'Or au §240, blessures (§242, §243, §298), broche en or du §273,
  tatouage au front du §279 (objet verrouillé, compté pour les préparatifs).
- **§201** : choix des deux ingrédients du mélange (un objet « Mélange » s'ajoute,
  les ingrédients restent) ; au §244, seule la mixture préparée est praticable.
  Puis un dé désigne la créature du tableau, combattue selon les règles ; le §138
  n'ouvre que le renvoi correspondant à la créature affrontée.
- **Épreuves** : §203 (Chance ; l'échec est une fin imprimée), §214, §229, §247,
  §251, §252, §291 (blessure de 2 points en cas d'échec) ; dé de la pilule du §223
  (le 1 est mortel, sinon 20 Pièces d'Or).
- **Jeu de dés du §206** : mise de 2 Pièces d'Or, deux dés pour chacun des trois
  Nains puis pour le héros ; total supérieur aux trois : +6 ; inférieur à l'un
  d'eux : −2 ; égalité avec le meilleur Nain : mise reprise. Quatre parties au plus.
- **Événements** : bousculade du §266 (deux objets du sac, au choix du joueur) ;
  butins facultatifs des §208, §220 (contenu de la caisse du §146) et §285 ;
  bougies du §241 en nombre illimité ; repas chaud du §287 (1 Pièce d'Or,
  Endurance +2, une fois) ; fleur dorée du §293 contre un objet magique, une arme ou
  deux portions de Provisions.
- **Combats** : §201, §207, §217, §225, §226 (fuite vers le §78), §230, §249, §253
  (morsures de 4 points), §270, §296.
- **Renvois** : prix du texte (§222, §276→267, §300 avec Chance −2, §342) ; or à
  montrer sans paiement (§276→109) ; Provisions remises (§264) ; conditions
  d'objets (§257, §258, §259, §263, §265, §290, §292) ; préparatifs du §239 ; renvois
  « pas encore visité » (§204, §209, §273, §284).
- **Fins** : §210, §288 et §299.

Non automatisé : les pétales de la fleur dorée changés en or au sang de chien
(gérés à la main).

## Fichiers et validation

- `catalogues/modules/cite_voleurs_1983.json` : manifeste, pages et ressources initiales.
- `catalogues/cite_voleurs_1983.json` : association de couverture.
- `catalogues/evenements_cite_1983.json` : catalogue des 400 paragraphes et de leurs renvois.
- `grimoire_modules/cite/controller.py` : navigation, garde des renvois et rendu.
- `grimoire_modules/cite/rules.py`, `encounters.py`, `feedback.py`, `actions.py` :
  règles pures, combats, comptes rendus et actions de la tranche analysée.
- `pdf_text_repairs.py` : réparations `cite-ocr-1983`.
- `tools/audit_cite.py` : audit du catalogue, avec contrôle optionnel du PDF privé.
- `tests/test_cite_errata.py`, `tests/test_cite_analysis.py` : réparations, audit
  et liens de lecture.
- `tests/test_cite_mechanics.py`, `tests/test_cite_phase3_2.py`,
  `tests/test_cite_phase3_3.py` : règles des §1 à 300, cohérence des tables avec le catalogue et scénarios d'interface sans divulgation.
- `tests/test_cite_presentation.py` : reconnaissance, couverture, prologue, profil,
  repas, consultation sans effets, sauvegarde et changement de module.

Les scénarios d'interface utilisent des PDF synthétiques. Un contrôle conditionnel
reconnaît également le PDF privé s'il est présent et vérifie son cadrage. Le
contrôle de l'archive Windows exige les trois ressources de catalogue du module.
