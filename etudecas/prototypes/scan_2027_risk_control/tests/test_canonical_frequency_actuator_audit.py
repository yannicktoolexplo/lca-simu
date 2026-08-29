from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_actuator_audit import (
    ACTUATOR_INPUTS,
    run_actuator_audit,
)


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_actuator_audit_is_separate_and_reports_realized_duty_cycle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "canonical_frequency_protocol.json").write_text(
        json.dumps({"measured_days": 4}), encoding="utf-8"
    )
    for input_name in ACTUATOR_INPUTS:
        data_dir = (
            source
            / "actuator_probe"
            / "excited"
            / input_name
            / "mrp_reference"
            / "seed_17"
            / "data"
        )
        data_dir.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "day": day,
                    "action": input_name,
                    "requested": 1.05,
                    "effective": 1.05,
                    "executed_control_volume_qty": (
                        10.0 if input_name != "production_target_multiplier" or day == 2 else 0.0
                    ),
                }
                for day in range(4)
            ]
        ).to_csv(data_dir / "canonical_action_ledger.csv", index=False)
    before = _hashes(source)

    result = run_actuator_audit(source, tmp_path / "audit")

    assert _hashes(source) == before
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["seed"] == 17
    assert payload["claims"]["source_package_modified"] is False
    rows = pd.read_csv(result["csv_path"]).set_index("action")
    assert rows.loc["order_multiplier", "realized_positive_volume_day_count"] == 4
    assert (
        rows.loc[
            "production_target_multiplier", "realized_positive_volume_day_count"
        ]
        == 1
    )
