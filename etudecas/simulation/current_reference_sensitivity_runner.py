"""Execute one sensitivity case through the retained current-reference adapters."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudecas.simulation import current_reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--current-reference-scan3-mode", required=True,
                        choices=current_reference.SCAN3_MODES)
    args, engine_args = parser.parse_known_args()
    if args.scenario_id != "scn:BASE":
        raise ValueError("The current-reference sensitivity adapter only supports scn:BASE")

    config, protocol, _, _, frozen_path, _ = current_reference.resolve_inputs()
    graph = current_reference.read(args.input)
    current_reference.validate_scan3_mode(args.current_reference_scan3_mode, args.days)
    if args.days > current_reference.FIRST:
        current_reference.validate_projection_contract(graph.get("meta", {}), args.days)
        if not graph.get("meta", {}).get("current_reference_other_use_profile"):
            raise ValueError("Prepared current-reference graph is missing its other-use projection")

    command = [
        "--input", args.input,
        "--output-dir", args.output_dir,
        "--scenario-id", args.scenario_id,
        "--days", str(args.days),
        *engine_args,
    ]
    current_reference.run_engine(
        graph=graph,
        protocol=protocol,
        config=config,
        frozen_path=frozen_path,
        command=command,
        output=Path(args.output_dir),
        days=args.days,
        scan3_mode=args.current_reference_scan3_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
