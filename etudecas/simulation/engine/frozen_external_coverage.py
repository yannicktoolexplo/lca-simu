"""Fixed-supply oracle for explicitly traced, revisable residual forecasts.

This helper creates no order. It allocates one existing pool twice as separate
views: physical requirements, then anticipatory protection. Those views are
never added as two physical consumptions. Its result is conditional planning
coverage, not a promise of material delivery or industrial validation.
"""
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
import math
import re

from .mrp_planning import Requirement, _allocate

EPS = Decimal("0.000001")


def _q(value):
    if isinstance(value,bool) or not math.isfinite(value) or value < 0:
        raise ValueError("Nonnegative finite coverage quantities required")
    return Decimal(str(value))


def _rows(rows):
    result = {}
    for row in rows:
        if not isinstance(row.requirement_id,str) or not row.requirement_id or row.requirement_id in result:
            raise ValueError("Unique requirement identities required")
        if type(row.due_day) is not int or row.due_day < 0:
            raise ValueError("Explicit nonnegative requirement dates required")
        _q(row.qty)
        result[row.requirement_id] = row
    return result


def _source_proof(before,after,pair,day,inputs,raw_ids):
    old_audit,new_audit = before[3][pair],after[3][pair]
    unit = (inputs.get("item_uoms") or {}).get(pair,(inputs.get("item_uoms") or {}).get(pair[1]))
    if not isinstance(unit,str) or not unit:
        raise ValueError("Missing explicit component unit")
    policy = old_audit.get("industrial_requirement_reconciliation_policy")
    if policy != new_audit.get("industrial_requirement_reconciliation_policy"):
        raise ValueError("Industrial normalization policy changed")
    fields = ("period_start_day","first_day","end_day_exclusive","known_day","source_file","source_cells","source_qty")
    def audit_windows(audit):
        if "industrial_windows" not in audit:
            raise ValueError("Missing industrial normalization provenance")
        return tuple(sorted(tuple(row[key] for key in fields) for row in audit["industrial_windows"]))
    old_windows,new_windows = audit_windows(old_audit),audit_windows(new_audit)
    source = tuple(sorted((w.period_start_day,w.first_day,w.end_day_exclusive,w.known_day,
        w.source_file,w.source_cells,w.qty) for w in (inputs.get("industrial_windows_by_pair") or {}).get(pair,())))
    if not source or old_windows != new_windows or old_windows != source:
        raise ValueError("Source windows, versions or source quantities are not identical")
    windows = {}
    for period,first,end,known,file,cells,qty in source:
        if known > day or first <= day or not period <= first < end <= period+7 or not file or not cells or period in windows:
            raise ValueError("Industrial source window is ambiguous or not yet known")
        _q(qty);windows[period] = (first,end)
    raw = _rows((inputs.get("requirements_by_pair") or {}).get(pair,()))
    if not set(raw_ids) <= set(raw):
        raise ValueError("Missing original external requirement provenance")
    old,new = _rows(before[2].get(pair,())),_rows(after[2].get(pair,()))
    for identity in raw_ids:
        row = raw[identity]
        if identity not in old or identity not in new:
            if not identity.startswith("external:") or not any(first <= row.due_day < end for first,end in windows.values()):
                raise ValueError("Disappearing root requirement has no explicit industrial window")
    pattern = re.compile(r"external:industrial-(planning|authoritative):"+re.escape(pair[0]+":"+pair[1])+r":W(\d+):D(\d+)(?::part\d+)?$")
    revisable = set()
    for row in tuple(old.values())+tuple(new.values()):
        if not row.requirement_id.startswith("external:"):
            continue
        if row.requirement_id in raw:
            original = raw[row.requirement_id]
            if original.due_day != row.due_day or abs(_q(original.qty)-_q(row.qty)) > EPS:
                raise ValueError("Unmapped external root quantity/date changed")
            continue
        match = pattern.fullmatch(row.requirement_id)
        if match is None or int(match[2]) not in windows:
            raise ValueError("Unknown external normalization identity or alias")
        first,end = windows[int(match[2])]
        if int(match[3]) != row.due_day or not first <= row.due_day < end:
            raise ValueError("Normalized external requirement is outside its source window")
        if match[1] == "authoritative" and policy != "source_weekly_with_committed_floor_v1":
            raise ValueError("Authoritative requirement lacks its declared policy")
        revisable.add(row.requirement_id)
    for identity,row in old.items():
        if identity.startswith("external:") and identity not in revisable:
            current = new.get(identity)
            if current is None or current.due_day != row.due_day or abs(_q(current.qty)-_q(row.qty)) > EPS:
                raise ValueError("An existing external commitment cannot disappear or change")
    for normalized,audit in ((old,old_audit),(new,new_audit)):
        for window in audit["industrial_windows"]:
            external = sum((_q(row.qty) for row in normalized.values()
                if row.requirement_id.startswith("external:")
                and window["first_day"] <= row.due_day < window["end_day_exclusive"]),Decimal(0))
            if "complement_qty" not in window or abs(external-_q(window["complement_qty"])) > EPS:
                raise ValueError("Normalized external quantities do not match the source-window reconciliation audit")
    return old,new,dict(unit=unit,normalization_policy=policy or "default_total_complement",
        source_window_count=len(source),knowledge_cutoff_day=day),frozenset(revisable)


