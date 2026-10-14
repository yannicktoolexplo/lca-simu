"""Opt-in weekly source-stock protection prototype; no engine-file changes.

API for the isolated runner: install(engine_module, graph, protocol) -> handle
with restore() and write_evidence(output_path). Hooks compose in LIFO order.
"""
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
import csv
import json
import math

KEY = "weekly_stock_protection"
MODE = "source_week_close_only_v1"
MARKER = "_isolated_stock_review_pair"


def resolve(payload):
    fields = {"schema_version", "mode", "origin_date", "review_weekday", "pairs", "between_reviews"}
    if (not isinstance(payload, dict) or set(payload) != fields
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["mode"] != MODE or type(payload["review_weekday"]) is not int
            or not 0 <= payload["review_weekday"] <= 6
            or payload["between_reviews"] != "no_stock_floor_daily_physical_needs_preserved"
            or not isinstance(payload["pairs"], list) or not payload["pairs"]):
        raise ValueError("Weekly protection requires an explicit candidate cadence and scope")
    origin = date.fromisoformat(payload["origin_date"])
    pairs = set()
    for row in payload["pairs"]:
        if (not isinstance(row, dict) or set(row) != {"node_id", "item_id"}
                or any(not isinstance(value, str) or not value for value in row.values())):
            raise ValueError("Weekly protection requires explicit article/site pairs")
        pair = row["node_id"], row["item_id"]
        if pair in pairs:
            raise ValueError("Duplicate weekly protection pair")
        pairs.add(pair)
    return origin, frozenset(pairs)


def review_points(points, *, decision_day, origin_weekday, review_weekday, point_type):
    """Keep the original floor at review closes, release it between closes.

    Points are non-consumable constraints; no physical requirement is removed.
    The original dated/fallback floor is evaluated, not recomputed or rescaled.
    """
    original = tuple(points)
    if not original:
        raise ValueError("Weekly protection requires an existing source floor")
    days = [p.day for p in original]
    if (len(set(days)) != len(days) or days != sorted(days) or days[0] < decision_day
            or any(not math.isfinite(p.minimum_qty) or p.minimum_qty < 0 for p in original)):
        raise ValueError("Source protection checkpoints must be ordered, unique and nonnegative")
    by_day = {p.day: p.minimum_qty for p in original}
    floor = 0.0
    changed, audit = [], []
    # The first zero explicitly prevents a prior review's floor from persisting
    # in a fresh snapshot. The last zero prevents persistence beyond the range.
    through = max(days)
    for day in range(decision_day, through + 1):
        floor = by_day.get(day, floor)
        if day <= decision_day:
            continue
        weekday = (origin_weekday + day) % 7
        if day != decision_day + 1 and weekday not in (review_weekday, (review_weekday + 1) % 7) and day != through:
            continue
        active = weekday == review_weekday
        qty = floor if active else 0.0
        kind = "review_close" if active else "between_reviews"
        changed.append(point_type(f"weekly_protection:{kind}:{day}", day, qty))
        audit.append(dict(checkpoint_day=day, checkpoint_weekday=weekday, kind=kind,
            source_floor_qty=floor, applied_floor_qty=qty))
    if not changed:
        raise ValueError("Weekly protection horizon contains no future checkpoint")
    if changed[-1].minimum_qty > 0:
        # A horizon ending on the review day must not retain its floor
        # indefinitely after that close.
        day = changed[-1].day + 1
        changed.append(point_type(f"weekly_protection:between_reviews:{day}", day, 0.0))
        audit.append(dict(checkpoint_day=day, checkpoint_weekday=(origin_weekday+day)%7,
            kind="between_reviews", source_floor_qty=floor, applied_floor_qty=0.0))
    return tuple(changed), audit


