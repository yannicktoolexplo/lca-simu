"""Import ecoinvent 3.10 cutoff for the OPERA Brightway25 project.

Credentials are read from ECOINVENT_USERNAME and ECOINVENT_PASSWORD.
Keep this script file-based on Windows: Brightway's ecoinvent importer can use
multiprocessing, which is fragile when launched from stdin.
"""

from __future__ import annotations

import argparse
import os
import sys

import bw2data as bd
import bw2io as bi


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--version", default="3.10")
    parser.add_argument("--system-model", default="cutoff")
    parser.add_argument("--biosphere-name", default="biosphere3")
    parser.add_argument("--with-lcia", action="store_true")
    parser.add_argument("--use-mp", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = os.environ.get("ECOINVENT_USERNAME")
    password = os.environ.get("ECOINVENT_PASSWORD")
    if not username or not password:
        print(
            "Missing ECOINVENT_USERNAME/ECOINVENT_PASSWORD environment variables.",
            file=sys.stderr,
        )
        return 2

    bd.projects.set_current(args.project)
    db_name = f"ecoinvent-{args.version}-{args.system_model}"
    print(f"project={bd.projects.current}")
    print(f"before={sorted(list(bd.databases))}")

    if db_name in bd.databases:
        print(f"{db_name} already present; skipping LCI import")
        if args.with_lcia:
            prefix = f"ecoinvent-{args.version}"
            has_versioned_methods = any(method and method[0] == prefix for method in bd.methods)
            if has_versioned_methods:
                print(f"LCIA methods for {prefix} already present; skipping LCIA import")
            else:
                bi.import_ecoinvent_release(
                    version=args.version,
                    system_model=args.system_model,
                    username=username,
                    password=password,
                    lci=False,
                    lcia=True,
                    biosphere_name=args.biosphere_name,
                    biosphere_write_mode="patch",
                    use_mp=args.use_mp,
                )
    else:
        bi.import_ecoinvent_release(
            version=args.version,
            system_model=args.system_model,
            username=username,
            password=password,
            lci=True,
            lcia=args.with_lcia,
            biosphere_name=args.biosphere_name,
            biosphere_write_mode="patch",
            use_mp=args.use_mp,
        )

    print(f"after={sorted(list(bd.databases))}")
    print(f"methods_count={len(list(bd.methods))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
