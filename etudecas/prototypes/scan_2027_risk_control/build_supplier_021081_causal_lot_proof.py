#!/usr/bin/env python3
"""Build a paired causal lot proof from completed 021081 campaign cases.

The traversal starts only from opening-purchase receipt lots identified by a
technical ERP ``source_row`` and a simulated ``risk_event_ids`` value.  It then
follows native parent-to-child lot genealogy.  A descendant is labelled
"exposed" as a full-lot upper bound; it is labelled a causal effect only when
its paired aggregate date or quantity differs from the same-seed baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as base,
)


CHAIN_ITEMS = {base.ITEM_ID, base.INTERMEDIATE_ITEM_ID, base.TARGET_PRODUCT_ID}


def validated_source_campaign(campaign_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Require a complete source campaign with a positive execution audit."""

    manifest_path = campaign_root / "campaign_manifest.json"
    audit_path = campaign_root / "execution_provenance_audit.json"
    manifest = base.read_json(manifest_path)
    audit = base.read_json(audit_path)
    if str(manifest.get("status") or "") != "complete":
        raise ValueError("Causal proof requires a complete source campaign")
    if not bool(audit.get("reproducibility_wording_allowed")):
        raise ValueError("Causal proof requires audited source execution provenance")
    return manifest, audit


def _proof_rows(case_dir: Path, filename: str) -> list[dict[str, str]]:
    path = case_dir / "proofs" / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return base.read_csv_rows(path)


def receipt_events(case_dir: Path) -> list[dict[str, str]]:
    return [
        row
        for row in _proof_rows(
            case_dir, "lot_events_021081_773474_268967.csv"
        )
        if str(row.get("event_type") or "")
        == "opening_purchase_order_receipt"
        and str(row.get("item_id") or "") == base.ITEM_ID
    ]


def trace_from_receipt(
    receipt: Mapping[str, Any] | None,
    genealogy: Sequence[Mapping[str, Any]],
    *,
    source_row: str,
) -> list[dict[str, Any]]:
    if receipt is None or not str(receipt.get("lot_id") or ""):
        return []
    adjacency: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for link in genealogy:
        parent = str(link.get("parent_lot_id") or "")
        if parent:
            adjacency[parent].append(link)
    queue: deque[tuple[str, int]] = deque(
        [(str(receipt.get("lot_id") or ""), 0)]
    )
    visited_lots: set[str] = {str(receipt.get("lot_id") or "")}
    visited_links: set[tuple[str, str, str, str]] = set()
    output: list[dict[str, Any]] = []
    while queue:
        parent_lot, depth = queue.popleft()
        for link in adjacency.get(parent_lot, []):
            key = (
                str(link.get("day") or ""),
                str(link.get("link_type") or ""),
                str(link.get("parent_lot_id") or ""),
                str(link.get("child_lot_id") or ""),
            )
            if key in visited_links:
                continue
            visited_links.add(key)
            child_lot = str(link.get("child_lot_id") or "")
            child_item = str(link.get("child_item_id") or "")
            record = {
                "origin_source_row": source_row,
                "origin_receipt_lot_id": str(receipt.get("lot_id") or ""),
                "depth": depth + 1,
                "exposure_semantics": (
                    "full_descendant_lot_quantity_upper_bound_not_attributed_consumption"
                ),
                **dict(link),
                "is_chain_item": child_item in CHAIN_ITEMS,
                "is_intermediate_descendant": child_item
                == base.INTERMEDIATE_ITEM_ID,
                "is_finished_product_descendant": child_item
                == base.TARGET_PRODUCT_ID,
                "is_customer_delivery": (
                    child_item == base.TARGET_PRODUCT_ID
                    and str(link.get("child_node_id") or "")
                    == base.TARGET_CLIENT_ID
                ),
            }
            output.append(record)
            if child_lot and child_lot not in visited_lots:
                visited_lots.add(child_lot)
                queue.append((child_lot, depth + 1))
    return output


