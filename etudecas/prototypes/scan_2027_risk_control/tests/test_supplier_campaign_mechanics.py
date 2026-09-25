from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_campaign_mechanics as mechanics,
    supplier_campaign_source_revision as revision,
    supplier_operating_point_full_campaign_v2 as v2,
    supplier_operating_point_full_campaign_v4 as v4,
)


def test_context_reads_current_dependencies_and_keeps_versions_separate(monkeypatch):
    monkeypatch.setattr(v2, "TARGET_QUANTITY_TOLERANCE", 123.0)
    monkeypatch.setattr(v4, "TARGET_QUANTITY_TOLERANCE", 456.0)
    assert v2._campaign_context.TARGET_QUANTITY_TOLERANCE == 123.0
    assert v4._campaign_context.TARGET_QUANTITY_TOLERANCE == 456.0
    monkeypatch.setattr(v2, "TARGET_QUANTITY_TOLERANCE", 789.0)
    assert v2._campaign_context.TARGET_QUANTITY_TOLERANCE == 789.0
    with pytest.raises(AttributeError):
        mechanics.Context({}).missing_dependency


def test_wrapper_supplies_original_defaults_and_live_context(monkeypatch):
    seen = []
    monkeypatch.setattr(
        mechanics,
        "select_unique_reference_shipment",
        lambda **kwargs: seen.append(kwargs) or {"sentinel": True},
    )
    lane = object()
    assert v2.select_unique_reference_shipment([], lane=lane) == {"sentinel": True}
    assert v4.select_unique_reference_shipment([], lane=lane) == {"sentinel": True}
    assert seen[0]["context"] is v2._campaign_context
    assert seen[1]["context"] is v4._campaign_context
    assert {k: v for k, v in seen[0].items() if k != "context"} == {
        k: v for k, v in seen[1].items() if k != "context"
    }


