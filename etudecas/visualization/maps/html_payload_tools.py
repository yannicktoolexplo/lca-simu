"""Transform generated map DATA as external JSON or autonomous gzip payloads.

The builder imports the pure transforms below. The CLI shares those transforms
and writes only with --execute; it never runs a simulation.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import textwrap
import os
from pathlib import Path
from typing import Any, Callable


def _decode_data_assignment(html_text: str) -> tuple[int, int, str, Any]:
    """Validate/decode DATA once and retain its exact source text and bounds."""
    marker = "const DATA ="
    marker_pos = html_text.find(marker)
    if marker_pos < 0:
        raise ValueError("Cannot find 'const DATA =' marker")
    obj_start = html_text.find("{", marker_pos + len(marker))
    if obj_start < 0:
        raise ValueError("No JSON object found after DATA marker")
    data, obj_end = json.JSONDecoder().raw_decode(html_text, obj_start)
    data_text = html_text[obj_start:obj_end]
    semicolon_end = obj_end
    while semicolon_end < len(html_text) and html_text[semicolon_end].isspace():
        semicolon_end += 1
    if semicolon_end < len(html_text) and html_text[semicolon_end] == ";":
        semicolon_end += 1
    return marker_pos, semicolon_end, data_text, data


def extract_data_assignment(html_text: str) -> tuple[int, int, str]:
    marker_pos, semicolon_end, data_text, _ = _decode_data_assignment(html_text)
    return marker_pos, semicolon_end, data_text


def ready_init_js() -> str:
    return (
        'if (document.readyState === "loading") { '
        'window.addEventListener("load", init); '
        '} else { init(); }'
    )


def replace_init_trigger(script_body: str) -> str:
    load_listener = 'window.addEventListener("load", init);'
    if load_listener in script_body:
        return script_body.replace(load_listener, ready_init_js(), 1)
    if "init();" in script_body:
        return script_body.replace("init();", ready_init_js(), 1)
    raise ValueError("Cannot find init trigger to defer until DATA is loaded")


def wrap_data_dependent_script(
    html_text: str,
    loader_js: str,
    boot_expression: str,
    *,
    data_assignment: tuple[int, int, str] | None = None,
) -> tuple[str, str]:
    # The chunk encoder passes the assignment already decoded from this HTML.
    # Standalone callers still receive the same JSON validation as before.
    marker_pos, semicolon_end, data_text = (
        extract_data_assignment(html_text) if data_assignment is None else data_assignment
    )
    script_close = html_text.find("</script>", semicolon_end)
    if script_close < 0:
        raise ValueError("Cannot find closing </script> after DATA payload")
    script_body = replace_init_trigger(html_text[semicolon_end:script_close])
    wrapped = (
        html_text[:marker_pos]
        + loader_js
        + "\n"
        + f"{boot_expression}.then(() => {{\n"
        + script_body
        + "\n}).catch((err) => {\n"
        + "  console.error(err);\n"
        + "  alert(String(err));\n"
        + "});\n"
        + html_text[script_close:]
    )
    return wrapped, data_text


def payload_mode_count(
    *,
    externalize_payload: bool = False,
    compress_embedded_payload: bool = False,
    chunked_embedded_payload: bool = False,
) -> int:
    return sum(
        [
            bool(externalize_payload),
            bool(compress_embedded_payload),
            bool(chunked_embedded_payload),
        ]
    )


def relative_payload_url(payload_path: Path, html_output_path: Path) -> str:
    try:
        return os.path.relpath(payload_path.resolve(), html_output_path.parent.resolve()).replace("\\", "/")
    except ValueError:
        return payload_path.name


def apply_html_payload_mode(
    html_text: str,
    html_output_path: Path,
    *,
    externalize_payload: bool = False,
    compress_embedded_payload: bool = False,
    chunked_embedded_payload: bool = False,
    payload_json: str | Path | None = None,
    log: Callable[[str], None] | None = print,
) -> str:
    if payload_mode_count(
        externalize_payload=externalize_payload,
        compress_embedded_payload=compress_embedded_payload,
        chunked_embedded_payload=chunked_embedded_payload,
    ) > 1:
        raise ValueError(
            "Use only one payload mode: --externalize-payload, "
            "--compress-embedded-payload or --chunked-embedded-payload."
        )

    if externalize_payload:

        payload_path = Path(payload_json) if payload_json else html_output_path.with_suffix(".data.json")
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        html_text, data_text = externalize(html_text, relative_payload_url(payload_path, html_output_path))
        payload_path.write_text(data_text, encoding="utf-8")
        if log is not None:
            log(f"[OK] External DATA payload generated: {payload_path.resolve()}")
        return html_text

    if compress_embedded_payload:

        html_text, compression_stats = compress_embedded(html_text)
        if log is not None:
            log(
                "[OK] Embedded compressed DATA payload: "
                f"{compression_stats['raw_bytes'] / 1024 / 1024:.2f} MB raw -> "
                f"{compression_stats['compressed_bytes'] / 1024 / 1024:.2f} MB gzip"
            )
        return html_text

    if chunked_embedded_payload:

        html_text, chunk_stats = chunk_embedded(html_text)
        if log is not None:
            log(
                "[OK] Embedded chunked DATA payload: "
                f"{chunk_stats['key_count']} keys ; "
                f"{chunk_stats['raw_bytes'] / 1024 / 1024:.2f} MB raw -> "
                f"{chunk_stats['compressed_bytes'] / 1024 / 1024:.2f} MB gzip"
            )
        return html_text

    return html_text


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
    width = max(1024, chunk_size)
    return [b64[start:start + width] for start in range(0, len(b64), width)], len(raw), len(compressed)


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
    marker_pos, semicolon_end, data_text, data = _decode_data_assignment(html_text)
    if not isinstance(data, dict):
        raise ValueError("DATA payload must be a JSON object for chunked embedding.")
    loader, stats = chunked_loader_js(data, chunk_size=chunk_size)
    chunked_html, _ = wrap_data_dependent_script(
        html_text,
        loader,
        "loadEmbeddedChunkedMapData()",
        data_assignment=(marker_pos, semicolon_end, data_text),
    )
    stats["html_bytes"] = len(chunked_html.encode("utf-8"))
    return chunked_html, stats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("external", "compressed", "chunked"))
    parser.add_argument("--input", type=Path, required=True, help="Input generated HTML.")
    parser.add_argument("--output", type=Path, help="Defaults to <input>.<mode>.html.")
    parser.add_argument("--data-output", type=Path, help="External mode only: sibling JSON by default.")
    parser.add_argument("--chunk-size", type=int, default=65536, help="Base64 chunk size, minimum 1024.")
    parser.add_argument("--execute", action="store_true", help="Write files; otherwise preview only.")
    args = parser.parse_args(argv)
    if args.data_output is not None and args.mode != "external":
        parser.error("--data-output requires --mode external")

    output = args.output or args.input.with_suffix(f".{args.mode}.html")
    source = args.input.read_text(encoding="utf-8")
    data_output = None
    if args.mode == "external":
        data_output = args.data_output or output.with_suffix(".data.json")
        document, data_text = externalize(source, relative_payload_url(data_output, output))
        stats = {"raw_bytes": len(data_text.encode("utf-8")), "data_output": str(data_output)}
    elif args.mode == "compressed":
        document, stats = compress_embedded(source, chunk_size=args.chunk_size)
    else:
        document, stats = chunk_embedded(source, chunk_size=args.chunk_size)

    print(json.dumps({"mode": args.mode, "input": str(args.input), "output": str(output),
                      "html_bytes": len(document.encode("utf-8")), "execute": args.execute,
                      "stats": stats}, ensure_ascii=False))
    if not args.execute:
        print("[DRY-RUN] pass --execute to write files")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    if data_output is not None:
        data_output.parent.mkdir(parents=True, exist_ok=True)
        data_output.write_text(data_text, encoding="utf-8")
    output.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    main()
