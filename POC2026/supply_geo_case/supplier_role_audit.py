"""Pure documentary annotations; never reclassify the modeled supply graph."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from typing import Any


ROLE_ASSESSMENT_LABELS = {
    "a_documenter": "A documenter",
    "coherent_function": "Fonction modelisee coherente",
    "review_role": "Role a revoir",
    "review_identity": "Identite a revoir",
    "assumption_only": "Hypothese uniquement",
    "multiple_decisions": "Plusieurs decisions a examiner",
}
MODEL_SCOPE = "Les rangs T sont des fonctions modelisees, pas des liens commerciaux prouves."
CONTEXT_SCOPE = "Compteurs et URL declares par le contexte, sans validation de preuve."
NATURE_LABELS = {
    "synthetic_process": "Processus synthetique",
    "assumption": "Hypothese",
    "identified_organization": "Organisation nommee (identite non validee)",
}
ROLES = ("t4", "t3", "t2", "t1", "oem")
DECISION_FIELDS = (
    "documented_activity", "role_assessment", "proposed_role", "confidence",
    "rationale", "source_urls", "source_scope",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tokens(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split("|") if part.strip()]


def _true(value: Any) -> bool:
    return value is True or _text(value).lower() in {"true", "1", "yes"}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _count(value: Any) -> int:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else 0


def _urls(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else [value]
    return list(dict.fromkeys(_text(item) for item in values if _text(item)))


def _node_geometry(nodes: list[dict[str, Any]], supplied: bool) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for node in nodes:
        lat, lon = _number(node.get("lat")), _number(node.get("lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        key = (lat, lon, _text(node.get("country_code")), _text(node.get("location")))
        group = groups.setdefault(key, {
            "lat": lat, "lon": lon, "country_code": key[2], "location": key[3],
            "occurrence_count": 0, "path_ids": set(),
        })
        group["occurrence_count"] += 1
        if path_id := _text(node.get("path_id")):
            group["path_ids"].add(path_id)
    coordinates = {(key[0], key[1]) for key in groups}
    collision = any(
        max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 0.1 + 1e-12
        for a in coordinates for b in coordinates
    )
    return {
        "node_occurrence_count": len(nodes) if supplied else None,
        "node_distinct_path_count": len({_text(n.get("path_id")) for n in nodes if _text(n.get("path_id"))}) if supplied else None,
        "node_geometry_collision": collision if coordinates else None,
        "node_geometry_status": "collision" if collision else "consistent" if coordinates else "unavailable",
        "node_geometry_basis": "Coordonnees des occurrences node_rows ; pas les coordonnees historiques de l'UID.",
        "node_geometry_groups": [
            {**group, "path_ids": sorted(group["path_ids"]), "distinct_path_count": len(group["path_ids"])}
            for group in groups.values()
        ],
    }


def _matches(record: dict[str, Any], uid: str, supplier_ids: set[str]) -> bool:
    site = _text(record.get("site_uid"))
    supplier = _text(record.get("supplier_id"))
    # When both selectors are supplied they must agree; neither is a fuzzy alias.
    return bool(site or supplier) and (not site or site == uid) and (
        not supplier or supplier in supplier_ids
    )


def _nature(name: Any) -> str:
    name = " ".join(_text(name).lower().replace("_", " ").split())
    name = name.replace('internal group', 'group')
    if any(token in name for token in ("assumption", "candidate", "market basket")):
        return "assumption"
    if any(token in name for token in ("internal", "process", "package", "material intermediate sourcing")):
        return "synthetic_process"
    return "identified_organization"


def _coordinate_disagreement(site: dict[str, Any]) -> bool | None:
    tail = _text(site.get("site_uid")).rsplit("@", 1)
    if len(tail) != 2 or len(parts := tail[1].split(",")) != 2:
        return None
    values = [_number(value) for value in (*parts, site.get("lat"), site.get("lon"))]
    if any(value is None for value in values):
        return None
    lat, lon, actual_lat, actual_lon = values
    if not (-90 <= lat <= 90 and -90 <= actual_lat <= 90
            and -180 <= lon <= 180 and -180 <= actual_lon <= 180):
        return None
    return any(delta > 0.1 and not math.isclose(delta, 0.1, abs_tol=1e-12, rel_tol=0)
               for delta in (abs(lat - actual_lat), abs(lon - actual_lon)))


def build_supplier_role_audit(
    site_rows: list[dict[str, Any]],
    path_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    node_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one dossier per input site, in input order, with detached values.

    Decisions match exact supplier IDs (site ``supplier_ids`` is pipe-delimited)
    or exact site UIDs. Both selectors together mean intersection. All matches
    are retained in ``decisions``; flat decision fields are populated only for
    a single match. Name-based nature is a heuristic, not identity validation.
    Paths must explicitly be primary. Counts use distinct path IDs, or input
    row positions when IDs are absent. Unknown coordinate checks return None.
    Context accepts summary counts or detailed URL rows; declared summary
    counts take precedence over URL counts and are never certified here.
    Optional node_rows are occurrences from primary_supply_nodes, matched by
    exact site_uid. Geometry collisions compare these occurrences, not old UIDs.
    """
    rows = []
    matched_decisions: set[int] = set()
    for site in site_rows:
        uid = _text(site.get("site_uid"))
        supplier_ids = set(_tokens(site.get("supplier_ids")))
        roles = set(_tokens(site.get("roles")))
        dossiers = []
        for index, decision in enumerate(decisions):
            if _matches(decision, uid, supplier_ids):
                matched_decisions.add(index)
                dossier = deepcopy(decision)
                for field in DECISION_FIELDS:
                    dossier.setdefault(field, [] if field == "source_urls" else "")
                dossier["source_urls"] = _urls(dossier.get("source_urls"))
                assessment = _text(dossier.get("role_assessment")) or "a_documenter"
                dossier["role_assessment_label"] = ROLE_ASSESSMENT_LABELS.get(assessment, "Evaluation non reconnue")
                dossiers.append(dossier)

        families: set[str] = set()
        paths: set[tuple[str, Any]] = set()
        inferred = _true(site.get("inferred_upstream"))
        for index, path in enumerate(path_rows):
            if path.get("path_type") != "primary":
                continue
            matching_roles = [role for role in ROLES if uid and _text(path.get(f"{role}_site_uid")) == uid]
            if not matching_roles:
                continue
            path_id = _text(path.get("path_id"))
            paths.add(("id", path_id) if path_id else ("row", index))
            if family := _text(path.get("family")):
                families.add(family)
            for role in matching_roles:
                status = _text(path.get(f"{role}_status")).lower()
                if role in {"t2", "t3", "t4"} and any(
                    marker in status for marker in ("inferred", "assum", "candidate")
                ):
                    inferred = True

        contexts = [row for row in context_rows if _matches(row, uid, supplier_ids)]
        urls = sorted({url for context in contexts for field in ("top_url", "url", "canonical_url")
                       if (url := _text(context.get(field)))})
        declared_counts = [row for row in contexts if "source_count" in row]
        source_count = sum(_count(row.get("source_count")) for row in declared_counts) if declared_counts else len(urls)
        verified = sum(_count(row.get("verified_evidence_count")) if "verified_evidence_count" in row
                       else int(row.get("verification_status") == "verified") for row in contexts)
        nature = _nature(site.get("name"))
        nodes = [node for node in (node_rows or []) if uid and _text(node.get("site_uid")) == uid]
        single = dossiers[0] if len(dossiers) == 1 else {}
        status = (_text(single.get("role_assessment")) or "a_documenter") if len(dossiers) <= 1 else "multiple_decisions"
        rows.append({
            "site_uid": uid,
            "supplier_ids": deepcopy(site.get("supplier_ids", "")),
            "name": deepcopy(site.get("name", "")),
            "roles_model": deepcopy(site.get("roles", "")),
            "model_scope": MODEL_SCOPE,
            "nature": nature,
            "nature_label": NATURE_LABELS[nature],
            "nature_basis": "name_heuristic_not_identity_verification",
            "status": status,
            "status_label": ROLE_ASSESSMENT_LABELS.get(status, "Evaluation non reconnue"),
            "role_assessment_label": ROLE_ASSESSMENT_LABELS.get(status, "Evaluation non reconnue"),
            **{field: deepcopy(single.get(field, [] if field == "source_urls" else "")) for field in DECISION_FIELDS},
            "source_urls": list(dict.fromkeys(url for dossier in dossiers for url in dossier["source_urls"])),
            "decisions": dossiers,
            "decision_count": len(dossiers),
            "families": sorted(families),
            "primary_path_count": len(paths),
            "synthetic_node": nature != "identified_organization",
            "inferred_upstream": inferred,
            "coordinates_uid_disagree": _coordinate_disagreement(site),
            "coordinates_uid_scope": "Ecart avec un identifiant historique ; ne prouve pas une erreur de geometrie actuelle.",
            **_node_geometry(nodes, node_rows is not None),
            "multiple_roles": len(roles) > 1,
            "identity_ambiguous": bool(_node_geometry(nodes, node_rows is not None)['node_geometry_collision']) or any(_true(d.get("identity_ambiguous")) or d.get("role_assessment") == "review_identity" for d in dossiers),
            "context_row_count": len(contexts),
            "context_source_count": source_count,
            "context_verified_count": verified,
            "context_urls": urls,
            "context_scope": CONTEXT_SCOPE,
        })
    return {
        "summary": {
            "site_count": len(site_rows), "row_count": len(rows),
            "documented_site_count": sum(bool(row["decision_count"]) for row in rows),
            "status_counts": dict(Counter(row["status"] for row in rows)),
            "nature_counts": dict(Counter(row["nature"] for row in rows)),
            "unmatched_decision_count": len(decisions) - len(matched_decisions),
            "unmatched_decision_indexes": [i for i in range(len(decisions)) if i not in matched_decisions],
            "model_scope": MODEL_SCOPE, "context_scope": CONTEXT_SCOPE,
        },
        "rows": rows,
    }
