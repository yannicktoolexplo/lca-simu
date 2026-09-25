from __future__ import annotations

import gzip
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as bridge_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v7 as relay_v7,
)
from etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters import finalize_v7 as finalizer_v7
from etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters import launch_v7 as launcher_v7
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as campaign_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7 as campaign_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


def _metrics(service: float) -> dict[str, float]:
    return {
        "demand_qty_268091": 100.0,
        "demand_qty_268967": 100.0,
        "demand_qty_global": 200.0,
        "on_due_qty_268091": 100.0 * service,
        "on_due_qty_268967": 100.0 * service,
        "on_due_qty_global": 200.0 * service,
    }


def _campaign_evidence() -> dict[tuple[str, int], dict[str, Any]]:
    service = {"op_100": 0.995, "op_93": 0.93, "op_80": 0.80}
    return {
        (candidate.key, seed): {
            "evidence_signature": hashlib.sha256(
                f"{candidate.key}:{seed}".encode()
            ).hexdigest(),
            "metrics": _metrics(service[candidate.target_group]),
        }
        for candidate in protocol_v7.FIXED_TRIPLET
        for seed in trace_package.CAMPAIGN_SEEDS
    }


def _lanes() -> list[dict[str, Any]]:
    return campaign_contract.lane_contract_payload(
        [
            {
                "lane_id": f"lane_{index:02d}",
                "edge_id": f"edge_{index:02d}",
                "supplier_id": f"supplier_{index:02d}",
                "item_id": f"item_{index:02d}",
                "dst_node_id": f"factory_{index:02d}",
                "target_product_id": "268091" if index % 2 else "268967",
                "planned_lead_days": 10.0 + index,
            }
            for index in range(18)
        ]
    )


def test_frozen_protocol_and_first_30_seed_contract() -> None:
    assert (
        trace_package.validate_frozen_v7_protocol()
        == Path(protocol_v7.__file__).resolve()
    )
    assert trace_package.CAMPAIGN_SEEDS == tuple(protocol_v7.V7_VALIDATION_SEEDS[:30])
    assert len(trace_package.CAMPAIGN_SEEDS) == 30
    assert len(set(trace_package.CAMPAIGN_SEEDS)) == 30
    assert len(trace_package.CAMPAIGN_SEED_BLOCKS) == 6
    assert all(len(block) == 5 for block in trace_package.CAMPAIGN_SEED_BLOCKS)
    assert not set(trace_package.CAMPAIGN_SEEDS) & set(protocol_v7.PRIOR_SEEDS)
    assert trace_package.CAMPAIGN_SEEDS != campaign_contract.CAMPAIGN_SEEDS


def test_frozen_protocol_pin_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = campaign_contract.sha256_file

    def changed(path: Path) -> str:
        if path.resolve() == Path(protocol_v7.__file__).resolve():
            return "0" * 64
        return original(path)

    monkeypatch.setattr(campaign_contract, "sha256_file", changed)
    with pytest.raises(trace_package.V7TracePackageError, match="protocol changed"):
        trace_package.validate_frozen_v7_protocol()


def test_reused_v4_v5_orchestrators_are_explicitly_pinned() -> None:
    assert set(relay_v7.FROZEN_ORCHESTRATOR_SHA256) == {
        "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v4",
        "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5",
    }
    for module, expected in relay_v7.FROZEN_ORCHESTRATOR_SHA256.items():
        path = relay_v7.relay_v4._module_path(  # noqa: SLF001
            Path(relay_v7.__file__).resolve().parents[3], module
        )
        actual = relay_v7.relay_v4.sha256_file(path)
        assert actual == expected or relay_v7._source_revision.accepts_current_revision(
            path, expected, actual
        )


