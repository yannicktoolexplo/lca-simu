"""Pure dated material planning, independent of the daily physical simulation.

Existing commitments are netted before proposing additional purchases, even
when late. This explicit no-duplicate-purchase convention is not claimed to be
the unidentified industrial ERP policy. Dates of firm receipts never change.
The signed balances are projections, not negative physical inventories.
The separate opt-in initial-receipt postponement helper below can revise only
explicitly replannable, unshipped commitments; ordinary planning stays firm.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from bisect import bisect_left, bisect_right
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from math import ceil, floor, fsum, isfinite, nextafter
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    due_day: int
    qty: float


class WeeklyProductionProgramme:
    """Bounded experiment: advance at most one existing lot per output process.

    Source quantities are compatible weekly budgets, not industrial OF IDs.
    No physical stock is held here; execution stays in the existing campaign.
    """
    def __init__(self, payload, *, bom_by_pair, pair_uoms):
        fields={"schema_version","mode","max_promotions_per_process","current_bucket_policy","assumption","series"}
        if (not isinstance(payload,dict) or set(payload)!=fields or payload["schema_version"]!=1
                or type(payload["schema_version"]) is not int or payload["mode"]!="current_week_existing_lot_v1"
                or type(payload["max_promotions_per_process"]) is not int or payload["max_promotions_per_process"]!=1
                or payload["current_bucket_policy"]!="latest_known_including_current"
                or not isinstance(payload["assumption"],str) or not payload["assumption"].strip()
                or not isinstance(payload["series"],list) or not payload["series"]):
            raise ValueError("Weekly production pilot requires explicit bounded policy and assumption")
        self.series={}; self.rows={}; self.events=[]
        self.bom_by_pair={pair:tuple(rows) for pair,rows in bom_by_pair.items()}
        for series in payload["series"]:
            if not isinstance(series,dict) or set(series)!={"node_id","output_item_id","versions"}:
                raise ValueError("Programme scope requires a produced article/site and versions")
            pair=(series["node_id"],series["output_item_id"])
            if pair in self.series or not bom_by_pair.get(pair) or pair_uoms.get(pair)!="UN":
                raise ValueError("Programme scope must be a unique existing physical UN manufacturing output")
            if not isinstance(series["versions"],list) or not series["versions"]:
                raise ValueError("Programme scope requires known versions")
            ratios=dict(bom_by_pair[pair]); versions=[]; seen=set()
            for version in series["versions"]:
                if not isinstance(version,dict) or set(version)!={"known_day","period_start_day","period_end_day_exclusive","component_budgets"}:
                    raise ValueError("Programme version requires explicit current-week source budgets")
                known,start,end=(version[k] for k in ("known_day","period_start_day","period_end_day_exclusive"))
                if (any(type(x) is not int for x in (known,start,end)) or known<0 or known!=start
                        or end!=start+7 or (start-4)%7 or known in seen):
                    raise ValueError("Programme source versions must be unique dated Sunday weeks")
                if not isinstance(version["component_budgets"],list):raise ValueError("Programme budgets must be a list")
                seen.add(known); budgets=[]; components=set()
                for budget in version["component_budgets"]:
                    if not isinstance(budget,dict) or set(budget)!={"item_id","qty","uom","source_file","source_cells"}:
                        raise ValueError("Programme budget requires source quantity, unit and provenance")
                    component=(pair[0],budget["item_id"])
                    quantity=budget["qty"]
                    if (component in components or component not in ratios or pair_uoms.get(component)!=budget["uom"]
                            or isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not isfinite(quantity) or quantity<0
                            or any(not isinstance(budget[k],str) or not budget[k].strip() for k in ("source_file","source_cells"))):
                        raise ValueError("Programme budgets must be finite, unique BOM components in their canonical units")
                    components.add(component);budgets.append(dict(budget,ratio=ratios[component]))
                versions.append(dict(version,component_budgets=budgets))
            self.series[pair]=tuple(sorted(versions,key=lambda v:v["known_day"]))

    def select(self, *, pair, decision_day, proposals, calendar, consumed, committed, available, capacity_qty,
               opening_pack_pending_qty=0):
        if pair in self.rows or opening_pack_pending_qty>0:return None
        # The pilot acts only at physical execution, never as a Sunday promise.
        if (decision_day+2)%7>=5:return None
        version=next((v for v in reversed(self.series.get(pair,()))
                      if v["known_day"]<=decision_day<v["period_end_day_exclusive"]),None)
        if version is None or len(version["component_budgets"])<2:return None
        slot=next(((r,a) for r,a in calendar if r==decision_day and r<version["period_end_day_exclusive"]),None)
        if slot is None:return None
        for proposal in sorted(proposals,key=lambda p:(p.release_day,p.proposal_id)):
            qty=proposal.qty
            if qty<=0 or qty!=int(qty) or slot[0]>=proposal.release_day or capacity_qty+1e-9<qty:continue
            if any(available.get(component,0)+1e-9<qty*ratio for component,ratio in self._bom(pair)):continue
            audit=[]
            for b in version["component_budgets"]:
                c=(pair[0],b["item_id"]); used=consumed.get(c,0); firm=committed.get(c,0)
                needed=qty*b["ratio"]
                if b["uom"]=="UN":needed=ceil(Decimal(str(qty))*Decimal(str(b["ratio"])))
                audit.append(dict(b,consumed_qty=used,committed_qty=firm,allocated_qty=needed,residual_qty=b["qty"]-used-firm-needed))
            if any(b["residual_qty"] < -1e-8 for b in audit):continue
            return dict(programme_id=f"PROGRAMME|{pair[0]}|{pair[1]}|D{decision_day}",node_id=pair[0],item_id=pair[1],
                decision_day=decision_day,source_known_day=version["known_day"],period_start_day=version["period_start_day"],
                period_end_day_exclusive=version["period_end_day_exclusive"],state="proposed",qty=qty,
                release_day=slot[0],available_day=slot[1],original_proposal_id=proposal.proposal_id,
                original_release_day=proposal.release_day,original_available_day=proposal.available_day,
                source_budgets=audit,campaign_id="",executed_qty=0.0)
        return None

    def _bom(self,pair):
        return self.bom_by_pair[pair]

    def accept(self,row):
        pair=(row["node_id"],row["item_id"])
        if pair in self.rows:raise ValueError("A process can be promoted only once in this pilot")
        self.rows[pair]=dict(row);self.events.append(dict(row,event="proposed",day=row["decision_day"]))

    def engage(self,pair,day,campaign_id):
        row=self.rows[pair]
        if (row["state"]!="proposed" or not campaign_id or day!=row["decision_day"]
                or day!=row["release_day"]):raise ValueError("Programme handoff requires a real campaign at the decision instant")
        row.update(state="engaged",campaign_id=campaign_id);self.events.append(dict(row,event="engaged",day=day))

    def execute(self,pair,day,campaign_id,qty):
        row=self.rows.get(pair)
        if row is None or row["state"]!="engaged" or row["campaign_id"]!=campaign_id:return
        if qty<0 or row["executed_qty"]+qty>row["qty"]+1e-6:raise ValueError("Programme execution exceeds its original lot")
        row["executed_qty"]+=qty
        if abs(row["executed_qty"]-row["qty"])<=1e-6:row.update(state="executed",executed_qty=row["qty"])
        self.events.append(dict(row,event="execution",day=day,executed_today_qty=qty))



@dataclass(frozen=True)
class IndustrialPlanningWindow:
    period_start_day: int
    first_day: int
    end_day_exclusive: int
    qty: float
    known_day: int
    source_file: str
    source_cells: str


class IndustrialComponentPlanningCalendar:
    """Total industrial forecasts used only for planning, never physical demand.

    Complete supplied weeks include explicit zero. Unprovided weeks remain
    absent. Current weeks freeze the preceding vintage; future weeks use the
    latest vintage actually known at the decision. Fractional UN forecasts are
    legitimate here: the physical external-use calendar is separate.
    """

    def __init__(self, payload, *, pair_uoms: Mapping, origin_date: str,
                 missing_period_policy: str | None = None):
        if missing_period_policy not in (None, "last_known_period_v1"):
            raise ValueError("Industrial planning missing-period policy must be explicit last_known_period_v1")
        self.missing_period_policy = missing_period_policy
        if (not isinstance(payload, dict)
                or set(payload) != {"schema_version", "origin", "scenario_id", "semantics", "versioned_series"}
                or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                or payload["origin"] != origin_date
                or payload["semantics"] != "industrial_total_gross_requirements_planning_only"
                or not isinstance(payload["scenario_id"], str) or not payload["scenario_id"].strip()
                or not isinstance(payload["versioned_series"], list) or not payload["versioned_series"]):
            raise ValueError("Industrial planning requires explicit total-forecast schema1 and matching origin")
        self._series = {}
        self._period_versions = {}
        for series in payload["versioned_series"]:
            pair = (series.get("node_id"), series.get("item_id"))
            if (pair not in pair_uoms or pair in self._series or series.get("uom") != pair_uoms[pair]
                    or series.get("repeat_period_days") != 0 or series.get("period_days") != 7
                    or series.get("period_anchor_day") != 4
                    or series.get("current_bucket_policy") != "freeze_previous_exclude_current_vintage"
                    or series.get("missing_future_policy") != "unprovided_not_observed_zero"):
                raise ValueError("Industrial planning series requires a unique modeled pair and dated non-repeating weeks")
            versions, days = [], set()
            if not isinstance(series.get("versions"), list) or not series["versions"]:
                raise ValueError("Industrial planning requires explicit vintages")
            for version in series["versions"]:
                known = version.get("known_day")
                if type(known) is not int or not 0 <= known < 365 or known in days or not isinstance(version.get("rows"), list):
                    raise ValueError("Industrial planning vintages require unique year-one knowledge dates")
                days.add(known)
                periods = {}
                for row in version["rows"]:
                    start = row.get("period_start_day")
                    if (type(start) is not int or not known < start <= known + 364
                            or (start - 4) % 7 or row.get("period_days") != 7 or start in periods):
                        raise ValueError("Industrial forecast weeks must be future Sundays inside the known 52-week horizon")
                    quantity = _number(row.get("qty"), "industrial total forecast")
                    if quantity < 0 or any(not isinstance(row.get(k), str) or not row[k].strip()
                                           for k in ("source_file", "source_cells")):
                        raise ValueError("Industrial forecasts require nonnegative quantities and cell provenance")
                    periods[start] = dict(row, qty=quantity)
                versions.append((known, periods))
            versions.sort(key=lambda entry: entry[0])
            self._series[pair] = ([known for known, _ in versions], versions)
            # Index each supplied period separately. A later omission must not
            # erase an older forecast in the opt-in policy; an explicit zero can.
            by_period = defaultdict(list)
            if missing_period_policy == "last_known_period_v1":
                for known, periods in versions:
                    for start, row in periods.items():
                        by_period[start].append((known, row))
            self._period_versions[pair] = {
                start: ([known for known, _ in rows], rows)
                for start, rows in by_period.items()
            }
        self.pairs = tuple(sorted(self._series))

    def windows(self, pair, *, decision_day: int, first_day: int, through_day: int):
        if (any(type(day) is not int for day in (decision_day, first_day, through_day))
                or first_day <= decision_day or through_day < first_day):
            raise ValueError("Industrial planning windows must be explicitly future at the decision")
        known_days, versions = self._series[pair]
        result = []
        first_period = 4 + ((first_day - 4) // 7) * 7
        for start in range(first_period, through_day + 1, 7):
            cutoff = min(decision_day, start - 1)
            index = bisect_right(known_days, cutoff) - 1
            row = versions[index][1].get(start) if index >= 0 else None
            selected_known = versions[index][0] if index >= 0 else None
            if row is None and self.missing_period_policy == "last_known_period_v1":
                period_days, period_rows = self._period_versions[pair].get(start, ((), ()))
                period_index = bisect_right(period_days, cutoff) - 1
                if period_index >= 0:
                    selected_known, row = period_rows[period_index]
            if row is None:
                continue
            first, end = max(start, first_day), min(start + 7, through_day + 1)
            qty = float(Decimal(str(row["qty"])) * Decimal(end - first) / Decimal(7))
            result.append(IndustrialPlanningWindow(start, first, end, qty,
                selected_known, row["source_file"], row["source_cells"]))
        return tuple(result)


def industrial_forecast_missing_policy(revision_policy, legacy_missing_policy):
    """Select a whole known MRP vintage, independently of customer forecasts.

    A missing week in a newer plan is not permission to resurrect an older
    industrial requirement: it may have moved. Keep it unknown (BOM/other-use
    fallback), not an invented observed zero. The ongoing week still uses
    the last vintage known before that week, as the calendar already does.
    """
    if revision_policy is None:
        return legacy_missing_policy
    if revision_policy != "latest_vintage_v1":
        raise ValueError("Unknown industrial forecast revision policy")
    return None


@dataclass(frozen=True)
class UnreportedPlanningWindow:
    """Scenario coverage, never a source cell with an observed zero quantity."""
    period_start_day: int
    first_day: int
    end_day_exclusive: int
    known_day: int
    declared_first_period_day: int
    declared_last_period_day: int
    coverage_source_file: str
    coverage_source_cells: str


class IndustrialPlanningHorizonCoverage:
    """Known global versions bound an explicit event-export interpretation.

    Actual I cells remain in the original calendar. A missing pair in a global
    vintage stays unknown, even when an older local version exists.
    """

    def __init__(self, payload, *, calendar, eligible_pairs, origin_date):
        fields = {"schema_version", "origin", "semantics", "rows"}
        if (not isinstance(payload, dict) or set(payload) != fields
                or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                or payload["origin"] != origin_date
                or payload["semantics"] != "global_source_snapshot_week_bounds"
                or not isinstance(payload["rows"], list) or not payload["rows"]
                or calendar is None or calendar.missing_period_policy is not None):
            raise ValueError("Exclusive horizon requires explicit global versions and latest-vintage source calendar")
        self.calendar = calendar
        self.eligible_pairs = frozenset(eligible_pairs)
        if not self.eligible_pairs or not self.eligible_pairs <= set(calendar.pairs):
            raise ValueError("Exclusive horizon requires known local industrial pairs")
        expected = {"known_day", "first_period_start_day", "last_period_start_day", "period_days",
                    "source_file", "source_cells", "present_pairs"}
        self.rows, seen = [], set()
        for raw in payload["rows"]:
            if (not isinstance(raw, dict) or set(raw) != expected
                    or any(type(raw[k]) is not int for k in ("known_day", "first_period_start_day", "last_period_start_day", "period_days"))
                    or not 0 <= raw["known_day"] < 365 or raw["known_day"] in seen
                    or (raw["known_day"] - 4) % 7
                    or raw["first_period_start_day"] != raw["known_day"]
                    or raw["last_period_start_day"] != raw["known_day"] + 364 or raw["period_days"] != 7
                    or any(not isinstance(raw[k], str) or not raw[k].strip() for k in ("source_file", "source_cells"))
                    or not isinstance(raw["present_pairs"], list)):
                raise ValueError("Global MRP horizon requires unique Sunday versions, 53 week starts and provenance")
            present = set()
            for pair_row in raw["present_pairs"]:
                if not isinstance(pair_row, dict) or set(pair_row) != {"node_id", "item_id"}:
                    raise ValueError("Global presence requires explicit article/site identities")
                pair = pair_row["node_id"], pair_row["item_id"]
                if (pair not in self.eligible_pairs or pair in present
                        or raw["known_day"] not in calendar._series[pair][0]):
                    raise ValueError("Declared pair presence must match a unique known local source version")
                present.add(pair)
            seen.add(raw["known_day"])
            self.rows.append(dict(raw, present_pairs=frozenset(present)))
        self.rows.sort(key=lambda r: r["known_day"])
        self.known_days = tuple(r["known_day"] for r in self.rows)
        if any(not set(calendar._series[pair][0]) <= seen for pair in self.eligible_pairs):
            raise ValueError("Global coverage cannot omit a known local source vintage")

    def select(self, pair, *, decision_day, first_day, through_day):
        """Return actual cells and separately assumed unreported intervals."""
        if pair not in self.eligible_pairs:
            raise ValueError("Exclusive source horizon pair is outside its explicit scope")
        original = self.calendar.windows(pair, decision_day=decision_day,
            first_day=first_day, through_day=through_day)
        actual_by_period = {w.period_start_day: w for w in original}
        actual, unreported = [], []
        first_period = 4 + ((first_day - 4) // 7) * 7
        for start in range(first_period, through_day + 1, 7):
            index = bisect_right(self.known_days, min(decision_day, start - 1)) - 1
            if index < 0:
                continue
            row = self.rows[index]
            if (pair not in row["present_pairs"]
                    or not row["first_period_start_day"] <= start <= row["last_period_start_day"]):
                continue
            window = actual_by_period.get(start)
            if window is not None:
                if window.known_day != row["known_day"]:
                    raise ValueError("Global and local industrial vintage selection disagree")
                actual.append(window)
            else:
                unreported.append(UnreportedPlanningWindow(start, max(start, first_day),
                    min(start + 7, through_day + 1), row["known_day"],
                    row["first_period_start_day"], row["last_period_start_day"],
                    row["source_file"], row["source_cells"]))
        return tuple(actual), tuple(unreported)


def exclude_unreported_revocable_requirements(requirements, windows, *, decision_day):
    """Apply only a declared scenario interpretation; retain all commitments."""
    original, windows = tuple(requirements), tuple(windows)
    _audit_separate_own_and_other(original, (), decision_day=decision_day)
    covered, audits = set(), []
    committed_prefixes = ("campaign:", "opening-pack:", "opening_production:")
    for window in windows:
        days = set(range(window.first_day, window.end_day_exclusive))
        if (window.known_day > decision_day or window.first_day <= decision_day
                or not window.period_start_day <= window.first_day < window.end_day_exclusive <= window.period_start_day + 7
                or not window.declared_first_period_day <= window.period_start_day <= window.declared_last_period_day
                or covered & days):
            raise ValueError("Unreported scenario coverage requires disjoint known future intervals")
        covered.update(days)
        rows = [r for r in original if r.due_day in days]
        committed = [r for r in rows if r.requirement_id.startswith(committed_prefixes)]
        reserves = [r for r in rows if r.requirement_id.startswith("reserve:")]
        removed = [r for r in rows if not r.requirement_id.startswith((*committed_prefixes, "reserve:"))]
        qty = lambda values: float(sum((Fraction(str(r.qty)) for r in values), Fraction(0)))
        audits.append(dict(period_start_day=window.period_start_day, first_day=window.first_day,
            end_day_exclusive=window.end_day_exclusive, source_vintage_day=window.known_day,
            declared_first_period_day=window.declared_first_period_day,
            declared_last_period_day=window.declared_last_period_day,
            coverage_source_file=window.coverage_source_file, coverage_source_cells=window.coverage_source_cells,
            status="unreported_week_assumed_no_revocable_need_not_observed_zero",
            before_qty=qty(rows), removed_revocable_qty=qty(removed), preserved_committed_qty=qty(committed),
            preserved_reserve_qty=qty(reserves), after_qty=qty(committed + reserves),
            removed_requirements=[[r.requirement_id, r.due_day, r.qty] for r in removed],
            preserved_requirements=[[r.requirement_id, r.due_day, r.qty] for r in committed],
            reserve_requirements=[[r.requirement_id, r.due_day, r.qty] for r in reserves]))
    retained = [r for r in original if r.due_day not in covered
                or r.requirement_id.startswith((*committed_prefixes, "reserve:"))]
    return retained, audits


def _reconcile_industrial_covered_horizon(requirements, windows, *, pair, decision_day):
    """Candidate volume reconciliation over supplied future dates only.

    This assumes industrial needs and own BOM describe overlapping uses over
    the covered horizon, despite their different weekly timing. It cannot
    establish that assumption: an early industrial need may be offset by a
    late BOM need. Keep that limitation visible in the opt-in scenario.
    """
    original = tuple(requirements)
    if len({row.requirement_id for row in original}) != len(original):
        raise ValueError("Covered-horizon reconciliation requires unique requirement identities")
    windows = sorted(windows, key=lambda row: (row.first_day, row.period_start_day))
    covered, periods, records = set(), set(), []
    zero = Decimal(0)
    for window in windows:
        if (any(type(day) is not int for day in (decision_day, window.known_day,
                window.period_start_day, window.first_day, window.end_day_exclusive))
                or window.known_day > decision_day
                or not window.period_start_day <= window.first_day < window.end_day_exclusive <= window.period_start_day + 7
                or window.first_day <= decision_day
                or window.period_start_day in periods):
            raise ValueError("Covered-horizon reconciliation requires known, unique, future source windows")
        dates = set(range(window.first_day, window.end_day_exclusive))
        if covered & dates:
            raise ValueError("Covered-horizon reconciliation requires disjoint source windows")
        covered.update(dates)
        periods.add(window.period_start_day)
        source = Decimal(str(window.qty))
        rows = [row for row in original if row.due_day in dates]
        amounts = [Decimal(str(row.qty)) for row in rows]
        if (not source.is_finite() or source < 0
                or any(not quantity.is_finite() or quantity < 0 for quantity in amounts)):
            raise ValueError("Covered-horizon reconciliation requires nonnegative finite quantities")
        own = sum((qty for row, qty in zip(rows, amounts)
                   if not row.requirement_id.startswith("external:")), zero)
        prior_extra = sum((qty for row, qty in zip(rows, amounts)
                           if row.requirement_id.startswith("external:")), zero)
        records.append((window, source, own, prior_extra, max(zero, source - own)))
    source_total = sum((row[1] for row in records), zero)
    own_total = sum((row[2] for row in records), zero)
    complement_total = max(zero, source_total - own_total)
    weekly_complement_total = sum((row[4] for row in records), zero)
    cumulative_weight, allocated = zero, zero
    added, audits = [], []
    for window, source, own, prior_extra, weight in records:
        cumulative_weight += weight
        # Cumulative allocation avoids independently rounded weekly budgets.
        # Fractional forecasts, including UN, remain forecasts, not movements.
        through = (complement_total * cumulative_weight / weekly_complement_total
                   if weekly_complement_total else zero)
        complement, allocated = through - allocated, through
        length = window.end_day_exclusive - window.first_day
        for offset, due in enumerate(range(window.first_day, window.end_day_exclusive)):
            quantity = complement * Decimal(offset + 1) / length - complement * Decimal(offset) / length
            if quantity > 0:
                added.append(Requirement(f"external:industrial-planning:{pair[0]}:{pair[1]}:W{window.period_start_day}:D{due}",
                                         due, float(quantity)))
        audits.append(dict(period_start_day=window.period_start_day, first_day=window.first_day,
            end_day_exclusive=window.end_day_exclusive, known_day=window.known_day,
            source_file=window.source_file, source_cells=window.source_cells,
            source_qty=float(source), own_qty=float(own), reconstructed_external_qty=float(prior_extra),
            complement_qty=float(complement), planning_qty=float(own + complement),
            source_excess_own_qty=float(max(zero, own - source)),
            weekly_complement_before_netting_qty=float(weight),
            temporal_overlap_removed_qty=float(weight - complement)))
    # Identity, quantity and date of every own need remain intact. Unknown
    # source dates, due/backlogged uses and their old estimates are untouched.
    preserved = [row for row in original
                 if not (row.requirement_id.startswith("external:") and row.due_day in covered)]
    return preserved + added, audits


def _reconcile_industrial_cumulative_envelope(requirements, windows, *, pair, decision_day):
    """Candidate common-use envelope; planned BOM can advance, never recede.

    This does not identify the real uses behind a source total. FIFO matches
    industrial forecasts to the earliest own BOM first, then to other uses.
    Physical BOM withdrawals, reservations and firm receipts are not changed.
    Fractions keep all prefix and allocation budgets exact before CSV floats.
    """
    original = tuple(requirements)
    if len({row.requirement_id for row in original}) != len(original):
        raise ValueError("Cumulative reconciliation requires unique requirement identities")
    windows = sorted(windows, key=lambda row: (row.first_day, row.period_start_day))
    by_day, periods, audits = {}, set(), []
    zero = Fraction(0)
    for window in windows:
        if (any(type(day) is not int for day in (decision_day, window.known_day,
                window.period_start_day, window.first_day, window.end_day_exclusive))
                or window.known_day > decision_day
                or not window.period_start_day <= window.first_day < window.end_day_exclusive <= window.period_start_day + 7
                or window.first_day <= decision_day or window.period_start_day in periods):
            raise ValueError("Cumulative reconciliation requires known, unique, future source windows")
        dates = range(window.first_day, window.end_day_exclusive)
        if any(day in by_day for day in dates):
            raise ValueError("Cumulative reconciliation requires disjoint source windows")
        if not isfinite(window.qty) or window.qty < 0:
            raise ValueError("Cumulative reconciliation requires nonnegative finite quantities")
        source = Fraction(str(window.qty))
        own_rows = [row for row in original if row.due_day in dates
                    and not row.requirement_id.startswith(("external:", "reserve:"))]
        external_rows = [row for row in original if row.due_day in dates
                         and row.requirement_id.startswith("external:")]
        if any(type(row.due_day) is not int or not isfinite(row.qty) or row.qty < 0
               for row in own_rows + external_rows):
            raise ValueError("Cumulative reconciliation requires nonnegative finite dated quantities")
        own = sum((Fraction(str(row.qty)) for row in own_rows), zero)
        prior_extra = sum((Fraction(str(row.qty)) for row in external_rows), zero)
        index = len(audits)
        for day in dates:
            by_day[day] = (index, source / len(dates))
        periods.add(window.period_start_day)
        audits.append(dict(period_start_day=window.period_start_day, first_day=window.first_day,
            end_day_exclusive=window.end_day_exclusive, known_day=window.known_day,
            source_file=window.source_file, source_cells=window.source_cells,
            source_qty=source, own_qty=own, reconstructed_external_qty=prior_extra,
            complement_qty=zero, planning_qty=zero,
            source_excess_own_qty=max(zero, own - source),
            weekly_complement_before_netting_qty=max(zero, source - own),
            own_planned_qty=zero, own_advanced_qty=zero,
            original_own_requirements=tuple(own_rows), own_planning_allocations=[]))
    own_rows = sorted((row for audit in audits for row in audit["original_own_requirements"]),
                      key=lambda row: (row.due_day, row.requirement_id))
    own_by_day = defaultdict(Fraction)
    for row in own_rows:
        own_by_day[row.due_day] += Fraction(str(row.qty))
    # Zero needs retain their identity without participating in FIFO funding.
    queue = deque((row, Fraction(str(row.qty))) for row in own_rows if row.qty > 0)
    added = []
    cumulative_source = cumulative_own = envelope = zero
    for day, (index, source) in sorted(by_day.items()):
        cumulative_source += source
        cumulative_own += own_by_day[day]
        next_envelope = max(cumulative_source, cumulative_own)
        quantity = next_envelope - envelope
        envelope = next_envelope
        audit = audits[index]
        audit["planning_qty"] += quantity
        while quantity and queue:
            own, remaining = queue.popleft()
            take = min(quantity, remaining)
            if day > own.due_day:
                raise ValueError("Cumulative reconciliation must never defer an own need")
            identity = f"industrial-envelope-own:{own.requirement_id}:D{day}"
            added.append(Requirement(identity, day, float(take)))
            audit["own_planned_qty"] += take
            if day < own.due_day:
                audit["own_advanced_qty"] += take
            audit["own_planning_allocations"].append(dict(requirement_id=own.requirement_id,
                original_due_day=own.due_day, planned_day=day, qty=float(take)))
            quantity -= take
            remaining -= take
            if remaining:
                queue.appendleft((own, remaining))
        if quantity:
            added.append(Requirement(
                f"external:industrial-envelope:{pair[0]}:{pair[1]}:D{day}", day, float(quantity)))
            audit["complement_qty"] += quantity
    if queue:
        raise ValueError("Cumulative reconciliation must preserve every own quantity")
    preserved = [row for row in original if row.due_day not in by_day
                 or row.requirement_id.startswith("reserve:")
                 or (row.qty == 0 and not row.requirement_id.startswith("external:"))]
    result = preserved + added
    if len({row.requirement_id for row in result}) != len(result):
        raise ValueError("Cumulative reconciliation generated a conflicting requirement identity")
    for audit in audits:
        for field, value in audit.items():
            if isinstance(value, Fraction):
                audit[field] = float(value)
    return result, audits


def _audit_separate_own_and_other(requirements, windows, *, decision_day):
    """Keep existing dated uses; a total industrial forecast is not another use.

    Existing external-use estimates are preserved, not certified as observed.
    Source windows only supply comparison evidence. Their absence does not
    assert zero, and their explicit zero cannot erase an independently supplied
    own/other requirement. Reserves remain untouched and outside usage totals.
    """
    original = tuple(requirements)
    if (type(decision_day) is not int
            or any(not isinstance(row.requirement_id, str) or not row.requirement_id.strip()
                   or type(row.due_day) is not int or isinstance(row.qty, bool)
                   or not isinstance(row.qty, (int, float)) or not isfinite(row.qty) or row.qty < 0
                   for row in original)
            or len({row.requirement_id for row in original}) != len(original)):
        raise ValueError("Separate uses require unique identities and finite nonnegative dated quantities")
    covered, periods, audits = set(), set(), []
    zero = Decimal(0)
    for window in windows:
        if (any(type(day) is not int for day in (window.known_day, window.period_start_day,
                window.first_day, window.end_day_exclusive))
                or window.known_day > decision_day
                or not window.period_start_day <= window.first_day < window.end_day_exclusive <= window.period_start_day + 7
                or window.first_day <= decision_day or window.period_start_day in periods
                or any(not isinstance(value, str) or not value.strip()
                       for value in (window.source_file, window.source_cells))):
            raise ValueError("Separate uses require known, unique, future source windows with provenance")
        dates = set(range(window.first_day, window.end_day_exclusive))
        if covered & dates:
            raise ValueError("Separate uses require disjoint source windows")
        if (isinstance(window.qty, bool) or not isinstance(window.qty, (int, float))
                or not isfinite(window.qty) or window.qty < 0):
            raise ValueError("Separate uses require nonnegative finite source quantities")
        covered.update(dates)
        periods.add(window.period_start_day)
        rows = [row for row in original if row.due_day in dates]
        source = Decimal(str(window.qty))
        own = sum((Decimal(str(row.qty)) for row in rows
                   if not row.requirement_id.startswith(("external:", "reserve:"))), zero)
        other = sum((Decimal(str(row.qty)) for row in rows
                     if row.requirement_id.startswith("external:")), zero)
        old_complement = max(zero, source - own)
        audits.append(dict(period_start_day=window.period_start_day, first_day=window.first_day,
            end_day_exclusive=window.end_day_exclusive, known_day=window.known_day,
            source_file=window.source_file, source_cells=window.source_cells,
            source_qty=float(source), own_qty=float(own), reconstructed_external_qty=float(other),
            complement_qty=float(other), planning_qty=float(own + other),
            source_excess_own_qty=float(max(zero, own - source)),
            weekly_complement_before_netting_qty=float(old_complement),
            # Signed comparison, not a physical removed quantity: a genuinely
            # separate estimate may exceed the old inferred residual.
            complement_delta_qty=float(old_complement - other)))
    return list(original), audits


def _conserved_weekly_forecast_parts(budget, days):
    """Publish float forecast parts whose decimal representations conserve budget.

    A repeated nearest float can exceed a whole-unit budget by 1e-15 and
    incorrectly order another unit. Keep that rounding residue in the final
    forecast day; this never rounds a physical stock or movement.
    """
    days = tuple(days)
    budget = Fraction(budget)
    if budget < 0 or not days:
        raise ValueError("Forecast distribution requires a nonnegative budget and dated days")
    if not budget:
        return ()
    share = budget / len(days)
    base = float(share)
    if Fraction(str(base)) > share:
        base = nextafter(base, 0.0)
    rows = [(day, base) for day in days[:-1] if base > 0]
    remaining = budget - sum((Fraction(str(qty)) for _, qty in rows), Fraction(0))
    for _ in range(8):
        if not remaining:
            return tuple(rows)
        quantity = float(remaining)
        if Fraction(str(quantity)) > remaining:
            quantity = nextafter(quantity, 0.0)
        represented = Fraction(str(quantity))
        if not 0 < represented <= remaining:
            raise ValueError("Forecast residue cannot be represented without losing its budget")
        rows.append((days[-1], quantity))
        remaining -= represented
    raise ValueError("Forecast residue exceeded the exact publication bound")


def reconcile_industrial_purchase_envelope(requirements, windows, omitted_windows, *, pair, decision_day):
    """Merge dated programmes after a documented FIFO committed-volume match.

    This candidate does not identify industrial OFs. Committed requirements
    stay on their original dates even if their matching I budget is earlier;
    that timing mismatch is disclosed. Every revocable model requirement is
    covered no later than its original date. Reserves never fund an I budget.
    """
    original, windows, omitted_windows = tuple(requirements), tuple(windows), tuple(omitted_windows)
    _, audits = _audit_separate_own_and_other(original, windows, decision_day=decision_day)
    exclude_unreported_revocable_requirements((), omitted_windows, decision_day=decision_day)
    actual_days = {d for w in windows for d in range(w.first_day,w.end_day_exclusive)}
    omitted_days = {d for w in omitted_windows for d in range(w.first_day,w.end_day_exclusive)}
    if actual_days & omitted_days:
        raise ValueError("Cumulative source programme cannot duplicate actual and assumed coverage")
    covered = actual_days | omitted_days
    if covered and len(covered) != max(covered)-min(covered)+1:
        raise ValueError("Cumulative programme requires continuous declared horizon coverage")
    committed_prefixes = ("campaign:","opening-pack:","opening_production:")
    committed = sorted((r for r in original if r.due_day in covered and r.requirement_id.startswith(committed_prefixes)),
                       key=lambda r:(r.due_day,r.requirement_id))
    revocable = sorted((r for r in original if r.due_day in covered
                       and not r.requirement_id.startswith((*committed_prefixes,"reserve:"))),
                       key=lambda r:(r.due_day,r.requirement_id))
    zero=Fraction(0)
    source_by_day=defaultdict(Fraction)
    for window in windows:
        for day,qty in _conserved_weekly_forecast_parts(Fraction(str(window.qty)),range(window.first_day,window.end_day_exclusive)):
            source_by_day[day]+=Fraction(str(qty))
    firm_queue=deque((r,Fraction(str(r.qty))) for r in committed if r.qty>0)
    source_remaining=defaultdict(Fraction)
    firm_allocations=[]
    later_assigned=zero
    for day,amount in sorted(source_by_day.items()):
        while amount and firm_queue:
            row,left=firm_queue.popleft()
            taken=min(left,amount)
            firm_allocations.append([row.requirement_id,row.due_day,day,str(taken)])
            if row.due_day>day:later_assigned+=taken
            left-=taken;amount-=taken
            if left:firm_queue.appendleft((row,left))
        source_remaining[day]=amount
    own_by_day=defaultdict(Fraction)
    committed_by_day=defaultdict(Fraction)
    for row in revocable:own_by_day[row.due_day]+=Fraction(str(row.qty))
    for row in committed:committed_by_day[row.due_day]+=Fraction(str(row.qty))
    queue=deque((r,Fraction(str(r.qty))) for r in revocable if r.qty>0)
    cumulative_source=cumulative_remaining=cumulative_own=cumulative_committed=envelope=zero
    added=[];allocations=[];points=[];complement_by_day=defaultdict(Fraction)
    advanced_by_day=defaultdict(Fraction)
    planned_model_by_day=defaultdict(Fraction)
    counters=defaultdict(int)
    def publish(identity,day,amount):
        for _,quantity in _conserved_weekly_forecast_parts(amount,(day,)):
            key=identity,day;counters[key]+=1
            suffix=f":part{counters[key]}" if counters[key]>1 else ""
            added.append(Requirement(f"{identity}:D{day}{suffix}",day,quantity))
    for day in sorted(covered):
        cumulative_source+=source_by_day[day]
        cumulative_remaining+=source_remaining[day]
        cumulative_own+=own_by_day[day]
        cumulative_committed+=committed_by_day[day]
        next_envelope=max(cumulative_remaining,cumulative_own)
        increment=next_envelope-envelope;envelope=next_envelope
        while increment and queue:
            row,left=queue.popleft();taken=min(increment,left)
            if day>row.due_day:
                raise ArithmeticError("Cumulative programme must not defer a model requirement")
            prefix="external:" if row.requirement_id.startswith("external:") else ""
            publish(f"{prefix}industrial-purchase-envelope:{row.requirement_id}",day,taken)
            allocations.append([row.requirement_id,row.due_day,day,str(taken)])
            planned_model_by_day[day]+=taken
            if day<row.due_day:advanced_by_day[day]+=taken
            left-=taken;increment-=taken
            if left:queue.appendleft((row,left))
        if increment:
            publish(f"external:industrial-purchase-envelope-complement:{pair[0]}:{pair[1]}",day,increment)
            complement_by_day[day]+=increment
        points.append([day,str(cumulative_source),str(cumulative_committed),str(cumulative_own),
            str(cumulative_remaining),str(envelope),str(cumulative_committed+envelope),
            str(max(zero,cumulative_source-cumulative_committed-envelope))])
    if queue:
        raise ArithmeticError("Cumulative programme must cover every revocable model quantity")
    retained=[r for r in original if r.due_day not in covered
              or r.requirement_id.startswith((*committed_prefixes,"reserve:")) or r.qty==0]+added
    if len({r.requirement_id for r in retained})!=len(retained):
        raise ValueError("Cumulative purchase programme generated duplicate identities")
    for audit in audits:
        days=range(audit["first_day"],audit["end_day_exclusive"])
        e=sum((committed_by_day[d] for d in days),zero)
        own=sum((planned_model_by_day[d] for d in days),zero)
        extra=sum((complement_by_day[d] for d in days),zero)
        audit.update(committed_qty=float(e),own_planned_qty=float(e+own),complement_qty=float(extra),
            planning_qty=float(e+own+extra),own_advanced_qty=float(sum((advanced_by_day[d] for d in days),zero)),
            complement_delta_qty=audit["weekly_complement_before_netting_qty"]-float(extra))
    qty=lambda rows:sum((Fraction(str(r.qty)) for r in rows),zero)
    source_total=sum(source_by_day.values(),zero)
    assigned=source_total-sum(source_remaining.values(),zero)
    audit=dict(policy="declared_horizon_cumulative_max_after_committed_fifo_v1",covered_days=len(covered),
        source_qty=str(source_total),committed_qty=str(qty(committed)),revocable_qty=str(qty(revocable)),
        source_assigned_committed_qty=str(assigned),source_assigned_later_committed_qty=str(later_assigned),
        source_residual_qty=str(source_total-assigned),envelope_revocable_qty=str(envelope),
        retained_requirement_qty=str(qty(committed)+envelope),
        source_windows=[[w.period_start_day,w.first_day,w.end_day_exclusive,w.qty,w.known_day,w.source_file,w.source_cells] for w in windows],
        omitted_windows=[[w.period_start_day,w.first_day,w.end_day_exclusive,w.known_day,w.declared_first_period_day,
                          w.declared_last_period_day,w.coverage_source_file,w.coverage_source_cells] for w in omitted_windows],
        original_requirements=[[r.requirement_id,r.due_day,r.qty] for r in original],
        output_requirements=[[r.requirement_id,r.due_day,r.qty] for r in retained],
        source_commitment_allocations=firm_allocations,revocable_allocations=allocations,cumulative_points=points)
    return retained,audits,audit


def reconcile_industrial_requirements(requirements, windows, *, pair, decision_day, policy=None):
    """Reconcile known forecasts; only the envelope policy advances planned BOM."""
    if policy is not None:
        if policy == "source_weekly_with_committed_floor_v1":
            original, windows = tuple(requirements), tuple(windows)
            _, audits = _audit_separate_own_and_other(original, windows, decision_day=decision_day)
            covered = set(); added=[]
            committed_prefixes=("campaign:","opening-pack:","opening_production:")
            for window,audit in zip(windows,audits):
                days=range(window.first_day,window.end_day_exclusive); covered.update(days)
                committed=sum((Fraction(str(r.qty)) for r in original if r.due_day in days
                    and r.requirement_id.startswith(committed_prefixes)),Fraction(0))
                residual=max(Fraction(0),Fraction(str(window.qty))-committed)
                day_parts = defaultdict(int)
                for day,quantity in _conserved_weekly_forecast_parts(residual, days):
                    day_parts[day] += 1
                    suffix = f":part{day_parts[day]}" if day_parts[day] > 1 else ""
                    added.append(Requirement(f"external:industrial-authoritative:{pair[0]}:{pair[1]}:W{window.period_start_day}:D{day}{suffix}",
                        day,quantity))
                audit.update(committed_qty=float(committed),complement_qty=float(residual),
                    planning_qty=float(committed+residual),
                    complement_delta_qty=audit["weekly_complement_before_netting_qty"]-float(residual))
            result=[r for r in original if r.due_day not in covered
                    or r.requirement_id.startswith((*committed_prefixes,"reserve:"))]+added
            if len({r.requirement_id for r in result})!=len(result):
                raise ValueError("Authoritative source planning generated a duplicate requirement identity")
            return result,audits
        if policy == "separate_own_and_other_v1":
            return _audit_separate_own_and_other(requirements, windows, decision_day=decision_day)
        if policy == "covered_cumulative_envelope_v1":
            return _reconcile_industrial_cumulative_envelope(requirements, windows, pair=pair, decision_day=decision_day)
        if policy != "covered_horizon_net_complement_v1":
            raise ValueError("Unknown industrial requirement reconciliation policy")
        return _reconcile_industrial_covered_horizon(requirements, windows, pair=pair, decision_day=decision_day)
    original, audits = tuple(requirements), []
    replaced, added, covered = set(), [], set()
    for window in windows:
        dates = set(range(window.first_day, window.end_day_exclusive))
        if window.first_day <= decision_day or covered & dates:
            raise ValueError("Industrial reconciliation requires disjoint future windows")
        covered.update(dates)
        rows = [row for row in original if row.due_day in dates]
        own = sum((Decimal(str(row.qty)) for row in rows if not row.requirement_id.startswith("external:")), Decimal(0))
        external = [row for row in rows if row.requirement_id.startswith("external:")]
        old_extra = sum((Decimal(str(row.qty)) for row in external), Decimal(0))
        total = Decimal(str(window.qty))
        complement = max(Decimal(0), total - own)
        replaced.update(row.requirement_id for row in external)
        length = window.end_day_exclusive - window.first_day
        for offset, due in enumerate(range(window.first_day, window.end_day_exclusive)):
            quantity = complement * Decimal(offset + 1) / length - complement * Decimal(offset) / length
            if quantity > 0:
                added.append(Requirement(f"external:industrial-planning:{pair[0]}:{pair[1]}:W{window.period_start_day}:D{due}", due, float(quantity)))
        audits.append(dict(period_start_day=window.period_start_day, first_day=window.first_day,
            end_day_exclusive=window.end_day_exclusive, known_day=window.known_day,
            source_file=window.source_file, source_cells=window.source_cells,
            source_qty=float(total), own_qty=float(own), reconstructed_external_qty=float(old_extra),
            complement_qty=float(complement), planning_qty=float(own + complement),
            source_excess_own_qty=float(max(Decimal(0), own - total))))
    reconciled = [row for row in original if row.requirement_id not in replaced] + added
    return reconciled, audits


@dataclass(frozen=True)
class ExternalComponentService:
    """Physical allocations to uses outside the modeled finished products."""

    allocations: tuple[Requirement, ...]
    remaining: tuple[Requirement, ...]
    demand_qty: float
    backlog_start_qty: float
    consumed_qty: float
    available_end_qty: float


def _component_quantity(value, *, uom: str, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field} must be a numeric component quantity")
    quantity = _number(value, field)
    if uom == "UN" and quantity != floor(quantity):
        raise ValueError(f"{field} must be integer for physical UN")
    return quantity


class ExternalComponentDemandCalendar:
    """One selected incremental scenario, never a sum of rolling MRP vintages.

    Weekly quantities are already net of the modeled product scope in the
    scenario estimator. This class neither derives them from stock nor subtracts
    a BOM again. Unprovided periods remain outside the declared scenario; they
    are not industrial observations of zero demand. Repeated years are synthetic.
    """

    def __init__(self, payload, *, pair_uoms: Mapping, origin_date: str, horizon_days: int):
        if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] not in (1, 2, 3):
            raise ValueError("External component demands require schema_version 1, 2 or 3")
        self.schema_version = payload["schema_version"]
        self.has_revisions = self.schema_version in (2, 3)
        if not self.has_revisions and "versioned_series" in payload:
            raise ValueError("Versioned external component demands require schema_version 2 or 3")
        if payload.get("origin") != origin_date:
            raise ValueError("External component demand origin must match the simulation")
        date.fromisoformat(origin_date)
        if type(horizon_days) is not int or horizon_days <= 0:
            raise ValueError("External component horizon must be a positive integer")
        self.scenario_id = payload.get("scenario_id")
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("External component scenario_id is required")
        if payload.get("semantics") != "incremental_non_modelled_component_use":
            raise ValueError("External component rows must describe incremental non-modeled uses")
        repeat = payload.get("repeat_period_days")
        if repeat is not None and (type(repeat) is not int or repeat != 365):
            raise ValueError("External component repetition must explicitly be 365 days or null")
        self.repeat_period_days = repeat
        self.horizon_days = horizon_days
        rows = payload.get("rows")
        if not isinstance(rows, list) or (not rows and not self.has_revisions):
            raise ValueError("External component rows must be a list, nonempty for schema 1")
        self.row_count = len(rows)
        self._daily: dict = defaultdict(list)
        self._provenance: dict = {}
        self._fixed_day_audit: dict = {}
        self._coverage_periods: dict = defaultdict(list)
        self._revision_series: dict = {}
        self._revision_identity: dict = {}
        self.version_count = 0
        intervals: dict = defaultdict(list)
        seen: set[str] = set()
        all_pairs = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("External component row must be an object")
            identity = row.get("demand_id")
            _identity(identity, seen, "external demand_id")
            pair = (row.get("node_id"), row.get("item_id"))
            uom = row.get("uom")
            if (any(not isinstance(part, str) or not part.strip() for part in pair)
                    or pair not in pair_uoms or not isinstance(uom, str) or not uom or pair_uoms[pair] != uom):
                raise ValueError("External demand must identify a modeled component with its exact unit")
            known, start, length = (row.get(k) for k in ("known_day", "period_start_day", "period_days"))
            if (any(type(day) is not int for day in (known, start, length))
                    or not 0 <= known <= start < 365 or not 1 <= length <= 7 or start + length > 365):
                raise ValueError("External component periods must lie in year one and be known by their start")
            if any(start < previous_end and previous_start < start + length
                   for previous_start, previous_end in intervals[pair]):
                raise ValueError("External component periods overlap; select one source plan rather than add vintages")
            intervals[pair].append((start, start + length))
            qty = _component_quantity(row.get("qty"), uom=uom, field="external component qty")
            for field in ("source_file", "source_cells", "estimation_basis"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"External component {field} is required")
            all_pairs.add(pair)
            cycles = range((horizon_days - 1) // repeat + 1) if repeat else range(1)
            total = Decimal(str(qty))
            # Difference of cumulative floors conserves each weekly UN total.
            cumulative = [Decimal(floor(total * i / length)) if uom == "UN" else total * i / length
                          for i in range(length + 1)]
            for cycle in cycles:
                shift = cycle * (repeat or 0)
                self._coverage_periods[pair].append((known + shift, start + shift, start + shift + length))
                for offset in range(length):
                    due_day = start + shift + offset
                    if due_day >= horizon_days:
                        continue
                    amount = float(cumulative[offset + 1] - cumulative[offset])
                    if self.has_revisions:
                        self._fixed_day_audit[(pair, due_day)] = {
                            "known_day": known + shift, "period_start_day": start + shift,
                            "source_file": row["source_file"], "source_cells": row["source_cells"],
                        }
                    if amount <= 0:
                        continue
                    requirement_id = f"external:{self.scenario_id}:{identity}:C{cycle}:D{due_day}"
                    requirement = Requirement(requirement_id, due_day, amount)
                    self._daily[pair].append((due_day, known + shift, requirement))
                    self._provenance[requirement_id] = {
                        "demand_id": identity, "scenario_id": self.scenario_id, "cycle_index": cycle,
                        "known_day": known + shift, "source_file": row["source_file"],
                        "source_cells": row["source_cells"], "estimation_basis": row["estimation_basis"],
                    }
        if self.has_revisions:
            self._load_revision_series(payload.get("versioned_series"), pair_uoms, all_pairs)
        self.versioned_pairs = tuple(sorted(self._revision_series))
        self.pairs = tuple(sorted(all_pairs))
        self._days = {}
        for pair, events in self._daily.items():
            events.sort(key=lambda event: (event[0], event[2].requirement_id))
            self._days[pair] = [event[0] for event in events]

    def _load_revision_series(self, series_rows, pair_uoms: Mapping, all_pairs: set) -> None:
        """Validate complete forecast vintages without treating omissions as data."""
        if not isinstance(series_rows, list) or not series_rows:
            raise ValueError("Revision schemas require nonempty versioned_series")
        for series in series_rows:
            if not isinstance(series, dict):
                raise ValueError("A versioned component series must be an object")
            pair = (series.get("node_id"), series.get("item_id"))
            uom = series.get("uom")
            if (any(not isinstance(part, str) or not part.strip() for part in pair)
                    or pair not in pair_uoms or not isinstance(uom, str) or not uom or pair_uoms[pair] != uom):
                raise ValueError("Versioned demand must identify a modeled component with its exact unit")
            if pair in all_pairs:
                raise ValueError("A component cannot have both fixed and versioned demand series")
            if (type(series.get("repeat_period_days")) is not int or series["repeat_period_days"] != 0
                    or type(series.get("period_anchor_day")) is not int or series["period_anchor_day"] != 4
                    or type(series.get("period_days")) is not int or series["period_days"] != 7):
                raise ValueError("Versioned component series requires no repetition, Sunday anchor 4 and seven-day periods")
            if (series.get("current_bucket_policy") != "freeze_previous_exclude_current_vintage"
                    or series.get("missing_future_policy") != "unprovided_not_observed_zero"):
                raise ValueError("Versioned component series must freeze current weeks and expose missing future periods")
            source_versions = series.get("versions")
            if not isinstance(source_versions, list) or not source_versions:
                raise ValueError("A versioned component series requires explicit vintages")
            versions, known_days, identities = [], set(), set()
            for version in source_versions:
                if not isinstance(version, dict):
                    raise ValueError("A component vintage must be an object")
                vintage_id, known = version.get("vintage_id"), version.get("known_day")
                _identity(vintage_id, identities, "component vintage_id")
                if type(known) is not int or not 0 <= known < 365 or known in known_days:
                    raise ValueError("Component vintage known_day must be unique and within year one")
                known_days.add(known)
                period_rows = version.get("rows")
                if not isinstance(period_rows, list):
                    raise ValueError("Component vintage rows must be an explicit list (possibly empty)")
                periods, row_ids = {}, set()
                for row in period_rows:
                    if not isinstance(row, dict):
                        raise ValueError("Component vintage row must be an object")
                    _identity(row.get("demand_id"), row_ids, "versioned demand_id")
                    start, length = row.get("period_start_day"), row.get("period_days")
                    if type(start) is not int or type(length) is not int or start in periods:
                        raise ValueError("Versioned periods require integer dates and unique weeks")
                    if self.schema_version == 3:
                        if not known < start <= known + 364 or (start - 4) % 7 != 0 or length != 7:
                            raise ValueError("Schema 3 periods must be future Sunday weeks within the known vintage's 52-week horizon")
                    elif not known < start < 365 or (start - 4) % 7 != 0 or length != min(7, 365 - start):
                        raise ValueError("Versioned periods must be unique future Sunday weeks, truncated only at year end")
                    qty = _component_quantity(row.get("qty"), uom=uom, field="versioned component qty")
                    for field in ("source_file", "source_cells", "estimation_basis"):
                        if not isinstance(row.get(field), str) or not row[field].strip():
                            raise ValueError(f"Versioned component {field} is required")
                    total = Decimal(str(qty))
                    cumulative = [Decimal(floor(total * i / length)) if uom == "UN" else total * i / length
                                  for i in range(length + 1)]
                    periods[start] = {**row, "daily_qty": tuple(float(cumulative[i + 1] - cumulative[i])
                                                               for i in range(length))}
                    for due_day in range(start, start + length):
                        identity = self._versioned_requirement_id(pair, start, due_day)
                        self._revision_identity[identity] = (pair, due_day)
                self.row_count += len(period_rows)
                versions.append({"vintage_id": vintage_id, "known_day": known, "periods": periods})
            versions.sort(key=lambda version: version["known_day"])
            self.version_count += len(versions)
            self._revision_series[pair] = {
                "versions": versions, "known_days": [version["known_day"] for version in versions],
            }
            all_pairs.add(pair)

    def _versioned_requirement_id(self, pair, period_start: int, due_day: int) -> str:
        # Forecast revisions change amounts, never the logical need's identity.
        return f"external:{self.scenario_id}:revision:{pair[0]}:{pair[1]}:W{period_start}:D{due_day}"

    def _revision_selection(self, pair, *, decision_day: int, due_day: int):
        period_start = 4 + ((due_day - 4) // 7) * 7
        series = self._revision_series[pair]
        as_of = min(decision_day, period_start - 1)
        index = bisect_right(series["known_days"], as_of) - 1
        version = series["versions"][index] if index >= 0 else None
        end = self.horizon_days if self.schema_version == 3 else 365
        row = version["periods"].get(period_start) if version is not None and 0 <= due_day < end else None
        return period_start, version, row

    def requirements(self, *, decision_day: int, first_day: int, through_day: int) -> dict:
        for value in (decision_day, first_day, through_day):
            _day(value, "external component query day")
        if decision_day < 0 or first_day < 0 or through_day < first_day:
            raise ValueError("Invalid external component query interval")
        result = {}
        for pair, events in self._daily.items():
            days = self._days[pair]
            selected = tuple(event[2] for event in events[bisect_left(days, first_day):bisect_right(days, through_day)]
                             if event[1] <= decision_day)
            if selected:
                result[pair] = selected
        for pair in self._revision_series:
            selected = []
            revision_end = self.horizon_days - 1 if self.schema_version == 3 else min(self.horizon_days - 1, 364)
            for due_day in range(first_day, min(through_day, revision_end) + 1):
                start, version, row = self._revision_selection(pair, decision_day=decision_day, due_day=due_day)
                if row is not None:
                    amount = row["daily_qty"][due_day - start]
                    if amount > 0:
                        selected.append(Requirement(self._versioned_requirement_id(pair, start, due_day), due_day, amount))
            if selected:
                result[pair] = tuple(selected)
        return result

    def covered_days(self, pair, *, decision_day: int, first_day: int, through_day: int) -> frozenset[int]:
        """Dates explicitly forecast in this snapshot, including declared zero.

        This uses exactly the causal vintage selection of requirements(). A
        missing week is not inferred from neighboring nonzero requirements.
        """
        for value in (decision_day, first_day, through_day):
            _day(value, "external component coverage day")
        if first_day <= decision_day or through_day < first_day:
            raise ValueError("Coverage requires a strictly future interval")
        stop = min(through_day, self.horizon_days - 1)
        if pair in self._revision_series:
            return frozenset(day for day in range(first_day, stop + 1)
                if self._revision_selection(pair, decision_day=decision_day, due_day=day)[2] is not None)
        return frozenset(day for known, start, end in self._coverage_periods.get(pair, ())
            if known <= decision_day for day in range(max(first_day, start), min(stop + 1, end)))

    def due(self, day: int) -> dict:
        return self.requirements(decision_day=day, first_day=day, through_day=day)

    def provenance(self, requirement_id: str) -> dict:
        if requirement_id in self._revision_identity:
            pair, due_day = self._revision_identity[requirement_id]
            _, version, row = self._revision_selection(pair, decision_day=due_day, due_day=due_day)
            if row is None:
                raise ValueError("No frozen physical demand exists for this versioned requirement")
            return {"demand_id": row["demand_id"], "scenario_id": self.scenario_id, "cycle_index": 0,
                    "vintage_id": version["vintage_id"], "known_day": version["known_day"],
                    "period_start_day": row["period_start_day"], "source_file": row["source_file"],
                    "source_cells": row["source_cells"], "estimation_basis": row["estimation_basis"],
                    "forecast_update_mode": "rolling_vintages_future_replacement_current_week_frozen"}
        return dict(self._provenance[requirement_id])

    def day_audit(self, pair, *, decision_day: int) -> dict:
        """Audit today's frozen need separately from the latest future forecast."""
        _day(decision_day, "external component audit day")
        if decision_day < 0 or pair not in self.pairs:
            raise ValueError("External component audit requires a modeled pair and nonnegative day")
        audit = {
            "forecast_selection_mode": "fixed_scenario", "forecast_vintage_id": "",
            "forecast_known_day": "", "forecast_latest_known_vintage_id": "",
            "forecast_latest_known_day": "", "forecast_period_start_day": "",
            "forecast_source_covered": 0, "forecast_coverage_reason": "unprovided_scenario_period",
            "forecast_source_file": "", "forecast_source_cells": "",
        }
        if pair not in self._revision_series:
            row = self._fixed_day_audit.get((pair, decision_day))
            if row is not None and row["known_day"] <= decision_day:
                audit.update(forecast_vintage_id="fixed", forecast_known_day=row["known_day"],
                             forecast_latest_known_vintage_id="fixed", forecast_latest_known_day=row["known_day"],
                             forecast_period_start_day=row["period_start_day"], forecast_source_covered=1,
                             forecast_coverage_reason="provided_scenario_period",
                             forecast_source_file=row["source_file"], forecast_source_cells=row["source_cells"])
            return audit
        start, version, row = self._revision_selection(pair, decision_day=decision_day, due_day=decision_day)
        series = self._revision_series[pair]
        latest_index = bisect_right(series["known_days"], decision_day) - 1
        latest = series["versions"][latest_index] if latest_index >= 0 else None
        audit.update(forecast_selection_mode="rolling_vintages_current_week_frozen",
                     forecast_period_start_day=start,
                     forecast_coverage_reason=("outside_revision_horizon" if decision_day >= (self.horizon_days if self.schema_version == 3 else 365)
                                               else "no_known_vintage_before_period" if version is None
                                               else "missing_period_in_selected_vintage"))
        if version is not None:
            audit.update(forecast_vintage_id=version["vintage_id"], forecast_known_day=version["known_day"])
        if latest is not None:
            audit.update(forecast_latest_known_vintage_id=latest["vintage_id"],
                         forecast_latest_known_day=latest["known_day"])
        if row is not None:
            audit.update(forecast_source_covered=1, forecast_coverage_reason="provided_scenario_period",
                         forecast_source_file=row["source_file"], forecast_source_cells=row["source_cells"])
        return audit


