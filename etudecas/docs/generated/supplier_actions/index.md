# Candidats fournisseurs et autorisation des actions

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### SUPPLIER-ACTION-001 — Un candidat descriptif ne libère pas une action

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le protocole consulte le sélecteur scientifique actuel. Sans audit de frontière il refuse la sélection ; un audit fourni invalide provoque une erreur. Les candidats descriptifs sont conservés avec leurs motifs mais aucune frontière actuellement prise en charge ne libère une sélection pour agir.

Périmètre : Préparation du protocole historique post-top3 ; trio descriptif, groupe non départagé et groupe service V3.

Unités : Identifiants fournisseurs ; groupes de candidats sans classement industriel implicite.

Limites : Aucune simulation exécutée et aucune recommandation industrielle. Les tests du raccordement remplacent certains validateurs amont. Une future autorisation d'action exige un contrat supplémentaire ; les anciens indicateurs V2 ne suffisent pas.

Sources métier : [SUPPLIER_ACTION_SELECTION.md](<../../SUPPLIER_ACTION_SELECTION.md>)

Références :

- implementation : [select_confirmed_action_suppliers](<../../../prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py#L589>)
- implementation : [_scientific_candidate_suppliers](<../../../prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py#L337>)
- implementation : [select_confirmed_top3](<../../../prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py#L713>)
- implementation : [main](<../../../prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py#L804>)
- test : [test_top3_selection_does_not_promote_legacy_consolidated_v2_flags](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_post_top3_action_protocol.py#L264>)
- test : [test_legacy_protocol_preserves_scientific_candidates_without_action_release](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py#L564>)
- test : [test_legacy_protocol_rejects_invalid_supplied_boundary](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py#L586>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### action-selection

[etudecas/prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py:589](<../../../prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py#L589>)

```python
def select_confirmed_action_suppliers(network_dir: Path, priority_boundary_audit_dir: Path | None=None) -> tuple[list[str], dict[str, Any]]:
```

Adapt scientific candidates to the legacy action-selection entry point.

Current signed boundaries expose descriptive candidates, never a globally
released action selection. Preserve their evidence without promoting a
scoped trio or an unordered group to an actionable top three. Missing
boundary input is a refusal; invalid supplied evidence raises.

### scientific-candidates

[etudecas/prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py:337](<../../../prototypes/scan_2027_risk_control/supplier_v2_controllable_action_selector.py#L337>)

```python
def _scientific_candidate_suppliers(network_dir: Path, priority_boundary_audit_dir: Path) -> tuple[list[str], dict[str, Any]]:
```

Read candidates only from the signed service-envelope boundary.

The legacy aggregate rank and its inherited ``top3`` flags are never used.
A released service-envelope trio remains scoped and therefore cannot
release an action. If that boundary is unresolved, the signed unranked
priority group is retained, also fail-closed.

### protocol-adapter

[etudecas/prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py:713](<../../../prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py#L713>)

```python
def select_confirmed_top3(network_results: Path, priority_boundary_audit_dir: Path | None=None) -> tuple[list[str], dict[str, Any]]:
```

Apply the current scientific action-selection contract.

The historical 10-realisation fields are deliberately ignored.  The
authoritative implementation lives in the additive V2 selector so both
entry points preserve scoped candidates without claiming action release.

### protocol-output

[etudecas/prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py:804](<../../../prototypes/scan_2027_risk_control/supplier_post_top3_action_protocol.py#L804>)

```python
def main(argv: Sequence[str] | None=None) -> int:
```

### legacy-rejection

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_post_top3_action_protocol.py:264](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_post_top3_action_protocol.py#L264>)

```python
def test_top3_selection_does_not_promote_legacy_consolidated_v2_flags(tmp_path: Path):
```

### candidate-scopes

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py:564](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py#L564>)

```python
def test_legacy_protocol_preserves_scientific_candidates_without_action_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary_kind: str):
```

### invalid-boundary

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py:586](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_v2_controllable_action_selector.py#L586>)

```python
def test_legacy_protocol_rejects_invalid_supplied_boundary(tmp_path: Path):
```
