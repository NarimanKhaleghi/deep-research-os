"""Proposal lifecycle — the governed-change machinery.

proposed → validated → approved | rejected → regression-tested → applied | regressed
→ (manual) reverted. See references/learning-protocol.md §7.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import paths, util  # noqa: E402

CLASSES = {"promote", "retire", "merge", "adopt_source", "adopt_method",
           "adopt_tool", "template", "weight", "rubric"}
EXPIRY_DAYS = 30


def _path() -> Path:
    return paths.runtime_learning_dir() / "proposals.jsonl"


def load_all() -> list[dict]:
    return util.read_jsonl(_path())


def save_all(rows: list[dict]) -> None:
    util.write_jsonl(_path(), rows)


def _update(pid: str, **fields) -> dict:
    rows = load_all()
    for r in rows:
        if r["id"] == pid:
            r.update(fields)
            save_all(rows)
            return r
    raise KeyError(f"proposal {pid} not found")


def validate(p: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if p.get("class") not in CLASSES:
        errors.append(f"invalid class: {p.get('class')}")
    if len(p.get("title", "")) < 6:
        errors.append("title too short")
    if len(p.get("summary", "")) < 20:
        errors.append("summary too short")
    ev = p.get("evidence") or {}
    has_evidence = any(
        [
            ev.get("stats"),
            ev.get("eval_delta") is not None,
            (ev.get("preferences") or 0) > 0,
            (ev.get("adjudications") or 0) > 0,
            ev.get("notes"),
        ]
    )
    if not has_evidence:
        errors.append("no numeric/text evidence attached")
    if not p.get("changes"):
        errors.append("no changes described")
    if not p.get("rollback"):
        errors.append("no rollback plan")
    return (not errors), errors


def create(
    class_: str,
    title: str,
    summary: str,
    *,
    evidence: Optional[dict] = None,
    changes: Optional[list] = None,
    rollback: str = "learn revert <id> restores pre-change files",
    origin: Optional[str] = None,
) -> dict:
    rows = load_all()
    rec = {
        "id": util.next_id("PRO", [r.get("id", "") for r in rows]),
        "at": util.utcnow_iso(),
        "class": class_,
        "title": title,
        "summary": summary,
        "evidence": evidence or {},
        "changes": changes or [],
        "rollback": rollback,
        "origin": origin,
        "status": "proposed",
        "validation": {},
    }
    ok, errors = validate(rec)
    rec["validation"] = {"ok": ok, "errors": errors}
    if not ok:
        rec["status"] = "invalid"
    util.append_jsonl(_path(), rec)
    return rec


def pending() -> list[dict]:
    return [p for p in load_all() if p["status"] in ("proposed", "approved")]


def decide(pid: str, action: str, by: str = "human", note: str = "") -> dict:
    if action not in ("approve", "reject"):
        raise ValueError("action must be approve|reject")
    p = get(pid)
    if p["status"] not in ("proposed",):
        raise ValueError(f"cannot {action} proposal in status '{p['status']}'")
    status = "approved" if action == "approve" else "rejected"
    return _update(pid, status=status, decision={"by": by, "at": util.utcnow_iso(), "note": note})


def get(pid: str) -> dict:
    for r in load_all():
        if r["id"] == pid:
            return r
    raise KeyError(f"proposal {pid} not found")


# ------------------------------------------------------------------ apply

def apply(pid: str, regression: Optional[Callable[[], tuple[bool, list[str]]]] = None) -> dict:
    """Run regression (if given), then apply changes. Regression failure → regressed."""
    p = get(pid)
    if p["status"] != "approved":
        raise ValueError(f"proposal {pid} is '{p['status']}', not 'approved'")

    checks: list[str] = []
    if regression is not None:
        passed, checks = regression()
        if not passed:
            return _update(pid, status="regressed",
                           regression={"ran": True, "pass": False, "checks": checks})

    base = paths.runtime_learning_dir()
    backup_dir = paths.archive_dir() / "backups" / pid
    affected = _affected_paths(p, base)
    for rel in affected:
        src = base / rel
        if src.exists():
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for ch in p["changes"]:
        _apply_change(ch, base)

    return _update(pid, status="applied", applied_at=util.utcnow_iso(),
                   backup_dir=str(backup_dir),
                   regression={"ran": regression is not None, "pass": True, "checks": checks})


def _affected_paths(p: dict, base: Path) -> set[str]:
    out: set[str] = set()
    for ch in p["changes"]:
        for key in ("file", "to"):
            v = ch.get(key)
            if v:
                out.add(v)
    return out


def _apply_change(ch: dict, base: Path) -> None:
    action = ch["action"]
    file = base / ch["file"]
    if action == "create":
        file.parent.mkdir(parents=True, exist_ok=True)
        util.atomic_write_text(file, ch.get("content", ""))
    elif action == "move":
        dest = base / ch["to"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file), str(dest))
    elif action == "delete":
        if file.exists():
            file.unlink()
    elif action == "modify":
        if "content" in ch:
            util.atomic_write_text(file, ch["content"])
        if "front_matter_set" in ch:
            _set_front_matter(file, ch["front_matter_set"])
        if "json_set" in ch:
            data = util.read_json(file, {})
            for pointer, value in ch["json_set"].items():
                _json_pointer_set(data, pointer, value)
            util.write_json(file, data)
    else:
        raise ValueError(f"unknown change action '{action}'")


def _set_front_matter(path: Path, updates: dict) -> None:
    text = util.load_text(path)
    meta, body = util.parse_front_matter(text)
    meta.update(updates)
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f'  - "{item}"')
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    util.atomic_write_text(path, "\n".join(lines) + "\n\n" + body)


def _json_pointer_set(data: dict, pointer: str, value) -> None:
    parts = pointer.split(".")
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


# ----------------------------------------------------------------- revert

def revert(pid: str, purge: bool = False) -> dict:
    p = get(pid)
    if p["status"] not in ("applied",):
        raise ValueError(f"cannot revert proposal in status '{p['status']}'")
    base = paths.runtime_learning_dir()
    backup_dir = Path(p.get("backup_dir") or (paths.archive_dir() / "backups" / pid))
    affected = _affected_paths(p, base)
    for rel in affected:
        backup = backup_dir / rel
        target = base / rel
        if backup.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        elif target.exists():
            target.unlink()  # was created by the proposal
    if purge and backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
    return _update(pid, status="reverted", reverted_at=util.utcnow_iso())


def expire(max_age_days: int = EXPIRY_DAYS) -> int:
    rows = load_all()
    now = util.utcnow_iso()
    n = 0
    for r in rows:
        if r["status"] == "proposed" and _older_than(r["at"], max_age_days):
            r["status"] = "expired"
            r["expired_at"] = now
            n += 1
    if n:
        save_all(rows)
    return n


def _older_than(iso: str, days: int) -> bool:
    from datetime import datetime, timezone

    try:
        t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - t).days > days


def explain(item: str) -> dict:
    """Why is this item like this? Walk stats, feedback and proposals."""
    k = util.normalize_text(item)
    out = {"item": item, "evidence": []}
    stats = util.read_json(paths.runtime_learning_dir() / "source_stats.json", {})
    for source, buckets in (stats.get("stats") or {}).items():
        if k in util.normalize_text(source):
            out["evidence"].append({"kind": "source_stats", "source": source, "buckets": buckets})
    for r in load_all():
        if k in util.normalize_text(r.get("title", "")) or k in util.normalize_text(r.get("summary", "")):
            out["evidence"].append({"kind": "proposal", "id": r["id"], "status": r["status"],
                                    "note": (r.get("decision") or {}).get("note", "")})
    for f in util.read_jsonl(paths.runtime_learning_dir() / "feedback.jsonl"):
        if k in util.normalize_text(f.get("label", "")):
            out["evidence"].append({"kind": "feedback", "id": f["id"], "label": f["label"], "at": f["at"]})
    out["conclusion"] = ("no direct evidence found — the item may be at defaults"
                         if not out["evidence"] else "explained by the entries above")
    return out