class ObservedExternalComponentExecution:
    """Realized other-product uses for a historical execution scenario only.

    Forecasts retain their own calendar. A supplied zero replaces the estimated
    physical use; an absent day leaves it intact. Rows become visible only on
    their execution day, so this object cannot reveal future observed demand.
    """

    def __init__(self, payload, *, pair_uoms, origin_date, horizon_days):
        if (not isinstance(payload, dict) or payload.get("schema_version") != 1
                or payload.get("repeat_period_days") is not None
                or payload.get("physical_use_only") is not True):
            raise ValueError("Observed uses require a non-repeating execution-only calendar")
        for row in payload.get("rows", ()):
            if row.get("period_days") != 1 or row.get("known_day") != row.get("period_start_day"):
                raise ValueError("Observed daily uses must become known on their execution day")
        self.calendar = ExternalComponentDemandCalendar(payload, pair_uoms=pair_uoms,
            origin_date=origin_date, horizon_days=horizon_days)
        self.pairs = self.calendar.pairs
        self._rows = {((row["node_id"], row["item_id"]), row["period_start_day"]): dict(row)
                      for row in payload["rows"]}

    def merge_due(self, day, estimated_due):
        _day(day, "observed execution day")
        result = dict(estimated_due)
        actual = self.calendar.due(day)
        for pair in self.pairs:
            if (pair, day) in self._rows:
                result[pair] = actual.get(pair, ())
        return result

    def provenance(self, requirement_id, forecast_calendar):
        try:
            detail = self.calendar.provenance(requirement_id)
        except KeyError:
            return {**forecast_calendar.provenance(requirement_id),
                    "physical_demand_source": "estimated_other_uses"}
        return {**detail, "physical_demand_source": "observed_other_uses"}

    def day_audit(self, pair, day):
        row = self._rows.get((pair, day))
        return {
            "physical_demand_source": "observed_other_uses" if row is not None else "estimated_other_uses",
            "physical_source_file": row["source_file"] if row is not None else "",
            "physical_source_cells": row["source_cells"] if row is not None else "",
            "physical_observation_qty": row["qty"] if row is not None else "",
            "physical_demand_known_day": row["known_day"] if row is not None else "",
        }