@pytest.fixture
def reviewed_sources(tmp_path, monkeypatch):
    root = tmp_path / "sources"
    root.mkdir()
    source = root / "core.py"
    source.write_bytes(b"reviewed source\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    ledger = root / "revision.json"
    ledger.write_text(
        json.dumps(
            {
                "schema": "supplier-campaign-source-revision.v1",
                "revision": "fixture-v1",
                "files": {
                    "core.py": {"sha256": digest, "historical_sha256": ["a" * 64]}
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(revision, "ROOT", root)
    monkeypatch.setattr(revision, "LEDGER", ledger)
    return root, source, ledger, digest


def test_reviewed_replacement_is_explicit_and_manifest_is_bound(reviewed_sources):
    _, source, _, digest = reviewed_sources
    current = revision.current_revision()
    assert revision.accepts_current_revision(source, "a" * 64, digest)
    assert not revision.accepts_current_revision(source, "b" * 64, digest)
    assert not revision.accepts_current_revision(source, "a" * 64, "0" * 64)
    revision.require_manifest_revision({"source_revision": current})
    with pytest.raises(ValueError, match="plan a new campaign"):
        revision.require_manifest_revision({})
    with pytest.raises(ValueError, match="plan a new campaign"):
        revision.require_manifest_revision({"source_revision": {"revision": "old"}})


@pytest.mark.parametrize("mutation", ["modified", "missing", "other_path", "ledger"])
def test_changed_dependency_or_ledger_cannot_reuse_receipt(reviewed_sources, mutation):
    root, source, ledger, digest = reviewed_sources
    manifest = {"source_revision": revision.current_revision()}
    if mutation == "modified":
        source.write_bytes(b"changed source!\n")
    elif mutation == "missing":
        source.unlink()
    elif mutation == "other_path":
        outside = root.parent / "core.py"
        outside.write_bytes(source.read_bytes())
        assert not revision.accepts_current_revision(outside, "a" * 64, digest)
        return
    else:
        payload = json.loads(ledger.read_text(encoding="utf-8"))
        payload["revision"] = "fixture-v2"
        ledger.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        revision.require_manifest_revision(manifest)
    if mutation != "ledger":
        assert not revision.accepts_current_revision(source, "a" * 64, digest)


@pytest.mark.parametrize("name", ["../core.py", "C:core.py", "sub\\core.py"])
def test_source_ledger_rejects_escaping_paths(reviewed_sources, name):
    _, _, ledger, digest = reviewed_sources
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["files"] = {name: {"sha256": digest}}
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="path"):
        revision.current_revision()


@pytest.mark.parametrize("prefix", ["", "launch_", "finalize_"])
@pytest.mark.parametrize("version", [5, 6, 7, 8])
def test_current_adapter_chain_uses_reviewed_revision(prefix, version):
    if prefix == "launch_" or (prefix == "finalize_" and version < 8):
        from etudecas.prototypes.scan_2027_risk_control import supplier_campaign_adapters
        module = supplier_campaign_adapters.PROFILES[(prefix[:-1], f"v{version}")]
    else:
        module = importlib.import_module(
            "etudecas.prototypes.scan_2027_risk_control."
            f"{prefix}supplier_operating_point_full_campaign_v{version}"
        )
    assert module.validate_frozen_implementation().is_file()


def test_changed_shared_mechanics_rejects_entire_adapter_chain(monkeypatch):
    real_read_bytes = Path.read_bytes
    shared = Path(mechanics.__file__).resolve()

    def changed_read_bytes(path):
        data = real_read_bytes(path)
        return data + b"# modified\n" if path.resolve() == shared else data

    monkeypatch.setattr(Path, "read_bytes", changed_read_bytes)
    module = importlib.import_module(
        "etudecas.prototypes.scan_2027_risk_control.supplier_operating_point_full_campaign_v8"
    )
    with pytest.raises(RuntimeError):
        module.validate_frozen_implementation()


@pytest.mark.parametrize("version", [2, 4])
def test_current_launcher_refuses_old_manifest_without_source_revision(version):
    launcher = importlib.import_module(
        "etudecas.prototypes.scan_2027_risk_control."
        f"launch_supplier_operating_point_full_campaign_v{version}"
    )
    runner = v2 if version == 2 else v4
    with pytest.raises(ValueError, match="plan a new campaign"):
        launcher._verify_signed_design({"runner": runner.__file__})


@pytest.mark.parametrize("mode,version", [("launch", 5), ("launch", 6), ("launch", 7), ("launch", 8), ("finalize", 5), ("finalize", 6), ("finalize", 7)])
def test_explicit_adapter_profile_restores_every_binding_after_failure(mode, version):
    from etudecas.prototypes.scan_2027_risk_control import supplier_campaign_adapters as adapters
    profile = adapters.PROFILES[(mode, f"v{version}")]
    names = profile.bindings()
    original = {key: getattr(profile.implementation_v4, key) for key in names}
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with profile.patched_context():
            for key, value in names.items():
                assert getattr(profile.implementation_v4, key) == value
            raise RuntimeError("synthetic failure")
    for key, value in original.items():
        assert getattr(profile.implementation_v4, key) is value


def test_adapter_relocation_is_explicit_and_does_not_translate_foreign_modules(tmp_path):
    from etudecas.prototypes.scan_2027_risk_control import supplier_campaign_adapters as adapters
    for name, (mode, version) in revision.ADAPTER_PROFILES.items():
        assert revision.module_argv(f"etudecas.prototypes.scan_2027_risk_control.{name}") == [adapters.MODULE_NAME, mode, version]
        assert revision.resolve_current_source(revision.ROOT / f"{name}.py") == Path(adapters.__file__)
        assert not (revision.ROOT / f"{name}.py").exists()
        assert revision.resolve_current_source(tmp_path / f"{name}.py") == (tmp_path / f"{name}.py").resolve()
        assert revision.module_argv(f"foreign.{name}") == [f"foreign.{name}"]


def test_all_explicit_profiles_refuse_changed_dispatcher(monkeypatch):
    from etudecas.prototypes.scan_2027_risk_control import supplier_campaign_adapters as adapters
    original = Path.read_bytes
    target = Path(adapters.__file__).resolve()
    def mutated(path):
        value = original(path)
        return value + b"# mutation\n" if path.resolve() == target else value
    monkeypatch.setattr(Path, "read_bytes", mutated)
    for profile in adapters.PROFILES.values():
        with pytest.raises(RuntimeError):
            profile.validate_frozen_implementation()


def test_v8_detached_command_returns_to_its_explicit_profile(tmp_path):
    from types import SimpleNamespace
    from etudecas.prototypes.scan_2027_risk_control import supplier_campaign_adapters as adapters
    profile = adapters.launch_v8
    args = SimpleNamespace(campaign_root=tmp_path, runner=profile.RUNNER, parallel_shards=2,
                           workers_per_shard=3, poll_seconds=4, reuse_evidence_dir=[tmp_path / "evidence"])
    command = profile._v8_detached_command(args)
    assert command[1:5] == ["-m", adapters.MODULE_NAME, "launch", "v8"]
    assert command[5:] == ["--campaign-root", str(tmp_path.resolve()), "--runner", str(profile.RUNNER.resolve()),
                          "--parallel-shards", "2", "--workers-per-shard", "3", "--poll-seconds", "4",
                          "--detached-child", "--reuse-evidence-dir", str((tmp_path / "evidence").resolve())]


# These three regressions append to test_supplier_campaign_mechanics.py.
# Its existing reviewed_sources fixture remains the only source fixture.


def test_revision_rereads_changed_bytes_even_with_same_size_and_mtime(reviewed_sources):
    _, source, _, _ = reviewed_sources
    revision.current_revision()
    original = source.read_bytes()
    prior_stat = source.stat()
    source.write_bytes(original[:-1] + b"!")
    os.utime(source, ns=(prior_stat.st_atime_ns, prior_stat.st_mtime_ns))
    assert source.stat().st_size == prior_stat.st_size
    assert source.stat().st_mtime_ns == prior_stat.st_mtime_ns
    with pytest.raises(ValueError, match="Campaign source revision changed: core.py"):
        revision.current_revision()


def test_revision_reports_first_ledger_error_when_later_read_finishes_first(
    reviewed_sources, monkeypatch
):
    root, source, ledger, _ = reviewed_sources
    second = root / "second.py"
    second.write_bytes(b"second source\n")
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["files"] = {
        source.name: {"sha256": "0" * 64},
        second.name: {"sha256": "0" * 64},
    }
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    second_read = Event()
    completed_reads = []
    original_read = Path.read_bytes

    def read_with_reversed_completion(path):
        data = original_read(path)
        if path == source:
            assert second_read.wait(5), "Second dependency read did not complete"
            completed_reads.append(source.name)
        elif path == second:
            completed_reads.append(second.name)
            second_read.set()
        return data

    monkeypatch.setattr(Path, "read_bytes", read_with_reversed_completion)
    with pytest.raises(ValueError, match="Campaign source revision changed: core.py"):
        revision.current_revision()
    assert completed_reads == [second.name, source.name]


def test_revision_checks_secondary_dependency_in_complete_graph(reviewed_sources):
    root, source, ledger, digest = reviewed_sources
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    secondary = None
    for index in range(31):
        secondary = root / f"dependency_{index:02d}.py"
        raw = f"source {index}\n".encode("utf-8")
        secondary.write_bytes(raw)
        payload["files"][secondary.name] = {"sha256": hashlib.sha256(raw).hexdigest()}
    payload["retired_modules"] = {"retired.py": {"historical_sha256": ["b" * 64]}}
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    assert revision.current_revision() == {
        "revision": payload["revision"],
        "ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest(),
        "files": payload["files"],
        "retired_modules": payload["retired_modules"],
    }
    assert secondary is not None
    secondary.write_bytes(b"changed secondary\n")
    with pytest.raises(ValueError, match="Campaign source revision changed: dependency_30.py"):
        revision.current_revision()
    assert not revision.accepts_current_revision(source, "a" * 64, digest)


# The tests below use data held in memory only. Run their exact node IDs;
# the historical integrity fixtures above are excluded after the Sophos incident.
def _memory_campaign_rows(*, client="C-XXXXX", factories=None):
    factories = factories or {"268091": "M-1810", "268967": "M-1430"}
    observations = (
        ("268091", 0, 10, 10, 8, 2, 7),
        ("268091", 1, 10, 12, 11, 1, 9),
        ("268967", 0, 20, 20, 20, 0, 20),
        ("268967", 1, 20, 20, 18, 2, 18),
    )
    service = [
        {"node_id": client, "item_id": f"item:{product}", "day": day,
         "demand_qty": demand, "required_with_backlog_qty": required,
         "served_qty": served, "backlog_end_qty": backlog}
        for product, day, demand, required, served, backlog, _ in observations
    ]
    production = [
        {"node_id": factories[product], "item_id": f"item:{product}",
         "day": day, "released_qty": released}
        for product, day, _, _, _, _, released in observations
    ]
    return service, production


# Manual oracle: 268091 serves 8 + 9 current-demand units; its two older
# backlog units served on day 1 must not be counted again as on-time service.
_MEMORY_TWO_DAY_METRICS = {
    "start_day": 0, "end_day": 1, "day_count": 2, "fully_observed": True,
    "demand_qty_268091": 20, "demand_qty_268967": 40, "demand_qty_global": 60,
    "on_due_qty_268091": 17, "on_due_qty_268967": 38, "on_due_qty_global": 55,
    "service_268091_pct": 85, "service_268967_pct": 95,
    "service_global_pct": 91.66666666666667,
    "backlog_qty_days_268091": 3, "backlog_qty_days_268967": 2,
    "max_backlog_qty_268091": 2, "max_backlog_qty_268967": 2,
    "backlog_qty_days_global": 5, "backlog_day_count_global": 2,
    "max_backlog_qty_global": 3, "ending_backlog_qty_global": 3,
    "production_released_268091_qty": 16, "production_released_268967_qty": 38,
}


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_horizons_accept_complete_rows_without_changing_them(runner):
    service, production = _memory_campaign_rows()
    before = ([dict(row) for row in service], [dict(row) for row in production])
    assert runner._validate_client_service_horizon(service, days=2) is None
    assert runner._validate_production_horizon(production, days=2) is None
    assert (service, production) == before


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_window_metrics_match_manual_two_day_oracle(runner):
    service, production = _memory_campaign_rows()
    result = runner._window_metrics(
        service_rows=service, production_rows=production, start_day=0, end_day=1
    )
    assert result["fully_observed"] is True
    assert result == pytest.approx(_MEMORY_TWO_DAY_METRICS)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_window_metrics_day_one_keeps_starting_backlog(runner):
    service, production = _memory_campaign_rows()
    expected = {
        "start_day": 1, "end_day": 1, "day_count": 1, "fully_observed": True,
        "demand_qty_268091": 10, "demand_qty_268967": 20, "demand_qty_global": 30,
        "on_due_qty_268091": 9, "on_due_qty_268967": 18, "on_due_qty_global": 27,
        "service_268091_pct": 90, "service_268967_pct": 90, "service_global_pct": 90,
        "backlog_qty_days_268091": 1, "backlog_qty_days_268967": 2,
        "max_backlog_qty_268091": 1, "max_backlog_qty_268967": 2,
        "backlog_qty_days_global": 3, "backlog_day_count_global": 1,
        "max_backlog_qty_global": 3, "ending_backlog_qty_global": 3,
        "production_released_268091_qty": 9, "production_released_268967_qty": 18,
    }
    result = runner._window_metrics(
        service_rows=service, production_rows=production, start_day=1, end_day=1
    )
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_window_metrics_zero_demand_has_full_service(runner):
    service, production = _memory_campaign_rows()
    for row in service:
        row.update(demand_qty=0, required_with_backlog_qty=0, served_qty=0, backlog_end_qty=0)
    for row in production:
        row["released_qty"] = 0
    expected = dict.fromkeys(_MEMORY_TWO_DAY_METRICS, 0)
    expected.update(start_day=0, end_day=1, day_count=2, fully_observed=True,
                    service_268091_pct=100, service_268967_pct=100, service_global_pct=100)
    runner._validate_client_service_horizon(service, days=2)
    runner._validate_production_horizon(production, days=2)
    assert runner._window_metrics(
        service_rows=service, production_rows=production, start_day=0, end_day=1
    ) == pytest.approx(expected)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_metrics_ignore_other_clients_products_and_factories(runner):
    service, production = _memory_campaign_rows()
    service += [dict(service[0], node_id="other-client", demand_qty=999),
                dict(service[0], item_id="item:other-product", demand_qty=999)]
    production += [dict(production[0], node_id="other-factory", released_qty=999),
                   dict(production[0], item_id="item:other-product", released_qty=999)]
    runner._validate_client_service_horizon(service, days=2)
    runner._validate_production_horizon(production, days=2)
    assert runner._window_metrics(
        service_rows=service, production_rows=production, start_day=0, end_day=1
    ) == pytest.approx(_MEMORY_TWO_DAY_METRICS)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
@pytest.mark.parametrize("field", ["demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"])
@pytest.mark.parametrize("value", [-1, None, float("nan"), float("inf")],
                         ids=["negative", "missing-value", "nan", "infinity"])
def test_memory_service_horizon_rejects_invalid_quantities(runner, field, value):
    service, _ = _memory_campaign_rows()
    service[0][field] = value
    with pytest.raises(ValueError, match=f"Invalid {field}"):
        runner._validate_client_service_horizon(service, days=2)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_service_horizon_rejects_required_below_demand(runner):
    service, _ = _memory_campaign_rows()
    service[0]["required_with_backlog_qty"] = 9
    with pytest.raises(ValueError, match="Required quantity below current demand"):
        runner._validate_client_service_horizon(service, days=2)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
@pytest.mark.parametrize("case", ["duplicate", "absent-row", "out-of-range-day",
                                 "invalid-day", "other-node", "other-product"])
@pytest.mark.parametrize("kind", ["service", "production"])
def test_memory_horizons_reject_invalid_row_matrices(runner, case, kind):
    service, production = _memory_campaign_rows()
    rows = service if kind == "service" else production
    if case == "duplicate":
        rows.append(dict(rows[0]))
    elif case == "absent-row":
        rows.pop()
    else:
        field, value = {"out-of-range-day": ("day", 2), "invalid-day": ("day", "bad"),
                        "other-node": ("node_id", "other-node"),
                        "other-product": ("item_id", "item:other-product")}[case]
        rows[0][field] = value
    validate = (runner._validate_client_service_horizon if kind == "service"
                else runner._validate_production_horizon)
    with pytest.raises(ValueError, match="Duplicate|matrix|production horizon"):
        validate(rows, days=2)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
@pytest.mark.parametrize("case", ["negative-start", "reversed-window", "service-absent",
                                 "service-duplicate", "production-absent", "production-duplicate"])
def test_memory_window_metrics_reject_invalid_windows(runner, case):
    service, production = _memory_campaign_rows()
    start, end = 0, 1
    if case == "negative-start":
        start = -1
    elif case == "reversed-window":
        start, end = 1, 0
    else:
        rows = service if case.startswith("service") else production
        if case.endswith("absent"):
            rows.pop()
        else:
            rows.append(dict(rows[0]))
    with pytest.raises(ValueError, match="outside the simulated horizon|Incomplete .* impact window"):
        runner._window_metrics(
            service_rows=service, production_rows=production, start_day=start, end_day=end
        )


def test_memory_metrics_use_each_versions_live_client_and_factories(monkeypatch):
    for runner, label in ((v2, "v2"), (v4, "v4")):
        monkeypatch.setattr(runner, "protocol", SimpleNamespace(CLIENT_NODE_ID=f"client-{label}"))
        monkeypatch.setattr(runner, "PRODUCT_FACTORY",
                            {"268091": f"factory-{label}-a", "268967": f"factory-{label}-b"})
    for runner, other, label in ((v2, v4, "v2"), (v4, v2, "v4")):
        service, production = _memory_campaign_rows(
            client=f"client-{label}",
            factories={"268091": f"factory-{label}-a", "268967": f"factory-{label}-b"},
        )
        runner._validate_client_service_horizon(service, days=2)
        runner._validate_production_horizon(production, days=2)
        assert runner._window_metrics(
            service_rows=service, production_rows=production, start_day=0, end_day=1
        ) == pytest.approx(_MEMORY_TWO_DAY_METRICS)
        with pytest.raises(ValueError, match="matrix"):
            other._validate_client_service_horizon(service, days=2)
        with pytest.raises(ValueError, match="production horizon"):
            other._validate_production_horizon(production, days=2)
        with pytest.raises(ValueError, match="Incomplete service impact window"):
            other._window_metrics(
                service_rows=service, production_rows=production, start_day=0, end_day=1
            )


def test_memory_service_horizon_reads_version_specific_products_live(monkeypatch):
    service, _ = _memory_campaign_rows()
    for product in ("268091", "268967"):
        monkeypatch.setattr(v2, "TARGET_PRODUCTS", (product,))
        selected = [row for row in service if row["item_id"] == f"item:{product}"]
        assert v2._validate_client_service_horizon(selected, days=2) is None
        with pytest.raises(ValueError, match="matrix"):
            v4._validate_client_service_horizon(selected, days=2)


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_holdout_contract_keeps_business_thresholds(runner, monkeypatch):
    monkeypatch.setattr(runner, "SEEDS", (7, 11))
    monkeypatch.setattr(runner, "STATE_EVALUATION_DAYS", 10)
    contract = runner._required_campaign_holdout_contract()
    assert (contract["fixed_point_count"], contract["seed_count"],
            contract["baseline_case_count"]) == (3, 2, 6)
    assert contract["seeds"] == [7, 11]
    assert contract["service_window"] == {"start_day": 0, "end_day": 9, "day_count": 10}
    assert contract["op100_minimum_global_and_each_product"] == 0.985
    assert contract["op93_global_pooled_and_median_band"] == [0.915, 0.945]
    assert contract["op80_global_pooled_and_median_band"] == [0.785, 0.815]
    assert contract["degraded_product_strictly_below"] == 0.995
    assert contract["same_seed_joint_strict_order_required"] == 24
    assert contract["retuning_after_holdout"] is False


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_lane_quantities_count_shipped_and_exact_lane_only(runner, monkeypatch):
    lane = runner.Lane("lane-a", "supplier", "item:A", "factory", "edge-a", "item:PF", 2)
    base = dict(src_node_id="supplier", item_id="item:A", dst_node_id="factory",
                edge_id="edge-a", risk_decision_day=1, pulled_qty=20, shipped_qty=4,
                shipment_id="ship-a")
    rows = [base, dict(base, shipment_id="ship-b", shipped_qty=6),
            dict(base, risk_decision_day=3, shipped_qty=2)]
    rows += [dict(base, **{key: value}) for key, value in (
        ("src_node_id", "elsewhere"), ("item_id", "item:B"),
        ("dst_node_id", "other-factory"), ("edge_id", "edge-b"),
        ("risk_decision_day", -1), ("pulled_qty", 0), ("shipped_qty", 0),
        ("shipment_id", " "),
    )]
    snapshot = [dict(row) for row in rows]
    monkeypatch.setattr(runner, "STATE_EVALUATION_DAYS", 3)
    assert runner._lane_day_quantity_map(rows, lane=lane) == {1: 10}
    monkeypatch.setattr(runner, "STATE_EVALUATION_DAYS", 4)
    assert runner._lane_day_quantity_map(rows, lane=lane) == {1: 10, 3: 2}
    assert rows == snapshot


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
@pytest.mark.parametrize("arrivals, expected", [
    ((12, 17), (10, 21, 40, 23, 11, True)),
    ((47,), (10, 51, 52, 5, 0, False)),
    ((), (8, 27, 40, 0, 0, False)),
], ids=["within-impact-window", "late-arrival-extends-horizon", "no-exposure"])
def test_memory_incident_horizon_matches_arrival_and_recovery_days(runner, monkeypatch, arrivals, expected):
    monkeypatch.setattr(runner, "MINIMUM_CASE_DAYS", 40)
    monkeypatch.setattr(runner, "MIN_RECOVERY_OBSERVATION_DAYS", 5)
    target = dict(impact_window_start_day=8, impact_window_end_day=27, target_arrival_day=10)
    result = runner._incident_horizon_from_trace(
        target=target, tagged_rows=[{"arrival_day": day} for day in arrivals]
    )
    fields = ("causal_window_start_day", "causal_window_end_day", "required_simulation_days",
              "recovery_observation_days_after_latest_stressed_arrival",
              "recovery_observation_days_within_impact_window", "recovery_fully_observed_within_360")
    assert tuple(result[field] for field in fields) == expected
    assert result["impact_window_days"] == 20
    assert result["causal_window_days"] == expected[1] - expected[0] + 1
    assert result["causal_window_defined"] is bool(arrivals)
    with pytest.raises(ValueError, match="lacks an arrival day"):
        runner._incident_horizon_from_trace(target=target, tagged_rows=[{"arrival_day": -1}])


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
def test_memory_shipment_signature_uses_ordered_projection(runner):
    # The expected transcript is written explicitly: other columns and day 2 are outside it.
    first = dict(shipment_id="A", risk_decision_day=0, risk_event_ids="",
                 src_node_id="S", dst_node_id="M", item_id="item:A", edge_id="e",
                 pulled_qty=10, shipped_qty=8, lead_days=2, arrival_day=2, reliability=0.8)
    second = dict(first, shipment_id="B", risk_decision_day=1, arrival_day=3)
    expected = hashlib.sha256(json.dumps(
        [first, second], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    rows = [dict(second, ignored_report_label="label"), first,
            dict(first, risk_decision_day=2), dict(first, risk_decision_day=-1)]
    assert runner._shipment_trace_signature(rows, end_day_exclusive=2) == expected


@pytest.mark.parametrize("runner", [v2, v4], ids=["v2", "v4"])
@pytest.mark.parametrize("field, value", [
    (None, None), ("campaign_signature", "another-campaign"),
    ("case_key", "another-case"), ("quality_branch_included", True),
    ("availability_incident_included", True),
    ("supplier_state_dependent_risks_enabled", True), ("status", "unknown"),
], ids=["valid", "wrong-campaign", "wrong-case", "quality", "availability", "state-risk", "status"])
def test_memory_evidence_validates_semantics_beyond_signature(runner, field, value):
    evidence = dict(schema_version=runner.CASE_SCHEMA_VERSION, campaign_signature="campaign",
                    engine_sha256="engine", case_key="case", case_signature="signature",
                    quality_branch_included=False, availability_incident_included=False,
                    supplier_state_dependent_risks_enabled=False, status="valid")
    if field is not None:
        evidence[field] = value
    evidence["evidence_signature"] = hashlib.sha256(json.dumps(
        evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    kwargs = dict(manifest={"campaign_signature": "campaign", "engine_sha256": "engine"},
                  case_key="case", case_signature="signature")
    if field is None:
        assert runner._validate_evidence(evidence, **kwargs) is None
    else:
        with pytest.raises(ValueError, match=field):
            runner._validate_evidence(evidence, **kwargs)
