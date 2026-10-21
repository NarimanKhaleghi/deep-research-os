"""OpenAIRE Graph connector — funded research outputs and repositories.

Keyless Graph API. Docs: https://graph.openaire.eu/docs/
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "openaire"
DOMAINS = ["academic"]
TIER = 1
BASE = "https://api.openaire.eu/graph/v1/researchProducts"


def _doi(rec: dict) -> str | None:
    for pid in rec.get("pid") or []:
        if str(pid.get("scheme") or "").lower() == "doi":
            return pid.get("value")
    for pid in rec.get("pids") or []:
        if str(pid.get("scheme") or "").lower() == "doi":
            return pid.get("value")
    return None


def _url(rec: dict) -> str:
    for inst in rec.get("instances") or []:
        urls = inst.get("urls") or []
        if urls:
            return urls[0]
        if inst.get("url"):
            return inst["url"]
    doi = _doi(rec)
    return f"https://doi.org/{doi}" if doi else "https://explore.openaire.eu/"


def parse_results(payload: dict) -> list[dict]:
    out = []
    for rec in payload.get("results") or []:
        access = rec.get("bestAccessRight") or {}
        if isinstance(access, dict):
            access = access.get("label") or access.get("code")
        out.append(
            make_record(
                service=SERVICE,
                title=rec.get("mainTitle") or rec.get("title") or "",
                url=_url(rec),
                doi=_doi(rec),
                authors=[a.get("fullName") or a.get("name") or "" for a in rec.get("authors") or []],
                published=str(rec.get("publicationDate") or "")[:10] or None,
                publisher=rec.get("publisher") or None,
                type_="preprint" if "preprint" in str(rec.get("type") or "").lower() else "journal-article",
                abstract=rec.get("description"),
                extra={"is_oa": str(access or "").upper() in ("OPEN", "OPEN ACCESS", "OA"),
                       "access_right": access, "openaire_id": rec.get("id")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    page = max(1, (offset // max(1, limit)) + 1)
    payload = http.get_json(
        BASE,
        params={"search": query, "type": "publication", "page": page,
                "pageSize": max(1, min(limit, 100))},
        timeout=25,
    )
    return parse_results(payload)
