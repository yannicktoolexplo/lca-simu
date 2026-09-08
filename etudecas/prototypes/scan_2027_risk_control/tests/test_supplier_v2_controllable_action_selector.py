from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_final_package as final_integrator,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v2_controllable_action_selector as selector,
)


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _network(root: Path, *, temporal_pass: bool = True) -> Path:
    network = root / "network-v2-consolidated"
    network.mkdir()
    gates = {
        "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
        "all_metric_rows_valid_pass": True,
        "j0_state_hash_pairing_100pct_pass": True,
        "input_graph_hash_pairing_100pct_pass": True,
        "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
        "all_release_gates_pass": True,
    }
    extensions = {
        "multi_lane_supplier_common_cause": {"pass": True, "complete": True},
        "temporal_robustness": {"pass": temporal_pass, "complete": True},
        "four_business_cause_confirmation": {"pass": True, "complete": True},
        "causal_lot_attribution": {"pass": True, "complete": True},
    }
    _json(
        network / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "confirmation_seed_count": 30,
            "rank3_rank4_interval_separated": True,
            "scientific_release_gates": gates,
            "extensions_required": extensions,
        },
    )
    _csv(
        network / "supplier_sensitivity_ranking.csv",
        [
            {"supplier_id": f"SUP-{rank}", "supplier_sensitivity_rank": rank}
            for rank in range(1, 5)
        ],
    )
    _csv(
        network / "confirmed_top3_stability.csv",
        [
            {
                "supplier_id": f"SUP-{rank}",
                "aggregate_confirmation_rank": rank,
                "top3_presence_seed_count": 29,
                "confirmation_seed_count": 30,
            }
            for rank in range(1, 4)
        ],
    )
    _json(network / "scientific_overlay_manifest.json", {"status": "complete"})
    _json(
        network / "scientific_promotion_controls.json",
        {"global_network_priority_robustness_evaluable": False},
    )
    return network


def _boundary(root: Path, *, envelope_released: bool = True) -> Path:
    boundary = root / "priority-boundary"
    boundary.mkdir()
    _json(boundary / "priority_boundary_audit_manifest.json", {"status": "complete"})
    _json(
        boundary / "scientific_priority_boundary_audit.json",
        {
            "status": "complete",
            "service_priority_scope": (
                selector.network_dashboard.boundary_contract.SUPPLIER_ENVELOPE_SCOPE
            ),
            "envelope_service_priority_set_release_pass": envelope_released,
            "envelope_service_priority_supplier_ids": (
                ["SUP-1", "SUP-2", "SUP-3"] if envelope_released else []
            ),
            "priority_group_supplier_ids_if_no_universal_top3": (
                [] if envelope_released else ["SUP-1", "SUP-2", "SUP-3", "SUP-4"]
            ),
            "universal_supplier_top3_release_pass": False,
            "industrial_supplier_criticality_claimed": False,
            "historical_occurrence_probability": "not_estimated",
        },
    )
    return boundary


