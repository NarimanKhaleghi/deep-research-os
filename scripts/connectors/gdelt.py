"""GDELT 2.0 connector — global multilingual news coverage (tier 2 context).

Keyless. Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "gdelt"
DOMAINS = ["news"]
TIER = 2
BASE = "https://api.gdeltproject.org/api/v2/doc/doc"


def parse_articles(payload: dict) -> list[dict]:
    out = []
    for a in payload.get("articles", []) or []:
        seendate = a.get("seendate") or ""
        published = None
        if len(seendate) >= 8:
            published = f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"
        out.append(
            make_record(
                service=SERVICE,
                title=a.get("title", ""),
                url=a.get("url", ""),
                published=published,
                publisher=a.get("domain"),
                type_="news",
                extra={
                    "language": a.get("language"),
                    "sourcecountry": a.get("sourcecountry"),
                    "socialimage": a.get("socialimage"),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, timespan: str = "1y", **kw) -> list[dict]:
    payload = http.get_json(
        BASE,
        params={
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max(1, min(limit, 50)),
            "timespan": timespan,
            "sort": "datedesc",
        },
    )
    return parse_articles(payload)
