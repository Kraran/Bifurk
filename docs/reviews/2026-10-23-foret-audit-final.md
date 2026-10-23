# Forêt : audit final de l’intégration

Revue des 400 analyses du catalogue, rapprochées du moteur ; relecture du PDF et
reproduction Qt ciblées sur les écarts. La présence d’un gestionnaire ne prouve
pas que toutes les règles du passage sont exécutées. Les constats initiaux
sont conservés avec le résultat des correctifs.

## Bilan

- 400 paragraphes classés ; 641 renvois recensés.
- PDF exact contrôlé : oui.
- 222 paragraphes ont un point d’entrée dans le moteur, et 222 dans le registre.
- Les classes portent sur les règles connues de chaque analyse, pas sur un pourcentage d’achèvement.

- couvert : 222.
- narratif : 178.

## Constats et correctifs

### F01 — Test de Chance absent après le Bandeau

Paragraphes : §158.

Observation initiale : Le bouton consomme le Bandeau mais ne lance aucun dé, ne dépense aucune Chance et laisse les routes 47 et 353 ouvertes ensemble. Reproduction Qt : 0 jet, 0 Chance dépensée après le bouton d’entrée. Le PDF demande Tenter sa Chance.

Résultat (corrige) : Usage du Bandeau et test de Chance atomiques, issue unique persistante ; réussite, échec, sauvegarde et annulation testés.

### F02 — Trois prises d’objets sans commande

Paragraphes : §146, §152, §242.

Observation initiale : Aucun bouton de prise n’est proposé : morceau de pierre facultatif (§146), couronne récupérée sans la porter (§152), lingot de valeur 28 Or contre abandon d’un objet (§242). Le PDF confirme les trois prises ; le lecteur conserve actuellement l’inventaire inchangé.

Résultat (corrige) : Pierre facultative, couronne recueillie sans port, lingot facultatif contre un objet retirable ; aucun crédit de 28 pièces.

### F03 — Historique du coffre et du tonneau incomplet

Paragraphes : §201, §215, §248, §293, §389.

Observation initiale : Les routes 201/248 → 389 restent ouvertes après destruction du coffre. La route 389 → 215 reste ouverte après examen du tonneau. Les gains de 389 et 248 sont déjà uniques : le défaut porte sur les choix et l’état d’examen, pas sur une duplication d’or démontrée.

Résultat (corrige) : Examen du tonneau indépendant de la prise du bouclier, coffre ouvert identifié par son effet unique ; routes filtrées dans les deux ordres.

### F04 — Essais du gantelet et de l’anneau reproposés

Paragraphes : §133, §374.

Observation initiale : Après les deux essais, les routes 133 → 374 et 374 → 133 restent proposées. Le PDF réserve ces choix à un objet non encore essayé. Les objets et bonus ne sont pas réattribués grâce aux marqueurs d’entrée existants.

Résultat (corrige) : Marqueurs d’essai persistants : renvois déjà utilisés fermés, indépendamment de la possession ultérieure.

### F05 — La branche sans clochette reste ouverte avec la clochette

Paragraphes : §191.

Observation initiale : Avec la clochette dans le sac, le lecteur autorise à la fois 184 et 243. Le PDF distingue explicitement si oui / sinon. Seule la condition de la route vers 184 est implémentée.

Résultat (corrige) : Présence et absence de la clochette donnent des routes complémentaires.

### F06 — Quatre renvois non cliquables dans le texte

Paragraphes : §251, §266, §343.

Observation initiale : Après extraction et réparations de l’édition, le parseur ne reconnaît pas 251 → 260, 266 → 129/354 et 343 → 8. Les formulations avec ensuite et vous vous rendrez ne sont pas reconnues. Les destinations du catalogue et les commandes/cartes correspondantes sont présentes.

Résultat (corrige) : Reconnaissance de ensuite et vous vous rendrez ; comparaison des 400 textes avec les 641 renvois du catalogue.

### F07 — Sept situations limites bloquées sans règle inventée

Paragraphes : §12, §14, §178, §218, §328, §358, §370.

