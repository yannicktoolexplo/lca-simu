from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_closed_loop import (
    CanonicalClosedLoopContractError,
    FEEDBACK_POLICY,
    REFERENCE_POLICY,
    _closed_loop_claim,
    _effective_command_levers,
    _save_control_diagnostics_plot,
    parse_args,
    run_canonical_closed_loop,
    run_from_config,
)


FAKE_ENGINE = r'''
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--scenario-id", required=True)
parser.add_argument("--days", required=True, type=int)
parser.add_argument("--warmup-days", type=int, default=0)
parser.add_argument("--seed", required=True, type=int)
parser.add_argument("--control-policy-json", default="")
parser.add_argument("--control-policy-v2-json", default="")
parser.add_argument("--control-policy-v3-json", default="")
parser.add_argument("--controller-prime-during-warmup", action="store_true")
parser.add_argument("--supplier-risk-events-csv", default="")
parser.add_argument("--common-random-numbers", action="store_true")
parser.add_argument("--output-profile", choices=["compact", "full"], default="compact")
parser.add_argument("--skip-map", action="store_true")
parser.add_argument("--skip-plots", action="store_true")
parser.add_argument("--lot-trace", action="store_true")
parser.add_argument("--no-lot-trace", action="store_true")
parser.add_argument("--skip-lot-audit", action="store_true")
parser.add_argument("--supplier-state-dependent-risks", action="store_true")
parser.add_argument("--no-supplier-state-dependent-risks", action="store_true")
parser.add_argument(
    "--supplier-state-risk-observation-warmup-days", type=int, default=30
)
parser.add_argument("--mrp-demand-signal-smoothing-days", type=int, default=1)
parser.add_argument("--fake-lookahead", type=int, default=None)
parser.add_argument("--fake-future-access", action="store_true")
parser.add_argument("--fake-ledger-effective", type=float, default=1.1)
parser.add_argument("--fake-incomplete-full", action="store_true")
parser.add_argument("--fail", action="store_true")
args, _ = parser.parse_known_args()
if args.fail:
    raise SystemExit(17)

input_path = Path(args.input).resolve()
output = Path(args.output_dir)
(output / "data").mkdir(parents=True, exist_ok=True)
(output / "summaries").mkdir(parents=True, exist_ok=True)
if args.output_profile == "full" and not args.fake_incomplete_full:
    for name in (
        "production_input_consumption_daily.csv",
        "production_input_replenishment_shipments_daily.csv",
        "production_input_stocks_pivot.csv",
        "production_lot_events.csv",
        "production_lot_genealogy.csv",
        "lot_path_audit_issues.csv",
    ):
        (output / "data" / name).write_text("column\nvalue\n", encoding="utf-8")
    (output / "reports").mkdir(parents=True, exist_ok=True)
    (output / "reports" / "lot_path_audit.md").write_text(
        "# Lot audit\n", encoding="utf-8"
    )
    (output / "maps").mkdir(parents=True, exist_ok=True)
    (output / "maps" / "fake_map.html").write_text(
        "<html></html>\n", encoding="utf-8"
    )
    (output / "plots" / "factories").mkdir(parents=True, exist_ok=True)
    (output / "plots" / "factories" / "fake_plot.png").write_bytes(b"fake png")
control_policy_path = (
    args.control_policy_json
    or args.control_policy_v2_json
    or args.control_policy_v3_json
)
controlled = bool(control_policy_path)
claim = False
if controlled:
    claim = json.loads(Path(control_policy_path).read_text())["engine_claim"]
served = 9.0 if controlled else 8.0
pd.DataFrame(
    {
        "day": range(args.days),
        "demand": [10.0] * args.days,
        "served": [served] * args.days,
        "backlog_end": [(10.0 - served) * (day + 1) for day in range(args.days)],
        "inventory_total": [20.0] * args.days,
        "total_economic_exposure_day": [100.0] * args.days,
        "estimated_source_ordered_qty": [10.0] * args.days,
        "external_procured_ordered_qty": [0.0] * args.days,
        "supplier_capacity_binding_qty": [0.0] * args.days,
    }
).to_csv(output / "data" / "first_simulation_daily.csv", index=False)
if controlled:
    days = list(range(args.days))
    command_days = list(range(max(0, args.days - 1)))
    pd.DataFrame(
        {
            "day": days,
            "observation_hash": [f"hash-{day}" for day in days],
        }
    ).to_csv(
        output / "data" / "canonical_closed_loop_observations.csv", index=False
    )
    pd.DataFrame(
        {
            "decision_day": days,
            "effective_day": [day + 1 for day in days],
            "causal_lag_days": [1] * len(days),
            "observation_hash": [f"hash-{day}" for day in days],
        }
    ).to_csv(
        output / "data" / "canonical_closed_loop_decisions.csv", index=False
    )
    pd.DataFrame(
        {
            "decision_day": command_days,
            "effective_day": [day + 1 for day in command_days],
            "causal_lag_days": [1] * len(command_days),
            "active": [1] * len(command_days),
            # The neutral safety-stock value is retained for slew/audit
            # traceability but correctly has no physical action-ledger row.
            "effective_json": [
                json.dumps(
                    {
                        "order_multiplier": 1.1,
                        "safety_stock_multiplier": 1.0,
                    }
                )
            ]
            * len(command_days),
            "source_line": [1000 + day for day in command_days],
        }
    ).to_csv(
        output / "data" / "canonical_closed_loop_commands.csv", index=False
    )
    pd.DataFrame(
        {
            "day": [day + 1 for day in command_days],
            "decision_day": command_days,
            "effective_day": [day + 1 for day in command_days],
            "causal_lag_days": [1] * len(command_days),
            "control_source_kind": ["state_feedback_generated_online"]
            * len(command_days),
            "source_line": [1000 + day for day in command_days],
            "action": ["order_multiplier"] * len(command_days),
            "effective": [args.fake_ledger_effective] * len(command_days),
            "status": ["applied"] * len(command_days),
            "executed_control_volume_qty": [1.0] * len(command_days),
        }
    ).to_csv(output / "data" / "canonical_action_ledger.csv", index=False)
summary = {
    "input_file": str(input_path),
    "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    "scenario_id": args.scenario_id,
    "sim_days": args.days,
    "policy": {
        "seed": args.seed,
        "common_random_numbers": args.common_random_numbers,
        "output_profile": args.output_profile,
        "lot_trace_enabled": args.lot_trace and not args.no_lot_trace,
        "initialization_policy": {
            "mrp_demand_signal_smoothing_days": args.mrp_demand_signal_smoothing_days
        },
        "supplier_state_dependent_risk": {
            "enabled": args.supplier_state_dependent_risks
            and not args.no_supplier_state_dependent_risks,
            "observation_warmup_days": (
                args.supplier_state_risk_observation_warmup_days
            ),
        },
        "control_provider": {
            "closed_loop_claimed": claim,
            "causal_lag_days": 1,
            "provider_causal_contract_satisfied": True,
            "observation_causal_contract_satisfied": (
                args.mrp_demand_signal_smoothing_days == 1
                and (args.fake_lookahead is None or args.fake_lookahead == 0)
                and not args.fake_future_access
            ),
            "controller_observation_forecast_lookahead_days": (
                args.fake_lookahead
                if args.fake_lookahead is not None
                else max(0, args.mrp_demand_signal_smoothing_days - 1)
            ),
            "demand_realization_window_days_effective": (
                args.mrp_demand_signal_smoothing_days
            ),
            "future_realization_access": (
                args.fake_future_access
                or args.mrp_demand_signal_smoothing_days > 1
            ),
            "physical_action_applied": True,
            "controller_warmup_matches_physical_warmup": (
                args.warmup_days == 0
            ),
        } if controlled else {},
    },
}
(output / "summaries" / "first_simulation_summary.json").write_text(
    json.dumps(summary), encoding="utf-8"
)
'''


