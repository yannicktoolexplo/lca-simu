#!/usr/bin/env python3
"""Split unresolved FRN-9C546CCC918C61 candidates into material-relevant sites."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_simulation_ready_researched.json"
OUT_CSV = BASE_DIR / "output8_GEO_FRN-9C546CCC918C61_site_split_changes.csv"
OUT_MD = BASE_DIR / "output8_GEO_FRN-9C546CCC918C61_site_split_report.md"


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


SITES = {
    "textile": {
        "name": "FRN-52C1B43CDDE847",
        "lat": None,
        "lon": None,
        "location": "Inazawa / Aichi, Japan",
        "site_address": '',
        "geocode_status": "source_backed_textile_site_candidate",
        "source_confidence": "medium_high",
        "source_urls": [
            "https://sources.invalid/FRN-52C1B43CDDE847/7ca5ae3ff480427a",
            'https://coordonnees.invalid/',
        ],
        "note": "Textile/fiber-processing candidate site; use as inactive switch candidate pending program material proof.",
    },
    "polymer": {
        "name": "FRN-F3FFB924CD457D",
        "lat": None,
        "lon": None,
        "location": "Nagoya / Aichi, Japan",
        "site_address": '',
        "geocode_status": "source_backed_polymer_resin_site_candidate",
        "source_confidence": "medium",
        "source_urls": [
            'https://coordonnees.invalid/',
            "https://sources.invalid/FRN-F3FFB924CD457D/eabfa729a6f1bb5a",
        ],
        "note": "Polymer/resin candidate site; use as inactive switch candidate pending grade and certificate.",
    },
    "composite": {
        "name": "FRN-8A956B599D7510",
        "lat": None,
        "lon": None,
        "location": "Masaki / Ehime, Japan",
        "site_address": '',
        "geocode_status": "source_backed_fiber_composite_site_candidate",
        "source_confidence": "medium_high",
        "source_urls": [
            "https://sources.invalid/FRN-8A956B599D7510/472a15487d9df296",
            'https://coordonnees.invalid/',
        ],
        "note": "Fiber/composite/carbon candidate site; use as inactive switch candidate pending material grade proof.",
    },
}


def choose_site(record: dict[str, Any]) -> str:
    text = " ".join(
        [
            clean(record.get("component")),
            clean(record.get("mass_material_match")),
            " ".join(clean(x) for x in record.get("raw_materials") or []),
        ]
    ).lower()
    if any(k in text for k in ["résine", "resine", "composite", "carbone", "carbon"]):
        return "composite"
    if any(k in text for k in ["caoutchouc", "polychloroprene", "ertalon", "plastic", "plastique"]):
        return "polymer"
    return "textile"


def update_toray_supplier(record: dict[str, Any], record_index: int) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    site_key = choose_site(record)
    site = SITES[site_key]
    for supplier in record.get("suppliers") or []:
        if not isinstance(supplier, dict):
            continue
        if clean(supplier.get("name")) != "FRN-0F56088BEA4986":
            continue
        if supplier.get("lat") not in (None, "") and supplier.get("lon") not in (None, ""):
            continue
        supplier["name"] = site["name"]
        supplier["lat"] = site["lat"]
        supplier["lon"] = site["lon"]
        supplier["location"] = site["location"]
        supplier["site_address"] = site["site_address"]
        supplier["geocode_status"] = site["geocode_status"]
        supplier["source_confidence"] = site["source_confidence"]
        supplier["site_selection_note"] = site["note"]
        supplier["source_urls"] = site["source_urls"]
        supplier["supplier_id"] = slug(f"{site['name']}__{supplier.get('role_hint')}")
        supplier["site_id"] = f"{supplier['supplier_id']}@{site['lat']},{site['lon']}"
        supplier.setdefault("correction_notes", []).append("FRN-9C546CCC918C61 generic unresolved node split to material-relevant candidate site.")
        changes.append(
            {
                "record_index": record_index,
                "component": record.get("component"),
                "chosen_site": site["name"],
                "site_key": site_key,
                "lat": site["lat"],
                "lon": site["lon"],
                "source_urls": " | ".join(site["source_urls"]),
            }
        )
    return changes


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    changes: list[dict[str, Any]] = []
    for idx, record in enumerate(records, 1):
        changes.extend(update_toray_supplier(record, idx))

    INPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if changes:
        with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(changes[0].keys()))
            writer.writeheader()
            writer.writerows(changes)
    else:
        OUT_CSV.write_text("", encoding="utf-8")
    lines = [
        "# FRN-9C546CCC918C61 Site Split",
        "",
        f"- JSON updated: `{INPUT_JSON.as_posix()}`",
        f"- Changes: **{len(changes)}**",
        "",
        "Generic unresolved `FRN-0F56088BEA4986` candidates were split by material context:",
        "",
        "- Textile/fiber: FRN-52C1B43CDDE847, Inazawa/Aichi.",
        "- Polymer/resin: FRN-F3FFB924CD457D.",
        "- Composite/carbon/fiber: FRN-8A956B599D7510.",
        "",
        f"Detail CSV: `{OUT_CSV.as_posix()}`",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {INPUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")
    print(f"Changes: {len(changes)}")


if __name__ == "__main__":
    main()
