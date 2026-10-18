"""PubMed connector (E-utilities) — biomedical literature, retraction types, MeSH.

Keyless (polite rate ≤3 req/s).
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "pubmed"
DOMAINS = ["academic"]
TIER = 1
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def parse_esearch(payload: dict) -> list[str]:
    return ((payload.get("esearchresult") or {}).get("idlist")) or []


def parse_esummary(payload: dict) -> list[dict]:
    result = payload.get("result") or {}
    uids = result.get("uids") or []
    out = []
    for uid in uids:
        item = result.get(uid)
        if not item:
            continue
        authors = [a.get("name", "") for a in item.get("authors", [])]
        doi = None
        for aid in item.get("articleids", []) or []:
            if aid.get("idtype") == "doi":
                doi = aid.get("value")
        pubtypes = item.get("pubtype") or []
        retracted = any("retract" in (p or "").lower() for p in pubtypes)
        out.append(
            make_record(
                service=SERVICE,
                title=item.get("title", ""),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                doi=doi,
                authors=[a for a in authors if a],
                published=(item.get("pubdate") or "")[:10] or None,
                publisher=item.get("fulljournalname") or item.get("source"),
                type_="journal-article",
                abstract=None,
                extra={
                    "pmid": uid,
                    "pubtype": pubtypes,
                    "is_retracted": retracted,
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    limit = max(1, min(limit, 25))
    es = http.get_json(
        f"{EUTILS}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json", "sort": "relevance"},
    )
    ids = parse_esearch(es)
    if not ids:
        return []
    summ = http.get_json(
        f"{EUTILS}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
    )
    return parse_esummary(summ)