def _enable_v3_service_group(
    network: Path,
    boundary: Path,
    *,
    supplier_ids: list[str],
) -> None:
    chain_ids = [f"chain-{index}" for index in range(1, 5)]
    boundary_manifest_path = boundary / "priority_boundary_audit_manifest.json"
    boundary_manifest = json.loads(boundary_manifest_path.read_text(encoding="utf-8"))
    boundary_manifest["package_signature"] = "fixture-boundary-package"
    _json(boundary_manifest_path, boundary_manifest)
    boundary_result_path = boundary / "scientific_priority_boundary_audit.json"
    boundary_result = json.loads(boundary_result_path.read_text(encoding="utf-8"))
    boundary_result.update(
        {
            "envelope_service_priority_set_release_pass": False,
            "envelope_service_priority_supplier_ids": [],
            "envelope_service_nonseparation_group_supplier_ids": supplier_ids,
            "priority_group_supplier_ids_if_no_universal_top3": [
                *supplier_ids,
                "SUP-5",
            ],
            "scoped_descriptive_priority_set_display_allowed": False,
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
        }
    )
    _json(boundary_result_path, boundary_result)
    ranking_path = boundary / "supplier_metric_rankings.csv"
    _csv(ranking_path, [{"supplier_id": supplier} for supplier in supplier_ids])
    lineage = {
        "priority_selection_status": "complete_service_nonseparation_group_follow_up",
        "priority_boundary_package_signature": "fixture-boundary-package",
        "priority_boundary_manifest_sha256": selector._sha256(boundary_manifest_path),
        "priority_boundary_result_sha256": selector._sha256(boundary_result_path),
        "priority_boundary_ranking_sha256": selector._sha256(ranking_path),
        "follow_up_supplier_ids": supplier_ids,
        "service_nonseparation_group_supplier_ids": supplier_ids,
        "selection_candidate_pool_supplier_ids": supplier_ids,
        "follow_up_chain_ids": chain_ids,
        "follow_up_driver_mappings": [
            {
                "supplier_id": supplier,
                "driver_chain_id": chain,
                "driver_scenario_id": f"scenario-{index}",
                "driver_failure_mode": "transport_delay",
            }
            for index, (supplier, chain) in enumerate(
                zip(supplier_ids, chain_ids, strict=True), 1
            )
        ],
        "service_nonseparation_group_fully_followed_up": True,
        "follow_up_group_is_unordered": True,
        "scientific_order_claimed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "slot_order_has_scientific_meaning": False,
    }
    _json(
        network / "scientific_promotion_controls.json",
        {
            "status": "scientific_controls_complete",
            "execution_integrity_pass": True,
            "priority_boundary_lineage_integrity_pass": True,
            "follow_up_group_supplier_count": 4,
            "follow_up_group_is_unordered": True,
            "global_network_priority_robustness_evaluable": False,
            "promotion_allowed": False,
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
            "slot_order_has_scientific_meaning": False,
            "priority_selection_lineage_sha256": "fixture-lineage-digest",
            "priority_selection_lineage": lineage,
        },
    )


def _audit(
    root: Path, *, transport_result: str = "recommended_if_physical_transport"
) -> Path:
    audit = root / "action-audit-v1"
    audit.mkdir()
    _json(
        audit / "manifest.json",
        {
            "status": "complete",
            "validation": {
                "new_simulation_run_count": 0,
                "previous_artifacts_mutated": False,
            },
        },
    )
    rows = [
        {
            "record_type": "tested_lever",
            "failure_mode": "transport_delay",
            "lever_id": "expedited_transport",
            "engine_fidelity": "native_simplified",
            "result_class": transport_result,
            "execution_verified_all_seeds": True,
        },
        {
            "record_type": "tested_lever",
            "failure_mode": "quality_hold",
            "lever_id": "expedited_transport",
            "engine_fidelity": "native_simplified",
            "result_class": "useful_post_release_not_quality_solution",
            "execution_verified_all_seeds": True,
        },
        {
            "record_type": "tested_lever",
            "failure_mode": "transport_delay",
            "lever_id": "targeted_stock",
            "engine_fidelity": "native_engine",
            "result_class": "ineffective_reactive_configuration",
            "execution_verified_all_seeds": False,
        },
        {
            "record_type": "tested_lever",
            "failure_mode": "quality_hold",
            "lever_id": "targeted_stock",
            "engine_fidelity": "native_engine",
            "result_class": "ineffective_response_configuration",
            "execution_verified_all_seeds": True,
        },
    ]
    for index in range(10):
        rows.append(
            {
                "record_type": "tested_lever",
                "failure_mode": f"other_mode_{index}",
                "lever_id": f"other_lever_{index}",
                "engine_fidelity": "approximation",
                "result_class": "excluded",
                "execution_verified_all_seeds": True,
            }
        )
    _csv(audit / "controllable_action_lever_audit.csv", rows)
    return audit


