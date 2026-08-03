# SCAN 2027 — State-dependent supplier-risk control PoC

## Research question

This prototype is an executable continuation of the 2026 RESILIENCE-SCAN work.
It tests the following question:

> How can an uncertain supplier-risk signal be transformed into a bounded,
> explainable operational response that protects service without creating order
> nervousness, supplier stress or a second disruption?

The decision layer remains deliberately located under `etudecas/prototypes/`.
It reads existing `etudecas` outputs and retains a reduced-order research bench,
while the end-2026 validation runner can now pass a bounded, auditable daily
control schedule to the canonical multi-item MRP engine. That schedule is
precomputed: the canonical replay is daily open loop and is not presented as
state-feedback closed-loop control.

## What the PoC implements

### 1. Adapter to the current SCAN work

The script automatically looks for:

- a recent `first_simulation_daily.csv` produced by the physical MRP simulation;
- a supplier-risk prediction CSV, preferring supplier-item-destination rows when
  identifiers are available;
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
    ├── forecast_action_stress_risk_service_chain.png
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
python -m pytest `
  etudecas/prototypes/scan_2027_risk_control/tests `
  -q

python -m pytest `
  etudecas/simulation/test_control_schedule.py `
  etudecas/simulation/test_control_schedule_engine_integration.py `
  etudecas/simulation/test_engine_api.py `
  etudecas/simulation/test_engine_contracts.py `
  etudecas/test_run_etudecas_pipeline.py `
  -q
```

The first command runs the complete scientific prototype suite, including both
`unittest.TestCase` and pytest-style tests; the second covers the typed
daily-control port and its engine/pipeline integration. Together they verify,
among other contracts:

- crisis-regime detection;
- the hypothesis that aggressive protection can create more endogenous supplier
  risk than a supplier-relief policy;
- real-output schema ingestion and explicit fallback provenance;
- expert regime-annotation validation and confidence-weighted voting;
- monotone probability-to-physical-risk mappings;
- paired seeds, adaptive and retrospective-oracle comparisons, and an exactly
  zero MRP-reference delta;
- censoring-aware reduced-model recovery exports (observed duration or
  right-censored lower bound/follow-up); trajectories without any backlog or
  service disruption are explicitly `not_applicable_no_disruption`, and
  recovery deltas are restricted to pairs where both durations are observed;
  a single non-reference pair reports a non-estimable 95% interval instead of
  a zero-width interval;
- TP/FP/FN/TN experiments and multi-expert RCI agreement;
- canonical schedule validation, bounds and engine integration;
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
- online state-feedback recomputation inside the canonical MRP simulation;
- causal identification from real supplier data.

## Remaining validation evidence

The six end-2026 work packages are executable. They are not all industrially
validated. The remaining evidence is:

1. representative procurement/planning regime annotations over real incidents;
2. incident-based calibration and sensitivity of prediction-to-physics
   coefficients;
3. a consolidated paired canonical campaign with 20–30 seeds, then 50+;
4. empirical alert-error frequencies and threshold/width/duration sensitivity;
5. procurement and planning review of the RCI, followed by explicit sign-off;
6. online state-feedback recomputation before using the term closed loop.

### 2027 research direction

1. Replace the finite selector with Scenario/Tube MPC.
2. Extend the current marginal binary-outcome score calibration to conditional
   predictive sets or distributionally robust uncertainty sets, and separately
   estimate uncertainty in the latent incident probability.
3. Add explicit stock, backlog, capacity and nervousness safety constraints.
4. Estimate supplier impedance from controlled virtual perturbations.
5. Integrate observability/controllability and adaptive model granularity.
6. Operationalize the PoC as a reusable simulation and decision-support module.

---

## End-2026 validation work package

The six activities previously listed as future work now have an executable
orchestration script:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_end_2026_validation.py
```