def _pool(result,pair,day):
    plan,audit = result[1][pair],result[3][pair]
    if plan.decision_day != day or "firm_receipts" not in audit:
        raise ValueError("Missing current native fixed-supply evidence")
    result = [("opening_stock",day,plan.opening_available_qty,"available")]
    result.extend((r.receipt_id,r.available_day,r.qty,r.state) for r in audit["firm_receipts"])
    result.extend((p.proposal_id,p.available_day,p.qty,"proposal") for p in plan.proposals)
    if len({r[0] for r in result}) != len(result):
        raise ValueError("A fixed supply identity is credited more than once")
    for identity,when,qty,_ in result:
        if not identity or type(when) is not int or when < day:
            raise ValueError("Invalid fixed receipt identity or availability")
        _q(qty)
    return result


def _allocate_fixed(rows,pool):
    return _allocate(tuple(sorted(rows,key=lambda r:(r.due_day,r.requirement_id))),pool)[0]


def _by_requirement(allocations):
    result = defaultdict(list)
    for row in allocations:
        result[row.requirement_id].append(row)
    return result


def _covered(rows,when):
    return sum((_q(a.qty) for a in rows if a.available_day <= when),Decimal(0))


def _minimum_coverage(old_external,union_external,own,old_allocations,own_allocations,union_allocations,day,old_rows):
    old_by,own_by,new_by = (_by_requirement(a) for a in (old_allocations,own_allocations,union_allocations))
    checks = 0
    retained = {**union_external,**own}
    for identity in sorted(retained):
        need = retained[identity]
        due = max(day,need.due_day)
        dates = {due}
        for collection in (old_by,own_by,new_by):
            dates.update(a.available_day for a in collection[identity] if a.available_day >= due)
        increment = max(Decimal(0),_q(need.qty)-_q(old_external[identity].qty)) if identity in old_external else _q(need.qty)
        for when in sorted(dates):
            minimum = (_covered(own_by[identity],when) if identity in own else
                       min(_covered(old_by[identity],when),_q(need.qty))+increment)
            previous = old_rows.get(identity)
            if (identity in own and previous is not None and previous.due_day == need.due_day
                    and abs(_q(previous.qty)-_q(need.qty)) <= EPS):
                minimum = max(minimum,_covered(old_by[identity],when))
            actual = _covered(new_by[identity],when)
            checks += 1
            if actual + EPS < minimum:
                return False,dict(day=when,requirement_id=identity,
                    obligation="remaining_own" if identity in own else "retained_external_requirement",
                    required_covered_qty=float(minimum),covered_qty=float(actual),shortfall_qty=float(minimum-actual)),checks
    return True,None,checks


def _step(points,when,default=Decimal(0)):
    return next((value for date,value in reversed(sorted(points.items())) if date <= when),default)