def serve_external_component_requirements(
    *, decision_day: int, available_qty: float, backlog: Iterable[Requirement],
    due: Iterable[Requirement], uom: str,
) -> ExternalComponentService:
    """Allocate only available stock, FIFO, without adding a finished product.

    Caller supplies stock after modeled production, excluding held/reserved
    quantities. The returned remainders retain their original identities/dates
    for tomorrow's execution and today's dated purchasing snapshot.
    """
    _day(decision_day, "external service day")
    if decision_day < 0 or not isinstance(uom, str) or not uom:
        raise ValueError("External service requires a nonnegative day and an explicit unit")
    available = Decimal(str(_component_quantity(available_qty, uom=uom, field="available stock")))
    pending, incoming = tuple(backlog), tuple(due)
    seen: set[str] = set()
    for row in pending + incoming:
        _identity(row.requirement_id, seen, "external remaining requirement")
        if not 0 <= _day(row.due_day, "external due day") <= decision_day:
            raise ValueError("Only current or overdue component demand can be physically consumed")
        _component_quantity(row.qty, uom=uom, field="remaining external demand")
    allocations, remaining = [], []
    for row in sorted(pending + incoming, key=lambda row: (row.due_day, row.requirement_id)):
        quantity = Decimal(str(row.qty))
        take = min(available, quantity)
        if take > 0:
            allocations.append(Requirement(row.requirement_id, row.due_day, float(take)))
        if quantity > take:
            remaining.append(Requirement(row.requirement_id, row.due_day, float(quantity - take)))
        available -= take
    return ExternalComponentService(
        tuple(allocations), tuple(remaining), fsum(row.qty for row in incoming),
        fsum(row.qty for row in pending), fsum(row.qty for row in allocations), float(available),
    )