def _inputs(tmp_path: Path, *, engine_claim: bool = True) -> tuple[Path, Path, Path]:
    graph = tmp_path / "graph.json"
    graph.write_text('{"scenarios": [{"id": "scn:BASE"}]}', encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"engine_claim": engine_claim}), encoding="utf-8")
    engine = tmp_path / "fake_engine.py"
    engine.write_text(FAKE_ENGINE, encoding="utf-8")
    return graph, policy, engine


def test_paired_runner_exports_kpis_deltas_and_strict_engine_claim(
    tmp_path: Path,
) -> None:
    graph, policy, engine = _inputs(tmp_path)
    output = tmp_path / "campaign"

    artifacts = run_canonical_closed_loop(
        repo_root=tmp_path,
        graph_path=graph,
        control_policy_path=policy,
        seeds=[11, 10],
        output_root=output,
        days=4,
        engine_script=engine,
        python_executable=sys.executable,
        engine_profile_metadata={"name": "fake"},
        make_plot=False,
    )

    assert artifacts.runs.shape[0] == 4
    assert artifacts.paired_deltas["seed"].tolist() == [10, 11]
    assert artifacts.paired_deltas["pairing_contract_verified"].all()
    assert artifacts.paired_deltas["true_state_feedback"].all()
    assert (
        artifacts.paired_deltas["closed_loop_claim_path"]
        == "$.policy.control_provider.closed_loop_claimed"
    ).all()
    assert (artifacts.paired_deltas["delta_vs_mrp_service_loss"] < 0.0).all()
    assert set(artifacts.paired_summary["policy"]) == {
        REFERENCE_POLICY,
        FEEDBACK_POLICY,
    }
    for name in (
        "canonical_closed_loop_runs.csv",
        "canonical_closed_loop_paired_deltas.csv",
        "canonical_closed_loop_paired_summary.csv",
        "canonical_closed_loop_commands.json",
        "canonical_closed_loop_manifest.json",
    ):
        assert (output / name).is_file()
    exported = pd.read_csv(output / "canonical_closed_loop_runs.csv")
    assert exported["common_random_numbers"].all()
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["all_feedback_runs_confirmed_by_engine"] is True
    assert len(manifest["engine_sha256"]) == 64
    assert len(manifest["runner"]["sha256"]) == 64
    assert manifest["generated_at_utc"]
    assert set(manifest["output_sha256"]) == {
        "runs",
        "paired_deltas",
        "paired_summary",
        "commands",
    }
    assert all(len(value) == 64 for value in manifest["output_sha256"].values())
    assert manifest["outputs"]["control_diagnostics_plot"] == ""
    assert manifest["outputs"]["control_diagnostics_plot_status"] == "disabled"
    assert artifacts.control_diagnostics_plot_path is None
    assert artifacts.control_diagnostics_plot_status == "disabled"
    commands = json.loads(
        (output / "canonical_closed_loop_commands.json").read_text(encoding="utf-8")
    )
    feedback_commands = [row["command"] for row in commands if row["policy"] == FEEDBACK_POLICY]
    reference_commands = [row["command"] for row in commands if row["policy"] == REFERENCE_POLICY]
    assert all("--control-policy-json" in command for command in feedback_commands)
    assert all("--control-policy-json" not in command for command in reference_commands)
    compact_flags = (
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
    )
    for command in [*reference_commands, *feedback_commands]:
        start = command.index("--output-profile")
        assert tuple(command[start : start + len(compact_flags)]) == compact_flags
        assert "--lot-trace" not in command
    assert set(artifacts.runs["engine_artifact_profile"]) == {"compact"}
    assert set(artifacts.runs["engine_artifact_contract_status"]) == {
        "compact_legacy_contract"
    }
    assert manifest["engine_artifact_profile"] == "compact"
    assert manifest["engine_artifact_contract"] == {
        "status": "compact_legacy_contract",
        "validated_run_count": 0,
    }


