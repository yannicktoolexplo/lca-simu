"""Diagnostics journaliers : flux exécutés, états restants et versions datées.

Sans identité de programme, un maximum est une enveloppe déclarée, jamais une
quantité de commandes distinctes. Une baisse du reste n'est pas une révision.
Ce module pur ne commande aucun mouvement ni aucune décision du simulateur.
"""
from collections import defaultdict
import math

EPS = 1e-9


def _number(value, default=0.0):
    if value in (None, ''):
        return default
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Un signal de production doit être fini et positif ou nul')
    return result


def _day(value):
    result = float(value)
    if not math.isfinite(result) or not result.is_integer():
        raise ValueError('Le jour de production doit être un entier')
    return int(result)


def aggregate_production_days(rows, *, horizon_days=None):
    """Regrouper les passes sans compter plusieurs fois le même reste.

    ``campaign_id`` ou ``programme_id`` distingue les programmes indépendants.
    Un flux de nouveaux besoins exige ``desired_signal_kind=new_requirement``.
    Une révision cible exige les cinq champs ``proposal_*`` documentés dans
    les tests ; sa date de connaissance ne peut dépasser le jour observé.
    """
    grouped = defaultdict(list)
    for row in rows:
        node, item = str(row.get('node_id') or ''), str(row.get('output_item_id') or '')
        if not node or not item:
            continue
        day = _day(row.get('day'))
        if horizon_days is not None and not 0 <= day < horizon_days:
            continue
        grouped[node, item, day].append(row)
    previous = {}
    known_requirement_events = {}
    output = []
    for (node, item, day), passes in sorted(grouped.items()):
        programmes = defaultdict(list)
        for row in passes:
            identity = str(row.get('campaign_id') or row.get('programme_id') or '')
            programmes[identity].append(row)
        planned = (max(_number(r.get('planned_qty_after_lot_rule')) for r in passes)
                   if '' in programmes else
                   sum(max(_number(r.get('planned_qty_after_lot_rule')) for r in rs)
                       for rs in programmes.values()))
        desired = 0.0
        new_requirement = 0.0
        all_new = True
        for rs in programmes.values():
            snapshots = []
            identified_flows = {}
            for index, row in enumerate(rs):
                value = _number(row.get('desired_qty'))
                if row.get('desired_signal_kind') == 'new_requirement':
                    identity = str(row.get('desired_signal_id') or f'pass:{index}')
                    identified_flows[identity] = max(identified_flows.get(identity, 0.0), value)
                else:
                    snapshots.append(value)
                    all_new = False
            flow = 0.0
            for identity, value in identified_flows.items():
                if identity.startswith('pass:'):
                    flow += value
                    continue
                event = (node, item, identity)
                if event in known_requirement_events:
                    if known_requirement_events[event] != value:
                        raise ValueError('Un même événement de nouveau besoin change de quantité')
                else:
                    flow += value
                    known_requirement_events[event] = value
            desired += max(snapshots, default=0.0) + flow
            new_requirement += flow
        actual = sum(_number(r.get('actual_qty')) for r in passes)
        fields = ('proposal_id', 'proposal_version', 'proposal_due_day', 'proposal_known_day', 'proposal_qty')
        snapshots = {}
        complete = all(all(r.get(f) not in (None, '') for f in fields) for r in passes)
        if complete:
            for row in passes:
                known = _day(row['proposal_known_day'])
                if known > day:
                    raise ValueError('Une version de programme ne peut être connue après le jour analysé')
                due = _day(row['proposal_due_day'])
                key = (node, item, str(row['proposal_id']), due)
                version = str(row['proposal_version'])
                value = _number(row['proposal_qty'])
                candidate = (known, version, value)
                if key in snapshots and snapshots[key][:2] == candidate[:2] and snapshots[key][2] != value:
                    raise ValueError('Une même version de proposition porte deux quantités cibles')
                if key not in snapshots or known > snapshots[key][0]:
                    snapshots[key] = candidate
                elif known == snapshots[key][0] and version != snapshots[key][1]:
                    raise ValueError('Deux versions simultanées sans ordre de connaissance sont ambiguës')
        changes = []
        for key, snapshot in snapshots.items():
            old = previous.get(key)
            if old is not None:
                if snapshot[0] < old[0]:
                    raise ValueError('Les versions de proposition régressent dans le temps connu')
                if snapshot[:2] == old[:2] and snapshot[2] != old[2]:
                    raise ValueError('Une même version de proposition change de quantité cible')
                changes.append((snapshot[2] != old[2],
                    100.0 * abs(snapshot[2] - old[2]) / max(old[2], snapshot[2], 1.0)))
            previous[key] = snapshot
        identifiable = complete and bool(changes)
        output.append(dict(node_id=node, output_item_id=item, day=day, actual_qty=actual,
            desired_qty=desired, planned_qty_after_lot_rule=planned,
            shortfall_vs_desired_qty=max(0.0, desired-actual),
            shortfall_vs_lot_plan_qty=max(0.0, planned-actual),
            requested_lot_starts=sum(_number(r.get('requested_lot_starts')) for r in passes),
            actual_lot_starts=sum(_number(r.get('actual_lot_starts')) for r in passes),
            new_requirement_qty=new_requirement if all_new else None,
            signal_status='programmes_identifies' if '' not in programmes else 'origine_inconnue',
            signal_semantics='flux_executé_et_enveloppe_des_etats_restants',
            plan_revision_count=sum(change for change, _ in changes) if identifiable else None,
            plan_revision_magnitude_pct=sum(v for _, v in changes)/len(changes) if identifiable else None,
            plan_revision_status='versions_comparees' if identifiable else 'revision_inconnue',
            plan_versions_identified=complete,
            binding_causes=sorted({str(r.get('binding_cause')) for r in passes
                                  if r.get('binding_cause') not in (None, '', 'none')}),
            pass_count=len(passes)))
    return output


