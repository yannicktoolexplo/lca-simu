# Audit numérique de la carte — 20 septembre 2026

## Conclusion

La grande majorité des valeurs tracées sont correctement copiées ou agrégées depuis les CSV du run utilisé. Cela ne suffit pas à rendre toutes les conclusions métier justes. Des erreurs de périmètre, d'unités et de qualification subsistent : le tableau matière présente une consommation théorique comme physique ; des alertes traitent des reliquats fractionnaires ou une référence retirée comme des ruptures ; certains graphiques additionnent des unités incompatibles ; le comparatif économique appelle « total » un coût hors approvisionnements externes.

L'audit est en lecture seule : aucun moteur, donnée source, résultat ni HTML livré n'a été modifié. La carte examinée est `simulation/result/_reruns/corrected_map_20260918/maps/supply_graph_corrected_map_20260918_enquetes_20260920.html`, empreinte SHA-256 `434511736e814d149b4ce0697d08d3d5b243fda0e2fc954f1d83ab4678a2cf5a`.

**Décision : réviser l'interprétation et les alertes avant d'utiliser cette carte pour prendre des décisions industrielles.** Les résultats physiques et les résultats d'affichage ne doivent pas être confondus.

## Méthode et couverture

Le script [audit_numeric.py](../../artifacts/testing/full_audit_20260920/numeric/audit_numeric.py) décompresse directement les données du HTML exact. Il ne réimporte aucun producteur Python de la carte. Il reconstruit les valeurs à partir des CSV et de formules séparées : groupes article/site/jour, cumuls, moyennes mobiles, histogrammes, sommes hebdomadaires, ratios et comparaisons de fenêtres. Les paramètres du run proviennent du `run_manifest.json` et de son **graphe préparé d'entrée**, jamais d'une assimilation au graphe brut Excel.

Les preuves à consulter sont :

- [numeric_summary.json](../../artifacts/testing/full_audit_20260920/numeric/numeric_summary.json) : résultat du dernier contrôle et empreintes des sources ; ce fichier fait foi pour les compteurs.
- [figure_inventory.json](../../artifacts/testing/full_audit_20260920/numeric/figure_inventory.json) : 538 figures élémentaires, chacune avec chemin, titre, type, empreinte, nombre de séries et état de rapprochement.
- [series_inventory.json](../../artifacts/testing/full_audit_20260920/numeric/series_inventory.json) : 1 246 séries temporelles, soit 1 852 391 valeurs embarquées, chacune avec statut, motif, nombre de valeurs et bornes temporelles.
- [reconciliation.json](../../artifacts/testing/full_audit_20260920/numeric/reconciliation.json) : contrôle par contrôle, méthode, tolérance générale, résultat et exemples d'écarts éventuels.
- [material_table_reconciliation.json](../../artifacts/testing/full_audit_20260920/numeric/material_table_reconciliation.json) : les 24 lignes de matières comparées au journal physique.
- [business_semantics_probe.json](../../artifacts/testing/full_audit_20260920/numeric/business_semantics_probe.json) et [backlog_thresholds.json](../../artifacts/testing/full_audit_20260920/numeric/backlog_thresholds.json) : preuves des problèmes d'interprétation.

Les nombres de points ne représentent pas des observations indépendantes : certains graphiques réutilisent un même CSV et les pics d'événements ajoutent deux points nuls autour de chaque valeur. Les 538 figures ne comprennent pas les conteneurs de deux panneaux ni les deux conteneurs de l'arbre KPI ; les séries internes de l'arbre KPI sont bien inventoriées et contrôlées. Les diagrammes de lots constituent un autre périmètre, traité par leurs audits et revues navigateur.

**Résultat final : 1 981 rapprochements réussis, aucun écart numérique non expliqué dans ce périmètre.** Les 1 246 séries temporelles inventoriées ont chacune été rapprochées sur toutes leurs valeurs embarquées ; les 538 figures ont des valeurs ou champs numériques rapprochés. Les contrôles portent au total sur 1 861 608 valeurs, en incluant aussi les barres, scores scalaires, champs de Gantt et autres contrôles hors séries temporelles. Les six séries d'intensité du risque ont été recalculées depuis les événements et multiplicateurs appliqués, avec leurs poids descriptifs : ce succès ne calibre pas les risques ni leur causalité. Les champs supplémentaires, textes et sémantiques ne sont pas couverts par cette seule réussite numérique.

