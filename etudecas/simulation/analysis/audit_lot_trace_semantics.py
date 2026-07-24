#!/usr/bin/env python3
"""Audit business semantics of lot genealogy exported by a simulation run."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


EPS = 1e-9
ROOT_CREATION_TYPES = {
    "external_procurement_receipt",
    "opening_production_order",
    "opening_stock",
    "production_output",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit lot identity, contribution and transport semantics.")
    parser.add_argument("--output-root", required=True, help="Simulation run containing data/ lot CSV files.")
    parser.add_argument("--report", default="", help="Markdown report path.")
    parser.add_argument("--max-examples", type=int, default=8)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(round(float(str(value).replace(",", "."))))
    except (TypeError, ValueError):
        return 0


def pct(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.1f}%" if denominator else "n/a"


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    data = [[str(value) for value in row] for row in rows]
    if not data:
        return "_Aucune ligne._"
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(row) + " |" for row in data],
        ]
    )


def walk(adjacency: dict[str, set[str]], root: str) -> set[str]:
    seen: set[str] = set()
    queue: deque[str] = deque([root])
    while queue:
        current = queue.popleft()
        for related in adjacency.get(current, set()):
            if related and related != root and related not in seen:
                seen.add(related)
                queue.append(related)
    return seen


def first_events(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for event in events:
        lot_id = event.get("lot_id", "")
        previous = result.get(lot_id)
        if lot_id and (previous is None or as_int(event.get("day")) < as_int(previous.get("day"))):
            result[lot_id] = event
    return result


def quantile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * ratio)]


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    data_dir = output_root / "data"
    events = read_csv(data_dir / "production_lot_events.csv")
    links = read_csv(data_dir / "production_lot_genealogy.csv")
    creations = first_events(events)
    events_by_lot: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        events_by_lot[event.get("lot_id", "")].append(event)

    children: dict[str, set[str]] = defaultdict(set)
    parents: dict[str, set[str]] = defaultdict(set)
    links_by_child: dict[str, list[dict[str, str]]] = defaultdict(list)
    for link in links:
        parent = link.get("parent_lot_id", "")
        child = link.get("child_lot_id", "")
        if parent and child:
            children[parent].add(child)
            parents[child].add(parent)
            links_by_child[child].append(link)

    event_types = Counter(row.get("event_type", "") for row in events)
    link_types = Counter(row.get("link_type", "") for row in links)

    # Lot identity should be stable after creation.
    node_changes = 0
    item_changes = 0
    uom_changes = 0
    for lot_id, creation in creations.items():
        lot_events = events_by_lot.get(lot_id, [])
        nodes = {row.get("node_id", "") for row in lot_events if row.get("node_id")}
        items = {row.get("item_id", "") for row in lot_events if row.get("item_id")}
        uoms = {row.get("uom", "") for row in lot_events if row.get("uom")}
        node_changes += len(nodes) > 1
        item_changes += len(items) > 1
        uom_changes += len(uoms) > 1

    # Production contribution: the relevant denominator is each BOM item,
    # never the sum of quantities expressed in heterogeneous units.
    production_links = [row for row in links if row.get("link_type") == "production"]
    production_by_child_item: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    production_uoms_by_child: dict[str, set[str]] = defaultdict(set)
    event_uom = {(row.get("lot_id", ""), row.get("item_id", "")): row.get("uom", "") for row in events}
    for link in production_links:
        child = link.get("child_lot_id", "")
        parent_item = link.get("parent_item_id", "")
        production_by_child_item[(child, parent_item)].append(link)
        parent_lot = link.get("parent_lot_id", "")
        uom = event_uom.get((parent_lot, parent_item), "")
        if uom:
            production_uoms_by_child[child].add(uom)

    split_groups = []
    attribution_factors: list[float] = []
    attribution_examples: list[tuple[float, dict[str, str], float, float]] = []
    for rows in production_by_child_item.values():
        unique_lots = {row.get("parent_lot_id", "") for row in rows}
        total = sum(as_float(row.get("parent_qty")) for row in rows)
        if len(unique_lots) <= 1 or total <= EPS:
            continue
        split_groups.append(rows)
        for row in rows:
            parent_qty = as_float(row.get("parent_qty"))
            child_qty = as_float(row.get("child_qty"))
            expected = child_qty * parent_qty / total if total > EPS else 0.0
            factor = child_qty / expected if expected > EPS else math.inf
            if math.isfinite(factor):
                attribution_factors.append(factor)
                attribution_examples.append((factor, row, total, expected))

    mixed_uom_productions = sum(len(uoms) > 1 for uoms in production_uoms_by_child.values())
    split_children = {row.get("child_lot_id", "") for rows in split_groups for row in rows}

    # Transport is currently inferred from receipt day + route + item.
    transport_links = [row for row in links if row.get("link_type") == "transport"]
    transport_groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in transport_links:
        key = (
            row.get("day", ""),
            row.get("parent_node_id", ""),
            row.get("child_node_id", ""),
            row.get("child_item_id", "") or row.get("parent_item_id", ""),
        )
        transport_groups[key].append(row)
    multi_parent_transport_groups = sum(
        len({row.get("parent_lot_id", "") for row in rows}) > 1 for rows in transport_groups.values()
    )
    multi_child_transport_groups = sum(
        len({row.get("child_lot_id", "") for row in rows}) > 1 for rows in transport_groups.values()
    )
    lane_receipt_lots = {
        lot_id for lot_id, event in creations.items() if event.get("event_type") == "lane_receipt"
    }
    unparented_receipts = [
        lot_id
        for lot_id in lane_receipt_lots
        if not any(row.get("link_type") == "transport" for row in links_by_child.get(lot_id, []))
    ]
    customer_receipts = [
        lot_id
        for lot_id in lane_receipt_lots
        if str(creations[lot_id].get("node_id", "")).startswith("C-")
    ]
    mixed_customer_receipts = [
        lot_id
        for lot_id in customer_receipts
        if len(
            {
                row.get("parent_lot_id", "")
                for row in links_by_child.get(lot_id, [])
                if row.get("link_type") == "transport"
            }
        )
        > 1
    ]

    # Exact end-to-end coverage.
    demand_lots = {
        row.get("lot_id", "") for row in events if row.get("event_type") == "demand_service"
    }
    demand_ancestors = set(demand_lots)
    queue = deque(demand_lots)
    while queue:
        child = queue.popleft()
        for parent in parents.get(child, set()):
            if parent not in demand_ancestors:
                demand_ancestors.add(parent)
                queue.append(parent)

    production_lots = [
        lot_id for lot_id, event in creations.items() if event.get("event_type") == "production_output"
    ]
    supplier_lots = [
        lot_id
        for lot_id, event in creations.items()
        if str(event.get("node_id", "")).startswith("SDC-")
        and event.get("event_type") in {"opening_stock", "external_procurement_receipt"}
    ]
    produced_by_item: dict[str, list[str]] = defaultdict(list)
    for lot_id in production_lots:
        produced_by_item[creations[lot_id].get("item_id", "")].append(lot_id)

    max_upstream = (0, "")
    max_downstream = (0, "")
    for lot_id in [*production_lots, *supplier_lots]:
        upstream_count = len(walk(parents, lot_id))
        downstream_count = len(walk(children, lot_id))
        max_upstream = max(max_upstream, (upstream_count, lot_id))
        max_downstream = max(max_downstream, (downstream_count, lot_id))

    per_item_rows = []
    for item_id, lot_ids in sorted(produced_by_item.items()):
        if len(lot_ids) < 10:
            continue
        reached = sum(lot_id in demand_ancestors for lot_id in lot_ids)
        per_item_rows.append([item_id, len(lot_ids), reached, pct(reached, len(lot_ids))])

    attribution_examples.sort(key=lambda value: value[0], reverse=True)
    example_rows = [
        [
            row.get("parent_lot_id", ""),
            row.get("parent_item_id", ""),
            row.get("child_lot_id", ""),
            f"{as_float(row.get('parent_qty')):.1f}",
            f"{total:.1f}",
            f"{expected:.1f}",
            f"x{factor:.1f}",
        ]
        for factor, row, total, expected in attribution_examples[: args.max_examples]
    ]

    report_path = Path(args.report) if args.report else output_root / "reports" / "lot_trace_semantic_diagnostic.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = f"""# Diagnostic semantique de la lotification

