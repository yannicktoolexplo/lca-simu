# SCAN 2027 — State-dependent supplier-risk control PoC

## Research question

This prototype is an executable continuation of the 2026 RESILIENCE-SCAN work.
It tests the following question:

> How can an uncertain supplier-risk signal be transformed into a bounded,
> explainable operational response that protects service without creating order
> nervousness, supplier stress or a second disruption?

The decision layer remains deliberately located under `etudecas/prototypes/`.
It reads existing `etudecas` outputs and retains a reduced-order research bench.
The end-2026 replay still supports a bounded, precomputed daily schedule and is
therefore explicitly open loop. A separate canonical state-feedback provider
now observes the realized multi-item engine state at the end of each measured
day and can issue bounded commands for the next day. The two integration modes
and their evidence are kept separate.

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
- canonical feedback causality, confirmation/dwell/slew/fallback, strict summary
  claim and paired MRP-versus-feedback campaign exports;
- a complete synthetic smoke run and its output contract.

## Scientific claims and limits

### What this PoC demonstrates

- risk must be translated into physical uncertainty, not used as a direct
  decision;
- the preferred response depends on the operating regime;
- the response can create supplier risk through order nervousness;
- scenario-based selection can compare bounded playbooks on a common basis;
- observability and controllability can be monitored alongside service KPIs;
- the canonical simulator can recompute a finite, bounded response from its
  realized end-of-day state with an auditable one-day causal delay.

### What it does not yet demonstrate

- industrially calibrated supplier-stress equations;
- guaranteed stability of the full multi-tier network;
- an optimized MPC controller;
- causal identification from real supplier data;
- a global canonical frequency response or a global gain/phase margin. The
  reduced-model impedance spectrum remains exploratory trajectory
  post-processing. The separate canonical frequency protocol below can estimate
  empirical harmonic-line responses, coherence and spectral-peak candidates,
  but only
  for its tested operating conditions and amplitudes; it does not identify an
  isolated global LTI FRF.

The canonical `supplier_disruption_score` is a bounded severity proxy derived
from active physical availability, capacity, quality, lead-time and write-off
effects. It is deliberately **not** an incident probability and must not be
calibrated or interpreted as one. The canonical feedback implementation is a
finite-state safety layer with temporal confirmation, dwell and slew limits; it is not yet
Scenario/Tube MPC and does not by itself establish stability or industrial
fitness.

## Remaining validation evidence

The six end-2026 work packages are executable. They are not all industrially
validated. The remaining evidence is:

1. representative procurement/planning regime annotations over real incidents;
2. incident-based calibration and sensitivity of prediction-to-physics
   coefficients;
3. a consolidated paired canonical campaign with 20–30 seeds, then 50+;
4. empirical alert-error frequencies and threshold/width/duration sensitivity;
5. procurement and planning review of the RCI, followed by explicit sign-off;
6. independent phase/amplitude and multi-seed stochastic replications of the
   tested-amplitude frequency study before making robust bandwidth claims.

### 2027 research direction

1. Replace the finite selector with Scenario/Tube MPC.
2. Extend the current marginal binary-outcome score calibration to conditional
   predictive sets or distributionally robust uncertainty sets, and separately
   estimate uncertainty in the latent incident probability.
3. Add explicit stock, backlog, capacity and nervousness safety constraints.
4. Extend the tested-amplitude canonical harmonic-line responses to
   multi-amplitude and MIMO replications with independent phase realizations and
   uncertainty.
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

### C.1. Canonical state-feedback loop

The canonical closed-loop path uses the versioned policy
`config/canonical_closed_loop_config.json` and the engine flag
`--control-policy-json`. It is a distinct alternative to
`--control-schedule-csv`; supplying both is rejected because a precomputed CSV
cannot simultaneously be claimed as online state feedback.

