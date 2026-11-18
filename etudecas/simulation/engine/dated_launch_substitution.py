"""Conservative applicability proof for configured reference transitions.

This is not a projection of substitute consumption. It proves that primary
components alone fund the candidate's complete declared trajectory under the
same dated commitments as the admission check. Unknown future uses/incidents
remain outside that conditional proof.
"""


def assess_primary_only_transitions(*, assess, arguments, transitions, base_result,
                                    result_policy, projection_policy):
    """Delegate arithmetic/priority to the existing primary-component check.

    The restricted probe must finish before a different component's shortage
    can stop the full check. Inputs are already materialized by the caller;
    generators must never be consumed independently by the two evaluations.
    """
    components = arguments['components']
    component_pairs = {pair for pair, _ in components}
    day = arguments['decision_day']
    unsupported = []
    for row in transitions:
        pair = row.get('node_id'), row.get('item_id')
        known = row.get('known_day')
        if (pair not in component_pairs
                or row.get('consume_policy') != 'use_old_until_new_stock_available'
                or not isinstance(row.get('old_item_id'), str) or not row['old_item_id']
                or row['old_item_id'] == row.get('item_id')
                or type(known) is not int or known < 0 or known > day
                or type(row.get('start_day')) is not int
                or type(row.get('end_day')) is not int
                or row['start_day'] < 0 or row['end_day'] < row['start_day']):
            unsupported.append(dict(row))
    proof = dict(
        method='primary_only_v2_complete_candidate_projection',
        conditional_on='declared_work_calendar_and_all_currently_known_obligations;unknown_future_uses_and_incidents_excluded',
        tested_through_day=base_result['projected_finish_day'],
        transitions=[dict(row) for row in transitions],
        status='not_proved',
    )
    if unsupported:
        proof.update(reason='unsupported_or_incomplete_transition_metadata', unsupported=unsupported)
        return dict(base_result, applicable=False, allowed=None,
            reason='dated_substitution_not_projectable', substitutions=list(transitions),
            substitution_projection=proof)

    primary_pairs = {(row['node_id'], row['item_id']) for row in transitions}
    shared = dict(arguments, policy=projection_policy, nonprojectable_substitutions=())
    # Keep every requirement during priority ordering. The arithmetic check
    # filters to the selected component pairs only after that ordering.
    probe = assess(**dict(shared, components=tuple(
        (pair, ratio) for pair, ratio in components if pair in primary_pairs)))
    proof.update(
        primary_components=[dict(node_id=node, item_id=item) for node, item in sorted(primary_pairs)],
        primary_result=probe['reason'],
        checked_work_days=len({row['day'] for row in probe.get('component_projection', ())}),
        component_projection=probe.get('component_projection', []),
    )
    if probe.get('first_shortage') is not None:
        proof['first_shortage'] = probe['first_shortage']
    if probe['allowed'] is not True:
        result = dict(probe, policy=result_policy, substitutions=list(transitions),
                      substitution_projection=proof)
        if probe['applicable'] and probe['reason'] != 'dated_material_shortfall':
            # A capacity/priority refusal is independent of the materials used.
            # It is not evidence that primary stock covers the candidate.
            proof['status'] = 'not_evaluated_capacity_or_priority_refusal'
            return result
        proof['reason'] = 'primary_coverage_not_proved'
        result.update(applicable=False, allowed=None, reason='dated_substitution_not_projectable')
        return result

    proof['status'] = 'primary_coverage_proved_for_complete_candidate'
    proof['projected_completed_qty'] = probe['projected_completed_qty']
    result = assess(**shared)
    result.update(policy=result_policy, substitutions=list(transitions), substitution_projection=proof)
    return result