For a fast self-contained check:

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_end_2026_validation.py `
  --synthetic `
  --days 84 `
  --paired-seed-count 4 `
  --confusion-seed-count 3 `
  --canonical-replay off
```

Each end-2026 manifest contains a machine-readable `provenance` block. It
classifies a canonical case-study baseline as
`etudecas_case_simulation_output` / `non_industrial`; it does not call that
baseline an industrial observation. For prediction files, sibling
`manifest.json` and `prediction_poc_report.md` evidence is inspected. When that
evidence identifies synthetic history, labels or temporal features, the
forecast is classified as `synthetic_prediction_poc` with status
`retrospective_synthetic_non_deployment`. SHA-256 values are exported for the
baseline, risk file and calibration file, together with a deterministic SCAN
execution-source snapshot hash and git HEAD, branch and dirty state when
available. The snapshot covers the SCAN package, canonical engine Python
sources, pipeline adapter and sensitivity adapter, including uncommitted
worktree bytes. Both Markdown reports reproduce this provenance.

### A. Regime calibration on simulated `etudecas` trajectories

The runner discovers the canonical case-study simulation output and its sibling
artifacts when available:

- production constraints;
- supplier capacity utilization;
- state-triggered supplier-risk events;
- factory nervousness;
- detailed input stocks and consumption.

Regime thresholds are calibrated with robust trajectory anchors and exported in
`config/calibrated_config.json`. Material tension is calculated from the low-tail
cover of active factory-item pairs when detailed files exist; aggregate inventory
is retained only as an explicitly marked fallback. Missing or gapped material
cover remains unknown and can never trigger `MATERIAL_TENSION` by itself; a
finite measured zero remains a real stockout. The evidence file has exactly one
row for each of the eight regimes, including `NOMINAL`, and records the executed
rule, variables, before/after thresholds, separation, confidence and limitations.
Both calibration and the operational reduced model call the same ordered regime
classifier, so priorities and threshold boundaries are identical.
Confidence is reported by complete regime rule. `NOMINAL` is the ordered
fallthrough after all positive predicates fail; its retained legacy
`supplier_stress` scalar is an exclusion-boundary diagnostic and is never
displayed as a high-confidence NOMINAL threshold. The threshold comparison plot
expands only executable positive-rule threshold maps.

The manifest and reports also expose `calibration_risk_source`. A value of
`forecast_fallback` means the discovered canonical state/applied-risk files did
not supply a nonzero event trajectory on the selected slice, so regime risk
anchors use the forecast proxy. It is never described as observed industrial
incident evidence.

The physical case-study daily file aggregates inventory, arrivals and
production across articles and bill-of-material levels, while demand is a
finished-product signal. Their raw ratios are therefore not assumed to share a
unit. For `etudecas_baseline`, SCAN retains the declared reduced-model nominal
parameters and exports the saturated aggregate refit candidate as
`diagnostic_only_not_applied`. The manifest and both reports expose the status,
declared values, diagnostic candidate, effective values and the missing unit
comparability assumption. A quantile refit is applied only to the internally
normalized `synthetic_fallback` model; those values remain synthetic research
hypotheses, not industrial estimates.

Without an annotation file this is explicitly a **pseudo-label calibration**.
Optional business annotations can be supplied with
`--regime-annotations-csv`. The strict schema is:
`day` or `period`, `site`/`site_id`, `item`/`article`/`item_id`,
`validated_regime`, `expert_confidence` in `[0, 1]`, and `comment`.
Conflicting daily annotations are combined by confidence-weighted vote; ties
fall back to the visible pseudo-label. The frame and manifest preserve
`pseudo_regime`, `business_validated_regime`, `regime_label_source`, coverage,
conflicts and provenance. Resolved days receive business-label provenance, but
the current thresholds are not automatically refitted on those labels; the
overall calibration therefore remains unvalidated until a representative
labelled sample is reviewed.

