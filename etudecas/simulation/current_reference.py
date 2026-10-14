"""Run retained W, with an explicit nominal prospective extension after 2025.

Historical execution retains the frozen F3/E4/W implementations. Future other
uses are an exogenous scenario, fixed from W's requested quantities; shortages
or future production cannot reduce that demand. Nothing here changes a workbook.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import gzip
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "etudecas/config/mrp_reference_20261013.json"
ORIGIN = date(2025, 1, 1)
FIRST = 362
SEASON = 364
MODE = "retained_W_historical_then_synthetic_v1"
FORECAST_MODES = ("source_priority", "coherent_scenario")
SCENARIO_KNOWN_DAY = 365  # 1 January 2026: never visible to a 2025 decision.
SCENARIO_FIRST_DAY = 369  # 5 January: first complete future Monday week.


def read(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def validate_projection_contract(meta, days):
    """The engine's annual managed-stock guard accepts only this full contract."""
    value = meta.get("current_reference_projection")
    if value is None:
        return False
    future = read(CONFIG)["future"]
    if (future["annual_growth"] != .05 or future["season_days"] != SEASON
            or future["historical_days"] != FIRST or future["first_synthetic_day"] != FIRST
            or future["planning_horizon_days"] != 364 or future["mode"] != MODE):
        raise ValueError("Configuration differs from implemented prospective equations")
    expected = dict(projection_contract(read(CONFIG), value.get("forecast_mode", "source_priority")),
                    schema_version=1, scenario_id="scn:BASE", days=days)
    if value != expected or type(days) is not int or not FIRST < days <= 1825:
        raise ValueError("Invalid retained-W prospective nominal contract")
    return True


def projection_contract(config, forecast_mode):
    """Keep the delivered source-priority contract byte-for-byte representable."""
    if forecast_mode not in FORECAST_MODES:
        raise ValueError("Unknown prospective forecast mode")
    result = dict(config["future"])
    if forecast_mode == "coherent_scenario":
        candidate = config["forecast_candidates"][forecast_mode]
        if candidate != dict(known_day=SCENARIO_KNOWN_DAY, first_target_day=SCENARIO_FIRST_DAY,
                customer_forecast="same_synthetic_customer_week_as_executed_orders",
                other_use_forecast="same_fixed_W_requested_profile_as_executed_other_uses",
                industrial_total="source_I_not_substituted_for_BOM_plus_other_uses_after_cutover",
                status="explicit_candidate_not_industrial_observation"):
            raise ValueError("Candidate forecast contract differs from implemented equations")
        result.update(forecast_mode=forecast_mode, forecast="coherent_scenario_after_2025", **candidate)
    return result


def season_day(day):
    """52 Monday weeks anchored to 30 December 2024; no weekday drift."""
    cycle, position = divmod(day + 2, SEASON)
    return cycle, position - 2


def grown(quantity, cycle, unit):
    value = Decimal(str(quantity)) * Decimal("1.05") ** cycle
    return int(value.to_integral_value(rounding=ROUND_FLOOR)) if unit == "UN" else float(value)