@dataclass(frozen=True)
class FirmReceipt:
    receipt_id: str
    available_day: int
    qty: float
    state: str = "in_transit"


@dataclass(frozen=True)
class LotSizing:
    minimum: float = 0.0
    multiple: float = 0.0
    maximum: float | None = None
    integer: bool = False
    # Procurement decision precision, in the SAME unit as the needs. Zero
    # preserves historical exact netting; this never rounds physical stocks.
    net_rounding_quantum: float = 0.0


@dataclass(frozen=True)
class Allocation:
    requirement_id: str
    supply_id: str
    supply_kind: str
    qty: float
    due_day: int
    available_day: int
    delay_days: int


@dataclass(frozen=True)
class OrderProposal:
    proposal_id: str
    release_day: int
    available_day: int
    requested_day: int
    qty: float


@dataclass(frozen=True)
class ProjectedBalance:
    day: int
    requirement_qty: float
    firm_receipt_qty: float
    proposed_receipt_qty: float
    before_proposals_qty: float
    after_proposals_qty: float


@dataclass(frozen=True)
class ProcurementGroup:
    group_id: str
    first_requirement_day: int
    window_end_day_exclusive: int
    physical_net_qty: float
    reserve_net_qty: float
    net_requirement_qty: float
    proposed_qty: float
    requirement_ids: tuple[str, ...]
    proposal_ids: tuple[str, ...]


@dataclass(frozen=True)
class DatedPlan:
    decision_day: int
    opening_available_qty: float
    commitment_allocations: tuple[Allocation, ...]
    allocations: tuple[Allocation, ...]
    proposals: tuple[OrderProposal, ...]
    balances: tuple[ProjectedBalance, ...]
    late_qty: float
    late_qty_days: float
    firm_late_qty: float
    proposed_qty: float
    unallocated_firm_qty: float
    closing_projected_qty: float
    procurement_groups: tuple[ProcurementGroup, ...] = ()
    net_rounding_quantum: float = 0.0
    uncovered_requirements: tuple[Requirement, ...] = ()


