"""Independent in-memory cases; no filesystem fixture or simulation mutation."""

import math
from copy import deepcopy
from collections import defaultdict

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    activate_initial_transfer_snapshot, dated_supply_release_calendar, plan_component_network,
    campaign_lot_count, canonical_production_batch_target_qty, continue_same_campaign_today,
    launch_campaign_qty, mrp_order_milestone_export_fields,
    production_campaign_work_days, production_remaining_day_capacity,
    internal_transfer_physical_milestones, internal_transfer_commitment_scope, LotLedger,
)
from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip, make_batch_id
from etudecas.simulation.engine.mrp_planning import InternalTransferCommitments, LotSizing, Requirement, FirmReceipt
from etudecas.simulation.engine import run_first_simulation as engine


def test_refresh_keeps_declared_gaillac_stock_without_inventing_route_or_bom():
    from etudecas.knowledge_graph.update_supply_graph_from_case_data import prune_orphan_inventory_states
    state = dict(item_id="item:002612", initial=414.0, uom="KG", initial_source="Stocks!E7:G7")
    row = dict(node_id="SDC-1450", item_id="item:002612", role="stock_external_use",
               supply_status="unconfigured", source_cells="Stocks!E7:G7")
    graph = dict(nodes=[dict(id="SDC-1450", type="factory", processes=[], inventory=dict(states=[state]))],
                 edges=[], meta=dict(managed_inventory_pairs=dict(schema_version=1, rows=[row])))
    before = deepcopy(graph)
    report = dict(unresolved=[])
    prune_orphan_inventory_states(graph, report)
    assert graph == before and report["unresolved"] == []
    assert graph["nodes"][0]["inventory"]["states"][0] is state
    # Repeat refresh is inert; it does not manufacture a stock from its declaration.
    prune_orphan_inventory_states(graph, report)
    assert graph == before


def test_refresh_keeps_candidate_hub_policy_forecast_and_routes_unchanged():
    from etudecas.knowledge_graph.update_supply_graph_from_case_data import prune_orphan_inventory_states
    graph = dict(nodes=[dict(id="SDC-1450", type="factory", processes=[], inventory=dict(states=[
        dict(item_id="item:001893", initial=1094.0, uom="KG")]))],
        edges=[dict(id="explicit-candidate", **{"from":"supplier", "to":"SDC-1450"},
                    items=["item:001893"], attrs=dict(lead_days=35, source="FIA candidate"))],
        meta=dict(managed_inventory_pairs=dict(schema_version=1, rows=[dict(
            node_id="SDC-1450", item_id="item:001893", role="stock_external_use",
            supply_status="configured_candidate", supply_policy=dict(lot_multiple_qty=300))]),
            managed_inventory_forecasts=dict(schema_version=3, rows=[], versioned_series=[dict(source="MRP I")])))
    before = deepcopy(graph)
    prune_orphan_inventory_states(graph, dict(unresolved=[]))
    assert graph == before


def test_refresh_only_preserves_declared_or_referenced_stocks():
    from etudecas.knowledge_graph.update_supply_graph_from_case_data import prune_orphan_inventory_states
    graph = dict(nodes=[dict(id="hub", inventory=dict(states=[
        dict(item_id=item, initial=7, uom="UN") for item in ("orphan", "bought", "made")]),
        processes=[dict(outputs=[dict(item_id="made")])])],
        edges=[{"from":"supplier", "to":"hub", "items":["bought"]}])
    report = dict(unresolved=[])
    prune_orphan_inventory_states(graph, report)
    assert [s["item_id"] for s in graph["nodes"][0]["inventory"]["states"]] == ["bought", "made"]
    assert len(report["unresolved"]) == 1 and "hub/orphan" in report["unresolved"][0]


def _opening_purchase_memory(source="supplier-source", lanes=None):
    """No files: an explicit source supplier and dates must survive absent topology."""
    pair = ("factory", "raw")
    raw = dict(source_row=7, src_node_id=source, dst_node_id=pair[0], item_id=pair[1],
        order_type="purchase_open_order", quantity=1250, uom="KG", physical_delivery_day=12,
        usable_day=24, receipt_release_days=8)
    pipeline, transit, mrp, shipments, initial, assumptions = defaultdict(list), defaultdict(float), [], [], [], []
    result = engine.seed_open_orders_from_metadata(pipeline, transit,
        opening_open_orders_payload=dict(source_file="Extract_En_cours.xlsx", rows=[raw]),
        lanes_by_dest_item={pair: lanes or []}, item_unit_map={"raw":"KG"},
        pair_mrp_safety_time_days={}, total_timeline_days=365, warmup_days=0,
        opening_production_bom_issues_by_day=defaultdict(list), opening_production_order_bom_issue_mode="wip",
        mrp_order_rows=mrp, supplier_shipment_rows=shipments, initialization_pipeline_rows=initial,
        assumptions_ledger_rows=assumptions, dated_purchase_availability=True)
    return dict(raw=raw, pair=pair, result=result, pipeline=pipeline, transit=transit,
                mrp=mrp, shipments=shipments, initial=initial, assumptions=assumptions)


def test_opening_purchase_missing_supplier_route_never_borrows_other_lead_or_edge():
    other = dict(src="other-supplier",edge_id="wrong-edge",lead_days=120,standard_order_qty=9999,mrp_share=1)
    state = _opening_purchase_memory(lanes=[other])
    row=state["mrp"][0]
    assert row["src_node_id"] == "supplier-source" and row["edge_id"] == ""
    assert row["lead_reference_days"] == row["standard_order_qty"] == row["mrp_share"] == 0
    assert row["opening_route_status"] == "source_supplier_route_absent"
    assert row["opening_creation_date_basis"] == "unknown_in_source"
    assert engine.mrp_order_milestone_export_fields(row)["order_decision_day"] == ""
    assert (row["physical_delivery_day"],row["available_day"],row["planned_receipt_qty"]) == (12,24,1250)
    assert state["result"][0] == state["transit"][state["pair"]] == 1250
    assert state["pipeline"][24][0][:3] == ("factory","raw",1250)
    assert state["shipments"][0]["src_node_id"] == "supplier-source"
    assert "route_cost_imputation" in row["opening_cost_basis"]


