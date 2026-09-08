from __future__ import annotations

import hashlib
import base64
import csv
import gzip
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.lot_trace import build_lot_trace_payload


SOURCE_MAP = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\industrial_supply_preliminary_consolidated_20260904_v4\assets\carte_reseau_existante_hors_ligne.html")
SOURCE_RESULTS = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_30_autonome_20260907T195728Z\bilan_provisoire_op_100_30_sur_30.json")
NOMINAL_NODE_SOURCE = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_network_nominal_trajectory_replay_20260904_v1\maps\carte_run_nominal_actuel.html")
CAUSAL_LOT_SOURCE = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\integrated_risk_lot_maps_20260831_v5\delay_338929_incident_lots_map.html")
CAUSAL_REPLAY_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_all18_causal_lot_replays_20260908_v1")
OP100_GRAPH = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7\graphs\op100_source.json")
OUTPUT_DIR = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_real_geographic_map_20260908_v1")
OUTPUT_HTML = OUTPUT_DIR / "OUVRIR_VRAIE_CARTE_GEOGRAPHIQUE_OP_100_30_SUR_30.html"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


CHUNK_PATTERN = re.compile(
    r"(?P<a>const DATA_CHUNKED_GZIP_BASE64\s*=\s*)(?P<chunks>\{.*?\})"
    r"(?P<b>;\s*const DATA_CHUNKED_MANIFEST\s*=\s*)(?P<manifest>\{.*?\})(?P<c>;)"
    , re.DOTALL,
)


def _decode_chunks(document: str):
    match = CHUNK_PATTERN.search(document)
    if not match:
        raise RuntimeError("Données autonomes de la carte introuvables.")
    chunks = json.loads(match.group("chunks"))
    manifest = json.loads(match.group("manifest"))
    decoded = {
        key: json.loads(gzip.decompress(base64.b64decode("".join(parts))))
        for key, parts in chunks.items()
    }
    return match, chunks, manifest, decoded


def _decode_legacy_data(document: str) -> dict:
    match = re.search(
        r"const DATA_GZIP_BASE64_CHUNKS\s*=\s*(\[.*?\]);", document, re.DOTALL
    )
    if not match:
        raise RuntimeError("Données de la carte causale introuvables.")
    encoded = "".join(json.loads(match.group(1)))
    return json.loads(gzip.decompress(base64.b64decode(encoded)))


