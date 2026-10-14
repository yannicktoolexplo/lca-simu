"""Read-only contracts for the autonomous, versioned MRP reference bundle."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "etudecas/config/mrp_reference_20261013.json"


def _config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _graph(config):
    with gzip.open(ROOT / config["assets"]["graph"]["path"], "rt", encoding="utf-8") as stream:
        return json.load(stream)


def test_reference_bundle_is_self_contained_and_hashed():
    config = _config()
    assert config["schema_version"] == 2
    assert config["default_forecast_mode"] == "coherent_scenario"
    assert config["comparison_forecast_modes"] == ["source_priority"]
    active_text = CONFIG.read_text(encoding="utf-8")
    for contract in config["assets"].values():
        path = ROOT / contract["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == contract["sha256"]
        active_text += path.read_text(encoding="utf-8") if path.suffix in {".json", ".py"} else ""
    assert "etudecas/artifacts" not in active_text
    engine_arguments = (ROOT / config["assets"]["engine_arguments"]["path"]).read_text(encoding="utf-8")
    assert "etudecas/config/mrp_730384_fixed_20261002" not in engine_arguments
    assert "etudecas/config/mrp_reference_20261013/supplier_neutral_floors.csv" in engine_arguments


def test_promoted_reference_uses_confirmed_twenty_lot_capacity():
    graph = _graph(_config())
    marker = "user_confirmed_capacity_up_to_20_lots_per_week_2026-10-14"
    processes = {(node["id"], process["id"]): process["lot_execution"]
        for node in graph["nodes"] for process in node.get("processes", [])
        if "lot_execution" in process}
    expected = {
        ("M-1430", "proc:MAKE_268967"),
        ("M-1810", "proc:MAKE_268091"),
        ("SDC-1450", "proc:MAKE_773474"),
    }
    assert {pair for pair, row in processes.items() if row.get("max_lots_per_week") == 20} == expected
    assert all(processes[pair]["source"] == marker for pair in expected)
    assert not any(row.get("max_lots_per_week") == 10 for row in processes.values())
    adjustment = graph["meta"]["current_reference_capacity_adjustment"]
    assert adjustment["decision"] == "up_to_20_production_lots_per_week_if_needed"
    assert adjustment["industrial_source_files_modified"] is False
