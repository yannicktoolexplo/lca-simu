# Publication et reprise des calibrations fournisseurs

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### CALIBRATION-EXECUTION-001 — Publier un fichier complet ou signaler l'échec

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

La V2 publie chaque fichier par remplacement atomique. Elle retente uniquement les refus Windows 5, 32 et 33, dans une limite de six essais ; les autres erreurs et les refus persistants sont propagés.

Périmètre : Écriture des JSON et CSV par le runner V2.

Unités : Secondes d'attente, codes Windows, fichiers UTF-8.

Limites : Pas de transaction entre plusieurs fichiers ; pas de garantie contre une panne matérielle. Les reprises restent soumises au contrôle du registre.

Sources métier : [CALIBRATION_EXECUTION.md](<../../CALIBRATION_EXECUTION.md>)

Références :

- implementation : [_write_atomic](<../../../atomic_io.py#L37>)
- implementation : [_replace_with_retry](<../../../atomic_io.py#L23>)
- contract : [RETRY_DELAYS](<../../../atomic_io.py#L19>)
- contract : [WINDOWS_RETRY_ERRORS](<../../../atomic_io.py#L20>)
- implementation : [write_json_atomic](<../../../atomic_io.py#L62>)
- implementation : [write_csv_atomic](<../../../atomic_io.py#L70>)
- test : [test_transient_replacement_preserves_old_file_until_success](<../../../tests/commun/test_atomic_io.py#L18>)
- test : [test_persistent_or_unrelated_failure_propagates](<../../../tests/commun/test_atomic_io.py#L43>)

### CALIBRATION-EXECUTION-002 — Conserver l'identité de l'exécution et du checkpoint

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

La signature V2 inclut le code de publication. Un dossier V1 est refusé. La reprise conserve les preuves du checkpoint de 15 répétitions et ajoute seulement les répétitions 16 à 30 ; un inventaire incohérent bloque la reprise.

Périmètre : Calibrations nouvelles exécutées par le runner V2.

Unités : SHA-256, graines et répétitions de simulation.

Limites : Le plan reste figé ; aucune migration ou réparation automatique d'une campagne historique. Les dépendances transitives ne sont pas toutes couvertes par ces empreintes.

Sources métier : [CALIBRATION_EXECUTION.md](<../../CALIBRATION_EXECUTION.md>)

Références :

- implementation : [_campaign_signature](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L348>)
- implementation : [_base_manifest](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1062>)
- implementation : [run_calibration](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1109>)
- implementation : [_load_ledger](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L679>)
- test : [test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L182>)
- test : [test_current_runner_refuses_v1_output_without_changing_it](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L354>)
- test : [test_failed_ledger_commit_cannot_be_silently_resumed](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L459>)
- test : [test_io_source_is_bound_to_signature_and_manifest](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L418>)

### CALIBRATION-EXECUTION-003 — Distinguer robustesse technique et validation métier

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Une exécution synthétique reste non publiable. La calibration caractérise des hypothèses de simulation ; les autorisations de promotion d'action et de publication confirmatoire restent fausses.

Périmètre : Interprétation du manifeste de calibration et des tests synthétiques.

Unités : Indicateurs booléens ; taux de service simulé.

Limites : Les tests ne qualifient ni un fournisseur réel ni les campagnes V8 historiques.

Sources métier : [CALIBRATION_EXECUTION.md](<../../CALIBRATION_EXECUTION.md>)

Références :

- implementation : [_base_manifest](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1062>)
- implementation : [run_calibration](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1109>)
- test : [test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L182>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### write

[etudecas/atomic_io.py:37](<../../../atomic_io.py#L37>)

```python
def _write_atomic(path: Path, serialize: Callable[[TextIO], None], *, newline: str | None) -> None:
```

### retry

[etudecas/atomic_io.py:23](<../../../atomic_io.py#L23>)

```python
def _replace_with_retry(temporary: Path, destination: Path) -> None:
```

### json

[etudecas/atomic_io.py:62](<../../../atomic_io.py#L62>)

```python
def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
```

### csv

[etudecas/atomic_io.py:70](<../../../atomic_io.py#L70>)

```python
def write_csv_atomic(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None=None) -> None:
```

### delays

[etudecas/atomic_io.py:19](<../../../atomic_io.py#L19>)

```python
RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)
```

### errors

[etudecas/atomic_io.py:20](<../../../atomic_io.py#L20>)

```python
WINDOWS_RETRY_ERRORS = frozenset({5, 32, 33})
```

### transient-test

[etudecas/tests/commun/test_atomic_io.py:18](<../../../tests/commun/test_atomic_io.py#L18>)

```python
def test_transient_replacement_preserves_old_file_until_success(tmp_path, monkeypatch, code):
```

### persistent-test

[etudecas/tests/commun/test_atomic_io.py:43](<../../../tests/commun/test_atomic_io.py#L43>)

```python
def test_persistent_or_unrelated_failure_propagates(tmp_path, monkeypatch, code, attempt_count):
```

### signature

[etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py:348](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L348>)

```python
def _campaign_signature(plan: ValidatedPlan, *, smoke_only: bool) -> str:
```

### manifest

[etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py:1062](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1062>)

```python
def _base_manifest(*, plan: ValidatedPlan, signature: str, output_dir: Path, workers: int, retention: str, custom_executor_used: bool, smoke_only: bool) -> dict[str, Any]:
```

### run

[etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py:1109](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L1109>)

```python
def run_calibration(*, plan_dir: Path, output_dir: Path, mode: str, workers: int=2, retention: str='summary', checkpoint_after_repetitions: int | None=None, case_executor: CaseExecutor | None=None) -> dict[str, Any]:
```

### ledger

[etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py:679](<../../../prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py#L679>)

```python
def _load_ledger(output_dir: Path, signature: str) -> dict[str, Any]:
```

### checkpoint-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py:182](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L182>)

```python
def test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30(tmp_path: Path, synthetic_plan) -> None:
```

### version-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py:354](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L354>)

```python
def test_current_runner_refuses_v1_output_without_changing_it(tmp_path, synthetic_plan):
```

### orphan-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py:459](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L459>)

```python
def test_failed_ledger_commit_cannot_be_silently_resumed(tmp_path, monkeypatch, synthetic_plan):
```

### binding-test

[etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py:418](<../../../prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py#L418>)

```python
def test_io_source_is_bound_to_signature_and_manifest(synthetic_plan, tmp_path, monkeypatch):
```