| Famille de figures | Nombre | Rapprochement effectué |
|---|---:|---|
| Usines et production | 55 | Stocks, besoins, cibles MRP, réceptions, production, principaux champs des Gantt |
| Stocks et flux fournisseurs | 54 | Stocks fin de jour, entrées/sorties, moyennes mobiles des cibles |
| Dépôt | 3 | Stocks, expéditions, réceptions datées |
| Modèle et détails MRP | 326 | Agrégats MRP, ordres, délais, statuts, flux hebdomadaires, histogrammes |
| Bilan du risque | 4 | Services, lancements/reports, nombre de fournisseurs/articles/flux, intensité descriptive |
| Comparatif nominal/risque | 6 | Backlog, service cumulé, reports, lancements, effets appliqués et coûts |
| Client | 3 | Demande, service, backlog, réceptions |
| Radars fournisseurs | 87 | 29 × 3 radars : scores de familles et moyennes des critères embarqués |

Les comparaisons ordinaires tolèrent `abs_tol=2e-5`, `rel_tol=1e-10` ; des arrondis monétaires du résumé justifient jusqu'à 0,10 pour les sommes de cinq ans. Les courbes de coûts journaliers arrondis utilisent 0,0002. Il s'agit de tolérances de sérialisation, pas de seuils métier de rupture.

### Ce que cette couverture ne certifie pas

- L'exactitude industrielle de chaque entrée Excel, ses unités de temps, ses coefficients de BOM, prix, capacités ou distributions de risque. Un graphique peut reproduire parfaitement une hypothèse inadaptée.
- Tous les textes et tableaux HTML préformatés, toutes les annotations, tous les seuils d'alerte et toutes les combinaisons de filtres. Les cas problématiques vérifiés ci-dessous sont précis ; le reste ne bénéficie pas d'une certification générale.
- Les estimations des 28 fournisseurs sans audit réel. Le rapprochement « critère → famille → radar » valide une opération arithmétique, pas les hypothèses proxy qui produisent ces critères.
- Les réponses originales et formules du classeur fournisseur indépendamment de son cache. Un audit source est présent pour 1 fournisseur sur 29 ; les autres restent estimés. Deux corrections de formules et des avertissements de qualité sont conservés dans le payload.
- Une validation externe des poids de criticité, de « Physics of Decision », des cascades de risques, ou du choix des 30/28 jours. Aucun intervalle de confiance expérimental n'a été établi.
- Les branches actuellement sans résultats : Monte Carlo, scan et plusieurs sensibilités sont indisponibles ou vides dans ce HTML. Cela ne signifie pas qu'elles ont été validées par l'audit de la carte active.
- La durée industrielle de chaque lot : le Gantt est une durée indicative issue de quantité/capacité, parfois un simple jalon de 0,6 jour ; ce n'est pas la date physique de disponibilité après maturation.

## Constats prioritaires

### N1 — Le tableau matière ne mesure pas la consommation physique annoncée — priorité 1

Le producteur [simulation_payload.py](../../visualization/maps/simulation_payload.py:309) calcule `ratio BOM / taille de batch × production totale`. La production totale comprend notamment les sorties d'en-cours présents à l'ouverture ; elle n'est donc pas une preuve que tous les intrants ont été débités pendant l'horizon. La substitution d'une ancienne référence et les arrondis physiques UN ne sont pas correctement représentés par cette multiplication.

| Site / matière | Tableau : consommation | Journal : `production_consume` | Écart tableau − journal |
|---|---:|---:|---:|
| M-1430 / 042342 | 429 321 261,6 UN | 429 321 288 UN | −26,4 UN |
| M-1430 / 734545 | 56 918,4 UN | 56 958 UN | −39,6 UN |
| M-1430 / 344135 | 7 114 800 UN | 7 007 000 UN | +107 800 UN |
| M-1810 / 338929 | 17 900 915 UN | 15 955 200 UN | +1 945 715 UN |
| M-1810 / 001893 | 138 087,65831 KG | 123 078,4128 KG | +15 009,24551 KG |

