"""Pure, conservative material split for already-engaged production campaigns.

The original usable stock and firm receipts are never changed. A virtual pool
only limits old-reference allocations across campaigns; it creates no purchase,
physical consumption, finished output credit, or new reference transition.
"""
from collections.abc import Mapping
from decimal import Decimal, ROUND_FLOOR
import json
import math


EPS = 1e-9
SUPPORTED_POLICY = "use_old_until_new_stock_available"


def _quantity(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return Decimal(str(value))


def _pair(value):
    if not isinstance(value, tuple) or len(value) != 2 or any(not isinstance(v, str) or not v for v in value):
        raise ValueError("Material identities must be explicit (site, item) tuples")
    return value


def _field(row, key):
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def allocate_campaign_materials(*, decision_day, active_campaigns_by_pair, bom_by_pair,
        available_by_pair, firm_receipts_by_pair, requirements_by_pair, reserve_targets_by_pair,
        reference_substitutes_by_pair=None, item_uoms=None, protected_component_pairs=()):
    """Allocate remaining BOM1:1 to current old stock only when safely eligible.

    Campaign tuples are (id, remaining_work, executed_WIP, expected_finish_day).
    Transition dictionaries use node_id/new_item_id/old_item_id/start_day/end_day/
    consume_policy, as the existing execution path. An omitted ratio means its
    existing1:1 semantics. Units must still be explicit for both references.
    The caller must protect unresolved competing BOM/transport/safety scopes.
    """
    if type(decision_day) is not int or decision_day < 0:
        raise ValueError("Campaign decision day must be a nonnegative integer")
    units = item_uoms or {}
    def unit(pair):
        value = units.get(pair, units.get(pair[1]))
        return value.strip().upper() if isinstance(value, str) else ""
    pool = {}
    for pair, value in available_by_pair.items():
        _pair(pair); pool[pair] = _quantity(value, "Usable stock")
        if unit(pair) == "UN" and pool[pair] != pool[pair].to_integral_value():
            raise ValueError("Physical UN usable stock must be integer")
    reserves = {_pair(p): _quantity(q, "Reserve target") for p, q in reserve_targets_by_pair.items()}
    own_needs = set()
    for pair, rows in requirements_by_pair.items():
        _pair(pair)
        quantities = [_quantity(_field(r, "qty"), "Own requirement") for r in rows]
        if any(qty > EPS for qty in quantities):
            own_needs.add(pair)
    receipts = {}
    for pair, rows in firm_receipts_by_pair.items():
        _pair(pair); receipts[pair] = []
        for row in rows:
            qty = _quantity(_field(row, "qty"), "Firm receipt")
            day = _field(row, "available_day")
            if type(day) is not int or day < 0:
                raise ValueError("Firm receipt availability must be a nonnegative integer")
            receipts[pair].append((day, qty))
    protected = {_pair(p) for p in protected_component_pairs}
    campaigns = []
    for output, row in active_campaigns_by_pair.items():
        _pair(output)
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise ValueError("Campaign requires id, remaining work, executed WIP and finish day")
        identity, remaining, wip, finish = row
        if not isinstance(identity, str) or not identity or type(finish) is not int or finish < decision_day:
            raise ValueError("Campaign identity and expected finish must be explicit and causal")
        remaining = _quantity(remaining, "Remaining campaign work")
        wip = _quantity(wip, "Executed campaign WIP")
        campaigns.append((output, identity, remaining, wip, finish))
    allocations, audits = {}, {}
    for output, identity, remaining, wip, finish in sorted(campaigns):
        rows, components, seen = [], [], set()
        for component, ratio in bom_by_pair.get(output, ()):
            _pair(component)
            if component in seen:
                raise ValueError("Campaign BOM components must be unique")
            seen.add(component)
            _quantity(ratio, "BOM ratio")
            # Preserve the existing float BOM calculation exactly when no
            # material is substituted; Decimal only partitions that quantity.
            legacy_needed = active_campaigns_by_pair[output][1] * ratio
            if not math.isfinite(legacy_needed):
                raise ValueError("Remaining BOM requirement must be finite")
            needed = Decimal(str(legacy_needed))
            left = needed
            principal_id = "campaign:" + identity + ":" + "|".join(component)
            attempts = []
            for index, transition in enumerate((reference_substitutes_by_pair or {}).get(component, ())):
                if left <= EPS:
                    break
                attempt = dict(transition_index=index, required_pair=component, allocated_qty=0.0)
                if not isinstance(transition, Mapping):
                    attempt["reason"] = "invalid_transition"
                    attempts.append(attempt); continue
                old_item = transition.get("old_item_id")
                old = (component[0], old_item) if isinstance(old_item, str) and old_item else None
                start, end = transition.get("start_day"), transition.get("end_day")
                ratio_keys = ("ratio", "conversion_ratio", "conversion_factor")
                reason = None
                if (old is None or old == component or transition.get("node_id") != component[0]
                        or transition.get("new_item_id") != component[1]):
                    reason = "reference_or_site_mismatch"
                elif transition.get("consume_policy") != SUPPORTED_POLICY:
                    reason = "unsupported_policy"
                elif any(isinstance(transition[k], bool) or not isinstance(transition[k], (int, float))
                         or transition[k] != 1 for k in ratio_keys if k in transition):
                    reason = "non_unit_ratio"
                elif (not unit(component) or not unit(old) or unit(component) != unit(old)
                        or (transition.get("uom") is not None
                            and str(transition["uom"]).strip().upper() != unit(component))):
                    reason = "units_missing_or_mismatched"
                elif type(start) is not int or type(end) is not int or not start <= decision_day <= finish <= end:
                    reason = "transition_not_active_through_finish"
                elif Decimal(str(available_by_pair.get(component, 0))) > EPS:
                    reason = "principal_usable_stock_positive"
                elif any(day <= finish and qty > EPS for day, qty in receipts.get(component, ())):
                    reason = "principal_firm_receipt_before_finish"
                elif old in protected:
                    reason = "protected_competing_scope"
                elif old in own_needs:
                    reason = "substitute_has_own_requirements"
                elif reserves.get(old, Decimal(0)) > EPS:
                    reason = "substitute_has_reserve_target"
                elif pool.get(old, Decimal(0)) <= EPS:
                    reason = "no_current_substitute_stock"
                attempt["consumed_pair"] = old
                if reason is not None:
                    attempt["reason"] = reason; attempts.append(attempt); continue
                before = pool[old]
                take = min(left, before)
                if unit(old) == "UN":
                    take = take.to_integral_value(rounding=ROUND_FLOOR)
                if take <= EPS:
                    attempt["reason"] = "no_whole_substitute_unit"
                    attempts.append(attempt); continue
                pool[old] -= take; left -= take
                suffix = json.dumps([output, component, old, index], separators=(",", ":"), ensure_ascii=True)
                rows.append(dict(required_pair=component, consumed_pair=old, qty=float(take),
                    requirement_id=principal_id + "|substitute:" + suffix))
                attempt.update(reason="allocated_current_stock", allocated_qty=float(take),
                    virtual_stock_before_qty=float(before), virtual_stock_after_qty=float(pool[old]))
                attempts.append(attempt)
            if left > 0 or needed == 0:
                rows.append(dict(required_pair=component, consumed_pair=component, qty=float(left),
                    requirement_id=principal_id))
            components.append(dict(required_pair=component, remaining_bom_qty=float(needed),
                substitute_qty=float(needed-left), principal_residual_qty=float(left), attempts=attempts))
        allocations[output] = tuple(rows)
        audits[output] = dict(campaign_id=identity, decision_day=decision_day, finish_day=finish,
            remaining_work_qty=float(remaining), excluded_executed_wip_qty=float(wip), components=components,
            physical_stock_mutated=False, substitute_future_receipts_used=False)
    return allocations, audits