A dated `period` is accepted only when the baseline exposes a coherent explicit
calendar origin. The offset is then computed from that origin and annotations
outside the simulated horizon remain unapplied and auditable. Without such an
origin the loader rejects dated annotations; it never treats the earliest
annotation as simulation day zero. Integer simulation `day` values remain the
portable format when a baseline has no calendar.

Recovery by regime is reported as a descriptive episode measure on the reduced
adaptive trajectory. An episode starts on its first observed non-`NOMINAL` day
and ends at the first day of seven consecutive observed `NOMINAL` days; shorter
nominal spells remain inside the episode. Episodes are grouped by their entry
regime. Incomplete end-of-horizon episodes are explicitly right-censored, and
an episode already active on the first day is marked left-truncated.
`regime_recovery_episodes.csv` preserves exact durations separately from
censored lower bounds. The accompanying figure is exploratory and does not
attribute a causal recovery effect to a regime.

```powershell
python etudecas/prototypes/scan_2027_risk_control/run_scan_continuation.py `
  --stage all `
  --regime-annotations-csv <regime_annotations.csv> `
  --canonical-replay overlay
```

### B. Prediction intervals converted into physical disturbances

The current supplier-item-site prediction outputs are converted into:

- an incident-probability centre plus lower / upper operational-envelope paths;
- availability multipliers;
- supplier-capacity multipliers;
- additional lead-time days;
- quality-yield multipliers;
- purchase- and transport-cost multipliers.

The combined exports contain both `scope=portfolio` rows, consumed by the
reduced-order controller, and `scope=supplier_item_destination` rows keyed by
`supplier_id`, `item_id` and `dst_node_id`. Dedicated portfolio-only files are
also written for simple downstream use; granular rows are never silently
discarded from the combined files.

When `prediction_test_scored_rows.csv` contains binary incident outcomes, the
score `|Y - p_hat|` is calibrated with the split-conformal finite-sample rank
`k = ceil((n + 1) * (1 - alpha))`. This construction concerns marginal
membership of a **future binary outcome** in the score envelope, under
exchangeability and with a predictor fixed independently of the calibration
rows. It is not a confidence interval for the latent probability
`P(Y=1 | X)`. It also supplies no coverage claim for portfolio selection or
aggregation, forecast-horizon transformations, or the mapped physical effects.

A finite calibration quantile is used only when `k <= n`. If `k > n` (for
example `n=1..8` at requested 90% coverage), the code does not cap the rank at
the largest observed score: it exports
`not_estimable_requested_rank_exceeds_calibration_size` and uses an explicitly
nonconformal `assumption_envelope`. A missing probability column and all other
fallback paths are likewise labelled `assumption_envelope`, with no nominal
coverage value.

The manifest distinguishes `requested_nominal_coverage` from
`effective_finite_sample_level = k / (n + 1)`, and also reports the requested
rank, the maximum attainable finite-sample level `n / (n + 1)`, the covered
target and the limitations. `empirical_calibration_coverage` is retained for
compatibility but is explicitly labelled as an in-sample calibration-score
inclusion rate, not independent predictive coverage. A source-provided interval
is identified separately when its semantics and coverage were not evaluated.
Before estimating the score quantile, exact rows shared by the operational target
snapshot and scored calibration set are excluded when both a temporal key and a
complete lane identity are available. The manifest reports
`calibration_rows_before`, `calibration_rows_after`, `excluded_overlap_rows`, the
matching keys, operational snapshot row count and unique probability count. No
weak supplier-only match is removed. These disclosures do not turn retrospective
synthetic evaluation into deployment evidence or into an interval for latent
`P(Y=1 | X)`.
After the predictor validity window (30 days by default), the centre decays
toward a configurable long-horizon prior and the operational-envelope span is
constrained to be non-decreasing, up to saturation at `[0, 1]`.

Existing uncertainty penalties and impact proxies are retained. Every physical
coefficient remains configurable and is reported as a research mapping pending
calibration on real incidents. One-at-a-time coefficient perturbations from
`--mapping-sensitivity-factors` are exported in
`physical_mapping_coefficient_sensitivity.csv`.

For canonical replay, the latest high-priority supplier-item-factory pairs are
translated into an auditable `canonical_supplier_risk_events.csv` using the
configured predictor validity horizon. When a graph is available, exact
supplier-item-destination compatibility is checked before selection:
incompatible high-priority rows are recorded as rejected and the requested
selection is refilled from the next compatible rows. Selected events carry the
canonical edge identifier. Pair-specific physical envelopes are used when
available; a portfolio proxy is retained only with explicit fallback provenance.

### C. Canonical action reinjection

Three modes are available:

```powershell
# Prepare daily schedules, ledgers and compatibility overlays only
python etudecas/prototypes/scan_2027_risk_control/run_end_2026_validation.py `
  --canonical-replay overlay

# Execute the full multi-item MRP engine with paired seeds
python etudecas/prototypes/scan_2027_risk_control/run_end_2026_validation.py `
  --canonical-replay run `
  --canonical-seed-count 3 `
  --canonical-engine-profile `
    etudecas/prototypes/scan_2027_risk_control/config/canonical_real_baseline_engine_profile.json

# Skip the full-engine stage
python etudecas/prototypes/scan_2027_risk_control/run_end_2026_validation.py `
  --canonical-replay off