class FrozenOtherUses:
    """Requested (not served) W quantities, fixed before any prospective run."""

    def __init__(self, path):
        if isinstance(path, dict):
            if path.get("schema_version") != 1 or path.get("quantity") != "W_requested_weekly_not_served":
                raise ValueError("Invalid fixed prospective other-use profile")
            self.units, self.weekly = {}, {}
            for row in path["rows"]:
                pair = row["node_id"], row["item_id"]
                key = pair, row["period_start_day"]
                qty = Decimal(row["qty"])
                if key in self.weekly or qty < 0 or not qty.is_finite():
                    raise ValueError("Invalid or duplicate prospective other-use week")
                self.units[pair], self.weekly[key] = row["uom"], qty
            self.path, self.source_sha256 = path["source_file"], path["source_sha256"]
            return
        weekly = defaultdict(Decimal)
        self.units = {}
        opener = gzip.open if Path(path).suffix == ".gz" else open
        with opener(path, mode="rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                day = int(row["day"])
                if not 0 <= day < FIRST:
                    raise ValueError("The exogenous profile must come from exactly W year one")
                pair = row["node_id"], row["item_id"]
                self.units[pair] = row["uom"]
                start = day - (ORIGIN + timedelta(days=day)).weekday()
                amount = Decimal(row["demand_qty"])
                if amount < 0 or not amount.is_finite():
                    raise ValueError("Invalid frozen requested quantity")
                weekly[pair, start] += amount
        self.weekly = {}
        for (pair, start), total in weekly.items():
            # Only the future copy of the opening five-day fragment is normalized.
            self.weekly[pair, start] = total * 7 / 5 if start == -2 else total
        self.path = rel(path)
        self.source_sha256 = sha(path)

    def payload(self):
        return dict(schema_version=1, quantity="W_requested_weekly_not_served", source_file=self.path,
            source_sha256=self.source_sha256,
            first_partial_week="Only future copy of W day0..4 normalized by7/5",
            rows=[dict(node_id=pair[0], item_id=pair[1], uom=self.units[pair], period_start_day=start, qty=str(qty))
                  for (pair, start), qty in sorted(self.weekly.items())])

    def quantity(self, pair, day):
        cycle, local = season_day(day)
        start = local - (ORIGIN + timedelta(days=local)).weekday()
        if (pair, start) not in self.weekly:
            raise ValueError(f"Missing exogenous template, never an implicit zero: {pair}/{start}")
        weekly = grown(self.weekly[pair, start], cycle, self.units[pair])
        offset = local - start
        if self.units[pair] == "UN":
            return weekly * (offset + 1) // 7 - weekly * offset // 7
        return weekly / 7

    def known_day(self, day):
        _, local = season_day(day)
        return local - (ORIGIN + timedelta(days=local)).weekday() + 6

    def requirements(self, day):
        from etudecas.simulation.engine.mrp_planning import Requirement
        return {pair: (Requirement(self.identity(pair, day), day, qty),)
                for pair in self.units if (qty := self.quantity(pair, day)) > 0}

    @staticmethod
    def identity(pair, day):
        return f"external:scn:BASE:synthetic_W:{pair[0]}:{pair[1]}:D{day}"

    def provenance(self, pair, day):
        cycle, _ = season_day(day)
        return dict(demand_id=self.identity(pair, day), scenario_id="scn:BASE", cycle_index=cycle,
                    known_day=self.known_day(day), source_file=self.path,
                    source_cells="demand_qty; fixed W requested weekly profile",
                    physical_demand_source="synthetic_fixed_W_other_uses",
                    estimation_basis="52-week repeat with 5% growth; independent of future production and shortages")


def install_projection(planning, engine, frozen, days, *, forecast_mode="source_priority", customer_payload=None):
    """Install explicit scenario calendars, leaving original classes available."""
    if forecast_mode not in FORECAST_MODES:
        raise ValueError("Unknown prospective forecast mode")
    coherent = forecast_mode == "coherent_scenario"
    restorations = []

    def replace(module, name, value):
        restorations.append((module, name, getattr(module, name)))
        setattr(module, name, value)

    native_external = planning.ExternalComponentDemandCalendar

    class ProjectedExternal(native_external):
        def __init__(self, payload, **kwargs):
            super().__init__(payload, **kwargs)
            self.execution_only = payload.get("physical_use_only") is True
            self.projected_provenance = {}

        def requirements(self, *, decision_day, first_day, through_day):
            result = super().requirements(decision_day=decision_day, first_day=first_day, through_day=through_day)
            if self.execution_only:
                return result
            from etudecas.simulation.engine.mrp_planning import Requirement
            for pair in self.pairs:
                rows = list(result.get(pair, ()))
                if coherent and decision_day >= SCENARIO_KNOWN_DAY:
                    if pair not in frozen.units:
                        raise ValueError(f"No fixed other-use scenario for forecast pair {pair}")
                    rows = [row for row in rows if row.due_day < SCENARIO_FIRST_DAY]
                for target in range(max(FIRST, first_day), min(through_day + 1, self.horizon_days)):
                    if coherent and decision_day >= SCENARIO_KNOWN_DAY and target >= SCENARIO_FIRST_DAY:
                        qty = frozen.quantity(pair, target)
                        identity = f"external:scn:BASE:coherent_forecast:{pair[0]}:{pair[1]}:D{target}"
                        self.projected_provenance[identity] = dict(demand_id=identity, scenario_id="scn:BASE",
                            cycle_index=season_day(target)[0], known_day=SCENARIO_KNOWN_DAY,
                            source_file=frozen.path, source_cells="W demand_qty; declared prospective scenario",
                            estimation_basis="Same fixed requested other-use scenario as physical execution; added to own BOM once")
                        if qty > 0:
                            rows.append(Requirement(identity, target, qty))
                        continue
                    # Supplied zero is genuine coverage too: never fill it with a guess.
                    if self._revision_selection(pair, decision_day=decision_day, due_day=target)[2] is not None:
                        continue
                    cycle, local = season_day(target)
                    start, version, row = self._revision_selection(pair,
                        decision_day=min(decision_day, FIRST - 1), due_day=local)
                    if row is not None:
                        qty = grown(row["qty"], cycle, self._projection_units[pair])
                        offset = local - start
                        qty = (qty * (offset + 1) // 7 - qty * offset // 7
                               if self._projection_units[pair] == "UN" else qty / 7)
                        known = version["known_day"]
                        file, cells = row["source_file"], row["source_cells"]
                    elif pair in frozen.units and frozen.known_day(target) <= decision_day:
                        qty, known = frozen.quantity(pair, target), frozen.known_day(target)
                        file, cells = frozen.path, "W demand_qty weekly profile; synthetic forecast fallback"
                    else:
                        continue
                    identity = f"external:scn:BASE:synthetic_forecast:{pair[0]}:{pair[1]}:D{target}"
                    self.projected_provenance[identity] = dict(demand_id=identity, scenario_id="scn:BASE",
                        cycle_index=cycle, known_day=known, source_file=file, source_cells=cells,
                        estimation_basis="Synthetic 52-week forecast extension, 5% growth, supplied periods take priority")
                    if qty > 0:
                        rows.append(Requirement(identity, target, qty))
                if rows:
                    result[pair] = tuple(sorted(rows, key=lambda row: (row.due_day, row.requirement_id)))
                else:
                    result.pop(pair, None)
            return result

        def covered_days(self, pair, *, decision_day, first_day, through_day):
            covered = set(super().covered_days(pair, decision_day=decision_day, first_day=first_day, through_day=through_day))
            if not self.execution_only:
                for target in range(max(FIRST, first_day), min(through_day + 1, self.horizon_days)):
                    if coherent and decision_day >= SCENARIO_KNOWN_DAY and target >= SCENARIO_FIRST_DAY:
                        if pair not in frozen.units:
                            raise ValueError(f"No fixed other-use scenario for forecast pair {pair}")
                        frozen.quantity(pair, target)  # Missing template is not an explicit zero.
                        covered.add(target)
                        continue
                    _, local = season_day(target)
                    if (self._revision_selection(pair, decision_day=min(decision_day, FIRST-1), due_day=local)[2]
                            is not None or pair in frozen.units and frozen.known_day(target) <= decision_day):
                        covered.add(target)
            return frozenset(covered)

        def provenance(self, requirement_id):
            return (dict(self.projected_provenance[requirement_id]) if requirement_id in self.projected_provenance
                    else super().provenance(requirement_id))

        def day_audit(self, pair, *, decision_day):
            audit = super().day_audit(pair, decision_day=decision_day)
            if coherent and decision_day >= SCENARIO_FIRST_DAY and not self.execution_only:
                audit.update(forecast_selection_mode="coherent_synthetic_other_uses_52_week_5pct_growth",
                    forecast_coverage_reason="declared_scenario_not_industrial_source", forecast_source_covered=0,
                    forecast_known_day=SCENARIO_KNOWN_DAY, forecast_vintage_id="coherent_scenario_20260101",
                    forecast_latest_known_day=SCENARIO_KNOWN_DAY,
                    forecast_latest_known_vintage_id="coherent_scenario_20260101",
                    forecast_period_start_day=decision_day - (ORIGIN + timedelta(days=decision_day)).weekday(),
                    forecast_source_file=frozen.path, forecast_source_cells="W requested demand_qty profile")
                return audit
            if decision_day >= FIRST and not self.execution_only and not audit["forecast_source_covered"]:
                _, local = season_day(decision_day)
                _, version, row = self._revision_selection(pair,
                    decision_day=min(decision_day, FIRST-1), due_day=local)
                if row is not None or pair in frozen.units:
                    audit.update(forecast_selection_mode="synthetic_52_week_forecast_5pct_growth",
                        forecast_coverage_reason="synthetic_scenario_not_source_observation",
                        forecast_source_covered=0,
                        forecast_known_day=version["known_day"] if row is not None else frozen.known_day(decision_day))
            return audit

    original_init = ProjectedExternal.__init__

    def external_init(self, payload, **kwargs):
        original_init(self, payload, **kwargs)
        self._projection_units = kwargs["pair_uoms"]

    ProjectedExternal.__init__ = external_init
    replace(planning, "ExternalComponentDemandCalendar", ProjectedExternal)
    replace(engine, "ExternalComponentDemandCalendar", ProjectedExternal)
    # This subclass is defined when engine is imported, so rebind its base explicitly.
    class ProjectedPlanning(ProjectedExternal):
        def due(self, day):
            raise ValueError("A planning-only forecast cannot execute physical demand")
    replace(engine, "PlanningOnlyExternalComponentCalendar", ProjectedPlanning)

    native_industrial = engine.IndustrialComponentPlanningCalendar

    class ProjectedIndustrial(native_industrial):
        def windows(self, pair, *, decision_day, first_day, through_day):
            from etudecas.simulation.engine.mrp_planning import IndustrialPlanningWindow
            if coherent and decision_day >= SCENARIO_KNOWN_DAY:
                # Do not let E4 or authoritative I replace the separate,
                # coherent BOM + other-use forecasts. Preserve pre-cutover days.
                if first_day >= SCENARIO_FIRST_DAY:
                    return ()
                return super().windows(pair, decision_day=decision_day, first_day=first_day,
                    through_day=min(through_day, SCENARIO_FIRST_DAY - 1))
            actual = list(super().windows(pair, decision_day=decision_day, first_day=first_day, through_day=through_day))
            covered = {d for w in actual for d in range(w.first_day, w.end_day_exclusive)}
            for start in range(4 + ((max(FIRST, first_day)-4)//7)*7, through_day + 1, 7):
                first, end = max(start, first_day, FIRST), min(start+7, through_day+1)
                missing = [d for d in range(first, end) if d not in covered]
                if not missing:
                    continue
                cycle, local_start = season_day(start)
                cutoff = min(decision_day, FIRST-1, local_start-1)
                if cutoff < 0:
                    continue
                local_first = missing[0] - cycle*SEASON
                local_end = missing[-1] + 1 - cycle*SEASON
                base = super().windows(pair, decision_day=cutoff,
                    first_day=local_first, through_day=local_end-1)
                for window in base:
                    actual.append(IndustrialPlanningWindow(start, window.first_day+cycle*SEASON,
                        window.end_day_exclusive+cycle*SEASON, window.qty*1.05**cycle, window.known_day,
                        "synthetic_52_week_forecast:" + window.source_file, window.source_cells))
            return tuple(sorted(actual, key=lambda row: row.first_day))

    replace(engine, "IndustrialComponentPlanningCalendar", ProjectedIndustrial)

    native_history = engine.SourceCustomerHistory
    customer_template = None
    if coherent:
        if not isinstance(customer_payload, dict):
            raise ValueError("Coherent forecasts require the unchanged customer history template")
        customer_template = native_history(customer_payload,
            demand_pairs={(row["node_id"], row["item_id"]) for row in customer_payload["rows"]},
            origin_date=ORIGIN.isoformat(), sim_days=FIRST)

    class ProjectedHistory(native_history):
        def __init__(self, payload, **kwargs):
            super().__init__(payload, **dict(kwargs, sim_days=min(FIRST, kwargs["sim_days"])))
            self.sim_days = kwargs["sim_days"]

        def quantity(self, pair, *, decision_day, target_day):
            if target_day != decision_day or not 0 <= target_day < self.sim_days:
                raise ValueError("Synthetic customer orders are only disclosed on arrival")
            if target_day < FIRST:
                result = super().quantity(pair, decision_day=decision_day, target_day=target_day)
            else:
                cycle, local = season_day(target_day)
                start = local - (ORIGIN + timedelta(days=local)).weekday()
                weekly, cell, file = self.rows[pair, start]
                quantity = grown(weekly, cycle, "UN")
                offset = local - start
                before, after = quantity*offset//7, quantity*(offset+1)//7
                audit = dict.fromkeys(engine.CUSTOMER_DEMAND_POLICY_FIELDS, "")
                audit.update(day=target_day, decision_day=decision_day, node_id=pair[0], item_id=pair[1], uom="UN",
                    policy=MODE, status="synthetic_52_week_orders_5pct_growth", source_row=cell,
                    source_file=file, period_start_day=start+cycle*SEASON, period_end_day=start+cycle*SEASON+6,
                    weekly_source_qty=quantity, day_qty=after-before, allocation_start_day=start+cycle*SEASON,
                    cumulative_before_qty=before, cumulative_through_qty=after)
                result = after-before, audit
            return result

    replace(engine, "SourceCustomerHistory", ProjectedHistory)
    original_resolve = engine.resolve_customer_demand_policy

    def resolve_customer(payload, **kwargs):
        if payload != "source_customer_history_v1" or kwargs["sim_days"] != days:
            raise ValueError("Prospective adapter requires its explicit customer history contract")
        return original_resolve(payload, **dict(kwargs, sim_days=min(FIRST, days)))
    replace(engine, "resolve_customer_demand_policy", resolve_customer)

    native_forecast = engine.RollingMrpForecast

    class ProjectedForecast(native_forecast):
        def selection(self, decision_day):
            selected = super().selection(decision_day)
            # The selection carries the decision date only after the scenario
            # publication. Source cells still resolve their own earlier vintage.
            return (decision_day, 0) if coherent and decision_day >= SCENARIO_KNOWN_DAY else selected

        def source_for_day(self, pair, *, selected, target_day):
            if (coherent and selected is not None and selected[0] >= SCENARIO_KNOWN_DAY
                    and target_day >= SCENARIO_FIRST_DAY):
                cycle, local = season_day(target_day)
                local_start = local - (ORIGIN + timedelta(days=local)).weekday()
                weekly, cell, file = customer_template.rows[pair, local_start]
                qty = grown(weekly, cycle, "UN")
                start = target_day - (ORIGIN + timedelta(days=target_day)).weekday()
                self._source_periods[SCENARIO_KNOWN_DAY, pair, target_day] = (start, start + 6, qty)
                return (qty / 7, f"synthetic_coherent_customer:{file}:{cell}"), SCENARIO_KNOWN_DAY
            actual, known = super().source_for_day(pair, selected=selected, target_day=target_day)
            if actual is not None or target_day < FIRST:
                return actual, known
            cycle, local = season_day(target_day)
            base, known = super().source_for_day(pair, selected=selected, target_day=local)
            if base is None:
                # A missing opening week must borrow the opening forecast,
                # not the final 2025 vintage's nearest (November) period.
                template_selected = self.selection(max(0, min(selected[0], max(0, local))))
                base, known = self.nearest_known_period(pair, selected=template_selected, target_day=local)
            qty = base[0] * 1.05**cycle
            marker = "synthetic_52_week_forecast:" + base[1]
            start = target_day - (ORIGIN + timedelta(days=target_day)).weekday()
            self._source_periods[known, pair, target_day] = (start, start+6, qty*7)
            return (qty, marker), known

        def projection_audit_rows(self, pair, *, decision_day, horizon_days):
            rows = super().projection_audit_rows(pair, decision_day=decision_day, horizon_days=horizon_days)
            for row in rows:
                if "synthetic_coherent_customer:" in row["source_rows"]:
                    row.update(policy="coherent_scenario_52_week_5pct_growth",
                               status="synthetic_scenario_not_industrial_forecast")
            return rows
    replace(engine, "RollingMrpForecast", ProjectedForecast)

    return restorations


def resolve_inputs():
    config = read(CONFIG)
    if (config.get("schema_version") != 2 or config.get("default_forecast_mode") != "coherent_scenario"
            or config.get("comparison_forecast_modes") != ["source_priority"]):
        raise ValueError("Unexpected autonomous MRP reference contract")
    assets = config["assets"]
    for name, contract in assets.items():
        path = ROOT / contract["path"]
        if sha(path) != contract["sha256"]:
            raise ValueError(f"Versioned MRP asset changed: {name}")
        if "content_sha256" in contract:
            with gzip.open(path, "rb") as stream:
                content_sha = hashlib.sha256(stream.read()).hexdigest()
            if content_sha != contract["content_sha256"]:
                raise ValueError(f"Versioned MRP asset content changed: {name}")
    protocol = read(ROOT/assets["protocol"]["path"])
    graph_path = ROOT/assets["graph"]["path"]
    graph = read(graph_path)
    inputs = {contract["path"]: contract["sha256"] for contract in assets.values()}
    inputs[rel(CONFIG)] = sha(CONFIG)
    frozen_path = ROOT/assets["other_use_profile"]["path"]
    engine_arguments = read(ROOT/assets["engine_arguments"]["path"])
    return config, protocol, graph, inputs, frozen_path, engine_arguments


def prepare_graph(graph, config, days, forecast_mode="source_priority"):
    graph = deepcopy(graph)
    if days > FIRST:
        graph["meta"]["current_reference_projection"] = dict(projection_contract(config, forecast_mode), schema_version=1,
            scenario_id="scn:BASE", days=days)
        validate_projection_contract(graph["meta"], days)
        source = ROOT/config["assets"]["other_use_profile"]["path"]
        graph["meta"]["current_reference_other_use_profile"] = FrozenOtherUses(source).payload()
        closures = graph["meta"]["manufacturing_closures"]["rows"]
        final_year = (ORIGIN + timedelta(days=days+364)).year
        for year in range(2026, final_year+1):
            start = date(year, 8, 1)
            start += timedelta(days=(-start.weekday()) % 7)
            closures.append(dict(node_id="M-1810", start_date=start.isoformat(),
                end_date=(start+timedelta(days=11)).isoformat(),
                provenance="prospective assumption: first two full August workweeks; only 2025 dates confirmed"))
    return graph


def run_engine(graph, protocol, config, frozen_path, command, output, days):
    adapter = importlib.import_module(config["adapter_module"])
    f3 = adapter.f3_module()
    tracker = adapter.tracker_for(f3, graph["meta"]["formats_reconciled_weekly_budgets"],
                                  protocol["cumulative_residual_pairs"])
    e4 = f3.e4_module()
    e4.TARGETS = {tuple(p) for p in protocol["forecast_reconciliation_pairs"]}
    e4.EFFECTIVE_POLICY = "F2_source_weekly_max_own_I_and_preserved_reserves"
    from etudecas.simulation.engine import mrp_planning as planning
    original_reconcile, original_observed = planning.reconcile_industrial_requirements, planning.ObservedExternalComponentExecution
    planner = e4.ScopedReconciliation(original_reconcile)
    planning.reconcile_industrial_requirements = planner.reconcile
    frozen = FrozenOtherUses(graph["meta"]["current_reference_other_use_profile"]) if days > FIRST else None

    class RuntimeObserved(original_observed):
        def merge_due(self, day, estimated_due):
            if day % 30 == 0:
                print(f"[current-reference] jour {day}/{days}", flush=True)
            if frozen is not None and day >= FIRST:
                # The supplied physical observations extend three days beyond
                # the 362-day validation run. Preserve them where supplied.
                return super().merge_due(day, frozen.requirements(day))
            return tracker.close(day, super().merge_due(day, estimated_due))

        def provenance(self, identity, forecast_calendar):
            if frozen is not None and ":synthetic_W:" in identity:
                *_, node, item_prefix, item, d = identity.split(":")
                return frozen.provenance((node, item_prefix+":"+item), int(d[1:]))
            if identity in tracker.provenance:
                return {**tracker.provenance[identity], "physical_demand_source": "reconstructed_scan3_residual_not_identified_other_format"}
            return super().provenance(identity, forecast_calendar)

        def day_audit(self, pair, day):
            if frozen is not None and day >= FIRST and (pair, day) not in self._rows:
                return dict(physical_demand_source="synthetic_fixed_W_other_uses", physical_source_file=frozen.path,
                    physical_source_cells="W demand_qty weekly profile", physical_observation_qty="",
                    physical_demand_known_day=frozen.known_day(day))
            return super().day_audit(pair, day)

    planning.ObservedExternalComponentExecution = RuntimeObserved
    engine = importlib.import_module("etudecas.simulation.engine.run_first_simulation")
    forecast_mode = graph["meta"].get("current_reference_projection", {}).get("forecast_mode", "source_priority")
    restorations = install_projection(planning, engine, frozen, days, forecast_mode=forecast_mode,
        customer_payload=graph["meta"].get("customer_demand_history")) if frozen else []
    original_consume = engine.LotLedger.consume
    targets = {(r["node_id"], r["item_id"]) for r in tracker.budgets}

    def consume(ledger, **kwargs):
        allocations = original_consume(ledger, **kwargs)
        quantity = math.fsum(float(r["qty"]) for r in allocations)
        pair = kwargs["node_id"], kwargs["item_id"]
        if pair in targets and kwargs["event_type"] == "production_consume" and kwargs["day"] < FIRST:
            if not ledger.enabled or not math.isclose(quantity, kwargs["qty"], rel_tol=1e-10, abs_tol=1e-7):
                raise ArithmeticError("Physical F3 ledger allocation differs from consumption")
            tracker.own_withdrawal(day=kwargs["day"], node_id=pair[0], item_id=pair[1], qty=quantity, event_type=kwargs["event_type"])
        if kwargs["event_type"] == "external_component_consume":
            tracker.served(kwargs["day"], kwargs.get("source_id", ""), quantity)
        return allocations

    engine.LotLedger.consume = consume
    weekly_module = importlib.import_module(config["weekly_plugin_module"])
    weekly = weekly_module.install(engine, graph, protocol)
    old_argv = sys.argv
    try:
        sys.argv = [__file__, *command]
        engine.main()
    finally:
        sys.argv = old_argv
        weekly.restore()
        engine.LotLedger.consume = original_consume
        for module, name, old in reversed(restorations):
            setattr(module, name, old)
        planning.reconcile_industrial_requirements = original_reconcile
        planning.ObservedExternalComponentExecution = original_observed
    if len(tracker.published) != sum(r["closing_day"] < days for r in tracker.budgets):
        raise ArithmeticError("A historical weekly budget was not published")
    weekly.write_evidence(output)
    rows = [tracker.published[k] for k in sorted(tracker.published)]
    for row in rows:
        row["residual_backlog_at_closing_qty"] = max(0., row["residual_requested_qty"]-row["residual_executed_on_closing_day_qty"])
    units = {(n["id"], s["item_id"]): s["uom"] for n in graph["nodes"] for s in n.get("inventory", {}).get("states", [])}
    windows = [dict(planner.windows[k], uom=units[(planner.windows[k]["node_id"],planner.windows[k]["item_id"])]) for k in sorted(planner.windows)]
    for filename, records, fields in (
        ("F3_weekly_reconciliation.csv", rows, list(rows[0]) if rows else ["budget_id"]),
        ("F3_residual_allocations.csv", tracker.allocations, ["day","requirement_id","node_id","item_id","qty","uom"]),
        ("F3_reconciliation_windows.csv", windows, e4.WINDOW_FIELDS),
        ("Cumulative_reconciliation.csv", tracker.cumulative_audit, list(tracker.cumulative_audit[0]) if tracker.cumulative_audit else ["node_id"]),
    ):
        with (output/"data"/filename).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    return dict(historical_F3_budgets=len(rows), E4_forecast_pairs=protocol["forecast_reconciliation_pairs"],
                F3_cumulative_pairs=protocol["cumulative_residual_pairs"],
                future_other_pairs=[list(p) for p in sorted(frozen.units)] if frozen else [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1825)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-id", default="scn:BASE", choices=["scn:BASE"])
    parser.add_argument("--forecast-mode", choices=FORECAST_MODES, default=None,
        help="Preserve source priority, or test coherent future forecasts without changing physical demand")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 1825:
        raise ValueError("Current reference supports 1 to1825 days, nominal only")
    output = Path(args.output_dir).resolve()
    if not output.is_relative_to(ROOT/"etudecas") or output.exists():
        raise ValueError("Use a new output directory under etudecas")
    config, protocol, graph, inputs, frozen_path, tail = resolve_inputs()
    forecast_mode = args.forecast_mode or config["default_forecast_mode"]
    graph = prepare_graph(graph, config, args.days, forecast_mode)
    tail = list(tail)
    for placeholder, value in (("__INPUT_GRAPH__", rel(output/"input_graph.json")),
                               ("__OUTPUT_DIR__", rel(output)), ("__DAYS__", str(args.days))):
        tail[tail.index(placeholder)] = value
    for i, token in enumerate(tail[:-1]):
        if token.startswith("--") and token.endswith("-csv"):
            inputs[tail[i+1]] = sha(ROOT/tail[i+1])
    manifest = dict(reference=config["reference_id"], scenario_id=args.scenario_id, days=args.days,
        forecast_mode=forecast_mode,
        last_simulated_date=(ORIGIN+timedelta(days=args.days-1)).isoformat(),
        status="prepared_not_executed", output=rel(output), graph=rel(output/"input_graph.json"),
        command=[sys.executable, "-B", "-m", "etudecas.simulation.current_reference", *list(argv or sys.argv[1:])],
        engine_arguments=tail, inputs=inputs, projection=graph["meta"].get("current_reference_projection"),
        limitations=["Execution is not industrial calibration or independent qualification.",
            "F3 is historical reconciliation, not an autonomous 2025 forecast.",
            "After day361, customer orders and other uses are synthetic scenarios, not observed deliveries.",
            "A 52-week cycle is364days; prospective seasons are not civil-year demand totals.",
            "Risk and sensitivity scenarios require a separate compatibility qualification."])
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    output.mkdir(parents=True, exist_ok=False)
    write(output/"input_graph.json", graph)
    inputs[rel(output/"input_graph.json")] = sha(output/"input_graph.json")
    write(output/"prepared.json", manifest)
    if args.prepare_only:
        print(json.dumps(dict(status="prepared_not_executed", manifest=rel(output/"prepared.json"))))
        return 0
    from etudecas.toolbox.cli import code_fingerprint
    before = code_fingerprint()
    started = time.monotonic()
    manifest["started_at_utc"] = datetime.now(timezone.utc).isoformat()
    error = None
    try:
        manifest["runtime"] = run_engine(graph, protocol, config, frozen_path, tail, output, args.days)
    except Exception as exc:
        error = exc
        manifest["error"] = repr(exc)
    after = code_fingerprint()
    manifest.update(seconds=time.monotonic()-started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
        code=before, code_after=after, code_and_inputs_unchanged=before==after and all(sha(ROOT/p)==v for p,v in inputs.items()),
        returncode=0 if error is None else 1)
    manifest["status"] = "passed_execution" if error is None and manifest["code_and_inputs_unchanged"] else "failed_execution"
    write(output/"run_manifest.json", manifest)
    if error is not None:
        raise error
    print(json.dumps(dict(status=manifest["status"], manifest=rel(output/"run_manifest.json"))))
    return 0 if manifest["status"] == "passed_execution" else 1


if __name__ == "__main__":
    raise SystemExit(main())
