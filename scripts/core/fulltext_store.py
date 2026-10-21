"""Durable full-text storage and verification.

Artifacts live next to source JSON records:

    sources/SRC-0001.pdf      original bytes (immutable; replaced files archived)
    sources/SRC-0001.txt      extracted plain text (the snapshot)
    sources/archive/…         superseded originals

The trust chain is original SHA-256 -> extracted text SHA-256 -> snapshot.sha256.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import fulltext, snapshot  # noqa: E402
from lib import util  # noqa: E402

_EXT = {"pdf": ".pdf", "jats": ".xml", "html": ".html", "text": ".txt"}
_REL = Path("sources")


def artifact_relpath(sid: str, fmt: str) -> Path:
    return _REL / f"{sid}{_EXT.get(fmt, '.bin')}"


def text_relpath(sid: str) -> Path:
    return _REL / f"{sid}.txt"


def _archive(project: Path, path: Path) -> Path | None:
    if not path.exists():
        return None
    digest = util.sha256_file(path)
    dest = Path(project) / "sources" / "archive" / f"{path.stem}-{digest[:8]}{path.suffix}"
    util.ensure_dir(dest.parent)
    if dest.exists():
        path.unlink()
    else:
        path.replace(dest)
    return dest


def store_artifact(
    project: Path,
    ledger,
    source: dict,
    data: bytes,
    artifact: dict,
    origin: dict,
    *,
    status: str = "verified",
    version: str = "unknown",
    license_: str | None = None,
    validation: dict | None = None,
    exception: dict | None = None,
) -> dict:
    """Persist original bytes + extracted text and update the source record."""
    project = Path(project)
    sid = source["id"]
    rel = artifact_relpath(sid, artifact.get("format") or "unknown")
    abs_path = project / rel
    sha = hashlib.sha256(data).hexdigest()
    if abs_path.exists():
        if util.sha256_file(abs_path) != sha:
            _archive(project, abs_path)
    util.atomic_write_bytes(abs_path, data)

    text = artifact.get("text") or ""
    text_rel = text_relpath(sid)
    util.atomic_write_text(project / text_rel, text)
    text_sha = util.sha256_text(text)
    snap = {
        "path": str(text_rel), "sha256": text_sha,
        "bytes": len(text.encode("utf-8")), "kind": "fulltext",
        "archived_url": None,
    }
    desc = fulltext.fulltext_descriptor(
        artifact, status=status, path=str(rel), sha256=sha,
        text_path=str(text_rel), text_sha256=text_sha,
        text_chars=len(text), origin=origin, validation=validation,
        version=version, license_=license_, exception=exception,
    )
    rec = ledger.update_source(
        sid, fulltext=desc, snapshot=snap,
        read_depth="full-text" if status == "verified" else "partial",
    )
    return rec


def store_abstract(
    project: Path,
    ledger,
    source: dict,
    abstract: str,
    origin: dict | None = None,
    *,
    quality: dict | None = None,
    exception: dict | None = None,
) -> dict:
    """Store an abstract-only snapshot and mark the source as abstract-only."""
    project = Path(project)
    sid = source["id"]
    text = (abstract or "").strip()
    snap = snapshot.snapshot_text(project, sid, text, "text")
    text_sha = snap["sha256"]
    desc = {
        "status": "abstract-only", "format": "text", "path": None,
        "sha256": None, "bytes": 0, "pages": 0,
        "text_path": snap["path"], "text_sha256": text_sha,
        "text_chars": len(text), "version": "unknown",
        "host": (origin or {}).get("host") or "",
        "license": (origin or {}).get("license"),
        "landing_url": (origin or {}).get("landing_url"),
        "retrieved_from": (origin or {}).get("final_url") or (origin or {}).get("url"),
        "retrieved_at": util.utcnow_iso(), "extractor": "metadata",
        "validation": {"abstract_quality": quality or {}},
        "exception": exception,
    }
    return ledger.update_source(sid, fulltext=desc, snapshot=snap, read_depth="abstract")




def store_metadata(
    project: Path,
    ledger,
    source: dict,
    abstract: str = "",
    origin: dict | None = None,
    *,
    reason: str = "metadata-only read",
) -> dict:
    """Store a metadata/abstract snapshot without claiming full-text coverage."""
    project = Path(project)
    sid = source["id"]
    text = (abstract or "").strip()
    if not text:
        text = "\n".join(x for x in [
            source.get("title") or "",
            source.get("url") or "",
            f"DOI: {source['doi']}" if source.get("doi") else "",
            f"Publisher: {source['publisher']}" if source.get("publisher") else "",
        ] if x)
    snap = snapshot.snapshot_text(project, sid, text, "metadata")
    desc = {
        "status": "partial", "format": "metadata", "path": None,
        "sha256": None, "bytes": 0, "pages": 0,
        "text_path": snap["path"], "text_sha256": snap["sha256"],
        "text_chars": len(text), "version": "unknown",
        "host": (origin or {}).get("host") or "",
        "license": (origin or {}).get("license"),
        "landing_url": (origin or {}).get("landing_url") or source.get("url"),
        "retrieved_from": (origin or {}).get("url") or source.get("url"),
        "retrieved_at": util.utcnow_iso(), "extractor": "metadata",
        "validation": {},
        "exception": {"reason": reason, "approved_at": util.utcnow_iso()},
    }
    return ledger.update_source(sid, fulltext=desc, snapshot=snap, read_depth="abstract")


def verify(project: Path, source: dict) -> dict:
    """Verify artifact, text and snapshot hashes for one source."""
    ft = source.get("fulltext") or {}
    snap = source.get("snapshot") or {}
    problems: list[str] = []
    if ft.get("status") != "verified":
        problems.append(f"status={ft.get('status') or 'missing'}")
    rel = ft.get("path")
    if rel:
        path = Path(project) / rel
        if not path.exists():
            problems.append("artifact missing")
        elif ft.get("sha256") and util.sha256_file(path) != ft["sha256"]:
            problems.append("artifact hash mismatch")
    else:
        problems.append("artifact path missing")
    trel = ft.get("text_path") or snap.get("path")
    if trel:
        tpath = Path(project) / trel
        if not tpath.exists():
            problems.append("text missing")
        else:
            tsha = util.sha256_file(tpath)
            if ft.get("text_sha256") and tsha != ft["text_sha256"]:
                problems.append("text hash mismatch")
            if snap.get("sha256") and tsha != snap["sha256"]:
                problems.append("snapshot hash mismatch")
            if ft.get("text_sha256") and snap.get("sha256") and ft["text_sha256"] != snap["sha256"]:
                problems.append("fulltext/snapshot hash disagree")
    else:
        problems.append("text path missing")
    return {"ok": not problems, "problems": problems}


def read_text(project: Path, source: dict) -> str:
    ft = source.get("fulltext") or {}
    rel = ft.get("text_path") or (source.get("snapshot") or {}).get("path")
    if not rel:
        return ""
    return util.load_text(Path(project) / rel)


def text_for_evidence(project: Path, source: dict) -> str:
    """Best available text: verified full text, else snapshot."""
    text = read_text(project, source)
    if text:
        return text
    return snapshot.read_snapshot(project, source)


def coverage(sources: list[dict], *, key_ids: set[str] | None = None) -> dict:
    """Full-text coverage metrics used by gates and reports."""
    key_ids = key_ids or set()
    counts = {"verified": 0, "abstract-only": 0, "partial": 0,
              "needs_ocr": 0, "failed": 0, "missing": 0}
    key_gaps: list[str] = []
    for src in sources:
        status = (src.get("fulltext") or {}).get("status") or "missing"
        counts[status if status in counts else "failed"] += 1
        if src.get("id") in key_ids and status != "verified":
            key_gaps.append(src["id"])
    total = len(sources)
    verified_ratio = counts["verified"] / total if total else 0.0
    abstract_ratio = counts["abstract-only"] / total if total else 0.0
    return {"counts": counts, "total": total,
            "verified_ratio": round(verified_ratio, 4),
            "abstract_ratio": round(abstract_ratio, 4),
            "key_gaps": key_gaps}
