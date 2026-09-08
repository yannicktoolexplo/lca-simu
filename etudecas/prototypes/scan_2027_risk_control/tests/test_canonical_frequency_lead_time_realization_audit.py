from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_lead_time_realization_audit import (
    COMPARISON_FILENAME,
    DETAIL_FILENAME,
    FIGURE_FILENAME,
    REPORT_FILENAME,
    analyze_lead_time_realization,
    discover_artifact_dirs,
    run_lead_time_realization_audit,
)


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _write_cell(
    root: Path,
    *,
    cell_id: str,
    amplitude_percent: float,
    applied_multipliers: list[float],
    realized_lead_days: list[int],
    phase_seed: int = 17,
    simulation_seed: int = 320260,
    include_stress: bool = False,
) -> Path:
    artifact = root / "cells" / cell_id / "attempts" / "attempt_001" / "artifacts"
    snapshot = (
        artifact
        / "provenance"
        / "source_snapshot"
        / "external"
        / "study_config__canonical_frequency_study_config.json"
    )
    snapshot.parent.mkdir(parents=True)
    config = {
        "name": f"frequency_test__{cell_id}",
        "identification": {
            "enabled_input_signals": ["supplier_lead_time_multiplier"],
            "peak_fraction": {
                "supplier_lead_time_multiplier": amplitude_percent / 100.0,
            },
            "phase_seed": phase_seed,
        },
        "operating_conditions": [
            {
                "name": "nominal_capacity",
                "supplier_lead_time_baseline": 1.0,
            },
            *(
                [
                    {
                        "name": "supplier_stress_capacity",
                        "supplier_lead_time_baseline": 1.2,
                    }
                ]
                if include_stress
                else []
            ),
        ],
        "campaign": {"seed": simulation_seed},
    }
    snapshot.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    protocol = {
        "schema_version": "scan.canonical_frequency_protocol.v1",
        "status": "complete_designed",
        "config": {
            "snapshot_relative_path": str(snapshot.relative_to(artifact)).replace("\\", "/"),
            "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        },
    }
    encoded_protocol = json.dumps(protocol, indent=2, sort_keys=True).encode("utf-8")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "canonical_frequency_protocol.json").write_bytes(encoded_protocol)
    (artifact / "canonical_frequency_manifest.json").write_bytes(encoded_protocol)
    (artifact.parent / "execution_request.json").write_text(
        json.dumps({"cell_id": cell_id}), encoding="utf-8"
    )

    days = list(range(len(applied_multipliers)))
    condition_inputs = [
        ("nominal_capacity", applied_multipliers, realized_lead_days),
        *(
            [
                (
                    "supplier_stress_capacity",
                    [value * 1.2 for value in applied_multipliers],
                    [math.ceil(35 * value * 1.2) for value in applied_multipliers],
                )
            ]
            if include_stress
            else []
        ),
    ]
    for condition, condition_multipliers, condition_realized in condition_inputs:
        data = (
            artifact
            / "runs"
            / condition
            / "excited"
            / "supplier_lead_time_multiplier"
            / "canonical_feedback"
            / f"seed_{simulation_seed}"
            / "data"
        )
        data.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "day": day,
                    "supplier_id": "SUP-1",
                    "dst_node_id": "PLANT-1",
                    "item_id": "item:1",
                    "edge_id": "edge:SUP-1_TO_PLANT-1_1",
                    "event_ids": f"frequency_lead_time_d{day}",
                    "lead_time_multiplier": multiplier,
                    "lead_time_extra_days": 0.0,
                    "quality_delay_days": 0.0,
                }
                for day, multiplier in zip(days, condition_multipliers)
            ]
        ).to_csv(data / "supplier_risk_events_applied_daily.csv", index=False)
        pd.DataFrame(
            [
                {
                    "day": day,
                    "src_node_id": "SUP-1",
                    "dst_node_id": "PLANT-1",
                    "item_id": "item:1",
                    "shipped_qty": 100.0,
                    "lead_days": lead_days,
                }
                for day, lead_days in zip(days, condition_realized)
            ]
        ).to_csv(data / "production_supplier_shipments_daily.csv", index=False)
        pd.DataFrame(
            [
                {
                    "edge_id": "edge:SUP-1_TO_PLANT-1_1",
                    "planned_lead_time_days": 35.0,
                }
            ]
        ).to_csv(data / "supplier_nominal_parameters.csv", index=False)
    return artifact


