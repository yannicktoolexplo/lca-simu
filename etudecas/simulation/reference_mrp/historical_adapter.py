"""Historical 2025 reconciliation retained as a versioned runtime adapter."""
from collections import defaultdict
from decimal import Decimal
import json

from . import reconciliation


class WeeklyTracker:
    """Publish documented weekly residual use only when its source week closes."""

    def __init__(self, budgets):
        self.budgets = budgets
        self.closes = defaultdict(list)
        self.own = defaultdict(Decimal)
        self.published = {}
        self.provenance = {}
        self.by_requirement = {}
        self.allocations = []
        for row in budgets:
            self.closes[row["closing_day"]].append(row)

    def own_withdrawal(self, *, day, node_id, item_id, qty, event_type):
        if event_type == "production_consume":
            self.own[(node_id, item_id, day)] += Decimal(str(qty))

    def close(self, day, existing):
        from etudecas.simulation.engine.mrp_planning import Requirement
        result = dict(existing)
        for source in self.closes.get(day, ()):
            pair = source["node_id"], source["item_id"]
            key = source["budget_id"]
            if key in self.published:
                raise ValueError("A weekly residual can be published only once")
            own = sum((self.own[(*pair, d)] for d in range(source["first_day"],
                source["end_day_exclusive"])), Decimal(0))
            target = Decimal(str(source["covered_scan3_qty"]))
            remainder = max(Decimal(0), target - own)
            rid = f"external:scn:BASE:zz-reconciled-F3:{key}:D{day}"
            row = dict(source, own_physical_qty=float(own), residual_requested_qty=float(remainder),
                own_exceeds_scan3_qty=float(max(Decimal(0), own-target)), requirement_id=rid,
                residual_executed_qty=0., residual_executed_on_closing_day_qty=0.,
                residual_backlog_initial_qty=0., residual_backlog_final_qty=float(remainder),
                first_execution_day=None, last_execution_day=None)
            self.published[key] = row
            self.by_requirement[rid] = row
            self.provenance[rid] = dict(demand_id=key, scenario_id="scn:BASE", cycle_index=0,
                known_day=day, source_file=source["source_file"], source_cells=source["scan3_source_cell"],
                estimation_basis=json.dumps(dict(method="weekly_scan3_minus_actual_own_BOM_residual",
                    budget_id=key, source_week_marker=source["source_week_marker"],
                    first_day=source["first_day"], end_day_exclusive=source["end_day_exclusive"],
                    J_covered_qty=source["covered_scan3_qty"], own_BOM_qty=float(own),
                    residual_qty=float(remainder),
                    own_excess_qty=float(max(Decimal(0), own-target)),
                    I_preserved_separately=True,
                    actual_alternate_SKU_scope="not_identified",
                    timing="Sunday closing accounting convention, not a measured production date",
                    planning_use="not available before closing day"), ensure_ascii=False))
            if remainder > 0:
                result[pair] = tuple(result.get(pair, ())) + (Requirement(rid, day, float(remainder)),)
        return result

    def served(self, day, requirement_id, qty):
        if requirement_id not in self.by_requirement:
            return
        row = self.by_requirement[requirement_id]
        assert day >= row["closing_day"]
        row["residual_executed_qty"] += qty
        if day == row["closing_day"]:
            row["residual_executed_on_closing_day_qty"] += qty
        row["residual_backlog_final_qty"] = max(0., row["residual_requested_qty"]-row["residual_executed_qty"])
        if row["first_execution_day"] is None:
            row["first_execution_day"] = day
        row["last_execution_day"] = day
        assert row["residual_executed_qty"] <= row["residual_requested_qty"] + 1e-6
        self.allocations.append(dict(day=day, requirement_id=requirement_id, node_id=row["node_id"],
            item_id=row["item_id"], qty=qty, uom=row["uom"]))


def f3_module():
    """Compatibility facade expected by current_reference."""
    class Facade:
        WeeklyTracker = globals()["WeeklyTracker"]

        @staticmethod
        def e4_module():
            return reconciliation
    return Facade


def tracker_for(f3, budgets, cumulative_pairs=()):
    physical_targets = {(r["node_id"], r["item_id"]) for r in budgets}
    cumulative_pairs = {tuple(pair) for pair in cumulative_pairs}

    class Tracker(f3.WeeklyTracker):
        def __init__(self, rows):
            super().__init__(rows)
            self.cumulative_closes = defaultdict(list)
            self.cumulative = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
            self.cumulative_audit = []
            for day, entries in self.closes.items():
                self.cumulative_closes[day] = [r for r in entries
                    if (r["node_id"], r["item_id"]) in cumulative_pairs]
                self.closes[day] = [r for r in entries
                    if (r["node_id"], r["item_id"]) not in cumulative_pairs]

        def own_withdrawal(self, *, day, node_id, item_id, qty, event_type):
            if event_type == "production_consume" and (node_id, item_id) in physical_targets:
                assert day >= 0
                self.own[(node_id, item_id, day)] += Decimal(str(qty))

        def close(self, day, existing):
            result = super().close(day, existing)
            from etudecas.simulation.engine.mrp_planning import Requirement
            for source in self.cumulative_closes.get(day, ()):
                pair = source["node_id"], source["item_id"]
                key = source["budget_id"]
                if key in self.published:
                    raise ValueError("A cumulative residual can be published only once")
                own = sum((self.own[(*pair, d)] for d in range(source["first_day"],
                    source["end_day_exclusive"])), Decimal(0))
                target = Decimal(str(source["covered_scan3_qty"]))
                cumulative = self.cumulative[pair]
                cumulative[0] += target
                cumulative[1] += own
                prior_requested = cumulative[2]
                remainder = max(Decimal(0), cumulative[0] - cumulative[1] - prior_requested)
                cumulative[2] += remainder
                if source["uom"] == "UN" and not all(q == q.to_integral_value() for q in (*cumulative, remainder)):
                    raise ArithmeticError("Physical UN reconciliation must remain integer")
                rid = f"external:scn:BASE:zz-reconciled-F3:{key}:D{day}"
                row = dict(source, own_physical_qty=float(own), residual_requested_qty=float(remainder),
                    own_exceeds_scan3_qty=float(max(Decimal(0), own-target)), requirement_id=rid,
                    residual_executed_qty=0., residual_executed_on_closing_day_qty=0.,
                    residual_backlog_initial_qty=0., residual_backlog_final_qty=float(remainder),
                    first_execution_day=None, last_execution_day=None)
                self.published[key] = row
                self.by_requirement[rid] = row
                audit = dict(node_id=pair[0], item_id=pair[1], closing_day=day,
                    source_cells=source["scan3_source_cell"], covered_source_cumulative_qty=float(cumulative[0]),
                    covered_own_cumulative_qty=float(cumulative[1]),
                    prior_requested_including_backlog_qty=float(prior_requested),
                    new_residual_qty=float(remainder), total_requested_qty=float(cumulative[2]),
                    cumulative_unreversed_excess_qty=float(max(Decimal(0), cumulative[1]+cumulative[2]-cumulative[0])))
                self.cumulative_audit.append(audit)
                self.provenance[rid] = dict(demand_id=key, scenario_id="scn:BASE", cycle_index=0,
                    known_day=day, source_file=source["source_file"], source_cells=source["scan3_source_cell"],
                    estimation_basis=json.dumps(dict(method="cumulative_documented_scan3_minus_own_and_prior_requested",
                        **audit, timing="Sunday closing, not measured production date",
                        planning_use="no future observation supplied to planner"), ensure_ascii=False))
                if remainder > 0:
                    result[pair] = tuple(result.get(pair, ())) + (Requirement(rid, day, float(remainder)),)
            return result
    return Tracker(budgets)