def _catalog(
    root: Path,
    *,
    qualified_alternative: bool = True,
    supplier_count: int = 3,
) -> Path:
    path = root / "action-inputs" / "action_eligibility_catalog.csv"
    lane = "SUP-1|item:X|M-X"

    def row(
        failure_mode: str,
        action_id: str,
        actuator: str,
        *,
        eligible: bool = True,
    ) -> dict[str, object]:
        return {
            "lane_key": lane,
            "supplier_id": "SUP-1",
            "item_id": "item:X",
            "dst_node_id": "M-X",
            "failure_mode": failure_mode,
            "action_id": action_id,
            "native_engine_actuator": actuator,
            "native_actuator_available": True,
            "baseline_positive_flow": True,
            "simulation_execution_allowed": eligible,
            "eligibility_status": "simulable_sous_prerequis" if eligible else "refuse",
            "refusal_reason": "" if eligible else "fixture_refusal",
            "structural_alternative_count": 1 if qualified_alternative else 0,
            "active_alternative_count": 1 if qualified_alternative else 0,
            "qualified_active_alternative_count": 1 if qualified_alternative else 0,
        }

    base_rows = [
        row(
            "transport_delay",
            "targeted_transport_after_observed_delay",
            "expedite_level|lead_time_adjustment_days",
        ),
        *[
            row(mode, "prepositioned_free_stock", "measurement_start_stock_scale_csv")
            for mode in (
                "transport_delay",
                "quality_hold",
                "quality_yield",
                "supply_availability",
            )
        ],
        row(
            "quality_hold",
            "post_release_transport_for_identified_lot",
            "expedite_level|lead_time_adjustment_days",
        ),
        *[
            row(
                mode,
                "prepared_qualified_alternative_source",
                "priority_weight_on_existing_active_lane",
            )
            for mode in ("quality_yield", "supply_availability")
        ],
        row("quality_hold", "post_receipt_transport_expedite", "expedite_level"),
        row("quality_hold", "alternate_released_lot", "none"),
        row("supply_availability", "replanning", "mrp_multiplier"),
        row("quality_yield", "laboratory_acceleration", "quality_delay_days"),
        row("supply_availability", "unknown_native_action", "native_but_unknown"),
    ]
    rows: list[dict[str, object]] = []
    for supplier_index in range(1, supplier_count + 1):
        supplier = f"SUP-{supplier_index}"
        supplier_lane = f"{supplier}|item:X|M-X"
        for source in base_rows:
            rows.append(
                {
                    **source,
                    "supplier_id": supplier,
                    "lane_key": supplier_lane,
                    "network_chain_ids": f"chain-{supplier_index}",
                }
            )
    _csv(path, rows)
    return path


def _prerequisites(
    root: Path,
    *,
    omit: str = "",
    supplier_count: int = 3,
) -> Path:
    path = root / "action-inputs" / "operational_prerequisites.csv"
    rows: list[dict[str, object]] = []
    for supplier_index in range(1, supplier_count + 1):
        lane = f"SUP-{supplier_index}|item:X|M-X"
        for action_id, policy in selector.ACTION_POLICIES.items():
            for prerequisite_id in policy["required_prerequisites"]:
                if prerequisite_id == omit:
                    continue
                positive = prerequisite_id in set(
                    policy.get("positive_value_prerequisites") or ()
                )
                rows.append(
                    {
                        "lane_key": lane,
                        "action_id": action_id,
                        "prerequisite_id": prerequisite_id,
                        "status": "verified",
                        "evidence_reference": f"evidence://{action_id}/{prerequisite_id}",
                        "value": 10 if positive else "",
                        "uom": (
                            "days"
                            if prerequisite_id == "transit_gain_committed"
                            else ("KG" if positive else "")
                        ),
                    }
                )
    _csv(path, rows)
    return path