def test_full_artifact_profile_writes_and_validates_complete_run_contract(
    tmp_path: Path,
) -> None:
    graph, policy, engine = _inputs(tmp_path)
    artifacts = run_canonical_closed_loop(
        repo_root=tmp_path,
        graph_path=graph,
        control_policy_path=policy,
        seeds=[17],
        output_root=tmp_path / "full_campaign",
        days=2,
        engine_script=engine,
        python_executable=sys.executable,
        engine_artifact_profile="full",
        make_plot=False,
    )

    commands = json.loads(
        (
            artifacts.output_root / "canonical_closed_loop_commands.json"
        ).read_text(encoding="utf-8")
    )
    for record in commands:
        command = record["command"]
        start = command.index("--output-profile")
        assert command[start : start + 3] == [
            "--output-profile",
            "full",
            "--lot-trace",
        ]
        for forbidden in (
            "--skip-map",
            "--skip-plots",
            "--no-lot-trace",
            "--skip-lot-audit",
        ):
            assert forbidden not in command
        result_dir = Path(record["result_dir"])
        assert (result_dir / "data" / "production_input_consumption_daily.csv").is_file()
        assert (result_dir / "maps" / "fake_map.html").is_file()
        assert (
            result_dir / "plots" / "factories" / "fake_plot.png"
        ).is_file()

    assert set(artifacts.runs["engine_artifact_profile"]) == {"full"}
    assert set(artifacts.runs["engine_artifact_contract_status"]) == {
        "validated_full"
    }
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["engine_artifact_profile"] == "full"
    assert manifest["engine_artifact_contract"]["status"] == "validated_full"
    assert manifest["engine_artifact_contract"]["validated_run_count"] == 2
    assert len(manifest["engine_artifact_contract"]["runs"]) == 2
    assert all(
        record["map_html_files"] == ["maps/fake_map.html"]
        for record in manifest["engine_artifact_contract"]["runs"]
    )


