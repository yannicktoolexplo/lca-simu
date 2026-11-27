"""Turn the branch inventory and a human-reviewed catalog into meeting inputs."""
import argparse
import csv
import json
import os
import subprocess
import re
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FIELDS = ("name", "family", "decision", "method", "finding", "limit", "next_test")
LEVELS = {"documente", "implemente", "resultat_archive", "reproduit"}
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_snapshot(folder):
    inventory = read_json(folder / "inventory.json")
    heads = {b["name"]: b["sha"] for b in inventory["branches"]}
    paths = defaultdict(dict)
    with (folder / "files.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            for branch in entry["branches"]:
                paths[entry["path"]][branch] = entry["blob"]
    if not heads or any(branch not in heads for versions in paths.values() for branch in versions):
        raise ValueError("Instantané incohérent : vérifier inventory.json et files.jsonl.")
    counts = Counter(branch for versions in paths.values() for branch in versions)
    for b in inventory["branches"]:
        if counts[b["name"]] != b["file_count"]:
            raise ValueError(f"Manifeste incomplet pour {b['name']}.")
    return inventory, heads, paths


def require_text(record, fields):
    for field in fields:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Texte requis : {record.get('id', 'entrée')} / {field}")


def historical_evidence(repo, catalog, heads):
    """Verify the original tree when a reviewed branch has moved since curation."""
    wanted = defaultdict(set)
    for card in catalog["capabilities"]:
        for source in card["evidence"]:
            sha = source["sha"]
            if OID.fullmatch(sha) and sha != heads.get(source["branch"]):
                wanted[sha].add(source["path"])
    versions = {}
    for sha, filenames in wanted.items():
        result = subprocess.run(
            ["git", "-C", str(repo), "--literal-pathspecs", "ls-tree", "-rz", "--full-tree",
             sha, "--", *sorted(filenames)],
            capture_output=True, env=dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"),
        )
        if result.returncode:
            continue  # A shallow clone may not have the original tree.
        for record in result.stdout.split(b"\0"):
            if record:
                info, raw_path = record.split(b"\t", 1)
                versions[sha, os.fsdecode(raw_path)] = info.split()[2].decode("ascii")
    return versions


def qualify(catalog, heads, paths, history):
    ready, paused, seen = [], [], set()
    for card in catalog["capabilities"]:
        require_text(card, ("id",) + FIELDS)
        key = card["id"]
        if key in seen or card["status"] not in LEVELS or not card["evidence"]:
            raise ValueError(f"Identifiant répété, niveau inconnu ou preuve absente : {key}")
        if type(card.get("external_ok")) is not bool:
            raise ValueError(f"Indiquer external_ok pour {key}")
        if card["external_ok"]:
            require_text(card.get("public", {}), FIELDS)
        seen.add(key)
        reasons, evidence = [], []
        for source in card["evidence"]:
            require_text(source, ("branch", "sha", "path", "blob"))
            branch, path = source["branch"], source["path"]
            if not all(OID.fullmatch(source[field]) for field in ("blob", "sha")):
                raise ValueError(f"SHA complet requis pour {key} / {path}")
            if branch not in heads:
                reasons.append(f"Branche absente : {branch}")
            elif path not in paths or branch not in paths[path]:
                reasons.append(f"Chemin absent : {branch} / {path}")
            elif paths[path][branch] != source["blob"]:
                reasons.append(f"Contenu modifié : {branch} / {path}")
            elif heads[branch] != source["sha"] and history.get((source["sha"], path)) != source["blob"]:
                reasons.append(f"Preuve historique indisponible ou différente : {source['sha']} / {path}")
            elif card["status"] == "reproduit" and heads[branch] != source["sha"]:
                reasons.append(f"Rejeu à qualifier sur la nouvelle révision de {branch}")
            else:
                evidence.append(dict(source, reviewed_sha=source["sha"], sha=heads[branch]))
        if card["status"] == "reproduit":
            run = card.get("replay", {})
            require_text(run, ("command", "environment", "oracle", "tolerance", "observed", "manifest"))
            if run["manifest"] not in {e["path"] for e in card["evidence"]}:
                raise ValueError(f"Le manifeste du rejeu doit figurer dans les preuves de {key}.")
        if reasons:
            paused.append({"id": key, "title": card["name"], "reasons": reasons})
        else:
            ready.append(dict(card, evidence=evidence))
    gaps, held_gaps = [], []
    held_ids = {issue["id"] for issue in paused}
    for gap in catalog["gaps"]:
        require_text(gap, ("title", "impact", "test", "priority"))
        ids = gap.get("capability_ids", [])
        if not isinstance(ids, list) or set(ids) - seen:
            raise ValueError(f"Fiche inconnue dans le manque : {gap['title']}")
        if type(gap.get("external_ok", False)) is not bool:
            raise ValueError(f"external_ok invalide : {gap['title']}")
        if gap.get("external_ok", False):
            require_text(gap.get("public", {}), ("title", "impact", "test", "priority"))
        if held_ids.intersection(ids):
            held_gaps.append({"title": gap["title"], "suspended_ids": sorted(held_ids.intersection(ids))})
        else:
            gaps.append(gap)
    return ready, paused, gaps, held_gaps


def row_text(value):
    return str(value).replace("|", " / ").replace("\n", " ")


def write_catalog(out, inventory, heads, ready, paused, gaps):
    lines = ["# Portefeuille des méthodes et des outils", "",
             "Les fiches ci-dessous ont été relues. Les tableaux de détection qui suivent servent à chercher d’autres capacités dans le dépôt.", "",
             "## Branches et périmètre", "", "| Branche | Révision | Entrées suivies |", "|---|---|---:|"]
    for b in inventory["branches"]:
        lines.append(f"| {row_text(b['name'])} | `{b['sha']}` | {b['file_count']} |")
    lines.extend(["", "Les entrées communes sont comptées dans chaque branche. Le fichier differences.tsv repère les chemins propres à un sous-ensemble de branches et les versions divergentes. Les preuves désignent les sources relues. Une nouvelle révision avec des fichiers identiques conserve la lecture de ces fichiers, sans attester l'exécution du reste du modèle.", "", "## Fiches relues"])
    for card in ready:
        lines.extend(["", f"### {card['name']}", "", f"**{card['family']}** · `{card['status']}` · `{card['id']}`", "",
                      f"**Décision.** {card['decision']}", "", f"**Méthode.** {card['method']}", "",
                      f"**Constat.** {card['finding']}", "", f"**Limite.** {card['limit']}", "",
                      f"**Prochain essai.** {card['next_test']}", "", "Sources consultées", ""])
        for e in card["evidence"]:
            lines.append(f"- `{e['branch']}` · `{e['sha']}` · `{e['path']}`")
    lines.extend(["", "## Manques proposés", ""])
    for gap in gaps:
        lines.append(f"- **{gap['priority']} · {gap['title']}.** {gap['impact']} Essai proposé : {gap['test']}")
    lines.extend(["", f"## Fiches suspendues ({len(paused)})", ""])
    for issue in paused:
        lines.append(f"- **{issue['title']}** — " + " / ".join(issue["reasons"]))
    for key, field, title in (("methods", "label", "Méthodes repérées"), ("tools", "name", "Outils repérés")):
        lines.extend(["", f"## {title}", "", "Indices automatiques. Les compteurs et exemples détaillés figurent dans inventory.json. Les numéros ci-dessous renvoient aux branches dans l’ordre du premier tableau.", "",
                      "| Entrée | Branches | Premier chemin à lire |", "|---|---|---|"])
        positions = {b: i for i, b in enumerate(heads, 1)}
        for item in inventory[key]:
            examples = item.get("examples", [])
            path = examples[0]["path"] if examples else ""
            refs = ", ".join(str(positions[b]) for b in item["branches"])
            lines.append(f"| {row_text(item[field])} | {refs} | {row_text(path)} |")
    (out / "portefeuille.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_method_queue(out, inventory, ready):
    by_method = defaultdict(list)
    known = {m["id"] for m in inventory["methods"]}
    for card in ready:
        ids = card.get("method_ids", [])
        if not isinstance(ids, list) or not ids or set(ids) - known:
            raise ValueError(f"Rattachement à la taxonomie à vérifier : {card['id']}")
        for method in ids:
            by_method[method].append(card["id"])
    with (out / "instruction.tsv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, delimiter="\t")
        writer.writerow(["méthode", "état de la revue", "fiches", "première vérification"])
        for method in inventory["methods"]:
            ids = by_method[method["id"]]
            kinds = method["counts"]
            if ids:
                state, action = "traitée dans une fiche", "Lire son périmètre, son niveau de preuve et ses limites."
            elif not method["branches"]:
                state, action = "aucun indice détecté", "Chercher synonymes, classeurs, notebooks et branches hors périmètre."
            elif set(kinds) & {"code", "notebook", "test"}:
                state, action = "code ou test à lire", "Identifier le calcul, vérifier son activation et rechercher le résultat associé."
            else:
                state, action = "pièces à instruire", "Lire la pièce et établir le lien entre sa méthode, son scénario et une décision."
            writer.writerow([method["label"], state, ", ".join(ids), action])


def write_differences(out, heads, paths):
    with (out / "differences.tsv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, delimiter="\t")
        writer.writerow(["path", "classification", *heads])
        for path, versions in sorted(paths.items()):
            divergent = len(set(versions.values())) > 1
            if divergent or len(versions) < len(heads):
                label = "versions divergentes" if divergent else "présence partielle"
                writer.writerow([path, label, *(versions.get(b, "") for b in heads)])


def run(scan, catalog_path, out, repo):
    inventory, heads, paths = load_snapshot(scan)
    catalog = read_json(catalog_path)
    history = historical_evidence(repo, catalog, heads)
    ready, paused, gaps, held_gaps = qualify(catalog, heads, paths, history)
    result = {"schema_version": 1, "snapshot": {"branches": heads},
              "capabilities": ready, "gaps": gaps, "suspended": paused, "suspended_gaps": held_gaps}
    if out.exists():
        raise FileExistsError(f"Choisir un nouveau dossier : {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "review"
        stage.mkdir()
        write_catalog(stage, inventory, heads, ready, paused, gaps)
        write_differences(stage, heads, paths)
        write_method_queue(stage, inventory, ready)
        (stage / "review.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        stage.rename(out)
    print(f"{len(ready)} fiches utilisables, {len(paused)} suspendues. {out / 'portefeuille.md'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True, help="Dossier produit par scan.py")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Clone pour vérifier les preuves antérieures")
    parser.add_argument("--catalog", type=Path, default=HERE / "catalog.json")
    parser.add_argument("--out", type=Path, required=True, help="Nouveau dossier de sortie")
    args = parser.parse_args()
    try:
        run(args.scan, args.catalog, args.out, args.repo)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Revue interrompue : {exc}\n")


if __name__ == "__main__":
    main()
