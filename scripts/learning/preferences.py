"""Preference elicitation — asking the human A/B questions, respectfully.

Rules (see references/learning-protocol.md §6): only real captured A/B pairs,
never mid-task, profile caps, 3 consecutive unanswered asks → trigger disables.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import paths, util  # noqa: E402

CAPS = {"quick": 0, "standard": 1, "deep": 2, "max": 3}
UNANSWERED_LIMIT = 3


def _state_path() -> Path:
    return paths.runtime_learning_dir() / "preferences.json"


def load() -> dict:
    return util.read_json(_state_path(), {
        "schema": 1, "answers": [], "pending": [],
        "unanswered_streak": 0, "disabled": False, "asked_total": 0,
    })


def save(state: dict) -> None:
    util.write_json(_state_path(), state)
    _write_md(state)


def can_ask(profile: str, asked_in_run: int) -> tuple[bool, str]:
    st = load()
    if st.get("disabled"):
        return False, "trigger disabled after 3 unanswered asks (re-arm: learn pref enable)"
    cap = CAPS.get(profile, 0)
    if cap == 0:
        return False, "quick profile never asks"
    if asked_in_run >= cap:
        return False, f"profile cap reached ({asked_in_run}/{cap})"
    return True, "ok"


def create_question(ctx: dict) -> dict:
    """Register a pending question; returns the record (render card via templates)."""
    st = load()
    pref_id = util.next_id("PREF", [q.get("id", "") for q in st["pending"]])
    rec = {
        "id": pref_id,
        "at": util.utcnow_iso(),
        "project": ctx.get("project"),
        "context": util.truncate(ctx.get("context", ""), 200),
        "option_a": ctx.get("a", {}),
        "option_b": ctx.get("b", {}),
        "status": "pending",
    }
    st["pending"].append(rec)
    st["asked_total"] = st.get("asked_total", 0) + 1
    save(st)
    return rec


def answer(pref_id: str, choice: str, note: str | None = None) -> dict:
    st = load()
    for q in st["pending"]:
        if q["id"] == pref_id:
            q["status"] = "answered"
            q["choice"] = choice
            q["note"] = note
            q["answered_at"] = util.utcnow_iso()
            st["answers"].append(q)
            st["pending"].remove(q)
            st["unanswered_streak"] = 0
            save(st)
            return q
    raise KeyError(f"pending question {pref_id} not found")


def mark_unanswered(pref_id: str) -> dict:
    """Expire a pending question as ignored; disables trigger at the limit."""
    st = load()
    for q in st["pending"]:
        if q["id"] == pref_id:
            q["status"] = "ignored"
            q["ignored_at"] = util.utcnow_iso()
            st["answers"].append(q)
            st["pending"].remove(q)
            st["unanswered_streak"] = st.get("unanswered_streak", 0) + 1
            if st["unanswered_streak"] >= UNANSWERED_LIMIT:
                st["disabled"] = True
            save(st)
            return q
    raise KeyError(f"pending question {pref_id} not found")


def enable() -> None:
    st = load()
    st["disabled"] = False
    st["unanswered_streak"] = 0
    save(st)


def _write_md(st: dict) -> None:
    lines = ["# Preferences — learned through A/B questions", ""]
    if st.get("disabled"):
        lines += ["> Trigger DISABLED after 3 unanswered asks. Re-arm: `learn pref enable`", ""]
    if not st.get("answers"):
        lines.append("_(no answers recorded yet)_")
    for a in st.get("answers", []):
        lines += [
            f"## {a['id']} — {a.get('choice', a.get('status'))}",
            f"- context: {a.get('context', '')}",
            f"- A: {(a.get('option_a') or {}).get('label', '')} — B: {(a.get('option_b') or {}).get('label', '')}",
            f"- answered: {a.get('answered_at', a.get('ignored_at', ''))}",
            "",
        ]
    util.atomic_write_text(paths.runtime_learning_dir() / "preferences.md", "\n".join(lines))
