"""Prepare meeting material from a human-reviewed portfolio (Python 3.11+)."""
import argparse
import base64
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zlib
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
STATUS = {
    "documente": "Documenté",
    "implemente": "Implémenté",
    "resultat_archive": "Résultat archivé",
    "reproduit": "Reproduit",
}
CAP_FIELDS = ("name", "family", "decision", "method", "finding", "limit", "next_test")
GAP_FIELDS = ("title", "impact", "test", "priority")
PROFILES = {
    "science": {
        "title": "Revue scientifique des simulations",
        "question": "Quelle expérience permet de départager les hypothèses du modèle ?",
        "primary": "Méthode", "secondary": "Décision étudiée",
        "questions": ["Quel comportement observé le modèle doit-il reproduire ?",
                      "Quel témoin, quelle métrique et quel seuil permettraient de réfuter notre hypothèse ?",
                      "Qui dispose des données et peut réaliser un rejeu indépendant ?"],
        "agenda": ["Définir le domaine de validité et le témoin.",
                   "Examiner les résultats, les hypothèses et la sensibilité.",
                   "Choisir le protocole, le critère de réfutation et le responsable du rejeu."],
        "closing": "Convenir du prochain essai",
    },
    "operations": {
        "title": "Simulation et décisions supply chain",
        "question": "Quelle décision de planification mérite un essai sur vos flux ?",
        "primary": "Décision à instruire", "secondary": "Méthode",
        "questions": ["Qui décide, à quelle date et avec quel horizon de replanification ?",
                      "Quel indicateur client et quel coût permettront d’arbitrer ?",
                      "Quel article, site ou flux pilote dispose d’un historique utilisable ?"],
        "agenda": ["Délimiter le flux et la décision à prendre.",
                   "Examiner les cas applicables aux contraintes du terrain.",
                   "Choisir le pilote, les données à fournir et le décideur."],
        "closing": "Choisir le périmètre du pilote",
    },
    "mixte": {
        "title": "Revue conjointe des simulations supply chain",
        "question": "Comment éprouver une règle de décision sur un flux représentatif ?",
        "primary": "Décision étudiée", "secondary": "Méthode",
        "questions": ["Qui utilise la décision et avec quelles informations à cette date ?",
                      "Quel scénario témoin permet de mesurer le gain opérationnel ?",
                      "Quels critères et quelles données les deux équipes acceptent-elles pour le pilote ?"],
        "agenda": ["Définir le cas d’usage et l’indicateur opérationnel.",
                   "Relier les résultats au mécanisme simulé et à ses hypothèses.",
                   "Valider ensemble le protocole, les responsables et la date de revue."],
        "closing": "Définir l’essai conjoint",
    },
}


def ordered_text(row, fields, context):
    if not isinstance(row, dict):
        raise ValueError(f"{context} doit contenir une fiche relue.")
    result = {}
    for key in fields:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{context}.{key} doit contenir du texte relu.")
        result[key] = value.strip()
    return result


def clean_visual(raw):
    result = ordered_text(raw, ("kind", "title", "unit", "x_label", "caption"), "visual")
    if result["kind"] not in ("line", "bar"):
        raise ValueError("visual.kind doit valoir line ou bar.")
    labels, series = raw.get("categories"), raw.get("series")
    if not isinstance(labels, list) or not labels or not all(isinstance(x, str) and x.strip() for x in labels):
        raise ValueError("visual.categories doit être une liste de libellés.")
    if not isinstance(series, list) or not series:
        raise ValueError("visual.series doit contenir une série au minimum.")
    if result["kind"] == "line" and len(labels) < 2:
        raise ValueError("Une courbe demande au moins deux abscisses.")
    result.update(categories=labels, series=[])
    for item in series:
        clean = ordered_text(item, ("name",), "série")
        ys = item.get("values")
        if not isinstance(ys, list) or len(ys) != len(labels) or not all(
            type(y) in (int, float) and math.isfinite(y) for y in ys
        ):
            raise ValueError("Chaque série doit fournir une valeur numérique finie par catégorie.")
        clean["values"] = ys
        result["series"].append(clean)
    return result


