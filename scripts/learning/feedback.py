"""Feedback journaling — every learning signal lands here (append-only)."""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import paths, util  # noqa: E402

VALID_TYPES = {"explicit", "implicit", "adjudication", "preference", "source_outcome", "run_outcome"}


def _path():
    return paths.runtime_learning_dir() / "feedback.jsonl"


def journal(
    type_: str,
    label: str,
    *,
    project: str | None = None,
    detail: str | None = None,
    weight: float = 1.0,
    source_id: str | None = None,
    capability_id: str | None = None,
) -> dict:
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid feedback type '{type_}'")
    rows = util.read_jsonl(_path())
    rec = {
        "id": util.next_id("FB", [r.get("id", "") for r in rows]),
        "at": util.utcnow_iso(),
        "project": project,
        "type": type_,
        "label": util.truncate(label.strip(), 140),
        "detail": util.truncate(detail, 400) if detail else None,
        "weight": weight,
        "source_id": source_id,
        "capability_id": capability_id,
        "scrubbed": True,
    }
    util.append_jsonl(_path(), rec)
    return rec


def list_feedback(project: str | None = None, limit: int = 50) -> list[dict]:
    rows = util.read_jsonl(_path())
    if project:
        rows = [r for r in rows if r.get("project") == project]
    return rows[-limit:]


def count_for_project(project: str) -> int:
    return sum(1 for r in util.read_jsonl(_path()) if r.get("project") == project)
