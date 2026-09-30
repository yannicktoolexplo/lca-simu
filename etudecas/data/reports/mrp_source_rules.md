# Règles MRP : analyse des sources industrielles et comparaison avec le moteur

Analyse du 28 septembre 2026. **Objectif : reproduire le comportement de la supply chain réelle**, en retrouvant les stocks hebdomadaires, les plans et les décisions compatibles avec les données. Les sections 1–14 décrivent l'audit initial ; la section 15 corrige la comparaison ; la section 16 conserve les essais antérieurs non retenus ; les sections 17–18 rapprochent les prévisions et le carnet initial. **La section 19 décrit la séparation livraison/disponibilité et le calcul des achats par échéance.** La variante à zéro jour est abandonnée comme piste de calibration.

Les deux classeurs apportent des paramètres explicites et des résultats de planification. Ils ne contiennent pas le code du MRP industriel. Le rapport distingue donc les règles écrites, les comportements vérifiés dans les chiffres et les règles qui restent à identifier. Il complète les nomenclatures, délais, capacités, commandes ouvertes et confirmations métier déjà disponibles dans les autres sources.

## Ce que contiennent les fichiers

| Fichier / feuille | Contenu vérifié | Usage correct |
|---|---|---|
| Flow_Data_Inventory_and_Replenishment_rules / Stocks | 1 646 photos, 26 articles, 32 couples article/site, 53 dates | Stocks réels de référence : 1er janvier 2025, puis les 52 lundis |
| Même classeur / Politique de stock MRP | 27 politiques | Délais de sécurité en jours ouvrés et quantités de sécurité, champs séparés |
| Même classeur / Taile de Lot | 4 politiques | Paramètres des lots de fabrication aux sites indiqués |
| Même classeur / Graph | Tableau croisé des stocks de 773474 à Gien et Gaillac | Représentation des mêmes stocks ; aucune règle supplémentaire |
| Flow_Data_MRP_results / Feuille1 | 53 398 lignes, 33 couples article/site, 52 versions de plan | Projections datées ; ce ne sont pas des mouvements tous exécutés |

**Horizon de 52 semaines confirmé.** Les versions vont du 5 janvier au 28 décembre 2025. Chaque version peut projeter jusqu'à 364 jours après sa date. En comptant la semaine courante, cela peut produire **53 dates**. Une projection de décembre 2025 peut donc aller jusqu'en décembre 2026. Les 52 versions ne doivent jamais être additionnées comme des flux annuels.

Toutes les dates de version et de semaine du MRP sont des dimanches. La photo de stock correspondante est généralement celle du lundi suivant. Le jour exact représenté par le libellé de semaine, à l'intérieur du processus ERP, n'est pas documenté.

Les 1 637 plans article/site/date présents ne contiennent pas tous 53 lignes : 1 480 présentent des semaines absentes entre deux lignes. Cela peut résulter d'un export qui omet certaines semaines. **Une absence ne prouve ni un flux nul ni une fin de l'horizon de planification.** La fréquence hebdomadaire de l'export ne prouve pas que le MRP lui-même ne tourne qu'une fois par semaine.

Le fichier Stocks conserve un filtre Excel sur 002612 : 1 540 lignes sont masquées et 106 visibles. L'analyse a lu toutes les lignes. Il ne faut pas limiter l'analyse aux lignes visibles à l'ouverture du classeur.

## 1. Toutes les sécurités et tous les temps de réception

Dans la feuille de politique : E = délai de sécurité, F = quantité de sécurité, G = unité de cette quantité. Dans Feuille1 du MRP : E = « Temps de réception en jours ». Les temps de réception sont constants pour chaque couple article/site dans cet export.

**Les deux colonnes de durée ne représentent pas automatiquement le même mécanisme.** Le calendrier lundi–vendredi des jours de sécurité a été confirmé par l'utilisateur. Le calendrier et les opérations incluses dans le temps de réception restent à préciser : achat, fabrication, transport, réception, contrôle qualité, etc.

| Article | Site | Sécurité : jours ouvrés | Sécurité : quantité, unité source | Temps de réception : jours | Cellules politique |
|---|---|---:|---|---:|---|
| 001757 | Avène (1810) | 20 | 0 G | 13 | E5:G5 |
| 001848 | Gien (1430) | Absente | Non renseignée | 26 | — |
| 001848 | Avène (1810) | 20 | 0 G | 13 | E12:G12 |
| 001893 | Gaillac (1450) | Absente | Non renseignée | 5 | — |
| 001893 | Avène (1810) | 15 | 0 KG | 24 | E7:G7 |
| 002612 | Gaillac (1450) | Absente | Non renseignée | 5 | — |
| 002612 | Avène (1810) | 20 | 0 KG | 9 | E4:G4 |
| 007923 | Gien (1430) | Absente | Non renseignée | 0 | — |
| 007923 | Avène (1810) | 15 | 0 G | 6 | E25:G25 |
| 016332 | Avène (1810) | 7 | 0 G | 1 | E6:G6 |
| 021081 | Gaillac (1450) | 0 | 900 000 KG | 75 | E23:G23 |
| 029313 | Gien (1430) | Absente | Non renseignée | 0 | — |
| 029313 | Avène (1810) | 7 | 0 G | 1 | E13:G13 |
| 038005 | Gien (1430) | 20 | 0 G | 14 | E11:G11 |
| 039668 | Avène (1810) | 7 | 0 G | 1 | E18:G18 |
| 042342 | Gien (1430) | 5 | 0 ZUN | 14 | E22:G22 |
| 049371 | Avène (1810) | 40 | 888 000 G | 9 | E26:G26 |
| 055703 | Avène (1810) | 30 | 0 G | 13 | E10:G10 |
| 099439 | Avène (1810) | 7 | 0 G | 1 | E28:G28 |
| 268091 | Dépôt Muret (1920) | 0 | 0 ZUN | 10 | E3:G3 |
| 268967 | Dépôt Muret (1920) | 60 | 0 ZUN | 15 | E2:G2 |
| 333362 | Gien (1430) | 10 | 110 000 ZUN | 5 | E16:G16 |
| 338928 | Avène (1810) | 10 | 0 ZUN | 6 | E15:G15 |
| 338929 | Avène (1810) | 10 | 0 ZUN | 6 | E24:G24 |
| 344135 | Gien (1430) | 10 | 0 ZUN | 4 | E14:G14 |
| 426331 | Avène (1810) | 10 | 0 ZUN | 1 | E8:G8 |
| 693055 | Gaillac (1450) | Absente | Non renseignée | 28 | — |
| 693055 | Avène (1810) | 20 | 0 G | 7 | E20:G20 |
| 708073 | Gien (1430) | 10 | 2 000 000 G | 5 | E27:G27 |
| 730384 | Gien (1430) | 10 | 23 500 M | 5 | E19:G19 |
| 734545 | Gien (1430) | 10 | 0 ZUN | 1 | E9:G9 |
| 773474 | Gien (1430) | 20 | 0 G | 6 | E17:G17 |
| 773474 | Gaillac (1450) | 20 | 0 G | 33 | E21:G21 |

G signifie grammes, KG kilogrammes, ZUN unités, M mètres. Exemples : 888 000 G = 888 kg ; 2 000 000 G = 2 000 kg. Les 900 000 de 021081 sont bien exprimés en **KG**.

Quatre articles ont simultanément une sécurité en jours et une sécurité en quantité : **333362, 730384, 049371 et 708073**. La façon de combiner ces deux protections n'est pas écrite : addition, maximum, anticipation des besoins ou autre traitement. La formule actuelle du modèle ne peut donc pas être tenue pour confirmée par le seul tableau.

Le champ est nommé **délai de sécurité**. Les données ne prouvent pas qu'il doit être transformé en une quantité cible égale à « consommation moyenne × nombre de jours ». Une avance de date et un stock physique cible sont deux mécanismes différents à départager.

Le zéro explicite de 268091 est conservé dans le relevé des données, sans le traduire en objectif de stock nul et sans relancer de scénario à zéro jour. Les stocks réellement présents dans les Excel restent la référence à reproduire. Une règle absente n'est pas un zéro : cinq couples stock n'ont aucune politique, et 029313/Gien n'existe que dans le MRP.

## 2. Tailles de lot écrites et vérifiées dans les projections

| Article | Site de fabrication | Lot fixe | Minimum | Maximum | Unité rapprochée des stocks | Cellules Taile de Lot |
|---|---|---:|---:|---:|---|---|
| 268967 | Gien | 0 | 107 800 | 107 800 | ZUN | E2:G2 |
| 268091 | Avène | 0 | 28 800 | 142 485 | ZUN | E3:G3 |
| 773474 | Gaillac | 3 200 000 | 0 | 0 | G | E4:G4 |
| 693055 | Gaillac | 600 000 | 0 | 0 | G | E5:G5 |

La feuille des lots n'a pas de colonne d'unité. L'unité ci-dessus vient du même article dans les stocks et le MRP. Pour 268967, minimum = maximum = **107 800 unités**. Pour 773474, le lot fixe est **3 200 kg** ; pour 693055, **600 kg**. Les zéros des bornes des lots fixes ne signifient pas une fabrication maximale de zéro : leur codification ERP précise reste à confirmer.

La quantité minimale de 268091 est **28 800 unités**, son maximum **142 485**. Le multiple de **14 400** et le nombre maximal de lots par semaine ne sont pas écrits dans cette feuille : ils viennent d'autres informations déjà disponibles et ne doivent pas être perdus.

Le contrôle des quantités prévues confirme trois régularités :

| Article / site | Comportement des entrées H | Portée de la conclusion |
|---|---|---|
| 773474 / Gaillac | **906 lignes positives sur 906**, multiples de 3 200 000 G | Confirme le lot fixe de 3 200 kg écrit pour cette fabrication |
| 693055 / Gaillac | **953 sur 953**, multiples de 600 000 G | Confirme le lot fixe de 600 kg écrit pour cette fabrication |
| 021081 / Gaillac | **170 sur 170**, multiples de 20 000 KG | Multiple très net de 20 tonnes à retrouver dans les règles d'achat/transport ; son origine n'est pas prouvée ici |

Ces comptes portent sur des lignes de plans successifs, pas sur autant de commandes distinctes. Une entrée hebdomadaire de 6 400 kg peut regrouper deux lots de 3 200 kg : elle n'invalide pas la taille du lot.

**Un lot de fabrication n'est pas nécessairement une réception hebdomadaire au dépôt.** Sur les 2 351 entrées positives de 268967 à Muret, aucune n'est un multiple exact de 107 800. Pour 268091, seules 5 sur 2 421 sont des multiples de 14 400. Les règles de lot sont définies à Gien ou Avène, alors que ces flux sont au dépôt. Fractionnement, regroupement et contenu de la colonne Entrée restent à caractériser : on ne peut ni imposer le lot d'usine à chaque réception du dépôt ni conclure que le lot source est faux.

## 3. Le calcul du stock projeté est retrouvé exactement

Dans chaque plan, pour un même article et un même site :

**Stock projeté de la ligne = stock projeté de la ligne précédente + Entrée − Sortie + contribution Stock_physique.**

Colonnes : H = Entrée, I = Sortie, J = Stock_physique, K = Stock fin de semaine. Pour la première ligne, la contribution initiale est déjà portée par J ; on ne doit pas ajouter une seconde fois le stock du fichier Stocks. La relation tient sur les **53 398 lignes** à la précision numérique du fichier, en conservant chaque version séparément.

Exemple 021081/Gaillac, plan du 5 janvier :

- `Feuille1!H277:K277` : 140 000 − 50 532 + 752 312 = **841 780 kg**.
- Ligne 278, semaine suivante : 841 780 + 120 000 − 30 220 + 379 880 = **1 311 440 kg**.

Cette équation explique comment le solde est calculé. Elle n'explique pas, à elle seule, comment le MRP a choisi les entrées et leurs dates.

## 4. Stock total et stock utilisable dans le plan : une distinction essentielle

La colonne J n'est pas seulement un stock initial placé dans la première semaine : **800 lignes** portent une contribution positive après la date du plan. Cela concerne par exemple 021081, 773474 et les deux produits finis.

Pour 021081, dans le plan du 5 janvier : **752 312 kg** sont portés dans la semaine du 5 janvier et **379 880 kg** dans celle du 12 janvier. Leur somme vaut **1 132 192 kg**, exactement le stock total de la photo du lundi 6 janvier (`Stocks!E190`).

Pour 773474/Gaillac, le même plan répartit **6 400 kg** en première semaine et **3 200 kg** au 26 janvier. Leur somme, **9 600 kg**, correspond à la photo du 6 janvier (`Stocks!E1611`).

**Confirmation utilisateur reçue pendant l'analyse : il s'agit de stock déjà présent, disponible plus tard, notamment pour des raisons de qualité.** Les dates de J décrivent donc la disponibilité de quantités physiques existantes. Elles ne doivent pas être traitées comme autant de nouvelles livraisons. La cause précise et l'identité des lots ne sont pas détaillées ligne par ligne dans l'export.

Sur les 1 615 photos appariables au lundi suivant, la somme J égale la photo dans **1 131 cas**, lui est inférieure dans **469** et supérieure dans **15**. Il reste donc des différences de périmètre ou de date à expliquer. Pour 268967, la première photo est 1 092 542 unités, contre 1 089 257 réparties dans J, soit 3 285 unités d'écart. Ce n'est pas un motif pour modifier arbitrairement l'Excel.

Le modèle doit distinguer les quantités présentes et les quantités disponibles à une date donnée. Tout rendre disponible immédiatement, ou compter à nouveau les contributions futures comme de nouvelles marchandises, peut changer les décisions. Le rapprochement détaillé avec l'inventaire est conservé dans le fichier de preuve stock_reconciliation.json, avec les écarts bruts et leurs dates.

## 4 bis. Rapprochement complet avec l'inventaire de stock

