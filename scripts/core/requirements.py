"""Requirements ledger — every explicit user requirement, tracked to the report.

The intake step extracts each explicit requirement from the user's prompt into
``requirements.json``. ``report build`` then refuses to pass until every
requirement is either **mapped** to an anchor that actually appears in the
report, or **waived** with a reason (waivers surface in Limitations). This is
what keeps a long, multi-constraint prompt from silently losing requirements.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import report_i18n  # noqa: E402
from lib import util  # noqa: E402

FILE = "requirements.json"
STATUSES = ("mapped", "waived", "unmet")


def req_path(project: Path) -> Path:
    return Path(project) / FILE


def load(project: Path) -> list[dict]:
    data = util.read_json(req_path(project), None)
    if data is None:
        return []
    if isinstance(data, dict):  # tolerate {"requirements": [...]}
        data = data.get("requirements") or []
    return list(data)


def save(project: Path, items: list[dict]) -> None:
    util.write_json(req_path(project), {"schema": 1, "requirements": items})


def add(project: Path, text: str, origin: str = "user prompt", rid: str | None = None) -> dict:
    items = load(project)
    if not rid:
        used = {i.get("id", "") for i in items}
        n = 1
        while f"RQ-{n:02d}" in used:
            n += 1
        rid = f"RQ-{n:02d}"
    if any(i.get("id") == rid for i in items):
        raise ValueError(f"requirement {rid} already exists")
    rec = {"id": rid, "text": text.strip(), "origin": origin,
           "mappings": [], "waiver": None, "created_at": util.utcnow_iso()}
    items.append(rec)
    save(project, items)
    return rec


def map_target(project: Path, rid: str, target: str) -> dict:
    items = load(project)
    for rec in items:
        if rec.get("id") == rid:
            target = target.strip()
            if target and target not in rec.setdefault("mappings", []):
                rec["mappings"].append(target)
            rec["waiver"] = None
            save(project, items)
            return rec
    raise KeyError(f"requirement {rid} not found")


def waive(project: Path, rid: str, reason: str) -> dict:
    items = load(project)
    for rec in items:
        if rec.get("id") == rid:
            rec["waiver"] = {"reason": reason.strip(), "at": util.utcnow_iso()}
            save(project, items)
            return rec
    raise KeyError(f"requirement {rid} not found")


def status_of(rec: dict) -> str:
    if rec.get("waiver"):
        return "waived"
    if rec.get("mappings"):
        return "mapped"
    return "unmet"


def coverage(project: Path, report_text: str | None = None) -> dict:
    """Coverage table; when ``report_text`` is given, anchors are verified to
    actually appear in the report (a mapping to a missing anchor counts unmet).
    """
    items = load(project)
    rows, unmet = [], []
    for rec in items:
        status = status_of(rec)
        present = []
        if status == "mapped" and report_text is not None:
            for m in rec["mappings"]:
                if _anchor_present(m, report_text):
                    present.append(m)
            if not present:
                status = "unmet"
        if status == "unmet":
            unmet.append(rec["id"])
        rows.append({
            "id": rec["id"], "text": rec["text"], "status": status,
            "mapped_to": "; ".join(present or rec.get("mappings") or []),
            "waiver_reason": (rec.get("waiver") or {}).get("reason", ""),
        })
    return {"total": len(items), "mapped": sum(1 for r in rows if r["status"] == "mapped"),
            "waived": sum(1 for r in rows if r["status"] == "waived"),
            "unmet": unmet, "rows": rows}


def _anchor_present(anchor: str, report_text: str) -> bool:
    """An anchor matches if its substantive tokens appear in the report.

    Anchors are human labels like ``Report §11 Sensitivity analysis`` — we strip
    section markers and quoting, normalize, and require every token of length
    >= 4 to be present (case-insensitive, Persian-aware via normalize_text).
    Anchors written in one language also resolve against the other language's
    template vocabulary (see ``report_i18n.anchor_aliases``), so a legacy
    English mapping stays valid in a Persian report and vice versa.
    """
    candidates = [anchor]
    alias = report_i18n.anchor_aliases(anchor)
    if alias and alias != anchor:
        candidates.append(alias)
    return any(_tokens_present(c, report_text) for c in candidates)


def _tokens_present(anchor: str, report_text: str) -> bool:
    norm_report = util.normalize_text(report_text)
    cleaned = anchor.replace("§", " ").replace("#", " ").replace("«", " ").replace("»", " ")
    tokens = [t for t in util.normalize_text(cleaned).split() if len(t) >= 4]
    if not tokens:
        return util.normalize_text(anchor) in norm_report
    return all(t in norm_report for t in tokens)
