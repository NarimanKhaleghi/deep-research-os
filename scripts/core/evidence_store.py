"""The Evidence Ledger — append-only JSONL journals, one project per run.

Layout (per project):
  sources/SRC-####.json    one file per source (metadata + snapshot + scores)
  evidence.jsonl           verbatim quotes
  claims.jsonl             claim lifecycle
  contradictions.jsonl     conflicts + adjudications
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402


class Ledger:
    def __init__(self, project: Path):
        self.project = Path(project)
        self.sources_dir = self.project / "sources"
        self.evidence_path = self.project / "evidence.jsonl"
        self.claims_path = self.project / "claims.jsonl"
        self.contradictions_path = self.project / "contradictions.jsonl"

    # ------------------------------------------------------------- sources

    def sources(self) -> list[dict]:
        out = []
        if self.sources_dir.exists():
            for f in sorted(self.sources_dir.glob("SRC-*.json")):
                rec = util.read_json(f, None)
                if rec:
                    out.append(rec)
        return out

    def source(self, sid: str) -> dict | None:
        return util.read_json(self.sources_dir / f"{sid}.json", None)

    def add_source(self, rec: dict) -> dict:
        existing = [s["id"] for s in self.sources()]
        rec = dict(rec)
        rec.setdefault("id", util.next_id("SRC", existing))
        rec.setdefault("accessed_at", util.utcnow_iso())
        util.write_json(self.sources_dir / f"{rec['id']}.json", rec)
        return rec

    def update_source(self, sid: str, **fields) -> dict:
        rec = self.source(sid)
        if rec is None:
            raise KeyError(f"source {sid} not found")
        rec.update(fields)
        util.write_json(self.sources_dir / f"{sid}.json", rec)
        return rec

    # ------------------------------------------------------------ evidence

    def evidence(self) -> list[dict]:
        return util.read_jsonl(self.evidence_path)

    def evidence_for(self, sid: str) -> list[dict]:
        return [e for e in self.evidence() if e["source_id"] == sid]

    def add_evidence(self, rec: dict) -> dict:
        rec = dict(rec)
        if not rec.get("id"):
            rec["id"] = util.next_id("EV", [e.get("id", "") for e in self.evidence()])
        rec.setdefault("added_at", util.utcnow_iso())
        util.append_jsonl(self.evidence_path, rec)
        return rec

    # -------------------------------------------------------------- claims

    def claims(self) -> list[dict]:
        return util.read_jsonl(self.claims_path)

    def claim(self, cid: str) -> dict | None:
        for c in self.claims():
            if c["id"] == cid:
                return c
        return None

    def add_claim(self, rec: dict) -> dict:
        rec = dict(rec)
        if not rec.get("id"):
            rec["id"] = util.next_id("CL", [c.get("id", "") for c in self.claims()])
        now = util.utcnow_iso()
        rec.setdefault("created_at", now)
        rec.setdefault("status", "unverified")
        rec.setdefault("status_reason", "")
        rec["updated_at"] = now
        util.append_jsonl(self.claims_path, rec)
        return rec

    def update_claim(self, cid: str, **fields) -> dict:
        rows = self.claims()
        out = None
        for r in rows:
            if r["id"] == cid:
                r.update(fields)
                r["updated_at"] = util.utcnow_iso()
                out = r
        if out is None:
            raise KeyError(f"claim {cid} not found")
        util.write_jsonl(self.claims_path, rows)
        return out

    # ------------------------------------------------------ contradictions

    def contradictions(self) -> list[dict]:
        return util.read_jsonl(self.contradictions_path)

    def contradiction(self, cxid: str) -> dict | None:
        for c in self.contradictions():
            if c["id"] == cxid:
                return c
        return None

    def add_contradiction(self, rec: dict) -> dict:
        rec = dict(rec)
        if not rec.get("id"):
            rec["id"] = util.next_id("CX", [c.get("id", "") for c in self.contradictions()])
        rec.setdefault("created_at", util.utcnow_iso())
        rec.setdefault("status", "open")
        util.append_jsonl(self.contradictions_path, rec)
        return rec

    def update_contradiction(self, cxid: str, **fields) -> dict:
        rows = self.contradictions()
        out = None
        for r in rows:
            if r["id"] == cxid:
                r.update(fields)
                out = r
        if out is None:
            raise KeyError(f"contradiction {cxid} not found")
        util.write_jsonl(self.contradictions_path, rows)
        return out

    # ------------------------------------------------------------ helpers

    def counts(self) -> dict:
        return {
            "sources": len(self.sources()),
            "evidence": len(self.evidence()),
            "claims": len(self.claims()),
            "contradictions": len(self.contradictions()),
        }

    def evidence_sources_for_claim(self, claim: dict) -> list[dict]:
        ids = set(claim.get("evidence_ids") or [])
        src_ids = {e["source_id"] for e in self.evidence() if e["id"] in ids}
        return [s for s in self.sources() if s["id"] in src_ids]

    def origin_keys_for_claim(self, claim: dict) -> list[str]:
        keys = {s.get("origin_key") or util.domain_of(s.get("url", ""))
                for s in self.evidence_sources_for_claim(claim)}
        return sorted(k for k in keys if k)
