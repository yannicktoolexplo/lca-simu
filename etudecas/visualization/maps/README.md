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