At the end of measured day `J`, the engine exposes only realized day-`J` state:
demand, served quantity and service, backlog quantity and equivalent days,
inventory and material/finished cover, production and supplier utilization,
the dimensionless median pairwise change of same-pair orders, active supplier
events and a bounded physical-disruption severity proxy. It never aggregates
order quantities across incompatible UOMs, and material cover uses only current
realized consumption/current-day need. The controller retains causal memory of backlog, order
nervousness, supplier stress and recent disruption. It classifies this state
into the same eight regimes (`NOMINAL`, `MATERIAL_TENSION`,
`CAPACITY_SATURATION`, `SUPPLIER_STRESS`, `OSCILLATORY`, `CRISIS`, `RECOVERY`
and `POST_CRISIS_OVERSTOCK`) and selects a configured finite playbook.

The timing invariant is `observation(J) -> decision(J) -> command(J+1)`. No
day-`J` action can depend on the end-of-day state it is about to change, and the
provider has no direct access to future realizations. The engine additionally
audits indirect access: because its MRP smoothing window is forward-inclusive,
a width above one day would place future realized-profile values into the
day-`J` demand state. Such a run is labelled with a positive look-ahead and
cannot set the strict closed-loop claim. The paired campaign appends
`--mrp-demand-signal-smoothing-days 1` after the canonical engine profile, so
both MRP and feedback arms use current-day demand only. Regime
`confirmation_days` provides temporal debounce, not distinct entry/exit
thresholds; policy changes occur on configured review days, subject to
`minimum_dwell_days`, except for an emergency review.
Per-lever `slew_limits` damp abrupt command changes. Invalid or non-finite
observations immediately activate the neutral `fallback_policy` and clear stale
external commands. MRP, lotification, campaigns, stock availability and
capacity constraints remain authoritative after the feedback command.

A direct one-run invocation is:

```powershell
python etudecas/simulation/engine/run_first_simulation.py `
  --input <canonical_graph.json> `
  --output-dir <closed_loop_result> `
  --scenario-id scn:BASE `
  --days 90 `
  --seed 200260 `
  --common-random-numbers `
  --supplier-state-dependent-risks `
  --mrp-demand-signal-smoothing-days 1 `
  --warmup-days 0 `
  --supplier-state-risk-observation-warmup-days 0 `
  --control-policy-json `
    etudecas/prototypes/scan_2027_risk_control/config/canonical_closed_loop_config.json
```

The engine writes four linked evidence files:

- `data/canonical_closed_loop_observations.csv`, including state validity and a
  deterministic observation hash;
- `data/canonical_closed_loop_decisions.csv`, including raw/confirmed regimes,
  confirmation, dwell/review outcome, fallback and decision/effective days;
- `data/canonical_closed_loop_commands.csv`, including requested/effective
  values, scope and slew-limited levers;
- `data/canonical_action_ledger.csv`, which follows those commands through the
  physical execution stages and records binding or no-flow reasons.

The engine summary records this evidence under `policy.control_provider`.
Merely passing `--control-policy-json` is insufficient for a scientific claim:
`closed_loop_claimed` becomes true only when observations exist, every command
obeys the one-day causal lag, observation/decision counts match, the observation
look-ahead is exactly zero and at least one feedback action was physically
applied. The campaign runner independently rereads the four evidence CSVs and
accepts only the authoritative
`policy.control_provider.closed_loop_claimed` boolean.

The controller's dynamic memory is not primed through a separate physical
warm-up. A run with `warmup_days > 0` is explicitly marked as a controller
cold-start mismatch and cannot claim the strict closed loop. The canonical
paired configuration sets `warmup_days=0` and also sets the state-dependent
supplier-risk observation warm-up to zero; both choices are exported in the
manifest. This is a documented experimental choice, not a general warm-up
solution.

For an appraised comparison rather than a single run, use the paired campaign:

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.canonical_closed_loop `
  --config etudecas/prototypes/scan_2027_risk_control/config/canonical_closed_loop_config.json `
  --graph auto `
  --days 90 `
  --seeds 200260,200261,200262 `
  --output-dir etudecas/prototypes/scan_2027_risk_control/outputs/canonical_closed_loop
```

For every seed, the runner executes `mrp_reference` and `canonical_feedback`
with the same untouched graph, external risk-event file, horizon, scenario and
common-random-number contract. State-generated supplier risks are not forced to
remain equal after intervention: their divergence can be a consequence of the
feedback trajectory. Engine failures and output-contract violations are raised,
and an existing non-empty run directory is not silently reused.
With only three configured seeds this is a smoke campaign. Its 95% paired
intervals use Student critical values; it is not presented as a consolidated
20--30-seed statistical validation.

