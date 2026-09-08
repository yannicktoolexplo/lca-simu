from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_common_cause_intermediate_15 as report,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _local_metric(
    product: str,
    *,
    on_due: float,
    delay_equivalent: float,
    released: float,
) -> dict[str, object]:
    demand = 1_000.0
    return {
        "backlog_end_qty": max(0.0, demand * (1.0 - on_due)),
        "backlog_qty_days_numerator": demand * delay_equivalent,
        "demand_qty_denominator": demand,
        "fill_rate": on_due,
        "normalized_backlog_days_per_demand_unit": delay_equivalent,
        "on_due_ratio": on_due,
        "outcome_day_count": 720,
        "outcome_end_day": 719,
        "outcome_spec_id": report.OUTCOME_SPEC_ID,
        "outcome_start_day": 0,
        "product_id": product,
        "recovery_metric_status": "excluded_not_redefined",
        "released_qty_numerator": released,
        "required_qty_denominator": demand,
        "series_complete": True,
        "series_day_count": 720,
        "served_on_due_qty_numerator": demand * on_due,
        "served_qty_numerator": demand * on_due,
        "uom": "UN",
    }


def _base_evidence(case_key: str, seed: int) -> dict[str, object]:
    return {
        "applied_event_ids": [],
        "case_key": case_key,
        "configured_event_ids": [],
        "extended_horizon_input_support_pass": True,
        "flow_metrics": [],
        "input_sha256": _digest(f"input-{seed}"),
        "j0_state_sha256": _digest(f"j0-{seed}"),
        "loaded_event_rows": [],
        "local_product_metrics": [],
        "lot_events": [],
        "lot_genealogy": [],
        "outcome_bundle_sha256": report.EXPECTED_OUTCOME_BUNDLE_SHA256,
        "post_J719_extrapolation_policy": "not_applicable_fixed_J0_J719",
        "preincident_state_snapshots": [],
        "product_metrics": [],
        "resolved_lot_trace_enabled": True,
        "reused_source_case": False,
        "risk_application_rows": [],
        "risk_input_sha256": "",
        "risk_load_warnings": [],
        "run_dir": "C:/must/not/be/read",
        "seed": seed,
        "simulation_days": 720,
        "status": "executed",
        "valid": True,
        "validation_errors": [],
    }


def _baseline_evidence(seed: int) -> dict[str, object]:
    payload = _base_evidence(report._baseline_key(seed), seed)
    local = [
        _local_metric(product, on_due=1.0, delay_equivalent=0.0, released=1_000.0)
        for product in report.runner.PRODUCTS
    ]
    compact_flows = []
    for scope in report.SUPPLIER_SCOPES:
        for lane in scope.lanes:
            compact_flows.append(
                {
                    "aggregation_source": "runner_generated_daily_baseline_exact_window",
                    "baseline_window_end_day": scope.end_day,
                    "baseline_window_start_day": scope.start_day,
                    "chain_id": lane.chain_id,
                    "cross_uom_aggregation_allowed": False,
                    "dst_node_id": lane.dst_node_id,
                    "item_id": lane.item_id,
                    "pulled_qty": 10.0,
                    "shipped_qty": 10.0,
                    "supplier_id": lane.supplier_id,
                    "uom": "KG",
                }
            )
    payload["local_product_metrics"] = local
    payload["product_metrics"] = [
        {"product_id": product, "uom": "UN", "on_due_ratio": 1.0}
        for product in report.runner.PRODUCTS
    ]
    payload["flow_metrics"] = compact_flows
    return payload


def _stress_evidence(
    scope: report.SupplierScope, cause: str, seed: int
) -> dict[str, object]:
    case = report._stress_case(scope, cause, seed)
    payload = _base_evidence(case.case_key, seed)
    cause_index = report.CAUSE_ORDER.index(cause)
    seed_index = report.EXPECTED_SEEDS.index(seed)
    supplier_index = report.SUPPLIER_SCOPES.index(scope)
    local = []
    for product_index, product in enumerate(scope.products):
        degradation = (
            0.01
            + 0.005 * cause_index
            + 0.002 * supplier_index
            + 0.001 * product_index
            + 0.0001 * seed_index
        )
        local.append(
            _local_metric(
                product,
                on_due=1.0 - degradation,
                delay_equivalent=1.0 + cause_index + 0.1 * seed_index,
                released=1_000.0 - (10.0 + cause_index + seed_index),
            )
        )
    risk_rows = report.runner._risk_rows(case)
    event_ids = [str(row["event_id"]) for row in risk_rows]
    supplier_index = report.SUPPLIER_SCOPES.index(scope)

    def shipped_qty() -> float:
        if cause == "quality_yield":
            return 8.0
        if cause == "supply_availability" and supplier_index == 0:
            return 0.0
        return 10.0

    payload.update(
        {
            "applied_event_ids": event_ids,
            "configured_event_ids": event_ids,
            "flow_metrics": [
                {
                    "chain_id": lane.chain_id,
                    "dst_node_id": lane.dst_node_id,
                    "item_id": lane.item_id,
                    "pulled_qty": 10.0,
                    "shipped_qty": shipped_qty(),
                    "supplier_id": lane.supplier_id,
                    "uom": "KG",
                }
                for lane in scope.lanes
            ],
            "loaded_event_rows": risk_rows,
            "local_product_metrics": local,
            "product_metrics": [
                {"product_id": product, "uom": "UN"} for product in scope.products
            ],
            "risk_application_rows": [
                {"event_ids": event_id} for event_id in event_ids
            ],
            "risk_input_sha256": _digest(case.case_key),
        }
    )
    return payload