def test_opening_purchase_exact_route_keeps_source_dates_quantity_and_unknown_creation():
    wrong=dict(src="other",edge_id="wrong",lead_days=120)
    exact=dict(src="supplier-source",edge_id="right",lead_days=21,standard_order_qty=4000,mrp_share=.4)
    state=_opening_purchase_memory(lanes=[wrong,exact]); row=state["mrp"][0]
    assert row["edge_id"] == "right" and row["release_day"] == -9
    assert row["opening_route_status"] == "exact_source_supplier_route"
    assert (row["physical_delivery_day"],row["available_day"],row["planned_receipt_qty"]) == (12,24,1250)
    assert row["opening_creation_date_basis"] == "unknown_in_source"


@pytest.mark.parametrize("source,lanes,status", [
    ("",[dict(src="other",edge_id="x")],"source_supplier_unknown"),
    ("A",[dict(src="A",edge_id="x"),dict(src="A",edge_id="y")],"source_supplier_route_ambiguous"),
])
def test_opening_purchase_unknown_or_ambiguous_route_does_not_choose_first(source,lanes,status):
    lane,audit=engine.opening_purchase_source_route(dict(src_node_id=source),lanes)
    assert lane is None and audit["opening_route_status"]==status


def _opening_material_memory(*, unit="KG", quantity=4, raw_qty=8, capacity=3, unselected=False, ratio=2):
    pair=("Gaillac","semi"); component=("Gaillac","raw")
    units={"semi":unit,"raw":"KG"}
    source=dict(node_id=pair[0],item_id=pair[1],source_file="Extract_En_cours.xlsx",source_row=105,
        source_marker="OF:105",order_type="opening_production_order",physical_delivery_day=0,arrival_day=2,
        receipt_qty=quantity)
    rows=[source]
    if unselected:
        rows.append(dict(source,source_row=106,source_marker="OF:106"))
    policy=dict(schema_version=1,mode="materials_at_source_G_v1",late_release_policy="source_G_I_workdays_v1",
        rows=[dict(source_file="Extract_En_cours.xlsx",source_row=105,node_id=pair[0],item_id=pair[1],
                   source_material_state="unknown",scenario_material_state="to_issue")])
    kwargs=dict(opening_orders=rows,nodes=[dict(id=pair[0],processes=[dict(outputs=[dict(item_id=pair[1])],capacity=dict(max_rate=capacity))])],
        bom_by_pair={pair:[(component,ratio)]},item_unit_map=units,origin_date="2025-01-01",
        dated_execution=True,lot_trace=True,bom_issue_mode="wip",material_policy=policy)
    book=engine.OpeningPackOrders(None,**kwargs)
    stock=defaultdict(float,{component:raw_qty})
    ledger=engine.LotLedger(enabled=True,scenario_id="memory_opening_material")
    ledger.seed_opening_stock(day=-1,stock=stock,item_unit_map=units)
    availability=engine.OpeningPurchaseAvailability([],item_unit_map=units)
    pipeline,transit,commitments=defaultdict(list),defaultdict(float),defaultdict(dict)
    def consume(p,q,f):
        assert q<=stock[p]
        stock[p]-=q
        return ledger.consume(day=f["day"],node_id=p[0],item_id=p[1],qty=q,event_type="production_consume",
                              source_id=f["fragment_id"],uom=units[p[1]])
    def materialize(s,f,parents):
        return engine.materialize_opening_pack_fragment(s,f,parents,ledger=ledger,availability=availability,
            stock=stock,pipeline=pipeline,in_transit=transit,commitments=commitments)
    def execute(day,cap):
        return engine.execute_opening_pack_fifo(book,pair,day=day,capacity=cap,
            available={component:stock[component]},consume=consume,materialize=materialize)
    return dict(pair=pair,component=component,units=units,kwargs=kwargs,policy=policy,book=book,stock=stock,
        ledger=ledger,availability=availability,pipeline=pipeline,transit=transit,commitments=commitments,execute=execute)


def test_opening_material_zero_stock_never_creates_output_or_debits_but_keeps_requirement():
    s=_opening_material_memory(raw_qty=0)
    assert s["execute"](0,3)==(3,[])
    assert not s["pipeline"] and not s["book"].fragments
    needs,receipts=s["book"].planning(0)
    assert needs[s["component"]][0].qty==8
    assert receipts[s["pair"]][0].qty==4
    assert not [r for r in s["ledger"].event_rows if r["event_type"]=="production_consume"]


def test_opening_material_capacity_stock_BOM_genealogy_and_source_dates_conserve():
    s=_opening_material_memory()
    assert s["execute"](-1,3)==(3,[])
    assert s["execute"](0,3)==(3,[])  # Complete source lot needs capacity4.
    assert s["stock"][s["component"]]==8
    assert s["book"].rows["OF:105"]["completed_qty"]==0
    assert s["availability"].held_by_pair[s["pair"]]==0
    assert s["execute"](1,5)[0]==1
    f=s["book"].fragments
    assert [r["qty"] for r in f]==[4]
    assert [r["available_day"] for r in f]==[5]  # Late Thu+2JO->Mon, sourceI remains documented.
    assert s["stock"][s["component"]]==0 and s["stock"][s["pair"]]==0
    assert s["availability"].held_by_pair[s["pair"]]==4
    debits=[r for r in s["ledger"].event_rows if r["event_type"]=="production_consume"]
    assert sum(r["qty"] for r in debits)==8
    assert sum(r["parent_qty"] for r in s["ledger"].genealogy_rows)==8
    assert all(s["ledger"].lots[r["lot_id"]]["uom"]=="KG" for r in f)
    engine.sync_opening_pack_commitments(s["book"],decision_day=1,commitments=s["commitments"])
    assert sum(r[1] for r in s["commitments"][s["pair"]].values())==4
    assert s["execute"](2,3)==(3,[])  # No second creation after completion.
    for r in f:
        s["availability"].release(r["fragment_id"],r["available_day"],r["qty"],ledger=s["ledger"])
    assert s["availability"].held_by_pair[s["pair"]]==0
    assert sum(r["qty"] for r in s["ledger"].event_rows if r["event_type"]=="production_consume")==8