Le rapprochement porte sur **tous les 1 615 relevés hebdomadaires présents dans l'inventaire**, associés au plan du dimanche précédent. Les 31 stocks du 1er janvier n'ont pas de plan à cette date. Inversement, 22 plans n'ont pas de photo associée : 14 pour 344135/Gien et 8 pour 029313/Gien. Ces absences restent visibles.

On compare le stock total de l'inventaire à **J de la semaine du plan + toutes les contributions J futures du même plan**, sans ajouter les entrées H et sans utiliser le solde projeté K comme stock de départ.

| Article / site, plan du 5 janvier et inventaire du 6 janvier | Unité | J dans la semaine du plan | J disponible plus tard | Total réparti dans le MRP | Inventaire | Écart MRP − inventaire |
|---|---|---:|---:|---:|---:|---:|
| 021081 / Gaillac | kg | 752 312 | 379 880 | 1 132 192 | 1 132 192 | 0 |
| 773474 / Gaillac | kg | 6 400 | 3 200 | 9 600 | 9 600 | 0 |
| 338929 / Avène | UN | 354 000 | 0 | 354 000 | 354 000 | 0 |
| 268967 / Muret | UN | 981 240 | 108 017 | 1 089 257 | 1 092 542 | −3 285 |
| 693055 / Gaillac | kg | 590 | 1 200 | 1 790 | 1 800 | −10 |
| 002612 / Gaillac | kg | 395 | 0 | 395 | 1 250 | −855 |

Sur l'ensemble : **1 131 égalités exactes, 469 totaux MRP inférieurs à l'inventaire et 15 supérieurs**. Les tolérances numériques ne changent aucun de ces résultats. Le détail conserve les quantités brutes, unités, dates et cellules sources, sans arrondir un écart de 1 UN à zéro.

Des différences répétées méritent une explication de périmètre :

- **002612/Gaillac : −19 kg sur 51 dates** ; −855 kg le 6 janvier.
- **693055/Gaillac : −10 kg sur 51 dates** ; −610 kg le 3 mars.
- **042342/Gien : −1 500 000 UN sur 42 dates**, −1 625 000 sur huit, avec deux autres valeurs ponctuelles. Ce sont des différences entre les deux fichiers, pas une erreur de conversion à corriger automatiquement.
- **268967/Muret : un écart aux 52 dates**, le plus souvent quelques milliers d'unités, mais pas une constante unique.
- **3 mars : 29 couples sur 31 diffèrent simultanément**. Un décalage d'extraction ou de période est une piste, sans cause confirmée.

Le cas 002612/Gaillac du 6 janvier doit rester ouvert : `Feuille1!H158:K158` contient **1 250 kg d'entrée, 0 sortie, 395 kg de stock et 1 645 kg de solde projeté**. L'inventaire corrigé contient **1 250 kg de stock total**. Ces valeurs désignent des choses différentes ; la signification des 1 250 kg confirmés auparavant est demandée à l'utilisateur. Aucun fichier n'est corrigé dans cette analyse.

**Stock de l'inventaire − J de la semaine courante n'est pas automatiquement tout du stock en contrôle qualité.** Cette différence contient les disponibilités futures connues **et** l'écart encore inexpliqué entre les deux extractions. Les quantités non rapprochées doivent rester identifiées séparément.

[Détail du rapprochement stock par stock et date par date](../../artifacts/testing/mrp_source_rules_20260928/stock_reconciliation.json) · [Vérification indépendante](../../artifacts/testing/mrp_source_rules_20260928/validation/export-oracle.json).

## 5. Les plans sont révisés ; ils ne décrivent pas tous des événements exécutés

Comparaison de la même semaine cible entre deux versions hebdomadaires consécutives :

| Article / site | Comparaisons sur semaines communes | Entrées H différentes | Sorties I différentes |
|---|---:|---:|---:|
| 268967/1920 | 2650 | 662 | 681 |
| 268091/1920 | 2428 | 1049 | 1270 |
| 338929/1810 | 1605 | 758 | 745 |
| 021081/1450 | 1083 | 26 | 215 |
| 773474/1450 | 1326 | 272 | 351 |

Les changements existent aussi à court terme. Pour 268967, parmi 153 comparaisons dont la semaine cible se trouve à au plus 15 jours calendaires de la nouvelle version, H change 33 fois. Il n'y a donc pas de gel absolu visible de tous les totaux hebdomadaires. Cela n'exclut pas un horizon gelé pour certains types d'ordres, qui ne sont pas identifiés dans l'export.

Une réception peut être prévue avant l'expiration du « Temps de réception » compté depuis la date de version : elle peut venir d'une commande déjà engagée. L'export ne donne pas sa date de création. Les temps de réception ne permettent donc pas de repousser automatiquement toutes les entrées à « date du plan + délai ».

Pour reproduire les décisions réelles, les prévisions doivent être celles qui étaient connues à la date de décision. La version de décembre ne doit pas piloter une décision de janvier. Les sorties prévues ne remplacent pas automatiquement les consommations et ventes réellement exécutées.

## 6. Les soldes projetés négatifs doivent rester visibles

**1 236 lignes** ont un stock fin de semaine négatif, notamment **623 pour 268091/Muret** et **516 pour 693055/Gaillac**. Les stocks physiques de la feuille Stocks sont, eux, non négatifs.

Un solde projeté négatif exprime un manque dans le plan tel qu'il est exporté. Ce n'est pas la preuve d'un stock physique négatif ni d'une livraison client réellement manquée. Le déficit peut dépendre des dates, besoins, ordres et statuts présents dans l'export. Le supprimer ou le remplacer par zéro ferait perdre une information utile pour reproduire le MRP.

## 7. Rapprochement avec les règles déjà disponibles

Par rapport à `Extract_Données_Complémentaires.xlsx`, 22 règles de sécurité sont identiques, trois valeurs changent et deux règles sont ajoutées :

| Article/site | Ancien fichier | Nouveau fichier | Références ancien → nouveau |
|---|---|---|---|
| 268967/Muret | 25 jours | 60 jours | Politique de Stock MRP!E26 → Politique de stock MRP!E2 |
| 268091/Muret | 20 jours | 0 jour | E25 → E3 |
| 426331/Avène | 7 jours | 10 jours | E20 → E8 |
| 773474/Gaillac | Absente | 20 jours | Nouvelle ligne 21 |
| 021081/Gaillac | Absente | 900 000 kg | Nouvelle ligne 23 |

Le minimum de lot de 268091 change de 14 400 à 28 800 (`Taille de Lots!G2` → `Taile de Lot!G3`) ; la règle de lot de 693055/Gaillac est ajoutée. Les deux autres règles de lot sont inchangées.

**Les paramètres ne portent pas de date d'entrée en vigueur.** Le fait qu'un classeur contienne les stocks de 2025 ne prouve pas que chaque règle de son tableau s'appliquait au 1er janvier. Les nouvelles lignes complètent les anciennes données ; les valeurs contradictoires doivent être datées et expliquées, pas remplacées automatiquement.

Confirmation utilisateur à conserver : pour **268967 (Permixon)**, l'objectif est **un an de stock sur toute la chaîne depuis l'entrée de Gaillac jusqu'au produit fini au dépôt**, exprimé en équivalent produit fini. Il s'agit d'une règle globale qui s'ajoute aux règles locales. Ces deux classeurs ne contiennent ni cette consigne ni les nomenclatures nécessaires à sa conversion. Il faut les rapprocher des BOM existantes et préciser la demande annuelle de référence et les stocks/encours/transits inclus. Compter chaque quantité physique une seule fois ; ne pas additionner les équivalents de composants complémentaires comme s'ils représentaient chacun un produit fini supplémentaire.

## 8. Règles encore impossibles à identifier avec certitude dans ces seuls exports

| Sujet | Ce que nous savons | Ce qu'il manque pour reproduire la décision |
|---|---|---|
| Déclenchement du réapprovisionnement | Besoins, entrées et soldes projetés datés | Calcul exact du besoin net, seuil et horizon utilisés |
| Sécurité en jours | Valeurs explicites, calendrier lundi–vendredi confirmé | Avance de date, couverture physique ou autre application ; combinaison avec la quantité de sécurité |
| Disponibilité du stock | J répartit du stock déjà présent selon sa disponibilité, confirmation utilisateur | Motifs détaillés, identités des lots et traitement des écarts avec l'inventaire |
| Temps de réception | Valeur E constante par article/site | Calendrier, point de départ et opérations comprises |
| Lots | Quatre règles écrites, deux vérifiées directement dans les entrées de fabrication | Règles des autres articles, arrondis, regroupement et fractionnement des entrées au dépôt |
| Achats de 021081 | Toutes les entrées prévues sont multiples de 20 tonnes | Origine : lot d'achat, arrondi, contrat, transport ou autre |
| Commandes ouvertes | Des entrées proches sont présentes | Identifiants, dates de création, ordres fermes/propositions et statuts |
| Besoins et prévisions | Les sorties I sont datées et révisées | Ventilation commandes clients/prévisions/retards/transferts et méthode de consommation des prévisions |
| Capacités et fabrication | Lots et sites connus | Ordonnancement, capacités, changements de série, rendements et délais physiques ; à compléter par les autres sources |
| Calendrier du calcul | 52 versions exportées | Fréquence réelle du MRP et jours de commande/livraison |
| Stock global du 268967 | Objectif d'un an confirmé par l'utilisateur | Répartition réelle entre étapes et assiette annuelle de calcul |

Les conventions actuelles du simulateur — 23 besoins forcés sur capacité × nomenclature, déduction de tout le transit futur sans limiter aux dates utiles, planchers génériques de couverture, pilotage et lissage de fabrication — ne sont pas démontrées comme règles industrielles par ces classeurs. Elles doivent être confrontées aux plans ; conserver des quantités issues des sources ne suffit pas à valider ces algorithmes.

## 9. Contrôles et limites des données

- Aucun doublon article/site/date dans Stocks, aucun doublon article/site/version/semaine dans le MRP.
- 31 couples stock ont 53 photos. 344135/Gien n'en a que trois, en décembre ; 029313/Gien est présent dans 8 versions MRP sans photo de stock correspondante. Une absence n'est jamais remplacée par zéro dans cette analyse.
- Les valeurs de stock suivent un coût unitaire constant par couple article/site ; devise et statuts de valorisation non précisés. Ces valeurs ne constituent pas des règles de commande.
- La correction 002612/Gaillac du 6 janvier est déjà présente avant cette analyse : `Stocks!E946 = 1 250 kg`, `F946 = 1 575`.
- Graph concorde avec les 53 dates de Stocks pour 773474. Son total général additionne des photos : il ne représente ni un stock à une date ni un flux annuel.
- Une recherche descriptive de rapprochement entre le solde K et différents horizons de besoins futurs est conservée dans le JSON. Elle n'identifie pas un algorithme de commande unique et n'est pas utilisée pour modifier la simulation.
- Les empreintes des deux classeurs sont restées inchangées. Les calculs sont faits en mémoire sur les données réelles ; aucun test de modification de date, d'altération ou de disparition de fichiers n'a été exécuté.

## 10. Ce qui diffère dans le MRP effectivement exécuté

Complément du 28 septembre, après les deux simulations de cinq ans `mrp_rules_integration_20260928`. Cet audit relit leurs résultats, le code et les Excel ; il ne modifie aucun moteur, paramètre, classeur ou HTML et ne lance pas de nouvelle simulation. Le logiciel ERP est inconnu, selon la réponse utilisateur. **Nous pouvons établir ce que fait notre moteur et ce que montrent les exports ; nous ne pouvons pas déclarer retrouvé tout l'algorithme industriel.**

Les contrôles précédents ont vérifié la conservation des quantités, la cohérence des lots et la fidélité arithmétique des courbes aux CSV, sur les scénarios et invariants couverts. Ces propriétés ne certifient pas que les décisions MRP reproduisent celles de l'entreprise. Le présent audit trouve notamment un problème de rattachement hebdomadaire et des hypothèses de pilotage encore non validées.

| Sujet | Modèle réellement exécuté | Sources industrielles / conclusion |
|---|---|---|
| Demande client | Une année issue de `demand_PF.xlsx`, répartie quotidiennement et répétée tous les 365 jours | Les besoins I des 52 plans Flow sont révisés. Volumes et profils diffèrent ; I n'est pas une vente réalisée |
| Besoins de composants | Pour 23 couples, priorité à capacité journalière × nomenclature | Le besoin planifié source varie par semaine. Une capacité confirmée ne justifie pas de la traiter comme une demande |
| Fabrication intermédiaire | Autre plancher capacité × nomenclature des destinations, puis commande asservie au stock | Ce plancher existe aussi en dehors de la liste des 23 forçages. Son équivalence avec l'ERP n'est pas démontrée |
| Sécurité en jours | Convertie en quantité cible ; maximum avec la sécurité quantitative et les autres planchers | Le libellé « délai de sécurité » ne confirme ni ce mécanisme ni le choix du maximum |
| Dates des besoins et réceptions | Le calcul net soustrait toutes les réceptions futures engagées | Les soldes sources sont datés semaine par semaine. Le calcul exact d'allocation aux dates reste inconnu |
| Stock indisponible | Option initiale ajoutée mais inactive dans les deux runs ; réceptions d'ouverture matérialisées à la date utilisable | J futur est du stock déjà détenu. Les dates de livraison et d'entrée du carnet peuvent aussi différer de plusieurs mois |
| Ordres de fabrication initiaux | Tous les O.Proc importés sont traités comme des encours dont les composants ont été engagés avant J0 | Les dates et quantités existent, mais les dates réelles de prélèvement matière ne sont pas fournies |
| Révision des ordres | Carnet initial importé une fois ; nouvelles décisions quotidiennes ; pas de rééchelonnement des ordres engagés dans le parcours BASE examiné | Les entrées et besoins des versions Flow changent. Statuts fermes/proposés et identifiants manquent pour reconstituer cette révision |
| Lots | Tailles souvent respectées, mais pilotage des lancements propre au modèle | Respecter un lot de 3,2 t ne garantit ni le bon nombre de lots ni les bonnes dates |
| Délais | Délais du graphe, distributions aléatoires et marges de couverture | Le « temps de réception » Flow ne décrit pas nécessairement les mêmes opérations |
| Périmètre | Deux PF et une partie des articles/sites ; certains stocks de sites entiers sont utilisés | Plusieurs composants semblent couvrir davantage de produits ou d'activités. Cinq couples Flow n'ont pas de série de stock simulée |
| Objectif Permixon | Aucune commande globale identifiée imposant un an sur toute la chaîne | La règle utilisateur est globale ; son assiette et sa répartition ne sont pas encore traduites dans le pilotage |

