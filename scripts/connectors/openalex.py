"""OpenAlex connector — 240M+ scholarly works, citation graph, retraction flags.

Keyless. Polite pool via ``mailto``.
Docs: https://docs.openalex.org
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "openalex"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.openalex.org"
MAILTO = os.environ.get("RESEARCH_OS_MAILTO", "deep-research-os@users.noreply.github.com")


def _abstract_from_inverted(inv: dict | None) -> str | None:
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions) or None


def parse_works(payload: dict) -> list[dict]:
    out = []
    for w in payload.get("results", []):
        authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])]
        loc = w.get("primary_location") or {}
        url = loc.get("landing_page_url") or w.get("doi") or w.get("id", "")
        out.append(
            make_record(
                service=SERVICE,
                title=w.get("display_name") or w.get("title") or "",
                url=url,
                doi=w.get("doi"),
                authors=[a for a in authors if a],
                published=str(w.get("publication_year") or "") or None,
                publisher=((loc.get("source") or {}).get("display_name")) or None,
                type_="journal-article",
                abstract=_abstract_from_inverted(w.get("abstract_inverted_index")),
                extra={
                    "cited_by_count": w.get("cited_by_count", 0),
                    "is_retracted": bool(w.get("is_retracted")),
                    "open_access": (w.get("open_access") or {}).get("is_oa"),
                    "id": w.get("id"),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    payload = http.get_json(
        f"{BASE}/works",
        params={
            "search": query,
            "per-page": max(1, min(limit, 25)),
            "mailto": MAILTO,
            "select": "id,doi,display_name,publication_year,authorships,primary_location,"
                      "abstract_inverted_index,is_retracted,cited_by_count,open_access",
        },
    )
    return parse_works(payload)


def get_work(doi: str) -> dict | None:
    """Fetch one work by DOI for verification (retraction flag, title)."""
    try:
        w = http.get_json(f"{BASE}/works/doi:{doi}", params={"mailto": MAILTO})
    except Exception:
        return None
    recs = parse_works({"results": [w]})
    return recs[0] if recs else None