## Perimetre
- Run: `{output_root}`
- Lots: **{len(creations):,}**
- Evenements: **{len(events):,}**
- Liens genealogiques: **{len(links):,}**
- Types d'evenements: `{dict(event_types)}`
- Types de liens: `{dict(link_types)}`

## Verdict
La genealogie est structurellement exploitable, mais elle n'est pas encore suffisamment
fiable pour une attribution quantitative MP/PFI -> PF -> client. Le principal defaut est
la propagation d'une contribution de production lorsque plusieurs lots du meme composant
alimentent une campagne. Les transports sont tracables comme flux, mais pas comme voyages
physiques, car le modele ne possede pas d'identifiant d'expedition/consolidation.

## Controle de chaque chemin
- Lots qui changent de noeud sans creation d'un lot enfant: **{node_changes}**
- Lots qui changent d'item: **{item_changes}**
- Lots qui changent d'unite: **{uom_changes}**
- Lots de production atteignant une consommation client: **{sum(lot in demand_ancestors for lot in production_lots)} / {len(production_lots)}** ({pct(sum(lot in demand_ancestors for lot in production_lots), len(production_lots))})
- Lots fournisseur atteignant une consommation client: **{sum(lot in demand_ancestors for lot in supplier_lots)} / {len(supplier_lots)}** ({pct(sum(lot in demand_ancestors for lot in supplier_lots), len(supplier_lots))})
- Plus grande ascendance exacte: **{max_upstream[0]} lots** pour `{max_upstream[1]}`
- Plus grande descendance exacte: **{max_downstream[0]} lots** pour `{max_downstream[1]}`
- Aucun chemin n'atteint la limite technique de 5 000 lots utilisee pour les statistiques.

