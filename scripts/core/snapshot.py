"""Snapshots — source permanence with SHA-256, link-rot insurance.

Every source gets a local snapshot file; claims survive page edits and deletions.
Optional Wayback lookup adds an external archive pointer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import http, util  # noqa: E402

WAYBACK_API = "https://archive.org/wayback/available"


def snapshot_text(project: Path, sid: str, text: str, kind: str) -> dict:
    """Write the snapshot file and return the snapshot descriptor."""
    suffix = {"text": ".txt", "html": ".html", "metadata": ".meta.json"}[kind]
    path = Path(project) / "sources" / f"{sid}{suffix}"
    util.atomic_write_text(path, text)
    return {
        "path": str(Path("sources") / f"{sid}{suffix}"),
        "sha256": util.sha256_text(text),
        "bytes": len(text.encode("utf-8")),
        "kind": kind,
        "archived_url": None,
    }


def wayback_lookup(url: str) -> str | None:
    """Nearest Wayback snapshot URL, or None (network-optional)."""
    try:
        payload = http.get_json(WAYBACK_API, params={"url": url}, timeout=8.0, retries=0)
    except Exception:
        return None
    snap = (payload.get("archived_snapshots") or {}).get("closest") or {}
    return snap.get("url") if snap.get("available") else None


def verify_snapshot(project: Path, source: dict) -> bool:
    """Re-hash the snapshot file; True when it matches the recorded hash."""
    snap = source.get("snapshot") or {}
    rel, want = snap.get("path"), snap.get("sha256")
    if not rel or not want:
        return False
    path = Path(project) / rel
    if not path.exists():
        return False
    return util.sha256_file(path) == want


def read_snapshot(project: Path, source: dict) -> str:
    snap = source.get("snapshot") or {}
    rel = snap.get("path")
    if not rel:
        return ""
    return util.load_text(Path(project) / rel)