def test_opening_material_selection_is_per_source_identity_not_whole_pair():
    s=_opening_material_memory(unselected=True)
    assert set(s["book"].rows)=={"OF:105"}
    assert s["kwargs"]["opening_orders"][1]["receipt_qty"]==4


def test_opening_material_fractional_KG_and_integer_UN_output_limits():
    kg=_opening_material_memory(quantity=1.5,raw_qty=3,capacity=2)
    assert kg["execute"](0,.75)==(.75,[])
    kg["execute"](1,2)
    assert [f["qty"] for f in kg["book"].fragments]==[1.5]
    assert kg["stock"][kg["component"]]==0
    un=_opening_material_memory(unit="UN",quantity=3,raw_qty=5,capacity=3)
    assert un["execute"](0,2.75)==(2.75,[])
    assert not un["book"].fragments
    assert un["book"].rows["OF:105"]["target_qty"]==3


def test_opening_material_one_kg_missing_blocks_3200_kg_then_completes_once():
    # Independent BOM oracle:3200kg *8.94kg/kg =28608kg, not a computed helper result.
    s=_opening_material_memory(quantity=3200,raw_qty=28607,capacity=6400,ratio=8.94)
    assert s["execute"](0,6400)==(6400,[])
    assert s["stock"][s["component"]]==28607
    assert not s["pipeline"] and not s["book"].fragments
    s["stock"][s["component"]]+=1
    s["ledger"].create_lot(day=1,node_id="Gaillac",item_id="raw",qty=1,uom="KG",source_type="memory_receipt",source_id="topup")
    assert s["execute"](1,6400)[0]==3200
    assert [r["qty"] for r in s["book"].fragments]==[3200]
    assert s["stock"][s["component"]]==0
    assert sum(r["qty"] for r in s["ledger"].event_rows if r["event_type"]=="production_consume")==28608
    assert s["execute"](2,6400)==(6400,[])
    assert len(s["book"].fragments)==1


def test_opening_material_engine_grams_and_unmodeled_capacity_preserve_source_lot():
    s=_opening_material_memory(unit="G",quantity=3200000,raw_qty=28608000,capacity=6400000,ratio=8.94)
    kwargs=deepcopy(s["kwargs"])
    kwargs["nodes"][0]["processes"][0]["capacity"]={}
    book=engine.OpeningPackOrders(None,**kwargs)
    assert book.rows["OF:105"]["output_uom"]=="G"
    f=book.candidate(book.rows["OF:105"],day=0,capacity=float("inf"),available={s["component"]:28608000})
    assert f["qty"]==3200000 and f["components"][s["component"]]==28608000
    assert f["available_day"]==2
    assert not book.candidate(book.rows["OF:105"],day=0,capacity=float("inf"),available={s["component"]:28607999})["qty"]


def test_opening_material_integer_component_roundoff_does_not_double_one_unit():
    s=_opening_material_memory(unit="G",quantity=600000,raw_qty=1,capacity=600000,ratio=1/600000)
    kwargs=deepcopy(s["kwargs"])
    kwargs["item_unit_map"]["raw"]="UN"
    book=engine.OpeningPackOrders(None,**kwargs)
    f=book.candidate(book.rows["OF:105"],day=0,capacity=600000,available={s["component"]:1})
    assert f["qty"]==600000 and f["components"][s["component"]]==1
    # A genuine amount above one physical unit still requires two units.
    kwargs["bom_by_pair"][s["pair"]]=[(s["component"],1.01/600000)]
    book=engine.OpeningPackOrders(None,**kwargs)
    assert not book.candidate(book.rows["OF:105"],day=0,capacity=600000,available={s["component"]:1})["qty"]


@pytest.mark.parametrize("fault",["known_source_state","different_identity","wrong_file","wrong_pair","duplicate_scope","zero_BOM","invalid_output_unit"])
def test_opening_material_rejects_unproved_state_identity_or_execution_contract(fault):
    s=_opening_material_memory();k=deepcopy(s["kwargs"]);p=k["material_policy"]
    if fault=="known_source_state":p["rows"][0]["source_material_state"]="already_consumed"
    elif fault=="different_identity":p["rows"][0]["source_row"]=106
    elif fault=="wrong_file":p["rows"][0]["source_file"]="other.xlsx"
    elif fault=="wrong_pair":p["rows"][0]["item_id"]="other"
    elif fault=="duplicate_scope":p["rows"].append(dict(p["rows"][0]))
    elif fault=="zero_BOM":k["bom_by_pair"]={s["pair"]:[(s["component"],0)]}
    elif fault=="invalid_output_unit":k["item_unit_map"]["semi"]="UNKNOWN"
    with pytest.raises(ValueError):engine.OpeningPackOrders(None,**k)


def test_receiving_time_does_not_move_order_after_physical_receipt():
    # Jan8 decision/dispatch, Jan15 receipt, Jan24 usable: historical export
    # incorrectly reported Jan17 (23-7). The receipt processing is not transport.
    order = dict(day=7, release_day=7, physical_delivery_day=14, available_day=23,
                 arrival_day=23, order_type="lane_release", release_qty=600000)
    exported = {**order, **mrp_order_milestone_export_fields(order)}
    assert (exported["order_decision_day"], exported["order_date_imt"],
            exported["physical_delivery_day"], exported["available_day"]) == (7, 7, 14, 23)
    assert exported["release_qty"] == 600000


def test_decision_and_future_departure_are_different_milestones():
    order = dict(day=5, release_day=14, physical_delivery_day=21, available_day=30,
                 order_type="lane_release", order_date_imt=23)
    result = mrp_order_milestone_export_fields(order)
    assert result["order_decision_day"] == 5
    assert result["order_date_imt"] == 14
    assert result["order_decision_date_basis"] == "recorded_simulation_decision"
    assert order["order_date_imt"] == 23  # Pure projection; no input mutation.


