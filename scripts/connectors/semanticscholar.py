"""Semantic Scholar connector — citation graph and open-access PDFs.

Keyless (rate-limited). Docs: https://api.semanticscholar.org/graph/v1
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "semanticscholar"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = ("title,abstract,year,authors,externalIds,openAccessPdf,venue,"
          "publicationTypes,citationCount,publicationDate")


def parse_results(payload: dict) -> list[dict]:
    out = []
    for p in payload.get("data") or []:
        ids = p.get("externalIds") or {}
        pdf = (p.get("openAccessPdf") or {}).get("url")
        pubtypes = [str(t).lower() for t in (p.get("publicationTypes") or [])]
        typ = "preprint" if "preprint" in pubtypes else "journal-article"
        url = pdf or (f"https://doi.org/{ids['DOI']}" if ids.get("DOI") else
                      f"https://www.semanticscholar.org/paper/{p.get('paperId')}")
        out.append(
            make_record(
                service=SERVICE,
                title=p.get("title") or "",
                url=url,
                doi=ids.get("DOI"),
                authors=[a.get("name", "") for a in p.get("authors") or []],
                published=str(p.get("year") or "") or None,
                publisher=p.get("venue") or None,
                type_=typ,
                abstract=p.get("abstract"),
                extra={
                    "is_oa": bool(pdf), "pdf_url": pdf,
                    "cited_by": p.get("citationCount", 0),
                    "paper_id": p.get("paperId"),
                    "publication_date": p.get("publicationDate"),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    payload = http.get_json(
        BASE,
        params={"query": query, "limit": max(1, min(limit, 100)),
                "offset": max(0, offset), "fields": FIELDS},
        timeout=25,
    )
    return parse_results(payload)
