"""Citation & claim verification (phase 6).

Online: DOI resolution + title fuzzy-match, URL liveness, retraction flags.
Offline: snapshot integrity (SHA-256) only.
Produces ``verify_report.json`` with citation precision — the FACT-style metric.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import claims as claims_mod  # noqa: E402
from core import credibility, snapshot  # noqa: E402
from core.evidence_store import Ledger  # noqa: E402
from lib import http, paths, util  # noqa: E402

TITLE_VERIFIED = 0.90
TITLE_REVIEW = 0.75


def run(project: Path, online: bool = False) -> dict:
    project = Path(project)
    ledger = Ledger(project)
    state = paths.load_state(project)

    per_source: dict[str, dict] = {}
    for s in ledger.sources():
        verif, retr = _verify_source(project, s, online)
        ledger.update_source(s["id"], verification=verif, retraction=retr)
        per_source[s["id"]] = {"verification": verif, "retraction": retr}

    # propagate retraction into credibility caps
    for s in ledger.sources():
        if (s.get("retraction") or {}).get("status") == "retracted":
            extra = dict(s.get("extra") or {})
            if not extra.get("is_retracted"):
                extra["is_retracted"] = True
                s = ledger.update_source(s["id"], extra=extra)
            ledger.update_source(s["id"], credibility=credibility.score_source(s))

    sources = {s["id"]: s for s in ledger.sources()}
    checked = [v["verification"] for v in per_source.values()
               if v["verification"]["status"] in ("verified", "review", "mismatch")]
    verified_n = sum(1 for v in checked if v["status"] == "verified")
    citation_precision = round(verified_n / len(checked), 3) if checked else None
    fabrication_suspected = [sid for sid, v in per_source.items()
                             if v["verification"]["status"] == "mismatch"]

    # ---------------------------------------------------------- claims
    evidence_by_id = {e["id"]: e for e in ledger.evidence()}
    cx_by_claim: dict[str, list[dict]] = {}
    for cx in ledger.contradictions():
        for cid in cx["claim_ids"]:
            cx_by_claim.setdefault(cid, []).append(cx)

    number_mismatches, corroboration_gaps, summary_counts = [], [], {}
    modality_mismatches, primary_source_gaps, staleness_warnings = [], [], []
    now = util.utcnow_iso()

    for c in ledger.claims():
        evs = [evidence_by_id[eid] for eid in c.get("evidence_ids", []) if eid in evidence_by_id]
        num_problems = claims_mod.number_conflicts(c, evs)
        srcs = ledger.evidence_sources_for_claim(c)
        origins = ledger.origin_keys_for_claim(c)
        cxs = cx_by_claim.get(c["id"], [])

        modality_bad = claims_mod.modality_mismatch(c, evs)
        needs_official = c.get("kind") == "normative" or claims_mod.has_modality(c.get("text", ""))
        official = claims_mod.official_sources(srcs)
        primary_gap = needs_official and not official
        if modality_bad:
            modality_mismatches.append({
                "claim_id": c["id"],
                "num_evidence": len(evs),
                "reason": "normative claim phrased as prohibition/obligation, "
                          "but no supporting quote contains normative language",
            })
        if primary_gap:
            primary_source_gaps.append({
                "claim_id": c["id"],
                "reason": "normative/regulatory claim has no official/primary source "
                          f"(have: {sorted({(s.get('type') or '?') for s in srcs}) or 'none'})",
            })
        stale = [s for s in (official or srcs)
                 if (claims_mod.staleness_months(s) or 0) > 18]
        if needs_official and stale:
            staleness_warnings.append({
                "claim_id": c["id"],
                "sources": [s["id"] for s in stale],
                "reason": "normative claim relies on a document older than 18 months — "
                          "re-check for updates before treating it as current",
            })

        status, reason = _classify(c, srcs, origins, num_problems, cxs,
                                   modality_bad=modality_bad, primary_gap=primary_gap)
        ledger.update_claim(c["id"], status=status, status_reason=reason,
                            origin_keys=origins, verified_at=now)
        summary_counts[status] = summary_counts.get(status, 0) + 1

        for n in num_problems:
            number_mismatches.append({"claim_id": c["id"], "number": n.get("raw"),
                                      "claim_status": status})
        if c.get("critical") and len(origins) < 2 \
                and status in ("supported", "weakly_supported"):
            corroboration_gaps.append({"claim_id": c["id"],
                                       "reason": "critical claim with a single origin",
                                       "origins": origins})

    report = {
        "generated_at": now,
        "mode": "online" if online else "offline",
        "per_source": per_source,
        "citation_precision": citation_precision,
        "checked_citations": len(checked),
        "fabrication_suspected": fabrication_suspected,
        "number_mismatches": number_mismatches,
        "corroboration_gaps": corroboration_gaps,
        "modality_mismatches": modality_mismatches,
        "primary_source_gaps": primary_source_gaps,
        "staleness_warnings": staleness_warnings,
        "claims_summary": summary_counts,
        "open_contradictions": [cx["id"] for cx in ledger.contradictions() if cx["status"] == "open"],
    }
    util.write_json(project / "verify_report.json", report)

    state.setdefault("counters", {})
    state["counters"]["verify_passes"] = state["counters"].get("verify_passes", 0) + 1
    state.setdefault("ran", {}).setdefault("steps", [])
    if "verify" not in state["ran"]["steps"]:
        state["ran"]["steps"].append("verify")
    state["ran"]["last_verify_at"] = now
    paths.save_state(project, state)
    return report


def _verify_source(project: Path, s: dict, online: bool) -> tuple[dict, dict]:
    now = util.utcnow_iso()
    doi = (s.get("doi") or "").strip().lower()

    if not online:
        ok = snapshot.verify_snapshot(project, s)
        verif = {"status": "verified" if ok else "unreachable",
                 "title_match": None, "method": "snapshot-hash",
                 "detail": "offline mode: snapshot integrity only", "at": now}
        retr = {"status": "unknown", "source_flag": None, "checked_at": now}
        return verif, retr

    verif = {"status": "unknown", "title_match": None, "method": "none", "detail": "", "at": now}
    retr = {"status": "unknown", "source_flag": None, "checked_at": now}

    if doi:
        from connectors import crossref, openalex

        cr = crossref.get_work(doi)
        oa = openalex.get_work(doi)
        meta = cr or oa
        if meta is None:
            verif.update(status="unreachable", method="crossref+openalex",
                         detail="DOI did not resolve via Crossref or OpenAlex")
        else:
            score = util.fuzzy(util.normalize_text(s.get("title", "")),
                               util.normalize_text(meta.get("title", "")))
            if score >= TITLE_VERIFIED:
                st = "verified"
            elif score >= TITLE_REVIEW:
                st = "review"
            else:
                st = "mismatch"
            verif.update(status=st, title_match=round(score, 3),
                         method="doi-resolve+title-match",
                         detail=f"resolved via {'Crossref' if cr else 'OpenAlex'}")
        oa_flag = bool((oa or {}).get("extra", {}).get("is_retracted"))
        cr_flag = bool((cr or {}).get("extra", {}).get("is_retraction_relation"))
        if oa_flag or cr_flag:
            retr = {"status": "retracted",
                    "source_flag": "openalex:is_retracted" if oa_flag else "crossref:update-to",
                    "checked_at": now}
        elif meta is not None:
            retr = {"status": "clean", "source_flag": None, "checked_at": now}
    else:
        alive, code = http.url_alive(s.get("url", ""))
        verif.update(status="verified" if alive else "unreachable",
                     method="url-liveness",
                     detail=f"HTTP {code}")
        retr = {"status": "unknown", "source_flag": None, "checked_at": now}

    if verif["status"] == "unknown":
        verif["status"] = "unreachable"
    return verif, retr


def _classify(claim: dict, srcs: list[dict], origins: list[str],
              num_problems: list[dict], cxs: list[dict],
              modality_bad: bool = False, primary_gap: bool = False) -> tuple[str, str]:
    if claim.get("status") == "outweighed":
        return "outweighed", claim.get("status_reason") or "adjudicated as outweighed"

    mismatch = [s for s in srcs if (s.get("verification") or {}).get("status") == "mismatch"]
    if mismatch:
        return "contradicted", f"citation failed verification for {mismatch[0]['id']}"

    retracted = [s for s in srcs if (s.get("retraction") or {}).get("status") == "retracted"]
    if retracted:
        return "contradicted", f"supporting source {retracted[0]['id']} is retracted"

    open_cx = [cx for cx in cxs if cx.get("status") == "open"]
    if open_cx:
        return "contradicted", f"open contradiction {open_cx[0]['id']}"

    if modality_bad:
        return "weakly_supported", ("normative phrasing (prohibition/obligation) not present "
                                    "in any supporting quote — wording is stronger than the evidence")

    if primary_gap:
        return "weakly_supported", ("normative/regulatory claim without an official or primary "
                                    "source — add the regulation/statistics document itself")

    if num_problems:
        raw = ", ".join(n.get("raw", "?") for n in num_problems[:3])
        return "weakly_supported", f"number(s) not found in quotes at matching precision: {raw}"

    if not srcs:
        return "unverifiable", "no supporting sources recorded"

    bands = {(s.get("credibility") or {}).get("band") for s in srcs}
    strong = [s for s in srcs
              if (s.get("credibility") or {}).get("band") in ("A", "B")
              and (s.get("verification") or {}).get("status") in ("verified", "review")]
    if strong:
        if claim.get("critical") and len(origins) < 2:
            return "weakly_supported", "critical claim with a single origin"
        return "supported", f"{len(strong)} verified A/B source(s)"

    reachable = [s for s in srcs if (s.get("verification") or {}).get("status") in ("verified", "review")]
    if bands & {"A", "B"} and not reachable:
        return "weakly_supported", "strong-band sources could not be verified in this mode"
    if bands & {"A", "B"}:
        return "weakly_supported", "A/B sources present but none passed verification"
    return "weakly_supported", "only C/D-band sources support this claim"