### Besoins et programme de fabrication : les deux principaux forçages

Pour **338929/Avène**, le besoin utilisé vaut **203 550 UN chaque jour**, contre une demande nominale moyenne d'environ **9 798 UN/j**. La cible de sécurité atteint **2,44 à 2,85 millions d'unités**. Le besoin à capacité maximale a donc une influence directe sur le surstock de packaging ; la totalité de l'écart de stock ne peut cependant pas lui être attribuée isolément.

Sur les 38 semaines présentes du premier plan, avec la convention actuelle de fin de semaine, le besoin source est **3 267 182 UN**, le signal brut nominal **2 517 682**, mais le signal utilisé **54 144 300** : **16,57 fois le besoin source**. Cette dernière somme est un signal de dimensionnement répété, pas une quantité réellement commandée ou consommée.

Un second mécanisme existe pour **773474/Gaillac** : le signal de fabrication a un plancher de **1 486 826,572 G/j**, calculé à partir de la capacité de Gien et de sa nomenclature. Le retirer de la liste des besoins statiques ne supprimerait pas à lui seul ce plancher. La commande de fabrication suit ensuite :

```text
cible = max(stock de base, jours de cible PF × signal)
commande brute = signal + 0,25 × (cible − stock)
commande lissée = max(0, 0,2 × commande précédente + 0,8 × commande brute)
```

Les règles de lots, composants disponibles, capacités et campagnes limitent cette commande. Dans les runs examinés, les jours de cible PF valent zéro. À J1, `0,8 × 1 486 826,572 = 1 189 461,2576 G`, puis la taille de lot conduit à fabriquer **3,2 millions G**. Ces gains de commande ne sont pas des règles retrouvées dans les Excel.

Références : `run_first_simulation.py:8580`, `:8634`, `:11201`, `:11212`, `:12324` ; liste des 23 couples dans `config/reproduction_20260920/nominal.json:101`. La dynamique des systèmes et les réactions à l'état peuvent être conservées en faisant évoluer cette couche de décision.

### Paramètres renseignés et paramètres qui déclenchent réellement une décision

Pour **773474/Gaillac**, les 20 jours sources changent la cible affichée à J0 : **7,285 → 29,142 millions G**. Mais le contrôleur de fabrication locale ne lit pas cette sécurité. La boucle de réapprovisionnement traite les paires ayant une liaison entrante ; elle ne transforme pas ce besoin affiché en ordre de fabrication local. Les premiers lancements J1/J8/J15/J22 sont identiques. **La règle est visible dans le diagnostic, sans être appliquée directement à la fabrication.**

Pour **021081/Gaillac**, les 900 000 kg sont bien lus comme cible. Pourtant, les deux runs ne créent **aucune nouvelle commande** sur 1 825 jours : les 23 réceptions proviennent toutes du carnet initial, pour **1 320 000 kg**. Le stock minimal reste **941 844 kg** et le besoin net reste nul. Une amélioration de sa courbe dans la variante ne démontre donc pas l'effet d'un nouvel achat déclenché par cette sécurité.

Pour **693055/Gaillac**, le lot source de 600 kg est connu, mais aucun processus de fabrication n'existe dans le graphe. Le modèle reçoit uniquement un ordre initial de 600 kg à J55. Il ne peut donc pas reproduire la suite des fabrications prévues dans le MRP par un simple changement de taille de lot.

Pour **268091**, le minimum de lot passe effectivement à 28 800 UN dans la variante ; sa sécurité au dépôt reste **20 jours**, conformément à la décision utilisateur. Pour **268967**, 60 jours remplacent 25 dans la variante, mais l'adéquation de leur conversion en stock cible reste à vérifier.

### Sécurité, disponibilité datée et réservations

Le modèle combine les protections par un maximum. Exemple 333362/Gien à J0 : `max(110 000 UN, 154 000 UN/j × 14 jours calendaires) = 2 156 000 UN`. Cela ne démontre pas comment l'ERP combine ses champs de quantité et de délai.

Il existe des mécanismes ERP où un délai de sécurité **avance les dates des besoins et des réceptions**, en complément du stock de sécurité quantitatif : c'est notamment la définition documentée par [SAP, Safety Time / Actual Range of Coverage](https://help.sap.com/docs/SAP_ERP/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html?locale=en-US). Cette référence explique une hypothèse à départager ; elle ne prouve pas le paramétrage du système industriel étudié, dont le logiciel est inconnu.

Le calcul net courant utilise `cible + retard − disponible − toutes les réceptions futures`. Les réceptions ont bien des dates dans le pipeline, mais cette soustraction ne les filtre pas selon la date du besoin. En outre, une paire provenant du snapshot n'utilise la couverture complète du délai que si elle est explicitement déclarée dynamique ; la liste correspondante est vide dans les runs. **Besoins dynamiques, couverture du délai et réception datée doivent être traités ensemble.** Le retrait isolé du forçage de 338929 avait déjà causé des ruptures ; il ne constitue pas une correction validée.

Les réservations sont distinctes des départs. À J0, sur les 9,6 millions G de 773474/Gaillac, 3,2 millions partent et 6,4 millions sont réservés pour J9/J18 : le disponible devient zéro, mais ces 6,4 millions restent sur le site. Cette distinction explique pourquoi un stock disponible ne se compare pas directement à un inventaire « Stock Total ».

Références : `run_first_simulation.py:12366`, `:12418`, `:12436`, `:13333`, `:13433`. La colonne `bn_qty` est recalculée après les commandes, en fin de journée ; elle ne décrit pas seule la décision initiale.

## 11. Deux différences de calendrier démontrées

### Livraison et disponibilité : cas 021081

Dans `Extract_En_cours.xlsx`, feuille `Sheet1` :

| Ligne | Quantité E | Date de livraison G | Champ H | Date d'entrée I |
|---|---:|---|---:|---|
|24|100 000 kg|7 janvier 2025|75|23 avril 2025|
|40|40 000 kg|7 janvier 2025|75|23 avril 2025|
|41|40 000 kg|14 janvier 2025|75|30 avril 2025|

Les dates G et I sont des valeurs stockées dans le fichier. **Le moteur n'ajoute pas arbitrairement trois mois à une date d'entrée : il importe ces deux dates.** Il interprète G comme livraison physique et I comme disponibilité, puis ne matérialise la réception en stock qu'à I (`run_first_simulation.py:5283`). Le délai de lane sert séparément à reconstruire le départ.

Le nouveau plan MRP du 5 janvier présente **140 000 kg en H277 au repère du 5 janvier**. Les 23 commandes initiales regroupées selon leur date G reproduisent exactement les 14 semaines H positives de ce premier plan, pour 1,32 million kg. Leurs dates I ne les reproduisent pas. Sans identifiants, cela ne prouve pas une correspondance individuelle de chaque ordre, mais établit une correspondance complète des quantités hebdomadaires.

Entre G et I, les quantités du carnet sont encore traitées comme du pipeline dans le modèle. Si G désigne bien la livraison physique au site et si le carnet est exécuté à ces dates, elles sont pourtant déjà physiquement sur le site : **140 000 kg au 13 janvier**, jusqu'à **1 180 000 kg au 21 avril**. Trente-six des 52 photos sont concernées ; moyenne de cette quantité intermédiaire : **404 615 kg**. Ce sont des dates planifiées de carnet, pas des preuves de livraisons industrielles exécutées.

Ce mécanisme est distinct des **379 880 kg déjà détenus** du J futur du 5 janvier. L'option de disponibilité du stock initial ne traite pas à elle seule toutes les réceptions ultérieures entre livraison physique et disponibilité. Pour comparer au stock total industriel, il faut représenter explicitement ces états et confirmer le sens du « temps de réception ». Le calendrier des 75 jours n'est pas établi : du 7 janvier au 23 avril, on compte 106 jours calendaires, ou 76 lundi–vendredi en excluant le départ et incluant l'arrivée.

### Le dimanche MRP ne peut pas être tenu systématiquement pour une fin de semaine

La carte actuelle compare les flux simulés du lundi au dimanche au repère dimanche d du MRP. Or, pour les 14 entrées positives de 021081, le dimanche qui correspond aux dates de livraison G est **celui qui précède ces livraisons** :

- H277, repère 5 janvier, 140 000 kg : livraisons G du mardi 7 janvier.
- H278, repère 12 janvier, 120 000 kg : livraisons G du mardi 14 janvier.
- H279, repère 19 janvier, 100 000 kg : livraison G du mardi 21 janvier.

**La convention de fin de semaine utilisée par la carte est donc inadaptée à ce rapprochement précis.** Elle introduit un rattachement de sept jours différent de celui des commandes sources. Les contrôles CSV→courbes validaient le calcul de cette convention, pas sa signification métier. Cette conclusion est démontrée pour H/021081/premier plan ; son extension aux I, aux autres articles et à la frontière dimanche/lundi reste à confirmer. Aucun HTML n'est corrigé silencieusement dans cet audit.

Les deux interprétations ont été recalculées sans combler les semaines absentes :

| Produit / dépôt | Convention de rattachement | Semaines complètes en 2025 | Sorties I prévues | Demande nominale sur ces jours | Écart modèle/source |
|---|---|---:|---:|---:|---:|
|268091|Semaine se terminant au dimanche indiqué|47|4 194 201 UN|3 132 285 UN|−25,32 %|
|268091|Lundi–dimanche suivant le repère|48|4 831 275 UN|3 213 884 UN|−33,48 %|
|268967|Semaine se terminant au dimanche indiqué|51|2 466 126 UN|1 558 383 UN|−36,81 %|
|268967|Lundi–dimanche suivant le repère|51|2 480 046 UN|1 558 383 UN|−37,16 %|

Les périmètres aux bornes changent : pour 268091, la seconde convention inclut I545 = 637 074 UN. À mêmes 47 lignes source, le seul déplacement temporel modifie le biais de −25,32 % à −24,07 %. Il faut donc distinguer changement de période et décalage des courbes. Dans tous ces cas, la demande nominale diffère sensiblement du besoin source. **Ces nombres comparent une demande du modèle à une sortie prévue, pas à une vente réellement exécutée.**

Le profil nominal ajoute une autre convention : les 52 étapes hebdomadaires commencent au 1er janvier, donc mercredi–mardi en 2025, puis le dernier jour du cycle de 365 jours vaut zéro. Les demandes négatives du fichier de 268967 sont compensées sur les semaines positives suivantes : huit semaines changent, total annuel conservé. Les projections Flow ne sont pas intégrées comme prévisions révisées au fil des cinq années.

## 12. Les encours initiaux et le périmètre expliquent une partie des écarts

### Une hypothèse d'encours qui pèse fortement sur la consommation

Les **22 O.Proc** initiaux sont traités en mode `wip` : leurs composants sont supposés engagés avant J0 et ne sont pas prélevés dans les stocks de 2025 lors de leur mise à disposition. Cela inclut 20 ordres de 268091, un de 773474 et un de 693055, sans nomenclature active pour ce dernier.

Exemple : l'ordre source de la ligne 91, **141 780 UN de 268091**, a une livraison au 12 mai et une entrée au 26 mai. Le modèle suppose néanmoins ses composants déjà engagés avant J0 et inscrit `issue_day = -1` dans l'audit, sans débit du stock initial. Les dates effectives de prélèvement matière ne sont pas présentes dans les données disponibles : **ce traitement est une hypothèse du nominal, pas une observation de production.**

Sur 2025, le nominal met à disposition **3 716 915 UN de 268091**, dont **1 945 715 issues des ordres initiaux** et **1 771 200 fabriquées par les nouvelles décisions**. Le packaging 338929 n'est nouvellement consommé que pour ces 1 771 200. Assimiler toute la mise à disposition PF à une fabrication consommant les matières de l'année fausserait l'explication des stocks. Références : `run_first_simulation.py:10742`, `:10802`, registre des lots du run.

### Des écarts de périmètre à éclaircir entre composants et produits finis

Sur les semaines présentes et communes du premier plan, avec la convention actuelle de semaine se terminant au dimanche, besoins composant I divisés par besoins PF I × nomenclature du modèle : **42,43 pour 002612/Avène** (39 semaines), **12,32 pour 007923/Avène** (37 semaines), **4,57 pour 773474/Gien** (26 semaines), **7,92 pour 021081/Gaillac** (34 semaines). Le caractère partagé des matières Avène avait été signalé par l'utilisateur. Les deux derniers rapports imposent également d'examiner le périmètre amont de Permixon.

Ce ne sont pas des coefficients d'allocation validés. Fabrication, sorties dépôt, variation des stocks, décalages de plan et ordres initiaux peuvent différer. On ne peut pas automatiquement diviser les stocks par ces rapports. Une allocation cohérente doit considérer ensemble demande, stocks et commandes en cours.

Cinq couples Flow n'ont pas de série de stock dans le modèle : **001848/Gien, 001893/Gaillac, 002612/Gaillac, 007923/Gien, 029313/Gien**. Les quatre premiers représentent 212 photos ; le dernier a des plans mais aucune photo. Une règle MRP ne remplace pas un périmètre absent.

### La règle d'un an pour Permixon a besoin d'une assiette explicite