class InternalTransferCommitments:
    """Experimental promises pegged to actual upstream campaign starts.

    This book owns no physical stock. Its remaining promises become one source
    requirement and one destination receipt in the network. Shipment handoff
    removes the same quantity from the book before the normal shipment is netted.
    """

    def __init__(self):
        self.orders = {}
        self.seen_campaigns = set()
        self.events = []

    def _event(self, row, day, event, quantity=0.0, **extra):
        self.events.append(dict(day=day, event=event, commitment_id=row["commitment_id"],
            campaign_id=row["campaign_id"], source_node_id=row["source_pair"][0],
            node_id=row["destination_pair"][0], item_id=row["source_pair"][1],
            uom=row["uom"], source_snapshot_day=row["source_snapshot_day"],
            source_requirement_id=row["source_requirement_id"], proposal_id=row["proposal_id"],
            original_dispatch_day=row["release_day"], original_available_day=row["available_day"],
            created_qty=row["qty"], event_qty=quantity, remaining_qty=row["remaining_qty"],
            support_allocations=row["support_allocations"],
            late_dispatch_days=max(0, day-row["release_day"]),
            early_handoff_days=max(0, row["release_day"]-day)
                if event in ("handoff_to_shipment", "advanced_to_dispatch") else 0,
            **extra))

    def from_started_campaign(self, *, day, campaign_id, source_pair, campaign_qty, plan, pegs, uom,
                              existing_campaign=False):
        if campaign_id in self.seen_campaigns:
            return ()
        if not campaign_id or type(day) is not int or day < 0 or campaign_qty <= 0:
            raise ValueError("Transfer pegging requires an actual positive campaign start")
        self.seen_campaigns.add(campaign_id)
        # Only the executable prefix of today's production proposals is financed.
        budget = Decimal(str(campaign_qty))
        launched = {"campaign:" + campaign_id: budget} if existing_campaign else {}
        for proposal in (() if existing_campaign else plan.proposals):
            if proposal.release_day <= day and budget > 0:
                taken = min(budget, Decimal(str(proposal.qty)))
                launched[proposal.proposal_id] = taken
                budget -= taken
        support, new_work = defaultdict(list), defaultdict(Decimal)
        for allocation in plan.allocations:
            qty = Decimal(str(allocation.qty))
            if allocation.supply_kind == "proposal" or (existing_campaign and allocation.supply_id == "campaign:" + campaign_id):
                funded = min(qty, launched.get(allocation.supply_id, Decimal(0)))
                launched[allocation.supply_id] = launched.get(allocation.supply_id, Decimal(0))-funded
                kind = "started_campaign"
            else:
                funded, kind = qty, allocation.supply_kind
            if funded > 0:
                support[allocation.requirement_id].append(dict(supply_id=allocation.supply_id,
                    kind=kind, qty=float(funded), available_day=allocation.available_day))
                if kind == "started_campaign":
                    new_work[allocation.requirement_id] += funded
        created = []
        for requirement_id, peg in sorted(pegs.items(), key=lambda kv: (kv[1]["release_day"], kv[0])):
            if tuple(peg["source_pair"]) != tuple(source_pair) or new_work[requirement_id] <= 0:
                continue
            quantity = Decimal(str(peg["qty"]))
            funded = sum((Decimal(str(a["qty"])) for a in support[requirement_id]), Decimal(0))
            if abs(funded-quantity) > Decimal("0.000001"):
                continue  # A partly funded transfer is still revocable.
            if uom == "UN" and quantity != quantity.to_integral_value():
                raise ValueError("A committed physical UN transfer must be integer")
            identity = f"internal_commitment:{len(self.orders)+1}"
            row = dict(peg, source_pair=tuple(source_pair), destination_pair=tuple(peg["destination_pair"]),
                commitment_id=identity, campaign_id=campaign_id, source_requirement_id=requirement_id,
                qty=float(quantity), remaining_qty=float(quantity), uom=uom,
                support_allocations=support[requirement_id])
            self.orders[identity] = row
            self._event(row, day, "created_nonphysical_promise", float(quantity))
            created.append(identity)
        return tuple(created)

    def planning_rows(self, *, decision_day, calendars):
        rows = []
        for row in self.orders.values():
            if row["remaining_qty"] <= 0:
                continue
            earliest = max(decision_day, row["release_day"])
            slot = next(((r,a) for r,a in calendars[row["destination_pair"]] if r >= earliest), None)
            if slot is None:
                raise ValueError("Transfer promise calendar does not cover its dispatch")
            rows.append(dict(row, qty=row["remaining_qty"], dispatch_day=slot[0], promised_day=slot[1]))
        return tuple(rows)

    def due_quantity(self, pair, day):
        return fsum(row["remaining_qty"] for row in self.orders.values()
                    if row["destination_pair"] == pair and row["release_day"] <= day)

    def handoff(self, *, pair, day, quantity, shipment_id, available_day, advance_context=None):
        remaining = Decimal(str(quantity))
        for row in sorted(self.orders.values(), key=lambda r: (r["release_day"], r["commitment_id"])):
            # A real rounded shipment already covers later promises of this
            # unique route. Keep their original dates for audit, but never
            # demand the same quantity again merely because it arrived early.
            if row["destination_pair"] != pair or remaining <= 0:
                continue
            taken = min(remaining, Decimal(str(row["remaining_qty"])))
            if taken <= 0:
                continue
            if row["uom"] == "UN" and taken != taken.to_integral_value():
                raise ValueError("A physical UN promise handoff must be integer")
            if advance_context is not None and day < row["release_day"]:
                # Timing annotation only: the following handoff is the sole
                # quantity debit. A partially shipped promise keeps its original
                # date for the remaining quantity and never changes identity.
                self._event(row, day, "advanced_to_dispatch", float(taken),
                    shipment_id=shipment_id, promised_dispatch_day=day,
                    promised_available_day=available_day, quantity_event_role="timing_only",
                    **advance_context)
            row["remaining_qty"] = float(Decimal(str(row["remaining_qty"]))-taken)
            remaining -= taken
            self._event(row, day, "handoff_to_shipment", float(taken),
                        shipment_id=shipment_id, promised_available_day=available_day)
        return float(Decimal(str(quantity))-remaining)

    def record_pending(self, *, day, rows):
        for projected in rows:
            row = self.orders[projected["commitment_id"]]
            self._event(row, day, "pending_nonphysical_promise",
                        promised_dispatch_day=projected["dispatch_day"],
                        promised_available_day=projected["promised_day"])


@dataclass(frozen=True)
class StockProtection:
    protection_id: str
    day: int
    minimum_qty: float


@dataclass(frozen=True)
class ReceiptReplanningStatus:
    receipt_id: str
    replannable: bool | None = None
    transport_departed: bool | None = None
    receipt_executed: bool | None = None
    known_day: int | None = None


@dataclass(frozen=True)
class ReceiptPostponementDecision:
    receipt_id: str
    old_available_day: int
    new_available_day: int
    reason: str
    first_deficit_day: int | None
    coverage_end_day: int


@dataclass(frozen=True)
class PostponedReceiptPlan:
    firm_receipts: tuple[FirmReceipt, ...]
    decisions: tuple[ReceiptPostponementDecision, ...]


def postpone_initial_receipts(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    protection: Iterable[StockProtection] = (), coverage_days: Iterable[int] = (),
    horizon_day: int, statuses: Iterable[ReceiptReplanningStatus] = (),
    policy: str | None = None,
    earliest_available_by_id: Mapping[str, int] | None = None,
) -> PostponedReceiptPlan:
    """Delay explicit unshipped commitments while preserving the protected stock.

    Candidate policy, not an inferred industrial order status. The caller owns
    causal status declarations and any expiry of the permission to reschedule.
    In particular, supplier ordering lead time is NOT a shipment departure date.
    The legacy ``in_transit`` planner label does not replace these explicit
    physical flags; ``held`` is always frozen because it is already received.

    Remove just one receipt, retaining all others including earlier revisions.
    Its latest safe availability is the first stock/protection deficit, bounded
    by continuous known forecast coverage and the explicit horizon. A gap is
    never a forecast zero. No deficit means postponement only to that boundary,
    not cancellation or an infinite date. Existing prior deficits prevent delay.
    Protection is a persistent level, not an extra daily consumption.

    Returned dates are *availability* dates on the supplied integer calendar.
    An explicit earliest-date map also permits re-advancing a previously
    postponed promise, never before its original contractual availability.
    Without that map, historical postponement-only behaviour is unchanged.
    The caller may convert to a physical date only with a known receipt calendar,
    choosing an achievable availability no later than this limit. It must retain
    quantities, identities and these commitments in its subsequent MRP netting.
    No physical inventory, source observation or new purchase is created here.
    """
    receipts = tuple(firm_receipts)
    if policy is None:
        return PostponedReceiptPlan(receipts, ())
    if policy != "known_need_and_protection_v1":
        raise ValueError("Unknown initial receipt postponement policy")
    _day(decision_day, "decision day")
    _day(horizon_day, "horizon day")
    if horizon_day < decision_day:
        raise ValueError("Postponement horizon must not precede the decision")
    initial = Decimal(str(_number(available_qty, "available quantity")))
    needs, points = tuple(requirements), tuple(protection)
    identities = set()
    for receipt in receipts:
        _identity(receipt.receipt_id, identities, "receipt identity")
        _day(receipt.available_day, "receipt availability")
        _number(receipt.qty, "receipt quantity")
        if receipt.state not in {"held", "confirmed", "in_transit"}:
            raise ValueError("Unknown firm receipt state")
    by_id, seen = {}, set()
    for status in statuses:
        _identity(status.receipt_id, seen, "replanning status identity")
        if status.receipt_id not in identities:
            raise ValueError("Replanning status must refer to an existing firm receipt")
        for value in (status.replannable, status.transport_departed, status.receipt_executed):
            if value is not None and type(value) is not bool:
                raise ValueError("Replanning physical statuses must be explicit booleans or unknown")
        if status.known_day is not None:
            _day(status.known_day, "status knowledge day")
        by_id[status.receipt_id] = status
    known = set()
    for day in coverage_days:
        _day(day, "forecast coverage day")
        if day > decision_day:
            known.add(day)
    through = decision_day
    while through < horizon_day and through + 1 in known:
        through += 1
    demand = defaultdict(Decimal)
    seen = set()
    for need in needs:
        _identity(need.requirement_id, seen, "requirement identity")
        _day(need.due_day, "requirement due day")
        quantity = Decimal(str(_number(need.qty, "requirement quantity")))
        demand[max(decision_day, need.due_day)] += quantity
    floors, seen = {}, set()
    for point in points:
        _identity(point.protection_id, seen, "protection identity")
        _day(point.day, "protection day")
        if point.day in floors:
            raise ValueError("Protection checkpoints require unique dates")
        floors[point.day] = Decimal(str(_number(point.minimum_qty, "protection quantity")))
    # Unknown past receipt state would make a counterfactual ambiguous: a
    # remaining firm row is not silently credited a second time at the decision.
    if any(row.available_day < decision_day for row in receipts):
        raise ValueError("Past firm receipts must be reconciled with stock before postponement")
    current = {row.receipt_id: row for row in receipts}
    earliest = dict(earliest_available_by_id or {})
    for identity, value in earliest.items():
        _day(value, "earliest contractual availability")
        if identity not in current or value > current[identity].available_day:
            raise ValueError("Earliest availability must identify an existing promise and not exceed its current date")
    decisions = []
    for original in sorted(receipts, key=lambda row: (row.available_day, row.receipt_id)):
        status = by_id.get(original.receipt_id)
        reason, first_deficit, target = "unchanged", None, original.available_day
        if status is None:
            reason = "status_missing"
        elif status.known_day is None or status.known_day > decision_day:
            reason = "status_not_known_at_decision"
        elif status.receipt_executed is True or original.state == "held":
            reason = "already_received"
        elif status.transport_departed is True:
            reason = "transport_already_departed"
        elif status.replannable is not True or status.transport_departed is not False or status.receipt_executed is not False:
            reason = "status_not_explicitly_replannable_unshipped"
        elif original.available_day <= decision_day:
            reason = "already_due"
        elif original.qty == 0:
            reason = "zero_quantity"
        elif earliest.get(original.receipt_id, original.available_day) >= through:
            reason = "no_later_continuous_coverage"
        else:
            supplies = defaultdict(Decimal)
            for identity, other in current.items():
                if identity != original.receipt_id:
                    supplies[other.available_day] += Decimal(str(other.qty))
            floor_qty = next((floors[d] for d in sorted(floors, reverse=True) if d <= decision_day), Decimal(0))
            balance = initial
            for day in range(decision_day, through + 1):
                floor_qty = floors.get(day, floor_qty)
                balance += supplies[day] - demand[day]
                if balance < floor_qty:
                    first_deficit = day
                    break
            limit = first_deficit if first_deficit is not None else through
            candidate = max(earliest.get(original.receipt_id, original.available_day), limit)
            if candidate != original.available_day:
                target = candidate
                reason = ("readvanced_to_protected_need" if target < original.available_day else
                    "postponed_to_first_protected_need" if first_deficit is not None else "postponed_to_known_horizon_boundary")
                current[original.receipt_id] = replace(original, available_day=target)
            else:
                reason = "receipt_already_needed"
        decisions.append(ReceiptPostponementDecision(original.receipt_id,
            original.available_day, target, reason, first_deficit, through))
    return PostponedReceiptPlan(tuple(current[row.receipt_id] for row in receipts), tuple(decisions))


@dataclass(frozen=True)
class ProtectionBalance:
    day: int
    target_qty: float
    projected_qty: float
    shortfall_qty: float


@dataclass(frozen=True)
class ProtectedDatedPlan:
    plan: DatedPlan
    protection: tuple[ProtectionBalance, ...]
    planning_envelope_requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class SupplierOffer:
    supplier_id: str
    purchase_unit_cost: float
    currency: str
    uom: str
    lead_days: int
    lot_sizing: LotSizing = LotSizing()
    availability_by_release: tuple[tuple[int, int], ...] = ()
    standard_order_qty: float | None = None
    review_calendar: bool = False


@dataclass(frozen=True)
class SourcedProposal:
    proposal: OrderProposal
    supplier_id: str
    role: str
    reason: str
    backup_required_qty: float = 0.0
    planning_supplier_id: str = ""


@dataclass(frozen=True)
class SourcedPlan:
    plan: DatedPlan
    proposals: tuple[SourcedProposal, ...]
    primary_available_day: int
    physical_shortage_before_primary_qty: float
    backup_proposed_qty: float
    retained_firm_qty: float
    bridge_surplus_qty: float


def _number(value: float, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite nonnegative quantity")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite nonnegative quantity") from exc
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite nonnegative quantity")
    return number