Observation initiale : Absence de moyen de paiement (12/14/218), absence de ration (178/328), absence d’arme (358) ou absence d’objet retirable (370). Le moteur refuse l’action sans dépense partielle. Les analyses et le PDF ne donnent pas toutes une issue explicite.

Résultat (corrige) : Décision utilisateur du 23/10/2026 : sorties de secours adaptées. Exceptions explicites et séparées du texte source, sans dette ni blessure ajoutée.

### F08 — Analyses et registre historique à harmoniser

Paragraphes : §70, §94, §136, §164, §248, §308, §352, §394, §400.

Observation initiale : Certaines analyses parlent encore de règles à préciser déjà décidées ou mises en œuvre : épée, bouclier, échange H/Chance, fuite et chute, correction 186 et retrait du colophon. Le devenir physique de la corde attachée et sa récupération restent peu explicites ; l’usage magique unique est déjà appliqué. Le registre omet des conditions d’objets, deux conditions explicites et la chute automatique.

Résultat (documente) : Analyses et registre harmonisés. Le devenir physique de la corde reste non précisé par la source ; son usage magique unique n’est jamais renouvelé.

## Registre réconcilié

Aucun point d’entrée ne manque au registre.

Ces ajouts de décompte ne représentent pas de nouvelles mécaniques à programmer.

## Comparaison des liens extraits

Les liens des 400 textes correspondent aux 641 renvois du catalogue.


## Relevé des 400 paragraphes