The campaign exports:

- `canonical_closed_loop_runs.csv`;
- `canonical_closed_loop_paired_deltas.csv`;
- `canonical_closed_loop_paired_summary.csv`;
- `canonical_closed_loop_commands.json` and
  `canonical_closed_loop_manifest.json`, including input/config hashes and the
  strict engine-authored claim;
- `canonical_closed_loop_comparison.png` and
  `canonical_closed_loop_control_diagnostics.png` when matplotlib and the
  engine feedback ledgers are available.

The paired runner uses the historical compact engine output by default.  Pass
`--engine-artifact-profile full` to request, for both arms, the direct factory
input-consumption and replenishment-shipment tables, lot events and genealogy,
the lot audit, the engine map and all node plots.  The runner validates this
contract after each arm and refuses a non-empty campaign root; compact mode and
existing cold-start campaigns are unchanged.

Once a paired campaign is complete, build a separate multi-node comparison
without modifying either physical run:

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.canonical_node_comparison `
  --paired-results-dir path/to/paired_campaign `
  --output-dir path/to/new_node_comparison `
  --seed 320270 `
  --plot
```

The resulting standalone HTML compares MRP and feedback trajectories by day,
node, item and lane, includes direct input consumption, replenishment, lot and
genealogy aggregates when the full profile is available, and reports absent
data instead of treating it as zero.  Sparse physical flow/event rows are
zero-filled only for declared flow and count indicators; missing state rows
remain missing.  The scope registry also records which customer-service totals
can be reconciled with the global daily table.  Other global production, stock
and shipment totals must not be presented as a naive sum of local tables.

Build the separate business-facing evidence pack from the same completed pair
and node comparison:

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.canonical_industrial_results `
  --paired-results-dir path/to/paired_campaign `
  --comparison-dir path/to/node_comparison `
  --output-dir path/to/new_industrial_pack `
  --seed 320270
```

This read-only post-processing step writes a self-contained HTML dashboard,
eight PNG figures, a French Markdown report, evidence CSVs and a provenance
manifest.  It exposes the simulated supplier-penalty/cost trade-off,
differences by physical-data family, end-of-horizon deferrals, lot-size
amplification, state-dependent supplier-penalty episodes, the chronology of
first divergences, crisis-command timing and client buffer.  The family view is
not a causal funnel, and the supplier-penalty index is not an observed incident
probability.
It refuses a non-empty output directory.  Component quantities retain their
own `G`, `KG`, `M` or `UN` unit and are never summed or compared by bar length
across incompatible units.  The result remains one simulated paired
counterfactual until it is repeated on independent realizations and calibrated
with industrial observations.

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

Open-loop canonical replays additionally emit `canonical_control_schedule.csv`,
`canonical_action_ledger.csv`, `canonical_runs.csv` and
`canonical_paired_summary.csv`. State-feedback engine runs instead add
`canonical_closed_loop_observations.csv`,
`canonical_closed_loop_decisions.csv` and
`canonical_closed_loop_commands.csv` beside the shared physical action ledger.
The paired closed-loop runner writes its `canonical_closed_loop_*` run, delta,
summary, command, manifest and optional comparison-figure artifacts at the
campaign root. The reporting package also includes regime separation,
physical-risk fan charts, a paired-effect forest plot, the
service/stock/nervousness/risk frontier, seed-interval convergence and a
TP/FP/FN/TN cost matrix.

### Closed-Loop V2: paired burn-in and guarded damping

`canonical_closed_loop_v2.py` is an additive protocol runner. It does not edit
the historical cold-start config, V1 runner or V1 map pane. Its dedicated
`config/canonical_closed_loop_v2_config.json` pre-registers 10 training seeds
and 30 disjoint validation seeds, a 60-day `preperiod` burn-in, observe-only
controller priming and a one-day causal action lag.

```bash
python etudecas/prototypes/scan_2027_risk_control/canonical_closed_loop_v2.py \
  --config etudecas/prototypes/scan_2027_risk_control/config/canonical_closed_loop_v2_config.json \
  --phase validation \
  --output-dir path/to/new_v2_output
```

