"""Claims — construction, numeric extraction, lifecycle helpers."""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

TYPES = {"statistic", "causal", "forecast", "opinion", "methodological", "definition"}
STATUSES = {"unverified", "supported", "weakly_supported", "contradicted",
            "unverifiable", "resolved", "outweighed"}


def build_claim(
    text: str,
    *,
    type_: str = "statistic",
    tags: list[str] | None = None,
    angles: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    critical: bool = False,
) -> dict:
    if type_ not in TYPES:
        raise ValueError(f"invalid claim type '{type_}'")
    numbers = util.extract_numbers(text)
    return {
        "text": text.strip(),
        "type": type_,
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "angles": angles or [],
        "evidence_ids": evidence_ids or [],
        "critical": critical,
        "numbers": numbers,
        "status": "unverified",
        "status_reason": "",
        "contradiction_ids": [],
        "verified_at": None,
    }


def number_conflicts(claim: dict, evidence_rows: list[dict]) -> list[dict]:
    """Numbers in the claim that don't appear (precision-aware) in its evidence quotes."""
    problems = []
    quotes_numbers: list[dict] = []
    for ev in evidence_rows:
        quotes_numbers.extend(ev.get("numbers") or [])
        quotes_numbers.extend(util.extract_numbers(ev.get("quote", "")))
    for n in claim.get("numbers") or []:
        if not util.numbers_match(n, quotes_numbers):
            problems.append(n)
    return problems


def confidence_from(status: str, sources: list[dict]) -> str:
    """Map verification status + source bands to a confidence label."""
    bands = {s.get("credibility", {}).get("band") for s in sources if s.get("credibility")}
    if status == "supported":
        if "A" in bands:
            return "high"
        return "medium"
    if status in ("weakly_supported", "resolved"):
        return "low"
    return "low"
