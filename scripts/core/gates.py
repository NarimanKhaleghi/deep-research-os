"""Phase gates 0–9 — implements references/quality/quality-gates.md exactly.

Each check returns a stable ``name`` (used by ``state.gate_waivers[]``).
Waivers silence a specific named check for this project, with the reason
surfaced in report Limitations.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import budget as budget_mod  # noqa: E402
from core import report_builder  # noqa: E402
from core import requirements as requirements_mod  # noqa: E402
from core import searchlog  # noqa: E402
from core import snapshot as snapshot_mod  # noqa: E402
from core.evidence_store import Ledger  # noqa: E402
from lib import paths, util  # noqa: E402

PROFILES = ("quick", "standard", "deep", "max")
RELEVANCE = {"supports", "refutes", "contextual", "methodological"}
STRENGTHS = {"established", "supported", "tentative"}
CONFIDENCES = {"high", "medium", "low"}
CLAIM_STATUSES = {"supported", "weakly_supported", "contradicted",
                  "unverifiable", "resolved", "outweighed"}


def _strict(state: dict) -> bool:
    """Academic deliverables follow PRISMA-style reproducibility hard gates."""
    return (state.get("deliverable_type") == "academic-paper"
            or state.get("review_protocol") in ("prisma", "systematic-review"))


def run(project: Path, phase: int, waivers: list[dict] | None = None, persist: bool = True) -> dict:
    project = Path(project)
    state = paths.load_state(project)
    ledger = Ledger(project)

    checks: list[dict] = []
    add = _adder(checks)
    brief_meta, _ = util.parse_front_matter(util.load_text(project / "brief.md"))
    angles = [str(a) for a in (brief_meta.get("angles") or [])]

    if phase == 0:
        _phase0(project, state, brief_meta, angles, add)
    elif phase == 1:
        _phase1(project, angles, add)
    elif phase == 2:
        _phase2(project, angles, add)
    elif phase == 3:
        _phase3(project, state, ledger, angles, add)
    elif phase == 4:
        _phase4(project, ledger, angles, add)
    elif phase == 5:
        _phase5(project, state, ledger, add)
    elif phase == 6:
        _phase6(project, state, ledger, add)
    elif phase == 7:
        _phase7(project, state, ledger, add)
    elif phase == 8:
        _phase8(project, state, add)
    elif phase == 9:
        _phase9(project, state, ledger, add)
    else:
        raise ValueError(f"unknown phase {phase}")

    waivers = waivers or (state.get("gate_waivers") or [])
    waived = {w.get("check") for w in waivers if int(w.get("phase", -1)) == phase}
    for c in checks:
        if not c["ok"] and c["name"] in waived:
            c["ok"] = True
            c["waived"] = True
        else:
            c["waived"] = False

    failures = [c for c in checks if not c["ok"]]
    result = {
        "phase": phase,
        "pass": not failures,
        "checks": checks,
        "waived": sorted(c["name"] for c in checks if c["waived"]),
        "failures": [{"check": c["name"], "detail": c["detail"]} for c in failures],
    }
    if persist:
        state.setdefault("phases", {}).setdefault(str(phase), {})
        if result["pass"]:
            state["phases"][str(phase)]["completed_at"] = state["phases"][str(phase)].get("completed_at") or util.utcnow_iso()
            state["phase_current"] = max(state.get("phase_current", 0), phase)
        state["updated_at"] = util.utcnow_iso()
        paths.save_state(project, state)
    return result


def _adder(checks: list) -> object:
    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return add


# --------------------------------------------------------------- phase 0

def _phase0(project, state, brief_meta, angles, add) -> None:
    missing = []
    for field in ("question", "title", "profile", "cutoff", "deliverable", "angles"):
        if not brief_meta.get(field):
            missing.append(field)
    if brief_meta.get("profile") not in PROFILES and brief_meta.get("profile"):
        missing.append("profile(valid)")
    sc = brief_meta.get("success_criteria")
    if not sc:
        missing.append("success_criteria")
    if len(angles) < 2:
        missing.append("angles(≥2)")
    maint = brief_meta.get("maintenance")
    if maint and maint not in ("ok", "due"):
        missing.append("maintenance")
    add("brief_front_matter", not missing, detail="missing/invalid: " + ", ".join(missing) if missing else "ok")

    ceilings = (state.get("budget") or {}).get("ceilings") or {}
    need = {"searches", "sources_read", "evidence", "claims", "verify_passes"}
    ok = need <= set(ceilings)
    add("budget_ceilings", ok, detail="ok" if ok else f"missing: {sorted(need - set(ceilings))}")

    if _strict(state):
        n = len(requirements_mod.load(project))
        add("requirements_recorded", n >= 1,
            detail=f"{n} requirement(s)" if n
            else "no requirements recorded — capture each explicit prompt constraint "
                 "with `requirements add --text ...`")


# --------------------------------------------------------------- phase 1

def _phase1(project, angles, add) -> None:
    plan = util.load_text(project / "plan.md")
    sections = util.md_sections(plan)
    minima = {"terminology": 5, "actors": 3, "source map": 2, "initial queries": 2}
    bad = []
    for name, minimum in minima.items():
        body = sections.get(name, "")
        n = util.count_bullets(body) or (len(re.findall(r"\|\s*\S", body)) - 1 if "|" in body else 0)
        if n < minimum:
            bad.append(f"{name}:{n}/{minimum}")
    add("plan_minimums", not bad, detail=", ".join(bad) or "ok")

    norm_plan = util.normalize_text(plan)
    absent = [a for a in angles if util.normalize_text(a) not in norm_plan]
    add("angles_in_plan", not absent, detail=", ".join(absent) or "ok")


# --------------------------------------------------------------- phase 2

def _phase2(project, angles, add) -> None:
    plan = util.load_text(project / "plan.md")
    sections = util.md_sections(plan)
    matrix = sections.get("collection matrix", "")
    need_lines = 2 * max(1, len(angles))
    lines = util.count_bullets(matrix) or sum(1 for ln in matrix.splitlines() if "|" in ln and "---" not in ln)
    add("matrix_volume", lines >= need_lines, detail=f"{lines}/{need_lines}")

    n_target = util.count_bullets(sections.get("target sources", ""))
    add("target_sources", n_target >= 1, detail=f"{n_target} bullet(s)")
    n_stop = util.count_bullets(sections.get("stop rules", ""))
    add("stop_rules", n_stop >= 1, detail=f"{n_stop} bullet(s)")

    norm_matrix = util.normalize_text(matrix)
    absent = [a for a in angles if util.normalize_text(a) not in norm_matrix]
    add("angles_in_matrix", not absent, detail=", ".join(absent) or "ok")


# --------------------------------------------------------------- phase 3

def _phase3(project, state, ledger, angles, add) -> None:
    sources = ledger.sources()
    bad = []
    for s in sources:
        problems = []
        if not s.get("title"):
            problems.append("title")
        if not (s.get("url") or s.get("doi")):
            problems.append("url|doi")
        if not s.get("accessed_at"):
            problems.append("accessed_at")
        if not s.get("tier"):
            problems.append("tier")
        if not (s.get("angles_covered") or []):
            problems.append("angles_covered")
        snap = s.get("snapshot") or {}
        if not snap.get("path"):
            problems.append("snapshot.path")
        if not snap.get("sha256"):
            problems.append("snapshot.sha256")
        if problems:
            bad.append(f"{s['id']}({','.join(problems)})")
    add("sources_well_formed", len(sources) >= 2 and not bad,
        detail=", ".join(bad) or f"{len(sources)} source(s)")

    covered = set()
    for s in sources:
        covered.update(s.get("angles_covered") or [])
    missing_angles = [a for a in angles if a not in covered]
    add("angle_coverage", not missing_angles, detail=", ".join(missing_angles) or "ok")

    b = budget_mod.check(state)
    over = [u for u in b["exceeded"] if u == "sources_read"]
    add("sources_budget", not over,
        detail="exceeded sources_read" if over else f"{b['usage'].get('sources_read', {}).get('used', 0)} used")

    # reproducibility gates (academic / PRISMA deliverables)
    if _strict(state):
        slog = searchlog.summarize(project)
        add("search_logged", slog["entries"] >= 1,
            detail=f"{slog['entries']} logged search(es)" if slog["entries"]
            else "no searches logged — connector searches log automatically; "
                 "record manual ones with `searchlog add`")
        no_status = [s["id"] for s in sources if not s.get("status")]
        no_reason = [s["id"] for s in sources
                     if s.get("status") == "excluded" and not s.get("exclusion_reason")]
        add("screening_reasons", not no_status and not no_reason,
            detail=", ".join([f"{i}(no status)" for i in no_status]
                             + [f"{i}(excluded, no reason)" for i in no_reason]) or "ok")


# --------------------------------------------------------------- phase 4

def _phase4(project, ledger, angles, add) -> None:
    evidence = ledger.evidence()
    sources = {s["id"]: s for s in ledger.sources()}
    bad = []
    for e in evidence:
        problems = []
        if e.get("source_id") not in sources:
            problems.append("source_id")
        if len((e.get("quote") or "").strip()) < 8:
            problems.append("quote")
        if not e.get("locator"):
            problems.append("locator")
        if e.get("relevance") not in RELEVANCE:
            problems.append("relevance")
        if angles and e.get("angle") not in angles:
            problems.append("angle∉brief")
        src = sources.get(e.get("source_id"))
        if src is not None:
            snap_text = snapshot_mod.read_snapshot(project, src)
            if not snap_text:
                problems.append("snapshot-missing")
            else:
                ok, _, _ = util.quote_in_text(e.get("quote", ""), snap_text, threshold=0.95)
                if not ok:
                    problems.append("quote∉snapshot")
        if problems:
            bad.append(f"{e['id']}({','.join(problems)})")
    add("evidence_valid", len(evidence) >= 1 and not bad,
        detail=", ".join(bad[:5]) or f"{len(evidence)} evidence record(s)")


# --------------------------------------------------------------- phase 5

def _phase5(project, state, ledger, add) -> None:
    sources = ledger.sources()
    unscored = [s["id"] for s in sources if not (s.get("credibility") or {}).get("score")]
    add("all_scored", not unscored, detail=", ".join(unscored) or "ok")
    bands = {(s.get("credibility") or {}).get("band") for s in sources}
    add("has_strong_source", bool(bands & {"A", "B"}),
        detail=f"bands: {sorted(b for b in bands if b)}")

    no_retraction = [s["id"] for s in sources
                     if s.get("doi") and not (s.get("retraction") or {}).get("checked_at")]
    add("retraction_checked", not no_retraction, detail=", ".join(no_retraction) or "ok")

    last = (state.get("ran") or {}).get("last_credibility_at") or ""
    newest = max((s.get("accessed_at") or "" for s in sources), default="")
    add("credibility_fresh", bool(last) and last >= newest,
        detail=f"scoring at {last or 'never'} vs newest source {newest or 'n/a'}")


# --------------------------------------------------------------- phase 6

def _phase6(project, state, ledger, add) -> None:
    vr = util.read_json(project / "verify_report.json", {}) or {}
    claims = ledger.claims()
    sources = {s["id"]: s for s in ledger.sources()}
    evidence_ids = {e["id"] for e in ledger.evidence()}

    newest_claim = max((c.get("updated_at") or "" for c in claims), default="")
    fresh = bool(vr) and (vr.get("generated_at") or "") >= newest_claim
    add("verify_report_fresh", fresh,
        detail=f"report {vr.get('generated_at', 'missing')} vs claims {newest_claim or 'n/a'}")
    add("verify_report_complete",
        vr.get("citation_precision") is not None and "fabrication_suspected" in vr
        and "corroboration_gaps" in vr,
        detail="ok" if vr else "missing verify_report.json")

    bad_status, bad_ids = [], []
    for c in claims:
        if c.get("status") == "unverified":
            bad_status.append(c["id"])
        for eid in c.get("evidence_ids") or []:
            if eid not in evidence_ids:
                bad_ids.append(f"{c['id']}→{eid}")
    add("claims_verified", not bad_status and not bad_ids and bool(claims),
        detail=("unverified: " + ", ".join(bad_status) if bad_status
                else ("bad evidence refs: " + ", ".join(bad_ids) if bad_ids else "ok")))

    single = [c["id"] for c in claims
              if c.get("critical") and c.get("status") == "supported"
              and len(ledger.origin_keys_for_claim(c)) < 2]
    add("critical_corroborated", not single,
        detail=", ".join(single) or "ok")

    scan_at = (state.get("ran") or {}).get("last_contradictions_scan_at") or ""
    add("contradictions_scanned", bool(scan_at) and scan_at >= newest_claim,
        detail=f"scan at {scan_at or 'never'} vs claims {newest_claim or 'n/a'}")

    cxs = ledger.contradictions()
    open_no_reason = [c["id"] for c in cxs if c["status"] == "open" and not c.get("detail")]
    contradicted_no_cx = [c["id"] for c in claims
                          if c.get("status") == "contradicted"
                          and not (c.get("contradiction_ids") or [])
                          and "retracted" not in (c.get("status_reason") or "")
                          and "verification" not in (c.get("status_reason") or "")]
    add("contradictions_linked", not open_no_reason and not contradicted_no_cx,
        detail=("open w/o reason: " + ", ".join(open_no_reason) if open_no_reason
                else ("contradicted w/o CX: " + ", ".join(contradicted_no_cx) if contradicted_no_cx else "ok")))

    unack = []
    for m in vr.get("number_mismatches") or []:
        c = ledger.claim(m.get("claim_id")) or {}
        if c.get("status") not in ("weakly_supported", "outweighed"):
            unack.append(f"{m.get('claim_id')}:{m.get('number')}")
    add("numbers_acknowledged", not unack, detail=", ".join(unack) or "ok")


# --------------------------------------------------------------- phase 7

def _phase7(project, state, ledger, add) -> None:
    fdir = project / "findings"
    files = sorted(fdir.glob("FN-*.md")) if fdir.exists() else []
    add("findings_exist", len(files) >= 1, detail=f"{len(files)} file(s)")
    if not files:
        add("findings_well_formed", False, detail="no findings")
        add("findings_supported", False, detail="no findings")
        return

    claim_ids = {c["id"] for c in ledger.claims()}
    bad = []
    for f in files:
        meta, _ = util.parse_front_matter(util.load_text(f))
        problems = []
        if not re.match(r"^FN-\d{2}$", str(meta.get("id") or "")):
            problems.append("id")
        if len(str(meta.get("title") or "")) < 6:
            problems.append("title")
        if meta.get("strength") not in STRENGTHS:
            problems.append("strength")
        if meta.get("confidence") not in CONFIDENCES:
            problems.append("confidence")
        cl = meta.get("claims") or []
        if not cl:
            problems.append("claims")
        for cid in cl:
            if cid not in claim_ids:
                problems.append(f"unknown:{cid}")
        if "counterpoints" not in meta:
            problems.append("counterpoints[]")
        if "gaps" not in meta:
            problems.append("gaps[]")
        if problems:
            bad.append(f"{f.stem}({','.join(problems)})")
    add("findings_well_formed", not bad, detail=", ".join(bad) or "ok")

    # no finding may lean on a contradicted-unresolved claim as support
    offenders = []
    for f in files:
        meta, _ = util.parse_front_matter(util.load_text(f))
        for cid in meta.get("claims") or []:
            c = ledger.claim(cid) or {}
            if c.get("status") == "contradicted" and meta.get("strength") == "established":
                offenders.append(f"{meta.get('id')}→{cid}")
    add("findings_supported", not offenders, detail=", ".join(offenders) or "ok")

    # academic deliverables: the model / scenarios / sensitivity findings must exist
    if _strict(state):
        kinds = []
        for f in files:
            meta, _ = util.parse_front_matter(util.load_text(f))
            kinds.append(str(meta.get("kind") or "analysis"))
        missing_kinds = [k for k in ("model", "scenarios", "sensitivity") if k not in kinds]
        add("findings_kinds", not missing_kinds,
            detail=("missing finding kinds: " + ", ".join(missing_kinds)
                    + " (`findings new --kind ...`)") if missing_kinds
            else f"kinds: {', '.join(sorted(set(kinds)))}")

        target = int(state.get("key_studies_target") or 8)
        fields = ("problem", "framework", "method", "context", "findings",
                  "limitations", "relevance")
        keys = [s for s in ledger.sources() if s.get("key_study")]
        incomplete = [s["id"] for s in keys
                      if not all((s.get("review") or {}).get(k) for k in fields)]
        detail = ""
        if len(keys) < target:
            detail = f"{len(keys)}/{target} key studies marked (`sources review --key`)"
        elif incomplete:
            detail = "incomplete review fields: " + ", ".join(incomplete)
        add("key_studies_reviewed", len(keys) >= target and not incomplete,
            detail=detail or f"{len(keys)} key studies reviewed")


# --------------------------------------------------------------- phase 8

def _phase8(project, state, add) -> None:
    if not (project / "report.md").exists():
        add("report_exists", False, detail="report.md missing — run `report build`")
        return
    add("report_exists", True, detail="ok")
    result = report_builder.check(project)
    for c in result["checks"]:
        add(c["name"], c["ok"], detail=c["detail"])


# --------------------------------------------------------------- phase 9

def _phase9(project, state, ledger, add) -> None:
    retro = util.read_json(project / "retrospective.json", {}) or {}
    required = ("worked", "failed", "budget_used", "metrics", "suggestions", "capability_candidate")
    missing = [k for k in required if k not in retro]
    add("retrospective_complete", not missing, detail=", ".join(missing) or "ok")

    feedback = util.read_jsonl(paths.runtime_learning_dir() / "feedback.jsonl")
    fb = [f for f in feedback if f.get("project") == state.get("slug")]
    skipped = bool(retro.get("feedback_skipped")) and bool(retro.get("feedback_skipped_reason"))
    add("feedback_recorded", bool(fb) or skipped, detail=f"{len(fb)} entrie(s)" if fb else "none")

    stats_doc = util.read_json(paths.runtime_learning_dir() / "source_stats.json", {}) or {}
    stats = stats_doc.get("stats") or {}
    evidence_sources = {e["source_id"] for e in ledger.evidence()}
    services = set()
    for s in ledger.sources():
        if s["id"] in evidence_sources:
            services.add(s.get("service") or "web")
    missing_stats = sorted(svc for svc in services if svc not in stats)
    add("source_stats_updated", not missing_stats, detail=", ".join(missing_stats) or "ok")

    from core import budget as _b

    ceilings = _b.ceilings_for(state.get("profile", "standard"))
    asked = state.get("preferences_asked", 0)
    add("preference_budget", asked <= ceilings.get("preferences", 99),
        detail=f"{asked}/{ceilings.get('preferences')}")
