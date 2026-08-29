# Map Payload Modes

Generated maps can use three payload modes.

## Autonomous raw HTML

Default mode. The full `DATA` object is embedded as plain JSON.

- Pros: works everywhere as a single file.
- Cons: very large HTML files.

## Autonomous compressed HTML

Use:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --compress-embedded-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/compress_html_payload.py --input map.html --execute
```

The map remains a single HTML file. The `DATA` payload is embedded as gzip/base64
and inflated in the browser before initialization.

Requires a recent browser with `DecompressionStream("gzip")`, such as recent
Edge or Chrome.

## Optional RESILIENCE-SCAN dashboard

To add the research-results tab and its curated curves to a generated map, pass
the final SCAN validation package:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py \
  --scan-results-dir path/to/real_release_candidate_strict_final_v6 \
  --closed-loop-results-dir path/to/canonical_closed_loop_campaign \
  --compress-embedded-payload \
  --output path/to/resilience_scan_map.html
```

The `RESILIENCE-SCAN` button appears only when `--scan-results-dir` contains a
valid package with `run_manifest.json`. The resulting HTML is self-contained:
selected PNG curves, summary metrics, policy tables and scientific limitations
are embedded in the map. When `--closed-loop-results-dir` contains a paired
canonical campaign, a separate `Boucle fermee` pane presents the strict J to
J+1 audit, paired MRP deltas and controller diagnostics. The pane confirms a
causal loop only when every feedback seed has the authoritative engine claim,
the representative summary reports zero demand-profile look-ahead and the
future-access flag is false; otherwise it displays an explicit contract warning.
It does not relabel the older precomputed schedules as closed-loop. Campaign
directories remain outside Git.

Closed-Loop V2 is additive and never replaces that historical pane:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py \
  --scan-results-dir path/to/scan_package \
  --closed-loop-results-dir path/to/v1_campaign \
  --closed-loop-v2-results-dir path/to/v2_protocol_or_validation_campaign \
  --compress-embedded-payload \
  --output path/to/resilience_scan_with_v2.html
```

The V2 argument accepts either the protocol root written by
`canonical_closed_loop_v2.py` or its `validation` campaign directory. A distinct
`Closed-Loop V2` pane is added only when the package is valid; omitting the
argument preserves the previous tabs and dashboard payload.

Frequency-domain evidence is also optional and additive:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py \
  --scan-results-dir path/to/scan_package \
  --closed-loop-results-dir path/to/v1_campaign \
  --closed-loop-v2-results-dir path/to/v2_protocol_or_validation_campaign \
  --scan-frequency-results-dir path/to/canonical_frequency_package \
  --compress-embedded-payload \
  --output path/to/resilience_scan_with_frequency_analysis.html
```

The frequency package must contain either
`canonical_frequency_protocol.json` or `canonical_frequency_manifest.json`,
plus non-empty `canonical_frequency_response.csv`,
`canonical_frequency_resonances.csv` and
`canonical_frequency_stability.csv`. When that contract is complete, a distinct
`Analyse fréquentielle` pane is added after the closed-loop panes. It can embed
the following curated figures when present:

- `canonical_frequency_excitation_response.png`;
- `canonical_frequency_bode_frf.png`;
- `canonical_frequency_coherence.png`;
- `canonical_frequency_resonances.png`;
- `canonical_frequency_time_frequency.png`;
- `canonical_frequency_stability.png`.

  The pane deliberately reports `global_stability_claimed=false` and presents
  the designed results as empirical, regime-conditioned harmonic-line
  responses, not isolated LTI FRFs, poles, or classical margins. Only rows
  whose baseline and excited feedback arms keep the same day-by-day regime
  trace are labeled as compatible at the tested amplitude only. No row is
  labeled as a local small-signal derivative without an amplitude sweep toward
  zero and invariant plant/controller active sets. An
absent or incomplete package adds no pane and leaves the historical SCAN,
cold-start, closed-loop V1 and Closed-Loop V2 views unchanged.

## Autonomous chunked HTML

Recommended for large 5-year maps:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --chunked-embedded-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/chunk_html_payload.py --input map.html --execute
```

The map remains a single HTML file, but every top-level `DATA` key is stored as
a separate gzip/base64 block with a manifest.

This is the recommended user-facing mode today: it preserves the existing map
UI, tabs, Plotly interactions, lot tracing and risk panels. Current generated
maps load all blocks before initialization for compatibility. The format is
ready for future panel-level lazy loading through
`loadEmbeddedChunkedMapGroup(groupName)`.

Typical 5-year map result observed:

- raw autonomous HTML: about 147 MB;
- compressed autonomous HTML: about 9.9 MB;
- chunked autonomous HTML: about 9.4 MB.

## External JSON payload

Use:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --externalize-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/externalize_html_payload.py --input map.html --execute
```

This produces a small HTML file and a sibling JSON payload. It is best for web
serving, but it is not fully autonomous.

## Supplier what-if panel

Use on an existing interactive autonomous map:

```bash
python etudecas/visualization/maps/inject_supplier_what_if.py --input map.interactive_autonomous.html --execute
```

This injects a floating `What-if fournisseurs` panel backed by normalized
sensitivity results, for example
`etudecas/simulation/experiments/result/supplier_parameter_ingested/metrics.csv`.

This is a precomputed what-if explorer: changing a slider selects a simulated
scenario already present in `metrics.csv`. It does not run the Python simulation
engine inside the browser. It also displays the standard simulation request
contract for the selected scenario. A truly live simulator should be implemented
as a local API or a Pyodide/WebWorker app layer on top of that same contract.
