"""Europe PMC connector — biomedical literature, PMC full text and preprints.

Keyless. Docs: https://europepmc.org/RestfulWebService
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

SERVICE = "europepmc"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _url(rec: dict) -> str:
    pmcid = rec.get("pmcid")
    if pmcid:
        return f"https://europepmc.org/article/PMC/{pmcid}"
    pmid = rec.get("pmid")
    if pmid:
        return f"https://europepmc.org/article/MED/{pmid}"
    doi = rec.get("doi")
    if doi:
        return f"https://doi.org/{doi}"
    return "https://europepmc.org/"


def parse_results(payload: dict) -> list[dict]:
    out = []
    for rec in (payload.get("resultList") or {}).get("result") or []:
        source = (rec.get("source") or "").upper()
        is_preprint = source == "PPR" or "preprint" in str(rec.get("pubType") or "").lower()
        out.append(
            make_record(
                service=SERVICE,
                title=rec.get("title") or "",
                url=_url(rec),
                doi=rec.get("doi"),
                authors=[a.strip() for a in (rec.get("authorString") or "").split(",") if a.strip()],
                published=str(rec.get("pubYear") or "") or None,
                publisher=rec.get("journalTitle") or rec.get("bookOrReportDetails", {}).get("publisher"),
                type_="preprint" if is_preprint else "journal-article",
                abstract=rec.get("abstractText"),
                extra={
                    "pmid": rec.get("pmid"), "pmcid": rec.get("pmcid"),
                    "source": source, "is_oa": str(rec.get("isOpenAccess") or "").upper() == "Y",
                    "in_epmc": str(rec.get("inEPMC") or "").upper() == "Y",
                    "has_pdf": str(rec.get("hasPDF") or "").upper() == "Y",
                    "license": rec.get("license"),
                    "cited_by": rec.get("citedByCount", 0),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    payload = http.get_json(
        BASE,
        params={
            "query": query, "format": "json", "resultType": "core",
            "pageSize": max(1, min(limit, 100)),
        },
    )
    return parse_results(payload)
