# Réexamen d’Etudecas et du pack — 18 septembre 2026

**Décision : qualification globale refusée en l’état ; corrections nécessaires.**

Les défauts dépassent le diagramme de lots. Des incohérences sont présentes dans les stocks exportés, leur valorisation et les quantités physiques en unités. Des défauts supplémentaires concernent les indicateurs, certains modes d’exécution et les protections contre les entrées invalides ou les résultats périmés.

Les vérifications antérieures étaient insuffisantes pour conclure à une validation métier globale. L’ouverture d’un panneau, la concordance de deux copies d’un KPI et une empreinte inchangée ne prouvent pas que le résultat est juste.

## Périmètre réel et méthode

- Inventaire initial exhaustif des sources Python des deux dossiers, hors résultats, caches et artefacts : **665 fichiers, 490 184 lignes, 248 fichiers classés comme tests**. Analyse syntaxique de ces fichiers : aucune erreur. Recherche statique des noms non définis et usages locaux invalides avec Ruff : deux signalements, détaillés plus bas.
- Analyse syntaxique des **11 scripts PowerShell** présents dans ces dossiers, sans les exécuter : aucune erreur de syntaxe. Ce contrôle ne valide pas leurs effets à l’exécution ni leurs environnements historiques.
- Revue manuelle ciblée des chemins sensibles : ingestion et graphe, API et HTTP, stocks et service client, production, généalogie, agrégations, sensibilités, reprises Monte Carlo, cartes, documentation, publication atomique et pack.
- Rapprochements indépendants sur **les quatre runs de 1 825 jours** : nominal, risques, sensibilité stock ×1,5 et accélération. Aucun recalcul de ces runs.
- Relecture des sources métier pour les produits 268091, 268967 et 773474 avec les auditeurs existants ; revue des limites de ces auditeurs.
- Vérifications du HTML effectivement livré, hors ligne, dans Chromium ; sélection de quatre lots, dont trois autres que le lot par défaut.
- Entrées volontairement invalides et détérioration contrôlée de copies temporaires pour tester les validateurs et les reprises.
- Une simulation courte, isolée, pour reproduire le défaut du mode `estimated_replenishment`. Elle utilise une copie du graphe ; ses sorties temporaires ont été supprimées.

**Ce n’est pas une lecture humaine ligne par ligne des 490 184 lignes, ni une certification scientifique complète.** L’inventaire et les contrôles automatiques couvrent le périmètre annoncé ; la profondeur de la revue manuelle varie par domaine. Les expériences historiques, distributions de risques et résultats de calibration ne sont pas requalifiés par cet audit.

Les preuves compactes sont dans [review_20260918](etudecas/artifacts/testing/review_20260918/). Les fichiers du simulateur, la carte et les sorties de référence n’ont pas été corrigés pendant cet audit. Les ajouts sont des outils de vérification et ce rapport.

## Constats sur les résultats actuels

### F01 — Haute : le diagramme n’applique pas le même contrat à tous les lots

Le payload embarque seulement un modèle de vue pour le lot par défaut. Pour les autres lots, `selectedLotTraceSnapshot` reconstruit une vue qui reprend l’historique entier des occurrences ancêtres. Un stock partagé apporte donc les consommations d’autres campagnes, y compris futures.

Pour **PBATCH-411EC755D7110AE0**, fabriqué à J279 : **5 449 événements amont**, dont **4 745 après J279**, jusqu’à J1817. Ils couvrent 1 008 campagnes. Une consommation destinée à une autre production n’est pas une cause de la fabrication sélectionnée.

Le bandeau lit par ailleurs les compteurs du modèle de vue absent et les remplace par zéro. Reproduction navigateur : le lot par défaut affiche 9 lots métier ; les trois autres lots testés affichent tous 0 malgré une identité métier connue.

Code : `visualization/maps/worldmap_html_template.py`, `selectedLotTraceSnapshot` vers L5003, collecte des événements vers L5073, compteurs vers L8404 ; `simulation/lot_trace/payload.py` vers L760.