For every seed, the protocol requires identical MRP/V2 core-state hashes at J0,
60 valid priming rows from J-60 through J-1, zero warm-up actions, first action
no earlier than J1, a strict engine closed-loop claim and zero command-gate
violations. It writes `canonical_closed_loop_v2_protocol.json` plus the usual
paired CSVs and two PNG figures. The cutover evidence is called a deterministic
paired burn-in replay, not a serialized snapshot. A terminal two-window
diagnostic is reported separately and never upgrades the burn-in to a
stationarity proof.

### Closed-Loop V3: continuous state-dependent supplier relief

V3 is additive. It has its own schema, engine flag, configuration and output
directory; it does not modify the cold-start V1 campaign, the V2 protocol or
their map panes. It retains the V2 supervisor and adds a bounded daily
correction inside the configured `SUPPLIER_STRESS / supplier_relief` branch.
The correction varies order and production targets smoothly with projected
stress, while backlog, service and stock-cover protections can reduce or cancel
it. It remains causal: day `J` state can affect only day `J + 1`.

For an explicit paired technical run:

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.canonical_closed_loop `
  --config etudecas/prototypes/scan_2027_risk_control/config/canonical_closed_loop_v3_continuous_config.json `
  --seeds 310271 `
  --output-dir path/to/new_v3_output
```

Always provide `--seeds` to this generic runner when using the V3
configuration. Its `training_seeds` and `validation_seeds` lists are not chosen
automatically because selecting a phase implicitly could launch a large
campaign by accident. The runner now rejects that ambiguous invocation instead
of silently substituting an unrelated default seed.

### Canonical frequency study: native spectra and designed harmonic-line responses

`canonical_frequency_study.py` is a third additive research protocol. It does
not replace the cold-start campaign, Closed-Loop V1 or Closed-Loop V2. It
separates evidence that has different scientific meaning:

- five-year Welch spectra from existing `etudecas` case-simulation outputs are
  descriptive only;
- bounded random-phase periodic multisines are injected in three separate SISO
  campaigns on exact DFT lines to probe demand, supplier-availability and
  supplier-lead-time responses;
- MRP and the feedback controller selected by the policy schema use paired
  baselines, common random numbers and the same designed exogenous signal;
- an external MRP schedule probes order, safety-stock and production-target
  levers. This remains a multiplicative MRP-overlay response, not an independent
  additive plant dither;
- low-coherence lines remain in the audit CSV but are invalidated for
  interpretation.
- numerical validity, supervisory-regime compatibility and a true local
  small-signal derivative are three distinct claims. An unchanged day-by-day
  regime trace is retained as tested-amplitude compatibility only. Without an
  amplitude sweep toward zero and invariant lot/capacity/constraint active
  sets, no line is promoted to a local derivative; changed traces remain
  amplitude-conditioned hybrid regime-switching responses.

```powershell
python etudecas/prototypes/scan_2027_risk_control/canonical_frequency_study.py `
  --config etudecas/prototypes/scan_2027_risk_control/config/canonical_frequency_study_config.json `
  --stage all `
  --output-dir path/to/new_frequency_output