def _write_evidence(
    runner_dir: Path,
    ledger: dict[str, object],
    case_key: str,
    payload: dict[str, object],
) -> None:
    relative = report.runner._canonical_ledger_relative_path(case_key)
    path = runner_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = report._canonical_json_bytes(payload)
    path.write_bytes(raw)
    ledger["case_files"][case_key] = relative.as_posix()
    ledger["case_file_sha256"][case_key] = report._sha256_bytes(raw)


def _write_ledger(runner_dir: Path, ledger: dict[str, object]) -> None:
    (runner_dir / report.LEDGER_FILE).write_bytes(report._canonical_json_bytes(ledger))


@pytest.fixture()
def complete_runner(tmp_path: Path) -> Path:
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    ledger: dict[str, object] = {
        "runner_signature": report.EXPECTED_RUNNER_SIGNATURE,
        "case_files": {},
        "case_file_sha256": {},
    }
    for seed in report.EXPECTED_SEEDS:
        baseline = _baseline_evidence(seed)
        _write_evidence(runner_dir, ledger, report._baseline_key(seed), baseline)
    for scope in report.SUPPLIER_SCOPES:
        for cause in report.CAUSE_ORDER:
            for seed in report.EXPECTED_SEEDS:
                stress = _stress_evidence(scope, cause, seed)
                _write_evidence(
                    runner_dir,
                    ledger,
                    report._case_key(scope.supplier_id, cause, seed),
                    stress,
                )
    _write_ledger(runner_dir, ledger)
    return runner_dir


def _minimal_incomplete_runner(tmp_path: Path, *, extra: bool = False) -> Path:
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    common = sorted(report._expected_common_keys())
    if not extra:
        common.pop()
    else:
        common.append(
            "multi_lane_supplier_common_cause::common__sdc-vd0519670a__"
            "transport_delay::seed_340297"
        )
    keys = [*common, *sorted(report._expected_baseline_keys())]
    ledger = {
        "runner_signature": report.EXPECTED_RUNNER_SIGNATURE,
        "case_files": {
            key: report.runner._canonical_ledger_relative_path(key).as_posix()
            for key in keys
        },
        "case_file_sha256": {key: "0" * 64 for key in keys},
    }
    _write_ledger(runner_dir, ledger)
    return runner_dir


def test_incomplete_readiness_and_build_do_not_read_evidence_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner_dir = _minimal_incomplete_runner(tmp_path)
    output = tmp_path / "result"

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("une preuve ne doit pas être lue avant 120/120")

    monkeypatch.setattr(report, "_load_evidence", forbidden)
    readiness, result = report.evaluate_readiness(runner_dir)
    assert readiness.ready is False
    assert readiness.completed_expected_cases == 119
    assert result is None
    with pytest.raises(report.NotReadyError):
        report.build_package(runner_dir=runner_dir, output_dir=output)
    assert not output.exists()


def test_extra_common_case_refuses_exact_checkpoint(tmp_path: Path) -> None:
    runner_dir = _minimal_incomplete_runner(tmp_path, extra=True)
    readiness, result = report.evaluate_readiness(runner_dir)
    assert readiness.ready is False
    assert readiness.completed_expected_cases == 120
    assert readiness.common_case_count_in_ledger == 121
    assert readiness.extra_case_count == 1
    assert result is None


