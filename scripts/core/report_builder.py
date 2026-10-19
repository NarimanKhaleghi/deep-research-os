"""Report builder — renders report.md/report.html from the ledger, then runs
the hard report gates from references/quality/quality-gates.md.
"""

from __future__ import annotations

import html as _html
import os
import re
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import bibmeta, requirements as requirements_mod, searchlog  # noqa: E402
from core.evidence_store import Ledger  # noqa: E402
from lib import paths, util  # noqa: E402

STRENGTH_RANK = {"established": 0, "supported": 1, "tentative": 2}
CONF_RANK = {"high": 0, "medium": 1, "low": 2}
WEAK_CLAIM_STATUSES = {"weakly_supported", "contradicted", "unverifiable"}

PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX|lorem ipsum|\[insert|placeholder)\b", re.I)
ID_RE = re.compile(r"\b(FN-\d{2}|CL-\d{4}|CX-\d{4}|SRC-\d{4}|EV-\d{4})\b")
REQUIRED_SECTIONS = ["Executive Summary", "Findings", "Methodology", "Limitations", "Bibliography"]


def _pkg_version() -> str:
    """Read the package version from pyproject.toml (fallback constant)."""
    try:
        import tomllib

        with open(paths.repo_root() / "pyproject.toml", "rb") as fh:
            return str(tomllib.load(fh)["project"]["version"])
    except Exception:  # noqa: BLE001
        return "1.1.0"


# ------------------------------------------------------------------ build

def build(project: Path, allow_flagged: bool = False) -> dict:
    project = Path(project)
    ledger = Ledger(project)
    state = paths.load_state(project)
    ctx = _context(project, ledger, state)

    from jinja2 import Environment, FileSystemLoader

    loader = FileSystemLoader(str(paths.repo_root() / "templates"))
    md_env = Environment(loader=loader, autoescape=False, trim_blocks=True, lstrip_blocks=True)
    html_env = Environment(loader=loader, autoescape=True, trim_blocks=True, lstrip_blocks=True)

    ctx["gates_summary"] = "pending — see `report check`"
    util.atomic_write_text(project / "report.md", md_env.get_template("report.md.j2").render(**ctx))
    util.atomic_write_text(project / "report.html", html_env.get_template("report.html.j2").render(**ctx))

    check_result = _run_check(project, ledger, state, ctx=ctx, allow_flagged=allow_flagged)
    downgraded = [c for c in check_result["checks"] if c.get("downgraded")]
    if downgraded:
        ctx["limitations"].append(
            "Gate downgrades via --allow-flagged: " + ", ".join(c["name"] for c in downgraded))
    ctx["gates_summary"] = _summary(check_result)
    ctx["requirements"] = requirements_mod.coverage(
        project, report_text=_strip_requirements_section(util.load_text(project / "report.md")))
    ctx["strict"] = _strict_mode(state)
    util.atomic_write_text(project / "report.md", md_env.get_template("report.md.j2").render(**ctx))
    util.atomic_write_text(project / "report.html", html_env.get_template("report.html.j2").render(**ctx))

    state.setdefault("ran", {})["last_report_check_at"] = util.utcnow_iso()
    steps = state["ran"].setdefault("steps", [])
    if "report" not in steps:
        steps.append("report")
    paths.save_state(project, state)

    return {"report_md": str(project / "report.md"), "report_html": str(project / "report.html"),
            "check": check_result, "metrics": check_result["metrics"]}


