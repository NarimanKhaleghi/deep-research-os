"""Claims — construction, numeric extraction, modality checks, lifecycle helpers."""

from __future__ import annotations

import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

TYPES = {"statistic", "causal", "forecast", "opinion", "methodological", "definition"}
KINDS = {"empirical", "normative", "theoretical"}
STATUSES = {"unverified", "supported", "weakly_supported", "contradicted",
            "unverifiable", "resolved", "outweighed"}

# Prohibition / obligation / permission signals (EN + FA) used to check that a
# normative claim is backed by a quote that actually says something normative.
MODALITY_RE = re.compile(
    r"(ممنوع|مجاز\s*نیست|غیرمجاز|نمی[\u200c\s]?توان|نباید|الزام|اجبار|باید|موظف|"
    r"مجوز|ممنوعیت|prohibit\w*|forbidden|banned|must\s+not|may\s+not|shall\s+not|"
    r"not\s+allowed|required\s+to|obligat\w*|mandat\w*|shall|must\b)",
    re.I)

OFFICIAL_SOURCE_TYPES = {
    "regulation", "law", "official-statistics", "government-report", "filing",
    "central-bank", "regulator", "official", "statistics",
}


def has_modality(text: str) -> bool:
    return bool(MODALITY_RE.search(text or ""))


def build_claim(
    text: str,
    *,
    type_: str = "statistic",
    kind: str = "empirical",
    tags: list[str] | None = None,
    angles: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    critical: bool = False,
) -> dict:
    if type_ not in TYPES:
        raise ValueError(f"invalid claim type '{type_}'")
    if kind not in KINDS:
        raise ValueError(f"invalid claim kind '{kind}'")
    numbers = util.extract_numbers(text)
    return {
        "text": text.strip(),
        "type": type_,
        "kind": kind,
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "angles": angles or [],
        "evidence_ids": evidence_ids or [],
        "critical": critical,
        "numbers": numbers,
        "modality": has_modality(text),
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


def modality_mismatch(claim: dict, evidence_rows: list[dict]) -> bool:
    """True when a claim uses normative language its quotes do not.

    Catches the classic overclaim: "the regulator *prohibits* X" supported only
    by a quote that says the bank bears final responsibility (no prohibition).
    """
    if not has_modality(claim.get("text", "")):
        return False
    return not any(has_modality(ev.get("quote", "")) for ev in evidence_rows)


def official_sources(sources: list[dict]) -> list[dict]:
    return [s for s in sources
            if (s.get("type") or "") in OFFICIAL_SOURCE_TYPES
            or (s.get("extra") or {}).get("official") is True]


def staleness_months(source: dict) -> int | None:
    """Age in months of the document date (as_of / published), if known."""
    from datetime import datetime, timezone
    date_str = str(source.get("as_of") or source.get("published") or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if not m:
        m = re.match(r"(\d{4})-(\d{2})", date_str)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        day = 1
    else:
        y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        dt = datetime(y, mo, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    return max(0, (now.year - dt.year) * 12 + (now.month - dt.month))


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