```

The default designed protocol uses one-day sampling, a 196-day exact period
(28 weeks, hence aligned with the plant's 7-day calendar and V2's 14-day dwell),
60 warm-up days and four measured periods (784 days), with the first measured
period reserved for settling. Demand, availability and lead-time excitations run
in three separate SISO campaigns so calendar-frequency mixing cannot be
misattributed across inputs. The designed graph copy
focuses demand on the reachable `268967` subnetwork while preserving the source
graph byte-for-byte. The supplier probe is the active 35-day
`SDC-VD0993480A → M-1430 / item:344135` component lane linked directly to that
finished item. It carries seven nonzero shipment and arrival days in every
retained preflight period under nominal and supplier-stress baselines; its
35–42 day operating delay remains below the 49-day
phase-unwrapping bound. Endogenous
supplier risks and stochastic lead times are disabled for the first
identification pass; explicit physical supplier perturbations remain active. A
separate stochastic, multi-seed robustness replication is still required.

Main exports are:

```text
canonical_frequency_protocol.json
canonical_frequency_native_spectra.csv
canonical_frequency_native_bands.csv
canonical_frequency_response.csv
canonical_frequency_closed_loop_comparison.csv
canonical_frequency_resonances.csv
canonical_frequency_stability.csv
canonical_frequency_delays.csv
canonical_frequency_nonlinearity.csv
canonical_frequency_regime_occupancy.csv
canonical_frequency_excitation_audit.csv
canonical_frequency_trajectories.csv
canonical_frequency_report.md
canonical_frequency_excitation_response.png
canonical_frequency_bode_frf.png
canonical_frequency_coherence.png
canonical_frequency_resonances.png
canonical_frequency_time_frequency.png
canonical_frequency_stability.png
```

#### V3 demand-frequency pilot

The first V3 pilot varies measured demand only, by +/-0.5%, at oscillation
periods of approximately 196, 65.3, 28 and 15.1 days. It compares MRP and V3
under a nominal condition and a fixed supplier-stress condition. Four 196-day
cycles are simulated; the first is discarded and the remaining three are
compared. In plain terms, the study makes demand oscillate at four speeds and
checks whether controller and physical outputs follow that rhythm in a visible,
repeatable way.

```powershell
python etudecas/prototypes/scan_2027_risk_control/canonical_frequency_study.py `
  --config etudecas/prototypes/scan_2027_risk_control/config/canonical_frequency_v3_demand_pilot_config.json `
  --stage designed `
  --output-dir path/to/new_v3_frequency_output
```

Use `--stage designed` to reproduce the completed pilot. `--stage all` also
requests the separate five-year observational spectra.

In the completed stressed-condition runs, V3 was causally and physically
active while the `SUPPLIER_STRESS` regime and `supplier_relief` policy remained
unchanged between the reference and excited trajectories. The controller moved
coherently at the two slowest periods, but its response and the main physical
flows were not repeatable enough over the three retained cycles. Of 320
response rows, 32 passed the numerical checks and eight feedback/MRP
comparisons were usable; none showed reliable attenuation caused by dynamic V3
modulation. The +/-0.5% signal also remained below the lot-sizing threshold for
some target production and shipment flows.

This pilot therefore demonstrates a real state-dependent dynamic controller and
a stable stressed operating branch, but not an isolated linear Bode model,
local stability proof or classical gain/phase margin. The next confirmation
should use ten cycles, at least five phase offsets, and separate tests at 0.25%,
0.5% and 1%. Larger 2% and 5% tests should be reported separately as nonlinear
regime experiments rather than as a local linear response.

Open `canonical_frequency_report.md` for the written result and the six
`canonical_frequency_*.png` files for the curves. To expose them in the map,
build a new HTML file with the same historical scan, V1 and V2 inputs and pass
the V3 package through `--scan-frequency-results-dir`; use a new output path so
the historical map remains untouched.

#### Historical V2 lead-time campaign

The MRP is already a feedback loop on inventory, transit and backlog. The V2
layer is a thresholded hybrid supervisor whose local playbook is often
constant. Consequently the protocol reports empirical disturbance-to-output
diagonal harmonic-line responses, V2/MRP attenuation, coherence, phase-slope
diagnostics, residual spectral energy, and symmetric period-to-period RMS
repeatability. The period-resampling quantiles are descriptive and are not
claimed as confidence intervals with calibrated 95% coverage. Weekly and
lotification nonlinearities can still transfer harmonics within one SISO
multisine, so the result is not called an isolated LTI FRF. The protocol
explicitly refuses a single global Bode, pole set or classical gain/phase margin
for V2 and always writes
`global_stability_claimed=false` and `industrial_validation_claimed=false`.
The runner also refuses the closed-loop label unless both V2 arms prove at least
one causally scheduled and physically applied feedback action. Exactly zero
responses remain numerical audit rows but are not classified as coherent or
identifiable response lines. A V2/MRP difference is labelled dynamic only when
a coherent control-output line proves modulation of a V2 command; otherwise an
active constant playbook is reported as static policy conditioning.

The first completed campaign is now accompanied by a strict posthoc audit. Its
current evidence must be read as follows:

