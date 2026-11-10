"""Read-only revisions of simulated weekly manufacturing launch programmes.

This counts comparable programme publications, never industrial OF revisions,
executed residuals, purchase rescheduling or a denominator of physical passes.
"""
from __future__ import annotations

from collections import Counter
import csv
import json
import math
from pathlib import Path

BASIS = 'simulated_weekly_launch_programme_v1'
AUTHORIZATION_BASIS = 'simulated_weekly_launch_programme_authorization_v1'
ACCEPTED_BASES = frozenset((BASIS, AUTHORIZATION_BASIS))
JOURNAL_FILENAME = 'production_programme_snapshots.csv'
SCHEMA_VERSION = 1
LABEL = 'Taux de révision du programme prévisionnel de fabrication simulé'
EPS = 1e-6


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f'{field} doit être entier')
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f'{field} doit être entier')
    return int(number)


def _vector(value, start, stop, field):
    data = json.loads(value) if isinstance(value, str) else value
    if not isinstance(data, dict):
        raise ValueError(f'{field} doit porter un échéancier daté')
    result = {}
    for key, qty in data.items():
        day = _integer(key, field)
        if day in result or isinstance(qty, bool):
            raise ValueError(f'{field} contient une date dupliquée ou une quantité invalide')
        quantity = float(qty)
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError(f'{field} contient une quantité invalide')
        result[day] = quantity
    if set(result) != set(range(start, stop)):
        raise ValueError(f'{field} ne couvre pas exactement sa fenêtre déclarée')
    return result


def production_programme_metrics(rows, *, expected_pairs=None, enabled=True, basis=None):
    """Changed active programme comparisons / identified active comparisons.

    First nonzero publication creates a programme. Later cancellations count;
    two zero states, changed coverage and moving horizon edges do not. A normal
    execution keeps the total target through committed launch credits. The
    commitment milestone (first work or campaign authorization) stays explicit;
    those bases cannot be mixed in one calculation.
    """
    rows = list(rows)
    observed_bases = {row.get('basis') for row in rows}
    if len(observed_bases) > 1:
        raise ValueError('Ne pas m\u00e9langer les bases du programme de fabrication')
    actual_basis = basis if basis is not None else next(iter(observed_bases), BASIS)
    if actual_basis not in ACCEPTED_BASES or (observed_bases and observed_bases != {actual_basis}):
        raise ValueError('La base du journal doit correspondre au contrat d\u00e9clar\u00e9')
    diagnostics = Counter()
    publications = {}
    scenarios, observed_pairs = set(), set()
    for source in rows if enabled else ():
        if _integer(source.get('schema_version'), 'schema_version') != SCHEMA_VERSION or source.get('basis') != actual_basis:
            raise ValueError('Contrat du journal de fabrication inconnu')
        identity = str(source.get('programme_id') or '')
        node, item, uom = (str(source.get(key) or '') for key in ('node_id', 'output_item_id', 'uom'))
        scenario = str(source.get('scenario_id') or '')
        if not all((identity, node, item, uom, scenario)):
            raise ValueError('Identité de programme, site, article, unité et scénario requis')
        decision, known, version, week, start, stop = (
            _integer(source.get(key), key) for key in ('decision_day', 'known_day', 'version',
                'week_start_day', 'coverage_start_day', 'coverage_end_day_exclusive'))
        if not 0 <= known <= decision or version < 1 or not 0 <= start or not week <= start < stop <= week + 7:
            raise ValueError('Connaissance, version ou couverture du programme invalide')
        target = _vector(source.get('launch_quantities_json'), start, stop, 'launch_quantities_json')
        committed = _vector(source.get('committed_quantities_json'), start, stop, 'committed_quantities_json')
        proposed = _vector(source.get('proposed_quantities_json'), start, stop, 'proposed_quantities_json')
        if any(abs(target[day] - committed[day] - proposed[day]) > EPS for day in target):
            raise ValueError('La cible doit conserver engagé + encore proposé')
        if any(qty > EPS and day > decision for day, qty in committed.items()):
            raise ValueError('Un engagement ne peut être connu avant son lancement')
        # Preserve raw absolute recommendation dates, including overdue ones.
        # Advancing a stale target to tomorrow would invent a new plan revision.
        snapshot = dict(identity=identity, pair=(node, item), uom=uom, scenario=scenario,
            decision=decision, known=known, version=version, week=week, start=start, stop=stop,
            target=target, committed=committed, proposed=proposed)
        key = identity, decision
        if key in publications:
            if publications[key] != snapshot:
                raise ValueError('Deux publications contradictoires pour un même programme et une décision')
            diagnostics['exact_duplicate_publications'] += 1
            continue
        publications[key] = snapshot
        scenarios.add(scenario)
        observed_pairs.add((node, item))
    if len(scenarios) > 1:
        raise ValueError('Ne pas mélanger plusieurs runs/scénarios dans un taux')
    previous, established = {}, set()
    changed = compared = 0
    temporal_gap = False
    for row in sorted(publications.values(), key=lambda r: (r['identity'], r['decision'])):
        identity, active = row['identity'], any(qty > EPS for qty in row['target'].values())
        old = previous.get(identity)
        gap = False
        if old is None and row['version'] != 1:
            raise ValueError('La premi\u00e8re publication du programme doit identifier son origine en version 1')
        if old is not None:
            if (old['pair'], old['uom'], old['scenario'], old['week']) != (row['pair'], row['uom'], row['scenario'], row['week']):
                raise ValueError('Une identité de programme ne peut changer de site, article, unité ou semaine')
            if row['version'] <= old['version'] or row['known'] < old['known']:
                raise ValueError('Les versions et dates de connaissance doivent progresser')
            gap = row['decision'] != old['decision'] + 1 or row['version'] != old['version'] + 1
            if gap:
                diagnostics['missing_publication_comparisons_excluded'] += 1
                temporal_gap = True
        if active and identity not in established:
            established.add(identity)
            diagnostics['programme_creations_excluded'] += 1
        elif old is not None and identity in established:
            was_active = any(qty > EPS for qty in old['target'].values())
            if not (active or was_active):
                diagnostics['inactive_zero_comparisons_excluded'] += 1
            elif gap:
                pass
            elif (old['start'], old['stop']) != (row['start'], row['stop']):
                diagnostics['coverage_change_comparisons_excluded'] += 1
            else:
                compared += 1
                different = any(abs(row['target'][day] - old['target'][day]) > EPS for day in row['target'])
                changed += different
                diagnostics['changed_comparisons' if different else 'unchanged_comparisons'] += 1
        else:
            diagnostics['initial_zero_publications_excluded'] += 1
        previous[identity] = row
    expected = None if expected_pairs is None else {tuple(pair) for pair in expected_pairs}
    complete = bool(publications) and not temporal_gap and (expected is None or expected <= observed_pairs)
    known = bool(enabled and complete and compared)
    status = ('simulated_weekly_programme_versions' if known else
              'journal_disabled' if not enabled else 'programme_revisions_unmeasurable')
    return dict(production_replanning_count=changed if known else None,
        production_replanning_comparable_count=compared,
        production_replanning_rate=changed / compared if known else None,
        production_replanning_basis=actual_basis,
        production_replanning_label=LABEL,
        planning_semantics_status=status,
        line_nervousness=changed if known else None,
        production_replanning_coverage_complete=complete,
        production_replanning_diagnostics=dict(diagnostics, published_snapshots=len(publications),
            raw_changed_comparisons=changed, raw_comparable_count=compared,
            observed_pairs=[list(pair) for pair in sorted(observed_pairs)],
            missing_pairs=[] if expected is None else [list(pair) for pair in sorted(expected - observed_pairs)],
            expected_scope='observed_only' if expected is None else 'explicit_produced_pairs',
            metric_unit='programme_comparisons', execution_is_not_replanning=True,
            commitment_milestone=('campaign_creation_authorization' if actual_basis == AUTHORIZATION_BASIS
                                  else 'first_physical_execution_v1'),
            industrial_OF_replanning_rate_identified=False))


