"""Budget manager — profiles as ceilings, exceptions recorded, spend journaled."""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

PROFILES: dict[str, dict] = {
    "quick":    {"searches": 3,  "sources_read": 3,  "evidence": 10, "claims": 5,
                 "verify_passes": 1, "preferences": 0, "max_spend_usd": 0},
    "standard": {"searches": 8,  "sources_read": 5,  "evidence": 25, "claims": 15,
                 "verify_passes": 2, "preferences": 1, "max_spend_usd": 0},
    "deep":     {"searches": 20, "sources_read": 8,  "evidence": 60, "claims": 40,
                 "verify_passes": 3, "preferences": 2, "max_spend_usd": 2},
    "max":      {"searches": 40, "sources_read": 20, "evidence": 150, "claims": 100,
                 "verify_passes": 5, "preferences": 3, "max_spend_usd": 20},
}

COUNTERS = ("searches", "sources_read", "evidence", "claims", "verify_passes")


def ceilings_for(profile: str, declared: dict | None = None) -> dict:
    base = dict(PROFILES.get(profile, PROFILES["standard"]))
    if declared:
        for k, v in declared.items():
            if k in base and isinstance(v, (int, float)) and not isinstance(v, bool):
                base[k] = v
    return base


def init_budget(state: dict, profile: str, declared: dict | None = None) -> dict:
    state["budget"] = {"ceilings": ceilings_for(profile, declared),
                       "spent_usd": 0.0, "exceptions": []}
    return state


def check(state: dict) -> dict:
    ceilings = (state.get("budget") or {}).get("ceilings") or {}
    counters = state.get("counters") or {}
    excused = {e.get("counter") for e in (state.get("budget") or {}).get("exceptions") or []}
    exceeded, usage = [], {}
    for c in COUNTERS:
        used = counters.get(c, 0)
        cap = ceilings.get(c)
        usage[c] = {"used": used, "ceiling": cap, "excused": c in excused}
        if cap is not None and used > cap and c not in excused:
            exceeded.append(c)
    spend = (state.get("budget") or {}).get("spent_usd", 0.0)
    cap_spend = ceilings.get("max_spend_usd")
    spend_ok = (cap_spend is None) or (spend <= cap_spend + 1e-9)
    return {
        "ok": not exceeded and spend_ok,
        "exceeded": exceeded + ([] if spend_ok else ["max_spend_usd"]),
        "usage": usage,
        "spent_usd": spend,
    }


def spend(state: dict, counter: str, n: int = 1) -> dict:
    if counter not in COUNTERS:
        raise ValueError(f"unknown counter '{counter}'")
    state.setdefault("counters", {})
    state["counters"][counter] = state["counters"].get(counter, 0) + n
    return state


def spend_usd(state: dict, amount: float) -> dict:
    state.setdefault("budget", {}).setdefault("spent_usd", 0.0)
    state["budget"]["spent_usd"] = round(state["budget"]["spent_usd"] + amount, 6)
    return state


def add_exception(state: dict, counter: str, reason: str) -> dict:
    b = state.setdefault("budget", {})
    b.setdefault("exceptions", []).append({
        "counter": counter,
        "ceiling": (b.get("ceilings") or {}).get(counter),
        "actual": (state.get("counters") or {}).get(counter),
        "reason": reason,
        "at": util.utcnow_iso(),
    })
    return state


def can_afford(state: dict, estimated_usd: float) -> bool:
    cap = ((state.get("budget") or {}).get("ceilings") or {}).get("max_spend_usd")
    if cap is None:
        return True
    return ((state.get("budget") or {}).get("spent_usd", 0.0) + estimated_usd) <= cap + 1e-9
