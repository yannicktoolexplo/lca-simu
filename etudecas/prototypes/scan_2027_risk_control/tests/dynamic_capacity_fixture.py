"""Rebuild an analytical audit from retained inputs, in a temporary directory."""

import hashlib
import json
import shutil
from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_dynamic_capacity_coupling_audit as audit,
)


def build_capacity_inputs(root: Path) -> dict[str, Path]:
    retained = Path(__file__).parent / "fixtures" / "dynamic_capacity"
    root.mkdir(parents=True, exist_ok=True)
    for record in json.loads((retained / "provenance.json").read_text())["files"]:
        source = retained / record["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
        shutil.copyfile(source, root / record["file"])
    paths = {"graph_path": audit.DEFAULT_GRAPH,
             "old_profile_path": audit.DEFAULT_OLD_PROFILE,
             "new_profile_path": audit.DEFAULT_NEW_PROFILE}
    for key, source in paths.items():
        target = root / source.name
        shutil.copyfile(source, target)
        paths[key] = target
    paths["supplier_parameters_path"] = root / "supplier_nominal_parameters.csv"
    paths["current_floors_path"] = root / "prepared_physical_supplier_floors.csv"
    return paths


def build_capacity_audit(root: Path) -> tuple[dict[str, Path], Path]:
    paths = build_capacity_inputs(root)
    output = root / "audit"
    audit.build(**paths, output_dir=output)
    audit.validate(output)
    return paths, output