def _day(value: int, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer day")
    return value


def _identity(value: str, seen: set[str], field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value in seen:
        raise ValueError(f"{field} must be nonempty and unique")
    seen.add(value)


def _lot_bounds(policy: LotSizing) -> tuple[float, float, float | None]:
    if type(policy.integer) is not bool:
        raise ValueError("integer must be a boolean")
    minimum = _number(policy.minimum, "minimum")
    multiple = _number(policy.multiple, "multiple")
    maximum = None if policy.maximum is None else _number(policy.maximum, "maximum")
    quantum = _number(policy.net_rounding_quantum, "net rounding quantum")
    if policy.integer and quantum:
        raise ValueError("Mass net rounding must not apply to physical UN")
    if maximum is not None and (maximum == 0 or minimum > maximum):
        raise ValueError("maximum must be positive and at least minimum")
    if policy.integer:
        # Bounds and purchase multiples are physical; forecasts may be fractional.
        for value in (minimum, multiple, maximum):
            if value is not None and value != floor(value):
                raise ValueError("Physical UN lot bounds must be integers")
    if multiple:
        step = Decimal(str(multiple))
        minimum = _number(float(ceil(Decimal(str(minimum)) / step) * step), "rounded minimum")
        if maximum is not None:
            maximum = float(floor(Decimal(str(maximum)) / step) * step)
            if maximum == 0 or minimum > maximum:
                raise ValueError("No purchase lot satisfies the bounds and multiple")
    return minimum, multiple, maximum


def _allocate(requirements, supplies):
    """FIFO needs and earliest availability; inputs contain only local copies."""
    # Decimal conversion of the declared quantities avoids a ghost UN purchase
    # after subtracting thirty 0.1 forecasts from three physical units.
    pools = [[identity, day, Decimal(str(qty)), kind] for identity, day, qty, kind in supplies]
    pools.sort(key=lambda row: (row[1], row[0]))
    allocations, missing = [], []
    cursor = 0
    for requirement in requirements:
        remaining = Decimal(str(requirement.qty))
        while remaining > 0 and cursor < len(pools):
            supply = pools[cursor]
            if supply[2] <= 0:
                cursor += 1
                continue
            qty = min(remaining, supply[2])
            allocations.append(Allocation(
                requirement.requirement_id, supply[0], supply[3], float(qty),
                requirement.due_day, supply[1], max(0, supply[1] - requirement.due_day),
            ))
            remaining -= qty
            supply[2] -= qty
        if remaining > 0:
            # Keep the exact remainder until lot sizing. A float here can round
            # down (e.g. 2 - 0.9999999999999999) and leave a need uncovered.
            missing.append((requirement, remaining))
    return tuple(allocations), tuple(missing), pools


def plan_dated_requirements(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    lead_days: int, lot_sizing: LotSizing | None = None,
    grouping_days: int | None = None,
    availability_by_release: Iterable[tuple[int, int]] | None = None,
) -> DatedPlan:
    """Propose quantities not covered by stock/commitments and expose lateness.

    Requirements describe remaining needs, not repeated daily MPS signals.
    Firm receipts include each held or undelivered quantity exactly once, at its
    availability date. Receipts already available belong in available_qty.
    New proposals remain revocable until their release is physically executed.
    Lot maxima limit one order, not total daily manufacturing capacity.
    An explicit calendar lists only permitted releases and their exact usable
    dates. Choose the latest feasible release, or the earliest still possible
    when late. Firm dates and quantities are never moved by this calendar.
    """
    decision_day = _day(decision_day, "decision_day")
    if grouping_days is not None and (_day(grouping_days, "grouping_days") < 0):
        raise ValueError("Procurement grouping days must be nonnegative")
    lead_days = _day(lead_days, "lead_days")
    if lead_days < 0:
        raise ValueError("lead_days must be nonnegative")
    available = _number(available_qty, "available_qty")
    policy = lot_sizing or LotSizing()
    minimum, multiple, maximum = _lot_bounds(policy)
    if policy.integer and available != floor(available):
        raise ValueError("Physical UN available stock must be integer")
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    seen = set()
    for row in needs:
        _identity(row.requirement_id, seen, "requirement_id")
        _day(row.due_day, "due_day")
        _number(row.qty, "requirement qty")
    needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    calendar = None
    if availability_by_release is not None:
        calendar = tuple(availability_by_release)
        if not calendar:
            raise ValueError("An explicit release calendar must not be empty")
        for index, (release, arrival) in enumerate(calendar):
            _day(release, "calendar release")
            _day(arrival, "calendar availability")
            if (release < decision_day or arrival < release
                    or (index and (release <= calendar[index - 1][0]
                                   or arrival < calendar[index - 1][1]))):
                raise ValueError("Release calendar must be causal, ordered and monotone")
        if calendar[-1][0] < max((r.due_day for r in needs), default=decision_day):
            raise ValueError("Release calendar must cover the requirement horizon")
    arrival_dates = tuple(row[1] for row in calendar) if calendar is not None else ()
    seen = {"opening_stock"}
    supplies = [("opening_stock", decision_day, available, "available")]
    for row in receipts:
        _identity(row.receipt_id, seen, "receipt_id")
        _day(row.available_day, "available_day")
        if row.available_day < decision_day:
            raise ValueError("Past receipts must be reconciled with available stock")
        qty = _number(row.qty, "firm receipt qty")
        if policy.integer and qty != floor(qty):
            raise ValueError("Physical UN firm receipts must be integer")
        if row.state not in ("held", "in_transit", "confirmed"):
            raise ValueError("Firm receipt state must be held, in_transit or confirmed")
        supplies.append((row.receipt_id, row.available_day, qty, row.state))

    committed_allocations, missing, _ = _allocate(needs, supplies)
    proposals, procurement_groups = [], []
    surplus = Decimal(0)
    quantum = Decimal(str(policy.net_rounding_quantum))
    pending = deque(missing)
    while pending:
        requirement, remainder = pending.popleft()
        raw_balance = remainder - surplus
        need = max(Decimal(0), raw_balance)
        surplus = max(Decimal(0), -raw_balance)
        members = [(requirement, need)]
        window_end = requirement.due_day + max(1, grouping_days or 0)
        if grouping_days is not None:
            # Anchor at the first STILL uncovered need, after existing firm
            # receipts and earlier purchase-lot surplus. Never move that due
            # date or create a second consumption/safety requirement.
            if need <= 0:
                continue
            if grouping_days:
                while pending and pending[0][0].due_day < window_end:
                    member, quantity = pending.popleft()
                    members.append((member, quantity))
                    need += quantity
        net_requirement = need
        if quantum:
            need = (need / quantum).quantize(Decimal(1), rounding=ROUND_HALF_UP) * quantum
        first_proposal = len(proposals)
        while need > 0:
            qty = max(need, Decimal(str(minimum)))
            if multiple:
                qty = ceil(qty / Decimal(str(multiple))) * Decimal(str(multiple))
            if policy.integer:
                qty = Decimal(ceil(qty))
            if maximum is not None:
                qty = min(qty, Decimal(str(maximum)))
            published_qty = _number(qty, "proposal qty")
            if Decimal(str(published_qty)) < qty:
                # The public engine interface uses floats. Represent a proposal
                # outward by at most one ULP, then use that SAME quantity for
                # netting and balances. Never erase a shortage with a tolerance
                # or turn floating-point dust into an extra physical UN lot.
                published_qty = _number(nextafter(published_qty, float("inf")), "proposal qty")
            qty = Decimal(str(published_qty))
            if qty <= 0:
                raise ValueError("Lot policy produced a zero purchase for a positive need")
            release = max(decision_day, requirement.due_day - lead_days)
            arrival = release + lead_days
            if calendar is not None:
                release, arrival = calendar[max(0, bisect_right(arrival_dates, requirement.due_day) - 1)]
            proposal_id = f"proposal:{len(proposals) + 1}"
            if proposal_id in seen:
                raise ValueError("Receipt id collides with a generated proposal id")
            proposals.append(OrderProposal(proposal_id, release, arrival, requirement.due_day, published_qty))
            surplus += max(Decimal(0), qty - need)
            need = max(Decimal(0), need - qty)
        if quantum:
            # Carry the real residual, including rounded-down deficits, into
            # the next dated need. Never round each day's forecast or inject
            # an imaginary receipt to make projected balances nonnegative.
            surplus = (sum((Decimal(str(row.qty)) for row in proposals[first_proposal:]), Decimal(0))
                       - net_requirement) if net_requirement else surplus
        if grouping_days is not None:
            grouped_proposals = proposals[first_proposal:]
            procurement_groups.append(ProcurementGroup(
                f"group:{len(procurement_groups) + 1}", requirement.due_day, window_end,
                float(sum((quantity for member, quantity in members if not member.requirement_id.startswith("reserve:")), Decimal(0))),
                float(sum((quantity for member, quantity in members if member.requirement_id.startswith("reserve:")), Decimal(0))),
                float(net_requirement), fsum(row.qty for row in grouped_proposals),
                tuple(member.requirement_id for member, _ in members),
                tuple(row.proposal_id for row in grouped_proposals),
            ))

    return _complete_plan(decision_day, available, needs, receipts, proposals, supplies, committed_allocations,
                          procurement_groups, net_rounding_quantum=policy.net_rounding_quantum)


def _complete_plan(decision_day, available, needs, receipts, proposals, supplies, committed_allocations,
                   procurement_groups=(), *, net_rounding_quantum=0.0):
    # Minimum/multiple rounding may provide earlier surplus. Reallocate by actual
    # availability so lateness is not overstated when that surplus covers a need.
    all_supplies = supplies + [(p.proposal_id, p.available_day, p.qty, "proposal") for p in proposals]
    allocations, uncovered, leftovers = _allocate(needs, all_supplies)
    uncovered_qty = sum((qty for _, qty in uncovered), Decimal(0))
    if uncovered and (not net_rounding_quantum
                      or uncovered_qty >= Decimal(str(net_rounding_quantum)) / 2):
        raise ArithmeticError("Proposed plan does not cover every remaining quantity")
    events: dict[int, list[list[float]]] = {decision_day: [[], [], []]}
    for row in needs:
        events.setdefault(max(decision_day, row.due_day), [[], [], []])[0].append(float(row.qty))
    for row in receipts:
        events.setdefault(row.available_day, [[], [], []])[1].append(float(row.qty))
    for row in proposals:
        events.setdefault(row.available_day, [[], [], []])[2].append(row.qty)
    balances = []
    before = after = Decimal(str(available))
    for day, amounts in sorted(events.items()):
        needed, firm, proposed = (sum((Decimal(str(value)) for value in group), Decimal(0)) for group in amounts)
        before += firm - needed
        after += firm + proposed - needed
        if not isfinite(before) or not isfinite(after):
            raise ValueError("Projected balance overflow")
        balances.append(ProjectedBalance(day, float(needed), float(firm), float(proposed), float(before), float(after)))
    return DatedPlan(
        decision_day, available, committed_allocations, allocations, tuple(proposals), tuple(balances),
        fsum(a.qty for a in allocations if a.delay_days),
        fsum(a.qty * a.delay_days for a in allocations),
        fsum(a.qty for a in allocations if a.delay_days and a.supply_kind in ("held", "in_transit", "confirmed")),
        fsum(p.qty for p in proposals),
        fsum(p[2] for p in leftovers if p[3] in ("held", "in_transit", "confirmed")),
        float(after),
        tuple(procurement_groups),
        net_rounding_quantum,
        tuple(Requirement(row.requirement_id, row.due_day, float(qty)) for row, qty in uncovered),
    )


def reschedule_dated_plan(plan, *, requirements, firm_receipts, proposals):
    """Rebuild date-dependent balances after a calendar moves new proposals.

    Quantities, identities and requested deadlines are immutable. Real firm
    receipts retain their dates. This is scheduling, not another netting pass.
    """
    proposals, receipts = tuple(proposals), tuple(firm_receipts)
    if plan.procurement_groups:
        raise ValueError("Calendar rescheduling does not support procurement groups")
    original = {row.proposal_id: (row.qty, row.requested_day) for row in plan.proposals}
    if (len(proposals) != len(original)
            or {row.proposal_id: (row.qty, row.requested_day) for row in proposals} != original):
        raise ValueError("Rescheduling must preserve proposal identities, quantities and requested dates")
    for row in proposals:
        _day(row.release_day, "rescheduled release")
        _day(row.available_day, "rescheduled availability")
        if row.release_day < plan.decision_day or row.available_day < row.release_day:
            raise ValueError("Rescheduled proposals must remain causal")
    needs = tuple(sorted(requirements, key=lambda row: (row.due_day, row.requirement_id)))
    supplies = [("opening_stock", plan.decision_day, plan.opening_available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in receipts]
    committed, _, _ = _allocate(needs, supplies)
    return _complete_plan(plan.decision_day, plan.opening_available_qty, needs, receipts,
                          proposals, supplies, committed, net_rounding_quantum=plan.net_rounding_quantum)


def plan_anticipated_requirements(
    *, decision_day: int, available_qty: float, requirements: Iterable[Requirement],
    firm_receipts: Iterable[FirmReceipt], source_working_days: int,
    origin_weekday: int, fixed_floor_qty: float, lead_days: int,
    lot_sizing: LotSizing | None = None, grouping_days: int | None = None,
    availability_by_release: tuple = (), sourcing: Mapping | None = None,
    allocated_sourcing: Mapping | None = None,
    fixed_floor_mode: str = "maximum",
    exact_release_calendar: Iterable[tuple[int, int]] | None = None,
):
    """Protect remaining needs early, without advancing physical consumption.

    The procurement envelope is max(cumulative anticipated needs, cumulative
    physical needs + fixed source floor) in the historical ``maximum`` mode.
    The explicit ``additive`` candidate reserves the fixed floor once, then
    anticipates each remaining need. Neither protection is physical consumption.
    Past protected dates are due now, never dropped: their material is still
    physically needed. Existing late commitments are retained, not duplicated.
    Optional allocated_sourcing retains explicit legacy supplier shares while
    matching each purchase's own lot and calendar; it does not infer roles.
    Returns physical plan, optional sourced plan, and protected planning needs.
    """
    if (type(source_working_days) is not int or source_working_days < 0
            or type(origin_weekday) is not int or not 0 <= origin_weekday < 7):
        raise ValueError("Anticipation requires whole Monday-Friday safety days")
    _day(decision_day, "decision day")
    _number(fixed_floor_qty, "fixed source floor")
    if fixed_floor_mode not in ("maximum", "additive"):
        raise ValueError("Fixed source floor mode must be maximum or additive")
    if sourcing is not None and allocated_sourcing is not None:
        raise ValueError("Supplier roles and legacy allocation are mutually exclusive")
    if exact_release_calendar is not None and (sourcing is not None or allocated_sourcing is not None):
        raise ValueError("Sourced anticipation must use the supplier offer calendars")
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    events = defaultdict(lambda: [Decimal(0), Decimal(0)])
    events[decision_day]
    offsets = {}
    for weekday in range(7):
        elapsed = count = 0
        while count < source_working_days:
            elapsed += 1
            count += (weekday - elapsed) % 7 < 5
        offsets[weekday] = elapsed
    identities = set()
    for need in needs:
        _identity(need.requirement_id, identities, "requirement_id")
        _day(need.due_day, "physical need day")
        quantity = Decimal(str(_number(need.qty, "requirement qty")))
        protected = max(decision_day, need.due_day - offsets[(origin_weekday + need.due_day) % 7])
        events[protected][0] += quantity
        events[max(decision_day, need.due_day)][1] += quantity
    anticipated = physical = envelope = Decimal(0)
    planning = []
    if fixed_floor_mode == "additive" and fixed_floor_qty:
        planning.append(Requirement(f"reserve:fixed_source:{decision_day}", decision_day, fixed_floor_qty))
    for when, (early, actual) in sorted(events.items()):
        anticipated += early
        physical += actual
        next_envelope = (anticipated if fixed_floor_mode == "additive" else
                         max(envelope, anticipated, physical + Decimal(str(fixed_floor_qty))))
        increment = next_envelope - envelope
        if increment:
            prefix = "anticipated" if anticipated >= next_envelope else "reserve:fixed_source"
            # One upward-rounded float can turn an exact integral cumulative
            # budget into N + dust, and thereby order a whole extra UN. Publish
            # the exact increment as dated fragments instead: no epsilon,
            # quantity removal or change to the protection calendar.
            for index, (due_day, quantity) in enumerate(
                    _conserved_weekly_forecast_parts(Fraction(increment), (when,))):
                identity = f"{prefix}:{when}" + (f":fragment:{index}" if index else "")
                planning.append(Requirement(identity, due_day, quantity))
        envelope = next_envelope
    if allocated_sourcing is not None:
        options = dict(allocated_sourcing)
        if grouping_days is not None:
            if options.get("grouping_days", grouping_days) != grouping_days:
                raise ValueError("Allocation and anticipation must use the same procurement review period")
            options["grouping_days"] = grouping_days
        sourced = plan_allocated_purchase_requirements(decision_day=decision_day,
            available_qty=available_qty, requirements=planning, firm_receipts=receipts, **options)
        net = sourced.plan
    elif sourcing is not None:
        options = dict(sourcing)
        if grouping_days is not None:
            if options.get("grouping_days", grouping_days) != grouping_days:
                raise ValueError("Sourcing and anticipation must use the same procurement review period")
            options["grouping_days"] = grouping_days
        if fixed_floor_mode == "additive":
            options["preserve_reserve_allocation"] = True
        sourced = plan_sourced_requirements(decision_day=decision_day,
            available_qty=available_qty, requirements=planning, firm_receipts=receipts, **options)
        net = sourced.plan
    else:
        sourced = None
        net = plan_dated_requirements(decision_day=decision_day, available_qty=available_qty,
            requirements=planning, firm_receipts=receipts, lead_days=lead_days,
            lot_sizing=lot_sizing, grouping_days=grouping_days,
            availability_by_release=exact_release_calendar)
        if availability_by_release and exact_release_calendar is None:
            calendar = tuple(availability_by_release)
            for index, (release, available) in enumerate(calendar):
                if (type(release) is not int or type(available) is not int or available < release
                        or (index == 0 and release != decision_day)
                        or (index and (release != calendar[index - 1][0] + 1
                                       or available < calendar[index - 1][1]))):
                    raise ValueError("Anticipated receipt calendar must be consecutive and monotone")
            if calendar[-1][0] < max((r.due_day for r in planning), default=decision_day):
                raise ValueError("Anticipated receipt calendar must cover the planning horizon")
            dates = [entry[1] for entry in calendar]
            proposals = tuple(replace(row, release_day=calendar[max(0, bisect_right(dates, row.requested_day) - 1)][0],
                available_day=calendar[max(0, bisect_right(dates, row.requested_day) - 1)][1]) for row in net.proposals)
            supplies = [("opening_stock", decision_day, available_qty, "available")] + [
                (r.receipt_id, r.available_day, r.qty, r.state) for r in receipts]
            commitments, _, _ = _allocate(tuple(planning), supplies)
            net = _complete_plan(decision_day, available_qty, tuple(planning), receipts,
                proposals, supplies, commitments, net.procurement_groups,
                net_rounding_quantum=net.net_rounding_quantum)
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (r.receipt_id, r.available_day, r.qty, r.state) for r in receipts]
    physical_needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    commitments, _, _ = _allocate(physical_needs, supplies)
    plan = _complete_plan(decision_day, available_qty, physical_needs, receipts,
        net.proposals, supplies, commitments, net.procurement_groups,
        net_rounding_quantum=net.net_rounding_quantum)
    audit = {"anticipated_requirements": tuple(planning), "anticipated_plan": net,
             "anticipated_safety_working_days": source_working_days,
             "anticipated_fixed_floor_qty": fixed_floor_qty,
             "anticipated_fixed_floor_mode": fixed_floor_mode,
             "protection_points": ()}  # Suppress legacy floor export in the candidate.
    return plan, replace(sourced, plan=plan) if sourced is not None else None, audit


def prospective_stock_protection(
    *, decision_day: int, requirements: Iterable[Requirement], source_working_days: int,
    origin_weekday: int, forecast_through_day: int, covered_days: Iterable[int],
    fixed_floor_qty: float, legacy_floor_qty: float,
    coverage_activation_day: int, coverage_complement_qty: float,
) -> tuple[tuple[StockProtection, ...], dict]:
    """Experimental non-consumable floor from complete dated forecast windows.

    At the close of t, protect requirements strictly in (t, t+N workdays].
    Weekends are skipped to determine the endpoint, not to remove demand.
    Missing dates or the forecast tail use the explicit legacy floor. Prefix
    sums make this linear in the planning horizon plus the requirement count.
    """
    for value, label in ((decision_day, "decision day"), (forecast_through_day, "forecast end"),
                         (coverage_activation_day, "coverage activation")):
        _day(value, label)
    if (type(source_working_days) is not int or source_working_days < 0
            or type(origin_weekday) is not int or not 0 <= origin_weekday < 7
            or forecast_through_day < decision_day or coverage_activation_day < decision_day):
        raise ValueError("Prospective protection requires whole working days and a valid forecast interval")
    for value in (fixed_floor_qty, legacy_floor_qty, coverage_complement_qty):
        _number(value, "prospective protection floor")
    horizon = forecast_through_day - decision_day
    amounts = [Decimal(0) for _ in range(horizon + 1)]
    for need in requirements:
        _day(need.due_day, "requirement day")
        _number(need.qty, "requirement qty")
        if decision_day < need.due_day <= forecast_through_day:
            amounts[need.due_day - decision_day] += Decimal(str(need.qty))
    known = set(covered_days)
    prefix, missing = [Decimal(0)], [0]
    for offset in range(1, horizon + 1):
        prefix.append(prefix[-1] + amounts[offset])
        missing.append(missing[-1] + (decision_day + offset not in known))
    elapsed = {}
    for weekday in range(7):
        days = workdays = 0
        while workdays < source_working_days:
            days += 1
            workdays += (weekday + days) % 7 < 5
        elapsed[weekday] = days
    points, details, dated_count, fallback_count = [], {}, 0, 0
    previous_signature = None
    # The last checkpoint explicitly restores legacy after the known horizon.
    dates = sorted(set(range(decision_day + 1, forecast_through_day + 2)) | {coverage_activation_day})
    tomorrow_floor = legacy_floor_qty
    tomorrow_basis = "fallback_incomplete_forecast"
    for when in dates:
        end = when + elapsed[(origin_weekday + when) % 7]
        complete = (when > decision_day and end <= forecast_through_day
                    and missing[end - decision_day] == missing[when - decision_day])
        need_qty = float(prefix[end - decision_day] - prefix[when - decision_day]) if complete else None
        source_floor = max(fixed_floor_qty, need_qty) if complete else legacy_floor_qty
        # Preserve legacy zero-lead coverage without creating a safety floor on
        # the decision day: source protection starts tomorrow in every mode.
        if when == decision_day:
            source_floor = 0.0
        floor_qty = max(source_floor, coverage_complement_qty if when >= coverage_activation_day else 0.0)
        basis = "dated_known_window" if complete else "fallback_incomplete_forecast"
        if decision_day < when <= forecast_through_day:
            dated_count += int(complete)
            fallback_count += int(not complete)
        if when == decision_day + 1:
            tomorrow_floor, tomorrow_basis = source_floor, basis
        detail = {"safety_window_end_day": end, "safety_window_need_qty": need_qty if complete else "",
                  "safety_window_covered": int(complete), "safety_source_floor_qty": source_floor}
        signature = (floor_qty, basis)
        if signature != previous_signature or when == coverage_activation_day:
            points.append(StockProtection(f"prospective:{when}:{basis}", when, floor_qty))
            details[when] = detail
            previous_signature = signature
    return tuple(points), {
        "prospective_safety_basis": tomorrow_basis,
        "prospective_safety_source_days": source_working_days,
        "prospective_safety_tomorrow_qty": tomorrow_floor,
        "prospective_safety_legacy_qty": legacy_floor_qty,
        "prospective_safety_dated_days": dated_count,
        "prospective_safety_fallback_days": fallback_count,
        "prospective_checkpoints": details,
    }


def plan_with_stock_protection(
    *, decision_day: int, available_qty: float, requirements: Iterable[Requirement],
    firm_receipts: Iterable[FirmReceipt], lead_days: int,
    lot_sizing: LotSizing | None = None, protection: Iterable[StockProtection] = (),
    availability_by_release: Iterable[tuple[int, int]] | None = None,
) -> ProtectedDatedPlan:
    """Net a persistent inventory floor without turning it into consumption.

    A checkpoint sets the floor until the next checkpoint; it is zero before
    the first. The nondecreasing envelope max(cumulative physical needs+floor)
    determines procurement. Physical balances and allocations are reconstructed
    from the ORIGINAL needs and the same proposals. Late firm volume retains
    the existing no-duplicate-purchase contract; a floor may therefore be late.
    """
    needs, receipts, points = tuple(requirements), tuple(firm_receipts), tuple(protection)
    if not points:
        return ProtectedDatedPlan(plan_dated_requirements(
            decision_day=decision_day, available_qty=available_qty, requirements=needs,
            firm_receipts=receipts, lead_days=lead_days, lot_sizing=lot_sizing,
            availability_by_release=availability_by_release,
        ), (), ())
    _day(decision_day, "decision_day")
    seen, days = set(), set()
    for point in points:
        _identity(point.protection_id, seen, "protection_id")
        _day(point.day, "protection day")
        _number(point.minimum_qty, "protection minimum")
        if point.day < decision_day or point.day in days:
            raise ValueError("Protection checkpoints must have distinct nonpast days")
        days.add(point.day)
    points = tuple(sorted(points, key=lambda point: point.day))
    amounts = defaultdict(list)
    seen = set()
    for need in needs:
        _identity(need.requirement_id, seen, "requirement_id")
        _day(need.due_day, "due_day")
        _number(need.qty, "requirement qty")
        amounts[max(decision_day, need.due_day)].append(Decimal(str(need.qty)))
    levels = {point.day: Decimal(str(point.minimum_qty)) for point in points}
    cumulative, floor_qty, envelope = Decimal(0), Decimal(0), Decimal(0)
    virtual = []
    for event_day in sorted(set(amounts) | set(levels)):
        cumulative += sum(amounts.get(event_day, ()), Decimal(0))
        floor_qty = levels.get(event_day, floor_qty)
        next_envelope = max(envelope, cumulative + floor_qty)
        increment = next_envelope - envelope
        if increment:
            represented = float(increment)
            if Decimal(str(represented)) < increment:
                represented = nextafter(represented, float("inf"))
            virtual.append(Requirement(f"protection_envelope:{event_day}", event_day, represented))
        envelope = next_envelope
    net = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=virtual,
        firm_receipts=receipts, lead_days=lead_days, lot_sizing=lot_sizing,
        availability_by_release=availability_by_release,
    )
    physical = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in receipts
    ]
    committed, _, _ = _allocate(physical, supplies)
    plan = _complete_plan(decision_day, available_qty, physical, receipts, net.proposals, supplies, committed,
                          net_rounding_quantum=net.net_rounding_quantum)
    physical_balances = {row.day: row.after_proposals_qty for row in plan.balances}
    floor_qty, projected = Decimal(0), float(available_qty)
    audit = []
    for event_day in sorted(set(physical_balances) | set(levels)):
        floor_qty = levels.get(event_day, floor_qty)
        projected = physical_balances.get(event_day, projected)
        audit.append(ProtectionBalance(event_day, float(floor_qty), projected, max(0.0, float(floor_qty) - projected)))
    return ProtectedDatedPlan(plan, tuple(audit), tuple(virtual))


