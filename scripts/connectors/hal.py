"""HAL connector — French open archive across disciplines.

Keyless. Docs: https://api.archives-ouvertes.fr/docs
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "hal"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.archives-ouvertes.fr/search/"
FL = "uri_s,doiId_s,title_s,authFullName_s,producedDateY_i,abstract_s,docType_s,openAccess_bool,journalTitle_s,language_s"


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def parse_results(payload: dict) -> list[dict]:
    out = []
    for rec in (payload.get("response") or {}).get("docs") or []:
        dtype = str(rec.get("docType_s") or "").upper()
        typ = "preprint" if dtype in ("PREPRINT", "UNDEFINED") else "journal-article"
        out.append(
            make_record(
                service=SERVICE,
                title=_first(rec.get("title_s")) or "",
                url=rec.get("uri_s") or (f"https://doi.org/{rec['doiId_s']}" if rec.get("doiId_s") else ""),
                doi=rec.get("doiId_s"),
                authors=rec.get("authFullName_s") or [],
                published=str(rec.get("producedDateY_i") or "") or None,
                publisher=_first(rec.get("journalTitle_s")) or "HAL",
                type_=typ,
                abstract=_first(rec.get("abstract_s")),
                extra={"is_oa": bool(rec.get("openAccess_bool")), "doc_type": dtype,
                       "language": rec.get("language_s")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    payload = http.get_json(
        BASE,
        params={"q": query, "fl": FL, "rows": max(1, min(limit, 100)),
                "start": max(0, offset), "wt": "json"},
        timeout=25,
    )
    return parse_results(payload)
