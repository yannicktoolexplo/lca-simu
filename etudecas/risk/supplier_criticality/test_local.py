"""Known-answer supplier criticality cases and the map compatibility boundary."""
from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path
import subprocess
import sys

def criticality_fixture(root: Path):
    """Four competing suppliers, a sole-source item, and an inactive supplier."""
    root.mkdir(parents=True, exist_ok=True)
    suppliers = [f"FIXTURE-S{i}" for i in range(1, 6)]
    raw = {"nodes": [{"id": sid, "type": "supplier_dc", "name": "Supplier " + sid,
                     "inventory": {"states": [{"item_id": "item:R", "initial": 20}]},
                     "processes": ([{"capacity": {"max_rate": 100}}] if i == 0 else []),
                     "simulation_constraints": {"supplier_item_capacity_qty_per_day": {"item:R": 100},
                         "supplier_item_capacity_basis": {"item:R": "fixture"}, "supplier_capacity_scale": 2}}
                    for i, sid in enumerate(suppliers)],
           "edges": [{"from": sid, "to": "F", "items": ["item:R"],
                      "transport_cost": {"value": i + 1}, "lead_time": {"mean": i + 2}}
                     for i, sid in enumerate(suppliers[:4])]}
    raw["nodes"].append({"id": "F", "type": "factory"})
    raw["edges"].append({"from": suppliers[0], "to": "F", "items": ["item:SOLE"],
                         "distance_km": 100, "lead_time": {"mean": 1}})
    datasets = [
        ("shipments", [dict(src_node_id=suppliers[0], dst_node_id="F", item_id="item:R", day=0, shipped_qty=70),
                       dict(src_node_id=suppliers[1], dst_node_id="F", item_id="item:R", day=0, shipped_qty=30),
                       dict(src_node_id=suppliers[0], dst_node_id="F", item_id="item:SOLE", day=1, shipped_qty=10)]),
        ("stocks", [dict(node_id=suppliers[0], day=0, stock_end_of_day=20),
                    dict(node_id=suppliers[0], day=1, stock_end_of_day=10),
                    dict(node_id=suppliers[1], day=0, stock_end_of_day=0)]),
        ("capacity", [dict(node_id=suppliers[0], day=0, utilization=.2),
                      dict(node_id=suppliers[0], day=1, utilization=.8)]),
        ("constraints", [dict(binding_cause="input_shortage", binding_input_item_id="item:SOLE", shortfall_vs_desired_qty=4),
                         dict(binding_cause="capacity", binding_input_item_id="item:R", shortfall_vs_desired_qty=999)]),
        ("sensitivity", [dict(case_id="baseline", status="ok", **{"kpi::fill_rate": 1, "kpi::ending_backlog": 0}),
                         dict(case_id="supplier_stock_node_FIXTURE-S1_low", status="ok", **{"kpi::fill_rate": "0,8", "kpi::ending_backlog": 25}),
                         dict(case_id="supplier_stock_node_FIXTURE-S1_high", status="ok", **{"kpi::fill_rate": 1, "kpi::ending_backlog": 0}),
                         dict(case_id="supplier_capacity_node_FIXTURE-S1_low", status="failed", **{"kpi::fill_rate": .1, "kpi::ending_backlog": 999})]),
        ("structural", [dict(case_id="baseline", status="ok", **{"kpi::fill_rate": 1, "kpi::ending_backlog": 0}),
                        dict(case_id="local_supplier_reliability_node_FIXTURE-S2_adverse", status="ok", **{"kpi::fill_rate": .9, "kpi::ending_backlog": 10})]),
    ]
    paths = []
    for name, rows in datasets:
        path = root / (name + ".csv")
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        paths.append(path)
    audits = {suppliers[0]: {"audit_status": "audited", "audit_risk_index": .8,
                             "criterion_count": 2, "answered_criterion_count": 2},
              suppliers[1]: {"audit_status": "not_available", "criteria": [{"row": 31}, {"row": 58}]}}
    return raw, paths, audits