class WeeklyProtection:
    def __init__(self, module, graph, protocol):
        self.module = module
        self.config = deepcopy(protocol[KEY])
        self.origin, self.pairs = resolve(self.config)
        graph_pairs = {(node["id"], state["item_id"]) for node in graph["nodes"]
            for state in node.get("inventory", {}).get("states", [])}
        if not self.pairs <= graph_pairs:
            raise ValueError("Weekly protection pair absent from the prepared graph")
        self.original_network = module.plan_component_network
        self.original_profile = module.source_stock_protection_profile
        self.evaluations = Counter()
        self.rows = {}
        self.closed = False
        module.plan_component_network = self.network
        module.source_stock_protection_profile = self.profile

    def network(self, **kwargs):
        # Only annotate this call's shallow-copied contexts. The caller's
        # requirements, firms, stock maps and configuration remain untouched.
        contexts = kwargs.get("source_safety_by_pair") or {}
        annotated = dict(contexts)
        for pair in self.pairs & set(contexts):
            if MARKER in contexts[pair]:
                raise ValueError("Weekly protection marker already present")
            annotated[pair] = dict(contexts[pair], **{MARKER: pair})
        if annotated == contexts:
            return self.original_network(**kwargs)
        return self.original_network(**dict(kwargs, source_safety_by_pair=annotated))

    def profile(self, **kwargs):
        pair = kwargs.pop(MARKER, None)
        if pair is None:
            return self.original_profile(**kwargs)
        pair = tuple(pair)
        if pair not in self.pairs:
            raise ValueError("Weekly protection escaped configured scope")
        projection = kwargs.get("projection")
        if not projection or projection["origin_weekday"] != self.origin.weekday():
            raise ValueError("Weekly protection requires the unchanged rolling source calendar")
        requirements = tuple(kwargs["requirements"])
        original, audit = self.original_profile(**dict(kwargs, requirements=requirements))
        changed, records = review_points(original, decision_day=kwargs["decision_day"],
            origin_weekday=self.origin.weekday(), review_weekday=self.config["review_weekday"],
            point_type=self.module.StockProtection)
        decision = kwargs["decision_day"]
        self.evaluations[(decision, pair)] += 1
        # Replace checkpoint metadata too: exported points must be those
        # actually passed to the netter, not the original daily constraints.
        details = {}
        source_days = projection["source_working_days"]
        for point, record in zip(changed, records):
            end = point.day
            for _ in range(source_days):
                end += 1
                while (self.origin.weekday() + end) % 7 > 4:
                    end += 1
            covered = end <= projection["forecast_through_day"]
            need = math.fsum(r.qty for r in requirements if point.day < r.due_day <= end) if covered else ""
            details[point.day] = dict(safety_window_end_day=end, safety_window_need_qty=need,
                safety_window_covered=int(covered), safety_source_floor_qty=record["source_floor_qty"])
            key = (decision, *pair, point.day)
            self.rows[key] = dict(decision_day=decision, node_id=pair[0], item_id=pair[1],
                source_safety_workdays=source_days, review_weekday=self.config["review_weekday"],
                **record, source_window_end_day=end, source_window_need_qty=need,
                source_window_covered=int(covered), effective_rule=MODE)
        tomorrow = changed[0].minimum_qty if changed[0].day == decision + 1 else 0.0
        original_target = audit.get("target_qty")
        audit = dict(audit, target_qty=tomorrow, protection_point_count=len(changed),
            prospective_safety_tomorrow_qty=tomorrow, prospective_safety_basis=MODE,
            prospective_checkpoints=details, weekly_protection_rule=MODE,
            weekly_protection_original_daily_target_qty=original_target,
            weekly_protection_between_reviews="source buffer may be crossed; daily physical requirements remain")
        return changed, audit

    def restore(self):
        if self.closed:
            return
        if self.module.plan_component_network != self.network or self.module.source_stock_protection_profile != self.profile:
            raise RuntimeError("Runtime hooks must be restored in reverse installation order")
        self.module.plan_component_network = self.original_network
        self.module.source_stock_protection_profile = self.original_profile
        self.closed = True

    def write_evidence(self, output_path):
        if not self.closed:
            raise RuntimeError("Restore runtime hooks before writing successful evidence")
        if not self.rows or set(pair for _, pair in self.evaluations) != set(self.pairs):
            raise RuntimeError("Configured weekly protection was not evaluated")
        rows = [dict(self.rows[key], evaluations=self.evaluations[(key[0], (key[1],key[2]))]) for key in sorted(self.rows)]
        with (output_path / "data/weekly_stock_protection.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        report = dict(policy=self.config, evaluated_pairs=[list(p) for p in sorted(self.pairs)],
            evaluations=sum(self.evaluations.values()), checkpoint_rows=len(rows),
            rule="At review close: unchanged source floor; between closes: no floor, physical requirements unchanged",
            source_safety_days="unchanged", observed_ERP_rule=False,
            journal="data/weekly_stock_protection.csv",
            export_contract="Native protection_points/protected_plan use candidate checkpoints; source_floor in journal preserves original floor for comparison")
        with (output_path / "reports/weekly_stock_protection.json").open("x", encoding="utf-8") as stream:
            json.dump(report,stream,indent=2,ensure_ascii=False)


def install(engine_module, graph, protocol):
    return WeeklyProtection(engine_module, graph, protocol)
