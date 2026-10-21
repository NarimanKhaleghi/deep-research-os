"""Zenodo connector — open repository records, datasets and preprints.

Keyless. Docs: https://developers.zenodo.org/
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "zenodo"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://zenodo.org/api/records"


def parse_results(payload: dict) -> list[dict]:
    out = []
    for hit in (payload.get("hits") or {}).get("hits") or []:
        md = hit.get("metadata") or {}
        links = hit.get("links") or {}
        rtype = str((md.get("resource_type") or {}).get("type") or "").lower()
        typ = "dataset" if "dataset" in rtype else "preprint" if "preprint" in rtype else "journal-article"
        url = links.get("self_html") or links.get("html") or (f"https://doi.org/{md['doi']}" if md.get("doi") else "")
        out.append(
            make_record(
                service=SERVICE,
                title=md.get("title") or "",
                url=url,
                doi=md.get("doi"),
                authors=[c.get("name", "") for c in md.get("creators") or []],
                published=str(md.get("publication_date") or "")[:10] or None,
                publisher="Zenodo",
                type_=typ,
                abstract=md.get("description"),
                extra={"is_oa": True, "zenodo_id": hit.get("id"),
                       "resource_type": rtype, "license": (md.get("license") or {}).get("id")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    page = max(1, (offset // max(1, limit)) + 1)
    payload = http.get_json(
        BASE,
        params={"q": query, "size": max(1, min(limit, 100)), "page": page,
                "sort": "bestmatch"},
        timeout=25,
    )
    return parse_results(payload)
