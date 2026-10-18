"""Maintenance cycle — stats recompute, proposals, insights and digest.

Runs monthly (or after N runs). Autonomous classes only for safe operations;
promotions/retirements/merges always become proposals awaiting human approval.
See references/learning-protocol.md §9.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from learning import feedback, proposals, sources_learning  # noqa: E402
from lib import paths, util  # noqa: E402

LOW_YIELD_RATE = 0.05
LOW_YIELD_ATTEMPTS = 20
PROMOTE_USES = 3
PROMOTE_RATE = 0.6
RETIRE_USES = 5
RETIRE_RATE = 0.4
MERGE_SIMILARITY = 0.85


def load_capabilities() -> list[dict]:
    out = []
    for f in sorted(paths.capabilities_dir().glob("CAP-*.md")):
        meta, body = util.parse_front_matter(util.load_text(f))
        if not meta.get("id"):
            continue
        meta["_file"] = f.name
        meta["_body"] = body
        meta.setdefault("metrics", {})
        out.append(meta)
    return out


def sync_registry(caps: list[dict]) -> None:
    reg = {
        "schema": 1,
        "updated_at": util.utcnow_iso(),
        "capabilities": {
            c["id"]: {
                "name": c.get("name"),
                "status": c.get("status"),
                "level": c.get("level"),
                "tags": c.get("tags") or [],
                "file": c.get("_file"),
                "metrics": c.get("metrics") or {},
            }
            for c in caps
        },
    }
    util.write_json(paths.runtime_learning_dir() / "registry.json", reg)


def run(create_proposals: bool = True) -> dict:
    result: dict = {"nudges": [], "proposals": [], "insights_updated": False,
                    "digest_written": None, "disabled_sources": []}
    stats = sources_learning.load_stats()
    disabled = list(stats.get("disabled_sources") or [])

    # 1) low-yield source retirement proposals
    for source, buckets in (stats.get("stats") or {}).items():
        attempts = sum(b.get("attempts", 0) for b in buckets.values())
        yields = sum(b.get("yields", 0) for b in buckets.values())
        if attempts >= LOW_YIELD_ATTEMPTS and yields / attempts < LOW_YIELD_RATE and source not in disabled:
            result["nudges"].append(
                {"source": source, "attempts": attempts, "yields": yields,
                 "action": "propose-retire"}
            )
            if create_proposals:
                p = proposals.create(
                    "retire",
                    f"Retire low-yield source: {source}",
                    f"Source '{source}' returned ≤5% usable results across {attempts} attempts "
                    f"({yields} yields). Retiring removes it from routing; revert restores it.",
                    evidence={"stats": {"attempts": attempts, "yields": yields,
                                        "yield_rate": round(yields / attempts, 3)}},
                    changes=[{
                        "file": "source_stats.json",
                        "action": "modify",
                        "json_set": {"disabled_sources": disabled + [source]},
                        "diff_summary": f"adds '{source}' to disabled_sources",
                    }],
                    origin="maintain",
                )
                result["proposals"].append(p["id"])

    # 2) capability lifecycle
    caps = load_capabilities()
    active = {c["id"]: c for c in caps if c.get("status") == "active"}
    for c in caps:
        m = c.get("metrics") or {}
        uses, rate = m.get("uses", 0), m.get("success_rate") or 0
        if c.get("status") == "candidate" and uses >= PROMOTE_USES and rate >= PROMOTE_RATE:
            if create_proposals:
                p = proposals.create(
                    "promote",
                    f"Promote capability: {c.get('name', c['id'])}",
                    f"Candidate {c['id']} succeeded {uses} times at {rate:.0%} "
                    f"(threshold: ≥{PROMOTE_USES} uses, ≥{PROMOTE_RATE:.0%}). Promote to active.",
                    evidence={"stats": {"uses": uses, "success_rate": rate}},
                    changes=[
                        {"file": f"capabilities/{c['_file']}", "action": "modify",
                         "front_matter_set": {"status": "active"}},
                        {"file": "registry.json", "action": "modify",
                         "json_set": {f"capabilities.{c['id']}.status": "active"}},
                    ],
                    origin="maintain",
                )
                result["proposals"].append(p["id"])
        if c.get("status") == "active" and uses >= RETIRE_USES and rate < RETIRE_RATE:
            if create_proposals:
                p = proposals.create(
                    "retire",
                    f"Retire capability: {c.get('name', c['id'])}",
                    f"Active capability {c['id']} succeeded only {rate:.0%} over {uses} uses "
                    f"(threshold: <{RETIRE_RATE:.0%} over ≥{RETIRE_USES}). Retire it.",
                    evidence={"stats": {"uses": uses, "success_rate": rate}},
                    changes=[
                        {"file": f"capabilities/{c['_file']}", "action": "modify",
                         "front_matter_set": {"status": "retired"}},
                        {"file": "registry.json", "action": "modify",
                         "json_set": {f"capabilities.{c['id']}.status": "retired"}},
                    ],
                    origin="maintain",
                )
                result["proposals"].append(p["id"])

    # 3) merge clustering (candidates with near-identical triggers)
    cands = [c for c in caps if c.get("status") == "candidate"]
    seen_pairs: set[tuple[str, str]] = set()
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            sim = util.fuzzy(util.normalize_text(a.get("trigger", "")),
                             util.normalize_text(b.get("trigger", "")))
            key = tuple(sorted([a["id"], b["id"]]))
            if sim >= MERGE_SIMILARITY and key not in seen_pairs:
                seen_pairs.add(key)
                if create_proposals:
                    p = proposals.create(
                        "merge",
                        f"Merge overlapping candidates: {a['id']} + {b['id']}",
                        f"Trigger similarity {sim:.0%} ≥ {MERGE_SIMILARITY:.0%}. Merging avoids "
                        f"duplicate routines; the keeper is {a['id']}.",
                        evidence={"stats": {"similarity": round(sim, 2)}},
                        changes=[
                            {"file": f"capabilities/{b['_file']}", "action": "modify",
                             "front_matter_set": {"status": "retired", "merged_into": a["id"]}},
                            {"file": "registry.json", "action": "modify",
                             "json_set": {f"capabilities.{b['id']}.status": "retired"}},
                        ],
                        origin="maintain",
                    )
                    result["proposals"].append(p["id"])

    sync_registry(caps)

    # 4) insights + digest
    _write_insights(stats)
    result["insights_updated"] = True
    digest = _write_digest(stats, caps)
    result["digest_written"] = digest
    result["disabled_sources"] = disabled
    return result


def _write_insights(stats: dict) -> None:
    movers = sources_learning.movers(stats, limit=10)
    pend = proposals.pending()
    fb = feedback.list_feedback(limit=10)
    lines = [
        "# Insights — what the learning loop currently believes",
        f"_updated {util.utcnow_iso()}_",
        "",
        "## Source landscape",
        "",
        "| Source | Attempts | Yield rate | Verified | Failed | Domains |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for m in movers:
        lines.append(f"| {m['source']} | {m['attempts']} | {m['yield_rate']} | {m['verified']} | {m['failed']} | {m['domains']} |")
    if not movers:
        lines.append("| _(no data yet)_ | | | | | |")
    disabled = stats.get("disabled_sources") or []
    if disabled:
        lines += ["", f"**Disabled sources:** {', '.join(disabled)}"]
    lines += ["", "## Pending proposals", ""]
    if pend:
        for p in pend:
            lines.append(f"- `{p['id']}` [{p['class']}] {p['title']} (since {p['at'][:10]})")
    else:
        lines.append("_(none — the loop is idle)_")
    lines += ["", "## Recent signals", ""]
    for f in fb[-10:]:
        lines.append(f"- {f['at'][:10]} · {f['type']} · {f['label']}")
    if not fb:
        lines.append("_(no feedback recorded yet)_")
    util.atomic_write_text(paths.runtime_learning_dir() / "insights.md", "\n".join(lines) + "\n")


def _write_digest(stats: dict, caps: list[dict]) -> str:
    from jinja2 import Environment, FileSystemLoader

    month = util.today_iso()[:7]
    env = Environment(loader=FileSystemLoader(str(paths.REPO_ROOT / "templates")), autoescape=False)
    tpl = env.get_template("digest.md.j2")

    movers = sources_learning.movers(stats, limit=8)
    pend = proposals.pending()
    applied = [p for p in proposals.load_all() if p["status"] == "applied"][-5:]
    regressed = [p for p in proposals.load_all() if p["status"] == "regressed"]
    promoted = [c["id"] for c in caps if c.get("status") == "active"]
    candidates = [c["id"] for c in caps if c.get("status") == "candidate"]

    # metric trends from run retrospectives (if the vault is reachable)
    current, previous = _collect_metrics()

    prefs_answers = []
    prefs = util.read_json(paths.runtime_learning_dir() / "preferences.json", {})
    for a in prefs.get("answers", [])[-5:]:
        prefs_answers.append(f"{a['id']}: chose {a.get('choice', a.get('status'))} — {a.get('context', '')}")

    alerts = []
    for name in ("citation_precision", "gate_pass_rate"):
        if previous.get(name) not in (None, 0) and current.get(name) is not None:
            if current[name] < previous[name]:
                alerts.append(f"{name} declining: {previous[name]} → {current[name]} (two-month rule check pending)")

    report = tpl.render(
        month=month,
        generated_at=util.utcnow_iso(),
        headline=_headline(current, previous, len(pend)),
        metrics=[
            {"name": k, "current": current.get(k, "—"), "previous": previous.get(k, "—"),
             "direction": _direction(current.get(k), previous.get(k))}
            for k in ("citation_precision", "gate_pass_rate", "runs", "contradictions_found")
        ],
        alerts=alerts,
        sources=[
            {"name": m["source"], "domain": m["domains"], "delta": "—",
             "yield": m["yield_rate"], "verified": m["verified"]}
            for m in movers
        ],
        capabilities={"promoted": promoted[-5:], "candidates": candidates, "retired": []},
        proposals={"pending": pend, "applied": applied, "regressed": regressed},
        preferences=prefs_answers,
        next_intent=("keep exploration ≥15%; review pending proposals before next maintenance"
                     if pend else "no action needed — the loop is idle"),
    )
    out = paths.runtime_learning_dir() / f"digest-{month}.md"
    util.atomic_write_text(out, report)
    return str(out)


def _collect_metrics() -> tuple[dict, dict]:
    """Aggregate the two latest months of run retrospectives from the vault."""
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    root = paths.vault_dir() / "projects"
    if root.exists():
        for retro in sorted(root.glob("*/retrospective.json")):
            r = util.read_json(retro, {})
            if r.get("at"):
                buckets[r["at"][:7]].append(r)
    months = sorted(buckets.keys())
    def agg(rows: list[dict]) -> dict:
        if not rows:
            return {}
        prec = [r["metrics"].get("citation_precision") for r in rows if r.get("metrics")]
        prec = [p for p in prec if p is not None]
        gates = [r["metrics"] for r in rows if r.get("metrics")]
        attempts = sum(g.get("gate_attempts", 0) for g in gates) or 1
        passed = sum(g.get("gates_passed_first_attempt", 0) for g in gates)
        return {
            "runs": len(rows),
            "citation_precision": round(sum(prec) / len(prec), 2) if prec else None,
            "gate_pass_rate": round(passed / attempts, 2),
            "contradictions_found": sum(g.get("contradictions_found", 0) for g in gates),
        }
    cur = agg(buckets[months[-1]]) if months else {}
    prev = agg(buckets[months[-2]]) if len(months) > 1 else {}
    return cur, prev


def _direction(cur, prev) -> str:
    if cur is None or prev in (None, "—", 0):
        return "—"
    if cur > prev:
        return "▲"
    if cur < prev:
        return "▼"
    return "="


def _headline(cur: dict, prev: dict, pending: int) -> str:
    if not cur:
        return "First month of data — the baseline is being established."
    bits = [f"{cur.get('runs', 0)} runs aggregated"]
    if cur.get("citation_precision") is not None:
        bits.append(f"citation precision {cur['citation_precision']}")
    if pending:
        bits.append(f"{pending} proposal(s) awaiting your review")
    return "; ".join(bits) + "."