def _context(project: Path, ledger: Ledger, state: dict) -> dict:
    brief_meta, _ = util.parse_front_matter(util.load_text(project / "brief.md"))
    sources = ledger.sources()
    evidence = ledger.evidence()
    claims = ledger.claims()
    cxs = ledger.contradictions()
    claim_by_id = {c["id"]: c for c in claims}
    ev_by_id = {e["id"]: e for e in evidence}
    vr = util.read_json(project / "verify_report.json", {}) or {}
    budget = state.get("budget") or {}
    counters = state.get("counters") or {}

    # -------- findings
    findings = []
    fdir = project / "findings"
    if fdir.exists():
        for f in sorted(fdir.glob("FN-*.md")):
            meta, body = util.parse_front_matter(util.load_text(f))
            claim_ids = [c for c in (meta.get("claims") or []) if isinstance(c, str)]
            src_ids = sorted({
                ev_by_id[eid]["source_id"]
                for cid in claim_ids
                for eid in (claim_by_id.get(cid) or {}).get("evidence_ids", [])
                if eid in ev_by_id
            })
            body = body.strip()
            findings.append({
                "id": meta.get("id") or f.stem,
                "title": str(meta.get("title") or f.stem),
                "strength": str(meta.get("strength") or "tentative"),
                "confidence": str(meta.get("confidence") or "low"),
                "kind": str(meta.get("kind") or "analysis"),
                "claims": claim_ids,
                "sources": src_ids,
                "counterpoints": [str(x) for x in (meta.get("counterpoints") or [])],
                "gaps": [str(x) for x in (meta.get("gaps") or [])],
                "section": str(meta.get("section") or "main"),
                "body": body,
                "body_html": md_to_html(body),
            })

    summary_findings = [f for f in findings if f["section"] == "summary"]
    if not summary_findings:
        ranked = sorted(findings, key=lambda f: (STRENGTH_RANK.get(f["strength"], 3),
                                                 CONF_RANK.get(f["confidence"], 3)))
        summary_findings = ranked[: min(3, len(ranked))]
    executive_summary = [{
        "title": f["title"],
        "text": _first_sentence(f["body"]),
        "confidence": f["confidence"],
        "claims": f["claims"],
    } for f in summary_findings]

    # -------- contradictions
    contras = [{
        "id": c["id"], "kind": c["kind"], "severity": c["severity"],
        "detail": c.get("detail", ""), "status": c["status"],
        "resolution": c.get("resolution"), "rationale": c.get("rationale"),
    } for c in cxs]

    # -------- coverage
    angles = brief_meta.get("angles") or []
    if isinstance(angles, str):
        angles = [angles]
    coverage = []
    for angle in angles:
        a = str(angle)
        cov_srcs = [s for s in sources if a in (s.get("angles_covered") or [])]
        cov_ev = [e for e in evidence if e.get("angle") == a]
        cov_claims = [c for c in claims if a in (c.get("angles") or [])]
        bands = sorted({(s.get("credibility") or {}).get("band") for s in cov_srcs
                        if (s.get("credibility") or {}).get("band")})
        coverage.append({"angle": a, "sources": len(cov_srcs), "evidence": len(cov_ev),
                         "claims": len(cov_claims), "bands": ", ".join(bands) or "—"})

    # -------- methodology
    tier_counts: dict[str, int] = {}
    for s in sources:
        b = (s.get("credibility") or {}).get("band")
        if b:
            tier_counts[b] = tier_counts.get(b, 0) + 1
    verified_count = sum(1 for v in (vr.get("per_source") or {}).values()
                         if (v.get("verification") or {}).get("status") == "verified")
    methodology = {
        "verified_count": verified_count,
        "tiers": [{"band": b, "count": tier_counts.get(b, 0)} for b in ("A", "B", "C", "D")],
        "corroboration_gaps": vr.get("corroboration_gaps") or [],
    }

    # -------- limitations
    limitations = _limitations(project, state, sources, claims, cxs, vr)

    # -------- budget
    budget_ctx = {
        "searches": counters.get("searches", 0),
        "sources_read": counters.get("sources_read", 0),
        "evidence": counters.get("evidence", 0),
        "claims": counters.get("claims", 0),
        "ceilings": budget.get("ceilings") or {},
        "exceptions": budget.get("exceptions") or [],
    }

    # -------- bibliography (APA 7 pieces + audit trail)
    bibliography = []
    for i, s in enumerate(sorted(sources, key=lambda x: (bibmeta.authors_apa(x).lower(),
                                                         bibmeta.source_year(x))), start=1):
        cred = s.get("credibility") or {}
        snap = s.get("snapshot") or {}
        apa = bibmeta.apa_reference(s)
        bibliography.append({
            "n": i,
            "authors": apa["authors"],
            "year": apa["year"],
            "title": apa["title"],
            "venue_parts": apa["venue_parts"],
            "doi": apa["doi"],
            "version_note": apa["version_note"],
            "flags": apa["flags"],
            "publisher": s.get("publisher") or util.domain_of(s.get("url", "")) or "—",
            "url": s.get("url") or "",
            "band": cred.get("band", "?"),
            "score": cred.get("score", "?"),
            "source_id": s["id"],
            "sha256": snap.get("sha256") or "",
        })

    # -------- search & screening (reproducibility block)
    slog = searchlog.summarize(project)
    status_counts: dict[str, int] = {}
    for s in sources:
        status_counts[s.get("status") or "unscreened"] = \
            status_counts.get(s.get("status") or "unscreened", 0) + 1
    excluded = [{"id": s["id"], "title": s.get("title", ""),
                 "reason": s.get("exclusion_reason") or "—"}
                for s in sources if s.get("status") == "excluded"]
    search_method = {
        "entries": slog["entries"],
        "engines": slog["engines"],
        "queries": slog["queries"],
        "first_at": slog["first_at"],
        "last_at": slog["last_at"],
        "status_counts": status_counts,
        "excluded": excluded,
        "total_sources": len(sources),
    }

    # -------- literature comparison matrix (key studies)
    matrix = []
    for s in sorted(sources, key=lambda x: (not bool(x.get("key_study")),
                                            bibmeta.authors_apa(x).lower())):
        review = s.get("review") or {}
        if not (s.get("key_study") or review):
            continue
        matrix.append({
            "source_id": s["id"],
            "key": bool(s.get("key_study")),
            "citation": f"{bibmeta.authors_apa(s)} ({bibmeta.source_year(s)})",
            "problem": review.get("problem") or "—",
            "framework": review.get("framework") or "—",
            "method": review.get("method") or "—",
            "context": review.get("context") or "—",
            "findings": review.get("findings") or "—",
            "limitations": review.get("limitations") or "—",
            "relevance": review.get("relevance") or "—",
        })

    # -------- requirement coverage (anchors validated against the report text)
    report_path = project / "report.md"
    report_text = util.load_text(report_path) if report_path.exists() else None
    requirements = requirements_mod.coverage(project, report_text=report_text)

    precision = vr.get("citation_precision")
    return {
        "title": brief_meta.get("title") or state.get("title") or "Research Report",
        "question": brief_meta.get("question") or state.get("question") or "",
        "slug": state.get("slug", ""),
        "profile": state.get("profile", "standard"),
        "deliverable_type": state.get("deliverable_type") or "report",
        "review_protocol": state.get("review_protocol") or "",
        "strict": _strict_mode(state),
        "generated_at": util.utcnow_iso(),
        "version": _pkg_version(),
        "citation_precision": f"{precision:.3f}" if isinstance(precision, (int, float)) else "n/a",
        "sources_count": len(sources),
        "evidence_count": len(evidence),
        "verify_mode": vr.get("mode", "not-run"),
        "spent_usd": (budget.get("spent_usd") or 0.0),
        "executive_summary": executive_summary,
        "findings": findings,
        "contradictions": contras,
        "coverage": coverage,
        "methodology": methodology,
        "budget": budget_ctx,
        "limitations": limitations,
        "bibliography": bibliography,
        "search_method": search_method,
        "matrix": matrix,
        "requirements": requirements,
    }


