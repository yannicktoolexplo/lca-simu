from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": MAIN_NS, "r": REL_NS, "rel": PKG_REL_NS}


def write_xlsx(path: str | Path, sheets: dict[str, list[dict[str, Any]]], columns: dict[str, list[str]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = [_safe_sheet_name(name, used=set()) for name in sheets]
    used: set[str] = set()
    sheet_names = []
    for name in sheets:
        sheet_names.append(_safe_sheet_name(name, used=used))

    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def string_index(value: Any) -> int:
        text = "" if value is None else str(value)
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_index[text]

    worksheet_xml: list[str] = []
    for raw_name, sheet_name in zip(sheets.keys(), sheet_names):
        headers = columns.get(raw_name) or _infer_columns(sheets[raw_name])
        rows = [dict(zip(headers, headers)), *sheets[raw_name]]
        worksheet_xml.append(_worksheet_xml(headers, rows, string_index))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml(len(sheet_names)))
        zf.writestr("_rels/.rels", _root_rels_xml())
        zf.writestr("xl/workbook.xml", _workbook_xml(sheet_names))
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheet_names)))
        zf.writestr("xl/sharedStrings.xml", _shared_strings_xml(shared_strings))
        zf.writestr("xl/styles.xml", _styles_xml())
        for idx, xml in enumerate(worksheet_xml, start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", xml)


def read_xlsx(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    with zipfile.ZipFile(Path(path)) as zf:
        shared_strings = _read_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib.get("Id"): rel.attrib.get("Target", "")
            for rel in rels.findall("rel:Relationship", NS)
        }
        out: dict[str, list[dict[str, Any]]] = {}
        for sheet in workbook.findall(".//a:sheet", NS):
            name = sheet.attrib.get("name") or ""
            rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
            target = rel_targets.get(rel_id, "")
            if not target:
                continue
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            target = target.replace("\\", "/")
            out[name] = _read_sheet(zf.read(target), shared_strings)
        return out


def _worksheet_xml(headers: list[str], rows: list[dict[str, Any]], string_index) -> str:
    xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, header in enumerate(headers, start=1):
            value = row.get(header, "")
            cell_ref = f"{_col_name(c_idx)}{r_idx}"
            if value is None or value == "":
                cells.append(f'<c r="{cell_ref}"/>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{cell_ref}" t="s"><v>{string_index(value)}</v></c>')
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )


def _read_sheet(xml_bytes: bytes, shared_strings: list[str]) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    raw_rows: list[list[Any]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        values: list[Any] = []
        for cell in row.findall("a:c", NS):
            idx = _col_index(cell.attrib.get("r", "A1"))
            while len(values) <= idx:
                values.append("")
            values[idx] = _cell_value(cell, shared_strings)
        raw_rows.append(values)
    if not raw_rows:
        return []
    headers = [str(value).strip() for value in raw_rows[0]]
    out: list[dict[str, Any]] = []
    for raw in raw_rows[1:]:
        if not any(value not in (None, "") for value in raw):
            continue
        out.append({headers[idx]: raw[idx] if idx < len(raw) else "" for idx in range(len(headers)) if headers[idx]})
    return out


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    value = cell.find("a:v", NS)
    if value is None or value.text is None:
        return ""
    raw = value.text
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(float(raw))]
        except (ValueError, IndexError):
            return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    return int(number) if number.is_integer() else number


def _content_types_xml(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        f"{sheets}</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{html.escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>{sheets}</sheets></workbook>'
    )


def _workbook_rels_xml(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    rels += (
        f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        f'<Relationship Id="rId{sheet_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}">{rels}</Relationships>'


def _shared_strings_xml(strings: list[str]) -> str:
    items = "".join(f"<si><t>{html.escape(text)}</t></si>" for text in strings)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="{MAIN_NS}" count="{len(strings)}" uniqueCount="{len(strings)}">{items}</sst>'


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{MAIN_NS}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>'
    )


def _infer_columns(rows: list[dict[str, Any]]) -> list[str]:
    cols: list[str] = []
    for row in rows:
        for key in row:
            if key not in cols:
                cols.append(key)
    return cols


def _safe_sheet_name(name: str, used: set[str]) -> str:
    clean = re.sub(r"[\[\]\*:/\\?]", "_", str(name or "Sheet")).strip()[:31] or "Sheet"
    base = clean
    counter = 2
    while clean in used:
        suffix = f"_{counter}"
        clean = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    used.add(clean)
    return clean


def _col_name(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return max(0, idx - 1)
