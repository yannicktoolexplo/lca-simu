"""Conditional replay of fixed requests, revealed only after own production.

The retained control is a scenario source, not an independent industrial
observation. Requested quantities are fixed; service and debts are not replayed.
"""
from collections import defaultdict
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path


MODE = "fixed_residual_replay"
DEFERRED_REASON = "deferred_fixed_residual_until_close"
PHYSICAL_SOURCE = "conditional_fixed_residual_from_retained_control"
STATUS = "conditional_scenario_not_industrial_observation"
INTEGER_FIELDS = ("first_day", "end_day_exclusive", "closing_day")
TEXT_FIELDS = ("node_id", "item_id", "uom")


def _number(value, *, integer=False, nonnegative=True):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a fixed residual quantity or date")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid fixed residual number") from exc
    if (not result.is_finite() or (nonnegative and result < 0)
            or (integer and result != result.to_integral_value())):
        raise ValueError("Fixed residual quantities/dates must be finite and physical UN integer")
    return result


class FixedResidualProfile:
    """Immutable-by-convention scenario input with exact horizon coverage."""

    def __init__(self, rows, budgets, *, days, profile_path, profile_sha256):
        if type(days) is not int or not 1 <= days <= 362:
            raise ValueError("Fixed residual replay is limited to the historical362-day window")
        if (not isinstance(profile_path, str) or not profile_path
                or not isinstance(profile_sha256, str) or len(profile_sha256) != 64
                or any(c not in "0123456789abcdef" for c in profile_sha256)):
            raise ValueError("Fixed residual profile requires source path and SHA256")
        expected = {}
        for source in budgets:
            closing = int(_number(source['closing_day'], integer=True))
            if closing >= days:
                continue
            identity = source['budget_id']
            if not isinstance(identity, str) or not identity or identity in expected:
                raise ValueError("Duplicate or invalid expected residual budget")
            expected[identity] = source
        values = {}
        for row in rows:
            identity = row.get('budget_id')
            if identity not in expected or identity in values:
                raise ValueError("Unknown or duplicate fixed residual budget")
            source = expected[identity]
            if any(row.get(field) != source[field] for field in TEXT_FIELDS):
                raise ValueError("Fixed residual article, site or unit differs from its source budget")
            if any(_number(row.get(field), integer=True) != _number(source[field], integer=True)
                   for field in INTEGER_FIELDS):
                raise ValueError("Fixed residual dates differ from their source budget")
            day = int(_number(row['closing_day'], integer=True))
            if not int(_number(row['first_day'], integer=True)) <= day < int(
                    _number(row['end_day_exclusive'], integer=True)):
                raise ValueError("Fixed residual closing lies outside its source window")
            rid = f"external:scn:BASE:zz-reconciled-F3:{identity}:D{day}"
            if row.get('requirement_id') != rid:
                raise ValueError("Fixed residual requirement identity differs from its budget")
            if _number(row.get('covered_scan3_qty')) != _number(source['covered_scan3_qty']):
                raise ValueError("Fixed residual source target differs from its budget")
            qty = _number(row.get('residual_requested_qty'), integer=source['uom'] == 'UN')
            values[identity] = dict(qty=qty, requirement_id=rid, closing_day=day)
        if set(values) != set(expected):
            raise ValueError("Every closing budget needs an explicit fixed request, including zero")
        self.values = values
        self.days = days
        self.path = profile_path
        self.sha256 = profile_sha256

    @classmethod
    def load(cls, path, budgets, *, days, root):
        root = Path(root).resolve()
        path = Path(path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Fixed residual profile must be inside the repository")
        before = path.read_bytes()
        import io
        rows = list(csv.DictReader(io.StringIO(before.decode('utf-8-sig'))))
        return cls(rows, budgets, days=days, profile_path=path.relative_to(root).as_posix(),
                   profile_sha256=hashlib.sha256(before).hexdigest())

    def payload(self):
        return dict(schema_version=1, profile_path=self.path, profile_sha256=self.sha256,
            rows=len(self.values), days=self.days, quantity_field='residual_requested_qty',
            knowledge='closing_day_after_own_production', status=STATUS)


def fixed_tracker_for(base_type, budgets, profile, cumulative_pairs=()):
    """Keep the historical publication/service order, changing only requests."""
    cumulative_pairs = {tuple(pair) for pair in cumulative_pairs}

    class FixedResidualTracker(base_type):
        def __init__(self):
            # Reuse bookkeeping only; neither legacy close nor its residual
            # formula is invoked by this tracker.
            super().__init__(budgets, mode='legacy_residual')
            self.mode = MODE
            self.profile = profile
            self.cumulative_closes = defaultdict(list)
            self.cumulative = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
            self.cumulative_audit = []
            for day, entries in self.closes.items():
                self.cumulative_closes[day] = [r for r in entries
                    if (r['node_id'], r['item_id']) in cumulative_pairs]
                self.closes[day] = [r for r in entries
                    if (r['node_id'], r['item_id']) not in cumulative_pairs]

        def close(self, day, existing):
            from etudecas.simulation.engine.mrp_planning import Requirement
            if type(day) is not int or not 0 <= day < profile.days:
                raise ValueError("Fixed residual close lies outside the declared horizon")
            result = dict(existing)
            sources = tuple(self.closes.get(day, ())) + tuple(self.cumulative_closes.get(day, ()))
            for source in sources:
                key = source['budget_id']
                if key in self.published:
                    raise ValueError("A fixed residual can be published only once")
                saved = profile.values[key]
                if saved['closing_day'] != day:
                    raise ValueError("Fixed residual cannot be revealed on another day")
                pair = source['node_id'], source['item_id']
                own = sum((self.own[(*pair, d)] for d in range(source['first_day'],
                    source['end_day_exclusive'])), Decimal(0))
                target = _number(source['covered_scan3_qty'])
                fixed = saved['qty']
                if source['uom'] == 'UN':
                    for qty in (target, own, fixed): _number(qty, integer=True)
                rid = saved['requirement_id']
                row = dict(source, scan3_reconciliation_mode=MODE,
                    scan3_target_qty=float(target), scan3_minus_own_qty=float(target-own),
                    fixed_residual_source_qty=float(fixed),
                    scan3_minus_own_and_fixed_residual_qty=float(target-own-fixed),
                    replay_profile_source=profile.path, replay_profile_sha256=profile.sha256,
                    replay_known_phase='after_own_production',
                    own_physical_qty=float(own), residual_requested_qty=float(fixed),
                    own_exceeds_scan3_qty=float(max(Decimal(0), own-target)), requirement_id=rid,
                    residual_executed_qty=0., residual_executed_on_closing_day_qty=0.,
                    residual_backlog_initial_qty=0., residual_backlog_final_qty=float(fixed),
                    first_execution_day=None, last_execution_day=None)
                self.published[key] = row
                self.by_requirement[rid] = row
                self.provenance[rid] = dict(demand_id=key, scenario_id='scn:BASE', cycle_index=0,
                    known_day=day, source_file=profile.path, source_cells='budget_id='+key,
                    estimation_basis=json.dumps(dict(method='fixed_residual_from_retained_control',
                        profile_path=profile.path, profile_sha256=profile.sha256,
                        source_budget_id=key, source_requirement_id=rid,
                        fixed_requested_qty=float(fixed), known_day=day,
                        known_phase='after_own_production', status=STATUS,
                        planning_use='not available before after-production closing'), ensure_ascii=False))
                if pair in cumulative_pairs:
                    cumulative = self.cumulative[pair]
                    prior = cumulative[2]
                    cumulative[0] += target
                    cumulative[1] += own
                    cumulative[2] += fixed
                    self.cumulative_audit.append(dict(node_id=pair[0], item_id=pair[1], closing_day=day,
                        source_cells=source['scan3_source_cell'], covered_source_cumulative_qty=float(cumulative[0]),
                        covered_own_cumulative_qty=float(cumulative[1]),
                        prior_requested_including_backlog_qty=float(prior), new_residual_qty=float(fixed),
                        total_requested_qty=float(cumulative[2]),
                        cumulative_unreversed_excess_qty=float(max(Decimal(0), cumulative[1]+cumulative[2]-cumulative[0])),
                        scan3_reconciliation_mode=MODE,
                        scan3_minus_own_and_fixed_residual_qty=float(cumulative[0]-cumulative[1]-cumulative[2])))
                if fixed:
                    result[pair] = tuple(result.get(pair, ())) + (Requirement(rid, day, float(fixed)),)
            return result

    return FixedResidualTracker()
