# SCAN 2027 — State-dependent supplier-risk control PoC

## Research question

This prototype is an executable continuation of the 2026 RESILIENCE-SCAN work.
It tests the following question:

> How can an uncertain supplier-risk signal be transformed into a bounded,
> explainable operational response that protects service without creating order
> nervousness, supplier stress or a second disruption?

The PoC is deliberately located under `etudecas/prototypes/`. It reads existing
`etudecas` outputs when they are available, but it does **not** modify the
canonical multi-item MRP engine. It is a reduced-order research bench that
prepares the closed-loop experiments planned for 2027.

## What the PoC implements

### 1. Adapter to the current SCAN work

The script automatically looks for:

- a recent `first_simulation_daily.csv` produced by the physical MRP simulation;
- a supplier-risk prediction CSV when one is available;
- otherwise, a deterministic synthetic fallback that exercises several dynamic
  regimes.

Different existing daily output schemas are aggregated into one reduced state in
**equivalent days of demand**. The source mode and columns are retained in the
run manifest for auditability.

### 2. State-dependent regime diagnosis

The PoC distinguishes:

- `NOMINAL`;
- `MATERIAL_TENSION`;
- `CAPACITY_SATURATION`;
- `SUPPLIER_STRESS`;
- `OSCILLATORY`;
- `CRISIS`;
- `RECOVERY`;
- `POST_CRISIS_OVERSTOCK`.

The diagnosis uses inventory coverage, backlog, capacity utilization, order
nervousness, supplier stress and predicted risk. The same risk score can thus
lead to a different response depending on the actual operating condition.

### 3. Probabilistic scenario propagation

Supplier-risk uncertainty is propagated through correlated scenario paths:

- demand variation;
- supply availability;
- production capacity;
- lead-time variation;
- risk-estimation error.

Every action is compared using the same scenario ensemble and random seed.

### 4. Endogenous supplier risk

The supplier is represented as a dynamic system whose state can be degraded by
our own response:

- abrupt order changes increase nervousness;
- orders above effective capacity increase pressure;
- expediting can add stress;
- smoothing and supplier-relief actions can reduce stress;
- stress feeds a future supplier-risk probability.

The objective includes a **Risk Creation Index**: the additional supplier risk
created by a candidate response relative to the MRP reference.

### 5. Bounded response playbooks

The PoC compares six transparent actions:

- `mrp_reference`;
- `reactive_buffer`;
- `service_protection`;
- `supplier_relief`;
- `balanced_robust`;
- `recovery_damping`.

The action library is filtered by the diagnosed regime. Order, production and
expediting changes are bounded by explicit safety limits.

### 6. Scenario-based robust selector

For each candidate, the PoC computes:

- expected objective;
- tail objective using a CVaR-style metric;
- service loss and backlog area;
- inventory excess and shortfall;
- order nervousness;
- supplier-risk area and Risk Creation Index;
- action magnitude and constraint violations.

The selected action minimizes expected loss plus a tail-risk penalty. This is a
transparent precursor to Scenario/Tube MPC, not a claim of optimal control.

### 7. Observability and controllability proxies

At every step, the PoC estimates:

- **observability**: whether available data and forecast uncertainty are
  sufficient to understand the state;
- **controllability**: whether inventory, production and supplier headroom still
  provide effective recovery levers.

These metrics are used for diagnosis and future integration with a safety layer.

### 8. Additional forward-looking research outputs

The run also derives:

- active non-smooth constraints (inventory floor, capacity binding, order cap,
  service floor, backlog/risk limits);
- an adaptive model-detail level;
- a supplier-impedance spectrum linking order changes to supplier response;
- a regime-transition matrix.

These outputs implement the main 2026–2027 research perspectives in one
self-contained demonstration.

## Quick start

From the repository root:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_scan_2027_poc.py
```

Force the synthetic demonstration:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_scan_2027_poc.py `
  --synthetic `
  --days 180 `
  --seed 2027
```

Use explicit existing outputs:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_scan_2027_poc.py `
  --baseline-csv etudecas/simulation/result/<run>/data/first_simulation_daily.csv `
  --risk-csv etudecas/prototypes/prediction/result/predicted_supplier_item_risk.csv `
  --output-dir etudecas/prototypes/scan_2027_risk_control/outputs/my_run
```

Skip figures for a fast batch run:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_scan_2027_poc.py --synthetic --no-plots
```

## Output package

Each run creates:

```text
<output>/
├── run_manifest.json
├── poc_report.md
├── data/
│   ├── input_series.csv
│   ├── adaptive_state_trajectory.csv
│   ├── policy_decisions.csv
│   ├── candidate_policy_evaluations.csv
│   ├── policy_comparison.csv
│   ├── fixed_policy_trajectories.csv
│   ├── regime_transition_matrix.csv
│   ├── active_constraints.csv
│   ├── adaptive_state_space.csv
│   └── supplier_impedance_spectrum.csv
└── plots/
    ├── adaptive_state_trajectory.png
    ├── regime_timeline.png
    ├── adaptive_policy_selection.png
    ├── policy_frontier.png
    ├── risk_creation_index_by_policy.png
    ├── supplier_risk_endogenous.png
    ├── observability_controllability_map.png
    ├── active_constraints.png
    ├── adaptive_state_space_level.png
    ├── supplier_impedance_spectrum.png
    └── regime_transition_matrix.png
```

## Tests

```powershell
python -m unittest discover `
  -s etudecas/prototypes/scan_2027_risk_control/tests `
  -v
```

The tests verify:

- crisis-regime detection;
- the hypothesis that aggressive protection can create more endogenous supplier
  risk than a supplier-relief policy;
- a complete synthetic smoke run and its output contract.

## Scientific claims and limits

### What this PoC demonstrates

- risk must be translated into physical uncertainty, not used as a direct
  decision;
- the preferred response depends on the operating regime;
- the response can create supplier risk through order nervousness;
- scenario-based selection can compare bounded playbooks on a common basis;
- observability and controllability can be monitored alongside service KPIs.

### What it does not yet demonstrate

- industrially calibrated supplier-stress equations;
- guaranteed stability of the full multi-tier network;
- an optimized MPC controller;
- closed-loop write-back into the canonical MRP simulation;
- causal identification from real supplier data.

## Planned continuation

### End of 2026

1. Calibrate regimes and thresholds on canonical `etudecas` trajectories.
2. Connect supplier-item-site prediction intervals to physical risk scenarios.
3. Replay selected actions in the full multi-item engine using paired seeds.
4. Measure false-positive and false-negative decision consequences.
5. Validate Risk Creation Index and supplier-stress proxies with business
   experts.

### 2027

1. Replace the finite selector with Scenario/Tube MPC.
2. Build conformal or distributionally robust uncertainty sets.
3. Add explicit stock, backlog, capacity and nervousness safety constraints.
4. Estimate supplier impedance from controlled virtual perturbations.
5. Integrate observability/controllability and adaptive model granularity.
6. Operationalize the PoC as a reusable simulation and decision-support module.