def test_equal_integer_delays_block_local_amplitude_conclusion_and_preserve_sources(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    half_percent = _write_cell(
        source_root,
        cell_id="confirmatory__amp_0p5pct__phase_17",
        amplitude_percent=0.5,
        applied_multipliers=[0.995, 1.005],
        realized_lead_days=[35, 36],
        include_stress=True,
    )
    one_percent = _write_cell(
        source_root,
        cell_id="pilot__amp_1pct__phase_17",
        amplitude_percent=1.0,
        applied_multipliers=[0.99, 1.01],
        realized_lead_days=[35, 36],
        include_stress=True,
    )
    before = _hashes(source_root)

    result = run_lead_time_realization_audit(
        [half_percent, one_percent], tmp_path / "audit"
    )

    assert _hashes(source_root) == before
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["claims"]["source_artifacts_modified"] is False
    assert payload["claims"]["requested_amplitudes_realized_as_distinct_inputs"] is False
    assert payload["claims"]["local_derivative_conclusion_blocked"] is True
    assert (
        payload["claims"][
            "local_derivative_conclusion_blocked_by_identical_realized_input"
        ]
        is True
    )
    assert payload["claims"]["local_derivative_claimed"] is False
    comparison = payload["comparisons"][0]
    assert comparison["left_requested_amplitude_percent"] == 0.5
    assert comparison["right_requested_amplitude_percent"] == 1.0
    assert comparison["requested_multiplier_difference_observation_count"] == 4
    assert comparison["realized_lead_days_mismatch_observation_count"] == 0
    assert comparison["realized_input_equivalent_on_overlap"] is True
    assert comparison["local_amplitude_conclusion_blocked"] is True

    observations = pd.read_csv(tmp_path / "audit" / DETAIL_FILENAME)
    assert set(observations["requested_amplitude_percent"]) == {0.5, 1.0}
    assert set(observations["nominal_lead_days"]) == {35.0}
    assert set(observations["realized_lead_days"]) == {35, 36, 42, 43}
    assert observations["ceil_rule_matches_realized"].all()
    comparisons = pd.read_csv(tmp_path / "audit" / COMPARISON_FILENAME)
    assert bool(comparisons.loc[0, "realized_input_equivalent_on_overlap"])

    figure_path = tmp_path / "audit" / FIGURE_FILENAME
    assert figure_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert figure_path.stat().st_size > 1_000
    figure = payload["figure"]
    assert figure["requested_amplitudes_percent"] == [0.5, 1.0]
    assert figure["conditions"] == [
        "nominal_capacity",
        "supplier_stress_capacity",
    ]
    assert figure["metrics"] == [
        "applied_lead_time_multiplier",
        "realized_lead_days",
    ]
    assert figure["comparison_uses_shared_observations"] is True
    assert figure["shared_observation_key_count_per_cell"] == 4
    stress_half_percent = next(
        row
        for row in figure["series"]
        if row["condition"] == "supplier_stress_capacity"
        and row["requested_amplitude_percent"] == 0.5
    )
    assert math.isclose(stress_half_percent["requested_multiplier_minimum"], 1.194)
    assert math.isclose(stress_half_percent["requested_multiplier_maximum"], 1.206)
    assert stress_half_percent["realized_lead_days_values"] == [42, 43]

    report_path = tmp_path / "audit" / REPORT_FILENAME
    report = report_path.read_text(encoding="utf-8")
    assert f"]({FIGURE_FILENAME})" in report
    assert "Capacité nominale" in report
    assert "Fournisseur sous tension" in report
    assert "conclusion locale bloquée" in report


def test_distinct_integer_delays_meet_only_the_realization_necessary_condition(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    half_percent = _write_cell(
        source_root,
        cell_id="amp_0p5",
        amplitude_percent=0.5,
        applied_multipliers=[0.995, 1.005],
        realized_lead_days=[35, 36],
    )
    five_percent = _write_cell(
        source_root,
        cell_id="amp_5",
        amplitude_percent=5.0,
        applied_multipliers=[0.95, 1.05],
        realized_lead_days=[math.ceil(35 * 0.95), math.ceil(35 * 1.05)],
    )

    payload = analyze_lead_time_realization([half_percent, five_percent])

    assert payload["claims"]["requested_amplitudes_realized_as_distinct_inputs"] is True
    assert payload["claims"]["local_derivative_conclusion_blocked"] is False
    assert payload["claims"]["local_derivative_claimed"] is False
    assert payload["claims"]["realized_input_distinctness_is_only_a_necessary_condition"]
    comparison = payload["comparisons"][0]
    assert comparison["realized_lead_days_mismatch_observation_count"] == 2
    assert comparison["realized_input_equivalent_on_overlap"] is False


def test_campaign_discovery_returns_complete_lead_time_cells(tmp_path: Path) -> None:
    source_root = tmp_path / "campaign"
    first = _write_cell(
        source_root,
        cell_id="amp_0p5",
        amplitude_percent=0.5,
        applied_multipliers=[1.005],
        realized_lead_days=[36],
    )
    second = _write_cell(
        source_root,
        cell_id="amp_1",
        amplitude_percent=1.0,
        applied_multipliers=[1.01],
        realized_lead_days=[36],
    )

    assert discover_artifact_dirs(source_root) == sorted([first.resolve(), second.resolve()])
