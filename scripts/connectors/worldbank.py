"""World Bank connector — indicator time series for 200+ economies (tier 1).

Keyless. Docs: https://datahelpdesk.worldbank.org/knowledgebase/topics/125589
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http, util  # noqa: E402

SERVICE = "worldbank"
DOMAINS = ["economics", "statistics"]
TIER = 1
BASE = "https://api.worldbank.org/v2"


def parse_indicators(payload: list) -> list[dict]:
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return []
    out = []
    for ind in payload[1]:
        out.append(
            make_record(
                service=SERVICE,
                title=ind.get("name", ""),
                url=f"https://data.worldbank.org/indicator/{ind.get('id')}",
                publisher="World Bank",
                type_="statistics",
                extra={"indicator_id": ind.get("id"), "source_note": ind.get("sourceNote")},
            )
        )
    return dedupe(out)


def parse_series(payload: list) -> list[dict]:
    """Parse an indicator data response into point records."""
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return []
    points = []
    for row in payload[1]:
        value = row.get("value")
        if value is None:
            continue
        points.append(
            {
                "country": (row.get("country") or {}).get("value"),
                "iso3": row.get("countryiso3code"),
                "indicator": (row.get("indicator") or {}).get("value"),
                "indicator_id": (row.get("indicator") or {}).get("id"),
                "year": row.get("date"),
                "value": value,
            }
        )
    return points


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    """Find indicators whose names match the query (fuzzy)."""
    payload = http.get_json(f"{BASE}/indicator", params={"format": "json", "per_page": 500})
    cands = parse_indicators(payload)
    q = util.normalize_text(query)
    ranked = sorted(cands, key=lambda r: util.fuzzy(q, util.normalize_text(r["title"])), reverse=True)
    scored = [r for r in ranked if util.fuzzy(q, util.normalize_text(r["title"])) >= 0.35]
    return (scored or ranked)[:limit]


def series(iso3: str, indicator_id: str, years: str = "2015:2026") -> list[dict]:
    """Pull data points for country + indicator (primary data for claims)."""
    payload = http.get_json(
        f"{BASE}/country/{iso3}/indicator/{indicator_id}",
        params={"format": "json", "per_page": 200, "date": years},
    )
    return parse_series(payload)
