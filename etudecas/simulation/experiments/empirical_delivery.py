"""Infer conservative receipt-date deviations, never identified supplier lead times.

The weekly H bucket is compared with an interval between physical stock photos.
J is deliberately unused: its future buckets are already-present physical stock.
Only information known at the closing photo can enter a subsequent decision.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path

ORIGIN = date(2025, 1, 1)
ROOT = Path(__file__).resolve().parents[2]


def day(value):
    value = value.date() if isinstance(value, datetime) else value
    return ((value if isinstance(value, date) else date.fromisoformat(str(value)[:10])) - ORIGIN).days


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reconcile_pair(photos, plans, *, item, site, unit, lookback_days=14,
                   search_days=21, quantity_tolerance=0.25):
    """Pure calculation; each plan row is [row, day, H, I, J, K].

    Select a vintage >=14 days before the START of the observed interval.
    Require one isolated H in the search neighbourhood, a rise >=50% of H,
    no rise >102% of H, and compatibility of H-rise with forecast I to 25% H.
    These thresholds define selection, not industrial measurement precision.
    """
    if lookback_days < 14 or search_days < 0 or not 0 <= quantity_tolerance <= 1:
        raise ValueError('Invalid conservative matching thresholds')
    if len({p['day'] for p in photos}) != len(photos):
        raise ValueError('Duplicate stock photo')
    ordered = sorted(photos, key=lambda p: p['day'])
    output, rejected = [], []
    for previous, current in zip(ordered, ordered[1:]):
        start, end = previous['day'], current['day']
        rise = current['qty'] - previous['qty']
        base = dict(item=item, site=site, observed_start_day=start,
                    observed_end_day=end, stock_net_increase=rise)
        def reject(reason, **detail):
            rejected.append(dict(base, reason=reason, **detail))
        if not 0 < end - start <= 7:
            reject('photo_gap_exceeds_week'); continue
        if rise <= 1e-8:
            reject('no_positive_net_stock_change'); continue
        available = [v for v in plans if v <= start - lookback_days]
        if not available:
            reject('no_plan_known_at_required_lookback'); continue
        vintage = max(available)
        if start - lookback_days - vintage > 7:
            reject('stale_or_missing_plan_at_required_lookback'); continue
        rows = plans[vintage]
        if len({r[1] for r in rows}) != len(rows):
            raise ValueError('Duplicate MRP bucket')
        # A H bucket is Sunday..Saturday, consistently with existing model.
        nearby = [r for r in rows if r[2] > 0 and
                  r[1] <= end + search_days and r[1] + 6 >= start + 1 - search_days]
        if len(nearby) != 1:
            reject('no_isolated_projected_receipt', candidate_count=len(nearby)); continue
        receipt = nearby[0]
        source_row, planned, quantity = receipt[:3]
        if planned <= vintage:
            reject('receipt_not_future_in_selected_plan'); continue
        if not 0.5 * quantity <= rise <= 1.02 * quantity:
            reject('net_rise_incompatible_with_receipt_quantity', projected_H=quantity); continue
        consumption, covered_days, i_cells = 0., set(), []
        for row in rows:
            overlap = set(range(start + 1, end + 1)).intersection(range(row[1], row[1] + 7))
            if overlap:
                if row[3] < 0:
                    raise ValueError('Negative forecast I cannot estimate consumption')
                consumption += row[3] * len(overlap) / 7
                covered_days.update(overlap)
                i_cells.append(f'Feuille1!I{row[0]}')
        if len(covered_days) != end - start:
            reject('forecast_I_window_incomplete'); continue
        residual = quantity - rise - consumption
        if abs(residual) > quantity_tolerance * quantity + 1e-8:
            reject('net_rise_plus_forecast_I_incompatible', projected_H=quantity,
                   forecast_I=consumption, residual=residual); continue
        lower, upper = start + 1 - (planned + 6), end - planned
        delta = math.floor((lower + upper) / 2 + .5)
        output.append(dict(base, id=f'{item}/{site}/photo:{end}/H:{planned}',
            known_day=end, delta_days=delta, lower_days=lower, upper_days=upper,
            planned_day=planned, planned_end_day=planned + 6, plan_known_day=vintage,
            projected_H=quantity, projected_I_in_photo_interval=consumption,
            implied_net_consumption_if_H_received=quantity-rise,
            quantity_residual=residual, unit=unit, confidence='conditional_isolated_match',
            sources={'stock_start':f'Stocks!E{previous["row"]}',
                     'stock_end':f'Stocks!E{current["row"]}',
                     'MRP_H':f'Feuille1!H{source_row}', 'MRP_I':i_cells}))
    # Chronological de-duplication: a later photo cannot change what was known
    # after an earlier photo. Keep the first match; never withdraw it in hindsight.
    seen, unique = set(), []
    for observation in output:
        if observation['planned_day'] in seen:
            rejected.append(dict(observation, reason='already_matched_projected_date'))
        else:
            unique.append(observation)
            seen.add(observation['planned_day'])
    return unique, rejected


def build_policy(root=ROOT, *, lookback_days=14, search_days=21, quantity_tolerance=.25):
    import openpyxl
    root = Path(root)
    source = root/'data/source'
    audit_path = root/'artifacts/testing/mrp_full_flow_audit_20260930/flows/results.json'
    inventory = source/'Flow_Data_Inventory_and_Replenishment_rules.xlsx'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    # Check actual workbook provenance; historical audit code may since have changed.
    hashes = {}
    for relative, expected in audit['input_hashes_before'].items():
        path = root.parent / Path(relative)
        if path.suffix.lower() == '.xlsx':
            actual = sha(path)
            if actual != expected:
                raise ValueError(f'Audited workbook changed: {relative}')
            hashes[str(path.relative_to(root.parent))] = actual
    hashes[str(audit_path.relative_to(root.parent))] = sha(audit_path)
    photos = defaultdict(list)
    book = openpyxl.load_workbook(inventory, read_only=True, data_only=True)
    try:
        for number, row in enumerate(book['Stocks'].iter_rows(min_row=2, values_only=True), 2):
            item, _, site, _, quantity, _, unit, stamp = row
            if item is None:
                continue
            unit = str(unit).upper()
            canonical, factor = ('KG', .001) if unit == 'G' else ('UN', 1.) if unit in ('UN', 'ZUN') else (unit, 1.)
            qty = float(quantity) * factor
            if not math.isfinite(qty) or qty < 0:
                raise ValueError(f'Invalid physical stock E{number}')
            photos[str(item).removesuffix('.0').zfill(6), str(site)].append(
                dict(day=day(stamp), qty=qty, row=number, unit=canonical))
    finally:
        book.close()
    observations, excluded, pair_summary = [], [], []
    for pair in audit['pairs']:
        item, site = pair['item'], pair['site']
        external = [o for o in pair['offers'] if o['transaction_kind'] == 'external_supplier_purchase']
        suppliers = {o['supplier'] for o in external}
        reason = None
        if not external:
            reason = 'no_external_supplier_offer'
        elif len(suppliers) != 1 or len(external) != len(pair['offers']):
            reason = 'supplier_or_internal_external_origin_ambiguous'
        elif not photos.get((item, site)):
            reason = 'no_physical_stock_photos'
        elif {p['unit'] for p in photos[item, site]} != {pair['unit']}:
            reason = 'source_units_incompatible'
        if reason:
            pair_summary.append(dict(item=item, site=site, included=False, reason=reason)); continue
        plans = {day(p['vintage']): [[r[0],day(r[1]),*r[4:8]] for r in p['rows']] for p in pair['plans']}
        accepted, rejected = reconcile_pair(photos[item, site], plans, item=item, site=site,
            unit=pair['unit'], lookback_days=lookback_days, search_days=search_days,
            quantity_tolerance=quantity_tolerance)
        for observation in accepted:
            observation['supplier'] = external[0]['supplier']
            observation['FIA_reference_days'] = external[0]['delivery_reference_days']
            observation['FIA_source'] = f'{external[0]["file"]}/{external[0]["sheet"]}!F{external[0]["row"]}'
            observation['receipt_processing_days'] = pair['receipt_days']
        observations.extend(accepted); excluded.extend(rejected)
        pair_summary.append(dict(item=item, site=site, included=True, accepted=len(accepted),
                                 exclusions=dict(Counter(r['reason'] for r in rejected))))
    observations.sort(key=lambda o:(o['known_day'],o['id']))
    return dict(schema_version=1, origin_date=ORIGIN.isoformat(), min_samples=5,
        law='uniform_empirical_event_midpoint_plus_FIA_reference',
        causal_eligibility='known_day <= purchase_decision_day',
        fallback='fixed_FIA_reference_if_fewer_than_min_samples',
        scope='common_pool_external_supplier_purchases_only',
        method=dict(lookback_days_before_photo_start=lookback_days,
            search_days_around_photo_window=search_days,
            net_rise_fraction_of_H=[.5,1.02], quantity_residual_tolerance_fraction_H=quantity_tolerance,
            H_week='Sunday label through following Saturday (model convention, not independently confirmed)',
            estimator='rounded midpoint of interval-censored observed-minus-planned receipt date',
            receipt_semantics='H physical arrival versus availability is not confirmed',
            event_weight='one vote per accepted stock-rise interval, not per individual order'),
        observations=observations, summary=dict(observation_count=len(observations),
            item_site_count=len({(o['item'],o['site']) for o in observations}),
            delta_day_counts=dict(sorted(Counter(o['delta_days'] for o in observations).items())),
            exclusion_counts=dict(Counter(r['reason'] for r in excluded)), pairs=pair_summary),
        limits=['This is a conditional date-deviation model, not measured purchase-to-receipt lead time.',
            'Positive-stock selection misses receipts hidden by consumption, partial and split receipts.',
            'Search window truncates eligible advances/delays; distribution tails are not measured.',
            'Forecast I is not executed consumption; stock adjustments or returns can mimic receipts.',
            'Sunday week-start orientation is a convention; week-end orientation shifts deviations by six days.',
            'H may describe availability rather than arrival; processing days can confound inferred deviations.',
            'Pooling across suppliers and applying date deviations to FIA lead times are explicit modelling assumptions.',
            'No per-supplier distribution and no causal future information in 2025 decisions.'],
        input_hashes=hashes, excluded_intervals=excluded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = ROOT/'artifacts/testing'
    if not output.is_relative_to(allowed.resolve()):
        raise ValueError('Evidence output must remain under etudecas/artifacts/testing')
    policy = build_policy()
    output.mkdir(parents=True, exist_ok=True)
    excluded = policy.pop('excluded_intervals')
    for name, data in [('empirical_policy.json',policy),('excluded_intervals.json',excluded)]:
        with (output/name).open('x', encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(policy['summary'],ensure_ascii=False))


if __name__ == '__main__':
    main()
