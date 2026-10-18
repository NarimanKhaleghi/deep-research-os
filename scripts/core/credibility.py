"""Credibility scorer — deterministic heuristics for the 6-dimension rubric.

See references/quality/credibility-rubric.md. Heuristics may be overridden by
the agent (recorded in ``overrides[]``); overrides feed rubric-tuning proposals.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

GOV_IO_HINTS = {
    "gov", "europa.eu", "un.org", "worldbank.org", "oecd.org", "imf.org",
    "bis.org", "ecb.europa.eu", "who.int", "iea.org", "eia.gov", "eurostat",
    "europa.eu", "ac.uk", "edu",
}
PEER_VENUE_HINTS = {
    "nature.com", "science.org", "thelancet.com", "nejm.org", "bmj.com",
    "springer.com", "link.springer.com", "wiley.com", "tandfonline.com",
    "sagepub.com", "sciencedirect.com", "plos.org", "mdpi.com",
    "academic.oup.com", "cambridge.org", "ieee.org", "acm.org", "jstor.org",
    "pubmed.ncbi.nlm.nih.gov", "doi.org",
}
QUALITY_PRESS = {"reuters.com", "ft.com", "economist.com", "bbc.com", "bbc.co.uk",
                 "apnews.com", "nytimes.com", "washingtonpost.com", "lemonde.fr",
                 "spiegel.de", "elpais.com", "bloomberg.com", "wsj.com"}
COI_HINTS = {"sponsored by", "funded by", "commissioned by", "advertorial",
             "paid content", "in partnership with", "press release", "promoted"}
AGGREGATOR_HINTS = {"medium.com", "substack.com", "blogspot.", "wordpress.com",
                    "wixsite.com", "weebly.com", "quora.com"}

HALF_LIFE_DAYS = {
    "journal-article": 1095, "preprint": 548, "report": 730, "news": 540,
    "statistics": 540, "filing": 1825, "webpage": 400, "book": 3650,
    "dataset": 730, "other": 730,
}


def _domain(url: str) -> str:
    return util.domain_of(url or "")


def _has_hint(domain: str, hints: set[str]) -> bool:
    return any(h in domain for h in hints)


def _age_days(published: str | None) -> int | None:
    if not published:
        return None
    for fmt, ln in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            dt = datetime.strptime(published[:ln], fmt)
            return max(0, (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days)
        except ValueError:
            continue
    return None


def score_source(source: dict) -> dict:
    """Compute {score, band, dimensions, rationale, scored_at, overrides}."""
    domain = _domain(source.get("url", ""))
    stype = source.get("type", "other")
    extra = source.get("extra") or {}
    doi = (source.get("doi") or "").lower()
    press = _has_hint(domain, QUALITY_PRESS)
    peer_venue = any(h in (source.get("url") or "").lower() for h in PEER_VENUE_HINTS)
    gov_io = _has_hint(domain, GOV_IO_HINTS) or (source.get("url", "").endswith(".gov"))

    # 1) authority (25)
    authority = 10
    if gov_io:
        authority += 8
    if doi:
        authority += 4
    if source.get("authors"):
        authority += 2
    if press or peer_venue:
        authority += 3
    authority = min(25, authority)

    # 2) review / editorial (20)
    review = {
        "journal-article": 16 if doi else 13,
        "preprint": 8,
        "report": 15 if gov_io else 12,
        "statistics": 18,
        "filing": 18,
        "news": 14 if press else 9,
        "webpage": 6,
        "book": 14,
        "dataset": 15,
    }.get(stype, 8)
    if peer_venue:
        review = min(20, review + 3)
    if _has_hint(domain, AGGREGATOR_HINTS):
        review = max(0, review - 6)

    # 3) recency vs half-life (15)
    age = _age_days(source.get("published"))
    half = HALF_LIFE_DAYS.get(stype, 730)
    if age is None:
        recency = 9.0  # unknown date: mild penalty vs fresh
    else:
        recency = round(15.0 * (2 ** (-age / half)), 2)

    # 4) evidence quality (20)
    evidence = 8
    if doi:
        evidence += 4
    if (extra.get("cited_by_count") or 0) >= 20:
        evidence += 4
    if stype in ("statistics", "filing"):
        evidence += 6
    if source.get("published"):
        evidence += 2
    if _has_hint(domain, AGGREGATOR_HINTS):
        evidence = max(0, evidence - 5)
    evidence = min(20, evidence)

    # 5) conflicts of interest (10)
    haystack = util.normalize_text(
        " ".join([source.get("title", ""), source.get("abstract") or "", source.get("publisher") or ""])
    )
    coi = 8
    if any(h in haystack for h in COI_HINTS):
        coi -= 5
    if stype == "news" and not press:
        coi -= 1
    if stype == "webpage":
        coi -= 1
    coi = max(0, coi)

    # 6) retraction / integrity (10)
    integrity = 10
    if extra.get("is_retracted"):
        integrity = 0
    elif doi:
        integrity = 9  # checkable, pending verify
    else:
        integrity = 7  # cannot be retraction-checked

    dims = {
        "authority": round(min(25, authority), 2),
        "review": round(min(20, review), 2),
        "recency": round(min(15, recency), 2),
        "evidence": round(min(20, evidence), 2),
        "coi": round(coi, 2),
        "integrity": round(integrity, 2),
    }
    total = int(round(sum(dims.values())))

    # retraction cap: a retracted work is never load-bearing
    if extra.get("is_retracted"):
        total = min(total, 40)

    rationale_bits = [f"{stype} via {source.get('service', '?')}"]
    if doi:
        rationale_bits.append("DOI present")
    if gov_io:
        rationale_bits.append("official/institutional domain")
    if press:
        rationale_bits.append("quality-press domain")
    if peer_venue:
        rationale_bits.append("peer-reviewed venue signal")
    if age is not None:
        rationale_bits.append(f"{age}d old vs {half}d half-life")
    if extra.get("is_retracted"):
        rationale_bits.append("RETRACTED — capped at D")
    if any(h in haystack for h in COI_HINTS):
        rationale_bits.append("COI signals in text")

    result = {
        "score": total,
        "band": band_for(total),
        "dimensions": dims,
        "rationale": "; ".join(rationale_bits),
        "scored_at": util.utcnow_iso(),
        "overrides": (source.get("credibility") or {}).get("overrides", []),
    }
    for ov in result["overrides"]:
        d = ov.get("dimension")
        if d in dims:
            dims[d] = round(max(0.0, dims[d] + ov.get("delta", 0)), 2)
    result["score"] = int(round(sum(dims.values())))
    if extra.get("is_retracted"):
        result["score"] = min(result["score"], 40)
    result["band"] = band_for(result["score"])
    return result


def band_for(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"
