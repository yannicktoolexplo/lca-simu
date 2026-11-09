"""Run-local map identities; no simulation, browser or file-tampering tests."""
import csv
import json
from pathlib import Path

from etudecas.visualization.maps import simulated_risk_lot_context as context


def _run(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    data = root / "data"
    data.mkdir(parents=True)
    with (data / "production_lot_events.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["lot_id", "risk_event_ids", "item_id"])
        writer.writeheader()
        writer.writerow({"lot_id": "LOT-00000001", "risk_event_ids": "E1" if name == "risk" else "",
                         "item_id": name})
    (data / "production_lot_genealogy.csv").write_text("parent_lot_id,child_lot_id\n", encoding="utf-8")
    (root / "run_manifest.json").write_text(json.dumps({"scenario_id": "scn:" + name}), encoding="utf-8")
    return root


def _trace(events: Path, *args, **kwargs):
    with events.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {"available": True, "events": rows,
            "lots": {row["lot_id"]: row for row in rows},
            "lot_options": [{"lot_id": row["lot_id"]} for row in rows]}


def test_same_lot_id_in_two_runs_does_not_join_nominal_to_risk(tmp_path, monkeypatch):
    nominal = _run(tmp_path, "nominal")
    risk = _run(tmp_path, "risk")
    monkeypatch.setattr(context, "build_lot_trace_payload", _trace)
    monkeypatch.setattr(context, "_registry_payload", lambda root, data: {"source": str(root)})
    nominal_trace = _trace(nominal / "data/production_lot_events.csv")
    result = context.build_simulated_risk_lot_context({}, risk,
                nominal_output_root=nominal, nominal_trace=nominal_trace)
    lot = result["lot_trace"]["lots"]["LOT-00000001"]
    assert lot["risk_event_ids"] == "E1"
    assert lot["item_id"] == "risk"
    assert nominal_trace["lots"]["LOT-00000001"]["risk_event_ids"] == ""
    assert result["output_root"] == str(risk.resolve())
    assert result["scenario_id"] == "scn:risk"
    assert result["service_impact_claim"] == "exposure_only_not_counterfactual_service_loss"
    other = context.build_simulated_risk_lot_context({}, nominal)
    assert result["run_key"] != other["run_key"]


def test_missing_risk_trace_does_not_fall_back_to_nominal(tmp_path):
    result = context.build_simulated_risk_lot_context({}, tmp_path / "absent",
                nominal_output_root=tmp_path / "nominal", nominal_trace={"available": True})
    assert result["available"] is False
    assert result["lot_trace"]["available"] is False
    assert result["run_key"] == ""


def test_same_run_reuses_nominal_payload_without_cross_run_copy(tmp_path, monkeypatch):
    root = _run(tmp_path, "nominal")
    trace = {"available": True, "lots": {"LOT-00000001": {"item_id": "nominal"}}}
    monkeypatch.setattr(context, "_registry_payload", lambda root, data: {})
    result = context.build_simulated_risk_lot_context({}, root,
                nominal_output_root=root, nominal_trace=trace)
    assert result["lot_trace"] is trace
    assert result["source_files"]["events"]["sha256"]


def test_display_graph_uses_references_without_mutating_source_names():
    source = {"items": [{"id": "item:268091", "code": "268091", "name": "PrivateBrand 10mg",
                         "uom_default": "UN"}],
              "nodes": [{"id": "C-1", "type": "customer"}],
              "edges": [{"to": "C-1", "items": ["item:268091"]}],
              "meta": {"source_file": "source.xlsx"}}
    displayed = {"item_label": "PrivateBrand 10mg", "title": "Stock PrivateBrand",
                 "item_id": "item:268091", "quantity": 125,
                 "items": source["items"],
                 "source_files": {"path": "PrivateBrand.csv", "sha256": "original"},
                 "json_panel": {"rows": [["PrivateBrand 10mg", "UN"]]}}
    displayed = context.reference_only_display_payload(displayed, source)
    assert displayed["item_label"] == "268091"
    assert displayed["title"] == "Stock 268091"
    assert displayed["json_panel"]["rows"][0] == ["268091", "UN"]
    assert displayed["source_files"] == {"path": "PrivateBrand.csv", "sha256": "original"}
    assert displayed["item_id"] == "item:268091" and displayed["quantity"] == 125
    assert source["items"][0]["name"] == "PrivateBrand 10mg"
    assert displayed["items"][0]["name"] == "268091"
