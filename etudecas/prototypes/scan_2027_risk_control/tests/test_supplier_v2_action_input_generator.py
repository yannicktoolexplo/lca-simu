from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v2_action_input_generator as generator,
)


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _stable_network(root: Path) -> Path:
    network = root / "network-v2-final"
    network.mkdir(parents=True)
    _json(
        network / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "confirmation_seed_count": 30,
            "rank3_rank4_interval_separated": True,
            "scientific_release_gates": {
                "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
                "all_metric_rows_valid_pass": True,
                "j0_state_hash_pairing_100pct_pass": True,
                "input_graph_hash_pairing_100pct_pass": True,
                "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
                "all_release_gates_pass": True,
            },
            "extensions_required": {
                "multi_lane_supplier_common_cause": {"pass": True, "complete": True},
                "temporal_robustness": {"pass": True, "complete": True},
                "four_business_cause_confirmation": {"pass": True, "complete": True},
                "causal_lot_attribution": {"pass": True, "complete": True},
            },
        },
    )
    _csv(
        network / "supplier_sensitivity_ranking.csv",
        [
            {"supplier_id": supplier, "supplier_sensitivity_rank": rank}
            for rank, supplier in enumerate(("SDC-A", "SDC-B", "SDC-C", "SDC-ALT"), 1)
        ],
    )
    _csv(
        network / "confirmed_top3_stability.csv",
        [
            {
                "supplier_id": supplier,
                "aggregate_confirmation_rank": rank,
                "confirmation_seed_count": 30,
                "top3_presence_seed_count": 29,
            }
            for rank, supplier in enumerate(("SDC-A", "SDC-B", "SDC-C"), 1)
        ],
    )
    _csv(
        network / "lane_sensitivity_ranking.csv",
        [
            {
                "chain_id": "A_X_M1_P1",
                "supplier_id": "SDC-A",
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "target_product_id": "P1",
                "lane_sensitivity_rank": 1,
            },
            {
                "chain_id": "B_Y_M2_P1",
                "supplier_id": "SDC-B",
                "item_id": "item:Y",
                "dst_node_id": "M-2",
                "target_product_id": "P1",
                "lane_sensitivity_rank": 2,
            },
            {
                "chain_id": "C_Z_M3_P2",
                "supplier_id": "SDC-C",
                "item_id": "item:Z",
                "dst_node_id": "M-3",
                "target_product_id": "P2",
                "lane_sensitivity_rank": 3,
            },
            {
                "chain_id": "ALT_X_M1_P1",
                "supplier_id": "SDC-ALT",
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "target_product_id": "P1",
                "lane_sensitivity_rank": 4,
            },
            {
                "chain_id": "A_X_M1_P2",
                "supplier_id": "SDC-A",
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "target_product_id": "P2",
                "lane_sensitivity_rank": 5,
            },
        ],
    )
    _json(network / "scientific_overlay_manifest.json", {"status": "complete"})
    _json(
        network / "scientific_promotion_controls.json",
        {"global_network_priority_robustness_evaluable": False},
    )
    return network


def _priority_boundary(root: Path, *, envelope_released: bool = True) -> Path:
    boundary = root / "priority-boundary"
    boundary.mkdir(parents=True)
    _json(boundary / "priority_boundary_audit_manifest.json", {"status": "complete"})
    _json(
        boundary / "scientific_priority_boundary_audit.json",
        {
            "status": "complete",
            "service_priority_scope": (
                generator.selector.network_dashboard.boundary_contract.SUPPLIER_ENVELOPE_SCOPE
            ),
            "envelope_service_priority_set_release_pass": envelope_released,
            "envelope_service_priority_supplier_ids": (
                ["SDC-A", "SDC-B", "SDC-C"] if envelope_released else []
            ),
            "priority_group_supplier_ids_if_no_universal_top3": (
                [] if envelope_released else ["SDC-A", "SDC-B", "SDC-C", "SDC-ALT"]
            ),
            "universal_supplier_top3_release_pass": False,
            "industrial_supplier_criticality_claimed": False,
            "historical_occurrence_probability": "not_estimated",
        },
    )
    return boundary


def _scope_audit(root: Path) -> Path:
    scope = root / "scope-audit"
    scope.mkdir(parents=True)
    _json(scope / "manifest.json", {"status": "complete", "lane_count": 4})
    _csv(
        scope / "supplier_lane_scope.csv",
        [
            {
                "supplier_id": "SDC-A",
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "downstream_products": "P1|P2",
                "baseline_positive_flow": True,
                "baseline_shipped_qty": 100,
                "uom": "UN",
            },
            {
                "supplier_id": "SDC-B",
                "item_id": "item:Y",
                "dst_node_id": "M-2",
                "downstream_products": "P1",
                "baseline_positive_flow": True,
                "baseline_shipped_qty": 200,
                "uom": "KG",
            },
            {
                "supplier_id": "SDC-C",
                "item_id": "item:Z",
                "dst_node_id": "M-3",
                "downstream_products": "P2",
                "baseline_positive_flow": True,
                "baseline_shipped_qty": 300,
                "uom": "G",
            },
            {
                "supplier_id": "SDC-ALT",
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "downstream_products": "P1|P2",
                "baseline_positive_flow": True,
                "baseline_shipped_qty": 50,
                "uom": "UN",
            },
        ],
    )
    _csv(
        scope / "supplier_item_source_coverage.csv",
        [
            {
                "item_id": "item:X",
                "dst_node_id": "M-1",
                "qualification_and_capacity_confirmed": False,
            }
        ],
    )
    return scope


def _source_field_audit(root: Path) -> Path:
    source = root / "source-field-audit"
    source.mkdir(parents=True)
    _json(
        source / "manifest.json",
        {
            "status": "complete",
            "audit_mode": "read_only_no_simulation",
            "summary": {
                "industrial_supplier_score_available": False,
                "historical_supplier_performance_available": False,
                "supplier_quality_history_available": False,
                "observed_supplier_capacity_available": False,
                "fia_lead_time_is_forecast_not_actual": True,
                "fia_standard_order_quantity_is_capacity": False,
            },
        },
    )
    _csv(
        source / "supplier_source_field_inventory.csv",
        [
            {
                "audit_id": "missing_quality",
                "domain": "quality",
                "usable_statement": "Aucune performance qualité disponible",
            },
            {
                "audit_id": "missing_capacity",
                "domain": "capacity",
                "usable_statement": "Aucune capacité industrielle disponible",
            },
        ],
    )
    return source


def _fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    return (
        _stable_network(root),
        _priority_boundary(root),
        _scope_audit(root),
        _source_field_audit(root),
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
        generator.selector.network_dashboard,
        "load_network_results",
        load_network_results,
    )


