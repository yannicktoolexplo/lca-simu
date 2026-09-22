# Corrections modèle et données après l'audit du 20 septembre 2026

Les corrections empêchent le lissage MRP de modifier la demande exécutée, suppriment une valorisation de stock dimensionnellement invalide, respectent l'unité déclarée du tarif de transport et distinguent les événements prévus des événements réalisés. Elles appliquent aussi les deux décisions métier confirmées : sécurité en jours ouvrés lundi-vendredi et totalité des jours sources au dépôt.

Le moteur et la préparation changent pour les nouveaux calculs. Aucun résultat historique ni aucune donnée source n'a été réécrit dans ce lot. Les comparaisons avec les anciens résultats doivent donc conserver l'identité et les paramètres de chaque version. Les quatre replays métier sont coordonnés séparément par l'agent principal ; les preuves décrites ici portent sur les tests ciblés et les simulations miniatures.

## Défauts corrigés et décisions explicites

| Audit | Changement | Contrôle indépendant |
|---|---|---|
| MD-01 | La consommation client et le dénominateur de service utilisent le profil source quotidien non lissé, après les perturbations explicites. Le lissage reste un signal de planification MRP. | Deux exécutions, lissage 1 et 7 jours, consomment exactement `10 × 7 + 100 = 170` unités de demande. Les signaux MRP diffèrent. Un autre essai conserve J364=100 puis J365=1 à la frontière annuelle. |
| MD-02 | Aucun prix d'un article inconnu n'est déduit de la médiane de prix d'autres articles ou unités. La préparation exporte `null`; le moteur refuse aussi les anciens taux marqués `global_value_median_fallback`. | Changer l'unité d'un autre article KG/G/UN laisse la valorisation inconnue. Pour un même matériau connu, 12 kg et 12 000 g donnent le même coût. Une conversion pièce→kg sans masse est refusée. |
| MD-04 | Un délai tiré lors d'une décision n'est observé qu'à la réception physique. Les colonnes de dates et de délai constatés restent vides auparavant. | La file d'observations ne produit rien avant la date de réception, ne produit aucun doublon et ignore les réceptions nulles. Le moteur miniature ne produit aucune alerte de délai observé avant sa première réception. |
| MD-05 | `transport_cost.per='unit'` facture les unités livrées ; le lot de commande ne sert plus implicitement de diviseur. `batch` requiert `transport_cost.batch_qty`; `shipment` facture l'occurrence. Une autre base exige une conversion explicite. | Le prix unitaire ne change pas quand le lot de commande passe de 1 à 100 000. Fractionner une quantité conserve le coût d'un tarif unitaire. Un tarif par lot sans taille de lot tarifaire échoue. |
| MD-06 | Les jours sources sont conservés et convertis en durée calendaire avec lundi-vendredi. L'ancrage existant `meta.mrp_seed.snapshot_at_utc`, soit le 1er janvier 2025, est utilisé. Sans date, J0 lundi est une convention explicitement exportée. | 28 cas sont comparés à un calendrier construit indépendamment avec `datetime` : 7 jours d'ancrage × 4 durées. Un jour ouvré après vendredi correspond à lundi, soit 3 jours calendaires. |
| MD-06 | Le facteur de cible dépôt vaut 1 par défaut. Une variante peut toujours fournir un facteur explicite, qui reste enregistré. | Test du défaut et option documentée `--soft-safety-time-stock-target-factor 1` pour le nouveau nominal. |
| MD-08 | Les départs futurs sont réservés ou seulement planifiés ; ils ne sont plus présentés comme déjà en transit. Les ordres d'ouverture sont qualifiés eux aussi. | Les sondes contiennent respectivement 21 et 42 départs après l'horizon ; leur quantité exécutée vaut zéro. Les coûts de ces départs restent en dehors du coût exécuté. |

Le calendrier de sécurité ne ferme ni usines, ni fournisseurs, ni transports pendant le week-end. Il n'introduit pas de calendrier de jours fériés. Le nombre source n'est jamais modifié. La conversion représente une couverture après le jour de référence ; elle varie donc selon la position dans la semaine.

Les points métier non décidés restent explicites dans `summary.model_qualifications` : le `tau_process` de trois jours reste une couverture de planification, sa durée physique demeure à confirmer ; les besoins MRP statiques restent fondés sur la capacité nominale × nomenclature ; le coût de possession des stocks réservés attend une règle de propriété. Aucune règle nouvelle n'a été inventée pour ces points.

## Contrat de sortie pour les consommateurs

`summary.economic_valuation` contient `status`, `complete`, `metric_basis`, les couples stock/article non valorisés et leur quantité-jours, les avertissements et `industrial_calibration_validated=false`.

Les clés historiques numériques `kpis.total_cost` et `kpis.total_economic_exposure` restent compatibles. En valorisation incomplète, elles représentent seulement les **sous-totaux connus**. Les alias explicites sont `known_cost_subtotal` et `known_economic_exposure_subtotal`. Il est incorrect de classer les scénarios sur un coût complet lorsque `complete=false`. Même `complete=true` indique la couverture des taux configurés, et non leur validation industrielle. Les hypothèses de prix, de coût et de propriété restent distinctes de cette couverture.

`summary.demand_execution_contract` indique le profil physique non lissé et la fenêtre MRP. `summary.policy.supplier_state_dependent_risk.lead_observation_basis` vaut `realized_transport_duration_observed_at_receipt`.

`data/production_supplier_shipments_daily.csv` conserve `day`, `arrival_day`, `shipped_qty` et ajoute :

- `observation_day`, `execution_status`, `source_inventory_reserved` ;
- `departure_executed`, `arrival_executed`, `executed_shipped_qty` ;
- `planned_departure_day`, `planned_arrival_day` ;
- `realized_departure_day`, `realized_arrival_day`, `realized_transport_lead_days` ;
- `lead_time_information_status`, soit `planned_not_yet_observed` ou `realized_at_receipt`.

