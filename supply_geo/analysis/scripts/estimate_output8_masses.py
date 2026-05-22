#!/usr/bin/env python3
"""
Estimate missing component masses in the cleaned output8 GEO JSON.

Primary source:
  data/quantity_material.xlsx

Priority:
  1. Exact BOM match: system/equipment + material.
  2. BOM material family sum for broad component labels.
  3. Whole-equipment mass for COTS/electronic assemblies.
  4. Global BOM material total when the system is too vague.
  5. Existing non-zero mass from the JSON.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_corrected.json"
MASS_WORKBOOK = ROOT / "data" / "quantity_material.xlsx"
OUTPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_corrected_mass_estimated.json"
OUTPUT_CSV = ROOT / "analysis" / "output8_GEO_mass_estimates.csv"
REPORT_MD = ROOT / "analysis" / "output8_GEO_mass_estimation_report.md"

XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


SYSTEM_ALIASES = {
    "ens equipements lateraux": "ENSEMBLE EQUIPEMENTS LATERALES",
    "ensemble equipements lateraux": "ENSEMBLE EQUIPEMENTS LATERALES",
    "ens stowage lateral": "ENS STOWAGE LATERAL",
    "stowage assemble avec porte": "STOWAGE ASSEMBLE AVEC PORTE",
    "ensemble porte": "ENSEMBLE PORTE",
    "ens porte": "ENSEMBLE PORTE",
    "ens structure porte": "ENSEMBLE PORTE",
    "bumper version porte": "BUMPER VERSION PORTE",
    "lightning": "LIGHTING x3",
    "lighting": "LIGHTING x3",
    "padding rembourrage": "PADDING",
    "system ife in flight entertainment est un ensemble d equipements et de logiciels qui permet aux passagers d occuper leur temps a bord d un avion": "SYSTEM IFE BOITIER",
    "system ife boitier": "SYSTEM IFE BOITIER",
    "coussin ottoman": 'COUSSIN OTTOMAN STD PITCH 38" QTU',
    "manchette acc mobile": "MANCHETTE ACC MOBILE",
    "accoudoir allee": "ACCOUDOIR ALLEE",
    "ens palette optimisee": "ENSEMBLE PALETTE OPTIMISEE",
    "ensemble palette optimisee": "ENSEMBLE PALETTE OPTIMISEE",
    "ens tablette cocktail": "ENS TABLETTE COCKTAIL",
    "ens tablette repas": "ENS TABLETTE REPAS",
    "ens tetiere": "ENSEMBLE TETIERE",
    "ensemble tetiere": "ENSEMBLE TETIERE",
    "support ecran": "SUPPORT ECRAN ASSEMBLE",
    "support ecran screen display cots": "SUPPORT ECRAN",
    "ens structure fauteuil": "ENS STRUCTURE FAUTEUIL",
    "habillage sous fauteuil": "HABILLAGE SOUS FAUTEUIL",
    "manchette equipee": "MANCHETTE EQUIPEE",
    "renfort tubulaire": "RENFORT TUBULAIRE",
    "structure ottoman horizontale": "Structure Ottoman (horizontale)",
    "support equipe": "SUPPORT EQUIPE",
    "support manchette equipee": "SUPPORT MANCHETTE EQUIPEE",
    "support nfc": "SUPPORT NFC",
    "ceinture de securite": "CEINTURE DE SECURITE",
    "support clamps": "SUPPORT + CLAMPS",
    "ens coque": "ENSEMBLE COQUE",
    "ensemble coque": "ENSEMBLE COQUE",
    "brackets set": "BRACKETS-SET (cables)",
    "sfcu seat function control unit": "SFCU",
    "sfcu": "SFCU",
    "commande actionnement ecu": "COMMANDE ACTIONNEMENT",
    "commande actionnement": "COMMANDE ACTIONNEMENT",
    "ecran screen display cots": "ECRAN 17,3 INCH PNR 00-5155-02",
    "ecran 00 5136 51 rev f seat power box 4 spb4": "00-5136-51 Rev F Seat Power Box 4 (SPB4)",
    "powerbox": "00-5136-51 Rev F Seat Power Box 4 (SPB4)",
    "remote extender unit": "REMOTE EXTENDER UNIT 3 (REU3)",
    "coussin tetiere": "COUSSIN TETIERE",
    "ens coussin assise": "ENS COUSSIN ASSISE",
    "ens coussin dossier version tetiere": "ENS COUSSIN DOSSIER VERSION TETIERE",
    "enscoussin dossier version tetiere": "ENS COUSSIN DOSSIER VERSION TETIERE",
    "ens coussin dossier": "ENS COUSSIN DOSSIER",
    "capot nfc": "CAPOT NFC",
    "ens structure fixe": "ENSEMBLE STRUCTURE FIXE",
    "siege": "SEAT_TOTAL",
}

PACKAGING_MATERIALS = {
    "bois",
    "carton",
    "film plastique",
    "mousse",
    "palette",
    "papier bulle",
    "papier gaufre",
    "papier gaufre",
    "papier intercalaires",
    "papier intercalaire",
    "papier kraft",
}

MATERIAL_FAMILIES = {
    "aluminium": {"a2017", "a2024", "a2075", "a5086", "a6060", "alu", "70 al 6000 30 analog pcb"},
    "steel": {"acier", "inox", "15cdv6", "30ncd16", "30ncd6", "35nc6", "z10cnt18", "4140 uns g41400", "50 inox 50 pa66", "80 inox 20 nylon"},
    "copper": {"alliage cu", "cable model"},
    "leather": {"ultra leather 330", "cuir 850"},
    "textile_foam_polyethylene": {"tissus 300", "tissus 600", "velour", "velours", "frmc55", "mousse"},
    "textile": {"tissus 300", "tissus 600", "velour", "velours", "velcro"},
    "foam": {"frmc55", "mousse"},
    "plastic": {
        "plastique",
        "ertalon",
        "kydex",
        "kydex 5555",
        "nylon",
        "polyamide 6 6",
        "copolimer lexan fst 9705",
        "lexan fst 9705",
        "xhr6006",
        "polychloroprene",
        "caoutchouc",
        "50 inox 50 pa66",
    },
    "composite": {"panneau nida lamina ep12 7", "resine br623 p4", "nidafic ecar", "prepreg", "film colle"},
    "electronics": {
        "screen display cots",
        "power box cots",
        "keyboard glo market for apos u",
        "50 ptfe 50 analog pcb",
        "70 al 6000 30 analog pcb",
        "diode cots",
    },
}


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def numeric(value: Any) -> float | None:
    if value in (None, "", "#N/A", "#REF!"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + ord(ch.upper()) - 64
    return max(index - 1, 0)


def xlsx_rows(path: Path) -> dict[str, list[list[Any]]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", XLSX_NS):
                shared_strings.append("".join(text.text or "" for text in item.findall(".//a:t", XLSX_NS)))

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib.get("Id"): rel.attrib.get("Target", "")
            for rel in rels
            if rel.tag.endswith("Relationship")
        }
        sheets: dict[str, list[list[Any]]] = {}
        rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in workbook.findall(".//a:sheet", XLSX_NS):
            name = sheet.attrib.get("name") or ""
            rel_id = sheet.attrib.get(rel_ns)
            target = rel_targets.get(rel_id or "", "")
            if not target:
                continue
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            target = target.replace("\\", "/")
            root = ET.fromstring(zf.read(target))
            rows: list[list[Any]] = []
            for row in root.findall(".//a:sheetData/a:row", XLSX_NS):
                values: list[Any] = []
                for cell in row.findall("a:c", XLSX_NS):
                    idx = col_index(cell.attrib.get("r", "A1"))
                    while len(values) <= idx:
                        values.append("")
                    value = ""
                    inline = cell.find("a:is", XLSX_NS)
                    if inline is not None:
                        value = "".join(text.text or "" for text in inline.findall(".//a:t", XLSX_NS))
                    else:
                        node = cell.find("a:v", XLSX_NS)
                        if node is not None and node.text is not None:
                            value = node.text
                            if cell.attrib.get("t") == "s":
                                try:
                                    value = shared_strings[int(float(value))]
                                except (ValueError, IndexError):
                                    pass
                    values[idx] = value
                rows.append(values)
            sheets[name] = rows
    return sheets


def cell(row: list[Any], index: int) -> Any:
    return row[index] if index < len(row) else ""


def parse_bom(sheets: dict[str, list[list[Any]]]) -> tuple[dict[tuple[str, str], float], dict[str, float], dict[str, float], dict[str, str]]:
    rows = sheets.get("BOM", [])
    if not rows:
        raise ValueError("BOM sheet not found in quantity_material.xlsx")

    header = [norm(value) for value in rows[0]]
    equipment_idx = header.index("equipement flux")
    material_idx = header.index("matiere")
    mass_idx = header.index("quantite par siege kg kwh pour energie")

    by_equipment_material: dict[tuple[str, str], float] = defaultdict(float)
    by_equipment_total: dict[str, float] = defaultdict(float)
    by_material_total: dict[str, float] = defaultdict(float)
    equipment_display: dict[str, str] = {}

    for row in rows[1:]:
        equipment = str(cell(row, equipment_idx) or "").strip()
        material = str(cell(row, material_idx) or "").strip()
        mass = numeric(cell(row, mass_idx))
        if not equipment or not material or mass is None or mass <= 0:
            continue
        equipment_key = norm(equipment)
        material_key = norm(material)
        equipment_display[equipment_key] = equipment
        by_equipment_material[(equipment_key, material_key)] += mass
        by_equipment_total[equipment_key] += mass
        if material_key not in PACKAGING_MATERIALS:
            by_material_total[material_key] += mass

    return dict(by_equipment_material), dict(by_equipment_total), dict(by_material_total), equipment_display


def equipment_for_system(system: str, equipment_display: dict[str, str]) -> tuple[str | None, str, str]:
    system_key = norm(system)
    if system_key in SYSTEM_ALIASES:
        alias = SYSTEM_ALIASES[system_key]
        if alias == "SEAT_TOTAL":
            return None, alias, "seat_total"
        return norm(alias), alias, "manual_alias"
    if system_key in equipment_display:
        return system_key, equipment_display[system_key], "exact_name"
    for equipment_key, equipment_name in equipment_display.items():
        if system_key and (system_key in equipment_key or equipment_key in system_key):
            return equipment_key, equipment_name, "fuzzy_name"
    return None, "", "no_equipment_match"


def component_material_candidates(component: str, raw_materials: list[Any]) -> tuple[list[str], list[str], str]:
    text = norm(component)
    raw_text = norm(" ".join(str(value) for value in raw_materials or []))
    candidates: list[str] = []
    families: list[str] = []

    exact_rules = [
        (r"\ba5086\b", "a5086"),
        (r"\ba2017\b", "a2017"),
        (r"\ba2024\b", "a2024"),
        (r"\ba2075\b", "a2075"),
        (r"\ba6060\b", "a6060"),
        (r"\b15cdv6\b", "15cdv6"),
        (r"\b30ncd6\b|\b30ncd16\b", "30ncd16"),
        (r"\b35nc6\b", "35nc6"),
        (r"\bz10cnt18\b", "z10cnt18"),
        (r"\b4140\b", "4140 uns g41400"),
        (r"\binox\b", "inox"),
        (r"\bacier\b|\bsteel\b", "acier"),
        (r"alliage cu|cuivre", "alliage cu"),
        (r"film decor aerfilm|aer\s*film|aerfilm", "film decor aerfilm ep0 33 714g m2"),
        (r"airvolt", "airvolt laminat"),
        (r"frmc55|polyurethane", "frmc55"),
        (r"ertalon", "ertalon"),
        (r"kydex", "kydex"),
        (r"kydex", "kydex 5555"),
        (r"lexan", "copolimer lexan fst 9705"),
        (r"nylon", "nylon"),
        (r"polyamide", "polyamide 6 6"),
        (r"caoutchouc", "caoutchouc"),
        (r"polychloroprene", "polychloroprene"),
        (r"resine br623", "resine br623 p4"),
        (r"silicone", "silicone 50 shore"),
        (r"ultra leather|cuir", "ultra leather 330"),
        (r"cuir", "cuir 850"),
        (r"velcro", "velcro"),
        (r"velours|velour", "velour"),
        (r"velours|velour", "velours"),
        (r"nida", "panneau nida lamina ep12 7"),
        (r"powerbox|power box", "power box cots"),
        (r"display|ecran", "screen display cots"),
        (r"clavier|keyboard|sfcu", "keyboard glo market for apos u"),
        (r"telecommande|remote", "50 ptfe 50 analog pcb"),
        (r"commande actionnement|ecu", "70 al 6000 30 analog pcb"),
        (r"ife boitier", "70 al 6000 30 analog pcb"),
        (r"cables|brackets", "cable model"),
        (r"lightning|lighting", "diode cots"),
        (r"support clamps|clamps", "50 inox 50 pa66"),
        (r"ceinture", "80 inox 20 nylon"),
    ]
    for pattern, material in exact_rules:
        if re.search(pattern, text):
            candidates.append(material)

    family_rules = [
        (r"65 aluminium|\baluminium\b|\balu\b", "aluminium"),
        (r"tissu|mousse|polyethylene|polyethylene", "textile_foam_polyethylene"),
        (r"moulage plastique|plastique|plastic", "plastic"),
        (r"autre.*cuir|cuir synthetique", "leather"),
        (r"titane|fibre de carbone|carbone|composite", "composite"),
        (r"electronics|electrical", "electronics"),
    ]
    for pattern, family in family_rules:
        if re.search(pattern, text):
            families.append(family)

    if not families:
        if "aluminium" in raw_text:
            families.append("aluminium")
        if "steel" in raw_text:
            families.append("steel")
        if "engineering plastic" in raw_text:
            families.append("plastic")
        if "textile" in raw_text or "foam" in raw_text:
            families.append("textile_foam_polyethylene")
        if "leather" in raw_text:
            families.append("leather")
        if "composite" in raw_text:
            families.append("composite")

    if text in {"aluminium", "alu"}:
        candidates = []
    if text in {"acier", "steel"}:
        candidates = ["acier"]
    if text in {"tissu"}:
        candidates = []
        families = ["textile"]

    candidates = list(dict.fromkeys(candidates))
    families = list(dict.fromkeys(families))
    label = ", ".join(candidates + [f"family:{family}" for family in families]) or "no_material_match"
    return candidates, families, label


def family_sum(equipment_key: str | None, family: str, by_equipment_material: dict[tuple[str, str], float], by_material_total: dict[str, float]) -> tuple[float | None, int]:
    materials = MATERIAL_FAMILIES.get(family, set())
    if not materials:
        return None, 0
    total = 0.0
    hits = 0
    if equipment_key:
        for material in materials:
            value = by_equipment_material.get((equipment_key, material))
            if value:
                total += value
                hits += 1
    else:
        for material in materials:
            value = by_material_total.get(material)
            if value:
                total += value
                hits += 1
    return (total, hits) if hits else (None, 0)


def mixed_material_split(
    equipment_key: str | None,
    component: str,
    by_equipment_material: dict[tuple[str, str], float],
) -> dict[str, Any] | None:
    if not equipment_key:
        return None
    text = norm(component)
    split_rules = [
        (
            "80 inox 20 nylon",
            [
                (r"acier|inox|steel", 0.80, "steel share of 80%INOX 20%Nylon"),
                (r"nylon|pa66|polyamide|plastique", 0.20, "nylon share of 80%INOX 20%Nylon"),
            ],
        ),
        (
            "50 inox 50 pa66",
            [
                (r"acier|inox|steel", 0.50, "steel share of 50% INOX 50% PA66"),
                (r"nylon|pa66|polyamide|plastique", 0.50, "PA66 share of 50% INOX 50% PA66"),
            ],
        ),
    ]
    for material, rules in split_rules:
        value = by_equipment_material.get((equipment_key, material))
        if not value:
            continue
        for pattern, share, label in rules:
            if re.search(pattern, text):
                return {
                    "mass_kg": value * share,
                    "material": material,
                    "label": label,
                }
    return None


def seat_total(by_material_total: dict[str, float]) -> float:
    return sum(value for material, value in by_material_total.items() if material not in PACKAGING_MATERIALS)


def percent_from_component(component: str) -> float | None:
    match = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", component)
    if not match:
        return None
    return float(match.group(1).replace(",", ".")) / 100.0


def estimate_mass(
    record: dict[str, Any],
    by_equipment_material: dict[tuple[str, str], float],
    by_equipment_total: dict[str, float],
    by_material_total: dict[str, float],
    equipment_display: dict[str, str],
    total_seat_mass: float,
) -> dict[str, Any]:
    equipment_key, equipment_name, equipment_method = equipment_for_system(str(record.get("system") or ""), equipment_display)
    candidates, families, material_match = component_material_candidates(str(record.get("component") or ""), record.get("raw_materials") or [])
    existing = numeric(record.get("mass_kg"))
    pct = percent_from_component(str(record.get("component") or ""))

    if pct is not None:
        return {
            "mass_kg": total_seat_mass * pct,
            "method": "percentage_of_bom_material_total",
            "confidence": "medium",
            "source": MASS_WORKBOOK.as_posix(),
            "equipment_match": "SEAT_TOTAL",
            "material_match": f"{pct:.0%} of total non-packaging BOM mass",
        }

    if equipment_key:
        mixed = mixed_material_split(equipment_key, str(record.get("component") or ""), by_equipment_material)
        if mixed is not None:
            return {
                "mass_kg": mixed["mass_kg"],
                "method": "bom_mixed_material_share",
                "confidence": "medium_high",
                "source": MASS_WORKBOOK.as_posix(),
                "equipment_match": equipment_name,
                "material_match": mixed["label"],
            }
        for material in candidates:
            value = by_equipment_material.get((equipment_key, material))
            if value is not None:
                return {
                    "mass_kg": value,
                    "method": "bom_exact_system_material",
                    "confidence": "high",
                    "source": MASS_WORKBOOK.as_posix(),
                    "equipment_match": equipment_name,
                    "material_match": material,
                }
        for family in families:
            value, hits = family_sum(equipment_key, family, by_equipment_material, by_material_total)
            if value is not None:
                return {
                    "mass_kg": value,
                    "method": "bom_system_material_family_sum",
                    "confidence": "medium_high" if hits > 1 else "medium",
                    "source": MASS_WORKBOOK.as_posix(),
                    "equipment_match": equipment_name,
                    "material_match": f"{family} ({hits} BOM material rows)",
                }
        if not candidates and not families and equipment_key in by_equipment_total:
            return {
                "mass_kg": by_equipment_total[equipment_key],
                "method": "bom_equipment_total_no_material_split",
                "confidence": "medium",
                "source": MASS_WORKBOOK.as_posix(),
                "equipment_match": equipment_name,
                "material_match": "whole equipment total",
            }

    for material in candidates:
        value = by_material_total.get(material)
        if value is not None:
            return {
                "mass_kg": value,
                "method": "bom_global_material_total",
                "confidence": "medium_low",
                "source": MASS_WORKBOOK.as_posix(),
                "equipment_match": equipment_method,
                "material_match": material,
            }
    for family in families:
        value, hits = family_sum(None, family, by_equipment_material, by_material_total)
        if value is not None:
            return {
                "mass_kg": value,
                "method": "bom_global_material_family_sum",
                "confidence": "low",
                "source": MASS_WORKBOOK.as_posix(),
                "equipment_match": equipment_method,
                "material_match": f"{family} ({hits} BOM material rows)",
            }

    if existing is not None and existing > 0:
        return {
            "mass_kg": existing,
            "method": "existing_nonzero_json_mass",
            "confidence": "medium_low",
            "source": INPUT_JSON.as_posix(),
            "equipment_match": equipment_method,
            "material_match": material_match,
        }

    return {
        "mass_kg": None,
        "method": "not_estimated",
        "confidence": "none",
        "source": "",
        "equipment_match": equipment_method,
        "material_match": material_match,
    }


def main() -> None:
    if not MASS_WORKBOOK.exists():
        raise FileNotFoundError(MASS_WORKBOOK)
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = source.get("records") or []
    sheets = xlsx_rows(MASS_WORKBOOK)
    by_equipment_material, by_equipment_total, by_material_total, equipment_display = parse_bom(sheets)
    total_seat_mass = seat_total(by_material_total)

    out = copy.deepcopy(source)
    out_records = out.get("records") or []
    estimate_rows: list[dict[str, Any]] = []
    changed = 0

    for index, record in enumerate(out_records, start=1):
        before = numeric(record.get("mass_kg"))
        estimate = estimate_mass(
            record,
            by_equipment_material,
            by_equipment_total,
            by_material_total,
            equipment_display,
            total_seat_mass,
        )
        if estimate["mass_kg"] is not None:
            record["mass_kg"] = round(float(estimate["mass_kg"]), 9)
            record["mass_status"] = "estimated" if estimate["method"] != "existing_nonzero_json_mass" else "provided_existing"
            record["mass_estimation_method"] = estimate["method"]
            record["mass_source"] = estimate["source"]
            record["mass_confidence"] = estimate["confidence"]
            record["mass_equipment_match"] = estimate["equipment_match"]
            record["mass_material_match"] = estimate["material_match"]
        else:
            record["mass_kg"] = None
            record["mass_status"] = "missing_after_estimation"
            record["mass_estimation_method"] = estimate["method"]
            record["mass_confidence"] = estimate["confidence"]
            record["mass_equipment_match"] = estimate["equipment_match"]
            record["mass_material_match"] = estimate["material_match"]
        if before != numeric(record.get("mass_kg")):
            changed += 1
        estimate_rows.append(
            {
                "record_index": index,
                "system": record.get("system", ""),
                "component": record.get("component", ""),
                "mass_kg_before": "" if before is None else before,
                "mass_kg_after": "" if record.get("mass_kg") is None else record.get("mass_kg"),
                "mass_status": record.get("mass_status", ""),
                "method": record.get("mass_estimation_method", ""),
                "confidence": record.get("mass_confidence", ""),
                "equipment_match": record.get("mass_equipment_match", ""),
                "material_match": record.get("mass_material_match", ""),
                "source": record.get("mass_source", ""),
            }
        )

    out.setdefault("_meta", {})
    out["_meta"]["mass_estimation"] = {
        "source_workbook": MASS_WORKBOOK.as_posix(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "script": Path(__file__).as_posix(),
        "total_non_packaging_bom_mass_kg": round(total_seat_mass, 9),
        "records_changed": changed,
    }
    OUTPUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "record_index",
        "system",
        "component",
        "mass_kg_before",
        "mass_kg_after",
        "mass_status",
        "method",
        "confidence",
        "equipment_match",
        "material_match",
        "source",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(estimate_rows)

    methods = Counter(row["method"] for row in estimate_rows)
    confidence = Counter(row["confidence"] for row in estimate_rows)
    missing = [row for row in estimate_rows if not row["mass_kg_after"]]
    lines = [
        "# Mass estimation for output8_GEO_normalized_corrected.json",
        "",
        f"- Input JSON: `{INPUT_JSON.as_posix()}`",
        f"- Workbook source: `{MASS_WORKBOOK.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Detail CSV: `{OUTPUT_CSV.as_posix()}`",
        f"- Non-packaging BOM mass used as seat-total fallback: `{total_seat_mass:.6f} kg`",
        "",
        "## Coverage",
        "",
        f"- Records: {len(estimate_rows)}",
        f"- Records with mass after estimation: {len(estimate_rows) - len(missing)}",
        f"- Records still missing mass: {len(missing)}",
        f"- Records whose mass value changed: {changed}",
        "",
        "## Methods",
        "",
    ]
    for method, count in methods.most_common():
        lines.append(f"- `{method}`: {count}")
    lines += ["", "## Confidence", ""]
    for key, count in confidence.most_common():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Remaining Missing", ""]
    if missing:
        for row in missing[:30]:
            lines.append(f"- R{row['record_index']}: {row['system']} / {row['component']} ({row['material_match']})")
    else:
        lines.append("- None.")
    lines += [
        "",
        "## Interpretation",
        "",
        "High confidence means an exact system + material mass was found in the LCA BOM. "
        "Medium confidence usually means a material-family sum or whole-equipment fallback. "
        "Low confidence global fallbacks should be reviewed before quantitative stress tests.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {OUTPUT_CSV}")
    print(f"[OK] wrote {REPORT_MD}")
    print(f"[INFO] records={len(estimate_rows)} with_mass={len(estimate_rows)-len(missing)} missing={len(missing)} changed={changed}")
    print("[INFO] methods=" + ", ".join(f"{key}:{value}" for key, value in methods.most_common()))


if __name__ == "__main__":
    main()
