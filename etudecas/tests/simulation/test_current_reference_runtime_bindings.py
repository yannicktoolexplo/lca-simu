"""Run the real reference adapter against memory-only runtime collaborators.

CSV evidence is written once into fresh pytest temporary directories. No source
file, timestamp, prior result or disappearance/integrity scenario is modified.
The engine module is already imported, reproducing the cached import path.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import sys

import pytest

from etudecas.simulation import current_reference as reference
from etudecas.simulation.engine import mrp_planning as planning
from etudecas.simulation.engine import run_first_simulation as engine


@pytest.fixture
def runtime(monkeypatch):
    state = SimpleNamespace(trackers=[], planners=[], weekly=[], calls=[],
        imports=[], fail_at=None, label=None, pair=None)

    class OriginalObserved:
        def merge_due(self, day, estimated_due):
            return {"base_day": day, "base_due": estimated_due}

        def provenance(self, identity, forecast_calendar):
            return {"source": "original"}

        def day_audit(self, pair, day):
            return {"day": day}

    class StaleEngineObserved(OriginalObserved):
        pass

    def original_reconcile(*args, **kwargs):
        return {"base": args[0]}

    def stale_engine_reconcile(*args, **kwargs):
        return {"stale": args[0]}

    original_consume = lambda ledger, **kwargs: [{"lot_id": "physical-parent", "qty": kwargs["qty"]}]
    monkeypatch.setattr(planning, "ObservedExternalComponentExecution", OriginalObserved)
    monkeypatch.setattr(planning, "reconcile_industrial_requirements", original_reconcile)
    monkeypatch.setattr(engine, "ObservedExternalComponentExecution", StaleEngineObserved)
    monkeypatch.setattr(engine, "reconcile_industrial_requirements", stale_engine_reconcile)
    monkeypatch.setattr(engine.LotLedger, "consume", original_consume)

    e4 = SimpleNamespace(WINDOW_FIELDS=["node_id", "item_id", "uom"])

    class ScopedReconciliation:
        def __init__(self, original):
            self.original, self.windows = original, {}
            self.targets = set(e4.TARGETS)
            state.planners.append(self)

        def reconcile(self, *args, **kwargs):
            return {"targets": self.targets, "original": self.original(*args, **kwargs)}

    e4.ScopedReconciliation = ScopedReconciliation
    f3 = SimpleNamespace(e4_module=lambda: e4)

    class Tracker:
        def __init__(self, payload):
            self.label, self.pair = payload["label"], tuple(payload["pair"])
            self.budgets = [dict(budget_id=self.label, closing_day=0,
                node_id=self.pair[0], item_id=self.pair[1])]
            self.published, self.provenance, self.allocations = {}, {}, []
            self.cumulative_audit, self.closed, self.withdrawals, self.served_rows = [], [], [], []

        def close(self, day, estimated_due):
            self.closed.append((day, deepcopy(estimated_due)))
            self.published[self.label] = dict(self.budgets[0],
                residual_requested_qty=20, residual_executed_on_closing_day_qty=7)
            return {"tracker": self.label, "known_due": estimated_due}

        def own_withdrawal(self, **kwargs):
            self.withdrawals.append(kwargs)

        def served(self, day, identity, quantity):
            self.served_rows.append((day, identity, quantity))

    def tracker_for(_f3, payload, cumulative, mode):
        tracker = Tracker(payload)
        state.trackers.append(tracker)
        return tracker

    adapter = SimpleNamespace(f3_module=lambda: f3, tracker_for=tracker_for)

    class Weekly:
        def __init__(self):
            self.restored, self.evidence_written = False, False

        def restore(self):
            self.restored = True

        def write_evidence(self, output):
            self.evidence_written = True

    def install(_engine, graph, protocol):
        weekly = Weekly()
        state.weekly.append(weekly)
        return weekly

    real_import = reference.importlib.import_module

    def runtime_import(name, *args, **kwargs):
        if name == "memory_reference_adapter":
            return adapter
        if name == "memory_weekly_plugin":
            return SimpleNamespace(install=install)
        if name == "etudecas.simulation.engine.run_first_simulation":
            state.imports.append((planning.ObservedExternalComponentExecution,
                                  planning.reconcile_industrial_requirements))
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(reference.importlib, "import_module", runtime_import)

    def main():
        state.calls.append(dict(label=state.label, observed=engine.ObservedExternalComponentExecution,
            reconcile=engine.reconcile_industrial_requirements, argv=sys.argv))
        if state.fail_at == "before_callbacks":
            raise RuntimeError("expected engine failure")
        result = engine.reconcile_industrial_requirements(state.label)
        state.calls[-1]["reconciled"] = result
        ledger = SimpleNamespace(enabled=True)
        engine.LotLedger.consume(ledger, node_id=state.pair[0], item_id=state.pair[1],
            day=0, event_type="production_consume", qty=12)
        engine.LotLedger.consume(ledger, node_id=state.pair[0], item_id=state.pair[1],
            day=0, event_type="external_component_consume", source_id="residual", qty=7)
        state.calls[-1]["merged"] = engine.ObservedExternalComponentExecution().merge_due(0, {"needed": 20})
        if state.fail_at == "after_callbacks":
            raise RuntimeError("expected engine failure")

    monkeypatch.setattr(engine, "main", main)
    state.originals = (OriginalObserved, original_reconcile,
        StaleEngineObserved, stale_engine_reconcile, original_consume, sys.argv)
    return state


def _run(runtime, tmp_path, label):
    pair = (f"factory-{label}", "item:PF")
    runtime.label, runtime.pair = label, pair
    graph = {"meta": {"formats_reconciled_weekly_budgets": {"label": label, "pair": pair}},
        "nodes": [{"id": pair[0], "inventory": {"states": [{"item_id": pair[1], "uom": "UN"}]}}]}
    protocol = {"cumulative_residual_pairs": [], "forecast_reconciliation_pairs": [list(pair)]}
    output = tmp_path / label
    (output / "data").mkdir(parents=True)
    result = reference.run_engine(graph, protocol,
        {"adapter_module": "memory_reference_adapter", "weekly_plugin_module": "memory_weekly_plugin"},
        None, ["--memory", label], output, 2)
    return result


def _assert_restored(runtime):
    planning_observed, planning_reconcile, engine_observed, engine_reconcile, consume, argv = runtime.originals
    assert planning.ObservedExternalComponentExecution is planning_observed
    assert planning.reconcile_industrial_requirements is planning_reconcile
    assert engine.ObservedExternalComponentExecution is engine_observed
    assert engine.reconcile_industrial_requirements is engine_reconcile
    assert engine.LotLedger.consume is consume and sys.argv is argv
    assert runtime.weekly[-1].restored


def test_cached_engine_uses_runtime_F3_and_E4_and_closes_the_budget(runtime, tmp_path):
    result = _run(runtime, tmp_path, "first")
    call, tracker = runtime.calls[0], runtime.trackers[0]
    assert call["merged"] == {"tracker": "first", "known_due": {"base_day": 0, "base_due": {"needed": 20}}}
    assert call["reconciled"] == {"targets": {runtime.pair}, "original": {"base": "first"}}
    assert call["observed"] is not runtime.originals[2]
    assert tracker.closed == [(0, {"base_day": 0, "base_due": {"needed": 20}})]
    assert tracker.withdrawals == [dict(day=0, node_id=runtime.pair[0], item_id=runtime.pair[1],
        qty=12.0, event_type="production_consume")]
    assert tracker.served_rows == [(0, "residual", 7.0)] and result["historical_F3_budgets"] == 1
    assert runtime.weekly[0].evidence_written
    _assert_restored(runtime)


def test_two_calls_have_separate_runtime_classes_trackers_and_reconciliation_contexts(runtime, tmp_path):
    first = _run(runtime, tmp_path, "first")
    _assert_restored(runtime)
    first_published = deepcopy(runtime.trackers[0].published)
    second = _run(runtime, tmp_path, "second")
    _assert_restored(runtime)
    assert first["historical_F3_budgets"] == second["historical_F3_budgets"] == 1
    assert runtime.calls[0]["observed"] is not runtime.calls[1]["observed"]
    assert runtime.calls[0]["merged"]["tracker"] == "first"
    assert runtime.calls[1]["merged"]["tracker"] == "second"
    assert runtime.calls[0]["reconciled"]["targets"] == {("factory-first", "item:PF")}
    assert runtime.calls[1]["reconciled"]["targets"] == {("factory-second", "item:PF")}
    assert runtime.trackers[0].published == first_published
    assert runtime.calls[0]["argv"][-1] == "first" and runtime.calls[1]["argv"][-1] == "second"


@pytest.mark.parametrize("failure", ["before_callbacks", "after_callbacks"])
def test_main_failure_restores_engine_aliases_planning_consume_weekly_and_argv(runtime, tmp_path, failure):
    runtime.fail_at = failure
    with pytest.raises(RuntimeError, match="expected engine failure"):
        _run(runtime, tmp_path, "failure")
    _assert_restored(runtime)
    assert not runtime.weekly[-1].evidence_written
    assert runtime.calls[0]["observed"] is not runtime.originals[2]
    assert runtime.calls[0]["reconcile"] is not runtime.originals[3]


def test_engine_is_imported_before_planning_is_patched(runtime, tmp_path):
    _run(runtime, tmp_path, "order")
    assert runtime.imports == [(runtime.originals[0], runtime.originals[1])]
    _assert_restored(runtime)
