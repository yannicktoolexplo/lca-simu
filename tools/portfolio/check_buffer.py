"""Comparer un export observé aux douze lignes de l'essai de stock tampon."""
import argparse
import csv
import re
from itertools import product
from pathlib import Path

GUIDE = Path(__file__).with_name("essai-tampon.md")
KEY_FIELDS = ("regime", "stock_initial", "jour")
MEASURES = ("recu", "livre_total", "livre_echeance", "stock_fin", "reliquat")
DAYS = ("J1", "J2", "J3")
REGIMES = {"Nominales": "nominal", "Avec choc": "choc"}


def read_reference():
    """Le tableau quotidien du guide est l'unique liste des valeurs attendues."""
    guide = GUIDE.read_text(encoding="utf-8")
    header = ("| Réceptions | Stock initial | Jour | Reçu | Livré au total | Livré à l’échéance "
              "| Stock utilisable en fin de jour | Demande en retard en fin de jour |")
    _, matched, rows = guide.partition(header + "\n")
    if not matched:
        raise ValueError("Tableau quotidien attendu introuvable. Vérifier son en-tête dans le guide.")
    table = rows.split("\n\n", 1)[0]
    reference = {}
    for line in table.splitlines():
        if not line.startswith("|"):
            continue
        regime, stock, day, *values = [cell.strip() for cell in line.strip("|").split("|")]
        if regime not in REGIMES:
            continue
        key = (REGIMES[regime], stock, day)
        if key in reference:
            raise ValueError(f"Clé répétée dans le guide {key}.")
        reference[key] = dict(zip(MEASURES, map(int, values), strict=True))
    if set(reference) != set(product(REGIMES.values(), ("0", "10"), DAYS)):
        raise ValueError("Les douze lignes attendues du guide sont introuvables.")
    return reference


def read_observed(stream, reference):
    reader = csv.reader(stream, strict=True)
    header = [field.strip() for field in next(reader, [])]
    if len(set(header)) != len(header):
        raise ValueError("En-tête ambigu, colonne répétée.")
    unexpected = set(header) - set(KEY_FIELDS + MEASURES)
    if unexpected:
        raise ValueError(f"Colonnes inconnues {sorted(unexpected)}.")
    for field in KEY_FIELDS:
        if field not in header:
            raise ValueError(f"Preuve manquante, colonne d’identification {field}.")
    observed = {}
    for row in reader:
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError(f"Ligne {reader.line_num}, nombre de colonnes incohérent.")
        cells = dict(zip(header, (value.strip() for value in row)))
        key = tuple(cells[field] for field in KEY_FIELDS)
        if key not in reference or key in observed:
            reason = "répétée" if key in observed else "inconnue ou incomplète"
            raise ValueError(f"Ligne {reader.line_num}, clé {reason} {key}.")
        measures = {}
        for field in MEASURES:
            value = cells.get(field)
            if not value:
                continue
            if not re.fullmatch(r"[0-9]+", value):
                raise ValueError(f"Ligne {reader.line_num}, {field} attend un entier positif ou nul.")
            measures[field] = int(value)
        observed[key] = measures
    return observed


def indicators(observed, regime, stock):
    days = [observed.get((regime, stock, day), {}) for day in DAYS]

    def total(field):
        if all(field in day for day in days):
            return sum(day[field] for day in days)
        return "?"

    return (f"{regime}, stock initial {stock} pièces | échéance {total('livre_echeance')}/15"
            f" | livré fin J3 {total('livre_total')}/15 | retard {total('reliquat')} pièces-jours"
            f" | stock fin J3 {days[-1].get('stock_fin', '?')} pièces")


def compare(reference, observed):
    missing = []
    differences = []
    for key, expected in reference.items():
        regime, stock, day = key
        where = f"{regime}, stock initial {stock}, {day}"
        if key not in observed:
            missing.append(f"{where}, ligne absente")
            continue
        for field, value in expected.items():
            if field not in observed[key]:
                missing.append(f"{where}, {field}")
            elif observed[key][field] != value:
                differences.append(f"{where}, {field} attendu {value}, observé {observed[key][field]}")
    for stock in ("0", "10"):
        for regime in REGIMES.values():
            print(indicators(observed, regime, stock))
    if missing:
        print(f"INCOMPLET — Première preuve manquante : {missing[0]}.")
    if differences:
        print(f"ÉCART — Première divergence : {differences[0]}.")
    if missing or differences:
        return 1
    print("CONFORME — Les 12 lignes concordent en pièces, à tolérance nulle.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="export CSV normalisé, UTF-8, séparateur virgule")
    parser.add_argument("--produit", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not args.produit.strip() or not args.version.strip():
        parser.error("Le produit et la version doivent être renseignés.")
    print(f"{args.produit.strip()} | version {args.version.strip()} | {args.csv}")
    try:
        reference = read_reference()
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Référence de l’essai indisponible. {exc}\n")
    try:
        with args.csv.open(encoding="utf-8-sig", newline="") as stream:
            observed = read_observed(stream, reference)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"EXPORT INEXPLOITABLE — {exc}")
        return 2
    return compare(reference, observed)


if __name__ == "__main__":
    raise SystemExit(main())