def plan_allocated_purchase_requirements(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    offers: tuple[SupplierOffer, ...], allocation_weights: tuple[float, ...],
    grouping_days: int | None = None,
) -> SourcedPlan:
    """Plan the supplied legacy allocation with each offer's real lot and date.

    Offers stay in their supplied execution order; prices never infer roles.
    Each share is based on the original uncovered group, capped by the amount
    still missing after the preceding rounded purchase. Rounding may therefore
    satisfy the whole group with the first supplier. Its surplus covers later
    needs once, regardless of supplier. Firm orders, including late ones, stay
    allocated and are never replaced by an unrequested rescue purchase.

    The common net mass quantum applies once before splitting a group; physical
    lot bounds and integer UN rounding then apply per offer. An all-zero weight
    vector uses the existing ordered fallback. Supplier availability is planned
    nominally; this helper neither executes a purchase nor predicts disruption.
    The inherited primary_available_day field refers only to the first supplied
    offer; backup/bridge fields are zero because no supplier roles are inferred.
    """
    offers, weights = tuple(offers), tuple(allocation_weights)
    if not offers or len(offers) != len(weights):
        raise ValueError("Allocated sourcing requires matching nonempty offers and weights")
    weights = tuple(Decimal(str(_number(w, "allocation weight"))) for w in weights)
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    first = offers[0]
    # Reuse the public input contract, without any supplier-specific lot sizing.
    # Actual purchases below are sized only after the allocation is known.
    neutral_policy = LotSizing(integer=first.lot_sizing.integer,
        net_rounding_quantum=first.lot_sizing.net_rounding_quantum)
    plan_dated_requirements(decision_day=decision_day, available_qty=available_qty,
        requirements=needs, firm_receipts=receipts, lead_days=first.lead_days,
        lot_sizing=neutral_policy, grouping_days=grouping_days)
    needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    seen, bounds, calendars = set(), {}, {}
    for offer in offers:
        _identity(offer.supplier_id, seen, "supplier_id")
        _number(offer.purchase_unit_cost, "purchase_unit_cost")
        if (not isinstance(offer.currency, str) or not offer.currency.strip()
                or not isinstance(offer.uom, str) or not offer.uom.strip()
                or offer.currency != first.currency or offer.uom != first.uom):
            raise ValueError("Allocated offers require the same explicit currency and physical unit")
        if _day(offer.lead_days, "lead_days") < 0:
            raise ValueError("Supplier lead must be nonnegative")
        bounds[offer.supplier_id] = _lot_bounds(offer.lot_sizing)
        if offer.uom == "UN" and not offer.lot_sizing.integer:
            raise ValueError("Physical UN allocated offers require integer lot policies")
        if (offer.lot_sizing.integer != first.lot_sizing.integer
                or offer.lot_sizing.net_rounding_quantum != first.lot_sizing.net_rounding_quantum):
            raise ValueError("Allocated offers must agree on physical integer and net rounding policies")
        calendar = tuple(offer.availability_by_release)
        for index, (release, arrival) in enumerate(calendar):
            _day(release, "calendar release")
            _day(arrival, "calendar availability")
            if (release < decision_day or arrival < release
                    or (index and (release <= calendar[index - 1][0]
                                   or arrival < calendar[index - 1][1]))):
                raise ValueError("Allocated supplier calendars must be causal, ordered and monotone")
        if calendar and calendar[-1][0] < max((r.due_day for r in needs), default=decision_day):
            raise ValueError("Allocated supplier calendars must cover the requirement horizon")
        calendars[offer.supplier_id] = calendar, tuple(row[1] for row in calendar)

    def dates(offer, due):
        calendar, arrivals = calendars[offer.supplier_id]
        if calendar:
            return calendar[max(0, bisect_right(arrivals, due) - 1)]
        release = max(decision_day, due - offer.lead_days)
        return release, release + offer.lead_days

    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (r.receipt_id, r.available_day, r.qty, r.state) for r in receipts]
    committed, missing, _ = _allocate(needs, supplies)
    occupied_ids = {row[0] for row in supplies}
    sourced, groups = [], []
    quantum = Decimal(str(first.lot_sizing.net_rounding_quantum))
    total_weight = sum(weights, Decimal(0))

    def buy(offer, requested_day, target):
        minimum, multiple, maximum = bounds[offer.supplier_id]
        purchased = Decimal(0)
        while target > 0:
            qty = max(target, Decimal(str(minimum)))
            if multiple:
                step = Decimal(str(multiple))
                qty = ceil(qty / step) * step
            if offer.lot_sizing.integer:
                qty = Decimal(ceil(qty))
            if maximum is not None:
                qty = min(qty, Decimal(str(maximum)))
            published = _number(qty, "allocated proposal qty")
            if Decimal(str(published)) < qty:
                published = _number(nextafter(published, float("inf")), "allocated proposal qty")
            qty = Decimal(str(published))
            if qty <= 0:
                raise ValueError("Allocated lot policy produced a zero purchase for a positive need")
            identity = f"sourcing:allocated:{len(sourced) + 1}"
            if identity in occupied_ids:
                raise ValueError("Firm receipt id collides with an allocated proposal id")
            proposal = OrderProposal(identity, *dates(offer, requested_day), requested_day, published)
            sourced.append(SourcedProposal(proposal, offer.supplier_id, "allocated",
                "explicit_legacy_allocation_with_supplier_lot_and_calendar",
                planning_supplier_id=offer.supplier_id))
            target -= qty
            purchased += qty
        return purchased

    pending, surplus = deque(missing), Decimal(0)
    while pending:
        requirement, remainder = pending.popleft()
        raw_balance = remainder - surplus
        need, surplus = max(Decimal(0), raw_balance), max(Decimal(0), -raw_balance)
        if need <= 0:
            continue
        members = [(requirement, need)]
        window_end = requirement.due_day + max(1, grouping_days or 0)
        if grouping_days:
            while pending and pending[0][0].due_day < window_end:
                member, quantity = pending.popleft()
                members.append((member, quantity))
                need += quantity
        net_requirement = need
        if quantum:
            need = (need / quantum).quantize(Decimal(1), rounding=ROUND_HALF_UP) * quantum
        first_proposal, remaining = len(sourced), need
        if total_weight:
            for offer, weight in zip(offers, weights):
                if remaining <= 0:
                    break
                target = min(remaining, need * weight / total_weight)
                remaining -= buy(offer, requirement.due_day, target)
        if remaining > 0:
            # All offers are nominally available here: the execution fallback
            # therefore starts with the first supplied offer, as in the legacy.
            remaining -= buy(first, requirement.due_day, remaining)
        rows = sourced[first_proposal:]
        proposed = sum((Decimal(str(row.proposal.qty)) for row in rows), Decimal(0))
        surplus = proposed - net_requirement
        if grouping_days is not None:
            groups.append(ProcurementGroup(
                f"sourcing:allocated:group:{len(groups) + 1}", requirement.due_day, window_end,
                float(sum((q for r, q in members if not r.requirement_id.startswith("reserve:")), Decimal(0))),
                float(sum((q for r, q in members if r.requirement_id.startswith("reserve:")), Decimal(0))),
                float(net_requirement), float(proposed), tuple(r.requirement_id for r, _ in members),
                tuple(row.proposal.proposal_id for row in rows)))
    proposals = tuple(row.proposal for row in sourced)
    plan = _complete_plan(decision_day, float(available_qty), needs, receipts,
        proposals, supplies, committed, groups,
        net_rounding_quantum=first.lot_sizing.net_rounding_quantum)
    return SourcedPlan(plan, tuple(sourced), dates(first, decision_day)[1], 0.0, 0.0,
        fsum(row.qty for row in receipts), 0.0)


