#!/usr/bin/env python3
"""Build temporal supplier-to-client propagation from paired experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from etudecas.simulation.uncertainty.temporal_propagation import (
    build_temporal_propagation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired-json", required=True)
    parser.add_argument("--graph-json", required=True)
    parser.add_argument("--lot-events-csv")
    parser.add_argument("--output-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paired = json.loads(Path(args.paired_json).read_text(encoding="utf-8"))
    graph = json.loads(Path(args.graph_json).read_text(encoding="utf-8"))
    payload = build_temporal_propagation(
        paired,
        graph,
        lot_events_csv=args.lot_events_csv,
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] Temporal propagation: {output.resolve()}")


if __name__ == "__main__":
    main()
