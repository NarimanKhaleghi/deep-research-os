"""Crossref connector — DOI metadata truth + retraction/correction relations.

Keyless. Polite pool via ``mailto``.
Docs: https://api.crossref.org
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "crossref"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.crossref.org"
MAILTO = os.environ.get("RESEARCH_OS_MAILTO", "deep-research-os@users.noreply.github.com")


def _year(item: dict) -> str | None:
    for key in ("issued", "published", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return None


def _authors(item: dict) -> list[str]:
    out = []
    for a in item.get("author", []) or []:
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if name:
            out.append(name)
    return out


def parse_items(payload: dict) -> list[dict]:
    items = ((payload.get("message") or {}).get("items")) or []
    out = []
    for it in items:
        updates = it.get("update-to") or []
        retraction = any(
            (u.get("type") or "").lower() in ("retraction", "retraction-of-publication")
            or "retract" in (u.get("label") or "").lower()
            for u in (updates if isinstance(updates, list) else [])
        )
        titles = it.get("title") or []
        out.append(
            make_record(
                service=SERVICE,
                title=(titles[0] if titles else "") or "",
                url=it.get("URL") or (f"https://doi.org/{it.get('DOI')}" if it.get("DOI") else ""),
                doi=it.get("DOI"),
                authors=_authors(it),
                published=_year(it),
                publisher=it.get("publisher"),
                type_="journal-article",
                abstract=it.get("abstract"),
                extra={
                    "container": (it.get("container-title") or [None])[0],
                    "update_to": updates,
                    "is_retraction_relation": retraction,
                    "cited_by": it.get("is-referenced-by-count", 0),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    payload = http.get_json(
        f"{BASE}/works",
        params={"query": query, "rows": max(1, min(limit, 100)),
                "offset": max(0, offset), "mailto": MAILTO},
    )
    return parse_items(payload)


def get_work(doi: str) -> dict | None:
    """Fetch canonical metadata by DOI for citation verification."""
    try:
        payload = http.get_json(f"{BASE}/works/{doi}", params={"mailto": MAILTO})
    except Exception:
        return None
    items = parse_items({"message": {"items": [payload.get("message", {})]}})
    return items[0] if items else None
