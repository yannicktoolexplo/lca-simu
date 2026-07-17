"""Import and process the OPERA aircraft-seat Brightway package."""

from __future__ import annotations

import argparse
from pathlib import Path

import bw2data as bd
from bw2io import BW2Package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--package", default="bw_tristan/OPERA_siege.bw2package")
    parser.add_argument("--database", default="OPERA_siege")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_path = Path(args.package)
    if not package_path.exists():
        raise FileNotFoundError(package_path)

    bd.projects.set_current(args.project)
    print(f"project={bd.projects.current}")
    print(f"before={sorted(list(bd.databases))}")

    if args.database not in bd.databases:
        BW2Package.import_file(str(package_path))
        print(f"imported={args.database}")
    else:
        print(f"{args.database} already present; skipping package import")

    bd.Database(args.database).process()
    print(f"processed={args.database}")
    print(f"after={sorted(list(bd.databases))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
