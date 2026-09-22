# Diagnostic metier et actions exploratoires

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### DECISION-001 — Retards reconstruits FIFO

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les cohortes journalieres sont servies FIFO ; les demandes ouvertes restent censurees. Le service le jour de la demande est borne, sans inventer un OTIF observe.

Périmètre : Diagnostic et livraison locale des runs existants ou reconstruits.

Unités : Jours, quantites et unites-jours par produit

Limites : Exploratoire, non calibre, sans Monte Carlo apparie ni recommandation industrielle ; voir les conventions du guide.

Sources métier : [DECISION_SUPPORT.md](<../../DECISION_SUPPORT.md>)

Références :

- implementation : [fifo_delay](<../../../decision_support.py#L47>)
- test : [test_fifo_delay_distinguishes_served_and_censored_demand](<../../../test_decision_support.py#L15>)
- test : [test_fifo_rejects_invalid_or_unaged_demand](<../../../test_decision_support.py#L26>)

### DECISION-002 — Score descriptif et pertes dans horizon

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le score retient service et reliquat ; le surcoût est exclu si la valorisation est incomplète ou inconnue et reste indisponible, pas zéro. Pertes matière et reports sans unité commune sont exclus. Les pertes sont rapprochées par article et unité.

Périmètre : Diagnostic et livraison locale des runs existants ou reconstruits.

Unités : Points descriptifs et quantites par unite

Limites : Exploratoire, non calibre, sans Monte Carlo apparie ni recommandation industrielle ; voir les conventions du guide.

Sources métier : [DECISION_SUPPORT.md](<../../DECISION_SUPPORT.md>)

Références :

- implementation : [score_breakdown](<../../../decision_support.py#L104>)
- implementation : [audit_losses](<../../../decision_support.py#L115>)
- test : [test_score_components_exclude_incomparable_quantities](<../../../test_decision_support.py#L36>)
- test : [test_loss_audit_excludes_departures_outside_horizon_and_preserves_units](<../../../test_decision_support.py#L54>)
- test : [test_unknown_cost_is_excluded_and_not_rendered_as_zero_score](<../../../test_decision_support.py#L46>)

### DECISION-003 — Preuves de blocage sans attribution abusive

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les contraintes lient usine, produit et composant ; le graphe donne les fournisseurs. Les liens explicites evenements-lots ne quantifient pas la causalite du retard client.

Périmètre : Diagnostic et livraison locale des runs existants ou reconstruits.

Unités : Jours bloques, identifiants et lignes source

Limites : Exploratoire, non calibre, sans Monte Carlo apparie ni recommandation industrielle ; voir les conventions du guide.

Sources métier : [DECISION_SUPPORT.md](<../../DECISION_SUPPORT.md>)

Références :

- implementation : [bottlenecks](<../../../decision_support.py#L143>)
- test : [test_bottlenecks_use_binding_input_and_explicit_causal_context](<../../../test_decision_support.py#L66>)

### DECISION-004 — Actions isolees et livraison controlee

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les actions sont executees dans un dossier separe. La reprise verifie calendrier, sources, dependances et artefacts ; la livraison refuse les invariants CSV incorrects.

Périmètre : Diagnostic et livraison locale des runs existants ou reconstruits.

Unités : Controles sans dimension et couts du modele

Limites : Exploratoire, non calibre, sans Monte Carlo apparie ni recommandation industrielle ; voir les conventions du guide.

Sources métier : [DECISION_SUPPORT.md](<../../DECISION_SUPPORT.md>)

Références :

- implementation : [execute_action](<../../../decision_actions.py#L17>)
- implementation : [deliver](<../../../decision_support.py#L238>)
- test : [test_action_replays_reference_in_isolated_directory_and_checks_cache](<../../../test_decision_actions.py#L9>)
- test : [test_failed_delivery_does_not_keep_an_old_success](<../../../test_decision_support.py#L91>)
- implementation : [render_report](<../../../decision_support.py#L201>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### fifo

[etudecas/decision_support.py:47](<../../../decision_support.py#L47>)

```python
def fifo_delay(rows, days):
```

Reconstruct daily demand cohorts under FIFO; not observed order-level OTIF.

### score

[etudecas/decision_support.py:104](<../../../decision_support.py#L104>)

```python
def score_breakdown(kpis):
```

Expose the existing score without changing weights or implying calibration.

### loss

[etudecas/decision_support.py:115](<../../../decision_support.py#L115>)

```python
def audit_losses(run, days):
```

Reconcile departures inside the measured horizon, retaining item and unit.

### bottlenecks

[etudecas/decision_support.py:143](<../../../decision_support.py#L143>)

```python
def bottlenecks(run, graph, output):
```

Link recorded input constraints to supplying lanes; no causal inference from proximity.

### delivery

[etudecas/decision_support.py:238](<../../../decision_support.py#L238>)

```python
def deliver(run, execute_actions=False, render_map=False, browser=False):
```

### actions

[etudecas/decision_actions.py:17](<../../../decision_actions.py#L17>)

```python
def execute_action(reference: Path, output: Path, action: str, targets: list[dict]) -> Path:
```

Replay the reference command with one measured-day control schedule.

### fifo-test

[etudecas/test_decision_support.py:15](<../../../test_decision_support.py#L15>)

```python
def test_fifo_delay_distinguishes_served_and_censored_demand():
```

### invalid-test

[etudecas/test_decision_support.py:26](<../../../test_decision_support.py#L26>)

```python
def test_fifo_rejects_invalid_or_unaged_demand(damage):
```

### score-test

[etudecas/test_decision_support.py:36](<../../../test_decision_support.py#L36>)

```python
def test_score_components_exclude_incomparable_quantities():
```

### loss-test

[etudecas/test_decision_support.py:54](<../../../test_decision_support.py#L54>)

```python
def test_loss_audit_excludes_departures_outside_horizon_and_preserves_units(tmp_path):
```

### bottlenecks-test

[etudecas/test_decision_support.py:66](<../../../test_decision_support.py#L66>)

```python
def test_bottlenecks_use_binding_input_and_explicit_causal_context(tmp_path):
```

### actions-test

[etudecas/test_decision_actions.py:9](<../../../test_decision_actions.py#L9>)

```python
def test_action_replays_reference_in_isolated_directory_and_checks_cache(tmp_path, monkeypatch):
```

### delivery-failure-test

[etudecas/test_decision_support.py:91](<../../../test_decision_support.py#L91>)

```python
def test_failed_delivery_does_not_keep_an_old_success(tmp_path, monkeypatch):
```

### reference-sensitivity-labels

[etudecas/decision_support.py:201](<../../../decision_support.py#L201>)

```python
def render_report(output, report, map_path):
```

### unknown-cost-test

[etudecas/test_decision_support.py:46](<../../../test_decision_support.py#L46>)

```python
def test_unknown_cost_is_excluded_and_not_rendered_as_zero_score():
```
