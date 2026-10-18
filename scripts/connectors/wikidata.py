"""Wikidata connector — entity disambiguation & identity anchors (tier 2).

Identity/relationships are what Wikidata is for; numbers under dispute are not.
Docs: https://www.wikidata.org/w/api.php
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "wikidata"
DOMAINS = ["entities"]
TIER = 2
API = "https://www.wikidata.org/w/api.php"


def parse_search(payload: dict) -> list[dict]:
    out = []
    for e in payload.get("search", []) or []:
        out.append(
            make_record(
                service=SERVICE,
                title=e.get("label") or e.get("id", ""),
                url=e.get("concepturi") or f"https://www.wikidata.org/wiki/{e.get('id')}",
                type_="webpage",
                publisher="Wikidata",
                abstract=e.get("description"),
                extra={"qid": e.get("id"), "match": e.get("match", {}).get("text")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, language: str = "en", **kw) -> list[dict]:
    payload = http.get_json(
        API,
        params={
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "uselang": language,
            "limit": max(1, min(limit, 25)),
            "format": "json",
        },
    )
    return parse_search(payload)


def entity(qid: str, language: str = "en") -> dict | None:
    """Fetch claims for a Q-id (identity map building)."""
    try:
        payload = http.get_json(
            API,
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "labels|claims|descriptions",
                "languages": language,
                "format": "json",
            },
        )
    except Exception:
        return None
    ent = (payload.get("entities") or {}).get(qid) or {}
    labels = ent.get("labels") or {}
    claims = ent.get("claims") or {}
    return {
        "qid": qid,
        "label": (labels.get(language) or {}).get("value"),
        "description": ((ent.get("descriptions") or {}).get(language) or {}).get("value"),
        "claim_count": len(claims),
        "raw": ent,
    }