Sur les 24 matières, 19 consommations théoriques diffèrent du journal physique de plus de 0,001 dans leur unité. Il ne faut pas corriger le journal pour le faire correspondre au tableau : c'est la définition et la source de la colonne affichée qu'il faut corriger.

Le cas 344135 est explicable par la référence précédente `EX-344135`, consommée en transition. Le cas 338929 doit distinguer production nouvelle et sorties d'en-cours initiaux. Les fragments fractionnaires UN concernent la formule d'affichage, alors que le journal physique respecte l'intégralité.

**Correction recommandée :** afficher séparément « consommation théorique BOM » et « consommation physique enregistrée », avec l'événement de substitution, les en-cours initiaux et la règle d'arrondi comme explications. Le tableau de bilan doit utiliser le second chiffre.

### N2 — « Livré » est compté au départ, et les anomalies de bilan sont masquées — priorité 1

[simulation_payload.py](../../visualization/maps/simulation_payload.py:197) regroupe les `shipped_qty` par `day`, la date de départ, puis affecte ce total à la destination. La colonne « livré » ne correspond donc pas nécessairement à des réceptions sur la période affichée.

Exemple M-1810 / 338929 sur les cinq années sélectionnées : **17 062 600 UN affichés livrés**, contre **16 582 600 UN réellement enregistrés en `lane_receipt`**, soit 480 000 UN d'écart. Neuf des 24 matières présentent un écart entre cette colonne et les réceptions physiques sur l'horizon.

Le backend signale par ailleurs `stock balance mismatch vs BOM consumption` sur **18 matières sur 24**. Mais `aggregateMaterialRow` dans [worldmap_html_template.py](../../visualization/maps/worldmap_html_template.py:8902) remplace ce diagnostic par « actif sur la fenêtre » dès qu'il existe une consommation ou une livraison. Ce remplacement efface un signal de non-réconciliation que le backend avait identifié.

**Correction recommandée :** dater « réceptionné » avec les réceptions physiques ; garder « expédié » séparé ; exposer un bilan ouverture + réceptions − consommations − sorties/ajustements = clôture. Conserver explicitement tout écart au lieu de le remplacer par un statut d'activité.

### N3 — Les alertes de disponibilité amplifient des reliquats prévisionnels — priorité 1

Le diagnostic client utilise `backlog > 0` puis devient critique au-delà de 14 jours, dans [build_supplychain_worldmap.py](../../visualization/maps/build_supplychain_worldmap.py:2655). Avec des besoins fractionnaires et des services physiques entiers, de minuscules reliquats persistent naturellement.

Le client est ainsi classé « Critique disponibilité », avec 1 825 jours de backlog. Pourtant :

- 268967 : backlog ≥1 UN uniquement à J0/J1/J2 ; aucun jour supérieur à 1 UN après J2.
- 268091 : backlog important à J0/J1 ; valeur CSV exactement 1 à J62/J63/J79 ; aucun jour supérieur à 1 UN après J2.
- Le cumul des deux références dépasse 2 UN uniquement à J0/J1/J2.

La présence du reliquat est une information juste. Sa conversion automatique en crise durable n'est pas une qualification métier fiable.

**Correction recommandée :** séparer reliquat de prévision, demande entière en retard et rupture significative. Conserver les petits écarts visibles ; définir avec le métier le seuil, le traitement des arrondis et l'indicateur de ponctualité. Ne pas appeler le taux servi/demandé cumulé « OTIF » : il inclut les rattrapages et ne prouve pas les livraisons à l'heure.

### N4 — Une ancienne référence épuisée déclenche le signal de rupture pendant cinq ans — priorité 1

Dans [global_kpi_tree_payload.py](../../visualization/maps/global_kpi_tree_payload.py:933), toute ligne de stock intrant à zéro déclenche `raw_material_stockout_flag`. Il n'y a pas de condition de besoin actif ni de fin d'utilisation de la référence.

