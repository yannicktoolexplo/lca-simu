# Règles MRP : analyse des sources industrielles et comparaison avec le moteur

## Fin 2025 : étendre la protection du stock partagé à 001757 et 002612

**Résultat : amélioration nette de 001757 et 002612, sans ajout de réceptions partielles ni modification des jours de sécurité.** Les deux nouveaux calculs de cinq ans ont terminé avec retour nul et empreintes inchangées (875,063 et 882,907 secondes). La variante `total_extension` est la meilleure des deux sur l'écart annuel de ces matières ; l'ancienne référence reste conservée pour comparaison.

| Écart absolu moyen aux photos 2025, kg | Référence | Sécurité partagée | Sécurité + besoins industriels totaux |
|---|---:|---:|---:|
| 001757 / année entière | 2 504,086 | 1 906,032 | **1 425,327** |
| 001757 / octobre–décembre | 4 276,469 | 2 549,027 | **1 275,801** |
| 002612 / année entière | 58 360,198 | 28 230,845 | **27 365,461** |
| 002612 / octobre–décembre | 68 019,345 | **34 202,691** | **34 202,691** |
| 055703 / année entière | 147,241 | 147,230 | 147,230 |
| 055703 / octobre–décembre | 119,403 | 113,826 | 113,826 |

Les écarts du dernier trimestre diminuent d'environ **70 % pour 001757** et **50 % pour 002612**. Pour ce dernier, le gain vient surtout de la sécurité persistante : le rapprochement du total I améliore légèrement certaines dates antérieures mais n'ajoute pas de gain au quatrième trimestre. Pour 001757, les deux mécanismes contribuent.

| Dernière photo, 29 décembre, stock physique en kg | Source | Référence simulée | Sécurité + besoins totaux |
|---|---:|---:|---:|
| 001757 / Avène | 9 368,378 | 4 498,613 | 7 824,444 |
| 002612 / Avène | 114 339,772 | 22 731,290 | 67 263,578 |
| 055703 / Avène | 933,345 | 979,698 | 960,989 |

Le résidu de **47 076 kg sur 002612** reste important : ces résultats ne justifient pas de déclarer sa calibration achevée ni d'augmenter arbitrairement la sécurité. Pour 055703, aucun paramètre d'achat n'a changé ; les 18,70848 kg supplémentaires consommés par la production expliquent le changement de stock final. L'écart annuel est pratiquement inchangé : ce n'est pas une nouvelle règle de calendrier validée pour cette matière.

### Disponibilité, service et effets sur les autres matières

Pour 002612, les jours à stock physique nul passent de **12 à zéro**, et ceux à stock disponible nul de **166 à zéro**, sur 2025. Le service simulé du PF268091 passe de **3 211 453 à 3 441 853 UN**, soit 230 400 UN de plus ; le reliquat de demande en fin d'année passe de 364 989 à 134 589 UN. La demande et le service du PF268967 sont inchangés. Les scénarios de demandes physiques des autres usages sont identiques ; leur consommation et la production sont contrôlées séparément.

Sur les cinq années simulées, la quantité totale livrée aux clients est identique ; la demande est rattrapée plus tôt. Aucun jour ne présente un arriéré client supérieur à celui de la référence dans les deux variantes.

Sur 29 couples comparables : **11 améliorent leur écart annuel, 12 restent identiques, 6 se dégradent légèrement**. Les six dégradations restent inférieures à 1,1 % sur cet indicateur : 001893/Avène (+158,078 kg de MAE), 029313 (+1,797 kg), 049371 (+36,763 kg), 099439 (+2,333 kg), 693055/Avène (+5,867 kg) et 426331 (+32,327 UN). Les unités ne sont pas additionnées pour fabriquer un score global. Ces effets aval accompagnent la production supplémentaire et restent visibles dans les courbes.

[Comparaison interactive, ouverte sur 001757](../../resultats/regroupement_001757_20260929/comparaison_mrp_securite_partagee.html) · [carte complète avec ce panneau](../../resultats/regroupement_001757_20260929/carte_mrp_securite_partagee.html) · [indicateurs annuels, dernier trimestre et service](../../artifacts/testing/mrp_year_end_20261001/analysis.json). Les autres panneaux et les deux suivis de lots de la carte complète restent historiques ; ils ne représentent pas les nouveaux calculs.

Étude isolée `mrp_year_end_20261001`, depuis la référence conservée du précédent essai. L'objectif est de rapprocher les stocks de fin d'année sans ajouter de réceptions partielles. **Le moteur n'est pas modifié** : deux graphes activent des mécanismes existants, en conservant les commandes et cartes antérieures.

Le premier candidat, `safety_extension`, applique à 001757/Avène et 002612/Avène la protection persistante déjà utilisée pour 055703 : garder la sécurité source dans le solde projeté, sans la consommer comme un besoin supplémentaire. La quantité est calculée avec la moyenne prévisionnelle globale existante et les **20 jours ouvrés sources**, puis combinée par maximum avec le complément de couverture. Cela ne réactive pas la protection sur besoins datés rejetée lors de l'essai précédent. Le second candidat, `total_extension`, ajoute uniquement le rapprochement hebdomadaire des besoins propres avec le total industriel I renseigné, comme pour 055703.

| Paramètre conservé | 001757 / Avène | 002612 / Avène |
|---|---:|---:|
| Fournisseur déjà utilisé par la référence | VD0951020A | VD0910216A |
| Prix FIA normalisé | 5,43 €/kg | 0,82 €/kg |
| Délai fournisseur | 84 jours | 35 jours |
| Traitement à réception | 13 jours ouvrés | 9 jours ouvrés |
| Standard de commande | 100 kg | 22 500 kg |
| Sécurité source | 20 jours ouvrés | 20 jours ouvrés |

La sélection explicite conserve les fournisseurs des 383 achats 001757 et des 42 achats 002612 de la référence sur cinq ans. Elle ne prouve pas une exclusivité industrielle. Les délais, stocks initiaux, hypothèses de demandes physiques des autres produits et nomenclatures restent identiques ; les consommations exécutées peuvent évoluer si la disponibilité permet davantage de production.

### Diagnostic avant essai

Les prévisions ne s'arrêtent pas au 31 décembre : l'horizon simulé reste de 364 jours et les versions MRP connues en automne portent déjà des besoins de 2026. Dans le plan du 28 décembre, I projeté en 2026 totalise 30 720 kg pour 001757, 312 131,346 kg pour 002612 et 2 135,6 kg pour 055703. Les quantités proviennent d'une seule version, jamais de la somme des plans successifs.

La référence ne déclare pas de protection persistante pour les deux premières matières. Le 26 octobre, la sécurité issue du taux global et des 20 jours ouvrés représente environ 2 977 kg pour 001757 et 42 333 kg pour 002612 ; l'exigence complémentaire de réserve du plan vaut respectivement environ 126 kg et zéro. Une partie de la cible est absorbée par les besoins déjà présents dans la couverture : cela ne maintient pas nécessairement cette sécurité disponible au fil du plan. Les champs historiques `safety_floor_qty` et `target_stock_qty` sont ceux du périmètre propre ; ils ne doivent pas être présentés comme toute la protection du stock industriel partagé.

La réconciliation du total I doit être examinée séparément. La quote-part de 72,18 % de 001757 n'est **pas** une preuve de 27,82 % de besoins totaux manquants : les besoins propres s'y ajoutent. Sur les semaines renseignées du plan du 26 octobre, le modèle représente environ 27 752 kg contre 30 480 kg sources ; pour 002612, le rapprochement se situe déjà autour de 100 %. La différence de répartition hebdomadaire peut compter même lorsque le total sur l'horizon est proche.

Pour la dernière photo de 002612, `Stocks!E1393 = 114 339,772 kg`. Dans le plan du 28 décembre, `Feuille1!J52500 = 98 089,772 kg` et `J52501 = 16 250 kg` disponibles plus tard : leur somme égale le stock physique. Les 16 250 kg ne constituent pas une réception future à ajouter. Le stock simulé comparable est de 22 731,290 kg. Pour 001757, la dernière photo vaut 9 368,378 kg contre 4 498,613 kg simulés. Pour 055703, le déficit se concentre sur certaines dates de réception ; le dernier stock simulé de 979,698 kg dépasse légèrement la photo de 933,345 kg.

[Protocole des deux calculs de cinq ans](../../artifacts/testing/mrp_year_end_20261001/plan.json) · [lecture des sources](../../artifacts/testing/mrp_year_end_20261001/source_review.json) · [contrôle indépendant des graphes et des 3 549 lignes I ajoutées](../../artifacts/testing/mrp_year_end_20261001/independent_preflight.json).

Précision d'unité : 002612/Avène est déjà en **KG** dans le Flow MRP ; 001757 et 055703 y sont en **G**. Les lectures appliquent l'unité de chaque ligne. Aucune conversion globale supplémentaire n'est effectuée. Le diagnostic complémentaire 055703 ne permet pas d'identifier une nouvelle règle commune d'anticipation : les occurrences H de 300 kg restent souvent 40 à 50 jours ouvrés avant le manque théorique, mais H, les engagements fermes et le traitement à réception ne sont pas suffisamment distingués pour en déduire une sécurité à augmenter. [Calcul contrefactuel et limites](../../artifacts/testing/mrp_year_end_20261001/source_055703_timing.json).

### Résidu 002612 : les achats ne sont pas l'unique explication possible

Le candidat reçoit 720 000 kg en 2025 et consomme 806 258,059 kg, dont 804 036,427 kg pour les autres usages estimés. Si cette consommation représentait exactement la consommation industrielle, le stock source final impliquerait environ 767 076 kg d'entrées, soit 47 076 kg de plus. C'est une identité **conditionnelle**, pas une mesure de livraisons manquantes.

Les 52 versions montrent 16 apparitions ou augmentations de J futur, en évitant de recompter les répétitions, mais ce registre n'est pas exhaustif : des hausses physiques de 28 991 kg le 25 août, 38 103 kg le 13 octobre et 12 312 kg le 3 novembre ne sont accompagnées d'aucun nouveau J futur visible. La somme J concorde avec 51 photos sur 52 ; le plan du 2 mars présente un désaccord de 13 026 kg avec la photo suivante. Ni le total de J apparus ni les seules hausses de stock ne reconstituent donc toutes les entrées.

Une reconstruction très restrictive du 6 octobre au 29 décembre, sans livraison masquée et avec des lots FIA supposés sur les hausses non expliquées, donnerait 112 917 à 119 367 kg de sorties nettes, contre 157 123 kg consommés dans la simulation. Cela illustre une autre explication possible du résidu : des consommations estimées trop élevées. **Ce n'est ni un intervalle de confiance ni une preuve permettant de réduire la demande physique.** Des entrées masquées par des consommations peuvent invalider ce calcul. Aucun paramètre de consommation n'est ajusté sur cette hypothèse. [Épisodes, cellules, bornes et hypothèses détaillées](../../artifacts/testing/mrp_year_end_20261001/source_002612_balance.json).

Validation de l'essai : les CSV des deux nouveaux calculs et la navigation de la carte complète passent la toolbox. Les preuves de 28 tests ciblés et du doctor existants sont réutilisées après vérification des empreintes, puisque le moteur est inchangé ; elles ne sont pas présentées comme de nouveaux tests exécutés pour cet essai. La contre-vérification indépendante contrôle 3 285 bilans physiques quotidiens, 10 950 contrôles de sécurité et 7 186 fenêtres de rapprochement I. Le navigateur vérifie 4 377 valeurs de stock, 117 valeurs filtrées sur le dernier trimestre et 64 cellules MRP, sans erreur JavaScript. [Contre-vérification](../../artifacts/testing/mrp_year_end_20261001/independent_final_review.json) · [preuves regroupées](../../artifacts/testing/mrp_year_end_20261001/native_final/gate-0b36ba13940f41a99e8c37625671560c/manifest.json).

## Essai de sécurité sur besoins datés et vérification des arrondis

**Résultat : ne pas retenir cette option comme nouvelle référence.** Les trois simulations de cinq ans ont terminé normalement. Le témoin reproduit les 38 CSV précédents à l'octet près. Sur les 29 couples article/site comparables en 2025, aucun n'améliore son écart moyen absolu aux photos ; 055703 se dégrade et les 28 autres restent identiques à cette précision. Les consommations et le service client sont inchangés dans ces essais.

| Écart moyen absolu aux 52 photos hebdomadaires | Référence | Protection par besoins datés |
|---|---:|---:|
| 055703 / Avène | 147,241 kg | 151,025 kg |
| 039668 / Avène | 135,971 kg | 135,971 kg |
| 708073 / Gien | 3 969,257 kg | 3 969,257 kg |

Le stock physique 055703 au 29 juin reste à 879,585 kg dans les trois calculs, contre 1 170,790 kg dans la photo du 30 juin. Dix nouvelles commandes de 300 kg et 3 300 kg reçus dans l'année, engagement initial compris, sont conservés. La nouvelle règle décale quelques commandes sans résoudre l'écart de juin. Pour 039668, la moyenne sur photos masque même deux jours supplémentaires à stock physique nul : trois au lieu d'un. La comparaison hebdomadaire ne suffit donc pas à vérifier tous les effets quotidiens.

Le 6 avril, le nouveau calcul augmente le besoin net à lancer de 22,919911 à 132,985770 kg ; **les deux donnent toujours 300 kg après arrondi**, le même jour. Le complément de couverture vaut zéro sur 361 des 365 jours de 055703 : il n'est pas la cause principale de ce faible effet. Les fenêtres futures intégralement connues sont présentes 226 jours sur 365 ; les 139 autres lendemains conservent explicitement la protection historique. L'essai ne démontre ni que toutes les sécurités datées sont inutiles, ni que la moyenne explique à elle seule le système réel.

