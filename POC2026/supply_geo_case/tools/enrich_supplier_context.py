#!/usr/bin/env python3
"""Collect weak-signal context for supply_geo supplier sites.

The script is intentionally separate from the SDD simulation. It searches a
small number of web results for each supplier/site, scores documentary weak
signals, then writes cache files consumed by the map adapter.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    "query_id",
    "query_family",
    "search_plan_version",
    "provider",
    "serp_engine",
    "search_region",
    "search_status",
    "retrieved_at_utc",
    "result_rank",
    "serp_rank_original",
    "title",
    "url",
    "canonical_url",
    "domain",
    "description",
    "signal_categories",
    "signal_hits",
    "weak_signal_score",
    "positive_signal_categories",
    "positive_signal_hits",
    "resilience_evidence_score",
    "aerospace_relevance_score",
    "official_source_candidate",
    "identity_match_score",
    "source_type",
    "source_quality_score",
    "publication_date_hint",
    "recency_factor",
    "evidence_strength_score",
    "verification_status",
    "potential_sdd_effects",
]

SEARCH_ATTEMPT_FIELDS = [
    "query_id",
    "search_plan_version",
    "scoring_rules_version",
    "site_uid",
    "supplier",
    "query_family",
    "query",
    "provider",
    "serp_engine",
    "search_region",
    "requested_at_utc",
    "duration_seconds",
    "status",
    "error_type",
    "result_count",
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
    "search_plan_version",
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
    "observed_fragility_score",
    "hazard_exposure_evidence_score",
    "dependency_evidence_score",
    "resilience_evidence_score",
    "resilience_categories",
    "structural_importance_score",
    "structural_path_count",
    "structural_system_count",
    "structural_component_count",
    "structural_score_basis",
    "verified_evidence_count",
    "candidate_evidence_count",
    "model_activation_status",
    "documentary_criticality_score",
    "aerospace_relevance_score",
    "official_source_candidate",
    "data_confidence_score",
    "risk_evidence_confidence_score",
    "context_short_summary",
]

EVIDENCE_FIELDS = [
    "evidence_id",
    "site_uid",
    "supplier",
    "roles",
    "country_code",
    "location",
    "query_family",
    "evidence_kind",
    "evidence_category",
    "fact_summary",
    "publication_date_hint",
    "recency_factor",
    "source_title",
    "source_url",
    "canonical_url",
    "source_domain",
    "source_type",
    "source_quality_score",
    "identity_match_score",
    "evidence_strength_score",
    "verification_status",
    "evidence_status",
    "model_activation_status",
    "potential_sdd_effects",
    "retrieved_at_utc",
    "query_id",
    "query",
    "serp_rank_original",
    "result_rank",
    "discovery_count",
    "query_ids",
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
            "compliance violation",
            "regulatory breach",
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

POSITIVE_SIGNAL_RULES = {
    "investissement_capacite": {
        "weight": 1.8,
        "terms": [
            "investment",
            "invests",
            "new plant",
            "new facility",
            "capacity expansion",
            "expands capacity",
            "production expansion",
            "investissement",
            "nouvelle usine",
            "extension de capacite",
        ],
    },
    "certification_qualite": {
        "weight": 1.4,
        "terms": [
            "as9100",
            "en 9100",
            "nadcap",
            "iso 9001",
            "certified",
            "certification",
            "accreditation",
        ],
    },
    "contrat_reussite": {
        "weight": 1.2,
        "terms": [
            "contract awarded",
            "selected by airbus",
            "selected by boeing",
            "long term agreement",
            "supplier award",
            "partnership",
            "contrat",
            "accord long terme",
            "prix fournisseur",
        ],
    },
    "diversification_localisation": {
        "weight": 1.3,
        "terms": [
            "dual source",
            "multi sourcing",
            "multiple sites",
            "global footprint",
            "local production",
            "regional production",
            "reduced dependency",
            "reduced its dependency",
            "reduced dependence",
            "double source",
            "multi-sourcing",
            "plusieurs sites",
            "production locale",
        ],
    },
}

QUERY_FAMILY_TEMPLATES = [
    (
        "identite_specialite",
        '"{supplier}" {location} official aerospace products aircraft supplier {families} {components}',
    ),
    (
        "certification_qualite",
        '"{supplier}" aerospace AS9100 EN9100 NADCAP certification quality {location}',
    ),
    (
        "incident_operationnel",
        '"{supplier}" {location} fire flood explosion strike shutdown disruption delay incident',
    ),
    (
        "fragilite_financiere",
        '"{supplier}" bankruptcy insolvency restructuring layoff plant closure acquisition financial',
    ),
    (
        "capacite_resilience",
        '"{supplier}" investment expansion new plant capacity contract aerospace supplier award',
    ),
    (
        "dependance_substitution",
        '"{supplier}" sole source single source shortage lead time dependency alternative supplier aerospace',
    ),
    (
        "exposition_climatique",
        '"{supplier}" {location} flood heatwave storm hurricane cyclone cold weather transport disruption',
    ),
]

RISK_QUERY_FAMILIES = {
    "incident_operationnel",
    "fragilite_financiere",
    "certification_qualite",
    "dependance_substitution",
    "exposition_climatique",
}

QUERY_FAMILY_RISK_CATEGORIES = {
    "certification_qualite": {"qualite_conformite"},
    "incident_operationnel": {"incident_industriel", "rupture_approvisionnement", "cyber_securite"},
    "fragilite_financiere": {"fragilite_financiere"},
    "dependance_substitution": {
        "dependance_source_unique",
        "rupture_approvisionnement",
        "risque_geopolitique_reglementaire",
    },
    "exposition_climatique": {"incident_industriel", "rupture_approvisionnement"},
}

QUERY_FAMILY_POSITIVE_CATEGORIES = {
    "identite_specialite": {"certification_qualite"},
    "certification_qualite": {"certification_qualite"},
    "capacite_resilience": {
        "investissement_capacite",
        "contrat_reussite",
        "diversification_localisation",
    },
    "dependance_substitution": {"diversification_localisation"},
}

AMBIGUOUS_PLACE_EVENT_PHRASES = {
    "alcoa highway",
    "airport highway",
    "highway was shutdown",
    "road was closed",
    "traffic delays",
    "vehicle crash",
    "crash involving",
}

HAZARD_CATEGORIES = {"incident_industriel"}
FRAGILITY_CATEGORIES = {
    "rupture_approvisionnement",
    "fragilite_financiere",
    "qualite_conformite",
    "cyber_securite",
    "risque_geopolitique_reglementaire",
}

SDD_EFFECTS_BY_CATEGORY = {
    "rupture_approvisionnement": "delai|capacite|stock_securite|transport_premium",
    "incident_industriel": "capacite|delai|maintenance|reprise_progressive",
    "fragilite_financiere": "capacite|delai|substitution_fournisseur",
    "risque_geopolitique_reglementaire": "transport|delai|substitution_regionale",
    "qualite_conformite": "rebut|reprise_qualite|delai",
    "dependance_source_unique": "capacite|delai|absence_alternative",
    "cyber_securite": "capacite|delai|reprise_progressive",
    "investissement_capacite": "capacite|resilience|delai",
    "certification_qualite": "qualite|rebut|confiance_fournisseur",
    "contrat_reussite": "capacite|continuite",
    "diversification_localisation": "substitution_regionale|resilience|delai",
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

IDENTITY_GENERIC_TOKENS = {
    "aerospace",
    "aircraft",
    "company",
    "component",
    "components",
    "engineering",
    "group",
    "industrie",
    "industries",
    "internal",
    "material",
    "production",
    "supplier",
}

PATH_SITE_COLUMNS = ["t4_site_uid", "t3_site_uid", "t2_site_uid", "t1_site_uid", "oem_site_uid"]
SEARCH_PLAN_VERSION = "supplier_context_evidence_v2"
SCORING_RULES_VERSION = "supplier_context_scoring_v2_1"
STRUCTURAL_IMPORTANCE_REFERENCES = {
    "allocated_mass_kg": 130.0,
    "path_count": 172.0,
    "system_count": 46.0,
    "component_count": 54.0,
}


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


def contains_normalized_term(text: str, term: Any) -> bool:
    normalized_term = normalize_text(term)
    if not normalized_term:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", text))


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


def canonicalize_url(url: Any) -> str:
    parsed = urllib.parse.urlparse(clean(url))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return clean(url)
    filtered_query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source"}
    ]
    normalized = parsed._replace(
        scheme="https",
        netloc=parsed.netloc.lower(),
        query=urllib.parse.urlencode(filtered_query),
        fragment="",
    )
    return urllib.parse.urlunparse(normalized).rstrip("/")


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
        terms = [term for term in rule["terms"] if contains_normalized_term(normalized, term)]
        if category == "incident_industriel" and set(terms) <= {"fire"} and any(
            phrase in normalized
            for phrase in ("fire barrier", "fire protection", "fire resistant", "fire safety", "fire performance")
        ):
            terms = []
        if not terms:
            continue
        hits[category] = sorted(set(terms))
        weighted += float(rule["weight"]) * min(1.0, 0.55 + 0.15 * len(terms))
    return clamp(weighted / 8.0), hits


def positive_signal_hits(text: str) -> tuple[float, dict[str, list[str]]]:
    normalized = normalize_text(text)
    weighted = 0.0
    hits: dict[str, list[str]] = {}
    for category, rule in POSITIVE_SIGNAL_RULES.items():
        terms = [term for term in rule["terms"] if contains_normalized_term(normalized, term)]
        if not terms:
            continue
        hits[category] = sorted(set(terms))
        weighted += float(rule["weight"]) * min(1.0, 0.55 + 0.15 * len(terms))
    return clamp(weighted / 6.0), hits


def weighted_hits_score(
    hits: dict[str, list[str]],
    rules: dict[str, dict[str, Any]],
    denominator: float,
) -> float:
    weighted = 0.0
    for category, terms in hits.items():
        if not terms or category not in rules:
            continue
        weighted += float(rules[category]["weight"]) * min(1.0, 0.55 + 0.15 * len(terms))
    return clamp(weighted / denominator)


def aerospace_relevance(text: str) -> float:
    normalized = normalize_text(text)
    hits = sum(1 for term in AEROSPACE_TERMS if normalize_text(term) in normalized)
    return clamp(hits / 4.0)


def identity_tokens(value: Any) -> list[str]:
    return [
        token
        for token in supplier_slug(supplier_search_name(value)).split()
        if token not in IDENTITY_GENERIC_TOKENS
    ]


def official_candidate(supplier: str, result: dict[str, str]) -> bool:
    tokens = identity_tokens(supplier)
    if not tokens:
        return False
    domain = normalize_text(result.get("domain"))
    title = normalize_text(result.get("title"))
    description = normalize_text(result.get("description"))
    domain_tokens = re.findall(r"[a-z0-9]+", domain)
    domain_hit = any(token == tokens[0] or token.startswith(f"{tokens[0]}-") for token in domain_tokens)
    identity_hits = sum(1 for token in tokens if token in title or token in description)
    if len(tokens) == 1:
        return domain_hit and contains_normalized_term(f"{title} {description}", tokens[0])
    if domain_hit and tokens[0] in f"{title} {description}":
        return True
    return domain_hit and identity_hits >= min(2, len(tokens))


def identity_match_score(site: dict[str, str], result: dict[str, str], is_official: bool) -> float:
    tokens = identity_tokens(site.get("name"))
    if not tokens:
        return 0.0
    title = normalize_text(result.get("title"))
    description = normalize_text(result.get("description"))
    domain = normalize_text(result.get("domain"))
    content = f"{title} {description}"
    token_hits = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", content))
    token_ratio = token_hits / max(1, len(tokens))
    exact_name = normalize_text(supplier_search_name(site.get("name")))
    exact_hit = bool(exact_name and exact_name in content)
    domain_hit = any(re.search(rf"(?:^|[.-]){re.escape(token)}(?:[.-]|$)", domain) for token in tokens)
    location = normalize_text(search_location_label(site.get("location"), site.get("country_code")))
    location_hit = bool(location and location in content)
    business_context = any(
        contains_normalized_term(content, term)
        for term in (
            "aerospace",
            "aircraft",
            "company",
            "corporation",
            "factory",
            "facility",
            "group",
            "manufacturing",
            "plant",
            "production",
            "refinery",
            "smelter",
            "supplier",
        )
    )
    score = 0.58 * token_ratio + 0.18 * (1.0 if exact_hit else 0.0) + 0.14 * (1.0 if domain_hit else 0.0)
    score += 0.10 * (1.0 if location_hit else 0.0)
    if is_official:
        score = max(score, 0.9)
    elif len(tokens) == 1 and not (business_context and (location_hit or domain_hit or aerospace_relevance(content) > 0.0)):
        score = min(score, 0.3)
    return clamp(score)


def source_type(row: dict[str, Any]) -> str:
    domain = clean(row.get("domain")).lower()
    if safe_float(row.get("official_source_candidate")) > 0:
        return "source_officielle_fournisseur"
    if domain.endswith(".gov") or domain.endswith(".gouv.fr") or domain.endswith(".europa.eu"):
        return "autorite_publique"
    if domain in LOW_CONTEXT_DOMAINS:
        return "annuaire_reseau_social"
    if domain.endswith(".wikipedia.org"):
        return "encyclopedie"
    return "presse_ou_source_metier"


def publication_date_hint(text: Any) -> str:
    normalized = clean(text)
    iso_match = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b", normalized)
    if iso_match:
        return f"{iso_match.group(1)}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"
    year_match = re.search(r"\b((?:19|20)\d{2})\b", normalized)
    return year_match.group(1) if year_match else ""


def evidence_recency_factor(date_hint: Any) -> float:
    match = re.match(r"^((?:19|20)\d{2})", clean(date_hint))
    if not match:
        return 0.75
    evidence_year = int(match.group(1))
    current_year = datetime.now(timezone.utc).year
    if evidence_year > current_year + 1:
        return 0.5
    age = max(0, current_year - evidence_year)
    if age <= 2:
        return 1.0
    if age <= 5:
        return 0.8
    if age <= 10:
        return 0.5
    return 0.25


def sdd_effects(categories: Iterable[str]) -> str:
    effects: list[str] = []
    for category in categories:
        for effect in clean(SDD_EFFECTS_BY_CATEGORY.get(category)).split("|"):
            if effect and effect not in effects:
                effects.append(effect)
    return "|".join(effects)


def supplier_identity_in_segment(site: dict[str, str], segment: str) -> bool:
    segment = normalize_text(segment)
    exact_name = normalize_text(supplier_search_name(site.get("name")))
    if exact_name and contains_normalized_term(segment, exact_name):
        return True
    tokens = identity_tokens(site.get("name"))
    if not tokens:
        return False
    token_hits = sum(1 for token in tokens if contains_normalized_term(segment, token))
    return token_hits >= min(2, len(tokens))


def contextual_signal_hits(
    site: dict[str, str],
    text: str,
    hits: dict[str, list[str]],
    query_family: str,
) -> dict[str, list[str]]:
    allowed_categories = QUERY_FAMILY_RISK_CATEGORIES.get(query_family, set())
    if not allowed_categories:
        return {}
    segments = [
        segment.strip()
        for segment in re.split(r"(?:[.!?;|]+|\s+[…]{1,3}\s+)", normalize_text(text))
        if segment.strip()
    ]
    out: dict[str, list[str]] = {}
    for category, terms in hits.items():
        if category not in allowed_categories:
            continue
        accepted_terms: list[str] = []
        for term in terms:
            for segment in segments:
                if not supplier_identity_in_segment(site, segment):
                    continue
                if not contains_normalized_term(segment, term):
                    continue
                if category == "incident_industriel" and any(
                    phrase in segment for phrase in AMBIGUOUS_PLACE_EVENT_PHRASES
                ):
                    continue
                if category == "incident_industriel":
                    event_consequence = any(
                        contains_normalized_term(segment, value)
                        for value in (
                            "accident",
                            "closed",
                            "closure",
                            "damaged",
                            "destroyed",
                            "disrupted",
                            "explosion",
                            "halted",
                            "hit",
                            "injured",
                            "killed",
                            "shutdown",
                            "stopped",
                        )
                    )
                    industrial_context = any(
                        contains_normalized_term(segment, value)
                        for value in (
                            "factory",
                            "facility",
                            "industrial",
                            "manufacturing",
                            "plant",
                            "production",
                            "refinery",
                            "site",
                            "smelter",
                            "warehouse",
                        )
                    )
                    if term in {"flood", "storm", "hurricane", "cyclone", "typhoon", "fire"} and not (
                        event_consequence and industrial_context
                    ):
                        continue
                if category == "qualite_conformite" and any(
                    contains_normalized_term(segment, value)
                    for value in ("certification", "certified", "approved", "strict compliance", "conformite des sieges")
                ):
                    continue
                if category == "dependance_source_unique" and any(
                    phrase in segment
                    for phrase in ("reduced dependency", "reduced its dependency", "reduced dependence")
                ):
                    continue
                accepted_terms.append(term)
                break
        if accepted_terms:
            out[category] = sorted(set(accepted_terms))
    return out


def contextual_positive_hits(
    site: dict[str, str],
    text: str,
    hits: dict[str, list[str]],
    query_family: str,
) -> dict[str, list[str]]:
    allowed_categories = QUERY_FAMILY_POSITIVE_CATEGORIES.get(query_family, set())
    if not allowed_categories:
        return {}
    segments = [
        segment.strip()
        for segment in re.split(r"(?:[.!?;|]+|\s+[…]{1,3}\s+)", normalize_text(text))
        if segment.strip()
    ]
    out: dict[str, list[str]] = {}
    for category, terms in hits.items():
        if category not in allowed_categories:
            continue
        accepted = [
            term
            for term in terms
            if any(
                supplier_identity_in_segment(site, segment)
                and contains_normalized_term(segment, term)
                for segment in segments
            )
        ]
        if accepted:
            out[category] = sorted(set(accepted))
    return out


def score_result(site: dict[str, str], result: dict[str, str], query_family: str = "contexte_general") -> dict[str, Any]:
    claim_text = " ".join([result.get("title", ""), result.get("description", "")])
    text = " ".join([claim_text, result.get("domain", "")])
    _raw_weak_score, raw_hits = signal_hits(claim_text)
    _raw_positive_score, raw_positive_hits = positive_signal_hits(claim_text)
    aero_score = aerospace_relevance(text)
    is_official = official_candidate(site.get("name", ""), result)
    identity_score = identity_match_score(site, result, is_official)
    gated_hits = (
        contextual_signal_hits(site, claim_text, raw_hits, query_family)
        if query_family in RISK_QUERY_FAMILIES and identity_score >= 0.45
        else {}
    )
    positive_hits = (
        contextual_positive_hits(site, claim_text, raw_positive_hits, query_family)
        if identity_score >= 0.45
        else {}
    )
    date_hint = publication_date_hint(text)
    recency_factor = evidence_recency_factor(date_hint)
    weak_score = weighted_hits_score(gated_hits, SIGNAL_RULES, 8.0) * recency_factor
    positive_score = weighted_hits_score(positive_hits, POSITIVE_SIGNAL_RULES, 6.0)
    base = {
        **result,
        "canonical_url": canonicalize_url(result.get("url")),
        "signal_categories": "|".join(sorted(gated_hits)),
        "signal_hits": json.dumps(gated_hits, ensure_ascii=False, sort_keys=True),
        "weak_signal_score": round(weak_score, 4),
        "positive_signal_categories": "|".join(sorted(positive_hits)),
        "positive_signal_hits": json.dumps(positive_hits, ensure_ascii=False, sort_keys=True),
        "resilience_evidence_score": round(positive_score, 4),
        "aerospace_relevance_score": round(aero_score, 4),
        "official_source_candidate": 1 if is_official else 0,
        "identity_match_score": round(identity_score, 4),
        "publication_date_hint": date_hint,
        "recency_factor": round(recency_factor, 4),
    }
    base["source_type"] = source_type(base)
    quality = source_quality_score(base)
    base["source_quality_score"] = round(quality, 4)
    signal_basis = max(weak_score, positive_score, 0.35 * aero_score)
    evidence_strength = clamp(identity_score * quality * signal_basis)
    base["evidence_strength_score"] = round(evidence_strength, 4)
    if identity_score < 0.35:
        verification = "identite_non_confirmee"
    elif is_official and query_family in {"identite_specialite", "certification_qualite", "capacite_resilience"}:
        verification = "source_primaire_a_consulter"
    elif quality >= 0.7 and evidence_strength >= 0.18:
        verification = "indice_fort_a_verifier"
    else:
        verification = "indice_serp_a_confirmer"
    base["verification_status"] = verification
    base["potential_sdd_effects"] = sdd_effects([*gated_hits, *positive_hits])
    return base


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
        -max(business_score, safe_float(row.get("evidence_strength_score"))),
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


def structural_importance_score(site: dict[str, str], max_mass: float, max_path_count: float) -> float:
    mass = max(0.0, safe_float(site.get("allocated_mass_kg")))
    paths = max(0.0, safe_float(site.get("path_count")))
    mass_score = math.log1p(mass) / math.log1p(STRUCTURAL_IMPORTANCE_REFERENCES["allocated_mass_kg"])
    path_score = math.log1p(paths) / math.log1p(STRUCTURAL_IMPORTANCE_REFERENCES["path_count"])
    return clamp(0.55 * mass_score + 0.45 * path_score)


def summarize_site(
    site: dict[str, str],
    query: str,
    provider: str,
    status: str,
    retrieved_at: str,
    rows: list[dict[str, Any]],
    *,
    max_mass: float = 1.0,
    max_path_count: float = 1.0,
    structural_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relevant_rows = [row for row in rows if safe_float(row.get("identity_match_score")) >= 0.35]
    candidate_rows = [
        row
        for row in relevant_rows
        if safe_float(row.get("evidence_strength_score")) >= 0.05
    ]
    source_count = len({clean(row.get("domain")) for row in relevant_rows if clean(row.get("domain"))})
    result_count = len(rows)
    weak_score = max((safe_float(row.get("evidence_strength_score")) for row in candidate_rows if clean(row.get("signal_categories"))), default=0.0)
    resilience_score = max(
        (safe_float(row.get("evidence_strength_score")) for row in candidate_rows if clean(row.get("positive_signal_categories"))),
        default=0.0,
    )
    aero_score = max((safe_float(row.get("aerospace_relevance_score")) for row in relevant_rows), default=0.0)
    official = any(safe_float(row.get("official_source_candidate")) > 0 for row in relevant_rows)
    signal_counter: Counter[str] = Counter()
    positive_counter: Counter[str] = Counter()
    hit_counter: Counter[str] = Counter()
    category_strength: dict[str, float] = defaultdict(float)
    for row in candidate_rows:
        evidence_strength = safe_float(row.get("evidence_strength_score"))
        for category in clean(row.get("signal_categories")).split("|"):
            if category:
                signal_counter[category] += 1
                category_strength[category] = max(category_strength[category], evidence_strength)
        for category in clean(row.get("positive_signal_categories")).split("|"):
            if category:
                positive_counter[category] += 1
                category_strength[category] = max(category_strength[category], evidence_strength)
        try:
            hits = json.loads(clean(row.get("signal_hits")) or "{}")
        except json.JSONDecodeError:
            hits = {}
        if isinstance(hits, dict):
            for category, terms in hits.items():
                if isinstance(terms, list):
                    for term in terms:
                        hit_counter[f"{category}:{term}"] += 1
    identity_mean = (
        sum(safe_float(row.get("identity_match_score")) for row in relevant_rows) / len(relevant_rows)
        if relevant_rows
        else 0.0
    )
    quality_max = max((safe_float(row.get("source_quality_score")) for row in relevant_rows), default=0.0)
    data_confidence = clamp(
        0.25 * min(len(relevant_rows) / 8.0, 1.0)
        + 0.20 * min(source_count / 4.0, 1.0)
        + 0.20 * identity_mean
        + 0.15 * quality_max
        + 0.20 * (1.0 if official else 0.0)
    )
    fragility_score = max((category_strength.get(category, 0.0) for category in FRAGILITY_CATEGORIES), default=0.0)
    hazard_score = max((category_strength.get(category, 0.0) for category in HAZARD_CATEGORIES), default=0.0)
    dependency_score = category_strength.get("dependance_source_unique", 0.0)
    risk_rows = [row for row in candidate_rows if clean(row.get("signal_categories"))]
    risk_evidence_confidence = max(
        (
            safe_float(row.get("identity_match_score"))
            * safe_float(row.get("source_quality_score"))
            for row in risk_rows
        ),
        default=0.0,
    )
    documentary_risk = 0.45 * fragility_score + 0.30 * hazard_score + 0.25 * dependency_score
    criticality = clamp(documentary_risk * (1.0 - 0.25 * resilience_score))
    structural_context = structural_context or {}
    structural_score = safe_float(
        structural_context.get("score"),
        structural_importance_score(site, max_mass, max_path_count),
    )
    top = relevant_rows[0] if relevant_rows else (rows[0] if rows else {})
    categories = "|".join(category for category, _ in signal_counter.most_common())
    positive_categories = "|".join(category for category, _ in positive_counter.most_common())
    hits_label = "|".join(hit for hit, _ in hit_counter.most_common(12))
    if categories:
        short = f"Indices SERP a confirmer: {categories}"
        if positive_categories:
            short += f" ; resilience observee: {positive_categories}"
    elif status.startswith("error:"):
        short = "Recherche bloquee ou erreur outil, a relancer via Bright Data ou plus tard"
    elif relevant_rows:
        short = "Identite ou specialite documentee, aucun incident fournisseur confirme"
    else:
        short = "Aucun resultat dont l'identite fournisseur est suffisamment confirmee"
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
        "search_plan_version": SEARCH_PLAN_VERSION,
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
        "observed_fragility_score": round(fragility_score, 4),
        "hazard_exposure_evidence_score": round(hazard_score, 4),
        "dependency_evidence_score": round(dependency_score, 4),
        "resilience_evidence_score": round(resilience_score, 4),
        "resilience_categories": positive_categories,
        "structural_importance_score": round(structural_score, 4),
        "structural_path_count": int(safe_float(structural_context.get("path_count"), site.get("path_count"))),
        "structural_system_count": int(safe_float(structural_context.get("system_count"))),
        "structural_component_count": int(safe_float(structural_context.get("component_count"))),
        "structural_score_basis": clean(structural_context.get("basis")) or "masse et nombre de chemins; substituabilite non documentee",
        "verified_evidence_count": 0,
        "candidate_evidence_count": sum(
            1
            for row in candidate_rows
            if clean(row.get("signal_categories")) or clean(row.get("positive_signal_categories"))
        ),
        "model_activation_status": "inactive",
        "documentary_criticality_score": round(criticality, 4),
        "aerospace_relevance_score": round(aero_score, 4),
        "official_source_candidate": 1 if official else 0,
        "data_confidence_score": round(data_confidence, 4),
        "risk_evidence_confidence_score": round(risk_evidence_confidence, 4),
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


def build_structural_context(path_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"paths": set(), "systems": set(), "components": set(), "mass_kg": 0.0}
    )
    for row in path_rows:
        site_uids = {clean(row.get(column)) for column in PATH_SITE_COLUMNS if clean(row.get(column))}
        mass = max(0.0, safe_float(row.get("path_mass_kg")))
        for site_uid in site_uids:
            if clean(row.get("path_id")):
                stats[site_uid]["paths"].add(clean(row.get("path_id")))
            if clean(row.get("system")):
                stats[site_uid]["systems"].add(clean(row.get("system")))
            if clean(row.get("component")):
                stats[site_uid]["components"].add(clean(row.get("component")))
            stats[site_uid]["mass_kg"] += mass
    out: dict[str, dict[str, Any]] = {}
    for site_uid, values in stats.items():
        mass_score = math.log1p(values["mass_kg"]) / math.log1p(STRUCTURAL_IMPORTANCE_REFERENCES["allocated_mass_kg"])
        path_score = math.log1p(len(values["paths"])) / math.log1p(STRUCTURAL_IMPORTANCE_REFERENCES["path_count"])
        system_score = len(values["systems"]) / STRUCTURAL_IMPORTANCE_REFERENCES["system_count"]
        component_score = len(values["components"]) / STRUCTURAL_IMPORTANCE_REFERENCES["component_count"]
        out[site_uid] = {
            "score": clamp(0.30 * mass_score + 0.25 * path_score + 0.25 * system_score + 0.20 * component_score),
            "path_count": len(values["paths"]),
            "system_count": len(values["systems"]),
            "component_count": len(values["components"]),
            "basis": "masse allouee, chemins, systemes et composants; alternatives qualifiees encore non documentees",
        }
    return out


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


def build_query_plan(
    site: dict[str, str],
    template: str,
    hints: dict[str, str] | None = None,
    profile: str = "evidence",
) -> list[dict[str, str]]:
    def planned_row(family: str, query: str) -> dict[str, str]:
        digest = hashlib.sha1(
            "|".join([SEARCH_PLAN_VERSION, clean(site.get("site_uid")), family, query]).encode("utf-8")
        ).hexdigest()[:16]
        return {"query_id": f"qry-{digest}", "query_family": family, "query": query}

    if profile == "basic":
        return [
            planned_row("contexte_general", query)
            for query in build_queries(site, template, hints)
        ]
    supplier = supplier_search_name(site.get("name"))
    planned_site = {**site, "name": supplier}
    plan: list[dict[str, str]] = []
    for family, family_template in QUERY_FAMILY_TEMPLATES:
        query = re.sub(r"\s+", " ", build_query(planned_site, family_template, hints)).strip()
        if query and query not in {row["query"] for row in plan}:
            plan.append(planned_row(family, query))
    return plan


def selected_sites(rows: list[dict[str, str]], *, offset: int, limit: int, exclude_oem: bool) -> list[dict[str, str]]:
    filtered = [
        row for row in rows
        if clean(row.get("site_uid")) and clean(row.get("name")) and not (exclude_oem and "OEM" in clean(row.get("roles")).split("|"))
    ]
    filtered.sort(key=lambda row: (-safe_float(row.get("allocated_mass_kg")), clean(row.get("name"))))
    if limit <= 0:
        return filtered[offset:]
    return filtered[offset: offset + limit]


def build_evidence_rows(result_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in result_rows:
        if safe_float(row.get("identity_match_score")) < 0.35:
            continue
        negative_categories = [value for value in clean(row.get("signal_categories")).split("|") if value]
        positive_categories = [value for value in clean(row.get("positive_signal_categories")).split("|") if value]
        categories: list[tuple[str, str]] = [
            *[("risque", category) for category in negative_categories],
            *[("resilience", category) for category in positive_categories],
        ]
        if safe_float(row.get("evidence_strength_score")) < 0.05:
            categories = []
        if not categories and (
            safe_float(row.get("official_source_candidate")) > 0
            or safe_float(row.get("aerospace_relevance_score")) >= 0.5
        ):
            categories.append(("capacite_specialite", "identite_specialite"))
        for evidence_kind, category in categories:
            canonical_url = clean(row.get("canonical_url")) or canonicalize_url(row.get("url"))
            key = (clean(row.get("site_uid")), canonical_url, category)
            digest = hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:16]
            description = clean(row.get("description"))
            title = clean(row.get("title"))
            query_id = clean(row.get("query_id"))
            candidate = {
                "evidence_id": f"ctx-{digest}",
                "site_uid": row.get("site_uid", ""),
                "supplier": row.get("supplier", ""),
                "roles": row.get("roles", ""),
                "country_code": row.get("country_code", ""),
                "location": row.get("location", ""),
                "query_family": row.get("query_family", ""),
                "evidence_kind": evidence_kind,
                "evidence_category": category,
                "fact_summary": (description or title)[:700],
                "publication_date_hint": row.get("publication_date_hint", ""),
                "recency_factor": row.get("recency_factor", ""),
                "source_title": title,
                "source_url": row.get("url", ""),
                "canonical_url": canonical_url,
                "source_domain": row.get("domain", ""),
                "source_type": row.get("source_type", ""),
                "source_quality_score": row.get("source_quality_score", ""),
                "identity_match_score": row.get("identity_match_score", ""),
                "evidence_strength_score": row.get("evidence_strength_score", ""),
                "verification_status": row.get("verification_status", ""),
                "evidence_status": (
                    "rejected"
                    if clean(row.get("verification_status")) == "identite_non_confirmee"
                    else "candidate"
                ),
                "model_activation_status": "inactive",
                "potential_sdd_effects": row.get("potential_sdd_effects", ""),
                "retrieved_at_utc": row.get("retrieved_at_utc", ""),
                "query_id": query_id,
                "query": row.get("query", ""),
                "serp_rank_original": row.get("serp_rank_original", ""),
                "result_rank": row.get("result_rank", ""),
                "discovery_count": 1,
                "query_ids": query_id,
            }
            existing = evidence_by_key.get(key)
            if existing is None:
                evidence_by_key[key] = candidate
                continue
            query_ids = {
                value
                for value in clean(existing.get("query_ids")).split("|")
                if value
            }
            if query_id:
                query_ids.add(query_id)
            discovery_count = int(safe_float(existing.get("discovery_count"), 1.0)) + 1
            if safe_float(candidate.get("evidence_strength_score")) > safe_float(existing.get("evidence_strength_score")):
                evidence_by_key[key] = candidate
                existing = candidate
            existing["discovery_count"] = discovery_count
            existing["query_ids"] = "|".join(sorted(query_ids))
    evidence_rows = list(evidence_by_key.values())
    evidence_rows.sort(
        key=lambda row: (
            clean(row.get("supplier")),
            -safe_float(row.get("evidence_strength_score")),
            clean(row.get("evidence_category")),
        )
    )
    return evidence_rows


def write_summary_json(
    path: Path,
    summaries: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> None:
    status_counts = Counter(clean(row.get("context_search_status")) for row in summaries)
    signal_counts: Counter[str] = Counter()
    for row in summaries:
        for category in clean(row.get("weak_signal_categories")).split("|"):
            if category:
                signal_counts[category] += 1
    payload = {
        "schema_version": "poc2026.supply_geo_case.supplier_context.v2",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "scoring_rules_version": SCORING_RULES_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_count": len(summaries),
        "result_count": len(result_rows),
        "evidence_count": len(evidence_rows),
        "evidence_status_counts": dict(Counter(clean(row.get("verification_status")) for row in evidence_rows)),
        "query_family_counts": dict(Counter(clean(row.get("query_family")) for row in result_rows)),
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
    parser.add_argument("--max-results", type=int, default=28, help="Maximum total results retained per site.")
    parser.add_argument("--results-per-query", type=int, default=4, help="Maximum results parsed for each query.")
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
        "--query-profile",
        choices=["basic", "evidence"],
        default="evidence",
        help="evidence runs targeted identity, incident, finance, quality, capacity, dependency and climate queries.",
    )
    parser.add_argument(
        "--max-queries-per-site",
        type=int,
        default=0,
        help=(
            "Limit queries per site. 0 runs the complete selected query profile."
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
    path_rows = read_csv(args.paths)
    site_hints = build_site_hints(path_rows)
    structural_by_site = build_structural_context(path_rows)

    result_path = args.output_dir / "supplier_context_results.csv"
    summary_path = args.output_dir / "supplier_context_summary.csv"
    evidence_path = args.output_dir / "supplier_context_evidence.csv"
    attempt_path = args.output_dir / "supplier_context_search_attempts.csv"
    json_path = args.output_dir.parent / "summaries" / "supplier_context_summary.json"
    existing_results = read_csv(result_path)
    existing_summaries = read_csv(summary_path)
    existing_attempts = read_csv(attempt_path)
    done = {
        clean(row.get("site_uid"))
        for row in existing_summaries
        if clean(row.get("site_uid"))
        and clean(row.get("search_plan_version")) == SEARCH_PLAN_VERSION
        and not args.refresh
    }
    existing_results_by_site: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in existing_results:
        existing_results_by_site[clean(row.get("site_uid"))].append(row)
    existing_summary_by_site = {clean(row.get("site_uid")): row for row in existing_summaries if clean(row.get("site_uid"))}

    work = [site for site in selected_sites(sites, offset=args.offset, limit=args.limit, exclude_oem=args.exclude_oem) if clean(site.get("site_uid")) not in done]
    work_site_uids = {clean(site.get("site_uid")) for site in work}
    result_rows = [row for row in existing_results if clean(row.get("site_uid")) not in work_site_uids]
    summary_rows = [row for row in existing_summaries if clean(row.get("site_uid")) not in work_site_uids]
    attempt_rows = [row for row in existing_attempts if clean(row.get("site_uid")) not in work_site_uids]
    max_mass = max((safe_float(site.get("allocated_mass_kg")) for site in sites), default=1.0)
    max_path_count = max((safe_float(site.get("path_count")) for site in sites), default=1.0)

    for index, site in enumerate(work, 1):
        hints = site_hints.get(clean(site.get("site_uid")), {})
        query_plan = (
            build_query_plan(site, args.query_template, hints, args.query_profile)
            if args.fallback_queries
            else build_query_plan(site, args.query_template, hints, "basic")[:1]
        )
        if args.max_queries_per_site > 0:
            query_plan = query_plan[:args.max_queries_per_site]
        query = " | ".join(row["query"] for row in query_plan)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        print(f"[{index}/{len(work)}] {site.get('name')} :: {query_plan[0]['query']} ({len(query_plan)} requete(s))")
        status = "ok"
        scored_rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        query_errors: list[str] = []
        for query_item in query_plan:
            if len(scored_rows) >= args.max_results:
                break
            search_query = query_item["query"]
            query_family = query_item["query_family"]
            requested_at = datetime.now(timezone.utc).isoformat()
            started = time.monotonic()
            raw_results: list[dict[str, str]] = []
            attempt_status = "ok"
            error_type = ""
            try:
                raw_results = search_results(
                    provider,
                    search_query,
                    max(1, args.results_per_query),
                    args.region,
                    args.serp_engine,
                )
            except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
                attempt_status = "error"
                error_type = type(exc).__name__
                query_errors.append(error_type)
                print(f"  -> {query_family}: error:{error_type}: {exc}", file=sys.stderr)
            attempt_rows.append(
                {
                    "query_id": query_item["query_id"],
                    "search_plan_version": SEARCH_PLAN_VERSION,
                    "scoring_rules_version": SCORING_RULES_VERSION,
                    "site_uid": site.get("site_uid", ""),
                    "supplier": site.get("name", ""),
                    "query_family": query_family,
                    "query": search_query,
                    "provider": provider,
                    "serp_engine": args.serp_engine,
                    "search_region": args.region,
                    "requested_at_utc": requested_at,
                    "duration_seconds": round(time.monotonic() - started, 4),
                    "status": attempt_status if raw_results or attempt_status == "error" else "no_results",
                    "error_type": error_type,
                    "result_count": len(raw_results),
                }
            )
            for original_rank, result in enumerate(raw_results, 1):
                url = clean(result.get("url"))
                canonical_url = canonicalize_url(url)
                if not url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)
                scored = score_result(site, result, query_family)
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
                        "query_id": query_item["query_id"],
                        "query_family": query_family,
                        "search_plan_version": SEARCH_PLAN_VERSION,
                        "provider": provider,
                        "serp_engine": args.serp_engine,
                        "search_region": args.region,
                        "search_status": attempt_status,
                        "retrieved_at_utc": retrieved_at,
                        "result_rank": len(scored_rows) + 1,
                        "serp_rank_original": original_rank,
                        **scored,
                    }
                )
                if len(scored_rows) >= args.max_results:
                    break
        if not scored_rows:
            status = f"error:{query_errors[-1]}" if query_errors else "no_results"
        elif query_errors:
            status = "ok_partiel"
        if not scored_rows and status.startswith("error:") and clean(site.get("site_uid")) in existing_summary_by_site:
            stale_summary = dict(existing_summary_by_site[clean(site.get("site_uid"))])
            stale_summary["context_search_status"] = f"cache_conserve_apres_{status}"
            summary_rows.append(stale_summary)
            result_rows.extend(existing_results_by_site.get(clean(site.get("site_uid")), []))
            continue
        rerank_result_rows(scored_rows)
        result_rows.extend(scored_rows)
        summary_rows.append(
            summarize_site(
                site,
                query,
                provider,
                status,
                retrieved_at,
                scored_rows,
                max_mass=max_mass,
                max_path_count=max_path_count,
                structural_context=structural_by_site.get(clean(site.get("site_uid")), {}),
            )
        )
        evidence_rows = build_evidence_rows(result_rows)
        write_csv(result_path, result_rows, RESULT_FIELDS)
        write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
        write_csv(evidence_path, evidence_rows, EVIDENCE_FIELDS)
        write_csv(attempt_path, attempt_rows, SEARCH_ATTEMPT_FIELDS)
        write_summary_json(json_path, summary_rows, result_rows, evidence_rows)
        if index < len(work) and args.delay > 0:
            time.sleep(args.delay)

    evidence_rows = build_evidence_rows(result_rows)
    write_csv(result_path, result_rows, RESULT_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    write_csv(evidence_path, evidence_rows, EVIDENCE_FIELDS)
    write_csv(attempt_path, attempt_rows, SEARCH_ATTEMPT_FIELDS)
    write_summary_json(json_path, summary_rows, result_rows, evidence_rows)
    print(f"Wrote {len(summary_rows)} supplier context summaries: {summary_path}")
    print(f"Wrote {len(result_rows)} supplier context result rows: {result_path}")
    print(f"Wrote {len(evidence_rows)} supplier context evidence rows: {evidence_path}")
    print(f"Wrote {len(attempt_rows)} supplier context search attempts: {attempt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