Avec la seule nomenclature actuelle, 1 PF268967 consomme **9,654718 G de 773474**, soit **0,08631317892 KG de 021081** en remontant la chaîne. Les stocks initiaux de 021081/Gaillac, 773474/Gaillac et Gien, et du PF au dépôt représentent **16 839 402 équivalents PF** si on les affecte tous exclusivement à ce produit. Cela correspond à **10,685 années de la demande nominale de 1 575 986 UN/an**.

**Ce calcul conditionnel ne signifie pas que l'entreprise possède dix ans de stock.** Il démontre que l'assiette du modèle, les allocations ou les coefficients doivent être clarifiés avant de traduire la consigne d'un an. Le calcul exclut les stocks fournisseurs, transits, encours et composants complémentaires ; ceux-ci ne sont pas additionnés comme des PF supplémentaires. Aucun stock n'est réduit dans cet audit.

## 13. Ce que les derniers essais permettent de conclure

Sur 28 couples et 1 407 photos hebdomadaires comparables, l'erreur absolue moyenne divisée par le stock moyen source a une médiane non pondérée de **77,03 % dans le nominal**, **76,84 % dans la variante**. Dix-huit couples s'améliorent, dix se dégradent. Aucun n'est sous 10 % sur cette mesure. Avec la clôture du jour de la photo au lieu de la veille, la médiane devient **76,85 → 77,21 %** : le faible gain global dépend du rapprochement horaire.

Exemples nominal → variante : **338929/Avène 244,47 → 250,24 %**, **773474/Gaillac 82,89 → 83,13 %**, **268091/dépôt 65,77 → 64,70 %**, **268967/dépôt 27,96 → 42,58 %**. Les erreurs de périmètre et les stocks indisponibles limitent leur interprétation comme erreur du seul MRP.

La taille des lots est souvent correcte : 773474 est produit par 3,2 t ; pourtant le premier plan prévoit 64 t jusqu'à sa dernière ligne du 20 juillet, contre 25,6 t nominales mises à disposition jusqu'à cette date. Pour 693055, 11,4 t sont prévues jusqu'au 7 décembre, contre 0,6 t issue du seul ordre initial. Ce sont des comparaisons entre plans et exécutions modélisées, avec la réserve de période hebdomadaire décrite plus haut.

Les aléas ne sont pas appariés : même graine 42, mais `common_random_numbers=false`. Exemple vérifié : les mêmes 54 tranches de 5 000 UN de 338929 commandées à J42 ont les mêmes départs J42–118, mais arrivent **J59–135 dans le nominal** et **J80–156 dans la variante**. Une modification d'autres commandes décale le flux de tirages. L'écart entre les courbes ne peut donc pas être attribué exclusivement aux paramètres locaux modifiés.

Dans ces runs BASE, les incidents fournisseurs et la génération de risques dépendant de l'état sont désactivés, tandis que les délais aléatoires sont actifs. La dépendance des décisions de production et d'achat aux stocks reste présente. Cela distingue le fonctionnement normal du moteur de sa couche d'incidents et de cascades.

## 14. Ordre de travail proposé

1. **Fixer les périmètres et les dates comparées.** Définir le repère hebdomadaire Flow, distinguer livraison physique/disponibilité, relier les besoins au bon article/site et identifier les produits couverts. Présenter les conventions concurrentes tant qu'elles ne sont pas confirmées.
2. **Reconstituer l'état de départ et les commandes engagées.** Séparer stock utilisable, détenu indisponible, réservé, transport et encours ; confirmer quels O.Proc avaient réellement consommé leurs composants avant J0. Exploiter les dates G/I existantes sans en inventer le calendrier.
3. **Préciser le sens des règles industrielles.** Délai de sécurité, quantité de sécurité, combinaison des deux, temps de réception, statuts des ordres et possibilités de rééchelonnement. Traduire la règle globale d'un an de Permixon sur une assiette définie. Documenter les hypothèses restantes avant de les intégrer au pilotage.
4. **Faire piloter achats et fabrication par les mêmes besoins datés.** Traiter ensemble les forçages capacité×BOM, les réceptions par échéance et le contrôleur de fabrication, selon les règles clarifiées au point précédent. Relier effectivement la politique 773474 aux lancements. Conserver le moteur de dynamique des systèmes, les capacités, les lots et les réactions à l'état.
5. **Valider progressivement.** Reproduire d'abord le tableau MRP hebdomadaire source avec ses propres H/I/J ; confronter ensuite les décisions proposées aux versions successives, puis la trajectoire simulée aux photos de stock. Identifier les règles sur une partie des semaines et vérifier sur les autres. Comparer les variantes avec des aléas appariés et conserver le nominal historique comme référence.

L'information supplémentaire la plus utile serait un extrait conservant les **identifiants d'ordres, leur type/statut, date de besoin, livraison et disponibilité**, accompagné de la définition des colonnes E/G/H/I/J et des périodes. Sans ces informations, plusieurs règles de décision peuvent produire le même tableau hebdomadaire.

## 15. Suite : comparaison corrigée et examen des O.Proc sur tous les plans de 2025

### Carte et comparaison reproductible

La [carte de comparaison actualisée](../../resultats/comparaison_mrp_fiabilisee_20260928/comparaison.html), bouton **Essais MRP 2025**, conserve les deux suivis de lots et les autres onglets historiques. Le panneau de comparaison utilise deux recalculs de 1 825 jours : nominal conservé et variante des paramètres sources. Leurs 33 CSV respectifs sont identiques aux références antérieures. Les figures de comparaison restent limitées à 2025.

La vue permet désormais de choisir explicitement trois conventions : dimanche–samedi à partir du repère source, lundi–dimanche suivant ce repère, et l'ancien lundi–dimanche se terminant au repère. La première est proposée par défaut, conformément au rapprochement des commandes 021081 ; sa généralisation industrielle reste non confirmée. Les bornes exactes accompagnent le survol, les exports et le tableau des périodes comparées. Une fenêtre doit inclure le repère et les sept jours agrégés ; aucune semaine partielle n'est totalisée.

Les stocks disponible, réservé et détenu indisponible restent distincts. Quand le registre de disponibilité manque, le stock total simulé n'est pas présenté comme entièrement reconstitué et aucune valeur manquante n'est transformée en zéro. Les photos industrielles restent les données de référence. Les cinq couples sans série simulée restent accessibles dans la couverture.

L'onglet Entrées / sorties expose aussi le carnet initial du couple sélectionné : quantité, type, date G de livraison prévue, date I de disponibilité interprétée, fichier et ligne CSV. Ces lignes ne sont pas ajoutées une seconde fois aux courbes. Le tableau porte sur les couples présents dans Flow ; les vingt OF de 268091/Avène ne font pas partie de ce sélecteur, faute de couple correspondant dans l'export.

### Réponse à la vérification des O.Proc avec le MRP complet

Les 52 versions des plans ont été examinées, en conservant séparément leurs cibles 2025 et 2026. Les 22 O.Proc du carnet comprennent vingt OF de 268091, un de 693055 et un de 773474. Les besoins et entrées projetés permettent des rapprochements de quantités ; les fichiers ne donnent pas les identifiants communs, statuts de lancement ou prélèvements matière nécessaires pour identifier l'état physique de chaque OF.

Un signal nouveau apparaît pour **338929** dans le premier plan du 5 janvier : **10 des 13 regroupements selon la date G** des OF 268091 correspondent exactement au besoin d'étuis après une majoration de **2 % et arrondi supérieur**. Aucun de ces treize groupes ne correspond simplement au rapport 1:1.

| Ordre(s) dans Extract_En_cours | Quantité de PF | Besoin d'étuis dans Flow_Data_MRP_results | Rapprochement |
|---|---:|---:|---|
| Ligne 75 | 139 660 | I705 = 142 454 | arrondi supérieur de 139 660 × 1,02 |
| Lignes 72 + 82 | 98 315 | I707 = 100 282 | arrondi supérieur de 98 315 × 1,02 |
| Ligne 91 | 141 780 | I723 = 144 616 | arrondi supérieur de 141 780 × 1,02 |

Les vingt OF totalisent **1 945 715 PF**, soit **1 984 632 étuis** après majoration et arrondi par ordre. Sur les repères du 5 janvier au 11 mai, le premier plan demande **2 129 248 étuis**, soit cette somme plus **144 616**. Trois déplacements de dates candidats permettent un rapprochement quantitatif de tous les ordres ; les valeurs répétées empêchent d'en faire une identification certaine des OF.

Aux dates G d'origine restant à venir, les correspondances passent de 10/13 à **4/12, 3/12 puis 2/11** dans les trois versions suivantes ; aucune ne persiste ensuite à ces dates d'origine. Les plans sont révisés : le rapprochement du premier plan n'est pas une règle de quantités figées pour toute l'année.

Pour 693055, l'ordre de 600 000 G correspond à H788 dans la semaine de sa date G. Pour 773474, H969 contient 9 600 000 G, soit trois lots fixes, sans pouvoir isoler l'ordre initial de 3 200 000 G. Pour 268091, le plan usine **268091/1810 est absent** : le plan de produit fini fourni concerne le dépôt 1920. On ne peut pas assimiler une réception au dépôt au lancement d'un OF à Avène.

**Conclusion : les plans comportent des besoins futurs compatibles avec les OF du carnet ; ils ne démontrent pas que toutes leurs matières étaient déjà engagées avant J0. Ils ne suffisent pas non plus à prouver la date réelle des prélèvements.** L'hypothèse globale du mode `wip` reste donc à remplacer par un traitement explicite des états d'ordres, avec les données permettant de les distinguer. Aucun basculement global vers une consommation à la réception n'est effectué sur cette seule inférence.

### Le facteur de 2 % n'est pas une perte physique démontrée

La nomenclature disponible écrit bien un étui par PF : `268091.xlsx/BOM!B15 = 1 000`, `E15 = 1 000`, `F15 = UN.` ; `Data_poc.xlsx/BOM!H46 = 1 000`, `K46 = 1 000`, `L46 = UN`. Le graphe et le moteur conservent ce rapport. Aucun coefficient de rebut/rendement de 2 % n'a été trouvé dans les fiches BOM/FIA et politiques pertinentes consultées.

Il s'agit donc d'une **majoration de besoin planifié candidate, absente des nomenclatures disponibles**, et non d'une donnée explicitement renseignée perdue à l'import. Une marge de 2 % et un rendement de 98 % ne sont pas équivalents : le second demande environ 2,0408 % de matière en plus. Le plan ne permet pas d'attribuer cet excédent à du rebut effectivement consommé ou détruit. La BOM physique et le registre matière ne sont pas modifiés ; un futur essai devra distinguer majoration de planification et consommation réelle.

Reproduction : [script des recalculs et du rendu](../../artifacts/testing/mrp_comparison_reliable_20260928/reproduce.py), [identité des 66 CSV](../../artifacts/testing/mrp_comparison_reliable_20260928/identity.json), [oracle indépendant](../../artifacts/testing/mrp_comparison_reliable_20260928/validation/source_oracle.py). L'exécution utilise un nouveau dossier de sortie, les fichiers sources restant inchangés. La correction concerne la comparaison ; les mécanismes MRP listés en sections 10–14 ne sont pas encore corrigés par ce rendu.

Validation sur les sources finales stabilisées : **8 tests ciblés en mémoire**, invariants des **deux simulations de cinq ans**, **299 440 contrôles numériques indépendants** sans échec (écart maximal 1e-9) et **20 parcours/contrôles du panneau dans Chromium** réussis. Ces derniers examinent 1 417 083 points de séries, les trois conventions, les 33 couples, les cinq vues, les versions MRP, les exports et les deux suivis de lots. Le contrôle géométrique SVG est échantillonné ; ces preuves ne certifient ni toutes les interactions possibles ni la calibration industrielle.

Preuves finales : [oracle Excel/CSV](../../artifacts/testing/mrp_comparison_reliable_20260928/validation/result_final.json), [navigateur du panneau](../../artifacts/testing/mrp_comparison_reliable_20260928/ui/run3/browser.json), [agrégation doctor/tests/qualification/navigateur](../../artifacts/testing/mrp_comparison_reliable_20260928/toolbox/gate-f53c136a6db341a1b2ec103369444720/manifest.json). Le premier démarrage Playwright avait été refusé sur un canal IPC Windows avant ouverture du navigateur ; les vérifications réussies ont été exécutées après approbation de l'outil hors sandbox, sans changer les protections système. Les preuves intermédiaires ne sont pas comptées comme validation du rendu final.

## 16. Essais séparés : échéances des réceptions et sécurité de fabrication

Cette étape modifie le moteur uniquement par **deux options désactivées par défaut**. Le nominal est recalculé sur 1 825 jours : ses **33 CSV sont identiques octet par octet** à la référence précédente. Les classeurs industriels, les sécurités sources, la BOM physique et l'hypothèse actuelle des OF initiaux sont conservés. Aucun essai à zéro jour n'est introduit.

La [nouvelle carte de comparaison](../../resultats/comparaison_mrp_date_20260928/comparaison.html), bouton **Comparaisons 2025**, contient quatre simulations de cinq ans : nominal historique, référence avec règles sources, filtrage des réceptions par échéance, puis filtrage avec sécurité de fabrication. Les comparaisons industrielles portent sur 2025. Les trois derniers calculs partagent le graphe des règles sources et les aléas indexés par liaison/jour/origine/rang ; des commandes supplémentaires peuvent rester sans correspondant. Le nominal garde son mécanisme aléatoire historique. Une seule graine ne permet pas une conclusion statistique multigraines.

### Changements et lecture de la carte

- `--mrp-receipt-netting-mode within_cover` ne déduit du besoin de réapprovisionnement par transport que les réceptions encore attendues dans la fenêtre de couverture existante, borne incluse. Les commandes plus tardives restent engagées et seront reçues. Les contrôleurs de stocks fournisseurs gardent leur règle historique. L'association à une modification initiale du pipeline non indexée est explicitement refusée.
- `--production-mrp-safety-targets` rend les sécurités des produits fabriqués effectives dans les cibles MPS et fabrication : maximum entre cible historique, quantité de sécurité fixe et jours de sécurité convertis × signal journalier du contrôleur, puis multiplicateur de pilotage habituel. Gains de dynamique des systèmes, capacités, nomenclatures, lots et délais restent en place.
- La vue **Besoins MRP** sépare réceptions dans l'horizon et plus tardives, précise l'échéance au survol et à l'export, et montre le calcul avant émission de commande séparément de la fin de journée. Une absence de relevé ne devient pas zéro. Une autre courbe affiche la cible réellement utilisée par la fabrication, distincte du diagnostic MRP et de la quantité produite.

