"""CORE connector — aggregated open-access repositories (API key required).

Set ``CORE_API_KEY`` to enable. Docs: https://api.core.ac.uk/docs/v3
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "core"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.core.ac.uk/v3/search/works"
def parse_results(payload: dict) -> list[dict]:
    out = []
    for rec in payload.get("results") or []:
        doi = rec.get("doi")
        url = rec.get("downloadUrl") or (f"https://doi.org/{doi}" if doi else
                                          f"https://core.ac.uk/works/{rec.get('id')}")
        dtype = str(rec.get("documentType") or "").lower()
        typ = "preprint" if "preprint" in dtype else "journal-article"
        out.append(
            make_record(
                service=SERVICE,
                title=rec.get("title") or "",
                url=url,
                doi=doi,
                authors=[a.get("name", "") for a in rec.get("authors") or []],
                published=str(rec.get("yearPublished") or "") or None,
                publisher=rec.get("publisher") or "CORE",
                type_=typ,
                abstract=rec.get("abstract"),
                extra={"is_oa": bool(rec.get("isOpenAccess", True)),
                       "core_id": rec.get("id"), "download_url": rec.get("downloadUrl")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    api_key = os.environ.get("CORE_API_KEY", "").strip()
    if not api_key:
        return []
    payload = http.get_json(
        BASE,
        params={"q": query, "limit": max(1, min(limit, 100)), "offset": max(0, offset)},
        headers={"Authorization": f"Bearer {api_key}"}, timeout=25,
    )
    return parse_results(payload)