- 1,104 harmonic-line rows were emitted; 52 pass the raw coherence threshold,
  but only 22 pass the complete numerical gate, all for supplier lead time;
- seven of those 22 retain the same supervisory-regime trace at the tested
  amplitude and 15 are hybrid. None proves a zero-amplitude local derivative;
- the three finite phase slopes (17.66--18.83 days) all come from hybrid
  regime-switching command responses. They are preserved as descriptive
  transition timing and removed from the local-delay field;
- DC-aware repeated-period diagnostics contain 164 responses below the
  numerical floor, 19 nonzero repeatable responses, 50 material interior
  peaks, 23 monotonic growth cases and 20 other nonstationary cases. A null
  response is no longer counted as an identified repeatable response;
- only one V2/MRP comparison passes the complete gate: -0.0395 dB for stressed
  supplier lead time to destination arrivals. Its exact paired three-period
  interval is approximately [-0.0781, 0] dB and no coherent dynamic modulation
  of a V2 command is identified, so the result is non-conclusive;
- actuator commands and realized operations are separate evidence. In the
  completed run, order and safety-stock overlays have positive realized volume
  on 784/784 days, whereas production-target control has positive realized
  volume on only 42/784 days. No actuator line passes the complete frequency
  validity gate.

`canonical_frequency_audit.py` reproduces this reclassification in a separate
read-only audit package. `canonical_frequency_robust_siso.py` prepares the next
lead-time campaign with 0.5%, 1%, 2% and 5% amplitudes, independent phase
realisations and a longer confirmatory repeated-period design. These tools do
not modify the immutable source package or any cold-start result.

The first 0.5%/1% comparison now stops that lead-time matrix before further
execution. The engine realizes transport time as
`ceil(nominal_days * multiplier + extra_delays)`. On the 92 shipment
observations shared by the two amplitudes, the requested multipliers differ but
the realized delays are identical: 35/36 days in the nominal condition and
42/43 days under supplier stress. Halving the requested amplitude therefore
halves the numerical denominator without halving the physical input. It cannot
support a local-response conclusion, and a 0.25% cell would repeat the same
integer-delay mechanism.

`canonical_frequency_lead_time_realization_audit.py` checks this condition from
the immutable shipment and risk ledgers, writes detailed CSV/JSON evidence, and
produces a plain-language Markdown report plus a requested-versus-realized PNG.
The controller also accepts the optional
`dynamics.recent_disruption_score_floor`; its default is `0.0`, which preserves
the historical incident-memory rule exactly. A frequency-specific study may
set a positive floor explicitly, but this does not remove daily lead-time
quantization. The next protocol must therefore separate (1) a local study based
on a genuinely continuous realized input in a fixed operating regime and (2)
finite-amplitude regime-transition experiments for the switched V2 controller.

## Current validation status

| Work package | Code status | Remaining evidence |
|---|---|---|
| Regime calibration | Pseudo-labels plus optional strict business annotations implemented | Representative industrial labels and coverage |
| Prediction interval to physics | Portfolio + granular exports, binary-outcome residual-score calibration, explicit nonconformal fallbacks, horizon decay and coefficient sensitivity implemented | Independent incident-based validation and latent-probability uncertainty calibration |
| Canonical reinjection | Open-loop schedule, causal `J -> J+1` hybrid supervisor and bounded continuous V3 correction implemented with physical ledgers | Industrial threshold/dynamics calibration, stability evidence and governance |
| Paired policy comparison | Reduced/open-loop benches plus V1 cold-start and V2 paired-burn-in canonical runners implemented and tested | Independent replication and industrial data |
| Frequency and state-dependent dynamics | Historical V2 lead-time audit plus a V3 demand-only pilot in a fixed stressed regime, with four measured frequencies and six report figures | Confirm repeatability over more cycles, phases and small demand amplitudes before any local transfer-function or stability-margin claim; study larger nonlinear regime changes separately |
| FP/FN study | TP/FP/FN/TN and configurable sensitivity grid implemented and tested | Empirical forecast-error frequencies |
| RCI business validation | Multi-expert review protocol implemented; `pending_business_review` without a complete panel | Procurement/planning review and explicit sign-off |
