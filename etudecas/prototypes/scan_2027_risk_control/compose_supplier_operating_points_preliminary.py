#!/usr/bin/env python3
"""Compose the accepted 93/80 operating points from additive fine runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)


ROOT = protocol.ARTIFACT_PARENT
DEFAULT_HIGH = (
    ROOT
    / "supplier_service_regime_fine_preliminary_20260904_v3"
    / "preliminary_operating_points.json"
)
DEFAULT_LOW = (
    ROOT
    / "supplier_service_regime_fine_preliminary_20260904_v1"
    / "preliminary_operating_points.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "supplier_service_regime_operating_points_preliminary_20260904_v1"
    / "preliminary_operating_points.json"
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _point(payload: dict[str, Any], point_id: str) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in payload.get("operating_points") or []
        if row.get("operating_point_id") == point_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Operating point is not unique: {point_id}")
    return matches[0]


def compose(high_path: Path, low_path: Path, output_path: Path) -> dict[str, Any]:
    high_path = high_path.resolve()
    low_path = low_path.resolve()
    high = _read(high_path)
    low = _read(low_path)
    if high.get("engine_sha256") != low.get("engine_sha256"):
        raise ValueError("Fine runs used different engines")
    points = [_point(high, "op_100"), _point(high, "op_93"), _point(low, "op_80")]
    if {row["degradation_family"] for row in points[1:]} != {
        "supplier_planned_lead"
    }:
        raise ValueError("The degraded points do not share the global lead axis")
    for row in points[1:]:
        service = float(row["screening_system_service"])
        target = float(row["target_service"])
        row["operating_point_label"] = (
            f"État simulé {service:.1%} global (cible {target:.0%}; "
            f"{'PF équilibrés' if row['balanced_products'] else 'PF asymétriques'})"
        )
    payload = {
        "schema_version": "etudecas.supplier_service_regime_operating_points_preliminary.v1",
        "status": "preliminary_operating_points_ready_for_network_screen",
        "selection_strategy": "one_common_global_supplier_lead_axis",
        "selected_family": "supplier_planned_lead",
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_supplier_performance": True,
        "engine_sha256": high["engine_sha256"],
        "source_manifests": [
            {"path": str(high_path), "sha256": protocol.sha256_file(high_path)},
            {"path": str(low_path), "sha256": protocol.sha256_file(low_path)},
        ],
        "operating_points": points,
    }
    protocol.write_json(output_path.resolve(), payload)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--high", type=Path, default=DEFAULT_HIGH)
    parser.add_argument("--low", type=Path, default=DEFAULT_LOW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = compose(args.high, args.low, args.output)
    for point in payload["operating_points"]:
        print(
            point["operating_point_id"],
            point.get("degradation_value"),
            point.get("screening_system_service", "reference"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
