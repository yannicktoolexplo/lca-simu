"""Build the offline two-scenario workshop-authorization comparison."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from etudecas.visualization.maps.build_muret_real_trace import script_json


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGIN = date(2025, 1, 1)
ITEM = "item:268967"
SECOND = "FROZEN|M-1430|item:268967|2"
COLORS = ("#324454", "#ad5013", "#006985")


def integer(value):
    qty = Decimal(str(value))
    if not qty.is_finite() or qty < 0 or qty != qty.to_integral_value():
        raise ValueError("Expected a nonnegative physical quantity in whole units")
    return int(qty)


def stamp(day):
    return (ORIGIN + timedelta(days=int(day))).isoformat()


def offset(value):
    return (date.fromisoformat(value) - ORIGIN).days


def build(trial: Path, output: Path, manifest: Path) -> dict:
    inputs = {}

    def read(path, expected=None):
        path = path.resolve()
        relative = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected:
            raise ValueError(f"Fingerprint mismatch: {relative}")
        inputs[path] = digest
        return raw

    proof = json.loads(read(trial))
    if proof["status"] != "completed_qualified_work_authorization_experiment":
        raise ValueError("Expected the qualified authorization experiment")

    def contract(key):
        entry = proof["evidence"][key]
        return json.loads(read(ROOT / entry["path"], entry["sha256"]))

    protocol = contract("protocol")
    review = contract("oracle")
    if (not review["passed"] or not review["source_stable"] or not review["checks"]
            or review["common_days"] != proof["common_comparison_days"] or not review["candidate_only_extension_days"]):
        raise ValueError("Invalid evidence for the common scoring window")
    common_days = review["common_days"]

    def rows(run, file):
        path = run / "data" / file
        relative = path.relative_to(ROOT).as_posix()
        raw = read(path, review["inputs_sha256"][relative])
        return csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))

    def series(run):
        stock = {}
        for row in rows(run, "production_stock_availability_daily.csv"):
            if row["node_id"] == "DC-1920" and row["item_id"] == ITEM:
                day = int(row["day"])
                if day in stock or row["uom"] != "UN":
                    raise ValueError("Expected one stock record per day in units")
                stock[day] = [integer(row[field]) for field in ("physical_qty", "available_qty", "held_qty")]
        demand = defaultdict(lambda: [0, 0])
        for row in rows(run, "production_demand_service_daily.csv"):
            if row["item_id"] == ITEM:
                day = int(row["day"])
                demand[day][0] += integer(row["demand_qty"])
                demand[day][1] += integer(row["served_qty"])
        packaging = defaultdict(int)
        for row in rows(run, "production_component_issues_daily.csv"):
            if all(row[key] == value for key, value in {"node_id": "M-1430", "item_id": ITEM,
                                                       "component_item_id": "item:333362"}.items()):
                if row["component_uom"] != "UN":
                    raise ValueError("Cartons must be reported in units")
                packaging[int(row["day"])] += integer(row["issued_qty"])
        if not set(range(common_days)) <= stock.keys() & demand.keys():
            raise ValueError("Missing stock or client data in the common window")
        return stock, demand, packaging

    def events(case):
        target = case["targets"][SECOND]
        component = case["component_344135"]
        order_id, _ = max(component["genealogy"][SECOND].items(), key=lambda link: integer(link[1]))
        early = component["early"][order_id]
        order = next(entry for entry in component["all_orders"] if entry[0] == order_id)
        result = [dict(date=stamp(early[key]), label=label, qty=integer(order[2]), lot=early["lot"])
                  for key, label in (("placed", "Achat du 344135"), ("physical", "Réception du composant"),
                                     ("available", "Composant libéré"))]
        for event in target["events"]:
            label = {"production_output": "Fabrication du deuxième lot", "lane_ship": "Départ de l’usine",
                     "lane_receipt": "Entrée physique à Muret", "stock_availability_release": "Libération à Muret"}.get(event["event"])
            if label:
                result.append(dict(date=event["date"], label=label, qty=integer(event["quantity"]),
                                   lot=event["lot"], shipment=event["shipment"]))
        return result

    witness_run = ROOT / protocol["witness"]
    candidate_run = ROOT / proof["evidence"]["native"]["path"]
    stocks, demand, packaging = zip(*(series(run) for run in (witness_run, candidate_run.parent)), strict=True)
    cases = [review[key] for key in ("witness", "candidate")]
    scores = [case["scores"][ITEM] for case in cases]
    source_packaging = [{row["date_start"]: row for row in score["weekly"]} for score in scores]
    source_photos = [{row["date"]: row for row in score["photos"]} for score in scores]
    weeks = []
    monday = (7 - ORIGIN.weekday()) % 7
    for start in range(monday, common_days, 7):
        end = min(start + 7, common_days)
        day = stamp(start)
        weekly = [sum(run[j] for j in range(start, end)) for run in packaging]
        physical, available, held = (list(values) for values in zip(*(run[start - 1] for run in stocks), strict=True))
        requested, served = ([sum(run[j][idx] for j in range(start, end)) for run in demand] for idx in (0, 1))
        carton = source_packaging[0].get(day)
        photo = source_photos[0].get(day)
        for idx in range(2):
            carton_compare = source_packaging[idx].get(day)
            photo_compare = source_photos[idx].get(day)
            if (bool(carton) != bool(carton_compare) or bool(photo) != bool(photo_compare)
                    or (carton and (carton["observed"] != carton_compare["observed"]
                                    or weekly[idx] != integer(carton_compare["simulated"])))
                    or (photo and (photo["quantity"] != photo_compare["quantity"]
                                   or physical[idx] != integer(photo_compare["simulated"])))):
                raise ValueError(f"Series diverge from the common-mask oracle on {day}")
        weeks.append(dict(date=day, end=stamp(end - 1),
                          packaging=[integer(carton["observed"]) if carton else None, *weekly],
                          physical=[integer(photo["quantity"]) if photo else None, *physical],
                          available=[None, *available], held=[None, *held],
                          demand=[None, *requested], served=[None, *served],
                          cells=dict(packaging=[carton["cell"]] if carton else [], physical=photo["source_cells"] if photo else [])))
    payload = dict(product=ITEM.split(":")[1], weeks=weeks,
                   colors=COLORS, common_end=stamp(common_days - 1),
                   closure={field: [run[common_days - 1][idx] for run in stocks]
                            for idx, field in enumerate(("physical", "available", "held"))},
                   cases=[dict(label=label, events=events(case), served=integer(case["network"][ITEM]["served"]),
                               weekly_mae=round(Decimal(score["weekly_mae"])), stock_mae=round(Decimal(score["stock_mae"])),
                               order_id=SECOND)
                          for label, case, score in zip(("Lancement 7 avril", "Lancement 14 avril"), cases, scores, strict=True)])
    template = read(HERE / "atelier_comparison.html").decode("utf-8")
    read(Path(__file__))
    if template.count("__ATELIER_DATA__") != 1:
        raise ValueError("Missing standalone template marker")
    html = template.replace("__ATELIER_DATA__", script_json(payload)).encode("utf-8")
    if (len(html) > 250_000 or output.suffix.lower() != ".html" or output.exists() or manifest.exists()
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != sha for path, sha in inputs.items())):
        raise ValueError("Invalid output, input change or size limit exceeded")

    with output.open("xb") as stream:
        stream.write(html)
    report = dict(status="built_offline_report", output=output.resolve().relative_to(ROOT).as_posix(),
                  output_sha256=hashlib.sha256(html).hexdigest(), bytes=len(html), common_days=common_days,
                  weeks=len(weeks), observed_packaging=sum(r["packaging"][0] is not None for r in weeks),
                  observed_physical=sum(r["physical"][0] is not None for r in weeks),
                  inputs_sha256={p.relative_to(ROOT).as_posix(): sha for p, sha in inputs.items()})
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("trial", "output", "manifest"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.trial, args.output, args.manifest), ensure_ascii=False))


if __name__ == "__main__":
    main()