Les autres onglets et les deux suivis de lots de cette copie restent ceux du nominal historique. Les nouveaux scénarios sont accessibles dans le panneau de comparaison ; cette carte ne présente pas une nouvelle généalogie de lots pour chacun des quatre calculs.

### Résultats : ne pas adopter ces deux changements isolément comme MRP industriel

Le tableau utilise les **52 dates des photos industrielles**, rapprochées de la clôture du dimanche précédent. Les valeurs sont des moyennes à ces dates, pas des moyennes sur tous les jours. L'inventaire source est un stock total ; le modèle comparé fournit un disponible. Ce rapprochement décrit un écart de niveaux, sans prouver une identité de périmètre physique.

| Article / site | Moyenne des photos sources | Référence règles sources | Réceptions datées | Avec sécurité fabrication |
|---|---:|---:|---:|---:|
| 338929 / Avène | 521 515 UN | 1 735 773 UN | 2 895 773 UN | 2 895 773 UN |
| 773474 / Gaillac | 25 169 kg | 4 062 kg | 4 062 kg | 41 415 kg |
| 021081 / Gaillac | 1 558 863 kg | 1 618 835 kg | 1 618 835 kg | 1 274 989 kg |

Pour **338929**, l'écart absolu moyen aux photos passe de **1 317 169 à 2 461 885 UN** avec le filtrage des réceptions : le résultat se dégrade. Écarter une commande tardive du besoin immédiat peut provoquer des nouvelles commandes répétées avant l'arrivée des précédentes. Le stock moyen quotidien 2025 augmente d'environ 66,8 %. Ce filtrage de fenêtre n'est donc **pas un calcul MRP complet des besoins et réceptions à chaque date** : il ne traite ni chaque rupture intermédiaire ni le remplacement d'un besoin déjà couvert plus tard.

Exemple vérifié dans les CSV : à **J53**, la variante commande **270 000 étuis**, disponibles entre **J134 et J210**, alors que sa fenêtre se termine à **J130**. Aucune de ces nouvelles quantités ne peut couvrir le manque qui motive cette décision. Sur J52–J58, elle engage 1 860 000 unités supplémentaires, dont 1 075 000 arrivent après la borne propre à leur décision ; la référence appariée ne commande pas pendant ces sept jours. Ce cas doit devenir un critère métier de la prochaine correction, au-delà de la seule justesse arithmétique du filtrage.

Pour **773474 à Gaillac**, la sécurité de fabrication réduit l'écart absolu moyen de **21 108 à 16 246 kg**, mais fait passer le modèle d'un stock trop faible à un stock trop élevé. Le signal de fabrication conservé est de **1 486 826,572 G/jour**, encore lié à une capacité aval. À J0, avec 20 jours ouvrés convertis en 28 jours calendaires, la cible appliquée vaut **41 631 144,016 G, soit 41 631 kg**. Elle diffère de la cible du diagnostic MRP, qui utilise un autre signal. Il faut corriger la base des besoins avant de considérer ce niveau comme une cible industrielle démontrée ; diminuer arbitrairement les jours sources ne résoudrait pas ce problème.

La fabrication supplémentaire de 773474 consomme davantage de **021081** : son écart absolu moyen aux photos passe de **322 608 à 404 142 kg**. Sur cinq ans, les trois variantes ont les mêmes quantités servies aux clients pour les deux PF ; ces hausses de stocks et de production n'apportent pas de gain de service mesuré dans cet essai. Les options restent expérimentales, sans remplacement du nominal.

Pour 021081, l'absence de nouvelles commandes **vers Gaillac** ne signifie pas absence d'activité amont : des commandes alimentent les stocks des fournisseurs. Dans la variante avec fabrication, le besoin net Gaillac est positif 114 jours, mais aucun des quatre fournisseurs n'atteint alors le lot expédiable de 20 000 kg. Leur maximum constaté sur cinq ans est de 19 709 kg ; ce n'est pas un plafond configuré. Le contrôleur utilise une capacité amont estimée et n'engage plus son réapprovisionnement proactif quand le signal de demande est nul. Ce diagnostic explique la différence entre besoin calculé et commande réalisable ; il ne démontre pas une capacité industrielle réelle de ces fournisseurs.

### Suite métier et portée des vérifications

La priorité devient de **calculer les besoins à partir du programme de fabrication et de la demande**, en réservant les capacités à leur rôle de limite, puis d'affecter les réceptions aux besoins datés pour éviter les commandes de remplacement répétées. Le moteur de dynamique des systèmes reste le cadre d'exécution. Les jours de sécurité source sont conservés. Les statuts physiques des O.Proc, le périmètre partagé Avène et l'objectif annuel de stock de toute la chaîne 268967 restent des sujets distincts non résolus par ces deux options.

La reproduction utilise [study.py](../../artifacts/testing/mrp_dated_receipts_20260928/study.py), phases `prepare`, `run`, `render`, avec un dossier de travail et un chemin HTML neufs. Les exécutions retenues sont sous `mrp_dated_receipts_20260928/final`. Une première tentative et un premier manifeste de tests ont été refusés car les fichiers de carte changeaient encore ; ils ne constituent pas une preuve réussie. Les quatre calculs et les tests ont été relancés après gel des sources.

Les **55 tests ciblés en mémoire** ont réussi. Les quatre simulations passent les invariants physiques. L'[oracle indépendant sur les ordres, réceptions et cibles](../../artifacts/testing/mrp_dated_receipts_20260928/validation/independent_csv.json) effectue **3 037 989 vérifications** sans anomalie ; le [rapprochement Excel/CSV vers les données du panneau](../../artifacts/testing/mrp_dated_receipts_20260928/payload_result.json) ajoute **443 195 contrôles numériques hérités et 1 308 315 contrôles du nouveau contrat**, sans échec. Le seul contrôle de version de schéma v3 est explicitement remplacé par le contrôle v4 ; les équations de l'oracle précédent restent inchangées. Aucun test d'altération, de disparition, de droits ou de dates de fichiers n'a été utilisé.

Le navigateur a réussi **6 contrôles ciblés** couvrant 33 couples, 471 095 points et 1 933 séries, avec 330 positions SVG échantillonnées, ainsi que **9 contrôles standards**. Les échéances, exports, absences de données, conversions, tableaux avant/après commande et deux suivis de lots sont vérifiés ; aucune erreur JavaScript ni requête réseau n'a été observée pendant le parcours ciblé. Les tableaux larges utilisent un défilement horizontal. Ce parcours ne couvre pas toutes les interactions ni chaque pixel.

Les liens des manifestes finaux et la couverture navigateur sont réunis dans le [bilan de livraison](../../artifacts/testing/mrp_dated_receipts_20260928/manifest.json). Ces preuves valident l'exécution et les calculs annoncés ; elles **ne certifient pas la calibration industrielle**, comme le montrent les écarts ci-dessus.

## 17. Corrections fondées sur les plans sources

### Ce que les données permettent réellement de corriger

**Quantité standard et quantité obligatoire étaient confondues.** La colonne G de FIA s'appelle « Quantité standard de commande ». Pour 338929, `268091.xlsx/FIA!G20` contient 5 000 UN ; pour 333362, `268967.xlsx/FIA!G4` contient 5 000 UN. Ce champ ne définit ni un minimum, ni un multiple obligatoire, ni une quantité maximale à expédier par jour.

La contradiction est vérifiable dans les 52 versions du MRP : seulement **2 des 1 082 H positifs de 338929** sont multiples de 5 000 ; pour 333362, **437 des 741 H positifs ne sont pas multiples de 5 000**. Exemples : H712 = 144 631 étuis ; H648 = 124 000 unités de 333362, H657 = 54 000 et H658 = 221 000. Ces comptes décrivent des lignes de projections successives, pas autant de réceptions industrielles distinctes.

Les variantes corrigées retirent donc le multiple et l'étalement artificiel en tranches de 5 000 pour ces deux couples. Les contraintes physiques de stock, les unités entières et les contraintes de transport effectivement renseignées restent actives. Cela ne crée pas une donnée de palettisation ou un minimum de livraison absent des fichiers.

**La capacité maximale ne constitue pas un besoin permanent.** Le moteur pouvait maintenir des besoins amont à partir de capacité × nomenclature même si la demande prévue était inférieure. Le mode corrigé propage la prévision dans les nomenclatures et entre sites. La capacité continue de limiter l'exécution ; elle ne devient plus un plancher de demande. Une prévision multiniveau et un programme de fabrication déjà développé ne sont pas développés une deuxième fois.

**693055 ne possède pas de processus de fabrication représenté à Gaillac.** Sa nomenclature aval est connue (`268091.xlsx/BOM`, ligne 12 : 406 G pour 1 000 PF), mais pas sa propre nomenclature ni sa capacité industrielle. Le repli historique utilisait un approvisionnement à quatre jours limité par deux jours de signal aval. Il ne s'agit pas d'une règle industrielle. Le nouveau classeur fournit pourtant un lot fixe de 600 000 G (`Taile de Lot!E5`) et le MRP indique un temps de réception de 28 jours à Gaillac. Les variantes corrigées utilisent ces données comme **frontière d'approvisionnement agrégée** : besoin prévu sur délai + revue, disponible et encours déduits, puis arrondi au lot fixe. Les réceptions gardent des lots séparés de 600 kg. La revue quotidienne est conservée comme convention du simulateur ; les 28 jours sont interprétés en jours calendaires, à confirmer. Le délai de transport vers Avène reste séparé à 70 jours. Aucune BOM ni capacité industrielle n'est inventée ; cette frontière ne peut pas simuler les contraintes de fabrication amont de ce composant.

### Règle de couverture et regroupements : vérification hors ajustement

Pour l'étui 338929, une règle de couverture des **trois semaines suivantes**, tenant compte des disponibilités J, reconstitue une part importante des projections. Le calcul autonome part d'un seul solde source au début de chaque segment puis utilise son propre solde ; il ne recopie pas H ou K à chaque semaine. Seuls les segments de semaines renseignées et les décisions au-delà du délai initial sont retenus.

Sur 722 semaines admissibles, **602 réceptions H et 644 soldes K sont retrouvés exactement**. La séparation chronologique donne 331/362 H exacts sur la première moitié des versions et 271/360 sur la seconde, soit **75,28 % sur la période de vérification**. La règle est informative, mais ne reproduit pas toutes les décisions. Elle ne justifie pas de remplacer arbitrairement tous les délais de sécurité par 21 jours.