{markdown_table(["Item produit", "Lots produits", "Atteignent le client", "Couverture"], per_item_rows)}

## Production et contribution quantitative
- Liens de production: **{len(production_links):,}**
- Campagnes/enfants utilisant plusieurs lots pour un meme composant: **{len(split_children):,} / {len(production_lots):,}**
- Groupes enfant-composant repartis sur plusieurs lots: **{len(split_groups):,}**
- Liens dont la contribution est surestimee par l'algorithme d'affichage actuel: **{len(attribution_factors):,}**
- Facteur de surestimation median: **x{statistics.median(attribution_factors):.2f}**
- Facteur p90: **x{quantile(attribution_factors, 0.90):.2f}**
- Productions combinant plusieurs unites BOM: **{mixed_uom_productions:,}**. Une part globale calculee en additionnant G, KG, M et UN n'a pas de sens physique.

La contribution correcte d'un lot composant a un lot produit doit etre calculee par
composant: `quantite du lot consommee / quantite totale de ce composant consommee`,
puis appliquee a la quantite produite. Elle ne doit pas utiliser la somme de tous les
composants de la BOM.

{markdown_table(["Lot parent", "Composant", "Lot produit", "Conso lot", "Conso composant", "PF attribuable", "Surestimation actuelle"], example_rows)}

## Transports
- Liens de transport: **{len(transport_links):,}**
- Groupes d'affichage deduits de `jour reception + origine + destination + item`: **{len(transport_groups):,}**
- Groupes fusionnant plusieurs lots parents: **{multi_parent_transport_groups:,}**
- Groupes produisant plusieurs lots recus: **{multi_child_transport_groups:,}**
- Lots de reception sans parent transport trace: **{len(unparented_receipts):,} / {len(lane_receipt_lots):,}**
- Lots clients melangeant plusieurs lots parents: **{len(mixed_customer_receipts):,} / {len(customer_receipts):,}**

Le regroupement actuel ne represente pas un camion. Il fusionne des flux qui arrivent le
meme jour sur une meme route pour un meme item, mais separe les items qui pourraient etre
dans le meme camion. Il faut ajouter `shipment_id`, `departure_day`, `arrival_day`,
`handling_unit_id` et une regle explicite de consolidation/capacite.

## Identite et nommage
- Les identifiants `LOT-00000001...` sont uniques et continus, mais purement techniques.
- Une reception cree un nouveau `LOT-*`; le numero de lot metier n'est donc pas stable le
  long de la chaine.
- Les libelles melangent vocabulaire metier francais et codes internes anglais
  (`production_output`, `lane_receipt`, `external_procurement_receipt`).
- Le libelle de selection n'affiche pas l'unite, alors que la quantite est affichee.

Le modele devrait distinguer:
1. `business_batch_id`, stable de la production jusqu'au client;
2. `stock_lot_id`, occurrence du lot dans un stock/site;
3. `shipment_id` et `handling_unit_id`, mouvement et contenant logistique.

## Priorites
1. **P0 - Contribution**: corriger la propagation par composant et recalculer les lots mixtes.
2. **P0 - Transport**: modeliser une expedition physique au lieu de l'inferer de la reception.
3. **P1 - Identite**: conserver un identifiant de lot metier stable et separer les occurrences de stock.
4. **P1 - Origines non tracees**: expliciter les {len(unparented_receipts)} receptions agregees/backorders sans parent lot.
5. **P1 - Nommage**: dictionnaire metier francais, unite et dates depart/arrivee dans chaque noeud.
6. **P2 - Historique**: accepter que le fournisseur des stocks initiaux J0 reste inconnu sans historique pre-horizon.
"""
    report_path.write_text(report, encoding="utf-8")
    print(f"[OK] Semantic lot diagnostic: {report_path.resolve()}")


if __name__ == "__main__":
    main()