def _balance(pool,needs,when):
    return sum((_q(qty) for _,date,qty,_ in pool if date <= when),Decimal(0))-sum(
        (_q(r.qty) for r in needs if r.due_day <= when),Decimal(0))


def _dynamic_source_floor(before,after,pair,inputs):
    """Authorize only documented rolling quantities, never altered parameters."""
    context = (inputs.get("source_safety_by_pair") or {}).get(pair)
    if not context or not context.get("projection"):
        return None
    if pair in (inputs.get("safety_requirements_by_pair") or {}):
        return None  # A separate source override requires its own provenance oracle.
    projection = context["projection"]
    fields = ("projection_policy","forecast_through_day","prospective_safety_source_days","fixed_source_qty","window_days")
    audits = [result[3][pair].get("chain_source_safety") for result in (before,after)]
    if not all(audits) or any(audits[0].get(k) != audits[1].get(k) for k in fields):
        raise ValueError("Dynamic protection parameters are missing or changed")
    expected = ("rolling_source_workdays_v1",projection["forecast_through_day"],
        projection["source_working_days"],context["fixed_qty"],math.ceil(context["safety_days"]))
    if tuple(audits[1].get(k) for k in fields) != expected:
        raise ValueError("Dynamic protection audit differs from source parameters")
    if any(a.get("weekly_protection_rule") for a in audits):
        return None  # Keep maximum until the separate review-calendar contract is proved.
    details = after[3][pair].get("prospective_checkpoints")
    if not isinstance(details,dict):
        raise ValueError("Dynamic protection checkpoints lack source evidence")
    requirements = tuple(after[2].get(pair,()))
    # The native tail is not a fixed industrial stock quantity: it repeats
    # max(fixed source floor, needs in the current decision's source window).
    # Allow its revision only when both native calculations publish and match
    # that formula. An untraced or otherwise unknown tail stays conservative.
    legacy = None
    legacy_fields = ("dated_requirement_qty","historical_constant_target_qty","prospective_safety_legacy_qty","basis")
    if all(all(k in audit for k in legacy_fields) for audit in audits):
        cutoff = after[1][pair].decision_day
        window = math.ceil(context["safety_days"])
        if (before[1][pair].decision_day != cutoff
                or cutoff+window > projection["forecast_through_day"]):
            raise ValueError("The fallback source window is not known at this decision")
        for result,audit in zip((before,after),audits):
            amount = sum((_q(r.qty) for r in result[2].get(pair,())
                if cutoff < r.due_day <= cutoff+window),Decimal(0))
            expected_legacy = max(_q(context["fixed_qty"]),amount)
            if (audit["basis"] != "future_dated_requirements_once_no_overdue_backlog_no_lot_as_daily_rate"
                    or abs(_q(audit["dated_requirement_qty"])-amount) > EPS
                    or any(abs(_q(audit[k])-expected_legacy) > EPS for k in legacy_fields[1:3])
                    or "prospective_safety_legacy_qty" not in result[3][pair]
                    or abs(_q(result[3][pair]["prospective_safety_legacy_qty"])-expected_legacy) > EPS):
                raise ValueError("Fallback quantity does not match its dated source-window formula")
            legacy = expected_legacy
    proven = {}
    for point in after[3][pair]["protection_points"]:
        record = details.get(point.day,details.get(str(point.day)))
        if not record:
            raise ValueError("A dynamic protection checkpoint is untraced")
        covered = record.get("safety_window_covered") == 1
        end = point.day;count = 0
        while count < projection["source_working_days"]:
            end += 1;count += (projection["origin_weekday"]+end)%7 < 5
        if covered:
            quantity = sum((_q(r.qty) for r in requirements if point.day < r.due_day <= end),Decimal(0))
            target = max(_q(context["fixed_qty"]),quantity)
            if (end != record["safety_window_end_day"] or end > projection["forecast_through_day"]
                    or abs(quantity-_q(record["safety_window_need_qty"])) > EPS
                    or abs(target-_q(point.minimum_qty)) > EPS
                    or abs(target-_q(record["safety_source_floor_qty"])) > EPS):
                raise ValueError("Dynamic protection quantity is inconsistent with dated maintained needs")
        elif legacy is not None:
            if (record.get("safety_window_covered") != 0 or end <= projection["forecast_through_day"]
                    or end != record["safety_window_end_day"]
                    or record.get("safety_window_need_qty") not in ("",None)
                    or abs(_q(record["safety_source_floor_qty"])-legacy) > EPS
                    or abs(_q(point.minimum_qty)-legacy) > EPS):
                raise ValueError("Fallback checkpoint does not preserve the proven source-window quantity")
        proven[point.day] = covered or legacy is not None
    return proven


