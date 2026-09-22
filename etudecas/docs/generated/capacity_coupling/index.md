# Couplage entre besoins et capacités fournisseurs

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### CAPACITY-COUPLING-001 — Le besoin peut modifier les capacités calculées

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

L'audit rejoue les capacités directes et amont en tenant compte du besoin, des capacités explicites, du stock, des lots et du taux d'utilisation. Changer le besoin peut donc modifier plusieurs mécanismes à la fois.

Périmètre : Relecture analytique des paramètres fournisseurs ; pas une nouvelle simulation.

Unités : Quantité dans l'unité de l'article ; capacités en quantité par jour ; délais en jours.

Limites : L'audit ne prouve pas une équivalence permanente avec toutes les branches du moteur. Les résultats de la fixture ne sont pas des performances observées.

Sources métier : [CAPACITY_COUPLING.md](<../../CAPACITY_COUPLING.md>)

Références :

- implementation : [replay_direct_capacity](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L158>)
- implementation : [replay_upstream_capacity](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L200>)
- implementation : [analyze](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L241>)
- test : [test_formula_replay_captures_lot_floor_and_upstream_coupling](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py#L30>)
- test : [test_retained_audit_builds_and_validates_without_engine](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py#L55>)

### CAPACITY-COUPLING-002 — Un audit doit correspondre aux entrées du protocole

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les chemins et empreintes des sources ainsi que le snapshot interne doivent correspondre. Un graphe différent est refusé, et l'audit doit interdire l'attribution causale au seul MRP.

Périmètre : Validation de l'audit de capacités associé au protocole de besoins dynamiques.

Unités : Chemins de fichiers, SHA-256 et nombres de liaisons.

Limites : Ces vérifications d'intégrité ne remplacent pas la validation scientifique d'une campagne ni celle de tous les checkpoints historiques.

Sources métier : [CAPACITY_COUPLING.md](<../../CAPACITY_COUPLING.md>)

Références :

- implementation : [validate_capacity_coupling_audit](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_requirement_reference_protocol.py#L458>)
- test : [test_capacity_audit_rejects_another_graph](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_requirement_reference.py#L70>)
- test : [test_retained_audit_builds_and_validates_without_engine](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py#L55>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### direct

[etudecas/prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py:158](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L158>)

```python
def replay_direct_capacity(row: Mapping[str, Any], *, demand_anchor: float, review_days: float) -> tuple[float, float, str]:
```

Replay ``derive_supplier_daily_capacity_by_pair`` for one single-lane pair.

### upstream

[etudecas/prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py:200](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L200>)

```python
def replay_upstream_capacity(row: Mapping[str, Any], *, demand_anchor: float, review_days: float) -> tuple[float, float]:
```

Replay the initial unmodelled-source daily-need and capacity formulas.

### analysis

[etudecas/prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py:241](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_capacity_coupling_audit.py#L241>)

```python
def analyze(*, graph_path: Path, supplier_parameters_path: Path, current_floors_path: Path, old_profile_path: Path, new_profile_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
```

### formula-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py:30](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py#L30>)

```python
def test_formula_replay_captures_lot_floor_and_upstream_coupling() -> None:
```

### audit-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py:55](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_capacity_coupling_audit.py#L55>)

```python
def test_retained_audit_builds_and_validates_without_engine(tmp_path: Path) -> None:
```

### binding

[etudecas/prototypes/scan_2027_risk_control/supplier_dynamic_requirement_reference_protocol.py:458](<../../../prototypes/scan_2027_risk_control/supplier_dynamic_requirement_reference_protocol.py#L458>)

```python
def validate_capacity_coupling_audit(capacity_audit_dir: Path, *, source: Mapping[str, Any]) -> dict[str, Any]:
```

Validate the additive analytical audit that proves the comparison coupling.

### binding-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_requirement_reference.py:70](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_dynamic_requirement_reference.py#L70>)

```python
def test_capacity_audit_rejects_another_graph(mismatch):
```
