#!/usr/bin/env python3
"""Collect weak-signal context for supply_geo supplier sites.

The script is intentionally separate from the SDD simulation. It searches a
small number of web results for each supplier/site, scores documentary weak
signals, then writes cache files consumed by the map adapter.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CASE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITES = CASE_ROOT / "outputs" / "data" / "primary_supply_sites.csv"
DEFAULT_PATHS = CASE_ROOT / "outputs" / "data" / "primary_supply_paths.csv"
DEFAULT_OUTPUT_DIR = CASE_ROOT / "outputs" / "data"

RESULT_FIELDS = [
    "site_uid",
    "supplier",
    "roles",
    "country_code",
    "location",
    "lat",
    "lon",
    "query",
    "provider",
    "search_status",
    "retrieved_at_utc",
    "result_rank",
    "title",
    "url",
    "domain",
    "description",
    "signal_categories",
    "signal_hits",
    "weak_signal_score",
    "aerospace_relevance_score",
    "official_source_candidate",
]

SUMMARY_FIELDS = [
    "site_uid",
    "supplier",
    "roles",
    "country_code",
    "location",
    "lat",
    "lon",
    "query",
    "provider",
    "context_search_status",
    "retrieved_at_utc",
    "result_count",
    "source_count",
    "top_title",
    "top_url",
    "top_domain",
    "weak_signal_score",
    "weak_signal_categories",
    "weak_signal_hits",
    "documentary_criticality_score",
    "aerospace_relevance_score",
    "official_source_candidate",
    "data_confidence_score",
    "context_short_summary",
]

SIGNAL_RULES = {
    "rupture_approvisionnement": {
        "weight": 2.0,
        "terms": [
            "shortage",
            "supply shortage",
            "supply chain disruption",
            "disruption",
            "delay",
            "delayed",
            "bottleneck",
            "lead time",
            "penurie",
            "rupture",
            "retard",
        ],
    },
    "incident_industriel": {
        "weight": 2.4,
        "terms": [
            "fire",
            "explosion",
            "accident",
            "shutdown",
            "plant closure",
            "factory closure",
            "flood",
            "storm",
            "hurricane",
            "cyclone",
            "typhoon",
            "earthquake",
            "incendie",
            "fermeture",
            "inondation",
            "tempete",
        ],
    },
    "fragilite_financiere": {
        "weight": 2.2,
        "terms": [
            "bankruptcy",
            "insolvency",
            "restructuring",
            "debt",
            "layoff",
            "profit warning",
            "receivership",
            "faillite",
            "redressement",
            "restructuration",
            "licenciement",
        ],
    },
    "risque_geopolitique_reglementaire": {
        "weight": 2.2,
        "terms": [
            "sanction",
            "export control",
            "tariff",
            "war",
            "conflict",
            "embargo",
            "forced labor",
            "human rights",
            "geopolitical",
            "droits humains",
            "controle export",
        ],
    },
    "qualite_conformite": {
        "weight": 1.8,
        "terms": [
            "recall",
            "defect",
            "non conformity",
            "non-conformity",
            "lawsuit",
            "litigation",
            "compliance",
            "quality issue",
            "rappel",
            "defaut",
            "litige",
            "conformite",
        ],
    },
    "dependance_source_unique": {
        "weight": 1.7,
        "terms": [
            "sole source",
            "single source",
            "unique supplier",
            "single supplier",
            "dependency",
            "monopoly",
            "source unique",
            "fournisseur unique",
            "dependance",
        ],
    },
    "cyber_securite": {
        "weight": 1.5,
        "terms": [
            "cyberattack",
            "ransomware",
            "data breach",
            "cyber attack",
            "cyberattaque",
            "rancongiciel",
        ],
    },
}

AEROSPACE_TERMS = [
    "aerospace",
    "aeronautic",
    "aeronautique",
    "aviation",
    "aircraft",
    "airbus",
    "boeing",
    "safran",
    "cabin",
    "seat",
    "siege aeronautique",
    "aircraft seat",
]

LOW_CONTEXT_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "panjiva.com",
    "leadiq.com",
    "zoominfo.com",
    "dnb.com",
    "wienerborse.at",
    "scribd.com",
    "yumpu.com",
}

PATH_SITE_COLUMNS = ["t4_site_uid", "t3_site_uid", "t2_site_uid", "t1_site_uid", "oem_site_uid"]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(clean(value).replace(",", "."))
    except ValueError:
        return default
    return out if math.isfinite(out) else default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.lower()).strip()


def supplier_slug(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"\b(sa|sas|gmbh|ag|inc|ltd|llc|plc|corp|corporation|group|the)\b", " ", text)
    tokens = [token for token in re.findall(r"[a-z0-9]+", text) if len(token) >= 3]
    return " ".join(tokens[:4])


def query_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_weighted_labels(counter: Counter[str], limit: int = 4) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for raw_label, _weight in counter.most_common(limit * 3):
        label = query_text(raw_label)
        if not label:
            continue
        if len(label) > 48:
            label = " ".join(label.split()[:5])
        key = normalize_text(label)
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= limit:
            break
    return " ".join(labels)


def search_location_label(location: Any, country_code: Any = "") -> str:
    location_text = clean(location)
    country_text = clean(country_code)
    if "," in location_text:
        location_text = location_text.split(",")[-1].strip()
    return location_text or country_text


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<.*?>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def result_domain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def decode_duckduckgo_url(href: str) -> str:
    href = html.unescape(clean(href))
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        href = "https://duckduckgo.com" + href
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    uddg = query.get("uddg", [""])[0]
    if uddg:
        return urllib.parse.unquote(uddg)
    return href


def decode_google_url(href: str) -> str:
    href = html.unescape(clean(href))
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/url?"):
        parsed = urllib.parse.urlparse("https://www.google.com" + href)
        query = urllib.parse.parse_qs(parsed.query)
        return urllib.parse.unquote(query.get("q", query.get("url", [""]))[0])
    if href.startswith("/"):
        return ""
    return href


def is_search_result_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    domain = result_domain(url)
    if domain in {"google.com", "duckduckgo.com"} or domain.endswith(".google.com"):
        return False
    return True


def parse_duckduckgo_results(page_html: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    modern_links = list(re.finditer(r'(?is)<a\b(?=[^>]*data-testid="result-title-a")[^>]*>(.*?)</a>', page_html))
    for index, link_match in enumerate(modern_links):
        anchor_html = link_match.group(0)
        href_match = re.search(r'(?is)href="([^"]+)"', anchor_html)
        if not href_match:
            continue
        url = decode_duckduckgo_url(href_match.group(1))
        if not is_search_result_url(url):
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        next_start = modern_links[index + 1].start() if index + 1 < len(modern_links) else min(len(page_html), link_match.end() + 6000)
        context = page_html[link_match.end():next_start]
        snippet = ""
        snippet_match = re.search(
            r'(?is)data-result="snippet".{0,2500}?<span[^>]*>(.*?)</span>',
            context,
        )
        if snippet_match:
            snippet = strip_tags(snippet_match.group(1))
        results.append(
            {
                "title": strip_tags(link_match.group(1)),
                "url": url,
                "domain": result_domain(url),
                "description": snippet,
            }
        )
        if len(results) >= max_results:
            return results

    chunks = re.split(r'(?is)<div[^>]+class="[^"]*(?:result|web-result)[^"]*"[^>]*>', page_html)
    for chunk in chunks[1:]:
        link_match = re.search(
            r'(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            chunk,
        )
        if not link_match:
            continue
        url = decode_duckduckgo_url(link_match.group(1))
        if not is_search_result_url(url):
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        snippet = ""
        snippet_match = re.search(
            r'(?is)<(?:a|div)[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
            chunk,
        )
        if snippet_match:
            snippet = strip_tags(snippet_match.group(1))
        results.append(
            {
                "title": strip_tags(link_match.group(2)),
                "url": url,
                "domain": result_domain(url),
                "description": snippet,
            }
        )
        if len(results) >= max_results:
            break
    return results


def parse_google_results(page_html: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    links = list(re.finditer(r'(?is)<a\b[^>]+href="([^"]+)"[^>]*>\s*<h3\b[^>]*>(.*?)</h3>', page_html))
    for index, link_match in enumerate(links):
        url = decode_google_url(link_match.group(1))
        if not is_search_result_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        next_start = links[index + 1].start() if index + 1 < len(links) else min(len(page_html), link_match.end() + 6000)
        context = page_html[link_match.end():next_start]
        snippet = ""
        snippet_match = re.search(
            r'(?is)<div\b[^>]+class="[^"]*(?:VwiC3b|yXK7lf|lyLwlc|kb0PBd)[^"]*"[^>]*>(.*?)</div>',
            context,
        )
        if snippet_match:
            snippet = strip_tags(snippet_match.group(1))
        if not snippet:
            text = strip_tags(context)
            text = re.sub(r"(?i)(cached|similar|translate this page).*", "", text)
            snippet = text[:420].strip()
        results.append(
            {
                "title": strip_tags(link_match.group(2)),
                "url": url,
                "domain": result_domain(url),
                "description": snippet,
            }
        )
        if len(results) >= max_results:
            break
    return results


def request_url(url: str, *, timeout: float = 25.0, headers: dict[str, str] | None = None, data: bytes | None = None) -> str:
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers, data=data, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def search_duckduckgo_html(query: str, max_results: int, region: str = "fr-fr") -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query, "kl": region})
    page = request_url(f"https://html.duckduckgo.com/html/?{params}")
    if "anomaly-modal" in page or "bots use duckduckgo too" in page.lower():
        raise RuntimeError("duckduckgo_bot_challenge")
    return parse_duckduckgo_results(page, max_results)


def default_search_provider() -> str:
    configured = os.environ.get("SUPPLIER_CONTEXT_PROVIDER", "")
    if configured:
        return configured
    if os.environ.get("BRIGHTDATA_API_TOKEN") and os.environ.get("BRIGHTDATA_SERP_ZONE"):
        return "brightdata_serp_api"
    return "duckduckgo_html"


def resolve_search_provider(provider: str) -> str:
    if provider == "auto":
        return default_search_provider()
    if provider == "brightdata":
        return "brightdata_serp_api"
    return provider


def search_brightdata_serp_api(query: str, max_results: int, region: str = "fr-fr", engine: str = "google") -> list[dict[str, str]]:
    token = os.environ.get("BRIGHTDATA_API_TOKEN", "")
    zone = os.environ.get("BRIGHTDATA_SERP_ZONE", "")
    timeout = safe_float(os.environ.get("BRIGHTDATA_REQUEST_TIMEOUT"), 90.0)
    retries = max(1, int(safe_float(os.environ.get("BRIGHTDATA_REQUEST_RETRIES"), 2.0)))
    if not token or not zone:
        raise RuntimeError("BRIGHTDATA_API_TOKEN and BRIGHTDATA_SERP_ZONE are required for provider=brightdata_serp_api")
    engine = clean(engine).lower() or "google"
    if engine == "duckduckgo":
        search_url = "https://duckduckgo.com/?" + urllib.parse.urlencode({"q": query, "kl": region})
    elif engine == "google":
        language = "fr" if region.lower().startswith("fr") else "en"
        search_url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query, "hl": language, "num": "10"})
    else:
        raise RuntimeError(f"Unsupported BRIGHTDATA_SERP_ENGINE={engine}")
    payload = json.dumps({"zone": zone, "url": search_url, "format": "raw", "data_format": "html"}).encode("utf-8")
    page = ""
    for attempt in range(retries):
        page = request_url(
            "https://api.brightdata.com/request",
            timeout=timeout,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        if page.strip():
            break
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    if not page.strip():
        raise RuntimeError("brightdata_empty_response")
    if engine == "duckduckgo":
        return parse_duckduckgo_results(page, max_results)
    return parse_google_results(page, max_results)


def search_results(provider: str, query: str, max_results: int, region: str, serp_engine: str = "google") -> list[dict[str, str]]:
    if provider == "brightdata_serp_api":
        return search_brightdata_serp_api(query, max_results, region, serp_engine)
    return search_duckduckgo_html(query, max_results, region)


def signal_hits(text: str) -> tuple[float, dict[str, list[str]]]:
    normalized = normalize_text(text)
    weighted = 0.0
    hits: dict[str, list[str]] = {}
    for category, rule in SIGNAL_RULES.items():
        terms = [term for term in rule["terms"] if normalize_text(term) in normalized]
        if not terms:
            continue
        hits[category] = sorted(set(terms))
        weighted += float(rule["weight"]) * min(1.0, 0.55 + 0.15 * len(terms))
    return clamp(weighted / 8.0), hits


def aerospace_relevance(text: str) -> float:
    normalized = normalize_text(text)
    hits = sum(1 for term in AEROSPACE_TERMS if normalize_text(term) in normalized)
    return clamp(hits / 4.0)


def official_candidate(supplier: str, result: dict[str, str]) -> bool:
    tokens = supplier_slug(supplier).split()
    if not tokens:
        return False
    domain = normalize_text(result.get("domain"))
    title = normalize_text(result.get("title"))
    description = normalize_text(result.get("description"))
    domain_tokens = re.findall(r"[a-z0-9]+", domain)
    domain_hit = any(token == tokens[0] or token.startswith(f"{tokens[0]}-") for token in domain_tokens)
    identity_hits = sum(1 for token in tokens if token in title or token in description)
    if domain_hit and tokens[0] in f"{title} {description}":
        return True
    if len(tokens) == 1:
        return domain_hit
    return domain_hit and identity_hits >= min(2, len(tokens))


def score_result(site: dict[str, str], result: dict[str, str]) -> dict[str, Any]:
    text = " ".join([result.get("title", ""), result.get("description", ""), result.get("domain", "")])
    weak_score, hits = signal_hits(text)
    aero_score = aerospace_relevance(text)
    is_official = official_candidate(site.get("name", ""), result)
    return {
        **result,
        "signal_categories": "|".join(sorted(hits)),
        "signal_hits": json.dumps(hits, ensure_ascii=False, sort_keys=True),
        "weak_signal_score": round(weak_score, 4),
        "aerospace_relevance_score": round(aero_score, 4),
        "official_source_candidate": 1 if is_official else 0,
    }


def source_quality_score(row: dict[str, Any]) -> float:
    domain = clean(row.get("domain")).lower()
    if safe_float(row.get("official_source_candidate")) > 0:
        return 1.0
    if domain.endswith(".gov") or domain.endswith(".gouv.fr") or domain.endswith(".europa.eu"):
        return 0.75
    if domain in LOW_CONTEXT_DOMAINS:
        return 0.15
    if domain.endswith(".wikipedia.org"):
        return 0.25
    return 0.45


def result_business_priority(row: dict[str, Any]) -> tuple[float, float, float, float, float, str, str]:
    weak_score = safe_float(row.get("weak_signal_score"))
    aero_score = safe_float(row.get("aerospace_relevance_score"))
    official_score = safe_float(row.get("official_source_candidate"))
    quality_score = source_quality_score(row)
    business_score = max(
        weak_score,
        clamp(0.45 * aero_score + 0.35 * official_score + 0.15 * quality_score + 0.05 * weak_score),
    )
    return (
        -business_score,
        -aero_score,
        -official_score,
        -quality_score,
        -weak_score,
        clean(row.get("domain")),
        clean(row.get("title")),
    )


def rerank_result_rows(rows: list[dict[str, Any]]) -> None:
    rows.sort(key=result_business_priority)
    for rank, row in enumerate(rows, 1):
        row["result_rank"] = rank


def summarize_site(site: dict[str, str], query: str, provider: str, status: str, retrieved_at: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_count = len({clean(row.get("domain")) for row in rows if clean(row.get("domain"))})
    result_count = len(rows)
    weak_score = max((safe_float(row.get("weak_signal_score")) for row in rows), default=0.0)
    aero_score = max((safe_float(row.get("aerospace_relevance_score")) for row in rows), default=0.0)
    official = any(safe_float(row.get("official_source_candidate")) > 0 for row in rows)
    signal_counter: Counter[str] = Counter()
    hit_counter: Counter[str] = Counter()
    for row in rows:
        for category in clean(row.get("signal_categories")).split("|"):
            if category:
                signal_counter[category] += 1
        try:
            hits = json.loads(clean(row.get("signal_hits")) or "{}")
        except json.JSONDecodeError:
            hits = {}
        if isinstance(hits, dict):
            for category, terms in hits.items():
                if isinstance(terms, list):
                    for term in terms:
                        hit_counter[f"{category}:{term}"] += 1
    data_confidence = clamp(
        0.35 * min(result_count / 5.0, 1.0)
        + 0.25 * (1.0 if official else 0.0)
        + 0.25 * aero_score
        + 0.15 * min(source_count / 4.0, 1.0)
    )
    if result_count:
        criticality = clamp(0.76 * weak_score + 0.14 * (1.0 - data_confidence) + 0.10 * (1.0 if "dependance_source_unique" in signal_counter else 0.0))
    elif status.startswith("error:"):
        criticality = 0.0
    else:
        criticality = 0.25
    top = rows[0] if rows else {}
    categories = "|".join(category for category, _ in signal_counter.most_common())
    hits_label = "|".join(hit for hit, _ in hit_counter.most_common(12))
    if categories:
        short = f"Signaux faibles: {categories}"
    elif status.startswith("error:"):
        short = "Recherche bloquee ou erreur outil, a relancer via Bright Data ou plus tard"
    elif result_count:
        short = "Aucun signal faible explicite dans les resultats collectes"
    else:
        short = "Aucun resultat exploitable collecte"
    return {
        "site_uid": site.get("site_uid", ""),
        "supplier": site.get("name", ""),
        "roles": site.get("roles", ""),
        "country_code": site.get("country_code", ""),
        "location": site.get("location", ""),
        "lat": site.get("lat", ""),
        "lon": site.get("lon", ""),
        "query": query,
        "provider": provider,
        "context_search_status": status,
        "retrieved_at_utc": retrieved_at,
        "result_count": result_count,
        "source_count": source_count,
        "top_title": top.get("title", ""),
        "top_url": top.get("url", ""),
        "top_domain": top.get("domain", ""),
        "weak_signal_score": round(weak_score, 4),
        "weak_signal_categories": categories,
        "weak_signal_hits": hits_label,
        "documentary_criticality_score": round(criticality, 4),
        "aerospace_relevance_score": round(aero_score, 4),
        "official_source_candidate": 1 if official else 0,
        "data_confidence_score": round(data_confidence, 4),
        "context_short_summary": short,
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_site_hints(path_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    counters: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {"families": Counter(), "components": Counter(), "systems": Counter()}
    )
    for row in path_rows:
        weight = max(safe_float(row.get("path_mass_kg")), safe_float(row.get("component_mass_kg")), 0.001)
        site_uids = {clean(row.get(column)) for column in PATH_SITE_COLUMNS if clean(row.get(column))}
        for site_uid in site_uids:
            counters[site_uid]["families"][clean(row.get("family"))] += weight
            counters[site_uid]["components"][clean(row.get("component"))] += weight
            counters[site_uid]["systems"][clean(row.get("system"))] += weight
    return {
        site_uid: {
            "families": compact_weighted_labels(values["families"], limit=3),
            "components": compact_weighted_labels(values["components"], limit=3),
            "systems": compact_weighted_labels(values["systems"], limit=2),
        }
        for site_uid, values in counters.items()
    }


def build_query(site: dict[str, str], template: str, hints: dict[str, str] | None = None) -> str:
    hints = hints or {}
    supplier = clean(site.get("name"))
    country_code = clean(site.get("country_code"))
    location = search_location_label(site.get("location"), country_code)
    country = " ".join(part for part in [country_code, location] if part)
    roles = clean(site.get("roles"))
    return template.format(
        supplier=supplier,
        country=country,
        country_code=country_code,
        location=location,
        roles=roles,
        families=hints.get("families", ""),
        components=hints.get("components", ""),
        systems=hints.get("systems", ""),
    ).strip()


def supplier_search_name(value: Any) -> str:
    text = clean(value)
    text = re.sub(r"\s+-\s+internal.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\(.*?\)\s*", " ", text)
    text = re.sub(r"\btier\s*\d+.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -/")
    return text or clean(value)


def build_queries(site: dict[str, str], template: str, hints: dict[str, str] | None = None) -> list[str]:
    hints = hints or {}
    supplier = supplier_search_name(site.get("name"))
    country_code = clean(site.get("country_code"))
    location = search_location_label(site.get("location"), country_code)
    country = " ".join(part for part in [country_code, location] if part)
    families = hints.get("families", "")
    components = hints.get("components", "")
    candidates = [
        build_query({**site, "name": supplier}, template, hints),
        f'"{supplier}" aerospace aircraft supplier {families} {components}',
        f'"{supplier}" "{location}" aerospace supplier material component',
        f'"{supplier}" company {country or location}',
        f'"{supplier}" supply chain risk shortage fire strike bankruptcy',
    ]
    if "/" in supplier:
        for part in [part.strip() for part in supplier.split("/") if part.strip()]:
            candidates.append(f'"{part}" aerospace supplier {country or location}')
            candidates.append(f'"{part}" supply chain risk')
    out: list[str] = []
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def selected_sites(rows: list[dict[str, str]], *, offset: int, limit: int, exclude_oem: bool) -> list[dict[str, str]]:
    filtered = [
        row for row in rows
        if clean(row.get("site_uid")) and clean(row.get("name")) and not (exclude_oem and "OEM" in clean(row.get("roles")).split("|"))
    ]
    filtered.sort(key=lambda row: (-safe_float(row.get("allocated_mass_kg")), clean(row.get("name"))))
    if limit <= 0:
        return filtered[offset:]
    return filtered[offset: offset + limit]


def write_summary_json(path: Path, summaries: list[dict[str, Any]], result_rows: list[dict[str, Any]]) -> None:
    status_counts = Counter(clean(row.get("context_search_status")) for row in summaries)
    signal_counts: Counter[str] = Counter()
    for row in summaries:
        for category in clean(row.get("weak_signal_categories")).split("|"):
            if category:
                signal_counts[category] += 1
    payload = {
        "schema_version": "poc2026.supply_geo_case.supplier_context.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_count": len(summaries),
        "result_count": len(result_rows),
        "status_counts": dict(status_counts),
        "signal_counts": dict(signal_counts),
        "top_critical_suppliers": sorted(
            summaries,
            key=lambda row: (-safe_float(row.get("documentary_criticality_score")), clean(row.get("supplier"))),
        )[:20],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich supply_geo supplier sites with DuckDuckGo/Bright Data SERP context.")
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    parser.add_argument("--paths", type=Path, default=DEFAULT_PATHS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--provider",
        choices=["auto", "duckduckgo_html", "brightdata_serp_api", "brightdata"],
        default=default_search_provider(),
        help=(
            "Search backend. brightdata_serp_api follows luminati-io/duckduckgo-api's "
            "Direct API Access pattern via https://api.brightdata.com/request. "
            "brightdata is kept as a legacy alias."
        ),
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of sites to search. Use 0 for all.")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--region", default="fr-fr")
    parser.add_argument(
        "--serp-engine",
        choices=["google", "duckduckgo"],
        default=os.environ.get("BRIGHTDATA_SERP_ENGINE", "google"),
        help="SERP engine used behind Bright Data. Direct duckduckgo_html ignores this option.",
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh sites already present in the cache.")
    parser.add_argument("--exclude-oem", action="store_true")
    parser.add_argument("--fallback-queries", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--max-queries-per-site",
        type=int,
        default=0,
        help=(
            "Limit fallback queries per site. 0 uses the provider default: 1 for Bright Data SERP, "
            "all fallback queries for direct DuckDuckGo HTML."
        ),
    )
    parser.add_argument(
        "--query-template",
        default='"{supplier}" aerospace aircraft supplier {families} {location}',
        help="Python format string with supplier, country, location, roles, families, components and systems.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    provider = resolve_search_provider(args.provider)
    sites = read_csv(args.sites)
    if not sites:
        print(f"No sites found in {args.sites}", file=sys.stderr)
        return 2
    site_hints = build_site_hints(read_csv(args.paths))

    result_path = args.output_dir / "supplier_context_results.csv"
    summary_path = args.output_dir / "supplier_context_summary.csv"
    json_path = args.output_dir.parent / "summaries" / "supplier_context_summary.json"
    existing_results = read_csv(result_path)
    existing_summaries = read_csv(summary_path)
    done = {clean(row.get("site_uid")) for row in existing_summaries if clean(row.get("site_uid")) and not args.refresh}
    existing_results_by_site: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in existing_results:
        existing_results_by_site[clean(row.get("site_uid"))].append(row)
    existing_summary_by_site = {clean(row.get("site_uid")): row for row in existing_summaries if clean(row.get("site_uid"))}

    work = [site for site in selected_sites(sites, offset=args.offset, limit=args.limit, exclude_oem=args.exclude_oem) if clean(site.get("site_uid")) not in done]
    result_rows = [row for row in existing_results if clean(row.get("site_uid")) not in {clean(site.get("site_uid")) for site in work}]
    summary_rows = [row for row in existing_summaries if clean(row.get("site_uid")) not in {clean(site.get("site_uid")) for site in work}]

    for index, site in enumerate(work, 1):
        hints = site_hints.get(clean(site.get("site_uid")), {})
        queries = build_queries(site, args.query_template, hints) if args.fallback_queries else [build_query(site, args.query_template, hints)]
        if args.max_queries_per_site > 0:
            queries = queries[:args.max_queries_per_site]
        elif provider == "brightdata_serp_api":
            queries = queries[:1]
        query = " | ".join(queries)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        print(f"[{index}/{len(work)}] {site.get('name')} :: {queries[0]} ({len(queries)} requete(s))")
        status = "ok"
        scored_rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        try:
            for search_query in queries:
                if len(scored_rows) >= args.max_results:
                    break
                raw_results = search_results(provider, search_query, args.max_results, args.region, args.serp_engine)
                for result in raw_results:
                    url = clean(result.get("url"))
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    scored = score_result(site, result)
                    scored_rows.append(
                        {
                            "site_uid": site.get("site_uid", ""),
                            "supplier": site.get("name", ""),
                            "roles": site.get("roles", ""),
                            "country_code": site.get("country_code", ""),
                            "location": site.get("location", ""),
                            "lat": site.get("lat", ""),
                            "lon": site.get("lon", ""),
                            "query": search_query,
                            "provider": provider,
                            "search_status": status,
                            "retrieved_at_utc": retrieved_at,
                            "result_rank": len(scored_rows) + 1,
                            **scored,
                        }
                    )
                    if len(scored_rows) >= args.max_results:
                        break
            if not scored_rows:
                status = "no_results"
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            status = f"error:{type(exc).__name__}"
            print(f"  -> {status}: {exc}", file=sys.stderr)
        if not scored_rows and status.startswith("error:") and clean(site.get("site_uid")) in existing_summary_by_site:
            stale_summary = dict(existing_summary_by_site[clean(site.get("site_uid"))])
            stale_summary["context_search_status"] = f"cache_conserve_apres_{status}"
            summary_rows.append(stale_summary)
            result_rows.extend(existing_results_by_site.get(clean(site.get("site_uid")), []))
            continue
        rerank_result_rows(scored_rows)
        result_rows.extend(scored_rows)
        summary_rows.append(summarize_site(site, query, provider, status, retrieved_at, scored_rows))
        write_csv(result_path, result_rows, RESULT_FIELDS)
        write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
        write_summary_json(json_path, summary_rows, result_rows)
        if index < len(work) and args.delay > 0:
            time.sleep(args.delay)

    write_csv(result_path, result_rows, RESULT_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    write_summary_json(json_path, summary_rows, result_rows)
    print(f"Wrote {len(summary_rows)} supplier context summaries: {summary_path}")
    print(f"Wrote {len(result_rows)} supplier context result rows: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
