"""Synthetic calibration inputs; no simulation or historical campaign reads."""

from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as protocol,
)


def build_synthetic_plan(root: Path) -> Path:
    reference = root / "reference"
    graph_path, engine, profile = (root / name for name in ("graph.json", "engine.py", "profile.json"))
    root.mkdir(parents=True, exist_ok=True)
    engine.write_text("raise RuntimeError('Synthetic fixture: engine must never run')\n", encoding="utf-8")
    protocol.write_json(profile, {"synthetic_test_only": True, "args": []})
    lanes, edges = [], []
    for index in range(18):
        supplier, item, destination = f"supplier:{index}", f"item:{index}", "factory:test"
        edge_id = f"edge:{index}"
        lanes.append(dict(supplier_id=supplier, item_id=item, dst_node_id=destination,
                          edge_id=edge_id, target_product_id=protocol.PRODUCTS[index % 2]))
        edges.append({"id": edge_id, "from": supplier, "to": destination, "items": [item],
                      "service_level": {"otif": 1.0}, "lead_time": {"mean": 2.0},
                      "delay_step_limit": {"value": 4}})
    nodes = {}
    for (node, item), capacity in protocol.MODELED_FINISHED_FACTORY_PROCESSES.items():
        nodes.setdefault(node, {"id": node, "processes": []})["processes"].append(
            {"outputs": [{"item_id": item}], "capacity": {"max_rate": capacity}})
    demands = [{"node_id": protocol.CLIENT_NODE_ID, "item_id": f"item:{product}",
                "profile": [{"points": [{"value": 100.0}]}]} for product in protocol.PRODUCTS]
    protocol.write_json(graph_path, {"synthetic_test_only": True, "nodes": list(nodes.values()),
                                     "edges": edges, "scenarios": [{"demand": demands}]})
    protocol.write_csv(reference / "active_lane_reference.csv", lanes)
    floors = [{"supplier_id": supplier, "item_id": item, "dst_node_id": destination,
               "tested_capacity_floor_qty_per_day": capacity}
              for (supplier, item, destination), capacity in protocol.IDENTIFIED_CAPACITY_PAIRS.items()]
    protocol.write_csv(reference / "inputs" / "prepared_physical_supplier_floors.csv", floors)
    rows = []
    for seed in [protocol.SCREENING_SEED, *protocol.FINAL_CONFIRMATION_SEEDS]:
        row = {"scenario_id": "baseline_nominal", "seed": seed, "valid": True}
        for product in protocol.PRODUCTS:
            row.update({f"horizon_complete_{product}": True,
                        f"on_due_volume_proxy_{product}": 0.99, f"demand_qty_{product}": 1000.0})
        rows.append(row)
    protocol.write_csv(reference / "screening_metrics.csv", rows[:1])
    protocol.write_csv(reference / "confirmation_metrics.csv", rows[1:])
    protocol.write_json(reference / "campaign_manifest.json", {
        "synthetic_test_only": True, "status": "complete", "days": protocol.MEASURED_DAYS,
        "graph_sha256": protocol.sha256_file(graph_path), "engine_sha256": protocol.sha256_file(engine),
        "profile_sha256": protocol.sha256_file(profile)})
    combined, stock = root / "legacy_combined", root / "legacy_stock"
    protocol.write_csv(combined / "paired_replay_results.csv", [
        {"variant": "target_hypothesis", "fill_rate_268091": 0.93, "fill_rate_268967": 0.8}])
    protocol.write_csv(stock / "baseline_calibration_metrics.csv", [
        {"scenario_id": "baseline_observed_order_book", "state_regime_target_cover_days": days,
         "product_on_due_volume_proxy": 0.8} for days in (300, 384, 385)])
    plan = root / "plan"
    protocol.prepare(output_dir=plan, reference_campaign=reference, graph_path=graph_path,
                     engine_path=engine, profile_path=profile, legacy_combined=combined, legacy_stock=stock)
    return plan
