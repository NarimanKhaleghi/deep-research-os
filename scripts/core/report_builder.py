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

from core import (bibmeta, model_spec, report_assets, report_i18n,  # noqa: E402
                  requirements as requirements_mod, searchlog)
from core.evidence_store import Ledger  # noqa: E402
from lib import paths, util  # noqa: E402

STRENGTH_RANK = {"established": 0, "supported": 1, "tentative": 2}
CONF_RANK = {"high": 0, "medium": 1, "low": 2}
WEAK_CLAIM_STATUSES = {"weakly_supported", "contradicted", "unverifiable"}

PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX|lorem ipsum|placeholder)\b|\[insert", re.I)
ID_RE = re.compile(r"\b(FN-\d{2}|CL-\d{4}|CX-\d{4}|SRC-\d{4}|EV-\d{4})\b")


def _pkg_version() -> str:
    """Read the package version from pyproject.toml (fallback constant)."""
    try:
        import tomllib

        with open(paths.repo_root() / "pyproject.toml", "rb") as fh:
            return str(tomllib.load(fh)["project"]["version"])
    except Exception:  # noqa: BLE001
        return "1.4.0"


# ------------------------------------------------------------------ build

def build(project: Path, allow_flagged: bool = False, lang: str | None = None) -> dict:
    project = Path(project)
    ledger = Ledger(project)
    state = paths.load_state(project)
    brief_meta, _ = util.parse_front_matter(util.load_text(project / "brief.md"))
    lang = report_i18n.resolve(
        lang,
        str(brief_meta.get("title") or ""), str(brief_meta.get("question") or ""),
        str(state.get("title") or ""), str(state.get("question") or ""),
    )
    ctx = _context(project, ledger, state, lang)

    from jinja2 import Environment, FileSystemLoader

    loader = FileSystemLoader(str(paths.repo_root() / "templates"))
    md_env = Environment(loader=loader, autoescape=False, trim_blocks=True, lstrip_blocks=True)
    html_env = Environment(loader=loader, autoescape=True, trim_blocks=True, lstrip_blocks=True)

    ctx["gates_summary"] = report_i18n.t(lang, "gates.pending")
    util.atomic_write_text(project / "report.md", md_env.get_template("report.md.j2").render(**ctx))
    util.atomic_write_text(project / "report.html", html_env.get_template("report.html.j2").render(**ctx))

    check_result = _run_check(project, ledger, state, ctx=ctx, allow_flagged=allow_flagged)
    downgraded = [c for c in check_result["checks"] if c.get("downgraded")]
    if downgraded:
        ctx["limitations"].append(report_i18n.t(
            lang, "lim.downgraded", names=", ".join(c["name"] for c in downgraded)))
    ctx["gates_summary"] = _summary(check_result, lang)
    ctx["requirements"] = requirements_mod.coverage(
        project, report_text=_strip_requirements_section(util.load_text(project / "report.md")))
    ctx["strict"] = _strict_mode(state)
    util.atomic_write_text(project / "report.md", md_env.get_template("report.md.j2").render(**ctx))
    util.atomic_write_text(project / "report.html", html_env.get_template("report.html.j2").render(**ctx))

    state.setdefault("ran", {})["last_report_check_at"] = util.utcnow_iso()
    state["report_lang"] = lang
    steps = state["ran"].setdefault("steps", [])
    if "report" not in steps:
        steps.append("report")
    paths.save_state(project, state)

    return {"report_md": str(project / "report.md"), "report_html": str(project / "report.html"),
            "check": check_result, "metrics": check_result["metrics"], "lang": lang}


def _context(project: Path, ledger: Ledger, state: dict, lang: str = "en") -> dict:
    brief_meta, _ = util.parse_front_matter(util.load_text(project / "brief.md"))
    sources = ledger.sources()
    source_by_id = {s["id"]: s for s in sources}
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
    finding_claims: dict[str, list[str]] = {}
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
            for cid in claim_ids:
                finding_claims.setdefault(cid, []).append(findings[-1]["id"])

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

    # -------- model card, evidence depth, numeric provenance
    model = model_spec.context(project, lang)
    model_required, model_reason = model_spec.is_required(state, findings)
    if model_required and not model["present"]:
        model["limitations"] = [report_i18n.t(lang, "lim.model.missing")]
    depth = _evidence_depth(sources, claims, evidence)
    provenance = _provenance_rows(claims, evidence, sources, lang)

    # -------- limitations
    limitations = _limitations(project, state, sources, claims, cxs, vr, lang,
                               extra=model["limitations"])

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
            "url": apa["url"],
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

    # -------- claim & evidence appendix (every claim, with verbatim quotes)
    claim_index = []
    for c in sorted(claims, key=lambda x: x["id"]):
        evs = []
        for eid in c.get("evidence_ids") or []:
            e = ev_by_id.get(eid)
            if not e:
                continue
            evs.append({
                "id": e.get("id", eid), "quote": e.get("quote", ""),
                "source_id": e.get("source_id", ""),
                "source_title": (source_by_id.get(e.get("source_id", "")) or {}).get("title", ""),
                "locator": e.get("locator") or "",
                "relevance": e.get("relevance") or "",
            })
        claim_index.append({
            "id": c["id"], "text": c.get("text", ""),
            "status": c.get("status") or "unverified",
            "type": c.get("type") or "—",
            "status_reason": c.get("status_reason") or "",
            "updated_at": c.get("updated_at") or "",
            "critical": bool(c.get("critical")),
            "angles": c.get("angles") or [],
            "evidence": evs,
            "findings": sorted(finding_claims.get(c["id"], [])),
        })

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
        "model": model,
        "model_required": model_required,
        "model_reason": model_reason,
        "evidence_depth": depth,
        "provenance": provenance,
        "budget": budget_ctx,
        "limitations": limitations,
        "bibliography": bibliography,
        "search_method": search_method,
        "matrix": matrix,
        "requirements": requirements,
        "lang": lang,
        "direction": "rtl" if lang == "fa" else "ltr",
        "labels": report_i18n.labels(lang),
        "assets_css": report_assets.report_css(lang),
        "assets_js": report_assets.report_js(),
        "claims_count": len(claims),
        "claim_status": {c["id"]: (c.get("status") or "") for c in claims},
        "claim_index": claim_index,
    }


