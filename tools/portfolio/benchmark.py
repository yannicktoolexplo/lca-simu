"""Render the internal functional comparison using the already qualified review."""
from datetime import date
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, urlsplit


EVIDENCE_LEVELS = {
    "documente": "méthode documentée",
    "implemente": "méthode implémentée",
    "resultat_archive": "résultat archivé",
    "reproduit": "résultat reproduit sur la révision qualifiée",
}


def required_text(record, field, owner):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} / {field} doit contenir du texte.")
    return value.strip()


def linked_ids(case, field, known):
    ids = case.get(field)
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) for item in ids):
        raise ValueError(f"{case['id']} / {field} doit désigner au moins une fiche.")
    unknown = set(ids).difference(known)
    if unknown or len(set(ids)) != len(ids):
        raise ValueError(f"{case['id']} / {field} contient une référence inconnue ou répétée : {ids}")
    return ids


def instructions(case, field):
    value = case.get(field)
    if isinstance(value, list):
        if not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"{case['id']} / {field} contient une liste vide ou une consigne manquante.")
        return "\n".join(f"{index}. {item.strip()}" for index, item in enumerate(value, 1))
    return required_text(case, field, case["id"])


def source_notes(sources):
    if not isinstance(sources, dict) or not sources:
        raise ValueError("La comparaison doit citer au moins une source publique.")
    notes = {}
    for key, source in sources.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(source, dict):
            raise ValueError(f"Source invalide : {key}")
        for field in ("product", "title", "url", "checked", "kind", "observation"):
            required_text(source, field, key)
        url = urlsplit(source["url"])
        if url.scheme not in ("https", "http") or not url.hostname:
            raise ValueError(f"{key} / url doit être une adresse web publique.")
        try:
            checked = date.fromisoformat(source["checked"])
        except ValueError as error:
            raise ValueError(f"{key} / checked doit donner la date de consultation.") from error
        if source["checked"] != checked.isoformat():
            raise ValueError(f"{key} / checked doit suivre le format AAAA-MM-JJ.")
        notes[key] = (f"- **{source['product']}** · {source['kind']}. {source['observation']} "
                      f"[{source['title']}](<{source['url']}>), consulté le {checked:%d/%m/%Y}.")
    return notes


def github_project(repo, remote):
    result = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "--", remote],
                            capture_output=True, text=True)
    if result.returncode:
        return None
    url = result.stdout.strip()
    if url.startswith("git@github.com:"):
        path = url.removeprefix("git@github.com:")
    else:
        parts = urlsplit(url)
        if parts.hostname != "github.com" or parts.scheme not in ("https", "http", "ssh", "git"):
            return None
        path = parts.path.lstrip("/")
    path = path.removesuffix("/").removesuffix(".git")
    if re.fullmatch(r"[\w.-]+/[\w.-]+", path):
        return f"https://github.com/{path}"
    return None


def internal_notes(card, github_url):
    lines = [f"- **{card['name']}** (`{card['id']}`) · {EVIDENCE_LEVELS[card['status']]}. {card['finding']}",
             f"  Limite de la preuve. {card['limit']}"]
    for evidence in card["evidence"]:
        label = f"`{evidence['path']}`"
        if github_url:
            url = f"{github_url}/blob/{evidence['sha']}/{quote(evidence['path'], safe='/')}"
            label = f"[{label}]({url})"
        lines.append(f"  - {label} · branche `{evidence['branch']}` "
                     f"· commit de l’inventaire `{evidence['sha']}`")
        if evidence["reviewed_sha"] != evidence["sha"]:
            lines[-1] += f" · fichier relu au commit `{evidence['reviewed_sha']}`"
    return lines


def render_comparison(registry, review, protocol_link, github_url=None):
    sources = source_notes(registry["sources"])
    cases = registry.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("La comparaison doit contenir au moins un cas opérationnel.")
    ready = {card["id"]: card for card in review["capabilities"]}
    paused = {card["id"]: card for card in review["suspended"]}
    seen = set()
    cited = set()
    opening = [
        "# Comparaison fonctionnelle des solutions de supply chain", "",
        "**Document de travail interne.** Chaque cas relie une décision métier à une fonction "
        "décrite publiquement et aux éléments vérifiés dans le dépôt. Aucune mesure comparative "
        "entre produits n’a été réalisée pour ce rapport.", "",
        f"[Consulter le protocole commun d’essai du stock tampon]({protocol_link}).",
    ]
    lines = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Chaque cas doit être un objet avec un identifiant.")
        for field in ("id", "title", "question", "opportunity"):
            required_text(case, field, "cas")
        key = case["id"]
        if key in seen:
            raise ValueError(f"Identifiant de cas répété : {key}")
        seen.add(key)
        references = linked_ids(case, "references", sources)
        cited.update(references)
        capabilities = linked_ids(case, "capabilities", ready.keys() | paused.keys())
        lines.extend(["", f"## {case['title']}", "", f"**Décision métier.** {case['question']}",
                      "", "### Éléments publics", ""])
        lines.extend(sources[ref] for ref in references)
        lines.extend(["", "### Ce que l’équipe a vérifié dans lca-simu", ""])
        for identifier in capabilities:
            if identifier in paused:
                card = paused[identifier]
                lines.append(f"- **{card['title']}** (`{identifier}`) · fiche suspendue. " + " / ".join(card["reasons"]))
            else:
                lines.extend(internal_notes(ready[identifier], github_url))
        lines.extend(["", "### Amélioration ou complémentarité à éprouver", "", case["opportunity"]])
        for field, label in (("procedure", "Protocole"), ("metric", "Indicateur à relever"),
                             ("decision", "Règle de décision")):
            lines.extend(["", f"**{label}**", "", instructions(case, field)])

    lines.extend(["", "## Consigner un essai comparatif", "",
                  "Ouvrir une fiche par cas et renseigner une ligne par configuration exécutée. "
                  "Fixer le critère de décision avant l’essai. Conserver les entrées et les "
                  "sorties pour permettre à un second lecteur de vérifier la mesure.", "",
                  "| Cas et date | Produit, éditeur et version ou commit | Conditions communes "
                  "(jeu de données, horizon, unités, hypothèses et paramètres) | Indicateur, "
                  "unité et seuil convenu | Valeur observée | Trace de la mesure et limites |",
                  "|---|---|---|---|---|---|",
                  "| À renseigner | À renseigner | À renseigner | À renseigner | Non mesurée | À renseigner |",
                  "", "Consigner ensuite l’écart au témoin dans l’unité convenue, les conditions "
                  "qui diffèrent entre les outils et leur effet sur la conclusion. Une configuration "
                  "inaccessible ou un résultat sans trace reste à vérifier.", ""])
    additional = [entry for key, entry in sources.items() if key not in cited]
    if additional:
        opening.extend(["", "## Éditeurs et références complémentaires", "", *additional])
    return "\n".join(opening + lines)


def protocol_href(output_folder):
    protocol = Path(__file__).resolve().with_name("essai-tampon.md")
    try:
        relative = os.path.relpath(protocol, output_folder.resolve())
    except ValueError:  # On Windows the output can live on another drive.
        return protocol.as_uri()
    return quote(Path(relative).as_posix(), safe="/")