def _physical_floors(before,after,pair,day,pool,union,inputs):
    if any("protection_points" not in result[3][pair] for result in (before,after)):
        raise ValueError("Missing explicit native physical protection checkpoints")
    floors = [{p.day:_q(p.minimum_qty) for p in result[3][pair]["protection_points"]} for result in (before,after)]
    native = [{b.day:Decimal(str(b.after_proposals_qty)) for b in result[1][pair].balances} for result in (before,after)]
    dynamic = _dynamic_source_floor(before,after,pair,inputs)
    # The source policy rounds net mass purchases to the nearest kilogram.
    # It never rounds stock, a firm receipt, a requirement, or physical UN.
    unit = (inputs.get("item_uoms") or {}).get(pair,(inputs.get("item_uoms") or {}).get(pair[1]))
    source_quantum = {"KG":Decimal(1),"G":Decimal(1000)}.get(unit,Decimal(0))
    lot = (inputs.get("lot_sizing_by_pair") or {}).get(pair)
    quantum = Decimal(0)
    if (source_quantum and lot is not None and not lot.integer
            and _q(lot.net_rounding_quantum) == source_quantum
            and all(_q(result[1][pair].net_rounding_quantum) == source_quantum for result in (before,after))):
        quantum = source_quantum
    rounding_residuals = []
    dates = {day}|set(floors[0])|set(floors[1])|{r.due_day for r in union}|{r[1] for r in pool}|set(native[0])|set(native[1])
    for when in sorted(d for d in dates if d >= day):
        revised = dynamic is not None and _step(dynamic,when,False)
        floor = _step(floors[1],when) if revised else max(_step(floors[0],when),_step(floors[1],when))
        balance = _balance(pool,union,when)
        deficit = max(Decimal(0),floor-balance)
        allowed = max(Decimal(0),_step(floors[0],when)-_step(native[0],when,
            _q(before[1][pair].opening_available_qty)))
        if deficit > allowed + EPS:
            fixed = _q((inputs.get("source_safety_by_pair") or {}).get(pair,{}).get("fixed_qty",0))
            # Match the native strict HALF_UP residual contract, not an added
            # tolerance per event. The complete deficit must be below half a
            # quantum. Physical balances, fixed floors and dated allocations
            # remain exact; no quantity or receipt is invented.
            if (revised and quantum and floor > fixed and balance >= fixed and balance >= 0
                    and deficit < quantum/2
                    and abs(balance-_step(native[1],when,_q(after[1][pair].opening_available_qty))) <= EPS):
                rounding_residuals.append(dict(day=when,target_qty=float(floor),projected_qty=float(balance),
                    shortfall_qty=float(deficit),allowed_existing_shortfall_qty=float(allowed),
                    quantum_qty=float(quantum),strict_half_quantum_limit_qty=float(quantum/2),
                    fixed_source_qty=float(fixed),uom=unit,policy="nearest_kg_half_up_v1"))
                continue
            return False,dict(day=when,target_qty=float(floor),shortfall_qty=float(deficit),allowed_existing_shortfall_qty=float(allowed)),rounding_residuals
    return True,None,rounding_residuals