def test_opening_order_does_not_invent_original_decision_on_day_zero():
    order = dict(day=0, release_day=-40, physical_delivery_day=16, available_day=34,
                 order_type="opening_purchase_order")
    result = mrp_order_milestone_export_fields(order)
    assert result["order_decision_day"] == ""
    assert result["order_date_imt"] == -40
    assert result["order_decision_date_basis"] == "opening_order_original_decision_unknown"


def test_opening_production_decision_also_remains_unknown():
    order = dict(day=0, release_day=3, arrival_day=18, order_type="opening_production_order")
    result = mrp_order_milestone_export_fields(order)
    assert result["order_decision_day"] == ""
    assert result["order_date_imt"] == 3


def _memory_campaign(capacity, material, *, campaign=150, pack=0):
    """Small independent physical budget: one input unit per work unit, lots50."""
    left, consumed, finished, lots, parents = campaign, 0, 0, [], []
    batch = None
    for sequence in range(1, math.ceil(campaign / 50) + 1):
        cap = production_remaining_day_capacity(capacity, executed_qty=consumed, opening_pack_qty=pack)
        batch = ProductionBatchWip("C1", make_batch_id("C1", sequence), "factory", "item:PF",
                                   0, 0, min(50, left))
        qty = min(cap, material - consumed, batch.remaining_qty)
        accepted = batch.add_execution(qty, [dict(lot_id="RAW1", qty=qty)])
        assert accepted == qty
        consumed += qty
        left -= qty
        released = batch.target_qty if batch.is_complete else 0
        if released:
            lots.append(batch.batch_id)
            parents.extend(batch.parent_allocations)
            finished += released
        if not continue_same_campaign_today(campaign_id="C1", remaining_campaign_id="C1" if left else "",
                remaining_qty=left, executed_qty=qty, completed_batch_qty=released,
                remaining_capacity_qty=production_remaining_day_capacity(
                    capacity, executed_qty=consumed, opening_pack_qty=pack)):
            break
    return dict(finished=finished, wip=0 if batch.is_complete else batch.executed_qty,
                consumed=consumed, remaining=left, batches=lots,
                finished_parent_qty=sum(p["qty"] for p in parents))


@pytest.mark.parametrize("capacity,material,expected", [
    (200, 200, (150, 0, 150, 0, 3)),
    (120, 200, (100, 20, 120, 30, 2)),
    (200, 75, (50, 25, 75, 75, 1)),
    (float("inf"), 200, (150, 0, 150, 0, 3)),
])
def test_intraday_campaign_conserves_work_material_and_distinct_batches(capacity, material, expected):
    result = _memory_campaign(capacity, material)
    assert (result["finished"], result["wip"], result["consumed"], result["remaining"],
            len(result["batches"])) == expected
    assert len(set(result["batches"])) == len(result["batches"])
    assert result["finished_parent_qty"] == result["finished"]
    assert result["finished"] + result["wip"] == result["consumed"]


def test_intraday_pack_shares_capacity_without_being_executed_again():
    result = _memory_campaign(120, 200, pack=60)
    assert (result["finished"], result["wip"], result["consumed"]) == (50, 10, 60)
    assert 60 + result["consumed"] == 120


def test_intraday_cannot_start_another_campaign_with_unused_capacity():
    result = _memory_campaign(200, 200, campaign=50)
    assert result["finished"] == result["consumed"] == 50
    assert result["remaining"] == result["wip"] == 0
    with pytest.raises(RuntimeError, match="cannot switch"):
        continue_same_campaign_today(campaign_id="C1", remaining_campaign_id="C2", remaining_qty=50,
                                     executed_qty=50, completed_batch_qty=50, remaining_capacity_qty=100)


def test_intraday_planning_changes_only_the_explicit_convention():
    assert production_campaign_work_days(150, capacity_qty=120, fixed_lot_qty=50) == 3
    assert production_campaign_work_days(150, capacity_qty=120, fixed_lot_qty=50, intraday=True) == 2
    assert production_campaign_work_days(9600, capacity_qty=0, fixed_lot_qty=3200) == 3
    assert production_campaign_work_days(9600, capacity_qty=0, fixed_lot_qty=3200, intraday=True) == 1
    with pytest.raises(RuntimeError, match="exceeded"):
        production_remaining_day_capacity(120, executed_qty=70, opening_pack_qty=60)


def test_intraday_finishes_yesterdays_wip_without_reconsuming_old_parents():
    policy = dict(enabled=True, fixed_lot_qty=50)
    first = ProductionBatchWip("C1", "C1-B001", "factory", "item:PF", -1, -1, 50,
                               executed_qty=40, parent_allocations=[dict(lot_id="YESTERDAY", qty=40)])
    remaining, consumed_today, produced, parent_qty = 110, 0, 0, 0
    passes = campaign_lot_count(remaining, policy)
    assert passes == 3
    for index in range(passes):
        batch = first if index == 0 else ProductionBatchWip(
            "C1", make_batch_id("C1", index + 1), "factory", "item:PF", -1, 0,
            canonical_production_batch_target_qty(remaining, policy, "UN"))
        qty = batch.remaining_qty
        batch.add_execution(qty, [dict(lot_id="TODAY", qty=qty)])
        consumed_today += qty
        remaining -= qty
        assert batch.is_complete
        produced += batch.target_qty
        parent_qty += sum(p["qty"] for p in batch.parent_allocations)
        assert continue_same_campaign_today(campaign_id="C1", remaining_campaign_id="C1" if remaining else "",
            remaining_qty=remaining, executed_qty=qty, completed_batch_qty=batch.target_qty,
            remaining_capacity_qty=float("inf")) == (index < 2)
    assert (consumed_today, produced, parent_qty, remaining) == (110, 150, 150, 0)


