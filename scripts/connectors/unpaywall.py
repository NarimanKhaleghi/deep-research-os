"""Unpaywall connector (helper) — legal OA full-text locations for a DOI.

Not a search source: used by ``read --doi`` to find an open full text.
Docs: https://unpaywall.org/products/api
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import http  # noqa: E402

SERVICE = "unpaywall"
DOMAINS = ["academic"]
TIER = 1
KIND = "helper"
BASE = "https://api.unpaywall.org/v2"
MAILTO = os.environ.get("RESEARCH_OS_MAILTO", "deep-research-os@users.noreply.github.com")


def find_oa(doi: str) -> dict | None:
    """Return {pdf_url, landing_url, is_oa, oa_status} for a DOI, or None."""
    try:
        payload = http.get_json(f"{BASE}/{doi}", params={"email": MAILTO})
    except Exception:
        return None
    best = payload.get("best_oa_location") or {}
    return {
        "doi": doi,
        "is_oa": bool(payload.get("is_oa")),
        "oa_status": payload.get("oa_status"),
        "pdf_url": best.get("url_for_pdf"),
        "landing_url": best.get("url") or payload.get("doi_url"),
        "title": payload.get("title"),
        "year": payload.get("year"),
        "journal": payload.get("journal_name"),
        "license": best.get("license"),
    }


def search(query: str, limit: int = 10, **kw) -> list[dict]:  # pragma: no cover
    return []
