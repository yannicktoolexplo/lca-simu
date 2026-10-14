"""Memory-only local/common manufactured-output MRP oracles; no file fixtures."""
from copy import deepcopy
from decimal import Decimal
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, IndustrialComponentPlanningCalendar, IndustrialPlanningWindow,
    InternalTransferCommitments, LotSizing, Requirement,
    reconcile_manufactured_output_requirements,
)
from etudecas.simulation.engine.run_first_simulation import (
    manufactured_output_mrp_export_rows, plan_component_network,
    reconcile_production_execution_snapshot, record_started_transfer_campaign,
    resolve_manufactured_output_mrp_policy,
)

SOURCE, DEST, RAW = ("maker", "bulk"), ("user", "bulk"), ("maker", "raw")
L, G = "local_source_v1", "common_cumulative_v1"
G2 = "common_horizon_cumulative_v2"


def _window(start, qty):
    return IndustrialPlanningWindow(start, start, start+7, qty, 0, "source.xlsx", f"I{start}")


def _reconcile(needs, windows, mode):
    return reconcile_manufactured_output_requirements(needs, windows,
        pair=SOURCE, decision_day=0, mode=mode)


def _sum(rows):
    return sum((Decimal(str(r.qty)) for r in rows), Decimal(0))


def _network(mode=None, *, commitments=False, source_forecast=600):
    args = dict(decision_day=0, requirements_by_pair={DEST: [Requirement("use", 20, 1200)]},
        available_by_pair={SOURCE: 0, RAW: 10000}, firm_receipts_by_pair={},
        transport_sources_by_pair={DEST: [(SOURCE, 1)]}, bom_by_pair={SOURCE: [(RAW, 2)]},
        lead_days_by_pair={DEST: 5, SOURCE: 3, RAW: 1},
        lot_sizing_by_pair={SOURCE: LotSizing(multiple=600, maximum=600, integer=True),
                           DEST: LotSizing(multiple=600, integer=True), RAW: LotSizing()},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={})
    if mode is not None:
        args.update(manufactured_output_mrp_by_pair={SOURCE: mode},
            manufactured_output_windows_by_pair={SOURCE: (_window(4, source_forecast), _window(11, 0))})
    if commitments:
        args.update(transfer_commitment_pairs={DEST},
            availability_by_release_by_pair={DEST: tuple((d, d+5) for d in range(50))})
    return args


def test_local_and_common_are_distinct_and_shifted_600_is_never_added_twice():
    windows = (_window(4, 600), _window(11, 0))
    shifted = [Requirement("derived:transfer", 12, 600)]
    before = deepcopy((shifted, windows))
    for mode in (L, G):
        result, audit = _reconcile(shifted, windows, mode)
        assert _sum(result) == 600  # I600 early and D600 late cover one quantity.
        assert all(r.due_day < 12 for r in result)
        assert set(audit["requirement_aliases"].values()) == {"derived:transfer"}
        assert all(r["original_target_day"] == 12 for r in audit["fragments"])
        assert sum(Decimal(str(r["qty"])) for r in audit["fragments"]) == 600
    assert (shifted, windows) == before
    larger = [Requirement("derived:transfer", 12, 1200)]
    local, _ = _reconcile(larger, windows, L)
    common, audit = _reconcile(larger, windows, G)
    assert _sum(local) == 600 and _sum(common) == 1200
    assert _sum([r for r in common if r.due_day < 12]) == 600
    assert _sum([r for r in common if r.due_day == 12]) == 600
    assert audit["cumulative"][-1]["planning_cumulative_qty"] == 1200


def test_common_preserves_earlier_downstream_need_and_local_excess_has_no_destination():
    needs = [Requirement("derived:earlier", 5, 600)]
    result, audit = _reconcile(needs, (_window(4, 0), _window(11, 1200)), G)
    assert _sum(result) == 1200
    assert _sum([r for r in result if r.due_day == 5]) == 600
    assert sum(Decimal(str(r["qty"])) for r in audit["fragments"]
               if r["original_requirement_id"] == "derived:earlier") == 600
    excess = [r for r in audit["fragments"] if not r["original_requirement_id"]]
    assert sum(Decimal(str(r["qty"])) for r in excess) == 600
    assert all(r["requirement_id"] not in audit["requirement_aliases"] for r in excess)