| § | Page PDF | Classe | Points d’entrée | Constats |
| --- | --- | --- | --- | --- |
| 1 | 19 | narratif | — | — |
| 2 | 20 | couvert | automatique | — |
| 3 | 20 | couvert | condition | — |
| 4 | 20 | couvert | effet | — |
| 5 | 20 | narratif | — | — |
| 6 | 20 | narratif | — | — |
| 7 | 21 | couvert | combat | — |
| 8 | 21 | narratif | — | — |
| 9 | 22 | couvert | combat | — |
| 10 | 22 | narratif | — | — |
| 11 | 22 | narratif | — | — |
| 12 | 22 | couvert | paiement | F07 |
| 13 | 23 | couvert | effet | — |
| 14 | 23 | couvert | paiement | F07 |
| 15 | 24 | couvert | combat | — |
| 16 | 24 | couvert | condition | — |
| 17 | 26 | couvert | condition | — |
| 18 | 26 | narratif | — | — |
| 19 | 26 | couvert | effet | — |
| 20 | 26 | narratif | — | — |
| 21 | 27 | couvert | effet | — |
| 22 | 27 | couvert | gaz | — |
| 23 | 27 | narratif | — | — |
| 24 | 28 | couvert | effet | — |
| 25 | 28 | narratif | — | — |
| 26 | 28 | narratif | — | — |
| 27 | 29 | narratif | — | — |
| 28 | 29 | couvert | condition | — |
| 29 | 29 | couvert | combat | — |
| 30 | 29 | couvert | effet | — |
| 31 | 30 | narratif | — | — |
| 32 | 31 | couvert | paiement | — |
| 33 | 31 | narratif | — | — |
| 34 | 31 | couvert | commande | — |
| 35 | 31 | couvert | effet | — |
| 36 | 32 | couvert | paiement | — |
| 37 | 32 | narratif | — | — |
| 38 | 32 | narratif | — | — |
| 39 | 34 | couvert | effet | — |
| 40 | 34 | narratif | — | — |
| 41 | 34 | narratif | — | — |
| 42 | 34 | couvert | effet | — |
| 43 | 35 | couvert | combat | — |
| 44 | 35 | couvert | effet | — |
| 45 | 35 | couvert | effet | — |
| 46 | 35 | couvert | effet | — |
| 47 | 36 | narratif | — | — |
| 48 | 36 | couvert | commande | — |
| 49 | 36 | couvert | combat | — |
| 50 | 38 | couvert | effet | — |
| 51 | 38 | narratif | — | — |
| 52 | 38 | couvert | commande | — |
| 53 | 38 | couvert | effet | — |
| 54 | 39 | narratif | — | — |
| 55 | 39 | couvert | effet | — |
| 56 | 39 | narratif | — | — |
| 57 | 40 | couvert | epreuve | — |
| 58 | 41 | couvert | effet | — |
| 59 | 41 | narratif | — | — |
| 60 | 41 | couvert | commande | — |
| 61 | 41 | narratif | — | — |
| 62 | 42 | narratif | — | — |
| 63 | 42 | narratif | — | — |
| 64 | 42 | couvert | effet | — |
| 65 | 42 | narratif | — | — |
| 66 | 43 | narratif | — | — |
| 67 | 43 | narratif | — | — |
| 68 | 43 | couvert | effet | — |
| 69 | 43 | narratif | — | — |
| 70 | 45 | couvert | effet | F08 |
| 71 | 45 | couvert | combat | — |
| 72 | 46 | narratif | — | — |
| 73 | 46 | couvert | commande | — |
| 74 | 46 | couvert | effet | — |
| 75 | 46 | narratif | — | — |
| 76 | 47 | narratif | — | — |
| 77 | 47 | narratif | — | — |
| 78 | 47 | couvert | effet | — |
| 79 | 47 | couvert | combat | — |
| 80 | 48 | narratif | — | — |
| 81 | 48 | couvert | epreuve | — |
| 82 | 48 | couvert | condition | — |
| 83 | 48 | couvert | effet | — |
| 84 | 48 | couvert | combat | — |
| 85 | 49 | narratif | — | — |
| 86 | 49 | narratif | — | — |
| 87 | 49 | narratif | — | — |
| 88 | 49 | narratif | — | — |
| 89 | 50 | couvert | paiement | — |
| 90 | 50 | couvert | epreuve | — |
| 91 | 52 | couvert | effet | — |
| 92 | 52 | couvert | condition | — |
| 93 | 53 | narratif | — | — |
| 94 | 53 | couvert | effet | F08 |
| 95 | 53 | couvert | condition | — |
| 96 | 53 | couvert | combat | — |
| 97 | 54 | narratif | — | — |
| 98 | 54 | couvert | commande | — |
| 99 | 55 | narratif | — | — |
| 100 | 55 | couvert | effet | — |
| 101 | 55 | couvert | effet | — |
| 102 | 56 | narratif | — | — |
| 103 | 56 | narratif | — | — |
| 104 | 56 | couvert | combat | — |
| 105 | 57 | narratif | — | — |
| 106 | 58 | couvert | effet | — |
| 107 | 58 | couvert | combat | — |
| 108 | 60 | couvert | effet | — |
| 109 | 60 | narratif | — | — |
| 110 | 60 | narratif | — | — |
| 111 | 61 | couvert | effet | — |
| 112 | 61 | narratif | — | — |
| 113 | 61 | narratif | — | — |
| 114 | 61 | couvert | condition | — |
| 115 | 62 | narratif | — | — |
| 116 | 62 | couvert | effet | — |
| 117 | 62 | couvert | combat | — |
| 118 | 62 | couvert | combat | — |
| 119 | 63 | narratif | — | — |
| 120 | 63 | couvert | condition | — |
| 121 | 63 | narratif | — | — |
| 122 | 64 | narratif | — | — |
| 123 | 64 | couvert | combat | — |
| 124 | 64 | narratif | — | — |
| 125 | 64 | narratif | — | — |
| 126 | 65 | couvert | condition | — |
| 127 | 65 | couvert | paiement | — |
| 128 | 65 | couvert | combat | — |
| 129 | 66 | couvert | effet | — |
| 130 | 66 | couvert | cout_route | — |
| 131 | 66 | narratif | — | — |
| 132 | 66 | couvert | condition | — |
| 133 | 67 | couvert | condition, effet | F04 |
| 134 | 67 | couvert | effet | — |
| 135 | 67 | narratif | — | — |
| 136 | 67 | narratif | — | F08 |
| 137 | 67 | couvert | condition | — |
| 138 | 68 | couvert | condition | — |
| 139 | 68 | narratif | — | — |
| 140 | 68 | narratif | — | — |
| 141 | 69 | couvert | effet | — |
| 142 | 69 | narratif | — | — |
| 143 | 71 | couvert | effet | — |
| 144 | 71 | narratif | — | — |
| 145 | 71 | couvert | effet | — |
| 146 | 72 | couvert | effet | F02 |
| 147 | 72 | narratif | — | — |
| 148 | 72 | narratif | — | — |
| 149 | 72 | narratif | — | — |
| 150 | 73 | narratif | — | — |
| 151 | 73 | narratif | — | — |
| 152 | 73 | couvert | effet | F02 |
| 153 | 74 | couvert | combat | — |
| 154 | 74 | couvert | commande | — |
| 155 | 74 | couvert | condition | — |
| 156 | 74 | couvert | automatique | — |
| 157 | 75 | narratif | — | — |
| 158 | 75 | couvert | epreuve | F01 |
| 159 | 75 | couvert | effet | — |
| 160 | 76 | couvert | condition | — |
| 161 | 78 | narratif | — | — |
| 162 | 78 | narratif | — | — |
| 163 | 78 | couvert | effet | — |
| 164 | 78 | narratif | — | F08 |
| 165 | 79 | couvert | combat | — |
| 166 | 79 | couvert | effet | — |
| 167 | 79 | couvert | combat | — |
| 168 | 80 | narratif | — | — |
| 169 | 80 | couvert | gaz | — |
| 170 | 80 | couvert | condition | — |
| 171 | 81 | narratif | — | — |
| 172 | 81 | couvert | condition | — |
| 173 | 81 | couvert | condition, effet | — |
| 174 | 82 | couvert | effet | — |
| 175 | 82 | narratif | — | — |
| 176 | 82 | couvert | effet | — |
| 177 | 83 | narratif | — | — |
| 178 | 83 | couvert | commande | F07 |
| 179 | 84 | couvert | effet | — |
| 180 | 84 | narratif | — | — |
| 181 | 84 | couvert | combat | — |
| 182 | 86 | couvert | commande | — |
| 183 | 86 | couvert | effet | — |
| 184 | 86 | couvert | effet | — |
| 185 | 87 | narratif | — | — |
| 186 | 87 | couvert | combat | — |
| 187 | 87 | narratif | — | — |
| 188 | 88 | narratif | — | — |
| 189 | 88 | narratif | — | — |
| 190 | 88 | narratif | — | — |
| 191 | 88 | couvert | condition | F05 |
| 192 | 89 | couvert | commande | — |
| 193 | 89 | couvert | combat | — |
| 194 | 89 | couvert | effet | — |
| 195 | 90 | narratif | — | — |
| 196 | 90 | couvert | condition | — |
| 197 | 91 | couvert | condition | — |
| 198 | 91 | narratif | — | — |
| 199 | 91 | couvert | condition, cout_route | — |
| 200 | 92 | couvert | effet | — |
| 201 | 92 | couvert | condition | F03 |
| 202 | 92 | couvert | effet | — |
| 203 | 92 | couvert | combat | — |
| 204 | 93 | couvert | commande, condition | — |
| 205 | 93 | couvert | effet | — |
| 206 | 93 | narratif | — | — |
| 207 | 93 | narratif | — | — |
| 208 | 94 | narratif | — | — |
| 209 | 94 | narratif | — | — |
| 210 | 94 | narratif | — | — |
| 211 | 94 | couvert | effet | — |
| 212 | 96 | couvert | combat | — |
| 213 | 96 | narratif | — | — |
| 214 | 96 | couvert | effet | — |
| 215 | 97 | couvert | automatique | F03 |
| 216 | 97 | narratif | — | — |
| 217 | 97 | couvert | effet | — |
| 218 | 97 | couvert | paiement | F07 |
| 219 | 98 | couvert | commande, effet | — |
| 220 | 98 | narratif | — | — |
| 221 | 98 | narratif | — | — |
| 222 | 98 | couvert | gaz | — |
| 223 | 99 | couvert | effet | — |
| 224 | 99 | narratif | — | — |
| 225 | 99 | narratif | — | — |
| 226 | 100 | narratif | — | — |
| 227 | 100 | couvert | combat | — |
| 228 | 100 | couvert | effet | — |
| 229 | 100 | couvert | epreuve | — |
| 230 | 102 | narratif | — | — |
| 231 | 102 | couvert | combat | — |
| 232 | 103 | couvert | effet | — |
| 233 | 103 | narratif | — | — |
| 234 | 103 | narratif | — | — |
| 235 | 103 | couvert | effet | — |
| 236 | 104 | narratif | — | — |
| 237 | 104 | couvert | condition, effet | — |
| 238 | 104 | narratif | — | — |
| 239 | 104 | narratif | — | — |
| 240 | 104 | couvert | condition | — |
| 241 | 105 | couvert | combat | — |
| 242 | 105 | couvert | commande | F02 |
| 243 | 105 | couvert | condition, cout_route | — |
| 244 | 105 | narratif | — | — |
| 245 | 106 | narratif | — | — |
| 246 | 106 | couvert | condition | — |
| 247 | 106 | narratif | — | — |
| 248 | 106 | couvert | condition, effet | F03, F08 |
| 249 | 107 | narratif | — | — |
| 250 | 107 | couvert | effet | — |
| 251 | 107 | couvert | epreuve | F06 |
| 252 | 107 | narratif | — | — |
| 253 | 109 | narratif | — | — |
| 254 | 109 | narratif | — | — |
| 255 | 109 | narratif | — | — |
| 256 | 109 | couvert | epreuve | — |
| 257 | 109 | couvert | effet | — |
| 258 | 110 | couvert | effet | — |
| 259 | 110 | couvert | commande | — |
| 260 | 110 | narratif | — | — |
| 261 | 111 | couvert | commande | — |
| 262 | 113 | couvert | commande, effet | — |
| 263 | 114 | narratif | — | — |
| 264 | 114 | narratif | — | — |
| 265 | 114 | couvert | combat | — |
| 266 | 116 | couvert | commande | F06 |
| 267 | 116 | narratif | — | — |
| 268 | 116 | couvert | effet | — |
| 269 | 117 | couvert | effet | — |
| 270 | 117 | narratif | — | — |
| 271 | 117 | couvert | condition | — |
| 272 | 118 | narratif | — | — |
| 273 | 118 | couvert | effet | — |
| 274 | 118 | narratif | — | — |
| 275 | 118 | couvert | effet | — |
| 276 | 119 | couvert | combat | — |
| 277 | 120 | couvert | effet | — |
| 278 | 120 | couvert | commande | — |
| 279 | 121 | couvert | paiement | — |
| 280 | 121 | narratif | — | — |
| 281 | 121 | narratif | — | — |
| 282 | 121 | narratif | — | — |
| 283 | 121 | couvert | effet | — |
| 284 | 122 | narratif | — | — |
| 285 | 122 | couvert | combat | — |
| 286 | 124 | couvert | combat | — |
| 287 | 124 | couvert | effet | — |
| 288 | 124 | narratif | — | — |
| 289 | 125 | narratif | — | — |
| 290 | 125 | couvert | combat | — |
| 291 | 125 | narratif | — | — |
| 292 | 126 | narratif | — | — |
| 293 | 126 | couvert | condition | F03 |
| 294 | 127 | narratif | — | — |
| 295 | 127 | couvert | condition | — |
| 296 | 127 | narratif | — | — |
| 297 | 129 | couvert | paiement | — |
| 298 | 129 | couvert | combat | — |
| 299 | 129 | couvert | effet | — |
| 300 | 130 | narratif | — | — |
| 301 | 130 | couvert | commande | — |
| 302 | 130 | couvert | effet | — |
| 303 | 131 | couvert | combat | — |
| 304 | 131 | couvert | commande | — |
| 305 | 131 | couvert | effet | — |
| 306 | 132 | narratif | — | — |
| 307 | 132 | narratif | — | — |
| 308 | 132 | couvert | commande | F08 |
| 309 | 133 | couvert | commande | — |
| 310 | 133 | couvert | combat | — |
| 311 | 133 | couvert | effet | — |
| 312 | 134 | couvert | effet | — |
| 313 | 134 | narratif | — | — |
| 314 | 134 | narratif | — | — |
| 315 | 134 | narratif | — | — |
| 316 | 135 | narratif | — | — |
| 317 | 135 | couvert | combat | — |
| 318 | 135 | narratif | — | — |
| 319 | 135 | couvert | condition | — |
| 320 | 137 | narratif | — | — |
| 321 | 137 | narratif | — | — |
| 322 | 137 | couvert | condition, effet | — |
| 323 | 137 | narratif | — | — |
| 324 | 138 | narratif | — | — |
| 325 | 138 | couvert | condition | — |
| 326 | 138 | narratif | — | — |
| 327 | 139 | narratif | — | — |
| 328 | 139 | couvert | commande | F07 |
| 329 | 139 | narratif | — | — |
| 330 | 140 | couvert | combat | — |
| 331 | 140 | narratif | — | — |
| 332 | 141 | narratif | — | — |
| 333 | 141 | couvert | automatique | — |
| 334 | 141 | narratif | — | — |
| 335 | 142 | narratif | — | — |
| 336 | 142 | couvert | condition | — |
| 337 | 142 | narratif | — | — |
| 338 | 143 | couvert | effet | — |
| 339 | 143 | narratif | — | — |
| 340 | 143 | narratif | — | — |
| 341 | 145 | couvert | effet | — |
| 342 | 145 | couvert | condition | — |
| 343 | 145 | couvert | paiement | F06 |
| 344 | 146 | narratif | — | — |
| 345 | 146 | couvert | effet | — |
| 346 | 146 | couvert | condition | — |
| 347 | 146 | couvert | combat | — |
| 348 | 147 | narratif | — | — |
| 349 | 147 | narratif | — | — |
| 350 | 147 | couvert | effet | — |
| 351 | 150 | narratif | — | — |
| 352 | 150 | couvert | combat | F08 |
| 353 | 150 | couvert | effet | — |
| 354 | 151 | couvert | effet | — |
| 355 | 151 | narratif | — | — |
| 356 | 151 | couvert | condition, effet | — |
| 357 | 151 | narratif | — | — |
| 358 | 152 | couvert | commande | F07 |
| 359 | 152 | narratif | — | — |
| 360 | 152 | couvert | condition | — |
| 361 | 154 | narratif | — | — |
| 362 | 154 | narratif | — | — |
| 363 | 154 | narratif | — | — |
| 364 | 154 | narratif | — | — |
| 365 | 155 | couvert | effet | — |
| 366 | 155 | couvert | condition | — |
| 367 | 155 | couvert | condition | — |
| 368 | 156 | narratif | — | — |
| 369 | 156 | narratif | — | — |
| 370 | 156 | couvert | commande | F07 |
| 371 | 156 | couvert | effet, option | — |
| 372 | 157 | couvert | commande | — |
| 373 | 157 | narratif | — | — |
| 374 | 157 | couvert | condition, effet | F04 |
| 375 | 158 | narratif | — | — |
| 376 | 158 | couvert | epreuve | — |
| 377 | 158 | couvert | combat | — |
| 378 | 160 | narratif | — | — |
| 379 | 160 | narratif | — | — |
| 380 | 160 | narratif | — | — |
| 381 | 160 | narratif | — | — |
| 382 | 161 | narratif | — | — |
| 383 | 161 | couvert | effet, option | — |
| 384 | 161 | narratif | — | — |
| 385 | 162 | narratif | — | — |
| 386 | 162 | narratif | — | — |
| 387 | 162 | couvert | effet | — |
| 388 | 162 | couvert | commande | — |
| 389 | 163 | couvert | condition, effet | F03 |
| 390 | 163 | narratif | — | — |
| 391 | 163 | couvert | condition | — |
| 392 | 163 | narratif | — | — |
| 393 | 164 | narratif | — | — |
| 394 | 164 | narratif | — | F08 |
| 395 | 165 | couvert | commande | — |
| 396 | 165 | narratif | — | — |
| 397 | 165 | narratif | — | — |
| 398 | 167 | narratif | — | — |
| 399 | 167 | couvert | automatique | — |
| 400 | 168 | couvert | automatique | F08 |

Reproduction :

```powershell
.\.venv\Scripts\python.exe tools/audit_foret_integration.py --pdf "03. La Foret de la Malediction (1983).pdf"
```

Le [JSON de revue](../../catalogues/revue_integration_foret_1983.json) contient la justification de chaque classement. Les observations
Qt et les extraits de travail restent privés dans audit-output. Aucune compilation.
