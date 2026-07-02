---
name: etudecas-map-payload
description: Use when working on Etudecas map HTML generation, Plotly panels, payload builders, compressed or chunked HTML, what-if interactions, scenario curves, or visual regression risks.
---

# Etudecas Map Payload

## Workflow

1. Separate business payload construction from HTML/JS rendering.
2. Keep raw, externalized, compressed and chunked payload modes compatible.
3. Do not silently hide missing data; expose diagnostics or warnings.
4. Escape JSON embedded in `<script>` safely.
5. Keep the map usable offline only when the required JS dependencies are embedded or otherwise documented.

## Key Files

- Builder monolith to reduce: `etudecas/visualization/maps/build_supplychain_worldmap.py`.
- Payload tools: `externalize_html_payload.py`, `compress_html_payload.py`, `chunk_html_payload.py`.
- What-if injection: `etudecas/visualization/maps/inject_supplier_what_if.py`.

## Validation

Run fast tests and, for UI changes, open the generated HTML:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```
