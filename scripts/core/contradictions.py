"""Contradiction scanner + adjudication ladder.

Detects numeric and polarity conflicts between claims sharing topic tags, and
implements the resolution protocol in references/quality/contradiction-protocol.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

RESOLUTIONS = {"source_a_wins", "source_b_wins", "scope_difference",
               "outweighed", "unresolved_both", "superseded"}

STOPWORDS = {
    # english
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "that",
    "this", "these", "those", "it", "its", "as", "at", "from", "than", "then",
    "more", "less", "most", "least", "more", "may", "can", "could", "will",
    "would", "should", "about", "into", "over", "under", "up", "down", "out",
    # persian
    "و", "در", "به", "از", "که", "این", "آن", "است", "بود", "شد", "شده",
    "برای", "با", "را", "تا", "هم", "یا", "بر", "می", "نیز", "هر",
}

UP_WORDS = {
    "increase", "increased", "increases", "rise", "rises", "rose", "grew",
    "grow", "growing", "growth", "higher", "improved", "improvement", "up",
    "faster", "gain", "gains", "boost", "boosts",
    "افزایش", "رشد", "بالا", "بیشتر", "بهبود", "صعود",
}
DOWN_WORDS = {
    "decrease", "decreased", "decreases", "fall", "falls", "fell", "falling",
    "drop", "dropped", "drops", "decline", "declined", "declines", "lower",
    "worsened", "worse", "down", "slower", "loss", "losses", "cut", "cuts",
    "کاهش", "افت", "پایین", "کمتر", "بدتر", "نزول",
}


def _tokens(text: str) -> list[str]:
    toks = util.normalize_text(text).replace("/", " ").split()
    return [t for t in toks if len(t) > 2 and t not in STOPWORDS]


def subject_overlap(a: str, b: str) -> tuple[int, float]:
    ta, tb = set(_tokens(a)), set(_tokens(b))
    shared = ta & tb
    return len(shared), util.fuzzy(" ".join(sorted(ta)[:10]), " ".join(sorted(tb)[:10]))


def _direction(text: str) -> str | None:
    t = util.normalize_text(text)
    has_up = any(w in t for w in UP_WORDS)
    has_dn = any(w in t for w in DOWN_WORDS)
    if has_up and not has_dn:
        return "up"
    if has_dn and not has_up:
        return "down"
    return None


def _units_compatible(a: str | None, b: str | None) -> bool:
    groups = [{"%", "percent"}, {"bn", "billion"}, {"mn", "million"}, {None, ""}]
    for g in groups:
        if (a or "") in g and (b or "") in g:
            return True
    if a is None or b is None:
        return True
    return False


def _numeric_conflict(a: dict, b: dict) -> list[dict]:
    conflicts = []
    for na in a.get("numbers") or []:
        for nb in b.get("numbers") or []:
            if not _units_compatible(na.get("unit"), nb.get("unit")):
                continue
            if util.numbers_match(na, [nb]) or util.numbers_match(nb, [na]):
                continue
            va, vb = na.get("value"), nb.get("value")
            rel = abs(va - vb) / max(abs(va), abs(vb), 1e-9)
            if rel <= 0.05:
                continue
            conflicts.append({"a": na, "b": nb})
    return conflicts


def scan(ledger, min_shared_tokens: int = 2) -> list[dict]:
    """Find new contradiction candidates; record them and return the CX records."""
    claims = [c for c in ledger.claims() if c.get("type") != "definition"]
    existing = {(tuple(sorted(c["claim_ids"])), c["kind"]) for c in ledger.contradictions()}
    created: list[dict] = []

    for i, a in enumerate(claims):
        for b in claims[i + 1 :]:
            tags_a, tags_b = set(a.get("tags") or []), set(b.get("tags") or [])
            if not (tags_a & tags_b):
                continue
            shared, sim = subject_overlap(a.get("text", ""), b.get("text", ""))
            if shared < min_shared_tokens and sim < 0.5:
                continue

            kind, detail = None, None
            num_conf = _numeric_conflict(a, b)
            if num_conf:
                kind = "numeric"
                c0 = num_conf[0]
                detail = (f"{a['id']} says {c0['a'].get('raw')} but {b['id']} says "
                          f"{c0['b'].get('raw')} on shared topic {sorted(tags_a & tags_b)}")
            else:
                da, db_ = _direction(a.get("text", "")), _direction(b.get("text", ""))
                if da and db_ and da != db_:
                    kind = "polarity"
                    detail = (f"{a['id']} signals '{da}' while {b['id']} signals '{db_}' "
                              f"on shared topic {sorted(tags_a & tags_b)}")

            if not kind:
                continue
            key = (tuple(sorted([a["id"], b["id"]])), kind)
            if key in existing:
                continue
            severity = "high" if (a.get("critical") or b.get("critical")) else "medium"
            cx = ledger.add_contradiction({
                "claim_ids": sorted([a["id"], b["id"]]),
                "kind": kind,
                "severity": severity,
                "detail": detail,
                "status": "open",
                "resolution": None,
                "rationale": None,
                "resolved_by": None,
                "resolved_at": None,
            })
            for cid in cx["claim_ids"]:
                c = ledger.claim(cid)
                ids = list(c.get("contradiction_ids") or [])
                if cx["id"] not in ids:
                    ids.append(cx["id"])
                    ledger.update_claim(cid, contradiction_ids=ids,
                                        status=("contradicted" if c.get("status") not in ("outweighed",) else c.get("status")),
                                        status_reason=f"conflict {cx['id']} ({kind})")
            existing.add(key)
            created.append(cx)
    return created


def adjudicate(ledger, cxid: str, resolution: str, rationale: str, by: str = "agent") -> dict:
    if resolution not in RESOLUTIONS:
        raise ValueError(f"invalid resolution '{resolution}'")
    cx = ledger.contradiction(cxid)
    if cx is None:
        raise KeyError(f"contradiction {cxid} not found")
    a_id, b_id = cx["claim_ids"][0], cx["claim_ids"][1]

    cx = ledger.update_contradiction(
        cxid, status="adjudicated", resolution=resolution,
        rationale=rationale, resolved_by=by, resolved_at=util.utcnow_iso(),
    )
    if resolution == "source_a_wins":
        ledger.update_claim(b_id, status="outweighed", status_reason=f"{cxid}: {resolution}")
    elif resolution == "source_b_wins":
        ledger.update_claim(a_id, status="outweighed", status_reason=f"{cxid}: {resolution}")
    elif resolution == "superseded":
        for cid in (a_id, b_id):
            ledger.update_claim(cid, status="outweighed", status_reason=f"{cxid}: superseded")
    elif resolution == "outweighed":
        for cid in (a_id, b_id):
            ledger.update_claim(cid, status="weakly_supported",
                                status_reason=f"{cxid}: both outweighed by external evidence")
    elif resolution == "scope_difference":
        for cid in (a_id, b_id):
            ledger.update_claim(cid, status="resolved",
                                status_reason=f"{cxid}: scope difference documented")
    # unresolved_both: statuses stay; the report shows both sides.
    return cx