def _input_manifest(
    *,
    network: Path,
    boundary: Path,
    catalog: Path,
    prerequisites: Path,
    candidate_supplier_ids: list[str],
    selection: dict[str, object],
) -> Path:
    manifest_path = catalog.parent / selector.ACTION_INPUT_MANIFEST_FILE
    artifact_hashes = {
        catalog.name: selector._sha256(catalog),
        prerequisites.name: selector._sha256(prerequisites),
    }
    scientific_hashes = selector._scientific_source_hashes(network, boundary)
    module_hashes = {
        "generator_module_sha256": selector._sha256(
            Path(selector.__file__)
            .resolve()
            .with_name("supplier_v2_action_input_generator.py")
        ),
        "selector_module_sha256": selector._sha256(Path(selector.__file__).resolve()),
        "top3_reader_module_sha256": selector._sha256(
            Path(selector.network_dashboard.__file__).resolve()
        ),
        "boundary_contract_module_sha256": selector._sha256(
            Path(selector.network_dashboard.boundary_contract.__file__).resolve()
        ),
        "extension_contract_module_sha256": selector._sha256(
            Path(selector.network_dashboard.extension_contract.__file__).resolve()
        ),
    }
    signature_payload = {
        "schema_version": selector.ACTION_INPUT_SCHEMA_VERSION,
        "network_hashes": {"lane_sensitivity_ranking.csv": "fixture"},
        "scientific_hashes": scientific_hashes,
        "scope_hashes": {"manifest.json": "fixture"},
        "source_field_hashes": {"manifest.json": "fixture"},
        **module_hashes,
        "allowed_action_ids": list(selector.ACTION_POLICIES),
        "artifact_file_sha256": artifact_hashes,
    }
    follow_up_chains = list(selection.get("follow_up_chain_ids") or [])
    catalog_rows = _read_csv(catalog)
    prerequisite_rows = _read_csv(prerequisites)
    payload = {
        "schema_version": selector.ACTION_INPUT_SCHEMA_VERSION,
        "status": "prepared_scientific_candidates_fail_closed",
        "generation_signature": selector._canonical_sha256(signature_payload),
        "signature_payload": signature_payload,
        "artifact_file_sha256": artifact_hashes,
        "network_selection_status": selection.get("selection_status"),
        "candidate_scope": selection.get("candidate_scope"),
        "priority_selection_lineage_sha256": selection.get(
            "priority_selection_lineage_sha256", ""
        ),
        "follow_up_group_supplier_count": selection.get(
            "follow_up_group_supplier_count"
        ),
        "follow_up_group_is_unordered": True,
        "follow_up_chain_ids": follow_up_chains,
        "follow_up_driver_mappings": list(
            selection.get("follow_up_driver_mappings") or []
        ),
        "candidate_supplier_ids": candidate_supplier_ids,
        "candidate_supplier_count": len(candidate_supplier_ids),
        "candidate_lane_count": len(follow_up_chains) or len(candidate_supplier_ids),
        "allowed_action_ids": list(selector.ACTION_POLICIES),
        "catalog_row_count": len(catalog_rows),
        "prerequisite_row_count": len(prerequisite_rows),
        "selector_executed": False,
        "selector_ready": False,
        "action_readiness_pass": False,
        "industrial_recommendation_claimed": False,
        "simulation_run_count": 0,
        "missing_data_never_promoted_to_verified": True,
        "qualified_active_alternative_count_forced_to_zero_without_register": True,
        "source_hashes": {
            "scientific": scientific_hashes,
            "network_overlay_data": signature_payload["network_hashes"],
            "scope_audit": signature_payload["scope_hashes"],
            "source_field_audit": signature_payload["source_field_hashes"],
            **module_hashes,
        },
        "outputs": [catalog.name, prerequisites.name],
    }
    _json(manifest_path, payload)
    return manifest_path


def _run_selector(**kwargs: object) -> dict[str, object]:
    network = Path(kwargs["network_dir"])
    boundary = Path(kwargs["priority_boundary_audit_dir"])
    catalog = Path(kwargs["action_catalog_path"])
    prerequisites = Path(kwargs["prerequisite_path"])
    suppliers, selection = selector._scientific_candidate_suppliers(
        network,
        boundary,
    )
    manifest = _input_manifest(
        network=network,
        boundary=boundary,
        catalog=catalog,
        prerequisites=prerequisites,
        candidate_supplier_ids=suppliers,
        selection=selection,
    )
    return selector.run_selector(
        **kwargs,
        action_input_manifest_path=manifest,
    )


def _fixture(
    root: Path,
    *,
    temporal_pass: bool = True,
    qualified_alternative: bool = True,
    omit_prerequisite: str = "",
    transport_result: str = "recommended_if_physical_transport",
    envelope_released: bool = True,
    supplier_count: int = 3,
) -> tuple[Path, Path, Path, Path, Path]:
    return (
        _network(root, temporal_pass=temporal_pass),
        _boundary(root, envelope_released=envelope_released),
        _catalog(
            root,
            qualified_alternative=qualified_alternative,
            supplier_count=supplier_count,
        ),
        _prerequisites(
            root,
            omit=omit_prerequisite,
            supplier_count=supplier_count,
        ),
        _audit(root, transport_result=transport_result),
    )