def plan_sourced_requirements(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    primary: SupplierOffer, backups: tuple[SupplierOffer, ...],
    protected_backup_receipt_ids: tuple[str, ...] = (),
    provisional_lots_until_release: bool = False,
    grouping_days: int | None = None,
    preserve_reserve_allocation: bool = False,
) -> SourcedPlan:
    """Optional purchase policy, not an inferred industrial ERP algorithm.

    Keep commitments. A backup may bridge a *physical* requirement before the
    earliest new primary delivery, only when it improves that requirement's
    availability. Technical reserve requirements never trigger a backup. Net
    backup proposals before sizing new primary purchases. Firm late purchases
    are neither cancelled nor moved; the extra horizon balance is disclosed.
    Calendars describe nominal planning availability, not executed receipts.
    The common additive candidate preserves a fixed reserve before anticipating
    physical needs and never duplicates a quantity assigned to a firm receipt.
    Review grouping is supplied explicitly; no article-specific window is inferred.
    """
    decision_day = _day(decision_day, "decision_day")
    if type(provisional_lots_until_release) is not bool:
        raise ValueError("Provisional purchase lots require an explicit boolean")
    if type(preserve_reserve_allocation) is not bool:
        raise ValueError("Reserve allocation preservation requires an explicit boolean")
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    baseline = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=needs,
        firm_receipts=receipts, lead_days=primary.lead_days, lot_sizing=primary.lot_sizing,
        grouping_days=grouping_days,
    )
    needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    offers = (primary, *backups)
    seen, calendars, prices = set(), {}, {}
    for offer in offers:
        _identity(offer.supplier_id, seen, "supplier_id")
        prices[offer.supplier_id] = _number(offer.purchase_unit_cost, "purchase_unit_cost")
        if (not isinstance(offer.currency, str) or not offer.currency.strip()
                or not isinstance(offer.uom, str) or not offer.uom.strip()
                or offer.currency != primary.currency or offer.uom != primary.uom):
            raise ValueError("Supplier prices must use the same explicit currency and physical unit")
        if _day(offer.lead_days, "lead_days") < 0:
            raise ValueError("Supplier lead must be nonnegative")
        _lot_bounds(offer.lot_sizing)
        if offer.lot_sizing.integer != primary.lot_sizing.integer:
            raise ValueError("Supplier physical integer policies must agree")
        if offer.lot_sizing.net_rounding_quantum != primary.lot_sizing.net_rounding_quantum:
            raise ValueError("Supplier net rounding policies must agree")
        if prices[offer.supplier_id] < prices[primary.supplier_id]:
            raise ValueError("Confirmed primary must have the cheapest comparable purchase price")
        calendar = tuple(offer.availability_by_release)
        if type(offer.review_calendar) is not bool or (offer.review_calendar and not calendar):
            raise ValueError("Supplier review calendar requires an explicit nonempty dated calendar")
        for index, (release, available) in enumerate(calendar):
            _day(release, "release day")
            _day(available, "available day")
            if (release < decision_day or available < release
                    or (index and ((release <= calendar[index - 1][0] if offer.review_calendar
                                    else release != calendar[index - 1][0] + 1)
                                   or available < calendar[index - 1][1]))):
                raise ValueError("Supplier calendar must have consecutive releases and monotone availability")
        if calendar and not offer.review_calendar and calendar[0][0] != decision_day:
            raise ValueError("Supplier calendar must start at the decision day")
        if calendar and calendar[-1][0] < max((r.due_day for r in needs), default=decision_day):
            raise ValueError("Supplier calendar must cover all future requirement dates")
        calendars[offer.supplier_id] = calendar
    protected = set(protected_backup_receipt_ids)
    if (len(protected) != len(protected_backup_receipt_ids)
            or not protected <= {row.receipt_id for row in receipts}):
        raise ValueError("Protected backup identities must reference unique existing firm receipts")

    if provisional_lots_until_release and backups:
        return _plan_provisional_purchase_lots(
            decision_day=decision_day, available_qty=available_qty, requirements=needs,
            firm_receipts=receipts, primary=primary, backups=backups,
            protected_backup_receipt_ids=protected_backup_receipt_ids,
            grouping_days=grouping_days, preserve_reserve_allocation=preserve_reserve_allocation,
        )

    def dates(offer, due):
        calendar = calendars[offer.supplier_id]
        if not calendar:
            release = max(decision_day, due - offer.lead_days)
            return release, release + offer.lead_days
        index = bisect_right([row[1] for row in calendar], due) - 1
        return calendar[max(0, index)]

    def calendar_proposals(plan, offer, prefix):
        return tuple(OrderProposal(
            f"{prefix}:{index}", *dates(offer, row.requested_day), row.requested_day, row.qty,
        ) for index, row in enumerate(plan.proposals, 1))

    primary_day = dates(primary, decision_day)[1]
    baseline_proposals = calendar_proposals(baseline, primary, "sourcing:primary")
    physical_needs = tuple(row for row in needs if not row.requirement_id.startswith("reserve:"))
    allocation_needs = (tuple(sorted(needs, key=lambda row: (
        row.due_day, not row.requirement_id.startswith("reserve:"), row.requirement_id)))
        if preserve_reserve_allocation else physical_needs)
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in receipts
    ]
    physical_supplies = supplies + [(p.proposal_id, p.available_day, p.qty, "proposal") for p in baseline_proposals]
    initial_allocations, missing, _ = _allocate(allocation_needs, physical_supplies)
    if missing and (not primary.lot_sizing.net_rounding_quantum or
                    sum((qty for _, qty in missing), Decimal(0)) >=
                    Decimal(str(primary.lot_sizing.net_rounding_quantum)) / 2):
        raise ArithmeticError("Primary plan must cover the physical requirements")
    physical_ids = {row.requirement_id for row in physical_needs}
    initial_shortage = fsum(a.qty for a in initial_allocations
        if a.requirement_id in physical_ids and a.due_day < primary_day and a.delay_days)
    backup_rows, backup_groups = [], []
    protected_for_bridge = protected | ({row.receipt_id for row in receipts}
                                       if preserve_reserve_allocation else set())
    # Cheapest confirmed backup first. Each newly proposed lot is netted before
    # inspecting the next requirement; its rounding surplus is not bought again.
    for offer in sorted(backups, key=lambda row: (prices[row.supplier_id], dates(row, decision_day)[1], row.supplier_id)):
        for need in physical_needs:
            if need.due_day >= primary_day:
                continue
            release, arrival = dates(offer, need.due_day)
            allocations, _, _ = _allocate(allocation_needs, physical_supplies)
            bridge_by_need = defaultdict(list)
            for allocation in allocations:
                if (allocation.requirement_id in physical_ids
                        and allocation.available_day > max(allocation.due_day, arrival)
                        and allocation.supply_id not in protected_for_bridge):
                    bridge_by_need[allocation.requirement_id].append(allocation.qty)
            bridge = fsum(bridge_by_need[need.requirement_id])
            if bridge <= 0:
                continue
            window_end = need.due_day + max(1, grouping_days or 0)
            members = [(need, bridge)]
            if offer.lot_sizing.net_rounding_quantum:
                # A previous sub-quantum rescue shortage is still physically
                # late. Carry it into the current rescue decision rather than
                # dropping each small dated quantity independently.
                members.extend((earlier, fsum(bridge_by_need[earlier.requirement_id]))
                    for earlier in physical_needs
                    if (earlier.due_day, earlier.requirement_id) < (need.due_day, need.requirement_id)
                    and bridge_by_need[earlier.requirement_id])
            if grouping_days:
                members.extend((later, fsum(bridge_by_need[later.requirement_id]))
                    for later in physical_needs
                    if later.requirement_id != need.requirement_id
                    and need.due_day <= later.due_day < min(window_end, primary_day)
                    and bridge_by_need[later.requirement_id])
            bridge = fsum(quantity for _, quantity in members)
            sized = plan_dated_requirements(
                decision_day=decision_day, available_qty=0.0,
                requirements=(Requirement(need.requirement_id, need.due_day, bridge),), firm_receipts=(),
                lead_days=offer.lead_days, lot_sizing=offer.lot_sizing,
            )
            group_proposal_ids = []
            for row in sized.proposals:
                proposal = OrderProposal(f"sourcing:backup:{len(backup_rows) + 1}", release, arrival, need.due_day, row.qty)
                backup_rows.append(SourcedProposal(proposal, offer.supplier_id, "backup",
                                                   "physical_shortage_before_primary", bridge))
                physical_supplies.append((proposal.proposal_id, arrival, proposal.qty, "proposal"))
                group_proposal_ids.append(proposal.proposal_id)
            if grouping_days is not None:
                backup_groups.append(ProcurementGroup(
                    f"sourcing:backup:group:{len(backup_groups) + 1}", need.due_day, window_end,
                    bridge, 0.0, bridge, fsum(row.qty for row in sized.proposals),
                    tuple(row.requirement_id for row, _ in members), tuple(group_proposal_ids)))
    # Temporary netting does not turn an unexecuted backup into a firm order in
    # the returned plan. It only prevents a second new primary purchase for it.
    temporary_firms = receipts + tuple(FirmReceipt(row.proposal.proposal_id, row.proposal.available_day,
                                                  row.proposal.qty, "confirmed") for row in backup_rows)
    primary_net = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=needs,
        firm_receipts=temporary_firms, lead_days=primary.lead_days, lot_sizing=primary.lot_sizing,
        grouping_days=grouping_days,
    )
    primary_proposals = calendar_proposals(primary_net, primary, "sourcing:primary")
    sourced = tuple(backup_rows) + tuple(SourcedProposal(row, primary.supplier_id, "primary",
                                                        "cheapest_confirmed_purchase_price") for row in primary_proposals)
    proposals = tuple(row.proposal for row in sourced)
    ids = {row[0] for row in supplies}
    if any(row.proposal_id in ids for row in proposals):
        raise ValueError("Firm receipt id collides with a sourced proposal id")
    # A technical reserve cannot absorb a rescue before its physical purpose.
    # Balances still retain every reserve event separately at its original date.
    if not preserve_reserve_allocation:
        allocation_needs = physical_needs + tuple(row for row in needs if row.requirement_id.startswith("reserve:"))
    commitments, _, _ = _allocate(allocation_needs, supplies)
    primary_ids = {old.proposal_id: new.proposal_id
                   for old, new in zip(primary_net.proposals, primary_proposals)}
    groups = tuple(backup_groups) + tuple(replace(group,
        group_id=f"sourcing:primary:{group.group_id}",
        proposal_ids=tuple(primary_ids[identity] for identity in group.proposal_ids))
        for group in primary_net.procurement_groups)
    plan = _complete_plan(decision_day, float(available_qty), allocation_needs, receipts,
                          proposals, supplies, commitments, groups,
                          net_rounding_quantum=primary.lot_sizing.net_rounding_quantum)
    return SourcedPlan(
        plan, sourced, primary_day, initial_shortage, fsum(row.proposal.qty for row in backup_rows),
        fsum(row.qty for row in receipts), max(0.0, plan.proposed_qty - baseline.proposed_qty),
    )


def _plan_provisional_purchase_lots(
    *, decision_day, available_qty, requirements, firm_receipts,
    primary, backups, protected_backup_receipt_ids,
    grouping_days=None, preserve_reserve_allocation=False,
):
    """Candidate lotting, not inferred purchase documents or supplier promises.

    Future proposals use the smallest declared positive standard in separate
    blocks. Only releases due now use the selected supplier's actual lot policy.
    Re-net after EACH such release, crediting its full rounded quantity once.
    Temporary receipts are local calculation objects, never persisted orders.
    Existing sourcing rules still handle dated rescue and protected commitments.
    """
    offers = (primary, *backups)
    standards = []
    for offer in offers:
        # Older pure callers specify their standard through the binding lot
        # policy. Runtime supplies the source standard separately, including
        # when it is explicitly nonbinding for actual purchase execution.
        standard = (offer.standard_order_qty if offer.standard_order_qty is not None
                    else max(offer.lot_sizing.minimum, offer.lot_sizing.multiple))
        standard = _number(standard, "source standard order quantity")
        if standard:
            standards.append(standard)
    if not standards:
        raise ValueError("Provisional purchase lots need a positive declared standard")
    quantum = min(standards)
    provisional_policy = LotSizing(minimum=quantum, multiple=quantum, maximum=quantum,
                                   integer=primary.lot_sizing.integer,
                                   net_rounding_quantum=primary.lot_sizing.net_rounding_quantum)
    _lot_bounds(provisional_policy)
    tentative_offers = tuple(replace(offer, lot_sizing=provisional_policy) for offer in offers)
    actual_offers = {offer.supplier_id: offer for offer in offers}
    released, released_groups = [], []
    temporary = tuple(firm_receipts)
    protected = tuple(protected_backup_receipt_ids)
    first_plan = None
    while True:
        candidate = plan_sourced_requirements(
            decision_day=decision_day, available_qty=available_qty,
            requirements=requirements, firm_receipts=temporary,
            primary=tentative_offers[0], backups=tentative_offers[1:],
            protected_backup_receipt_ids=protected,
            grouping_days=grouping_days, preserve_reserve_allocation=preserve_reserve_allocation,
        )
        if first_plan is None:
            first_plan = candidate
        due = next((row for row in candidate.proposals if row.proposal.release_day <= decision_day), None)
        if due is None:
            break
        offer = actual_offers[due.supplier_id]
        # Do not mistake unused provisional rounding surplus for a net need.
        due_rows = [due]
        if grouping_days:
            due_rows.extend(row for row in candidate.proposals
                if row != due and row.supplier_id == due.supplier_id
                and row.role == due.role and row.proposal.release_day <= decision_day
                and due.proposal.requested_day <= row.proposal.requested_day
                < due.proposal.requested_day + grouping_days)
        assigned_by_id = defaultdict(list)
        for allocation in candidate.plan.allocations:
            assigned_by_id[allocation.supply_id].append(allocation.qty)
        quantity_to_size = fsum(min(row.proposal.qty,
            fsum(assigned_by_id[row.proposal.proposal_id])) for row in due_rows)
        if quantity_to_size <= 0:
            raise ArithmeticError("An exigible provisional purchase has no allocated need")
        sized = plan_dated_requirements(
            decision_day=decision_day, available_qty=0,
            requirements=(Requirement("release_net_need", due.proposal.requested_day, quantity_to_size),),
            firm_receipts=(), lead_days=offer.lead_days, lot_sizing=offer.lot_sizing,
        )
        if not sized.proposals:
            raise ArithmeticError("An exigible purchase must make positive netting progress")
        release_ids = []
        for row in sized.proposals:
            identity = f"sourcing:release:{len(released) + 1}"
            if identity in {r.receipt_id for r in temporary}:
                raise ValueError("Firm receipt collides with a candidate release identity")
            proposal = replace(due.proposal, proposal_id=identity, qty=row.qty)
            released.append(replace(due, proposal=proposal,
                reason=due.reason + ":supplier_lot_at_release"))
            release_ids.append(identity)
            temporary += (FirmReceipt(identity, proposal.available_day, proposal.qty, "confirmed"),)
            if due.role == "backup":
                protected += (identity,)
        if grouping_days is not None:
            source_ids = {row.proposal.proposal_id for row in due_rows}
            members = tuple(allocation for allocation in candidate.plan.allocations
                            if allocation.supply_id in source_ids)
            reserve = fsum(row.qty for row in members if row.requirement_id.startswith("reserve:"))
            released_groups.append(ProcurementGroup(
                f"sourcing:release:group:{len(released_groups) + 1}", due.proposal.requested_day,
                due.proposal.requested_day + max(1, grouping_days or 0),
                max(0.0, quantity_to_size - reserve), reserve, quantity_to_size,
                fsum(row.qty for row in sized.proposals),
                tuple(dict.fromkeys(row.requirement_id for row in members)), tuple(release_ids)))
    future = tuple(replace(row, supplier_id="", role="provisional",
        reason="minimum_admissible_standard_supplier_not_committed",
        planning_supplier_id=row.supplier_id) for row in candidate.proposals)
    sourced = tuple(released) + future
    proposals = tuple(row.proposal for row in sourced)
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in firm_receipts]
    # Preserve the existing physical-before-reserve allocation convention.
    allocation_needs = (tuple(sorted(requirements, key=lambda row: (
        row.due_day, not row.requirement_id.startswith("reserve:"), row.requirement_id)))
        if preserve_reserve_allocation else
        tuple(row for row in requirements if not row.requirement_id.startswith("reserve:")) + tuple(
            row for row in requirements if row.requirement_id.startswith("reserve:")))
    commitments, _, _ = _allocate(allocation_needs, supplies)
    plan = _complete_plan(decision_day, available_qty, allocation_needs, firm_receipts,
                          proposals, supplies, commitments,
                          tuple(released_groups) + candidate.plan.procurement_groups,
                          net_rounding_quantum=primary.lot_sizing.net_rounding_quantum)
    return SourcedPlan(plan, sourced, first_plan.primary_available_day,
        first_plan.physical_shortage_before_primary_qty,
        fsum(row.proposal.qty for row in released if row.role == "backup"),
        fsum(row.qty for row in firm_receipts),
        max(0.0, plan.proposed_qty - first_plan.plan.proposed_qty))
