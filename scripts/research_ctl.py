#!/usr/bin/env python3
"""research_ctl — the deep-research-os command line.

The agent's primary interface: every command prints JSON to stdout (parse it);
`--human` prints a compact readable rendering. Exit codes: 0 ok · 1 gate/report
check failed · 2 error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors import registry  # noqa: E402
from core import budget as budget_mod  # noqa: E402
from core import claims as claims_mod  # noqa: E402
from core import contradictions as contradictions_mod  # noqa: E402
from core import credibility, extract, fulltext, fulltext_store, gates, model_spec  # noqa: E402
from core import manuscript as manuscript_mod  # noqa: E402
from core import report_builder, reporting_guidelines, resolver  # noqa: E402
from core import venue_profile, writing_corpus  # noqa: E402
from core import requirements as requirements_mod  # noqa: E402
from core import searchlog  # noqa: E402
from core import snapshot as snapshot_mod  # noqa: E402
from core import verify_citations  # noqa: E402
from core.evidence_store import Ledger  # noqa: E402
from learning import feedback as feedback_mod  # noqa: E402
from learning import maintain, preferences, proposals, sources_learning  # noqa: E402
from learning import upstream_scan  # noqa: E402
from lib import http, paths, util  # noqa: E402

RELEVANCE_CHOICES = ["supports", "refutes", "contextual", "methodological"]
CLAIM_TYPES = ["statistic", "causal", "forecast", "opinion", "methodological", "definition"]
STRENGTHS = ["established", "supported", "tentative"]
CONFIDENCES = ["high", "medium", "low"]
RESOLUTIONS = sorted(contradictions_mod.RESOLUTIONS)

BRIEF_KEYS = ["question", "title", "profile", "cutoff", "deliverable", "domain",
              "maintenance", "privacy_mode", "allow_paid", "success_criteria",
              "angles", "created", "deliverable_type", "review_protocol",
              "key_studies_target", "project_dir"]


# ================================================================== output

def out(obj, code: int = 0) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
    sys.exit(code)


def fail(message: str, code: int = 2) -> None:
    out({"error": message}, code)


def _human(obj: dict) -> str:
    lines = []
    for k, v in obj.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False, default=str)
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


# =============================================================== helpers

def _project(args) -> Path:
    return paths.resolve_project(getattr(args, "project", None), getattr(args, "vault", None))


def _state(project: Path) -> dict:
    return paths.load_state(project)


def _save(project: Path, state: dict) -> None:
    state["updated_at"] = util.utcnow_iso()
    paths.save_state(project, state)


def _bump(state: dict, counter: str, n: int = 1) -> None:
    state.setdefault("counters", {})
    state["counters"][counter] = state["counters"].get(counter, 0) + n


def _health(state: dict, service: str, ok: bool, error: str | None = None) -> None:
    h = state.setdefault("source_health", {}).setdefault(
        service, {"attempts": 0, "failures": 0, "last_error": None, "cost_usd": 0.0})
    h["attempts"] = h.get("attempts", 0) + 1
    if not ok:
        h["failures"] = h.get("failures", 0) + 1
        h["last_error"] = util.truncate(error or "", 200)


def _settings_path() -> Path:
    return paths.runtime_learning_dir() / "settings.json"


def _mode() -> str:
    return (util.read_json(_settings_path(), {}) or {}).get("mode", "auto")


def _learning_write_guard() -> str | None:
    if _mode() == "off":
        return "learning is off (`learn mode auto` to re-enable)"
    return None


def _choose_yn(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _serialize_front_matter(meta: dict, body: str) -> str:
    keys = [k for k in BRIEF_KEYS if k in meta] + sorted(k for k in meta if k not in BRIEF_KEYS)

    def q(s: str) -> str:
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = ["---"]
    for k in keys:
        v = meta[k]
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {q(item)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {q(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n" + (body or "").strip() + "\n"


def _write_front_matter(path: Path, updates: dict) -> dict:
    meta, body = util.parse_front_matter(util.load_text(path))
    meta.update(updates)
    util.atomic_write_text(path, _serialize_front_matter(meta, body))
    return meta


def _render_template(name: str, **ctx) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(paths.repo_root() / "templates")),
                      autoescape=False, trim_blocks=True, lstrip_blocks=True)
    return env.get_template(name).render(**ctx)


# ================================================================== init

def cmd_init(args) -> dict:
    paths.seed_runtime()
    profile = args.profile
    if profile == "max" and args.max_spend is None and not args.declare_uncapped:
        fail("profile 'max' requires declared spend: pass --max-spend N (or --declare-uncapped)")
    base_slug = util.slugify(args.title or args.question)
    if args.dir:
        project = Path(args.dir).expanduser().resolve()
        if (project / "state.json").exists():
            fail(f"{project} already contains a research project")
        if project.exists() and any(project.iterdir()) and not args.force:
            fail(f"{project} is not empty — pass --force to use it anyway")
        try:
            paths.guard_output_location(project)
        except ValueError as exc:
            fail(str(exc))
        slug = project.name or base_slug
        vault = project.parent
        vault_base = None
    else:
        vault = paths.vault_dir(args.vault)
        try:
            paths.guard_output_location(vault)
        except ValueError:
            fail("the default vault would land inside the skill/installation directory — "
                 "research outputs must go in a folder you choose: "
                 "init \"question\" --dir /path/to/your/folder")
        slug, n = base_slug, 2
        while (vault / "projects" / slug).exists():
            slug, n = f"{base_slug}-{n}", n + 1
        project = vault / "projects" / slug
        vault_base = str(vault)
    util.ensure_dir(project / "sources")
    util.ensure_dir(project / "findings")

    deliverable_type = args.deliverable_type
    review_protocol = args.review_protocol or ("prisma" if deliverable_type == "academic-paper" else "none")
    key_studies_target = args.key_studies_target or (
        8 if deliverable_type in ("academic-paper", "academic-manuscript") else 0)

    now = util.utcnow_iso()
    cutoff = args.cutoff or (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    angles = [a.strip() for a in (args.angles or "").split(";") if a.strip()]
    criteria = [s.strip() for s in (args.success or "").split(";") if s.strip()]

    state = {
        "slug": slug, "title": args.title or args.question, "question": args.question,
        "profile": profile, "privacy_mode": bool(args.privacy),
        "project_dir": str(project), "vault_base": vault_base,
        "deliverable_type": deliverable_type, "review_protocol": review_protocol,
        "key_studies_target": key_studies_target,
        "created_at": now, "updated_at": now, "phase_current": 0,
        "counters": {"searches": 0, "sources_read": 0, "evidence": 0, "claims": 0, "verify_passes": 0},
        "phases": {"0": {}}, "gate_waivers": [], "ran": {"steps": [], "last_verify_at": None,
                                                          "last_contradictions_scan_at": None,
                                                          "last_credibility_at": None,
                                                          "last_report_check_at": None},
        "preferences_asked": 0, "source_health": {}, "capability_used": [],
        "schema_version": "1.0.0",
    }
    budget_mod.init_budget(state, profile,
                           {"max_spend_usd": args.max_spend} if args.max_spend is not None else None)
    if args.declare_uncapped:
        state["budget"]["ceilings"]["max_spend_usd"] = None

    brief_md = _render_template(
        "brief.md.j2",
        question=args.question, title=args.title or args.question, profile=profile,
        cutoff=cutoff, deliverable=args.deliverable, domain=args.domain,
        maintenance=args.maintenance, privacy_mode=bool(args.privacy),
        success_criteria=criteria, angles=angles, created_at=now,
        deliverable_type=deliverable_type, review_protocol=review_protocol,
        key_studies_target=key_studies_target, project_dir=str(project),
    )
    util.atomic_write_text(project / "brief.md", brief_md)
    util.atomic_write_text(project / "plan.md",
                           f"# Research Plan — {args.title or args.question}\n\n"
                           "> Build this with `research_ctl.py plan set-section` per "
                           "references/phases/01-landscape.md and 02-plan.md.\n")
    util.write_json(paths.state_path(project), state)
    paths.register_project(project)
    return {"project": slug, "path": str(project),
            "deliverable_type": deliverable_type, "review_protocol": review_protocol,
            "note": "outputs live in the folder above; later commands find the most recent "
                    "project automatically, or use `--project <path>` / "
                    "`export RESEARCH_OS_PROJECT=<path>`",
            "next": "brief set … → plan set-section … → gate --phase 0"}


# ================================================================= status

def cmd_status(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    counts = ledger.counts()
    b = budget_mod.check(state)

    probe = None
    for phase in range(0, 10):
        r = gates.run(project, phase, persist=False)
        if not r["pass"]:
            probe = {"phase": phase, "failures": r["failures"]}
            break

    completed = sorted(int(k) for k, v in (state.get("phases") or {}).items() if v.get("completed_at"))
    return {
        "project": state.get("slug"), "path": str(project),
        "title": state.get("title"), "question": state.get("question"),
        "profile": state.get("profile"), "privacy_mode": state.get("privacy_mode", False),
        "phase_current": state.get("phase_current", 0), "phases_completed": completed,
        "counts": counts,
        "budget": {"spent_usd": (state.get("budget") or {}).get("spent_usd", 0.0),
                   "usage": b["usage"], "ok": b["ok"], "exceeded": b["exceeded"],
                   "exceptions": len((state.get("budget") or {}).get("exceptions") or [])},
        "ran": state.get("ran", {}),
        "learning": {"mode": _mode(),
                     "pending_proposals": len(proposals.pending()),
                     "preferences_asked": state.get("preferences_asked", 0)},
        "next_failing": probe,
        "hint": (f"phase {probe['phase']} gate not passing — run `gate --phase {probe['phase']}`"
                 if probe else "all gates passing — ready for `report build`"),
    }


# =================================================================== gate

def cmd_gate(args) -> tuple[dict, int]:
    project = _project(args)
    result = gates.run(project, args.phase)
    return result, (0 if result["pass"] else 1)


# ================================================================== brief

def cmd_brief_set(args) -> dict:
    project = _project(args)
    updates: dict = {}
    if args.question is not None:
        updates["question"] = args.question
    if args.title is not None:
        updates["title"] = args.title
    if args.profile is not None:
        updates["profile"] = args.profile
    if args.cutoff is not None:
        updates["cutoff"] = args.cutoff
    if args.deliverable is not None:
        updates["deliverable"] = args.deliverable
    if args.domain is not None:
        updates["domain"] = args.domain
    if args.maintenance is not None:
        updates["maintenance"] = args.maintenance
    if args.privacy is not None:
        updates["privacy_mode"] = _choose_yn(args.privacy)
    if args.angles is not None:
        updates["angles"] = [a.strip() for a in args.angles.split(";") if a.strip()]
    if args.success is not None:
        updates["success_criteria"] = [s.strip() for s in args.success.split(";") if s.strip()]
    if getattr(args, "deliverable_type", None) is not None:
        updates["deliverable_type"] = args.deliverable_type
    if getattr(args, "review_protocol", None) is not None:
        updates["review_protocol"] = args.review_protocol
    if getattr(args, "key_studies_target", None) is not None:
        updates["key_studies_target"] = args.key_studies_target
    if not updates:
        fail("nothing to set — pass at least one field flag")
    meta = _write_front_matter(project / "brief.md", updates)

    state = _state(project)
    for k in ("question", "title", "profile", "deliverable_type", "review_protocol",
              "key_studies_target"):
        if k in updates:
            state[k] = updates[k]
    if "privacy_mode" in updates:
        state["privacy_mode"] = updates["privacy_mode"]
    if updates.get("deliverable_type") == "academic-paper" and "review_protocol" not in updates \
            and meta.get("review_protocol") in (None, "none"):
        meta = _write_front_matter(project / "brief.md", {"review_protocol": "prisma"})
        state["review_protocol"] = "prisma"
    _save(project, state)
    return {"brief": {k: meta.get(k) for k in BRIEF_KEYS if k in meta}}


def cmd_brief_show(args) -> dict:
    project = _project(args)
    meta, body = util.parse_front_matter(util.load_text(project / "brief.md"))
    return {"front_matter": meta, "body": body}


# =================================================================== plan

def cmd_plan_set_section(args) -> dict:
    project = _project(args)
    content = args.text
    if args.file:
        content = util.load_text(Path(args.file))
    if args.stdin or (content is None and not sys.stdin.isatty()):
        content = sys.stdin.read()
    if not content or not content.strip():
        fail("no section content — pass --text, --file or pipe via stdin")

    plan_path = project / "plan.md"
    plan = util.load_text(plan_path) or "# Research Plan\n"
    name = args.name.strip()
    pattern = re.compile(rf"^##\s+{re.escape(name)}\s*$", re.M)
    m = pattern.search(plan)
    section_md = f"## {name}\n\n{content.strip()}\n"
    if m:
        nxt = re.search(r"^##\s+", plan[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(plan)
        plan = plan[:m.start()] + section_md + "\n" + plan[end:]
    else:
        plan = plan.rstrip() + "\n\n" + section_md
    util.atomic_write_text(plan_path, plan)
    return {"plan": str(plan_path), "section": name,
            "bullets": util.count_bullets(content)}


def cmd_plan_show(args) -> dict:
    project = _project(args)
    return {"plan": util.load_text(project / "plan.md"),
            "sections": list(util.md_sections(util.load_text(project / "plan.md")).keys())}


# ================================================================= search

def cmd_search(args) -> dict:
    project = _project(args)
    state = _state(project)
    query = args.query_flag or args.query_pos
    if not query:
        fail("query required: `search --query \"…\"`")
    domains = [d.strip() for d in args.domains.split(",") if d.strip()] if args.domains else None
    result = registry.route(
        query, domains=domains, limit=args.limit,
        profile=state.get("profile", "standard"),
        override_source=args.source, seed=args.seed,
        all_academic=bool(getattr(args, "all_academic", False)),
        per_source=getattr(args, "per_source", None),
        page=getattr(args, "page", 1),
        year_from=getattr(args, "year_from", None),
        year_to=getattr(args, "year_to", None),
        oa_only=bool(getattr(args, "oa_only", False)),
        types=[t.strip() for t in (getattr(args, "type_filter", None) or "").split(",") if t.strip()] or None,
        sort=getattr(args, "sort", "relevance"),
    )
    _bump(state, "searches")
    for name, count in result["provenance"].items():
        sources_learning.record_search(name, domains, count)
    for f in result["failures"]:
        _health(state, f["service"], False, f["error"])
    for name in result["provenance"]:
        if name not in {f["service"] for f in result["failures"]}:
            _health(state, name, True)
    _save(project, state)

    records = []
    for r in result["records"][: args.limit]:
        records.append({
            "title": r.get("title"), "url": r.get("url"), "doi": r.get("doi"),
            "service": r.get("service"), "published": r.get("published"),
            "authors": (r.get("authors") or [])[:3],
            "type": r.get("type"),
            "abstract": util.truncate(r.get("abstract") or "", 300),
            "seen_in": (r.get("extra") or {}).get("seen_in", []),
            "is_oa": (r.get("extra") or {}).get("is_oa"),
            "citations": (r.get("extra") or {}).get("cited_by_count")
                         or (r.get("extra") or {}).get("cited_by"),
            "pdf_url": (r.get("extra") or {}).get("pdf_url"),
        })
    entry = searchlog.append(project, {
        "query": query, "engine": "connector-route", "manual": False,
        "domains": domains or ["auto"], "angle": getattr(args, "angle", None),
        "chosen": result["chosen"],
        "provenance": result["provenance"],
        "failures": [f["service"] for f in result["failures"]],
        "hits": sum(result["provenance"].values()),
        "kept": len(records),
        "urls": [r["url"] for r in records if r.get("url")][:60],
        "notes": getattr(args, "notes", None),
        "filters": result.get("filters"),
    })
    return {"query": query, "chosen": result["chosen"], "provenance": result["provenance"],
            "failures": result["failures"], "filters": result.get("filters"),
            "count": len(records), "records": records, "search_log_id": entry["id"]}


def cmd_searchlog_add(args) -> dict:
    project = _project(args)
    entry = searchlog.append(project, {
        "query": args.query, "engine": args.engine, "manual": True,
        "angle": args.angle, "hits": args.hits, "kept": args.kept or 0,
        "notes": args.notes, "urls": [],
    })
    return {"search_log_id": entry["id"], "entry": entry}


def cmd_searchlog_list(args) -> dict:
    project = _project(args)
    return searchlog.summarize(project)


# =========================================================== requirements

def cmd_requirements_add(args) -> dict:
    project = _project(args)
    try:
        rec = requirements_mod.add(project, args.text, origin=args.origin or "user prompt",
                                   rid=args.id)
    except ValueError as exc:
        fail(str(exc))
    return {"requirement": rec, "total": len(requirements_mod.load(project))}


def cmd_requirements_map(args) -> dict:
    project = _project(args)
    try:
        rec = requirements_mod.map_target(project, args.requirement_id, args.target)
    except KeyError as exc:
        fail(str(exc))
    cov = requirements_mod.coverage(project)
    return {"requirement": rec, "unmet": cov["unmet"]}


def cmd_requirements_waive(args) -> dict:
    project = _project(args)
    try:
        rec = requirements_mod.waive(project, args.requirement_id, args.reason)
    except KeyError as exc:
        fail(str(exc))
    return {"requirement": rec}


def cmd_requirements_list(args) -> dict:
    project = _project(args)
    return requirements_mod.coverage(project)


# ================================================================ project

def cmd_project_where(args) -> dict:
    project = _project(args)
    return {"path": str(project), "slug": paths.load_state(project).get("slug")}


def cmd_project_move(args) -> dict:
    import shutil
    project = _project(args)
    target = Path(args.to).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        fail(f"{target} is not empty — choose an empty or new folder")
    try:
        paths.guard_output_location(target)
    except ValueError as exc:
        fail(str(exc))
    old = project
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.rmdir()
    shutil.copytree(old, target)
    if args.remove_original:
        shutil.rmtree(old)
    state = paths.load_state(target)
    state["project_dir"] = str(target)
    paths.save_state(target, state)
    paths.register_project(target)
    return {"moved_to": str(target), "original_removed": bool(args.remove_original),
            "note": "use `--project " + str(target) + "` or export RESEARCH_OS_PROJECT"}


# =================================================================== read

def _infer_tier(stype: str, service: str) -> int:
    if stype in ("journal-article", "statistics", "filing", "report", "dataset", "book"):
        return 1
    if stype in ("news", "webpage"):
        return 2
    if service == "hackernews":
        return 3
    return 2


def _norm_doi(value: str | None) -> str | None:
    return fulltext.normalize_doi(value)


def _find_source(ledger: Ledger, *, source_id: str | None = None,
                 doi: str | None = None, url: str | None = None) -> dict | None:
    if source_id:
        return ledger.source(source_id)
    want = _norm_doi(doi)
    want_url = util.normalize_text(url or "")
    for src in ledger.sources():
        if want and _norm_doi(src.get("doi")) == want:
            return src
        if want and _norm_doi(src.get("published_doi")) == want:
            return src
        if want_url and util.normalize_text(src.get("url") or "") == want_url:
            return src
    return None


def _metadata_for_doi(doi: str) -> dict:
    from connectors import crossref, openalex

    rec = crossref.get_work(doi)
    if rec:
        return rec
    rec = openalex.get_work(doi)
    return rec or {"title": "", "url": f"https://doi.org/{doi}", "doi": doi,
                   "authors": [], "published": None, "publisher": None,
                   "type": "journal-article", "abstract": None, "extra": {}}


def _new_source(ledger: Ledger, rec: dict, *, angles: list[str] | None = None,
                service: str = "fulltext") -> dict:
    title = (rec.get("title") or "").strip() or (rec.get("doi") or "Untitled source")
    url = (rec.get("url") or "").strip() or (
        f"https://doi.org/{rec['doi']}" if rec.get("doi") else "local://untitled")
    doi = _norm_doi(rec.get("doi"))
    return ledger.add_source({
        "url": url, "doi": doi, "title": title,
        "authors": rec.get("authors") or [],
        "publisher": rec.get("publisher") or util.domain_of(url),
        "published": rec.get("published"),
        "accessed_at": util.utcnow_iso(), "service": service,
        "type": rec.get("type") or "journal-article",
        "tier": _infer_tier(rec.get("type") or "journal-article", service),
        "origin_key": util.domain_of(url), "angles_covered": angles or ["unassigned"],
        "abstract": rec.get("abstract"),
        "status": "included", "extra": rec.get("extra") or {},
        "read_depth": "abstract",
    })


def _merge_source_metadata(ledger: Ledger, source: dict, rec: dict) -> dict:
    fields = {}
    for key in ("title", "doi", "url", "publisher", "published", "abstract"):
        if rec.get(key) and not source.get(key):
            fields[key] = rec[key]
    if rec.get("authors") and not source.get("authors"):
        fields["authors"] = rec["authors"]
    if rec.get("extra"):
        extra = dict(source.get("extra") or {})
        for k, v in rec["extra"].items():
            extra.setdefault(k, v)
        fields["extra"] = extra
    return ledger.update_source(source["id"], **fields) if fields else source


def _record_attempt(state: dict, provider: str, ok: bool, error: str | None = None) -> None:
    _health(state, provider or "fulltext", ok, error)


def _try_fulltext_candidate(project: Path, ledger: Ledger, source: dict,
                            candidate: dict, state: dict) -> dict:
    sid = source["id"]
    tmp = Path(project) / "sources" / f".{sid}.download"
    try:
        info = http.download(candidate["url"], tmp, timeout=90, retries=1,
                             allowed_content_types=http.FULLTEXT_CONTENT_TYPES)
        data = tmp.read_bytes()
        artifact = fulltext.extract_artifact(
            data, filename=candidate.get("url", "").split("?")[0],
            content_type=info.get("content_type"))
        validation = fulltext.validate_identity(source, artifact, strict=True)
        if not validation["ok"]:
            raise ValueError("identity check failed: " + "; ".join(validation["reasons"]))
        if artifact.get("format") == "html":
            raise ValueError("only a landing page was available (HTML is partial, not verified)")
        status = "verified"
        if int(validation.get("chars") or 0) < 1200:
            status = "needs_ocr"
            raise ValueError(f"extracted text too short ({validation.get('chars')} chars)")
        origin = {
            "url": candidate["url"], "final_url": info.get("final_url") or candidate["url"],
            "host": candidate.get("host") or util.domain_of(candidate["url"]),
            "bytes": info.get("bytes") or len(data),
            "license": candidate.get("license"),
            "landing_url": candidate.get("landing_url"),
        }
        rec = fulltext_store.store_artifact(
            project, ledger, source, data, artifact, origin, status=status,
            version=candidate.get("version") or "unknown",
            license_=candidate.get("license"), validation=validation,
        )
        rec = ledger.update_source(sid, read_at=util.utcnow_iso(),
                                   abstract=source.get("abstract") or artifact.get("abstract") or None)
        _record_attempt(state, candidate.get("provider") or "fulltext", True)
        return {"source": rec, "candidate": candidate, "validation": validation,
                "artifact": artifact}
    except Exception as exc:  # noqa: BLE001
        _record_attempt(state, candidate.get("provider") or "fulltext", False,
                        f"{type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _store_abstract_only(project: Path, ledger: Ledger, source: dict,
                         abstract: str, *, reason: str, state: dict) -> dict:
    quality = fulltext.assess_abstract(abstract, title=source.get("title") or "")
    if quality["verdict"] != "comprehensive":
        fail("abstract is not comprehensive enough for an abstract-only exception "
             f"(verdict={quality['verdict']}, words={quality['words']}, score={quality['score']}); "
             "supply full text or use --metadata-only for context-only metadata")
    exception = {"reason": reason, "approved_at": util.utcnow_iso(),
                 "quality": quality["verdict"], "words": quality["words"],
                 "score": quality["score"]}
    rec = fulltext_store.store_abstract(project, ledger, source, abstract,
                                        quality=quality, exception=exception)
    _record_attempt(state, "abstract", True)
    return rec


def _legacy_read(project: Path, state: dict, ledger: Ledger, source: dict,
                 url: str, args) -> dict:
    """Web/news page snapshot path retained for non-academic sources."""
    title = args.title or source.get("title")
    published = None
    text = ""
    try:
        if url.lower().endswith(".pdf") or args.pdf:
            data = http.get_bytes(url)
            text, _ = extract.extract_pdf(data)
            if text and not title:
                title = util.truncate(next((l for l in text.splitlines() if l.strip()), ""), 120)
        else:
            page = extract.fetch_page(url)
            text = page.get("text") or ""
            title = title or page.get("title")
            published = page.get("published")
            url = page.get("final_url") or url
    except http.OfflineError:
        fail("offline mode is on (RESEARCH_OS_OFFLINE=1) — read requires network")
    except Exception as exc:  # noqa: BLE001
        _health(state, args.service or "web", False, f"{type(exc).__name__}: {exc}")
        _save(project, state)
        fail(f"fetch failed: {type(exc).__name__}: {exc}")
    text = (text or "").strip()
    if len(text) < 200:
        _health(state, args.service or "web", False, "extracted text too short")
        _save(project, state)
        fail(f"extracted text too short ({len(text)} chars) — page may be JS-rendered; "
             "try the Playwright/SearXNG ladder in references/sources/fallbacks.md")
    sid = source["id"]
    snap = snapshot_mod.snapshot_text(project, sid, text, "text")
    if not http.is_offline() and args.wayback:
        snap["archived_url"] = snapshot_mod.wayback_lookup(url)
    fields = {
        "url": url, "title": title or url, "published": source.get("published") or published,
        "accessed_at": util.utcnow_iso(), "snapshot": snap, "read_depth": "partial",
    }
    rec = ledger.update_source(sid, **fields)
    cred = credibility.score_source(rec)
    rec = ledger.update_source(sid, credibility=cred)
    _bump(state, "sources_read")
    state.setdefault("ran", {})["last_credibility_at"] = util.utcnow_iso()
    _health(state, args.service or rec.get("service") or "web", True)
    _save(project, state)
    return {"source_id": sid, "title": rec["title"], "service": rec.get("service"),
            "type": rec.get("type"), "status": "partial",
            "words": len(text.split()), "chars": len(text), "snapshot": snap,
            "credibility": {"band": cred["band"], "score": cred["score"]},
            "text_path": str(project / snap["path"]), "excerpt": text[:2500],
            "warnings": ["web page stored as partial snapshot; use --doi/--require-fulltext for academic full text"]}


def cmd_read(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)

    url = args.url
    doi = _norm_doi(getattr(args, "doi", None))
    file_path = Path(args.file).expanduser() if getattr(args, "file", None) else None
    existing = _find_source(ledger, source_id=args.source_id, doi=doi, url=url)

    if file_path:
        if not file_path.exists():
            fail(f"file not found: {file_path}")
        data = file_path.read_bytes()
        artifact = fulltext.extract_artifact(data, filename=file_path.name)
        if existing is None:
            rec = {"title": artifact.get("title") or file_path.stem,
                   "url": f"local://{file_path.name}", "doi": artifact.get("doi"),
                   "authors": artifact.get("authors") or [], "type": "journal-article",
                   "abstract": artifact.get("abstract") or None, "extra": {}}
            existing = _new_source(ledger, rec, angles=args.angles.split(",") if args.angles else None,
                                   service="local-file")
        validation = fulltext.validate_identity(existing, artifact, strict=not args.force)
        if not validation["ok"] and not args.force:
            fail("identity check failed: " + "; ".join(validation["reasons"]))
        if validation.get("abstract_only") and not args.allow_abstract:
            fail("file looks abstract-only; pass --allow-abstract with a reason to store it")
        if validation.get("abstract_only"):
            return _read_result(project, state, ledger, existing,
                                _store_abstract_only(project, ledger, existing,
                                                     artifact.get("text") or "",
                                                     reason=args.abstract_reason or "user-supplied abstract",
                                                     state=state), "abstract-only")
        origin = {"url": str(file_path), "final_url": str(file_path),
                  "host": "local", "bytes": len(data)}
        rec = fulltext_store.store_artifact(
            project, ledger, existing, data, artifact, origin,
            status="verified", version="unknown", validation=validation)
        rec = ledger.update_source(existing["id"], read_at=util.utcnow_iso())
        _bump(state, "sources_read")
        _save(project, state)
        return _read_result(project, state, ledger, rec, {"validation": validation}, "verified")

    if doi and existing is None:
        meta = _metadata_for_doi(doi)
        existing = _new_source(ledger, meta, angles=args.angles.split(",") if args.angles else None,
                               service="doi")
    elif existing is None and url:
        existing = _new_source(ledger, {"title": args.title or url, "url": url,
                                        "doi": registry.extract_doi_from_url(url),
                                        "authors": [], "type": "webpage", "extra": {}},
                               angles=args.angles.split(",") if args.angles else None,
                               service=args.service or "web")
    if existing is None:
        fail("pass a URL, --doi, --file or --source-id")
    doi = doi or _norm_doi(existing.get("doi"))
    if doi and existing.get("doi") != doi:
        existing = ledger.update_source(existing["id"], doi=doi)

    if (not doi and not args.require_fulltext and not args.metadata_only
            and not args.allow_abstract and url):
        return _legacy_read(project, state, ledger, existing, url, args)

    abstract = existing.get("abstract") or ""
    if args.metadata_only:
        rec = fulltext_store.store_metadata(
            project, ledger, existing, abstract,
            reason=args.abstract_reason or "metadata-only read")
        _save(project, state)
        return _read_result(project, state, ledger, rec, {}, "metadata-only")

    if not args.refresh and (existing.get("fulltext") or {}).get("status") == "verified":
        check = fulltext_store.verify(project, existing)
        if check["ok"]:
            return _read_result(project, state, ledger, existing,
                                {"already_verified": True}, "verified")

    candidates = resolver.resolve(existing, doi=doi or existing.get("doi"), url=url,
                                  include_preprint=not args.no_preprint)
    attempts: list[dict] = []
    for cand in candidates:
        try:
            result = _try_fulltext_candidate(project, ledger, existing, cand, state)
            _bump(state, "sources_read")
            state.setdefault("ran", {})["last_credibility_at"] = util.utcnow_iso()
            _save(project, state)
            return _read_result(project, state, ledger, result["source"],
                                {"candidate": cand, "validation": result["validation"],
                                 "attempts": attempts}, "verified")
        except Exception as exc:  # noqa: BLE001
            attempts.append({"provider": cand.get("provider"), "url": cand.get("url"),
                             "error": util.truncate(f"{type(exc).__name__}: {exc}", 300)})

    if abstract and args.allow_abstract:
        rec = _store_abstract_only(project, ledger, existing, abstract,
                                   reason=args.abstract_reason or "no lawful full text found",
                                   state=state)
        _save(project, state)
        return _read_result(project, state, ledger, rec,
                            {"attempts": attempts}, "abstract-only")

    _save(project, state)
    if args.require_fulltext:
        fail("no lawful verified full text found; attempts: " + json.dumps(attempts, ensure_ascii=False))
    fail("no lawful full text found; use --allow-abstract for a documented exception, "
         "or add a PDF to inbox/ and run `fulltext scan-inbox`; attempts: "
         + json.dumps(attempts, ensure_ascii=False))


def _read_result(project: Path, state: dict, ledger: Ledger, source: dict,
                 extra: dict, status: str) -> dict:
    text = fulltext_store.read_text(project, source)
    cred = source.get("credibility") or credibility.score_source(source)
    if not source.get("credibility"):
        source = ledger.update_source(source["id"], credibility=cred)
    snap = source.get("snapshot") or {}
    return {
        "source_id": source["id"], "title": source.get("title"), "service": source.get("service"),
        "type": source.get("type"), "status": status,
        "fulltext": source.get("fulltext"),
        "words": len(text.split()), "chars": len(text),
        "snapshot": snap, "credibility": {"band": cred.get("band"), "score": cred.get("score")},
        "text_path": str(project / snap["path"]) if snap.get("path") else None,
        "excerpt": text[:2500],
        **extra,
    }



def cmd_sources_update(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    fields: dict = {}
    for attr, key in (("title", "title"), ("type", "type"), ("publisher", "publisher"),
                      ("published", "published"), ("doi", "doi"), ("as_of", "as_of"),
                      ("venue", "venue"), ("volume", "volume"), ("issue", "issue"),
                      ("pages", "pages"), ("published_doi", "published_doi"),
                      ("preprint_doi", "preprint_doi"), ("read_depth", "read_depth")):
        val = getattr(args, attr, None)
        if val is not None:
            fields[key] = val
    if args.tier is not None:
        fields["tier"] = args.tier
    if args.angles is not None:
        fields["angles_covered"] = [a.strip() for a in args.angles.split(",") if a.strip()]
    if args.year is not None:
        fields["year"] = args.year
    if args.status is not None:
        if args.status == "excluded" and not args.exclude_reason:
            fail("status 'excluded' requires --exclude-reason (screening must be auditable)")
        fields["status"] = args.status
        if args.exclude_reason:
            fields["exclusion_reason"] = args.exclude_reason
    if not fields:
        fail("nothing to update")
    rec = ledger.update_source(args.source_id, **fields)
    if any(k in fields for k in ("type", "published", "doi")):
        rec = ledger.update_source(args.source_id, credibility=credibility.score_source(rec))
    return {"source": {k: rec.get(k) for k in ("id", "title", "type", "tier", "angles_covered",
                                               "url", "doi", "status", "exclusion_reason",
                                               "venue", "year", "as_of", "read_depth")},
            "credibility": {"band": (rec.get("credibility") or {}).get("band"),
                            "score": (rec.get("credibility") or {}).get("score")}}


def cmd_model_check(args) -> tuple[dict, int]:
    project = _project(args)
    state = _state(project)
    findings = []
    for path in sorted((project / "findings").glob("FN-*.md")):
        meta, body = util.parse_front_matter(util.load_text(path))
        meta["_body"] = body
        findings.append(meta)
    strict, reason = model_spec.is_required(state, findings)
    result = model_spec.validate(
        project, source_ids={s["id"] for s in Ledger(project).sources()},
        strict_contract=strict)
    result["required"] = strict
    result["required_by"] = reason
    if not strict and not result["present"]:
        result["valid"] = True
        result["ok"] = True
        result["errors"] = []
        result["warnings"] = ["model.json not present; not required for this deliverable"]
    result.pop("_data", None)
    return result, (0 if result["valid"] else 1)


def cmd_sources_review(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    rec = ledger.source(args.source_id)
    if rec is None:
        fail(f"source {args.source_id} not found")
    review = dict(rec.get("review") or {})
    for attr, key in (("problem", "problem"), ("framework", "framework"), ("method", "method"),
                      ("context", "context"), ("findings", "findings"),
                      ("limitations", "limitations"), ("relevance_note", "relevance")):
        val = getattr(args, attr, None)
        if val is not None:
            review[key] = val
    fields: dict = {"review": review}
    if args.key:
        fields["key_study"] = True
    if args.unkey:
        fields["key_study"] = False
    rec = ledger.update_source(args.source_id, **fields)
    filled = sorted(k for k in ("problem", "framework", "method", "context", "findings",
                                "limitations", "relevance") if review.get(k))
    return {"source_id": args.source_id, "key_study": bool(rec.get("key_study")),
            "review_fields": filled,
            "missing_fields": [k for k in ("problem", "framework", "method", "context",
                                           "findings", "limitations", "relevance")
                               if not review.get(k)]}


def cmd_sources_enrich(args) -> dict:
    project = _project(args)
    from core import bibmeta
    ledger = Ledger(project)
    if args.all:
        targets = [s["id"] for s in ledger.sources() if s.get("doi")]
        if not targets:
            fail("no sources carry a DOI — nothing to enrich")
    elif args.source_id:
        targets = [args.source_id]
    else:
        fail("pass --source-id or --all")
    online = not args.offline
    results = [bibmeta.enrich_source(project, sid, online=online) for sid in targets]
    return {"enriched": sum(1 for r in results if r["enriched"]), "results": results}


# =============================================================== evidence

def cmd_evidence_add(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    src = ledger.source(args.source_id)
    if src is None:
        fail(f"source {args.source_id} not found")
    if not args.quote or len(args.quote.strip()) < 8:
        fail("quote must be verbatim and ≥8 chars")

    snap_text = snapshot_mod.read_snapshot(project, src)
    found = False
    if snap_text:
        found, _, _ = util.quote_in_text(args.quote, snap_text, threshold=0.95)
    validation = {"quote_found": bool(found), "checked_in": "snapshot" if snap_text else "missing",
                  "threshold": 0.95, "at": util.utcnow_iso()}
    rec = ledger.add_evidence({
        "source_id": args.source_id, "quote": args.quote.strip(),
        "locator": args.locator, "relevance": args.relevance, "angle": args.angle,
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "numbers": util.extract_numbers(args.quote),
        "validation": validation,
    })
    _bump(state, "evidence")
    _save(project, state)
    result = {"evidence_id": rec["id"], "validation": validation}
    if not found:
        result["warning"] = ("quote not found in the snapshot (fuzzy ≥0.95) — phase-4 gate "
                             "will fail until fixed")
    if args.angle is None:
        result.setdefault("warnings", []).append("no angle given — phase-4 gate requires angle ∈ brief angles")
    return result


def cmd_evidence_list(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    rows = ledger.evidence()
    if args.source_id:
        rows = [e for e in rows if e["source_id"] == args.source_id]
    return {"count": len(rows), "evidence": [
        {k: e.get(k) for k in ("id", "source_id", "angle", "relevance", "locator",
                               "quote", "validation")} for e in rows]}


# ================================================================= claims

def cmd_claims_add(args) -> tuple[dict, int]:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    try:
        claim = claims_mod.build_claim(
            args.text, type_=args.type, kind=args.kind,
            tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
            angles=[a.strip() for a in (args.angles or "").split(",") if a.strip()],
            evidence_ids=[e.strip() for e in (args.evidence or "").split(",") if e.strip()],
            critical=bool(args.critical),
        )
    except ValueError as exc:
        fail(str(exc))
    rec = ledger.add_claim(claim)
    _bump(state, "claims")
    _save(project, state)
    warnings = [] if rec["evidence_ids"] else ["claim has no evidence_ids — phase-6 gate requires them"]
    if rec.get("modality"):
        warnings.append("normative phrasing detected — supporting quotes must also be normative, "
                        "and an official/primary source is required for `kind: normative`")
    return {"claim_id": rec["id"], "numbers": rec["numbers"], "status": rec["status"],
            "kind": rec["kind"], "modality": rec.get("modality", False),
            "warnings": warnings}, 0


def cmd_claims_list(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    return {"count": len(ledger.claims()), "claims": ledger.claims()}


# ============================================================ credibility

def cmd_credibility_score(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    scored = []
    for s in ledger.sources():
        extra = dict(s.get("extra") or {})
        if not (s.get("retraction") or {}).get("checked_at"):
            retr = {"status": "retracted" if extra.get("is_retracted") else "unknown",
                    "source_flag": "connector:is_retracted" if extra.get("is_retracted") else None,
                    "checked_at": util.utcnow_iso(), "method": "connector-metadata"}
            ledger.update_source(s["id"], retraction=retr)
            s["retraction"] = retr
        if s.get("credibility", {}).get("score") and not args.force:
            scored.append({"source_id": s["id"], "band": s["credibility"]["band"],
                           "score": s["credibility"]["score"], "rescored": False})
            continue
        cred = credibility.score_source(s)
        ledger.update_source(s["id"], credibility=cred)
        scored.append({"source_id": s["id"], "band": cred["band"],
                       "score": cred["score"], "rescored": True,
                       "rationale": cred["rationale"]})
    state.setdefault("ran", {})["last_credibility_at"] = util.utcnow_iso()
    _save(project, state)
    bands = {}
    for row in scored:
        bands[row["band"]] = bands.get(row["band"], 0) + 1
    return {"scored": len(scored), "bands": bands, "sources": scored}


def cmd_credibility_show(args) -> dict:
    project = _project(args)
    src = Ledger(project).source(args.source_id)
    if src is None:
        fail(f"source {args.source_id} not found")
    return {"source_id": src["id"], "title": src.get("title"),
            "credibility": src.get("credibility"), "verification": src.get("verification"),
            "retraction": src.get("retraction"), "snapshot": src.get("snapshot")}


# ================================================================= verify

def cmd_verify(args) -> dict:
    project = _project(args)
    report = verify_citations.run(project, online=args.online)
    return {"mode": report["mode"], "citation_precision": report["citation_precision"],
            "checked_citations": report["checked_citations"],
            "fabrication_suspected": report["fabrication_suspected"],
            "number_mismatches": report["number_mismatches"],
            "corroboration_gaps": report["corroboration_gaps"],
            "modality_mismatches": report["modality_mismatches"],
            "primary_source_gaps": report["primary_source_gaps"],
            "staleness_warnings": report["staleness_warnings"],
            "claims_summary": report["claims_summary"],
            "open_contradictions": report["open_contradictions"],
            "report_path": str(project / "verify_report.json")}


# ========================================================== contradictions

def cmd_contradictions_scan(args) -> dict:
    project = _project(args)
    state = _state(project)
    created = contradictions_mod.scan(Ledger(project))
    state.setdefault("ran", {})["last_contradictions_scan_at"] = util.utcnow_iso()
    steps = state["ran"].setdefault("steps", [])
    if "contradictions" not in steps:
        steps.append("contradictions")
    _save(project, state)
    return {"created": [c["id"] for c in created], "created_count": len(created)}


def cmd_contradictions_list(args) -> dict:
    project = _project(args)
    rows = Ledger(project).contradictions()
    if args.open:
        rows = [r for r in rows if r["status"] == "open"]
    return {"count": len(rows), "contradictions": rows}


def cmd_contradictions_adjudicate(args) -> dict:
    project = _project(args)
    cx = contradictions_mod.adjudicate(
        Ledger(project), args.cx_id, args.resolution, args.rationale, by=args.by)
    guard = _learning_write_guard()
    if not guard:
        try:
            state = _state(project)
            feedback_mod.journal("adjudication", f"{cx['id']} {args.resolution}",
                                 project=state.get("slug"), detail=args.rationale)
        except Exception:
            pass
    return {"contradiction": cx}


# =============================================================== findings

def _next_finding_id(project: Path) -> str:
    nums = [int(m.group(1)) for f in (project / "findings").glob("FN-*.md")
            if (m := re.match(r"FN-(\d+)\.md$", f.name))]
    return f"FN-{(max(nums) + 1 if nums else 1):02d}"


def cmd_findings_new(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    claim_ids = [c.strip() for c in args.claims.split(",") if c.strip()]
    for cid in claim_ids:
        if ledger.claim(cid) is None:
            fail(f"claim {cid} not found")
    body = args.body
    if args.body_file:
        body = util.load_text(Path(args.body_file))
    if not body and not sys.stdin.isatty():
        body = sys.stdin.read()
    if not body or not body.strip():
        fail("finding body required (--body, --body-file or stdin)")

    fid = _next_finding_id(project)
    meta = {
        "id": fid, "title": args.title, "strength": args.strength,
        "confidence": args.confidence, "kind": args.kind, "claims": claim_ids,
        "counterpoints": [c.strip() for c in (args.counterpoints or "").split(";") if c.strip()],
        "gaps": [g.strip() for g in (args.gaps or "").split(";") if g.strip()],
        "angles": [a.strip() for a in (args.angles or "").split(",") if a.strip()],
        "section": args.section,
        "written_at": util.utcnow_iso(),
    }
    path = project / "findings" / f"{fid}.md"
    util.atomic_write_text(path, _serialize_front_matter(meta, body))
    return {"finding": path.name, "meta": meta, "path": str(path)}


def cmd_findings_list(args) -> dict:
    project = _project(args)
    out = []
    for f in sorted((project / "findings").glob("FN-*.md")):
        meta, _ = util.parse_front_matter(util.load_text(f))
        out.append(meta)
    return {"count": len(out), "findings": out}


# ================================================================= report

def cmd_report_build(args) -> tuple[dict, int]:
    project = _project(args)
    res = report_builder.build(project, allow_flagged=args.allow_flagged,
                               lang=getattr(args, "lang", None))
    check = res["check"]
    return {"report_md": res["report_md"], "report_html": res["report_html"],
            "lang": res["lang"], "pass": check["pass"],
            "failures": [c for c in check["checks"] if not c["ok"]],
            "checks": check["checks"],
            "metrics": res["metrics"]}, (0 if check["pass"] else 1)


def cmd_report_check(args) -> tuple[dict, int]:
    project = _project(args)
    state = _state(project)
    check = report_builder.check(project, allow_flagged=args.allow_flagged)
    state.setdefault("ran", {})["last_report_check_at"] = util.utcnow_iso()
    _save(project, state)
    return check, (0 if check["pass"] else 1)


# ================================================================= export

def cmd_export(args) -> dict:
    project = _project(args)
    out_dir = Path(args.out) if args.out else project / "exports" / util.today_iso()
    util.ensure_dir(out_dir)
    include_fulltext = bool(getattr(args, "include_fulltext", False))
    ledger = Ledger(project)
    artifacts = set()
    for src in ledger.sources():
        rel = (src.get("fulltext") or {}).get("path")
        if rel:
            artifacts.add(Path(rel).as_posix())
    copied, skipped = [], []
    for pattern in ("report.md", "report.html", "brief.md", "plan.md", "manuscript.md",
                    "manuscript.html", "venue.json", "verify_report.json",
                    "retrospective.json", "evidence.jsonl", "claims.jsonl", "contradictions.jsonl"):
        f = project / pattern
        if f.exists():
            util.atomic_write_text(out_dir / f.name, f.read_text(encoding="utf-8"))
            copied.append(f.name)
    for sub in ("sources", "findings", "manuscript"):
        for f in (project / sub).glob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project).as_posix()
            if not include_fulltext and rel in artifacts:
                skipped.append(rel)
                continue
            util.ensure_dir(out_dir / sub)
            (out_dir / sub / f.name).write_bytes(f.read_bytes())
            copied.append(rel)
    if include_fulltext:
        for f in (project / "sources" / "archive").glob("*"):
            if f.is_file():
                rel = f.relative_to(project).as_posix()
                util.ensure_dir(out_dir / "sources" / "archive")
                (out_dir / rel).write_bytes(f.read_bytes())
                copied.append(rel)
    return {"out": str(out_dir), "files": copied,
            "fulltext_artifacts_excluded": 0 if include_fulltext else len(skipped),
            "skipped": skipped,
            "note": "full-text artifacts are local-only; use --include-fulltext for a private backup"}


# ================================================================== learn

def cmd_learn_status(args) -> dict:
    st = preferences.load()
    caps = maintain.load_capabilities()
    stats = sources_learning.load_stats()
    digests = sorted(p.name for p in paths.runtime_learning_dir().glob("digest-*.md"))
    return {
        "mode": _mode(),
        "home": str(paths.runtime_home()),
        "feedback_entries": len(util.read_jsonl(paths.runtime_learning_dir() / "feedback.jsonl")),
        "proposals_pending": len(proposals.pending()),
        "capabilities": {"total": len(caps),
                         "active": sum(1 for c in caps if c.get("status") == "active")},
        "source_stats_sources": len((stats.get("stats") or {})),
        "disabled_sources": stats.get("disabled_sources") or [],
        "movers": sources_learning.movers(stats, limit=5),
        "preferences": {"asked_total": st.get("asked_total", 0), "pending": len(st.get("pending") or []),
                        "disabled": st.get("disabled", False)},
        "recent_digests": digests[-3:],
    }


def cmd_learn_mode(args) -> dict:
    util.write_json(_settings_path(), {"mode": args.mode, "at": util.utcnow_iso()})
    return {"mode": args.mode}


def cmd_learn_feedback(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    project_slug = None
    try:
        project_slug = _state(_project(args)).get("slug")
    except Exception:
        pass
    rec = feedback_mod.journal(
        args.type, args.label, project=project_slug, detail=args.detail,
        weight=args.weight, source_id=args.source_id, capability_id=args.capability_id)
    return {"feedback": rec}


def cmd_learn_retrospect(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    vr = util.read_json(project / "verify_report.json", {}) or {}
    counters = state.get("counters") or {}
    cxs = ledger.contradictions()

    skipped = bool(args.skip_feedback) or _mode() == "off"
    reason = args.skip_reason or ("learning is off" if _mode() == "off" else "user skipped")
    retro = {
        "slug": state.get("slug"), "at": util.utcnow_iso(),
        "worked": args.worked, "failed": args.failed,
        "budget_used": {"searches": counters.get("searches", 0),
                        "sources_read": counters.get("sources_read", 0),
                        "evidence": counters.get("evidence", 0),
                        "claims": counters.get("claims", 0),
                        "verify_passes": counters.get("verify_passes", 0),
                        "spent_usd": (state.get("budget") or {}).get("spent_usd", 0.0)},
        "metrics": {"citation_precision": vr.get("citation_precision"),
                    "verify_mode": vr.get("mode"),
                    "contradictions": {"total": len(cxs),
                                       "adjudicated": sum(1 for c in cxs if c["status"] == "adjudicated"),
                                       "open": sum(1 for c in cxs if c["status"] == "open")},
                    "phases_completed": sorted(int(k) for k, v in (state.get("phases") or {}).items()
                                               if v.get("completed_at"))},
        "suggestions": args.suggestion,
        "capability_candidate": json.loads(args.capability_json) if args.capability_json else None,
        "feedback_skipped": skipped,
        "feedback_skipped_reason": reason if skipped else None,
    }
    util.write_json(project / "retrospective.json", retro)

    journaled = []
    if not skipped:
        journaled.append(feedback_mod.journal(
            "run_outcome", f"run {state.get('slug')} completed",
            project=state.get("slug"),
            detail=f"precision={vr.get('citation_precision')} mode={vr.get('mode')}")["id"])
        by_source = {}
        srcs = {s["id"]: s for s in ledger.sources()}
        for e in ledger.evidence():
            s = srcs.get(e["source_id"])
            if s:
                by_source.setdefault(s.get("service") or "web", set()).add(
                    util.domain_of(s.get("url", "")) or "general")
        for svc, domains in by_source.items():
            for d in domains:
                sources_learning.record_outcome(svc, d, "evidence")
        for sid in vr.get("fabrication_suspected") or []:
            s = srcs.get(sid)
            if s:
                sources_learning.record_outcome(s.get("service") or "web",
                                                util.domain_of(s.get("url", "")) or "general",
                                                "fabricated")
    steps = state.setdefault("ran", {}).setdefault("steps", [])
    if "retrospect" not in steps:
        steps.append("retrospect")
    _save(project, state)
    return {"retrospective": str(project / "retrospective.json"),
            "feedback_skipped": skipped, "journaled": journaled}


def cmd_learn_pref(args) -> dict:
    action = args.action
    if action == "list":
        st = preferences.load()
        return {"pending": st.get("pending") or [], "answers": st.get("answers") or [],
                "disabled": st.get("disabled", False)}
    if action == "ask":
        guard = _learning_write_guard()
        if guard:
            fail(guard)
        project = _project(args)
        state = _state(project)
        allowed, why = preferences.can_ask(state.get("profile", "standard"),
                                            state.get("preferences_asked", 0))
        if not allowed and not args.force:
            fail(f"preference question not allowed: {why}")
        try:
            a = json.loads(args.a_json)
            b = json.loads(args.b_json)
        except json.JSONDecodeError as exc:
            fail(f"invalid --a-json/--b-json: {exc}")
        rec = preferences.create_question({
            "project": state.get("slug"), "context": args.context, "a": a, "b": b})
        state["preferences_asked"] = state.get("preferences_asked", 0) + 1
        _save(project, state)
        card = _render_template(
            "preference-question.md.j2",
            ctx={"project": state.get("slug"), "why": (" — " + args.context) if args.context else "",
                 "pref_id": rec["id"], "a": a, "b": b, "detail": args.detail or ""})
        card_path = project / "preference-questions" / f"{rec['id']}.md"
        util.atomic_write_text(card_path, card)
        return {"preference_id": rec["id"], "card": str(card_path), "markdown": card,
                "answer_with": f"learn pref answer {rec['id']} --choice A|B"}
    if action == "answer":
        guard = _learning_write_guard()
        if guard:
            fail(guard)
        pref_id = args.pref_id or args.pref_pos
        if not pref_id or not args.choice:
            fail("usage: learn pref answer PREF-0001 --choice A|B")
        rec = preferences.answer(pref_id, args.choice, args.note)
        try:
            feedback_mod.journal("preference", f"{pref_id} → {args.choice}",
                                 detail=args.note)
        except Exception:
            pass
        return {"preference": rec}
    if action == "mark-unanswered":
        pref_id = args.pref_id or args.pref_pos
        if not pref_id:
            fail("usage: learn pref mark-unanswered PREF-0001")
        rec = preferences.mark_unanswered(pref_id)
        return {"preference": rec}
    if action == "enable":
        preferences.enable()
        return {"preferences": "re-enabled"}
    fail(f"unknown pref action '{action}'")


def cmd_learn_proposals(args) -> dict:
    rows = proposals.load_all() if args.all else proposals.pending()
    return {"count": len(rows), "proposals": rows}


def _regression():
    import subprocess

    tests_dir = paths.repo_root() / "tests"
    if not tests_dir.exists():
        return True, ["tests/ not present — regression skipped"]
    env = dict(os.environ, RESEARCH_OS_OFFLINE="1",
               RESEARCH_OS_HOME=os.environ.get("RESEARCH_OS_HOME", "/tmp/deep-research-os-regression"))
    py = sys.executable
    checks = []
    commands = [[py, "-m", "pytest", "-q", "--no-header", str(tests_dir)]]
    evals = paths.repo_root() / "evals" / "run_evals.py"
    if evals.exists():
        commands.append([py, str(evals), "--offline"])
    for cmd in commands:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                               cwd=paths.repo_root(), env=env)
        except Exception as exc:  # noqa: BLE001
            checks.append(f"{cmd[1]}: unavailable ({exc})")
            continue
        if p.returncode != 0:
            tail = (p.stdout or p.stderr or "")[-400:]
            return False, [f"{' '.join(cmd[1:3])} failed rc={p.returncode}", tail]
        checks.append(f"{' '.join(cmd[1:3])}: green")
    return True, checks


def cmd_learn_approve(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    try:
        p = proposals.get(args.proposal_id)
    except KeyError:
        fail(f"proposal {args.proposal_id} not found")
    proposals.decide(args.proposal_id, "approve", by=args.by or "human", note=args.note or "")
    reg = None if args.no_regression else _regression
    applied = proposals.apply(args.proposal_id, regression=reg)
    return {"proposal": applied}


def cmd_learn_reject(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    return {"proposal": proposals.decide(args.proposal_id, "reject",
                                         by=args.by or "human", note=args.note or "")}


def cmd_learn_apply(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    reg = None if args.no_regression else _regression
    return {"proposal": proposals.apply(args.proposal_id, regression=reg)}


def cmd_learn_revert(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    return {"proposal": proposals.revert(args.proposal_id, purge=args.purge)}


def cmd_learn_explain(args) -> dict:
    return proposals.explain(args.item)


def cmd_learn_maintain(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    return maintain.run(create_proposals=not args.no_proposals)


def cmd_learn_scan_upstream(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    return upstream_scan.scan(write_report=True, update_watchlist=args.update_watchlist)


def cmd_learn_digest(args) -> dict:
    guard = _learning_write_guard()
    if guard:
        fail(guard)
    return maintain.run(create_proposals=False)


# ================================================================= doctor

def cmd_doctor(args) -> dict:
    import shutil

    paths.seed_runtime()
    searxng = None
    if not http.is_offline():
        try:
            alive, _code = http.url_alive(os.environ.get("RESEARCH_OS_SEARXNG",
                                                         "http://127.0.0.1:8888"), timeout=3.0)
            searxng = bool(alive)
        except Exception:
            searxng = False
    info = {
        "checked_at": util.utcnow_iso(),
        "python": sys.version.split()[0],
        "offline": http.is_offline(),
        "research_home": str(paths.runtime_home()),
        "vault": str(paths.vault_dir(args.vault)),
        "tools": {
            "uv": shutil.which("uv"),
            "pdftotext": shutil.which("pdftotext"),
            "git": shutil.which("git"),
        },
        "searxng_up": searxng,
        "search_fallback": "duckduckgo-lite (no key needed)",
        "mcp_configs_present": {
            "opencode": (Path.home() / ".config" / "opencode" / "opencode.jsonc").exists(),
            "claude": (Path.home() / ".claude.json").exists(),
            "project_mcp_json": (Path.cwd() / ".mcp.json").exists(),
            "codex": (Path.home() / ".codex" / "config.toml").exists(),
        },
        "paid_upgrade_keys": {
            k: bool(os.environ.get(k)) for k in
            ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
             "SERPAPI_KEY", "TAVILY_API_KEY", "EXA_API_KEY", "BRAVE_API_KEY",
             "SCRAPINGBEE_API_KEY", "FIRECRAWL_API_KEY")
        },
        "optional_local": {
            "playwright_installed": bool(shutil.which("playwright")) or _module("playwright"),
            "camoufox": _module("camoufox"),
        },
        "verdict": None,
    }
    info["paid_tools_available"] = any(info["paid_upgrade_keys"].values())
    info["verdict"] = ("keyless-capable; turbo available" if info["paid_tools_available"]
                       else "keyless mode — full pipeline runs without paid APIs")
    if not args.no_write:
        util.write_json(paths.runtime_home() / "capabilities.json", info)
        info["written_to"] = str(paths.runtime_home() / "capabilities.json")
    return info


def _module(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


# ================================================================ parser

def cmd_fulltext_assess(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    source = ledger.source(args.source_id)
    if source is None:
        fail(f"source {args.source_id} not found")
    check = fulltext_store.verify(project, source)
    ft = source.get("fulltext") or {}
    quality = None
    if ft.get("status") == "abstract-only":
        quality = fulltext.assess_abstract(fulltext_store.read_text(project, source),
                                           title=source.get("title") or "")
    return {"source_id": source["id"], "title": source.get("title"),
            "read_depth": source.get("read_depth"), "fulltext": ft,
            "verify": check, "abstract_quality": quality}


def cmd_fulltext_verify(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    sources = ledger.sources()
    if getattr(args, "source_id", None):
        sources = [s for s in sources if s["id"] == args.source_id]
    results = []
    for source in sources:
        check = fulltext_store.verify(project, source)
        results.append({"source_id": source["id"], "status": (source.get("fulltext") or {}).get("status"),
                        "ok": check["ok"], "problems": check["problems"]})
    return {"ok": all(r["ok"] for r in results), "results": results}


def cmd_fulltext_coverage(args) -> dict:
    project = _project(args)
    ledger = Ledger(project)
    sources = ledger.sources()
    key_ids = {s["id"] for s in sources if s.get("key_study")}
    return fulltext_store.coverage(sources, key_ids=key_ids)


def cmd_fulltext_request(args) -> dict:
    project = _project(args)
    source = Ledger(project).source(args.source_id)
    if source is None:
        fail(f"source {args.source_id} not found")
    return resolver.request_template(source)


def cmd_fulltext_scan_inbox(args) -> dict:
    project = _project(args)
    state = _state(project)
    ledger = Ledger(project)
    inbox = Path(args.inbox).expanduser() if args.inbox else project / "inbox"
    if not inbox.exists():
        return {"inbox": str(inbox), "found": 0, "stored": [], "skipped": [],
                "note": "inbox/ does not exist; create it and copy PDFs/XML there"}
    stored, skipped, failed = [], [], []
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".pdf", ".xml", ".jats", ".html", ".htm", ".txt"):
            continue
        try:
            data = path.read_bytes()
            artifact = fulltext.extract_artifact(data, filename=path.name)
            source = _find_source(ledger, doi=artifact.get("doi"))
            if source is None:
                best = 0.0
                for src in ledger.sources():
                    if src.get("title") and artifact.get("title"):
                        score = util.fuzzy(util.normalize_text(src["title"]),
                                           util.normalize_text(artifact["title"]))
                        if score > best:
                            best, source = score, src
                if best < 0.90:
                    source = None
            if source is None:
                rec = {"title": artifact.get("title") or path.stem,
                       "url": f"local://{path.name}", "doi": artifact.get("doi"),
                       "authors": artifact.get("authors") or [], "type": "journal-article",
                       "abstract": artifact.get("abstract") or None, "extra": {}}
                source = _new_source(ledger, rec, angles=args.angles.split(",") if args.angles else None,
                                     service="inbox")
            validation = fulltext.validate_identity(source, artifact, strict=True)
            if not validation["ok"]:
                skipped.append({"file": path.name, "source_id": source["id"],
                                "reason": "; ".join(validation["reasons"])})
                continue
            if validation.get("abstract_only"):
                skipped.append({"file": path.name, "source_id": source["id"],
                                "reason": "abstract-only; use `read --file … --allow-abstract`"})
                continue
            origin = {"url": str(path), "final_url": str(path), "host": "local",
                      "bytes": len(data)}
            rec = fulltext_store.store_artifact(
                project, ledger, source, data, artifact, origin,
                status="verified", version="unknown", validation=validation)
            rec = ledger.update_source(source["id"], read_at=util.utcnow_iso())
            stored.append({"file": path.name, "source_id": rec["id"],
                           "chars": validation.get("chars")})
        except Exception as exc:  # noqa: BLE001
            failed.append({"file": path.name, "error": util.truncate(f"{type(exc).__name__}: {exc}", 300)})
    if stored:
        _bump(state, "sources_read", len(stored))
        _save(project, state)
    return {"inbox": str(inbox), "stored": stored, "skipped": skipped, "failed": failed}


def cmd_manuscript_scaffold(args) -> dict:
    project = _project(args)
    return manuscript_mod.scaffold(project, force=args.force)


def cmd_manuscript_build(args) -> tuple[dict, int]:
    project = _project(args)
    try:
        result = manuscript_mod.build(project, style=args.style, lang=args.lang)
    except (FileNotFoundError, ValueError) as exc:
        fail(str(exc))
    return result, (0 if result.get("ok") else 1)


def cmd_manuscript_check(args) -> tuple[dict, int]:
    project = _project(args)
    result = manuscript_mod.check(project, style=args.style, lang=args.lang)
    return result, (0 if result.get("ok") else 1)


def cmd_manuscript_show(args) -> dict:
    project = _project(args)
    path = project / "manuscript.md"
    if not path.exists():
        path = manuscript_mod.draft_path(project)
    if not path.exists():
        fail("no manuscript.md or manuscript/draft.md — run `manuscript scaffold`")
    return {"path": str(path), "text": util.load_text(path)}


def cmd_corpus_analyze(args) -> dict:
    project = _project(args)
    try:
        return writing_corpus.build(project, Path(args.dir).expanduser() if args.dir else None)
    except FileNotFoundError as exc:
        fail(str(exc))


def cmd_corpus_show(args) -> dict:
    project = _project(args)
    profile = writing_corpus.load(project)
    if not profile:
        fail("no corpus profile — run `corpus analyze --dir /path/to/papers`")
    return profile


def cmd_venue_init(args) -> dict:
    project = _project(args)
    return venue_profile.write_default(project)


def cmd_venue_check(args) -> dict:
    project = _project(args)
    path = project / "manuscript.md"
    if not path.exists():
        path = manuscript_mod.draft_path(project)
    if not path.exists():
        fail("no manuscript text — run `manuscript build` or scaffold the draft")
    meta, body = manuscript_mod.load_draft(project)
    return venue_profile.check(project, util.load_text(path), abstract=str(meta.get("abstract") or ""),
                               keywords=meta.get("keywords") or [])


def cmd_reporting_check(args) -> dict:
    project = _project(args)
    path = Path(args.file).expanduser() if args.file else project / "manuscript.md"
    if not path.exists():
        path = manuscript_mod.draft_path(project)
    if not path.exists():
        fail("no manuscript text — run `manuscript build` or scaffold the draft")
    text = util.load_text(path)
    guideline = args.guideline or reporting_guidelines.detect(text)
    if not guideline:
        fail("cannot detect a reporting guideline; pass --guideline consort|prisma|strobe|coreq|care|tripod|arrive")
    return reporting_guidelines.check(text, guideline)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="research_ctl", description="deep-research-os agent CLI")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--project", help="project slug (default: newest)")
        sp.add_argument("--vault", help="vault path override")
        sp.add_argument("--human", action="store_true", help="readable output")

    # init
    sp = sub.add_parser("init", help="create a research project")
    sp.add_argument("question")
    sp.add_argument("--title")
    sp.add_argument("--profile", choices=["quick", "standard", "deep", "max"], default="standard")
    sp.add_argument("--cutoff", help="ISO date (evidence cutoff)")
    sp.add_argument("--angles", help="';'-separated sub-questions")
    sp.add_argument("--deliverable")
    sp.add_argument("--domain")
    sp.add_argument("--success", help="';'-separated success criteria")
    sp.add_argument("--maintenance", choices=["ok", "due"], default=None)
    sp.add_argument("--privacy", action="store_true")
    sp.add_argument("--max-spend", type=float, default=None)
    sp.add_argument("--declare-uncapped", action="store_true")
    sp.add_argument("--vault")
    sp.add_argument("--dir", help="exact project directory (user-chosen folder for the outputs)")
    sp.add_argument("--force", action="store_true", help="allow --dir into a non-empty folder")
    sp.add_argument("--deliverable-type",
                    choices=["report", "academic-paper", "academic-manuscript",
                             "decision-framework", "memo", "osint-brief", "dataset"],
                    default="report",
                    help="academic-manuscript adds full-text-first gates; academic-paper keeps report-style analysis gates")
    sp.add_argument("--review-protocol", choices=["none", "prisma"], default=None,
                    help="systematic-review protocol (academic-paper defaults to prisma)")
    sp.add_argument("--key-studies-target", type=int, default=None,
                    help="how many key studies must carry comparison-matrix fields")
    sp.add_argument("--human", action="store_true")
    sp.set_defaults(func=cmd_init)

    # status
    sp = sub.add_parser("status", help="where the run stands")
    common(sp)
    sp.set_defaults(func=cmd_status)

    # gate
    sp = sub.add_parser("gate", help="run a phase gate")
    sp.add_argument("--phase", type=int, required=True, choices=range(0, 10))
    common(sp)
    sp.set_defaults(func=cmd_gate)

    # brief
    sp = sub.add_parser("brief", help="brief.md front-matter")
    bsub = sp.add_subparsers(dest="brief_cmd", required=True)
    s2 = bsub.add_parser("set")
    s2.add_argument("--question"); s2.add_argument("--title")
    s2.add_argument("--profile", choices=["quick", "standard", "deep", "max"])
    s2.add_argument("--cutoff"); s2.add_argument("--deliverable"); s2.add_argument("--domain")
    s2.add_argument("--maintenance", choices=["ok", "due"])
    s2.add_argument("--privacy"); s2.add_argument("--angles"); s2.add_argument("--success")
    s2.add_argument("--deliverable-type",
                    choices=["report", "academic-paper", "academic-manuscript",
                             "decision-framework", "memo", "osint-brief", "dataset"])
    s2.add_argument("--review-protocol", choices=["none", "prisma"])
    s2.add_argument("--key-studies-target", type=int)
    common(s2); s2.set_defaults(func=cmd_brief_set)
    s2 = bsub.add_parser("show"); common(s2); s2.set_defaults(func=cmd_brief_show)

    # plan
    sp = sub.add_parser("plan", help="plan.md sections")
    psub = sp.add_subparsers(dest="plan_cmd", required=True)
    s2 = psub.add_parser("set-section")
    s2.add_argument("--name", required=True)
    s2.add_argument("--text"); s2.add_argument("--file"); s2.add_argument("--stdin", action="store_true")
    common(s2); s2.set_defaults(func=cmd_plan_set_section)
    s2 = psub.add_parser("show"); common(s2); s2.set_defaults(func=cmd_plan_show)

    # search
    sp = sub.add_parser("search", help="route a query across connectors")
    sp.add_argument("query_pos", nargs="?")
    sp.add_argument("--query", dest="query_flag")
    sp.add_argument("--domains", help="comma-separated: academic,news,statistics,economics,filings,tech,entities,web")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--source", help="override router with one connector")
    sp.add_argument("--all-academic", action="store_true",
                    help="query every enabled academic connector (slower, broader)")
    sp.add_argument("--per-source", type=int, help="results requested from each connector (max 100)")
    sp.add_argument("--page", type=int, default=1, help="1-based result page")
    sp.add_argument("--year-from", type=int, help="minimum publication year")
    sp.add_argument("--year-to", type=int, help="maximum publication year")
    sp.add_argument("--oa-only", action="store_true", help="keep open-access records only")
    sp.add_argument("--type", dest="type_filter",
                    help="comma-separated: article,preprint,review,dataset,book,conference,report")
    sp.add_argument("--sort", choices=["relevance", "citations", "date"], default="relevance")
    sp.add_argument("--seed", type=int)
    sp.add_argument("--angle", help="research angle this search serves (logged for PRISMA)")
    sp.add_argument("--notes", help="free-text note stored in the search log")
    common(sp); sp.set_defaults(func=cmd_search)

    # searchlog
    sp = sub.add_parser("searchlog", help="reproducible search journal (SCH-####)")
    lsub = sp.add_subparsers(dest="searchlog_cmd", required=True)
    s2 = lsub.add_parser("add", help="record a manual/engine search")
    s2.add_argument("--query", required=True)
    s2.add_argument("--engine", required=True)
    s2.add_argument("--hits", type=int, required=True, help="total hits seen")
    s2.add_argument("--kept", type=int, default=0, help="hits kept after screening")
    s2.add_argument("--angle")
    s2.add_argument("--notes")
    common(s2); s2.set_defaults(func=cmd_searchlog_add)
    s2 = lsub.add_parser("list", help="summary of all logged searches")
    common(s2); s2.set_defaults(func=cmd_searchlog_list)

    # requirements
    sp = sub.add_parser("requirements", help="deliverable requirement coverage (RQ-##)")
    qsub = sp.add_subparsers(dest="requirements_cmd", required=True)
    s2 = qsub.add_parser("add")
    s2.add_argument("--text", required=True)
    s2.add_argument("--origin", help="where the requirement came from (default: user prompt)")
    s2.add_argument("--id", help="explicit RQ-## id")
    common(s2); s2.set_defaults(func=cmd_requirements_add)
    s2 = qsub.add_parser("map", help="map a requirement to its report section/finding")
    s2.add_argument("--requirement-id", "--requirement", dest="requirement_id", required=True)
    s2.add_argument("--target", required=True,
                    help="report section heading or finding id that fulfils it")
    common(s2); s2.set_defaults(func=cmd_requirements_map)
    s2 = qsub.add_parser("waive", help="waive a requirement with a reason (shown in Limitations)")
    s2.add_argument("--requirement-id", "--requirement", dest="requirement_id", required=True)
    s2.add_argument("--reason", required=True)
    common(s2); s2.set_defaults(func=cmd_requirements_waive)
    s2 = qsub.add_parser("list"); common(s2); s2.set_defaults(func=cmd_requirements_list)

    # project
    sp = sub.add_parser("project", help="project location helpers")
    psub = sp.add_subparsers(dest="project_cmd", required=True)
    s2 = psub.add_parser("where"); common(s2); s2.set_defaults(func=cmd_project_where)
    s2 = psub.add_parser("move", help="move the project folder (e.g. into ~/Research)")
    s2.add_argument("--to", required=True)
    s2.add_argument("--remove-original", action="store_true")
    common(s2); s2.set_defaults(func=cmd_project_move)

    # read
    sp = sub.add_parser("read", help="fetch + extract + snapshot a source")
    sp.add_argument("url", nargs="?")
    sp.add_argument("--source-id")
    sp.add_argument("--doi", help="resolve legal full text for a DOI")
    sp.add_argument("--file", help="read a local PDF/JATS/HTML/text artifact")
    sp.add_argument("--title"); sp.add_argument("--service"); sp.add_argument("--type")
    sp.add_argument("--tier", type=int); sp.add_argument("--angles")
    sp.add_argument("--pdf", action="store_true", help="treat as PDF")
    sp.add_argument("--wayback", action="store_true", help="look up an archive URL")
    sp.add_argument("--metadata-only", dest="metadata_only", action="store_true",
                    help="store abstract/metadata only; no full-text claim")
    sp.add_argument("--require-fulltext", dest="require_fulltext", action="store_true",
                    help="fail unless a verified lawful full text is stored")
    sp.add_argument("--allow-abstract", dest="allow_abstract", action="store_true",
                    help="allow a comprehensive abstract as a documented exception")
    sp.add_argument("--abstract-reason", dest="abstract_reason",
                    help="reason recorded with an abstract-only exception")
    sp.add_argument("--refresh", action="store_true", help="re-resolve even if verified")
    sp.add_argument("--no-preprint", dest="no_preprint", action="store_true",
                    help="do not use preprint servers")
    sp.add_argument("--force", action="store_true",
                    help="skip strict identity rejection for local files")
    common(sp); sp.set_defaults(func=cmd_read)

    # fulltext
    sp = sub.add_parser("fulltext", help="full-text artifacts and coverage")
    fsub = sp.add_subparsers(dest="fulltext_cmd", required=True)
    s2 = fsub.add_parser("assess", help="verify one source's full-text trust chain")
    s2.add_argument("--source-id", "--source", dest="source_id", required=True)
    common(s2); s2.set_defaults(func=cmd_fulltext_assess)
    s2 = fsub.add_parser("verify", help="verify stored artifact/text/snapshot hashes")
    s2.add_argument("--source-id", "--source", dest="source_id")
    common(s2); s2.set_defaults(func=cmd_fulltext_verify)
    s2 = fsub.add_parser("coverage", help="verified/abstract/partial coverage metrics")
    common(s2); s2.set_defaults(func=cmd_fulltext_coverage)
    s2 = fsub.add_parser("request", help="author/institution full-text request template")
    s2.add_argument("--source-id", "--source", dest="source_id", required=True)
    common(s2); s2.set_defaults(func=cmd_fulltext_request)
    s2 = fsub.add_parser("scan-inbox", help="match PDFs/XML in inbox/ to sources")
    s2.add_argument("--inbox"); s2.add_argument("--angles")
    common(s2); s2.set_defaults(func=cmd_fulltext_scan_inbox)

    # manuscript
    sp = sub.add_parser("manuscript", help="academic manuscript scaffold/build/check")
    msub = sp.add_subparsers(dest="manuscript_cmd", required=True)
    s2 = msub.add_parser("scaffold", help="create manuscript/draft.md")
    s2.add_argument("--force", action="store_true")
    common(s2); s2.set_defaults(func=cmd_manuscript_scaffold)
    s2 = msub.add_parser("build", help="render manuscript.md and manuscript.html")
    s2.add_argument("--style", choices=["apa", "vancouver", "ieee"])
    s2.add_argument("--lang", choices=["en", "fa"])
    common(s2); s2.set_defaults(func=cmd_manuscript_build)
    s2 = msub.add_parser("check", help="run manuscript hard gates")
    s2.add_argument("--style", choices=["apa", "vancouver", "ieee"])
    s2.add_argument("--lang", choices=["en", "fa"])
    common(s2); s2.set_defaults(func=cmd_manuscript_check)
    s2 = msub.add_parser("show", help="print manuscript.md or the draft")
    common(s2); s2.set_defaults(func=cmd_manuscript_show)

    # corpus
    sp = sub.add_parser("corpus", help="academic writing corpus profile")
    csub = sp.add_subparsers(dest="corpus_cmd", required=True)
    s2 = csub.add_parser("analyze", help="analyze PDFs/XML/text into corpus/profile.json")
    s2.add_argument("--dir")
    common(s2); s2.set_defaults(func=cmd_corpus_analyze)
    s2 = csub.add_parser("show"); common(s2); s2.set_defaults(func=cmd_corpus_show)

    # venue
    sp = sub.add_parser("venue", help="venue profile (style, limits, checklist)")
    vsub = sp.add_subparsers(dest="venue_cmd", required=True)
    s2 = vsub.add_parser("init", help="write a default venue.json")
    common(s2); s2.set_defaults(func=cmd_venue_init)
    s2 = vsub.add_parser("check", help="check the manuscript against venue.json")
    common(s2); s2.set_defaults(func=cmd_venue_check)

    # reporting
    sp = sub.add_parser("reporting", help="reporting-guideline checklist")
    rsub = sp.add_subparsers(dest="reporting_cmd", required=True)
    s2 = rsub.add_parser("check", help="check CONSORT/PRISMA/STROBE/... items")
    s2.add_argument("--guideline", choices=["consort", "prisma", "strobe", "coreq", "care", "tripod", "arrive"])
    s2.add_argument("--file")
    common(s2); s2.set_defaults(func=cmd_reporting_check)

    # sources
    sp = sub.add_parser("sources", help="source records")
    ssub = sp.add_subparsers(dest="sources_cmd", required=True)
    s2 = ssub.add_parser("update")
    s2.add_argument("--source-id", "--source", dest="source_id", required=True)
    s2.add_argument("--title"); s2.add_argument("--type"); s2.add_argument("--tier", type=int)
    s2.add_argument("--angles"); s2.add_argument("--publisher"); s2.add_argument("--published")
    s2.add_argument("--doi")
    s2.add_argument("--status", choices=["screened", "included", "excluded"],
                    help="screening decision (excluded requires --exclude-reason)")
    s2.add_argument("--exclude-reason", dest="exclude_reason",
                    help="why the source was excluded (required for status excluded)")
    s2.add_argument("--as-of", dest="as_of",
                    help="document/effective date for policy sources (YYYY-MM-DD)")
    s2.add_argument("--depth", dest="read_depth",
                    choices=["abstract", "partial", "full-text"],
                    help="how much of the source was actually read (key studies require full-text)")
    s2.add_argument("--venue"); s2.add_argument("--year", type=int)
    s2.add_argument("--volume"); s2.add_argument("--issue"); s2.add_argument("--pages")
    s2.add_argument("--published-doi", dest="published_doi")
    s2.add_argument("--preprint-doi", dest="preprint_doi")
    common(s2); s2.set_defaults(func=cmd_sources_update)
    s2 = ssub.add_parser("review", help="key-study comparison fields (literature matrix)")
    s2.add_argument("--source-id", "--source", dest="source_id", required=True)
    s2.add_argument("--problem"); s2.add_argument("--framework"); s2.add_argument("--method")
    s2.add_argument("--context"); s2.add_argument("--findings"); s2.add_argument("--limitations")
    s2.add_argument("--relevance", dest="relevance_note")
    s2.add_argument("--key", action="store_true", help="mark as key study for the matrix")
    s2.add_argument("--unkey", action="store_true", help="remove key-study mark")
    common(s2); s2.set_defaults(func=cmd_sources_review)
    s2 = ssub.add_parser("enrich", help="fill bibliographic fields from Crossref (needs DOI)")
    s2.add_argument("--source-id", "--source", dest="source_id")
    s2.add_argument("--all", action="store_true", help="enrich every source that has a DOI")
    s2.add_argument("--offline", action="store_true", help="no-op report (never hits network)")
    common(s2); s2.set_defaults(func=cmd_sources_enrich)

    # evidence
    sp = sub.add_parser("evidence", help="evidence ledger")
    esub = sp.add_subparsers(dest="evidence_cmd", required=True)
    s2 = esub.add_parser("add")
    s2.add_argument("--source-id", "--source", dest="source_id", required=True)
    s2.add_argument("--quote", required=True)
    s2.add_argument("--locator", required=True)
    s2.add_argument("--relevance", choices=RELEVANCE_CHOICES, default="supports")
    s2.add_argument("--angle", default=None)
    s2.add_argument("--tags", default="")
    common(s2); s2.set_defaults(func=cmd_evidence_add)
    s2 = esub.add_parser("list")
    s2.add_argument("--source-id")
    common(s2); s2.set_defaults(func=cmd_evidence_list)

    # claims
    sp = sub.add_parser("claims", help="claims ledger")
    csub = sp.add_subparsers(dest="claims_cmd", required=True)
    s2 = csub.add_parser("add")
    s2.add_argument("--text", required=True)
    s2.add_argument("--type", choices=CLAIM_TYPES, default="statistic")
    s2.add_argument("--kind", choices=["empirical", "normative", "theoretical"],
                    default="empirical",
                    help="normative claims require an official/primary source at verify time")
    s2.add_argument("--tags", default="")
    s2.add_argument("--angles", default="")
    s2.add_argument("--evidence", "--evidence-ids", dest="evidence", default="")
    s2.add_argument("--critical", action="store_true")
    common(s2); s2.set_defaults(func=cmd_claims_add)
    s2 = csub.add_parser("list"); common(s2); s2.set_defaults(func=cmd_claims_list)

    # credibility
    sp = sub.add_parser("credibility", help="scoring")
    rsub = sp.add_subparsers(dest="credibility_cmd", required=True)
    s2 = rsub.add_parser("score")
    s2.add_argument("--force", action="store_true", help="rescore even if already scored")
    common(s2); s2.set_defaults(func=cmd_credibility_score)
    s2 = rsub.add_parser("show")
    s2.add_argument("source_id")
    common(s2); s2.set_defaults(func=cmd_credibility_show)

    # verify
    sp = sub.add_parser("verify", help="citation + claim verification (phase 6)")
    sp.add_argument("--online", action="store_true", help="DOI/title/URL checks (needs network)")
    common(sp); sp.set_defaults(func=cmd_verify)

    # contradictions
    sp = sub.add_parser("contradictions", help="conflict scanner")
    xsub = sp.add_subparsers(dest="contradictions_cmd", required=True)
    s2 = xsub.add_parser("scan"); common(s2); s2.set_defaults(func=cmd_contradictions_scan)
    s2 = xsub.add_parser("list"); s2.add_argument("--open", action="store_true")
    common(s2); s2.set_defaults(func=cmd_contradictions_list)
    s2 = xsub.add_parser("adjudicate")
    s2.add_argument("cx_id")
    s2.add_argument("--resolution", required=True, choices=RESOLUTIONS)
    s2.add_argument("--rationale", required=True)
    s2.add_argument("--by", default="agent")
    common(s2); s2.set_defaults(func=cmd_contradictions_adjudicate)

    # findings
    sp = sub.add_parser("findings", help="finding files")
    fsub = sp.add_subparsers(dest="findings_cmd", required=True)
    s2 = fsub.add_parser("new")
    s2.add_argument("--title", required=True)
    s2.add_argument("--strength", choices=STRENGTHS, default="supported")
    s2.add_argument("--confidence", choices=CONFIDENCES, default="medium")
    s2.add_argument("--claims", required=True, help="comma-separated CL-#### ids")
    s2.add_argument("--kind", choices=["analysis", "model", "scenarios", "sensitivity",
                                       "literature-matrix", "methodology", "conclusion"],
                    default="analysis",
                    help="model/scenarios/sensitivity are required for academic-paper deliverables")
    s2.add_argument("--counterpoints", default="", help="';'-separated")
    s2.add_argument("--gaps", default="", help="';'-separated")
    s2.add_argument("--angles", default="")
    s2.add_argument("--section", choices=["summary", "main", "appendix"], default="main")
    s2.add_argument("--body"); s2.add_argument("--body-file")
    common(s2)
    s2.set_defaults(func=cmd_findings_new)
    s2 = fsub.add_parser("list"); common(s2); s2.set_defaults(func=cmd_findings_list)

    # model
    sp = sub.add_parser("model", help="model.json card and reproducibility checks")
    msub = sp.add_subparsers(dest="model_cmd", required=True)
    s2 = msub.add_parser("check", help="validate equations, inputs and recomputed outputs")
    common(s2); s2.set_defaults(func=cmd_model_check)

    # report
    sp = sub.add_parser("report", help="report build/check")
    rsub2 = sp.add_subparsers(dest="report_cmd", required=True)
    s2 = rsub2.add_parser("build", help="render report.md/report.html and run report gates")
    s2.add_argument("--allow-flagged", action="store_true")
    s2.add_argument("--lang", choices=["en", "fa"],
                    help="report language (default: auto-detect from the brief)")
    common(s2); s2.set_defaults(func=cmd_report_build)
    s2 = rsub2.add_parser("check")
    s2.add_argument("--allow-flagged", action="store_true")
    common(s2); s2.set_defaults(func=cmd_report_check)

    # export
    sp = sub.add_parser("export", help="copy run artifacts (full text excluded by default)")
    sp.add_argument("--out")
    sp.add_argument("--include-fulltext", action="store_true",
                    help="include original full-text artifacts (private backup only)")
    common(sp); sp.set_defaults(func=cmd_export)

    # learn
    sp = sub.add_parser("learn", help="governed learning loop")
    lsub = sp.add_subparsers(dest="learn_cmd", required=True)
    s2 = lsub.add_parser("status"); common(s2); s2.set_defaults(func=cmd_learn_status)
    s2 = lsub.add_parser("mode")
    s2.add_argument("mode", choices=["auto", "advisory", "off"])
    common(s2); s2.set_defaults(func=cmd_learn_mode)
    s2 = lsub.add_parser("feedback")
    s2.add_argument("--type", choices=sorted(feedback_mod.VALID_TYPES), required=True)
    s2.add_argument("--label", required=True)
    s2.add_argument("--detail"); s2.add_argument("--weight", type=float, default=1.0)
    s2.add_argument("--source-id"); s2.add_argument("--capability-id")
    common(s2); s2.set_defaults(func=cmd_learn_feedback)
    s2 = lsub.add_parser("retrospect")
    s2.add_argument("--worked", action="append", default=[])
    s2.add_argument("--failed", action="append", default=[])
    s2.add_argument("--suggestion", action="append", default=[])
    s2.add_argument("--capability-json")
    s2.add_argument("--skip-feedback", action="store_true")
    s2.add_argument("--skip-reason")
    common(s2); s2.set_defaults(func=cmd_learn_retrospect)
    s2 = lsub.add_parser("pref")
    s2.add_argument("action", choices=["list", "ask", "answer", "mark-unanswered", "enable"])
    s2.add_argument("pref_pos", nargs="?")
    s2.add_argument("--pref-id"); s2.add_argument("--choice", choices=["A", "B"])
    s2.add_argument("--note"); s2.add_argument("--context"); s2.add_argument("--detail")
    s2.add_argument("--a-json"); s2.add_argument("--b-json")
    s2.add_argument("--force", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_pref)
    s2 = lsub.add_parser("proposals")
    s2.add_argument("--all", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_proposals)
    s2 = lsub.add_parser("approve")
    s2.add_argument("proposal_id"); s2.add_argument("--note"); s2.add_argument("--by")
    s2.add_argument("--no-regression", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_approve)
    s2 = lsub.add_parser("reject")
    s2.add_argument("proposal_id"); s2.add_argument("--note"); s2.add_argument("--by")
    common(s2); s2.set_defaults(func=cmd_learn_reject)
    s2 = lsub.add_parser("apply")
    s2.add_argument("proposal_id"); s2.add_argument("--no-regression", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_apply)
    s2 = lsub.add_parser("revert")
    s2.add_argument("proposal_id"); s2.add_argument("--purge", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_revert)
    s2 = lsub.add_parser("explain")
    s2.add_argument("item")
    common(s2); s2.set_defaults(func=cmd_learn_explain)
    s2 = lsub.add_parser("maintain")
    s2.add_argument("--no-proposals", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_maintain)
    s2 = lsub.add_parser("scan-upstream")
    s2.add_argument("--update-watchlist", action="store_true")
    common(s2); s2.set_defaults(func=cmd_learn_scan_upstream)
    s2 = lsub.add_parser("digest"); common(s2); s2.set_defaults(func=cmd_learn_digest)

    # doctor
    sp = sub.add_parser("doctor", help="environment capability probe")
    sp.add_argument("--no-write", action="store_true")
    sp.add_argument("--vault")
    sp.add_argument("--human", action="store_true")
    sp.set_defaults(func=cmd_doctor)

    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except http.OfflineError as exc:
        fail(str(exc))
        return
    except FileNotFoundError as exc:
        fail(str(exc))
        return
    except KeyError as exc:
        fail(str(exc))
        return
    except ValueError as exc:
        fail(str(exc))
        return
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"{type(exc).__name__}: {exc}")

    code = 0
    if isinstance(result, tuple):
        result, code = result
    if getattr(args, "human", False) and isinstance(result, dict):
        print(_human(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(code)


if __name__ == "__main__":
    main()