```

The canonical schedule exposes bounded daily levers for:

- MRP order quantity after the base need calculation and before lane
  lotification;
- safety-stock targets;
- production targets before lotification, campaign and capacity constraints;
- factory and supplier capacity;
- external-procurement headroom;
- expedite level and lead-time adjustment;
- multi-source priority weight.

The optional engine profile is a versioned list of baseline physics and
initialization arguments. It is passed as an argument vector, never through a
shell, and is hashed into replay metadata. It cannot override the graph, output,
horizon, seed, common-random-number mode, risk-event file or control schedule.
Leaving it blank preserves the graph-default behavior.

Every scheduled lever is reconciled in `canonical_action_ledger.csv` with
requested and effective values, bound status, source scope, action stage,
quantity chain and binding reason. Statuses distinguish physical application,
neutral or zero-flow resolution, absence of relative allocation effect, and a
schedule row that did not reach a compatible physical stage. The quantitative
chain keeps the neutral MRP need, safety/order/supplier controls, constraints,
lotification and executable receipt separate. Every fixed policy and the
adaptive day-by-day schedule starts from the same untouched graph,
supplier-risk events and paired random-number streams.
`mrp_reference` deliberately exercises the historical no-schedule path. The
legacy graph overlays remain in `overlay` packages for compatibility only; they
are not combined with daily schedules in executable replays.

### D. Paired-seed policy comparison

Every playbook is compared against `mrp_reference` with common random numbers.
The package reports paired means, 95% intervals, p90 deltas and win rates for:

- service and backlog;
- recovery time and inventory/overstock;
- order and production nervousness;
- expedite and external procurement;
- capacity violations, quality loss, RCI and economic exposure.

The reference policy must have exactly zero paired delta; this is enforced by a
unit test. Reduced-order experiments report the adaptive policy and a
retrospective best-fixed oracle on the same physical seed. Canonical results also
include a clearly marked `run_kind=derived_oracle` row selected ex post from the
already executed fixed-policy results for that seed. It is not an additional
engine run, and no online oracle policy is claimed.

The reduced paired and confusion benches may consume demand and risk paths from
the simulated etudecas case, but they reconstruct initial stocks, pipeline and
subsequent dynamics in equivalent demand-days. They are therefore hypothesis
tests, not replays of article/BOM physical states. The separately identified
canonical-engine campaign provides the multi-product physical-integration
evidence.

Recovery metrics in both reduced and canonical comparisons distinguish an
observed seven-day stable return, a right-censored lower bound, and
`not_applicable_no_disruption`. A service-only episode is anchored at minimum
service rather than an artificial zero-backlog peak. Recovery deltas and
confidence intervals are estimated only from pairs with two observed recovery
times; MRP self-deltas remain exactly zero even when duration is not estimable.

### E. Explicit false-positive / false-negative experiments

Forecast and physical truth are separated into four cases:

| Case | Forecast | Physical event |
|---|---:|---:|
| TP | yes | yes |
| FP | yes | no |
| FN | no | yes |
| TN | no | no |

The same physical random path is used where comparisons require it. The action
channel is explicit: `mrp_reference` remains active without an alert, while the
bounded `--confusion-alert-response-policy` (default `balanced_robust`) is
applied only for the declared alert window. Results include service, backlog,
unused stock/overstock, over-ordering, order nervousness, expediting, cost,
supplier stress/risk and regret relative to both a correct-forecast oracle and
MRP. A configurable full-factorial grid over alert threshold, interval
half-width and event duration is written to
`forecast_confusion_sensitivity.csv` and summarized in
`forecast_alert_threshold_regret.png`. Forecast and physical truth
probabilities stay fixed across the threshold grid. The interval upper bound
grades the bounded response magnitude, so width affects the operational
trajectory instead of only an observability label. This identifies the
asymmetric cost of acting on a false alert versus missing a real supplier event.

### F. Procurement and planning validation of the RCI

The runner creates:

- `rci_business_review_template.csv` with model outputs;
- `rci_business_review_blind.csv` for unbiased review, deterministically
  shuffled and stripped of RCI, controller-selection, ranking, and
  selected-window signals;
- `rci_business_variable_dictionary.csv`;
- `rci_business_validation_guide.md`;
- `rci_business_validation_status.json`.

All candidate playbooks are included, not only the selected response. This avoids
selection bias and exposes high-RCI counterfactuals such as aggressive buffering.
Procurement and planning reviewers independently classify whether each action
could create supplier stress or planning instability. Once a completed file is
passed with `--business-review-csv`, the script estimates an RCI threshold,
precision, recall, F1, accuracy, false positives/negatives and rank correlation
with plausibility ratings. Long-format reviews retain `episode_id` and
`reviewer_id`; agreement is reported with Cohen's kappa for two reviewers and
Fleiss' kappa for larger complete panels.

The workshop validates only the reduced-order proxy scoped as
`scan_reduced_order_policy_model`, formula version
`scan.reduced_risk_creation_area.v1`. Canonical replays expose the separate
`canonical_risk_creation_proxy`, version
`scan.canonical_weighted_six_component_rci.v1`, while retaining
`risk_creation_index` only as a compatibility alias. Their formulas, scales,
rankings, and thresholds are not transferable without a dedicated alignment
study.

Review-pack identity uses schema `scan.rci_business_review_pack.v2`. Before
hashing, finite numeric `model_rci*` values are canonicalized to 12 significant
decimal digits. This preserves the same identity after both standard pandas CSV
parsing and `float_precision="round_trip"`, while edits at or above the declared
canonical precision still invalidate the pack. Schema-v1 review files are stale
and must be regenerated.

Until a complete review is supplied, the manifest correctly reports
`pending_business_review`. A complete, structurally valid expert panel produces
`review_available`, keeps tied votes unresolved, and separates in-sample
threshold fit from leave-one-episode-out performance. Neither status claims
industrial validation; explicit business governance sign-off is still required.
Only in that `review_available` state, reporting creates
`rci_model_vs_business_evaluations.png`: four direct comparisons of model RCI
with expert risk, plausibility, supplier-pressure and planning-nervousness
ratings. No composite expert score or placeholder point is produced while the
review remains pending.

### End-2026 output additions

```text
<output>/
├── end_2026_validation_report.md
├── rci_business_validation_guide.md
├── rci_business_validation_status.json
├── config/calibrated_config.json
├── data/
│   ├── regime_calibration_frame.csv
│   ├── regime_calibration_evidence.csv
│   ├── regime_thresholds_before_after.csv
│   ├── regime_transition_matrix.csv
│   ├── regime_recovery_episodes.csv
│   ├── prediction_interval_envelope.csv
│   ├── physical_risk_envelope.csv
│   ├── portfolio_prediction_interval_envelope.csv
│   ├── portfolio_physical_risk_envelope.csv
│   ├── physical_mapping_coefficient_sensitivity.csv
│   ├── paired_policy_runs.csv
│   ├── paired_policy_summary.csv
│   ├── forecast_confusion_runs.csv
│   ├── forecast_confusion_summary.csv
│   ├── forecast_confusion_regret.csv
│   ├── forecast_confusion_sensitivity.csv
│   ├── rci_business_review_template.csv
│   ├── rci_business_review_blind.csv
│   ├── rci_business_variable_dictionary.csv
│   ├── canonical_runs.csv
│   ├── canonical_paired_summary.csv
│   └── canonical_control_overlays.csv
├── canonical_replay/
│   ├── adaptive_control_schedule.csv
│   ├── canonical_control_overlays.csv
│   ├── canonical_supplier_risk_events.csv
│   ├── canonical_risk_mapping_ledger.csv
│   ├── canonical_action_ledger.csv
│   └── <policy>/
│       ├── canonical_control_schedule.csv
│       └── seed_<seed>/data/canonical_action_ledger.csv
├── plots/forecast_action_stress_risk_service_chain.png
└── plots/end_2026/
    ├── regime_calibration_trajectory.png
    ├── regime_separation_map.png
    ├── regime_threshold_comparison.png
    ├── regime_recovery_time_by_entry_regime.png
    ├── prediction_interval.png
    ├── prediction_to_physical_perturbations.png
    ├── physical_availability_fan_chart.png
    ├── physical_capacity_fan_chart.png
    ├── paired_policy_comparison.png
    ├── paired_policy_forest_plot.png
    ├── paired_interval_convergence.png
    ├── service_stock_nervousness_risk_frontier.png
    ├── forecast_confusion_cases.png
    ├── forecast_error_regret.png
    ├── forecast_confusion_cost_matrix.png
    ├── forecast_alert_threshold_regret.png
    ├── rci_business_review_episodes.png
    ├── rci_model_vs_business_evaluations.png  # only with a complete review
    ├── canonical_mrp_vs_adaptive_trajectory.png
    ├── canonical_order_production_nervousness.png
    └── canonical_paired_replay.png
```

Executable canonical runs additionally emit `canonical_control_schedule.csv`,
`canonical_action_ledger.csv`, `canonical_runs.csv` and
`canonical_paired_summary.csv`. The reporting package also includes regime
separation, physical-risk fan charts, a paired-effect forest plot, the
service/stock/nervousness/risk frontier, seed-interval convergence and a
TP/FP/FN/TN cost matrix.

## Current validation status

| Work package | Code status | Remaining evidence |
|---|---|---|
| Regime calibration | Pseudo-labels plus optional strict business annotations implemented | Representative industrial labels and coverage |
| Prediction interval to physics | Portfolio + granular exports, binary-outcome residual-score calibration, explicit nonconformal fallbacks, horizon decay and coefficient sensitivity implemented | Independent incident-based validation and latent-probability uncertainty calibration |
| Canonical reinjection | Bounded daily open-loop port, ledger and executable replay implemented | Online state-feedback controller |
| Paired policy comparison | Implemented and tested | Large canonical campaign |
| FP/FN study | TP/FP/FN/TN and configurable sensitivity grid implemented and tested | Empirical forecast-error frequencies |
| RCI business validation | Multi-expert review protocol implemented; `pending_business_review` without a complete panel | Procurement/planning review and explicit sign-off |