Le stock de `EX-344135` est à zéro en fin de journée pendant **1 825 jours sur 1 825**. La nouvelle référence 344135 est également à zéro pendant 54 jours. Le signal « MP usine zéro 30j » monte donc mécaniquement de 1 à 30 pendant le premier mois, puis reste à 30 : il ne démontre pas trente jours d'arrêt ou de manque de matière utile. Cette série alimente également le score « Physics of Decision ».

**Correction recommandée :** exiger un besoin non couvert de la référence valide, tenir compte des substitutions et séparer stock nul, rupture de couverture et production effectivement bloquée.

### N5 — Certains graphiques MRP additionnent KG, G et UN — priorité 1

Les courbes physiques principales sont regroupées par unité, ce qui est un bon choix. Mais les panneaux de détails MRP agrègent toutes les références d'un site sans conversion, notamment dans [build_supplychain_worldmap.py](../../visualization/maps/build_supplychain_worldmap.py:6921) et [build_supplychain_worldmap.py](../../visualization/maps/build_supplychain_worldmap.py:7190).

Exemple `M-1810`, J0, `StockProj` : la courbe vaut **2 019 867,6852**, somme de **248 049,0852 KG + 767 665 UN + 1 004 153,6 G**. L'arithmétique correspond au CSV ; ce total n'a aucune unité physique cohérente. Même problème pour les besoins et cibles agrégés. Les regroupements « volumes dominants » de références hétérogènes ne prouvent pas non plus une importance économique ou opérationnelle.

**Correction recommandée :** sélectionner article/unité ; convertir G/KG uniquement lorsque la comparaison a un sens ; pour une vue globale, utiliser des jours de couverture, une valeur financière documentée, un pourcentage ou un nombre de lignes. Ne jamais présenter une somme UN+KG+G comme un volume total.

### N6 — Le classement « coût total » change selon le périmètre — priorité 1

Le comparatif choisit le scénario risque comme « coût total le plus bas ». Les montants sont correctement copiés ; ce sont les coûts opérationnels, **hors approvisionnements externes**. Le moteur exporte aussi ces coûts externes et l'exposition économique complète.

| Somme des CSV journaliers, coûts simulés | Nominal | Risque | Risque − nominal |
|---|---:|---:|---:|
| Coût opérationnel | 289 514 141,07 | 262 259 663,94 | −27 254 477,13 |
| Approvisionnements externes / exceptionnel | 85 778 749,94 | 129 784 089,18 | +44 005 339,24 |
| Exposition économique complète | 375 292 891,01 | 392 043 753,12 | **+16 750 862,11** |

Le libellé « total » et la mise en avant du minimum dans [scenario_comparison_payload.py](../../visualization/maps/scenario_comparison_payload.py:575) induisent une lecture économique opposée selon le périmètre retenu. L'arbre KPI distingue mieux « coût opérationnel ». Ces chiffres demeurent des coûts de modèle, soumis aux hypothèses de valorisation examinées dans l'audit du moteur.

**Correction recommandée :** afficher les trois composantes, le périmètre de coût et la quantité servie ; ne pas présenter la baisse du coût opérationnel liée à une production moindre comme un gain économique validé.

### N7 — Plusieurs comparaisons de production utilisent des références différentes — priorité 2

L'adhérence mensuelle à 52,6 % et le respect du plan lotifié à 100 % sont arithmétiquement compatibles. La première compare la production à la demande aval ; la seconde compare l'exécution au plan lotifié. Les stocks initiaux, les lots, les fenêtres et les produits intermédiaires modifient leur relation.

Dans le profil compact courant, `production_input_consumption_daily.csv` manque. Pour l'intermédiaire, [global_kpi_tree_payload.py](../../visualization/maps/global_kpi_tree_payload.py:578) utilise donc `desired_qty`, tandis que les PF utilisent la demande client. La formule explique ce repli dans les définitions, mais une valeur affichée comme « adhérence usine » peut laisser croire à un plan mal exécuté.

