"""Data Commons connector — knowledge-graph statistics across gov datasets.

Keyless base path (optional API key raises limits). Best-effort: the public API
shapes have changed over time, so every call degrades gracefully to [].
Docs: https://docs.datacommons.org/api/
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "datacommons"
DOMAINS = ["statistics", "economics"]
TIER = 1
V2 = "https://api.datacommons.org/v2"


def parse_search(payload: dict) -> list[dict]:
    """Parse /v2/search or legacy /v1/search entity results."""
    out = []
    for sec in payload.get("section", []) or []:  # legacy v1 shape
        for e in sec.get("entity", []) or []:
            out.append(
                make_record(
                    service=SERVICE,
                    title=e.get("name", ""),
                    url=f"https://datacommons.org/browser/{e.get('dcid')}",
                    type_="statistics",
                    publisher="Data Commons",
                    extra={"dcid": e.get("dcid"), "type": e.get("type")},
                )
            )
    for e in payload.get("entities", []) or []:  # v2-ish shape
        out.append(
            make_record(
                service=SERVICE,
                title=e.get("name") or e.get("dcid", ""),
                url=f"https://datacommons.org/browser/{e.get('dcid')}",
                type_="statistics",
                publisher="Data Commons",
                extra={"dcid": e.get("dcid")},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, **kw) -> list[dict]:
    try:
        payload = http.get_json(f"{V2}/search", params={"query": query, "per_page": limit})
    except Exception:
        return []
    return parse_search(payload)[:limit]


def observation(variable_dcid: str, entity_dcid: str, year: str = "2024") -> dict | None:
    """Fetch a single observation value (for anchoring a number)."""
    try:
        payload = http.post_json(
            f"{V2}/observation",
            {
                "variable": {"dcids": [variable_dcid]},
                "entity": {"dcids": [entity_dcid]},
                "date": year,
            },
        )
    except Exception:
        return None
    return payload or None