def test_covered_firm_FIFO_keeps_dates_ids_and_uncovered_firm_does_not_consume_I():
    firm = Requirement("internal_commitment:1", 15, 600)
    outside = Requirement("initial_snapshot_hypothesis:2", 25, 300)
    downstream = Requirement("derived:revocable", 16, 600)
    fallback = Requirement("derived:uncovered", 24, 900)
    windows = (_window(4, 600), _window(11, 0))
    for mode, expected in [(L, 1800), (G, 2400)]:
        result, audit = _reconcile([firm, outside, downstream, fallback], windows, mode)
        assert firm in result and outside in result and fallback in result
        assert _sum(result) == expected
        assert audit["summary"]["matched_committed_qty"] == pytest.approx(600)
        assert audit["summary"]["residual_source_qty"] == 0
        assert {r["requirement_id"] for r in audit["committed_matches"]} == {firm.requirement_id}
        assert all(r["original_target_day"] == 15 for r in audit["committed_matches"])
        assert audit["summary"]["fallback_qty"] == 1200


def test_explicit_zero_differs_from_unprovided_and_off_network_is_unchanged():
    needs = [Requirement("derived:covered", 5, 600), Requirement("derived:missing", 15, 600)]
    local, audit = _reconcile(needs, (_window(4, 0),), L)
    assert local == [needs[1]] and audit["summary"]["covered_days"] == 7
    common, _ = _reconcile(needs, (_window(4, 0),), G)
    assert _sum(common) == 1200
    untouched, audit = _reconcile(needs, (), L)
    assert untouched == needs and audit["summary"]["fallback_qty"] == 1200
    args = _network()
    before = deepcopy(args)
    nominal = plan_component_network(**args)
    assert nominal == plan_component_network(**args,
        manufactured_output_mrp_by_pair=None, manufactured_output_windows_by_pair=None)
    assert args == before
    assert all("manufactured_output_mrp" not in a for a in nominal[2].values())


def test_manufacturing_and_BOM_are_netted_once_and_own_active_OF_is_supply():
    for mode, expected in [(L, 600), (G, 1200)]:
        args = _network(mode)
        plans, requirements, _ = plan_component_network(**args)
        assert plans[SOURCE].proposed_qty == expected
        assert _sum(requirements[RAW]) == 2*expected
        assert all(p.qty == 600 and p.qty == int(p.qty) for p in plans[SOURCE].proposals)
    args = _network(L, source_forecast=1200)
    args["active_campaigns_by_pair"] = {SOURCE: ("existing-OF", 400, 200, 3)}
    plans, requirements, audit = plan_component_network(**args)
    assert plans[SOURCE].proposed_qty == 600  # Gross I1200 - existing output600.
    assert _sum(requirements[SOURCE]) == 1200  # OF is not an extra output demand.
    assert _sum(requirements[RAW]) == 400*2 + 600*2
    assert [(r.receipt_id, r.qty) for r in audit[SOURCE]["firm_receipts"]] == [("campaign:existing-OF", 600)]
    args["active_campaigns_by_pair"] = {}
    args["firm_receipts_by_pair"] = {SOURCE: [FirmReceipt("opening-OF", 3, 600, "held")]}
    plans, requirements, _ = plan_component_network(**args)
    assert plans[SOURCE].proposed_qty == 600 and _sum(requirements[RAW]) == 1200


def test_aliases_peg_one_whole_transfer_without_second_order_or_local_destination():
    for mode, campaign_qty, expected_created in [(L, 600, ()), (G, 1200, ("internal_commitment:1",)),
                                                (G2, 1200, ("internal_commitment:1",))]:
        args = _network(mode, commitments=True)
        snapshots, plans, _, audit = reconcile_production_execution_snapshot(args,
            available_by_pair=args["available_by_pair"], firm_receipts_by_pair={}, produced_pairs={SOURCE})
        before = deepcopy((args, snapshots, plans))
        book = InternalTransferCommitments()
        created = record_started_transfer_campaign(book, day=12, source_pair=SOURCE,
            campaign_id="C", campaign_qty=campaign_qty, executed_qty=600,
            new_plan=plans[SOURCE], snapshot=snapshots[SOURCE], uom="UN")
        assert created == expected_created
        assert (args, snapshots, plans) == before
        if created:
            row = book.orders[created[0]]
            assert row["qty"] == 1200 and row["release_day"] == 15 and row["available_day"] == 20
            assert row["source_requirement_id"] in audit[SOURCE]["transfer_pegs"]
            assert sum(Decimal(str(a["qty"])) for a in row["support_allocations"]) == 1200
            assert all("planning_requirement_id" in a for a in row["support_allocations"])
            assert record_started_transfer_campaign(book, day=13, source_pair=SOURCE,
                campaign_id="C", campaign_qty=1200, executed_qty=600,
                new_plan=plans[SOURCE], snapshot=snapshots[SOURCE], uom="UN") == ()
            assert book.handoff(pair=DEST, day=15, quantity=1200, shipment_id="S", available_day=20) == 1200
            assert book.orders[created[0]]["remaining_qty"] == 0 and len(book.orders) == 1


