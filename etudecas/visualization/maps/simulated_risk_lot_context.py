"""Keep a simulated-risk run's lot identities separate from the nominal run.

This is a read-only map adapter. Native incident attribution remains the job of
the risk-impact registry; a lineage exposure is never labelled a lost sale.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from etudecas.simulation.lot_trace import build_lot_trace_payload
from etudecas.simulation.lot_trace.risk_impact_registry import build_risk_impact_registry_from_directory


TRACE_FILES = {
    "events": "production_lot_events.csv",
    "genealogy": "production_lot_genealogy.csv",
    "plan_events": "production_plan_events.csv",
    "input_stocks": "production_input_stocks_daily.csv",
    "output_products": "production_output_products_daily.csv",
    "dc_stocks": "production_dc_stocks_daily.csv",
    "demand_service": "production_demand_service_daily.csv",
    "supplier_stocks": "production_supplier_stocks_daily.csv",
    "campaigns": "production_campaigns.csv",
    "mrp_orders": "mrp_orders_daily.csv",
    "state_events": "supplier_state_dependent_risk_events.csv",
    "shipments": "production_supplier_shipments_daily.csv",
}


def reference_only_display_payload(payload: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Redact display labels only, after all analytical builders have finished.

    Source graph, identifiers, numeric quantities and provenance are preserved.
    Copy-on-write preserves raw graph objects even when an analytical payload
    shares them. Unchanged numerical/trace arrays are not duplicated.
    """
    customers = {str(node.get("id") or "") for node in raw.get("nodes", []) or []
                 if node.get("type") == "customer"}
    client_items = {str(item) for edge in raw.get("edges", []) or []
                    if str(edge.get("to") or "") in customers for item in edge.get("items", []) or []}
    replacements = {}
    for item in raw.get("items", []) or []:
        identity = str(item.get("id") or "")
        reference = str(item.get("code") or identity).removeprefix("item:")
        name = str(item.get("name") or "").strip()
        if len(name) >= 3 and name.casefold() != reference.casefold():
            replacements[name] = reference
            prefix = name.split()[0]
            if identity in client_items and len(prefix) >= 3 and prefix.casefold() not in {
                "produit", "product", "finished", "article", "item",
            }:
                replacements[prefix] = reference
    if not replacements:
        return payload
    references = {name.casefold(): reference for name, reference in replacements.items()}
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in
                         sorted(replacements, key=len, reverse=True)) + r")(?!\w)", re.I)
    protected = {"id", "source_files", "source_hashes", "provenance", "critical_hashes",
                 "input_hashes", "path", "filename", "input_graph", "output_root", "output_dir",
                 "risk_event_ids", "event_ids", "causal_event_ids", "causal_root_ids"}
    display_fields = {"name", "label", "title", "text", "html", "description", "tooltip",
                      "item_name", "product_name", "display_name", "short_name", "notes"}
    def visit(value, display=False):
        if isinstance(value, dict):
            changed = None
            for key, child in value.items():
                if key in protected or key.endswith(("_id", "_ids", "_sha256")):
                    continue
                is_display = display or key in display_fields or key.endswith(("_label", "_labels", "_title", "_html"))
                updated = visit(child, is_display or key in {"data_panel", "json_panel"})
                if updated is not child:
                    if changed is None: changed = dict(value)
                    changed[key] = updated
            return changed if changed is not None else value
        elif isinstance(value, list):
            changed = None
            for index, child in enumerate(value):
                updated = visit(child, display)
                if updated is not child:
                    if changed is None: changed = list(value)
                    changed[index] = updated
            return changed if changed is not None else value
        elif display and isinstance(value, str):
            updated = pattern.sub(lambda match: references[match.group().casefold()], value)
            return value if updated == value else updated
        return value
    return visit(payload)


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _registry_payload(root: Path, data: Path) -> dict[str, Any]:
    # These are the two explicit output conventions used by campaign runners;
    # never discover an unrelated neighbour or a historical repository default.
    filenames = {
        "incidents": "risk_impact_incidents.csv",
        "bundles": "risk_impact_exposure_bundles.csv",
        "bundle_events": "risk_impact_bundle_events.csv",
        "client_service": "risk_impact_client_service.csv",
        "costs": "risk_impact_costs.csv",
    }
    for folder in (root / "risk_registry", root / "risk_impact_registry"):
        quality_path = folder / "risk_impact_quality.json"
        if not quality_path.is_file():
            continue
        quality = json.loads(quality_path.read_text(encoding="utf-8-sig"))
        recorded = quality.get("provenance", {}).get("source_files", {})
        if not recorded:
            # A registry without source provenance cannot identify this run.
            continue
        for record in recorded.values():
            source = Path(str(record.get("path") or ""))
            expected = record.get("sha256")
            if expected and source.resolve().parent != data.resolve():
                raise ValueError(f"Risk registry belongs to another run: {source}")
            if expected and (not source.is_file() or _sha(source) != expected):
                raise ValueError(f"Stale risk registry source: {source}")
        outputs = quality.get("registry_outputs", {}).get("csv_artifacts", {})
        tables = {}
        for key, filename in filenames.items():
            path = folder / filename
            expected = outputs.get(key, {}).get("sha256")
            if expected and _sha(path) != expected:
                raise ValueError(f"Risk registry output differs from its provenance: {path}")
            tables[key] = _csv(path)
        return {**tables, "quality": quality, "source": str(folder),
                "service_impact_claim": "exposure_only_not_counterfactual_service_loss"}
    registry = build_risk_impact_registry_from_directory(data)
    return {key: getattr(registry, key) for key in filenames} | {
        "quality": registry.quality, "source": "built_read_only_from_selected_run",
        "service_impact_claim": "exposure_only_not_counterfactual_service_loss",
    }


