"""Source statistics — the data behind ε-greedy routing (Beta-smoothed)."""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import paths, util  # noqa: E402

STATS_FILE = "source_stats.json"
_PRIOR_ALPHA = 2.0  # Beta prior: never 0-confidence, never 100%
_PRIOR_BETA = 2.0
MIN_WEIGHT = 0.05


def _path():
    return paths.runtime_learning_dir() / STATS_FILE


def load_stats() -> dict:
    data = util.read_json(_path(), None)
    if data is None:
        data = {"schema": 1, "stats": {}}
    data.setdefault("stats", {})
    return data


def save_stats(stats: dict) -> None:
    util.write_json(_path(), stats)


def _bucket(stats: dict, source: str, domain: str) -> dict:
    src = stats["stats"].setdefault(source, {})
    return src.setdefault(domain or "general", {
        "attempts": 0, "yields": 0, "evidence": 0,
        "verified": 0, "failed_verify": 0, "fabricated": 0,
    })


def record_search(source: str, domains: list[str] | None, n_results: int) -> None:
    stats = load_stats()
    for d in (domains or ["general"]):
        b = _bucket(stats, source, d)
        b["attempts"] += 1
        b["yields"] += max(0, n_results)
    save_stats(stats)


def record_outcome(source: str, domain: str, outcome: str) -> None:
    """outcome ∈ {evidence, verified, failed_verify, fabricated, kept, dropped}."""
    stats = load_stats()
    b = _bucket(stats, source, domain or "general")
    if outcome in ("evidence", "kept"):
        b["evidence"] += 1
    elif outcome in b:
        b[outcome] += 1
    save_stats(stats)


def attempts_for(stats: dict, source: str, domains: list[str] | None) -> int:
    buckets = stats.get("stats", {}).get(source, {})
    if not domains:
        return sum(b.get("attempts", 0) for b in buckets.values())
    return sum(buckets.get(d, {}).get("attempts", 0) for d in domains)


def weight(stats: dict, source: str, domains: list[str] | None) -> float:
    """Beta-smoothed success weight for routing, floored at MIN_WEIGHT."""
    buckets = stats.get("stats", {}).get(source, {})
    use = [buckets[d] for d in domains if d in buckets] if domains else list(buckets.values())
    if not use:
        return (0 + _PRIOR_ALPHA) / (_PRIOR_ALPHA + _PRIOR_BETA)  # prior mean 0.5
    attempts = sum(b.get("attempts", 0) for b in use)
    successes = sum(b.get("yields", 0) + b.get("verified", 0) for b in use)
    w = (successes + _PRIOR_ALPHA) / (attempts + _PRIOR_ALPHA + _PRIOR_BETA)
    return max(MIN_WEIGHT, min(1.0, w))


def movers(stats: dict, limit: int = 8) -> list[dict]:
    """Top sources by attempt volume with yield + verify rates (for digests)."""
    rows = []
    for source, buckets in stats.get("stats", {}).items():
        a = sum(b.get("attempts", 0) for b in buckets.values())
        y = sum(b.get("yields", 0) for b in buckets.values())
        v = sum(b.get("verified", 0) for b in buckets.values())
        f = sum(b.get("fabricated", 0) + b.get("failed_verify", 0) for b in buckets.values())
        if a == 0:
            continue
        rows.append({
            "source": source,
            "attempts": a,
            "yield_rate": round(y / a, 2),
            "verified": v,
            "failed": f,
            "domains": ",".join(sorted(buckets.keys())),
        })
    rows.sort(key=lambda r: r["attempts"], reverse=True)
    return rows[:limit]