def test_wrapper_contexts_patch_and_restore_first_30_v7_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(campaign_v7, "validate_frozen_implementation", lambda: Path())
    campaign_impl = campaign_v7.implementation_v4
    campaign_before = (
        campaign_impl.v4_bridge,
        campaign_impl.__file__,
        campaign_impl.SEEDS,
        campaign_impl.SEED_BLOCK_SIZE,
        campaign_impl.SEED_BLOCKS,
        campaign_impl._design_payload,  # noqa: SLF001
        campaign_impl._build_v4_state_validation_binding,  # noqa: SLF001
    )
    with campaign_v7.patched_v7_context():
        assert campaign_impl.v4_bridge is bridge_v7
        assert Path(campaign_impl.__file__).resolve() == campaign_v7.ADAPTER_PATH
        assert campaign_impl.SEEDS == trace_package.CAMPAIGN_SEEDS
        assert campaign_impl.SEED_BLOCK_SIZE == 5
        assert campaign_impl.SEED_BLOCKS == trace_package.CAMPAIGN_SEED_BLOCKS
        assert campaign_impl._design_payload is campaign_v7._build_v7_design_payload  # noqa: SLF001
        assert (  # noqa: SLF001
            campaign_impl._build_v4_state_validation_binding
            is campaign_v7._build_v7_state_validation_binding
        )
    assert (
        campaign_impl.v4_bridge,
        campaign_impl.__file__,
        campaign_impl.SEEDS,
        campaign_impl.SEED_BLOCK_SIZE,
        campaign_impl.SEED_BLOCKS,
        campaign_impl._design_payload,  # noqa: SLF001
        campaign_impl._build_v4_state_validation_binding,  # noqa: SLF001
    ) == campaign_before

    monkeypatch.setattr(launcher_v7, "validate_frozen_implementation", lambda: Path())
    launcher_impl = launcher_v7.implementation_v4
    launcher_before = (
        launcher_impl.v4_bridge,
        launcher_impl.RUNNER,
        launcher_impl.EXPECTED_CAMPAIGN_SEEDS,
    )
    with launcher_v7.patched_v7_context():
        assert launcher_impl.v4_bridge is bridge_v7
        assert launcher_impl.RUNNER == launcher_v7.RUNNER
        assert launcher_impl.EXPECTED_CAMPAIGN_SEEDS == trace_package.CAMPAIGN_SEEDS
    assert (
        launcher_impl.v4_bridge,
        launcher_impl.RUNNER,
        launcher_impl.EXPECTED_CAMPAIGN_SEEDS,
    ) == launcher_before

    monkeypatch.setattr(finalizer_v7, "validate_frozen_implementation", lambda: Path())
    finalizer_impl = finalizer_v7.implementation_v4
    finalizer_before = (
        finalizer_impl.v4_bridge,
        finalizer_impl.SOURCE_RUNNER_SHA256,
        finalizer_impl.EXPECTED_SEEDS,
        finalizer_impl._validate_operating_point_provenance,  # noqa: SLF001
    )
    with finalizer_v7.patched_v7_context():
        assert finalizer_impl.v4_bridge is bridge_v7
        assert finalizer_impl.EXPECTED_SEEDS == trace_package.CAMPAIGN_SEEDS
        assert finalizer_impl.SOURCE_RUNNER_SHA256 == (
            campaign_contract.sha256_file(finalizer_v7.V7_CAMPAIGN_RUNNER)
        )
        assert (  # noqa: SLF001
            finalizer_impl._validate_operating_point_provenance
            == finalizer_v7._v7_provenance
        )
    assert (
        finalizer_impl.v4_bridge,
        finalizer_impl.SOURCE_RUNNER_SHA256,
        finalizer_impl.EXPECTED_SEEDS,
        finalizer_impl._validate_operating_point_provenance,  # noqa: SLF001
    ) == finalizer_before
    assert campaign_contract.CAMPAIGN_SEEDS != trace_package.CAMPAIGN_SEEDS


def test_campaign_v7_binding_states_true_scientific_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation = {
        "role": "sole_scientific_authorization_for_fixed_triplet",
        "status": protocol_v7.ACCEPTED_STATUS,
        "accepted": True,
        "plan_signature": "a" * 64,
        "result_signature": "b" * 64,
        "validation_seed_count": 150,
        "fresh_physical_evidence_case_count": 450,
        "prior_version_simulation_evidence_reused": False,
        "retuning_after_any_v7_result": False,
    }
    baseline = {
        "role": "campaign_initial_conditions_and_pairing_only",
        "seeds": list(trace_package.CAMPAIGN_SEEDS),
        "physical_case_count": 90,
        "subset_of_v7_validation": True,
        "same_seeds_required_for_baseline_and_incidents": True,
        "acceptance_gate": False,
        "used_for_operating_point_retuning": False,
    }
    holdout = {
        "status": protocol_v7.ACCEPTED_STATUS,
        "accepted": True,
        "publishable": True,
        "execution_mode": protocol_v7.OFFICIAL_EXECUTION_MODE,
        "retuning_after_holdout": False,
        "validation_protocol": validation,
        "campaign_baseline_contract": baseline,
    }
    monkeypatch.setattr(
        campaign_v7,
        "_ORIGINAL_STATE_VALIDATION_BINDING",
        lambda **kwargs: {
            "interpretation": "Exact binding to the accepted fresh V4 holdout",
            "v4_plan_signature": "a" * 64,
            "v4_holdout_signature": "b" * 64,
            "v4_trace_index_signature": "d" * 64,
            "campaign_seeds": list(trace_package.CAMPAIGN_SEEDS),
            "binding_signature": "legacy",
        },
    )
    binding = campaign_v7._build_v7_state_validation_binding(  # noqa: SLF001
        manifest={},
        bridge={
            "source": {
                "plan_signature": "a" * 64,
                "development_selection_signature": "c" * 64,
                "holdout_signature": "b" * 64,
            },
            "holdout_contract": holdout,
            "trace_index_signature": "d" * 64,
        },
    )
    assert "accepted official V7" in binding["interpretation"]
    assert "accepted fresh V4 holdout" not in binding["interpretation"]
    assert binding["scientific_provenance_v7"]["validation_seed_count"] == 150
    assert binding["scientific_provenance_v7"]["fresh_validation_case_count"] == 450
    assert (
        binding["scientific_provenance_v7"][
            "campaign_baseline_subset_is_acceptance_gate"
        ]
        is False
    )
    unsigned = dict(binding)
    signature = unsigned.pop("binding_signature")
    assert signature == campaign_v7.implementation_v4._stable_sha256(unsigned)  # noqa: SLF001
    (tmp_path / "state_validation_binding.json").write_text(
        json.dumps(binding), encoding="utf-8"
    )
    assert dashboard_v7._validate_v7_binding(tmp_path) == binding  # noqa: SLF001

    monkeypatch.setattr(
        campaign_v7,
        "_ORIGINAL_DESIGN_PAYLOAD",
        lambda *args, **kwargs: {
            "expected_counts": {
                "imported_v4_holdout_service_proofs": 90,
                "imported_v4_holdout_shipment_traces": 90,
            },
            "operating_point_preflight_contract": {
                "kind": "signed_v4_holdout_state_validation_binding",
            },
            "operating_points_holdout_contract": holdout,
            "operating_points_producer": "v4_fresh_holdout_bridge",
        },
    )
    design = campaign_v7._build_v7_design_payload()  # noqa: SLF001
    assert design["operating_points_scientific_producer"] == (
        "v7_fixed_triplet_confirmation_bridge"
    )
    assert design["operating_points_producer_is_legacy_dispatch_key"] is True
    assert (
        design["expected_counts"]["imported_v7_campaign_baseline_shipment_traces"] == 90
    )
    assert design["operating_point_preflight_contract"]["kind"] == (
        "signed_v7_confirmation_state_validation_binding"
    )