def _strict_mode(state: dict) -> bool:
    """Academic deliverables follow PRISMA-style reproducibility hard gates."""
    return (state.get("deliverable_type") == "academic-paper"
            or state.get("review_protocol") in ("prisma", "systematic-review"))


def _strip_requirements_section(text: str) -> str:
    return re.sub(r"^##\s+Requirement Coverage\s*$.*?(?=^##\s|\Z)", "", text,
                  flags=re.M | re.S)


def _first_sentence(body: str) -> str:
    text = re.sub(r"^#+\s.*$", "", body, flags=re.M).strip()
    text = re.sub(r"[*_`>]", "", text)
    text = util.truncate(text.split(". ")[0].strip(), 240)
    return text or "—"


def _limitations(project: Path, state: dict, sources: list[dict], claims: list[dict],
                 cxs: list[dict], vr: dict) -> list[str]:
    lim: list[str] = []
    for req in requirements_mod.load(project):
        w = req.get("waiver") or {}
        if w.get("reason"):
            lim.append(f"Waived requirement {req['id']} ({util.truncate(req.get('text', ''), 80)}): "
                       f"{w['reason']}")
    for ex in (state.get("budget") or {}).get("exceptions") or []:
        lim.append(f"Budget exception: {ex.get('counter')} reached {ex.get('actual')} "
                   f"(ceiling {ex.get('ceiling')}) — {ex.get('reason')}")
    for w in state.get("gate_waivers") or []:
        lim.append(f"Gate waiver (phase {w.get('phase')} · {w.get('check')}): {w.get('reason')}")
    for key, h in (state.get("source_health") or {}).items():
        if (h.get("failures") or 0) > 0:
            lim.append(f"Source health: {key} failed {h['failures']}×"
                       + (f" (last error: {h.get('last_error')})" if h.get("last_error") else ""))
    retracted = [s["id"] for s in sources if (s.get("retraction") or {}).get("status") == "retracted"]
    if retracted:
        lim.append(f"Retracted sources excluded from load-bearing claims: {', '.join(retracted)}")
    open_cx = [c["id"] for c in cxs if c["status"] == "open"]
    if open_cx:
        lim.append(f"Unresolved contradictions remain visible: {', '.join(open_cx)}")
    gaps = vr.get("corroboration_gaps") or []
    if gaps:
        lim.append(f"Corroboration gaps: {len(gaps)} critical claim(s) rest on a single origin "
                   f"({', '.join(g['claim_id'] for g in gaps[:5])}).")
    weak = [c["id"] for c in claims if c.get("status") in WEAK_CLAIM_STATUSES]
    if weak:
        lim.append(f"Weakly supported / contradicted claims are labeled inline: "
                   f"{len(weak)} claim(s).")
    unreachable = [sid for sid, v in (vr.get("per_source") or {}).items()
                   if (v.get("verification") or {}).get("status") in ("unreachable",)]
    if unreachable:
        lim.append(f"Citations that could not be machine-verified: {', '.join(unreachable)}.")
    if not lim:
        lim.append("No waivers, budget exceptions, or health failures were recorded for this run.")
    return lim


