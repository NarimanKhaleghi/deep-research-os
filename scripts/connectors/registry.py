"""Connector registry, catalog metadata and the ε-greedy search router.

Learning-aware: weights come from ``source_stats.json`` (Beta-smoothed success
rates), with a mandatory exploration floor so the router never tunnel-visions.
"""

from __future__ import annotations

import importlib
import os
import random
import re
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe  # noqa: E402
from learning import sources_learning  # noqa: E402
from lib import util  # noqa: E402

# name -> (module, kind, domains, tier, description)
CATALOG: dict[str, dict] = {
    "openalex": {"kind": "search", "domains": ["academic"], "tier": 1,
                 "about": "240M+ scholarly works, citation graph, retraction flags"},
    "crossref": {"kind": "search", "domains": ["academic"], "tier": 1,
                 "about": "DOI metadata truth, retraction/correction relations"},
    "arxiv": {"kind": "search", "domains": ["academic"], "tier": 2,
              "about": "Preprints (CS/ML/physics); label as preprint"},
    "pubmed": {"kind": "search", "domains": ["academic"], "tier": 1,
               "about": "Biomedical literature, MeSH terms, retraction types"},
    "gdelt": {"kind": "search", "domains": ["news"], "tier": 2,
              "about": "Global multilingual news coverage (artlist API)"},
    "worldbank": {"kind": "search", "domains": ["economics", "statistics"], "tier": 1,
                  "about": "Indicator time series, 200+ economies"},
    "datacommons": {"kind": "search", "domains": ["statistics", "economics"], "tier": 1,
                    "about": "Knowledge-graph statistics across gov datasets"},
    "census": {"kind": "search", "domains": ["statistics"], "tier": 1,
               "about": "US Census dataset catalog + tables"},
    "wikidata": {"kind": "search", "domains": ["entities"], "tier": 2,
                 "about": "Entity disambiguation and identity anchors"},
    "sec_edgar": {"kind": "search", "domains": ["filings"], "tier": 1,
                  "about": "SEC full-text search + company filings"},
    "hackernews": {"kind": "search", "domains": ["tech"], "tier": 3,
                   "about": "Tech pulse (leads only — promote to primary sources)"},
    "web": {"kind": "search", "domains": ["web"], "tier": 2,
            "about": "Web search via local SearXNG or DuckDuckGo lite"},
    "unpaywall": {"kind": "helper", "domains": ["academic"], "tier": 1,
                  "about": "Legal OA full-text locations for a DOI"},
}

# source -> module path (all live in connectors/)
_MODULE = {name: f"connectors.{name}" for name in CATALOG}

EPSILON_DEFAULT = 0.15
EPSILON_NEW_DOMAIN = 0.25
PICK_COUNT = {"quick": 2, "standard": 3, "deep": 3, "max": 4}


def catalog() -> list[dict]:
    return [{"name": k, **v} for k, v in CATALOG.items()]


def _load(name: str):
    return importlib.import_module(_MODULE[name])


def searchable(domains: list[str] | None = None) -> list[str]:
    names = [n for n, m in CATALOG.items() if m["kind"] == "search"]
    disabled = set(sources_learning.load_stats().get("disabled_sources") or [])
    names = [n for n in names if n not in disabled]
    if domains:
        want = {d.strip().lower() for d in domains if d.strip()}
        names = [n for n in names if want & {m.lower() for m in CATALOG[n]["domains"]}]
    return names


def choose_sources(
    domains: list[str] | None,
    k: int,
    seed: int | None = None,
    stats: dict | None = None,
) -> list[str]:
    """ε-greedy pick of k searchable sources for the given domains."""
    names = searchable(domains)
    if not names:
        return []
    if len(names) <= k:
        return names
    stats = stats if stats is not None else sources_learning.load_stats()
    rng = random.Random(seed)
    total_attempts = sum(
        sources_learning.attempts_for(stats, n, domains) for n in names
    )
    eps = EPSILON_NEW_DOMAIN if total_attempts < 20 else EPSILON_DEFAULT
    picked: list[str] = []
    pool = list(names)
    while pool and len(picked) < k:
        if rng.random() < eps:
            choice = rng.choice(pool)
        else:
            weights = [sources_learning.weight(stats, n, domains) for n in pool]
            choice = rng.choices(pool, weights=weights, k=1)[0]
        picked.append(choice)
        pool.remove(choice)
    return picked


def route(
    query: str,
    *,
    domains: list[str] | None = None,
    limit: int = 10,
    profile: str = "standard",
    override_source: str | None = None,
    seed: int | None = None,
) -> dict:
    """Run the chosen connectors and aggregate normalized records.

    Returns {records, chosen, provenance, failures}. Never raises for a single
    connector failure — failures are reported so the caller can journal them.
    """
    if override_source:
        if override_source not in CATALOG:
            raise ValueError(f"unknown source '{override_source}'")
        chosen = [override_source]
    else:
        k = PICK_COUNT.get(profile, 3)
        chosen = choose_sources(domains, k, seed=seed)

    records: list[dict] = []
    failures: list[dict] = []
    provenance: dict[str, int] = {}
    per_source = max(2, limit // max(1, len(chosen)))

    for name in chosen:
        try:
            mod = _load(name)
            got = mod.search(query, limit=per_source)
            for r in got:
                r.setdefault("service", name)
            provenance[name] = len(got)
            records.extend(got)
        except Exception as exc:  # noqa: BLE001 — single-source failure is data
            failures.append({"service": name, "error": f"{type(exc).__name__}: {util.truncate(str(exc), 160)}"})
            provenance[name] = 0

    merged = _merge_provenance(records)
    return {
        "records": merged[: max(limit, 1) * 2],
        "chosen": chosen,
        "provenance": provenance,
        "failures": failures,
    }


def _merge_provenance(records: list[dict]) -> list[dict]:
    """Dedupe across services, recording multi-service sightings."""
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for r in records:
        key = (r.get("doi") or "").lower() or util.normalize_text(r.get("url") or "") or util.normalize_text(r.get("title") or "")
        if not key:
            continue
        if key in by_key:
            seen = by_key[key]["extra"].setdefault("seen_in", [])
            if r["service"] not in seen:
                seen.append(r["service"])
            continue
        r["extra"].setdefault("seen_in", [r["service"]])
        by_key[key] = r
        order.append(key)
    return [by_key[k] for k in order]


def extract_doi_from_url(url: str) -> str | None:
    m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", url or "")
    return m.group(0).rstrip(".") if m else None
