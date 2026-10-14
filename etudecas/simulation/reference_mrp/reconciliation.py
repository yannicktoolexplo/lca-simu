"""Scoped industrial-forecast reconciliation retained by the MRP reference."""
from collections import Counter, defaultdict
import math

TARGETS = {("M-1430", "item:773474"), ("M-1810", "item:693055")}
EFFECTIVE_POLICY = "source_weekly_max_own_I_and_preserved_reserves"
WINDOW_FIELDS = ["node_id", "item_id", "uom", "decision_day", "period_start_day", "first_day",
    "end_day_exclusive", "known_day", "source_file", "source_cells", "source_qty", "own_qty",
    "original_external_qty", "effective_external_qty", "effective_delta_vs_original_external_qty",
    "planning_usage_qty", "reserve_qty", "weekly_complement_before_netting_qty",
    "complement_delta_qty", "effective_policy", "evaluations"]


class ScopedReconciliation:
    """Apply the retained source-I rule only to explicitly configured pairs."""

    def __init__(self, original):
        self.original = original
        self.calls = Counter()
        self.windows = {}

    def reconcile(self, requirements, windows, *, pair, decision_day, policy=None):
        self.calls[pair] += 1
        if pair not in TARGETS:
            return self.original(requirements, windows, pair=pair, decision_day=decision_day, policy=policy)
        if policy != "separate_own_and_other_v1":
            raise ValueError("Retained reconciliation requires the separate-use context")
        original, source_windows = tuple(requirements), tuple(windows)
        _, original_audits = self.original(original, source_windows, pair=pair,
            decision_day=decision_day, policy=policy)
        usage = tuple(row for row in original if not row.requirement_id.startswith("reserve:"))
        legacy, legacy_audits = self.original(usage, source_windows, pair=pair,
            decision_day=decision_day, policy=None)
        by_id = {row.requirement_id: row for row in legacy}
        if len(by_id) != len(legacy):
            raise ValueError("Duplicate requirement identity")
        restored = []
        for row in original:
            if row.requirement_id.startswith("reserve:"):
                restored.append(row)
            elif row.requirement_id in by_id:
                restored.append(by_id.pop(row.requirement_id))
        restored.extend(row for row in legacy if row.requirement_id in by_id)
        result_ids = {row.requirement_id: row for row in restored}
        if len(result_ids) != len(restored):
            raise ValueError("Duplicate reconciled identity")
        assert all(result_ids.get(row.requirement_id) == row for row in original
                   if not row.requirement_id.startswith("external:"))
        covered = {day for window in source_windows for day in range(window.first_day, window.end_day_exclusive)}
        assert all(result_ids.get(row.requirement_id) == row for row in original if row.due_day not in covered)
        if not source_windows:
            assert restored == list(original)
            return restored, []
        by_day, reserves_by_day = defaultdict(list), defaultdict(list)
        for row in restored:
            (reserves_by_day if row.requirement_id.startswith("reserve:") else by_day)[row.due_day].append(row.qty)
        assert len(original_audits) == len(legacy_audits) == len(source_windows)
        merged_audits = []
        for window, prior, adapted in zip(source_windows, original_audits, legacy_audits):
            for field in ("period_start_day", "first_day", "end_day_exclusive", "known_day",
                          "source_file", "source_cells"):
                assert prior[field] == adapted[field]
            merged = dict(prior, **adapted)
            budget = max(0.0, merged["source_qty"] - merged["own_qty"])
            merged["weekly_complement_before_netting_qty"] = budget
            merged["complement_delta_qty"] = budget - merged["complement_qty"]
            assert math.isclose(merged["complement_delta_qty"], 0, abs_tol=1e-7, rel_tol=1e-10)
            days = range(window.first_day, window.end_day_exclusive)
            actual_usage = math.fsum(q for day in days for q in by_day[day])
            reserve_qty = math.fsum(q for day in days for q in reserves_by_day[day])
            assert math.isclose(actual_usage, max(merged["own_qty"], merged["source_qty"]),
                                abs_tol=1e-7, rel_tol=1e-10)
            assert window.known_day <= decision_day < window.first_day
            key = (*pair, decision_day, window.period_start_day, window.first_day, window.end_day_exclusive)
            evaluations = self.windows.get(key, {}).get("evaluations", 0) + 1
            self.windows[key] = dict(node_id=pair[0], item_id=pair[1], uom="G", decision_day=decision_day,
                **{field: merged[field] for field in ("period_start_day", "first_day", "end_day_exclusive",
                    "known_day", "source_file", "source_cells", "source_qty", "own_qty")},
                original_external_qty=prior["reconstructed_external_qty"],
                effective_external_qty=merged["complement_qty"],
                effective_delta_vs_original_external_qty=merged["complement_qty"] - prior["reconstructed_external_qty"],
                planning_usage_qty=actual_usage, reserve_qty=reserve_qty,
                weekly_complement_before_netting_qty=budget,
                complement_delta_qty=merged["complement_delta_qty"],
                effective_policy=EFFECTIVE_POLICY, evaluations=evaluations)
            merged_audits.append(merged)
        return restored, merged_audits
