# Sémantique auditée : demande, sécurité, coûts et exécution physique

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### AUDITED-DEMAND-001 — Demande exécutée distincte du signal MRP

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

La demande client utilisée pour le service vient du profil source quotidien sans lissage, après perturbations explicites. La fenêtre future de lissage est réservée à la planification MRP.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Quantités par article dans leur unité source ; jours calendaires du simulateur.

Limites : La demande et les prévisions peuvent rester fractionnaires ; ce contrat ne transforme pas une prévision en mouvement physique fractionnaire. Le changement modifie les nouveaux résultats, pas les historiques.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- implementation : [demand_targets_for_day](<../../../simulation/engine/run_first_simulation.py#L2935>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)
- test : [test_engine_preserves_last_day_of_year_and_repeating_source_boundary](<../../../simulation/test_audit_model_semantics.py#L210>)

### AUDITED-SAFETY-001 — Jours de sécurité ouvrés avec ancrage explicite

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les jours sources de sécurité sont conservés. Le calendrier lundi-vendredi confirmé pour tous les sites les convertit en durée calendaire après le jour de référence. La date civile du scénario ou du snapshot sert d'ancrage ; à défaut J0 lundi est une convention déclarée.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Jours ouvrés source, jours calendaires effectifs et date d'évaluation distincts.

Limites : Ce calendrier concerne uniquement la couverture de sécurité. Aucune fermeture physique des usines ou transports, aucun jour férié ni calendrier de production nouveau n'est déduit.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [safety_calendar_days](<../../../simulation/engine/model_semantics.py#L86>)
- implementation : [safety_calendar_anchor](<../../../simulation/engine/model_semantics.py#L72>)
- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_working_day_coverage_matches_independent_calendar](<../../../simulation/test_audit_model_semantics.py#L107>)
- test : [test_calendar_anchor_and_full_source_target_are_explicit](<../../../simulation/test_audit_model_semantics.py#L118>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)

### AUDITED-SAFETY-002 — Application intégrale de la sécurité source au dépôt

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le facteur par défaut de la cible de sécurité souple est 1, conformément à la décision utilisateur. Une sensibilité peut fournir un autre facteur explicite ; elle conserve son identité et ses paramètres.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Facteur sans dimension ; quantité cible dans l'unité de l'article.

Limites : Les valeurs historiques 0,75 ne sont pas réécrites. Un graphe ou une option explicite peut encore déclarer une sensibilité différente ; le nouveau nominal doit retenir le facteur 1.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [scenario_initialization_policy](<../../../simulation/engine/run_first_simulation.py#L4687>)
- test : [test_calendar_anchor_and_full_source_target_are_explicit](<../../../simulation/test_audit_model_semantics.py#L118>)

### AUDITED-VALUATION-001 — Prix inconnu distinct de zéro et coûts incomplets

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Un prix manquant reste inconnu ; une médiane mélangeant prix/kg, prix/pièce ou prix/mètre est interdite. La préparation exporte null et le moteur refuse l'ancien fallback global. Les coûts numériques historiques restent des sous-totaux connus avec couverture explicite, jamais un coût complet lorsque complete=false.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Valeur par unité physique documentée ; taux de possession par unité et jour ; quantité-jours non valorisée.

Limites : complete=true décrit la couverture des taux configurés, pas une calibration industrielle. Aucun prix BOM ni taux de change n'est inventé. Les classements économiques complets exigent une couverture suffisante et des hypothèses compatibles.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [derive_item_unit_value_map](<../../../simulation_prep/prepare_simulation_graph.py#L128>)
- implementation : [holding_cost_per_unit_day_from_value](<../../../simulation_prep/prepare_simulation_graph.py#L172>)
- implementation : [inventory_holding_rate](<../../../simulation/engine/model_semantics.py#L10>)
- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_missing_price_is_not_imputed_from_unrelated_dimension](<../../../simulation/test_audit_model_semantics.py#L27>)
- test : [test_known_same_material_cost_is_invariant_under_kg_to_g_conversion](<../../../simulation/test_audit_model_semantics.py#L42>)
- test : [test_piece_price_cannot_silently_become_kg_price](<../../../simulation/test_audit_model_semantics.py#L54>)
- test : [test_unknown_and_explicit_zero_cost_remain_distinguishable](<../../../simulation/test_audit_model_semantics.py#L62>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)

### AUDITED-OBSERVATION-001 — Délai prévu et délai constaté séparés

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Un délai simulé lors d'une décision reste prévisionnel jusqu'à la réception. Les risques dépendant d'un délai observé ne reçoivent cette observation qu'à la date physique de réception ; une réception nulle n'apporte pas d'observation.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Jours de transport entre départ et réception ; date d'observation distincte de date de décision.

Limites : Les dates futures restent disponibles comme prévisions. Ce contrat n'est ni un modèle probabiliste de précision ETA ni une preuve de causalité propre à un incident.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [ReceiptLeadObservations](<../../../simulation/engine/model_semantics.py#L53>)
- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_receipt_observation_never_reveals_future_sampled_delay](<../../../simulation/test_audit_model_semantics.py#L94>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)
- test : [test_engine_preserves_last_day_of_year_and_repeating_source_boundary](<../../../simulation/test_audit_model_semantics.py#L210>)

### AUDITED-TRANSPORT-001 — Base tarifaire déclarée pour le transport

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

per=unit utilise les unités livrées et ne divise pas par le lot de commande. Une base batch/lot exige batch_qty propre au tarif ; shipment/dispatch facture l'occurrence. Une autre base nécessite une conversion explicite.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Monnaie par unité livrée, par lot tarifaire ou par expédition selon la base déclarée.

Limites : Le respect logiciel du tarif ne valide pas sa valeur industrielle. Le nombre de camions ou palettes nécessite toujours des données logistiques adaptées ; le lot d'approvisionnement n'est pas automatiquement une unité tarifaire.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [transport_charge](<../../../simulation/engine/model_semantics.py#L22>)
- test : [test_unit_tariff_obeys_declared_unit_not_order_size](<../../../simulation/test_audit_model_semantics.py#L69>)
- test : [test_batch_tariff_requires_its_own_explicit_conversion](<../../../simulation/test_audit_model_semantics.py#L78>)

### AUDITED-SHIPMENT-001 — Prévu, réservé, parti et reçu selon les dates physiques

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Un départ futur reste planifié ou réservé, puis devient en transit et enfin reçu. Les colonnes exécutées ne comptent aucun départ après l'horizon. Le moteur conserve les prévisions historiques tout en exportant leur état et les dates réalisées séparément.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Quantités physiques par article ; jours mesurés relatifs à J0 ; états à la fin de l'horizon.

Limites : Le champ historique shipped_qty peut contenir une prévision future. Un consommateur doit utiliser executed_shipped_qty ou les dates et indicateurs d'exécution. Une réservation ne prouve pas un chargement de camion.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [shipment_execution_state](<../../../simulation/engine/model_semantics.py#L45>)
- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_shipment_status_depends_on_physical_dates](<../../../simulation/test_audit_model_semantics.py#L89>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)
- test : [test_engine_preserves_last_day_of_year_and_repeating_source_boundary](<../../../simulation/test_audit_model_semantics.py#L210>)

### AUDITED-TAU-001 — Durée physique tau à confirmer

Statut déclaré : **known_gap**. Relecture des sources : **aucun changement détecté**.

La convention actuelle garde tau_process comme couverture de planification ; la durée physique de trois jours n'a pas été confirmée. Cette limite est exportée explicitement et aucune nouvelle immobilisation de production n'est appliquée.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Jours de planification ; durée physique non validée.

Limites : Le test vérifie l'export de la qualification, pas la pertinence industrielle d'une libération le même jour. Une décision métier et des essais physiques distincts restent nécessaires.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)

### AUDITED-MRP-001 — Besoins MRP statiques encore non validés

Statut déclaré : **known_gap**. Relecture des sources : **aucun changement détecté**.

Les couples configurés en besoin MRP statique conservent leur base capacité nominale multipliée par nomenclature. Ils ne sont pas présentés comme une demande observée ; aucune substitution par un besoin dynamique n'est faite sans décision explicite.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Quantité théorique par jour et article, unité de nomenclature.

Limites : La bonne sélection technique des modes statique/dynamique ne valide pas le dimensionnement métier des 23 références du cas historique. Le registre garde ce choix au statut de lacune connue.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [resolve_mrp_requirement_pair_modes](<../../../simulation/engine/run_first_simulation.py#L3813>)
- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_targeted_dynamic_pair_overrides_inherited_and_cli_static_modes](<../../../simulation/test_supplier_risk_planning_semantics.py#L11>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)

### AUDITED-RESERVATION-001 — Propriété du stock réservé encore à définir

Statut déclaré : **known_gap**. Relecture des sources : **aucun changement détecté**.

La convention actuelle exclut le stock réservé du coût de possession du stock disponible jusqu'au départ. La règle de propriété économique pendant la réservation est exportée comme non décidée.

Périmètre : Nouvelles exécutions du moteur et sorties de traçabilité ; sources et résultats historiques conservés.

Unités : Quantité-jours détenue ou réservée ; coût de possession du périmètre configuré.

Limites : Le test vérifie la qualification explicite. Il ne valide pas cette règle comptable ; un coût complet industriel doit préciser transfert de propriété et détention économique.

Sources métier : [2026-09-20-audit-model-corrections.md](<../../changes/2026-09-20-audit-model-corrections.md>)

Références :

- implementation : [main](<../../../simulation/engine/run_first_simulation.py#L6869>)
- test : [test_engine_preserves_source_demand_and_qualifies_incomplete_costs](<../../../simulation/test_audit_model_semantics.py#L171>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### engine-run

[etudecas/simulation/engine/run_first_simulation.py:6869](<../../../simulation/engine/run_first_simulation.py#L6869>)

```python
def main() -> None:
```

### demand-profile

[etudecas/simulation/engine/run_first_simulation.py:2935](<../../../simulation/engine/run_first_simulation.py#L2935>)

```python
def demand_targets_for_day(demand_profiles: dict[tuple[str, str], list[dict[str, Any]]], day: int, *, window_days: int=1) -> dict[tuple[str, str], float]:
```

### initialization

[etudecas/simulation/engine/run_first_simulation.py:4687](<../../../simulation/engine/run_first_simulation.py#L4687>)

```python
def scenario_initialization_policy(scenario: dict[str, Any], *, review_period_days: int, safety_stock_days: float) -> dict[str, Any]:
```

### safety-calendar

[etudecas/simulation/engine/model_semantics.py:86](<../../../simulation/engine/model_semantics.py#L86>)

```python
def safety_calendar_days(source_days: float, *, day: int, anchor_weekday: int, calendar: str) -> float:
```

Elapsed cover after N working days; no production/transport closure implied.

### safety-anchor

[etudecas/simulation/engine/model_semantics.py:72](<../../../simulation/engine/model_semantics.py#L72>)

```python
def safety_calendar_anchor(graph: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
```

### known-value

[etudecas/simulation_prep/prepare_simulation_graph.py:128](<../../../simulation_prep/prepare_simulation_graph.py#L128>)

```python
def derive_item_unit_value_map(edges: list[dict[str, Any]], item_unit_map: dict[str, str], price_map: dict[tuple[str, str, str], dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any]]:
```

### holding-conversion

[etudecas/simulation_prep/prepare_simulation_graph.py:172](<../../../simulation_prep/prepare_simulation_graph.py#L172>)

```python
def holding_cost_per_unit_day_from_value(*, item_id: str, unit: Any, item_unit_map: dict[str, str], item_unit_value_map: dict[str, float], fallback_global_unit_value: float | None, annual_carry_rate: float) -> tuple[float | None, str, float | None]:
```

### holding-contract

[etudecas/simulation/engine/model_semantics.py:10](<../../../simulation/engine/model_semantics.py#L10>)

```python
def inventory_holding_rate(payload: dict[str, Any]) -> tuple[float | None, str]:
```

### receipt-observation

[etudecas/simulation/engine/model_semantics.py:53](<../../../simulation/engine/model_semantics.py#L53>)

```python
class ReceiptLeadObservations
```

Latent sampled outcomes become observations only on their receipt date.

### tariff

[etudecas/simulation/engine/model_semantics.py:22](<../../../simulation/engine/model_semantics.py#L22>)

```python
def transport_charge(lane: dict[str, Any], pulled_qty: float, delivered_qty: float) -> tuple[float, str, float]:
```

The declared tariff unit governs billing; procurement lot size is not a tariff.

### execution-state

[etudecas/simulation/engine/model_semantics.py:45](<../../../simulation/engine/model_semantics.py#L45>)

```python
def shipment_execution_state(departure_day: int, arrival_day: int, observation_day: int, *, reserved: bool=True) -> str:
```

### mrp-modes

[etudecas/simulation/engine/run_first_simulation.py:3813](<../../../simulation/engine/run_first_simulation.py#L3813>)

```python
def resolve_mrp_requirement_pair_modes(inherited_static_pairs: Any, cli_static_pairs: Any, cli_dynamic_pairs: Any) -> tuple[list[str], list[str]]:
```

Resolve additive static requests and targeted dynamic overrides.

### demand-integration-test

[etudecas/simulation/test_audit_model_semantics.py:171](<../../../simulation/test_audit_model_semantics.py#L171>)

```python
def test_engine_preserves_source_demand_and_qualifies_incomplete_costs(tmp_path):
```

### annual-boundary-test

[etudecas/simulation/test_audit_model_semantics.py:210](<../../../simulation/test_audit_model_semantics.py#L210>)

```python
def test_engine_preserves_last_day_of_year_and_repeating_source_boundary(tmp_path):
```

### calendar-test

[etudecas/simulation/test_audit_model_semantics.py:107](<../../../simulation/test_audit_model_semantics.py#L107>)

```python
def test_working_day_coverage_matches_independent_calendar(weekday, source_days):
```

### calendar-default-test

[etudecas/simulation/test_audit_model_semantics.py:118](<../../../simulation/test_audit_model_semantics.py#L118>)

```python
def test_calendar_anchor_and_full_source_target_are_explicit():
```

### unknown-price-test

[etudecas/simulation/test_audit_model_semantics.py:27](<../../../simulation/test_audit_model_semantics.py#L27>)

```python
def test_missing_price_is_not_imputed_from_unrelated_dimension(other_uom, other_price):
```

### unit-conversion-test

[etudecas/simulation/test_audit_model_semantics.py:42](<../../../simulation/test_audit_model_semantics.py#L42>)

```python
def test_known_same_material_cost_is_invariant_under_kg_to_g_conversion():
```

### incompatible-price-test

[etudecas/simulation/test_audit_model_semantics.py:54](<../../../simulation/test_audit_model_semantics.py#L54>)

```python
def test_piece_price_cannot_silently_become_kg_price():
```

### unknown-zero-test

[etudecas/simulation/test_audit_model_semantics.py:62](<../../../simulation/test_audit_model_semantics.py#L62>)

```python
def test_unknown_and_explicit_zero_cost_remain_distinguishable():
```

### receipt-observation-test

[etudecas/simulation/test_audit_model_semantics.py:94](<../../../simulation/test_audit_model_semantics.py#L94>)

```python
def test_receipt_observation_never_reveals_future_sampled_delay():
```

### unit-tariff-test

[etudecas/simulation/test_audit_model_semantics.py:69](<../../../simulation/test_audit_model_semantics.py#L69>)

```python
def test_unit_tariff_obeys_declared_unit_not_order_size(procurement_lot):
```

### batch-tariff-test

[etudecas/simulation/test_audit_model_semantics.py:78](<../../../simulation/test_audit_model_semantics.py#L78>)

```python
def test_batch_tariff_requires_its_own_explicit_conversion():
```

### execution-state-test

[etudecas/simulation/test_audit_model_semantics.py:89](<../../../simulation/test_audit_model_semantics.py#L89>)

```python
def test_shipment_status_depends_on_physical_dates(observation, status):
```

### mrp-modes-test

[etudecas/simulation/test_supplier_risk_planning_semantics.py:11](<../../../simulation/test_supplier_risk_planning_semantics.py#L11>)

```python
def test_targeted_dynamic_pair_overrides_inherited_and_cli_static_modes() -> None:
```
