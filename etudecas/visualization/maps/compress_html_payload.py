#!/usr/bin/env python3
"""Embed the generated map DATA payload as compressed JSON inside one HTML file.

The output remains autonomous: no sibling JSON file is required. The browser
uses ``DecompressionStream("gzip")`` to inflate the embedded payload before the
map initializes.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path
import textwrap

try:
    from etudecas.visualization.maps.html_payload_tools import extract_data_assignment, wrap_data_dependent_script
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.html_payload_tools import extract_data_assignment, wrap_data_dependent_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compress generated map DATA payload into autonomous HTML.")
    parser.add_argument("--input", required=True, help="Input generated HTML.")
    parser.add_argument("--output", help="Output HTML. Defaults to <input>.compressed.html")
    parser.add_argument("--chunk-size", type=int, default=65536, help="Base64 chunk size in the generated HTML.")
    parser.add_argument("--execute", action="store_true", help="Write file. Default is dry-run.")
    return parser.parse_args()


def compressed_loader_js(data_text: str, *, chunk_size: int = 65536) -> tuple[str, int, int]:
    compact_text = json.dumps(json.loads(data_text), separators=(",", ":"), ensure_ascii=False)
    raw = compact_text.encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    b64 = base64.b64encode(compressed).decode("ascii")
    chunks = textwrap.wrap(b64, max(1024, chunk_size))
    loader = (
        "let DATA = {};\n"
        f"const DATA_GZIP_BASE64_CHUNKS = {json.dumps(chunks)};\n"
        "async function loadEmbeddedCompressedMapData() {\n"
        "  if (!(\"DecompressionStream\" in window)) {\n"
        "    throw new Error(\"Ce navigateur ne supporte pas DecompressionStream(gzip). Utilise Edge/Chrome recent ou genere la carte sans compression embarquee.\");\n"
        "  }\n"
        "  const binary = atob(DATA_GZIP_BASE64_CHUNKS.join(\"\"));\n"
        "  const bytes = new Uint8Array(binary.length);\n"
        "  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);\n"
        "  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(\"gzip\"));\n"
        "  const text = await new Response(stream).text();\n"
        "  DATA = JSON.parse(text);\n"
        "}"
    )
    return loader, len(raw), len(compressed)


def compress_embedded(html_text: str, *, chunk_size: int = 65536) -> tuple[str, dict[str, int]]:
    _, _, data_text = extract_data_assignment(html_text)
    loader, raw_bytes, compressed_bytes = compressed_loader_js(data_text, chunk_size=chunk_size)
    compressed_html, _ = wrap_data_dependent_script(
        html_text,
        loader,
        "loadEmbeddedCompressedMapData()",
    )
    return compressed_html, {
        "raw_bytes": raw_bytes,
        "compressed_bytes": compressed_bytes,
        "html_bytes": len(compressed_html.encode("utf-8")),
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".compressed.html")
    html_text = input_path.read_text(encoding="utf-8")
    compressed_html, stats = compress_embedded(html_text, chunk_size=args.chunk_size)
    print(f"[INFO] Input HTML: {input_path} ({input_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"[INFO] Raw DATA: {stats['raw_bytes'] / 1024 / 1024:.2f} MB")
    print(f"[INFO] Gzip DATA: {stats['compressed_bytes'] / 1024 / 1024:.2f} MB")
    print(f"[INFO] Output HTML estimate: {stats['html_bytes'] / 1024 / 1024:.2f} MB -> {output_path}")
    print("[INFO] Output remains autonomous; no external JSON is needed.")
    if not args.execute:
        print("[DRY-RUN] pass --execute to write file")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compressed_html, encoding="utf-8")
    print(f"[OK] Wrote {output_path.resolve()}")


if __name__ == "__main__":
    main()