def daily_plan_metrics(rows, *, horizon_days=None):
    """Adhérence à l'enveloppe journalière et vraies révisions identifiables.

    Un total d'états par jour est un dénominateur d'exposition, pas le volume
    d'ordres distincts. Les révisions manquantes restent ``None`` / CSV vide.
    """
    daily = aggregate_production_days(rows, horizon_days=horizon_days)
    # Never sum quantities across articles (e.g. G + UN). Each homogeneous
    # site/article pair supplies one dimensionless ratio, equally weighted.
    planned_by_pair = defaultdict(float)
    covered_by_pair = defaultdict(float)
    for row in daily:
        pair = row['node_id'], row['output_item_id']
        planned_by_pair[pair] += row['planned_qty_after_lot_rule']
        covered_by_pair[pair] += min(row['actual_qty'], row['planned_qty_after_lot_rule'])
    adherence = [covered_by_pair[pair]/qty for pair, qty in planned_by_pair.items() if qty > EPS]
    comparable = [r for r in daily if r['plan_revision_count'] is not None]
    # First snapshots have no previous version; unidentified programmes cannot
    # turn an unknown revision into a zero-change recommendation.
    identified = bool(comparable) and all(r['plan_versions_identified'] for r in daily)
    changes = sum(r['plan_revision_count'] for r in comparable) if identified else None
    count = sum(r['planned_qty_after_lot_rule'] > EPS or r['actual_qty'] > EPS for r in daily)
    return dict(line_adherence=sum(adherence)/len(adherence) if adherence else None,
        line_nervousness=changes, production_replanning_count=changes,
        production_replanning_rate=changes/len(comparable) if identified else None,
        production_planning_line_count=count,
        planning_semantics_status='versions_comparees' if identified else 'revision_inconnue',
        line_adherence_basis='moyenne_non_ponderee_ratios_site_article_execution_sur_enveloppe_pas_adherence_aux_OF',
        plan_signal_origin_status='programmes_identifies' if daily and all(r['signal_status']=='programmes_identifies' for r in daily) else 'origine_inconnue')
