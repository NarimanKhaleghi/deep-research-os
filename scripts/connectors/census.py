"""US Census connector — official statistics API (keyless, ≤500 queries/day).

Search mode fuzzy-matches the dataset catalog; data mode pulls table rows.
Docs: https://www.census.gov/data/developers.html
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http, util  # noqa: E402

SERVICE = "census"
DOMAINS = ["statistics"]
TIER = 1
BASE = "https://api.census.gov/data"
CATALOG = "https://api.census.gov/data.json"


def parse_catalog(payload: dict, query: str, limit: int) -> list[dict]:
    q = util.normalize_text(query)
    scored = []
    for ds in payload.get("dataset", []) or []:
        title = ds.get("title", "")
        score = util.fuzzy(q, util.normalize_text(title))
        if score >= 0.4:
            scored.append((score, ds))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, ds in scored[:limit]:
        out.append(
            make_record(
                service=SERVICE,
                title=ds.get("title", ""),
                url=ds.get("c_dataset") and f"https://data.census.gov/table?q={'+'.join(ds.get('c_dataset', []))}" or "https://data.census.gov",
                publisher=ds.get("publisher", {}).get("name") if isinstance(ds.get("publisher"), dict) else "US Census Bureau",
                type_="statistics",
                abstract=ds.get("description"),
                extra={"c_dataset": ds.get("c_dataset"), "vintage": ds.get("c_vintage")},
            )
        )
    return dedupe(out)


def parse_table(rows: list) -> list[dict]:
    """Convert Census array-of-arrays (header first) into dict rows."""
    if not rows or len(rows) < 2:
        return []
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:]]


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    payload = http.get_json(CATALOG)
    return parse_catalog(payload, query, limit)


def table(year: int, dataset: str, variables: list[str], for_clause: str) -> list[dict]:
    get = ",".join(["NAME", *variables])
    url = f"{BASE}/{year}/{dataset}?get={get}&for={for_clause}"
    rows = http.get_json(url)
    return parse_table(rows)