def test_existing_transfer_commitment_survives_local_reconciliation_and_nets_once():
    args = _network(G, commitments=True)
    args["available_by_pair"][SOURCE] = 600
    args["firm_receipts_by_pair"] = {SOURCE: [FirmReceipt("quality", 5, 600, "held")]}
    args["transfer_commitment_rows"] = (dict(commitment_id="internal_commitment:old",
        source_pair=SOURCE, destination_pair=DEST, qty=600, dispatch_day=15,
        promised_day=20, release_day=15, available_day=20),)
    before = deepcopy(args)
    plans, requirements, audit = plan_component_network(**args)
    assert args == before
    assert Requirement("internal_commitment:old", 15, 600) in requirements[SOURCE]
    assert _sum(requirements[SOURCE]) == 1200  # C600 plus remaining revocable D600.
    assert plans[SOURCE].proposed_qty == 0  # Available600 + real held600, each once.
    assert _sum(requirements.get(RAW, ())) == 0
    assert [(r.receipt_id, r.qty) for r in audit[DEST]["firm_receipts"]] == [("internal_commitment:old", 600)]
    assert audit[SOURCE]["manufactured_output_mrp"]["summary"]["residual_source_qty"] == 0


def test_fractional_forecast_parts_cannot_inflate_a_physical_UN_order():
    result, _ = _reconcile([], (_window(4, 100),), L)
    assert _sum(result) == 100
    args = _network(L, source_forecast=100)
    args["lot_sizing_by_pair"][SOURCE] = LotSizing(integer=True)
    plans, _, _ = plan_component_network(**args)
    assert plans[SOURCE].proposed_qty == 100
    assert all(p.qty == int(p.qty) for p in plans[SOURCE].proposals)


def test_calendar_uses_prior_vintage_for_current_week_and_no_future_information():
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="local-I",
        semantics="industrial_total_gross_requirements_planning_only", versioned_series=[dict(
            node_id=SOURCE[0], item_id=SOURCE[1], uom="G", repeat_period_days=0, period_days=7,
            period_anchor_day=4, current_bucket_policy="freeze_previous_exclude_current_vintage",
            missing_future_policy="unprovided_not_observed_zero", versions=[
                dict(known_day=0, rows=[dict(period_start_day=4, period_days=7, qty=700,
                    source_file="source.xlsx", source_cells="I1")]),
                dict(known_day=4, rows=[dict(period_start_day=11, period_days=7, qty=1400,
                    source_file="source.xlsx", source_cells="I2")]),
                dict(known_day=11, rows=[dict(period_start_day=18, period_days=7, qty=0,
                    source_file="source.xlsx", source_cells="I3")])])])
    calendar = IndustrialComponentPlanningCalendar(payload, pair_uoms={SOURCE: "G"}, origin_date="2025-01-01")
    selected = calendar.windows(SOURCE, decision_day=4, first_day=5, through_day=24)
    assert [(w.period_start_day, w.qty, w.known_day) for w in selected] == [(4, 600, 0), (11, 1400, 4)]
    selected = calendar.windows(SOURCE, decision_day=11, first_day=12, through_day=24)
    assert [(w.period_start_day, w.qty, w.known_day) for w in selected] == [(11, 1200, 4), (18, 0, 11)]


def test_opt_in_scope_and_export_preserve_auditable_input_and_alias_dates():
    payload = dict(schema_version=1, mode=G, pairs=[dict(node_id=SOURCE[0], item_id=SOURCE[1],
        source_file="source.xlsx", source_cells="I1:I52")])
    assert resolve_manufactured_output_mrp_policy(None, produced_pairs={SOURCE}, bom_by_pair={SOURCE: [(RAW, 2)]}) is None
    assert resolve_manufactured_output_mrp_policy(payload, produced_pairs={SOURCE}, bom_by_pair={SOURCE: [(RAW, 2)]}) == payload
    invalid = deepcopy(payload)
    invalid["pairs"][0]["node_id"] = "unmodeled"
    with pytest.raises(ValueError):
        resolve_manufactured_output_mrp_policy(invalid, produced_pairs={SOURCE}, bom_by_pair={SOURCE: [(RAW, 2)]})
    _, _, audit = plan_component_network(**_network(G, commitments=True))
    rows = manufactured_output_mrp_export_rows(audit, decision_day=0, phase="before_dispatch",
        modes={SOURCE: G}, item_units={SOURCE[1]: "G"})
    inputs = [json.loads(r["record_json"]) for r in rows if r["record_type"] == "replaced_revocable"]
    fragments = [json.loads(r["record_json"]) for r in rows if r["record_type"] == "fragments"]
    assert len(inputs) == 1 and inputs[0]["qty"] == 1200
    assert inputs[0]["transfer_peg"]["release_day"] == 15
    assert all(r["original_target_day"] == 15 and r["transfer_peg"]["qty"] == 1200 for r in fragments)
    assert len({r["requirement_id"] for r in fragments}) == len(fragments)


