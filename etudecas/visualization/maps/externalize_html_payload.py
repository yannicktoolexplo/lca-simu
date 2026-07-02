#!/usr/bin/env python3
"""Externalize the large ``const DATA = {...};`` payload from a generated map.

This reduces HTML size but requires serving the HTML through HTTP in browsers
that block ``fetch()`` from ``file://`` URLs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from etudecas.visualization.maps.html_payload_tools import wrap_data_dependent_script
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.html_payload_tools import wrap_data_dependent_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Externalize generated map DATA payload.")
    parser.add_argument("--input", required=True, help="Input generated HTML.")
    parser.add_argument("--output", help="Output HTML. Defaults to <input>.external.html")
    parser.add_argument("--data-output", help="Output JSON. Defaults to <output>.data.json")
    parser.add_argument("--execute", action="store_true", help="Write files. Default is dry-run.")
    return parser.parse_args()


def externalize(html_text: str, data_url: str) -> tuple[str, str]:
    loader = (
        f"let DATA = {{}};\n"
        f"const DATA_EXTERNAL_URL = {json.dumps(data_url)};\n"
        "    async function loadExternalMapData() {\n"
        "      const response = await fetch(DATA_EXTERNAL_URL);\n"
        "      if (!response.ok) throw new Error(`Cannot load ${DATA_EXTERNAL_URL}: ${response.status}`);\n"
        "      DATA = await response.json();\n"
        "    }"
    )
    return wrap_data_dependent_script(html_text, loader, "loadExternalMapData()")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".external.html")
    data_output = Path(args.data_output) if args.data_output else output_path.with_suffix(".data.json")
    html_text = input_path.read_text(encoding="utf-8")
    data_url = data_output.name if data_output.parent == output_path.parent else str(data_output)
    new_html, data_text = externalize(html_text, data_url)
    print(f"[INFO] Input HTML: {input_path} ({input_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"[INFO] Extracted DATA: {len(data_text) / 1024 / 1024:.2f} MB -> {data_output}")
    print(f"[INFO] Output HTML estimate: {len(new_html) / 1024 / 1024:.2f} MB -> {output_path}")
    if not args.execute:
        print("[DRY-RUN] pass --execute to write files")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data_output.parent.mkdir(parents=True, exist_ok=True)
    data_output.write_text(data_text, encoding="utf-8")
    output_path.write_text(new_html, encoding="utf-8")
    print(f"[OK] Wrote {output_path.resolve()}")
    print(f"[OK] Wrote {data_output.resolve()}")


if __name__ == "__main__":
    main()