def _anticipated_view(before,after,pair,day,inputs,old,new,external,own,pool):
    old_audit,new_audit = before[3][pair],after[3][pair]
    contexts = inputs.get("anticipated_need_by_pair") or {}
    has = ["anticipated_requirements" in audit or "anticipated_plan" in audit for audit in (old_audit,new_audit)]
    if not any(has) and pair not in contexts:
        return True,dict(status="not_applicable")
    context = contexts.get(pair)
    fields = ("anticipated_safety_working_days","anticipated_fixed_floor_qty","anticipated_fixed_floor_mode")
    if not context or not all(has) or any(old_audit.get(k) != new_audit.get(k) for k in fields):
        raise ValueError("Anticipation source/calendar provenance is missing or changed")
    days,weekday = context["source_working_days"],context["origin_weekday"]
    fixed,mode = context["fixed_floor_qty"],context.get("fixed_floor_mode","maximum")
    if (type(days) is not int or days < 0 or type(weekday) is not int or not 0 <= weekday < 7
            or (days,fixed,mode) != tuple(new_audit[k] for k in fields)):
        raise ValueError("Anticipation audit does not match its declared source parameters")
    def shift(rows):
        result = {}
        for identity,row in rows.items():
            elapsed = count = 0
            while count < days:
                elapsed += 1;count += (weekday+row.due_day-elapsed)%7 < 5
            result[identity] = replace(row,due_day=max(day,row.due_day-elapsed))
        return result
    old_early,new_early,external_early,own_early = (shift(rows) for rows in (old,new,external,own))
    if mode == "additive" and fixed:
        identity = "frozen_reduction:fixed_anticipation_floor"
        if any(identity in rows for rows in (old_early,new_early,external_early,own_early)):
            raise ValueError("Ambiguous fixed anticipation reserve identity")
        floor = Requirement(identity,day,fixed)
        old_early[identity]=new_early[identity]=own_early[identity]=floor
    elif mode != "maximum" and mode != "additive":
        raise ValueError("Unknown anticipation fixed-floor mode")
    union_early = tuple(own_early.values())+tuple(external_early.values())
    old_alloc = _allocate_fixed(old_early.values(),_pool(before,pair,day))
    own_alloc = _allocate_fixed(new_early.values(),pool)
    union_alloc = _allocate_fixed(union_early,pool)
    old_external = {k:v for k,v in old_early.items() if k.startswith("external:")}
    allowed,first,checks = _minimum_coverage(old_external,external_early,own_early,old_alloc,own_alloc,union_alloc,day,old_early)
    if not allowed:
        return False,dict(status="refused",reason="anticipated_obligation_coverage_worsened",first_worsening=first,checks=checks)
    # Native anticipated requirements are a separate cumulative envelope. Keep
    # its existing deficit bound while applying the union, without consuming it twice.
    native = tuple(new_audit["anticipated_requirements"])
    old_native = tuple(old_audit["anticipated_requirements"])
    old_pool = _pool(before,pair,day)
    dates = ({day}|{r.due_day for r in union_early}|{r.due_day for r in native}
        |{r.due_day for r in old_native}|{r[1] for r in pool}|{r[1] for r in old_pool})
    physical_union = tuple(own.values())+tuple(external.values())
    dates.update(r.due_day for r in physical_union)
    for when in sorted(d for d in dates if d >= day):
        supplied = sum((_q(qty) for _,date,qty,_ in pool if date <= when),Decimal(0))
        early = sum((_q(r.qty) for r in union_early if r.due_day <= when),Decimal(0))
        required = early if mode == "additive" else max(early,
            sum((_q(r.qty) for r in physical_union if r.due_day <= when),Decimal(0))+_q(fixed))
        native_required = sum((_q(r.qty) for r in native if r.due_day <= when),Decimal(0))
        old_required = sum((_q(r.qty) for r in old_native if r.due_day <= when),Decimal(0))
        old_supplied = sum((_q(qty) for _,date,qty,_ in old_pool if date <= when),Decimal(0))
        original_deficit = max(Decimal(0),old_required-old_supplied)
        candidate_deficit = max(Decimal(0),native_required-supplied)
        shortage,permitted = max(Decimal(0),required-supplied),min(original_deficit,candidate_deficit)
        if shortage > permitted+EPS:
            return False,dict(status="refused",reason="candidate_anticipation_envelope_eroded",day=when,
                shortfall_qty=float(shortage),allowed_existing_shortfall_qty=float(permitted),
                original_shortfall_qty=float(original_deficit),candidate_shortfall_qty=float(candidate_deficit),checks=checks)
    return True,dict(status="passed_fixed_supply_view",checks=checks,source_working_days=days)