Les écarts révèlent des regroupements : dans le premier plan, H719 = 289 232 au 13 avril 2025 puis H720 = 0 au 20 avril, au lieu de deux besoins de 144 616. Parmi 30 épisodes d'anticipation qui se résorbent, 29 se terminent pendant une semaine contenant un jour férié national. Cette association est compatible avec un calendrier industriel ; elle ne démontre pas les jours de fermeture de l'entreprise. Le calendrier lundi–vendredi confirmé par l'utilisateur n'est donc pas remplacé automatiquement. Sources calendaires : [API publique 2025](https://calendrier.api.gouv.fr/jours-feries/metropole/2025.json), [Service Public 2026](https://www.service-public.gouv.fr/particuliers/actualites/A18558).

Preuves : [analyse des réceptions et des cellules](../../artifacts/testing/mrp_source_driven_20260928/source_supply/analysis.json), [projection autonome](../../artifacts/testing/mrp_source_driven_20260928/source_supply/autonomous_projection.json), [association au calendrier](../../artifacts/testing/mrp_source_driven_20260928/source_supply/calendar_association.json).

### Prévisions industrielles : utilisation datée, sans copier les résultats

Une variante séparée utilise les **5 178 besoins futurs I des deux produits finis au dépôt**. À chaque décision, seule la dernière version déjà connue est utilisée. Les données H ne deviennent pas des commandes simulées, et K ne remplace pas le stock du modèle. Une semaine absente conserve la prévision nominale ; un zéro explicitement renseigné reste zéro. La demande physique demeure celle de `demand_PF.xlsx`.

Les 104 lignes de semaine courante sont conservées comme preuves mais exclues des nouveaux besoins prévisionnels. Pour 268091, le besoin de la semaine augmente dans chacune des 51 transitions où il devient la semaine courante ; exemple : 73 218 dans le plan du 8 juin, puis 874 805 dans celui du 15 juin. Cela peut agréger des reliquats et ne décrit pas automatiquement de nouvelles ventes à créer chaque semaine. L'état industriel des reliquats n'est pas fourni. Pour les quatre années suivantes, les versions de 2025 sont répétées annuellement : c'est une convention de prolongation, pas quatre années de données industrielles.

### Comparer des stocks de même nature et des périmètres compatibles

La photo d'inventaire porte sur le total détenu. La contribution J à la semaine courante indique ce qui est déjà présent et disponible dans cette période du plan ; les J futurs correspondent à du stock déjà détenu, rendu utilisable plus tard. Comparer directement tout l'inventaire au seul disponible simulé peut donc doubler artificiellement un écart.

Sur les 52 versions, 773474 à Gaillac représente en moyenne **25 169 kg dans l'inventaire**, mais **12 615 kg de J courant** et autant en J futur. Pour 021081, l'inventaire moyen atteint **1 558 863 kg**, contre **447 692 kg de J courant** et **1 111 474 kg en J futur**. Les écarts de date et de périmètre empêchent de supposer une égalité parfaite. Les comparaisons doivent présenter les deux références séparément.

Autre limite démontrée : sur les semaines communes d'une même version, le besoin de 773474 à Gien vaut en médiane **2,96 fois** celui déduit du seul PF268967 par la nomenclature disponible ; à Gaillac, le ratio est 3,53. Ce constat signale des périmètres ou programmes différents. **Il ne constitue pas un facteur de division des stocks.** Les sources ne sont pas redimensionnées pour faire coïncider les courbes. [Oracle nomenclatures et périmètres](../../artifacts/testing/mrp_source_driven_20260928/validation/perimeter-oracle.json).

### Vérification : le premier calcul corrigé a été refusé

Les premiers recalculs sur cinq ans ont révélé des ruptures tardives et douze erreurs de généalogie, malgré la réussite des anciens invariants généraux. Un résidu numérique de fabrication presque nul pouvait prélever une unité de packaging par jour, alors que l'encours n'enregistrait plus de travail. Les contrôles ont retrouvé jusqu'à 78 unités consommées sans lien vers le lot fini. Il s'agit d'un défaut du moteur, pas d'un rebut industriel à ajouter au modèle.

Le moteur neutralise désormais ces résidus avant prélèvement. La qualification rapproche exactement les consommations et la généalogie des campagnes closes, y compris un parent totalement absent des liens. Elle conserve la possibilité d'un encours dans une campagne ouverte et refuse explicitement toute erreur du rapport de parcours des lots. Les preuves précédentes avec ces erreurs restent des échecs ; les succès arithmétiques ou navigateur ne les annulent pas.

### Résultats des corrections après recalcul sur cinq ans

La [carte corrigée](../../resultats/mrp_source_driven_20260928/carte_corrigee.html), bouton **Comparaisons 2025**, permet de superposer quatre calculs : nominal conservé, référence avec paramètres sources et aléas appariés, besoins corrigés avec prévision historique, puis besoins corrigés avec prévisions MRP sources. Les deux derniers utilisent également la frontière 693055 décrite ci-dessus. Les autres onglets et les deux suivis de lots restent ceux du nominal historique ; le panneau ne prétend pas afficher la nouvelle généalogie de chaque variante.

L'écart moyen absolu ci-dessous est calculé sur **52 photos hebdomadaires de 2025**, rapprochées de la clôture simulée précédente, hors photo d'ouverture. Il compare le disponible simulé à la photo totale : **les différences de périmètre précédemment décrites restent applicables**. Ces chiffres ne doivent pas être lus comme une mesure pure de justesse du MRP.

| Article / site | Unité | Référence avec règles sources | Besoins corrigés | Avec prévisions MRP sources |
|---|---|---:|---:|---:|
| 338929 / Avène | UN | 1 317 169 | **229 088** | 794 177 |
| 333362 / Gien | UN | 792 825 | 278 173 | **207 858** |
| 773474 / Gaillac | kg | 21 108 | **13 046** | 15 815 |
| 021081 / Gaillac | kg | **322 608** | 416 299 | 416 299 |
| 268091 / dépôt | UN | 519 057 | 521 550 | **397 256** |
| 268967 / dépôt | UN | 291 701 | **138 669** | 261 774 |

L'étui 338929 passe d'un stock moyen de 1 735 773 à **530 124 UN** aux dates comparées, contre **521 515 UN** dans les photos : son écart absolu moyen diminue de **82,6 %**. Une moyenne proche ne signifie pas que chaque semaine correspond : l'écart hebdomadaire moyen reste de 229 088 UN. Les prévisions industrielles ne sont **pas systématiquement meilleures** : elles améliorent le PF268091, mais augmentent notamment le stock et l'écart du PF268967 et de l'étui par rapport à la variante corrigée à prévision historique.

Contre-vérification de périmètre : en utilisant **J courant**, l'écart moyen de 773474/Gaillac est de 9 662 kg pour la référence, 7 015 kg pour les besoins corrigés et 9 785 kg avec prévisions sources. Le nominal historique est à 9 600 kg. Pour 268967/dépôt, ces écarts sont respectivement 355 357, 165 212 et 374 309 UN, contre **82 451 UN pour le nominal historique**. La nouvelle variante n'est donc pas meilleure que toutes les références sur tous les indicateurs.

Sur cinq ans, les deux variantes servent finalement presque 100 % de la demande des deux PF. Les réapprovisionnements de 693055 représentent respectivement **7 et 8 lots de 600 kg**, reçus chacun après 28 jours ; les commandes de repli à quatre jours disparaissent, ainsi que les blocages de fabrication liés à ce composant. Les douze erreurs de généalogie de la première exécution ont disparu.

**Le service cumulé ne certifie pas la ponctualité.** Avec prévision historique, 268091 connaît encore 22 jours de retard client après le démarrage, jusqu'à 160 544 UN en attente. Avec prévisions sources, aucun stock de commandes clients en attente d'au moins 100 UN n'est relevé après J10. Pour 333362, les blocages de fabrication concernent 56 campagnes dans la première variante et 19 dans la seconde, représentant 982 et 224 journées contraintes. Il ne s'agit pas d'autant d'incidents indépendants. Les stocks au dépôt peuvent protéger les clients pendant ces retards de fabrication.

**Le traitement des besoins par date reste incomplet.** À J1824 dans la variante corrigée à prévision historique, le stock 333362 est nul, mais 272 027 UN de réceptions encore attendues couvrent comptablement la cible : le besoin net est inférieur à une unité. Les 33 réceptions arrivent entre J1828 et J1930. Supprimer le découpage par 5 000 ne résout pas cette anticipation. Exclure simplement ces réceptions et recommander toute leur quantité doublerait l'approvisionnement ; il faut distinguer nouvelles quantités à commander et ordres existants à replanifier, avec leurs possibilités physiques de modification. Le précédent filtre `within_cover` reste désactivé. **Aucune des deux variantes n'est présentée comme une reproduction complète du MRP industriel.**

L'état disponible/indisponible de 021081, le périmètre multiproduit de certaines matières, le calendrier industriel des regroupements et l'état physique des OF initiaux demeurent des limites précises. Les coûts de la frontière 693055 utilisent la convention économique existante faute de coût industriel renseigné : **36 000 € par lot de 600 kg** avec les paramètres courants. Cette valeur n'est pas un prix industriel vérifié et ne permet pas de conclure à un gain économique.

### Preuves finales et reproduction

Reproduction : [recette](../../artifacts/testing/mrp_source_driven_20260928/study.py), [commandes et conventions exactes](../../artifacts/testing/mrp_source_driven_20260928/final_v2/plan.json). Exécuter `prepare`, `run`, puis `render` avec un nouveau `--workdir` et un nouveau `--html` ; les sorties existantes sont protégées contre l'écrasement. Les quatre calculs de 1 825 jours ont duré respectivement 40,5, 52,8, 47,4 et 47,7 secondes dans cette session, contrôles et rendu exclus ; ce relevé ne constitue pas un benchmark comparatif de performance.

Les **33 CSV du nominal sont identiques octet par octet** à la référence conservée. **74 tests ciblés en mémoire** et les invariants des quatre calculs passent sur le code stabilisé. L'oracle indépendant effectue **1 083 945 vérifications sans échec** : prévisions connues à la décision, demande physique conservée, unités entières, propagation des nomenclatures, quantités standards non contraignantes, ordres et réceptions 693055, coûts conventionnels, et rapprochement des stocks. Le contenu numérique de la carte passe en plus **443 195 vérifications existantes et 1 308 315 vérifications du contrat de courbes**, sans anomalie.

Le navigateur hors ligne vérifie les **33 couples, cinq vues et trois conventions hebdomadaires**, 156 choix de version, les exports et l'accès aux deux suivis. **4 174 207 points** sont rapprochés du contenu numérique ; **50 623 positions SVG** sont échantillonnées. Les 31 conventions visibles correspondent aux données embarquées. Les neuf contrôles standards passent aussi, sans erreur JavaScript ni requête réseau pendant les parcours. Les captures ont été examinées ; cet accès aux suivis ne certifie pas chaque lot historique.

Liens : [identité du nominal](../../artifacts/testing/mrp_source_driven_20260928/final_v2/identity.json), [contre-vérification indépendante](../../artifacts/testing/mrp_source_driven_20260928/validation/independent-csv-final-v2.json), [données et courbes](../../artifacts/testing/mrp_source_driven_20260928/payload_result_final.json), [navigateur final](../../artifacts/testing/mrp_source_driven_20260928/ui_v2/review-db1d8742ea9646a3a2315927ec731e3e/manifest.json), [bilan des manifestes](../../artifacts/testing/mrp_source_driven_20260928/manifest.json). Ces contrôles ne certifient pas une calibration industrielle complète. Les premières preuves invalidées ou en échec sont conservées séparément ; elles ne sont pas utilisées comme qualification finale. Aucun test d'altération de fichiers, de dates ou de protections système n'a été effectué.

## 18. Rapprochement du carnet, des plans et des photos de stock

**Les trois fichiers sont complémentaires et ont été croisés par article, division, unité et date.** `Extract_En_cours.xlsx` décrit 104 lignes engagées au démarrage (53 AVICDE, 29 ECHCDE, 22 O.Proc). Le fichier Flow MRP conserve 52 versions des projections, soit 53 398 lignes et 33 couples article/site. Le fichier d'inventaire donne les photos de stock total. Ces photos constituent des observations ; un ordre et une projection restent des prévisions tant que leur exécution n'est pas identifiée.

### Ce qui correspond entre les fichiers

Pour les achats du carnet, **les 49 regroupements article/site/semaine disposant d'une ligne dans le premier plan MRP donnent exactement les mêmes quantités**, en utilisant la date G de livraison et des semaines dimanche–samedi. Quinze autres regroupements n'ont pas de semaine correspondante et restent manquants, pas nuls. Avec la date I de disponibilité, on ne retrouve que cinq égalités, contre 36 différences et 26 semaines absentes. Ce résultat étaye le rattachement des H du premier plan aux livraisons prévues, sans prouver leurs dates réelles d'exécution.

Deux lignes du carnet apparemment identiques ne doivent pas être supprimées : **lignes 63 et 66**, 049371/Avène, 1 800 kg chacune. Avec la ligne 67, elles donnent les **5 400 kg de H445** du MRP. Sans identifiant d'ordre, supprimer l'une ferait perdre une quantité cohérente avec le plan.

Les O.Proc ne sont pas tous rapprochables de la même façon :

- **693055/Gaillac, ligne 103** : 600 000 G, livraison G le 27 janvier, disponibilité I le 25 février. H788 du premier plan contient bien 600 000 G dans la semaine du 26 janvier.
- **773474/Gaillac, ligne 105** : 3 200 000 G, G le 24 janvier, I le 3 mars. H969 contient 9 600 000 G dans la semaine du 19 janvier : le plan agrège trois fois le volume de cet ordre, sans permettre d'identifier les trois ordres.
- Les **20 O.Proc de 268091/Avène**, lignes 72–91, n'ont pas de couple 268091/1810 dans le Flow MRP. Le plan du produit au dépôt ne constitue pas une correspondance directe avec l'usine.

L'analyse rapproche également **1 614 intervalles entre photos** et les ordres initiaux attendus sur ces intervalles. Pour 773474/Gaillac, les photos du 20 et du 27 janvier passent de 6 400 à 9 600 kg : +3 200 kg est compatible avec la livraison G du 24 janvier. Pour 693055/Gaillac, le stock augmente de 600 kg entre le 24 février et le 3 mars, près de la date I du 25 février, tandis qu'il diminuait la semaine du 27 janvier. Ces exemples interdisent d'assimiler automatiquement toute variation à une réception identifiée. Les sorties, transferts et ajustements peuvent se compenser ; le résidu n'est pas déclaré « consommation réelle ».

Sur les 104 lignes, **99 délais G→I correspondent à lundi–vendredi hors jours fériés nationaux**, contre 70 avec seulement lundi–vendredi et trois en jours calendaires. Les cinq exceptions concernent 021081/Gaillac, avec neuf jours ouvrés supplémentaires en traversant août. Une fermeture est plausible, pas démontrée. Cette constatation sur le carnet ne modifie pas le calendrier de sécurité confirmé par l'utilisateur.

Preuves : [correspondances anciennes/nouvelles et cellules](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/crosswalk_v2.json), [104 ordres et contexte des stocks](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/orders_stocks.json), [tableau CSV des rapprochements](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/orders_stocks.csv).

### Anciennes et nouvelles données : différences exactes

L'ancien inventaire d'ouverture contient 32 couples ; le nouveau en contient 31 au 1er janvier. **344135/Gien manque à cette date** dans le nouveau fichier, même si l'ancien stock valait zéro. Parmi les 31 couples communs, **27 quantités sont identiques**. Les quatre différences nouveau−ancien sont : +0,00328125 kg pour 002612/Avène ; −0,172 G pour 038005/Gien ; +1 UN pour 042342/Gien ; +0,000023437 G pour 055703/Avène. Elles ne justifient pas les grands écarts ultérieurs des simulations.

Les règles, en revanche, présentent des différences significatives : minimum de fabrication 268091 de **14 400 à 28 800 UN** ; sécurité du PF268967 au dépôt de **25 à 60 jours ouvrés** ; 426331/Avène de **7 à 10 jours**. La nouvelle source affiche « 00 » pour la sécurité de 268091 au dépôt, contre 20 auparavant : les simulations conservent les **20 jours protégés**, sans essai arbitraire à zéro. Les fichiers ne donnent pas les dates d'entrée en vigueur de ces différences. Pour les temps de réception, neuf couples ancien/nouveau sont identiques et huit diffèrent, notamment 338929 : 4→6 ; 333362 : 4→5 ; 693055/Gaillac : 21→28 ; 773474/Gaillac : 26→33.

Dans le premier plan du 5 janvier, la somme des contributions J, courantes et futures, égale la photo du 6 janvier pour **22 des 31 couples comparables**. Les neuf différences restantes sont conservées : ni égalité universelle supposée, ni remplacement automatique du stock simulé chaque semaine.

Les recettes anciennes ont aussi été recoupées : **46 des 48 liens de nomenclature comparés concordent**, deux sont absents du seul `Data_poc.xlsx` mais présents dans les autres classeurs. Aucune fraction de stock multiproduit n'est déduite arbitrairement de ces rapprochements.

Le 6 janvier, **002612/Gaillac est bien à 1 250 kg**, cellule `Stocks!E946` ; F946 contient la valeur financière 1 575, pas une quantité. La devise n'est pas renseignée dans l'en-tête. La carte historique `02_carte_lots_recente.html` contient encore son ancien extrait à 1 250 414 ; les cartes de comparaison plus récentes et la livraison ci-dessous lisent 1 250. L'index signale cette limite historique.

### Défauts du modèle distingués des incertitudes industrielles

**Un défaut est corrigé dans les variantes, avec nominal conservé.** Le carnet initial réduisait durablement l'horizon de couverture, en plus d'être déduit comme quantités déjà commandées. Pour 333362, six ordres totalisant 629 000 UN étaient reçus entre J58 et J91 ; pourtant ils retranchaient encore 66 jours de couverture à J1824. Le calcul corrigé garde les 125 jours d'horizon, au lieu de 59. Pour 338929, il conserve 92 jours au lieu de 78. Les commandes initiales restent comptées une seule fois en quantités. Les stocks de sécurité, délais physiques et nomenclatures ne sont pas modifiés par cette correction.

**Deux autres défauts de représentation sont localisés mais pas corrigés dans cette livraison :**

- Les dates G et I sont conservées dans les entrées, mais le moteur ne matérialise actuellement l'arrivée qu'à I. Il classe donc encore comme transit les quantités potentiellement présentes entre G et I. Une correction devra passer le même lot du transit au stock bloqué à G, puis au disponible à I, sans seconde réception ni coût. Ces dates restent celles du scénario planifié, pas des observations industrielles.
- Les graphes courants ne séparent pas le stock initial disponible du stock déjà détenu mais disponible plus tard. Pour 021081, le plan du 5 janvier indique **752 312 kg disponibles et 379 880 kg futurs**, soit 1 132 192 kg, égal à la photo du 6 janvier. Le stock initial du 1er janvier est d'une autre date : imposer rétroactivement cette répartition nécessiterait une hypothèse explicite. Les 379 880 kg ne doivent jamais être créés comme un nouvel achat.

Le même délai FIA est en outre utilisé à deux étages, pour l'approvisionnement du fournisseur puis pour son transport vers l'usine. Exemple vérifié du registre précédent pour 338929 : commande amont J0, réception fournisseur J42, expédition immédiate, réception usine J112. La source donne un délai prévisionnel de livraison de 42 jours ; elle ne justifie pas à elle seule cette décomposition et une durée totale de 112 jours. Une distribution Erlang et ce découpage appartiennent au modèle, pas au classeur. [Audit de l'initialisation et états physiques](../../artifacts/testing/mrp_alignment_20260928/engine/initial_receipt_states.json).

### Effet mesuré du correctif et statut de la reproduction

Les quatre simulations de **1 825 jours** ont été relancées. Les **33 CSV du nominal restent identiques**. Les deux variantes corrigées sont comparées à leurs résultats précédents, avec les mêmes entrées et conventions. Écart absolu moyen aux 52 photos de 2025, disponible simulé contre total photographié, clôture précédente :

| Article/site | Unité | Prévision historique avant → après | Prévisions MRP sources avant → après |
|---|---|---:|---:|
| 338929/Avène | UN | 229 088 → 251 787 | 794 177 → 971 633 |
| 333362/Gien | UN | 278 173 → 243 237 | 207 858 → 466 252 |
| 773474/Gaillac | kg | 13 046 → 13 046 | 15 815 → 16 369 |
| 021081/Gaillac | kg | 416 299 → 416 299 | 416 299 → 409 697 |
| 268091/dépôt | UN | 521 550 → 521 550 | 397 256 → 397 256 |
| 268967/dépôt | UN | 138 669 → 160 044 | 261 774 → 367 501 |

**Corriger le double crédit n'améliore pas toutes les courbes.** Le défaut pouvait compenser d'autres écarts de demande, délai ou disponibilité. Ce résultat ne justifie ni de le conserver dans le mode corrigé, ni d'adopter cette variante comme calibration industrielle réussie. La [nouvelle carte de comparaison](../../resultats/mrp_alignment_20260928/carte.html) expose ces calculs ; les autres onglets et les deux suivis restent ceux du nominal historique. [Détail avant/après](../../artifacts/testing/mrp_alignment_20260928/stock_comparison.json).

Une étude séparée évalue des règles de couverture sur les plans, avec sélection sur la première moitié des versions puis vérification sur la seconde. **18 036 points** ont été recalculés et contre-vérifiés indépendamment. H et K ne sont pas recopiés à chaque semaine ; un K source amorce chaque segment contigu, éventuellement situé plus loin dans le plan. Il s'agit donc d'une reproduction conditionnelle par segments, pas d'un MRP complet initialisé une seule fois. Les cibles calendaires se recouvrent entre versions ; la seconde moitié n'est pas constituée d'observations entièrement indépendantes. La contrainte de lancement physique des ordres n'est pas modélisée dans ce diagnostic.

Pour 338929, le candidat trois semaines retrouve **167 des 225 H positifs** de vérification ; l'erreur absolue sur H rapportée au volume source est de **16,32 %**. Pour 268091/dépôt, un candidat fondé sur la valeur source « 00 », uniquement dans cette analyse de fichier et jamais appliqué au nominal, donne une erreur H de 7,13 % mais un écart moyen de K de **267 035 UN**. Reproduire assez bien une réception sans reproduire le solde ne valide pas la règle. Beaucoup d'autres articles restent nettement moins bien reproduits ; aucune sélection n'est intégrée automatiquement au moteur. [Résultats par article](../../artifacts/testing/mrp_alignment_20260928/rule_replay_summary.csv).

La poursuite doit donc porter sur **l'état physique et la disponibilité**, **un délai fournisseur non dupliqué**, puis **l'affectation des besoins et ordres par date** : une commande ferme trop tardive doit produire un retard explicite, pas disparaître du calcul ou être rachetée une seconde fois. Les trois sources fournissent les contraintes de rapprochement de cette étape. Elles ne rendent pas un solde hebdomadaire équivalent à un journal complet des mouvements exécutés.

Vérifications réalisées sur le code stabilisé : **91 tests ciblés en mémoire**, invariants des quatre simulations, contre-calcul indépendant de la couverture sur les cinq ans, unités physiques et généalogie, rapprochement des données et courbes. Les sources industrielles n'ont pas été modifiées. Les durées moteur relevées sont 42,0, 37,6, 38,1 et 41,9 secondes, hors contrôles et rendu ; ce n'est pas un benchmark. Aucun test d'altération de fichiers ou de protection système. [Manifestes et limites de la livraison](../../artifacts/testing/mrp_alignment_20260928/manifest.json).

## 19. Livraison, disponibilité et achats par échéance

### Règles extraites et limites de leur identification

Le [catalogue consolidé](../../artifacts/testing/mrp_execution_20260928/rules/catalogue.json) rapproche **157 champs sur 41 couples article/site**, avec les cellules anciennes et nouvelles, les unités, les différences et les décisions utilisateur. Il distingue quatre états : donnée extraite, propriété démontrée dans les chiffres, hypothèse candidate et information absente. Neuf classeurs sont suivis par empreinte. Les comparaisons Flow MRP portent sur 33 couples ; les populations ne sont donc pas interchangeables.

Le [premier plan du 5 janvier](../../artifacts/testing/mrp_execution_20260928/rules/initial_plan.json) sépare J courant et J futur, besoins I, engagements du carnet et références H/K. **J futur représente du stock déjà présent.** Il ne devient jamais un achat. Pour 021081/Gaillac, 752 312 kg disponibles et 379 880 kg disponibles plus tard composent les 1 132 192 kg détenus. Cette répartition est vérifiée au 5 janvier ; elle n'est pas imposée rétrospectivement à l'ouverture du 1er janvier. Les mouvements détaillés des quatre jours intermédiaires manquent.

Les paramètres explicites sont extraits ; **toutes les règles de décision du MRP industriel ne sont pas identifiées**. Restent notamment le traitement des reliquats, le statut matière des O.Proc, les calendriers de réception, le gel des commandes et le périmètre multiproduit. Les stocks et résultats H/K demeurent des références à retrouver, pas des valeurs injectées chaque semaine pour forcer l'accord.

**Une règle présente dans le catalogue n'est pas nécessairement appliquée intégralement par le nouveau contrôleur.** Les sécurités des sorties de fabrication, les programmes exécutés et les transferts de PF vers le dépôt restent en partie pilotés par le moteur historique. La séparation J courant/J futur du 5 janvier reste un rapprochement à cette date, pas un nouvel état d'ouverture au 1er janvier. Le sens exact du délai de sécurité dans l'ERP, les horizons fermes et les règles de rééchelonnement restent à déterminer. Le calendrier de sécurité confirmé et les valeurs sources ne sont pas abaissés pour améliorer artificiellement les écarts.

### Ce qui change dans le moteur expérimental

Deux modes optionnels s'ajoutent au mode historique. Le moteur physique reste celui de la dynamique des systèmes, avec dépendance à l'état, capacités, nomenclatures et lots. Les paramètres de sécurité du scénario sont préservés : lundi–vendredi, dépôt à 100 %, et 20 jours protégés pour 268091 au dépôt. `tau_process` conserve sa convention de planification.

- **`availability`** : chaque achat initial arrive physiquement à G. Le même lot est bloqué jusqu'à I, puis devient disponible. Cette libération ne crée ni une deuxième livraison ni un nouveau lot. Le stock physique inclut disponible, bloqué et réservé avant départ. La détention du stock bloqué entre dans le coût de stockage selon les taux existants ; les coûts d'achat du carnet initial conservent leur convention historique.
- **`dated`** : un calcul indépendant, [mrp_planning.py](../../simulation/engine/mrp_planning.py), affecte le stock et les engagements aux besoins datés avant de proposer des achats supplémentaires. Un engagement en retard reste attendu et son retard est affiché : il n'est pas automatiquement racheté. Les minimums, multiples et maximums dimensionnent les propositions ; les quantités physiques UN restent entières.
- Le calcul du réseau crédite les fabrications en cours une seule fois et propage les nouveaux besoins par les nomenclatures. La protection de stock est identifiée séparément : **ce n'est pas une consommation physique**. Les achats et transferts de composants sont déclenchés aux dates de lancement, sous contraintes. Les programmes de fabrication et les flux de produits finis vers le dépôt conservent leur pilotage physique antérieur ; les nouvelles propositions les concernant restent des projections.
- Une protection complémentaire non couverte est demandée à la date du calcul augmentée du délai de planification : la commande correspondante peut donc être passée immédiatement. Sa quantité reste la cible diminuée des besoins bruts déjà comptés dans l'horizon, puis le stock et les engagements sont déduits. L'ancienne échéance recalculée à « aujourd'hui + couverture » pouvait repousser indéfiniment le lancement lorsque la couverture dépassait le délai. Cette convention de reconstitution corrige ce report ; elle ne prouve pas une nouvelle règle de stock minimum industriel.
- Pour les nouveaux achats externes concernés, **le délai fournisseur FIA intervient une fois**, de la commande à la livraison. Le temps de réception E s'ajoute ensuite jusqu'à la disponibilité. Son calendrier lundi–vendredi est une convention candidate, distincte du calendrier de sécurité confirmé ; les jours fériés et fermetures ne sont pas inventés. La fabrication du fournisseur et le départ du camion restent inconnus : la livraison est représentée à cette frontière agrégée, avec identité fournisseur, sans trajet détaillé fabriqué.

La fin prévue d'une campagne en cours est également bornée par la disponibilité des composants affectés à son travail restant. Cette contrainte remonte l'amont vers l'aval, puis recalcule le solde et le retard projetés. Un garde-fou exige que le changement des seules dates fermes conserve les mêmes propositions d'achats. C'est une condition nécessaire de disponibilité, **pas un ordonnancement complet sous capacité** ; aucune durée physique supplémentaire n'est ajoutée à `tau_process`.

Les dates G/I du carnet sont des dates **planifiées dans la source**, ensuite exécutées dans le modèle. Elles ne prouvent pas que la livraison industrielle a eu lieu ce jour-là. Les O.Proc ne sont pas reclassés arbitrairement en fabrications déjà consommées.

Le délai de référence sert à planifier ; les délais tirés et la fiabilité des fournisseurs restent des hypothèses du scénario physique. La table des achats présente séparément délai source, délai tiré et temps de réception. Un décalage de livraison simulée ne doit donc pas être attribué automatiquement à une règle du MRP industriel. Une seule graine est comparée ici : cette passe n'est pas une campagne statistique de calibration.

### Comparaison et lecture de la carte

Ouvrir la [carte finale de cette étape](../../resultats/mrp_execution_20260928/carte_mrp.html), puis **Comparaisons 2025**. Le lien de l'index pointe vers cette version ; les essais précédents restent des références séparées.

Le protocole conserve quatre scénarios de 1 825 jours : nominal historique ; prévisions sources avec moteur précédent ; séparation livraison/disponibilité ; achats calculés par échéance. La comparaison industrielle concerne **2025 seulement**. Les quatre années suivantes prolongent les hypothèses de demande et de prévisions de 2025 ; elles ne constituent pas quatre années de données industrielles supplémentaires.

Le panneau de comparaison distingue disponible, bloqué, réservé et total physique. Il présente les dates G/I et les achats exécutés, puis les besoins, engagements, propositions et retards de planification. Une table hebdomadaire permet de comparer les projections à une même date de calcul. Son solde disponible exclut la réserve de planification des consommations et utilise les disponibilités à I : il n'est pas automatiquement équivalent au solde K industriel. La dernière semaine incomplète masque H/K. Le calcul simulé intervient **après production et service client, avant les achats, transferts et expéditions restants du jour** ; son stock de départ peut différer de la clôture quotidienne. L'instant exact de l'export ERP reste inconnu.

Les autres onglets et les deux suivis de lots de la carte conservée restent ceux du nominal historique. Les nouveaux scénarios sont explicitement limités au panneau de comparaison. Le mode daté expérimental refuse les combinaisons non qualifiées avec incidents, préchauffage ou redimensionnement d'état.

### Résultats : amélioration partielle, variante non adoptée comme nominal

Les quatre simulations sont terminées et passent les invariants. **Les 33 CSV du nominal sont identiques à la référence conservée**, ainsi que les 33 CSV de la référence avec prévisions sources à leur précédent calcul. La variante disponibilité préserve les stocks disponibles, les productions, les commandes et la demande de cette référence ; elle ajoute la présence physique et les coûts de détention du stock entre G et I.

La comparaison principale ci-dessous oppose **réceptions datées** et **achats par échéance**, deux modes qui décrivent tous deux disponible + réservé + bloqué. Erreur absolue moyenne aux 52 photos de 2025, avec la clôture simulée de la veille ; unités propres à chaque ligne :

| Article/site | Unité | Réceptions datées | Achats par échéance | Évolution de l'erreur |
|---|---|---:|---:|---:|
| 338929/Avène | UN | 970 525 | 963 646 | −0,7 % |
| 333362/Gien | UN | 464 054 | 366 070 | −21,1 % |
| 773474/Gaillac | kg | 16 369 | 16 369 | 0 % |
| 021081/Gaillac | kg | 689 712 | 689 712 | 0 % |
| 268091/dépôt | UN | 397 256 | 397 256 | 0 % |
| 268967/dépôt | UN | 367 501 | 428 322 | +16,5 % |

Sur les **29 couples comparables**, douze erreurs diminuent, douze augmentent et cinq restent identiques. Les couvertures diffèrent : 344135/Gien ne dispose que de **trois photos**, et 001848/Gien garde un périmètre partiel. Quatre couples sources sont exclus faute de séries comparables. L'erreur de 042342/Gien diminue de 56 566 845 à 52 304 163 UN. En revanche, 693055/Gaillac passe de 862,5 à 1 081,7 kg et 338928/Avène de 345 197 à 667 176 UN. Ces chiffres ne sont pas additionnés entre unités différentes.

Une baisse d'erreur ne suffit pas à établir un bon niveau de stock : pour 338929, le stock physique moyen source vaut 521 515 UN, contre **1 413 142 UN** dans le nouveau mode. Pour 333362, les moyennes sont 322 436 et 647 460 UN ; l'erreur hebdomadaire reste de 366 070 UN. La protection corrigée peut rétablir la fabrication tout en créant trop de stock par rapport aux sources. **La moyenne et la trajectoire doivent être vérifiées séparément.** [Tous les écarts, les deux alignements temporels et les volumes d'achats](../../artifacts/testing/mrp_execution_20260928/impact_v6.json).

Sur cinq ans, les volumes clients servis et les indicateurs de reliquat retrouvent ceux du mode disponibilité. Pour 268967, le retard supplémentaire J968–J974 de l'essai intermédiaire disparaît ; l'accumulation des reliquats revient de 292 995,9 à **8 814,9 UN·jours**. Les reliquats supérieurs à une unité sont limités au démarrage dans ce scénario. Les résidus fractionnaires de prévision restent distingués des mouvements physiques entiers. Un ratio cumulé proche de 100 % n'est toujours ni un service industriel à l'heure ni une validation de l'ERP.

La correction de réserve fait passer les jours de contrainte liés à **344135 en 2025 de 246 à zéro**, entre les deux essais datés. Elle engage notamment 480 000 UN à J0, disponibles J47, et 120 000 à J4, disponibles J20. Ces quantités sont présentes avant le lancement de fabrication J74. L'achat J74 garde le même délai défavorable de 70 jours, avec disponibilité J148 : c'est la protection reconstituée qui évite la rupture, pas une réduction de ce délai. Les capacités configurées ne sont pas augmentées. La fabrication 2025 revient aux volumes du témoin : 1 940 400 PF268967 et 1 900 800 PF268091. Pour 338928, l'achat préventif fait au contraire monter le stock moyen et dégrade l'accord aux photos. [Causalité, bilans et comparaisons des deux essais](../../artifacts/testing/mrp_execution_20260928/engine/impact_v6_diagnostic.json).

**Les quantités et dates MRP ne sont pas encore reproduites.** Sur les 33 couples, l'écart entre H de la semaine courante et les réceptions physiques simulées diminue dans un cas, augmente dans six et reste identique dans 26. H décrit une réception projetée industriellement, pas son exécution observée. La comparaison des plans à même version, entre les deux essais datés, améliore K sur 18 couples mais le dégrade sur dix. L'écart entre H source et les disponibilités projetées du modèle diminue sur huit couples et augmente sur neuf ; **ce dernier calcul compare la livraison H à la disponibilité I, pas deux calendriers de livraison identiques**. Les témoins historiques n'exportent pas ces mêmes projections par version : aucun faux plan K de référence n'est créé. Les sources ne permettent pas d'apparier les identifiants et dates de création des commandes industrielles individuelles. [Métriques H/K, quantités et délais par couple](../../artifacts/testing/mrp_execution_20260928/engine/impact_v6_diagnostic.json).

**Cette variante reste une étude, sans remplacement du nominal.** Les matières partagées, le stock initial indisponible, le calendrier de réception et le couplage entre programmes prévisionnels et exécution physique restent déterminants. Le besoin utilisateur d'un an de couverture sur l'ensemble de la chaîne 268967 n'est pas transformé en un an à chaque nœud ; son périmètre et les coefficients restent à rapprocher avant calibration.

Durées d'exécution, CSV et contrôles internes du moteur compris, qualifications externes et navigateur exclus : nominal **72,2 s** ; prévisions sources **82,7 s** ; séparation G/I **83,2 s** ; achats par échéance **391,5 s**. Le calcul daté coûte ici 4,71 fois le mode disponibilité. Certaines qualifications indépendantes ont tourné en parallèle : ces durées sur une machine et une graine ne constituent pas un benchmark. Cette passe apporte une représentation et des preuves supplémentaires, **pas une accélération du nouveau mode**.

### Vérification des corrections

Les **314 tests ciblés** passent sur le code stabilisé, avec 135 sélecteurs explicitement relus. Ils couvrent les états physiques, les dates, les lots, les exports et le calcul daté, sans altération de fichiers de test. Les simulations de validation ont fait détecter puis corriger des colonnes manquantes dans l'export de généalogie, un arrondi intermédiaire des besoins fractionnaires, des retraits fournisseur fictifs dans un export de flux, une couverture incomplète du calendrier d'une paire introduite par le carnet initial, une date de fin de campagne antérieure à ses composants et le report permanent de la réserve. Le cas d'arrondi a été reproduit sur les valeurs réelles 001893/Avène ; les résidus restent désormais précis jusqu'au dimensionnement et la quantité publique couvre effectivement le besoin. La borne de campagne est vérifiée notamment sur le cas J905/J908/J971 de l'essai précédent et sur deux fabrications dépendantes. Les nouveaux tests imposent une commande préventive quand la protection manque, puis l'absence de double achat une fois la commande engagée ou reçue. Les contrôles de couverture et de bilan n'ont pas été supprimés. [Manifeste des tests](../../artifacts/testing/mrp_execution_20260928/validation/final_v6/tests-08ff7b1253724f0496a994698ff01a2b/manifest.json).

Pour 001848/Gien, l'unité du registre permet de lire les 7 000 kg du carnet sans reprendre les 7 000 000 G bruts comme des kg. L'absence d'état initial dans le graphe reste explicite ; une quantité simulée nulle avant réception ne devient pas une observation industrielle. La carte expose ce périmètre partiel et refuse des unités contradictoires.

Les **18 diagnostics datés** du planificateur pur ont été réexécutés après ses corrections numériques et contre-vérifiés par 1 570 contrôles indépendants : leurs résultats sont inchangés. Ils ne prouvent pas à eux seuls le contrôleur de réserve du réseau ni son raccord au calendrier de fabrication. Pour 021081, le carnet initial suffit à retrouver H/K sur les 25 premières semaines renseignées, sans nouvelle proposition ; cela ne valide pas le mécanisme du plancher de sécurité de 900 000 kg. Pour 338929, le premier segment contient 22 semaines : 2 156 564 UN de besoins, 411 600 UN de stock et engagements, et 1 744 964 UN à compléter. Les retards varient selon le calendrier candidat. Pour 333362, la première séquence ne contient qu'une semaine connue : elle ne permet pas d'identifier sa politique d'achat. [Diagnostic et preuve indépendante](../../artifacts/testing/mrp_execution_20260928/validation/revalidation/refresh.json).

Les quatre qualifications natives réussissent. L'[oracle indépendant des CSV](../../artifacts/testing/mrp_execution_20260928/validation/execution_csv_v6.json) effectue **3 088 981 contrôles**, sans échec : stocks, unités, dates G/I, identité des lots, coûts, commandes et projections. Les **100 CSV des trois scénarios témoins** sont identiques à leur calcul précédent ; la demande physique reste identique dans les quatre scénarios. Les flux du mode daté changent avec la correction de réserve et sont de nouveau contrôlés, sans imposer leur identité avec l'essai refusé.

L'oracle rapproche **1 412 échéances de réserve** avec la date du calcul augmentée du délai. Dans 54 instantanés, un manque doit être couvert immédiatement : les propositions le couvrent. Quinze instantanés ne comportent qu'une réserve déjà couverte et ne rachètent rien ; le cas d'une réserve seule non couverte est vérifié par les tests purs. La borne de disponibilité matière est contrôlée sur **trois campagnes distinctes**, présentes dans huit instantanés, avec 71 besoins de composants. Ces rapprochements d'échéances portent sur les instantanés hebdomadaires exportés de 2025 ; ils ne constituent pas une vérification exhaustive de chaque date prévisionnelle des cinq ans.

L'[oracle du contenu de la carte](../../artifacts/testing/mrp_execution_20260928/validation/payload_v6.json) rapproche les cellules sources et les CSV au contenu numérique affichable : **3 183 827 contrôles**, sans échec. Il vérifie notamment les 55 champs du diagnostic, les stocks, les unités et dates, les tableaux d'achats et les projections. Les empreintes restent stables pendant ces contrôles. Ces nombres décrivent la couverture des rapprochements ; **ils ne mesurent pas la fidélité du modèle à l'industrie**.

La [revue navigateur finale](../../artifacts/testing/mrp_execution_20260928/ui/review-3bea9003a4f94f3788fccc1eb98ba522/manifest.json) parcourt les 33 couples, cinq vues et trois calendriers, ainsi que 156 choix de version. Elle rapproche **5 441 678 points**, 51 163 cellules de projection et 8 226 cellules d'ordres ; 60 832 positions SVG sont échantillonnées. Les exports et l'accès aux deux suivis passent, sans erreur JavaScript ni requête réseau. Les neuf parcours natifs passent également sur le même HTML. Les captures ont été examinées : courbes et légendes sont lisibles, les tableaux les plus larges demandent un défilement horizontal. Cela ne certifie ni chaque pixel ni chaque lot historique.

Le [contrôle d'ensemble des preuves natives](../../artifacts/testing/mrp_execution_20260928/validation/final_v6/gate-a06cd7b873f748cbaefd099ade852ce1/manifest.json) confirme les empreintes du code, des entrées et des résultats. Le [manifeste de livraison](../../artifacts/testing/mrp_execution_20260928/manifest.json) réunit ces vérifications et les contre-calculs indépendants, avec **validation technique réussie, calibration industrielle non acquise et nominal non remplacé**.

### Reproduire cette étape

La [recette existante](../../artifacts/testing/mrp_execution_20260928/study.py) prépare les quatre scénarios, les simule puis construit la carte. Le [plan exécuté](../../artifacts/testing/mrp_execution_20260928/simulation_v6/plan.json) conserve les commandes complètes et les empreintes des entrées. Depuis la racine du dépôt, utiliser un dossier de travail neuf et un nouveau nom de carte :

```powershell
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py prepare --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py run --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py render --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle --html etudecas/resultats/mrp_reproduction_nouvelle.html
```

La recette refuse d'écraser ses fichiers existants. Elle dépend des graphes et recettes précédents cités dans le plan, ainsi que de la carte nominale conservée ; ces fichiers sont donc encore nécessaires à sa reproduction. Les cinq premiers essais de cette étape restent des preuves intermédiaires, avec leurs échecs ou limites documentés. **Seule la livraison `simulation_v6` est retenue ici.** Aucun test d'altération de fichiers, de dates ou de protections système n'a été effectué.

## Preuves et reproduction

Complément modèle : [calculs reproductibles](../../artifacts/testing/mrp_system_comparison_20260928/analyse.py) et [résultats / empreintes des 18 entrées inchangées](../../artifacts/testing/mrp_system_comparison_20260928/evidence.json). Trois audits indépendants en lecture seule ont couvert le moteur, les besoins/périmètres et les stocks/réceptions ; les regroupements des 23 commandes 021081 et les deux alignements ont été contre-calculés séparément. Aucune nouvelle simulation ni aucun test d'altération de fichiers n'a été lancé pour ce complément.

[Données détaillées de l'analyse](../../artifacts/testing/mrp_source_rules_20260928/analysis.json) · [Oracle indépendant sur les Excel](../../artifacts/testing/mrp_source_rules_20260928/validation/export-oracle.json) · [Script de lecture](../../artifacts/testing/mrp_source_rules_20260928/analyse.py).

Les deux calculs indépendants de l'audit initial rapprochent les cellules et les équations du MRP. Ils ne prouvent pas l'identité d'un algorithme ERP non fourni. Cet audit initial n'a changé aucun moteur, stock nominal ou carte. Les étapes ultérieures sont décrites en sections 15 à 19 ; les fichiers industriels restent inchangés.
