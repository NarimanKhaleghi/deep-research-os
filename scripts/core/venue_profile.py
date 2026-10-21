"""Journal/venue profile used by manuscript checks and rendering."""

from __future__ import annotations

from pathlib import Path

from core import citation_style, reporting_guidelines
from lib import util

DEFAULTS = {
    "name": "Target venue",
    "style": "apa",
    "language": "en",
    "word_limit": 8000,
    "abstract_limit": 300,
    "title_limit": 20,
    "keyword_min": 3,
    "keyword_max": 8,
    "sections": ["Abstract", "Introduction", "Methods", "Results", "Discussion",
                 "Conclusion", "References"],
    "reporting_guidelines": [],
    "blind_review": True,
    "reference_limit": None,
    "figure_limit": None,
    "table_limit": None,
}


def load(project: Path) -> dict:
    data = util.read_json(Path(project) / "venue.json", {}) or {}
    profile = dict(DEFAULTS)
    profile.update({k: v for k, v in data.items() if v is not None})
    return profile


def write_default(project: Path) -> dict:
    path = Path(project) / "venue.json"
    if path.exists():
        return load(project)
    util.write_json(path, DEFAULTS)
    return dict(DEFAULTS)


def check(project: Path, text: str, *, word_count: int | None = None,
          abstract: str = "", keywords: list[str] | None = None) -> dict:
    profile = load(project)
    errors, warnings = [], []
    if profile.get("style") not in citation_style.STYLES:
        errors.append(f"unknown citation style: {profile.get('style')}")
    wc = word_count if word_count is not None else len(text.split())
    limit = profile.get("word_limit")
    if limit and wc > int(limit):
        errors.append(f"word count {wc} exceeds venue limit {limit}")
    elif limit and wc < int(limit) * 0.55:
        warnings.append(f"word count {wc} is far below venue limit {limit}")
    alimit = profile.get("abstract_limit")
    if alimit and len(abstract.split()) > int(alimit):
        errors.append(f"abstract {len(abstract.split())} words exceeds limit {alimit}")
    kws = keywords or []
    if len(kws) < int(profile.get("keyword_min") or 0):
        errors.append(f"only {len(kws)} keywords; venue requires at least {profile.get('keyword_min')}")
    if profile.get("keyword_max") and len(kws) > int(profile["keyword_max"]):
        errors.append(f"{len(kws)} keywords exceeds venue maximum {profile['keyword_max']}")
    guidelines = profile.get("reporting_guidelines") or []
    if guidelines:
        rg = reporting_guidelines.check_all(text, guidelines)
        if not rg["ok"]:
            for r in rg["results"]:
                if not r["ok"]:
                    errors.append(f"{r.get('name', r['guideline'])} missing: " + ", ".join(r["missing"][:4]))
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "profile": profile, "word_count": wc}