def programme_metrics_from_directory(output_dir):
    """Return None if no journal exists, preserving legacy unknown metrics."""
    root = Path(output_dir)
    path = root / 'data' / JOURNAL_FILENAME
    if not path.is_file():
        return None
    summary_path = root / 'summaries/first_simulation_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8-sig')) if summary_path.is_file() else {}
    contract = summary.get('production_programme_revisions') or {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return programme_metrics_with_contract(rows, contract)


def programme_metrics_with_contract(rows, contract):
    """Validate the export receipt in memory before interpreting a CSV journal."""
    rows = list(rows)
    if not contract or contract.get('basis') not in ACCEPTED_BASES or contract.get('schema_version') != SCHEMA_VERSION:
        result = production_programme_metrics([], enabled=False)
        result['production_replanning_diagnostics']['contract_status'] = 'missing_or_unknown_export_contract'
        return result
    declared = contract.get('published_snapshot_count')
    if declared is not None:
        count = _integer(declared, 'published_snapshot_count')
        unique = {(str(row.get('programme_id') or ''), _integer(row.get('decision_day'), 'decision_day')) for row in rows}
        if count < 0 or count != len(rows) or count != len(unique):
            raise ValueError('Le nombre de publications du CSV ne correspond pas au résumé source')
    expected = contract.get('expected_pairs')
    if expected is not None:
        expected = [(row['node_id'], row.get('output_item_id', row.get('item_id'))) if isinstance(row, dict) else tuple(row)
                    for row in expected]
    return production_programme_metrics(rows, expected_pairs=expected,
        enabled=contract.get('enabled') is True and contract.get('complete_scope') is True,
        basis=contract['basis'])


def replanning_rate_from_metrics(row):
    """Use explicit rates, or the explicit matching programme denominator only.

    Missing/empty explicit rates are authoritative unknowns. A complete_scope
    refusal must never be hidden by computing another rate from count fields.
    """
    def value(name):
        for key in ('kpi::' + name, name):
            if key in row:
                return True, row[key]
        return False, None
    _, coverage = value('production_replanning_coverage_complete')
    if coverage is False or coverage == 0 or (isinstance(coverage, str) and coverage.strip().lower() in {'false', '0'}):
        return None
    def number(raw):
        if raw in (None, '') or isinstance(raw, bool):
            return None
        try:
            result = float(raw)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None
    present, raw = value('production_replanning_rate')
    if present:
        rate = number(raw)
        return rate if rate is not None and 0 <= rate <= 1 else None
    has_count, raw_count = value('production_replanning_count')
    has_denominator, raw_denominator = value('production_replanning_comparable_count')
    numerator, denominator = number(raw_count), number(raw_denominator)
    if (not has_count or not has_denominator or numerator is None or denominator is None
            or not numerator.is_integer() or not denominator.is_integer()
            or denominator <= 0 or not 0 <= numerator <= denominator):
        return None
    return numerator / denominator