def test_multiple_supplier_contract_and_known_scores(tmp_path):
    from etudecas.risk.supplier_criticality.local import build_supplier_local_criticality
    raw, paths, audits = criticality_fixture(tmp_path)
    metrics, ranking, summary = build_supplier_local_criticality(raw, *paths, supplier_audits=audits)
    rows = {row["supplier_id"]: row for row in ranking}
    # S1 maximizes volume, activity, sole sourcing and shortage; only standard sensitivity is nonzero.
    assert metrics["FIXTURE-S1"]["scores"]["local"] == 1
    assert metrics["FIXTURE-S1"]["scores"]["system"] == .5
    assert metrics["FIXTURE-S1"]["scores"]["overall"] == .775
    assert rows["FIXTURE-S1"]["avg_stock_end_of_day"] == 15
    assert rows["FIXTURE-S1"]["avg_capacity_utilization"] == .5
    assert rows["FIXTURE-S1"]["shortage_supported_qty"] == 4
    assert rows["FIXTURE-S1"]["standard_fill_impact"] == .2
    assert rows["FIXTURE-S2"]["observed_sourcing_share"] == .3
    assert rows["FIXTURE-S2"]["target_sourcing_share"] == .2
    assert rows["FIXTURE-S3"]["target_sourcing_share"] == .05
    assert rows["FIXTURE-S4"]["target_sourcing_share"] == .05
    assert rows["FIXTURE-S5"]["first_shipment_day"] == ""
    assert rows["FIXTURE-S5"]["overall_criticality_score"] == 0
    assert summary["supplier_count"] == 5
    assert audits["FIXTURE-S2"]["audit_status"] == "estimated"


def test_audit_annotation_does_not_change_operational_rank(tmp_path):
    from etudecas.risk.supplier_criticality.local import build_supplier_local_criticality
    raw, paths, audits = criticality_fixture(tmp_path)
    before = build_supplier_local_criticality(raw, *paths, supplier_audits=deepcopy(audits))
    audits["FIXTURE-S1"]["audit_risk_index"] = 0
    after = build_supplier_local_criticality(raw, *paths, supplier_audits=audits)
    fields = ("supplier_id", "rank", "overall_criticality_score")
    assert [tuple(r[f] for f in fields) for r in before[1]] == [tuple(r[f] for f in fields) for r in after[1]]
    assert before[0]["FIXTURE-S1"]["scores"]["indicative_adjusted"] != after[0]["FIXTURE-S1"]["scores"]["indicative_adjusted"]


def test_missing_sources_and_nested_data_fallback(tmp_path):
    from etudecas.risk.supplier_criticality.local import build_supplier_local_criticality
    missing = tmp_path / "absent.csv"
    assert build_supplier_local_criticality({"nodes": [], "edges": []}, *([missing] * 6))[1] == []
    raw, paths, audits = criticality_fixture(tmp_path / "data")
    direct = build_supplier_local_criticality(raw, *paths, supplier_audits=deepcopy(audits))
    nested = build_supplier_local_criticality(raw, *[tmp_path/p.name for p in paths], supplier_audits=deepcopy(audits))
    assert direct == nested


def test_map_preserves_public_compatibility_imports():
    from etudecas.risk.supplier_criticality import local
    from etudecas.visualization.maps import build_supplychain_worldmap as legacy
    for name in ("build_supplier_local_criticality", "build_edge_item_sets", "select_best_supplier_case_pair"):
        assert getattr(legacy, name) is getattr(local, name)


def test_risk_module_import_does_not_load_visualization():
    code = "import sys,json; import etudecas.risk.supplier_criticality.local; print(json.dumps([m for m in sys.modules if m.startswith('etudecas.visualization')]))"
    result = subprocess.run([sys.executable, "-B", "-c", code], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == []
