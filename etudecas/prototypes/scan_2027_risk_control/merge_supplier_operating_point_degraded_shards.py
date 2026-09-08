#!/usr/bin/env python3
"""Merge disjoint/resumed degraded supplier screens without masking conflicts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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


DEFAULT_INPUTS = (
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_incidents_accelerated_20260904_v1",
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_incidents_reverse_20260904_v1",
)
DEFAULT_OUTPUT = (
    protocol.ARTIFACT_PARENT
    / "supplier_operating_point_degraded_merged_current_engine_20260904_v1"
)
POINT_IDS = ("op_93", "op_80")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row["operating_point_id"]),
        str(row["chain_id"]),
        str(row["incident_mechanism"]),
        int(row["seed"]),
    )


def _canonical_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: "" if row.get(field) is None else str(row.get(field))
        for field in campaign.DETAIL_FIELDS
    }


def _evidence_key(payload: Mapping[str, Any]) -> tuple[str, str, str, int] | None:
    point = payload.get("operating_point") or {}
    incident = payload.get("incident")
    metrics = payload.get("metrics") or {}
    point_id = str(point.get("operating_point_id") or "")
    seed = int(metrics.get("seed") or -1)
    if point_id not in POINT_IDS or seed != protocol.SCREENING_SEED:
        return None
    if not incident:
        return (point_id, "__baseline__", "", seed)
    return (
        point_id,
        str(incident.get("chain_id") or ""),
        str(incident.get("incident_mechanism") or ""),
        seed,
    )


def merge(*, inputs: Sequence[Path], output: Path) -> None:
    sources = [path.resolve() for path in inputs]
    output = output.resolve()
    current_engine_sha = protocol.sha256_file(protocol.DEFAULT_ENGINE)
    merged: dict[tuple[str, str, str, int], dict[str, str]] = {}
    selected_source: dict[tuple[str, str, str, int], Path] = {}
    duplicate_count = 0
    for source in sources:
        detail_path = source / "supplier_operating_point_comparison.csv"
        for row in campaign._read_csv(detail_path):
            if (
                str(row["operating_point_id"]) not in POINT_IDS
                or int(row["seed"]) != protocol.SCREENING_SEED
            ):
                continue
            if str(row.get("engine_sha256") or "").casefold() != current_engine_sha.casefold():
                continue
            key = _row_key(row)
            canonical = _canonical_row(row)
            existing = merged.get(key)
            if existing is not None:
                duplicate_count += 1
                if existing != canonical:
                    differing = [
                        field
                        for field in campaign.DETAIL_FIELDS
                        if existing.get(field) != canonical.get(field)
                    ]
                    raise ValueError(
                        f"Divergent duplicate {key}: fields={','.join(differing)}"
                    )
                continue
            merged[key] = canonical
            selected_source[key] = source
    evidence_candidates: dict[
        tuple[str, str, str, int], list[tuple[Path, Path]]
    ] = {}
    for source in sources:
        for path in sorted((source / "case_evidence").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            key = _evidence_key(payload)
            if key is not None:
                evidence_candidates.setdefault(key, []).append((source, path))

    # Rebuild every detail row from the atomic evidence.  Besides keeping the
    # merged table reproducible, this lets interpretation-only corrections
    # (notably availability events that prevent shipment) be applied to cached
    # engine results without rerunning the simulation.
    for key in list(merged):
        preferred_source = selected_source[key]
        incident_candidates = evidence_candidates.get(key) or []
        baseline_key = (key[0], "__baseline__", "", key[3])
        baseline_candidates = evidence_candidates.get(baseline_key) or []
        if not incident_candidates or not baseline_candidates:
            raise ValueError(f"Missing atomic evidence needed to rebuild {key}")
        _, incident_path = next(
            (
                candidate
                for candidate in incident_candidates
                if candidate[0] == preferred_source
            ),
            incident_candidates[0],
        )
        _, baseline_path = next(
            (
                candidate
                for candidate in baseline_candidates
                if candidate[0] == preferred_source
            ),
            baseline_candidates[0],
        )
        rebuilt = _canonical_row(
            campaign._detail_row(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                json.loads(incident_path.read_text(encoding="utf-8")),
            )
        )
        if _row_key(rebuilt) != key:
            raise ValueError(f"Atomic evidence rebuilt the wrong key: {key}")
        merged[key] = rebuilt

    rows = sorted(merged.values(), key=_row_key)
    counts = {
        point_id: sum(row["operating_point_id"] == point_id for row in rows)
        for point_id in POINT_IDS
    }
    expected_per_point = 18 * len(campaign.MECHANISMS)
    if any(count != expected_per_point for count in counts.values()):
        raise ValueError(
            "Combined shard coverage is incomplete: "
            + ", ".join(f"{point}={count}" for point, count in counts.items())
        )
    if len(rows) != 2 * expected_per_point:
        raise ValueError(f"Expected 72 degraded rows, found {len(rows)}")
    output.mkdir(parents=True, exist_ok=True)
    detail_output = output / "supplier_operating_point_comparison.csv"
    campaign._write_csv(detail_output, rows, campaign.DETAIL_FIELDS)
    summary_fields, summaries = campaign._summary_rows(rows)
    campaign._write_csv(
        output / "supplier_operating_point_comparison_summary.csv",
        summaries,
        summary_fields,
    )

    required_evidence_keys = set(merged) | {
        (point_id, "__baseline__", "", protocol.SCREENING_SEED)
        for point_id in POINT_IDS
    }
    evidence_dir = output / "case_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_index: list[dict[str, Any]] = []
    for key in sorted(required_evidence_keys):
        candidates = evidence_candidates.get(key) or []
        if not candidates:
            raise ValueError(f"Missing atomic case evidence for {key}")
        preferred_source = selected_source.get(key)
        source, evidence_path = next(
            (
                candidate
                for candidate in candidates
                if preferred_source is not None and candidate[0] == preferred_source
            ),
            candidates[0],
        )
        destination = evidence_dir / evidence_path.name
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(evidence_path, temporary)
        temporary.replace(destination)
        evidence_index.append(
            {
                "operating_point_id": key[0],
                "chain_id": key[1],
                "incident_mechanism": key[2],
                "seed": key[3],
                "selected_source": str(source),
                "source_evidence": str(evidence_path),
                "merged_evidence": str(destination),
                "sha256": _sha256(destination),
            }
        )
    campaign._write_json(output / "case_evidence_index.json", evidence_index)
    campaign._write_json(
        output / "merge_manifest.json",
        {
            "schema_version": "etudecas.supplier_degraded_shard_merge.v1",
            "status": "complete",
            "row_count": len(rows),
            "row_count_by_operating_point": counts,
            "atomic_case_evidence_count": len(evidence_index),
            "duplicate_identical_row_count": duplicate_count,
            "duplicate_divergence_count": 0,
            "same_current_engine_for_all_rows": True,
            "rows_rebuilt_from_atomic_evidence": True,
            "physical_exercise_rule": {
                "supply_availability": "applied to at least one eligible requirement",
                "transport_delay": "applied to at least one positive shipment",
            },
            "engine_sha256": current_engine_sha,
            "quality_branch_included": False,
            "supplier_state_dependent_risks_enabled": False,
            "inputs": [
                {
                    "directory": str(source),
                    "detail_csv_sha256": _sha256(
                        source / "supplier_operating_point_comparison.csv"
                    ),
                }
                for source in sources
            ],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        dest="input_dirs",
        help="Repeat for each independent shard; defaults to forward and reverse.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    merge(inputs=args.input_dirs or DEFAULT_INPUTS, output=args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
