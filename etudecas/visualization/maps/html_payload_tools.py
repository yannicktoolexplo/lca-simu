"""Helpers for transforming generated map HTML DATA payloads."""

from __future__ import annotations

import json


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
