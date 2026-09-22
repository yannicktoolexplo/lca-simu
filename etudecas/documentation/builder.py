"""Generate documentation without importing or executing simulator modules.

Fingerprints describe Python ASTs, not raw bytes: CRLF/LF and formatting do not
invalidate business references. They are change detectors, not proof of business
validation or replacements for hashes of simulation inputs and outputs.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = Path("etudecas/docs/rules/lot_risk.json")
DEFAULT_OUTPUT = Path("etudecas/docs/generated")
FORMAT_VERSION = "etudecas.documentation.v1"
FINGERPRINT_METHOD = "python-ast-v1"
STATUSES = {"documented", "hypothesis", "experimental", "known_gap"}


class DocumentationError(ValueError):
    """Invalid or unresolved documentation contract."""


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise DocumentationError(f"Path outside repository: {relative}")
    return path


def _required_text(row: dict[str, Any], name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise DocumentationError(f"Missing non-empty string: {name}")
    return value


def load_registry(root: Path, registry_path: Path) -> dict[str, Any]:
    raw = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or raw.get("schema_version") != FORMAT_VERSION:
        raise DocumentationError("Unsupported documentation registry schema")
    if raw.get("fingerprint_method") != FINGERPRINT_METHOD:
        raise DocumentationError("Unsupported fingerprint method")
    _required_text(raw, "title")
    for name in ("references", "rules"):
        if not isinstance(raw.get(name), list) or not raw[name]:
            raise DocumentationError(f"{name} must be a non-empty list")
    refs: dict[str, dict[str, Any]] = {}
    for ref in raw["references"]:
        if not isinstance(ref, dict):
            raise DocumentationError("Each reference must be an object")
        key = _required_text(ref, "id")
        if key in refs:
            raise DocumentationError(f"Duplicate reference: {key}")
        if ref.get("kind") not in {"implementation", "test", "contract"}:
            raise DocumentationError(f"Invalid reference kind: {key}")
        _inside(root, _required_text(ref, "path"))
        _required_text(ref, "symbol")
        if not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("reference_fingerprint", ""))):
            raise DocumentationError(f"Missing/invalid reference_fingerprint: {key}")
        refs[key] = ref
    ids: set[str] = set()
    for rule in raw["rules"]:
        if not isinstance(rule, dict):
            raise DocumentationError("Each rule must be an object")
        key = _required_text(rule, "id")
        if not re.fullmatch(r"[A-Z]+(?:-[A-Z]+)*-\d{3}", key) or key in ids:
            raise DocumentationError(f"Invalid or duplicate rule id: {key}")
        ids.add(key)
        for name in ("title", "statement", "units", "scope", "limitations"):
            _required_text(rule, name)
        if rule.get("status") not in STATUSES:
            raise DocumentationError(f"Invalid rule status: {key}")
        links = rule.get("references")
        if not isinstance(links, list) or not links or any(not isinstance(x, str) for x in links):
            raise DocumentationError(f"Missing reference list: {key}")
        unknown = set(links) - refs.keys()
        if unknown:
            raise DocumentationError(f"Unknown references for {key}: {sorted(unknown)}")
        if not {"implementation", "test"} <= {refs[x]["kind"] for x in links}:
            raise DocumentationError(f"Rule requires implementation and test references: {key}")
        sources = rule.get("sources")
        if not isinstance(sources, list) or not sources:
            raise DocumentationError(f"Missing business source: {key}")
        for source in sources:
            if not isinstance(source, str) or not _inside(root, source).is_file():
                raise DocumentationError(f"Missing source for {key}: {source}")
    used = {key for rule in raw["rules"] for key in rule["references"]}
    if set(refs) - used:
        raise DocumentationError(f"Unlinked references: {sorted(set(refs) - used)}")
    source_paths = {path for rule in raw["rules"] for path in rule["sources"]}
    snapshots = raw.get("business_source_fingerprints")
    if not isinstance(snapshots, dict) or set(snapshots) != source_paths:
        raise DocumentationError("Business source fingerprints must match declared sources")
    if any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in snapshots.values()):
        raise DocumentationError("Invalid business source fingerprint")
    return raw


def _named_nodes(body: list[ast.stmt]) -> dict[str, ast.AST]:
    nodes: dict[str, ast.AST] = {}
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    nodes[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nodes[node.target.id] = node
    return nodes


def inspect_reference(root: Path, ref: dict[str, Any], cache: dict[str, ast.Module]) -> dict[str, Any]:
    path = _inside(root, ref["path"])
    if ref["path"] not in cache:
        try:
            cache[ref["path"]] = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, SyntaxError) as exc:
            raise DocumentationError(f"Cannot parse {ref['path']}: {exc}") from exc
    node: ast.AST = cache[ref["path"]]
    for part in ref["symbol"].split("."):
        node = _named_nodes(getattr(node, "body", [])).get(part)  # type: ignore[assignment]
        if node is None:
            raise DocumentationError(f"Symbol not found: {ref['path']}::{ref['symbol']}")
    # Keep docstrings but exclude source positions and version-specific empty AST
    # fields (e.g. type_params introduced in Python 3.12).
    def canonical(value: Any) -> Any:
        if isinstance(value, ast.AST):
            return {"node": type(value).__name__, **{
                name: canonical(field) for name, field in ast.iter_fields(value)
                if field is not None and field != []
            }}
        if isinstance(value, list):
            return [canonical(item) for item in value]
        if isinstance(value, (bytes, complex)) or value is Ellipsis:
            return {"literal_type": type(value).__name__, "value": repr(value)}
        return value
    digest = hashlib.sha256(json.dumps(canonical(node), sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        declaration = f"{prefix} {node.name}({ast.unparse(node.args)})"
        if node.returns:
            declaration += f" -> {ast.unparse(node.returns)}"
        declaration += ":"
    elif isinstance(node, ast.ClassDef):
        declaration = f"class {node.name}"
    else:
        declaration = ast.unparse(node)
    docstring = ast.get_docstring(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else None
    return {
        "id": ref["id"], "kind": ref["kind"], "path": ref["path"],
        "symbol": ref["symbol"], "line": node.lineno,
        "fingerprint": digest, "reference_fingerprint": ref["reference_fingerprint"],
        "changed": digest != ref["reference_fingerprint"],
        "declaration": declaration, "docstring": docstring,
    }


def _link(root: Path, output: Path, path: str, label: str, line: int | None = None) -> str:
    relative = Path(os.path.relpath(_inside(root, path), output)).as_posix()
    anchor = f"#L{line}" if line else ""
    return f"[{label}](<{relative}{anchor}>)"


def render(root: Path, registry: dict[str, Any], output: Path) -> tuple[dict[str, str], list[str]]:
    cache: dict[str, ast.Module] = {}
    refs = {ref["id"]: inspect_reference(root, ref, cache) for ref in registry["references"]}
    changed = [key for key, ref in refs.items() if ref["changed"]]
    source_hashes = {
        path: hashlib.sha256(_inside(root, path).read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
        for path in sorted(registry["business_source_fingerprints"])
    }
    changed_sources = [path for path, digest in source_hashes.items()
                       if digest != registry["business_source_fingerprints"][path]]
    lines = [
        f"# {registry['title']}", "",
        "Document généré : modifier le registre et les sources, puis relancer le générateur.", "",
        "Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.",
        "Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.", "",
        "## Règles métier", "",
    ]
    impact: list[dict[str, Any]] = []
    for rule in registry["rules"]:
        affected = sorted(set(rule["references"]) & set(changed))
        affected_sources = sorted(set(rule["sources"]) & set(changed_sources))
        impact.append({"rule_id": rule["id"], "status": rule["status"], "changed_references": affected,
                       "changed_business_sources": affected_sources})
        lines += [
            f"### {rule['id']} — {rule['title']}", "",
            f"Statut déclaré : **{rule['status']}**. Relecture des sources : **{'requise' if affected or affected_sources else 'aucun changement détecté'}**.", "",
            rule["statement"], "", f"Périmètre : {rule['scope']}", "",
            f"Unités : {rule['units']}", "", f"Limites : {rule['limitations']}", "",
            "Sources métier : " + ", ".join(_link(root, output, path, Path(path).name) for path in rule["sources"]), "",
            "Références :", "",
        ]
        for key in rule["references"]:
            ref = refs[key]
            lines.append(f"- {ref['kind']} : " + _link(root, output, ref["path"], ref["symbol"], ref["line"]))
        lines.append("")
    lines += ["## Référence technique extraite", "",
              "Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.", ""]
    for ref in refs.values():
        lines += [f"### {ref['id']}", "",
                  _link(root, output, ref["path"], f"{ref['path']}:{ref['line']}", ref["line"]), "",
                  "```python", ref["declaration"], "```", ""]
        if ref["docstring"]:
            lines += [ref["docstring"], ""]
    manifest = {
        "schema_version": FORMAT_VERSION, "fingerprint_method": FINGERPRINT_METHOD,
        "business_source_fingerprints": source_hashes,
        "references": list(refs.values()), "rules": impact,
        "tests_executed": False,
    }
    return {
        "index.md": "\n".join(lines).rstrip() + "\n",
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    }, changed + changed_sources


def run(command: str, *, root: Path, registry_path: Path, output: Path) -> int:
    registry = load_registry(root, registry_path)
    artifacts, changed = render(root, registry, output)
    if command == "inspect":
        print(artifacts["manifest.json"], end="")
        return 0
    stale: list[str] = []
    for name, content in artifacts.items():
        path = output / name
        if command == "build":
            output.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8", newline="\n")
        elif not path.is_file() or path.read_text(encoding="utf-8") != content:
            stale.append(name)
    if stale:
        print("Documentation out of date: " + ", ".join(stale))
        print("Run: python -m etudecas.documentation build")
    if changed:
        print("Business review required for changed references: " + ", ".join(changed))
        print("Use inspect to review affected rules; build never updates reference fingerprints.")
    if not stale and not changed:
        print("Documentation generated." if command == "build" else "Documentation is current; business validation is not inferred.")
    return int(bool(stale or changed))


def _watch_state(root: Path, registry_path: Path, output: Path) -> tuple[Any, ...]:
    paths = {registry_path, Path(__file__), output / "index.md", output / "manifest.json"}
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            refs = raw.get("references", [])
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                        paths.add(_inside(root, ref["path"]))
            sources = raw.get("business_source_fingerprints", {})
            if isinstance(sources, dict):
                paths.update(_inside(root, path) for path in sources)
    except (OSError, ValueError, TypeError):
        # Keep watching a partially saved registry; the next save retries it.
        pass
    return tuple((str(path), (path.stat().st_mtime_ns, path.stat().st_size) if path.is_file() else None)
                 for path in sorted(paths))


def watch(*, root: Path, registry_path: Path, output: Path, interval: float) -> int:
    print("Watching documentation sources; Ctrl+C to stop. Business fingerprints are never accepted automatically.")
    previous: tuple[Any, ...] | None = None
    try:
        while True:
            current = _watch_state(root, registry_path, output)
            if current != previous:
                try:
                    run("build", root=root, registry_path=registry_path, output=output)
                except (OSError, ValueError, TypeError) as exc:
                    print(f"Documentation error (waiting for next edit): {exc}")
                previous = _watch_state(root, registry_path, output)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "inspect", "watch", "build-all", "check-all", "watch-all"))
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--interval", type=float, default=2.0, help="Watch polling interval in seconds")
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.interval) or args.interval <= 0:
            raise DocumentationError("--interval must be a positive finite number")
        if args.command.endswith("-all"):
            from .batch import run_all, watch_all
            if args.registry != DEFAULT_REGISTRY or args.output_dir != DEFAULT_OUTPUT:
                raise DocumentationError("Batch commands use catalog.json, not --registry/--output-dir")
            return (watch_all(REPO_ROOT, args.interval) if args.command == "watch-all"
                    else run_all(args.command.removesuffix("-all"), REPO_ROOT))
        if args.command == "watch":
            return watch(root=REPO_ROOT, registry_path=_inside(REPO_ROOT, str(args.registry)),
                         output=_inside(REPO_ROOT, str(args.output_dir)), interval=args.interval)
        return run(args.command, root=REPO_ROOT,
                   registry_path=_inside(REPO_ROOT, str(args.registry)),
                   output=_inside(REPO_ROOT, str(args.output_dir)))
    except (DocumentationError, OSError, ValueError, TypeError) as exc:
        print(f"Documentation error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