@pytest.fixture(autouse=True)
def _signed_overlay_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_network_results(
        _network: Path,
        *,
        priority_boundary_audit_dir: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        audit = json.loads(
            (
                Path(priority_boundary_audit_dir)
                / "scientific_priority_boundary_audit.json"
            ).read_text(encoding="utf-8")
        )
        released = audit["envelope_service_priority_set_release_pass"] is True
        envelope_ids = list(audit["envelope_service_priority_supplier_ids"])
        group_ids = list(audit["priority_group_supplier_ids_if_no_universal_top3"])
        return {
            "input_status": "signed_scientific_overlay_and_audits_valid",
            "priority_reporting_status": (
                "envelope_service_top3_released" if released else "priority_group_only"
            ),
            "stable_priorities": (
                [{"supplier_id": supplier} for supplier in envelope_ids]
                if released
                else []
            ),
            "priority_group_supplier_ids": group_ids,
        }

    monkeypatch.setattr(
        selector.network_dashboard,
        "load_network_results",
        load_network_results,
    )


def test_direct_cli_help_works_from_repository_root():
    script = Path(selector.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--network-results" in completed.stdout
    assert "--priority-boundary-audit" in completed.stdout
    assert "--action-input-manifest" in completed.stdout
    assert "--prerequisite-evidence" in completed.stdout


def test_selector_keeps_only_native_controllable_actions_with_all_prerequisites(
    tmp_path: Path,
):
    network, boundary, catalog, prerequisites, audit = _fixture(tmp_path)
    source_hashes = {
        path: selector._sha256(path)
        for directory in (network, boundary, audit)
        for path in directory.rglob("*")
        if path.is_file()
    } | {
        catalog: selector._sha256(catalog),
        prerequisites: selector._sha256(prerequisites),
    }
    manifest = _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    selected = _read_csv(tmp_path / "selection" / selector.SELECTED_FILE)
    blocked = _read_csv(tmp_path / "selection" / selector.BLOCKED_FILE)
    assert manifest["status"] == "blocked_scoped_priority_not_globally_released"
    assert manifest["selection_status"] == "scoped_envelope_action_candidates_only"
    assert manifest["candidate_supplier_ids"] == ["SUP-1", "SUP-2", "SUP-3"]
    assert manifest["selected_supplier_ids"] == []
    assert selected == []
    assert len(blocked) == 39
    assert manifest["scientific_blocked_candidate_count"] == 39
    assert manifest["operationally_ready_but_scientifically_blocked_count"] == 24
    assert manifest["action_readiness_pass"] is False
    assert {row["action_id"] for row in blocked} >= set(selector.ACTION_POLICIES)
    assert all(row["selector_status"] == "blocked" for row in blocked)
    assert all(
        row["candidate_scope"] == selector.SCOPED_CANDIDATE_SCOPE for row in blocked
    )
    assert all(
        row["scientific_blocking_reason"] == selector.SCIENTIFIC_BLOCKING_REASON
        and selector.SCIENTIFIC_BLOCKING_REASON in row["blocking_reasons"]
        for row in blocked
    )
    code_hashes = manifest["source_hashes"]
    assert code_hashes["selector_module_sha256"] == selector._sha256(
        Path(selector.__file__).resolve()
    )
    assert code_hashes["top3_reader_module_sha256"] == selector._sha256(
        Path(selector.network_dashboard.__file__).resolve()
    )
    scientific_hashes = code_hashes["scientific"]
    assert scientific_hashes == {
        "network_overlay": {
            name: selector._sha256(network / name)
            for name in selector.SCIENTIFIC_OVERLAY_FILES
        },
        "priority_boundary_audit": {
            name: selector._sha256(boundary / name)
            for name in selector.PRIORITY_BOUNDARY_FILES
        },
    }
    verdict = manifest["scientific_verdict"]
    assert "catalogue de candidats bloques" in verdict["conclusion_allowed"]
    assert "ni une probabilite d'incident" in verdict["claims_forbidden"]
    assert all(row["future_test_only_not_recommendation"] == "True" for row in blocked)
    assert all(row["in_horizon_stock_injection_allowed"] == "False" for row in blocked)
    blocked_ids = {row["action_id"] for row in blocked}
    assert {
        "post_receipt_transport_expedite",
        "alternate_released_lot",
        "replanning",
        "laboratory_acceleration",
        "unknown_native_action",
    } <= blocked_ids
    boundary_payload = json.loads(
        (boundary / "scientific_priority_boundary_audit.json").read_text(
            encoding="utf-8"
        )
    )
    validated = final_integrator._validate_scientific_action_selection(
        tmp_path / "selection",
        network_root=network,
        boundary_root=boundary,
        boundary=boundary_payload,
        network_conclusion="envelope_service_top3_scoped",
        source_network_hashes=None,
    )
    assert validated["schema_version"] == selector.SCHEMA_VERSION
    for module in (final_integrator, selector.network_dashboard):
        module_path = Path(module.__file__).resolve()
        assert (
            selector._sha256(module_path)
            == hashlib.sha256(module_path.read_bytes()).hexdigest()
        )
    assert all(
        selector._sha256(path) == digest for path, digest in source_hashes.items()
    )


def test_missing_prepared_stock_evidence_blocks_every_stock_scenario(tmp_path: Path):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        omit_prerequisite="stock_build_source_identified",
    )
    _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    selected = _read_csv(tmp_path / "selection" / selector.SELECTED_FILE)
    blocked = _read_csv(tmp_path / "selection" / selector.BLOCKED_FILE)
    assert all(row["action_id"] != "prepositioned_free_stock" for row in selected)
    stock = [row for row in blocked if row["action_id"] == "prepositioned_free_stock"]
    assert len(stock) == 12
    assert all(
        "prerequis_absent:stock_build_source_identified" in row["blocking_reasons"]
        for row in stock
    )


def test_unqualified_or_inactive_alternative_is_never_selected(tmp_path: Path):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        qualified_alternative=False,
    )
    _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    selected = _read_csv(tmp_path / "selection" / selector.SELECTED_FILE)
    blocked = _read_csv(tmp_path / "selection" / selector.BLOCKED_FILE)
    assert all(
        row["action_id"] != "prepared_qualified_alternative_source" for row in selected
    )
    alternatives = [
        row
        for row in blocked
        if row["action_id"] == "prepared_qualified_alternative_source"
    ]
    assert len(alternatives) == 6
    assert all(
        "aucune_source_alternative_active_dans_v2" in row["blocking_reasons"]
        for row in alternatives
    )