[Comparaison interactive de l'essai](../../resultats/regroupement_001757_20260929/comparaison_mrp_securite_besoins_dates.html) · [résultats numériques](../../artifacts/testing/mrp_dated_safety_20261001/analysis.json) · [reproduction du témoin](../../artifacts/testing/mrp_dated_safety_20261001/baseline_equivalence.json). L'option reste expérimentale, désactivée dans la référence conservée. Les anciens panneaux et suivis de lots de la carte complète gardent leurs données historiques ; seuls les panneaux de comparaison présentent ces trois nouveaux calculs.

Contrôles exécutés : 28 cas ciblés en mémoire, qualification des CSV des trois calculs et navigation hors ligne de la carte complète. La contre-vérification indépendante contrôle notamment 7 300 décisions quotidiennes et 75 920 niveaux de protection reconstruits sans les helpers de production. Le rapprochement navigateur porte sur 4 377 valeurs de stock, 90 cellules du tableau de sécurité et 2 190 points des nouvelles courbes, sans erreur JavaScript. Ces contrôles vérifient le calcul et son affichage ; l'essai reste négatif pour la calibration industrielle. [Contre-vérification](../../artifacts/testing/mrp_dated_safety_20261001/independent_final_review.json) · [rapport navigateur détaillé](../../artifacts/testing/mrp_dated_safety_20261001/view_2ea73c62/report.json).

Protocole `mrp_dated_safety_20261001` : trois calculs distincts de 1 825 jours à partir du dernier candidat 055703 utilisant tout le besoin MRP renseigné. Le témoin conserve la protection par moyenne ; le deuxième modifie uniquement 055703/Avène ; le troisième applique la même modification à 055703/Avène, 039668/Avène et 708073/Gien. Les prévisions de ces deux dernières matières restent celles de la référence : le test ne leur ajoute pas simultanément le total industriel. [Protocole et commandes](../../artifacts/testing/mrp_dated_safety_20261001/plan.json).

Pour chaque clôture projetée `t`, l'option `dated_requirements_with_coverage` protège :

`P(t) = max(quantité fixe de sécurité source, somme des besoins datés dans ]t ; t + N jours ouvrés sources])`.

Le calendrier lundi–vendredi détermine la borne finale ; les besoins alloués aux samedis et dimanches à l'intérieur de cette fenêtre ne disparaissent pas. La protection débute le lendemain de la décision. Les besoins propres sont propagés par la BOM avant le rapprochement avec le total industriel et avant ce calcul de protection. Il n'y a ni consommation supplémentaire, ni cumul de la protection de chaque jour comme s'il s'agissait de nouvelles sorties.

La fenêtre doit être intégralement renseignée dans les prévisions connues à la décision. Les valeurs nulles explicites comptent comme renseignées ; une période absente, une version encore inconnue ou une fin d'horizon ne devient pas un besoin industriel nul. Dans ces cas, l'option conserve explicitement le plancher historique. Le complément historique de couverture reste activé à sa date précédente ; son maximum avec P(t) est utilisé, jamais leur somme. Les métadonnées et les traces distinguent fenêtres renseignées et retour à la moyenne.

### L'arrondi au multiple supérieur existe déjà pour les commandes

Dans la voie d'achat agrégée de 055703, le moteur déduit d'abord stocks et engagements du besoin. Les propositions futures peuvent encore être au besoin net exact ; lors du lancement, la somme à émettre est arrondie au standard supérieur, dans la limite de la capacité représentée. Avec une capacité suffisante et un standard de 300 kg :

| Besoin net à commander | Commande émise |
|---:|---:|
| 299 kg | 300 kg |
| 300 kg | 300 kg |
| 305 kg | 600 kg |
| 600 kg | 600 kg |
| 601 kg | 900 kg |

305 kg de besoin **brut** avec 5 kg déjà disponibles, ou engagés et affectés, ne laisse que 300 kg nets : la commande est alors de 300 kg. Les propositions futures de 055703 ne sont donc pas identiques à des commandes déjà émises. Appliquer le multiple dès la proposition serait une expérience distincte ; le présent test de sécurité ne modifie pas cet arrondi. La quantité standard de la FIA ne prouve pas seule qu'un multiple est contractuellement obligatoire : il s'agit de la convention actuelle, compatible avec les lots 055703 représentés. [Audit de l'arrondi](../../artifacts/testing/mrp_dated_safety_20261001/rounding_review.json).

### Les arrondis visibles dans les plans industriels

Lecture des 53 398 lignes de `Flow_Data_MRP_results.xlsx`, versions du 5 janvier au 28 décembre 2025. Les valeurs H de ces trois matières sont exprimées en grammes dans la source et converties ici en kg. **Les comptes ci-dessous sont des cellules dans 52 versions successives, pas des commandes distinctes ni des achats annuels.** Toutes les semaines projetées des versions 2025 sont incluses, y compris celles de 2026.

| Matière | Standard FIA | Quantités positives H dans les plans |
|---|---:|---|
| 055703 / Avène | 300 kg | 187 cellules à 300 kg ; 2 à 450 kg ; 52 inférieures à 300 kg |
| 039668 / Avène | 450 kg | 55 cellules à 450 kg ; 24 à 300 kg ; 54 autres inférieures à 450 kg |
| 708073 / Gien | 5 000 kg | 32 cellules à 5 000 kg ; 209 à 10 000 kg |

Pour 055703, **chacune des 52 versions comporte exactement une dernière entrée positive inférieure au standard**. Exemples : `Feuille1!H494`, plan du 5 janvier, semaine du 15 juin, 101,564999 kg ; `H52811`, plan du 28 décembre, semaine du 21 juin 2026, 135,254979 kg. Les exceptions à 450 kg se trouvent en `H1441` et `H3470`. Pour 039668, la dernière entrée positive est également inférieure à 450 kg dans les 52 versions, mais 26 autres entrées inférieures précèdent ces dernières entrées. Pour 708073, les 108 cellules positives visant une semaine de 2025 sont toutes de 10 000 kg, soit deux standards.

Cela justifie d'étudier séparément le regroupement des besoins, l'arrondi des commandes émises et le traitement du dernier approvisionnement projeté. Le motif de fin de plan est observé ; son mécanisme ERP reste à établir. H représente des entrées hebdomadaires prévues et agrégées, pas des réceptions exécutées. Des multiples ne prouvent pas à eux seuls un `ceil(besoin net / standard)` sans reconstruire l'état connu à la décision. [Audit source avec cellules, fournisseurs, prix, délais et empreintes](../../artifacts/testing/mrp_dated_safety_20261001/source_rounding_review.json).

## 055703 : distinguer consommation et calendrier des réceptions

Cette contre-analyse utilise le candidat `mrp_055703_full_needs_20261001` sans le modifier ni recalculer une nouvelle trajectoire. Elle reprend directement les deux classeurs sources, les 53 photos (ouverture incluse), les 52 versions MRP et les registres du calcul. [Calcul reproductible](../../artifacts/testing/mrp_055703_balance_20261001/audit.py) · [résultats détaillés](../../artifacts/testing/mrp_055703_balance_20261001/analysis.json) · [preuves et limites](../../artifacts/testing/mrp_055703_balance_20261001/manifest.json).

**Le résidu de juin indique surtout un décalage des approvisionnements, pas une consommation physique à majorer de 81 % à 100 %.** Les sources présentent sept hausses importantes avant le 30 juin, chacune accompagnée de 300 kg en J futur dans le même plan : matière déjà présente, en attente de disponibilité. Sur l'année, onze épisodes sont corroborés. La petite hausse de 0,22 kg au 29 décembre ne constitue pas une livraison standard.

Ces épisodes permettent une reconstruction conditionnelle, pas une identification certaine de chaque livraison. Sous l'hypothèse d'un arrivage de 300 kg par épisode et sans mouvement supplémentaire masqué :

`sorties nettes reconstituées = stock initial + réceptions reconstituées − stock photographié`

Les sorties nettes peuvent inclure consommation, transfert, perte ou correction. La colonne H des plans reste une prévision et n'est jamais utilisée comme preuve de réception exécutée.

| Cumul au 30 juin, simulation à la clôture du 29 juin | Sources / reconstruction conditionnelle | Simulation |
|---|---:|---:|
| Stock initial | 569,805 kg | 569,805 kg |
| Réceptions physiques | 2 100 kg, sept épisodes | 1 800 kg, six réceptions |
| Sorties nettes / consommations | 1 499,015 kg | 1 490,220 kg |
| Stock physique final | 1 170,790 kg | 879,585 kg |

Ainsi, `291,205 kg de différence de stock = 300 kg de différence d'entrées − 8,795 kg de différence de sorties`. L'écart de sorties représente environ 0,59 % des sorties nettes reconstituées. La proximité est un indice fort, mais dépend de l'hypothèse d'arrivages et ne prouve pas l'absence de mouvements masqués.

À la dernière photo du 29 décembre, les réceptions cumulées reconstituées et simulées sont toutes deux de 3 300 kg. Les sorties nettes sources sont de 2 936,460 kg, contre 2 890,107 kg consommés en simulation ; les stocks valent respectivement 933,345 et 979,698 kg. L'écart de sorties est d'environ 1,58 %. Les volumes cumulés annuels sont donc proches, tandis que la répartition des réceptions au cours de l'année reste différente.

### Ce que signifie réellement la part de 81,07 %

La part provient du premier plan connu : 1 799,35 kg de besoins industriels sur l'horizon commun et 340,5691212 kg de besoin théorique déduit de la prévision du PF et de la BOM. Le résidu vaut 1 458,7808788 kg, soit 81,0726583933 %. C'est une **hypothèse de répartition des usages**, pas un paramètre de l'ERP ni une mesure de consommation. L'horizon commun contient des semaines sans ligne : il ne faut pas présenter cette fraction comme une mesure annuelle exhaustive.

Depuis la correction précédente, les futurs achats de 055703 utilisent le total industriel renseigné, réconcilié avec les besoins propres. Les sorties physiques des autres usages gardent cette estimation et la sélection causale des versions. Le présent bilan ne justifie pas de les remplacer mécaniquement par 100 % de I : cela augmenterait les sorties alors que leur cumul est déjà proche de la reconstruction source.

### Disponibilité : une semaine n'est pas une date d'exécution exacte

`J25530` place les 300 kg du plan du 29 juin dans **la semaine commençant le 6 juillet**. Le 6 juillet ne prouve pas une libération exactement ce jour-là. L'ancien commentaire « 6 juillet contre 14 juillet » donnait une précision quotidienne excessive. Le modèle libère le 14 juillet après réception le 25 juin et treize jours lundi–vendredi. Avec la convention de buckets dimanche–samedi, une réception industrielle le 24 juin suivie de treize jours ouvrés aboutirait au 11 juillet, dans le bucket source. Les photos hebdomadaires ne donnent pas le jour exact de réception.

La convention de treize jours est aussi cohérente avec l'engagement initial `Extract_En_cours.xlsx`, ligne 69 : réception prévue le 17 janvier, disponibilité prévue le 5 février. Les autres épisodes annuels sont compatibles avec treize jours ouvrés pour au moins une date de réception dans leur intervalle photographique. **Aucune correction automatique du délai qualité à sept jours n'est justifiée.**

### Deux précautions sources importantes

- Plan du 2 mars : `J8465 + J8467 = 1 006,945002 kg`, contre 746,790002 kg sur la photo du 3 mars (`Stocks!E1374`). Le total MRP correspond à la photo du 10 mars. Ce décalage de 260,155 kg reste signalé ; le lot de 300 kg n'est pas compté deux fois. Les 51 autres rapprochements hebdomadaires concordent.
- Les photos des 28 juillet, 4 août, 11 août et 18 août restent à 786,625001 kg, alors que I en semaine courante conserve 65,6 kg. Un besoin MRP courant n'est donc pas une consommation exécutée. Cette période est cohérente avec une activité réduite ou arrêtée ; elle ne permet pas, seule, d'identifier chaque mouvement.

La prochaine correction du modèle doit porter sur le déclenchement daté des achats et être testée contre ces cumuls, en conservant les consommations et les sécurités sources. Le bilan ne justifie pas d'ajouter arbitrairement un lot ni d'injecter les réceptions reconstituées comme commandes fermes.

### Piste de déclenchement identifiée, encore à tester

Le simulateur transforme les trente jours ouvrés de sécurité en une quantité calculée avec une **moyenne prévisionnelle sur 120 jours**. Cette moyenne peut masquer la concentration des besoins à court terme. Le 16 mars (J74), une révision fait passer la protection d'environ 491,77 kg au 12 mars à 372,84 kg, alors que le total des besoins industriels sur l'horizon exporté augmente d'environ 1 876,65 à 2 182,64 kg. Ces deux mesures ne portent pas sur la même fenêtre : la baisse de la moyenne proche n'est donc pas, en soi, une erreur de somme.

Le 5 avril, la protection reste à 372,01 kg et ne déclenche pas d'achat. Le 6 avril, une nouvelle version fait passer le taux moyen de 9,0733 à 10,2762 kg/jour et la protection à 411,05 kg. Un besoin net de 22,9199 kg déclenche alors une commande standard de 300 kg, reçue le 27 avril. Or le plan industriel du 16 mars porte déjà une entrée H de 300 kg pour la semaine du 23 mars (`Feuille1!H10460`). Cette entrée demeure une prévision, pas un ordre identifié.

**Hypothèse commune à éprouver ensuite :** préserver les trente jours ouvrés sources, mais comparer la protection fondée sur une moyenne à une protection calculée sur les besoins réellement datés de la fenêtre concernée. Le scénario industriel et le simulateur n'ont déjà plus le même stock à ces dates : cette observation ne suffit pas à démontrer que la moyenne sur 120 jours est l'unique cause, ni que sa suppression améliorera les autres matières. Aucune modification de cette règle n'est appliquée dans le présent diagnostic.

## 055703 : utiliser le total industriel dans la planification des achats

Demande utilisateur : prendre en compte **100 % des besoins MRP sources de 055703 à Avène**. La règle commune est activée pour ce seul couple dans l'essai `mrp_055703_full_needs_20261001`, à partir du scénario de couverture conservée précédent. Il s'agit des besoins prévus colonne I, pas d'ordres industriels injectés dans le modèle.

Pour chaque semaine renseignée de la version connue à la date du calcul, après propagation de nos besoins de fabrication :

`complément de planning = max(total industriel I − besoins propres déjà datés, 0)`

`besoins retenus = besoins propres + complément de planning`

Le complément remplace les futurs besoins « autres usages » estimés sur cette semaine. Il ne s'ajoute pas à leur ancienne quote-part de 81,0726583933 %. Ainsi, un total source de 100 kg et 30 kg de besoins propres donnent 70 kg de complément et **100 kg à planifier**, pas 130 ou 180 kg. Lorsque nos besoins propres dépassent le total industriel, ils sont conservés et le dépassement reste visible. Ce cas n'est pas présenté comme une égalité à la source.

Les périodes sont rapprochées **par semaine**, pas par maximum quotidien : un besoin propre de 100 kg concentré sur un seul jour est déjà inclus dans une semaine source de 100 kg. La partie restante d'une semaine est proratisée selon la répartition uniforme existante ; le fichier ne donne pas le calendrier quotidien réel. La semaine courante reste figée, les révisions remplacent les prévisions futures et aucune version future n'est utilisée avant sa date de connaissance. Une semaine absente conserve les besoins reconstruits précédents ; une valeur I égale à zéro reste une donnée distincte. Pour 055703, le contrôle direct du classeur compte **52 versions, 1 725 lignes futures I, dont 10 zéros explicites**.

La moyenne de besoins utilisée pour calculer sécurité et couverture suit le plan ainsi réconcilié. Les jours et quantités fixes de sécurité, prix, fournisseurs, standards de commande, délais FIA et stocks initiaux restent inchangés. Les arriérés physiques déjà dus restent comptés séparément ; leur éventuelle inclusion dans I n'est pas identifiable dans ces extractions.

**La correction porte sur les besoins de planification, pas sur une consommation physique supplémentaire.** Les fabrications consomment leurs composants et les autres usages suivent leur scénario documenté. Transformer le complément de planning en sortie physique créerait un double compte ou modifierait le périmètre sans preuve. Les effets sur stocks et surstock doivent donc être mesurés par la simulation, même si les courbes de besoins sont désormais cohérentes avec les sources.

### Résultats de la correction sur 2025

[Comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_mrp_055703_besoins_complets.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_055703_besoins_complets.html) · [protocole reproductible](../../artifacts/testing/mrp_055703_full_needs_20261001/plan.json).

| Indicateur 055703 / Avène | Avant | Besoins industriels complets |
|---|---:|---:|
| Écart absolu moyen aux 52 photos de stock physique | 205,14 kg | **147,24 kg** |
| Stock simulé à la clôture du 29 juin, pour la photo du 30 juin | 579,59 kg | **879,59 kg** |
| Écart à la photo du 30 juin : 1 170,79 kg | −591,20 kg | **−291,20 kg** |
| Réceptions physiques annuelles, engagements initiaux inclus | 3 300 kg | 3 300 kg |
| Stock physique simulé au 31 décembre | 979,70 kg | 979,70 kg |

L'écart moyen diminue de **28,22 %**. Le gain provient du calendrier des réceptions, sans augmentation du volume annuel reçu. Les consommations 2025 restent identiques : 70,1568 kg pour le produit étudié et 2 819,950287 kg pour les autres usages estimés. Le service client est inchangé. Sur les 29 couples comparables, seul l'écart de 055703 change ; les 28 autres restent identiques.

Le lot de 300 kg qui explique le gain de juin est lancé le **4 juin au lieu du 11 juin**, reçu physiquement le **25 juin au lieu du 2 juillet**, et disponible le **14 juillet au lieu du 21 juillet**. Les 300 kg supplémentaires à la clôture du 29 juin sont donc en attente de disponibilité qualité. Les achats nouveaux restent **10 commandes de 300 kg**, soit 3 000 kg commandés et reçus sur 2025, auxquels s'ajoute une réception de 300 kg issue des engagements initiaux. Le calendrier de disponibilité reste imparfait : la source situe 300 kg déjà présents au 29 juin comme disponibles dans la semaine commençant le 6 juillet, sans date d'exécution quotidienne certaine.

Validation : 14 tests ciblés en mémoire, deux simulations de cinq ans qualifiées, oracle indépendant sur 1 825 décisions et 1 772 fenêtres hebdomadaires, puis navigateur hors ligne (2 918 valeurs de stock et 294 valeurs du graphique de projection rapprochées des exports). Dans 162 fenêtres, les besoins propres dépassent I : le maximum est conservé et ce désaccord reste explicite. [Bilan des preuves et limites](../../artifacts/testing/mrp_055703_full_needs_20261001/manifest.json).

Le stock de juin est mieux reproduit, mais il manque encore environ **291 kg** par rapport à la photo source. Reprendre tout le besoin prévisionnel ne démontre pas que toutes les conventions industrielles de déclenchement, d'engagement et de réception sont retrouvées. L'essai reste distinct du nominal. Les deux calculs de 1 825 jours ont terminé avec un code retour nul, en environ 58 minutes chacun sur cette exécution ralentie ; cela n'est pas un benchmark de performance comparable au passage précédent. Les 38 CSV du témoin sont identiques octet par octet à la référence conservée.

## Essai suivant : conserver la couverture en maintenant la sécurité

La protection de sécurité seule avait supprimé une partie de la couverture historique et retardé les achats de 708073. Le nouvel essai `mrp_coverage_floor_20261001` teste donc une règle commune sur 055703/Avène, 039668/Avène et 708073/Gien : **conserver le plus grand des deux niveaux, sans les additionner**. Il reste un candidat explicite, pas une règle ERP démontrée ni un remplacement du nominal.

Au jour du calcul `d`, le complément historique `C` est la cible de couverture moins les besoins physiques déjà représentés jusqu'à `d + couverture`, avec un minimum de zéro. La sécurité `S` conserve les jours ouvrés et la quantité fixe sources. Elle s'applique dès `d + 1` ; le complément historique garde son échéance `d + délai`. Après activation des deux, le niveau protégé est `max(S, C)`. Avant, seul le niveau déjà activé s'applique. Le calcul déduit une seule fois le stock disponible et les engagements ; cette protection ne devient jamais une consommation de matière.

Le témoin reproduit l'ancien essai à protection seule sur les trois couples. Les deux nouveaux calculs durent 1 825 jours, avec les mêmes prévisions, parts des usages partagés, stocks, sécurités, offres fournisseurs, délais FIA fixes et arrondis de commande. Le seul changement des graphes est le mode de protection des trois couples. La validation industrielle reste limitée aux photos et plans 2025 ; les années après les dernières prévisions ne valident pas une calibration sur cinq ans.

[Nouvelle comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_mrp_couverture_securite.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_couverture_securite.html) · [protocole et commandes](../../artifacts/testing/mrp_coverage_floor_20261001/plan.json).

Résultats 2025, écart absolu moyen du stock physique aux 52 photos, clôture de la veille :

| Article / site | Couverture historique (kg) | Sécurité seule, essai précédent (kg) | Couverture conservée et sécurité (kg) |
|---|---:|---:|---:|
| 055703 / Avène | 308,34 | 205,14 | 205,14 |
| 039668 / Avène | 141,27 | 135,97 | 135,97 |
| 708073 / Gien | 3 969,26 | 6 177,34 | 3 969,26 |

La régression de 708073 est corrigée : **35 à 0 jours de stock disponible nul**, réceptions annuelles **20 000 à 25 000 kg**, consommation propre **13 677,664 à 15 387,372 kg**. Au 4 avril (J93), le stock disponible est inchangé à 4 416,778811 kg ; la sécurité est 2 000 kg, le complément historique 4 406,584316 kg, activé à J128. Un besoin net de 706,787243 kg retrouve une commande standard de **5 000 kg**, avec réception physique à J121 et disponibilité à J128. Le service des PF reste identique.

**Aucun progrès supplémentaire sur l'écart moyen aux photos de 055703 ou 039668** avec cette correction. Les trajectoires de 055703 sont identiques ; pour 039668, une réception avance d'un jour (J99 à J98), ce qui modifie trois clôtures quotidiennes sans changer cet indicateur. Le creux de juin de 055703 reste présent : son complément historique est déjà inférieur à la sécurité à cette période. Le présent résultat répare la perte de couverture de 708073, sans démontrer une meilleure reconstruction des achats industriels sur toutes les matières. Le témoin conserve ses **38 CSV strictement identiques** à l'essai précédent.

Le contrôle ne se limite pas aux trois articles : parmi les **29 couples comparables**, trois écarts de stock diminuent, sept augmentent et dix-neuf restent identiques par rapport à la sécurité seule. La reprise des consommations de 708073 modifie la production et les stocks liés, sans changer le service client annuel. Par exemple, l'écart de 268967 au dépôt passe de 318 449 à 413 811 UN ; celui de 344135/Gien, de 420 596 à 564 996 UN. Les améliorations concernent 708073, 734545 et 773474. **La restauration de la couverture n'est donc pas une amélioration générale de calibration** ; conserver cet essai séparé, et ne pas additionner des erreurs exprimées dans des unités différentes.

### Autre cause identifiée sur 055703 : besoins projetés incomplets à court terme

Les besoins « autres produits » représentent une fraction fixe du besoin industriel, estimée sur le premier plan : **81,0726583933 %** pour 055703. La différence est censée être apportée par les fabrications de 268091. Or, après déduction des stocks et engagements de PF, notre planning ne place aucun besoin propre sur les fenêtres suivantes. La projection matière reste donc inférieure au total industriel, même lorsque la consommation cumulée passée est proche.

Comparaison sur les mêmes semaines, de la semaine suivante à sept semaines après la date du plan, semaine courante exclue :

| Plan connu | Besoins MRP sources (kg) | Besoins projetés du simulateur (kg) | Cellules sources |
|---|---:|---:|---|
| 4 mai 2025 | 613,200 | 497,138 | Feuille1!I17536:I17542 |
| 18 mai 2025 | 602,400 | 488,382 | Feuille1!I19530:I19536 |
| 1er juin 2025 | 684,200 | 554,699 | Feuille1!I21539:I21545 |
| 29 juin 2025 | 381,800 | 309,535 | Feuille1!I25530:I25533 ; semaines sans ligne omises |

Ces valeurs proviennent du `run_transfer` conservé de l'essai précédent et de `Flow_Data_MRP_results.xlsx`. La fraction initiale vient de `1458,7808788 / 1799,35`, avec 340,5691212 kg théoriques attribués au PF étudié. Son statut reste `hypothesis_only`. Une fraction correcte sur l'horizon initial ne garantit pas une répartition correcte à chaque date.

La source confirme aussi une réception physique avant fin juin : le plan du 29 juin porte 870,790001 kg immédiatement disponibles (`J25529`) et 300 kg déjà présents mais disponibles le 6 juillet (`J25530`). Leur total, **1 170,790001 kg**, correspond à la photo du 30 juin (`Stocks!E417/H417`). Dans l'ancien essai, le lot commandé le 11 juin arrive physiquement le 2 juillet et devient disponible le 21 juillet. Une réception prévue H n'est pas une preuve de commande ferme identifiée ; les révisions successives de H ne permettent pas d'affirmer qu'il s'agit du même ordre.

La prochaine hypothèse à éprouver porte donc sur la **réconciliation des besoins industriels agrégés avec les besoins propres et les autres usages**, en séparant prévision d'achat et consommation physique. Ne pas augmenter les jours de sécurité ni ajouter une seconde consommation pour compenser cette différence. Le présent essai de couverture ne modifie pas cette décomposition.

Contre-vérification sur les mêmes quatre fenêtres de mai/juin : 039668 ne reconstitue que **82,8575466251 %** des besoins sources et 708073 **38,6267607778 %**, exactement leurs parts fixes « autres produits ». Aucun besoin BOM propre ne complète ces fenêtres. Au plan du 1er juin, cela donne respectivement **322,482 / 389,200 kg** (`Feuille1!I21470:I21476`) et **1 483,849 / 3 841,504 kg** (`Feuille1!I21914:I21918`). Ce constat est commun aux trois références ; il ne démontre pas que leur sécurité est insuffisante.

Une règle candidate serait de rapprocher, à chaque semaine et millésime, le besoin industriel total du besoin propre simulé : complément de **planning** `max(0, total industriel − propre simulé)`. Elle n'est pas encore appliquée. Lorsque le besoin propre dépasse le total industriel, le désaccord doit rester visible ; aucune consommation négative ne doit être créée. Utiliser ce total pour acheter tout en conservant des consommations physiques plus basses pourrait créer du surstock : la cohérence entre le périmètre des prévisions et celui des consommations doit être testée conjointement. Les H restent des résultats de comparaison, sans injection dans les achats simulés.

## Choix courant : délai prévisionnel fournisseur fixe

Décision utilisateur : suspendre l'estimation des avances/retards et retenir le **délai prévisionnel FIA du fournisseur choisi**, sans tirage Erlang ni décalage empirique pour les nouvelles livraisons fournisseurs du MRP daté. Le traitement à réception reste une étape séparée ; les sécurités sources sont conservées.

Pour poursuivre cette étude, reprendre la commande `commands.source` du [plan reproductible](../../artifacts/testing/empirical_delivery_20261001/study/plan.json), avec `--supplier-delivery-mode source` et un nouveau dossier de sortie. Le calcul `study/source` existe déjà sur 1 825 jours : il constitue la base retenue pour la suite. Les anciens scénarios et le défaut historique du moteur ne sont pas modifiés par cette décision documentée. La couverture de planification conserve encore sa convention précédente ; ce choix porte sur le délai physique fournisseur, pas sur une révision des autres règles MRP.

Les analyses de variabilité ci-dessous restent des travaux exploratoires conservés ; leur loi empirique n'est plus la règle retenue pour poursuivre la comparaison.

## Essai général : actualiser les besoins complémentaires des 19 couples concernés

[Comparaison interactive de toutes les références](../../resultats/regroupement_001757_20260929/comparaison_mrp_revisions_generalisees.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_revisions_generalisees.html) · [plan reproductible](../../artifacts/testing/mrp_all_revisions_20261001/plan.json).

À la demande utilisateur, la règle d'actualisation des besoins futurs a été appliquée aux **quinze couples restés figés**, en conservant les quatre séries déjà révisées. Le candidat contient 19 séries versionnées et aucune ligne complémentaire fixe. Les 478 anciennes lignes des quinze couples sont remplacées par 780 versions / 27 072 lignes futures, toutes rapprochées directement du fichier MRP. Prix, sécurités, stocks initiaux, fournisseurs, standards, engagements initiaux et délais prévisionnels fixes restent identiques. **Cet essai ne remplace pas automatiquement le point de départ.**

La règle reste commune : dernière version connue pour le futur, semaine courante figée selon la dernière version antérieure, horizon de planification de 52 semaines. Les parts estimées des autres usages restent celles du premier plan. Pour 021081, la part conserve la déduction initiale de 276 421,84455 kg de besoins induits en aval ; aucune seconde déduction n'est appliquée. Les rapports entre usages peuvent toutefois évoluer : conserver cette fraction ne démontre pas qu'elle reste exacte toute l'année.

L'unique extension du code de préparation concerne `revision_series` : elle accepte aussi UN. Le besoin hebdomadaire fractionnaire estimé est conservé dans la provenance, puis arrondi une fois selon `floor(q + 0.5)`, comme l'estimation initiale ; le calendrier répartit ensuite des quantités journalières entières. Les parcours KG/G sont conservés, les conversions masse/UN sont refusées. Aucun changement du moteur physique n'est introduit.

### Résultats sur les quinze couples directement modifiés

L'indicateur ci-dessous est l'écart absolu moyen du **stock physique total** aux photos 2025, simulation à la clôture de la veille. Une baisse est une amélioration de proximité des stocks, pas une preuve de meilleure disponibilité.

| Article / site | Unité | Avant | Essai général | Évolution de l'écart |
|---|---|---:|---:|---:|
| 002612 / Avène | kg | 68 694,19 | 58 360,20 | −15,0 % |
| 007923 / Avène | kg | 25 537,80 | 25 811,46 | +1,1 % |
| 016332 / Avène | kg | 480,05 | 558,41 | +16,3 % |
| 021081 / Gaillac | kg | 233 299,65 | 260 232,01 | +11,5 % |
| 029313 / Avène | kg | 113,29 | 165,17 | +45,8 % |
| 038005 / Gien | kg | 25 626,69 | 22 978,49 | −10,3 % |
| 042342 / Gien | UN | 36 180 055,21 | 24 890 781,02 | −31,2 % |
| 049371 / Avène | kg | 3 877,99 | 3 774,79 | −2,7 % |
| 055703 / Avène | kg | 463,40 | 308,34 | −33,5 % |
| 099439 / Avène | kg | 2 672,11 | 2 398,93 | −10,2 % |
| 426331 / Avène | UN | 7 160,35 | 7 703,88 | +7,6 % |
| 693055 / Avène | kg | 722,74 | 925,99 | +28,1 % |
| 708073 / Gien | kg | 4 056,13 | 3 969,26 | −2,1 % |
| 734545 / Gien | UN | 2 347,44 | 2 259,38 | −3,8 % |
| 773474 / Gien | kg | 11 592,64 | 11 886,90 | +2,5 % |

**Huit améliorations, sept dégradations parmi les quinze.** Sur l'ensemble des 29 couples comparables, y compris les effets indirects, 11 écarts diminuent, 17 augmentent et un reste identique. La baisse de 344135/Gien est négligeable (3 UN sur environ 565 000 UN d'erreur) ; elle reste comptée comme variation numérique, pas comme progrès industriel significatif. Quatre couples restent non comparables dans le payload. Ne pas additionner les écarts exprimés dans des unités différentes.

Les effets indirects touchent aussi les références déjà actualisées : l'écart de 001848/Avène augmente de 14,7 %, celui de 039668 de 3,0 %, tandis que ceux de 001757 et 001893 diminuent légèrement. Leurs séries de prévisions n'ont pas été modifiées ; leurs trajectoires peuvent changer via la production et les autres composants.

### Disponibilité et production : raison de conserver l'essai séparé

Pour 268091, les quantités servies en 2025 passent de **3 499 453 à 3 211 453 UN**, soit **288 000 UN de moins**, avec un retard final passant d'environ 76 989 à 364 989 UN. Le service de 268967 est inchangé. Les quantités totales servies sur cinq ans restent identiques, mais les années après les dernières prévisions ne permettent pas de conclure à une amélioration industrielle.

Le registre `production_constraint_daily.csv` identifie pour 268091 à Avène :

- 001893 limitant sur 45 jours dans les deux scénarios ;
- 002612 limitant sur **81 jours** dans le candidat, contre aucun dans la référence ;
- 693055 limitant sur 28 jours contre 65 ;
- 029313 limitant sur six jours, et 049371 sur un jour, dans le candidat.

Ces jours signalent un manque par rapport au plan de lot ; ils ne sont ni un décompte d'ordres perdus ni une attribution causale exclusive des 288 000 UN. Les stocks physiques nuls passent notamment de 0 à 12 jours pour 002612, de 0 à 50 pour 029313 et de 101 à 182 pour 693055/Avène. Le cas 002612 montre qu'un stock moyen plus proche des photos peut coexister avec une disponibilité moins bonne. La prochaine analyse doit rapprocher les réceptions engagées au démarrage, leurs dates de disponibilité, le dimensionnement des achats et l'estimation des autres usages ; augmenter arbitrairement une sécurité ne résout pas ce diagnostic.

### Vérifications et limites

Simulation normale **1 825 jours, retour 0, 418,954 secondes**. Code et entrées inchangés pendant le calcul. Les dix tests ciblés en mémoire passent, ainsi que la qualification des exports. L'oracle indépendant contrôle 5 475 demandes journalières, les unités physiques entières et les quinze bilans matière (résidu maximal inférieur à 0,00005 kg). La comparaison autonome est vérifiée hors ligne sur 29 couples et 2 918 valeurs affichées, sans erreur JavaScript. La carte complète passe aussi sa revue ; une première tentative avait expiré pendant la navigation et reste conservée dans les preuves. Le [manifeste de livraison](../../artifacts/testing/mrp_all_revisions_20261001/manifest.json) regroupe la contre-vérification indépendante, les preuves natives et la revue de la carte ; les [chiffres par couple et service](../../artifacts/testing/mrp_all_revisions_20261001/analysis.json) et le [diagnostic de contraintes](../../artifacts/testing/mrp_all_revisions_20261001/production_diagnostic.json) restent consultables.

Les I projetés restent des hypothèses de consommation physique complémentaire. Les semaines absentes ne sont pas des consommations réelles nulles démontrées : 042342 n'a ainsi que 231 jours 2025 couverts. Les 19 séries ne se répètent pas après leurs dernières périodes fournies, situées en 2026 ; aucune prévision 2027–2029 n'est inventée. Certaines phrases du champ `assumptions`, hérité du graphe historique et conservé pour contrôler les différences, parlent encore de répétition annuelle ou d'autres articles inchangés : **elles ne décrivent pas cet essai**. Les séries effectives, le plan d'exécution et la présente documentation font foi pour son périmètre. Les autres vues de la carte et les deux suivis de lots restent historiques.

## Essai 055703 : fournisseur cohérent, protection datée et vérification sur deux autres matières

Étude isolée du 1er octobre 2026 : [comparaison interactive, ouverte sur 055703](../../resultats/regroupement_001757_20260929/comparaison_mrp_protection_055703.html) · [carte complète avec ce panneau](../../resultats/regroupement_001757_20260929/carte_mrp_protection_055703.html) · [plan des quatre simulations](../../artifacts/testing/mrp_055703_policies_20261001/plan.json).

**Décision : conserver les résultats comme expériences ; ne pas généraliser ni remplacer automatiquement la référence.** La protection améliore 055703, mais ne résout pas son écart de juin et dégrade nettement 708073. Une meilleure courbe sur un article ne démontre pas une règle commune du MRP industriel.

### Règle expérimentale et différences contrôlées

Une option générique `meta.supplier_planning_policy` permet de déclarer l'offre fournisseur utilisée à la fois pour les dates du plan et pour les nouveaux achats. Le mode facultatif `protection_mode: dated_stock_floor` maintient un niveau disponible projeté : `max(stock de sécurité source, taux global des besoins connus × durée calendaire correspondant aux jours ouvrés de sécurité)`. La durée est recalculée à la date de décision ; 30 jours ouvrés ne valent pas toujours 42 jours calendaires. La protection persiste après les consommations prévues, sans être elle-même consommée. Elle remplace, dans ce candidat, l'ancienne réserve complémentaire de couverture ; **elle ne s'y ajoute pas**.

Sans option, le moteur conserve son comportement. La déclaration exige une offre existante issue de FIA, une unité compatible et une provenance ; elle refuse les politiques concurrentes de sourcing ou de regroupement. Aucun article n'est codé en dur dans cette extension. Les autres offres restent dans le graphe ; les engagements historiques ne sont pas réaffectés. La sélection est exclusive pour les nouveaux achats de cet essai : aucun secours hypothétique n'est ajouté. La fenêtre historique servant au calcul de couverture n'est pas unifiée avec le nouveau délai.

Quatre calculs de **1 825 jours**, mêmes prévisions et parts des autres usages, stocks initiaux, prix, standards et sécurités sources :

1. Référence : nouvelle option absente, recalcul du scénario à dix-neuf prévisions actualisées.
2. Délai : offre 055703/VD0914320A à 21 jours utilisée au plan comme à l'exécution, puis 13 jours de réception selon le calendrier candidat lundi–vendredi.
3. Protection : même sélection, avec les **30 jours ouvrés sources** interprétés comme un plancher disponible daté.
4. Vérification sur d'autres matières, choisies **avant les résultats** : même règle aussi sur 039668/Avène (7 jours, stock fixe nul) et 708073/Gien (10 jours, stock fixe 2 000 kg), chacun avec son fournisseur unique et ses paramètres propres.

### Résultats et cause de la non-généralisation

Écarts absolus moyens du stock physique en kg, aux 52 photos après ouverture, clôture simulée de la veille :

| Article / site | Référence | Délai seul sur 055703 | Protection sur 055703 | Même règle sur les trois matières |
|---|---:|---:|---:|---:|
| 055703 / Avène | 308,34 | 462,34 | **205,14** | 205,14 |
| 039668 / Avène | 141,27 | 141,27 | 141,27 | **135,97** |
| 708073 / Gien | 3 969,26 | 3 969,26 | 3 969,26 | **6 177,34** |

Pour 055703, raccourcir le délai de planification retarde les commandes : la première passe de J39 à J64. Le dernier achat est physiquement reçu en J378, hors de 2025 ; le stock final tombe de 679,698 à 379,698 kg. Avec protection, l'écart moyen diminue de **33,47 %** par rapport à la référence et le stock final atteint **979,698 kg**, contre 933,345 kg dans la dernière photo source. Les jours sans disponible valent respectivement 0, 4 et 0. Mais **le 30 juin reste à 579,585 kg simulés contre 1 170,790 kg sources**, pour la référence comme pour la protection : l'amélioration annuelle ne corrige pas toute la cadence d'approvisionnement.

Pour 039668, le gain reste modeste (environ 3,8 %) ; les jours sans disponible passent de 6 à 4. Pour 708073, l'écart moyen augmente d'environ 55,6 % et les jours sans disponible passent de **0 à 35**, dont 15 jours sans stock physique. Les réceptions 2025 passent de **25 000 à 20 000 kg**.

Le contre-exemple 708073 est identifié **avant toute divergence de consommation** : au J93 (4 avril), les deux scénarios ont 4 416,778811 kg de stock disponible et les mêmes besoins physiques projetés, 44 847,667827 kg. La référence ajoute une réserve de couverture de **4 406,584316 kg**, tandis que le candidat la remplace par un plancher de **2 000 kg**. La référence demande un lancement immédiat de 706,787243 kg, arrondi au standard de 5 000 kg ; le candidat n'en demande aucun. Le premier lancement passe ainsi du **4 avril au 26 mai**, la réception physique du **2 mai au 23 juin**, et la disponibilité du **9 mai au 30 juin**. La règle candidate réduit ici une protection existante plus élevée : elle n'est donc pas une amélioration universelle.

Le service annuel et son retard cumulé restent identiques dans les quatre calculs : 3 211 453 UN servies pour 268091, 1 575 985 UN pour 268967. Cela n'annule pas la dégradation matière de 708073 : sa consommation par la production représentée baisse de 15 387,372 à 13 677,664 kg, et des stocks intermédiaires/finis peuvent absorber des écarts. Aucun gain de service n'est attribué à cette expérience.

La suite pertinente consiste à comprendre comment articuler **couverture existante, protection datée et anticipation des engagements**, sans remplacer aveuglément la première par un plancher plus bas, ni additionner deux fois la même sécurité. Les jours sources restent inchangés. Aucun achat industriel n'est injecté pour forcer la courbe.

### Vérifications, reproduction et limites

Les quatre simulations terminent avec code retour 0, code moteur et entrées stables : 518,172 s / 519,032 s / 505,328 s / 520,859 s. Deux calculs ont tourné simultanément au maximum : ces temps ne constituent pas un benchmark de performance. La [contrepreuve de référence](../../artifacts/testing/mrp_055703_policies_20261001/baseline_equivalence.json) rapproche **38 CSV récursifs identiques octet pour octet** (37 dans `data`, un dans `reports`) au calcul antérieur.

Les **16 tests ciblés de calcul en mémoire** et les quatre qualifications CSV passent. L'oracle indépendant confronte directement les photos Excel aux stocks, les bilans des trois matières, les prévisions et les disponibilités calculées. Les scénarios conservent les mêmes 34 675 lignes de demande complémentaire et de provenance, sans création de consommation de protection. Les quantités physiques UN restent entières. [Chiffres affichés et service](../../artifacts/testing/mrp_055703_policies_20261001/analysis.json) · [manifeste de livraison et preuves](../../artifacts/testing/mrp_055703_policies_20261001/manifest.json).

La comparaison autonome passe la revue hors ligne sur **5 836 valeurs aux photos**, les quatre scénarios, les onglets et le zoom. La carte complète passe également son parcours natif, sans erreur JavaScript. Deux premières tentatives de ce parcours restent conservées comme refusées : attente du panneau, puis manipulation du très gros nœud contenant le JSON. Le panneau est désormais chargé par une URL Blob au lieu d'un attribut `srcdoc` volumineux ; le contrôleur lit le JSON dans la page et ne retourne que l'article sélectionné. Les données embarquées restent identiques. La fermeture et la réouverture réutilisent la même iframe et sont vérifiées. Ce correctif de chargement ne réduit pas la taille des données ni ne démontre une limite précise du navigateur.

La [recette](../../artifacts/testing/mrp_055703_policies_20261001/study.py) et les commandes exactes du plan décrivent les quatre calculs ; les sorties existantes ne doivent pas être écrasées. Les HTML antérieurs sont conservés. Dans la carte complète, les autres onglets et les deux suivis de lots restent ceux du scénario historique ; les nouveaux résultats figurent dans le panneau comparatif. Seule l'année 2025 est confrontée aux photos sources. Les prévisions s'arrêtent en 2026, sans répétition artificielle : exécuter cinq ans ne constitue pas cinq ans de calibration industrielle. Les propositions à dates futures conservent par ailleurs le délai scalaire calculé au jour de décision, hors des parcours disposant d'un calendrier futur spécifique.

## Diagnostic 055703 à Avène — après généralisation des prévisions révisées

Analyse du 1er octobre 2026, première année 2025 de `mrp_all_revisions_20261001/run`, comparée à `mrp_001893_revisions_20260930/run`. Aucun paramètre, moteur ou HTML modifié pour ce diagnostic. [Comparaison existante, sélectionner 055703 / Avène](../../resultats/regroupement_001757_20260929/comparaison_mrp_revisions_generalisees.html).

### Paramètres et cohérence des sources

| Donnée | Valeur vérifiée | Source |
|---|---|---|
| Fournisseur utilisé | VD0914320A : 20,35 EUR/kg, 21 jours, standard 300 kg | `268091.xlsx/FIA!A16:H16` |
| Autre offre | VD0964290A : 49,20 EUR/kg, 42 jours, standard 300 kg | `FIA!A17:H17` |
| Nomenclature 268091 | 81,2 g pour 1 000 PF | `268091.xlsx/BOM!C10:F10` |
| Sécurité | 30 jours ouvrés, quantité fixe nulle | Inventory, `Politique de stock MRP!E10:G10` |
| Traitement à réception | 13 jours dans les 52 versions ; calendrier lundi–vendredi candidat | Flow MRP, `Feuille1!E473` et versions suivantes |
| Engagement initial | 300 kg, livraison prévue le 17 janvier, disponibilité le 5 février | `Extract_En_cours.xlsx/Sheet1!A69:I69` |

Le fournisseur utilisé est moins cher **et** plus rapide : l'autre n'est pas un secours rapide démontré. L'ancien stock initial (569,805000976563 kg) et le nouveau (569,805001 kg) concordent à l'arrondi près ; l'ancienne sécurité vaut également 30 jours. Aucune anomalie g/kg identifiée. La valorisation comptable des photos est de 18,99 EUR/kg : elle ne constitue pas un prix d'achat FIA supplémentaire.

### Ce qui s'améliore et ce qui reste différent

L'écart absolu moyen du stock physique aux 52 photos après ouverture passe de **463,40 à 308,34 kg (−33,5 %)**. Dans l'essai général, 2 819,950287 kg sont consommés par les autres usages estimés et 70,1568 kg par la production représentée, soit **2 890,107087 kg**. Les achats physiquement reçus passent de quatre à dix lots de 300 kg, engagement initial inclus : **1 200 → 3 000 kg**. La part complémentaire de 81,07 % reste une estimation issue du premier plan, pas une ventilation industrielle démontrée.

Les photos sources montrent onze hausses importantes (plus de 100 kg), les 27 janvier, 17 février, 10 mars, 31 mars, 5 mai, 26 mai, 30 juin, 1er septembre, 27 octobre, 17 novembre et 15 décembre. Toutes sont compatibles avec 300 kg reçus moins les sorties de la semaine. Les espacements varient de 21 à 63 jours : ce n'est pas un calendrier fixe établi.

**Reconstruction conditionnelle**, sans autre entrée ni ajustement masqué : onze réceptions de 300 kg donnent `569,805001 + 3 300 − 933,345021 = 2 936,459980 kg` de sorties nettes jusqu'à la dernière photo. C'est 46,352893 kg de plus que la consommation simulée, soit environ 1,6 %. Ce rapprochement ne transforme pas les photos en registre exact des réceptions ou consommations.

| Date de photo | Stock source kg | Stock simulé kg | Entrées sources reconstituées kg | Entrées simulées kg | Sorties sources reconstituées kg | Consommation simulée kg |
|---|---:|---:|---:|---:|---:|---:|
| 31 mars | 1 124,790 | 571,592 | 1 200 | 600 | 645,015 | 598,213 |
| 30 juin | 1 170,790 | 579,585 | 2 100 | 1 500 | 1 499,015 | 1 490,220 |
| 29 décembre | 933,345 | 679,698 | 3 300 | 3 000 | 2 936,460 | 2 890,107 |

Flux cumulés depuis l'ouverture ; simulation à la clôture de la veille. Au 30 juin, environ **591 kg d'écart** correspondent à **600 kg d'entrées en moins**, compensés par environ 9 kg de consommation en moins, sous l'hypothèse précitée. Fin décembre, **253,647 kg d'écart** correspondent à 300 kg d'entrées en moins, compensés par 46,353 kg de consommation en moins. Le stock simulé final contient déjà **300 kg présents mais indisponibles jusqu'au 7 janvier 2026** ; cette quantité est bien incluse dans les 679,698 kg physiques.

### Précautions sur les versions MRP et piste commune

Le premier H de 300 kg est présent en `H474` puis `H1435`, reporté en `H2442`, puis se retrouve vraisemblablement dans le J futur de `J3468`. Le 26 janvier, `J3467 + J3468 = 396,280001 + 300 = 696,280001 kg`, exactement la photo du 27 janvier (`Stocks!E744`). C'est vraisemblablement un même approvisionnement reporté puis disponible plus tard, pas plusieurs achats. Les quatre H de 300 kg du premier plan ne prouvent pas quatre engagements fermes : certaines versions suivantes proposent 450 kg et déplacent les échéances. Ne pas injecter arbitrairement tous les H initiaux comme commandes fermes.

Sur 52 versions, 51 sommes J concordent avec la photo suivante. Exception : le 2 mars, J vaut 1 006,945002 kg contre 746,790002 kg sur la photo du 3 mars ; la photo du 10 mars vaut justement 1 006,945002 kg. Ce décalage apparent reste signalé, sans correction arbitraire. Les J futurs répétés et les 14 H positifs de semaine courante ne sont pas des décomptes de commandes annuelles.

La piste prioritaire est **l'anticipation et le déclenchement des lots, avec la protection du stock partagé**. Dans le contrôleur actuel, une réserve complémentaire est calculée après déduction des besoins déjà présents dans l'horizon (`plan_component_network`) ; elle n'est pas automatiquement équivalente à un minimum de stock conservé à chaque date. Une réserve complémentaire nulle ne signifie donc pas, à elle seule, que la sécurité est ignorée. L'interprétation des 30 jours doit être testée comme règle commune, sans augmenter cette valeur source ni ajouter artificiellement un lot pour ajuster la courbe.

Le facteur de sécurité de cet essai vaut explicitement 1. Exemple de différence entre conventions : au jour 330, le disponible vaut 356,939 kg, contre `9,971982 kg/j × 42 jours calendaires = 418,823 kg` pour un plancher calculé sur les 30 jours ouvrés et les besoins globaux connus. Les 300 kg complémentaires sont encore indisponibles. Cela ne prouve pas que le MRP industriel applique ce plancher. Dans les traces, `target_stock_qty` reste une cible du périmètre du produit étudié (190,080 kg ce jour-là), tandis que `dated_global_target_rate_qty` inclut les autres usages : ne pas présenter ces deux indicateurs comme une même cible globale.

Autre incohérence de convention identifiée : sans politique de sourcing explicite pour ce couple, le planificateur retient le maximum des deux délais fournisseurs, soit 42 jours plus réception (59–61 jours au total), tandis que les achats sont exécutés avec le fournisseur à 21 jours plus réception (38–40 jours). À échéance de besoin identique, cet écart avance le lancement calculé de 21 jours par rapport à un délai cohérent avec le fournisseur retenu ; il n'explique pas directement un stock trop bas. Il faut isoler son effet avant toute généralisation.

Contrôles exécutés : relecture indépendante des Excel et du code ; **730 bilans physiques journaliers** et décompositions disponible/bloqué/réservé rapprochés des CSV des deux calculs, sans erreur au seuil 0,0001 kg. [Calcul reproductible en lecture des entrées](../../artifacts/testing/mrp_all_revisions_20261001/audit_055703.py) · [chiffres, achats, photos et empreintes des entrées](../../artifacts/testing/mrp_all_revisions_20261001/audit_055703.json). Aucune nouvelle simulation ni qualification globale lancée : ces contrôles ciblés expliquent les résultats existants et ne certifient pas encore une nouvelle règle industrielle.

## Diagnostic 001893 à Avène — base au délai fournisseur fixe

Périmètre : `empirical_delivery_20261001/study/source`, première année 2025, article `item:001893`, site `M-1810`. Analyse seule ; aucun paramètre ni résultat de simulation modifié.

**Fin décembre, l'écart de stock porte presque entièrement sur le stock déjà présent mais disponible en janvier.** Le plan du 28 décembre donne 37 157,928 kg dans la semaine courante (`Flow_Data_MRP_results.xlsx/Feuille1!J52451`), 20 900 kg disponibles le 4 janvier 2026 (`J52452`) et 44 820 kg le 25 janvier (`J52455`). Leur somme, 102 877,928 kg, correspond exactement à la photo du 29 décembre (`Flow_Data_Inventory_and_Replenishment_rules.xlsx/Stocks!E1183`). Selon la définition confirmée de J, ces 65 720 kg futurs sont déjà physiquement présents, pas des achats restant à recevoir.

À la clôture du 28 décembre (J361), le CSV `production_stock_availability_daily.csv` contient 37 025,088714 kg disponibles et physiques, sans indisponible. L'écart au total source est donc 65 852,839286 kg, dont 65 720 kg de disponibilité future source ; l'écart au seul disponible source est 132,839286 kg. Cette proximité ponctuelle du disponible ne valide pas toute la trajectoire : le 3 février, la photo vaut 14 623,304 kg, contre 71 760 kg physiques simulés à la clôture précédente, tous encore indisponibles.

Le registre `mrp_orders_daily.csv` contient six achats externes lancés et physiquement reçus en 2025 : 71 760 kg puis cinq fois 23 920 kg, soit **191 360 kg**, tous auprès de VD0910216A, à 28 jours de livraison puis 24 jours ouvrés de traitement à réception. La première commande part le 5 janvier, arrive le 2 février et devient disponible le 6 mars. Aucun ordre initial 001893/1810 n'est importé : les cinq lignes 001893 du carnet (`Extract_En_cours`, lignes 9–13) concernent 1820 et ne doivent pas être réaffectées sans preuve.

Le bilan physique simulé 2025 se ferme : 9 783,5 kg initiaux + 191 360 kg reçus − 164 118,411286 kg consommés = 37 025,088714 kg finaux (écart inférieur à 0,00001 kg en additionnant les exports arrondis). Les consommations comprennent 155 454,046486 kg estimés pour les autres produits et environ 8 664,365 kg pour les produits représentés. Les 53 photos sources donnent 253 974,674 kg de hausses positives cumulées, soit 62 614,674 kg de plus que toutes les réceptions simulées. C'est un cumul de hausses nettes, pas une mesure exhaustive des livraisons : consommations simultanées, transferts ou corrections éventuelles restent à distinguer.

**Défaut d'entrée identifié : les besoins partagés restent figés au premier plan du 5 janvier pour cette référence.** Ses 40 lignes (`Feuille1!118:157`) s'arrêtent au 19 octobre, sans besoin renseigné en novembre/décembre. L'estimation des autres usages retient 82,7728 % des besoins futurs de ce premier plan ; cette part est une hypothèse, pas une nomenclature industrielle complète. Les versions sources ultérieures contiennent bien des besoins de fin d'année et de 2026. Dans le calcul, l'achat suivant n'est lancé qu'à J369 (5 janvier 2026), pour réception à J397. La priorité est de présenter au planificateur les versions connues et leurs besoins futurs, avant de calibrer davantage les regroupements.

Les trois offres FIA (`FIA268091`, lignes 5–7) sont 4,40 €/kg / 56 jours / 22 800 kg ; 4,64 €/kg / 28 jours / 23 920 kg ; 5,105 €/kg / 42 jours / 20 900 kg. La sécurité source reste 15 jours ouvrés, stock de sécurité fixe nul. Les projections H ne se réduisent pas aux multiples de 23 920 kg : 950 kg est fréquent au début, puis 19 000, 20 900, 22 800 et 23 920 kg apparaissent. Une quantité projetée ne suffit pas à identifier un fournisseur, une commande ou une palette. Le choix fournisseur et le fractionnement des réceptions restent à rapprocher des données, sans multiplier arbitrairement la sécurité.

Contrôles : lectures des CSV du calcul conservé, rapprochement direct et indépendant des cellules Excel, fermeture du bilan matière. Aucune nouvelle simulation ni qualification globale exécutée pour ce diagnostic.

### Essai séparé : prévisions 001893 révisées sur un horizon de 52 semaines

[Comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_001893_revisions.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_001893_revisions.html) · [plan reproductible](../../artifacts/testing/mrp_001893_revisions_20260930/plan.json).

Règle commune appliquée : **à chaque publication d'un plan MRP, remplacer les besoins futurs par la dernière version connue, sans additionner les versions ni réécrire la semaine en cours**. Le mécanisme existant est réutilisé pour 001893/1810 : 38 lignes complémentaires fixes sont remplacées par 52 versions, soit 2 023 lignes futures. La part initiale estimée de 82,7728067775 % reste inchangée. Prix, choix fournisseur, standards, stocks initiaux, délais fixes et sécurités sont strictement identiques au point de départ. Le moteur n'a pas été modifié ; ce résultat reste un scénario séparé, reproductible avec `study.py prepare`, puis `study.py run` dans le dossier de preuves (les fichiers existants sont protégés contre l'écrasement).

| Indicateur 001893/Avène, 2025 | Point de départ | Besoins révisés |
|---|---:|---:|
| Écart absolu moyen du physique aux 52 photos | 37 355,43 kg | **18 953,16 kg (−49,26 %)** |
| Écart absolu moyen du disponible au J de la semaine courante | 19 641,19 kg | **15 350,47 kg (−21,85 %)** |
| Nouveaux achats lancés | 6 / 191 360 kg | 17 / 454 480 kg |
| Réceptions physiques dans l'année | 191 360 kg | 430 560 kg |
| Consommation complémentaire estimée exécutée | 155 454,05 kg | 342 599,25 kg |
| Consommation des produits représentés | 8 664,36 kg | 8 664,36 kg |
| Jours de stock physique nul / disponible nul | 15 / 47 | 15 / 47 |

La comparaison du disponible utilise ici le J courant du plan, pas le stock total des photos. Sur 45 des 52 semaines, la somme des J datés concorde exactement avec la photo voisine ; les sept autres gardent leur écart de source/date. Ce rapprochement n'identifie pas des consommations observées.

**Rapprochement du 29 décembre, à clôture simulée du 28 décembre :** le physique passe de 37 025,09 à **65 159,89 kg**, contre 102 877,93 kg en source. Le candidat se décompose en 41 239,89 kg disponibles et 23 920 kg indisponibles, contre respectivement 37 157,93 et 65 720 kg dans le MRP source. Il reçoit 23 920 kg supplémentaires **le 30 décembre**, et termine le 31 à 89 079,89 kg physiques, dont 47 840 kg indisponibles. Cette valeur du 31 ne doit pas être présentée comme une comparaison à date identique avec la photo du 29.

La correction rétablit des besoins et achats de fin d'année mais ne résout pas les ruptures initiales ni tous les décalages de réception. Les 17 achats restent tous sur VD0910216A : 71 760 kg une fois puis 23 920 kg seize fois, livraison fixe 28 jours puis traitement de réception 24 jours ouvrés. Le rapprochement fournisseur/fractionnement reste ouvert : les H source peuvent être des échéances regroupées ou fractionnées et ne prouvent ni un quota d'achat ni un fournisseur exécutant. Aucune quantité standard source ni règle de sélection n'a été ajustée pour améliorer la courbe.

Les métriques de stock 2025 des autres couples représentés sont inchangées, comme le service PF 2025. Sur cinq ans, les quantités servies totales sont identiques ; le cumul des retards de 268091 change, ce qui ne constitue pas une validation industrielle des années sans nouvelles données. Les autres onglets de la carte et les deux suivis de lots conservent leur scénario historique ; seul le panneau de comparaison contient cet essai.

**Vérification :** exécution normale de 1 825 jours terminée en 429,734 s, retour 0, seize fichiers moteur/calcul et toutes les entrées inchangés. Quatorze tests ciblés en mémoire passent, ainsi que la qualification des exports. La [contre-vérification indépendante](../../artifacts/testing/mrp_001893_revisions_20260930/validation/independent.json) rapproche directement les 2 023 cellules Excel, les 365 demandes journalières, les dates de livraison/disponibilité et le bilan des lots (résidu inférieur à 0,00002 kg). La [revue ciblée de la comparaison](../../artifacts/testing/mrp_001893_revisions_20260930/view_001893_4899dfa9/report.json) vérifie hors ligne six onglets, les deux scénarios, 208 valeurs aux dates des photos, les bases physique/disponible et le zoom, sans erreur JavaScript. Les preuves sont regroupées dans le [manifeste de livraison](../../artifacts/testing/mrp_001893_revisions_20260930/manifest.json).

Limites conservées : les I projetés restent une hypothèse de consommation physique ; la part des autres usages n'est pas une nomenclature industrielle complète. Les prévisions de cet article ne sont pas répétées artificiellement après leur fin, le 7 novembre 2026. En 2025, 329 jours sont couverts ; les périodes 1–11 janvier, 27 juillet–16 août et 28–31 décembre restent non fournies, pas des demandes industrielles nulles démontrées. La simulation de cinq ans vérifie l'exécution ; elle ne calibre pas les besoins industriels de 2027–2029.

## Bilan annuel des avances et retards fournisseurs — toutes les données 2025 disponibles

Le [rapport annuel](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/rapport_annuel.md) étend le rapprochement aux **douze mois et 52 versions MRP**, au-delà du carnet initial. Les dernières photos datent du **29 décembre 2025** : aucune arrivée du 30–31 décembre n'est inventée. Le périmètre d'origine externe FIA + carnet couvre **23 couples article/site, 1 146 intervalles et 300 hausses nettes**.

**278 hausses ont une prévision historique candidate ; 44 rapprochements sont retenus pour une statistique conditionnelle**, sur **16 références**, avec au moins un cas chaque mois. La sélection n'est pas un recensement de toutes les livraisons : consommations masquant une entrée, regroupements, révisions, corrections et identités manquantes limitent le rapprochement. Les 300 fenêtres et tous leurs motifs restent dans le [tableau détaillé](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/annual_arrival_windows.csv).

La référence de date est **G du carnet initial** lorsqu'un lien unique est possible (3 cas retenus), sinon la **première prévision suivie entrant dans l'horizon du délai fournisseur FIA** (41 cas). Ce franchissement est une convention d'estimation commune, pas une date de commande observée. Pour plusieurs délais fournisseurs possibles, les références alternatives sont conservées sans inventer le fournisseur exécutant. Le suivi des versions privilégie une date cible stable ; un changement de date n'est lié par quantité que si celle-ci est unique dans les deux versions. Les quantités modifiées après la référence, traces partagées et références trop récentes restent hors statistique principale. Les révisions avant la référence figée restent documentées sans invalider automatiquement le rapprochement.

| Résultat sur les 44 fenêtres retenues | Nombre |
|---|---:|
| Intervalle entièrement après la prévision : retard reconstitué | **8** |
| Intervalle recouvrant la période prévue : signe indécidable | **36** |
| Intervalle entièrement avant la prévision | **0** |

La moyenne des **milieux d'intervalle** est **+2,75 jours**, médiane **+1,5 jour**, écart-type descriptif **9,72 jours**. Avec les bornes possibles des dates, la moyenne peut aller de **−3,55 à +9,05 jours** : ce n'est pas un intervalle de confiance. Les centres de 36 cas sont dans ±7 jours, mais seuls trois intervalles complets y tiennent. **Ni 36/44 ni 8/44 ne sont un taux de ponctualité/retard de tous les fournisseurs.** Zéro avance entièrement identifiable ne signifie pas zéro arrivée anticipée ; 12 centres d'intervalle sont négatifs.

Les retards reconstitués incluent **042342 : 30–43 jours**, **333362 : 37–50 jours puis 16–29 jours**, et cinq cas de **2–15 jours** pour 001848, 007923 et 333362. Les deux grands retards ont été relus dans les versions successives et les photos : les H persistent en étant reportés, puis disparaissent autour d'une hausse compatible. Il n'est pas démontré qu'ils correspondent à des commandes individuelles inchangées.

La partition des 300 fenêtres est complète : **44 retenues**, **8 sans H contemporain**, **14 sans référence historique exploitable**, puis, par priorité de motif, **59 avec hausse supérieure au H**, **60 avec trace partagée**, **64 avec quantité révisée après référence**, **51 avec référence trop récente**. Les motifs détaillés peuvent se cumuler ; cette partition n'en compte qu'un par fenêtre. Une analyse plus restrictive excluant les références déjà dans l'horizon au premier point connu conserve **17 cas**, dont **5 retards**, moyenne centrale **+3,09 jours** ; la composition de l'échantillon change.

Livrables : [par mois](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/statistiques_mensuelles.csv), [par article](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/statistiques_articles.csv), [traces et cellules sources](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/annual_results.json), [preuve indépendante](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/validation/report.json). Le calcul arithmétique et la relecture ne certifient pas une loi industrielle ; aucune simulation ni distribution du moteur n'est modifiée par ce bilan.

## Avance/retard des livraisons fournisseurs : ancrage dans les engagements sources

**Question métier : date d'arrivée physique repérée dans les stocks moins date de livraison prévue par les sources.** Ce calcul est distinct de la concordance générale entre les hausses de stock et les H MRP de la section suivante. Aucun résultat simulé n'est utilisé ici.

Le [nouvel audit fournisseur](../../artifacts/testing/supplier_delivery_dates_20261001/results.json) relit le carnet `Extract_En_cours`, les photos et les plans MRP. Le carnet fournit **82 achats externes** AVICDE/ECHCDE, avec fournisseur, quantité et **date physique prévue G** ; **66** ont des photos au même article/site (15 couples, dates prévues janvier–mai). La colonne **I** est une disponibilité prévue après traitement de réception et ne mesure jamais une arrivée réelle. Le délai FIA est renseigné lorsque le fournisseur du carnet est retrouvé ; il n'est pas confondu avec le traitement de réception. Sans date d'émission de commande, le délai complet réellement écoulé depuis l'achat reste inconnu.

Le périmètre annuel des origines externes est l'union **FIA + carnet**, pas FIA seule : **23 couples avec photos, 1 146 intervalles, 300 hausses nettes**. Cela ajoute **001848/Gien**, fournisseur VD0951020A explicitement renseigné en ligne 7 du carnet. Pour **734545**, le carnet ligne 104 cite **VD0525906A**, tandis que la FIA cite VD1095770A : une seule offre FIA n'établit pas l'identité de toutes les livraisons réelles. L'identifiant fournisseur affecté aux anciens rapprochements est donc une attribution par catalogue, pas une preuve d'exécution.

Chaque engagement est comparé à **toutes** les hausses voisines, avec trois fenêtres de recherche ±21, ±42 et ±84 jours pour rendre visible la dépendance au rayon. Un candidat corroboré exige une hausse ne dépassant pas la quantité de l'engagement et un H de même quantité dans l'une des deux dernières versions connues à la photo, sur une semaine recouvrant la hausse. Aucun I prévisionnel n'est transformé en consommation réelle. Aucun candidat n'est retenu parce qu'il est simplement le plus proche de la date prévue. Les liens uniques dans les deux sens restent conditionnels : achats non listés, fractionnements/regroupements, révisions et corrections de stock peuvent les invalider.

Exemples de fenêtres **conditionnelles** trouvées à ±21 jours (pas un histogramme industriel) :

| Article/site | Fournisseur du carnet | Quantité prévue | Livraison prévue G | Photos encadrant la hausse | Écart possible |
|---|---|---:|---|---|---|
| 001757/Avène | VD0951020A | 2 000 kg | 5 mars | 10–17 mars | +5 à +12 jours |
| 001757/Avène | VD0951020A | 4 000 kg | 28 janvier | 27 janvier–3 février | −1 à +6 jours |
| 001848/Avène | VD0951020A | 6 000 kg | 20 février | 17–24 février | −3 à +4 jours |
| 038005/Gien | VD0520132A | 10 000 kg | 7 avril | 24–31 mars | −14 à −7 jours |
| 055703/Avène | VD0914320A | 300 kg | 17 janvier | 20–27 janvier | +3 à +10 jours |
| 734545/Gien | VD0525906A | 6 400 unités | 6 janvier | 6–13 janvier | 0 à +7 jours |

Les bornes sont les dates des photos, sans précision inventée sur l'heure de prise. Pour 001848, le H de 6 000 kg reste dans les sept versions du 5 janvier au 16 février, semaine cible du 16 février, puis disparaît du plan du 23 février ; la hausse réelle est 5 819,8 kg. Pour 055703, H=300 kg est reporté de la semaine du 12 à celle du 19 janvier, puis disparaît au 26 janvier ; la hausse est 222,09 kg. Ces traces renforcent les hypothèses sans identifier une transaction exécutée.

**La statistique globale de retard fournisseur n'est pas identifiée par cette sélection.** À ±21 jours, seuls 6 engagements sur les 66 couverts ont un lien corroboré unique (2 fenêtres tardives, 1 précoce, 3 compatibles avec la date prévue). À ±42 jours, 4 restent uniques ; à ±84 jours, 3. Les ensembles changent, et la moyenne des centres passe de +1,83 à +10,50 puis +12,83 jours : cela démontre l'instabilité de l'appariement, pas une mesure du retard moyen industriel. Les cas ambigus ne sont pas des livraisons à l'heure. Le carnet initial ne couvre pas les nouveaux achats du reste de 2025.

Les [300 hausses du périmètre externe](../../artifacts/testing/supplier_delivery_dates_20261001/annual_stock_rises.csv) et [tous les candidats, sources et motifs](../../artifacts/testing/supplier_delivery_dates_20261001/candidates.csv) restent consultables. Aucune loi du moteur n'a été recalibrée avec ces résultats.

## Reprise exhaustive des variations de stock et des plans MRP 2025

**Statut : analyse des données sources, sans changement du moteur ni de la loi de livraison. La loi à quatorze rapprochements ci-dessous reste expérimentale ; elle ne représente pas une distribution industrielle validée.**

Le [rapport exhaustif](../../artifacts/testing/stock_mrp_exhaustive_20261001/rapport.md) couvre les **1 646 photos**, **32 couples article/site** et **1 614 intervalles** : **411 hausses**, **846 baisses**, **357 périodes stables**. Les **53 398 lignes MRP** sont rapprochées directement des Excel par un validateur indépendant. Le MRP possède 33 couples : 029313/Gien n'a pas de photo ; 344135/Gien n'en possède que trois. La dernière photo est datée du 29 décembre 2025.

Avec la convention dimanche début de semaine et la dernière version connue au début de chaque semaine cible, **410/411 hausses** sont couvertes par des lignes MRP : **388** rencontrent une entrée H dans les semaines recouvrantes, **22** aucune. **52 hausses dépassent même tout le H possible de ces semaines** ; ce décompte inclut les 22 sans H. Ces nombres sont des concordances de calendrier et de quantité, pas des taux de ponctualité. Les bornes de quantité n'imposent pas une répartition journalière uniforme.

Sur une cohorte commune de **253 hausses** dont les quatre anticipations sont disponibles, un H recouvrant existe dans **241 cas** avec le plan récent, **201** à 14 jours, **190** à 28 jours et **193** à 56 jours. Les volumes H possibles suffisent à couvrir la hausse nette dans respectivement **225, 169, 165 et 167 cas**. Cela distingue les révisions des plans d'une comparaison faite sur des populations différentes. Le calendrier alternatif où le dimanche clôt la semaine est également calculé ; aucune convention n'est sélectionnée uniquement pour améliorer le résultat.

Le calcul conditionnel `entrées = variation de stock + I prévu` est effectué pour **toutes les périodes couvertes**, même sans hausse. Il donne **68 résultats négatifs sur 1 583 périodes couvertes** avec le plan récent et **258 sur 1 033** à 14 jours. Ces résultats restent négatifs et signalés ; ils ne sont pas corrigés arbitrairement. Les I, notamment courants, peuvent inclure des besoins reportés et ne prouvent pas la consommation exécutée. Les semaines absentes restent inconnues, jamais zéro.

Le rapprochement cumulé FIFO permet regroupements et fractionnements, conserve les volumes non rapprochés et s'interrompt aux données manquantes ou reconstructions négatives. Les profils temporels ainsi calculés dépendent fortement des volumes et des consommations supposées : **ils ne fournissent pas un taux de retard fournisseur réel ni une loi à réinjecter dans le moteur**. Un contrôle de sensibilité conserve séparément les blocs d'au moins deux périodes où les quantités projetées et reconstituées diffèrent d'au plus 10 % ; ce seuil descriptif n'identifie pas les commandes. KG, UN et M restent séparés.

Contrôle complémentaire : **1 131 égalités / 1 615** rapprochements entre ΣJ du plan du dimanche et photo du lundi, **484 écarts**. J décrit du stock déjà présent et n'est jamais additionné aux réceptions H. Pour **039668**, toutes les cinq hausses sont conservées, dont quatre importantes et **0,030 kg** le 17 novembre ; cette dernière ne prouve pas une réception.

Livrables : [synthèse des 32 références](../../artifacts/testing/stock_mrp_exhaustive_20261001/summary_by_reference.csv), [toutes les périodes et huit conventions](../../artifacts/testing/stock_mrp_exhaustive_20261001/intervals.csv), [bornes H](../../artifacts/testing/stock_mrp_exhaustive_20261001/weekly_bounds.csv), [statistiques et limites](../../artifacts/testing/stock_mrp_exhaustive_20261001/summary.json), [preuve indépendante](../../artifacts/testing/stock_mrp_exhaustive_20261001/validation/report.json). Les **12 912 calculs de périodes**, **6 227 allocations** et **2 056 blocs** ont été contre-vérifiés sans importer les fonctions de l'analyse. Les simulations et cartes précédentes restent inchangées.

## Distribution empirique des décalages de réception — mise en application

Le mode `--supplier-delivery-mode empirical` remplace le tirage Erlang des **nouveaux achats externes agrégés**, dans le parcours MRP daté. Il utilise une politique explicite `meta.empirical_supplier_delivery_policy`. Les références historiques restent reproductibles avec `sampled`, et le témoin `source` conserve le délai FIA fixe. Les transferts internes ne sont pas calibrés avec les réceptions fournisseurs. La loi ne change ni les quantités standard, ni les sécurités sources, ni les engagements initiaux, ni le délai de traitement de réception. La couverture de planification conserve sa convention précédente afin d'isoler l'effet physique ; ce mode n'est donc pas une suppression de toute convention Erlang à tous les niveaux du modèle.

**Ce que mesure la loi :** un décalage estimé entre une semaine de réception projetée H et une fenêtre de remontée du stock physique. Elle ne mesure pas directement le délai entre émission d'une commande identifiée et réception. Son application sous la forme `délai FIA + décalage` est une hypothèse commune explicite, autorisée pour cette reconstitution. Les incertitudes d'identification, de périmètre, de calendrier et de consommation ne disparaissent pas avec le tirage.

### Rapprochement conservateur et traçable

Le module [empirical_delivery.py](../../simulation/experiments/empirical_delivery.py) rapproche les sources déjà auditées des photos Excel relues directement. Il vérifie leurs empreintes ; il refuse les données modifiées au lieu de réutiliser silencieusement une ancienne extraction. Le calcul conserve les motifs d'exclusion et les cellules d'origine.

1. Couple article/site avec une origine externe unique renseignée par la FIA ; fournisseurs multiples, origine interne et absence de photos exclus de l'estimation.
2. Deux photos de stock espacées d'au plus sept jours, avec hausse nette positive. Quantités G converties en kg, ZUN traitées comme unités.
3. Dernier plan connu **au moins quatorze jours avant le début** de cette fenêtre, jamais le plan publié après la remontée. Une seule entrée H positive dans le voisinage de recherche ±21 jours ; sinon rapprochement ambigu.
4. Hausse nette entre 50 % et 102 % du H candidat ; différence `H − hausse − I prévu sur la fenêtre` inférieure ou égale à 25 % de H. Les I sont proratisés sur les seuls jours couverts et les semaines absentes entraînent un rejet. Ces seuils sélectionnent des cas compatibles, pas des commandes industrielles certaines.
5. Un H daté ne peut expliquer deux remontées. Déduplication chronologique : un nouvel événement ne retire jamais rétroactivement une observation déjà connue. J, y compris futur, n'est jamais une nouvelle réception.

Les photos encadrent la réception possible entre le lendemain de la première et la seconde. Le H est représenté par sa semaine dimanche–samedi, convention explicite. On conserve l'intervalle complet du décalage et on utilise son milieu arrondi pour le tirage ; les bornes ne sont pas présentées comme des dates mesurées. Une autre orientation de la semaine déplacerait les estimations de six jours. La distinction H arrivée physique/disponibilité reste à confirmer et peut affecter l'interprétation.

### Loi obtenue et utilisation sans connaissance du futur

**14 événements compatibles, six couples article/site** : 029313, 039668, 338928, 426331 à Avène ; 708073 et 734545 à Gien. Chaque événement pèse une fois, sans prétendre qu'il correspond à une commande unique.

| Décalage central estimé | Événements dans le pool complet |
|---|---:|
| −12 jours | 1 |
| −5 jours | 4 |
| +2 jours | 8 |
| +9 jours | 1 |

La moyenne de ces valeurs vaut −0,5 jour et leur écart-type de population environ 5,03 jours. Ce ne sont pas la moyenne et l'écart-type des délais fournisseurs réels. Les hausses visibles favorisent les réceptions peu masquées par consommation ; la fenêtre de recherche tronque les décalages extrêmes. Aucun taux de ponctualité industriel ni loi individuelle fournisseur n'est déduit de quatorze cas.

À chaque commande, le moteur ne retient que les événements dont la photo finale est déjà connue (`known_day <= decision_day`). Avant cinq événements, il conserve le **délai FIA fixe, sans tirage**, plutôt qu'un retour à Erlang. Le cinquième devient connu **le 21 avril 2025, J110**. Ensuite, un événement admissible est tiré uniformément ; le délai vaut FIA + son décalage, avec minimum physique d'un jour et valeur avant bornage tracée. Les bornes Erlang historiques ne sont pas appliquées à cette loi. Le traitement de réception E intervient ensuite, selon son calendrier propre. Le mode empirique refuse actuellement un préchauffage non nul pour éviter de décaler implicitement les dates de connaissance.

Les colonnes `empirical_sample_id`, `empirical_known_day`, `empirical_pool_size`, `empirical_delta_days`, `empirical_status`, `empirical_unclipped_lead_days` permettent de vérifier chaque achat exécuté. Elles n'apparaissent que dans les sorties du mode empirique, afin de conserver le format des références. Le résumé enregistre la politique complète et ses limites. Après 2025, le pool acquis reste connu ; aucun nouvel historique industriel n'est inventé.

Pour **039668**, deux événements sont retenus (juin et décembre). **Mars est exclu de l'apprentissage** : les 300 kg de l'ancien plan sont incompatibles avec une hausse nette de 426,115 kg selon le critère fixé. La première commande simulée de mars utilise donc les 35 jours FIA par repli, pas une valeur ajustée pour forcer la photo du 31 mars.

### Reproduction et contrôle

La [politique finale](../../artifacts/testing/empirical_delivery_20261001/calibration/final/empirical_policy.json) et les [exclusions](../../artifacts/testing/empirical_delivery_20261001/calibration/final/excluded_intervals.json) sont produites par `python -B -m etudecas.simulation.experiments.empirical_delivery --output etudecas/artifacts/testing/NOUVEAU_DOSSIER`. La commande utilise l'extraction détaillée `mrp_full_flow_audit_20260930/flows/results.json` et vérifie les Excel associés ; cette extraction reste une entrée nécessaire à la recalibration.

Le [protocole comparatif](../../artifacts/testing/empirical_delivery_20261001/study/plan.json) conserve les prévisions révisées de 039668 dans **les trois calculs de 1 825 jours** : Erlang, FIA fixe, empirique. Il ne mélange pas la correction des prévisions et celle des délais. Les graines et l'appariement par liaison/date sont conservés ; des décisions différentes peuvent néanmoins changer les dates et donc les tirages correspondants. Le témoin Erlang doit reproduire la variante révisée précédente. Les photos sources ne portent que sur 2025 ; les années suivantes vérifient la propagation et la stabilité, sans validation industrielle pluriannuelle.

L'oracle indépendant a vérifié directement les Excel, les conversions, les quatorze rapprochements et les différences autorisées des graphes : [130 contrôles des entrées](../../artifacts/testing/empirical_delivery_20261001/validation/inputs.json). Les rapprochements chronologiques et le tirage sans données futures sont également couverts par les tests ciblés en mémoire. Une bonne cohérence technique ne démontre pas que cette petite loi conditionnelle reproduit toute la variabilité industrielle.

### Résultats des trois simulations terminées

[Carte complète](../../resultats/regroupement_001757_20260929/carte_delais_empiriques.html) · [comparaison directe](../../resultats/regroupement_001757_20260929/comparaison_delais_empiriques.html). Les autres vues et les deux suivis de lots restent historiques. Le panneau de comparaison contient les trois nouveaux calculs et l'onglet Gaillac. Dans « Entrées / sorties », **Pourquoi ce délai fournisseur ?** détaille chaque achat empirique : taille du pool connu, décalage, événement et date de connaissance, ou repli fixe.

| 039668 / Avène, 2025 | Erlang, mêmes prévisions révisées | FIA fixe | Loi empirique |
|---|---:|---:|---:|
| Première commande | 5 mars | 5 mars | 5 mars |
| Première livraison physique | 14 mai | 9 avril | 9 avril |
| Première disponibilité | 15 mai | 10 avril | 10 avril |
| Écart absolu moyen aux 52 photos, kg | 178,27 | 137,12 | 140,21 |
| Clôtures à stock physique nul | 29 jours | 2 jours | 4 jours |
| Nouveaux ordres émis en 2025 | 4 × 450 kg | 4 × 450 kg | 4 × 450 kg |
| Réceptions physiques pendant 2025 | 1 350 kg | 1 350 kg | 1 350 kg |

La première réception avance de **35 jours** grâce au repli FIA fixe avant acquisition de l'historique suffisant. La photo source remonte dès le 31 mars : l'écart restant d'environ neuf jours jusqu'à la livraison du 9 avril ne doit pas être masqué par un ajustement supplémentaire de la distribution. Il reste à expliquer le besoin daté et le lancement du 5 mars. Les quatre délais empiriques de 039668 valent **35, 37, 30 et 37 jours** ; les livraisons de la dernière commande tombent en janvier 2026. Le cas fixe explique que la réduction de dispersion fait l'essentiel du progrès sur cette référence ; la distribution estimée n'optimise pas sa courbe.

Sur les **29 couples comparables**, la variante empirique améliore l'écart absolu moyen aux stocks sources pour **19**, le dégrade pour **8**, le conserve pour **2**. Le témoin fixe donne 16/8/5. Le couple partiel 001848/Gien, représenté seulement par engagements initiaux, figure parmi les inchangés ; aucune somme des kg, mètres et UN. Exemples : 001848/Avène passe de 2 323,62 à 2 114,05 kg ; 338929/Avène de 1 006 918,69 à 909 712,04 UN. En revanche, 001757/Avène passe de 2 634,33 à 2 639,49 kg. Ces résultats sont propres au scénario et à la graine testés, pas une preuve de supériorité statistique générale.

Les **385 achats externes lancés en 2025** sous loi empirique comprennent 157 replis fixes et 228 tirages depuis les observations déjà connues. Les décalages effectivement tirés cette année vont de −5 à +9 jours ; le −12 devient connu en décembre et n'a pas été tiré sur ces commandes. L'écart absolu moyen aux FIA tombe à 2,10 jours, avec 365/385 achats dans ±7 jours. Une partie de cette faible dispersion provient nécessairement du repli fixe : ce n'est pas un taux de ponctualité industriel observé. Le témoin Erlang avec ces mêmes prévisions compte 391 achats, écart absolu moyen 24,05 jours, 85 dans ±7 jours.

**Contrepartie réseau à conserver dans le bilan :** les deux variantes servent 28 800 UN de moins de 268091 pendant 2025 (3 499 453 contre 3 528 253), avec reliquat de fin d'année 76 989 au lieu de 48 189 UN. Le cumul quantité × jours de retard 2025 augmente également (304 797 contre 153 684 UN·jours). Cela ne permet pas d'attribuer la différence au seul composant 039668 : les délais de tous les achats externes ont changé. Sur cinq ans, le total servi reste identique ; le cumul de retard de 268091 diminue de 495,07 millions d'UN·jours à 460,94 millions en empirique, ou 452,25 millions en fixe. Le service de 268967 reste identique. Une amélioration des stocks d'un composant ne démontre donc pas une amélioration générale du service.

Le décompte limité aux **28 couples disposant de 52 photos** donne 18 améliorations, huit dégradations et deux inchangés pour l'empirique. Le 29e couple, 344135/Gien, n'a que trois photos ; son amélioration explique le total 19 ci-dessus. Le périmètre physique partiel de 001848/Gien reste une autre limite, distincte du nombre de photos.

Les trois exécutions se terminent avec code retour nul et moteur inchangé, en environ 11,5 minutes chacune sur ce poste, lancées en parallèle. Les 19 tests ciblés en mémoire et les trois qualifications physiques passent. La [contre-vérification finale](../../artifacts/testing/empirical_delivery_20261001/validation/outputs.json) passe 202 contrôles : 37 CSV Erlang strictement identiques à la référence révisée, 6 229 achats sur cinq ans contrôlés, tirages empiriques sans données futures, quantités UN entières, réceptions et disponibilités, champs exportés dans la carte et écarts de stock recalculés. Les [résultats détaillés](../../artifacts/testing/empirical_delivery_20261001/analysis.json) et le [manifeste de livraison](../../artifacts/testing/empirical_delivery_20261001/manifest.json) distinguent la cohérence technique de la calibration industrielle limitée. La loi est appliquée au nouveau scénario ; l'Erlang historique reste conservé comme référence.

## Dispersion des délais : sources et simulation — 30 septembre 2026

**La dispersion physique du modèle est une hypothèse non calibrée sur les commandes industrielles.** L'import FIA prend le délai source comme moyenne d'une loi Erlang à quatre étapes et fixe la borne haute à `max(délai + 14, 2 × délai)` (`update_supply_graph_from_case_data.py`, fonction d'application FIA). Seule la moyenne est renseignée par la FIA ; les quatre étapes et la borne sont des conventions. Le mode courant est `erlang`, avec délais stochastiques activés. Pour une référence de 35 jours, l'écart-type théorique avant arrondi et plafonnement vaut 17,5 jours et le plafond 70 jours. Une option nommée `industrial` existe, mais sa docstring précise également qu'elle est une approximation sans historique de commandes ; son nom ne constitue pas une validation industrielle.

Mesure sur la référence de cinq ans `gaillac_039668_20260930/study/reference`, nouveaux achats externes uniquement, hors carnet initial, transferts et apports amont simplifiés. Les groupes annuels suivent la **date de lancement**, même si la livraison intervient l'année suivante. Le délai mesuré va du lancement à la réception physique ; le traitement de réception avant disponibilité est exclu.

| Référence de délai | Achats lancés en 2025 | Délais physiques simulés min–max | Écarts par rapport à la référence |
|---|---:|---:|---:|
| 35 jours, quatre couples article/site | 35 | 10–70 jours | −25 à +35 jours |
| 42 jours, 338929/Avène | 30 | 11–80 jours | −31 à +38 jours |
| 84 jours, 001757/Avène | 147 | 6–168 jours | −78 à +84 jours |

Sur les **389 nouveaux achats externes lancés en 2025**, 84 sont dans ±7 jours de la référence (21,6 %), 242 s'en écartent de plus de 14 jours (62,2 %). L'écart absolu moyen est 24,10 jours, mais il mélange des délais de référence de 15 à 154 jours et donne un poids identique à chaque commande. Sur les **2 093 achats des cinq ans**, ces compteurs sont respectivement 477, 1 245 et 24,49 jours. Les 389 tirages 2025 utilisent tous quatre étapes Erlang. Les deux achats 039668 de la référence reçoivent 56 et 21 jours ; les quatre achats du scénario révisé reçoivent 70, 33, 27 et 52 jours. Ces valeurs ne sont pas des délais industriels mesurés.

**Dans les données sources, la mesure identifiable est différente : la stabilité des prochaines entrées projetées.** Pour chacun des 22 couples munis d'offres externes, on compare deux versions hebdomadaires consécutives et la première semaine H positive de chacune. On exclut le roulement normal lorsque l'ancienne échéance est déjà atteinte à la nouvelle version, ainsi que l'absence de H positif. Sur 1 087 transitions : 617 exclues pour échéance atteinte, sept sans prochaine entrée ; **463 comparaisons retenues**. Les dates sont inchangées dans 360 cas (77,8 %), se déplacent d'au plus sept jours dans 432 cas (93,3 %), d'au plus quatorze dans 448 (96,8 %). Les quantités restent identiques dans 417 cas ; elles changent dans 46. Les cibles incluent 2026 dans 67 comparaisons. La sélection concerne la prochaine entrée, pas toutes les réceptions, et n'identifie pas une même commande entre versions. Les décalages extrêmes, de −126 à +91 jours, peuvent notamment refléter suppressions, substitutions et modifications du plan ; ils ne doivent pas devenir une distribution de retards fournisseurs.

Pour **039668**, 46 comparaisons : 27 dates stables, onze avances de sept jours, six reports de sept jours, un de quatorze et un de vingt-huit. Exemple recoupé directement : `Feuille1!H398` annonce 300 kg le 13 avril dans le plan du 5 janvier ; `H5395` les situe au 30 mars dans celui du 9 février ; `H11417` au 6 avril dans celui du 23 mars ; `H12443` porte 450 kg au 30 mars dans celui du 30 mars. Les photos `Stocks!E1272` et `E1047` passent de 132,725 kg le 24 mars à 558,840 kg le 31 mars. Cette hausse corrobore une entrée fin mars ; elle n'identifie ni la date de commande ni un délai fournisseur réellement exécuté de 35 jours.

Le carnet initial ne contient pas non plus la date de création des commandes. Son intervalle livraison→disponibilité porte sur le traitement de réception : 99 dates sur 104 sont expliquées par les jours ouvrés et fériés dans l'audit précédent ; ce n'est pas une statistique de ponctualité du fournisseur. **Les 93,3 % de stabilité des plans et les 21,6 % de délais simulés proches de la référence ne sont donc pas deux mesures comparables directement.** Les sources ne justifient actuellement ni la forte dispersion Erlang du nominal ni, inversement, une nouvelle hypothèse arbitraire « fournisseurs toujours à ±7 jours ».

Aucun moteur ni résultat de simulation n'a été modifié pour cette analyse. La prochaine comparaison causale doit séparer délai FIA déterministe pour identifier les décisions MRP, traitement de réception documenté et scénario d'incertitude distinct. La variabilité empirique des fournisseurs reste à estimer avec des rapprochements explicitement qualifiés.

Preuves : [mesures simulées](../../artifacts/testing/gaillac_039668_20260930/delivery_variation.json), [révisions des plans et lignes sources](../../artifacts/testing/gaillac_039668_20260930/delivery_source_revision.json). Le parent et un agent en lecture seule retrouvent indépendamment les compteurs sources. L'agent a également contre-vérifié les 2 093 identités délai = réception physique − lancement, l'unicité des ordres et les statistiques simulées indiquées ci-dessus : 2 130 contrôles, aucun écart ; les percentiles accessoires du JSON ne sont pas inclus dans cette contre-vérification. Cette analyse de fichiers existants n'est pas une nouvelle qualification de simulation.

## Livraison Gaillac et diagnostic 039668 — 30 septembre 2026

La [carte complète](../../resultats/regroupement_001757_20260929/carte_gaillac_039668.html) conserve les vues historiques et leurs deux suivis de lots. Son bouton « Gaillac et 039668 · comparaison » ouvre les deux nouveaux calculs ; la [comparaison directe](../../resultats/regroupement_001757_20260929/comparaison_gaillac_039668.html) présente les mêmes données. Les références précédentes sont conservées. Les autres onglets historiques ne sont pas présentés comme les résultats du nouvel essai.

### Gaillac : représentation livrée et limites physiques

Le site actif `SDC-1450` reste une usine et porte désormais explicitement les fonctions réception, stockage, fabrication et expédition. Son nom devient « Gaillac — fabrication et stockage (D-1450) ». Aucun stock, procédé ni transport n'est créé par ce changement. Le nœud vide `DC-1450` était déjà absent de la carte compacte historique ; il ne s'agit pas d'un nouvel entrepôt supprimé.

L'onglet **Gaillac · fabrication et stockage** présente les cinq articles sources, la date de photo sélectionnable, les stocks disponible, indisponible et réservé, et les mouvements simulés séparés : achats, production, transport, consommation et libération. 001893 et 002612 y restent explicitement hors simulation physique. Le réapprovisionnement agrégé de 693055 apparaît comme « apport amont simplifié », sans le transformer en fabrication démontrée. Les liens des articles ouvrent leurs courbes.

Un tableau convertit quatre positions distinctes en **équivalent théorique de PF 268967** : 021081 à Gaillac, 773474 à Gaillac et à Gien, 268967 au dépôt. Les BOM donnent 8,94 kg de matière par kg intermédiaire et 0,009654718 kg intermédiaire par PF. Les résultats ne constituent pas une couverture industrielle : stocks potentiellement partagés, absence d'allocation, transit, encours et PF en usine exclus. Un stock ou un facteur absent donne une valeur absente, jamais zéro. L'objectif d'un an sur la chaîne ne devient pas un an de sécurité par site.

Deux simulations de **1 825 jours** sont terminées. La référence reproduit tous les résultats physiques antérieurs : **36 CSV identiques octet pour octet ; dans le 37e, seul le nom de Gaillac change sur trois lignes**. Le moteur est resté identique pendant les deux exécutions. La comparaison industrielle concerne uniquement 2025.

### 039668 : sources recoupées

| Paramètre | Valeur et provenance |
|---|---|
| Usage dans 268091 | 40,6 g pour 1 000 PF, soit 0,0000406 kg/PF ; `268091.xlsx/BOM!A8:F8`, `demand_PF.xlsx/BOM` ligne 40 |
| Fournisseur renseigné | VD1096202A ; `268091.xlsx/FIA!A14:H14` |
| Prix | 12,21 EUR/kg |
| Délai fournisseur de référence | 35 jours calendaires, `FIA!F14` |
| Quantité standard | 450 kg, `FIA!G14:H14` ; ne prouve pas un multiple obligatoire pour chaque ordre |
| Réception | 1 jour, E du flux MRP, constant dans les 52 versions |
| Sécurité | 7 jours ouvrés ; stock de sécurité fixe nul, sans supprimer la protection temporelle ; politique source ligne 18, ancienne politique ligne 10 |
| Stock initial | 459 695 g = 459,695 kg ; ancienne feuille Stocks ligne 15, nouvelle ligne 1045 |
| Valeur initiale | 5 612,87595 EUR = 459,695 × 12,21 ; nouvelle feuille Stocks F1045 |

Ces rapprochements ne montrent pas d'erreur d'un facteur 1 000. Aucun ordre initial de 039668 n'est repris du carnet. Les photos hebdomadaires concernent tout le stock Avène ; la BOM étudiée ne couvre que 268091.

**Premier défaut identifié : le complément de besoins pour les autres produits est figé sur janvier.** La référence conserve 34 périodes futures issues du premier plan, totalisant 823,065439 kg, et aucune période après le 25 octobre. Cette absence est une limite du scénario, pas une consommation industrielle nulle démontrée. Le plan initial contient 993,35 kg de besoins futurs, ou 1 026,35 kg en incluant la semaine courante. La part complémentaire estimée est 82,8575466 % ; ce n'est pas une allocation industrielle connue.

L'essai isolé réutilise le mécanisme commun de prévisions versionnées : 52 versions, 1 773 lignes futures, uniquement les versions connues à la date de décision, semaine courante figée. Il conserve la part initiale estimée, les quantités standard, prix, sécurité et politiques de délai. Il n'utilise ni les stocks futurs ni H/K pour ajuster cette part. Les I restent des besoins prévus, non des consommations exécutées observées.

### Résultats de l'essai — référence conservée

| Indicateur 039668 / Avène en 2025 | Référence | Prévisions révisées |
|---|---:|---:|
| Écart absolu moyen aux 52 photos, kg | 175,27 | 178,27 |
| Biais moyen simulé − source, kg | −150,44 | −92,66 |
| Nouveaux ordres lancés | 2 × 450 kg | 4 × 450 kg |
| Quantité physiquement reçue pendant 2025 | 450 kg | 1 350 kg |
| Consommation simulée pour 268091 | 46,7712 kg | 46,7712 kg |
| Consommation complémentaire estimée | 823,0654 kg | 1 657,3995 kg |
| Jours de clôture avec stock physique nul | 15 | 29 |
| Stock physique au 31 décembre | 39,8584 kg | 105,5243 kg |

Les photos sont rapprochées de la clôture simulée de la veille, ouverture exclue. Le 29 décembre, la source indique **479,795 kg** : ce n'est pas une photo au 31 décembre. La variante réduit le biais, mais dégrade l'écart absolu moyen de 1,71 % et augmente les jours de stock physique nul ; **elle ne remplace pas la référence**. Les améliorations de juillet et novembre ne compensent pas les dégradations d'avril et octobre. Sur les 29 couples comparables : 7 écarts moyens diminuent, 8 augmentent, 14 sont inchangés ; aucune somme entre unités. L'un des couples inchangés, 001848/Gien, n'a qu'un périmètre partiel d'engagements initiaux.

Le service client 2025 est identique dans les deux essais. Sur cinq ans, les quantités servies restent identiques ; le cumul quantité × jours de retard de 268091 diminue, de 542,33 à 495,07 millions d'UN·jours. Ce résultat ne valide pas une calibration industrielle sur cinq ans : les versions sources disponibles s'arrêtent en 2025.

**Deuxième problème à isoler : les délais tirés ne sont pas appariés entre les commandes des deux calculs.** Dans la référence, la première commande part le 23 mars, reçoit un délai fournisseur de 56 jours au lieu des 35 jours de référence, arrive le 18 mai et devient disponible le 19 mai. Dans l'essai, elle part le 5 mars, mais reçoit 70 jours : arrivée le 14 mai, disponibilité le 15 mai. À graine égale, une décision modifiée ne garantit pas les mêmes tirages par commande ; cet essai ne mesure donc pas l'effet pur du seul calendrier des besoins. Les délais tirés des quatre commandes de l'essai sont 70, 33, 27 et 52 jours, toujours pour une référence de 35 jours.

Les H de la semaine courante des plans du 30 mars, 22 juin, 26 octobre et 7 décembre portent respectivement **450, 450, 250 et 399,85 kg** (`Feuille1!H12443`, `H24453`, `H43135`, `H49534`). Des hausses de stocks proches suivent dans les photos. Cela corrobore des entrées à ces périodes, sans identifier quatre commandes exécutées ni leurs dates de création. Même avec 35 jours fixes après un lancement le 23 mars, la disponibilité tomberait le 28 avril : le tirage aléatoire n'explique donc pas à lui seul le décalage par rapport à la hausse source de fin mars.

**Suite commune à tester :** conserver la reconstruction des versions connues, mais comparer d'abord deux essais avec délais de référence déterministes pour isoler le déclenchement. Vérifier ensuite, pour chaque besoin daté, le stock utilisable, les engagements attendus, la sécurité et la taille standard au moment où une proposition devient nécessaire. Confronter les dates et quantités obtenues aux semaines H et aux photos, puis tester cette même règle sur d'autres matières. Ne pas ajouter de coefficient propre à 039668, forcer une réception sur une photo, ni considérer toutes les variations de I comme des consommations industrielles certaines.

Preuves : [protocole de référence](../../artifacts/testing/gaillac_039668_20260930/study/plan.json), [protocole de la variante](../../artifacts/testing/gaillac_039668_20260930/study/revisions_plan.json), [analyse des résultats](../../artifacts/testing/gaillac_039668_20260930/analysis.json), [97 contrôles indépendants](../../artifacts/testing/gaillac_039668_20260930/validation/final.json), [manifeste de livraison](../../artifacts/testing/gaillac_039668_20260930/manifest.json). Les contrôles arithmétiques ne certifient pas les règles industrielles absentes des sources.

## Gaillac : fabrication et stockage — revue du 30 septembre 2026

**Gaillac doit être traité comme un site assurant plusieurs fonctions : réception, stockage, fabrication et expédition.** Le stockage est déjà partiellement représenté ; le défaut principal est son périmètre incomplet, puis la représentation incomplète de la fabrication de 693055. Cette revue ne modifie pas le moteur, les flux ni les simulations de référence.

Le rapprochement porte sur le graphe effectivement utilisé par les derniers témoins (`artifacts/testing/mrp_delivery_rules_20260930/study/graph.json`), les sources Excel et les [plans MRP déjà audités](../../artifacts/testing/mrp_full_flow_audit_20260930/flows/results.json). Les quinze entrées enregistrées de cet audit ont été relues et leurs empreintes sont inchangées. Deux analyses indépendantes ont couvert les sources et le modèle ; aucun nouveau test, navigateur ou calcul physique n'a été lancé pour cette revue.

### Cinq stocks industriels, trois dans le modèle

Quantités en **kg**, y compris 693055 et 773474 convertis depuis les grammes sources. Les valeurs de fin sont les **photos du 29 décembre**, pas une clôture inventée au 31 décembre. Chaque article dispose de 53 photos, ouverture du 1er janvier comprise.

| Article à Gaillac | Stock au 1er janvier 2025 | Stock au 29 décembre 2025 | Représentation actuelle |
|---|---:|---:|---|
| 001893 | 1 094 | 979,5 | Stock source présent, absent du périmètre physique simulé |
| 002612 | 414 | 277,5 | Stock source présent, absent du périmètre physique simulé |
| 021081 | 1 142 100 | 1 534 614 | Stock représenté ; matière de la fabrication de 773474 |
| 693055 | 1 800 | 10 | Stock et transfert vers Avène représentés ; fabrication amont agrégée |
| 773474 | 9 600 | 35 200 | Stock, fabrication locale et transfert vers Gien représentés |

Provenance : `Flow_Data_Inventory_and_Replenishment_rules.xlsx/Stocks`, colonne E pour la quantité et H pour la date. Lignes initiale/finale respectives : 001893 **1406/845**, 002612 **1435/817**, 021081 **1576/579**, 693055 **1051/1474**, 773474 **209/1528**. Les deux stocks absents du modèle figuraient déjà dans `Extract_Données_Complémentaires.xlsx/Stocks`, lignes 5 et 7 : ce ne sont pas de nouveaux stocks apparus seulement dans le fichier hebdomadaire.

### Fonctions et routes prouvées, sorties restant à attribuer

`demand_PF.xlsx/Acteurs!A7:K7` décrit Gaillac comme fabricant de **693055 et 773474**. Les ordres `O.Proc` du carnet initial, `Extract_En_cours.xlsx/Sheet1`, lignes **103 et 105**, portent respectivement 600 kg et 3 200 kg de ces produits à Gaillac.

- **021081 → 773474 à Gaillac** : BOM de `773474.xlsx`, ligne 2, 8,94 kg de matière pour 1 kg de produit intermédiaire.
- **773474 : Gaillac → Gien** : `demand_PF.xlsx/Relations_acteurs`, ligne 9, et `268967.xlsx/FIA`, ligne 9. Les 10 jours FIA sont un délai d'approvisionnement interne ; ils ne prouvent pas dix jours de trajet routier.
- **693055 : Gaillac → Avène** : `demand_PF.xlsx/Relations_acteurs`, ligne 36, et `268091.xlsx/FIA`, ligne 22. Même distinction pour les 70 jours indiqués. Le BOM amont de 693055 manque ; le moteur représente actuellement son réapprovisionnement agrégé par 600 kg avec une convention de délai, pas sa fabrication physique complète.
- **001893 et 002612 à Gaillac** : le stockage et des besoins MRP sont prouvés, mais les sources examinées ne donnent pas de route Gaillac → Avène pour ces matières. Les routes renseignées vers Avène viennent de fournisseurs externes. Les ordres du carnet en division **1820** ne doivent pas être réaffectés à 1450 ou 1810 sans correspondance explicite.

Pour le plan du 5 janvier, les sorties I de Gaillac comprennent **607,103 kg de 001893** le 23 février et le 13 juillet (`Feuille1!I115`, `I117`), puis **1 300 et 245 kg de 002612** les 23 février et 16 mars (`I160`, `I161`). Le rapprochement exploratoire de toutes les versions, sur les cibles 2025, trouve **zéro égalité de quantité** entre ces I à Gaillac et un H à Avène la même semaine ou la suivante : 92 occurrences positives examinées pour 001893, 215 pour 002612. Ce sont des occurrences dans des plans révisés, pas des commandes annuelles. L'absence de correspondance directe ne prouve pas l'absence de transferts fractionnés, regroupés ou décalés ; elle interdit simplement de présenter un routage vers Avène comme déjà reconstitué.

### Correction à préparer sans inventer les flux

1. **Un seul site physique Gaillac, plusieurs fonctions.** Le graphe porte `SDC-1450`, type `factory`, avec les trois stocks actifs, et un `DC-1450` vide, isolé. Ce second nœud ne représente pas un second entrepôt industriel démontré. Conserver l'identifiant actif et réconcilier les alias avant de retirer le doublon d'affichage ; ne pas dupliquer les quantités.
2. **Présenter les cinq stocks dans la vue site**, avec les deux matières manquantes explicitement marquées « stock source ; flux non représentés ». Leur future intégration physique exige d'attribuer leurs entrées et sorties ; ajouter un stock initial immobile ne reproduirait pas leur gestion réelle.
3. **Séparer les opérations** : achat externe, fabrication locale, transfert interne, consommation et libération du stock déjà détenu. Le passage indisponible → disponible conserve la quantité physique. Exemple 773474 au 5 janvier : 6 400 kg disponibles + 3 200 kg disponibles plus tard = 9 600 kg déjà présents (`Feuille1!J968`, `J970`), pas 3 200 kg de nouvelle réception.
4. **Séparer les calendriers et les limites** : fermeture de production, réception, libération et expédition ne sont pas interchangeables. Aucune capacité maximale d'entreposage documentée n'est actuellement portée par le graphe. Le maximum de stock observé n'est pas une capacité d'entrepôt ; les limites de lots de fabrication n'en sont pas une non plus. Les coûts d'entreposage actuels sont des conventions, et ceux des deux PFI ne disposent pas d'un taux exploitable : un coût nul par défaut ne signifie pas stockage gratuit.
5. **Calculer la couverture de 268967 sur toute la chaîne** : convertir les stocks distincts de 021081, de 773474 et des PF en équivalent PF avec les BOM et rendements applicables, en distinguant disponible, indisponible et transit. L'objectif utilisateur d'environ un an concerne le total de la chaîne, pas une année de sécurité ajoutée à chaque site ; il ne s'applique pas automatiquement à 001893, 002612 ou 693055. Une matière déjà consommée ne doit plus figurer simultanément en stock amont et dans le produit fabriqué.

**Décision de cette revue :** rôle mixte Gaillac confirmé ; routages PFI confirmés ; rôle de réserve des deux autres matières pour Avène non établi. Priorité à compléter la vue des stocks et à expliquer leurs mouvements, avant de modifier le pilotage MRP ou de créer des transferts. Les soldes nets des photos et les H/I prévisionnels ne suffisent pas à attribuer chaque mouvement exécuté.

## Essai du calendrier de réception dans le moteur — 30 septembre 2026

Une option **désactivée par défaut** accepte désormais des dates non ouvrées explicites dans chaque politique de réception fournisseur : `nonworking_dates`, `calendar_id`, `calendar_status`, `calendar_source`. L'opérateur commun compte les jours lundi–vendredi après la livraison G, en excluant les dates renseignées, jusqu'à atteindre E jours de réception. E = 0 conserve G. Les dates sont absolues : aucune répétition annuelle n'est déduite d'une liste 2025.

Le calendrier intervient aux trois endroits du parcours d'achat externe daté : délai de référence au jour de décision, calendrier des offres principal/secours, disponibilité I des nouveaux ordres lancés. Les dates G/I du carnet initial, J détenu initialement, le délai fournisseur FIA, la sécurité, les fabrications et les transferts internes ne sont pas recalculés par cette option. Les 39 cas ciblés en mémoire passent ; le comportement historique sans dates supplémentaires reste couvert.

Le [protocole comparatif](../../artifacts/testing/mrp_receipt_calendar_20260930/study/plan.json) prévoit deux simulations de **1 825 jours**, mêmes paramètres et aléas configurés. `reference` conserve le graphe précédent ; `calendar` ajoute seulement les fériés métropolitains 2025 aux **22 couples d'achats externes concernés**, plus la fermeture du 4 au 17 août pour le seul couple 021081/Gaillac. Cette portée reste une hypothèse conditionnelle de calendrier de réception, pas un arrêt généralisé de l'entreprise. La comparaison industrielle porte uniquement sur 2025 ; les années suivantes testent la stabilité et la propagation, sans calendrier annuel extrapolé.

**Point de contrôle causal :** la référence n'a aucun nouvel achat de 021081 en 2025 ; le premier est au jour 554, le 9 juillet 2026. Les engagements initiaux ont déjà leurs dates G/I renseignées. On n'attend donc aucun effet direct de la fermeture 2025 sur les nouvelles réceptions de ce composant ; un changement à Gaillac peut venir indirectement du reste du réseau. L'expérience ne doit pas être présentée comme une correction des 23 commandes initiales.

**Limite du planificateur :** hors sourcing explicite, les propositions futures utilisent encore un délai entier recalculé au jour de décision. Chaque ordre réellement lancé recalcule sa disponibilité exacte depuis sa livraison et son calendrier ; le calendrier des offres principal/secours est également daté. Une résolution exacte de toutes les dates futures de proposition relève d'un changement distinct. Les comparaisons H/K des plans restent diagnostiques, notamment parce que H source et les entrées simulées ne sont pas forcément datés au même stade physique/disponible.

Les preuves sources et le différentiel des graphes sont contre-vérifiés dans [input_check.json](../../artifacts/testing/mrp_receipt_calendar_20260930/validation/input_check.json). Les deux simulations de 1 825 jours sont terminées, avec le moteur inchangé pendant les calculs. Sans activation du calendrier, les 37 CSV du témoin reproduisent ceux de la référence précédente à l'identique. Les invariants des deux calculs et le recalcul indépendant des dates G/E/I, des stocks tenus et des lots passent ; voir [la contre-vérification](../../artifacts/testing/mrp_receipt_calendar_20260930/validation/runs_check.json) et [le manifeste de cette passe](../../artifacts/testing/mrp_receipt_calendar_20260930/manifest.json). La même graine aléatoire est conservée ; après une modification des décisions, cela ne garantit pas un tirage identique pour chaque commande correspondante.

### Résultat et décision

**Le calendrier est mieux explicité, mais cette variante ne constitue pas une amélioration générale de calibration. Elle reste optionnelle et ne remplace pas la référence.** Sur les 28 couples article/site avec stock représenté dans le graphe et photos comparables, l'écart absolu moyen aux stocks sources diminue pour 14, augmente pour 11 et reste identique pour 3. Le 29e couple comparable, 001848/Gien, n'est représenté que par les engagements initiaux ; son résultat inchangé est compté séparément. Les unités ne sont pas additionnées entre articles.

L'écart ci-dessous compare le stock physique simulé (disponible + réservé + indisponible) en clôture de la veille aux photos du lundi de 2025. La photo initiale n'entre pas dans cette moyenne et les données absentes ne sont pas remplacées par zéro.

| Article / site | Unité | Écart moyen de référence | Avec calendrier | Lecture |
|---|---|---:|---:|---|
| 001757 / Avène | kg | 2 637,03 | 2 802,79 | Dégradation de 165,75 kg |
| 001848 / Avène | kg | 2 325,64 | 2 321,37 | Amélioration faible |
| 002612 / Avène | kg | 70 412,23 | 69 066,11 | Amélioration, écart encore important |
| 038005 / Gien | kg | 26 458,01 | 28 752,57 | Dégradation |
| 042342 / Gien | UN | 35 955 023,48 | 36 242 836,54 | Dégradation ; périmètre partagé toujours à considérer |
| 338929 / Avène | UN | 1 005 257,15 | 1 004 517,35 | Amélioration faible |
| 021081 / Gaillac | kg | 233 299,65 | 233 299,65 | Aucun effet, conformément au contrôle causal |

Le **service client 2025 reste identique** : 3 528 253 UN servies pour 268091, avec environ 48 189 UN en attente en fin d'année ; 1 575 985 UN servies pour 268967, avec un reliquat prévisionnel inférieur à une unité. Sur les cinq ans, les quantités totales servies et le cumul quantité × jours de retard sont également identiques. Cela ne démontre pas une correspondance avec le service industriel réel.

À dates de livraison G, délais E et quantités de commande du témoin fixés, l'ajout du calendrier reporte la disponibilité de **79 nouveaux ordres sur 389 lancés en 2025**, de 1 à 5 jours calendaires ; les 310 autres restent identiques. Ce calcul isole l'effet direct sur les dates et n'est pas une troisième simulation. Dans la simulation complète, les décisions peuvent ensuite changer : 001757 passe de **147 à 141 nouveaux ordres**, pour **34 700 kg commandés dans les deux cas** ; 001848 conserve quatre ordres et 22 000 kg, dont trois ordres au principal et un au secours. Ces compteurs excluent les engagements initiaux et ne sont pas des nombres de commandes industrielles déduits des versions hebdomadaires MRP.

Les projections MRP ne donnent pas non plus une amélioration uniforme. Pour 001757, l'écart moyen de K projeté passe de 2 947,41 à 3 104,19 kg. Pour 693055/Gaillac, il reste proche de 1 387 kg. Les comparaisons de H restent diagnostiques tant que les dates physiques et disponibles ne sont pas strictement alignées ; les versions successives d'un plan ne sont pas additionnées comme des flux exécutés.

**Suite prioritaire :** expliquer le déclenchement et le regroupement des propositions à partir des besoins datés, du stock disponible, des engagements et de la sécurité. Utiliser 001757 pour identifier une règle candidate, puis la confronter à 001848, 693055 et aux autres articles sans coefficients ajustés par période. Le calendrier testé est une brique métier distincte, pas une justification pour modifier les quantités de sécurité ou forcer les courbes de stock.

Résultats complets : [comparaison par couple](../../artifacts/testing/mrp_receipt_calendar_20260930/stock_comparison.csv), [flux, service et projections](../../artifacts/testing/mrp_receipt_calendar_20260930/comparison.json). Les durées des calculs parallèles sont d'environ 618 et 623 secondes ; ce ne sont pas des mesures isolées de performance. Aucune nouvelle carte HTML n'a été générée dans cette passe.

## Complément : fermeture d'août 2025 — 30 septembre 2026

L'utilisateur indique une fermeture de l'entreprise pendant les **deux ou trois premières semaines d'août**. Les dates exactes et le périmètre (sites, production, réception, contrôle/libération) ne sont pas encore précisés. Cette information justifie une passe ciblée sur les calendriers et les signatures de stock ; elle ne transforme pas toutes les semaines sans mouvement en fermetures démontrées.

Quatre interprétations calendaires ont été fixées avant le calcul, sans recherche automatique des dates donnant le meilleur ajustement. Toutes conservent lundi–vendredi et les jours fériés métropolitains 2025, puis suspendent le compteur du délai de réception pendant l'intervalle candidat. Les dates de livraison G, durées H et disponibilités I des **104 lignes du carnet initial** sont relues directement.

| Fermeture candidate, bornes incluses | Dates I reproduites | Écarts restants |
|---|---:|---|
| Aucune fermeture estivale, jours fériés seulement | 99/104 | Cinq lignes de 021081/Gaillac |
| **4–17 août : deux premières semaines complètes** | **104/104** | Aucun |
| 4–24 août : trois premières semaines complètes | 99/104 | Les cinq dates sont prédites sept jours trop tard |
| 1–14 août : quatorze premiers jours calendaires | 99/104 | Les mêmes cinq lignes restent décalées |
| 1–21 août : vingt et un premiers jours calendaires | 99/104 | Les cinq dates sont prédites sept jours trop tard |

**Les neuf jours supplémentaires sont expliqués par les 4–8 et 11–14 août**, le vendredi 15 août étant déjà exclu comme férié. Exemple `Extract_En_cours/Sheet1!G23:I23` : livraison le 16 avril, temps de réception 75 jours, disponibilité indiquée le **21 août**. Le calcul donne le 7 août sans fermeture estivale, **le 21 août avec fermeture 4–17 août**, et le 28 août avec fermeture 4–24 août. Autre exemple, ligne 25 : livraison le 20 mai, disponibilité le **19 septembre**, reproduite par la même règle, sans coefficient propre à l'article ou au mois.

**Portée de la preuve :** seules cinq lignes (23, 25, 30, 39 et 42), toutes sur 021081 à Gaillac, permettent de départager les candidats. Les 99 autres restent identiques dans tous les essais ; deux des cinq lignes partagent les mêmes dates. Le résultat étaye donc fortement ce **calendrier de réception/disponibilité à Gaillac parmi les hypothèses testées**, mais ne démontre pas deux semaines de fermeture pour toutes les usines et toutes les fonctions. Une fermeture de production de trois semaines peut coexister avec une disponibilité qualité reprenant plus tôt. Les dates du carnet sont des dates documentées, pas la preuve de leur exécution industrielle ultérieure.

La règle candidate se formule ainsi : **date disponible = avancer depuis la date de livraison du nombre de jours de réception renseigné, en utilisant le calendrier applicable à la fonction et au site**. Elle ne change ni le délai fournisseur FIA, ni les jours de sécurité, ni les dates déjà explicites du carnet. L'intégration dans le moteur reste à qualifier séparément ; aucune modification du nominal n'est faite par cette passe.

Cette hypothèse suspend le **décompte des jours de réception pendant la fermeture** ; il ne suffit pas de déplacer au jour de reprise une disponibilité qui tomberait pendant les congés. La ligne 25 le montre : sans fermeture, le calcul donne le 8 septembre, déjà hors août ; le carnet donne le 19 septembre. Le décompte suspendu retrouve le 19 septembre. Cela ne démontre pas que tous les phénomènes physiques ou chimiques sont suspendus, seulement que ce calendrier explique le délai de gestion représenté par les dates du carnet.

### Croisement avec les photos et les plans de l'été

La passe complémentaire couvre tous les couples dans les plans de juin à septembre. Le tableau indique le nombre de références dont la quantité physique photographiée est **strictement identique entre les deux lundis**. Les références sans deux photos sont exclues, pas remplacées par zéro.

| Site | 28 juillet → 4 août | 4 → 11 août | 11 → 18 août | 18 → 25 août |
|---|---:|---:|---:|---:|
| Avène | 15/15 | 15/15 | 15/15 | 0/15 |
| Gaillac | 5/5 | 5/5 | 5/5 | 4/5 |
| Gien | 3/9 | 2/9 | 9/9 | 5/9 |
| Dépôt Muret | 0/2 | 0/2 | 0/2 | 0/2 |

À Avène, les 15 stocks changent également du 21 au 28 juillet : le plateau commun est donc borné par les photos **28 juillet–18 août**, soit trois intervalles hebdomadaires, puis tous changent du 18 au 25 août. À Gaillac, les cinq stocks étaient déjà stables du 21 au 28 juillet ; on ne peut pas y dater le début de fermeture à partir de ce seul plateau. Gien montre des changements plus tardifs et le dépôt continue à varier. C'est compatible avec des calendriers différents selon le site ou la fonction. Une photo inchangée peut aussi refléter des mouvements compensés ou une photo reconduite : elle ne démontre pas à elle seule l'absence de tout flux brut.

Deux exemples expliquent pourquoi il faut séparer les flux :

- **001757/Avène**, plans des 27 juillet, 3 et 10 août : H = 2 000 kg et I = 1 200 kg sont reconduits, avec J courant = 3 855,020 kg et J futur = 1 975 kg. Les photos restent à 5 830,020 kg. Les I répétés ne constituent pas une preuve de consommations réalisées pendant la fermeture (`I29064/I30080/I31120`).
- **021081/Gaillac**, plans des 17 et 24 août : J courant passe de **455 560 à 955 320 kg**, J futur de **1 319 640 à 819 880 kg**, mais le total reste **1 775 200 kg**, égal aux photos correspondantes. Les 499 760 kg passent du stock détenu disponible plus tard au stock courant (`J32433`, puis `J33461`) : ce n'est pas une nouvelle livraison physique de 499 760 kg.

Ces observations ne justifient pas un blocage unique de tout le réseau pendant trois semaines. La suite doit distinguer les calendriers de **fabrication, réception physique, mise à disposition et expédition**, ainsi que le report des besoins non exécutés. Le calendrier fournisseur et le calcul de sécurité ne doivent pas être modifiés par propagation implicite de la fermeture de l'usine. Les années autres que 2025 nécessitent leur propre calendrier ou une convention explicitement déclarée.

Les détails de cette passe sont dans [les rapprochements été](../../artifacts/testing/mrp_august_closure_20260930/flows/results.json) et [la contre-vérification des photos](../../artifacts/testing/mrp_august_closure_20260930/validation/august_stock_check.json).

Preuves : [calcul des candidats](../../artifacts/testing/mrp_august_closure_20260930/calendar.json), [oracle indépendant](../../artifacts/testing/mrp_august_closure_20260930/validation/closure_check.json), [manifeste de cette passe](../../artifacts/testing/mrp_august_closure_20260930/manifest.json). La conclusion de l'audit antérieur « cinq dates restent inexpliquées » est désormais précisée par cette nouvelle information utilisateur et cette hypothèse testée ; ses preuves historiques restent conservées.

## Audit exhaustif des flux et des stocks 2025 — 30 septembre 2026

**Conclusion : les données permettent un rapprochement beaucoup plus précis, mais il serait faux de dire que toutes les règles industrielles sont déjà respectées par la simulation.** Les conversions BOM sont cohérentes ; les stocks détenus et disponibles sont distingués ; les principales incertitudes concernent les calendriers de réception, les usages partagés, les catalogues fournisseurs et le déclenchement des achats/fabrications. Cet audit ne change ni le moteur, ni les Excel, ni le nominal, ni les cartes conservées.

La preuve courante est [le manifeste de cet audit](../../artifacts/testing/mrp_full_flow_audit_20260930/manifest.json). Il rassemble une extraction exhaustive, une lecture du code et une contre-vérification indépendante. Les simulations utilisées sont les calculs existants `mrp_delivery_rules_20260930/study/reference` et `fia_fixe`, exécutés sur 1 825 jours ; **seule leur première année, 2025, est rapprochée ici**. Aucune nouvelle simulation ni campagne de tests artificiels n'a été exécutée pour cet audit en lecture seule.

### Périmètre et sens des données

- **53 398 lignes MRP**, 26 articles, 33 couples article/site, quatre sites et 52 dates de plan globales ; **1 637 plans article/site**. Tous les couples n'ont pas 52 versions : 029313/Gien en a huit, 344135/Gien en a 17, à partir du 7 septembre.
- **1 646 photos de stock sur 32 couples**, dont 31 photos au 1er janvier et 1 615 photos du lundi. 029313/Gien n'a pas de photo ; 344135/Gien n'en a que trois.
- **104 lignes du carnet initial** : 53 `AVICDE`, 29 `ECHCDE`, 22 `O.Proc`. Ce sont des éléments existants, pas un historique des commandes créées pendant toute l'année ; aucun identifiant d'ordre ni date de création n'est ajouté par l'audit.
- **35 offres FIA**, dont 33 externes et deux approvisionnements internes, pour 24 couples. Six couples ont plusieurs offres. Le détail des prix, bases, devises, standards, délais et cellules se trouve dans le [catalogue fournisseurs](../../artifacts/testing/mrp_purchase_parameters_20260930/extraction/purchase_offers.csv), dont les 12 empreintes Excel ont été revérifiées.
- **24 lignes de nomenclature industrielle**, normalisées et rapprochées des anciens classeurs et du graphe réellement simulé : [détail BOM](../../artifacts/testing/mrp_full_flow_audit_20260930/bom_crosswalk.csv).

Dans `Flow_Data_MRP_results/Feuille1`, **H = entrées projetées**, **I = besoins**, **J = stock déjà détenu, ventilé selon sa disponibilité**, **K = solde projeté**. La colonne E contient le temps de réception, pas le délai fournisseur FIA. Les unités G sont converties en KG ; ZUN en UN ; M reste en mètres. Toutes les lignes sont lues, y compris masquées.

Les 53 398 bilans `K = K précédent + J + H − I` concordent, sans doublon de clé. Cela vérifie la cohérence arithmétique de l'export, pas sa réalisation physique. **19 359 semaines internes ne sont pas renseignées**, dans 1 480 plans ; 1 492 plans s'arrêtent avant la borne de 364 jours. Aucun besoin ni flux brut n'est déclaré nul dans ces semaines par l'audit. Un bilan net inchangé entre deux lignes ne permet pas de séparer les entrées et sorties absentes.

### Quantités et fréquence, pour chacun des 33 couples

Le tableau donne les échéances 2025 du **premier plan disponible par couple** : 5 janvier, sauf 344135/Gien au 7 septembre. « Sem. H+ » compte les semaines où une entrée est projetée : **ce n'est pas le nombre de commandes individuelles réellement passées**. Les semaines absentes sont exclues, sans annualisation. Le [CSV complet](../../artifacts/testing/mrp_full_flow_audit_20260930/flows/summary.csv) ajoute les besoins, tailles médianes, intervalles entre entrées et une seconde lecture des semaines courantes des versions successives ; cette seconde lecture reste un ensemble de prévisions, pas un historique exécuté.

La dernière colonne mesure l'écart absolu moyen entre les stocks physiques de la simulation de référence et les photos réelles de 2025, dans l'unité de la ligne. La clôture simulée de la veille est comparée à chaque photo du lundi ; 52 photos par couple, **sauf 344135 : trois seulement**. « Absent » signifie pas de comparaison, jamais stock nul. Les quatre absences sont trois couples hors du registre physique simulé et 029313/Gien sans photo. Les périmètres industriels partagés restent à considérer : une erreur de stock ne mesure pas à elle seule la qualité de la règle MRP.

Sites : 1810 Avène ; 1430 Gien ; 1450 Gaillac ; 1920 dépôt Muret. E est le temps de réception déclaré dans le flux MRP.

| Article/site | Unité | Sem. renseignées | Sem. H+ | Quantité H projetée | E jours | Écart moyen stock référence |
|---|---|---:|---:|---:|---:|---:|
| 001757/1810 | KG | 32 | 10 | 18000.000 | 13 | 2637.0 |
| 001848/1430 | KG | 48 | 14 | 98000.000 | 26 | 23408.3 |
| 001848/1810 | KG | 30 | 2 | 9331.160 | 13 | 2325.6 |
| 001893/1450 | KG | 5 | 2 | 700.000 | 5 | absent |
| 001893/1810 | KG | 40 | 32 | 188308.217 | 24 | 37166.9 |
| 002612/1450 | KG | 4 | 2 | 2500.000 | 5 | absent |
| 002612/1810 | KG | 40 | 10 | 210505.604 | 9 | 70412.2 |
| 007923/1430 | KG | 1 | 0 | 0.000 | 0 | absent |
| 007923/1810 | KG | 38 | 6 | 114510.000 | 6 | 25951.4 |
| 016332/1810 | KG | 36 | 21 | 6892.960 | 1 | 484.4 |
| 021081/1450 | KG | 35 | 14 | 1320000.000 | 75 | 233299.7 |
| 029313/1430 | KG | 1 | 0 | 0.000 | 0 | absent |
| 029313/1810 | KG | 31 | 3 | 859.175 | 1 | 138.2 |
| 038005/1430 | KG | 39 | 15 | 160000.000 | 14 | 26458.0 |
| 039668/1810 | KG | 35 | 2 | 572.655 | 1 | 175.3 |
| 042342/1430 | UN | 24 | 8 | 240000000.000 | 14 | 35955023.5 |
| 049371/1810 | KG | 29 | 8 | 21600.000 | 9 | 3891.3 |
| 055703/1810 | KG | 35 | 5 | 1301.565 | 13 | 451.4 |
| 099439/1810 | KG | 37 | 24 | 38257.258 | 1 | 2792.1 |
| 268091/1920 | UN | 48 | 48 | 4450277.000 | 10 | 491987.6 |
| 268967/1920 | UN | 52 | 30 | 1594134.000 | 15 | 388933.9 |
| 333362/1430 | UN | 18 | 9 | 1346000.000 | 5 | 338282.1 |
| 338928/1810 | UN | 41 | 32 | 4431930.000 | 6 | 605222.6 |
| 338929/1810 | UN | 39 | 23 | 3055636.000 | 6 | 1005257.2 |
| 344135/1430 | UN | 3 | 2 | 331537.000 | 4 | 564999.0 |
| 426331/1810 | UN | 41 | 10 | 108560.000 | 1 | 7251.0 |
| 693055/1450 | KG | 26 | 16 | 11400.000 | 28 | 856.9 |
| 693055/1810 | KG | 39 | 17 | 10800.000 | 7 | 708.4 |
| 708073/1430 | KG | 37 | 3 | 30000.000 | 5 | 3873.6 |
| 730384/1430 | M | 13 | 3 | 261000.000 | 5 | 152343.4 |
| 734545/1430 | UN | 41 | 6 | 38400.000 | 1 | 2240.8 |
| 773474/1430 | KG | 27 | 12 | 73600.000 | 6 | 11636.2 |
| 773474/1450 | KG | 17 | 10 | 64000.000 | 33 | 20307.7 |

Exemple qui interdit de compter chaque H courant comme une nouvelle commande : pour **001757**, les versions des 27 juillet, 3 août et 10 août reprennent H = 2 000 kg, I = 1 200 kg, J courant = 3 855,020 kg et J futur = 1 975 kg. Les photos des 28 juillet, 4 août et 11 août restent toutes à **5 830,020 kg**. Références MRP : H29064/H30080/H31120 et J29066/J30082/J31122 ; inventaire : E1583/E1381/E612. Additionner H donnerait 6 000 kg sans preuve de trois nouveaux achats. Cela reste compatible avec des propositions/engagements reconduits, sans identification certaine d'une même commande.

Dans la simulation, les identifiants permettent en revanche un vrai décompte : la référence a lancé en 2025 **147 achats de 001757 pour 34 700 kg**, quatre de 001848 pour 22 000 kg, six de 002612 pour 135 000 kg et 30 de 338929 pour 2 151 600 UN. Ce sont les nouveaux achats externes par année de lancement, hors carnet initial et hors transferts ; pas les réceptions de l'année. Tous les couples et la variante FIA fixe figurent dans [simulation_2025.csv](../../artifacts/testing/mrp_full_flow_audit_20260930/simulation_2025.csv).

### Ce que l'évolution réelle des stocks apporte

La comparaison de **la somme J du seul plan courant** à la photo du lundi suivant donne **1 131 égalités sur 1 615 rapprochements**, soit environ 70 %. Comparer seulement J immédiatement disponible ne donne que 890 égalités : le stock déjà détenu mais disponible plus tard est indispensable. Les 484 écarts restants ne sont pas tous des erreurs de quantité : statuts exclus, réservations et différence d'horodatage restent des explications à départager.

- 001757, 001848/Avène, 002612/Avène, 007923/Avène et 338929 concordent **51 semaines sur 52** ; le 2 mars concentre 29 écarts parmi les couples, ce qui invite à traiter cette version commune avant d'inventer 29 règles différentes.
- 042342/Gien présente un écart de **−1 500 000 UN sur 42 semaines** entre J total et la photo. 002612/Gaillac présente **−19 kg sur 51 semaines** ; 693055/Gaillac **−10 kg sur 51 semaines**. Ce sont des différences de périmètre/statut possibles, pas des coefficients de consommation établis.
- Les deux PF au dépôt ne concordent jamais exactement entre J et le stock total : cette différence doit être conservée dans le rapprochement des stocks disponibles, réservés et physiques.
- La source actuelle contient bien **1 250 kg** pour 002612/Gaillac le 6 janvier (`Stocks!E946`). L'ancienne anomalie à 1 250 414 ne doit plus être utilisée comme valeur du fichier courant. J vaut 395 kg dans le plan du 5 janvier (`Feuille1!J158`) : cet autre écart reste visible.
- L'ancien inventaire au 1er janvier se raccorde au nouveau sur 31 couples : 28 concordances au seuil de 0,000001 unité ; écarts de +0,00328125 kg pour 002612/Avène, −0,000172 kg pour 038005/Gien et +1 UN pour 042342/Gien. 344135 n'a pas de photo récente au 1er janvier. Ces petites différences ne justifient pas les grands écarts ultérieurs.

Le [rapprochement hebdomadaire](../../artifacts/testing/mrp_full_flow_audit_20260930/stock_2025_bridge.csv) conserve **1 583 intervalles de sept jours**. Il compare le changement réel de stock à H−I de la semaine suivante annoncé par le plan précédent ; une semaine source absente reste vide. Ce rapprochement repose sur une hypothèse d'alignement temporel déclarée : son résidu ne permet pas d'identifier séparément les réceptions exécutées, les prélèvements, les ajustements et les transferts. J futur n'est jamais ajouté comme une nouvelle arrivée physique.

### Délais : une nouvelle hypothèse commune étayée

Il faut traiter séparément **délai fournisseur FIA**, **réception/disponibilité** et **sécurité**. La FIA ne précise pas le calendrier de son délai ; le simulateur le traite comme calendaire. Les jours de sécurité suivent la convention utilisateur lundi–vendredi. Le carnet donne des dates G de livraison et I de disponibilité, ainsi qu'un nombre H de jours de réception.

Sur **toutes les 104 lignes du carnet** :

| Calcul de disponibilité depuis G | Dates I reproduites |
|---|---:|
| Ajouter H jours calendaires | 3/104 |
| Ajouter H jours lundi–vendredi | 70/104 |
| Ajouter H jours lundi–vendredi en excluant les jours fériés métropolitains 2025 | **99/104** |

Le calendrier candidat reprend la [liste officielle des jours fériés 2025](https://calendrier.api.gouv.fr/jours-feries/metropole/2025.json), consultée le 30 septembre 2026. La [preuve de calcul](../../artifacts/testing/mrp_full_flow_audit_20260930/receipt_calendar.json) conserve toutes les dates candidates, les 104 prédictions et les écarts. Les cinq restants concernent **021081/Gaillac**, lignes 23, 25, 30, 39 et 42 : chaque intervalle contient **neuf jours ouvrés non fériés de plus** que les 75 jours indiqués. Fermeture estivale ou autre indisponibilité commune est une hypothèse ; les dates exactes de fermeture ne sont pas identifiées. Ce calcul rétrospectif n'active aucun nouveau calendrier et ne modifie pas la sécurité.

Le champ E du MRP est constant pour chaque couple, mais diffère du carnet sur huit couples : 001848/Gien 14→26 ; 002612/Avène 8→9 ; 049371/Avène 8→9 ; 333362/Gien 4→5 ; 338929/Avène 4→6 ; 693055/Gaillac 21→28 ; 734545/Gien 0→1 ; 773474/Gaillac 26→33. Ne pas additionner deux valeurs concurrentes d'un même temps de réception.

Exemple 002612/Avène : fournisseur retenu FIA **35 jours**, réception MRP **9 jours**, sécurité **20 jours ouvrés**. Dans la référence, les six nouveaux achats reçoivent des délais de livraison simulés de **24 à 70 jours** ; ce sont des tirages du moteur, pas des retards industriels mesurés. La variante FIA fixe applique 35 jours, puis la réception ; elle conserve la couverture prudente antérieure. Cela n'établit pas que l'industriel utilise cette couverture.

### BOM, tailles, prix et catalogues : correspondances et limites

Les **24 coefficients BOM** correspondent au graphe simulé et à `demand_PF.xlsx`. `Data_poc.xlsx` n'en couvre que 22 : il utilise encore 693710 à la place de 007923 pour 268091 et ne porte pas la recette 021081→773474. Ces deux écarts sont déjà résolus dans le graphe courant. Pour 1 000 PF 268091 : 1,624 kg de 001757, 1,218 kg de 001848, 2,03 kg de 002612, 3,248 kg de 007923 et 1 000 UN de 338929. Pour 1 kg de 773474 : 8,94 kg de 021081. La base 1 000 de la recette n'est pas un lot de production.

Les ratios empêchent d'attribuer automatiquement tous les besoins I aux seuls PF étudiés : dans le premier plan, 001757, 016332 et 049371 représentent chacun **15,813 millions de PF équivalents** par leur coefficient BOM, contre **178,712 millions pour 002612** et **46,728 millions pour 007923**. Les horizons renseignés diffèrent et ce sont des besoins planifiés, pas une production exécutée ; ces valeurs servent à détecter le périmètre, **pas à calculer un diviseur de stock définitif**. Même les emballages 338928/338929, tous deux à un pour un, ont des besoins différents. Les indications utilisateur sur les matières partagées restent une autre source d'information, distincte de ce diagnostic numérique. Les usages partagés et autres conditionnements doivent rester distincts du besoin explosé de nos seuls PF.

La FIA indique une **quantité standard**, sans colonne « multiple obligatoire », minimum d'achat ou maximum. Les quantités projetées fournissent des contre-exemples au multiple imposé partout. Les lots de fabrication sont des paramètres séparés : 268091 minimum 28 800 et maximum 142 485 UN dans la source récente ; avec le multiple de 14 400 retenu par le modèle, le maximum réalisé par campagne est 129 600. 773474 a un lot fixe de 3 200 kg et 693055 de 600 kg après conversion depuis G, unité retrouvée dans les autres sources.

Sur les premières versions des 24 couples avec FIA, **277 semaines ont H positif : 110 sont compatibles avec au moins un multiple de standard, 167 ne le sont pas**. Pour 338929, aucune des 23 entrées hebdomadaires initiales n'est un multiple de 5 000 UN ; pour 002612, neuf sur dix sont compatibles avec 22 500 kg, mais H189 indique 8 005,604 kg. Pour 001757, le plan initial est compatible avec des pas de 100 et de 1 000 kg ; les versions ultérieures montrent aussi 1 500 kg (`H4028`) et 500 kg (`H47027`). Cela réfute « chaque H est une commande complète au standard », pas nécessairement un standard contraignant sur chaque commande individuelle : réception partielle et agrégation doivent rester possibles.

Deux catalogues fournisseurs sont incomplets au regard du carnet : **049371/Avène** a onze lignes de 1 800 kg chez VD0518550B (58–68), alors que sa FIA donne VD0520132A, standard 1 600 kg et 147 jours ; **734545/Gien** a 6 400 UN chez VD0525906A (ligne 104), alors que sa FIA donne VD1095770A, standard 6 300 UN et 21 jours. Le carnet peut représenter des conditions antérieures ou d'autres fournisseurs ; leurs prix/délais non renseignés ne sont pas déduits du fournisseur FIA. D'autres lignes concernent la division 1820 hors périmètre MRP fourni ; une offre Avène n'est pas automatiquement une offre au même prix pour Gien.

Les 64 rapprochements tarifaires FIA–relations de l'extraction antérieure concordent après division par la base et conversion d'unité ; leurs sources sont inchangées. Pas de facteur 1 000 sur les prix 002612/338929. Pour 021081, les prix restent en **USD/kg**, sans conversion FX implicite ; un total monétaire multidevise ne doit pas être présenté comme un coût euro validé. Un prix source nul n'est pas une preuve de matière gratuite.

### Les règles de base sont-elles réellement appliquées ?

| Règle | Constat dans la configuration de référence actuelle | Statut |
|---|---|---|
| Sécurité achats lundi–vendredi, facteur 100 % | Conversion quotidienne et facteurs 1 ; `run_first_simulation.py:11055,13781`. | Conforme à la convention, pour les paramètres retenus ; traduction ERP en cible de stock non démontrée. |
| Sécurité pour déclencher la fabrication | `--production-mrp-safety-targets` absent ; contrôleurs `:11841,12754` gardent leur cible historique. Pour 773474 au jour 0, CSV trace : sécurité convertie 28 jours mais activation 0 et cible dédiée 0. | **Sécurité chargée ne signifie pas utilisée dans tous les contrôleurs.** |
| Livraison FIA et délai jusqu'à disponibilité | Champs séparés ; `:14827–14881`. Par exemple 338929 : FIA 42, référence disponibilité 50, livraison tirée 32, disponibilité réalisée 40 jours. | Distinction correcte ; le calendrier et l'aléa fournisseur sont des conventions. |
| Couverture prudente | Erlang 4 étages et marge 1,65 écart-type (`:4654`), ajoutés par le modèle. `fia_fixe` les conserve. | Hypothèse non extraite de l'ERP ; peut augmenter l'anticipation au-delà de FIA + sécurité. |
| Disponibilité des commandes initiales | G/I conservées séparément, stock détenu crédité une fois. | Cohérent ; les dates initiales de création restent inconnues. |
| Calendrier de réception | Nouveaux achats : lundi–vendredi sans fériés. | **La piste 99/104 montre une amélioration à tester**, séparément de la sécurité. |
| Standards et regroupement | Arrondi standard par défaut ; exceptions 338929/333362 ; `procurement_batching` non activé dans le graphe courant. | **Pas encore de règle commune de regroupement validée partout.** |
| Fournisseurs multiples | Politique principal/secours propre à 001848 ; ailleurs classement historique transport/délai et parts prédéfinies. | Règle prix/urgence générale non établie ; catalogues partiels pour deux autres matières. |
| Horizon | 364 jours glissants, dernière version connue à la décision ; pas d'injection de prévision future. | Implémenté ; queues absentes dans les sources et années ultérieures non calibrées. |
| BOM et quantités physiques | 24 coefficients et unités rapprochés ; UN physiques entières. | Cohérent sur le périmètre renseigné ; ne prouve pas tous les usages industriels. |
| Fabrication 693055 | Approvisionnement amont agrégé 600 kg, délai 28 jours issu de E, capacité inconnue. | Convention de frontière, **pas fabrication physique complètement reconstruite**. |

Trois paramètres récents sont bien appliqués au graphe daté : sécurité 426331 = 10 jours, sécurité 268967/DC = 60 jours, minimum 268091 = 28 800. **268091/DC reste à 20 jours alors que la source récente indique 00** : l'étude a interprété l'instruction antérieure « pas d'essai à zéro » comme maintien du nominal (`mrp_rules_integration_20260928/study.py:77–81`). Cette interprétation antérieure doit être distinguée d'une confirmation métier spécifique du 20 ; aucune nouvelle modification n'est faite dans cet audit. Le registre séparé `simulation/lot_policy/engine_adapter.py:59` conserve par ailleurs le minimum historique 14 400, alors que le contrôleur de campagne utilise 28 800 : rapprochement des registres nécessaire.

### Suite prioritaire, selon les preuves

1. Tester **le même calendrier de réception** sur tous les couples, avec les fériés candidats et sans inventer les neuf jours de fermeture résiduels. Conserver les dates G/I explicites du carnet et la sécurité nominale.
2. Réconcilier **stock physique total / stock MRP détenu / stock disponible** et la version commune du 2 mars, avant de modifier les règles de consommation pour compenser ces écarts.
3. Traiter les **paramètres chargés mais non utilisés par la fabrication**, le conflit 268091/DC et les deux registres de minimum de fabrication ; chaque essai reste séparé de la référence.
4. Croiser **fournisseur, standard, prix, engagements et reports** pour reconstruire une règle commune de proposition. Les 52 versions révisées ne doivent pas devenir 52 historiques d'exécution ; les deux fournisseurs absents de FIA restent signalés.
5. Reprendre les essais transférables avec trois jugements distincts : H/I/K planifiés, évolution des stocks physiques 2025 et service PF. Une amélioration de quelques stocks ne suffit pas à accepter une règle si elle détériore le service ou d'autres articles.

## Registre courant des règles communes — 30 septembre 2026

**Point d'entrée pour la suite.** Une règle commune signifie un même calcul utilisant les paramètres du couple article/site/fournisseur et l'état des ordres. Elle ne signifie pas une même quantité ou un même nombre de jours pour tous les articles. Aucune règle différente selon le mois ou selon le morceau de courbe à reproduire n'est admise sans donnée métier correspondante.

Les statuts ci-dessous ont un sens précis : **confirmé** par les données ou l'utilisateur ; **convention du moteur** vérifiée dans le code mais non démontrée comme règle ERP ; **candidat** soumis à comparaison ; **réfuté comme règle universelle** lorsqu'un contre-exemple l'empêche de s'appliquer partout. Les sections historiques suivantes restent conservées pour comprendre les essais et leurs limites.

| Identifiant | Règle commune, en termes métier | Statut et portée | Dans le moteur |
|---|---|---|---|
| MRP-01 | Recalculer à partir de la dernière prévision connue à la date de décision ; ne jamais additionner plusieurs versions comme des besoins exécutés. | Confirmé : 52 versions de plans, distinctes de leur horizon futur. | `ExternalComponentDemandCalendar`, sélection datée des prévisions. |
| MRP-02 | Compter le stock existant une seule fois et respecter sa date de disponibilité. Un stock en qualité n'est pas une future livraison fournisseur. | Confirmé par rapprochement J/photos et confirmation utilisateur. | Stock disponible, `FirmReceipt(state="held")`, registre de disponibilité initiale. |
| MRP-03 | Déduire les quantités déjà engagées avant de proposer un achat supplémentaire ; distinguer reliquat et quantité déjà reçue. | Le rapprochement H/J étaye les réceptions partielles. La conservation de tout engagement même tardif est une convention du moteur, pas une règle ERP entièrement identifiée. | `plan_dated_requirements`, engagements identifiés et allocations tardives exposées. |
| MRP-04 | Une proposition future non lancée peut être recalculée ; une commande engagée n'est pas annulée au seul motif que la prévision change. | Distinction étayée par les révisions. La frontière exacte entre proposition et engagement n'est pas fournie par H. | Propositions révocables jusqu'au lancement ; carnet engagé conservé. Le préfixe FIA du banc reste seulement supposé engagé. |
| MRP-05 | Protéger les besoins futurs datés, sans transformer cette protection en consommation supplémentaire. | Candidat : couvertures 7/7/6/3 semaines étudiées pour 001757/001848/002612/338929. L'opérateur est commun ; sa conversion depuis les durées industrielles reste à établir. | Primitive générique `plan_with_stock_protection` déjà présente. Son activation dans la simulation complète reste limitée et ne doit pas être confondue avec le banc de comparaison. |
| MRP-06 | Regrouper les besoins encore découverts, puis réutiliser le surplus d'arrondi pour les besoins suivants. | Convention explicite ; fenêtre ancrée au premier besoin non couvert. Une fréquence fixe de commande n'est pas déduite de la seule fréquence hebdomadaire de l'export. | `grouping_days`, `ProcurementGroup`, allocation du surplus une fois. |
| MRP-07 | Distinguer quantité standard de référence, minimum, multiple obligatoire, maximum par ordre et contrainte physique de conditionnement. | Les lots fixes de fabrication sont confirmés par la feuille dédiée. La FIA ne prouve pas à elle seule un multiple obligatoire pour chaque entrée hebdomadaire H. | `LotSizing` et arrondi d'exécution `mrp_purchase_order_quantity` ; vérifier les deux niveaux avant de modifier une proposition. |
| MRP-08 | Choisir le fournisseur et dimensionner le secours en tenant compte du manque avant disponibilité du principal. | Principal moins cher/secours plus rapide confirmé pour 001848 uniquement. Pour 002612, les standards 22 500 et 23 750 kg ne suffisent pas à identifier automatiquement le fournisseur choisi. | `plan_sourced_requirements` ; ne pas généraliser une identité fournisseur ou une règle tarifaire sans preuve. |
| MRP-09 | Garder l'horizon prévisionnel après la fin de la période de résultats affichée. | Horizon source jusqu'à 364 jours futurs. Une dernière ligne plus proche n'est pas une preuve de demande nulle ensuite. | `mrp_planning_horizon_days: 364` ; distinguer horizon de décision et durée d'exécution. |
| MRP-10 | Appliquer les jours de sécurité sur lundi–vendredi et conserver intégralement les jours source du dépôt. | Confirmé par l'utilisateur. Le calendrier des autres durées et des fermetures reste à documenter. | Conventions de sécurité conservées ; aucun essai de sécurité à zéro adopté. |
| MRP-11 | Ajuster systématiquement le dernier achat pour terminer à stock nul. | **Réfuté comme règle universelle.** Des soldes finaux positifs, voire négatifs, existent dans les sources. Une fermeture arithmétique du bilan ne prouve pas les bonnes quantités aux bonnes dates. | Aucun plafonnement terminal universel ajouté au nominal. |
| MRP-12 | Respecter les dates possibles de réception ; ne pas confondre réception physique, disponibilité qualité et semaine d'affichage. | Livraison/disponibilité distinctes confirmées. Une anticipation avant fermeture est une piste ; un jour férié ne démontre pas une fermeture industrielle de toute la semaine. | Dates distinctes ; calendrier de réception supplémentaire à qualifier séparément. |
| MRP-13 | Comparer le plan aux délais prévisionnels fournisseurs, puis étudier séparément les aléas de livraison. | Paramètres FIA connus ; distributions des retards industriels non identifiées par ces fichiers. Jours FIA conservés comme calendaires par convention. | `--supplier-delivery-mode source` pour les nouveaux achats externes datés ; mode aléatoire conservé pour les études qui le demandent. |

### Comment une règle passe de l'hypothèse au moteur

Chaque essai doit préciser les cellules sources, l'unité, les dates de décision et d'échéance, les données reprises comme engagements et les semaines absentes. Il compare au minimum les réceptions positives exactes **à la même date et pour la même quantité**, l'erreur de quantité, le solde projeté et la première divergence. Les semaines où les deux calculs donnent zéro ne doivent pas masquer des commandes mal reproduites.

Le banc à entrées identiques utilise les besoins I, le stock J daté et les engagements initiaux supposés. Les H/K ultérieurs ne servent qu'à évaluer le résultat. Il est distinct de la simulation physique, dont les besoins résultent aussi des productions, consommations des articles partagés, disponibilités et transports.

Une intégration doit conserver les sécurités source, les UN physiques entières, les engagements existants et les deux suivis de lots. Elle doit également vérifier que l'exécution ne réarrondit pas une quantité différemment du plan. La réussite du banc n'autorise pas à déclarer la simulation annuelle calibrée : cette dernière exige sa propre comparaison et qualification.

La passe courante et ses preuves sont conservées sous `etudecas/artifacts/testing/mrp_common_policy_20260930`. Le point de reprise précédent est reproductible avec `etudecas/config/mrp_reconstruction_20260930/reproduce.py`.

### Processus itératif : apprendre sur un article, transférer la règle sans retouche

Le protocole du 30 septembre 2026 ajoute une étape obligatoire avant toute nouvelle intégration : **classer plusieurs règles sur un seul article, puis conserver exactement leur formule pour les autres articles**. Une règle commune utilise les paramètres industriels de chaque article ; elle ne choisit pas un nombre de semaines ou un arrondi différent pour mieux suivre chaque courbe. Le [protocole figé](../../artifacts/testing/mrp_rule_transfer_20260930/protocol.json) contient les candidats, les critères et l'ordre de transfert avant l'exécution.

Le premier article est **338929 à Avène**, mono-fournisseur, sur les échéances janvier–juin du plan du 5 janvier. Le transfert porte d'abord sur **001757**, également mono-fournisseur, puis sur **001848 et 002612**, dont le multisourcing ajoute une difficulté distincte. Le plan du 6 juillet teste ensuite juillet–décembre pour les quatre articles. Les 52 versions servent uniquement à vérifier la stabilité : elles ne représentent pas 52 historiques de commandes indépendants. Ces sources ayant déjà été examinées, il s'agit d'une validation rétrospective à paramètres gelés, pas d'un test aveugle.

Sept candidats sont définis. `S` désigne les jours ouvrés de sécurité source, `R` les jours de réception source et `Q` la quantité standard du fournisseur. Le calendrier ouvré de `R` reste une hypothèse, contrairement à celui de `S`. Le fournisseur est l'unique offre ou, à titre de convention commune pour ce banc, l'offre au prix unitaire comparable le plus bas ; les quantités H ne servent jamais à choisir rétrospectivement le fournisseur.

| Candidat | Mécanisme | Quantité proposée |
|---|---|---|
| A | Couvrir les besoins futurs sur `S/5` semaines, arrondi supérieur | Multiple supérieur de `Q` |
| B | Couvrir sur `(S+R)/5` semaines, arrondi supérieur | Multiple supérieur de `Q` |
| C | Couvrir sur `(S+R)/5` semaines, arrondi au plus proche | Multiple supérieur de `Q` |
| D | Même couverture que C | Minimum `Q`, sans multiple imposé |
| E | Même couverture que C | Besoin net, standard seulement indicatif |
| F | Regrouper les besoins encore découverts dans la fenêtre C, à partir du premier manque | Multiple supérieur de `Q` |
| G | Même regroupement que F | Besoin net, standard seulement indicatif |

La formule arrondie de C/E retrouve certains nombres de semaines étudiés auparavant ; cette origine rétrospective est déclarée. F/G isolent le regroupement sans ajouter un plancher de sécurité : ce sont des comparateurs de mécanisme, pas une suppression des sécurités du nominal. Les quantités physiques UN restent entières, y compris lorsque le standard est indicatif. Aucun arrondi au millier n'est introduit spécialement pour 001757.

Les sept candidats utilisent **les mêmes semaines comparables** sur chaque plan. Les H supposés engagés avant le délai fournisseur sont imposés identiquement et exclus des scores ; leur influence sur le stock restant est explicitement reconnue. J est compté une seule fois à sa date. Après ce préfixe, H et K servent uniquement à évaluer les résultats. Les semaines absentes, les fenêtres tronquées et les propositions hors semaine renseignée restent distinguées ; le sous-ensemble sans trou futur n'efface pas l'effet d'éventuels trous antérieurs.

Le classement utilise seulement l'erreur de réceptions de 338929 au premier semestre, puis l'erreur de stock projeté pour départager les candidats. Les règles sont ensuite transférées dans cet ordre sans ajustement. Une réception n'est exacte que si **semaine et quantité** concordent ; les achats manqués, supplémentaires et de mauvaise quantité sont comptés séparément. K reste un stock **projeté**, distinct des photos d'inventaire physique. Un contre-exemple suffit à rejeter l'affirmation de règle commune exacte ; un candidat partiel conserve ses réussites et ses échecs. Moins de trois réceptions positives comparables ne suffisent pas à soutenir une généralisation.

Une nouvelle idée après échec devra être formulée dans une nouvelle version du protocole et rejouée sur tous les articles. Une exception n'est admissible que si elle correspond à une condition métier issue des sources, telle qu'un véritable minimum contractuel ou un état d'engagement, et non au code article ou à une période qui améliore le score. La simulation physique sur cinq ans intervient après ce filtrage, lorsqu'une modification du moteur est effectivement proposée ; le banc seul ne qualifie ni le service client ni les stocks physiques.

**Premier cycle exécuté : sept candidats sur 208 plans, soit 1 456 calculs de planification.** Les résultats sont dans le [tableau CSV](../../artifacts/testing/mrp_rule_transfer_20260930/scores.csv) et la [matrice détaillée avec contre-exemples](../../artifacts/testing/mrp_rule_transfer_20260930/results.json). Les 208 plans sont les quatre articles et leurs 52 versions ; ils ne constituent pas 208 observations industrielles indépendantes. Le programme appelle les fonctions existantes du moteur et ne simule pas d'exécution physique.

Le classement sur le seul apprentissage 338929 est **D/E ex æquo, puis C, B, A, G, F**. D et E donnent exactement les mêmes H/K sur ses semaines scorées : on ne peut donc pas déduire de cet article seul si le standard doit être un minimum. Leurs 11 réceptions positives exactes sur 13 ne suffisent pas non plus à expliquer tous les volumes : leur erreur absolue totale de réceptions représente encore 31,1 % du volume source de la fenêtre.

Réceptions positives retrouvées **à la même semaine et pour la même quantité**, avec les paramètres gelés et les mêmes semaines comparables pour tous les candidats :

| Article à Avène | D : standard minimum, H1 | D, H2 | E : standard indicatif, H1 | E, H2 |
|---|---:|---:|---:|---:|
| 338929, apprentissage H1 | 11/13 | 10/11 | 11/13 | 10/11 |
| 001757, transfert mono-fournisseur | 0/6 | 0/6 | 0/6 | 0/6 |
| 001848, transfert multi-fournisseur | 0/1 | 0/1 | 0/1 | 0/1 |
| 002612, transfert multi-fournisseur | 7/7 | 1/9 | 0/7 | 0/9 |

Le transfert départage donc des mécanismes indiscernables à l'apprentissage : D retrouve toutes les réceptions comparables et K de 002612 en H1, E ne les retrouve pas. Mais D échoue en H2 et sur 001757. Les sept candidats sont écartés **comme explications exactes communes dans les conditions du banc**, sans remplacement du nominal. Les correspondances partielles restent documentées ; aucun paramètre propre à un article n'est ajusté pour sauver le résultat.

Le résultat **7/7 de 002612 en H1** subsiste sur ses **19 semaines sans trou dans la fenêtre future ni dans l'historique**. À l'inverse, pour 338929 en H1, le sous-ensemble aussi strict retrouve huit réceptions sur neuf : même en retirant l'ambiguïté des semaines manquantes, il reste un contre-exemple à la règle proposée.

Trois contre-exemples localisent le prochain travail. Pour **001757**, le 6 avril, D/E proposent 780,328 kg et C arrondit à 800 kg, contre 1 000 kg en `Feuille1!H14` : le standard FIA de 100 kg ne suffit pas à expliquer le regroupement. Pour **001848**, les 3 331,16 kg du 18 mai (`H101`) et les 4 000 kg du 2 novembre (`H26194`) ne sont pas reproduits par un minimum global de 6 000 kg. La seconde quantité est compatible avec le fournisseur de secours connu, mais la compatibilité de quantité ne remplace pas une identité d'ordre. Pour **338929**, D/E calculent 144 616 UN le 13 avril, contre 289 232 en `H719`, puis placent 144 616 la semaine suivante : une règle de date ou de regroupement reste à expliquer. Ajouter un facteur constant à toutes les quantités ne corrigerait pas ces mécanismes différents.

Les limites du jeu de données comptent dans le verdict. En H2 de 002612, le premier écart K du 17 août inclut déjà une proposition de 22 500 kg dans une semaine antérieure absente : ce n'est pas, à lui seul, une réception source explicitement contradictoire. Pour 001757, aucune semaine H2 ne garde une fenêtre future entièrement renseignée ; pour 001757 et 001848, les périodes principales ont toutes des trous antérieurs. Les scores principaux reposent donc sur l'hypothèse déclarée de zéros internes. Les sous-scores stricts sont fournis et ne sont pas remplacés par des zéros quand ils sont vides. Ces limites empêchent de confondre rejet d'une reconstruction exacte et preuve exhaustive du fonctionnement de l'ERP.

La prochaine itération devra séparer **protection des besoins**, **politique réelle de lot de commande** et **sélection fournisseur selon l'état du besoin et des engagements**. Elle devra garder les cas qui concordent et expliquer les contre-exemples ci-dessus avec des conditions métier vérifiables. Il n'est pas justifié à ce stade d'imposer partout un minimum, un multiple du standard, un multiplicateur dix, ni une période de fermeture supposée. Les anciens candidats « stock final systématiquement nul » et « toute semaine fériée fermée » restent rejetés comme règles universelles.

Reproduction : `python -B etudecas/artifacts/testing/mrp_rule_transfer_20260930/study.py --protocol CHEMIN_PROTOCOLE --output DOSSIER_NEUF_SOUS_ARTIFACTS_TESTING`. Le [script unique](../../artifacts/testing/mrp_rule_transfer_20260930/study.py) refuse d'écraser ses résultats ; les candidats restent explicites et les formules nouvelles exigent une implémentation relue. Le protocole et les entrées sont empreintés. Ce cycle n'ajoute aucun fichier au moteur et ne régénère aucune carte.

**Vérification de ce cycle.** Les huit tests ciblés en mémoire des fonctions de couverture et regroupement passent, ainsi que le [contrôle de leurs preuves natives](../../artifacts/testing/mrp_rule_transfer_20260930/native/gate-2d9b74cff7ee4e4992500517b1149570/manifest.json). Un agent distinct a relu directement les quatre classeurs utiles et recalculé les paramètres, les semaines comparables, les scores, les ex æquo et les verdicts. Son [oracle indépendant](../../artifacts/testing/mrp_rule_transfer_20260930/validation/transfer_check.json) n'importe ni les fonctions du moteur ni celles du banc : il reproduit les sept trajectoires sur chacun des 208 plans par une récurrence arithmétique distincte. Les 333 381 rapprochements ne comportent aucun échec ; ils vérifient le calcul livré, pas l'identification de l'ERP. Le [manifeste de ce cycle](../../artifacts/testing/mrp_rule_transfer_20260930/manifest.json) regroupe les empreintes, les preuves et la décision de ne pas intégrer ces candidats comme règle commune exacte.

### Comparaison avec les fonctions réellement utilisées par le simulateur

La [carte des règles communes](../../resultats/regroupement_001757_20260929/carte_regles_communes.html) ajoute un panneau indépendant à la carte de regroupement de référence. Il propose quatre articles, leurs 52 versions et trois calculs : besoins datés seuls, couverture datée, hypothèse calendaire. Les autres onglets et les deux suivis de lots restent ceux de la référence historique. Le candidat calendrier utilise un calcul analytique séparé ; les deux autres variantes appellent les fonctions existantes du moteur.

Le script `compare_engine.py` appelle directement `plan_dated_requirements` et `plan_with_stock_protection`. Sur les 208 plans, ce second helper retrouve les propositions du replay analytique précédent, à la tolérance numérique près. Ce raccord est nouveau ; les scores de la couverture ne constituent pas une nouvelle amélioration par rapport au replay précédent.

| Article | Réceptions positives exactes H1 : daté simple → couverture | Réceptions positives exactes H2 : daté simple → couverture |
|---|---:|---:|
| 001757 | 0/6 → 4/6 | 1/6 → 3/6 |
| 001848 | 0/1 → 0/1 | 0/1 → 0/1 |
| 002612, standard 22 500 kg | 1/7 → 7/7 | 2/9 → 1/9 |
| 338929 | 0/13 → 11/13 | 4/11 → 10/11 |

H1 = échéances janvier–juin du plan du 5 janvier ; H2 = juillet–décembre du plan du 6 juillet. Les préfixes imposés, dates sources absentes et fenêtres de couverture incomplètes sont exclus. Le calcul « daté simple » du banc n'inclut pas la réserve technique du runtime complet, son multisourcing ou l'exécution physique : il ne faut pas attribuer ces scores à la simulation nominale entière.

**Règle de protection testée :** à une date donnée, protéger la somme des besoins bruts des N semaines suivantes. Les quantités J déjà présentes sont fournies une seule fois au planificateur, comme stock disponible ou stock à libérer plus tard. Elles ne sont pas déduites une seconde fois de cette cible. L'enveloppe cumulée des besoins et de la protection déclenche les achats sans compter la protection comme une consommation.

Les paramètres 7/7/6/3 semaines et 1 000/6 000/22 500/1 comme arrondis sont des candidats documentés. La couverture datée améliore plusieurs cas par rapport au helper simple mais ne résout pas le choix fournisseur de 002612 ni le traitement des dernières propositions de 001848. Son intégration générale au runtime nécessite encore de composer proprement protection, sourcing et regroupement : leurs gardes actuelles interdisent certaines combinaisons.

### Paramètres d'achat : prix, délais, standards et choix fournisseur

**Complément du 30 septembre 2026.** Le prix doit être ramené à sa base et à son unité avant toute comparaison : montant / base de prix, puis conversion d'unité si nécessaire. La devise reste explicite. Une quantité standard d'achat n'est ni une quantité minimale démontrée, ni une palette, ni un maximum de fabrication. La FIA identifie l'article et le fournisseur ; elle ne fournit pas à elle seule le site destinataire.

L'inventaire couvre **12 classeurs, 35 feuilles et 35 lignes FIA**, dont 33 offres externes et deux approvisionnements internes, rattachés à 24 couples article/site. Les six couples multisourcing sont 001848, 001893, 002612, 007923 et 055703 à Avène, et 021081 à Gaillac. Les 64 rapprochements de prix FIA/relations concordent après normalisation de la base et de l'unité. Les quatre offres de 021081 sont cependant en **USD/kg** : 12,10 / 12,10 / 12,15 / 15,00, toutes à 120 jours et 20 000 kg de standard. Elles restent séparées des offres EUR ; aucun taux de change industriel n'est ajouté.

Dans les 72 lignes de relations recensées, les champs fréquence, priorité, limite de délai et coût de transport sont vides. Les parts fournisseurs, fréquences de regroupement et coûts transport utilisés par la simulation ne peuvent donc pas être présentés comme provenant de ces cellules. Les différences numériques entre anciennes et nouvelles politiques portent sur trois sécurités — 426331/Avène : 7→10 jours ; 268091/dépôt1920 : 20→0 ; 268967/dépôt1920 : 25→60 — et sur le minimum de fabrication de 268091 : 14 400→28 800 UN. Ce sont des divergences entre fichiers, sans date d'effet explicite ; l'audit ne remplace pas les paramètres du nominal. Les sept différences purement typographiques, comme `07` et `7`, ne sont pas classées comme conflits.

Les huit offres ci-dessous sont lues directement dans `268091.xlsx/FIA`. Le rapprochement avec les relations du graphe et le carnet concerne ici Avène ; les autres sites ne sont pas fusionnés.

| Article | Fournisseur | Prix d'achat normalisé | Délai livraison prévisionnel source, jours | Quantité standard source | Ligne FIA |
|---|---|---:|---:|---:|---:|
| 001757 | VD0951020A | 5,43 EUR/kg | 84 | 100 kg | 2 |
| 001848 | VD0519670A | 4,20 EUR/kg | 21 | 4 000 kg | 3 |
| 001848 | VD0951020A | 1,58 EUR/kg | 56 | 6 000 kg | 4 |
| 002612 | VD0500655A | 1,34 EUR/kg | 28 | 21 600 kg | 8 |
| 002612 | VD0910216A | 0,82 EUR/kg | 35 | 22 500 kg | 9 |
| 002612 | VD0990780A | 1,295 EUR/kg | 35 | 23 750 kg | 10 |
| 002612 | VD1091642A | 1,225 EUR/kg | 35 | 22 500 kg | 11 |
| 338929, étui | VD0914360C | 0,21585 EUR/UN | 42 | 5 000 UN | 20 |

Cellules : A = article, B = fournisseur, C = montant, D = base de prix, E = devise, F = délai, G = quantité standard, H = unité. Ainsi `C9/D9 = 820/1 000 = 0,82 EUR/kg` pour 002612 ; `C20/D20 = 215,85/1 000 = 0,21585 EUR/UN` pour l'étui. Aucun facteur 1 000 erroné n'est constaté sur ces prix dans le graphe de référence examiné. Le calendrier du délai fournisseur n'est pas précisé dans la FIA ; son interprétation en jours calendaires dans le moteur reste une convention distincte des jours de sécurité confirmés.

**001757 : distinguer la source de l'hypothèse de regroupement.** La FIA donne 100 kg. Les 1 000 kg utilisés dans le banc de reconstruction sont un arrondi candidat issu des flux MRP, pas une correction de cette cellule source. Retrouver des entrées hebdomadaires de 1 000 kg ne prouve pas que chaque commande individuelle impose ce minimum.

**002612 : quatre offres, pas seulement deux.** Deux fournisseurs ont le même standard de 22 500 kg. Les deux commandes initiales d'Avène sont explicitement affectées à VD0910216A, le moins cher (`Extract_En_cours.xlsx/Sheet1!D14:D15`). En revanche, les H futurs ne portent pas le fournisseur. Dans les 52 versions, 365 cellules H valent exactement 22 500 kg et 113 valent 23 750 kg ; ces dernières apparaissent dans 49 versions, dès le plan du 19 janvier pour le 23 février (`Feuille1!H2136`). **Ce sont des occurrences dans des projections alternatives, pas 478 commandes exécutées.** Elles contredisent le standard unique de 22 500 kg imposé partout, mais ne prouvent pas à elles seules un changement de fournisseur.

**Délai fournisseur, livraison et disponibilité restent trois informations distinctes.** Sur les sept commandes initiales d'Avène concernant ces quatre articles, les sept quantités correspondent à H dans la semaine de livraison G ; une seule correspond dans la semaine de disponibilité I. Les treize commandes sélectionnées, autres sites compris, ont un intervalle G→I compatible avec le nombre de jours lundi–vendredi indiqué dans leur carnet. Cela ne démontre pas le calendrier de tous les autres ordres : voir la section 18 pour l'analyse incluant les jours fériés.

Des paramètres diffèrent déjà entre sources : réception de 002612/Avène = 8 jours dans `Extract_En_cours!H14:H15`, contre 9 dans Flow MRP ; 338929/Avène = 4 jours en `H101`, contre 6 ; 001848/Gien = 14 jours en `H7`, contre 26. La date de validité d'un changement de paramètre n'est pas fournie. Il faut conserver les dates explicites des engagements initiaux et documenter le paramètre utilisé pour les nouvelles propositions, sans réécrire rétroactivement le carnet.

### Ce que la référence simulée applique effectivement

L'examen porte sur le témoin historique `mrp_policy_20260929/study/reference_figee`, pas sur une nouvelle simulation. Le CSV `data/mrp_orders_daily.csv` est filtré sur les nouveaux achats fournisseurs destinés à Avène, lancés aux jours 0 à 364 ; les ordres d'ouverture sont exclus. Chaque ligne retenue possède un identifiant MRP distinct. Une commande lancée en 2025 peut être livrée en 2026. Ces nombres d'ordres ne se comparent pas directement au nombre de cellules H, qui agrègent les réceptions prévues par semaine.

| Article | Nouveaux ordres lancés | Quantité commandée | Fournisseurs effectivement utilisés |
|---|---:|---:|---|
| 001757 | 147 | 34 700 kg | VD0951020A |
| 001848 | 4 | 22 000 kg | VD0951020A : 3 × 6 000 kg ; VD0519670A : 1 × 4 000 kg |
| 002612 | 6 | 135 000 kg | VD0910216A : 6 × 22 500 kg |
| 338929 | 30 | 2 151 600 UN | VD0914360C |

Pour 002612, le paramétrage multisourcing historique est `legacy`, avec des parts 70/20/5/5 triées selon le coût de transport puis le délai et l'identifiant. Ce n'est pas une politique industrielle démontrée. **Les parts configurées ne sont pas les parts réalisées** : dans ce témoin, arrondis et traitement successif des besoins conduisent aux six achats ci-dessus chez le seul fournisseur à 0,82 EUR/kg. Le choix principal/secours confirmé de 001848 s'applique séparément ; son CSV conserve pourtant `mrp_share=0.3` au principal et `0.7` au secours, champs hérités qui ne représentent pas leurs parts effectivement commandées.

Les délais sont également différents selon ce que l'on mesure. Le témoin utilise des délais aléatoires Erlang : pour les six commandes de 002612, le délai fournisseur source de 35 jours donne des délais tirés de **24, 27, 31, 43, 60 et 70 jours**. Pour 001757, la référence est 84 jours, mais les tirages des 147 ordres vont de 6 à 168 jours. Ces tirages sont des conventions du simulateur, pas des délais industriels mesurés dans les Excel. La recherche de la règle MRP doit comparer d'abord des plans aux mêmes besoins et délais prévisionnels ; les aléas d'exécution se vérifient séparément.

Le standard de 5 000 UN de 338929 est conservé comme donnée source mais explicitement non contraignant dans ce témoin. Cela explique que les achats simulés ne soient pas tous des multiples de 5 000. La source fournit un contre-exemple concret au multiple obligatoire : `Extract_En_cours.xlsx/Sheet1!E101` porte **57 600 UN**, chez le fournisseur identifié VD0914360C (`D101`), alors que 57 600 n'est pas divisible par 5 000. Cette convention est distincte des quantités physiques UN, qui doivent rester entières.

**Points techniques identifiés, sans correction silencieuse pendant l'audit.** L'import FIA (`knowledge_graph/update_supply_graph_from_case_data.py`, `update_edge_from_fia`) met à jour le nom de feuille mais conserve parfois un ancien numéro de ligne : le graphe témoin cite la ligne 8 pour 001757 alors que la FIA le contient en ligne 2. La préparation (`simulation_prep/prepare_simulation_graph.py`) peut aussi réécrire les prix depuis les relations `Data_poc`/`demand_PF`, sans arbitrage explicite de validité ; les quatre prix examinés restent cependant corrects. Enfin, les achats génériques ne contrôlent pas la devise comme le fait la politique spécifique de 001848. Un prix USD ne doit donc pas être comparé ou additionné à un prix EUR sans conversion documentée. Ces constats nécessitent un traitement séparé de la provenance et des conventions économiques ; ils ne prouvent pas une erreur de prix sur les quatre références ci-dessus.

**Suite de l'identification :** confronter pour chaque fournisseur le prix d'achat normalisé, le délai jusqu'à livraison, le temps jusqu'à disponibilité, les engagements existants et le caractère réellement contraignant du standard. Traiter les signatures de quantités comme des indices, pas comme des identifiants fournisseur. Pour 002612, expliquer les 23 750 kg projetés et leurs révisions sans inventer un basculement saisonnier ; pour 001757, expliquer le regroupement des besoins au-delà du standard de 100 kg. Aucun paramètre source ni règle du nominal n'est modifié par cet audit.

Preuves de cette passe : [inventaire des offres](../../artifacts/testing/mrp_purchase_parameters_20260930/extraction/purchase_offers.csv), [contre-vérification des quatre articles](../../artifacts/testing/mrp_purchase_parameters_20260930/validation/purchase_source_check.json), [rapprochement des dates du carnet](../../artifacts/testing/mrp_purchase_parameters_20260930/validation/initial_receipts_check.json), [achats effectivement simulés](../../artifacts/testing/mrp_purchase_parameters_20260930/runtime_purchase_check.json). Le manifeste de livraison regroupe les empreintes et les limites de ces contrôles ; il ne certifie pas l'identification complète du système industriel.

### Intégration du délai fournisseur source : comparaison contrôlée

Le mode `--supplier-delivery-mode source` applique à chaque nouvel achat externe agrégé du MRP daté le délai FIA explicite de sa liaison. Il refuse un délai absent, par défaut ou non entier, plutôt que de l'appeler « donnée source ». Il n'effectue pas de tirage aléatoire pour cette livraison. Les contraintes et incidents explicitement activés restent applicables ; le scénario de comparaison est BASE.

Ce mode conserve les dates G/I des engagements initiaux, les jours de sécurité, la couverture prudente existante, les transferts internes et la frontière de production 693055. Le délai de réception E s'applique toujours après la livraison. Son calendrier lundi–vendredi sans jours fériés reste une convention candidate, distincte des jours de sécurité confirmés. Ainsi, une commande au 1er janvier avec 35 jours FIA est livrée au 5 février ; avec neuf jours lundi–vendredi de réception, elle devient disponible au 18 février.

Le défaut `sampled` permet de reproduire les anciens calculs. L'option globale existante `--no-stochastic-lead-times` fixe aussi les autres délais et change les couvertures prudentes. Pour une liaison Erlang à quatre étapes de moyenne 35 jours, la couverture prudente existante est de 64 jours ; le mode fournisseur `source` ne la supprime pas. Cette différence justifie les trois variantes séparées de la recette `etudecas/artifacts/testing/mrp_delivery_rules_20260930/study.py` : témoin, livraison fournisseur seule fixe, puis délais fixes globaux.

Les constats d'audit suivants ont également été corrigés : les imports FIA conservent désormais leur véritable ligne Excel, et les exports de sourcing explicite affichent une part historique non applicable comme vide avec son motif, au lieu de faire croire à un quota 30/70 exécuté. Les paramètres de prix, standards et décisions physiques ne changent pas du fait de ces corrections de provenance et d'affichage. Les hypothèses de couverture, de regroupement, de calendrier industriel et de sélection fournisseur non démontrées restent séparées ; elles ne deviennent pas des règles générales par cette intégration.

La référence des délais avant correction est vérifiée dans [les six commandes 002612](../../artifacts/testing/mrp_delivery_rules_20260930/validation/deliveries_002612.json) : livraisons après 24 à 70 jours, moyenne 42,5, pour 35 jours FIA ; disponibilité après 35 à 83 jours, moyenne 55,17. Ces dates viennent de la simulation historique, pas de livraisons industrielles observées.

Les trois nouveaux calculs de **1 825 jours** sont terminés. Dans la variante fournisseur fixe, les six nouvelles commandes 002612 lancées en 2025 sont livrées après **35 jours** et disponibles après **48 jours**, une fois les neuf jours de réception lundi–vendredi écoulés. Ce résultat vérifie la convention programmée ; il ne mesure pas la ponctualité réelle du fournisseur. La source ne confirme pas encore le calendrier des jours FIA.

La [nouvelle carte des délais fournisseurs](../../resultats/regroupement_001757_20260929/carte_delais_fournisseurs.html), bouton **Comparaisons 2025**, conserve le témoin et ajoute les deux variantes. Elle ouvre 002612/Avène avec le témoin et la livraison au délai annoncé. Les autres onglets, le panneau « Règles communes MRP » et les deux suivis de lots gardent leurs résultats historiques. Leur contenu extérieur au panneau de comparaison est préservé ; ces vues ne sont pas présentées comme les résultats des trois nouveaux calculs.

Erreur absolue moyenne entre les **52 photos de stock 2025** et le stock physique simulé à la clôture de la veille, sans mélanger kg et unités :

| Article à Avène | Unité | Témoin, délais aléatoires | Livraison au délai fournisseur | Délais fixes globaux, couverture également modifiée |
|---|---|---:|---:|---:|
| 001757 | kg | 2 637 | 2 597 | 2 545 |
| 001848 | kg | 2 326 | 1 999 | 2 256 |
| 002612 | kg | 70 412 | 68 694 | 68 512 |
| 338929 | UN | 1 005 257 | 909 712 | 590 682 |

La seule fixation des livraisons améliore ces quatre erreurs de respectivement **1,5 %, 14,1 %, 2,4 % et 9,5 %**. Cela ne suffit pas à retrouver les stocks industriels : pour 002612, la moyenne simulée reste proche de 41 009 kg contre 105 740 kg dans les photos ; pour 338929, elle reste à 1 359 243 UN contre 521 515 UN. Pour 001848, l'erreur absolue baisse, mais le biais moyen devient plus négatif. L'effet d'une correction se juge donc sur la trajectoire, les volumes et le niveau moyen, pas sur un indicateur seul. La variante globale améliore davantage 338929 tout en étant moins bonne que la variante fournisseur seule sur 001848 ; elle n'est pas adoptée comme règle industrielle universelle.

Sur l'ensemble des **29 couples comparables** du panneau, la variante fournisseur seule réduit l'erreur dans **16 cas**, l'augmente dans **huit** et la conserve dans **cinq** ; quatre autres couples n'ont pas de métrique comparable. Ce comptage vient des métriques exportées, dont le contre-calcul direct Excel/CSV de cette étape porte sur les quatre articles du tableau. La variante globale réduit 17 erreurs, en augmente onze et en conserve une. Les couples n'ont pas tous le même nombre de photos ni le même périmètre représenté ; ce bilan n'est pas un score industriel global.

Les temps de calcul mesurés sont **857,4 s**, **857,9 s** et **930,8 s**, respectivement. Des exécutions indépendantes ont tourné en parallèle : ces durées ne sont pas un benchmark de performance. Les années sans nouvelles versions industrielles des prévisions prolongent les conventions du modèle ; la comparaison aux sources porte uniquement sur 2025.

Le contrôle du service client interdit également de conclure à une amélioration générale : pour 268091 en 2025, le volume servi passe de **3 528 253 UN** dans le témoin à **3 499 453 UN** avec la livraison fournisseur fixe, soit **28 800 UN de moins** ; les jours avec au moins une unité de reliquat passent de sept à neuf. La variante globale sert 3 125 053 UN et compte 35 jours avec reliquat. La demande physique est identique. Les délais annoncés sont utiles pour isoler les hypothèses du MRP, mais la variante n'est pas adoptée comme nouveau nominal sur la seule amélioration des écarts de stock.

Le déficit de 28 800 UN apparaît dans le service des **26–28 décembre**. Le 30 novembre (J333), le témoin fabrique un lot supplémentaire de 28 800 UN, tandis que la variante fournisseur fixe ne le fabrique pas : le registre signale une contrainte sur **693055**, avec une capacité de fabrication non limitante. Le témoin reçoit ce jour-là 50 kg de 693055, puis consomme 11,6928 kg pour ce lot ; la variante n'a pas cette réception au même jour. Ce rapprochement établit la chaîne locale matière–fabrication–service. Il ne permet pas d'attribuer directement ce manque aux 35 jours de 002612 : les trajectoires et les autres aléas peuvent diverger après modification des décisions. Le [diagnostic daté](../../artifacts/testing/mrp_delivery_rules_20260930/validation/service_268091_timing.json) conserve les lignes CSV et les huit contrôles correspondants.

Les **26 cas de tests ciblés** et les **trois qualifications CSV** passent. L'[oracle indépendant](../../artifacts/testing/mrp_delivery_rules_20260930/validation/runs_check.json) réalise **770 459 contrôles** : dates de livraison/disponibilité, identité des lots, carnet initial conservé, demande PF identique sur cinq ans, quantités UN entières et conservation des couvertures entre témoin et variante fournisseur seule. Il recalcule directement depuis les Excel et CSV les douze erreurs de stock du tableau, puis les rapproche du contenu de la carte. Ces contrôles valident les conventions programmées, pas l'identification complète du MRP industriel.

Le [parcours navigateur natif](../../artifacts/testing/mrp_delivery_rules_20260930/browser/native/browser-f4bbbd1d9df64c21b9d96336de1d5377/manifest.json) et le [regroupement des preuves natives](../../artifacts/testing/mrp_delivery_rules_20260930/validation/native/gate-82be5a235d8d4798853c7c766642d5f4/manifest.json) passent. La revue supplémentaire reste **partielle** : le parcours étendu rencontre des délais d'attente sur certains clics. Le parcours court avec clics souris visibles valide les courbes stocks/flux des deux articles et l'export de 002612, mais son sélecteur de scénarios devient ambigu pour 001848, car l'attribut `data-run` existe aussi sur des lignes de commandes. Cela limite la preuve du script ; ce n'est pas une erreur démontrée des valeurs affichées. La [preuve détaillée](../../artifacts/testing/mrp_delivery_rules_20260930/browser/review-4bb9a32d42a74c2aaf4aec2033c7b535/manifest.json) conserve cette limite, sans transformer un contrôle échoué en réussite.

La [capture 002612 examinée](../../artifacts/testing/mrp_delivery_rules_20260930/browser/review-4bb9a32d42a74c2aaf4aec2033c7b535/002612_stock_reference_delais_fixes.png) montre les courbes et légendes lisibles, les points sources distincts et les périmètres explicites. La carte reconstruit néanmoins de grandes tables, même repliées, à chaque changement de vue : c'est une limite de performance à traiter séparément. Le [manifeste de livraison](../../artifacts/testing/mrp_delivery_rules_20260930/manifest.json) distingue qualification du moteur, contrôle des résultats et couverture partielle de l'interface.

Les commandes exactes, le graphe commun et leurs empreintes sont dans le [plan de reproduction](../../artifacts/testing/mrp_delivery_rules_20260930/study/plan.json). La [recette](../../artifacts/testing/mrp_delivery_rules_20260930/study.py) applique `prepare`, puis `run --variant reference`, `run --variant fia_fixe`, `run --variant fixe_global` et `render`. Elle refuse les destinations existantes : pour une nouvelle reproduction, adapter son dossier d'étude et son nom de carte. Elle dépend des références antérieures indiquées dans le plan ; aucun résultat antérieur n'a été écrasé. Les [métriques détaillées](../../artifacts/testing/mrp_delivery_rules_20260930/comparison_metrics.json) gardent le périmètre et l'unité de chaque couple article/site.

### Deux hypothèses générales testées et non adoptées

**Plafond de fin de plan.** Ramener la dernière proposition au besoin net restant retrouve les 3 331,16 kg de 001848 au 18 mai dans le plan du 5 janvier. Sur les 52 versions, cependant, il retrouve le solde final nul mais seulement trois dernières réceptions à la bonne semaine et pour la bonne quantité. Pour 001757, il dégrade les 52 soldes finaux auparavant exacts. Le plafond n'est donc pas intégré comme règle universelle. De plus, 206 des 208 plans s'arrêtent avant la borne des 52 semaines : le dernier point exporté ne peut pas être traité sans hypothèse comme la fin des besoins connus.

**Fermeture d'une semaine contenant un jour férié.** Les jours fériés 2025/2026 sont vérifiés dans le [calendrier public métropolitain](https://calendrier.api.gouv.fr/jours-feries/metropole.json), consulté le 30 septembre 2026. La fermeture de toute la semaine reste une hypothèse, distincte de ces dates officielles. Le test anticipe les besoins sur la semaine ouverte précédente et n'altère pas les engagements du préfixe.

Pour 001757, ce candidat explique les 3 000 kg du 13 avril (`Feuille1!H15`) : avant les semaines de Pâques, du 1er mai et du 8 mai, la couverture passe de sept à dix semaines. L'erreur moyenne H1 baisse de 500 à 71,43 kg ; mais celle de H2 augmente de 500 à 666,67 kg. Le même calendrier dégrade 002612. Les sources contiennent aussi des réceptions positives pendant les semaines supposées fermées : la fermeture hebdomadaire n'est pas une règle commune identifiée.

**Contre-exemple à surveiller dans les courbes :** pour 338929/H2, le candidat calendrier retrouve le solde K sur les lignes comparées, mais place 144 631 UN au 2 novembre, une semaine absente de la source, au lieu du 9 novembre (`H26757`). Un stock projeté exact ne suffit donc pas à valider les dates de réception.

Les quantités et calendriers du nominal restent inchangés à l'issue de ces contre-épreuves. Les vérifications indépendantes figurent dans `validation/analysis_check.json`, `validation/engine_comparison_check.json` et `validation/calendar_check.json` de cette passe ; elles certifient les calculs annoncés, pas l'identification complète de l'ERP.

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