def build_simulated_risk_lot_context(
    raw: dict[str, Any],
    output_root: Path,
    *,
    nominal_output_root: Path | None = None,
    nominal_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    data = root / "data" if (root / "data").is_dir() else root
    files = {key: data / filename for key, filename in TRACE_FILES.items()}
    if not files["events"].is_file() or not files["genealogy"].is_file():
        return {"available": False, "run_key": "", "output_root": str(root),
                "reason": "selected_risk_run_has_no_native_lot_trace", "lot_trace": {"available": False}}
    manifest_path = root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.is_file() else {}
    before = {key: {"path": str(path), "sha256": _sha(path)}
              for key, path in files.items() if path.is_file()}
    if manifest_path.is_file():
        before["run_manifest"] = {"path": str(manifest_path), "sha256": _sha(manifest_path)}
    graph_path = None
    if manifest.get("input_graph"):
        candidate = Path(str(manifest["input_graph"]))
        for path in (candidate, root / candidate):
            if path.is_file():
                graph_path = path.resolve()
                before["input_graph"] = {"path": str(graph_path), "sha256": _sha(graph_path)}
                break
    identity = json.dumps({"output_root": str(root), "sources": before}, sort_keys=True)
    run_key = "risk:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    scenario_id = str(manifest.get("scenario_id") or "")
    same_run = nominal_output_root is not None and root == Path(nominal_output_root).resolve()
    if same_run and nominal_trace is not None:
        trace = nominal_trace
    else:
        run_graph = raw
        if graph_path is not None:
            if graph_path.suffix == ".gz":
                with gzip.open(graph_path, "rt", encoding="utf-8-sig") as stream:
                    run_graph = json.load(stream)
            else:
                run_graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
        trace = build_lot_trace_payload(
            files["events"], files["genealogy"], files["plan_events"], run_graph,
            files["input_stocks"], files["output_products"], files["dc_stocks"],
            files["demand_service"], files["supplier_stocks"],
            production_campaigns_csv=files["campaigns"], mrp_orders_csv=files["mrp_orders"],
            include_causal_links=False,
        )
    registry = _registry_payload(root, data)
    for record in before.values():
        if _sha(Path(record["path"])) != record["sha256"]:
            raise ValueError("Risk-run sources changed while the map payload was built")
    return {"available": bool(trace.get("available")), "run_key": run_key,
            "scenario_id": scenario_id, "label": "Calcul des risques simulés",
            "output_root": str(root), "source_files": before, "lot_trace": trace,
            "registry": registry, "identity_scope": "run_local_lot_and_shipment_ids",
            "service_impact_claim": "exposure_only_not_counterfactual_service_loss"}