def test_min_max_multiple_campaign_remains_one_batch_not_a_second_launch():
    policy = dict(enabled=True, fixed_lot_qty=0, min_lot_qty=28800,
                  max_lot_qty=142485, lot_multiple_qty=14400)
    campaign = launch_campaign_qty(150000, policy)
    assert campaign == 129600  # Nine complete pallets under the unchanged max.
    assert campaign_lot_count(campaign, policy) == 1
    assert canonical_production_batch_target_qty(campaign, policy, "UN") == campaign
    assert not continue_same_campaign_today(campaign_id="C1", remaining_campaign_id="", remaining_qty=0,
        executed_qty=campaign, completed_batch_qty=campaign, remaining_capacity_qty=203550-campaign)


def _initial_transfer_case(*, stock=6400, lead=10, receipt=6, gross=6400, orders=()):
    source, dest = ("maker", "intermediate"), ("user", "intermediate")
    row = dict(snapshot_id="first-source", known_day=4, node_id=dest[0], item_id=dest[1],
        source_node_id=source[0], uom="KG", current_week_start_day=4, current_week_end_day=10,
        origin_current_issue_qty=6400, origin_current_available_qty=6400, source_cells="I-source;J-source",
        destination_receipts=[dict(week_start_day=11, week_end_day=17, qty=gross, source_cells="H-destination")])
    calendar = dated_supply_release_calendar(decision_day=4, through_day=60,
        physical_lead_days=lead, receipt_days=receipt, review_days=7, pair_review_days=7,
        origin_date="2025-01-01")
    return dict(day=4, observations=[row], book=InternalTransferCommitments(), processed=set(),
        calendars={dest: calendar}, lanes_by_dest_item={dest: [dict(src=source[0], lead_days=lead)]},
        eligible_pairs={dest}, available_by_pair={source: stock}, existing_orders=orders,
        item_uoms={dest[1]: "KG"})


def test_initial_transfer_is_known_once_and_does_not_create_physical_stock():
    args = _initial_transfer_case()
    args["day"] = 3  # Closing Jan4 must not activate a Jan5 source snapshot.
    assert activate_initial_transfer_snapshot(**args) == []
    assert not args["book"].orders and not args["processed"]
    args["day"] = 4
    audit = activate_initial_transfer_snapshot(**args)
    assert (audit[0]["selected_qty"], audit[0]["release_day"],
            audit[0]["physical_delivery_day"], audit[0]["available_day"]) == (6400, 7, 17, 26)
    assert args["available_by_pair"] == {("maker", "intermediate"): 6400}
    assert len(args["book"].events) == 1
    assert activate_initial_transfer_snapshot(**args) == []
    args["day"] = 11
    assert activate_initial_transfer_snapshot(**args) == []
    assert len(args["book"].events) == 1


@pytest.mark.parametrize("covered,expected", [(0,6400), (3200,3200), (6400,0), (9600,0)])
def test_initial_transfer_deducts_existing_route_orders_once(covered, expected):
    existing = dict(src_node_id="maker", dst_node_id="user", item_id="intermediate",
                    physical_delivery_day=16, planned_receipt_qty=covered, mrp_order_id="EXISTING")
    args = _initial_transfer_case(orders=[existing, dict(existing)])
    audit = activate_initial_transfer_snapshot(**args)
    assert audit[0]["selected_qty"] == expected
    assert audit[0]["existing_order_cover_qty"] == covered


def test_initial_transfer_does_not_use_current_or_later_H_for_693_counterexample():
    args = _initial_transfer_case(stock=590, lead=7, receipt=7, gross=0)
    args["observations"][0]["origin_current_issue_qty"] = 1800
    args["observations"][0]["origin_current_available_qty"] = 590
    args["observations"][0]["destination_receipts"] += [
        dict(week_start_day=4, week_end_day=10, qty=600, source_cells="H811"),
        dict(week_start_day=18, week_end_day=24, qty=600, source_cells="H813")]
    audit = activate_initial_transfer_snapshot(**args)
    assert audit[0]["physical_delivery_day"] == 14
    assert audit[0]["selected_qty"] == 0
    assert not args["book"].orders


@pytest.mark.parametrize("field", ["physical_available", "origin_current_issue_qty", "origin_current_available_qty"])
def test_initial_transfer_requires_full_source_corroboration_and_available_stock(field):
    args = _initial_transfer_case()
    if field == "physical_available":
        args["available_by_pair"][("maker", "intermediate")] = 6399
    else:
        args["observations"][0][field] = 6399
    assert activate_initial_transfer_snapshot(**args)[0]["selected_qty"] == 0
    assert not args["book"].orders


def test_initial_transfer_rejects_fractional_UN():
    args = _initial_transfer_case(gross=3.5)
    args["observations"][0]["uom"] = args["item_uoms"]["intermediate"] = "UN"
    with pytest.raises(ValueError, match="physical units"):
        activate_initial_transfer_snapshot(**args)


@pytest.mark.parametrize("quantity", [0.5, -1, float("inf"), float("nan"), True, False])
def test_initial_transfer_rejects_invalid_existing_physical_UN_cover(quantity):
    existing = dict(src_node_id="maker",dst_node_id="user",item_id="intermediate",
        physical_delivery_day=17,planned_receipt_qty=quantity,mrp_order_id="EXISTING")
    args = _initial_transfer_case(orders=[existing])
    args["observations"][0]["uom"] = args["item_uoms"]["intermediate"] = "UN"
    with pytest.raises(ValueError, match="physical units"):
        activate_initial_transfer_snapshot(**args)


@pytest.mark.parametrize("planned", [0, None, ""])
def test_initial_transfer_documented_zero_cover_is_not_an_absent_receipt(planned):
    existing = dict(src_node_id="maker",dst_node_id="user",item_id="intermediate",
        physical_delivery_day=17,planned_receipt_qty=planned,release_qty=0.5,mrp_order_id="EXISTING")
    args = _initial_transfer_case(orders=[existing])
    args["observations"][0]["uom"] = args["item_uoms"]["intermediate"] = "UN"
    if planned == 0:
        audit = activate_initial_transfer_snapshot(**args)
        assert audit[0]["existing_order_cover_qty"] == 0
        assert audit[0]["selected_qty"] == 6400
    else:
        with pytest.raises(ValueError, match="physical units"):
            activate_initial_transfer_snapshot(**args)