Preuves : `lot-browser/lot-browser.json` et captures associées ; [diagnostic initial du lot](etudecas/artifacts/testing/lot-PBATCH-411EC755D7110AE0/diagnostic.md).

Correction attendue : même contrat de sélection et d’allocation pour tous les lots, compteurs calculés sur ce contrat, historique contextuel distinct des contributions causales. Un simple filtre « avant J279 » serait insuffisant.

### F02 — Haute : des stocks « fin de journée » sont enregistrés avant les expéditions

Le moteur écrit `production_output_products_daily.stock_end_of_day` à la fin de la production, puis exécute les expéditions. Il actualise ensuite les stocks d’entrée, mais pas cette colonne des produits fabriqués.

Sur le nominal, **1 221 lignes sur 5 475** diffèrent du stock de clôture reconstruit à partir des lots :

| Site / article | Jours différents | Écart maximal, en UN |
|---|---:|---:|
| M-1430 / 268967 | 65 | 107 800 |
| M-1810 / 268091 | 1 131 | 43 200 |
| SDC-1450 / 773474 | 25 | 9 600 000 |

Pour chaque ligne, la différence correspond exactement aux quantités débitées pour expédition/réservation ce jour-là. Ce n’est donc pas une incertitude sur l’origine de l’écart.

`finished_goods_inventory_value.py` consomme cette colonne. Aux prix déjà présents dans les exports, la valorisation moyenne des stocks usine dépasse celle de fin de journée de **4 678,63 € pour 268091** et **6 024,08 € pour 268967**. Ce sont des écarts moyens de valorisation, pas des coûts supplémentaires à additionner sur les jours. Les courbes qui consomment la même colonne sont également concernées.

Code : `simulation/engine/run_first_simulation.py:L11500`, actualisation limitée aux entrées vers L14161 ; `simulation/analysis/finished_goods_inventory_value.py:L277` ; `visualization/maps/simulation_payload.py:L158`.

Preuves : `stock-timing.json`, `nominal-invariants.json`. Les trois autres runs présentent également ce décalage. Cela ne démontre pas, à lui seul, une erreur du calcul interne des coûts journaliers, calculés à un autre stade.

### F03 — Haute : le moteur sert des fractions d’articles indivisibles

**Règle confirmée par l’utilisateur pendant cet audit :** stocks et mouvements physiques entiers pour les articles en UN ; calculs prévisionnels fractionnaires autorisés.

Le moteur utilise directement `min(available, required)` pour le service client, sans conversion entre prévision fractionnaire et exécution physique. Exemple nominal : **7 072,591837 UN du 268091 servis à J2**. Le registre des lots reprend cette quantité et un stock restant fractionnaire.

Sur le nominal : 3 391 lignes de service client, 5 622 événements de mouvement de lots et 2 639 lignes de stock fournisseur présentent des fractions en UN. Ces comptes se recoupent et **ne doivent pas être additionnés comme des incidents distincts**.

Code : `simulation/engine/run_first_simulation.py:L11528` pour le service ; `LotLedger.consume` vers L1299 accepte aussi des fractions.

Correction attendue : définir une exécution entière commune au stock agrégé, au service et aux lots, en conservant les fractions prévisionnelles sans création ni disparition de demande. Arrondir les libellés ne corrige pas ce défaut.

### F04 — Moyenne à haute : les stocks fournisseurs et les lots dérivent séparément

La création d’un lot en UN arrondit la quantité ; certaines réceptions agrégées restent fractionnaires. Exemple : à J21, fournisseur SDC-VD1095770A, article 734545, le registre porte 1 823 UN contre 1 822,666667 dans le stock agrégé.

| Run | Lignes différentes / 60 225 | Écart absolu maximal |
|---|---:|---:|
| Nominal | 7 156 | 27,15 |
| Risques | 11 893 | 35,12 |
| Stock ×1,5 | 11 893 | 35,12 |
| Accélération | 11 893 | 37,733333 |

Ces maxima concernent des couples article/site différents : ce ne sont pas des quantités à sommer. La dérive doit être éliminée à la source, conjointement à F03. Le contrôle ne doit pas augmenter sa tolérance pour faire disparaître ces différences.

