"""DOAJ connector — peer-reviewed open-access journals.

Keyless. Docs: https://doaj.org/api/v3/docs
"""

from __future__ import annotations

import os
import sys
from urllib.parse import quote

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "doaj"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://doaj.org/api/search/articles"


def _doi(bib: dict) -> str | None:
    for ident in bib.get("identifier") or []:
        if str(ident.get("type") or "").lower() == "doi":
            return ident.get("id")
    return None


def parse_results(payload: dict) -> list[dict]:
    out = []
    for item in payload.get("results") or []:
        bib = item.get("bibjson") or {}
        journal = bib.get("journal") or {}
        links = bib.get("link") or []
        url = ""
        for link in links:
            if str(link.get("type") or "").lower() in ("fulltext", "homepage"):
                url = link.get("url") or ""
                if link.get("type") == "fulltext":
                    break
        if not url:
            url = f"https://doaj.org/article/{item.get('id')}" if item.get("id") else "https://doaj.org/"
        authors = [a.get("name", "") for a in bib.get("author") or []]
        out.append(
            make_record(
                service=SERVICE,
                title=bib.get("title") or "",
                url=url,
                doi=_doi(bib),
                authors=[a for a in authors if a],
                published=str(bib.get("year") or "") or None,
                publisher=journal.get("title") or journal.get("publisher"),
                type_="journal-article",
                abstract=bib.get("abstract"),
                extra={
                    "is_oa": True, "license": (journal.get("license") or [{}])[0].get("type")
                    if isinstance(journal.get("license"), list) else journal.get("license"),
                    "journal": journal.get("title"),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    page = max(1, (offset // max(1, limit)) + 1)
    payload = http.get_json(
        f"{BASE}/{quote(query, safe='')}",
        params={"pageSize": max(1, min(limit, 100)), "page": page},
    )
    return parse_results(payload)
