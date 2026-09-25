"""Explicit source revision for newly planned campaigns, never historical receipts.

Historical SHA constants remain in their original adapters.  The adjacent ledger
authorizes one reviewed replacement graph and binds every shared dependency.
Changing a file requires a new reviewed ledger and therefore a new campaign
signature; this module never updates either a ledger or an existing receipt.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "supplier_campaign_source_revision.json"

# Explicit migration of entry points; historical identifiers remain in receipts.
ADAPTER_MODULE = "etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters"
ADAPTER_PROFILES = {
    f"{mode}_supplier_operating_point_full_campaign_v{version}": (mode, f"v{version}")
    for mode, versions in (("launch", (5, 6, 7, 8)), ("finalize", (5, 6, 7)))
    for version in versions
}


def module_argv(module: str) -> list[str]:
    """Translate only the seven retired local entry points to explicit profiles."""
    name = module.rsplit(".", 1)[-1]
    if module == f"etudecas.prototypes.scan_2027_risk_control.{name}" and name in ADAPTER_PROFILES:
        return [ADAPTER_MODULE, *ADAPTER_PROFILES[name]]
    return [module]


def resolve_current_source(path: Path) -> Path:
    """Locate the reviewed implementation of a retired local adapter identity."""
    path = path.resolve()
    if path.parent == ROOT and path.stem in ADAPTER_PROFILES:
        return ROOT / "supplier_campaign_adapters.py"
    return path


def current_revision() -> dict[str, Any]:
    """Read and verify the entire reviewed source graph, without cached hashes."""
    raw = LEDGER.read_bytes()
    ledger = json.loads(raw)
    if ledger.get("schema") != "supplier-campaign-source-revision.v1":
        raise ValueError("Unknown campaign source revision schema")
    files = ledger.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Campaign source revision has no files")

    def verify_source(item: tuple[str, Any]) -> None:
        name, record = item
        if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise ValueError("Invalid campaign source revision path")
        path = ROOT / name
        if path.resolve().parent != ROOT or not path.is_file():
            raise ValueError(f"Campaign source revision file missing: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256"):
            raise ValueError(f"Campaign source revision changed: {name}")

    # Every call rereads every source; map preserves ledger error order.
    with ThreadPoolExecutor(max_workers=min(4, len(files))) as pool:
        for _ in pool.map(verify_source, files.items()):
            pass
    receipt = {
        "revision": ledger["revision"],
        "ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "files": files,
    }
    if "retired_modules" in ledger:
        receipt["retired_modules"] = ledger["retired_modules"]
    return receipt


def accepts_current_revision(
    path: Path, historical_sha256: str, observed_sha256: str
) -> bool:
    """Allow only the explicitly reviewed replacement of a historical pin."""
    try:
        path = path.resolve()
        if path.parent != ROOT:
            return False
        record = current_revision()["files"].get(path.name, {})
        return historical_sha256 in record.get(
            "historical_sha256", []
        ) and observed_sha256 == record.get("sha256")
    except (OSError, ValueError, KeyError, TypeError):
        return False


def require_manifest_revision(manifest: Mapping[str, Any]) -> None:
    """An old or altered source graph cannot be resumed with current mechanics."""
    if manifest.get("source_revision") != current_revision():
        raise ValueError("Campaign source revision differs; plan a new campaign")
