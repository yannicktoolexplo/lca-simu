#!/usr/bin/env python3
"""Audit requested actuator commands versus realized physical operation days."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_study import (  # noqa: E402
    _actuator_realization_evidence,
)


SCHEMA_VERSION = "scan.canonical_frequency_actuator_realization_audit.v1"
ACTUATOR_INPUTS = (
    "order_multiplier",
    "safety_stock_multiplier",
    "production_target_multiplier",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_actuator_audit(
    artifact_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    source = Path(artifact_dir).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Scientific artifact directory does not exist: {source}")
    if destination == source or source in destination.parents:
        raise ValueError("output_dir must be outside the immutable source package.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {destination}")
    protocol_path = source / "canonical_frequency_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    measured_days = int(protocol.get("measured_days") or protocol["sampling"]["measured_days"])
    discovered_seeds: set[int] = set()
    for input_name in ACTUATOR_INPUTS:
        seed_root = source / "actuator_probe" / "excited" / input_name / "mrp_reference"
        for candidate in seed_root.glob("seed_*"):
            try:
                discovered_seeds.add(int(candidate.name.removeprefix("seed_")))
            except ValueError:
                continue
    if len(discovered_seeds) != 1:
        raise ValueError(
            "Expected exactly one common actuator seed, found: "
            + ", ".join(str(value) for value in sorted(discovered_seeds))
        )
    seed = discovered_seeds.pop()
    rows: list[dict[str, Any]] = []
    for input_name in ACTUATOR_INPUTS:
        result_dir = (
            source
            / "actuator_probe"
            / "excited"
            / input_name
            / "mrp_reference"
            / f"seed_{seed}"
        )
        ledger_path = result_dir / "data" / "canonical_action_ledger.csv"
        if not ledger_path.is_file():
            raise FileNotFoundError(f"Missing actuator action ledger: {ledger_path}")
        rows.append(
            _actuator_realization_evidence(
                ledger_path,
                input_name=input_name,
                measured_days=measured_days,
            )
        )
    frame = pd.DataFrame(rows)
    destination.mkdir(parents=True, exist_ok=True)
    csv_path = destination / "canonical_frequency_actuator_realization_audit.csv"
    json_path = destination / "canonical_frequency_actuator_realization_audit.json"
    frame.to_csv(csv_path, index=False)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_artifact_dir": str(source),
        "source_protocol": {
            "path": str(protocol_path),
            "sha256": _sha256(protocol_path),
        },
        "measured_days": measured_days,
        "seed": seed,
        "claims": {
            "source_package_modified": False,
            "executed_volume_is_incremental_causal_effect": False,
            "actuator_frequency_response_identified": False,
        },
        "rows": rows,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return {"csv_path": csv_path, "json_path": json_path, "payload": payload}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_actuator_audit(args.artifact_dir, args.output_dir)
    print(result["json_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ACTUATOR_INPUTS", "SCHEMA_VERSION", "run_actuator_audit"]