def _strict_mode(state: dict) -> bool:
    """Academic deliverables follow PRISMA-style reproducibility hard gates."""
    return (state.get("deliverable_type") == "academic-paper"
            or state.get("review_protocol") in ("prisma", "systematic-review"))


def _strip_requirements_section(text: str) -> str:
    for heading in report_i18n.heading_variants("requirements"):
        text = re.sub(rf"^##\s+{re.escape(heading)}\s*$.*?(?=^##\s|\Z)", "", text,
                      flags=re.M | re.S)
    return text


def _first_sentence(body: str) -> str:
    text = re.sub(r"^#+\s.*$", "", body, flags=re.M).strip()
    text = re.sub(r"[*_`>]", "", text)
    text = util.truncate(text.split(". ")[0].strip(), 240)
    return text or "—"


def _limitations(project: Path, state: dict, sources: list[dict], claims: list[dict],
                 cxs: list[dict], vr: dict, lang: str = "en",
                 extra: list[str] | None = None) -> list[str]:
    t = report_i18n.t
    lim: list[str] = []
    for req in requirements_mod.load(project):
        w = req.get("waiver") or {}
        if w.get("reason"):
            lim.append(t(lang, "lim.waived", id=req["id"],
                         text=util.truncate(req.get("text", ""), 80), reason=w["reason"]))
    for ex in (state.get("budget") or {}).get("exceptions") or []:
        lim.append(t(lang, "lim.budget", counter=ex.get("counter"), actual=ex.get("actual"),
                     ceiling=ex.get("ceiling"), reason=ex.get("reason")))
    for w in state.get("gate_waivers") or []:
        lim.append(t(lang, "lim.gate_waiver", phase=w.get("phase"), check=w.get("check"),
                     reason=w.get("reason")))
    for key, h in (state.get("source_health") or {}).items():
        if (h.get("failures") or 0) > 0:
            if h.get("last_error"):
                lim.append(t(lang, "lim.health", source=key, n=h["failures"], err=h["last_error"]))
            else:
                lim.append(t(lang, "lim.health_plain", source=key, n=h["failures"]))
    retracted = [s["id"] for s in sources if (s.get("retraction") or {}).get("status") == "retracted"]
    if retracted:
        lim.append(t(lang, "lim.retracted", ids=", ".join(retracted)))
    open_cx = [c["id"] for c in cxs if c["status"] == "open"]
    if open_cx:
        lim.append(t(lang, "lim.open_cx", ids=", ".join(open_cx)))
    gaps = vr.get("corroboration_gaps") or []
    if gaps:
        lim.append(t(lang, "lim.gaps", n=len(gaps),
                     ids=", ".join(g["claim_id"] for g in gaps[:5])))
    weak = [c["id"] for c in claims if c.get("status") in WEAK_CLAIM_STATUSES]
    if weak:
        lim.append(t(lang, "lim.weak", n=len(weak)))
    unreachable = [sid for sid, v in (vr.get("per_source") or {}).items()
                   if (v.get("verification") or {}).get("status") in ("unreachable",)]
    if unreachable:
        lim.append(t(lang, "lim.unreachable", ids=", ".join(unreachable)))
    for item in extra or []:
        if item and item not in lim:
            lim.append(item)
    if not lim:
        lim.append(t(lang, "lim.none"))
    return lim