def assess_frozen_external_coverage(*, before,after,pair,day,network_inputs,raw_requirement_ids):
    """Assess changed normalization against fixed supplies; never re-plan."""
    try:
        old,new,source,revisable = _source_proof(before,after,pair,day,network_inputs,raw_requirement_ids)
        old_external = {k:v for k,v in old.items() if k.startswith("external:")}
        new_external = {k:v for k,v in new.items() if k.startswith("external:")}
        external = {}
        for identity in sorted(set(old_external)|set(new_external)):
            left,right = old_external.get(identity),new_external.get(identity)
            if identity in revisable:
                if right is not None:
                    external[identity] = right
                continue
            if left is not None and right is not None and left.due_day != right.due_day:
                raise ValueError("External identity changed date without a source alias")
            original = right if right is not None else left
            external[identity] = replace(original,qty=float(max(_q(left.qty) if left else Decimal(0),_q(right.qty) if right else Decimal(0))))
        own = {k:v for k,v in new.items() if not k.startswith("external:")}
        pool = _pool(after,pair,day)
        firm_signatures = [tuple(sorted((r.receipt_id,r.available_day,r.qty,r.state)
            for r in result[3][pair]["firm_receipts"])) for result in (before,after)]
        if firm_signatures[0] != firm_signatures[1]:
            raise ValueError("Existing firm receipt quantities or dates changed")
        if abs(_q(before[1][pair].opening_available_qty)-_q(after[1][pair].opening_available_qty)) > EPS:
            raise ValueError("Opening material stock changed in a planning counterfactual")
        union = tuple(own.values())+tuple(external.values())
        allocations = _allocate_fixed(union,pool)
        allowed,first,checks = _minimum_coverage(old_external,external,own,
            before[1][pair].allocations,after[1][pair].allocations,allocations,day,old)
        evidence = dict(source,physical_checks=checks,
            fixed_supply_count=len(pool),fixed_supply_qty=float(sum((_q(row[2]) for row in pool),Decimal(0))),
            retained_external_qty=float(sum((_q(r.qty) for r in external.values()),Decimal(0))),
            revisable_forecast_count=len(revisable),
            revised_forecast_qty=float(sum((_q(r.qty) for k,r in external.items() if k in revisable),Decimal(0))),
            remaining_own_qty=float(sum((_q(r.qty) for r in own.values()),Decimal(0))),
            new_external_qty=float(sum((max(Decimal(0),_q(row.qty)-_q(old_external[k].qty))
                if k in old_external else _q(row.qty) for k,row in new_external.items()),Decimal(0))),
            creates_proposals=False)
        if not allowed:
            return False,dict(evidence,reason="fixed_supply_external_or_own_coverage_worsened",first_worsening=first)
        protected,floor,rounding = _physical_floors(before,after,pair,day,pool,union,network_inputs)
        evidence["dynamic_safety_rounding_residuals"] = rounding
        if all("prospective_safety_legacy_qty" in result[3][pair] for result in (before,after)):
            evidence["native_source_safety_fallback_qty"] = dict(
                before=before[3][pair]["prospective_safety_legacy_qty"],
                after=after[3][pair]["prospective_safety_legacy_qty"])
        if not protected:
            return False,dict(evidence,reason="fixed_supply_revised_protection_worsened",first_worsening=floor)
        early,early_evidence = _anticipated_view(before,after,pair,day,network_inputs,old,new,external,own,pool)
        return early,dict(evidence,reason="fixed_supply_revised_coverage_not_worsened" if early else "fixed_supply_revised_anticipation_worsened",
            anticipation=early_evidence)
    except (KeyError,TypeError,ValueError) as exc:
        return False,dict(reason="external_forecast_provenance_or_fixed_supply_invalid",detail=str(exc),creates_proposals=False)