def _summary(res: dict) -> str:
    checks = res["checks"]
    passed = sum(1 for c in checks if c["ok"])
    note = ""
    downgraded = [c for c in checks if c.get("downgraded")]
    if downgraded:
        note = f"; {len(downgraded)} downgraded via --allow-flagged: " + ", ".join(c["name"] for c in downgraded)
    return f"{passed}/{len(checks)} hard checks passed{note}"


# ------------------------------------------------------------------ gates

def _run_check(project: Path, ledger: Ledger, state: dict, ctx: dict,
               allow_flagged: bool) -> dict:
    report_path = project / "report.md"
    report_text = util.load_text(report_path)
    findings_meta = []
    fdir = project / "findings"
    if fdir.exists():
        for f in sorted(fdir.glob("FN-*.md")):
            meta, _ = util.parse_front_matter(util.load_text(f))
            findings_meta.append(meta)

    sources = {s["id"]: s for s in ledger.sources()}
    ev_ids = {e["id"] for e in ledger.evidence()}
    claim_ids = {c["id"] for c in ledger.claims()}
    cx_ids = {c["id"] for c in ledger.contradictions()}
    claim_by_id = {c["id"]: c for c in ledger.claims()}

    checks: list[dict] = []

    def add(name, ok, hard=True, detail=""):
        checks.append({"name": name, "ok": bool(ok), "hard": hard, "detail": detail})

    mr = {"findings": len(findings_meta), "uncited_lines": 0, "unknown_ids": [],
          "broken_refs": 0, "placeholders": 0, "weak_unlabeled": [], "missing_from_bib": []}

    # gate 0: report exists with required sections
    missing_sections = [s for s in REQUIRED_SECTIONS if f"## {s}" not in report_text]
    add("report_structure", bool(report_text) and not missing_sections,
        detail=("missing sections: " + ", ".join(missing_sections)) if missing_sections else "ok")

    # gate 1: all ledger IDs referenced exist
    referenced = set(ID_RE.findall(report_text))
    unknown = sorted(i for i in referenced
                     if (i.startswith("CL-") and i not in claim_ids)
                     or (i.startswith("CX-") and i not in cx_ids)
                     or (i.startswith("EV-") and i not in ev_ids)
                     or (i.startswith("SRC-") and i not in sources)
                     or (i.startswith("FN-") and i not in {m.get("id") for m in findings_meta}))
    mr["unknown_ids"] = unknown
    add("ids_resolve", not unknown, detail=", ".join(unknown) or "ok")

    # gate 2: zero uncited fact-bearing lines in Findings
    find_sec = _section_text(report_text, "Findings")
    uncited = _uncited_lines(find_sec)
    mr["uncited_lines"] = len(uncited)
    add("findings_cited", not uncited and bool(findings_meta),
        detail=(f"{len(uncited)} uncited line(s): " + " | ".join(uncited[:3])) if uncited
        else ("no findings yet" if not findings_meta else "ok"))

    # gate 3: bibliography covers every SRC cited anywhere
    bib_sec = _section_text(report_text, "Bibliography")
    cited_srcs = {i for i in ID_RE.findall(report_text) if i.startswith("SRC-")}
    bib_srcs = set(re.findall(r"\[(SRC-\d{4})\]", bib_sec)) | set(re.findall(r"(SRC-\d{4})", bib_sec))
    missing_bib = sorted(cited_srcs - bib_srcs)
    mr["missing_from_bib"] = missing_bib
    add("bibliography_covers", not missing_bib, detail=", ".join(missing_bib) or "ok")

    # gate 4: numbers consistent (downgradable)
    vr = util.read_json(project / "verify_report.json", {}) or {}
    bad_mismatch = []
    for m in vr.get("number_mismatches") or []:
        cid = m.get("claim_id")
        c = claim_by_id.get(cid) or {}
        if c.get("status") not in ("weakly_supported", "outweighed"):
            bad_mismatch.append(f"{cid}:{m.get('number')}")
    number_ok = not bad_mismatch
    if not number_ok and allow_flagged:
        add("numbers_consistent", True, hard=False,
            detail=f"downgraded (--allow-flagged): {', '.join(bad_mismatch)}")
        checks[-1]["downgraded"] = True
    else:
        add("numbers_consistent", number_ok, detail=", ".join(bad_mismatch) or "ok")

    # gate 5: no placeholders (downgradable)
    ph = PLACEHOLDER_RE.findall(report_text)
    mr["placeholders"] = len(ph)
    if ph and allow_flagged:
        add("no_placeholders", True, hard=False, detail=f"downgraded: {sorted(set(ph))}")
        checks[-1]["downgraded"] = True
    else:
        add("no_placeholders", not ph, detail=f"{len(ph)} placeholder marker(s)")

    # gate 6: open contradictions visible (downgradable)
    open_cx = [cid for cid in cx_ids if (ledger.contradiction(cid) or {}).get("status") == "open"]
    missing_cx = [cid for cid in open_cx if cid not in referenced]
    if missing_cx and allow_flagged:
        add("contradictions_visible", True, hard=False,
            detail=f"downgraded: hidden open CX {missing_cx}")
        checks[-1]["downgraded"] = True
    else:
        add("contradictions_visible", not missing_cx, detail=", ".join(missing_cx) or "ok")

    # gate 7: weak claims labeled inline (downgradable)
    weak_unlabeled = []
    for meta in findings_meta:
        for cid in (meta.get("claims") or []):
            c = claim_by_id.get(cid) or {}
            if c.get("status") in WEAK_CLAIM_STATUSES and meta.get("strength") == "established":
                weak_unlabeled.append(f"{meta.get('id')}→{cid}")
    mr["weak_unlabeled"] = weak_unlabeled
    if weak_unlabeled and allow_flagged:
        add("weak_labeled", True, hard=False,
            detail=f"downgraded: {', '.join(weak_unlabeled)}")
        checks[-1]["downgraded"] = True
    else:
        add("weak_labeled", not weak_unlabeled, detail=", ".join(weak_unlabeled) or "ok")

    # gate 8: limitations mention waivers + health failures
    lim_sec = _section_text(report_text, "Limitations")
    miss_lim = []
    for w in state.get("gate_waivers") or []:
        if str(w.get("check")) not in lim_sec and str(w.get("reason", ""))[:20] not in lim_sec:
            miss_lim.append(f"waiver {w.get('phase')}/{w.get('check')}")
    for key, h in (state.get("source_health") or {}).items():
        if (h.get("failures") or 0) > 0 and key not in lim_sec:
            miss_lim.append(f"health {key}")
    add("limitations_complete", bool(lim_sec.strip()) and not miss_lim,
        detail=", ".join(miss_lim) or ("ok" if lim_sec.strip() else "empty Limitations"))

    # gate: verification freshness
    claims = ledger.claims()
    newest_claim = max((c.get("updated_at") or "" for c in claims), default="")
    vr_time = (vr or {}).get("generated_at") or ""
    fresh = bool(vr) and vr_time >= newest_claim if newest_claim else bool(vr)
    add("verify_fresh", fresh,
        detail=f"verify_report at {vr_time or 'missing'} vs newest claim {newest_claim or 'n/a'}")

    # gate: requirement coverage (every explicit requirement mapped to an anchor
    # that appears in the report, or waived with a reason). The Requirement
    # Coverage section itself is stripped first so a mapping target printed in
    # that table cannot trivially satisfy its own anchor.
    strict = _strict_mode(state)
    cov = requirements_mod.coverage(project, report_text=_strip_requirements_section(report_text))
    if strict and cov["total"] == 0:
        add("requirements_coverage", False,
            detail="academic deliverable with no requirements recorded — "
                   "run `requirements add` for each explicit prompt constraint")
    else:
        detail = "ok" if not cov["unmet"] else \
            "unmet: " + ", ".join(f"{r['id']} ({util.truncate(r['text'], 60)})"
                                  for r in cov["rows"] if r["id"] in cov["unmet"])
        add("requirements_coverage", not cov["unmet"], detail=detail)

    # gate: bibliography completeness (hard for academic deliverables, advisory otherwise)
    bib_missing = []
    for sid, s in sorted(sources.items()):
        if s.get("status") == "excluded":
            continue
        miss = bibmeta.missing_bib_fields(s, strict=strict)
        if miss:
            bib_missing.append(f"{sid}({','.join(miss)})")
    add("bibliography_complete", not bib_missing, hard=strict,
        detail=", ".join(bib_missing) or "ok")

    hard_fail = [c for c in checks if c["hard"] and not c["ok"]]
    return {"pass": not hard_fail, "checks": checks, "metrics": mr}


