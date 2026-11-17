"""Conditional admission of one batch using only a current known snapshot.

The physical trajectory remains continuous on the declared work calendar.
Other firm capacity reservations may reject it; they never create fictitious
pauses in that trajectory. No stock, order, reservation or demand is mutated.
"""
from decimal import Decimal
import math

from etudecas.simulation.engine.production_component_issues import incremental_component_issue
from etudecas.simulation.engine.programme_opening_coverage import FIRM_COMPONENT_ORIGINS
from etudecas.simulation.lot_policy.models import normalize_uom

DATED_MATERIAL_LAUNCH_POLICY = "known_dated_continuity_v1"


def _qty(value, unit=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError("Dated launch needs finite nonnegative quantities")
    if unit is not None and normalize_uom(unit)=="UN" and value!=int(value):
        raise ValueError("Physical component units must remain integer")
    return Decimal(str(value))


def assess_dated_material_launch(*, decision_day, batch_qty, components, available_by_pair,
        item_uoms, firm_receipts, other_requirements, capacity_context, own_order_id=None,
        nonprojectable_substitutions=()):
    """Project one fixed physical batch; return an auditable admission decision.

    components: ((node,item), coefficient per finished-unit) pairs.
    Receipts/other requirements carry explicit known_day at or before decision.
    Firm origins follow the existing native component-commitment contract.
    """
    if type(decision_day) is not int or decision_day<0 or _qty(batch_qty)<=0:
        raise ValueError("Invalid dated launch decision")
    if batch_qty!=int(batch_qty):
        raise ValueError("This admission policy supports integer finished-unit batches")
    result=dict(policy=DATED_MATERIAL_LAUNCH_POLICY,snapshot_known_day=decision_day,
        applicable=True,allowed=False,reason="",batch_qty=batch_qty,projected_finish_day=None,
        work_allocations=[],capacity_reservations=[],component_projection=[],
        firm_receipts=[],other_requirements=[],excluded_own_order_id=own_order_id,
        conditional_on="declared_future_capacity_and_known_commitments;unknown_future_residuals_or_incidents_excluded")
    if capacity_context is None:
        result.update(applicable=False,allowed=None,reason='unknown_finite_capacity');return result
    context=capacity_context
    if context['known_day']>decision_day or context['first_work_day']!=decision_day:
        raise ValueError("Capacity must be known at the current launch decision")
    rate=float(context['capacity_qty']);current=context.get('current_capacity_qty')
    current=rate if current is None else float(current)
    if _qty(rate)<=0 or _qty(current)<0:raise ValueError("Invalid capacity")
    if context.get('active_remaining_qty',0)>0:
        result['reason']='existing_active_campaign';return result
    closed=set(context.get('closed_days',()))
    horizon=decision_day+366
    capacity={d:0.0 if d in closed else min(rate,current) if d==decision_day else rate
              for d in range(decision_day,horizon)}
    if capacity[decision_day]<=0:
        result['reason']='no_current_capacity';return result
    left=float(batch_qty);work={}
    for d,daily in capacity.items():
        amount=min(left,daily)
        if amount>0:work[d]=amount;left-=amount
        if left<=0:break
    if left>0:
        result.update(applicable=False,allowed=None,reason='capacity_horizon_exhausted');return result
    finish=max(work);result['projected_finish_day']=finish
    result['work_allocations']=[dict(day=d,qty=q) for d,q in work.items()]
    transitions=[row for row in nonprojectable_substitutions
        if row.get('start_day',decision_day)<=finish and row.get('end_day',finish)>=decision_day]
    if transitions:
        result.update(applicable=False,allowed=None,reason='dated_substitution_not_projectable',
            substitutions=transitions);return result
    components=tuple(components);pairs={pair for pair,_ in components}
    if len(pairs)!=len(components):
        raise ValueError("Dated batch requires a unique component BOM")
    if not components:
        result.update(applicable=False,allowed=None,reason='no_projectable_component_bom');return result
    balance={pair:_qty(available_by_pair.get(pair,0),item_uoms[pair[1]]) for pair in pairs}
    result['usable_stock_snapshot']=[dict(node_id=p[0],item_id=p[1],qty=float(balance[p]),uom=item_uoms[p[1]])
        for p in sorted(pairs)]
    result['bom']=[dict(node_id=p[0],item_id=p[1],ratio=ratio,uom=item_uoms[p[1]]) for p,ratio in components]
    receipts={};requirements={};seen=set()
    for kind,records,date_field,target in (('receipt',firm_receipts,'available_day',receipts),
            ('requirement',other_requirements,'due_day',requirements)):
        for row in records:
            pair=(row['node_id'],row['item_id']);identity=row['identity'];known=row['known_day'];when=row[date_field]
            if pair not in pairs:continue
            if (not isinstance(identity,str) or not identity or (kind,pair,identity) in seen
                    or type(known) is not int or known>decision_day or type(when) is not int):
                raise ValueError("Dated material identity/date not known at decision")
            seen.add((kind,pair,identity));quantity=_qty(row['qty'],item_uoms[pair[1]])
            if kind=='receipt' and (when<=decision_day or row['origin'] not in FIRM_COMPONENT_ORIGINS):
                raise ValueError("Only future usable firm receipts are additional to current stock")
            target.setdefault(max(decision_day,when),[]).append((pair,quantity))
            result['firm_receipts' if kind=='receipt' else 'other_requirements'].append(dict(row))
    reservations={d:0.0 for d in capacity};identities=set()
    committed=tuple(context.get('opening_work',()))+tuple(context.get('frozen_work',()))
    for identity,earliest,quantity in sorted(committed,key=lambda r:(r[1],r[0])):
        if not identity or identity in identities or type(earliest) is not int:
            raise ValueError("Duplicate or invalid firm capacity identity")
        identities.add(identity);_qty(quantity)
        if identity==own_order_id:continue
        remaining=float(quantity);allocations=[]
        for d in range(max(decision_day,earliest),horizon):
            amount=min(remaining,max(0,capacity[d]-reservations[d]))
            if amount>0:
                reservations[d]+=amount;remaining-=amount;allocations.append(dict(day=d,qty=amount))
            if remaining<=0:break
        result['capacity_reservations'].append(dict(order_id=identity,earliest_day=earliest,
            qty=quantity,allocations=allocations,unplaced_qty=remaining))
    conflicts=[dict(day=d,batch_work=q,other_reserved=reservations[d],capacity=capacity[d])
        for d,q in work.items() if q+reservations[d]>capacity[d]]
    if conflicts:
        result.update(reason='known_capacity_commitment_conflict',capacity_conflicts=conflicts);return result
    issued={pair:0.0 for pair in pairs};executed=0.0
    for d in range(decision_day,finish+1):
        for pair,quantity in receipts.get(d,()):balance[pair]+=quantity
        for pair,quantity in requirements.get(d,()):balance[pair]-=quantity
        if d not in work:continue
        debits={}
        for pair,ratio in components:
            if _qty(ratio)<=0:raise ValueError("BOM coefficients must be positive")
            unit=item_uoms[pair[1]]
            debit=incremental_component_issue(executed,work[d],ratio,unit,issued[pair])
            debits[pair]=debit
            available=balance[pair]
            result['component_projection'].append(dict(day=d,node_id=pair[0],item_id=pair[1],uom=unit,
                usable_after_other_requirements=float(available),batch_issue_qty=debit,
                cumulative_batch_work=executed+work[d],shortfall_qty=float(max(Decimal(0),Decimal(str(debit))-available))))
            if Decimal(str(debit))>available:
                result.update(reason='dated_material_shortfall',first_shortage=dict(day=d,node_id=pair[0],item_id=pair[1],
                    required_qty=debit,available_qty=float(available)));return result
        for pair,debit in debits.items():balance[pair]-=Decimal(str(debit));issued[pair]+=debit
        executed+=work[d]
    result.update(allowed=True,reason='known_dated_material_continuity',projected_completed_qty=executed)
    return result