def _evidence_depth(sources: list[dict], claims: list[dict],
                    evidence: list[dict]) -> dict:
    counts = {"full": 0, "partial": 0, "abstract": 0, "unknown": 0}
    for source in sources:
        ft_status = (source.get("fulltext") or {}).get("status")
        if ft_status:
            key = {"verified": "full", "partial": "partial",
                   "abstract-only": "abstract"}.get(ft_status, "unknown")
        else:
            depth = str(source.get("read_depth") or "unknown")
            key = {"full-text": "full", "partial": "partial",
                   "abstract": "abstract"}.get(depth, "unknown")
        counts[key] += 1
    by_id = {e.get("id"): e for e in evidence}
    source_by_id = {s.get("id"): s for s in sources}
    key_gaps = [s["id"] for s in sources
                if s.get("key_study")
                and ((s.get("fulltext") or {}).get("status") != "verified"
                     if (s.get("fulltext") or {}).get("status")
                     else str(s.get("read_depth") or "") != "full-text")]
    critical_abstract = []
    for claim in claims:
        if not claim.get("critical"):
            continue
        used = [source_by_id.get((by_id.get(eid) or {}).get("source_id"))
                for eid in claim.get("evidence_ids") or []]
        used = [s for s in used if s]
        def _not_verified(src: dict) -> bool:
            status = (src.get("fulltext") or {}).get("status")
            if status:
                return status != "verified"
            return str(src.get("read_depth") or "unknown") in {"abstract", "unknown"}

        if used and all(_not_verified(s) for s in used):
            critical_abstract.append(claim.get("id"))
    return {"counts": counts, "key_gaps": key_gaps,
            "critical_abstract": critical_abstract,
            "total": len(sources)}


def _format_number(number: dict) -> str:
    raw_value = number.get("raw")
    if raw_value is None:
        raw_value = number.get("value", "")
    raw = str(raw_value)
    unit = str(number.get("unit") or "")
    if unit and not raw.endswith(unit):
        return f"{raw} {unit}"
    return raw


def _provenance_rows(claims: list[dict], evidence: list[dict],
                     sources: list[dict], lang: str) -> list[dict]:
    by_id = {e.get("id"): e for e in evidence}
    source_by_id = {s.get("id"): s for s in sources}
    rows = []
    for claim in sorted(claims, key=lambda c: c.get("id", "")):
        if not claim.get("numbers"):
            continue
        values = ", ".join(_format_number(n) for n in claim.get("numbers") or [])
        linked = [by_id.get(eid) for eid in claim.get("evidence_ids") or []]
        linked = [e for e in linked if e]
        if not linked:
            rows.append({
                "claim_id": claim.get("id"), "text": util.truncate(claim.get("text", ""), 110),
                "values": values, "source": "—", "date": "—", "locator": "—",
                "depth": report_i18n.t(lang, "depth.unknown"),
            })
            continue
        for ev in linked:
            src = source_by_id.get(ev.get("source_id")) or {}
            depth = str(src.get("read_depth") or "unknown")
            rows.append({
                "claim_id": claim.get("id"),
                "text": util.truncate(claim.get("text", ""), 110),
                "values": values,
                "source": f"[{src.get('id', ev.get('source_id'))}] "
                          f"{util.truncate(src.get('title', ''), 60)}",
                "date": str(src.get("as_of") or src.get("published") or "—"),
                "locator": ev.get("locator") or "—",
                "depth": report_i18n.t(lang, f"depth.{depth}", default=depth),
            })
    return rows


def _provenance_gaps(claims: list[dict], evidence: list[dict],
                     sources: list[dict]) -> list[str]:
    by_id = {e.get("id"): e for e in evidence}
    source_by_id = {s.get("id"): s for s in sources}
    gaps = []
    for claim in claims:
        linked = [by_id.get(eid) for eid in claim.get("evidence_ids") or []]
        linked = [e for e in linked if e]
        if claim.get("numbers"):
            if not linked:
                gaps.append(f"{claim.get('id')}:no-evidence")
            for ev in linked:
                src = source_by_id.get(ev.get("source_id")) or {}
                if not (src.get("as_of") or src.get("published")):
                    gaps.append(f"{claim.get('id')}:{src.get('id', '?')}:undated")
        if claim.get("kind") == "normative":
            for ev in linked:
                src = source_by_id.get(ev.get("source_id")) or {}
                if str(src.get("type") or "") in {
                        "regulation", "law", "official", "central-bank", "regulator",
                        "government-report"} and not (src.get("as_of") or src.get("published")):
                    gaps.append(f"{claim.get('id')}:{src.get('id')}:no-as-of")
    return sorted(set(gaps))


