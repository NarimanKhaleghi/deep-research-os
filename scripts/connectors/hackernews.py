"""Hacker News (Algolia) connector — tech pulse, tier 3 lead generation only.

Docs: https://hn.algolia.com/api
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "hackernews"
DOMAINS = ["tech"]
TIER = 3
BASE = "https://hn.algolia.com/api/v1"


def parse_hits(payload: dict) -> list[dict]:
    out = []
    for h in payload.get("hits", []) or []:
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        out.append(
            make_record(
                service=SERVICE,
                title=h.get("title") or h.get("story_title") or "",
                url=url,
                published=(h.get("created_at") or "")[:10] or None,
                publisher="Hacker News",
                type_="webpage",
                abstract=h.get("story_text"),
                extra={
                    "points": h.get("points"),
                    "num_comments": h.get("num_comments"),
                    "author": h.get("author"),
                    "hn_discussion": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    payload = http.get_json(
        f"{BASE}/search",
        params={"query": query, "tags": "story", "hitsPerPage": max(1, min(limit, 30))},
    )
    return parse_hits(payload)
