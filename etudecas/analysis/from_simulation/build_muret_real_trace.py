"""Prepare a source-bound investigation from Muret back to production inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from time import monotonic

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string, get_column_letter


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "etudecas/artifacts/testing"
SOURCE = ROOT / "etudecas/data/source"
LINKED = ARTIFACTS / "parcours_arrivees_20261112/routes/dataset_v2.json"
LINKED_MANIFEST = LINKED.with_name("extraction_manifest_v2.json")
BASELINE_MANIFEST = ARTIFACTS / "donnees_reliees_20261112/extractor/extraction_manifest.json"
DEFAULT_OUTPUT = ARTIFACTS / "remontee_muret_reel_20261119/data"
PRODUCTS = {
    "268967": {"factory": "1430", "packaging": "333362"},
    "268091": {"factory": "1810", "packaging": "338929"},
}
TABLES = ("stocks", "opening_stocks", "movements", "mrp", "opening_orders", "lot_rules", "policies")
MOVEMENT_FIELDS = ("divers", "inbound", "outbound", "scan3")
ONE_WEEK = timedelta(days=7)
ONE_DAY = timedelta(days=1)


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def dec(value) -> Decimal:
    return Decimal(str(value))


def json_number(value: Decimal | None):
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def observed_sum(rows: list[dict], name: str) -> Decimal | None:
    """A missing row, cell, or unit remains unknown."""
    if not rows or any(row.get(name) is None or row.get("factor") is None for row in rows):
        return None
    units = {row.get("canonical_unit") for row in rows}
    if None in units or len(units) != 1:
        raise ValueError(f"Independent units in {name}")
    return sum((dec(row[name]) * dec(row["factor"]) for row in rows), Decimal(0))


def linked_dataset(path: Path, route_manifest: Path, extraction_manifest: Path, inputs: dict[Path, str]):
    for file in (path, route_manifest, extraction_manifest, Path(__file__)):
        inputs[file] = sha(file)
    routes = read_json(route_manifest)
    extraction = read_json(extraction_manifest)
    if routes["dataset_sha256"] != inputs[path] or routes["baseline_sha256"] != extraction["dataset_sha256"]:
        raise ValueError("The source dataset and its two manifests must correspond")
    for manifest in (routes, extraction):
        for name, expected in manifest["input_sha256"].items():
            file = ROOT / name
            actual = inputs[file] if file in inputs else sha(file)
            if actual != expected:
                raise ValueError(f"Source differs from the linked extraction: {name}")
            inputs[file] = actual
    data = read_json(path)
    if data["schema"] != "etudecas.linked_industrial.v1":
        raise ValueError("Unsupported linked dataset")
    for entry in data["sources"].values():
        if inputs.get(SOURCE / entry["file"]) != entry["sha256"]:
            raise ValueError(f"Unbound workbook: {entry['file']}")
    return data


def week_of(marker: str) -> str:
    source_day = date.fromisoformat(marker)
    if source_day.weekday() != 6:
        raise ValueError(f"Expected a Sunday source bucket, got {marker}")
    return (source_day + ONE_DAY).isoformat()


def selected_pair_data(data: dict, wanted: set[tuple[str, str]]):
    pairs = {
        f"{site}/{item}": dict(site=site, item=item, **{table: [] for table in TABLES})
        for site, item in sorted(wanted)
    }
    for table in TABLES:
        for row in data["tables"][table]:
            key = f"{row['site']}/{row['item']}"
            if key not in pairs:
                continue
            record = dict(row)
            if table in ("movements", "mrp"):
                record["week_start"] = week_of(row["date"])
            pairs[key][table].append(record)
        for pair in pairs.values():
            pair[table].sort(key=lambda row: (
                row.get("date") or row.get("delivery_date") or "",
                row.get("version") or "", row["row"]))
    return pairs


def read_bom_cells(data: dict, productions: dict[str, str]) -> dict[str, list[dict]]:
    """Enrich checked BOM rows with real classifications from column D."""
    all_boms = defaultdict(list)
    for output, site in productions.items():
        key = f"bom_{output}"
        rows = [r for r in data["tables"]["bom"] if r["source"] == key and r["parent"] == output]
        if not rows:
            continue
        source = data["sources"][key]
        columns = {name: column_index_from_string(column) for name, column in source["columns"].items()}
        category_column = columns["item"] + 1
        book = load_workbook(SOURCE / source["file"], read_only=True, data_only=True)
        try:
            positions = {r["row"]: r for r in rows}
            for i, values in enumerate(book[source["sheet"]].iter_rows(
                    max_row=max(positions), max_col=max(columns.values()), values_only=True), 1):
                if i not in positions:
                    continue
                row = positions[i]
                parent, base_qty, item, quantity = (values[columns[field]-1]
                    for field in ("parent", "base_qty", "item", "qty"))
                category = values[category_column-1]
                if (str(parent), str(item), base_qty, quantity) != (
                        row["parent"], row["item"], row["base_qty"], row["qty"]):
                    raise ValueError(f"BOM source values differ at {source['file']}!A{i}:F{i}")
                if row["factor"] is None or not row["base_qty"]:
                    raise ValueError(f"Missing calculation unit in BOM {row['id']}")
                kind = {
                    "mp": "matière",
                    "pack": "emballage",
                    "sf": "semi-fini",
                }.get(str(category).casefold(), "type source indéterminé")
                if row["item"] in {"693055", "773474"}:
                    kind = "semi-fini"
                output_unit, output_factor = {"UN": ("UN", 1), "G": ("KG", "0.001"), "KG": ("KG", 1)}[
                    row["base_unit"]]
                per_output = dec(row["qty"]) * dec(row["factor"]) / (
                    dec(row["base_qty"]) * dec(output_factor))
                all_boms[output].append(dict(
                    item=row["item"], site=site, kind=kind, source_kind=category,
                    qty_per_pf=json_number(per_output) if output_unit == "UN" else None,
                    qty_per_output=json_number(per_output), output_unit=output_unit, unit=row["canonical_unit"],
                    bom_id=row["id"], source=row["source"], row=row["row"],
                    qty=row["qty"], source_unit=row["unit"], base_qty=row["base_qty"],
                    base_unit=row["base_unit"], category_cell=f"{get_column_letter(category_column)}{i}",
                ))
        finally:
            book.close()
    return dict(all_boms)


def index_by(rows: list[dict], field: str) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for row in rows:
        index[row[field]].append(row)
    return index


def ids(rows: list[dict]) -> list[str]:
    return [row["id"] for row in rows]


def single_photo(rows: list[dict]) -> Decimal | None:
    # Two photos at the same date do not prove a combined quantity.
    return observed_sum(rows, "qty") if len(rows) == 1 else None


def build_weeks(product: dict, depot: dict, factory_components: dict[str, list[dict]]) -> list[dict]:
    photos = index_by(depot["stocks"], "date")
    movements = index_by(depot["movements"], "week_start")
    demands = index_by(product["demand_actual"], "date")
    components = {item: index_by(rows, "week_start") for item, rows in factory_components.items()}
    packaging_spec, = (r for r in product["components"] if r["item"] == product["packaging"])
    packaging_ratio = dec(packaging_spec["qty_per_pf"])
    if packaging_spec["unit"] != "UN" or not packaging_ratio > 0:
        raise ValueError("The chosen packaging observation needs a whole-unit BOM basis")

    result = []
    week = date(2024, 12, 30)
    while week.year <= 2025:
        start = week.isoformat()
        end = (week + ONE_WEEK - ONE_DAY).isoformat()
        closing = (week + ONE_WEEK).isoformat()
        opening_rows, closing_rows = photos[start], photos[closing]
        opening, close = single_photo(opening_rows), single_photo(closing_rows)
        change = close - opening if opening is not None and close is not None else None
        movement = {field: observed_sum(movements[start], field) for field in MOVEMENT_FIELDS}
        total = sum(movement.values()) if all(q is not None for q in movement.values()) else None
        residual = change - total if change is not None and total is not None else None
        raw_demand = observed_sum(demands[start], "qty")
        demand = -raw_demand if raw_demand is not None else None
        # A stock bridge needs both stock photos and a documented signed correction.
        # It treats signed recorded demand as the client movement in an explicit scenario.
        divers = movement["divers"]
        inbound_condition = (change - divers + demand
            if change is not None and total is not None and demand is not None else None)
        package_rows = components[product["packaging"]][start]
        package_scan = observed_sum(package_rows, "scan3")
        package_withdrawals = -package_scan if package_scan is not None else None
        estimated = package_withdrawals / packaging_ratio if package_withdrawals is not None else None
        component_week = {}
        for component in product["components"]:
            item = component["item"]
            records = components[item][start]
            theoretical = dec(component["qty_per_pf"]) * estimated if estimated is not None else None
            component_week[item] = dict(
                unit=component["unit"], scan3=json_number(observed_sum(records, "scan3")),
                other_outbound=json_number(observed_sum(records, "outbound")),
                theoretical_from_packaging=json_number(theoretical), movement_ids=ids(records),
            )
        result.append(dict(
            start=start, end=end, stock_end_date=closing,
            crosses_year_boundary=week.year != 2025 or (week + ONE_WEEK - ONE_DAY).year != 2025,
            stock_start=json_number(opening), stock_end=json_number(close),
            stock_start_ids=ids(opening_rows), stock_end_ids=ids(closing_rows),
            stock_change=json_number(change), movement_ids=ids(movements[start]),
            movement={k: json_number(v) for k,v in movement.items()},
            movement_sum=json_number(total), balance_residual=json_number(residual),
            raw_demand=json_number(raw_demand), demand=json_number(demand),
            demand_ids=ids(demands[start]), conditional_inbound=json_number(inbound_condition),
            packaging_withdrawals=json_number(package_withdrawals),
            estimated_production=json_number(estimated), packaging_movement_ids=ids(package_rows),
            components=component_week,
        ))
        week += ONE_WEEK
    return result


def build_payload(data: dict) -> dict:
    boms = read_bom_cells(data, {
        **{pf: info["factory"] for pf,info in PRODUCTS.items()}, "773474": "1450",
    })
    wanted = {(site, pf) for pf, info in PRODUCTS.items() for site in ("1920", info["factory"])}
    wanted.update((component["site"], component["item"]) for rows in boms.values() for component in rows)
    # Documented internal transfer is a possible line of inquiry, not a shipment identity.
    transfer_kinds = {"documented_route", "reconciled_legacy_route"}
    changed = True
    while changed:
        before = len(wanted)
        wanted.update((route["source_site"], route["item"]) for route in data["routes"]
            if route["source_site"] and (route["destination_site"], route["item"]) in wanted
            and route["relation"] in transfer_kinds)
        changed = len(wanted) != before
    pairs = selected_pair_data(data, wanted)
    products = {}
    for pf, info in PRODUCTS.items():
        product = dict(info, components=boms[pf], **{
            table: [row for row in data["tables"][table] if row["item"] == pf]
            for table in ("demand_actual", "demand_forecast")
        })
        product["weeks"] = build_weeks(product, pairs[f"1920/{pf}"], {
            row["item"]: pairs[f"{row['site']}/{row['item']}"]["movements"] for row in boms[pf]
        })
        products[pf] = product
    return dict(
        schema="etudecas.muret_real_trace.v1", products=products, pairs=pairs,
        sources=data["sources"], sites=data["sites"],
        routes=[route for route in data["routes"] if (route["destination_site"], route["item"]) in wanted],
        boms=boms, semantics={
            "movement": "Mouvement hebdomadaire signé. Le dimanche source repère la semaine du lundi suivant.",
            "muret_outbound": "Sorties est le mouvement net signé de la colonne I à Muret. Le journal des départs clients bruts manque.",
            "stock_balance": "Stock physique final moins stock physique initial, puis retrait de la somme signée de Divers, Entrées, Sorties et Scan3.",
            "conditional_inbound": "Variation du stock moins Divers plus demande signée retournée. Ce bilan suppose que la demande est entièrement servie dans sa semaine et que les autres flux sont couverts par Divers.",
            "packaging": "Prélèvement net Scan3 des étuis, de signe inversé, divisé par le coefficient de la nomenclature. Estimation du conditionnement, avec sa provenance.",
            "component": "Scan3 et Sorties hors Scan3 sont deux mouvements distincts. La quantité théorique est dérivée de la nomenclature et de l’estimation étuis.",
            "mrp": "La version indique la date du calcul et la semaine indique l’échéance. Les lignes MRP restent des plans ou des états datés distincts des mouvements physiques.",
            "orders": "Carnet partiel à dates de livraison et disponibilité prévues. Création et numéro d’ordre inconnus.",
            "links": "Les liens comparent un article, un site, une période, une route documentée ou une nomenclature. Le rattachement réel entre lots et expéditions reste inconnu.",
            "null": "Une valeur absente est inconnue. Les zéros renseignés restent des observations.",
        },
    )


def source_oracles(payload: dict, data: dict) -> list[dict]:
    """Direct checks for the two representative weeks using raw workbook cells."""
    oracle_rows = [
        ("268967", "2025-03-17", "1920", 808, 83, 72, 66, 854, "333362", 49250),
        ("268091", "2025-10-13", "1920", 785, 57, 58, 43, 967, "338929", 249600),
    ]

    checks = []
    for pf, week, site, move_row, open_row, close_row, demand_row, pack_row, pack_item, pack_qty in oracle_rows:
        record, = (r for r in payload["products"][pf]["weeks"] if r["start"] == week)
        source_cells = {}
        for key, position, max_col in (
            ("movement", move_row, 10), ("stock_current_start", open_row, 8),
            ("stock_current_end", close_row, 8), ("demand_history", demand_row, 3),
        ):
            source = data["sources"][key.split("_start")[0].split("_end")[0]]
            book = load_workbook(SOURCE / source["file"], read_only=True, data_only=True)
            try:
                values, = book[source["sheet"]].iter_rows(min_row=position, max_row=position,
                    max_col=max_col, values_only=True)
                source_cells[key] = values
            finally:
                book.close()
        move, begin, close, requested = (source_cells[key] for key in (
            "movement", "stock_current_start", "stock_current_end", "demand_history"))
        if not (str(move[0]) == str(begin[0]) == str(close[0]) == str(requested[0]) == pf
                and all(str(v) == site for v in (move[3], begin[2], close[2]))):
            raise ValueError(f"Oracle source scope differs for {pf}")
        marker = str(move[4])[:10]
        monday = date.fromisoformat(week)
        if not (date.fromisoformat(marker) + ONE_DAY == monday
                and str(begin[7])[:10] == str(requested[1])[:10] == week
                and str(close[7])[:10] == (monday+ONE_WEEK).isoformat()):
            raise ValueError(f"Oracle source week differs for {pf}")
        expected = (begin[4], close[4], tuple(move[6:10]), requested[2])
        actual = (record["stock_start"], record["stock_end"],
            tuple(record["movement"][k] for k in MOVEMENT_FIELDS), record["raw_demand"])
        if expected != actual or record["balance_residual"] != close[4] - begin[4] - sum(move[6:10]):
            raise ValueError(f"Raw stock and movement check differs for {pf} {week}")
        if record["conditional_inbound"] != close[4] - begin[4] - move[6] - requested[2]:
            raise ValueError(f"Raw conditional stock bridge differs for {pf} {week}")
        if pack_row is not None:
            source = data["sources"]["movement"]
            book = load_workbook(SOURCE / source["file"], read_only=True, data_only=True)
            try:
                values, = book[source["sheet"]].iter_rows(min_row=pack_row, max_row=pack_row,
                    max_col=10, values_only=True)
            finally:
                book.close()
            packaging = (values[0], values[3], str(values[4])[:10], values[9])
            if packaging != (pack_item, PRODUCTS[pf]["factory"], marker, -pack_qty):
                raise ValueError(f"Raw packaging movement differs for {pf} {week}")
            if record["estimated_production"] != pack_qty:
                raise ValueError(f"Estimated packaging differs for {pf} {week}")
        checks.append(dict(product=pf, week=week, passed=True,
            stock_cells=[f"Stocks!E{open_row}",f"Stocks!E{close_row}"],
            movement_cells=f"Feuille1!G{move_row}:J{move_row}",
            demand_cell=f"Historique!C{demand_row}",
            packaging_cell=f"Feuille1!J{pack_row}" if pack_row else None,
            balance_residual=record["balance_residual"], conditional_inbound=record["conditional_inbound"]))
    return checks


def json_dump(path: Path, value: dict):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linked-data", type=Path, default=LINKED)
    parser.add_argument("--route-manifest", type=Path, default=LINKED_MANIFEST)
    parser.add_argument("--extraction-manifest", type=Path, default=BASELINE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ARTIFACTS) or any((out/name).exists() for name in (
            "muret_trace.json", "extraction_manifest.json")):
        raise ValueError("Use a fresh output directory under Etudecas analysis artifacts")
    started = monotonic()
    inputs = {}
    data = linked_dataset(args.linked_data.resolve(), args.route_manifest.resolve(),
        args.extraction_manifest.resolve(), inputs)
    payload = build_payload(data)
    checks = source_oracles(payload, data)
    if not all(sha(path) == signature for path, signature in inputs.items()):
        raise ValueError("Input data changed during extraction")
    out.mkdir(parents=True, exist_ok=True)
    dataset = out / "muret_trace.json"
    json_dump(dataset, payload)
    manifest = dict(
        status="passed", source_stable=True, dataset=dataset.relative_to(ROOT).as_posix(),
        dataset_sha256=sha(dataset), dataset_bytes=dataset.stat().st_size,
        inputs_sha256={p.relative_to(ROOT).as_posix(): h for p,h in inputs.items()},
        pair_count=len(payload["pairs"]),
        week_count={pf:len(row["weeks"]) for pf,row in payload["products"].items()},
        source_oracles=checks, physical_simulation_executed=False,
        elapsed_seconds=monotonic()-started,
    )
    json_dump(out / "extraction_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