def test_builds_12_business_rows_without_csv_or_engine(
    complete_runner: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("lecture CSV/moteur interdite")

    monkeypatch.setattr(report.runner, "_read_csv", forbidden)
    output = tmp_path / "intermediate"
    built = report.build_package(runner_dir=complete_runner, output_dir=output)
    assert built == output.resolve()
    assert {path.name for path in output.iterdir()} == set(report.OUTPUT_FILES)
    manifest = report.validate_package(output)
    assert manifest["guards"]["runner_csv_read_allowed"] is False
    assert len(manifest["source_evidence"]) == 135

    result = json.loads((output / report.RESULT_JSON).read_text(encoding="utf-8"))
    assert len(result["resultats"]) == 12
    first = result["resultats"][0]
    assert first["fournisseur"] == "SDC-VD0519670A"
    assert first["cause"] == "transport_delay"
    assert first["produit"] == "268091"
    assert first["ecart_service_points"] == pytest.approx(
        {"moyenne": -1.07, "minimum": -1.14, "maximum": -1.0}
    )
    assert first["retard_cumule_equivalent_jours"] == pytest.approx(
        {"moyenne": 1.7, "minimum": 1.0, "maximum": 2.4}
    )
    assert first["ecart_production_liberee_cumulee_j719_un"] == pytest.approx(
        {"moyenne": 17.0, "minimum": 10.0, "maximum": 24.0}
    )
    assert first["fenetre"] == "J55–J234"
    assert first["simulations_avec_effet_aval"] == 15
    assert first["consequence_aval"]["ce_nombre_est_une_probabilite"] is False
    assert first["perturbation_configuree"]["nombre_flux"] == 2
    assert (
        first["effet_physique_obtenu_dans_le_modele"][
            "simulations_avec_perturbation_appliquee"
        ]
        == 15
    )
    availability = next(
        row
        for row in result["resultats"]
        if row["fournisseur"] == "SDC-VD0519670A"
        and row["cause"] == "supply_availability"
    )
    assert all(
        flow["ecart_quantite_expediee_pourcent"]["moyenne"] == -100.0
        for flow in availability["effet_physique_obtenu_dans_le_modele"]["flux"]
    )
    page = (output / report.RESULT_HTML).read_text(encoding="utf-8")
    assert "Nous n'estimons pas encore sa fréquence d'occurrence" in page
    assert "Aucun ordre de priorité ni recommandation" in page
    assert "Service simulé en volume" in page
    assert "J55–J234" in page and "J60–J239" in page
    assert "15/15 simulations avec effet aval" in page
    assert "Effet physique obtenu sur les flux du modèle" in page
    assert "ne garantit pas 50 % livré" in page
    assert "Aucun laboratoire, stock de quarantaine natif" in page
    assert "ni une preuve sur les lots" in page
    assert "maximum obtenus dans les simulations" in page
    assert "maximum observé" not in page
    assert "Production à rattraper" not in page
    assert "<script" not in page
    assert "http://" not in page and "https://" not in page


def test_downstream_effect_count_uses_explicit_tolerances() -> None:
    zero = {
        "service_delta_percentage_points": 0.0,
        "delay_equivalent_days": 0.0,
        "released_production_gap_units": -0.0,
    }
    noise = {
        "service_delta_percentage_points": 0.5 * report.SERVICE_EFFECT_TOLERANCE_POINTS,
        "delay_equivalent_days": 0.5 * report.DELAY_EFFECT_TOLERANCE_DAYS,
        "released_production_gap_units": (
            0.5 * report.PRODUCTION_EFFECT_TOLERANCE_UNITS
        ),
    }
    effect = dict(zero, delay_equivalent_days=0.001)
    assert report._has_downstream_effect(zero) is False
    assert report._has_downstream_effect(noise) is False
    assert report._has_downstream_effect(effect) is True


def test_hash_and_valid_true_are_fail_closed(
    complete_runner: Path, tmp_path: Path
) -> None:
    ledger_path = complete_runner / report.LEDGER_FILE
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    key = sorted(report._expected_common_keys())[0]
    evidence_path = complete_runner / ledger["case_files"][key]
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Empreinte de preuve invalide"):
        report.build_package(
            runner_dir=complete_runner,
            output_dir=tmp_path / "bad-hash",
        )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["valid"] = False
    raw = report._canonical_json_bytes(payload)
    evidence_path.write_bytes(raw)
    ledger["case_file_sha256"][key] = report._sha256_bytes(raw)
    _write_ledger(complete_runner, ledger)
    with pytest.raises(ValueError, match="Preuve non valide"):
        report.build_package(
            runner_dir=complete_runner,
            output_dir=tmp_path / "invalid-evidence",
        )


def test_package_is_non_overwritable_and_tamper_evident(
    complete_runner: Path, tmp_path: Path
) -> None:
    output = tmp_path / "intermediate"
    report.build_package(runner_dir=complete_runner, output_dir=output)
    with pytest.raises(FileExistsError):
        report.build_package(runner_dir=complete_runner, output_dir=output)
    page = output / report.RESULT_HTML
    page.write_text(page.read_text(encoding="utf-8") + "altéré", encoding="utf-8")
    with pytest.raises(ValueError, match="altéré"):
        report.validate_package(output)