@pytest.mark.parametrize("covered", [0, 3200, 6400])
@pytest.mark.parametrize("covered_destination", ["user", "user2"])
def test_initial_transfer_shares_origin_I_across_destinations_and_existing_orders(covered, covered_destination):
    args = _initial_transfer_case(stock=12800)
    first = args["observations"][0]
    first["origin_current_available_qty"] = 12800
    second = deepcopy(first)
    second.update(snapshot_id="second-destination",node_id="user2")
    args["observations"].append(second)
    pair2 = ("user2","intermediate")
    args["calendars"][pair2] = args["calendars"][("user","intermediate")]
    args["lanes_by_dest_item"][pair2] = [dict(src="maker",lead_days=10)]
    args["eligible_pairs"].add(pair2)
    existing = dict(src_node_id="maker",dst_node_id=covered_destination,item_id="intermediate",
        physical_delivery_day=17,planned_receipt_qty=covered,mrp_order_id="EXISTING")
    args["existing_orders"] = [existing,dict(existing)]
    audit = activate_initial_transfer_snapshot(**args)
    assert sum(row["selected_qty"] for row in audit) + covered == 6400
    if covered_destination == "user":
        assert audit[1]["selected_qty"] == 0
    assert args["available_by_pair"][("maker","intermediate")] == 12800


def test_initial_transfer_book_nets_once_and_empty_scope_does_not_change_planning():
    args = _initial_transfer_case()
    source, dest, raw = ("maker", "intermediate"), ("user", "intermediate"), ("maker", "raw")
    network = dict(decision_day=4, requirements_by_pair={dest:[Requirement("use", 26, 6400)]},
        available_by_pair={source:6400,raw:100000}, firm_receipts_by_pair={},
        transport_sources_by_pair={dest:[(source,1)]}, bom_by_pair={source:[(raw,1)]},
        lead_days_by_pair={source:10,dest:19,raw:1},
        lot_sizing_by_pair={source:LotSizing(multiple=3200),dest:LotSizing(multiple=3200),raw:LotSizing()},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        availability_by_release_by_pair=args["calendars"])
    baseline = plan_component_network(**network)
    empty = plan_component_network(**network, transfer_commitment_pairs={dest}, transfer_commitment_rows=())
    assert baseline[:2] == empty[:2]
    for pair in baseline[2]:
        assert baseline[2][pair] == {k:v for k,v in empty[2][pair].items()
                                    if k not in {"transfer_pegs","transfer_promises"}}
    activate_initial_transfer_snapshot(**args)
    book = args["book"]
    promises = book.planning_rows(decision_day=4, calendars=args["calendars"])
    plans, needs, audit = plan_component_network(**network, transfer_commitment_pairs={dest}, transfer_commitment_rows=promises)
    assert all(p.proposed_qty == 0 for p in plans.values())
    assert sum(r.qty for r in needs[source]) == 6400
    assert book.handoff(pair=dest,day=7,quantity=3200,shipment_id="SHIP1",available_day=26) == 3200
    network["decision_day"] = 7
    network["available_by_pair"][source] = 3200
    network["firm_receipts_by_pair"][dest] = [FirmReceipt("SHIP1",26,3200,"in_transit")]
    plans, needs, audit = plan_component_network(**network, transfer_commitment_pairs={dest},
        transfer_commitment_rows=book.planning_rows(decision_day=7,calendars=args["calendars"]))
    assert all(p.proposed_qty == 0 for p in plans.values())
    assert sum(r.qty for r in audit[dest]["firm_receipts"]) == 6400
    assert sum(r.qty for r in needs[source]) == 3200


@pytest.mark.parametrize("decision,arrival,lead,departure,transit,wait", [
    (7,17,10,15,2,8),  # Jan8 reservation, Jan16 departure, Jan18 arrival.
    (7,14,7,12,2,5),   # Same convention on the other manufactured intermediate.
    (7,8,1,7,1,0),     # A one-day delivery is not delayed to force two-day transit.
    (8,10,2,8,2,0),    # Friday departure and Sunday receipt retain calendar days.
    (10,17,7,15,2,5),  # Weekend decision remains a calendar-day date, no hidden shift.
    (358,368,10,366,2,8),  # Reservation stays on site at the 362-day closing.
    (7,20,10,18,2,11), # An existing later delivery slot is also preserved.
])
def test_reserved_origin_preserves_delivery_date(decision,arrival,lead,departure,transit,wait):
    timing = internal_transfer_physical_milestones(decision_day=decision,arrival_day=arrival,
        delivery_days=lead,transit_days=2)
    assert timing["release_day"] == departure
    assert timing["physical_transport_days"] == transit
    assert timing["origin_reserved_wait_days"] == wait
    assert timing["delivery_effective_days"] == arrival-decision == wait+transit
    order = dict(day=decision,release_day=departure,physical_delivery_day=arrival,
                 available_day=arrival+9,order_type="lane_release")
    dates = mrp_order_milestone_export_fields(order)
    assert dates["order_decision_day"] == decision
    assert dates["order_date_imt"] == departure


@pytest.mark.parametrize("changes", [dict(transit_days=0),dict(transit_days=True),
    dict(delivery_days=0),dict(arrival_day=16),dict(decision_day=7.0)])
def test_reserved_origin_rejects_invalid_calendar_contract(changes):
    args = dict(decision_day=7,arrival_day=17,delivery_days=10,transit_days=2)
    with pytest.raises(ValueError):
        internal_transfer_physical_milestones(**(args|changes))