def check(project: Path, allow_flagged: bool = False) -> dict:
    project = Path(project)
    ledger = Ledger(project)
    state = paths.load_state(project)
    return _run_check(project, ledger, state, ctx={}, allow_flagged=allow_flagged)


# ------------------------------------------------------------------ helpers

def _section_text(text: str, heading: str) -> str:
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
                  text, re.M | re.S)
    return m.group(1) if m else ""


def _uncited_lines(section: str) -> list[str]:
    out = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or len(line) < 25:
            continue
        if line.startswith(("#", ">", "|", "**", "_", "```")):
            continue
        if line.startswith("---"):
            continue
        if re.match(r"^(counterpoints|gaps|evidence|sources)[.:]", line, re.I):
            continue
        if ID_RE.search(line):
            continue
        if line.endswith(":") and len(line) < 80:
            continue
        out.append(util.truncate(line, 90))
    return out


def md_to_html(body: str) -> str:
    """Very small markdown → HTML for finding bodies (paragraphs, bold, links, lists)."""
    def inline(t: str) -> str:
        t = _html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
        return t

    html_parts, para, in_list = [], [], False
    for line in body.splitlines():
        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            html_parts.append(f"<li>{inline(item)}</li>")
            continue
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        if not line.strip():
            if para:
                html_parts.append(f"<p>{inline(' '.join(para))}</p>")
                para = []
            continue
        if line.startswith("#"):
            continue
        para.append(line.strip())
    if in_list:
        html_parts.append("</ul>")
    if para:
        html_parts.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(html_parts)
