"""Package the verified 2025 D1920 investigation as an offline HTML page."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ETUDECAS = HERE.parents[1]
PRODUCTS = {"268091", "268967"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def script_json(value) -> str:
    # Prevent workbook cell text from ending an embedded script element.
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")


def build(dataset: Path, output: Path, manifest: Path | None) -> dict:
    dataset, output = dataset.resolve(), output.resolve()
    if output.suffix.lower() != ".html":
        raise ValueError("Expected a new HTML output")
    if output.exists() or (manifest is not None and manifest.exists()):
        raise FileExistsError("Choose new report and manifest paths.")

    template_path = HERE / "D1920_real_trace.html"
    script_path = HERE / "D1920_real_trace.js"
    files = {path: path.read_bytes() for path in (dataset, template_path, script_path)}
    data = json.loads(files[dataset].decode("utf-8"))
    if set(data["products"]) != PRODUCTS or not data["sources"] or not data["pairs"]:
        raise ValueError("Expected a two-product industrial data package.")
    for product, context in data["products"].items():
        dates = [week["start"] for week in context["weeks"]]
        if not dates or dates != sorted(set(dates)) or f"1920/{product}" not in data["pairs"]:
            raise ValueError(f"Missing or ambiguous D1920 weeks for {product}")
    explorer = ETUDECAS / "resultats/donnees_reliees_20261112/explorateur_donnees.html"
    relative_explorer = Path(os.path.relpath(explorer, output.parent)).as_posix() if explorer.is_file() else None
    template = files[template_path].decode("utf-8")
    script = files[script_path].decode("utf-8")
    payload = script_json({"data": data, "explorer": relative_explorer})
    if template.count("__D1920_DATA__") != 1 or template.count("__D1920_SCRIPT__") != 1 or "</script" in script.lower():
        raise ValueError("Invalid standalone report template.")
    html = template.replace("__D1920_SCRIPT__", script).replace("__D1920_DATA__", payload).encode("utf-8")
    if len(html) > 80 * 1024 ** 2:
        raise ValueError("Offline report exceeds the declared size budget.")
    if any(path.read_bytes() != data for path, data in files.items()):
        raise ValueError("An input changed during report preparation.")

    with output.open("xb") as stream:
        stream.write(html)
    evidence = {
        "status": "built_offline_report",
        "output": str(output),
        "output_sha256": sha(html),
        "bytes": len(html),
        "weeks_by_product": {name: len(value["weeks"]) for name, value in data["products"].items()},
        "inputs_sha256": {str(path): sha(value) for path, value in files.items()},
        "explorer": relative_explorer,
    }
    if manifest is not None:
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False, indent=2)
    return evidence


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dataset", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--manifest", type=Path)
    args = cli.parse_args()
    print(json.dumps(build(args.dataset, args.output, args.manifest), ensure_ascii=False))


if __name__ == "__main__":
    main()
