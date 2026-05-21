#!/usr/bin/env python3
"""Infer transport lanes from supplier geolocation and list missing sites.

The generated modes are simulation assumptions, not freight contracts. They are
good enough to remove impossible truck-only longhaul paths and to make switch
scenarios behave consistently by origin/destination.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_simulation_ready_researched.json"
OUTPUT_JSON = INPUT_JSON
LANES_CSV = BASE_DIR / "output8_GEO_geo_inferred_transport_lanes.csv"
MISSING_NODES_CSV = BASE_DIR / "output8_GEO_missing_geolocation_nodes.csv"
MISSING_LANES_CSV = BASE_DIR / "output8_GEO_missing_geolocation_lanes.csv"
PROMPT_MD = BASE_DIR / "output8_GEO_missing_geolocation_chatgpt_prompt.md"
REPORT_MD = BASE_DIR / "output8_GEO_geo_transport_completion_report.md"

ROLE_SEQUENCE = [
    ("T4", "tier4_raw_material"),
    ("T3", "tier3_first_transformation"),
    ("T2", "tier2_second_transformation"),
    ("T1", "tier1"),
    ("OEM", "oem"),
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def has_coords(node: dict[str, Any]) -> bool:
    return safe_float(node.get("lat")) is not None and safe_float(node.get("lon")) is not None


def haversine_km(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    lat1 = safe_float(a.get("lat"))
    lon1 = safe_float(a.get("lon"))
    lat2 = safe_float(b.get("lat"))
    lon2 = safe_float(b.get("lon"))
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def is_europe(node: dict[str, Any]) -> bool:
    lat = safe_float(node.get("lat"))
    lon = safe_float(node.get("lon"))
    if lat is None or lon is None:
        return False
    return 34.0 <= lat <= 72.5 and -25.0 <= lon <= 45.0


def node_key(node: dict[str, Any]) -> str:
    sid = clean(node.get("supplier_id")) or slug(clean(node.get("name")))
    role = clean(node.get("role_hint"))
    return f"{sid}::{role}"


def node_label(node: dict[str, Any]) -> str:
    return clean(node.get("name"))


def nodes_by_role(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    suppliers = [s for s in record.get("suppliers") or [] if isinstance(s, dict)]
    for code, role in ROLE_SEQUENCE:
        if role == "oem":
            out[code] = [s for s in record.get("oem_sites") or [] if isinstance(s, dict)]
        else:
            out[code] = [s for s in suppliers if s.get("role_hint") == role]
    return out


def is_internal_t2_t1(edge: str, src: dict[str, Any], dst: dict[str, Any], distance: float | None) -> bool:
    if edge != "T2->T1":
        return False
    text = " ".join(
        [
            clean(src.get("name")),
            clean(src.get("supplier_status")),
            clean(src.get("simulation_node_type")),
        ]
    ).lower()
    dst_name = clean(dst.get("name")).lower()
    return "internal" in text or (dst_name and dst_name in clean(src.get("name")).lower()) or (distance is not None and distance <= 2.0)


def infer_modes(edge: str, src: dict[str, Any], dst: dict[str, Any], distance: float | None) -> tuple[list[str], str, str]:
    if is_internal_t2_t1(edge, src, dst, distance):
        return ["internal"], "high", "internal process colocated with downstream T1"
    if distance is None:
        return [], "none", "missing coordinates"
    if distance <= 2:
        return ["internal"], "high", "same-site or colocated nodes"
    if distance <= 800:
        return ["truck"], "medium_high", "regional lane under 800 km"
    if is_europe(src) and is_europe(dst) and distance <= 2500:
        return ["truck", "rail"], "medium", "European long regional lane; rail/truck baseline"
    if distance <= 2500:
        return ["truck", "rail"], "medium_low", "regional long lane; rail/truck baseline pending freight validation"
    return ["truck", "ship"], "medium", "intercontinental or very long lane; sea/truck baseline"


def alternate_modes(distance: float | None, baseline_modes: list[str]) -> list[dict[str, Any]]:
    if distance is None or "internal" in baseline_modes:
        return []
    out: list[dict[str, Any]] = []
    if distance > 2500:
        out.append(
            {
                "scenario_suffix": "air_expedite",
                "modes": ["truck", "air"],
                "status": "expedite_candidate_requires_freight_validation",
            }
        )
    elif distance > 800 and "rail" in baseline_modes:
        out.append(
            {
                "scenario_suffix": "truck_only_candidate",
                "modes": ["truck"],
                "status": "cost_or_simplicity_candidate_requires_lane_validation",
            }
        )
    return out


def scenario_exists(record: dict[str, Any], edge: str, src: dict[str, Any], dst: dict[str, Any]) -> bool:
    src_name = node_label(src)
    dst_name = node_label(dst)
    src_id = clean(src.get("supplier_id"))
    dst_id = clean(dst.get("supplier_id"))
    for scenario in record.get("transport_scenarios") or []:
        if not isinstance(scenario, dict) or scenario.get("edge") != edge:
            continue
        from_ok = clean(scenario.get("from")) == src_name or (src_id and clean(scenario.get("from_supplier_id")) == src_id)
        to_ok = clean(scenario.get("to")) == dst_name or (dst_id and clean(scenario.get("to_supplier_id")) == dst_id)
        if from_ok and to_ok and "baseline" in clean(scenario.get("scenario_id")).lower():
            return True
    return False


def make_scenario(record_index: int, edge: str, src: dict[str, Any], dst: dict[str, Any], distance: float, modes: list[str], confidence: str, note: str) -> dict[str, Any]:
    return {
        "scenario_id": f"baseline_geo_{record_index:03d}_{edge.lower().replace('->', '_')}_{slug(node_label(src))}_{slug(node_label(dst))}"[:180],
        "edge": edge,
        "from": node_label(src),
        "to": node_label(dst),
        "from_supplier_id": clean(src.get("supplier_id")),
        "to_supplier_id": clean(dst.get("supplier_id")),
        "distance_km_haversine": round(distance, 1),
        "modes": modes,
        "source": "geolocation_distance_heuristic",
        "confidence": confidence,
        "status": "baseline_secondary_lane_inferred_from_geolocation",
        "note": note,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    lanes: list[dict[str, Any]] = []
    missing_lanes: list[dict[str, Any]] = []
    missing_nodes: dict[str, dict[str, Any]] = {}
    added = 0
    skipped_existing = 0

    for record_index, record in enumerate(records, 1):
        if record.get("simulation_supply_usable") is False:
            continue
        by_role = nodes_by_role(record)
        for (left_code, _left_role), (right_code, _right_role) in zip(ROLE_SEQUENCE, ROLE_SEQUENCE[1:]):
            edge = f"{left_code}->{right_code}"
            for src in by_role[left_code]:
                for dst in by_role[right_code]:
                    if not has_coords(src) or not has_coords(dst):
                        for role_code, node in [(left_code, src), (right_code, dst)]:
                            if has_coords(node):
                                continue
                            key = node_key(node)
                            item = missing_nodes.setdefault(
                                key,
                                {
                                    "supplier": node_label(node),
                                    "role": role_code,
                                    "location": clean(node.get("location")),
                                    "current_geocode_status": clean(node.get("geocode_status")),
                                    "supplier_status": clean(node.get("supplier_status")),
                                    "supplier_id": clean(node.get("supplier_id")),
                                    "record_count": 0,
                                    "records": set(),
                                    "components": set(),
                                },
                            )
                            item["record_count"] += 1
                            item["records"].add(str(record_index))
                            item["components"].add(clean(record.get("component")))
                        missing_lanes.append(
                            {
                                "record_index": record_index,
                                "system": record.get("system"),
                                "component": record.get("component"),
                                "edge": edge,
                                "from": node_label(src),
                                "to": node_label(dst),
                                "from_has_coords": has_coords(src),
                                "to_has_coords": has_coords(dst),
                                "action": "geolocate missing node before lane transport inference",
                            }
                        )
                        continue

                    distance = haversine_km(src, dst)
                    modes, confidence, note = infer_modes(edge, src, dst, distance)
                    if not modes or distance is None:
                        continue
                    lane_row = {
                        "record_index": record_index,
                        "system": record.get("system"),
                        "component": record.get("component"),
                        "edge": edge,
                        "from": node_label(src),
                        "to": node_label(dst),
                        "distance_km_haversine": round(distance, 1),
                        "modes": "|".join(modes),
                        "confidence": confidence,
                        "note": note,
                    }
                    lanes.append(lane_row)
                    if scenario_exists(record, edge, src, dst):
                        skipped_existing += 1
                        continue
                    scenario = make_scenario(record_index, edge, src, dst, distance, modes, confidence, note)
                    record.setdefault("transport_scenarios", []).append(scenario)
                    for alt in alternate_modes(distance, modes):
                        alt_scenario = dict(scenario)
                        alt_scenario["scenario_id"] = scenario["scenario_id"].replace("baseline_geo", f"{alt['scenario_suffix']}_geo", 1)
                        alt_scenario["modes"] = alt["modes"]
                        alt_scenario["status"] = alt["status"]
                        alt_scenario["note"] = "alternative scenario generated from geolocation heuristic"
                        record["transport_scenarios"].append(alt_scenario)
                    added += 1

    node_rows: list[dict[str, Any]] = []
    for item in missing_nodes.values():
        row = dict(item)
        row["records"] = ",".join(sorted(row["records"], key=lambda x: int(x)))
        row["components"] = " | ".join(sorted(row["components"])[:20])
        node_rows.append(row)
    node_rows.sort(key=lambda r: (-int(r["record_count"]), r["supplier"]))

    data.setdefault("_meta", {})["geo_inferred_transport_lanes"] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "added_baseline_lane_scenarios": added,
        "skipped_existing_lane_scenarios": skipped_existing,
        "missing_geolocation_nodes": len(node_rows),
        "policy": "distance-based heuristic for simulation lanes; validate freight modes before procurement-grade use",
    }

    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(LANES_CSV, lanes)
    write_csv(MISSING_NODES_CSV, node_rows)
    write_csv(MISSING_LANES_CSV, missing_lanes)

    lines = [
        "# Geolocation Missing Sites Prompt",
        "",
        "Tu es un expert geocoding supply chain aeronautique.",
        "",
        "Objectif: completer uniquement des sites industriels ou logistiques plausibles, sans utiliser un centroide pays si un site metier existe.",
        "",
        "Regles:",
        "- Donner latitude/longitude, adresse, niveau de confiance, source URL.",
        "- Si le fournisseur est trop generique ou si le site programme n'est pas deduisible, repondre `do_not_geocode_without_BOM_or_supplier_site`.",
        "- Ne pas inventer un site actif; proposer un candidat inactif si besoin.",
        "",
        "Donnees a completer:",
        "",
        "```csv",
        "supplier;role;location;current_geocode_status;supplier_status;records;components",
    ]
    for row in node_rows[:80]:
        lines.append(
            ";".join(
                clean(row.get(col)).replace("\n", " ")
                for col in ["supplier", "role", "location", "current_geocode_status", "supplier_status", "records", "components"]
            )
        )
    lines.extend(["```", ""])
    PROMPT_MD.write_text("\n".join(lines), encoding="utf-8")

    report = [
        "# Transport lanes inferred from geolocation",
        "",
        f"- Input/Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Generated at: `{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}`",
        f"- Lane rows computed: **{len(lanes)}**",
        f"- Baseline lane scenarios added: **{added}**",
        f"- Existing lane scenarios kept: **{skipped_existing}**",
        f"- Missing geolocation nodes: **{len(node_rows)}**",
        f"- Missing geolocation lane rows: **{len(missing_lanes)}**",
        "",
        "## Files",
        "",
        f"- Lane catalog: `{LANES_CSV.as_posix()}`",
        f"- Missing node worklist: `{MISSING_NODES_CSV.as_posix()}`",
        f"- Missing lane worklist: `{MISSING_LANES_CSV.as_posix()}`",
        f"- ChatGPT prompt: `{PROMPT_MD.as_posix()}`",
    ]
    REPORT_MD.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {LANES_CSV}")
    print(f"Wrote {MISSING_NODES_CSV}")
    print(f"Wrote {MISSING_LANES_CSV}")
    print(f"Wrote {PROMPT_MD}")
    print(f"Wrote {REPORT_MD}")
    print(f"Added lane scenarios: {added}")
    print(f"Missing nodes: {len(node_rows)}")


if __name__ == "__main__":
    main()
