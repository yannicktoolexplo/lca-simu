#!/usr/bin/env python3
"""Embed generated map DATA as autonomous top-level compressed chunks.

This keeps a single HTML file while storing each top-level DATA key as a
separate gzip/base64 block. Current generated maps still load all blocks before
initialization for compatibility, but the format allows future panels to load
specific blocks on demand.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path
import textwrap
from typing import Any

try:
    from etudecas.visualization.maps.html_payload_tools import extract_data_assignment, wrap_data_dependent_script
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.html_payload_tools import extract_data_assignment, wrap_data_dependent_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk generated map DATA payload into autonomous compressed blocks.")
    parser.add_argument("--input", required=True, help="Input generated HTML.")
    parser.add_argument("--output", help="Output HTML. Defaults to <input>.chunked.html")
    parser.add_argument("--chunk-size", type=int, default=65536, help="Base64 chunk size per DATA block.")
    parser.add_argument("--execute", action="store_true", help="Write file. Default is dry-run.")
    return parser.parse_args()


def group_for_key(key: str) -> str:
    if key in {"nodes", "edges", "node_type_styles", "timeline_horizon_days", "factory_like_node_ids"}:
        return "core"
    if "lot_trace" in key:
        return "lot_trace"
    if key == "montecarlo_uncertainty" or "uncertainty" in key:
        return "uncertainty"
    if key == "scan_dashboard":
        return "risk"
    if "sensitivity" in key or key in {"scenario_comparison", "realistic_sensitivity", "threshold_sensitivity"}:
        return "sensitivity"
    if "risk" in key:
        return "risk"
    if "hover" in key or "current_metrics" in key or key in {"factory_hover_series", "simulation_diagnostics"}:
        return "simulation"
    if key in {"data_panel", "json_panel", "material_balance_rows", "global_kpi_tree", "model_panel"}:
        return "diagnostics"
    return "other"


def encode_json_chunk(value: Any, *, chunk_size: int) -> tuple[list[str], int, int]:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    b64 = base64.b64encode(compressed).decode("ascii")
    return textwrap.wrap(b64, max(1024, chunk_size)), len(raw), len(compressed)


def chunked_loader_js(data: dict[str, Any], *, chunk_size: int = 65536) -> tuple[str, dict[str, Any]]:
    encoded: dict[str, list[str]] = {}
    manifest: dict[str, dict[str, Any]] = {}
    raw_total = 0
    compressed_total = 0
    for key, value in data.items():
        chunks, raw_bytes, compressed_bytes = encode_json_chunk(value, chunk_size=chunk_size)
        encoded[key] = chunks
        manifest[key] = {
            "group": group_for_key(key),
            "raw_bytes": raw_bytes,
            "compressed_bytes": compressed_bytes,
        }
        raw_total += raw_bytes
        compressed_total += compressed_bytes

    loader = (
        "let DATA = {};\n"
        f"const DATA_CHUNKED_GZIP_BASE64 = {json.dumps(encoded, separators=(',', ':'))};\n"
        f"const DATA_CHUNKED_MANIFEST = {json.dumps(manifest, separators=(',', ':'))};\n"
        "const DATA_CHUNKED_LOADED_KEYS = new Set();\n"
        "async function inflateEmbeddedGzipChunks(chunks) {\n"
        "  if (!(\"DecompressionStream\" in window)) {\n"
        "    throw new Error(\"Ce navigateur ne supporte pas DecompressionStream(gzip). Utilise Edge/Chrome recent ou genere la carte sans compression embarquee.\");\n"
        "  }\n"
        "  const binary = atob(chunks.join(\"\"));\n"
        "  const bytes = new Uint8Array(binary.length);\n"
        "  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);\n"
        "  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(\"gzip\"));\n"
        "  return await new Response(stream).text();\n"
        "}\n"
        "async function loadEmbeddedChunkedMapData(keys) {\n"
        "  const wanted = keys || Object.keys(DATA_CHUNKED_GZIP_BASE64);\n"
        "  await Promise.all(wanted.map(async (key) => {\n"
        "    if (DATA_CHUNKED_LOADED_KEYS.has(key)) return;\n"
        "    const chunks = DATA_CHUNKED_GZIP_BASE64[key];\n"
        "    if (!chunks) return;\n"
        "    const text = await inflateEmbeddedGzipChunks(chunks);\n"
        "    DATA[key] = JSON.parse(text);\n"
        "    DATA_CHUNKED_LOADED_KEYS.add(key);\n"
        "  }));\n"
        "}\n"
        "async function loadEmbeddedChunkedMapGroup(groupName) {\n"
        "  const keys = Object.keys(DATA_CHUNKED_MANIFEST).filter((key) => DATA_CHUNKED_MANIFEST[key].group === groupName);\n"
        "  await loadEmbeddedChunkedMapData(keys);\n"
        "}"
    )
    stats = {
        "key_count": len(data),
        "raw_bytes": raw_total,
        "compressed_bytes": compressed_total,
        "manifest": manifest,
    }
    return loader, stats


def chunk_embedded(html_text: str, *, chunk_size: int = 65536) -> tuple[str, dict[str, Any]]:
    _, _, data_text = extract_data_assignment(html_text)
    data = json.loads(data_text)
    if not isinstance(data, dict):
        raise ValueError("DATA payload must be a JSON object for chunked embedding.")
    loader, stats = chunked_loader_js(data, chunk_size=chunk_size)
    chunked_html, _ = wrap_data_dependent_script(
        html_text,
        loader,
        "loadEmbeddedChunkedMapData()",
    )
    stats["html_bytes"] = len(chunked_html.encode("utf-8"))
    return chunked_html, stats


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".chunked.html")
    html_text = input_path.read_text(encoding="utf-8")
    chunked_html, stats = chunk_embedded(html_text, chunk_size=args.chunk_size)
    print(f"[INFO] Input HTML: {input_path} ({input_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"[INFO] DATA keys: {stats['key_count']}")
    print(f"[INFO] Raw top-level DATA chunks: {stats['raw_bytes'] / 1024 / 1024:.2f} MB")
    print(f"[INFO] Gzip top-level DATA chunks: {stats['compressed_bytes'] / 1024 / 1024:.2f} MB")
    print(f"[INFO] Output HTML estimate: {stats['html_bytes'] / 1024 / 1024:.2f} MB -> {output_path}")
    print("[INFO] Output remains autonomous; block manifest can support future panel-level lazy loading.")
    if not args.execute:
        print("[DRY-RUN] pass --execute to write file")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(chunked_html, encoding="utf-8")
    print(f"[OK] Wrote {output_path.resolve()}")


if __name__ == "__main__":
    main()
