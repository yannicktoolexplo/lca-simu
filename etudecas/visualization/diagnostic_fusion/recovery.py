"""Historical stock-movement windows; never infer measured customer service.

The accounting witnesses are alternative decompositions of the same net I,
not simulations, inferred shipments, or a fitted industrial explanation.
"""
from datetime import date, timedelta

WINDOWS = (1, 2, 4)


def units(value):
    return f'{value:,}'.replace(',', ' ')


def accounting_witness(episode):
    """Show non-identification under the explicit candidate equation I = R - C."""
    fields = ('I_signed_UN', 'demand_UN', 'H_UN', 'G_UN',
              'stock_open_UN', 'stock_close_UN', 'residual_UN')
    if any(episode.get(k) is None for k in fields):
        return {'status': 'unknown', 'reason': 'Donnée nécessaire absente.'}
    i, demand = episode['I_signed_UN'], episode['demand_UN']
    if episode['residual_UN'] != 0:
        return {'status': 'unclosed', 'reason': 'Bilan non fermé : pas de décomposition exacte.'}
    minimum_c = max(-i, 0)
    if demand <= minimum_c:
        return {'status': 'not_discriminating',
                'reason': 'Ces deux constructions ne donnent pas deux flux distincts admissibles.'}
    cases = []
    for label, c in [('demand_served', demand), ('minimum_nonnegative_flows', minimum_c)]:
        r = i + c
        end = episode['stock_open_UN'] + episode['H_UN'] + episode['G_UN'] + r - c
        cases.append(dict(id=label, hypothetical_customer_UN=c,
                          hypothetical_net_component_receipts_UN=r,
                          reconstructed_I_UN=r-c, reconstructed_stock_close_UN=end))
    return dict(status='ambiguous', equation='I = R - C ; S1 = S0 + H + G + R - C',
                assumption='I agrège des apports R et des sorties clients C ; hypothèse candidate, non confirmée. H reste séparé.',
                cases=cases,
                summary=(f"Sous l’hypothèse I = apports − sorties clients, {units(demand)} ou "
                         f"{units(minimum_c)} UN sorties donnent le même stock final, avec des apports différents."))


def window(rows, start, weeks):
    first = date.fromisoformat(start)
    dates = [(first + timedelta(weeks=w)).isoformat() for w in range(weeks)]
    selected = [rows[d] for d in dates if d in rows]
    result = dict(weeks=weeks, start=start,
                  end_exclusive=(first + timedelta(weeks=weeks)).isoformat(),
                  observed_weeks=len(selected), status='incomplete',
                  missing_weeks=[d for d in dates if d not in rows],
                  episode_ids=[e['id'] for e in selected])
    fields = ('demand_UN', 'I_signed_UN', 'H_UN', 'G_UN', 'stock_open_UN', 'stock_close_UN')
    result['unknown_value_weeks'] = [e['week_start'] for e in selected
                                   if any(e.get(k) is None for k in fields)]
    result['discontinuous_stock_weeks'] = [b['week_start'] for a, b in zip(selected, selected[1:])
                                          if a.get('stock_close_UN') != b.get('stock_open_UN')]
    totals = ('demand_UN', 'abs_I_UN', 'positive_I_UN', 'negative_I_magnitude_UN',
              'stock_delta_UN', 'residual_UN', 'proxy_minus_demand_UN')
    result.update(dict.fromkeys(totals))
    if result['missing_weeks'] or result['unknown_value_weeks'] or result['discontinuous_stock_weeks']:
        return result
    result['status'] = 'complete'
    result['demand_UN'] = sum(e['demand_UN'] for e in selected)
    result['positive_I_UN'] = sum(max(e['I_signed_UN'], 0) for e in selected)
    result['negative_I_magnitude_UN'] = sum(max(-e['I_signed_UN'], 0) for e in selected)
    result['abs_I_UN'] = result['positive_I_UN'] + result['negative_I_magnitude_UN']
    result['stock_delta_UN'] = selected[-1]['stock_close_UN'] - selected[0]['stock_open_UN']
    result['residual_UN'] = result['stock_delta_UN'] - sum(e['H_UN'] + e['G_UN'] + e['I_signed_UN'] for e in selected)
    result['proxy_minus_demand_UN'] = result['abs_I_UN'] - result['demand_UN']
    return result


def add_recovery(data):
    """Identical fixed windows for all episodes, including incomplete year ends."""
    indexed = {}
    for e in data['episodes']:
        rows = indexed.setdefault(e['product'], {})
        if e['week_start'] in rows:
            raise ValueError('Duplicate product/week in recovery inputs')
        rows[e['week_start']] = e
    for e in data['episodes']:
        windows = [window(indexed[e['product']], e['week_start'], n) for n in WINDOWS]
        complete = [w for w in windows if w['status'] == 'complete']
        candidates = [w for w in complete if w['weeks'] > 1 and w['proxy_minus_demand_UN'] >= 0]
        if e['demand_UN'] is None or e['abs_I_proxy_UN'] is None:
            summary = 'Données insuffisantes pour comparer la reprise.'
        elif e['abs_I_proxy_UN'] >= e['demand_UN']:
            summary = 'Cette semaine n’est pas un creux sous la demande ; les mouvements restent distincts des livraisons.'
        elif candidates:
            w = candidates[0]
            summary = (f"Sur {w['weeks']} semaines, abs(I) dépasse la demande de {units(w['proxy_minus_demand_UN'])} UN ; "
                       f"il inclut {units(w['positive_I_UN'])} UN de crédits de stock. Aucun rattrapage client démontré.")
        elif complete and complete[-1]['weeks'] > 1:
            w = complete[-1]
            summary = (f"Sur {w['weeks']} semaines, abs(I) reste inférieur à la demande de {units(-w['proxy_minus_demand_UN'])} UN. "
                       "Cet écart ne mesure pas un retard client.")
        else:
            summary = 'Recul insuffisant : aucune fenêtre complète de reprise à 2 ou 4 semaines.'
        e['recovery'] = dict(summary=summary, windows=windows,
                             witness=accounting_witness(e))
    data['conventions']['recovery'] = (
        'Fenêtres fixes de 1/2/4 semaines depuis le lundi sélectionné, fin exclue. '
        'Somme des abs(I), crédits positifs et débits négatifs séparés ; aucun ne certifie les flux clients bruts. '
        'Témoins comptables hypothétiques sous I = R − C, sans observation future injectée dans le moteur. '
        'Valeur absente, photo discontinue ou fin de série : fenêtre incomplète, aucun zéro imputé.')