def test_cli_help_runs_from_repository_root() -> None:
    script = Path(generator.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--network-results" in completed.stdout
    assert "--priority-boundary-audit" in completed.stdout
    assert "--source-field-audit" in completed.stdout


def test_generator_builds_only_four_allowed_actions_without_running_selector(
    tmp_path: Path,
) -> None:
    network, boundary, scope, source = _fixture(tmp_path)
    source_hashes_before = {
        "network": _hashes(network),
        "boundary": _hashes(boundary),
        "scope": _hashes(scope),
        "source": _hashes(source),
    }
    output = tmp_path / "action-inputs"
    manifest = generator.generate_action_inputs(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        scope_audit_dir=scope,
        source_field_audit_dir=source,
        output_dir=output,
    )

    catalog = _read_csv(output / generator.CATALOG_FILE)
    prerequisites = _read_csv(output / generator.PREREQUISITE_FILE)
    assert manifest["candidate_supplier_count"] == 3
    assert manifest["candidate_lane_count"] == 3
    assert manifest["candidate_supplier_ids"] == ["SDC-A", "SDC-B", "SDC-C"]
    assert manifest["network_selection_status"] == (
        "scoped_envelope_action_candidates_only"
    )
    assert len(catalog) == 24
    assert len(prerequisites) == 78
    assert {row["action_id"] for row in catalog} == set(generator.ALLOWED_ACTION_IDS)
    assert {row["supplier_id"] for row in catalog} == {"SDC-A", "SDC-B", "SDC-C"}
    assert all(row["not_a_recommendation"] == "True" for row in catalog)
    assert all(row["operational_prerequisites_verified"] == "False" for row in catalog)
    assert manifest["selector_executed"] is False
    assert manifest["simulation_run_count"] == 0
    assert manifest["industrial_recommendation_claimed"] is False
    assert manifest["fully_verified_lane_action_count"] == 0
    assert manifest["selector_ready"] is False
    assert manifest["action_readiness_pass"] is False
    assert all(row["supplier_priority_rank"] == "" for row in catalog)
    assert manifest["generation_signature"] == generator.selector._canonical_sha256(
        manifest["signature_payload"]
    )
    assert manifest["artifact_file_sha256"] == {
        generator.CATALOG_FILE: generator._sha256(output / generator.CATALOG_FILE),
        generator.PREREQUISITE_FILE: generator._sha256(
            output / generator.PREREQUISITE_FILE
        ),
    }
    assert {path.name for path in output.iterdir()} == {
        generator.CATALOG_FILE,
        generator.PREREQUISITE_FILE,
        generator.MANIFEST_FILE,
    }
    code_hashes = manifest["source_hashes"]
    assert (
        code_hashes["generator_module_sha256"]
        == hashlib.sha256(Path(generator.__file__).resolve().read_bytes()).hexdigest()
    )
    assert (
        code_hashes["selector_module_sha256"]
        == hashlib.sha256(
            Path(generator.selector.__file__).resolve().read_bytes()
        ).hexdigest()
    )
    assert (
        code_hashes["top3_reader_module_sha256"]
        == hashlib.sha256(
            Path(generator.selector.network_dashboard.__file__).resolve().read_bytes()
        ).hexdigest()
    )
    assert code_hashes["scientific"] == {
        "network_overlay": {
            name: generator._sha256(network / name)
            for name in generator.selector.SCIENTIFIC_OVERLAY_FILES
        },
        "priority_boundary_audit": {
            name: generator._sha256(boundary / name)
            for name in generator.selector.PRIORITY_BOUNDARY_FILES
        },
    }
    assert source_hashes_before == {
        "network": _hashes(network),
        "boundary": _hashes(boundary),
        "scope": _hashes(scope),
        "source": _hashes(source),
    }


def test_missing_operational_data_remains_unverified_and_unquantified(
    tmp_path: Path,
) -> None:
    network, boundary, scope, source = _fixture(tmp_path)
    output = tmp_path / "action-inputs"
    generator.generate_action_inputs(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        scope_audit_dir=scope,
        source_field_audit_dir=source,
        output_dir=output,
    )
    prerequisites = _read_csv(output / generator.PREREQUISITE_FILE)
    positive_value_ids = {
        "transit_gain_committed",
        "quantity_and_uom_confirmed",
        "capacity_quantity_committed",
    }
    unverified_positive = [
        row for row in prerequisites if row["prerequisite_id"] in positive_value_ids
    ]
    assert unverified_positive
    assert all(row["status"] == "not_verified" for row in unverified_positive)
    assert all(row["value"] == "" and row["uom"] == "" for row in unverified_positive)
    qualification = [
        row
        for row in prerequisites
        if row["prerequisite_id"] == "supplier_material_qualification_valid"
    ]
    assert qualification
    assert all(row["status"] == "not_verified" for row in qualification)

    active_alternative = [
        row
        for row in prerequisites
        if row["lane_key"] == "SDC-A|item:X|M-1"
        and row["prerequisite_id"] == "alternative_lane_positive_v2_flow"
    ]
    assert len(active_alternative) == 1
    assert active_alternative[0]["status"] == "verified"
    assert active_alternative[0]["value"] == "1"
    catalog = _read_csv(output / generator.CATALOG_FILE)
    alternative_rows = [
        row
        for row in catalog
        if row["lane_key"] == "SDC-A|item:X|M-1"
        and row["action_id"] == "prepared_qualified_alternative_source"
    ]
    assert alternative_rows
    assert all(row["active_alternative_count"] == "1" for row in alternative_rows)
    assert all(
        row["qualified_active_alternative_count"] == "0" for row in alternative_rows
    )


def test_generator_refuses_unsigned_scientific_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network, boundary, scope, source = _fixture(tmp_path)
    monkeypatch.setattr(
        generator.selector.network_dashboard,
        "load_network_results",
        lambda *_args, **_kwargs: {"input_status": "invalid"},
    )
    output = tmp_path / "action-inputs"
    with pytest.raises(ValueError, match="ne sont pas validées"):
        generator.generate_action_inputs(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            scope_audit_dir=scope,
            source_field_audit_dir=source,
            output_dir=output,
        )
    assert not output.exists()


def test_unresolved_boundary_uses_only_the_signed_unranked_group(
    tmp_path: Path,
) -> None:
    network = _stable_network(tmp_path)
    boundary = _priority_boundary(tmp_path, envelope_released=False)
    scope = _scope_audit(tmp_path)
    source = _source_field_audit(tmp_path)
    output = tmp_path / "action-inputs"
    manifest = generator.generate_action_inputs(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        scope_audit_dir=scope,
        source_field_audit_dir=source,
        output_dir=output,
    )
    assert manifest["candidate_supplier_ids"] == [
        "SDC-A",
        "SDC-B",
        "SDC-C",
        "SDC-ALT",
    ]
    assert manifest["network_selection_status"] == (
        "unseparated_priority_group_action_candidates_only"
    )
    assert manifest["selector_ready"] is False


def test_generator_propagates_v3_four_supplier_unordered_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network = _stable_network(tmp_path)
    boundary = _priority_boundary(tmp_path, envelope_released=False)
    scope = _scope_audit(tmp_path)
    source = _source_field_audit(tmp_path)
    supplier_ids = ["SDC-A", "SDC-ALT", "SDC-B", "SDC-C"]
    monkeypatch.setattr(
        generator.selector,
        "_scientific_candidate_suppliers",
        lambda *_args, **_kwargs: (
            supplier_ids,
            {
                "selection_status": (
                    "service_nonseparation_group_action_candidates_only"
                ),
                "candidate_scope": (
                    generator.selector.SERVICE_NONSEPARATION_GROUP_CANDIDATE_SCOPE
                ),
                "priority_selection_lineage_sha256": "fixture-v3-lineage",
                "follow_up_group_supplier_count": 4,
                "follow_up_group_is_unordered": True,
                "follow_up_chain_ids": [
                    "A_X_M1_P1",
                    "ALT_X_M1_P1",
                    "B_Y_M2_P1",
                    "C_Z_M3_P2",
                ],
                "follow_up_driver_mappings": [
                    {
                        "supplier_id": supplier,
                        "driver_chain_id": chain,
                        "driver_scenario_id": f"scenario-{index}",
                        "driver_failure_mode": "transport_delay",
                    }
                    for index, (supplier, chain) in enumerate(
                        zip(
                            supplier_ids,
                            [
                                "A_X_M1_P1",
                                "ALT_X_M1_P1",
                                "B_Y_M2_P1",
                                "C_Z_M3_P2",
                            ],
                            strict=True,
                        ),
                        1,
                    )
                ],
            },
        ),
    )

    output = tmp_path / "action-inputs"
    manifest = generator.generate_action_inputs(
        network_dir=network,
        priority_boundary_audit_dir=boundary,
        scope_audit_dir=scope,
        source_field_audit_dir=source,
        output_dir=output,
    )

    assert manifest["candidate_supplier_ids"] == supplier_ids
    assert manifest["candidate_supplier_count"] == 4
    assert manifest["candidate_lane_count"] == 4
    assert manifest["network_selection_status"] == (
        "service_nonseparation_group_action_candidates_only"
    )
    assert manifest["candidate_scope"] == (
        generator.selector.SERVICE_NONSEPARATION_GROUP_CANDIDATE_SCOPE
    )
    assert manifest["priority_selection_lineage_sha256"] == "fixture-v3-lineage"
    assert manifest["follow_up_group_supplier_count"] == 4
    assert manifest["follow_up_group_is_unordered"] is True
    assert manifest["follow_up_chain_ids"] == [
        "A_X_M1_P1",
        "ALT_X_M1_P1",
        "B_Y_M2_P1",
        "C_Z_M3_P2",
    ]
    assert manifest["selector_ready"] is False
    assert manifest["action_readiness_pass"] is False
    assert manifest["industrial_recommendation_claimed"] is False
    catalog = _read_csv(output / generator.CATALOG_FILE)
    assert len(catalog) == 32
    assert all(row["supplier_priority_rank"] == "" for row in catalog)
    assert all(row["lane_sensitivity_rank"] == "" for row in catalog)
    assert len(_read_csv(output / generator.PREREQUISITE_FILE)) == 104


def test_generator_refuses_priority_lane_missing_from_scope(tmp_path: Path) -> None:
    network, boundary, scope, source = _fixture(tmp_path)
    rows = _read_csv(scope / "supplier_lane_scope.csv")
    _csv(
        scope / "supplier_lane_scope.csv",
        [row for row in rows if row["supplier_id"] != "SDC-C"],
    )
    scope_manifest_path = scope / "manifest.json"
    scope_manifest = json.loads(scope_manifest_path.read_text(encoding="utf-8"))
    scope_manifest["lane_count"] = 3
    _json(scope_manifest_path, scope_manifest)
    with pytest.raises(ValueError, match="absente de l'audit de périmètre"):
        generator.generate_action_inputs(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            scope_audit_dir=scope,
            source_field_audit_dir=source,
            output_dir=tmp_path / "action-inputs",
        )


def test_generator_never_overwrites_an_existing_output(tmp_path: Path) -> None:
    network, boundary, scope, source = _fixture(tmp_path)
    output = tmp_path / "action-inputs"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generator.generate_action_inputs(
            network_dir=network,
            priority_boundary_audit_dir=boundary,
            scope_audit_dir=scope,
            source_field_audit_dir=source,
            output_dir=output,
        )
    assert marker.read_text(encoding="utf-8") == "keep"