def test_reconciliation_rejects_unknown_modes_future_source_and_overlapping_windows():
    with pytest.raises(ValueError):
        _reconcile([], (), "silent_local")
    future = IndustrialPlanningWindow(4, 4, 11, 600, 1, "source.xlsx", "I1")
    with pytest.raises(ValueError):
        _reconcile([], (future,), L)
    with pytest.raises(ValueError):
        _reconcile([], (_window(4, 600), _window(4, 600)), G)


def test_horizon_common_reconciles_uncovered_D_instead_of_adding_it_again():
    needs = [Requirement("derived:covered", 5, 4200), Requirement("derived:unprovided", 14, 6600)]
    windows = (_window(4, 10800),)
    local, _ = _reconcile(needs, windows, L)
    first_common, _ = _reconcile(needs, windows, G)
    result, audit = _reconcile(needs, windows, G2)
    assert _sum(local) == 17400 and _sum(first_common) == 17400
    assert _sum(result) == 10800  # Jan5 quantities: I10800 vs total D4200+6600.
    assert audit["summary"]["covered_revocable_qty"] == 4200
    assert audit["summary"]["all_revocable_input_qty"] == 10800
    assert audit["summary"]["outside_source_coverage_revocable_qty"] == 6600
    assert audit["summary"]["fallback_qty"] == 0 and audit["fallback"] == []
    assert {r["requirement_id"]: r["source_covered"] for r in audit["replaced_revocable"]} == {
        "derived:covered": True, "derived:unprovided": False}
    for original in needs:
        fragments = [r for r in audit["fragments"] if r["original_requirement_id"] == original.requirement_id]
        assert sum(Decimal(str(r["qty"])) for r in fragments) == original.qty
        assert all(r["original_target_day"] == original.due_day for r in fragments)
        assert all(r["allocation_basis"] == "snapshot_fifo_hypothesis" for r in fragments)


def test_horizon_common_keeps_already_due_D_before_any_local_I():
    needs = [Requirement("derived:late", -1, 300), Requirement("derived:today", 0, 300),
             Requirement("derived:future", 14, 600)]
    result, audit = _reconcile(needs, (_window(4, 600),), G2)
    assert _sum(result) == 1200
    assert [(r.due_day, r.qty) for r in result] == [(-1, 300), (0, 300), (14, 600)]
    assert audit["summary"]["covered_revocable_qty"] == 0
    assert audit["summary"]["outside_source_coverage_revocable_qty"] == 1200
    assert set(audit["requirement_aliases"].values()) == {r.requirement_id for r in needs}


def test_horizon_common_without_I_preserves_D_profile_and_network_quantities():
    needs = [Requirement("derived:a", 5, 600), Requirement("derived:b", 14, 1200)]
    result, audit = _reconcile(needs, (), G2)
    assert [(r.due_day, r.qty) for r in result] == [(5, 600), (14, 1200)]
    assert audit["summary"]["source_qty"] == 0 and audit["summary"]["fallback_qty"] == 0
    assert all(not r["source_covered"] for r in audit["replaced_revocable"])
    args = _network()
    nominal, _, _ = plan_component_network(**args)
    common, _, _ = plan_component_network(**args,
        manufactured_output_mrp_by_pair={SOURCE: G2}, manufactured_output_windows_by_pair={SOURCE: ()})
    for pair in nominal:
        assert [(p.release_day, p.available_day, p.qty) for p in nominal[pair].proposals] == [
            (p.release_day, p.available_day, p.qty) for p in common[pair].proposals]


def test_horizon_common_preserves_outside_C_and_reserve_without_consuming_I():
    firm = Requirement("internal_commitment:outside", 20, 600)
    reserve = Requirement("reserve:source", 19, 100)
    needs = [firm, reserve, Requirement("derived:unprovided", 14, 600)]
    result, audit = _reconcile(needs, (_window(4, 600),), G2)
    assert firm in result and reserve in result and _sum(result) == 1300
    assert audit["summary"]["matched_committed_qty"] == 0
    assert audit["summary"]["residual_source_qty"] == 600
    assert {r["requirement_id"] for r in audit["fallback"]} == {firm.requirement_id, reserve.requirement_id}
    assert audit["summary"]["fallback_qty"] == 700
    payload = dict(schema_version=1, mode=G2, pairs=[dict(node_id=SOURCE[0], item_id=SOURCE[1],
        source_file="source.xlsx", source_cells="I1")])
    assert resolve_manufactured_output_mrp_policy(payload, produced_pairs={SOURCE},
        bom_by_pair={SOURCE: [(RAW, 2)]}) == payload