Code : `LotLedger.create_lot` vers L1165 et chemins d’alimentation des stocks agrégés. Preuves : les quatre fichiers `*-invariants.json`.

### F05 — Haute pour l’interprétation : le score agrège des quantités non comparables

`compute_observed_impact` divise les pertes fournisseurs, additionnées sans unité commune, par la demande de produits finis. La désignation « score descriptif » n’annule pas ce problème dimensionnel.

Reproduction : à demande et service identiques, représenter une perte de 1 kg par 1 000 g fait passer sa contribution de 1 à 1 000. Le score ne possède aucune information d’unité permettant de normaliser cette variation.

Dans le rapport livré, le terme « pertes matière » représente **98,699 % du score**. Son poids rend le classement particulièrement sensible à cette convention. La décomposition arithmétique est juste ; elle ne valide pas le sens du classement.

Code : `visualization/maps/scenario_comparison_payload.py:L92`. Preuves : `adversarial.json`, `decision_support/decision-report.json` du run figé.

Correction attendue : conserver les pertes par article/unité, puis définir avec justification métier une éventuelle conversion commune — valeur, équivalent produit ou ratios propres à chaque flux. Ne pas inventer de nouveaux poids pour retrouver un classement attendu.

### F06 — Haute pour l’interprétation : demandes d’achat non exécutées et pertes sont mélangées

`external_procured_rejected_today` additionne les quantités non commandées faute de capacité et les rejets qualité. Cette somme alimente `non_quality_loss_qty` et `quality_loss_qty_proxy`.

Une demande non exécutée, éventuellement redemandée plus tard, n’est pas une quantité de matière détruite. Le nominal affiche ainsi environ **4,101 milliards de quantités arithmétiques** dans ce champ, malgré zéro perte de fiabilité fournisseur. Les unités sont en outre hétérogènes.

Code : `run_first_simulation.py:L11874`, L11986–11987, puis L14718. Défaut de sémantique et d’agrégation confirmé par le code ; aucune estimation de pertes physiques globales ne doit être déduite de ce nombre.

### F07 — Moyenne : statut orange et présentation des lots trompeurs

Après départ du stock usine, un lot déjà produit et livré peut revenir au libellé « MP/PFI disponibles pour produire ». Le code mélange stock restant et disponibilité historique des intrants. Ce n’est pas une preuve de retard. Les captures confirment aussi des textes débordants et des étapes nécessitant un défilement horizontal.

Code : `simulation/lot_trace/payload.py:L270–365`. Séparer progression, position physique et contraintes historiques ; tester le cadrage et le contenu, au-delà de l’ouverture du panneau.

## Défauts d’autres modes et des protections

### F08 — Haute sur ce mode : arrêt du réapprovisionnement estimé

En mode `estimated_replenishment`, `register_mrp_order` est appelée vers L10602, avant sa définition locale vers L11601. Une copie du graphe nominal, passée à ce mode pour un essai de cinq jours, s’arrête avec **UnboundLocalError**. Le pilote `run_first_simulation_state_family_pilot.py` présente le même ordre d’appel signalé statiquement ; lui n’a pas fait l’objet d’un second essai dynamique.

La référence utilise `external_procurement` : ce défaut n’explique pas ses résultats actuels. Preuves : `ruff-undefined.json`, `estimated-replenishment-probe.json`.

### F09 — Haute : un scénario inexistant peut devenir le premier scénario

`choose_scenario` retourne le premier scénario quand l’identifiant demandé est absent. Reproduction : demande `scn:ABSENT`, retour `scn:BASE`. L’interface HTTP vérifie l’existence du scénario, mais cette protection n’est pas commune à tous les points d’entrée.

Code : `simulation/engine/run_first_simulation.py:L2897`, `engine/api.py` et `analysis_batch_common.py`. Il faut refuser une sélection explicite inconnue, pas substituer silencieusement un scénario.

### F10 — Moyenne à haute : contrat d’entrée encore incomplet

