"""Helpers for transforming generated map HTML DATA payloads."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


def find_balanced_object(text: str, start: int) -> tuple[int, int]:
    open_pos = text.find("{", start)
    if open_pos < 0:
        raise ValueError("No JSON object found after DATA marker")
    depth = 0
    in_string = False
    escape = False
    for idx in range(open_pos, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_pos, idx + 1
    raise ValueError("Unbalanced JSON object after DATA marker")


def extract_data_assignment(html_text: str) -> tuple[int, int, str]:
    marker = "const DATA ="
    marker_pos = html_text.find(marker)
    if marker_pos < 0:
        raise ValueError("Cannot find 'const DATA =' marker")
    obj_start, obj_end = find_balanced_object(html_text, marker_pos + len(marker))
    data_text = html_text[obj_start:obj_end]
    json.loads(data_text)
    semicolon_end = obj_end
    while semicolon_end < len(html_text) and html_text[semicolon_end].isspace():
        semicolon_end += 1
    if semicolon_end < len(html_text) and html_text[semicolon_end] == ";":
        semicolon_end += 1
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


def wrap_data_dependent_script(html_text: str, loader_js: str, boot_expression: str) -> tuple[str, str]:
    marker_pos, semicolon_end, data_text = extract_data_assignment(html_text)
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
        from etudecas.visualization.maps.externalize_html_payload import externalize

        payload_path = Path(payload_json) if payload_json else html_output_path.with_suffix(".data.json")
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        html_text, data_text = externalize(html_text, relative_payload_url(payload_path, html_output_path))
        payload_path.write_text(data_text, encoding="utf-8")
        if log is not None:
            log(f"[OK] External DATA payload generated: {payload_path.resolve()}")
        return html_text

    if compress_embedded_payload:
        from etudecas.visualization.maps.compress_html_payload import compress_embedded

        html_text, compression_stats = compress_embedded(html_text)
        if log is not None:
            log(
                "[OK] Embedded compressed DATA payload: "
                f"{compression_stats['raw_bytes'] / 1024 / 1024:.2f} MB raw -> "
                f"{compression_stats['compressed_bytes'] / 1024 / 1024:.2f} MB gzip"
            )
        return html_text

    if chunked_embedded_payload:
        from etudecas.visualization.maps.chunk_html_payload import chunk_embedded

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
