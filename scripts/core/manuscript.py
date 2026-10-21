"""Academic manuscript scaffold, build, render and hard checks.

The manuscript is authored by the agent/user in ``manuscript/draft.md``; this
module supplies structure, citation rendering, venue formatting and gates. It
never fabricates prose or references.
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import citation_style, fulltext, fulltext_store, reporting_guidelines, venue_profile  # noqa: E402
from core.evidence_store import Ledger  # noqa: E402
from lib import paths, util  # noqa: E402

MARKER_RE = re.compile(r"\[@SRC-\d{4}(?:\s*;\s*@?SRC-\d{4})*\]")
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX|lorem ipsum|placeholder)\b|\[insert", re.I)
REQUIRED_SECTIONS = ("introduction", "methods", "results", "discussion", "conclusion")
SECTION_ALIASES = {
    "مقدمه": "introduction",
    "روش": "methods", "روش‌ها": "methods", "روشها": "methods",
    "مواد و روش‌ها": "methods", "مواد و روشها": "methods",
    "یافته": "results", "یافته‌ها": "results", "یافتهها": "results", "نتایج": "results",
    "بحث": "discussion", "بحث و نتیجه‌گیری": "discussion",
    "نتیجه": "conclusion", "نتیجه‌گیری": "conclusion", "نتیجهگیری": "conclusion",
    "محدودیت": "limitations", "محدودیت‌ها": "limitations", "محدودیتها": "limitations",
    "اخلاق": "ethics", "اخلاق و رضایت": "ethics",
    "حمایت مالی": "funding", "منابع مالی": "funding",
    "تضاد منافع": "conflicts", "تعارض منافع": "conflicts",
    "دسترسی به داده": "data availability", "دسترسی داده": "data availability",
}


def draft_path(project: Path) -> Path:
    return Path(project) / "manuscript" / "draft.md"


def load_draft(project: Path) -> tuple[dict, str]:
    path = draft_path(project)
    if not path.exists():
        return {}, ""
    return util.parse_front_matter(util.load_text(path))


def scaffold(project: Path, *, force: bool = False) -> dict:
    project = Path(project)
    path = draft_path(project)
    if path.exists() and not force:
        return {"path": str(path), "created": False}
    state = paths.load_state(project)
    brief, _ = util.parse_front_matter(util.load_text(project / "brief.md"))
    title = str(brief.get("title") or state.get("title") or "Untitled manuscript")
    meta = {
        "title": title,
        "authors": ["Author One"],
        "affiliations": ["Institution"],
        "keywords": ["keyword one", "keyword two", "keyword three"],
        "abstract": "TODO: structured abstract (background, objective, methods, results, conclusions).",
        "funding": "TODO",
        "conflicts": "The authors declare no competing interests.",
        "data_availability": "TODO: repository/DOI or access statement.",
        "ethics": "TODO: approval/consent statement (or 'not applicable').",
        "registration": "",
        "language": state.get("report_language") or "en",
        "reporting_guidelines": [],
    }
    body = "\n\n".join([
        "## Introduction",
        "TODO: establish the problem, the gap, and the contribution.",
        "## Methods",
        "TODO: design, setting, participants/materials, measures, and analysis.",
        "## Results",
        "TODO: report findings with effect sizes, uncertainty, and citations.",
        "## Discussion",
        "TODO: interpret against prior work, state limitations, and implications.",
        "## Conclusion",
        "TODO: one-paragraph conclusion that does not overclaim.",
        "## Limitations",
        "TODO: design, measurement, sampling, and generalisability limits.",
        "## Ethics and consent",
        "TODO",
        "## Funding",
        "TODO",
        "## Conflicts of interest",
        "The authors declare no competing interests.",
        "## Data availability",
        "TODO",
    ])
    util.atomic_write_text(path, _front_matter(meta) + body + "\n")
    return {"path": str(path), "created": True, "next": "edit manuscript/draft.md, then `manuscript build`"}


def _front_matter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {json_quote(str(item))}")
        elif value is None or value == "":
            lines.append(f"{key}: null")
        else:
            lines.append(f"{key}: {json_quote(str(value))}")
    lines.append("---\n")
    return "\n".join(lines) + "\n"


def md_to_html(text: str) -> str:
    """Small, dependency-free Markdown subset for print-ready HTML."""
    out: list[str] = []
    in_ul = False
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            if in_ul:
                out.append("</ul>")
                in_ul = False
            continue
        if line.startswith("### "):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.lstrip().startswith(("- ", "* ")):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
        elif line.startswith("> "):
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<p>{_inline(line)}</p>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def _inline(text: str) -> str:
    value = html.escape(text)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    return value


def json_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _section(body: str, name: str) -> str:
    m = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def _sections(body: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"^##\s+(.+?)\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S):
        key = re.sub(r"\s+", " ", m.group(1).strip().lower())
        key = re.sub(r"^[\d۰-۹]+[.)\s-]*", "", key)
        out[SECTION_ALIASES.get(key, key)] = m.group(2).strip()
    return out


def _cited_ids(text: str) -> list[str]:
    ids: list[str] = []
    for m in MARKER_RE.finditer(text):
        for sid in re.findall(r"SRC-\d{4}", m.group(0)):
            if sid not in ids:
                ids.append(sid)
    return ids


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 30]


def build(project: Path, *, style: str | None = None, lang: str | None = None) -> dict:
    project = Path(project)
    state = paths.load_state(project)
    meta, body = load_draft(project)
    if not body:
        raise FileNotFoundError("manuscript/draft.md missing — run `manuscript scaffold` and write it")
    venue = venue_profile.load(project)
    style = style or venue.get("style") or "apa"
    lang = lang or meta.get("language") or venue.get("language") or "en"
    ledger = Ledger(project)
    sources = ledger.sources()
    cited = _cited_ids(body)
    by_id = {s["id"]: s for s in sources}
    unknown = [sid for sid in cited if sid not in by_id]
    if unknown:
        raise ValueError("unknown citation ids: " + ", ".join(unknown))
    ordered = [by_id[sid] for sid in cited]
    rendered_body = citation_style.render_citations(body, sources, style)
    abstract = str(meta.get("abstract") or "").strip()
    keywords = meta.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    authors = meta.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(";") if a.strip()]
    refs = citation_style.bibliography(ordered, style)
    ctx = {
        "title": meta.get("title") or state.get("title") or "Untitled manuscript",
        "authors": authors, "affiliations": meta.get("affiliations") or [],
        "abstract": abstract, "keywords": keywords, "body": rendered_body,
        "bibliography": refs, "style": style, "lang": lang,
        "direction": "rtl" if lang == "fa" else "ltr",
        "venue": venue, "funding": meta.get("funding") or "",
        "conflicts": meta.get("conflicts") or "",
        "data_availability": meta.get("data_availability") or "",
        "ethics": meta.get("ethics") or "", "registration": meta.get("registration") or "",
    }
    ctx["body_html"] = md_to_html(rendered_body)
    ctx["manuscript_css"] = (paths.repo_root() / "templates" / "assets" / "manuscript.css").read_text(encoding="utf-8")
    ctx["abstract_html"] = md_to_html(abstract)
    ctx["authors_text"] = ", ".join(str(a) for a in authors)
    ctx["affiliations_text"] = "; ".join(str(a) for a in (meta.get("affiliations") or []))
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(paths.repo_root() / "templates")),
                      autoescape=False, trim_blocks=True, lstrip_blocks=True)
    md = env.get_template("manuscript.md.j2").render(**ctx)
    html_env = Environment(loader=FileSystemLoader(str(paths.repo_root() / "templates")),
                           autoescape=True, trim_blocks=True, lstrip_blocks=True)
    html = html_env.get_template("manuscript.html.j2").render(**ctx)
    util.atomic_write_text(project / "manuscript.md", md)
    util.atomic_write_text(project / "manuscript.html", html)
    result = check(project, text=body, meta=meta, style=style, lang=lang)
    result.update({"manuscript_md": str(project / "manuscript.md"),
                   "manuscript_html": str(project / "manuscript.html"),
                   "style": style, "lang": lang, "cited_sources": cited})
    state.setdefault("ran", {})["last_manuscript_check_at"] = util.utcnow_iso()
    paths.save_state(project, state)
    return result


def check(project: Path, *, text: str | None = None, meta: dict | None = None,
          style: str | None = None, lang: str | None = None) -> dict:
    project = Path(project)
    state = paths.load_state(project)
    ledger = Ledger(project)
    sources = ledger.sources()
    by_id = {s["id"]: s for s in sources}
    if meta is None or text is None:
        meta, body = load_draft(project)
        venue = venue_profile.load(project)
        style = style or venue.get("style") or "apa"
        lang = lang or meta.get("language") or "en"
        if text is None:
            text = body
    else:
        body = text
    venue = venue_profile.load(project)
    style = style or venue.get("style") or "apa"
    sections = _sections(body)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "", hard: bool = True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "hard": hard})

    if not body.strip():
        add("draft_exists", False, "manuscript/draft.md is missing or empty — run `manuscript scaffold`")
        return {"ok": False, "checks": checks, "metrics": {}}

    add("draft_exists", True, "ok")
    missing = [s for s in REQUIRED_SECTIONS if s not in sections or len(sections[s].split()) < 40]
    add("imrad_sections", not missing, "missing/thin: " + ", ".join(missing) if missing else "ok")

    abstract = str(meta.get("abstract") or "").strip()
    aq = fulltext.assess_abstract(abstract, title=str(meta.get("title") or ""))
    add("abstract_comprehensive", aq["verdict"] == "comprehensive",
        f"verdict={aq['verdict']}, words={aq['words']}, score={aq['score']}")

    keywords = meta.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    add("keywords", 3 <= len(keywords) <= 8, f"{len(keywords)} keyword(s)")

    title = str(meta.get("title") or "")
    add("title_length", 4 <= len(title.split()) <= 30, f"{len(title.split())} words")

    missing_meta = [k for k in ("authors", "affiliations", "funding", "conflicts",
                                "data_availability", "ethics") if not meta.get(k)]
    add("metadata_complete", not missing_meta, ", ".join(missing_meta) or "ok")

    cited = _cited_ids(body)
    unknown = [sid for sid in cited if sid not in by_id]
    add("citations_resolve", not unknown, ", ".join(unknown) or "ok")
    add("citations_present", bool(cited), f"{len(cited)} cited source(s)")

    included = [s for s in sources if s.get("status") != "excluded"]
    uncited = [s["id"] for s in included if s["id"] not in cited]
    add("included_sources_cited", len(uncited) <= max(2, len(included) // 5),
        ", ".join(uncited[:8]) or "ok")

    key_uncited = [s["id"] for s in included if s.get("key_study") and s["id"] not in cited]
    add("key_studies_cited", not key_uncited, ", ".join(key_uncited) or "ok")

    numeric_uncited = []
    for para in _paragraphs(body):
        if re.search(r"\d+(?:\.\d+)?\s?%|\bp\s*[<=>]|confidence interval|\bn\s*=\s*\d+", para, re.I):
            if not MARKER_RE.search(para):
                numeric_uncited.append(util.truncate(para, 90))
    add("numeric_claims_cited", not numeric_uncited,
        " | ".join(numeric_uncited[:3]) or "ok")

    cov = fulltext_store.coverage(included, key_ids={s["id"] for s in included if s.get("key_study")})
    add("fulltext_coverage",
        cov["verified_ratio"] >= 0.80 and cov["abstract_ratio"] <= 0.20,
        f"verified {cov['verified_ratio']:.0%}, abstract {cov['abstract_ratio']:.0%} of {cov['total']}")
    add("fulltext_key_studies", not cov["key_gaps"], ", ".join(cov["key_gaps"]) or "ok")

    critical_bad = []
    for claim in ledger.claims():
        if not claim.get("critical"):
            continue
        for src in ledger.evidence_sources_for_claim(claim):
            if (src.get("fulltext") or {}).get("status") != "verified":
                critical_bad.append(f"{claim['id']}→{src['id']}")
    add("fulltext_critical_claims", not critical_bad, ", ".join(critical_bad[:5]) or "ok")

    integrity_bad = []
    for src in included:
        if (src.get("fulltext") or {}).get("status") == "verified":
            vr = fulltext_store.verify(project, src)
            if not vr["ok"]:
                integrity_bad.append(f"{src['id']}({'; '.join(vr['problems'])})")
    add("fulltext_integrity", not integrity_bad, ", ".join(integrity_bad[:5]) or "ok")

    placeholders = sorted(set(m.group(0) for m in PLACEHOLDER_RE.finditer(body)))
    add("no_placeholders", not placeholders, ", ".join(placeholders) or "ok")

    guidelines = meta.get("reporting_guidelines") or venue.get("reporting_guidelines") or []
    if isinstance(guidelines, str):
        guidelines = [g.strip() for g in guidelines.split(",") if g.strip()]
    if guidelines:
        rg = reporting_guidelines.check_all(body + "\n" + abstract, guidelines)
        missing_items = [f"{r['guideline']}:{','.join(r['missing'][:4])}" for r in rg["results"] if not r["ok"]]
        add("reporting_guideline", rg["ok"], "; ".join(missing_items) or "ok")
    else:
        add("reporting_guideline", True, "not declared", hard=False)

    vc = venue_profile.check(project, body, abstract=abstract, keywords=keywords)
    add("venue_profile", vc["ok"], "; ".join(vc["errors"]) or "ok")
    for w in vc.get("warnings") or []:
        add("venue_warning", True, w, hard=False)

    hard = [c for c in checks if c["hard"] and not c["ok"]]
    return {"ok": not hard, "checks": checks,
            "metrics": {"words": len(body.split()), "abstract_words": len(abstract.split()),
                        "cited_sources": len(cited), "included_sources": len(included),
                        "fulltext": cov},
            "style": style, "lang": lang}
