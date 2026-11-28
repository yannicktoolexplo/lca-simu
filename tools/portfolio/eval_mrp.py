"""Produire le dossier à examiner puis noter séparément la réponse JSON."""
import argparse
import json
import sys
from pathlib import Path


DIR = Path(__file__).resolve().parent
DATA = DIR / "mrp_evals"
SKILL = DIR.parents[1] / ".agents" / "skills" / "etudecas-supply-diagnose"
AXES = ("calcul", "sources", "incertitude", "suite")


def read_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def make_prompt(case, with_skill=False):
    packet = read_json(DATA / "cases.json")[case]
    parts = []
    if with_skill:
        parts.extend([
            (SKILL / "SKILL.md").read_text(encoding="utf-8"),
            (SKILL / "references" / "tickets.md").read_text(encoding="utf-8"),
        ])
    parts.extend([
        "Résous ce dossier synthétique en utilisant uniquement ses pièces.",
        packet["question"],
        packet["perimetre"],
        "\nPièces du dossier",
        *(f"{key} — {record}" for key, record in packet["pieces"].items()),
        "\nChamps de la réponse",
        *(f"{key} — {question}" for key, question in packet["champs"].items()),
        '\nRéponds en JSON seul. Utilise un objet de la forme '
        '{"constats":{"champ":{"valeur":0,"pieces":["ID"]}},'
        '"note_reunion":"…"} avec une entrée par champ. Cite les pièces nécessaires '
        'au constat. Pour la note, rédige en français le calcul ou le changement '
        "observé, la limite de l'explication, la donnée à rechercher et ce qu'elle "
        "permettrait de décider.",
    ])
    return "\n".join(parts)


def exact_value(actual, expected):
    # JSON booleans differ from 0 and 1, while 800.0 represents the number 800.
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            exact_value(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            exact_value(left, right) for left, right in zip(actual, expected)
        )
    if type(actual) is bool or type(expected) is bool:
        return actual is expected
    return actual == expected


def score(expected, response):
    failures = {axis: [] for axis in AXES}
    if not isinstance(response, dict) or not isinstance(response.get("constats"), dict):
        raise ValueError("La réponse doit contenir un objet constats.")
    facts = response["constats"]
    if facts.keys() != expected.keys():
        raise ValueError("Champs inattendus ou absents dans constats.")
    for name, rule in expected.items():
        claim = facts[name]
        if not isinstance(claim, dict) or "valeur" not in claim or "pieces" not in claim:
            raise ValueError(f"Valeur ou pièces absentes pour {name}.")
        if not exact_value(claim["valeur"], rule["valeur"]):
            failures[rule["axe"]].append(name)
        cited = claim["pieces"]
        if not isinstance(cited, list) or not all(isinstance(p, str) for p in cited):
            raise ValueError(f"Les pièces de {name} doivent former une liste d'identifiants.")
        required = set(rule["pieces"])
        allowed = required.union(rule.get("aussi", []))
        if not required <= set(cited) <= allowed:
            failures["sources"].append(name)
    note = response.get("note_reunion")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("Note de réunion absente.")
    return {
        "reussi_controles_structures": not any(failures.values()),
        "champs_en_echec": failures,
        "note_a_relire": note,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prompt = subs.add_parser("prompt", help="Présenter les pièces sans le corrigé.")
    grade = subs.add_parser("grade", help="Vérifier les constats et leurs preuves.")
    for sub in (prompt, grade):
        sub.add_argument("cas", choices=("stock", "prevision", "gel"))
    prompt.add_argument("--avec-skill", action="store_true", help="Ajouter les instructions métier au même dossier.")
    grade.add_argument("reponse", nargs="?", type=Path, help="Fichier JSON. Par défaut, lire l'entrée standard.")
    args = parser.parse_args()
    if args.command == "prompt":
        print(make_prompt(args.cas, args.avec_skill))
        return 0
    try:
        response = read_json(args.reponse) if args.reponse else json.load(sys.stdin)
        result = score(read_json(DATA / "oracles.json")[args.cas], response)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Réponse illisible ou incomplète : {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["reussi_controles_structures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