def test_reserved_origin_retains_integer_lot_identity_without_second_consumption():
    ledger=LotLedger(enabled=True,scenario_id="memory")
    lot=ledger.create_lot(day=0,node_id="origin",item_id="item:U",qty=100,uom="UN",source_type="initial")
    allocation=ledger.consume(day=7,node_id="origin",item_id="item:U",qty=60,uom="UN",
        event_type="shipment_reserve",shipment_id="SHIP1",departure_day=15,arrival_day=17)
    assert ledger.lots[lot]["qty_remaining"] == 40
    assert sum(a["qty"] for a in allocation) == 60
    ledger.record_allocation_event(day=15,event_type="lane_ship",parent_allocations=allocation,
        shipment_id="SHIP1",departure_day=15,arrival_day=17)
    assert ledger.lots[lot]["qty_remaining"] == 40
    events=[r for r in ledger.event_rows if r["shipment_id"] == "SHIP1"]
    assert [(r["day"],r["event_type"]) for r in events] == [(7,"shipment_reserve"),(15,"lane_ship")]
    assert all(r["lot_id"] == lot for r in events)


def test_reserved_origin_scope_excludes_external_and_finished_goods():
    raw,pfi,pf=("factory","raw"),("factory","semi"),("dc","finished")
    lanes={raw:[dict(src="supplier")],pfi:[dict(src="maker")],pf:[dict(src="factory")]}
    scope=internal_transfer_commitment_scope("initial_snapshot_matched_v1",
        lanes_by_dest_item=lanes,produced_pairs={("maker","semi"),("factory","finished")},
        production_input_pairs={raw,pfi,pf},push_destinations={pf})
    assert scope == {pfi}



def _local_safety_memory(*, unit="KG", scale=1):
    pair,raw=("plant","semi"),("plant","raw")
    series=dict(node_id=pair[0],item_id=pair[1],uom=unit,period_anchor_day=4,period_days=7,
        repeat_period_days=0,current_bucket_policy="freeze_previous_exclude_current_vintage",
        missing_future_policy="unprovided_not_observed_zero",safety_source_file="policy.xlsx",
        safety_source_cells="policy!E2",safety_source_working_days=20,
        versions=[dict(known_day=81,rows=[dict(period_start_day=102,period_days=7,qty=6400*scale,
            source_file="MRP.xlsx",source_cells="I2")])])
    policy=dict(schema_version=1,mode="latest_local_I_for_safety_v1",
        scope="manufactured_outputs_with_documented_source_safety_days_and_local_I",
        missing_policy="current_network_requirements_per_unprovided_day",
        current_week_policy="freeze_previous_exclude_current_vintage",
        calendar=dict(schema_version=1,origin="2025-01-01",scenario_id="memory",
            semantics="industrial_total_gross_requirements_planning_only",versioned_series=[series]))
    nodes=[dict(id=pair[0],processes=[dict(outputs=[dict(item_id=pair[1])])],inventory=dict(states=[
        dict(item_id=pair[1],mrp_policy=dict(safety_time_days=20,source="policy.xlsx/policy!E2"))]))]
    units={pair[1]:unit,raw[1]:unit}
    calendar=engine.resolve_local_safety_forecasts(policy,nodes=nodes,item_unit_map=units,origin_date="2025-01-01")
    override=engine.local_safety_forecast_inputs(calendar,decision_day=81,through_day=140,item_unit_map=units)
    network=dict(decision_day=81,requirements_by_pair={pair:[]},available_by_pair={pair:3200*scale,raw:100000*scale},
        firm_receipts_by_pair={},transport_sources_by_pair={},bom_by_pair={pair:[(raw,1)]},
        lead_days_by_pair={pair:1,raw:1},lot_sizing_by_pair={pair:LotSizing(multiple=3200*scale),raw:LotSizing()},
        reserve_targets_by_pair={},coverage_days_by_pair={},active_campaigns_by_pair={},
        source_safety_by_pair={pair:dict(safety_days=28,fixed_qty=0,projection=dict(
            source_working_days=20,origin_weekday=2,forecast_through_day=140))})
    return dict(pair=pair,raw=raw,policy=policy,nodes=nodes,units=units,calendar=calendar,
                override=override,network=network)


def test_local_safety_absent_override_preserves_network_and_inputs():
    s=_local_safety_memory(); before=deepcopy(s["network"])
    a=engine.plan_component_network(**s["network"])
    b=engine.plan_component_network(**s["network"],safety_requirements_by_pair={})
    assert a==b and s["network"]==before
    assert engine.resolve_local_safety_forecasts(None,nodes=[],item_unit_map={},origin_date="2025-01-01") is None
    assert engine.local_safety_forecast_inputs(None,decision_day=81,through_day=140,item_unit_map={}) is None


@pytest.mark.parametrize("unit,scale",[("KG",1),("G",1000)])
def test_local_safety_source_I_protects_without_duplicate_need_and_nets_firm_once(unit,scale):
    s=_local_safety_memory(unit=unit,scale=scale);p=s["pair"]
    before=deepcopy(s["network"])
    plans,needs,audit=engine.plan_component_network(**s["network"],safety_requirements_by_pair=s["override"])
    assert needs[p]==[] and plans[p].proposed_qty==3200*scale
    assert audit[p]["chain_source_safety"]["target_qty"]==pytest.approx(6400*scale)
    assert s["network"]==before
    firms={p:[FirmReceipt("engaged",82,3200*scale,"confirmed")]}
    snapshots,plans,needs,audit=engine.reconcile_production_execution_snapshot(
        dict(s["network"],safety_requirements_by_pair=s["override"]),available_by_pair=s["network"]["available_by_pair"],
        firm_receipts_by_pair=firms,produced_pairs={p})
    assert plans[p].proposed_qty==0 and needs[p]==[]
    assert audit[p]["chain_source_safety"]["target_qty"]==pytest.approx(6400*scale)
    assert any(point.minimum_qty==pytest.approx(6400*scale) for point in snapshots[p]["protection"])


def test_local_safety_actual_calendar_20_workdays_and_partial_source_weeks():
    s=_local_safety_memory();series=s["policy"]["calendar"]["versioned_series"][0]
    series["versions"][0]["rows"].append(dict(period_start_day=109,period_days=7,qty=6400,
        source_file="MRP.xlsx",source_cells="I3"))
    cal=engine.resolve_local_safety_forecasts(s["policy"],nodes=s["nodes"],item_unit_map=s["units"],origin_date="2025-01-01")
    override=engine.local_safety_forecast_inputs(cal,decision_day=81,through_day=140,item_unit_map=s["units"])
    _,_,audit=engine.plan_component_network(**s["network"],safety_requirements_by_pair=override)
    # Independent dates: closing March24 +20Mon-Fri =April21; full Apr13-19 plus2/7Apr20-26.
    assert audit[s["pair"]]["chain_source_safety"]["target_qty"]==pytest.approx(6400+2*6400/7)


