"""Command-line helpers for generic simulation run packages."""

from __future__ import annotations

import argparse
from pathlib import Path

from etudecas.simulation.run_format.exporter import export_run_package
from etudecas.simulation.run_format.validator import validate_run_package


def _print_validations(validations: list[dict]) -> None:
    for row in validations:
        status = "OK" if row.get("ok") else "FAIL"
        print(f"[{status}] {row.get('name')} - {row.get('detail', '')}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and validate generic etudecas simulation run packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Export a generic package from an existing simulation result directory.")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--input-graph", default="")
    export.add_argument("--package-dir", default="")
    export.add_argument("--map-html", default="")

    validate = sub.add_parser("validate", help="Validate an existing generic run package.")
    validate.add_argument("--package-dir", required=True)

    args = parser.parse_args()
    if args.command == "export":
        package_dir = export_run_package(
            output_dir=Path(args.output_dir),
            input_graph=Path(args.input_graph) if args.input_graph else None,
            package_dir=Path(args.package_dir) if args.package_dir else None,
            map_html=Path(args.map_html) if args.map_html else None,
        )
        print(f"[OK] Generic run package: {package_dir.resolve()}", flush=True)
        _print_validations(validate_run_package(package_dir))
        return
    if args.command == "validate":
        validations = validate_run_package(Path(args.package_dir))
        _print_validations(validations)
        if any(not row.get("ok") for row in validations):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
