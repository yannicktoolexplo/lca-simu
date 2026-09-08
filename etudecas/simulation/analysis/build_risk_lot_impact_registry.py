from __future__ import annotations

import argparse
import json
from pathlib import Path

from etudecas.simulation.lot_trace.risk_impact_registry import (
    build_risk_impact_registry_from_directory,
    write_risk_impact_registry,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a versioned incident -> shipment -> lot -> campaign -> client impact registry "
            "without modifying the source simulation run."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Simulation arm directory or its data/ directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New, empty output directory. Existing non-empty directories are rejected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = build_risk_impact_registry_from_directory(args.data_dir)
    written = write_risk_impact_registry(registry, args.output_dir)
    provenance = registry.quality.get("provenance", {})
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "files": {name: str(path.resolve()) for name, path in written.items()},
                "counts": registry.quality.get("counts", {}),
                "quantity_reconciliation": registry.quality.get(
                    "quantity_reconciliation", {}
                ),
                "provenance": {
                    "verification_status": provenance.get("verification_status"),
                    "identity": provenance.get("identity", {}),
                    "critical_hashes": provenance.get("critical_hashes", {}),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
