"""Regenerate only the map presentation, preserving embedded simulation results."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from POC2026.supply_geo_case.adapter import (
    CASE_ROOT,
    build_map_selection_paths,
    read_csv_rows,
    write_enriched_base_map_html,
)


def embedded_payload(html: str, name: str) -> dict:
    marker = f"const {name} = "
    start = html.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(html, start)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dashboard-json', type=Path)
    args = parser.parse_args()
    output = CASE_ROOT / "outputs"
    target = output / "maps" / "supply_geo_base_results_map.html"
    html = target.read_text(encoding="utf-8")
    payload = embedded_payload(html, "SDD_MAP_PAYLOAD")
    dashboard = embedded_payload(html, "BASE_DASHBOARD_PAYLOAD")
    if args.dashboard_json:
        dashboard = json.loads(args.dashboard_json.read_text(encoding='utf-8'))
    dashboard["selection_paths"] = build_map_selection_paths(
        read_csv_rows(output / "data" / "primary_supply_paths.csv"),
        read_csv_rows(output / "data" / "primary_supply_lanes.csv"),
    )
    reference = json.loads((output / "maps" / "source_map_reference.json").read_text(encoding="utf-8"))
    staging = target.with_suffix(".tmp.html")
    try:
        write_enriched_base_map_html(
            staging,
            source_map=Path(reference["source_map_html"]),
            site_rows=[],
            sdd_results={},
            dashboard_payload=dashboard,
            prebuilt_map_payload=payload,
        )
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)
    print(f"Map display refreshed: {target}")


if __name__ == "__main__":
    main()
