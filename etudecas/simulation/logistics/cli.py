"""CLI for auditable consolidation of lot shipment events."""

from __future__ import annotations

import argparse

from .consolidation import consolidate_shipments
from .io import load_lane_shipments, load_profiles_csv, write_consolidation_result
from .models import ConsolidationPolicy, TruckCapacity


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolidate simulated lane shipments into trucks."
    )
    parser.add_argument("--lot-events", required=True, help="production_lot_events.csv")
    parser.add_argument("--graph", required=True, help="Simulation graph JSON used by the run.")
    parser.add_argument("--profiles", default="", help="Optional sourced item logistics profile CSV.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bucket-days", type=int, default=7)
    parser.add_argument("--max-weight-kg", type=float, default=23_000.0)
    parser.add_argument("--max-pallets", type=float, default=33.0)
    parser.add_argument(
        "--max-volume-m3",
        type=float,
        default=0.0,
        help="Optional sourced volume capacity. Zero leaves volume unconstrained and audited as such.",
    )
    parser.add_argument(
        "--capacity-source",
        default="user_requirement_33_euro_pallets_23t",
        help="Source or decision reference for the configured truck capacities.",
    )
    parser.add_argument(
        "--no-mix-items",
        action="store_true",
        help="Prevent different items from sharing one consolidation group.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lines = load_lane_shipments(args.lot_events, args.graph)
    profiles = load_profiles_csv(args.profiles) if args.profiles else []
    result = consolidate_shipments(
        lines,
        profiles=profiles,
        capacity=TruckCapacity(
            max_weight_kg=args.max_weight_kg,
            max_pallets=args.max_pallets,
            max_volume_m3=args.max_volume_m3 or None,
            source_reference=args.capacity_source,
        ),
        policy=ConsolidationPolicy(
            bucket_days=args.bucket_days,
            mix_items=not args.no_mix_items,
        ),
    )
    paths = write_consolidation_result(args.output_dir, result)
    print(f"[OK] Input shipment lines: {result.audit['input_line_count']}")
    print(f"[OK] Dimensioned truck load proposals: {result.audit['truck_load_count']}")
    print(
        "[OK] Weekly fallback groups with unknown truck count: "
        f"{result.audit['fallback_group_count']}"
    )
    print(f"[OK] Audit: {paths['audit']}")
    return 0