def _namespace_causal_ids(value):
    """Prevent incident lots/campaigns from overwriting nominal identifiers."""
    if isinstance(value, dict):
        return {_namespace_causal_ids(k): _namespace_causal_ids(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_namespace_causal_ids(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?<!INC338929::)(LOT-\d+)", r"INC338929::\1", value)
        value = re.sub(r"(?<!INC338929::)(LEVT-\d+)", r"INC338929::\1", value)
        value = re.sub(
            r"(?<!INC338929::)(CMP-\d+-[A-Za-z0-9:._-]+)",
            r"INC338929::\1",
            value,
        )
    return value


def _namespace_replay_ids(value, namespace: str):
    """Keep independent replay identifiers distinct inside one native lot viewer."""
    if isinstance(value, dict):
        return {
            _namespace_replay_ids(key, namespace): _namespace_replay_ids(item, namespace)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_namespace_replay_ids(item, namespace) for item in value]
    if isinstance(value, str):
        for prefix in ("LOT-", "LEVT-", "CMP-"):
            value = re.sub(
                rf"(?<!{re.escape(namespace)})(?={re.escape(prefix)})",
                namespace,
                value,
            )
    return value


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _existing(path: Path) -> Path | None:
    return path if path.is_file() else None


def _build_representative_replay_traces() -> list[dict]:
    """Build compact causal subgraphs for all 18 representative op_100 lanes."""
    manifest_path = CAUSAL_REPLAY_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = json.loads(OP100_GRAPH.read_text(encoding="utf-8"))
    scenarios = []
    for target in manifest.get("targets", []):
        output_dir = Path(target["output_dir"])
        data_dir = output_dir / "data"
        registry_dir = output_dir / "risk_lot_registry"
        entities = _read_csv_rows(registry_dir / "risk_impact_entities.csv")
        edges = _read_csv_rows(registry_dir / "risk_impact_edges.csv")
        finished_entities = {
            row["lot_id"]: row
            for row in entities
            if row.get("entity_type") == "finished_product_lot" and row.get("lot_id")
        }
        if not finished_entities:
            continue
        allowed_lot_ids = {
            row.get("lot_id", "") for row in entities if row.get("lot_id")
        }
        allowed_lot_ids.update(
            row.get(key, "")
            for row in edges
            for key in ("source_lot_id", "target_lot_id")
            if row.get(key)
        )
        trace = build_lot_trace_payload(
            data_dir / "production_lot_events.csv",
            data_dir / "production_lot_genealogy.csv",
            data_dir / "production_plan_events.csv",
            raw=raw,
            input_stocks_csv=_existing(data_dir / "production_input_stocks_daily.csv"),
            output_products_csv=_existing(data_dir / "production_output_products_daily.csv"),
            demand_service_csv=_existing(data_dir / "production_demand_service_daily.csv"),
            supplier_stocks_csv=_existing(data_dir / "production_supplier_stocks_daily.csv"),
            visible_finished_product_items=[f"item:{target['target_product_id']}"],
            production_campaigns_csv=data_dir / "production_campaigns.csv",
        )
        allowed_campaign_ids = {
            row.get("entity_id", "")
            for row in entities
            if row.get("entity_type") == "production_campaign" and row.get("entity_id")
        }
        allowed_campaign_ids.update(
            trace.get("lots", {}).get(lot_id, {}).get("production_campaign_id", "")
            for lot_id in finished_entities
        )
        allowed_campaign_ids.discard("")
        deferred_by_campaign = {
            row.get("campaign_id", ""): row for row in trace.get("deferred_orders", [])
        }
        measurement = target.get("measurement_30_of_30", {})
        item_id = str(target["item_id"])
        namespace = f"OP100_{item_id}_{target['seed']}::"
        causal_options = []
        visuals = {}
        for lot_id, entity in finished_entities.items():
            lot = trace.get("lots", {}).get(lot_id)
            if not lot:
                continue
            lot["scenario_kind"] = f"op100_transport_delay_{item_id}"
            lot["scenario_label"] = f"Retard +120 j sur le composant {item_id}"
            option = dict(lot)
            option["label"] = (
                f"[INCIDENT {item_id} — LOT AVAL EXPOSÉ] "
                + str(option.get("label") or lot_id)
            )
            causal_options.append(option)
            campaign_id = str(lot.get("production_campaign_id") or "")
            deferred = deferred_by_campaign.get(campaign_id, {})
            binding_items = {
                str(value).replace("item:", "")
                for value in deferred.get("blocking_input_item_ids", [])
            }
            direct_delay = item_id in binding_items
            exposed_low = float(entity.get("attributed_qty_lower") or 0.0)
            exposed_high = float(entity.get("attributed_qty_upper") or 0.0)
            service_loss = float(
                measurement.get("impact_service_loss_fed_product_pp") or 0.0
            )
            due_loss = float(
                measurement.get("impact_on_due_loss_fed_product_qty") or 0.0
            )
            created_day = int(float(lot.get("created_day") or entity.get("day") or 0))
            stressed_arrival_day = (
                measurement.get("target_latest_stressed_arrival_day")
                or measurement.get("target_arrival_day", "")
            )
            steps = [
                {"kind": "", "eyebrow": "FOURNISSEUR", "title": target["supplier_id"], "caption": "voie testée"},
                {"kind": "alert", "eyebrow": "EXPÉDITION", "title": "+120 jours", "caption": f"décision J{measurement.get('target_decision_day', '')}"},
                {"kind": "alert", "eyebrow": "COMPOSANT", "title": item_id, "caption": f"arrivée retardée J{stressed_arrival_day}"},
                {"kind": "good" if not direct_delay else "alert", "eyebrow": "LOT PRODUIT", "title": lot_id, "caption": f"créé J{created_day}"},
                {"kind": "", "eyebrow": "PRODUIT / CLIENT", "title": target["target_product_id"], "caption": "service aval mesuré"},
            ]
            if direct_delay:
                lot_effect = (
                    f"La campagne de ce lot a aussi enregistré {deferred.get('delay_days', 0)} jour(s) "
                    f"de blocage avec {item_id} comme composant manquant."
                )
            else:
                lot_effect = (
                    "La généalogie prouve que ce lot contient de la matière issue de l’expédition "
                    "touchée. Elle ne suffit pas, à elle seule, à dire que ce lot particulier a été retardé."
                )
            if service_loss <= 1e-9:
                service_effect = (
                    " Dans ce cas représentatif, les protections du réseau absorbent l’incident : "
                    "aucune unité à l’heure n’est perdue."
                )
            else:
                service_effect = (
                    " La comparaison avec la référence utilisant la même graine aléatoire mesure "
                    "la perte de service de toute la réalisation, pas de ce seul lot."
                )
            selection_note = str(target.get("selection_label") or "cas représentatif")
            format_integer = lambda value: f"{value:,.0f}".replace(",", " ")
            visuals[lot_id] = {
                "lot_id": lot_id,
                "short_lot_id": lot_id,
                "scenario_kind": "op100_incident_lineage",
                "badge": f"HYPOTHÈSE SIMULÉE · INCIDENT {item_id} · TRACE NATIVE",
                "headline": f"Comment l’incident {item_id} atteint-il le lot {lot_id} ?",
                "lead": f"Choix parmi 30 répétitions : {selection_note}.",
                "supplier_id": target["supplier_id"],
                "component_id": item_id,
                "factory_id": target["destination_id"],
                "product_id": target["target_product_id"],
                "steps": steps,
                "kpis": [
                    {"value": f"−{service_loss:.2f} pt".replace(".", ","), "label": "service perdu dans cette réalisation"},
                    {"value": format_integer(exposed_low) if abs(exposed_low - exposed_high) < 1e-9 else f"{format_integer(exposed_low)}–{format_integer(exposed_high)}", "label": "unités de ce lot reliées à l’incident"},
                    {"value": f"J{created_day}", "label": "création du lot produit"},
                    {"value": format_integer(due_loss), "label": "unités à l’heure perdues, scénario apparié"},
                ],
                "meaning": (
                    f"{lot_effect}{service_effect}"
                ),
                "proof": (
                    "Chaînage natif par identifiant d’expédition et généalogie physique ; "
                    "couverture de quantité contrôlée à 100 %."
                ),
            }
        causal_options.sort(key=lambda row: (row.get("created_day", 0), row.get("lot_id", "")))
        filtered = {
            **trace,
            "lots": {
                lot_id: lot for lot_id, lot in trace.get("lots", {}).items()
                if lot_id in allowed_lot_ids
            },
            "lot_options": causal_options,
            "events": [
                row for row in trace.get("events", [])
                if row.get("lot_id") in allowed_lot_ids
                or row.get("related_lot_id") in allowed_lot_ids
            ],
            "genealogy": [
                row for row in trace.get("genealogy", [])
                if row.get("parent_lot_id") in allowed_lot_ids
                and row.get("child_lot_id") in allowed_lot_ids
            ],
            "plan_events": [
                row for row in trace.get("plan_events", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "campaigns": [
                row for row in trace.get("campaigns", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "deferred_orders": [
                row for row in trace.get("deferred_orders", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "stock_context": {
                key: value for key, value in trace.get("stock_context", {}).items()
                if key in allowed_lot_ids
            },
        }
        filtered = _namespace_replay_ids(filtered, namespace)
        namespaced_visuals = {}
        for lot_id, visual in visuals.items():
            namespaced_id = namespace + lot_id
            namespaced_visuals[namespaced_id] = visual
            if namespaced_id in filtered["lots"]:
                filtered["lots"][namespaced_id]["causal_visual"] = visual
        scenarios.append({
            "trace": filtered,
            "visuals": namespaced_visuals,
            "scenario": {
                "scenario_id": f"op100_transport_delay_{item_id}_{target['seed']}",
                "label": f"Retard +120 j sur {item_id} — réalisation représentative",
                "supplier_id": target["supplier_id"],
                "destination_id": target["destination_id"],
                "target_product_id": target["target_product_id"],
                "causal_finished_lot_count": len(causal_options),
                "selection_label": target.get("selection_label", ""),
            },
        })
    return scenarios


def _merge_causal_lots(nominal_trace: dict) -> dict:
    causal_data = _decode_legacy_data(CAUSAL_LOT_SOURCE.read_text(encoding="utf-8"))
    causal = _namespace_causal_ids(causal_data["lot_trace"])
    deferred = causal.get("deferred_orders", [])
    impacted_ids = []
    order_by_lot = {}
    for order in deferred:
        impacted_ids.extend(order.get("completed_lot_ids", []))
        for lot_id in order.get("completed_lot_ids", []):
            order_by_lot[lot_id] = order
        if order.get("completed_lot_id"):
            impacted_ids.append(order["completed_lot_id"])
            order_by_lot[order["completed_lot_id"]] = order
    impacted_ids = list(dict.fromkeys(identifier for identifier in impacted_ids if identifier))
    incident_options = []
    for lot_id in impacted_ids:
        lot = causal.get("lots", {}).get(lot_id)
        if not lot:
            continue
        order = order_by_lot[lot_id]
        lot.update({
            "label": (
                "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
                + lot.get("label", lot_id)
            ),
            "scenario_kind": "incident_338929",
            "scenario_label": "Retard simulé du composant 338929",
            "pf_input_status": "completed_after_input_shortage",
            "pf_input_status_label": (
                f"Libéré après {order.get('delay_days', 0)} jour(s) de report — manque du composant 338929"
            ),
            "pf_availability_status": "completed_after_input_shortage",
            "pf_availability_status_label": (
                f"Production achevée à J{order.get('completed_day', '')} après blocage par 338929"
            ),
            "pf_blocking_input_item_ids": ["item:338929"],
            "pf_input_shortfall_qty": order.get("blocked_lot_qty", 0.0),
            "causal_delay_days": order.get("delay_days", 0),
            "causal_first_delay_day": order.get("first_delay_day", ""),
            "causal_completed_day": order.get("completed_day", ""),
        })
        option = dict(lot)
        option["label"] = (
            "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
            + option.get("label", lot_id).removeprefix(
                "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
            ).replace("INC338929::", "")
        )
        incident_options.append(option)
    incident_options.sort(key=lambda row: (row.get("created_day", 0), row.get("lot_id", "")))
    nominal_deferred_options = []
    nominal_deferred_ids = set()
    for order in nominal_trace.get("deferred_orders", []):
        blocking = list(order.get("blocking_input_item_ids", []))
        component = (blocking[0] if blocking else "item:inconnu").replace("item:", "")
        for lot_id in order.get("completed_lot_ids", []) or [order.get("completed_lot_id")]:
            lot = nominal_trace.get("lots", {}).get(lot_id)
            if not lot:
                continue
            nominal_deferred_ids.add(lot_id)
            lot.update({
                "scenario_kind": f"nominal_deferred_{component}",
                "scenario_label": f"Run nominal — report dû au composant {component}",
                "causal_delay_days": order.get("delay_days", 0),
                "causal_first_delay_day": order.get("first_delay_day", ""),
                "causal_completed_day": order.get("completed_day", ""),
            })
            source_option = next(
                (row for row in nominal_trace.get("lot_options", []) if row.get("lot_id") == lot_id),
                lot,
            )
            option = dict(source_option)
            option.update({
                "scenario_kind": f"nominal_deferred_{component}",
                "scenario_label": f"Run nominal — report dû au composant {component}",
                "label": f"[RUN NOMINAL — LOT PRODUIT APRÈS REPORT {component}] " + option.get("label", lot_id),
            })
            nominal_deferred_options.append(option)
    nominal_regular_options = [
        row for row in nominal_trace.get("lot_options", [])
        if row.get("lot_id") not in nominal_deferred_ids
    ]
    merged = dict(nominal_trace)
    merged["lots"] = {**nominal_trace.get("lots", {}), **causal.get("lots", {})}
    # Put the small, decision-relevant incident set first in the existing picker;
    # the nominal catalogue remains complete immediately afterwards.
    merged["lot_options"] = incident_options + nominal_deferred_options + nominal_regular_options
    for key in ("events", "genealogy", "plan_events", "campaigns", "deferred_orders"):
        merged[key] = list(nominal_trace.get(key, [])) + list(causal.get(key, []))
    nominal_stock_context = nominal_trace.get("stock_context", {})
    causal_stock_context = causal.get("stock_context", {})
    if isinstance(nominal_stock_context, dict) and isinstance(causal_stock_context, dict):
        merged["stock_context"] = {**nominal_stock_context, **causal_stock_context}
    else:
        merged["stock_context"] = list(nominal_stock_context or []) + list(causal_stock_context or [])
    merged["causal_scenarios"] = [{
        "scenario_id": "incident_338929",
        "label": "Retard simulé du composant 338929",
        "supplier_id": "SDC-VD0914360C",
        "destination_id": "M-1810",
        "target_product_id": "268091",
        "impacted_released_lot_count": len(incident_options),
        "deferred_order_count": len(deferred),
        "delay_event_count": sum(int(row.get("delay_event_count", 0)) for row in deferred),
    }]
    merged["summary"] = dict(nominal_trace.get("summary", {}))
    merged["summary"].update({
        "causal_scenario_count": 1,
        "causal_impacted_released_lot_count": len(incident_options),
        "causal_deferred_order_count": len(deferred),
    })
    replay_scenarios = _build_representative_replay_traces()
    replay_option_count = 0
    replay_lot_count = 0
    for replay in replay_scenarios:
        trace = replay["trace"]
        replay_options = list(trace.get("lot_options", []))
        replay_option_count += len(replay_options)
        replay_lot_count += len(trace.get("lots", {}))
        merged["lot_options"] = replay_options + list(merged.get("lot_options", []))
        merged["lots"].update(trace.get("lots", {}))
        for key in ("events", "genealogy", "plan_events", "campaigns", "deferred_orders"):
            merged[key] = list(merged.get(key, [])) + list(trace.get(key, []))
        existing_stock_context = merged.get("stock_context", [])
        replay_stock_context = trace.get("stock_context", [])
        if isinstance(existing_stock_context, dict) and isinstance(replay_stock_context, dict):
            existing_stock_context.update(replay_stock_context)
        elif isinstance(existing_stock_context, list) and isinstance(replay_stock_context, list):
            existing_stock_context.extend(replay_stock_context)
        elif replay_stock_context:
            # Preserve both schemas without silently dropping either source.
            merged["stock_context"] = {
                "nominal": existing_stock_context,
                "representative_replays": replay_stock_context,
            }
        merged["causal_scenarios"].append(replay["scenario"])
    merged["summary"].update({
        "causal_scenario_count": 1 + len(replay_scenarios),
        "op100_representative_causal_finished_lot_count": replay_option_count,
        "op100_representative_causal_subgraph_lot_count": replay_lot_count,
    })
    return merged


def _causal_lot_visual_payload(document: str) -> dict:
    _, _, _, decoded = _decode_chunks(document)
    trace = decoded["lot_trace"]
    lots = trace.get("lots", {})
    payload = {
        lot_id: dict(lot["causal_visual"])
        for lot_id, lot in lots.items()
        if isinstance(lot, dict) and isinstance(lot.get("causal_visual"), dict)
    }
    for order in trace.get("deferred_orders", []):
        is_incident = "INC338929::" in str(order.get("campaign_id", ""))
        blocking_items = list(order.get("blocking_input_item_ids", []))
        component_id = (
            str(blocking_items[0]).replace("item:", "") if blocking_items else "inconnu"
        )
        supplier_id = {
            "338929": "SDC-VD0914360C",
            "344135": "SDC-VD0993480A",
        }.get(component_id, "Fournisseur associé")
        for lot_id in order.get("completed_lot_ids", []) or [order.get("completed_lot_id")]:
            if not lot_id or lot_id not in lots:
                continue
            # A native risk-to-lot card carries stronger and more complete
            # causality than the generic deferred-order summary.
            if lot_id in payload:
                continue
            lot = lots[lot_id]
            payload[lot_id] = {
                "lot_id": lot_id,
                "short_lot_id": lot_id.replace("INC338929::", ""),
                "scenario_kind": "incident" if is_incident else "nominal",
                "badge": (
                    f"HYPOTHÈSE SIMULÉE · INCIDENT {component_id}"
                    if is_incident else f"SIMULÉ · REPORT DANS LE RUN NOMINAL · {component_id}"
                ),
                "supplier_id": supplier_id,
                "component_id": component_id,
                "factory_id": order.get("node_id", "M-1810"),
                "product_id": str(order.get("output_item_id", "item:268091")).replace("item:", ""),
                "first_delay_day": order.get("first_delay_day"),
                "last_delay_day": order.get("last_delay_day"),
                "completed_day": order.get("completed_day"),
                "delay_days": order.get("delay_days", 0),
                "blocked_qty": order.get("blocked_lot_qty", 0.0),
                "released_qty": order.get("actual_completion_qty", lot.get("qty", 0.0)),
                "upstream_lot_count": lot.get("upstream_lot_count", 0),
                "downstream_lot_count": lot.get("downstream_lot_count", 0),
                "downstream_node_count": lot.get("downstream_node_count", 0),
                "event_count": lot.get("event_count", 0),
                "meaning": (
                    f"L’incident imposé sur {component_id} a décalé la fabrication. Le lot a ensuite été terminé et libéré : il s’agit d’une indisponibilité temporaire, pas d’une perte définitive."
                    if is_incident else
                    f"Sans incident ajouté, le besoin en {component_id} a déjà retardé cette fabrication dans le run nominal. Ce signal révèle une fragilité interne de la configuration simulée."
                ),
            }
    return payload


def _with_original_node_curves(current_document: str) -> str:
    """Restore the audited nominal node panels removed by the compact delivery."""
    current_match, chunks, manifest, current = _decode_chunks(current_document)
    _, _, _, nominal = _decode_chunks(NOMINAL_NODE_SOURCE.read_text(encoding="utf-8"))
    replace_keys = (
        "timeline_horizon_days", "factory_hover_series", "factory_hover_images",
        "factory_current_metrics", "supplier_hover_images",
        "distribution_center_hover_images", "customer_hover_images",
        "customer_current_metrics", "global_kpi_tree", "lot_trace",
        "material_balance_rows", "supplier_local_metrics", "simulation_diagnostics",
    )
    for key in replace_keys:
        if key in nominal:
            current[key] = nominal[key]
    current["lot_trace"] = _merge_causal_lots(current["lot_trace"])
    # Restore the rich nominal figures on nodes/edges while preserving the newer
    # campaign-level state and uncertainty payloads from the consolidated map.
    old_model = nominal.get("model_panel", {})
    new_model = current.get("model_panel", {})
    for section in ("nodes", "edges"):
        merged = dict(new_model.get(section, {}))
        for identifier, assets in old_model.get(section, {}).items():
            merged[identifier] = {**merged.get(identifier, {}), **assets}
        new_model[section] = merged
    current["model_panel"] = new_model
    for key in replace_keys + ("model_panel",):
        raw = json.dumps(current[key], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        compressed = gzip.compress(raw, mtime=0)
        encoded = base64.b64encode(compressed).decode("ascii")
        chunks[key] = [encoded[i:i + 262144] for i in range(0, len(encoded), 262144)]
        manifest[key]["raw_bytes"] = len(raw)
        manifest[key]["compressed_bytes"] = len(compressed)
    replacement = (
        current_match.group("a") + json.dumps(chunks, separators=(",", ":"))
        + current_match.group("b") + json.dumps(manifest, separators=(",", ":"))
        + current_match.group("c")
    )
    return current_document[:current_match.start()] + replacement + current_document[current_match.end():]


def build() -> Path:
    source_hash = sha256(SOURCE_MAP)
    replay_manifest = json.loads(
        (CAUSAL_REPLAY_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    document = _with_original_node_curves(SOURCE_MAP.read_text(encoding="utf-8"))
    document = document.replace(
        "Les cascades actuelles et le suivi causal des lots ne sont pas encore intégrés à la carte ; utiliser aussi les trois vues du bilan.",
        "Les 18 voies fournisseurs ont été retracées : 12 atteignent des lots finis dans le cas représentatif et 6 n’en atteignent aucun avant la fin de l’horizon. Les lots trouvés sont intégrés au sélecteur existant.",
    )
    causal_visuals = _causal_lot_visual_payload(document)
    causal_visual_payload = json.dumps(
        causal_visuals, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    results = json.loads(SOURCE_RESULTS.read_text(encoding="utf-8"))
    rows = results["lane_statistics"]
    rows.sort(key=lambda r: (r["mechanism"], -float(r["service_loss_mean_pp"]), r["supplier_id"], r["item_id"]))
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css = r"""
<style id="op100RealMapStyle">
#op100Open{position:fixed;right:18px;bottom:18px;z-index:99990;border:0;border-radius:999px;background:#0b3b75;color:#fff;padding:13px 19px;font:700 14px system-ui;box-shadow:0 8px 28px #0f172a55;cursor:pointer}
#op100Panel{position:fixed;z-index:99991;right:14px;top:76px;bottom:14px;width:min(550px,calc(100vw - 28px));background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 55px #0f172a66;display:none;overflow:hidden;font:14px/1.38 system-ui;color:#0f2747}
#op100Panel.open{display:flex;flex-direction:column}.op100Head{padding:16px 18px;background:#0b3b75;color:white}.op100Head h2{font-size:19px;margin:2px 36px 4px 0}.op100Head p{margin:0;color:#dbeafe;font-size:12px}.op100Close{position:absolute;right:15px;top:13px;border:0;background:#ffffff22;color:white;border-radius:50%;width:32px;height:32px;font-size:21px;cursor:pointer}.op100Kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 12px}.op100Kpi{background:white;border:1px solid #dbe5f0;border-radius:10px;padding:8px}.op100Kpi strong{display:block;font-size:18px}.op100Kpi span{font-size:11px;color:#52657b}.op100Controls{display:flex;gap:8px;padding:0 12px 10px}.op100Controls select{flex:1;padding:8px;border:1px solid #b8c6d8;border-radius:8px;background:white}.op100Note{margin:0 12px 10px;padding:9px 10px;border-radius:9px;background:#fff7ed;border-left:4px solid #ea580c;font-size:12px}.op100Rows{overflow:auto;padding:0 12px 14px}.op100Row{background:white;border:1px solid #dbe5f0;border-radius:11px;padding:10px;margin-bottom:8px;cursor:pointer}.op100Row:hover,.op100Row.active{border-color:#2563eb;box-shadow:0 0 0 2px #dbeafe}.op100Title{display:flex;justify-content:space-between;gap:8px;font-weight:800}.op100Loss{color:#b42318}.op100Path{font-size:12px;color:#52657b;margin:3px 0 7px}.op100Metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;font-size:11px}.op100Metrics b{display:block;font-size:13px;color:#102a4c}.op100Zero{color:#64748b}.op100Detail{display:none;margin-top:9px;padding-top:8px;border-top:1px solid #e2e8f0;font-size:12px}.op100Row.active .op100Detail{display:block}@media(max-width:700px){#op100Panel{left:8px;right:8px;top:76px;bottom:8px;width:auto}}
.causalLotVisual{border:2px solid #fb923c;border-radius:14px;background:linear-gradient(135deg,#fff7ed,#fff);padding:14px;margin:0 0 14px;color:#172033;box-shadow:0 6px 18px #9a341222}.causalLotVisualHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.causalLotBadge{display:inline-block;border-radius:999px;background:#ffedd5;color:#9a3412;padding:4px 9px;font-size:10px;font-weight:900;letter-spacing:.04em}.causalLotVisual h3{font-size:17px;margin:6px 0 3px}.causalLotVisualLead{font-size:12px;color:#5b6472}.causalLotKpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:12px 0}.causalLotKpi{border:1px solid #fed7aa;border-radius:10px;background:#fff;padding:8px}.causalLotKpi strong{display:block;font-size:18px;color:#9a3412}.causalLotKpi span{font-size:10px;color:#657083}.causalLotFlow{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));align-items:stretch;gap:5px;margin:12px 0}.causalLotStep{grid-column:span 1;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:8px 5px;text-align:center;font-size:10px}.causalLotStep b{display:block;font-size:11px;margin:3px 0}.causalLotStep.alert{border-color:#ef4444;background:#fff1f2}.causalLotStep.good{border-color:#22c55e;background:#f0fdf4}.causalLotArrow{display:flex;align-items:center;justify-content:center;color:#ea580c;font-size:20px;font-weight:900}.causalLotMeaning{border-left:4px solid #2563eb;background:#eff6ff;border-radius:8px;padding:9px 10px;font-size:12px}.causalLotProof{font-size:10px;color:#657083;margin-top:8px}@media(max-width:850px){.causalLotKpis{grid-template-columns:repeat(2,1fr)}.causalLotFlow{display:flex;overflow:auto}.causalLotStep{min-width:135px}.causalLotArrow{min-width:20px}}
#lotTracePanel.causalVisualActive{z-index:60;width:min(1080px,calc(100vw - 32px));max-height:min(700px,calc(100vh - 280px))}
.op100LotBtn{margin-top:9px;border:0;border-radius:8px;background:#0f766e;color:#fff;padding:7px 10px;font-weight:800;cursor:pointer}.op100LotBtn:hover{background:#115e59}
.op100NoLot{margin-top:9px;border-radius:8px;background:#f1f5f9;border:1px solid #cbd5e1;color:#475569;padding:7px 9px;font-weight:700}
</style>"""
    body = r"""
<button id="op100Open" type="button">Résultats op_100 · 30/30</button>
<aside id="op100Panel" aria-label="Résultats simulés op 100">
 <div class="op100Head"><button class="op100Close" id="op100Close" aria-label="Fermer">×</button><h2>État simulé proche de 100 %</h2><p>Carte géographique réelle + résultats conditionnels de 30 répétitions</p></div>
 <div class="op100Kpis"><div class="op100Kpi"><strong>30/30</strong><span>répétitions</span></div><div class="op100Kpi"><strong>18</strong><span>voies physiques</span></div><div class="op100Kpi"><strong>1 080</strong><span>incidents appariés</span></div></div>
 <div class="op100Controls"><select id="op100Mechanism"><option value="transport_delay">Retard transport +120 jours</option><option value="planned_delivery_shortfall">Livraison réduite de 50 % pendant 42 jours</option></select><select id="op100Site"><option value="">Tous les sites</option><option>M-1810</option><option>M-1430</option></select></div>
 <p class="op100Note" id="op100Note"></p><div class="op100Rows" id="op100Rows"></div>
</aside>
<script id="op100RealMapScript">
const OP100_ROWS=__PAYLOAD__;
const CAUSAL_LOT_VISUALS=__CAUSAL_VISUAL_PAYLOAD__;
(()=>{const panel=document.getElementById('op100Panel'),box=document.getElementById('op100Rows'),mech=document.getElementById('op100Mechanism'),site=document.getElementById('op100Site'),note=document.getElementById('op100Note');
const nf=new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}),ff=v=>Number(v).toFixed(2).replace('.',',');
function render(){let rows=OP100_ROWS.filter(r=>r.mechanism===mech.value&&(!site.value||r.dst_node_id===site.value));rows.sort((a,b)=>b.service_loss_mean_pp-a.service_loss_mean_pp);note.textContent=mech.value==='transport_delay'?'Stress-test sévère : un retard de 120 jours est imposé. Les premières lignes indiquent où les protections actuelles cèdent le plus souvent.':'À cet état de fonctionnement, ce stress a bien touché les 18 voies mais les stocks et flux déjà engagés en absorbent l’effet sur le service. Cela ne signifie pas que les fournisseurs sont sans risque.';box.innerHTML=rows.map((r,i)=>{const item=String(r.item_id).replace('item:','');const hasLots=Object.values(CAUSAL_LOT_VISUALS).some(d=>d.scenario_kind==='op100_incident_lineage'&&d.supplier_id===r.supplier_id&&d.component_id===item);const lotAction=mech.value!=='transport_delay'?'':hasLots?`<br><button class="op100LotBtn" data-supplier="${r.supplier_id}" data-item="${item}">Voir les lots causalement exposés</button>`:'<div class="op100NoLot">Traçage réalisé : aucun lot produit aval atteint avant la fin de l’horizon dans le cas représentatif.</div>';return `<article class="op100Row" tabindex="0"><div class="op100Title"><span>${i+1}. ${r.supplier_id}</span><span class="${r.service_loss_mean_pp?'op100Loss':'op100Zero'}">−${ff(r.service_loss_mean_pp)} pt</span></div><div class="op100Path">Article ${item} → ${r.dst_node_id} → produit ${r.target_product_id}</div><div class="op100Metrics"><span><b>${r.positive_service_effect_count}/30</b>répétitions pénalisées</span><span><b>${ff(r.service_loss_p10_pp)}–${ff(r.service_loss_p90_pp)}</b>dispersion P10–P90</span><span><b>${nf.format(r.on_due_units_lost_mean)}</b>unités à l’heure perdues</span></div><div class="op100Detail"><b>Lecture métier.</b> Baisse médiane : ${ff(r.service_loss_median_pp)} point(s) ; maximum : ${ff(r.service_loss_max_pp)}. Production non libérée : ${nf.format(r.production_not_released_mean_qty)} unités en moyenne. Incident effectivement rencontré : ${r.physical_exercise_count}/30. Résultat simulé pour ce seul état, pas une notation historique du fournisseur.${lotAction}</div></article>`}).join('');box.querySelectorAll('.op100Row').forEach(el=>{const toggle=()=>{box.querySelectorAll('.op100Row').forEach(x=>x!==el&&x.classList.remove('active'));el.classList.toggle('active')};el.onclick=toggle;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle()}}});box.querySelectorAll('.op100LotBtn').forEach(btn=>btn.onclick=e=>{e.stopPropagation();openCausalLot(btn.dataset.supplier,btn.dataset.item)});}
document.getElementById('op100Open').onclick=()=>panel.classList.add('open');document.getElementById('op100Close').onclick=()=>panel.classList.remove('open');
const qty=v=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}).format(Number(v||0));
function causalCard(d){const k=d.kpis||[{value:`${d.delay_days} j`,label:'de report de production'},{value:qty(d.blocked_qty),label:'unités temporairement bloquées'},{value:`J${d.completed_day}`,label:'jour de libération du lot'},{value:qty(d.released_qty),label:'unités finalement libérées'}];const s=d.steps||[{kind:'',eyebrow:'FOURNISSEUR',title:d.supplier_id,caption:'flux amont'},{kind:'alert',eyebrow:'COMPOSANT',title:d.component_id,caption:'manquant'},{kind:'alert',eyebrow:'PRODUCTION',title:d.factory_id,caption:`report J${d.first_delay_day}–J${d.last_delay_day}`},{kind:'good',eyebrow:'LOT LIBÉRÉ',title:d.short_lot_id,caption:`à J${d.completed_day}`},{kind:'',eyebrow:'PRODUIT',title:d.product_id,caption:`${d.downstream_lot_count} lot(s) aval`}];const flow=s.map((x,i)=>`${i?'<div class="causalLotArrow">→</div>':''}<div class="causalLotStep ${x.kind||''}"><span>${x.eyebrow}</span><b>${x.title}</b><small>${x.caption}</small></div>`).join('');return `<section class="causalLotVisual"><div class="causalLotVisualHead"><div><span class="causalLotBadge">${d.badge}</span><h3>${d.headline||`Pourquoi le lot ${d.short_lot_id} a-t-il été retardé ?`}</h3><div class="causalLotVisualLead">${d.lead||'Lecture directe de la cause jusqu’à la remise à disposition du produit.'}</div></div></div><div class="causalLotKpis">${k.map(x=>`<div class="causalLotKpi"><strong>${x.value}</strong><span>${x.label}</span></div>`).join('')}</div><div class="causalLotFlow">${flow}</div><div class="causalLotMeaning"><b>Ce que cela signifie :</b> ${d.meaning}</div><div class="causalLotProof">${d.proof||`Preuve détaillée sous cette synthèse : ${d.upstream_lot_count} lots amont, ${d.downstream_lot_count} lots aval et événements de production associés.`}</div></section>`}
function selectedCausal(selectId){const el=document.getElementById(selectId);return el?CAUSAL_LOT_VISUALS[el.value]:null}
function cleanCausalNamespace(root){if(!root)return;const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode())node.nodeValue=node.nodeValue.replaceAll('INC338929::','').replace(/OP100_[A-Za-z0-9_]+::/g,'')}
function openCausalLot(supplier,item){const match=Object.entries(CAUSAL_LOT_VISUALS).find(([,d])=>d.supplier_id===supplier&&d.component_id===item&&d.scenario_kind==='op100_incident_lineage');if(!match)return;const select=document.getElementById('lotTraceSelect');if(select){select.value=match[0];select.dispatchEvent(new Event('change',{bubbles:true}))}panel.classList.remove('open');setTimeout(()=>document.getElementById('lotTraceFocusBtn')?.click(),40)}
function renderCausalVisuals(){const panelBody=document.getElementById('lotTracePanelBody'),lotPanel=document.getElementById('lotTracePanel'),panelData=selectedCausal('lotTraceSelect');lotPanel?.classList.toggle('causalVisualActive',!!panelData);if(panelData)document.getElementById('factoryHoverPanel')?.classList.remove('visible');if(panelBody&&!panelBody.querySelector('.causalLotVisual')&&panelData)panelBody.insertAdjacentHTML('afterbegin',causalCard(panelData));if(panelData){cleanCausalNamespace(document.getElementById('lotTracePanelTitle'));cleanCausalNamespace(panelBody);cleanCausalNamespace(document.getElementById('stats'))}const graph=document.getElementById('lotTraceGraphWrap');if(graph){document.getElementById('causalLotVisualModal')?.remove();const d=selectedCausal('lotTraceModalSelect');if(d){const holder=document.createElement('div');holder.id='causalLotVisualModal';holder.innerHTML=causalCard(d);graph.parentNode.insertBefore(holder,graph);setTimeout(()=>cleanCausalNamespace(document.getElementById('lotTraceModal')),0)}}}
const lotPanelBody=document.getElementById('lotTracePanelBody'),lotGraph=document.getElementById('lotTraceGraphWrap');if(lotPanelBody)new MutationObserver(()=>setTimeout(renderCausalVisuals,0)).observe(lotPanelBody,{childList:true});if(lotGraph)new MutationObserver(()=>setTimeout(renderCausalVisuals,0)).observe(lotGraph,{childList:true});['lotTraceSelect','lotTraceModalSelect'].forEach(id=>document.getElementById(id)?.addEventListener('change',()=>setTimeout(renderCausalVisuals,30)));['lotTraceFocusBtn','lotTraceOpenBtn'].forEach(id=>document.getElementById(id)?.addEventListener('click',()=>setTimeout(renderCausalVisuals,60)));
mech.onchange=render;site.onchange=render;render();})();
</script>""".replace("__PAYLOAD__", payload).replace("__CAUSAL_VISUAL_PAYLOAD__", causal_visual_payload)
    marker = "</body>"
    if marker not in document or "Plotly.newPlot" not in document:
        raise RuntimeError("La carte source n'a pas le contrat attendu.")
    enriched = document.replace(marker, css + body + "\n" + marker, 1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(enriched, encoding="utf-8")
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_real_geographic_map.v1",
        "entrypoint": OUTPUT_HTML.name,
        "fully_offline": True,
        "simulation_started": False,
        "source_map": str(SOURCE_MAP),
        "source_map_sha256": source_hash,
        "source_results": str(SOURCE_RESULTS),
        "source_results_sha256": sha256(SOURCE_RESULTS),
        "source_package_signature": "0231b89f05b07d739fafac72478926bfb23d6cfd2edf8f659b786cdaa8d1367a",
        "nominal_node_curve_source": str(NOMINAL_NODE_SOURCE),
        "nominal_node_curve_source_sha256": sha256(NOMINAL_NODE_SOURCE),
        "causal_lot_source": str(CAUSAL_LOT_SOURCE),
        "causal_lot_source_sha256": sha256(CAUSAL_LOT_SOURCE),
        "causal_lot_scope": "338929_detaille_plus_18_voies_op100_representatives_et_reports_nominaux",
        "causal_replay_root": str(CAUSAL_REPLAY_ROOT),
        "causal_replay_manifest_sha256": sha256(CAUSAL_REPLAY_ROOT / "manifest.json"),
        "representative_item_count": len({
            row.get("component_id") for row in causal_visuals.values()
            if row.get("scenario_kind") == "op100_incident_lineage"
        }),
        "representative_replayed_lane_count": int(replay_manifest.get("lane_count", 0)),
        "representative_lane_without_finished_lot_count": int(replay_manifest.get("lane_count", 0)) - len({
            row.get("component_id") for row in causal_visuals.values()
            if row.get("scenario_kind") == "op100_incident_lineage"
        }),
        "representative_causal_finished_lot_count": sum(
            row.get("scenario_kind") == "op100_incident_lineage"
            for row in causal_visuals.values()
        ),
        "causal_visual_card_count": len(causal_visuals),
        "lane_count": 18,
        "incident_case_count": 1080,
        "simulation_count": 30,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if sha256(SOURCE_MAP) != source_hash:
        raise RuntimeError("La carte source a été modifiée.")
    return OUTPUT_HTML


if __name__ == "__main__":
    print(build())
