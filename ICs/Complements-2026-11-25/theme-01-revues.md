# 01 Choisir cinq dossiers fournisseurs

Complément de veille et de calcul du 25 novembre 2026, préparé pour la supervision. Destinataire : ingénieur achats ou gestionnaire de projet. Les résultats du cahier sont des simulations documentées ; les recalculs ci-dessous ont été faits pour ce complément et ne sont attribués à aucun intervenant.

## Ce qui est déjà acquis

[Cahiers métier](../Cahiers-metier.md), lignes 7 à 11 ; [cas fournisseurs](../Cas/Revue-fournisseurs.md), sections « Comment le test a été construit » et « Ce que la revue peut en tirer », lignes 11 à 29. Les 27 résultats exploitables comprennent 13 mono-source, dont 5 cas de baisse, et 14 autres, dont 1 cas. Deux fournisseurs supplémentaires n'ont pas de résultat. Le choix des cinq délais les plus longs manque les six cas. Les neuf règles et les deux seuils de baisse sont déjà dans le CSV : il suffit de renvoyer à ces pièces pour cet acquis.

**Question à trancher.** Faut-il réserver une place aux autres fournisseurs, ou uniquement rechercher une liste qui contienne au moins un cas de baisse ? Ce sont deux objectifs différents. Le groupe d'un fournisseur doit être connu avant le tirage ; le résultat de sa perturbation sert ensuite à évaluer la règle, pas à orienter rétrospectivement ce tirage.

## Lectures métier et ouverture vers la recherche

- **Pratique de sélection.** Statistique Canada, *Probability sampling*, mise à jour du 2 septembre 2021, sections tirage simple et stratifié, [page primaire](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/prob/5214899-eng.htm). En réunion, demander d'abord la liste complète et une définition vérifiable de chaque groupe. Un quota de quatre mono-source et un autre n'accorde pas la même chance d'inclusion à tous : 4/13 contre 1/14. On ne peut pas utiliser directement la proportion de dossiers préoccupants dans cette revue pour estimer celle du portefeuille.
- **Standard et évolution.** ISO 28000:2022, publiée en mars 2022, [notice primaire](https://www.iso.org/standard/79612.html), et amendement *Climate action changes*, publié le 23 février 2024, [notice](https://www.iso.org/fr/standard/88413.html). Les notices confirment un cadre de gestion de la sécurité comprenant la supply chain et l'existence de l'amendement. Elles ne prescrivent aucun quota 4+1. Conséquence proposée : demander au responsable achats quels scénarios affectant la continuité et quelles preuves de solutions de remplacement sont retenus, puis consulter le texte applicable si l'organisation l'utilise.
- **Recherche appliquée ayant donné des résultats.** Simchi-Levi et al., *Identifying Risks and Mitigating Disruptions in the Automotive Supply Chain*, *Interfaces* 45(5), 375–390, publication en ligne le 20 octobre 2015, [éditeur et résumé primaire](https://pubsonline.informs.org/doi/abs/10.1287/inte.2015.0804). L'étude menée avec un constructeur automobile évalue d'abord l'effet opérationnel d'une rupture, puis sa probabilité. Cela justifie d'interroger stock utilisable, délai de reprise et alternatives réellement qualifiées, plutôt que de classer sur le délai nominal seul. Ce résultat publié n'est pas une validation de notre quota.

Ces sources ont été ouvertes le 25 novembre 2026. Une référence ancienne reste utile pour la méthode ; l'amendement de 2024 constitue l'évolution de standard identifiée ici.

## Essai exécuté sur les données publiques

Témoin : tirage de cinq dossiers sans remise parmi 27. Variante : tirages à l'intérieur des deux groupes, budget identique. Critère préalable : minimiser les listes ne contenant **aucun** des six cas, en conservant au moins un dossier de chaque groupe.

| Plan | Listes sans aucun cas / listes possibles | Probabilité de ne détecter aucun cas | Nombre moyen de cas détectés sur les 6 |
| --- | ---: | ---: | ---: |
| Uniforme | 20 349 / 80 730 | 25,206 % | 1,111 |
| 3 mono-source + 2 autres | 4 368 / 26 026 | 16,783 % | 1,297 |
| 4 mono-source + 1 autre | 910 / 10 010 | 9,091 % | 1,610 |
| 5 mono-source | 56 / 1 287 | 4,351 % | 1,923 |

Recalcul : `C(8,4) × C(13,1) / (C(13,4) × C(14,1)) = 910/10010`. Les cinq places toutes mono-source ont une probabilité de manquer tout plus faible, mais excluent le cas de l'autre groupe. Le plan 4+1 est le meilleur **parmi les quotas testés respectant la représentation des deux groupes**. Ses 90,909 % de listes contenant un cas ne signifient pas que 90,909 % des fournisseurs critiques sont repérés : on en trouve en moyenne 1,610 sur 6. Six cas pour cinq places empêchent de tous les examiner lors d'une seule revue.

Le script [verifier-cas.py](verifier-cas.py) recalcule les 14 lignes de tirage du CSV et vérifie la cohérence des quatre lignes de règles fixes, sans prétendre reconstruire leurs listes nominatives. Le [tableur](Calculs-revues-et-alertes.xlsx) permet de reprendre les calculs.

## Suite réaliste pour l'intervenant

Préparer une fiche d'entretien : référence concernée, autre source qualifiée et capacité, premier ordre touché, stock libéré, délai de reprise, date de preuve. Pour un nouveau test, demander une ligne par fournisseur et perturbation : identifiant anonyme, groupe fixé avant résultat, durée d'arrêt, service témoin et perturbé, définition du service, résultat manquant et motif. Évaluer aussi les non-sélectionnés. Les deux dossiers sans résultat doivent rester « inconnus » et non « sans risque ». Une liste de questions et la lecture commentée de l'étude appliquée sont ici une amorce suffisante ; aucun nouvel algorithme n'est nécessaire.
