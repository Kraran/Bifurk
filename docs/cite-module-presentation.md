# La Cité des Voleurs — module et présentation

Les phases 1 et 2 ajoutent l'identité du troisième livre, sa consultation et le
catalogue des renvois relus ; les phases 3.1 à 3.4 rendent jouables les
événements des §1 à 400. Rien n'est présenté comme jouable avant vérification.

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
Depuis la phase 7, la Cité a son annonce sonore et son décor de lecture
(`assets/sounds/book_cite.wav`, `assets/cite.jpg`), fournis par Franck.

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
- renvois corrigés d'après l'édition originale anglaise (VO), qui fait référence
  en cas de litige : §81 → 304, §112 → 334, §113 → 375, §145 → 24, §168 → 359 et
  §182 → 354 (le PDF ne permet pas de savoir si l'erreur est imprimée ou due à
  la reconnaissance) ;
- valeurs alignées sur la VO là où la traduction diverge : §8 (+2 Chance), §37
  (+2 Chance au lieu d'Endurance), §137 (−2 Chance au lieu d'Endurance après la
  volée), §293 (une pièce d'armure au lieu d'une arme) ;
- coquilles typographiques (tirets « ŕ », mots coupés ou mal reconnus).

Les conjectures OCR (§1, §73, §109, §119, §180, §342) et la valeur ambiguë du
§217 (second Chien de Lune 11/9) sont résolues, par l'exemplaire papier (§1) ou
la VO, et consignées dans `source_issues`.

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
§387 (traités en phase 3.4) ; les dés du §206, la créature du §201 et les §279 et §293 sont
traités en phase 3.3.

## Phase 3.3 : événements des §201 à 300

La tranche analysée s'étend aux §1 à 300 (`analysed_range` [1, 300]), avec les
mêmes principes.

- **Effets d'arrivée** : nuit de repos et arc en bois d'if du §201, or trouvé
  (§209, §274, §295), amende de tout l'or et Chance −2 au §221, pierres précieuses
  vendues 9 Pièces d'Or au §240, blessures (§242, §243, §298), broche en or du §273,
  tatouage au front du §279 (une marque, hors du sac depuis la phase 4 ; comptée pour les préparatifs).
- **§201** : choix des deux ingrédients du mélange (un objet « Mélange » s'ajoute,
  les ingrédients restent) ; au §244, seule la mixture préparée est proposée.
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
  Endurance +2, une fois) ; fleur dorée du §293 contre un objet magique, une pièce d’armure ou
  deux portions de Provisions.
- **Combats** : §201, §207, §217, §225, §226 (fuite vers le §78), §230, §249, §253
  (morsures de 4 points), §270, §296.
- **Renvois** : prix du texte (§222, §276→267, §300 avec Chance −2, §342) ; or à
  montrer sans paiement (§276→109) ; Provisions remises (§264) ; conditions
  d'objets (§257, §258, §259, §263, §265, §290, §292) ; préparatifs du §239 ; renvois
  « pas encore visité » (§204, §209, §273, §284).
- **Fins** : §210, §288 et §299.

Les pétales de la fleur dorée ne comptent qu'au seul paragraphe qui en parle :
le renvoi §184→55 exige les fleurs d'or, et l'arrivée au §55 les change en
10 Pièces d'Or (la fleur quitte le sac).

## Phase 3.4 : événements des §301 à 400

Tout le livre est analysé (`analysed_range` [1, 400]). Chaque route, valeur,
prix et effet a été vérifié sur l'édition anglaise (VO), qui fait référence en
cas de litige : aucune nouvelle divergence n'est apparue dans cette tranche (les
écarts suspectés relevaient de l'OCR de la VO et ont été relus sur la page).

- **Effets d'arrivée** : blessures (§305, §330, §366, §373, §379), soins (§325,
  §380), or trouvé (§306, §322, §324, §328, §340, §359, §397) et prix payés (§341,
  §364, au plus l'or possédé), Chance (§332, §338, §340, §376, §395), objets reçus
  (laissez-passer, chouette en or, pierres précieuses, clef en fer, bottes
  magiques, boucliers, casque magique, broche scorpion de cuivre…), Habileté
  (§362, §365, §373, §374, §387 ; gain plafonné au score initial), objets en
  argent fondus au §343.
- **Boucliers et casque** : le Bouclier magnifique (§340) et le Casque magique
  (§376) ajoutent chacun 1 à la Force d'Attaque tant qu'ils sont dans le sac.
- **§354, prêteur sur gages** : ventes facultatives et répétables aux prix du
  texte (gobelet 8, passe-partout 15, broche scorpion 10, anneau 12, bracelet 5,
  casque 7, flûte 5, bandeau, osselets et miroir 1) ; les objets verrouillés ne
  se vendent pas. Le renvoi vers le §316 demande 10 Pièces d'Or à montrer.
- **§378, boulet de canon** : un dé chacun, le héros d'abord, jusqu'au premier 1 ;
  celui qui le fait lâche le boulet et paie 5 Pièces d'Or (au plus ce qu'il a).
