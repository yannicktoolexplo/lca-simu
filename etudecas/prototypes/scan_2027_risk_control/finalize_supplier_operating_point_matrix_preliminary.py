#!/usr/bin/env python3
"""Assemble a comparable 100/93/80 supplier screen from one engine generation."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_incident_preliminary as campaign,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as protocol,
)


DEFAULT_DEGRADED_SCREEN = (
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_degraded_merged_current_engine_20260904_v1"
    / "supplier_operating_point_comparison.csv"
)
DEFAULT_CURRENT_HEALTHY = (
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_op100_merged_current_engine_20260904_v1"
    / "op100_current_engine_audit.csv"
)
DEFAULT_OUTPUT = (
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_matrix_current_engine_preliminary_20260904_v1"
)
POINT_IDS = ("op_100", "op_93", "op_80")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _key(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row["operating_point_id"]),
        str(row["chain_id"]),
        str(row["incident_mechanism"]),
        int(row["seed"]),
    )


def _dominant_rows(
    rows: Sequence[Mapping[str, Any]], metric: str
) -> list[Mapping[str, Any]]:
    by_chain: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if campaign._truthy(row.get("incident_physically_exercised")):
            by_chain.setdefault(str(row["chain_id"]), []).append(row)
    dominant = [
        max(
            chain_rows,
            key=lambda row: (
                float(row[metric]),
                float(row["backlog_qty_days_delta"]),
                -float(row["production_delta"]),
                str(row["incident_mechanism"]),
            ),
        )
        for chain_rows in by_chain.values()
    ]
    return sorted(
        dominant,
        key=lambda row: (
            -float(row[metric]),
            -float(row["backlog_qty_days_delta"]),
            float(row["production_delta"]),
            str(row["chain_id"]),
        ),
    )


def _ranking_outputs(
    rows: Sequence[Mapping[str, Any]], output: Path
) -> dict[str, Any]:
    ranking_rows: list[dict[str, Any]] = []
    top3_global: dict[str, list[dict[str, Any]]] = {}
    top3_product: dict[str, list[dict[str, Any]]] = {}
    dominant_global_by_point_chain: dict[tuple[str, str], Mapping[str, Any]] = {}
    global_rank_by_point_chain: dict[tuple[str, str], int] = {}
    for point_id in POINT_IDS:
        point_rows = [row for row in rows if row["operating_point_id"] == point_id]
        global_order = _dominant_rows(point_rows, "global_service_loss_pp")
        product_order = _dominant_rows(point_rows, "service_loss_pp")
        product_rank = {
            str(row["chain_id"]): rank
            for rank, row in enumerate(product_order, start=1)
        }
        for rank, row in enumerate(global_order, start=1):
            chain_id = str(row["chain_id"])
            dominant_global_by_point_chain[(point_id, chain_id)] = row
            global_rank_by_point_chain[(point_id, chain_id)] = rank
            ranking_rows.append(
                {
                    "operating_point_id": point_id,
                    "global_rank": rank,
                    "product_rank": product_rank.get(chain_id, ""),
                    "chain_id": chain_id,
                    "supplier_id": row["supplier_id"],
                    "item_id": row["item_id"],
                    "factory_id": row["factory_id"],
                    "product_id": row["product_id"],
                    "dominant_incident_mechanism": row["incident_mechanism"],
                    "global_service_loss_pp": row["global_service_loss_pp"],
                    "product_service_loss_pp": row["service_loss_pp"],
                    "backlog_qty_days_delta": row["backlog_qty_days_delta"],
                    "production_delta": row["production_delta"],
                    "incident_physically_exercised": row[
                        "incident_physically_exercised"
                    ],
                }
            )
        top3_global[point_id] = [
            dict(row)
            for row in global_order
            if float(row["global_service_loss_pp"]) > 1e-12
        ][:3]
        top3_product[point_id] = [
            dict(row)
            for row in product_order
            if float(row["service_loss_pp"]) > 1e-12
        ][:3]
    campaign._write_csv(
        output / "network_priority_ranking_all_states.csv",
        ranking_rows,
        list(ranking_rows[0]) if ranking_rows else [],
    )

    global_sets = {
        point: {str(row["chain_id"]) for row in selected}
        for point, selected in top3_global.items()
    }
    product_sets = {
        point: {str(row["chain_id"]) for row in selected}
        for point, selected in top3_product.items()
    }

    def intersections(sets: Mapping[str, set[str]]) -> dict[str, list[str]]:
        return {
            "all_three": sorted(set.intersection(*(sets[point] for point in POINT_IDS))),
            "op100_op93": sorted(sets["op_100"] & sets["op_93"]),
            "op93_op80": sorted(sets["op_93"] & sets["op_80"]),
            "op100_op80": sorted(sets["op_100"] & sets["op_80"]),
            "union": sorted(set.union(*(sets[point] for point in POINT_IDS))),
        }

    stability_rows: list[dict[str, Any]] = []
    for chain_id in sorted(set.union(*global_sets.values())):
        for point_id in POINT_IDS:
            row = dominant_global_by_point_chain.get((point_id, chain_id))
            stability_rows.append(
                {
                    "chain_id": chain_id,
                    "operating_point_id": point_id,
                    "in_global_top3": chain_id in global_sets[point_id],
                    "global_rank": global_rank_by_point_chain.get(
                        (point_id, chain_id), ""
                    ),
                    "supplier_id": "" if row is None else row["supplier_id"],
                    "item_id": "" if row is None else row["item_id"],
                    "factory_id": "" if row is None else row["factory_id"],
                    "product_id": "" if row is None else row["product_id"],
                    "dominant_incident_mechanism": (
                        "" if row is None else row["incident_mechanism"]
                    ),
                    "global_service_loss_pp": (
                        "" if row is None else row["global_service_loss_pp"]
                    ),
                    "product_service_loss_pp": (
                        "" if row is None else row["service_loss_pp"]
                    ),
                }
            )
    campaign._write_csv(
        output / "top3_supplier_stability.csv",
        stability_rows,
        list(stability_rows[0]) if stability_rows else [],
    )
    payload = {
        "selection_rule": (
            "physically_exercised_cases_only; strictly_positive_loss_only; "
            "no_composite_score"
        ),
        "top3_global_by_operating_point": top3_global,
        "top3_product_by_operating_point": top3_product,
        "global_top3_intersections": intersections(global_sets),
        "product_top3_intersections": intersections(product_sets),
    }
    campaign._write_json(output / "top3_by_operating_point.json", payload)
    return payload


def finalize(*, degraded_screen: Path, current_healthy: Path, output: Path) -> None:
    degraded_screen = degraded_screen.resolve()
    current_healthy = current_healthy.resolve()
    output = output.resolve()
    degraded_rows = [
        row
        for row in campaign._read_csv(degraded_screen)
        if str(row["operating_point_id"]) in {"op_93", "op_80"}
        and int(row["seed"]) == protocol.SCREENING_SEED
    ]
    healthy_rows = [
        row
        for row in campaign._read_csv(current_healthy)
        if str(row["operating_point_id"]) == "op_100"
        and int(row["seed"]) == protocol.SCREENING_SEED
    ]
    rows = [*healthy_rows, *degraded_rows]
    keyed = {_key(row): row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError("Duplicate operating-point incident rows")
    expected_rows_per_point = 18 * len(campaign.MECHANISMS)
    counts = {
        point_id: sum(str(row["operating_point_id"]) == point_id for row in rows)
        for point_id in POINT_IDS
    }
    if any(count != expected_rows_per_point for count in counts.values()):
        raise ValueError(
            "Incomplete 18-lane/two-cause matrix: "
            + ", ".join(f"{point}={count}" for point, count in counts.items())
        )
    expected_mechanisms = set(campaign.MECHANISMS)
    for point_id in POINT_IDS:
        point_rows = [row for row in rows if row["operating_point_id"] == point_id]
        if len({str(row["chain_id"]) for row in point_rows}) != 18:
            raise ValueError(f"{point_id} does not contain 18 distinct supplier lanes")
        if {str(row["incident_mechanism"]) for row in point_rows} != expected_mechanisms:
            raise ValueError(f"{point_id} does not contain the same two incident causes")
    current_engine_sha = protocol.sha256_file(protocol.DEFAULT_ENGINE)
    missing_sha = [row for row in rows if not str(row.get("engine_sha256") or "")]
    wrong_sha = [
        row
        for row in rows
        if str(row.get("engine_sha256") or "").casefold()
        != current_engine_sha.casefold()
    ]
    if missing_sha or wrong_sha:
        raise ValueError(
            "Refusing a false comparison: all 108 rows must carry the same current "
            f"engine SHA (missing={len(missing_sha)}, wrong={len(wrong_sha)})"
        )
    rows = sorted(keyed.values(), key=_key)
    output.mkdir(parents=True, exist_ok=True)
    detail_path = output / "supplier_operating_point_comparison.csv"
    campaign._write_csv(detail_path, rows, campaign.DETAIL_FIELDS)
    summary_fields, summaries = campaign._summary_rows(rows)
    campaign._write_csv(
        output / "supplier_operating_point_comparison_summary.csv",
        summaries,
        summary_fields,
    )
    priority = campaign._priority_outputs(rows, output)
    all_state_rankings = _ranking_outputs(rows, output)
    campaign._write_json(
        output / "campaign_manifest.json",
        {
            "schema_version": (
                "etudecas.supplier_operating_point_matrix_current_engine."
                "preliminary.v1"
            ),
            "status": "complete",
            "evidence_status": "PRELIMINARY_ONE_SEED_SCREENING",
            "detail_row_count": len(rows),
            "row_count_by_operating_point": counts,
            "lane_count": 18,
            "incident_mechanisms": list(campaign.MECHANISMS),
            "seed_ids": [protocol.SCREENING_SEED],
            "same_engine_for_all_108_rows": True,
            "engine_sha256": current_engine_sha,
            "quality_branch_included": False,
            "supplier_state_dependent_risks_enabled": False,
            "historical_incident_probability_estimated": False,
            "primary_ranking_metric": "global_service_loss_pp",
            "priority_selection": priority,
            "all_state_top3_analysis": all_state_rankings,
            "limits": [
                "one seed per supplier lane and incident mechanism",
                "incidents are hypotheses, not observed supplier probabilities",
                "op_80 is globally near 80% but asymmetric between products",
            ],
            "inputs": {
                "degraded_screen": str(degraded_screen),
                "degraded_screen_sha256": _sha256(degraded_screen),
                "current_healthy": str(current_healthy),
                "current_healthy_sha256": _sha256(current_healthy),
            },
            "completed_at_utc": _now(),
        },
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--degraded-screen", type=Path, default=DEFAULT_DEGRADED_SCREEN)
    parser.add_argument("--current-healthy", type=Path, default=DEFAULT_CURRENT_HEALTHY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    finalize(
        degraded_screen=args.degraded_screen,
        current_healthy=args.current_healthy,
        output=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