def test_dashboard_reader_patches_and_restores_v7_campaign_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = dashboard_v7.implementation_v4.v4_contract.CAMPAIGN_SEEDS
    template_before = dashboard_v7.implementation_v4.HTML_TEMPLATE
    observed: list[tuple[int, ...]] = []
    monkeypatch.setattr(dashboard_v7, "validate_frozen_implementation", lambda: Path())

    def load(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        observed.append(dashboard_v7.implementation_v4.v4_contract.CAMPAIGN_SEEDS)
        return {"status": "ok"}

    monkeypatch.setattr(dashboard_v7.implementation_v4, "load_dashboard_data", load)
    monkeypatch.setattr(dashboard_v7, "_validate_v7_binding", lambda _path: {})
    assert dashboard_v7.load_dashboard_data(results_dir=Path("unused")) == {
        "status": "ok"
    }
    assert observed == [trace_package.CAMPAIGN_SEEDS]
    assert dashboard_v7.implementation_v4.v4_contract.CAMPAIGN_SEEDS == before
    assert dashboard_v7.implementation_v4.HTML_TEMPLATE == template_before


def test_dashboard_v7_visible_provenance_is_not_v4() -> None:
    template = dashboard_v7._v7_html_template()  # noqa: SLF001
    assert "Campagne fournisseurs V4" not in template
    assert "holdout V4" not in template
    assert "CAMPAGNE FOURNISSEURS V7" in template
    assert "150 graines" in template
    assert "450 simulations" in template
    assert "30 premières graines" in template
    assert "90 situations normales" in template


def test_dashboard_rejects_legacy_v4_scientific_provenance(tmp_path: Path) -> None:
    unsigned = {
        "interpretation": "Exact binding to the accepted fresh V4 holdout",
        "campaign_seeds": list(trace_package.CAMPAIGN_SEEDS),
        "v4_plan_signature": "a" * 64,
        "v4_holdout_signature": "b" * 64,
        "v4_trace_index_signature": "c" * 64,
    }
    binding = {
        **unsigned,
        "binding_signature": dashboard_v7.implementation_v4._stable_payload_sha256(  # noqa: SLF001
            unsigned
        ),
    }
    (tmp_path / "state_validation_binding.json").write_text(
        json.dumps(binding), encoding="utf-8"
    )
    with pytest.raises(
        dashboard_v7.DashboardInputError, match="provenance scientifique V7"
    ):
        dashboard_v7._validate_v7_binding(tmp_path)  # noqa: SLF001


def test_v7_bundle_source_requires_both_gzip_and_csv_hashes(tmp_path: Path) -> None:
    raw = b"day,shipment_id\n0,S1\n"
    compressed = gzip.compress(raw, mtime=0)
    relative = "retained/case/production_supplier_shipments_daily.csv.gz"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(compressed)
    row = {
        "source_relative_path": trace_package.SHIPMENT_SOURCE,
        "relative_path": relative,
        "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
        "gzip_bytes": len(compressed),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
    }
    observed, observed_row = trace_package._bundle_source(  # noqa: SLF001
        run_dir=tmp_path,
        evidence={"retained_bundle": {"files": [row]}},
    )
    assert observed == raw
    assert observed_row == row
    row["source_sha256"] = "f" * 64
    with pytest.raises(trace_package.V7TracePackageError, match="source hash"):
        trace_package._bundle_source(  # noqa: SLF001
            run_dir=tmp_path,
            evidence={"retained_bundle": {"files": [row]}},
        )
    row["source_sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_bytes(compressed + b"tamper")
    with pytest.raises(trace_package.V7TracePackageError, match="gzip hash"):
        trace_package._bundle_source(  # noqa: SLF001
            run_dir=tmp_path,
            evidence={"retained_bundle": {"files": [row]}},
        )


def test_trace_package_publish_race_never_deletes_foreign_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "traces"
    plan_dir.mkdir()
    run_dir.mkdir()
    monkeypatch.setattr(
        trace_package,
        "_build_payloads",
        lambda *args, **kwargs: ({"schema_version": "test"}, {}, {}, {}),
    )
    original_rename = Path.rename

    def collide(source: Path, target: Path) -> Path:
        resolved = Path(target)
        resolved.mkdir(parents=True)
        (resolved / "owned-by-other-process.txt").write_text(
            "do not delete\n", encoding="utf-8"
        )
        raise FileExistsError("simulated concurrent publisher")

    monkeypatch.setattr(Path, "rename", collide)
    with pytest.raises(FileExistsError, match="concurrent publisher"):
        trace_package.build_package(plan_dir, run_dir, output_dir)
    monkeypatch.setattr(Path, "rename", original_rename)
    assert (output_dir / "owned-by-other-process.txt").read_text(
        encoding="utf-8"
    ) == "do not delete\n"
    assert not any(tmp_path.glob(".traces.building-*"))


def test_bridge_exclusive_publish_never_overwrites_existing_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "bridge.json"
    output.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        bridge_v7._publish_bridge_exclusive(  # noqa: SLF001
            output, {"artifact": "ours"}
        )
    assert output.read_text(encoding="utf-8") == "foreign\n"
    assert not any(tmp_path.glob(".bridge.json.building-*"))


def test_trace_gate_rejects_any_nonaccepted_v7_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = SimpleNamespace(
        plan_dir=tmp_path / "plan",
        manifest={"plan_signature": "a" * 64},
    )
    monkeypatch.setattr(trace_package, "validate_frozen_v7_protocol", lambda: Path())
    monkeypatch.setattr(protocol_v7, "validate_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        protocol_v7,
        "validate_result",
        lambda *args, **kwargs: {
            "status": protocol_v7.REJECTED_STATUS,
            "accepted": False,
            "publishable": True,
        },
    )
    monkeypatch.setattr(protocol_v7, "validated_evidence", lambda *args, **kwargs: {})
    with pytest.raises(trace_package.V7TracePackageError, match="accepted complete"):
        trace_package._validate_v7(tmp_path / "plan", tmp_path / "run")  # noqa: SLF001


def test_campaign_subset_statistics_are_descriptive_not_an_acceptance_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_v7, "DESCRIPTIVE_BOOTSTRAP_REPLICATES", 50)
    summaries, bootstrap = bridge_v7._campaign_baseline_statistics(  # noqa: SLF001
        _campaign_evidence()
    )
    assert summaries["op_100"]["pooled"]["system_on_due_service"] == 0.995
    assert summaries["op_93"]["pooled"]["system_on_due_service"] == 0.93
    assert summaries["op_80"]["pooled"]["system_on_due_service"] == 0.8
    assert all(row["acceptance_gate"] is False for row in summaries.values())
    assert bootstrap["contract"]["acceptance_gate"] is False
    assert bootstrap["contract"]["replicates"] == 50


def test_bridge_exposes_150_seed_authorization_and_30_seed_pairing_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "trace_package"
    plan_dir.mkdir()
    run_dir.mkdir()
    package_dir.mkdir()
    (plan_dir / "protocol_manifest.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "validation_result.json").write_text("{}\n", encoding="utf-8")
    (package_dir / "trace_package_manifest.json").write_text("{}\n", encoding="utf-8")

    inventory: dict[str, Any] = {}
    for candidate in protocol_v7.FIXED_TRIPLET:
        graph = plan_dir / f"{candidate.key}.graphml"
        graph.write_text(candidate.key, encoding="utf-8")
        inventory[candidate.key] = {
            "graph_path": graph.name,
            "graph_sha256": campaign_contract.sha256_file(graph),
        }
    plan = SimpleNamespace(
        plan_dir=plan_dir,
        candidates=protocol_v7.FIXED_TRIPLET,
        manifest={
            "plan_signature": "1" * 64,
            "inventory": inventory,
            "execution_contract": {
                "engine": {"sha256": "2" * 64},
                "engine_profile": {"sha256": "3" * 64},
            },
        },
    )
    run_manifest = {"run_signature": "4" * 64}
    result = {
        "result_signature": "5" * 64,
        "evidence_signature_set_sha256": "6" * 64,
        "status": protocol_v7.ACCEPTED_STATUS,
    }
    evidence = _campaign_evidence()
    selection_unsigned = {"selection": "first_30"}
    selection = {
        **selection_unsigned,
        "selection_signature": campaign_contract.stable_sha256(selection_unsigned),
    }
    (package_dir / "campaign_trace_selection.json").write_text(
        json.dumps(selection), encoding="utf-8"
    )
    traces = [
        {
            "operating_point_id": candidate.target_group,
            "candidate_key": candidate.key,
            "candidate_id": candidate.candidate_id,
            "seed": seed,
            "evidence_relative_path": f"evidence/{candidate.key}/{seed}.json",
            "evidence_sha256": "7" * 64,
            "evidence_signature": "8" * 64,
            "shipment_trace": {},
        }
        for candidate in protocol_v7.FIXED_TRIPLET
        for seed in trace_package.CAMPAIGN_SEEDS
    ]
    package = {
        "run_signature": "9" * 64,
        "v4_v5_v6_simulation_evidence_reused": False,
        "campaign_cohort": {
            "seeds": list(trace_package.CAMPAIGN_SEEDS),
            "same_seeds_required_for_baseline_and_incidents": True,
        },
        "v7_source": {"result_signature": result["result_signature"]},
        "trace_index": traces,
        "lane_contract": {"lanes": _lanes()},
    }
    monkeypatch.setattr(
        bridge_v7,
        "_validate_v7_acceptance",
        lambda *args, **kwargs: (plan, run_manifest, result, evidence),
    )
    monkeypatch.setattr(
        trace_package, "validate_package", lambda *args, **kwargs: package
    )
    monkeypatch.setattr(bridge_v7, "DESCRIPTIVE_BOOTSTRAP_REPLICATES", 20)

    payload = bridge_v7.build_bridge_payload(plan_dir, run_dir, package_dir)
    validation = payload["holdout_contract"]["validation_protocol"]
    baseline = payload["holdout_contract"]["campaign_baseline_contract"]
    assert validation["role"] == "sole_scientific_authorization_for_fixed_triplet"
    assert validation["validation_seed_count"] == 150
    assert validation["fresh_physical_evidence_case_count"] == 450
    assert validation["prior_version_simulation_evidence_reused"] is False
    assert baseline["role"] == "campaign_initial_conditions_and_pairing_only"
    assert baseline["seed_count"] == 30
    assert baseline["physical_case_count"] == 90
    assert baseline["same_seeds_required_for_baseline_and_incidents"] is True
    assert baseline["used_for_operating_point_retuning"] is False
    assert baseline["acceptance_gate"] is False
    assert payload["cohorts"] == {
        "campaign_repetitions_reuse_v4_fresh_holdout": list(
            trace_package.CAMPAIGN_SEEDS
        ),
        "incident_window_design_reserved": [campaign_contract.INCIDENT_DESIGN_SEED],
        "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
    }
    assert payload["quality_branch_included"] is False
    assert payload["supplier_state_dependent_risks_enabled"] is False
    assert payload["acute_incident_included_in_operating_point"] is False
    actual_protocol_sha = campaign_contract.sha256_file(Path(protocol_v7.__file__))
    assert payload["source_hashes"]["v7_protocol_driver_sha256"] == actual_protocol_sha
    assert actual_protocol_sha != trace_package.EXPECTED_V7_PROTOCOL_SHA256
    bridge_path = tmp_path / "bridge.json"
    bridge_path.write_text(json.dumps(payload), encoding="utf-8")
    assert bridge_v7.validate_bridge(bridge_path, revalidate_source=False) == payload
    payload["source_hashes"]["v7_protocol_driver_sha256"] = trace_package.EXPECTED_V7_PROTOCOL_SHA256
    payload.pop("artifact_signature")
    payload["artifact_signature"] = campaign_contract.stable_sha256(payload)
    bridge_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(bridge_v7.V7BridgeError, match="compatibility structure changed"):
        bridge_v7.validate_bridge(bridge_path, revalidate_source=False)

    # The trace-package manifest must identify the same actual reviewed source,
    # even though upstream physics is supplied by the synthetic fixture here.
    monkeypatch.setattr(trace_package, "_validate_v7", lambda *args: (plan, result, evidence))
    monkeypatch.setattr(trace_package, "_campaign_lanes", lambda *args: _lanes())
    monkeypatch.setattr(trace_package, "_trace_adapter", lambda *args: (None, plan))

    def case_material(**kwargs: Any) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
        candidate, seed = kwargs["candidate"], kwargs["seed"]
        reference = {"relative_path": trace_package._trace_relative(candidate, seed)}
        return b"fixture", reference, {"evidence_signature": "8" * 64}

    monkeypatch.setattr(trace_package, "_case_material", case_material)
    manifest, selection, index, _ = trace_package._build_payloads(plan_dir, run_dir, package_dir)
    assert manifest["v7_source"]["protocol_driver_sha256"] == actual_protocol_sha
    assert manifest["v7_source"]["protocol_driver_sha256"] != trace_package.EXPECTED_V7_PROTOCOL_SHA256
    assert len(index) == 90
    assert selection["campaign_seeds"] == list(trace_package.CAMPAIGN_SEEDS)
    assert manifest["engine_runs_performed"] == 0


def test_relay_no_go_precedes_all_downstream_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "v7_plan"
    run_dir = tmp_path / "v7_run"
    plan_dir.mkdir()
    run_dir.mkdir()
    config = relay_v7.V7CampaignRelayConfig(
        repo=Path(relay_v7.__file__).resolve().parents[3],
        v7_plan_dir=plan_dir,
        v7_run_dir=run_dir,
        trace_package_dir=tmp_path / "traces",
        bridge_json=tmp_path / "bridge.json",
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        supervision_dir=tmp_path / "supervision",
    ).resolved()
    relay = relay_v7.FullCampaignRelayV7(config)
    monkeypatch.setattr(
        relay,
        "validate_v7_handoff",
        lambda: (_ for _ in ()).throw(relay_v7.ScientificNoGo("rejected")),
    )
    with pytest.raises(relay_v7.ScientificNoGo, match="rejected"):
        relay.prepare()
    assert not config.supervision_dir.exists()
    assert not config.trace_package_dir.exists()
    assert not config.bridge_json.exists()
    assert not config.campaign_root.exists()
    assert not config.results_dir.exists()


def test_relay_stage_order_stops_at_consolidated_campaign_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relay = object.__new__(relay_v7.FullCampaignRelayV7)
    relay.status = {}
    calls: list[str] = []
    for method in (
        "prepare",
        "build_trace_package",
        "build_and_validate_bridge",
        "plan_campaign",
        "launch_campaign",
        "finalize_campaign",
    ):
        monkeypatch.setattr(relay, method, lambda name=method: calls.append(name))
    monkeypatch.setattr(relay_v7.relay_v4, "_now", lambda: "now")
    monkeypatch.setattr(relay, "_assert_source_inventory_unchanged", lambda: None)

    def update(stage: str, message: str, **kwargs: Any) -> None:
        del message, kwargs
        calls.append(stage)

    monkeypatch.setattr(relay, "update_status", update)
    assert relay.execute() == 0
    assert calls == [
        "prepare",
        "build_trace_package",
        "build_and_validate_bridge",
        "plan_campaign",
        "launch_campaign",
        "finalize_campaign",
        "campagne_v7_consolidee",
    ]


def test_relay_result_readiness_uses_seed_aware_dashboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = relay_v7.V7CampaignRelayConfig(
        repo=Path(relay_v7.__file__).resolve().parents[3],
        v7_plan_dir=tmp_path / "plan",
        v7_run_dir=tmp_path / "run",
        trace_package_dir=tmp_path / "traces",
        bridge_json=tmp_path / "bridge.json",
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        supervision_dir=tmp_path / "supervision",
    ).resolved()
    config.results_dir.mkdir()
    payload = {
        "status": "complete_validated",
        "expected_contract": {
            "repetition_ids": list(trace_package.CAMPAIGN_SEEDS),
            "paired_repetition_count": 30,
            "lane_count": 18,
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "mechanisms": ["transport_delay", "planned_delivery_shortfall"],
            "quality_branch_included": False,
            "availability_incident_included": False,
        },
        "comparability_checks": {
            "complete_3x18x2x30_matrix": True,
            "all_3330_metrics_reconstructed_from_signed_case_evidence": True,
            "mandatory_non_reusable_op93_smoke_validated": True,
            "quality_or_availability_incident_count": 0,
        },
        "signed_case_evidence": {"case_count": 3_330},
    }
    (config.results_dir / "campaign_validation.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    relay = relay_v7.FullCampaignRelayV7(config)
    monkeypatch.setattr(relay, "_campaign_plan_ready", lambda: True)
    monkeypatch.setattr(
        finalizer_v7,
        "validate_v7_overlay",
        lambda *_args, **_kwargs: {
            "status": "complete_validated_v7_overlay",
            "v7_comparability_checks": {
                "v7_confirmation_150_seeds_450_cases_signed_and_accepted": True,
                "v7_first30_90_shipment_traces_used_for_pairing_without_rerun": True,
                "campaign_subset_used_as_v7_acceptance_gate": False,
            },
        },
    )
    calls: list[Path] = []
    monkeypatch.setattr(
        dashboard_v7,
        "load_dashboard_data",
        lambda *, results_dir, **kwargs: calls.append(results_dir) or {},
    )
    assert relay._results_ready() is True  # noqa: SLF001
    assert calls == [config.results_dir]


def test_relay_contract_states_scientific_separation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "plan"
    run = tmp_path / "run"
    plan.mkdir()
    run.mkdir()
    config = relay_v7.V7CampaignRelayConfig(
        repo=Path(relay_v7.__file__).resolve().parents[3],
        v7_plan_dir=plan,
        v7_run_dir=run,
        trace_package_dir=tmp_path / "traces",
        bridge_json=tmp_path / "bridge.json",
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        supervision_dir=tmp_path / "supervision",
    ).resolved()
    relay = relay_v7.FullCampaignRelayV7(config)
    monkeypatch.setattr(relay, "_module_inventory_v7", lambda: [])
    handoff = {
        "status": "accepted_read_only_v7_handoff",
        "validation_seed_count": 150,
        "fresh_physical_evidence_case_count": 450,
    }
    contract = relay._build_contract(handoff)  # noqa: SLF001
    science = contract["scientific_contract"]
    execution = contract["execution_contract"]
    assert science["validation_seed_count"] == 150
    assert science["fresh_validation_case_count"] == 450
    assert science["campaign_seed_count"] == 30
    assert science["baseline_rows"] == 90
    assert science["incident_rows"] == 3_240
    assert science["campaign_rows"] == 3_330
    assert science["same_30_seeds_for_baseline_and_incidents"] is True
    assert science["campaign_subset_used_for_v7_acceptance"] is False
    assert science["prior_version_simulation_evidence_reused"] is False
    assert science["quality_incident_included"] is False
    assert science["availability_incident_included"] is False
    assert science["capacity_incident_included"] is False
    assert science["stock_incident_included"] is False
    assert science["supplier_state_dependent_risks_enabled"] is False
    assert execution["v7_engine_runs_started_by_relay"] == 0
    assert execution["post_campaign_lots_curves_actions_html_in_this_stage"] is False
    unsigned = dict(contract)
    signature = unsigned.pop("contract_signature")
    assert signature == relay_v7.relay_v4.stable_sha256(unsigned)


class _FakeDetachedProcess:
    def __init__(self, *, pid: int, return_code: int | None) -> None:
        self.pid = pid
        self.return_code = return_code

    def poll(self) -> int | None:
        return self.return_code


def _write_detached_receipt(
    path: Path,
    *,
    schema_version: str,
    status: str,
    token: str,
    pid: int = 0,
) -> dict[str, Any]:
    unsigned: dict[str, Any] = {
        "schema_version": schema_version,
        "status": status,
        "launch_token": token,
        "pid": pid,
    }
    if status == "detached_relay_ready":
        unsigned.update(
            {
                "lock_acquired": True,
                "contract_signature": "a" * 64,
            }
        )
    payload = {
        **unsigned,
        "receipt_signature": relay_v7.relay_v4.stable_sha256(unsigned),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _relay_detach_args(tmp_path: Path) -> SimpleNamespace:
    plan = tmp_path / "plan"
    run = tmp_path / "run"
    plan.mkdir()
    run.mkdir()
    return SimpleNamespace(
        repo=Path(relay_v7.__file__).resolve().parents[3],
        v7_plan_dir=plan,
        v7_run_dir=run,
        trace_package_dir=tmp_path / "traces",
        bridge_json=tmp_path / "bridge.json",
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        supervision_dir=tmp_path / "relay_supervision",
        parallel_shards=2,
        workers_per_shard=2,
        launcher_poll_seconds=0.1,
        relay_poll_seconds=0.1,
        max_wait_hours=1.0,
    )


def test_bridge_v4_compatibility_dependency_hash_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = campaign_contract.sha256_file

    def changed(path: Path) -> str:
        if path.resolve() == Path(bridge_v7.bridge_v4_contract.__file__).resolve():
            return "0" * 64
        return original(path)

    monkeypatch.setattr(campaign_contract, "sha256_file", changed)
    with pytest.raises(bridge_v7.V7BridgeError, match="compatibility contract changed"):
        bridge_v7._validate_frozen_compatibility_contract()  # noqa: SLF001


def test_relay_inventory_explicitly_covers_transitive_campaign_semantics() -> None:
    required = {
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_multiseed_refinement_v6",
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_operating_point_campaign_v4_contract",
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_service_landscape_campaign",
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_service_regime_calibration_protocol",
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_operating_point_full_campaign_v6",
        "etudecas.prototypes.scan_2027_risk_control."
        "launch_supplier_operating_point_full_campaign_v6",
        "etudecas.prototypes.scan_2027_risk_control."
        "finalize_supplier_operating_point_full_campaign_v6",
        "etudecas.simulation.engine.run_first_simulation",
    }
    assert required.issubset(relay_v7.V7_MODULES)


def test_relay_refuses_dependency_drift_before_any_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relay = object.__new__(relay_v7.FullCampaignRelayV7)
    relay.contract = {
        "source_inventory": [
            {"module": "campaign_core", "path": "core.py", "sha256": "a" * 64}
        ]
    }
    monkeypatch.setattr(
        relay,
        "_module_inventory_v7",
        lambda: [{"module": "campaign_core", "path": "core.py", "sha256": "b" * 64}],
    )
    ran: list[bool] = []
    relay.command_executor = lambda *_args: ran.append(True) or 0
    with pytest.raises(relay_v7.FullCampaignRelayError, match="d\u00e9pendance mature"):
        relay.run_step(
            step="must_not_start",
            command=["python", "forbidden.py"],
            completion_check=lambda: False,
            message_fr="must not run",
        )
    assert ran == []


@pytest.mark.parametrize(
    ("schema_version", "ready_status", "waiter"),
    [
        (
            relay_v7.DETACHED_RECEIPT_SCHEMA_VERSION,
            "detached_relay_ready",
            relay_v7._wait_for_detached_ready,  # noqa: SLF001
        ),
    ],
)
def test_detached_parent_accepts_signed_ready_even_if_child_exits_zero_immediately(
    tmp_path: Path,
    schema_version: str,
    ready_status: str,
    waiter: Any,
) -> None:
    token = "ready-token"
    process = _FakeDetachedProcess(pid=4242, return_code=0)
    receipt_path = tmp_path / "detached.json"
    expected = _write_detached_receipt(
        receipt_path,
        schema_version=schema_version,
        status=ready_status,
        token=token,
        pid=process.pid,
    )
    assert (
        waiter(
            process,
            receipt_path=receipt_path,
            token=token,
            timeout_seconds=0.0,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("schema_version", "waiter"),
    [
        (
            relay_v7.DETACHED_RECEIPT_SCHEMA_VERSION,
            relay_v7._wait_for_detached_ready,  # noqa: SLF001
        ),
    ],
)
def test_detached_child_death_before_ready_is_signed_failure(
    tmp_path: Path,
    schema_version: str,
    waiter: Any,
) -> None:
    token = "dead-token"
    process = _FakeDetachedProcess(pid=4343, return_code=7)
    receipt_path = tmp_path / "detached.json"
    _write_detached_receipt(
        receipt_path,
        schema_version=schema_version,
        status="detached_start_reserved",
        token=token,
    )
    with pytest.raises(relay_v7.FullCampaignRelayError, match="avant readiness"):
        waiter(
            process,
            receipt_path=receipt_path,
            token=token,
            timeout_seconds=1.0,
        )
    failed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert failed["status"] == "detached_child_exited_before_ready"
    unsigned = dict(failed)
    signature = unsigned.pop("receipt_signature")
    assert signature == relay_v7.relay_v4.stable_sha256(unsigned)


def test_direct_detached_timeout_stops_child_and_signs_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = "timeout-token"
    process = _FakeDetachedProcess(pid=4444, return_code=None)
    receipt_path = tmp_path / "detached.json"
    _write_detached_receipt(
        receipt_path,
        schema_version=relay_v7.DETACHED_RECEIPT_SCHEMA_VERSION,
        status="detached_start_reserved",
        token=token,
    )
    stopped: list[int] = []
    monkeypatch.setattr(
        relay_v7, "_stop_detached_tree", lambda candidate: stopped.append(candidate.pid)
    )
    with pytest.raises(relay_v7.FullCampaignRelayError, match="limite"):
        relay_v7._wait_for_detached_ready(  # noqa: SLF001
            process,
            receipt_path=receipt_path,
            token=token,
            timeout_seconds=0.0,
        )
    assert stopped == [process.pid]
    failed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert failed["status"] == "detached_start_timeout"


def test_relay_lock_retry_handles_parent_child_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[int] = []

    class Candidate:
        def __enter__(self) -> None:
            attempts.append(1)
            if len(attempts) < 3:
                raise relay_v7.FullCampaignRelayError("busy")

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(relay_v7.relay_v5, "_relay_lock", lambda _path: Candidate())
    monkeypatch.setattr(relay_v7.time, "sleep", lambda _seconds: None)
    with relay_v7._relay_lock_with_retry(  # noqa: SLF001
        tmp_path / ".lock", wait_seconds=10.0
    ):
        pass
    assert len(attempts) == 3


def test_two_direct_detach_attempts_create_only_one_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _relay_detach_args(tmp_path)
    barrier = threading.Barrier(2)
    children: list[_FakeDetachedProcess] = []

    def handoff(_relay: relay_v7.FullCampaignRelayV7) -> dict[str, Any]:
        barrier.wait(timeout=5.0)
        return {"result_signature": "a" * 64}

    def popen(*_args: Any, **_kwargs: Any) -> _FakeDetachedProcess:
        child = _FakeDetachedProcess(pid=5000 + len(children), return_code=None)
        children.append(child)
        return child

    monkeypatch.setattr(relay_v7.FullCampaignRelayV7, "validate_v7_handoff", handoff)
    monkeypatch.setattr(relay_v7.subprocess, "Popen", popen)
    monkeypatch.setattr(
        relay_v7,
        "_wait_for_detached_ready",
        lambda *_args, **_kwargs: {"status": "detached_relay_ready"},
    )

    def launch() -> str:
        try:
            relay_v7.detach(args)
        except relay_v7.FullCampaignRelayError:
            return "refused"
        return "started"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result() for future in (pool.submit(launch), pool.submit(launch))
        ]
    assert sorted(outcomes) == ["refused", "started"]
    assert len(children) == 1


def _write_v7_overlay_fixture(
    tmp_path: Path,
    *,
    scientific_authorization: str = ("accepted_official_v7_fixed_triplet_confirmation"),
) -> tuple[Path, Path]:
    campaign_root = tmp_path / "campaign"
    output_dir = tmp_path / "results"
    campaign_root.mkdir()
    output_dir.mkdir()
    science = {
        "scientific_authorization": scientific_authorization,
        "v7_plan_signature": "a" * 64,
        "v7_result_signature": "b" * 64,
        "validation_seed_count": 150,
        "fresh_validation_case_count": 450,
        "campaign_baseline_seed_count": 30,
        "campaign_baseline_trace_count": 90,
        "campaign_baseline_subset_is_acceptance_gate": False,
        "same_30_seeds_for_baseline_and_incidents": True,
        "prior_version_simulation_evidence_reused": False,
        "retuning_after_v7": False,
    }
    manifest_unsigned = {
        "quality_branch_included": False,
        "quality_incident_included": False,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "stock_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
    }
    manifest = {
        **manifest_unsigned,
        "campaign_signature": finalizer_v7.implementation_v4._stable_sha256(  # noqa: SLF001
            manifest_unsigned
        ),
    }
    manifest_path = campaign_root / "campaign_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    binding_unsigned = {
        "campaign_seeds": list(trace_package.CAMPAIGN_SEEDS),
        "scientific_provenance_v7": science,
    }
    binding = {
        **binding_unsigned,
        "binding_signature": finalizer_v7.implementation_v4._stable_sha256(  # noqa: SLF001
            binding_unsigned
        ),
    }
    (output_dir / "state_validation_binding.json").write_text(
        json.dumps(binding), encoding="utf-8"
    )
    base = {
        "schema_version": "legacy_v4_compatibility_envelope",
        "status": "complete_validated",
        "inputs": {
            "campaign_manifest": str(manifest_path.resolve()),
            "campaign_manifest_sha256": finalizer_v7.implementation_v4._sha256(  # noqa: SLF001
                manifest_path
            ),
            "operating_point_provenance": {
                "producer": "v7_fixed_triplet_confirmation_bridge",
                "legacy_v4_producer_dispatch_key": "v4_fresh_holdout_bridge",
                "legacy_v4_producer_is_compatibility_alias": True,
                "scientific_provenance_v7": science,
            },
        },
        "expected_contract": {
            "repetition_ids": list(trace_package.CAMPAIGN_SEEDS),
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "mechanisms": ["transport_delay", "planned_delivery_shortfall"],
            "quality_branch_included": False,
            "availability_incident_included": False,
        },
        "comparability_checks": {
            "v4_holdout_state_binding_signed_and_accepted": True,
            "v4_holdout_shipment_traces_reused_without_rerun": True,
            "all_3330_metrics_reconstructed_from_signed_case_evidence": True,
            "quality_or_availability_incident_count": 0,
        },
    }
    (output_dir / "campaign_validation.json").write_text(
        json.dumps(base), encoding="utf-8"
    )
    return campaign_root, output_dir


def test_signed_v7_result_overlay_disambiguates_legacy_reader_aliases(
    tmp_path: Path,
) -> None:
    campaign_root, output_dir = _write_v7_overlay_fixture(tmp_path)
    base = json.loads(
        (output_dir / "campaign_validation.json").read_text(encoding="utf-8")
    )
    payload = finalizer_v7.write_v7_overlay(
        campaign_root, output_dir, validated_base=base
    )
    assert payload == finalizer_v7.validate_v7_overlay(campaign_root, output_dir)
    assert payload["status"] == "complete_validated_v7_overlay"
    assert payload["counts"] == {
        "validation_seed_count": 150,
        "validation_case_count": 450,
        "campaign_seed_count": 30,
        "baseline_row_count": 90,
        "incident_row_count": 3_240,
        "campaign_row_count": 3_330,
    }
    assert (
        payload["legacy_reader_aliases"][
            "legacy_keys_are_scientific_v4_evidence_claims"
        ]
        is False
    )
    assert (
        payload["v7_comparability_checks"][
            "quality_capacity_availability_stock_or_state_risk_incident_count"
        ]
        == 0
    )


def test_v7_result_overlay_rejects_false_scientific_authorization(
    tmp_path: Path,
) -> None:
    campaign_root, output_dir = _write_v7_overlay_fixture(
        tmp_path, scientific_authorization="legacy_v4_holdout"
    )
    with pytest.raises(
        finalizer_v7.V7FinalizerAdapterError,
        match="cannot authorize V7 release",
    ):
        finalizer_v7.write_v7_overlay(
            campaign_root,
            output_dir,
            validated_base=json.loads(
                (output_dir / "campaign_validation.json").read_text(encoding="utf-8")
            ),
        )
    assert not (output_dir / finalizer_v7.V7_RESULT_OVERLAY_NAME).exists()


def test_finalizer_refuses_to_retrofit_missing_overlay_on_existing_result(
    tmp_path: Path,
) -> None:
    campaign_root, output_dir = _write_v7_overlay_fixture(tmp_path)
    return_code = finalizer_v7.main(
        [
            "--campaign-root",
            str(campaign_root),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert return_code == 2
    assert not (output_dir / finalizer_v7.V7_RESULT_OVERLAY_NAME).exists()