Les essais suivants ne produisent aucune erreur du validateur de graphe : stock initial négatif, article de stock absent du catalogue, ratio de nomenclature négatif, arc sans origine ni destination.

Par ailleurs, le parseur JSON refuse correctement un horizon négatif, mais `simulate(SimulationRequest(...))` ne repasse pas par cette validation. Un horizon −1 atteint l’exécuteur ; une chaîne `"false"` dans le champ CRN est interprétée comme vraie. L’exécuteur est remplacé par un observateur dans cette reproduction : aucune simulation invalide n’a été lancée par ce test.

Code : `knowledge_graph/schema.py`, `simulation/engine/api.py:L292`. Preuve : `adversarial.json`. Aucun de ces essais ne prouve que le graphe de référence contient ces entrées invalides ; ils démontrent un défaut de protection.

### F11 — Haute pour la reproductibilité : dépendances absentes de l’empreinte Monte Carlo

`_implementation_fingerprint` parcourt le répertoire du script moteur et quelques fichiers supplémentaires. Avec le moteur canonique sous `engine/`, des dépendances sœurs comme `lot_policy/` ne sont pas incluses.

Reproduction en arborescence temporaire : le moteur importe une dépendance sœur, sa valeur change de 1 à 2, l’empreinte reste identique. Un changement de cette nature ne peut donc pas invalider la reprise par ce mécanisme.

Code : `simulation/montecarlo/run_montecarlo_analysis.py:L138`. Aucun résultat Monte Carlo périmé n’a été démontré dans la carte courante, qui n’est pas qualifiée comme étude probabiliste. Le défaut concerne la garantie de reprise.

### F12 — Haute pour les expériences : facteur de sensibilité inconnu ignoré

`apply_scales` accepte un dictionnaire de facteurs sans vérifier que tous les noms sont consommés. Reproduction : `misspelled_capacity_scale=0.5` produit exactement le graphe obtenu avec des facteurs neutres, sans erreur.

Le matérialiseur de sensibilités transmet ces noms et peut donc enregistrer un paramètre annoncé mais sans effet. Une absence d’effet métier ne doit pas être confondue avec une instruction jamais appliquée.

Code : `simulation/analysis_batch_common.py`, `simulation/experiments/sensitivity/materialize.py`. Les deux sensibilités livrées utilisent un autre chemin, par calendrier de contrôles ; ce défaut ne prouve pas leur non-application.

### F13 — Moyenne : reprise d’une action malgré un fichier de contrôle absent

`decision_actions.execute_action` vérifie sa signature calculée et le résumé, mais pas le fichier réel du calendrier lors d’une réutilisation. Reproduction temporaire : après suppression du calendrier, le même appel retourne le dossier en cache sans erreur.

Les empreintes figées actuelles protègent séparément les fichiers qu’elles recensent ; cela ne corrige pas le contrat de réutilisation de cette fonction. Code : `decision_actions.py:L58`. Preuve : `adversarial.json`.

### F14 — Pack : plusieurs défauts de validation restent présents

Le pack est indépendant du simulateur ; ses défauts ne sont pas une preuve de corruption des calculs Etudecas.

| Reproduction | Résultat actuel |
|---|---|
| Colonne de score exigée mais absente | Rapport `ok` |
| Colonne `integer` contenant 1,5 | Rapport `ok` |
| Moyenne pondérée avec poids 2 et −1 | Score 2 pour des entrées 1 et 0 |
| Validation des résultats volontairement mise à `reject` | CLI : `Case executed`, code de sortie 0 |
| Exemple `supply_chain_bullwhip` | Échec : colonne visuelle `quality` absente |

Les exemples `example_minimal` et `fal_aircraft` réussissent. Tous les essais ont été exécutés dans une copie temporaire. Preuves : `adversarial.json`, `pack-examples.json`. Les défauts déjà identifiés dans l’audit du 16 septembre ne doivent pas être considérés comme corrigés parce que d’autres priorités ont été achevées.

## Règle métier à confirmer : sécurité au dépôt