Les quatre états physiques sont `planned_pending_departure`, `reserved_pending_departure`, `in_transit`, `received`. Le champ historique `shipped_qty` peut toujours désigner une quantité prévue au-delà de l'horizon ; les nouveaux consommateurs doivent sélectionner l'état ou utiliser `executed_shipped_qty`.

`reports/mrp_safety_stock_reference.csv` ajoute `safety_time_source_days`, `safety_time_calendar`, `safety_time_effective_at_day`, `safety_time_calendar_days`. `safety_time_days` conserve son rôle de durée utilisée par le moteur, désormais calendaire après conversion. Le référentiel est évalué au dernier jour ; les variations quotidiennes sont dans `data/mrp_trace_daily.csv`, avec les jours sources et le calendrier. Les ordres MRP disposent également de ces deux champs de provenance. La date d'ancrage et le périmètre du calendrier sont dans `summary.model_qualifications.safety_calendar`.

## Vérification et preuves

104 tests ciblés passent, sans échec ni saut : 46 contre-exemples et propriétés nouveaux, puis 58 tests existants sur les risques, les commandes d'ouverture, les stocks observés, les commandes de contrôle et les contrats physiques. Le test existant d'intégration demande/perturbation passe également séparément. La préparation réelle a été exécutée vers le dossier de preuve : **65 états, 53 valorisations connues et 12 inconnues explicites**, sans médiane inter-unités résiduelle.

Les premiers essais du nouveau test d'intégration ont corrigé la sonde elle-même : filtrage des articles de la fixture, nom canonique du CSV et activation effective du signal BOM nécessaire au lissage. Les assertions n'ont pas été supprimées pour masquer un échec moteur.

Commandes reproductibles depuis la racine :

```powershell
python -m pytest etudecas/simulation/test_audit_model_semantics.py -q
python -m pytest etudecas/simulation/test_supplier_risk_planning_semantics.py etudecas/simulation/test_opening_purchase_order_supplier_risk.py etudecas/simulation/test_opening_observed_stock_scale.py etudecas/simulation/test_control_schedule_engine_integration.py etudecas/testing/test_correction_contracts.py -q
python etudecas/artifacts/testing/audit_corrections_20260920/model/verify_corrections.py
```

Preuves : [correction-proof.json](../../artifacts/testing/audit_corrections_20260920/model/correction-proof.json), [contre-exemples JUnit](../../artifacts/testing/audit_corrections_20260920/model/counterexample-tests.xml), [tests existants JUnit](../../artifacts/testing/audit_corrections_20260920/model/existing-targeted-tests.xml), [préparation réelle](../../artifacts/testing/audit_corrections_20260920/model/preparation_report.json). Le JSON de preuve enregistre les SHA-256 des fichiers de code concernés. Les simulations miniatures persistent dans ce même dossier, et non dans `simulation/result`.

## Limites conservées

Le respect de `per='unit'` corrige le contrat logiciel ; il ne transforme pas les tarifs estimés en tarifs de transport vérifiés. Une base réelle par camion ou palette demande toujours les données correspondantes. La valorisation BOM d'un produit sans prix n'a pas été inventée.

Ces contrôles ne constituent ni une certification scientifique de tous les scénarios ni une validation des choix encore en attente. La nouvelle file d'observations de réception n'est pas incluse dans le hash optionnel de frontière warmup : celui-ci reste un audit partiel d'état et se déclare déjà non assimilable à un checkpoint de reprise. Cette omission n'altère pas les calculs, mais doit être complétée avant de prétendre hacher l'intégralité de l'état causal.

## Documentation automatisée et contre-revue

Le onzième registre, `docs/rules/audited_semantics.json`, relie ces règles à leurs fonctions Python et à leurs vrais tests, avec empreintes AST produites par `documentation.builder.inspect_reference`. Les conventions implémentées sont `documented`; tau physique, besoins MRP statiques et propriété des réservations restent `known_gap`. Le générateur détecte un changement du code ou de cette source métier ; il n'approuve pas automatiquement une nouvelle règle et n'exécute pas les tests.

```powershell
python -m etudecas.documentation.builder build --registry etudecas/docs/rules/audited_semantics.json --output-dir etudecas/docs/generated/audited_semantics
python -m etudecas.documentation.builder check --registry etudecas/docs/rules/audited_semantics.json --output-dir etudecas/docs/generated/audited_semantics
```

La contre-revue indépendante des producteurs de la carte a trouvé puis vérifié deux corrections supplémentaires, réalisées dans le lot visualisation : une courbe de réceptions prévues cherchait une colonne absente du CSV d'ordres ; un diagnostic DC comptait des réceptions futures non exécutées. La sonde finale trouve la réception prévue de 15 unités en semaine J7 et zéro réception exécutée pour le départ J10/arrivée J12 sur l'horizon J0-J1. Les bilans physiques réussissent l'oracle `20 + 5 - 8 = 17`, excluent la réception J10 et détectent une clôture altérée à 16.

Quatre oracles Chromium vérifient aussi les agrégations de périodes : stocks d'ouverture et clôture des années 2-3, rejet des années disjointes, rejet d'une année absente, maintien de l'alerte quand deux écarts annuels opposés s'annulent sur le total. Les preuves sont dans [review_payload](../../artifacts/testing/audit_corrections_20260920/model/review_payload/evidence.json) et [ui-evidence.json](../../artifacts/testing/audit_corrections_20260920/model/review_payload/ui-evidence.json). Cette contre-revue est ciblée et ne se présente pas comme une revue exhaustive du DOM.