def test_config_and_cli_select_full_artifact_profile(tmp_path: Path) -> None:
    graph, _, engine = _inputs(tmp_path)
    config = tmp_path / "full_config.json"
    config.write_text(
        json.dumps(
            {
                "engine_claim": True,
                "campaign": {
                    "graph": str(graph),
                    "days": 2,
                    "seeds": [18],
                    "engine_artifact_profile": "full",
                    "plot": False,
                },
            }
        ),
        encoding="utf-8",
    )

    artifacts = run_from_config(
        config,
        repo_root=tmp_path,
        output_root=tmp_path / "configured_full_campaign",
        engine_script=engine,
        make_plot=False,
    )
    assert set(artifacts.runs["engine_artifact_profile"]) == {"full"}
    assert parse_args(["--engine-artifact-profile", "full"]).engine_artifact_profile == "full"


def test_full_artifact_profile_rejects_incomplete_engine_output(
    tmp_path: Path,
) -> None:
    graph, policy, engine = _inputs(tmp_path)
    with pytest.raises(
        CanonicalClosedLoopContractError,
        match="Full engine artifact contract failed.*production_input_consumption_daily",
    ):
        run_canonical_closed_loop(
            repo_root=tmp_path,
            graph_path=graph,
            control_policy_path=policy,
            seeds=[19],
            output_root=tmp_path / "incomplete_full_campaign",
            days=2,
            engine_script=engine,
            python_executable=sys.executable,
            engine_extra_args=["--fake-incomplete-full"],
            engine_artifact_profile="full",
            make_plot=False,
        )


def test_runner_refuses_non_empty_output_root_without_touching_it(
    tmp_path: Path,
) -> None:
    graph, policy, engine = _inputs(tmp_path)
    output = tmp_path / "existing_campaign"
    output.mkdir()
    marker = output / "keep-me.txt"
    marker.write_text("existing user result", encoding="utf-8")

    with pytest.raises(FileExistsError, match="existing non-empty output root"):
        run_canonical_closed_loop(
            repo_root=tmp_path,
            graph_path=graph,
            control_policy_path=policy,
            seeds=[20],
            output_root=output,
            days=2,
            engine_script=engine,
            python_executable=sys.executable,
            make_plot=False,
        )

    assert marker.read_text(encoding="utf-8") == "existing user result"
    assert sorted(path.name for path in output.iterdir()) == ["keep-me.txt"]