def _summary(res: dict, lang: str = "en") -> str:
    checks = res["checks"]
    passed = sum(1 for c in checks if c["ok"])
    note = ""
    downgraded = [c for c in checks if c.get("downgraded")]
    if downgraded:
        note = "; " + report_i18n.t(
            lang, "gates.downgraded", k=len(downgraded),
            names=", ".join(c["name"] for c in downgraded))
    return report_i18n.t(lang, "gates.summary", p=passed, n=len(checks)) + note


# ------------------------------------------------------------------ gates

def _run_check(project: Path, ledger: Ledger, state: dict, ctx: dict,
               allow_flagged: bool) -> dict:
    report_path = project / "report.md"
    report_text = util.load_text(report_path)
    findings_meta = []
    fdir = project / "findings"
    if fdir.exists():
        for f in sorted(fdir.glob("FN-*.md")):
            meta, body = util.parse_front_matter(util.load_text(f))
            meta["_body"] = body
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

    # gate 0: report exists with required sections (english or persian headings)
    missing_sections = [key for key in report_i18n.REQUIRED_SECTION_KEYS
                        if not _has_section(report_text, key)]
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
    find_sec = _section_text(report_text, "findings")
    uncited = _uncited_lines(find_sec)
    mr["uncited_lines"] = len(uncited)
    add("findings_cited", not uncited and bool(findings_meta),
        detail=(f"{len(uncited)} uncited line(s): " + " | ".join(uncited[:3])) if uncited
        else ("no findings yet" if not findings_meta else "ok"))

    # gate 3: bibliography covers every SRC cited anywhere
    bib_sec = _section_text(report_text, "bibliography")
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
    lim_sec = _section_text(report_text, "limitations")
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
    model_required, model_reason = model_spec.is_required(state, findings_meta)
    model_check = model_spec.validate(
        project, source_ids=set(sources), strict_contract=model_required)
    if model_required and not model_check["present"]:
        add("model_artifact", False,
            detail=f"required by {model_reason}: model.json is missing")
    elif model_check["present"]:
        detail = "ok" if model_check["valid"] else "; ".join(model_check["errors"][:4])
        add("model_artifact", model_check["valid"], detail=detail)
    else:
        add("model_artifact", True, detail="not required")

    model_ctx = model_spec.context(
        project, ctx.get("lang") or state.get("report_lang") or "en")
    if model_ctx.get("present"):
        disclosed = [x for x in model_ctx.get("limitations") or []
                     if str(x)[:24] not in lim_sec]
        add("model_scope_disclosed", not disclosed,
            detail=("missing from Limitations: " + "; ".join(disclosed[:2])
                    if disclosed else "ok"))

    if strict or model_required:
        depth = _evidence_depth(ledger.sources(), claims, ledger.evidence())
        depth_gaps = [f"key study {sid} is not full-text" for sid in depth["key_gaps"]]
        depth_gaps += [f"critical claim {cid} rests only on abstract/unrecorded reading"
                       for cid in depth["critical_abstract"]]
        add("evidence_depth", not depth_gaps,
            detail="; ".join(depth_gaps[:4]) or "ok")
        provenance_gaps = _provenance_gaps(claims, ledger.evidence(), ledger.sources())
        add("numeric_provenance", not provenance_gaps,
            detail="; ".join(provenance_gaps[:4]) or "ok")

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

def _section_text(text: str, key: str) -> str:
    """Body of a canonical section, accepting its english or persian heading."""
    for heading in report_i18n.heading_variants(key):
        m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
        if m:
            return m.group(1)
    return ""


def _has_section(text: str, key: str) -> bool:
    return any(f"## {h}" in text for h in report_i18n.heading_variants(key))


def _uncited_lines(section: str) -> list[str]:
    out = _uncited_table_rows(section)
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


def _uncited_table_rows(section: str) -> list[str]:
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        rows = [row for row in block if row.strip().startswith("|")]
        if len(rows) < 3:
            return
        body_rows = rows[1:]
        if body_rows and _is_table_separator(body_rows[0]):
            body_rows = body_rows[1:]
        for row in body_rows:
            if not re.search(r"\d", row):
                continue
            if ID_RE.search(row) or re.search(r"\b(assumption|derived|input|output)\b",
                                                row, re.I):
                continue
            out.append("table row: " + util.truncate(row.strip(), 110))

    for raw in section.splitlines():
        if raw.strip().startswith("|"):
            block.append(raw)
        else:
            flush()
            block = []
    flush()
    return out


def _is_table_separator(row: str) -> bool:
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


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