Les données sources de sécurité n’ont pas été remplacées par la sensibilité ×1,5. Cependant, la référence applique **0,75** à la cible calculée depuis les délais de sécurité de DC-1920, pour les produits 268091 et 268967 :

| Article | Délai source conservé | Référence moyenne calculée | Cible moyenne avec coefficient |
|---|---:|---:|---:|
| 268091 | 20 jours | 215 898,284639 | 161 923,713479 |
| 268967 | 25 jours | 130 764,430679 | 98 073,323010 |

Les composants usine ont des surcharges de coefficient à 1. La conservation de la donnée source ne suffit donc pas à affirmer une application intégrale partout. **Question posée à l’utilisateur ; aucune modification de cette règle pendant l’audit.** Le choix du coefficient et celui d’un plancher physique obligatoire sont deux décisions distinctes.

## Résultats qui se réconcilient, avec leurs limites

- Sur les quatre runs : équations journalières de service et reliquat, limites de service par stock disponible, rapprochements des totaux de demande/service/production et des coûts journaliers avec les résumés, aux tolérances d’arrondi enregistrées. La justesse des prix et des hypothèses de coût n’est pas démontrée par une somme correcte.
- Registre de lots : identifiants d’événements uniques, quantités non négatives, équations de mouvement avec séparation réservation/départ, existence des extrémités de généalogie, quantités produites libérées en incluant les ordres de fabrication initiaux. Ces contrôles n’effacent pas F03 et F04.
- Stocks d’entrée usine et stocks dépôt rapprochés du registre ; les divergences de produits fabriqués et fournisseurs restent explicitement en échec.
- **19 839 expéditions fournisseurs identifiées dans l’horizon**, nominal et risques réunis : jointure avec les départs du registre et quantité prélevée concordantes, sans doublon d’identifiant. Dans chaque run, 66 lignes du carnet initial n’ont pas cette identité native ; elles sont comptées séparément. Les départs hors horizon ne sont pas déclarés absents du registre mesuré.
- Pour les trois produits audités, les valorisations des composants initiaux se rapprochent des sources à l’arrondi près ; ordres de fabrication initiaux et nombres de lignes d’achat associés concordent dans le périmètre des auditeurs. Des divisions/ordres hors périmètre restent signalés dans les métadonnées : ce n’est pas une validation exhaustive de tous les classeurs.
- Les huit registres de documentation sont à jour vis-à-vis de leurs références. Cela vérifie la cohérence documentaire enregistrée, pas la véracité métier de chaque règle ni une couverture totale du moteur.

## Dispositif de vérification ajouté

1. **Oracle arithmétique séparé** : [independent_review.py](etudecas/testing/independent_review.py) n’importe ni moteur, ni générateur de payload, ni validateur de production. Il lit les CSV, recalcule les équations, vérifie les identités, les horizons et la règle des UN. Les fichiers manquants et les écarts font échouer la commande.
2. **Vérification du vérificateur** : [test_independent_review.py](etudecas/testing/test_independent_review.py), cas calculable à la main (10 unités, 4 transférées, 6 restantes), corruptions volontaires, donnée manquante et distinction prévision fractionnaire/service entier. Neuf tests réussissent.
3. **Contrôle métier du navigateur** : [lot_browser_review.py](etudecas/testing/lot_browser_review.py) sélectionne des lots différents, lit le bandeau effectivement affiché et échoue sur les compteurs faux ; conserve les captures.
4. **Essais adverses** : [adversarial_review.py](etudecas/testing/adversarial_review.py) reproduit les lacunes de contrats et de cache dans des répertoires temporaires. Son échec actuel est le résultat attendu de l’audit, pas un succès à masquer.

Exemples de commandes, depuis la racine du dépôt :

```powershell
python -m pytest etudecas/testing/test_independent_review.py -q
python -m etudecas.testing.independent_review --run etudecas/simulation/result/_reruns/reviewed_map_20260918 --output etudecas/artifacts/testing/review_20260918/nominal-invariants.json
python -m etudecas.testing.lot_browser_review --html etudecas/simulation/result/_reruns/reviewed_map_20260918/maps/supply_graph_reviewed_map_20260918.html --output etudecas/artifacts/testing/review_20260918/lot-browser
python -m etudecas.testing.adversarial_review --output etudecas/artifacts/testing/review_20260918/adversarial.json
python -S -m etudecas.reference_status --output etudecas/artifacts/testing/review_20260918/reference-after.json
```

