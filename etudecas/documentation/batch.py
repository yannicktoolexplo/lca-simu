"""Build or check every declared documentation registry, without accepting fingerprints."""

import json
from pathlib import Path
import time

from .builder import DocumentationError, _inside, _watch_state, run

CATALOG = "etudecas/docs/catalog.json"


def entries(root: Path):
    payload = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "etudecas.documentation.catalog.v1":
        raise DocumentationError("Invalid documentation catalog")
    rows = payload.get("registries")
    if not isinstance(rows, list) or not rows:
        raise DocumentationError("Catalog requires registries")
    result, registries, outputs = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in ("registry", "output")):
            raise DocumentationError("Invalid catalog entry")
        registry, output = (_inside(root, row[k]) for k in ("registry", "output"))
        if registry in registries or output in outputs:
            raise DocumentationError("Duplicate catalog registry or output")
        registries.add(registry)
        outputs.add(output)
        result.append((registry, output))
    discovered = {p.resolve() for p in (root / "etudecas/docs/rules").glob("*.json")}
    if registries != discovered:
        raise DocumentationError("Catalog must cover exactly every registry in docs/rules")
    return result


def run_all(command: str, root: Path) -> int:
    items = entries(root)
    code = 0
    for registry, output in items:
        print(f"[{registry.stem}]")
        try:
            code = max(code, run(command, root=root, registry_path=registry, output=output))
        except (OSError, ValueError, TypeError) as exc:
            print(f"Documentation error: {exc}")
            code = 2
    return code


def watch_all(root: Path, interval: float) -> int:
    previous = None
    print("Watching all documentation registries; Ctrl+C to stop. Fingerprints are never accepted automatically.")
    try:
        while True:
            try:
                catalog = root / CATALOG
                state = (catalog.read_bytes(), tuple(sorted(p.name for p in (root / "etudecas/docs/rules").glob("*.json"))),
                         tuple(_watch_state(root, r, o) for r, o in entries(root)))
                if state != previous:
                    run_all("build", root)
                previous = (catalog.read_bytes(), state[1],
                            tuple(_watch_state(root, r, o) for r, o in entries(root)))
            except (OSError, ValueError, TypeError) as exc:
                error = str(exc)
                if error != previous:
                    print(f"Documentation error (waiting for next edit): {error}")
                previous = error
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