def test_unresolved_boundary_keeps_the_signed_group_fail_closed(tmp_path: Path):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        envelope_released=False,
        supplier_count=4,
    )
    manifest = _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    assert manifest["status"] == "blocked_priority_boundary_unresolved"
    assert manifest["selection_status"] == (
        "unseparated_priority_group_action_candidates_only"
    )
    assert manifest["candidate_supplier_ids"] == [
        "SUP-1",
        "SUP-2",
        "SUP-3",
        "SUP-4",
    ]
    assert manifest["selected_action_test_count"] == 0
    assert manifest["blocked_action_candidate_count"] == 52
    assert _read_csv(tmp_path / "selection" / selector.SELECTED_FILE) == []


def test_v3_uses_exact_four_supplier_service_group_not_universal_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        envelope_released=False,
        supplier_count=4,
    )
    supplier_ids = ["SUP-1", "SUP-2", "SUP-3", "SUP-4"]
    _enable_v3_service_group(network, boundary, supplier_ids=supplier_ids)
    monkeypatch.setattr(
        selector.network_dashboard.extension_contract,
        "validate_scientific_overlay",
        lambda _path: {"status": "complete"},
    )
    monkeypatch.setattr(
        selector.network_dashboard.boundary_contract,
        "validate_audit_package",
        lambda _path: {"status": "complete"},
    )

    manifest = _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )

    assert manifest["status"] == "blocked_service_nonseparation_group_follow_up"
    assert manifest["selection_status"] == (
        "service_nonseparation_group_action_candidates_only"
    )
    assert manifest["candidate_scope"] == (
        selector.SERVICE_NONSEPARATION_GROUP_CANDIDATE_SCOPE
    )
    assert manifest["candidate_supplier_ids"] == supplier_ids
    assert manifest["follow_up_group_supplier_count"] == 4
    assert manifest["follow_up_group_is_unordered"] is True
    assert manifest["follow_up_chain_ids"] == [
        "chain-1",
        "chain-2",
        "chain-3",
        "chain-4",
    ]
    assert manifest["selected_supplier_ids"] == []
    assert manifest["selected_action_test_count"] == 0
    assert manifest["blocked_action_candidate_count"] == 52
    assert _read_csv(tmp_path / "selection" / selector.SELECTED_FILE) == []