**Correction recommandée :** libeller « écart production/demande sur 30 jours » et « respect du plan lotifié » séparément, rendre visibles la référence de chaque ligne et le recours au repli. Préférer les consommations aval réellement enregistrées lorsqu'elles sont disponibles dans le journal.

## Autres limites vérifiées

- **Horizon du tableau matière.** La lecture de la date de départ maximale J1947 crée une année 6 de 123 jours dans son payload alors que le run s'arrête à J1824. L'interface actuelle limite bien la sélection à cinq ans : l'année 6 n'est donc pas affichée via les contrôles courants. Cela n'annule pas le problème départ/réception déjà démontré sur les cinq années. À corriger dans le contrat de données en utilisant l'horizon du manifeste.
- **J0 de stock usine.** La courbe physique utilise le stock avant production à J0, puis les stocks fin de journée à partir de J1. Les valeurs se rapprochent du CSV mais la convention doit être visible : un clic J0 dans le suivi des lots peut légitimement montrer un stock fin de journée différent.
- **Gantt.** Durée calculée par `ceil(quantité/capacité)` ou jalon 0,6 jour. Le payload conserve séparément `tau_process` ; l'encart prévient que ce n'est pas une charge usine complète. Montrer date de lancement, durée d'occupation et date de disponibilité séparément serait plus direct.
- **Sensibilité et Monte Carlo.** Le comparatif actuel contient exactement nominal + risque, deux runs de 1 825 jours. Plusieurs autres blocs de sensibilité sont vides ; le panneau Monte Carlo annonce correctement son absence. L'enveloppe P10–P90 des scénarios sélectionnés est bien décrite comme descriptive, pas comme intervalle de confiance.
- **Audits fournisseurs.** Les 87 radars ont des valeurs cohérentes avec les critères embarqués mais leur accessibilité effective dépend du rendu. La revue navigateur a trouvé un défaut d'accès à ces radars ; voir [interface.md](interface.md).

## Ce qui est solide

Les courbes usuelles sont rattachables aux sources : dates cohérentes, transformations de moyennes mobiles explicites, distinction position MRP / stock physique dans les vues principales, présence de journaux physiques, scénario risque séparé, conservation des identités article/site et règles d'unités dans la traçabilité. Le calcul cumulé du service et les coûts journaliers sont reconstructibles. Les erreurs trouvées n'autorisent pas à conclure que tous les calculs du moteur sont faux ; elles interdisent en revanche d'assimiler automatiquement « CSV reproduit » à « interprétation métier validée ».

## Vérification à conserver pour les changements suivants

1. Associer à chaque figure/colonne un contrat explicite : objet métier, unité, date de référence, scénario, horizon, agrégation, source et statut observé/simulé/prévu/estimé.
2. Exécuter le rapprochement indépendant avec des fixtures métier comprenant changement de référence, en-cours initiaux, unités entières, réservations, départ avant J0, arrivée après horizon et stocks nuls sans besoin.
3. Faire échouer la livraison si une colonne dite physique ne se réconcilie pas au journal, si deux unités incompatibles sont additionnées ou si une anomalie est supprimée par le rendu.
4. Conserver séparément les vérifications des données sources, des formules, de l'affichage et de la calibration industrielle. Les quatre niveaux ne sont pas interchangeables.

Changements réalisés : rapport, script de rapprochement et preuves d'audit uniquement.

Tests exécutés : script indépendant sur le HTML livré et les CSV nominaux/risque ; inventaires et résultats détaillés joints. Les premiers essais ont révélé des insuffisances dans l'oracle d'audit (filtre de dates, nom d'événement, convention J30) qui ont été corrigées avant interprétation ; elles ne sont pas rapportées comme défauts du produit.

Risques / limites : calibration industrielle et contrôle exhaustif de chaque texte/tableau non acquis ; vérification des radars limitée aux données de critères déjà embarquées ; un rapprochement réussi ne valide pas une agrégation métier.

Prochaine étape recommandée : corriger N1 à N6 avec preuves de non-régression et rendre les contrats de sources visibles dans la carte, avant d'élargir les simulations d'incidents.