@pytest.mark.parametrize(
    ("schema_version", "expected_flag", "expected_provider_source"),
    [
        (
            "scan.canonical_state_feedback.v2",
            "--control-policy-v2-json",
            "control_provider_v2.py",
        ),
        (
            "scan.canonical_state_feedback.v3",
            "--control-policy-v3-json",
            "control_provider_v3.py",
        ),
    ],
)
def test_config_selects_versioned_interface_and_allows_priming(
    tmp_path: Path,
    schema_version: str,
    expected_flag: str,
    expected_provider_source: str,
) -> None:
    graph, _, engine = _inputs(tmp_path)
    policy = tmp_path / "versioned_policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "engine_claim": True,
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "versioned_closed_loop_config.json"
    config.write_text(
        json.dumps(
            {
                "campaign": {
                    "graph": str(graph),
                    "control_policy_json": str(policy),
                    "days": 2,
                    "seeds": [37],
                    "controller_prime_during_warmup": True,
                    "engine_args": [
                        "--warmup-days",
                        "0",
                        "--supplier-state-risk-observation-warmup-days",
                        "0",
                    ],
                    "plot": False,
                }
            }
        ),
        encoding="utf-8",
    )

    artifacts = run_from_config(
        config,
        repo_root=tmp_path,
        output_root=tmp_path / "versioned_campaign",
        engine_script=engine,
        make_plot=False,
    )

    commands = json.loads(
        (artifacts.output_root / "canonical_closed_loop_commands.json").read_text(
            encoding="utf-8"
        )
    )
    feedback_command = next(
        record["command"]
        for record in commands
        if record["policy"] == FEEDBACK_POLICY
    )
    reference_command = next(
        record["command"]
        for record in commands
        if record["policy"] == REFERENCE_POLICY
    )
    assert expected_flag in feedback_command
    assert "--controller-prime-during-warmup" in feedback_command
    assert expected_flag not in reference_command
    assert "--controller-prime-during-warmup" not in reference_command

    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["control_policy"]["engine_flag"] == expected_flag
    assert (
        Path(manifest["control_provider_source"]["path"]).name
        == expected_provider_source
    )