def test_local_safety_zero_replaces_basis_but_missing_days_keep_current_needs():
    s=_local_safety_memory();series=s["policy"]["calendar"]["versioned_series"][0]
    series["versions"][0]["rows"][0]["qty"]=0
    cal=engine.resolve_local_safety_forecasts(s["policy"],nodes=s["nodes"],item_unit_map=s["units"],origin_date="2025-01-01")
    override=engine.local_safety_forecast_inputs(cal,decision_day=81,through_day=140,item_unit_map=s["units"])
    needs=[Requirement("covered",103,11),Requirement("missing",100,17)]
    selected,audit=engine.select_local_safety_requirements(needs,override[s["pair"]],decision_day=81)
    assert selected==(needs[1],) and needs[0].qty==11
    assert audit["local_safety_documented_days"]==7 and audit["local_safety_documented_I_qty"]==0
    assert audit["local_safety_replaced_network_qty"]==11 and audit["local_safety_retained_network_qty"]==17


def test_local_safety_latest_vintage_current_week_future_omission_and_explicit_zero():
    s=_local_safety_memory();series=s["policy"]["calendar"]["versioned_series"][0]
    row=lambda start,qty:dict(period_start_day=start,period_days=7,qty=qty,source_file="MRP.xlsx",source_cells=f"I{start}")
    series["versions"]=[dict(known_day=4,rows=[row(11,70),row(18,140),row(25,210)]),
        dict(known_day=11,rows=[row(18,0)]),dict(known_day=18,rows=[]),dict(known_day=25,rows=[row(32,700)])]
    cal=engine.resolve_local_safety_forecasts(s["policy"],nodes=s["nodes"],item_unit_map=s["units"],origin_date="2025-01-01")
    early=engine.local_safety_forecast_inputs(cal,decision_day=3,through_day=40,item_unit_map=s["units"])[s["pair"]]
    assert not early["covered_days"] and not early["requirements"]
    current=engine.local_safety_forecast_inputs(cal,decision_day=11,through_day=40,item_unit_map=s["units"])[s["pair"]]
    assert sum(r.qty for r in current["requirements"])==60  # Six remaining days from prior70kgweek.
    assert set(range(18,25))<=current["covered_days"] and 25 not in current["covered_days"]
    omitted=engine.local_safety_forecast_inputs(cal,decision_day=18,through_day=40,item_unit_map=s["units"])[s["pair"]]
    assert set(range(19,25))==set(omitted["covered_days"]) and not omitted["requirements"]
    assert 32 not in omitted["covered_days"]  # Future known_day25 is inaccessible.


def test_local_safety_before_first_plan_falls_back_and_zero_source_days_remain_zero():
    s=_local_safety_memory();p=s["pair"]
    early=engine.local_safety_forecast_inputs(s["calendar"],decision_day=80,through_day=140,item_unit_map=s["units"])
    needs=[Requirement("ordinary_net_need",100,70)]
    selected,audit=engine.select_local_safety_requirements(needs,early[p],decision_day=80)
    assert selected==tuple(needs) and audit["local_safety_documented_days"]==0
    s["policy"]["calendar"]["versioned_series"][0]["safety_source_working_days"]=0
    s["nodes"][0]["inventory"]["states"][0]["mrp_policy"]["safety_time_days"]=0
    calendar=engine.resolve_local_safety_forecasts(s["policy"],nodes=s["nodes"],item_unit_map=s["units"],origin_date="2025-01-01")
    override=engine.local_safety_forecast_inputs(calendar,decision_day=81,through_day=140,item_unit_map=s["units"])
    s["network"]["source_safety_by_pair"][p]["safety_days"]=0
    s["network"]["source_safety_by_pair"][p]["projection"]["source_working_days"]=0
    plans,_,audit=engine.plan_component_network(**s["network"],safety_requirements_by_pair=override)
    assert plans[p].proposed_qty==0 and audit[p]["chain_source_safety"]["target_qty"]==0


@pytest.mark.parametrize("fault",["not_produced","source_days_absent","wrong_policy_provenance","wrong_unit"])
def test_local_safety_generic_selection_rejects_missing_business_evidence(fault):
    s=_local_safety_memory()
    if fault=="not_produced":s["nodes"][0]["processes"]=[]
    elif fault=="source_days_absent":s["nodes"][0]["inventory"]["states"][0]["mrp_policy"].pop("safety_time_days")
    elif fault=="wrong_policy_provenance":s["policy"]["calendar"]["versioned_series"][0]["safety_source_cells"]="other"
    else:s["policy"]["calendar"]["versioned_series"][0]["uom"]="G"
    with pytest.raises(ValueError):engine.resolve_local_safety_forecasts(s["policy"],nodes=s["nodes"],
        item_unit_map=s["units"],origin_date="2025-01-01")


@pytest.mark.parametrize("fault",["future_version","overlap","outside_coverage","duplicate_identity","quantity","covered_days"])
def test_local_safety_rejects_invalid_override_contract(fault):
    from dataclasses import replace
    s=_local_safety_memory();override=deepcopy(s["override"][s["pair"]])
    if fault=="future_version":override["windows"]=(replace(override["windows"][0],known_day=82),)
    elif fault=="overlap":override["windows"]*=2
    elif fault=="outside_coverage":override["requirements"]+=(Requirement("outside",130,1),)
    elif fault=="duplicate_identity":override["requirements"]+=(override["requirements"][0],)
    elif fault=="quantity":override["requirements"]=(replace(override["requirements"][0],qty=1),)+override["requirements"][1:]
    else:override["covered_days"]=frozenset()
    with pytest.raises(ValueError):engine.select_local_safety_requirements([],override,decision_day=81)
