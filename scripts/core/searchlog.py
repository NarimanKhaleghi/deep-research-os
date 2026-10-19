"""Search log — an append-only journal of every search executed for a project.

This is what makes a review reproducible: query strings, engines, dates and
hit counts are recorded as they happen (connector searches automatically,
manual searches via ``searchlog add``). The report's screening / PRISMA block
is computed from this log plus the source screening statuses — never invented.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402

FILE = "searches.jsonl"


def log_path(project: Path) -> Path:
    return Path(project) / FILE


def load(project: Path) -> list[dict]:
    rows = []
    path = log_path(project)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def append(project: Path, rec: dict) -> dict:
    rows = load(project)
    ids = [r.get("id", "") for r in rows]
    rec = dict(rec)
    rec.setdefault("id", util.next_id("SCH", ids))
    rec.setdefault("at", util.utcnow_iso())
    with open(log_path(project), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def summarize(project: Path) -> dict:
    """Aggregate the log for the report: engines, queries, counts."""
    rows = load(project)
    engines: dict[str, dict] = {}
    for r in rows:
        eng = r.get("engine") or "unknown"
        e = engines.setdefault(eng, {"queries": 0, "hits": 0, "kept": 0})
        e["queries"] += 1
        e["hits"] += int(r.get("hits") or 0)
        e["kept"] += int(r.get("kept") or 0)
    return {
        "entries": len(rows),
        "engines": [{"engine": k, **v} for k, v in sorted(engines.items())],
        "queries": [{"id": r.get("id"), "query": r.get("query"), "engine": r.get("engine"),
                     "angle": r.get("angle"), "hits": r.get("hits"), "kept": r.get("kept"),
                     "at": r.get("at"), "manual": bool(r.get("manual"))} for r in rows],
        "first_at": rows[0]["at"] if rows else None,
        "last_at": rows[-1]["at"] if rows else None,
    }