def static_png(blob):
    """Preserve static PNG pixels and rendering metadata, discard embedded text."""
    magic = b"\x89PNG\r\n\x1a\n"
    if not blob.startswith(magic):
        raise ValueError("La pièce référencée doit être une image PNG.")
    pos = len(magic)
    clean = bytearray(magic)
    dimensions = None
    has_data = False
    while pos + 12 <= len(blob):
        length, kind = struct.unpack_from(">I4s", blob, pos)
        end = pos + 12 + length
        if end > len(blob) or zlib.crc32(blob[pos + 4:end - 4]) != int.from_bytes(blob[end - 4:end], "big"):
            raise ValueError("Bloc PNG incomplet ou corrompu.")
        if pos == len(magic):
            if kind != b"IHDR" or length != 13:
                raise ValueError("En-tête PNG manquant.")
            dimensions = struct.unpack_from(">II", blob, pos + 8)
            if not all(dimensions):
                raise ValueError("Dimensions PNG invalides.")
        if kind in (b"acTL", b"fcTL", b"fdAT"):
            raise ValueError("Seul un PNG fixe peut illustrer la réunion.")
        if kind in (b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB"):
            clean.extend(blob[pos:end])
        has_data |= kind == b"IDAT"
        if kind == b"IEND":
            if not has_data or length or end != len(blob):
                raise ValueError("Fin de fichier PNG incorrecte.")
            return bytes(clean), dimensions
        pos = end
    raise ValueError("PNG sans fin de fichier.")


def reviewed_image(raw, evidence, repo, external):
    view = ordered_text(raw, ("title", "caption"), "visual")
    ref = ordered_text(raw.get("evidence"), ("branch", "path", "blob"), "visual.evidence")
    if external and raw.get("approved_blob") != ref["blob"]:
        raise ValueError("Valider explicitement l’image externe via public.visual.approved_blob.")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", ref["blob"]) or not ref["path"].lower().endswith(".png"):
        raise ValueError("La référence de figure doit désigner un blob Git complet et un chemin PNG.")
    match = next((item for item in evidence if all(item.get(k) == v for k, v in ref.items())), None)
    if not match:
        raise ValueError("La figure doit correspondre à une preuve de la fiche (branche, chemin et blob).")
    git = ["git", "-C", str(repo)]
    actual = subprocess.check_output([*git, "rev-parse", "--verify", match["sha"] + ":" + ref["path"]]).decode().strip()
    if actual != ref["blob"]:
        raise ValueError("Le blob de la figure a changé. Relire l’image à la révision demandée.")
    png, (width, height) = static_png(subprocess.check_output([*git, "cat-file", "blob", actual]))
    view.update(kind="image", width=width, height=height, data=base64.b64encode(png).decode("ascii"))
    return view


def private_note_path(out, path, external, question):
    if external and question and path is None:
        raise ValueError("Avec --question en mode externe, préciser --private-out CHEMIN.md hors de --out, "
                         "ou utiliser --public-question pour un texte partageable.")
    if path is None:
        return None
    if not external or not question:
        raise ValueError("--private-out exige une --question en mode externe.")
    path = path.resolve()
    if path.is_relative_to(out.resolve()) or path in out.resolve().parents:
        raise ValueError("--private-out doit désigner un fichier distinct hors du dossier de diffusion.")
    if path.exists():
        raise ValueError(f"Le fichier de préparation existe déjà : {path}")
    return path


def selected_rows(review, audience, external, focus, repo=Path(".")):
    caps, gaps = review["capabilities"], review["gaps"]
    by_id = {c["id"]: c for c in caps}
    if len(by_id) != len(caps):
        raise ValueError("Deux capacités ont le même identifiant.")
    if focus and set(focus) - by_id.keys():
        raise ValueError(f"Identifiants inconnus : {', '.join(sorted(set(focus) - by_id.keys()))}")
    branches = review["snapshot"]["branches"]
    selected = []
    for cid, source in by_id.items():
        if focus and cid not in focus:
            continue
        if external and source.get("external_ok") is not True:
            if focus:
                raise ValueError(f"Diffusion externe indisponible pour {cid}.")
            continue
        view = source.get("public") if external else source
        row = ordered_text(view, CAP_FIELDS, f"{cid} ({audience})")
        state = source.get("status")
        if state not in STATUS:
            raise ValueError(f"{cid} : niveau de preuve inconnu.")
        row.update(status=STATUS[state], evidence=[])
        sources = source.get("evidence")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{cid} : au moins une preuve référencée est nécessaire.")
        for ev in sources:
            item = ordered_text(ev, ("branch", "sha", "path"), f"{cid}.evidence")
            if branches.get(item["branch"]) != item["sha"] or not re.fullmatch(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", item["sha"]):
                raise ValueError(f"{cid} : référence incohérente avec l’instantané.")
            if not external:
                row["evidence"].append(f'{item["branch"]} @ {item["sha"]} / {item["path"]}')
        if view.get("visual") is not None:
            visual = view["visual"]
            if isinstance(visual, dict) and visual.get("kind") == "image":
                row["visual"] = reviewed_image(visual, sources, repo, external)
            else:
                row["visual"] = clean_visual(visual)
        selected.append(row)

    if not selected:
        raise ValueError("Aucune fiche relue pour ce public et cette sélection.")
    selected_gaps = []
    for gap in gaps:
        if focus and not set(gap.get("capability_ids", ())).intersection(focus):
            continue
        if external and gap.get("external_ok") is not True:
            continue
        view = gap.get("public") if external else gap
        selected_gaps.append(ordered_text(view, GAP_FIELDS, "lacune"))
    return selected, selected_gaps


def write_brief(path, data):
    p = data["profile"]
    lines = [f'# {p["title"]}', "", data["scope"], "", f'**Question de réunion** — {data["question"]}',
             "", "## Ordre du jour proposé (30 min)", ""]
    for duration, stage in zip(("5 min", "15 min", "10 min"), p["agenda"]):
        lines.append(f"- **{duration}** — {stage}")
    lines += ["", "## Questions à poser", ""] + [f"- {q}" for q in p["questions"]]
    for c in data["caps"]:
        lines += ["", f'## {c["name"]}', "", f'{c["family"]} · {c["status"]}', "",
                  f'**Décision.** {c["decision"]}', "", f'**Méthode.** {c["method"]}', "",
                  f'**Constat.** {c["finding"]}', "", f'**Limite.** {c["limit"]}', "",
                  f'**Prochain essai.** {c["next_test"]}']
        if c.get("visual"):
            v = c["visual"]
            unit = f' ({v["unit"]})' if "unit" in v else ""
            lines += ["", f'**Figure.** {v["title"]}{unit}. {v["caption"]}']
        if c["evidence"]:
            lines += ["", "**Pièces du dépôt**", ""] + [f"- `{ref}`" for ref in c["evidence"]]
    if data["gaps"]:
        lines += ["", "## Questions restant à instruire", ""]
        for g in data["gaps"]:
            lines += [f'- **{g["title"]}** ({g["priority"]}). {g["impact"]} Essai proposé : {g["test"]}']
    lines += ["", "## Décision à consigner en séance", "",
              "| Décision ou essai retenu | Indicateur et critère d’acceptation | Responsable | Échéance |",
              "|---|---|---|---|", "| À convenir | À convenir | À désigner | À fixer |", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--review", type=Path, required=True)
    cli.add_argument("--audience", choices=PROFILES, required=True)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--repo", type=Path, default=Path("."), help="Dépôt Git contenant les éventuelles figures PNG.")
    cli.add_argument("--private-out", type=Path, help="Fichier Markdown privé, hors du dossier de diffusion.")
    cli.add_argument("--question", help="Question de préparation interne. Figure sur le support scientifique interne.")
    cli.add_argument("--public-question", help="Question explicitement relue pour un support externe.")
    cli.add_argument("--external", action="store_true", help="Mode partageable pour un public scientifique externe.")
    cli.add_argument("--focus", action="append", metavar="ID", help="Limiter les fiches à ces identifiants. Répétable.")
    args = cli.parse_args()
    external = args.external or args.audience != "science"
    if args.public_question and not external:
        cli.error("--public-question nécessite un support externe (utiliser --external pour les scientifiques).")
    node = shutil.which("node")
    if not node:
        cli.error("Installer Node.js 18+ et PptxGenJS (npm ci --prefix tools/portfolio).")
    try:
        private_path = private_note_path(args.out, args.private_out, external, args.question)
        review = json.loads(args.review.read_text(encoding="utf-8"))
        caps, gaps = selected_rows(review, args.audience, external, args.focus, args.repo)
        p = PROFILES[args.audience]
        question = (args.public_question if external else args.question) or p["question"]
        material = {"profile": p, "audience": args.audience, "caps": caps, "gaps": gaps,
                    "statuses": list(STATUS.values()), "question": question,
                    "scope": "Sélection relue pour diffusion externe" if external else "Revue scientifique interne"}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Publish the completed directory together, preserving any earlier meeting.
        if args.out.exists() and any(args.out.iterdir()):
            raise ValueError(f"Choisir un dossier de sortie vide : {args.out}")
        with TemporaryDirectory(dir=args.out.parent) as stage:
            dest = Path(stage) / "meeting"
            dest.mkdir()
            payload = Path(stage) / "presentation.json"
            payload.write_text(json.dumps(material, ensure_ascii=False), encoding="utf-8")
            command = [node, str(HERE / "deck.cjs"), str(payload), str(dest / "presentation.pptx")]
            subprocess.run(command, check=True)
            write_brief(dest / "brief.md", material)
            files = ["brief.md", "presentation.pptx"]
            if private_path:
                private_path.parent.mkdir(parents=True, exist_ok=True)
                with private_path.open("x", encoding="utf-8") as handle:
                    handle.write("# Préparation interne du rendez-vous\n\n"
                                 f"**Question de préparation** — {args.question}\n\n"
                                 f"**Question portée au support partageable** — {question}\n")
            if os.name == "nt" and args.out.is_dir():
                # Windows requires a nonexistent destination. rmdir only accepts an empty folder.
                args.out.rmdir()
            os.replace(dest, args.out)
        print("\n".join(str(args.out / name) for name in files))
        if private_path:
            print(private_path)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        cli.exit(1, f"Export impossible : {exc}\n")


if __name__ == "__main__":
    main()