- **Amendes des §150 et §335** : l'infobulle annonce tout l'or remis ; le §367
  rend la Pièce d'Or que le texte laisse au héros.
- **Combats** : §309, §311 (le premier garde, puis deux gardes à la fois), §323
  (barre incandescente : 3 points par blessure), §326 (deux chiens à la fois, fuite
  vers le §180), §331, §349, §351, §356, §357 (fuite après trois assauts), §361,
  §385, §386, §392 (souffle de feu : un dé par assaut, 1 à 3 brûlent d'un point,
  Chance possible). En combat simultané, des boutons « Cibler » choisissent
  l'adversaire attaqué ; les autres sont seulement parés et blessent s'ils
  l'emportent.
- **Épreuves** : §389 (Habileté), §390 et §391 (Chance).
- **Renvois** : prix du texte (§316→279, §381→261, §394→368) ; conditions d'objets
  (§334, §336, §352, §353, §358) ; article en argent remis au §53 ; préparatifs au
  §367 ; « pas encore visité » (§373, §383).
- **Fins** : §346 (mort) et §400 (victoire, annoncée comme telle). Le livre compte
  11 fins, toutes accessibles depuis le §1 ; l'audit vérifie qu'elles coïncident
  avec celles du moteur.

Interprétations retenues : le gant du §324 n'est pas pris ; la « clef métallique »
du §353 est la clef en fer ; au §343, tous les objets en argent fondent (flèche
d'argent comprise) ; §370 et §387 sans autre effet que ceux imprimés.

## Phase 4 : vente, jeux d'argent, états, quête finale

Relecture transversale des mécaniques déjà posées en phases 3.1 à 3.4, puce par
puce du plan, avec deux changements.

- **États qui ne sont pas des objets** : le tatouage du §279 devient une
  *marque* rangée dans la sauvegarde (`book_state.cite.marks`), jamais dans le sac :
  il ne peut être ni volé, ni vendu, ni donné en paiement, et n'apparaît pas parmi
  les objets. Le message d'arrivée l'annonce (« Marque : Tatouage au front »). Une
  sauvegarde antérieure où il figure dans le sac est migrée à l'ouverture d'un
  paragraphe. La créature du §201 reste mémorisée pour le §138.
- **Marque sur la fiche** : le tatouage s'affiche à droite du nom de
  l'aventurier dès qu'il est acquis, avec l'illustration de Franck (licorne
  blanche cabrée sur un soleil jaune, `assets/marks/cite-tattoo.png`, 256 px à
  fond transparent, rien n'est repris du livre). Elle est réduite une seule fois
  à la taille réelle de l'écran (nette de 100 % à 200 %) ; si le fichier manque,
  un médaillon dessiné au QPainter la remplace. Une infobulle dit ce qu'est la marque selon
  le texte, sans rien révéler de son usage. À l'arrivée au §279 seulement, il
  clignote lentement (trois battements de 1,6 s) ; ouverture d'une sauvegarde,
  annulation et rétablissement l'affichent sans clignoter. Le crochet est
  générique : un module déclare ses marques (`grimoire_modules/marks.py`,
  `SheetMark` : clé, titre, infobulle, dessin de secours, image facultative) et s'inscrit dans `SHEET_MARKS`
  (`grimoire_modules/controller.py`) ; les autres modules n'affichent rien.
- **§244, choix final** : seule la carte de la mixture préparée au §201 est
  affichée (aucune carte grisée, aucune infobulle, aucun indice) ; sans mixture
  enregistrée (ancienne sauvegarde), les trois cartes restent ouvertes.
- **Vente au prix du texte** : §240 (9 Pièces d'Or) et prêteur du §354.
- **Jeux d'argent** : §206, §223 et §378, dés affichés à l'écran, mise et solde
  vérifiés avant chaque partie. Le défi du §398→378 exige de posséder au moins
  5 Pièces d'Or ; sinon la carte est grisée et son infobulle ne cite que la
  condition imprimée (« celui qui laisse tomber le boulet verse 5 Pièces d'Or à
  l'autre »).
- **Variantes de combat** : §157 (Force d'Attaque −3), §253 (morsures de 4),
  §392 (souffle de feu), §10 (victoire en six assauts au plus → §212, sinon §130),
  §140 (fuite après trois assauts), §326 (deux chiens à la fois).
- **Soins et pertes** : dé d'Endurance du §83 et emplâtre du §167 (plafonnés) ;
  armure du §11 ; or et objets volés (§63, §148, §266), tous annulables.
- **Quête finale** : les objets requis sont vérifiés par les renvois écrits
  (§108, §156, §239, §367), sans liste visible.

Aucun nombre caché dans le livre : seuls les §206 et §285 demandent de noter
quelque chose (scores des dés, objets gardés).

## Phase 5 : interface (boutiques, vente, icônes, infobulles)

- **Boutiques sans divulgation** : une fenêtre par boutique (§36, §52, §241…),
  chaque article avec son icône et son prix ; la description dit seulement que
  l'article rejoint le sac à dos et que son usage n'est dit que par le livre
  (aucun chiffre, aucun renvoi). L'or disponible et le prix restent visibles ; la
  règle du livre (« un seul achat possible ici », « chaque article ne s'achète
  qu'une fois ») est dite une seule fois, en tête de la fenêtre, et ferme les
  articles concernés. Au §241, seule boutique où le livre
  permet plusieurs exemplaires, un compteur règle la quantité et le solde affiche
  le total (« 3 × 1 = 3 Pièces d'Or »).
- **Fenêtre de vente** (§354) : symétrique de l'achat. Liste à sélection
  multiple des objets que le prêteur reprend, avec icône et prix offert ; le
  solde annonce la somme reçue, puis une confirmation (« Vendre A et B pour
  N Pièces d'Or ? », boutons Vendre / Garder) précède la vente. Le bruit des
  pièces accompagne le changement d'or ; la vente est annulable.
- **Icônes** : une quarantaine de dessins ajoutés dans `item_icons.py` (anneaux,
  broches, clefs, boucliers, fleurs, argenterie, curiosités…), dans le style des
  autres grimoires ; `item_qicon` fournit la même icône aux fenêtres, nette de
  100 % à 200 %.
- **Infobulles des choix grisés** : la raison cite seulement ce qui manque, tel
  que le livre l'écrit : « il vous faut l'objet indiqué par le livre (…) »,
  « pas assez d'or : il vous faut N Pièces d'Or, vous en avez G (…) ». Jamais de
  destination, de nombre d'usages, ni d'annonce de la suite. Les conditions de
  mission et les conditions négatives gardent la raison générique. Le renvoi
  §354→307 porte la condition imprimée (« Pas de quoi vous offrir le
  tatouage ») ; au §336, l'objet requis est nommé « Pierres précieuses ».
- **Bijoux et curiosités** : tout va dans le sac à dos (aucun emplacement porté).

## Phase 6 : carte des rues et directions

La carte d'exploration (`exploration_map.py`) lit trois données relues du
catalogue, signalé par `"street_map": true` :

- `place` sur chaque paragraphe : la rue, le bâtiment ou le quartier
  (16 valeurs : Porte du Sable Noir, Rue du Port, Rue du Sabot, Rue de l'Écurie,
  Rue de la Tour, Rue du Moulin, Rue du Marché, Rue de la Clef, Rue de l'Horloge,
  Rue de la Bougie, Rue du Pont, Jardin public, Remparts, Égouts,
  Tour de Zanbar Bone, Hors les murs) ;
- `spot` : un même lieu décrit par plusieurs paragraphes selon le sens d'arrivée
  (§30/333, §78/369, §103/196/304, §104/174, §182/316) ;
- `direction` (`nord`, `sud`, `est`, `ouest`) sur 163 renvois : le déplacement
  annoncé par le libellé du choix ou par la phrase du paragraphe qui mène au
  renvoi. Pour une ville, seule cette direction relue place les vignettes ; un
  libellé sans champ `direction` ne déplace rien.

Règles d'affichage :

- seuls les passages visités ont une vignette. La rue y figure en bandeau, au-dessus
  du titre de la scène. Une sortie non visitée reste « § N · non exploré », sans titre,
  rue ni direction ;
- les paragraphes d'un même lieu partagent une vignette (« § 78 · 369 »), placée à la
  première visite. Les allers-retours ne dupliquent ni vignette ni trait : un trait
  à double flèche signale le passage dans les deux sens ;
- une rue d'au moins deux vignettes visitées est encadrée et nommée, si son cadre
  ne chevauche aucune autre rue. L'index regroupe les lieux par rue, et la recherche
  trouve aussi le nom d'une rue ;
- sans direction, une scène se place au plus près du lieu précédent ;
- rien n'est ajouté aux sauvegardes : la carte se reconstruit à partir de
  `visited_paragraphs` et de `transitions`. Les anciennes parties et l'annulation
  fonctionnent donc sans migration. Les autres livres gardent leur carte inchangée.

Tests : `tests/test_exploration_map.py` (`StreetMapTests`) et
`tests/test_place_labels.py` (`CiteStreetCatalogueTests`).

## Phase 7 : annonce sonore, décor et illustrations

- **Couverture** : toujours lue à la volée sur la page 1 du PDF importé, jamais copiée.
- **Annonce sonore** : `assets/sounds/book_cite.wav`, préparée par
  `scripts/prepare_book_sounds.py` comme celles du Sorcier et de la Forêt (silences
  retirés, PCM mono 16 bits 22,05 kHz, −21 dBFS RMS, crête −7,1 dBFS, 1,28 s). Elle
  joue au choix de la couverture et coupe l'annonce précédente ; la case de son
  coupé est respectée. Le script ne traite que les sources présentes et fusionne
  le manifeste `book_sounds.json` : les autres annonces restent identiques.
- **Décor** : `assets/cite.jpg` (JPEG 1152 × 1728, même format que `foret.jpg`,
  fichier fourni sans réencodage) remplit la scène lorsqu'un paragraphe n'a pas
  d'illustration. `main.BOOK_BACKGROUNDS` associe chaque adaptateur à son décor ;
  le Sorcier garde le décor neutre et la Forêt le sien.
- **Illustrations** (`catalogues/cite_voleurs_1983.json`, schéma 6) : chacune des
  85 images du PDF est cataloguée (page, rectangle, statut, paragraphes).
  - 23 illustrations pleine page portent le numéro du paragraphe dans leur légende
    (`verifie_legende`) ;
  - celle de la page 64, sans légende, est insérée dans le texte du §113
    (`verifie_position`) ;
  - trois pleines pages sans légende (pages 56, 72 et 86) sont associées aux
    §88, 135 et 171 d'après la scène représentée (`probable`, affichées avec la
    mention « association probable ») ;
  - la feuille d'aventure (page 5) et 56 vignettes et ornements restent hors des
    popups (`hors_paragraphe`).
  Une illustration n'apparaît qu'en arrivant à son paragraphe : rien n'est dévoilé
  à l'avance.
- **Ambiance de ville** : aucune boucle d'ambiance supplémentaire n'est ajoutée.

Tests : `tests/test_cite_phase7.py` (catalogue, contrôle de chaque image sur le PDF
privé s'il est présent, annonce, décor) et `tests/test_windows_distribution.py`
(ressources exigées dans l'archive Windows).

## Fichiers et validation

- `catalogues/modules/cite_voleurs_1983.json` : manifeste, pages et ressources initiales.
- `catalogues/cite_voleurs_1983.json` : couverture, illustrations et ornements.
- `assets/cite.jpg`, `assets/sounds/book_cite.wav` : décor et annonce sonore.
- `catalogues/evenements_cite_1983.json` : catalogue des 400 paragraphes et de leurs renvois.
- `grimoire_modules/cite/controller.py` : navigation, garde des renvois et rendu.
- `grimoire_modules/cite/rules.py`, `encounters.py`, `feedback.py`, `actions.py` :
  règles pures, combats, comptes rendus et actions de la tranche analysée.
- `pdf_text_repairs.py` : réparations `cite-ocr-1983`.
- `tools/audit_cite.py` : audit du catalogue, avec contrôle optionnel du PDF privé.
- `tests/test_cite_errata.py`, `tests/test_cite_analysis.py` : réparations, audit
  et liens de lecture.
- `tests/test_cite_mechanics.py`, `tests/test_cite_phase3_2.py`,
  `tests/test_cite_phase3_3.py`, `tests/test_cite_phase3_4.py` : règles des §1 à 400, cohérence des tables avec le catalogue et scénarios d'interface sans divulgation.
- `tests/test_boutique_sacoche_alerte.py`, `tests/test_infobulle_choix.py`,
  `tests/test_icones_objets.py` : boutiques, vente, raisons des choix grisés et
  icônes des objets de la Cité.
- `exploration_map.py`, `tests/test_exploration_map.py`, `tests/test_place_labels.py` :
  carte des rues, lieux partagés et directions relues.
- `tests/test_cite_presentation.py` : reconnaissance, couverture, prologue, profil,
  repas, consultation sans effets, sauvegarde et changement de module.

Les scénarios d'interface utilisent des PDF synthétiques. Un contrôle conditionnel
reconnaît également le PDF privé s'il est présent et vérifie son cadrage. Le
contrôle de l'archive Windows exige les trois ressources de catalogue du module,
le décor et l'annonce sonore.