def test_generic_runner_requires_explicit_phase_seeds(tmp_path: Path) -> None:
    graph, _, engine = _inputs(tmp_path)
    policy = tmp_path / "v3_policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_state_feedback.v3",
                "engine_claim": True,
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "v3_phase_seed_config.json"
    config.write_text(
        json.dumps(
            {
                "campaign": {
                    "graph": str(graph),
                    "control_policy_json": str(policy),
                    "training_seeds": [31, 32],
                    "validation_seeds": [41, 42],
                    "plot": False,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not select training_seeds or validation_seeds automatically",
    ):
        run_from_config(
            config,
            repo_root=tmp_path,
            output_root=tmp_path / "ambiguous_v3_campaign",
            engine_script=engine,
            make_plot=False,
        )


def test_config_still_rejects_priming_for_v1_policy(tmp_path: Path) -> None:
    graph, _, engine = _inputs(tmp_path)
    policy = tmp_path / "v1_policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_state_feedback.v1",
                "engine_claim": True,
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "v1_priming_config.json"
    config.write_text(
        json.dumps(
            {
                "campaign": {
                    "graph": str(graph),
                    "control_policy_json": str(policy),
                    "days": 2,
                    "seeds": [41],
                    "controller_prime_during_warmup": True,
                    "plot": False,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only for V2 or V3"):
        run_from_config(
            config,
            repo_root=tmp_path,
            output_root=tmp_path / "invalid_v1_priming",
            engine_script=engine,
            make_plot=False,
        )


def test_configured_causal_window_overrides_profile_for_both_paired_arms(
    tmp_path: Path,
) -> None:
    graph, _, engine = _inputs(tmp_path)
    profile = tmp_path / "engine_profile.json"
    profile.write_text(
        json.dumps(
            {
                "name": "forward_window_fixture",
                "args": ["--mrp-demand-signal-smoothing-days", "7"],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "closed_loop_config.json"
    config.write_text(
        json.dumps(
            {
                "engine_claim": True,
                "campaign": {
                    "graph": str(graph),
                    "days": 3,
                    "seeds": [19],
                    "scenario_id": "scn:BASE",
                    "engine_args": [
                        "--mrp-demand-signal-smoothing-days",
                        "1",
                        "--warmup-days",
                        "0",
                        "--supplier-state-risk-observation-warmup-days",
                        "0",
                    ],
                    "plot": False,
                },
            }
        ),
        encoding="utf-8",
    )

    artifacts = run_from_config(
        config,
        repo_root=tmp_path,
        output_root=tmp_path / "configured_campaign",
        engine_script=engine,
        engine_profile_path=profile,
        make_plot=False,
    )

    commands = json.loads(
        (artifacts.output_root / "canonical_closed_loop_commands.json").read_text(
            encoding="utf-8"
        )
    )
    for record in commands:
        command = record["command"]
        values = [
            command[index + 1]
            for index, token in enumerate(command[:-1])
            if token == "--mrp-demand-signal-smoothing-days"
        ]
        assert values == ["7", "1"]
        summary = json.loads(
            (
                Path(record["result_dir"])
                / "summaries"
                / "first_simulation_summary.json"
            ).read_text(encoding="utf-8")
        )
        assert (
            summary["policy"]["initialization_policy"][
                "mrp_demand_signal_smoothing_days"
            ]
            == 1
        )
    configured_manifest = json.loads(
        artifacts.manifest_path.read_text(encoding="utf-8")
    )
    assert configured_manifest[
        "supplier_state_risk_observation_warmup_days"
    ] == 0


def test_flag_alone_never_creates_true_state_feedback_claim(tmp_path: Path) -> None:
    graph, policy, engine = _inputs(tmp_path, engine_claim=False)
    artifacts = run_canonical_closed_loop(
        repo_root=tmp_path,
        graph_path=graph,
        control_policy_path=policy,
        seeds=[7],
        output_root=tmp_path / "campaign",
        days=2,
        engine_script=engine,
        python_executable=sys.executable,
        make_plot=False,
    )
    feedback = artifacts.runs.loc[artifacts.runs["policy"].eq(FEEDBACK_POLICY)].iloc[0]
    assert bool(feedback["control_policy_requested"]) is True
    assert bool(feedback["engine_closed_loop_claimed"]) is False
    assert bool(feedback["true_state_feedback"]) is False
    assert feedback["closed_loop_evidence_status"] == "not_claimed_by_engine_summary"


@pytest.mark.parametrize(
    ("summary", "expected_status"),
    [
        ({}, "missing_engine_summary_claim"),
        ({"closed_loop_claimed": True}, "missing_engine_summary_claim"),
        (
            {"policy": {"closed_loop_claimed": True}},
            "missing_engine_summary_claim",
        ),
        (
            {
                "policy": {
                    "control_provider": {"closed_loop_claimed": "true"}
                }
            },
            "invalid_non_boolean_engine_summary_claim",
        ),
        (
            {
                "closed_loop_claimed": False,
                "policy": {"control_provider": {"closed_loop_claimed": True}},
            },
            "conflicting_engine_summary_claims",
        ),
    ],
)
def test_closed_loop_claim_rejects_missing_non_boolean_or_conflicting_evidence(
    summary: dict[str, object], expected_status: str
) -> None:
    claimed, _, status = _closed_loop_claim(summary)
    assert claimed is False
    assert status == expected_status


def test_only_provider_boolean_can_authorize_closed_loop_claim() -> None:
    claimed, path, status = _closed_loop_claim(
        {"policy": {"control_provider": {"closed_loop_claimed": True}}}
    )

    assert claimed is True
    assert path == "$.policy.control_provider.closed_loop_claimed"
    assert status == "confirmed_by_engine_summary"


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--fake-lookahead", "1"],
        ["--fake-future-access"],
    ],
)
def test_runner_rejects_claim_with_noncausal_observation_metadata(
    tmp_path: Path,
    extra_args: list[str],
) -> None:
    graph, policy, engine = _inputs(tmp_path)

    with pytest.raises(
        CanonicalClosedLoopContractError,
        match="controller observation|future_realization_access",
    ):
        run_canonical_closed_loop(
            repo_root=tmp_path,
            graph_path=graph,
            control_policy_path=policy,
            seeds=[23],
            output_root=tmp_path / ("invalid_" + extra_args[0].lstrip("-")),
            days=2,
            engine_script=engine,
            python_executable=sys.executable,
            engine_extra_args=extra_args,
            make_plot=False,
        )


def test_runner_rejects_action_ledger_that_does_not_match_command(
    tmp_path: Path,
) -> None:
    graph, policy, engine = _inputs(tmp_path)

    with pytest.raises(
        CanonicalClosedLoopContractError,
        match="effective value does not match command",
    ):
        run_canonical_closed_loop(
            repo_root=tmp_path,
            graph_path=graph,
            control_policy_path=policy,
            seeds=[29],
            output_root=tmp_path / "invalid_ledger_join",
            days=2,
            engine_script=engine,
            python_executable=sys.executable,
            engine_extra_args=["--fake-ledger-effective", "1.2"],
            make_plot=False,
        )


def test_engine_failure_is_raised_not_converted_to_success(tmp_path: Path) -> None:
    graph, policy, engine = _inputs(tmp_path)
    output = tmp_path / "campaign"
    with pytest.raises(subprocess.CalledProcessError) as raised:
        run_canonical_closed_loop(
            repo_root=tmp_path,
            graph_path=graph,
            control_policy_path=policy,
            seeds=[3],
            output_root=output,
            days=2,
            engine_script=engine,
            python_executable=sys.executable,
            engine_extra_args=["--fail"],
            make_plot=False,
        )
    assert raised.value.returncode == 17
    assert (output / REFERENCE_POLICY / "seed_3" / "engine_stderr.log").is_file()


def _diagnostic_fixture(tmp_path: Path) -> tuple[pd.DataFrame, Path, Path]:
    reference_dir = tmp_path / "mrp"
    feedback_dir = tmp_path / "feedback"
    for result_dir in (reference_dir, feedback_dir):
        (result_dir / "data").mkdir(parents=True)

    days = list(range(6))
    common_daily = {
        "day": days,
        "demand": [10.0] * 6,
        "served": [9.0, 9.0, 8.0, 9.0, 10.0, 10.0],
        "backlog_end": [1.0, 2.0, 4.0, 3.0, 1.0, 0.0],
        "estimated_source_ordered_qty": [10.0, 11.0, 12.0, 11.0, 10.0, 10.0],
        "external_procured_ordered_qty": [0.0] * 6,
    }
    pd.DataFrame(
        {**common_daily, "inventory_total": [20.0, 19.0, 17.0, 16.0, 17.0, 18.0]}
    ).to_csv(reference_dir / "data" / "first_simulation_daily.csv", index=False)
    pd.DataFrame(
        {
            **common_daily,
            "served": [9.0, 9.5, 9.0, 10.0, 10.0, 10.0],
            "inventory_total": [20.0, 19.5, 18.0, 18.0, 19.0, 20.0],
        }
    ).to_csv(feedback_dir / "data" / "first_simulation_daily.csv", index=False)

    pd.DataFrame(
        {
            "day": days,
            "service_level": [0.9, 0.95, 0.9, 1.0, 1.0, 1.0],
            "backlog_days": [0.1, 0.2, 0.4, 0.3, 0.1, 0.0],
            "supplier_disruption_score": [0.0, 0.1, 0.35, 0.25, 0.1, 0.0],
            "supplier_stress": [0.0, 0.08, 0.32, 0.4, 0.3, 0.2],
            "production_utilization": [0.7, 0.8, 0.98, 0.9, 0.8, 0.7],
            "supplier_utilization": [0.65, 0.75, 0.96, 0.88, 0.78, 0.7],
            "observation_hash": [f"hash-{day}" for day in days],
        }
    ).to_csv(
        feedback_dir / "data" / "canonical_closed_loop_observations.csv",
        index=False,
    )
    decision_days = list(range(5))
    pd.DataFrame(
        {
            "decision_day": decision_days,
            "effective_day": [day + 1 for day in decision_days],
            "causal_lag_days": [1] * 5,
            "confirmed_regime": [
                "NOMINAL",
                "MATERIAL_TENSION",
                "CRISIS",
                "RECOVERY",
                "NOMINAL",
            ],
            "selected_policy": [
                "mrp_reference",
                "service_protection",
                "balanced_robust",
                "recovery_damping",
                "mrp_reference",
            ],
            "fallback_applied": [0] * 5,
        }
    ).to_csv(
        feedback_dir / "data" / "canonical_closed_loop_decisions.csv",
        index=False,
    )
    lever_values = [
        (1.0, 1.0, 0.0, 0),
        (1.05, 1.1, 0.05, -1),
        (1.1, 1.2, 0.1, -1),
        (0.95, 1.0, 0.02, 0),
        (1.0, 1.0, 0.0, 0),
    ]
    pd.DataFrame(
        {
            "decision_day": decision_days,
            "effective_day": [day + 1 for day in decision_days],
            "causal_lag_days": [1] * 5,
            "scope_type": ["global"] * 5,
            "effective_json": [
                json.dumps(
                    {
                        "order_multiplier": order,
                        "safety_stock_multiplier": safety,
                        "expedite_level": expedite,
                        "lead_time_adjustment_days": lead,
                    }
                )
                for order, safety, expedite, lead in lever_values
            ],
        }
    ).to_csv(
        feedback_dir / "data" / "canonical_closed_loop_commands.csv",
        index=False,
    )
    runs = pd.DataFrame(
        [
            {"policy": REFERENCE_POLICY, "seed": 101, "result_dir": str(reference_dir)},
            {"policy": FEEDBACK_POLICY, "seed": 101, "result_dir": str(feedback_dir)},
        ]
    )
    return runs, reference_dir, feedback_dir


def test_control_diagnostics_is_optional_when_feedback_audit_csvs_are_missing(
    tmp_path: Path,
) -> None:
    runs = pd.DataFrame(
        [
            {"policy": REFERENCE_POLICY, "seed": 4, "result_dir": str(tmp_path / "mrp")},
            {"policy": FEEDBACK_POLICY, "seed": 4, "result_dir": str(tmp_path / "feedback")},
        ]
    )
    path, status = _save_control_diagnostics_plot(tmp_path, runs)
    assert path is None
    assert status.startswith("missing_feedback_audit_csvs:")


def test_control_diagnostics_parses_j_plus_1_levers_and_writes_png(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    runs, _, feedback_dir = _diagnostic_fixture(tmp_path)
    command_frame = pd.read_csv(
        feedback_dir / "data" / "canonical_closed_loop_commands.csv"
    )
    levers = _effective_command_levers(command_frame)
    assert set(levers["causal_lag_days"]) == {1}
    assert (levers["effective_day"] == levers["decision_day"] + 1).all()
    assert {"order_multiplier", "expedite_level"}.issubset(set(levers["action"]))

    path, status = _save_control_diagnostics_plot(tmp_path, runs)
    assert status == "written"
    assert path == tmp_path / "canonical_closed_loop_control_diagnostics.png"
    assert path.is_file()
    assert path.stat().st_size > 1_000


def test_control_diagnostics_rejects_noncausal_command_days() -> None:
    commands = pd.DataFrame(
        {
            "decision_day": [3],
            "effective_day": [3],
            "effective_json": ['{"order_multiplier": 1.1}'],
        }
    )
    with pytest.raises(
        CanonicalClosedLoopContractError,
        match=r"decision J -> action J\+1",
    ):
        _effective_command_levers(commands)
