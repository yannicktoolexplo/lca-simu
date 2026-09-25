# Contrats des entrées et de l'API HTTP de simulation

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### SIMULATION-INPUT-001 — Interpréter les valeurs sans conversions ambiguës

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le parseur de dictionnaire exige des booléens réels, des jours et graines entiers non négatifs, et des multiplicateurs finis non négatifs. Il refuse les champs inconnus et exige une seule source de graphe.

Périmètre : request_from_dict ; les objets internes construits directement ne passent pas par ce parseur.

Unités : Jours, graines entières et multiplicateurs sans dimension.

Limites : Zéro jour conserve la convention Python historique ; les planchers et effets physiques des multiplicateurs restent définis dans le moteur.

Sources métier : [SIMULATION_INPUT_CONTRACT.md](<../../SIMULATION_INPUT_CONTRACT.md>)

Références :

- implementation : [request_from_dict](<../../../simulation/engine/api.py#L197>)
- implementation : [_float_mapping](<../../../simulation/engine/api.py#L148>)
- implementation : [_bool_mapping](<../../../simulation/engine/api.py#L167>)
- implementation : [overrides_from_dict](<../../../simulation/engine/api.py#L177>)
- test : [test_request_rejects_coercions](<../../../tests/moteur/test_request_contract.py#L14>)
- test : [test_scales_require_finite_nonnegative_numbers](<../../../tests/moteur/test_request_contract.py#L20>)
- test : [test_false_zero_and_internal_controls_are_preserved](<../../../tests/moteur/test_request_contract.py#L32>)

### SIMULATION-INPUT-002 — Réserver le moteur et les sorties au serveur

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

HTTP impose le moteur et un nouveau dossier de résultats, refuse les arguments moteur libres et contrôle les chemins résolus sous la racine d'entrée. Le scénario doit exister et l'horizon être explicite et borné.

Périmètre : POST /simulate du serveur local.

Unités : Chemins locaux, jours, identifiants de scénario et de run.

Limites : Pas de protection contre une modification concurrente des fichiers par un acteur local. Le contrat Python interne conserve ses options de confiance.

Sources métier : [SIMULATION_INPUT_CONTRACT.md](<../../SIMULATION_INPUT_CONTRACT.md>)

Références :

- implementation : [request_from_http](<../../../simulation/engine/http_contract.py#L41>)
- implementation : [confined_file](<../../../simulation/engine/http_contract.py#L21>)
- contract : [HTTP_FIELDS](<../../../simulation/engine/http_contract.py#L13>)
- test : [test_http_rejects_internal_fields_and_unbounded_horizon](<../../../tests/moteur/test_http_contract.py#L24>)
- test : [test_http_paths_cannot_escape_input_root](<../../../tests/moteur/test_http_contract.py#L42>)
- test : [test_http_assigns_engine_and_unique_output_without_writing](<../../../tests/moteur/test_http_contract.py#L32>)

### SIMULATION-INPUT-003 — Contrôler l'accès local et les exécutions simultanées

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le serveur local exige un jeton pour simuler, contrôle l'origine et l'hôte, limite le corps, réserve un seul créneau et applique un délai au sous-processus moteur. Les erreurs libèrent le créneau et ne sont pas annoncées comme succès.

Périmètre : Service HTTP local avec configuration contrôlée par son opérateur.

Unités : Octets, secondes et nombre de simulations concurrentes.

Limites : Le délai ne couvre pas tout le prétraitement ni les descendants éventuels du moteur. Ni la mémoire, ni les sorties, ni le nombre de connexions ne sont bornés. Outil local uniquement.

Sources métier : [SIMULATION_INPUT_CONTRACT.md](<../../SIMULATION_INPUT_CONTRACT.md>)

Références :

- implementation : [SimulationApiServer](<../../../simulation/engine/server.py#L24>)
- implementation : [SimulationApiHandler._check_origin_and_host](<../../../simulation/engine/server.py#L105>)
- implementation : [SimulationApiHandler.do_POST](<../../../simulation/engine/server.py#L128>)
- implementation : [run_simulation_bounded](<../../../simulation/engine/bounded_execution.py#L9>)
- test : [test_http_rejects_before_simulation](<../../../tests/moteur/test_http_contract.py#L102>)
- test : [test_busy_and_timeout_release_slot](<../../../tests/moteur/test_http_contract.py#L128>)
- test : [test_real_subprocess_timeout](<../../../tests/moteur/test_http_contract.py#L158>)
- test : [test_partial_body_times_out_and_releases_slot](<../../../tests/moteur/test_http_contract.py#L145>)

### SIMULATION-INPUT-004 — Rapporter les graphes mal formés et les nombres non finis

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le validateur retourne des erreurs structurées pour les conteneurs et lignes invalides. Les champs numériques qu'il contrôle doivent être finis et ne peuvent pas être des booléens. Stocks et ratios BOM negatifs, articles absents et arcs sans extremites sont refuses.

Périmètre : Contrat de graphe, moteur CLI et API Python/HTTP.

Unités : Unités des articles pour les stocks et quantités ; jours ; ratios de nomenclature.

Limites : Les chaînes numériques finies restent acceptées dans le graphe. Ce contrôle ne couvre pas tous les champs moteur et ne démontre ni conservation physique ni validité scientifique.

Sources métier : [SIMULATION_INPUT_CONTRACT.md](<../../SIMULATION_INPUT_CONTRACT.md>)

Références :

- implementation : [validate_graph_contract](<../../../knowledge_graph/schema.py#L29>)
- implementation : [_validate_shapes](<../../../knowledge_graph/schema.py#L166>)
- implementation : [_is_number](<../../../knowledge_graph/schema.py#L157>)
- test : [test_nonfinite_inventory_is_rejected](<../../../knowledge_graph/test_schema_contract.py#L12>)
- test : [test_malformed_top_level_rows_return_issues](<../../../knowledge_graph/test_schema_contract.py#L20>)
- test : [test_malformed_nested_rows_return_issues](<../../../knowledge_graph/test_schema_contract.py#L29>)
- test : [test_valid_graph_validation_does_not_mutate_input](<../../../knowledge_graph/test_schema_contract.py#L35>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### parser

[etudecas/simulation/engine/api.py:197](<../../../simulation/engine/api.py#L197>)

```python
def request_from_dict(payload: dict[str, Any]) -> SimulationRequest:
```

Parse trusted Python/JSON input without coercing strings into booleans.

Internal paths and engine arguments remain available here; HTTP applies its
narrower contract before calling this parser. Zero days means graph horizon.

### scales

[etudecas/simulation/engine/api.py:148](<../../../simulation/engine/api.py#L148>)

```python
def _float_mapping(value: Any) -> dict[str, float]:
```

### flags

[etudecas/simulation/engine/api.py:167](<../../../simulation/engine/api.py#L167>)

```python
def _bool_mapping(value: Any) -> dict[str, bool]:
```

### overrides

[etudecas/simulation/engine/api.py:177](<../../../simulation/engine/api.py#L177>)

```python
def overrides_from_dict(payload: dict[str, Any] | None) -> SimulationOverrides:
```

### http

[etudecas/simulation/engine/http_contract.py:41](<../../../simulation/engine/http_contract.py#L41>)

```python
def request_from_http(payload, *, input_root: Path, output_root: Path, max_days: int=3660):
```

### path

[etudecas/simulation/engine/http_contract.py:21](<../../../simulation/engine/http_contract.py#L21>)

```python
def confined_file(value, root: Path, suffix: str) -> Path:
```

### fields

[etudecas/simulation/engine/http_contract.py:13](<../../../simulation/engine/http_contract.py#L13>)

```python
HTTP_FIELDS = frozenset({'input_graph', 'input_path', 'scenario_id', 'days', 'output_profile', 'overrides', 'run_lot_audit', 'seed', 'common_random_numbers', 'control_schedule_csv', 'control_policy_json', 'demand_perturbation_csv', 'skip_map', 'skip_plots'})
```

### server

[etudecas/simulation/engine/server.py:24](<../../../simulation/engine/server.py#L24>)

```python
class SimulationApiServer
```

### origin

[etudecas/simulation/engine/server.py:105](<../../../simulation/engine/server.py#L105>)

```python
def _check_origin_and_host(self):
```

### post

[etudecas/simulation/engine/server.py:128](<../../../simulation/engine/server.py#L128>)

```python
def do_POST(self):
```

### bounded

[etudecas/simulation/engine/bounded_execution.py:9](<../../../simulation/engine/bounded_execution.py#L9>)

```python
def run_simulation_bounded(run_script: Path, input_json: Path, output_dir: Path, scenario_id: str, days: int=0, skip_map: bool=True, skip_plots: bool=True, extra_args: list[str] | None=None, use_living_initial_state: bool=True, *, timeout_seconds: float) -> tuple[dict[str, Any], str]:
```

### graph

[etudecas/knowledge_graph/schema.py:29](<../../../knowledge_graph/schema.py#L29>)

```python
def validate_graph_contract(graph: dict[str, Any]) -> list[dict[str, str]]:
```

### shapes

[etudecas/knowledge_graph/schema.py:166](<../../../knowledge_graph/schema.py#L166>)

```python
def _validate_shapes(graph: dict[str, Any]) -> list[dict[str, str]]:
```

Report malformed containers before inspecting their business fields.

### numeric

[etudecas/knowledge_graph/schema.py:157](<../../../knowledge_graph/schema.py#L157>)

```python
def _is_number(value: Any) -> bool:
```

### types-test

[etudecas/tests/moteur/test_request_contract.py:14](<../../../tests/moteur/test_request_contract.py#L14>)

```python
def test_request_rejects_coercions(field, value):
```

### scales-test

[etudecas/tests/moteur/test_request_contract.py:20](<../../../tests/moteur/test_request_contract.py#L20>)

```python
def test_scales_require_finite_nonnegative_numbers(value):
```

### false-test

[etudecas/tests/moteur/test_request_contract.py:32](<../../../tests/moteur/test_request_contract.py#L32>)

```python
def test_false_zero_and_internal_controls_are_preserved():
```

### forbidden-test

[etudecas/tests/moteur/test_http_contract.py:24](<../../../tests/moteur/test_http_contract.py#L24>)

```python
def test_http_rejects_internal_fields_and_unbounded_horizon(tmp_path, field, value):
```

### paths-test

[etudecas/tests/moteur/test_http_contract.py:42](<../../../tests/moteur/test_http_contract.py#L42>)

```python
def test_http_paths_cannot_escape_input_root(tmp_path, field):
```

### unique-test

[etudecas/tests/moteur/test_http_contract.py:32](<../../../tests/moteur/test_http_contract.py#L32>)

```python
def test_http_assigns_engine_and_unique_output_without_writing(tmp_path):
```

### access-test

[etudecas/tests/moteur/test_http_contract.py:102](<../../../tests/moteur/test_http_contract.py#L102>)

```python
def test_http_rejects_before_simulation(tmp_path, monkeypatch, headers, status):
```

### busy-test

[etudecas/tests/moteur/test_http_contract.py:128](<../../../tests/moteur/test_http_contract.py#L128>)

```python
def test_busy_and_timeout_release_slot(tmp_path, monkeypatch):
```

### deadline-test

[etudecas/tests/moteur/test_http_contract.py:158](<../../../tests/moteur/test_http_contract.py#L158>)

```python
def test_real_subprocess_timeout(tmp_path):
```

### partial-test

[etudecas/tests/moteur/test_http_contract.py:145](<../../../tests/moteur/test_http_contract.py#L145>)

```python
def test_partial_body_times_out_and_releases_slot(tmp_path):
```

### finite-test

[etudecas/knowledge_graph/test_schema_contract.py:12](<../../../knowledge_graph/test_schema_contract.py#L12>)

```python
def test_nonfinite_inventory_is_rejected(value):
```

### shape-test

[etudecas/knowledge_graph/test_schema_contract.py:20](<../../../knowledge_graph/test_schema_contract.py#L20>)

```python
def test_malformed_top_level_rows_return_issues(field, value):
```

### nested-test

[etudecas/knowledge_graph/test_schema_contract.py:29](<../../../knowledge_graph/test_schema_contract.py#L29>)

```python
def test_malformed_nested_rows_return_issues(node):
```

### immutable-test

[etudecas/knowledge_graph/test_schema_contract.py:35](<../../../knowledge_graph/test_schema_contract.py#L35>)

```python
def test_valid_graph_validation_does_not_mutate_input():
```
