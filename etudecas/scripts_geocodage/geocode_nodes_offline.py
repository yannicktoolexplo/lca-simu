#!/usr/bin/env python3
"""Offline geocoding for supply graph nodes.

Uses a legacy actor->(lat, lon) mapping and a location fallback.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CODE_RE = re.compile(r"\b(VD[0-9A-Z]+|D[0-9]+|[0-9]{4,5}|XXXXX)\b", re.IGNORECASE)
COUNTRY_MAP = {
    "France": "France",
    "Belgique": "Belgium",
    "Allemagne": "Germany",
    "Italie": "Italy",
    "Suede": "Sweden",
    "Suede ": "Sweden",
    "Suede\u0300": "Sweden",
    "Su\u00e8de": "Sweden",
    "Germany": "Germany",
}
TYPE_TO_PREFIX = {
    "factory": "M",
    "distribution_center": "DC",
    "supplier_dc": "SDC",
    "customer": "C",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline geocoding for supply_graph JSON.")
    parser.add_argument(
        "--input-json",
        default="etudecas/donnees/supply_graph_poc.json",
        help="Path to input supply graph JSON.",
    )
    parser.add_argument(
        "--coords-json",
        default="etudecas/scripts_geocodage/legacy_actor_coords.json",
        help="Path to legacy actor coords JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/result_geocodage",
        help="Output directory for geocoded JSON and report.",
    )
    parser.add_argument(
        "--output-name",
        default="supply_graph_poc_geocoded.json",
        help="Filename for geocoded JSON.",
    )
    return parser.parse_args()


def norm_location(location_id: str | None) -> str | None:
    if not location_id:
        return None
    return " - ".join(part.strip() for part in str(location_id).split(" - "))


def country_from_location(location_id: str | None) -> str | None:
    norm = norm_location(location_id)
    if not norm:
        return None
    country = norm.split(" - ")[0].strip()
    return COUNTRY_MAP.get(country, country or None)


def dedup_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def code_variants(raw_code: str) -> list[str]:
    code = raw_code.strip().upper()
    if not code:
        return []
    variants = [code]
    if code.startswith("D") and code[1:].isdigit():
        variants.append(code[1:])
    elif code.isdigit():
        variants.append(f"D{code}")
    return dedup_keep_order(variants)


def extract_codes(node: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    node_id = str(node.get("id", ""))
    if "-" in node_id:
        codes.extend(code_variants(node_id.split("-", 1)[1]))
    name = str(node.get("name", ""))
    for token in CODE_RE.findall(name):
        codes.extend(code_variants(token))
    return dedup_keep_order(codes)


def candidate_prefixes(node: dict[str, Any]) -> list[str]:
    prefixes: list[str] = []
    node_type = node.get("type")
    if node_type in TYPE_TO_PREFIX:
        prefixes.append(TYPE_TO_PREFIX[node_type])
    node_id = str(node.get("id", ""))
    if "-" in node_id:
        prefixes.append(node_id.split("-", 1)[0].upper())
    # Some historical keys used DC and SDC interchangeably for Dxxxx actors.
    if "DC" in prefixes or "SDC" in prefixes:
        prefixes.extend(["DC", "SDC"])
    return dedup_keep_order(prefixes)


def candidate_legacy_keys(node: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for prefix in candidate_prefixes(node):
        for code in extract_codes(node):
            keys.append(f"{prefix} - {code}")
    return dedup_keep_order(keys)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_json)
    coords_path = Path(args.coords_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    legacy_coords = json.loads(coords_path.read_text(encoding="utf-8"))

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("Expected 'nodes' to be a list.")

    location_coords: dict[str, list[tuple[float, float]]] = defaultdict(list)
    pending_by_location: dict[str, list[dict[str, Any]]] = defaultdict(list)
    report_rows: list[dict[str, Any]] = []
    method_counts: Counter[str] = Counter()

    for node in nodes:
        node_id = str(node.get("id"))
        location_id = norm_location(node.get("location_ID"))

        matched_key = None
        matched_coord = None
        for key in candidate_legacy_keys(node):
            if key in legacy_coords:
                matched_key = key
                coord = legacy_coords[key]
                matched_coord = (float(coord[0]), float(coord[1]))
                break

        geo = node.get("geo")
        if not isinstance(geo, dict):
            geo = {}
            node["geo"] = geo

        if matched_coord:
            lat, lon = matched_coord
            geo["lat"] = lat
            geo["lon"] = lon
            if (country := country_from_location(location_id)) is not None:
                geo["country"] = country
            geo["raw"] = {
                "method": "legacy_id_map",
                "legacy_key": matched_key,
                "location_ID": location_id,
            }
            node.setdefault("defaults", {})["geo"] = False
            method_counts["legacy_id_map"] += 1
            if location_id:
                location_coords[location_id].append((lat, lon))
            report_rows.append(
                {
                    "node_id": node_id,
                    "status": "geocoded",
                    "method": "legacy_id_map",
                    "legacy_key": matched_key,
                    "location_ID": location_id,
                    "lat": lat,
                    "lon": lon,
                }
            )
        else:
            if location_id:
                pending_by_location[location_id].append(node)
            report_rows.append(
                {
                    "node_id": node_id,
                    "status": "pending",
                    "method": None,
                    "legacy_key": None,
                    "location_ID": location_id,
                    "lat": None,
                    "lon": None,
                }
            )

    row_by_id = {row["node_id"]: row for row in report_rows}
    for location_id, pending_nodes in pending_by_location.items():
        coords = location_coords.get(location_id, [])
        if not coords:
            continue
        lat = sum(c[0] for c in coords) / len(coords)
        lon = sum(c[1] for c in coords) / len(coords)
        for node in pending_nodes:
            node_id = str(node.get("id"))
            geo = node["geo"]
            geo["lat"] = lat
            geo["lon"] = lon
            if (country := country_from_location(location_id)) is not None:
                geo["country"] = country
            geo["raw"] = {
                "method": "location_fallback",
                "legacy_key": None,
                "location_ID": location_id,
            }
            node.setdefault("defaults", {})["geo"] = False
            method_counts["location_fallback"] += 1
            row = row_by_id[node_id]
            row["status"] = "geocoded"
            row["method"] = "location_fallback"
            row["lat"] = lat
            row["lon"] = lon

    geocoded_rows = [row for row in report_rows if row["status"] == "geocoded"]
    unmatched_rows = [row for row in report_rows if row["status"] != "geocoded"]
    method_counts["unmatched"] = len(unmatched_rows)

    geocoded_path = output_dir / args.output_name
    report_path = output_dir / "geocodage_report.json"
    csv_path = output_dir / "geocodage_report.csv"

    geocoded_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_json": str(input_path),
        "coords_json": str(coords_path),
        "output_json": str(geocoded_path),
        "total_nodes": len(nodes),
        "geocoded_nodes": len(geocoded_rows),
        "unmatched_nodes": len(unmatched_rows),
        "method_counts": dict(method_counts),
        "unmatched_node_ids": [row["node_id"] for row in unmatched_rows],
        "rows": report_rows,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    header = "node_id,status,method,legacy_key,location_ID,lat,lon\n"
    lines = [header]
    for row in report_rows:
        line = ",".join(
            [
                str(row.get("node_id", "")),
                str(row.get("status", "")),
                str(row.get("method", "")),
                str(row.get("legacy_key", "")),
                str(row.get("location_ID", "")).replace(",", " "),
                str(row.get("lat", "")),
                str(row.get("lon", "")),
            ]
        )
        lines.append(f"{line}\n")
    csv_path.write_text("".join(lines), encoding="utf-8")

    print(f"Geocoded: {len(geocoded_rows)}/{len(nodes)}")
    if unmatched_rows:
        print("Unmatched nodes:", ", ".join(row["node_id"] for row in unmatched_rows))


if __name__ == "__main__":
    main()
