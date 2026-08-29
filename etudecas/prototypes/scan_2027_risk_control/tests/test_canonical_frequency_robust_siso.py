from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import canonical_frequency_robust_siso as robust
from etudecas.prototypes.scan_2027_risk_control import canonical_frequency_study as study


def _load_default_config() -> dict:
    return json.loads(robust.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(tmp_path: Path, *, profile: str = "confirmatory", **filters) -> dict:
    return robust.build_campaign_plan(
        robust.DEFAULT_CONFIG_PATH,
        repo_root=robust.REPO_ROOT,
        campaign_dir=tmp_path / "campaign",
        profile=profile,
        **filters,
    )


def _write_fake_complete_attempt(cell: dict) -> None:
    artifacts = Path(cell["cell_root"]) / "attempts" / "attempt_001" / "artifacts"
    artifacts.mkdir(parents=True)
    response_path = artifacts / "canonical_frequency_response.csv"
    headers = [
        "condition",
        "policy",
        "input_signal",
        "output_signal",
        "frequency_bin",
        "coherence",
        "valid_bin",
        "phase_deg",
        "elasticity_magnitude",
        "tested_amplitude_regime_trace_compatible",
    ]
    seed_index = [320260, 421267, 522274, 623281, 724288].index(cell["phase_seed"])
    phase = 179.0 if seed_index % 2 == 0 else -179.0
    with response_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for condition in cell["operating_conditions"]:
            writer.writerow(
                {
                    "condition": condition,
                    "policy": "v2_closed_loop",
                    "input_signal": robust.TARGET_INPUT_SIGNAL,
                    "output_signal": "probe_destination_arrivals_qty",
                    "frequency_bin": 1,
                    "coherence": 0.9,
                    "valid_bin": True,
                    "phase_deg": phase,
                    "elasticity_magnitude": 1.0
                    + float(cell["amplitude_percent"]) / 100.0
                    + seed_index / 1000.0,
                    "tested_amplitude_regime_trace_compatible": True,
                }
            )
    protocol = {
        "schema_version": "scan.canonical_frequency_protocol.v1",
        "status": "complete_designed",
        "config": {"sha256": cell["config_sha256"]},
        "output_sha256": {response_path.name: _sha256(response_path)},
    }
    encoded = json.dumps(protocol, indent=2, sort_keys=True).encode("utf-8")
    (artifacts / "canonical_frequency_protocol.json").write_bytes(encoded)
    (artifacts / "canonical_frequency_manifest.json").write_bytes(encoded)


def test_master_protocol_is_strict_and_encodes_requested_confirmatory_matrix() -> None:
    normalized = robust.validate_robust_siso_config(_load_default_config())

    confirmatory = normalized["profiles"]["confirmatory"]
    assert confirmatory["amplitudes_percent"] == (0.5, 1.0, 2.0, 5.0)
    assert len(confirmatory["phase_seeds"]) == 5
    assert confirmatory["measured_periods"] == 10
    assert confirmatory["discarded_periods"] == 1
    assert confirmatory["retained_periods"] == 9
    assert normalized["profiles"]["pilot"]["confirmatory"] is False
    assert normalized["profiles"]["pilot"]["measured_periods"] < 10
    assert all(value is False for value in normalized["claims"].values())


def test_strict_validator_rejects_unknown_keys_and_weakened_confirmatory_grid() -> None:
    payload = _load_default_config()
    payload["unknown"] = True
    with pytest.raises(robust.RobustSisoContractError, match="extra=unknown"):
        robust.validate_robust_siso_config(payload)

    payload = _load_default_config()
    payload["profiles"]["confirmatory"]["phase_seeds"] = [1, 2, 3, 4]
    with pytest.raises(robust.RobustSisoContractError, match="at least five"):
        robust.validate_robust_siso_config(payload)


def test_plan_builds_full_grid_but_filters_execution_subset(tmp_path: Path) -> None:
    plan = _plan(
        tmp_path,
        amplitude_filters_percent=(2.0,),
        phase_filters=(522274,),
    )

    assert plan["configured_cell_count"] == 20
    assert plan["selected_cell_count"] == 1
    selected = [cell for cell in plan["cells"] if cell["selected"]]
    assert selected[0]["cell_id"] == "confirmatory__amp_2pct__phase_522274"
    assert plan["campaign_dir"].endswith("confirmatory")
    assert plan["enabled_input_signals"] == [robust.TARGET_INPUT_SIGNAL]
    assert plan["actuator_probe_enabled"] is False


def test_pilot_is_explicitly_nonconfirmatory_and_short(tmp_path: Path) -> None:
    plan = _plan(tmp_path, profile="pilot")

    assert plan["configured_cell_count"] == 4
    assert plan["confirmatory"] is False
    assert all(cell["confirmatory"] is False for cell in plan["cells"])
    assert all(cell["retained_periods"] == 3 for cell in plan["cells"])
    assert "non-confirmatory" in plan["profile_interpretation"]


def test_cell_config_enables_only_lead_time_and_disables_actuator(tmp_path: Path) -> None:
    plan = _plan(
        tmp_path,
        amplitude_filters_percent=(0.5,),
        phase_filters=(320260,),
    )
    cell = next(cell for cell in plan["cells"] if cell["selected"])
    generated = cell["config_payload"]

    assert generated["identification"]["enabled_input_signals"] == [
        "supplier_lead_time_multiplier"
    ]
    assert generated["identification"]["peak_fraction"]["supplier_lead_time_multiplier"] == 0.005
    assert generated["identification"]["measured_periods"] == 10
    assert generated["actuator_probe"]["enabled"] is False
    normalized = study.validate_frequency_config(generated)
    assert normalized["enabled_input_signals"] == ("supplier_lead_time_multiplier",)
    assert normalized["measured_periods"] == 10
    assert normalized["days"] == 1960
    assert cell["argv"][-3:] == [
        "--stage",
        "designed",
        "--no-plot",
    ]
    assert "canonical_frequency_study.py" in cell["command"]


def test_materialization_is_append_only_and_refuses_config_collision(tmp_path: Path) -> None:
    plan = _plan(tmp_path, profile="pilot")
    first_manifest = robust.materialize_plan(plan)
    second_manifest = robust.materialize_plan(plan)

    assert first_manifest.is_file()
    assert second_manifest.is_file()
    assert first_manifest != second_manifest
    first_cell = plan["cells"][0]
    support_by_field = {row["field"]: row for row in first_cell["support_files"]}
    assert set(support_by_field) == {"control_policy_json", "engine_profile"}
    for support in support_by_field.values():
        destination = Path(support["destination_path"])
        assert destination.is_file()
        assert _sha256(destination) == support["source_sha256"]
    cell_config = Path(plan["cells"][0]["config_path"])
    cell_config.write_text("{}\n", encoding="utf-8")
    with pytest.raises(robust.RobustSisoContractError, match="Refusing to overwrite"):
        robust.materialize_plan(plan)


def test_incomplete_matrix_blocks_local_and_dynamic_claims(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    robust.materialize_plan(plan)

    aggregate, tables = robust.aggregate_campaign(plan)

    assert aggregate["coverage"]["complete_cell_count"] == 0
    assert aggregate["coverage"]["matrix_complete"] is False
    assert aggregate["claim_gate"]["local_derivative_proven"] is False
    assert aggregate["claim_gate"]["dynamic_closed_loop_proven"] is False
    assert aggregate["claim_gate"]["eligible_for_scientific_review"] is False
    assert len(tables["cell_coverage"]) == 20


def test_aggregate_reads_verified_cells_and_reports_phase_wrapped_dispersion(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    robust.materialize_plan(plan)
    for cell in plan["cells"]:
        _write_fake_complete_attempt(cell)

    aggregate, tables = robust.aggregate_campaign(plan)

    assert aggregate["coverage"]["complete_cell_count"] == 20
    assert aggregate["coverage"]["matrix_complete"] is True
    assert aggregate["claim_gate"]["eligible_for_scientific_review"] is True
    assert aggregate["claim_gate"]["local_derivative_proven"] is False
    assert aggregate["claim_gate"]["dynamic_closed_loop_proven"] is False
    assert aggregate["response_evidence"]["valid_row_count"] == 40
    assert len(tables["amplitude_summary"]) == 4
    assert len(tables["phase_summary"]) == 5
    assert len(tables["amplitude_line_dispersion"]) == 8
    assert len(tables["phase_line_dispersion"]) == 10
    assert max(
        row["phase_circular_std_deg"] for row in tables["amplitude_line_dispersion"]
    ) < 2.0

    aggregate_root = robust.write_aggregate(plan, aggregate, tables)
    assert (aggregate_root / "robust_siso_aggregate.json").is_file()
    assert (aggregate_root / "robust_siso_amplitude_line_dispersion.csv").is_file()
    assert (aggregate_root / "robust_siso_phase_line_dispersion.csv").is_file()
    assert (aggregate_root / "robust_siso_aggregate_ledger.csv").is_file()


def test_partial_attempt_is_not_complete_and_default_cli_is_plan_only(tmp_path: Path, capsys) -> None:
    plan = _plan(tmp_path, profile="pilot")
    robust.materialize_plan(plan)
    cell = plan["cells"][0]
    (Path(cell["cell_root"]) / "attempts" / "attempt_001" / "artifacts").mkdir(parents=True)

    assert robust.inspect_cell(cell)["state"] == "partial"
    args = robust.parse_args([])
    assert args.execute is False
    assert args.profile == "confirmatory"

    returncode = robust.main(
        [
            "--campaign-dir",
            str(tmp_path / "cli_campaign"),
            "--profile",
            "pilot",
            "--amplitude",
            "1",
            "--phase",
            "320260",
        ]
    )
    output = capsys.readouterr().out
    assert returncode == 0
    assert "Plan-only mode: no simulation was launched" in output
