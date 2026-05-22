#!/usr/bin/env python3
"""Attach LCA mass re-audit policy to the simulation-ready JSON."""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_simulation_ready_researched.json"
POLICY_CSV = BASE_DIR / "output8_GEO_lca_mass_reaudit_records.csv"
REPORT_MD = BASE_DIR / "output8_GEO_lca_mass_reaudit_json_update.md"


def clean(value: Any) -> str:
    return str(value or "").strip()


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def read_policy() -> dict[str, dict[str, Any]]:
    with POLICY_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        idx = clean(row.get("record_index"))
        if not idx:
            continue
        out[idx] = {
            "current_mass_kg": as_float(row.get("current_mass_kg")),
            "recommended_additive_mass_kg": as_float(row.get("recommended_additive_mass_kg")),
            "topdown_reference_mass_kg": as_float(row.get("topdown_reference_mass_kg")),
            "mass_policy": clean(row.get("mass_policy")),
            "mass_policy_action": clean(row.get("mass_policy_action")),
            "is_seat_aggregate": clean(row.get("is_seat_aggregate")) == "yes",
            "duplicate_signature_count": int(float(row.get("duplicate_signature_count") or 0)),
            "duplicate_mass_warning": clean(row.get("duplicate_mass_warning")) == "yes",
            "reaudit_source": POLICY_CSV.as_posix(),
        }
    return out


def apply_summary_to_entry(entry: dict[str, Any], policy: dict[str, Any]) -> None:
    trace = entry.setdefault("lca_component_trace", {})
    trace["lca_mass_policy"] = policy["mass_policy"]
    trace["lca_recommended_additive_mass_kg"] = policy["recommended_additive_mass_kg"]
    trace["lca_topdown_reference_mass_kg"] = policy["topdown_reference_mass_kg"]
    trace["lca_current_source_mass_kg"] = policy["current_mass_kg"]
    trace["lca_mass_policy_action"] = policy["mass_policy_action"]


def main() -> None:
    policy_by_index = read_policy()
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    updated = 0
    for idx, record in enumerate(records, 1):
        policy = policy_by_index.get(str(idx))
        if not policy:
            continue
        record["lca_mass_reaudit"] = policy
        lca = record.setdefault("lca_traceability", {})
        lca["mass_policy"] = policy["mass_policy"]
        lca["mass_policy_action"] = policy["mass_policy_action"]
        lca["current_source_mass_kg"] = policy["current_mass_kg"]
        lca["recommended_additive_mass_kg"] = policy["recommended_additive_mass_kg"]
        lca["topdown_reference_mass_kg"] = policy["topdown_reference_mass_kg"]
        lca["is_seat_aggregate"] = policy["is_seat_aggregate"]
        lca["duplicate_mass_warning"] = policy["duplicate_mass_warning"]
        for container in ("suppliers", "oem_sites", "logistics_providers"):
            for entry in record.get(container) or []:
                if isinstance(entry, dict):
                    apply_summary_to_entry(entry, policy)
        updated += 1

    data.setdefault("_meta", {})
    data["_meta"]["lca_mass_reaudit_applied"] = {
        "source_csv": POLICY_CSV.as_posix(),
        "records_updated": updated,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "note": "Map and simulations should use recommended_additive_mass_kg for additive quantitative views; topdown_reference_mass_kg is non-additive reference.",
    }
    INPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LCA Mass Reaudit JSON Update",
        "",
        f"- JSON updated: `{INPUT_JSON.as_posix()}`",
        f"- Policy source: `{POLICY_CSV.as_posix()}`",
        f"- Records updated: **{updated}**",
        "",
        "The JSON now carries `lca_traceability.recommended_additive_mass_kg`, `topdown_reference_mass_kg`, and `mass_policy` for map display and downstream simulation.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {INPUT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Records updated: {updated}")


if __name__ == "__main__":
    main()