Les trois commandes d’audit métier sont actuellement **rouges**. Les empreintes peuvent être **vertes** simultanément : une référence inchangée peut contenir des erreurs.

## Critères obligatoires pour les prochains changements

Avant le code : règle attendue, unités, granularité temporelle, résultat calculable indépendamment, cas limite et impacts autorisés. Si la règle manque ou se contredit, poser une question métier précise et laisser cette décision ouverte.

Après le code : cas connu, corruption détectée, invariant sur les CSV, égalité entre CSV/payload/affichage, puis tests de non-régression. Pour une modification du moteur, recalcul dans un nouveau dossier avec comparaison à la référence conservée ; jamais acceptation silencieuse d’empreintes ou remplacement de la référence.

L’acceptation devra identifier séparément **correct sur les preuves contrôlées**, **incorrect**, **non vérifié** et **hypothèse à confirmer**. Un test qui compare deux sorties issues du même calcul ne constitue pas seul un oracle indépendant.

## Ordre de correction recommandé

1. Exécution physique entière et registre cohérent ; corriger le moment d’export des stocks et vérifier les valorisations dépendantes.
2. Contrat unique de traçabilité pour tous les lots, conservation des contributions, compteurs et statuts ; cas de composants partagés, mélanges, livraisons partielles et fin d’horizon.
3. Indicateurs de pertes et classement : unités homogènes, séparation des demandes non exécutées et des pertes réelles.
4. Contrats communs à tous les points d’entrée, refus des scénarios/facteurs inconnus, réparation du mode estimé et couverture de chaque branche.
5. Provenance complète des reprises et contrôle des preuves en cache ; pack et documentation alignés sur les vérifications réellement faites.

Il n’est pas nécessaire de relancer des campagnes de calibration ou Monte Carlo pour diagnostiquer ces défauts. La validation d’un moteur corrigé nécessitera ensuite des recalculs ciblés et comparables, distincts de la référence préservée.

## Exécution des suites

Le détail consolidé est conservé dans `etudecas/artifacts/testing/review_20260918/`. La suite centrale a terminé à **687 réussites, 2 tests lents ignorés et 53 sous-tests réussis**. Les deux tests ignorés ciblent une ancienne livraison de cinq ans ; le navigateur courant a été contrôlé séparément.

L’invocation globale initiale a atteint sa limite de 1 200 secondes. Son journal atteste 90 modules terminés, avec 974 réussites et 7 ignorés, avant le module V7 interrompu. Ce dernier et les modules suivants sont repris séparément ; ces chiffres recoupent en partie la suite centrale et ne doivent pas être additionnés sans dédoublonnage.

La reprise termine à **871 réussites et 20 ignorés**. Après dédoublonnage par module complet et contrôle contre la collecte actuelle : **2 521 tests recensés dans 244 modules, 2 492 réussis, 29 ignorés, aucun échec des tests existants ni des tests du vérificateur, aucun module manquant**. Les 53 sous-tests ne sont pas ajoutés à ce total. La consolidation utilise les rapports JUnit et, pour les modules terminés avant interruption, le journal de progression conservé. Elle ne constitue pas un passage unique ininterrompu de la suite.

Les 29 tests ignorés restent **non vérifiés**, notamment les intégrations historiques, les deux anciens cas de lots de cinq ans et un contrôle nécessitant Node.js. Voir `test-consolidation.json`, `pytest-all.log`, `pytest-remaining.xml` et `core/pytest.xml` pour le périmètre et les preuves.

Contrôle final : **155 empreintes de référence sur 155 concordent** ; aucune dérive des références documentaires enregistrées. Les nouveaux audits métier restent en échec sur les défauts décrits. **Tests verts et référence inchangée ne valent donc pas acceptation métier.**