def test_v3_rejects_boundary_tamper_before_creating_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        envelope_released=False,
        supplier_count=4,
    )
    _enable_v3_service_group(
        network,
        boundary,
        supplier_ids=["SUP-1", "SUP-2", "SUP-3", "SUP-4"],
    )
    monkeypatch.setattr(
        selector.network_dashboard.extension_contract,
        "validate_scientific_overlay",
        lambda _path: {"status": "complete"},
    )
    monkeypatch.setattr(
        selector.network_dashboard.boundary_contract,
        "validate_audit_package",
        lambda _path: {"status": "complete"},
    )
    result_path = boundary / "scientific_priority_boundary_audit.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["envelope_service_nonseparation_group_supplier_ids"] = [
        "SUP-1",
        "SUP-2",
        "SUP-3",
    ]
    _json(result_path, payload)

    output = tmp_path / "selection"
    with pytest.raises(ValueError, match="frontiere vivante"):
        _run_selector(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            action_catalog_path=catalog,
            prerequisite_path=prerequisites,
            action_audit_dir=audit,
            output_dir=output,
        )
    assert not output.exists()


def test_selector_rejects_catalog_changed_after_generator_signature(
    tmp_path: Path,
):
    network, boundary, catalog, prerequisites, audit = _fixture(tmp_path)
    suppliers, selection = selector._scientific_candidate_suppliers(
        network,
        boundary,
    )
    input_manifest = _input_manifest(
        network=network,
        boundary=boundary,
        catalog=catalog,
        prerequisites=prerequisites,
        candidate_supplier_ids=suppliers,
        selection=selection,
    )
    with catalog.open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")

    output = tmp_path / "selection"
    with pytest.raises(ValueError, match="Empreinte du catalogue"):
        selector.run_selector(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            action_input_manifest_path=input_manifest,
            action_catalog_path=catalog,
            prerequisite_path=prerequisites,
            action_audit_dir=audit,
            output_dir=output,
        )
    assert not output.exists()


def test_boundary_trio_overrides_the_inherited_aggregate_top3(tmp_path: Path):
    network = _network(tmp_path)
    boundary = _boundary(tmp_path)
    boundary_path = boundary / "scientific_priority_boundary_audit.json"
    boundary_payload = json.loads(boundary_path.read_text(encoding="utf-8"))
    boundary_payload["envelope_service_priority_supplier_ids"] = [
        "SUP-2",
        "SUP-3",
        "SUP-4",
    ]
    _json(boundary_path, boundary_payload)
    catalog = _catalog(tmp_path, supplier_count=4)
    catalog_rows = [row for row in _read_csv(catalog) if row["supplier_id"] != "SUP-1"]
    _csv(catalog, catalog_rows)
    prerequisites = _prerequisites(tmp_path, supplier_count=4)
    prerequisite_rows = [
        row
        for row in _read_csv(prerequisites)
        if not row["lane_key"].startswith("SUP-1|")
    ]
    _csv(prerequisites, prerequisite_rows)
    audit = _audit(tmp_path)
    manifest = _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    assert manifest["candidate_supplier_ids"] == ["SUP-2", "SUP-3", "SUP-4"]
    assert manifest["selected_supplier_ids"] == []
    assert {
        row["supplier_id"]
        for row in _read_csv(tmp_path / "selection" / selector.BLOCKED_FILE)
    } == {"SUP-2", "SUP-3", "SUP-4"}


def test_prior_audit_must_support_transport_action(tmp_path: Path):
    network, boundary, catalog, prerequisites, audit = _fixture(
        tmp_path,
        transport_result="counterproductive_proxy",
    )
    _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=tmp_path / "selection",
    )
    selected = _read_csv(tmp_path / "selection" / selector.SELECTED_FILE)
    blocked = _read_csv(tmp_path / "selection" / selector.BLOCKED_FILE)
    assert all(
        row["action_id"] != "targeted_transport_after_observed_delay"
        for row in selected
    )
    transport = next(
        row
        for row in blocked
        if row["action_id"] == "targeted_transport_after_observed_delay"
    )
    assert "prior_audit_result_not_compatible" in transport["blocking_reasons"]


def test_existing_output_is_never_overwritten(tmp_path: Path):
    network, boundary, catalog, prerequisites, audit = _fixture(tmp_path)
    output = tmp_path / "selection"
    _run_selector(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        action_catalog_path=catalog,
        prerequisite_path=prerequisites,
        action_audit_dir=audit,
        output_dir=output,
    )
    with pytest.raises(FileExistsError):
        _run_selector(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            action_catalog_path=catalog,
            prerequisite_path=prerequisites,
            action_audit_dir=audit,
            output_dir=output,
        )