def aggregate_trace(
    receipt: Mapping[str, Any] | None,
    descendants: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    intermediate_lots = {
        str(row.get("child_lot_id") or ""): base.to_float(
            row.get("child_qty")
        )
        for row in descendants
        if bool(row.get("is_intermediate_descendant"))
        and str(row.get("link_type") or "") == "production"
    }
    finished_lots = {
        str(row.get("child_lot_id") or ""): base.to_float(
            row.get("child_qty")
        )
        for row in descendants
        if bool(row.get("is_finished_product_descendant"))
        and str(row.get("link_type") or "") == "production"
    }
    deliveries = [row for row in descendants if bool(row.get("is_customer_delivery"))]
    days = [base.to_int(row.get("day"), -1) for row in descendants]
    days = [day for day in days if day >= 0]
    return {
        "receipt_present_in_horizon": receipt is not None,
        "receipt_lot_id": str(receipt.get("lot_id") or "") if receipt else "",
        "receipt_usable_day": base.to_int(receipt.get("day"), -1)
        if receipt
        else -1,
        "receipt_qty_kg": base.to_float(receipt.get("qty")) if receipt else 0.0,
        "descendant_link_count": len(descendants),
        "first_descendant_day": min(days) if days else "",
        "last_descendant_day": max(days) if days else "",
        "intermediate_descendant_lot_count": len(intermediate_lots),
        "intermediate_exposed_full_lot_upper_bound_qty_g": sum(
            intermediate_lots.values()
        ),
        "finished_descendant_lot_count": len(finished_lots),
        "finished_exposed_full_lot_upper_bound_qty": sum(
            finished_lots.values()
        ),
        "customer_delivery_link_count": len(deliveries),
        "customer_delivery_qty": sum(
            base.to_float(row.get("child_qty")) for row in deliveries
        ),
        "consumption_status": (
            "receipt_has_native_descendants_in_horizon"
            if descendants
            else "receipt_not_consumed_in_test_horizon"
        ),
    }


def build_proof(
    *,
    campaign_root: Path,
    state_regime: str,
    scenario_id: str,
    seed: int,
    output_dir: Path,
) -> dict[str, Any]:
    campaign_root = campaign_root.resolve()
    source_manifest, source_execution_audit = validated_source_campaign(
        campaign_root
    )
    stress_dir = (
        campaign_root / "cases" / state_regime / scenario_id / f"seed_{seed}"
    )
    baseline_dir = (
        campaign_root
        / "cases"
        / state_regime
        / "baseline_observed_order_book"
        / f"seed_{seed}"
    )
    stress_audit = _proof_rows(
        stress_dir, "opening_purchase_order_supplier_risk_audit_021081.csv"
    )
    affected = [
        row
        for row in stress_audit
        if str(row.get("risk_event_ids") or "").strip()
    ]
    if not affected:
        raise ValueError("Selected stress case has no risk-affected opening PO rows")
    baseline_receipts = {
        str(row.get("source_row") or ""): row
        for row in receipt_events(baseline_dir)
    }
    stress_receipts = {
        str(row.get("source_row") or ""): row for row in receipt_events(stress_dir)
    }
    baseline_genealogy = _proof_rows(
        baseline_dir, "lot_genealogy_021081_773474_268967.csv"
    )
    stress_genealogy = _proof_rows(
        stress_dir, "lot_genealogy_021081_773474_268967.csv"
    )
    comparison: list[dict[str, Any]] = []
    baseline_descendant_rows: list[dict[str, Any]] = []
    stress_descendant_rows: list[dict[str, Any]] = []
    for audit_row in sorted(affected, key=lambda row: base.to_int(row.get("source_row"))):
        source_row = str(audit_row.get("source_row") or "")
        baseline_receipt = baseline_receipts.get(source_row)
        stress_receipt = stress_receipts.get(source_row)
        baseline_descendants = trace_from_receipt(
            baseline_receipt, baseline_genealogy, source_row=source_row
        )
        stress_descendants = trace_from_receipt(
            stress_receipt, stress_genealogy, source_row=source_row
        )
        baseline_descendant_rows.extend(baseline_descendants)
        stress_descendant_rows.extend(stress_descendants)
        baseline_agg = aggregate_trace(baseline_receipt, baseline_descendants)
        stress_agg = aggregate_trace(stress_receipt, stress_descendants)
        receipt_causal_fields = (
            "receipt_usable_day",
            "receipt_qty_kg",
        )
        descendant_causal_fields = (
            "intermediate_descendant_lot_count",
            "intermediate_exposed_full_lot_upper_bound_qty_g",
            "finished_descendant_lot_count",
            "finished_exposed_full_lot_upper_bound_qty",
            "customer_delivery_link_count",
            "customer_delivery_qty",
            "first_descendant_day",
            "last_descendant_day",
        )
        receipt_changed = [
            field
            for field in receipt_causal_fields
            if str(stress_agg.get(field, "")) != str(baseline_agg.get(field, ""))
        ]
        descendant_changed = [
            field
            for field in descendant_causal_fields
            if str(stress_agg.get(field, "")) != str(baseline_agg.get(field, ""))
        ]
        changed = [*receipt_changed, *descendant_changed]
        comparison.append(
            {
                "source_row": source_row,
                "source_row_semantics": (
                    "technical_erp_snapshot_line_not_industrial_lot_or_order_id"
                ),
                "shipment_id": str(audit_row.get("shipment_id") or ""),
                "supplier_id": str(audit_row.get("supplier_id") or ""),
                "risk_event_ids": str(audit_row.get("risk_event_ids") or ""),
                "risk_types": str(audit_row.get("risk_types") or ""),
                "planned_usable_day_before": base.to_int(
                    audit_row.get("usable_day_before"), -1
                ),
                "simulated_usable_day_after": base.to_int(
                    audit_row.get("usable_day_after"), -1
                ),
                **{f"baseline_{key}": value for key, value in baseline_agg.items()},
                **{f"stress_{key}": value for key, value in stress_agg.items()},
                "changed_paired_fields": ";".join(changed),
                "changed_receipt_fields": ";".join(receipt_changed),
                "changed_descendant_fields": ";".join(descendant_changed),
                "causal_effect_on_receipt": bool(receipt_changed),
                "causal_effect_on_descendants": bool(descendant_changed),
                "causal_effect_in_simulation": bool(changed),
                "lot_exposure_interpretation": (
                    "descendant full-lot quantities are upper bounds; causal effect "
                    "requires a paired date or quantity difference"
                ),
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    base.write_csv(output_dir / "receipt_paired_causal_comparison.csv", comparison)
    base.write_csv(
        output_dir / "baseline_native_descendant_links.csv",
        baseline_descendant_rows,
    )
    base.write_csv(
        output_dir / "stress_native_descendant_links.csv", stress_descendant_rows
    )
    summary = {
        "schema_version": "supplier-021081-causal-lot-proof.v2",
        "campaign_root": str(campaign_root),
        "state_regime": state_regime,
        "scenario_id": scenario_id,
        "seed": seed,
        "paired_baseline": "baseline_observed_order_book",
        "affected_opening_po_technical_row_count": len(affected),
        "technical_rows_with_any_descendant": sum(
            base.to_int(row.get("stress_descendant_link_count")) > 0
            for row in comparison
        ),
        "technical_rows_with_paired_causal_effect": sum(
            bool(row.get("causal_effect_in_simulation")) for row in comparison
        ),
        "technical_rows_with_paired_receipt_effect": sum(
            bool(row.get("causal_effect_on_receipt")) for row in comparison
        ),
        "technical_rows_with_paired_descendant_effect": sum(
            bool(row.get("causal_effect_on_descendants")) for row in comparison
        ),
        "baseline_descendant_link_count": len(baseline_descendant_rows),
        "stress_descendant_link_count": len(stress_descendant_rows),
        "interpretation": (
            "source_row is a technical ERP snapshot line, not an observed industrial "
            "lot or order identifier. Exposed lot quantities are full-lot upper "
            "bounds. A causal effect is reported only for paired date/quantity changes."
        ),
        "no_descendant_wording": (
            "receipt not consumed in the tested horizon"
        ),
        "source_campaign_manifest_sha256": base.sha256_file(
            campaign_root / "campaign_manifest.json"
        ),
        "source_execution_provenance_audit_sha256": base.sha256_file(
            campaign_root / "execution_provenance_audit.json"
        ),
        "source_execution_provenance_reproducible": bool(
            source_execution_audit.get("reproducibility_wording_allowed")
        ),
    }
    base.write_json(output_dir / "causal_lot_proof_summary.json", summary)
    input_paths = {
        "baseline_receipt_events": baseline_dir
        / "proofs"
        / "lot_events_021081_773474_268967.csv",
        "baseline_genealogy": baseline_dir
        / "proofs"
        / "lot_genealogy_021081_773474_268967.csv",
        "stress_opening_order_risk_audit": stress_dir
        / "proofs"
        / "opening_purchase_order_supplier_risk_audit_021081.csv",
        "stress_receipt_events": stress_dir
        / "proofs"
        / "lot_events_021081_773474_268967.csv",
        "stress_genealogy": stress_dir
        / "proofs"
        / "lot_genealogy_021081_773474_268967.csv",
    }
    outputs = {
        "receipt_paired_causal_comparison.csv": base.sha256_file(
            output_dir / "receipt_paired_causal_comparison.csv"
        ),
        "baseline_native_descendant_links.csv": base.sha256_file(
            output_dir / "baseline_native_descendant_links.csv"
        ),
        "stress_native_descendant_links.csv": base.sha256_file(
            output_dir / "stress_native_descendant_links.csv"
        ),
        "causal_lot_proof_summary.json": base.sha256_file(
            output_dir / "causal_lot_proof_summary.json"
        ),
    }
    proof_manifest = {
        "schema_version": "supplier-021081-causal-lot-proof-manifest.v2",
        "status": "complete",
        "proof_builder": str(Path(__file__).resolve()),
        "proof_builder_sha256": base.sha256_file(Path(__file__).resolve()),
        "source_campaign": str(campaign_root),
        "source_campaign_schema_version": source_manifest.get("schema_version"),
        "source_campaign_manifest_sha256": summary[
            "source_campaign_manifest_sha256"
        ],
        "source_execution_provenance_audit_sha256": summary[
            "source_execution_provenance_audit_sha256"
        ],
        "source_execution_provenance_reproducible": True,
        "state_regime": state_regime,
        "scenario_id": scenario_id,
        "seed": seed,
        "input_sha256": {
            name: base.sha256_file(path) for name, path in input_paths.items()
        },
        "output_sha256": outputs,
        "scientific_scope": {
            "source_row": (
                "technical source-line identifier, not an industrial lot or order"
            ),
            "exposure": "full descendant lot quantity is an upper bound",
            "causality": (
                "paired receipt and descendant changes are reported separately"
            ),
        },
    }
    base.write_json(output_dir / "causal_proof_manifest.json", proof_manifest)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root")
    parser.add_argument("--state-regime", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_proof(
        campaign_root=Path(args.campaign_root),
        state_regime=args.state_regime,
        scenario_id=args.scenario_id,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )
    print(f"[OK] causal lot proof: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
