"""Analyze a user-supplied academic writing corpus into an advisory style profile.

The corpus is never copied into outputs and never used to imitate authors
verbatim. It only informs structural and rhetorical choices.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import fulltext  # noqa: E402
from lib import util  # noqa: E402

HEDGES = {"may", "might", "could", "suggest", "suggests", "likely", "possibly",
          "appears", "seems", "potential", "potentially", "arguably", "perhaps",
          "شاید", "ممکن", "احتمالا", "به نظر"}
BOOSTERS = {"clearly", "demonstrates", "proves", "undoubtedly", "significantly",
            "strongly", "definitely", "مطمئنا", "قطعا", "به‌وضوح"}
FIRST_PERSON = {"we", "our", "us", "i", "my", "ما", "مال ما"}
TRANSITIONS = {"however", "therefore", "moreover", "furthermore", "nevertheless",
               "consequently", "in contrast", "by contrast", "thus", "hence",
               "با این حال", "بنابراین", "علاوه بر این", "در مقابل"}
GUIDELINES = {"consort": "CONSORT", "prisma": "PRISMA", "strobe": "STROBE",
              "coreq": "COREQ", "care": "CARE", "tripod": "TRIPOD", "arrive": "ARRIVE"}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n{2,}", text) if len(s.strip()) > 20]


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06ff]+(?:[-’'][\w\u0600-\u06ff]+)?", text.lower())


def _is_fa(text: str) -> bool:
    fa = len(re.findall(r"[\u0600-\u06ff]", text))
    return fa > max(20, len(text) * 0.05)


def _classify(text: str, name: str) -> str:
    low = (name + " " + text[:8000]).lower()
    if any(x in low for x in ("systematic review", "meta-analysis", "prisma", "مرور نظام")):
        return "review"
    if any(x in low for x in ("randomized", "randomised", "trial", "کارآزمایی")):
        return "empirical"
    if any(x in low for x in ("case study", "case report", "مطالعه موردی")):
        return "case-study"
    if any(x in low for x in ("policy analysis", "regulatory", "سیاست")):
        return "policy"
    if any(x in low for x in ("theoretical", "conceptual framework", "نظری")):
        return "theoretical"
    if any(x in low for x in ("method", "protocol", "روش")):
        return "methods"
    return "empirical"


def analyze_text(text: str, *, name: str = "") -> dict:
    words = _words(text)
    sents = _sentences(text)
    n = max(1, len(words))
    low = text.lower()
    sections = fulltext.section_presence(text)
    hedges = sum(1 for w in words if w in HEDGES)
    boosters = sum(1 for w in words if w in BOOSTERS)
    first = sum(1 for w in words if w in FIRST_PERSON)
    transitions = sum(1 for t in TRANSITIONS if t in low)
    citations = len(re.findall(r"\([A-Z][^()]{0,80}(?:19|20)\d{2}[a-z]?\)", text))
    doi_refs = len(re.findall(r"10\.\d{4,9}/", text))
    guideline_hits = [label for key, label in GUIDELINES.items()
                      if re.search(rf"\b{key}\b", low)]
    return {
        "name": name, "genre": _classify(text, name), "language": "fa" if _is_fa(text) else "en",
        "words": len(words), "sentences": len(sents),
        "avg_sentence_words": round(len(words) / max(1, len(sents)), 1),
        "sections": sections,
        "hedges_per_1000": round(hedges * 1000 / n, 1),
        "boosters_per_1000": round(boosters * 1000 / n, 1),
        "first_person_per_1000": round(first * 1000 / n, 1),
        "transitions": transitions,
        "citations": citations, "doi_refs": doi_refs,
        "citation_density_per_1000": round((citations + doi_refs) * 1000 / n, 1),
        "reporting_guidelines": guideline_hits,
        "has_imrad": all(sections.get(k) for k in ("introduction", "methods", "results", "discussion")),
    }


def analyze_files(paths: Iterable[Path]) -> dict:
    docs = []
    errors = []
    for path in paths:
        try:
            data = path.read_bytes()
            artifact = fulltext.extract_artifact(data, filename=path.name)
            docs.append(analyze_text(artifact.get("text") or "", name=path.name))
        except Exception as exc:  # noqa: BLE001
            errors.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
    if not docs:
        return {"documents": 0, "docs": [], "errors": errors, "guidance": []}
    n = len(docs)
    genres: dict[str, int] = {}
    langs: dict[str, int] = {}
    for d in docs:
        genres[d["genre"]] = genres.get(d["genre"], 0) + 1
        langs[d["language"]] = langs.get(d["language"], 0) + 1
    section_rates = {k: round(sum(1 for d in docs if d["sections"].get(k)) / n, 2)
                     for k in ("introduction", "methods", "results", "discussion",
                               "conclusion", "references")}
    guidance = []
    if section_rates["methods"] >= 0.8:
        guidance.append("Use an explicit Methods section with design, sample, measures, and analysis.")
    if section_rates["results"] >= 0.8:
        guidance.append("Report Results separately from interpretation; put effect sizes and uncertainty first.")
    if sum(d["hedges_per_1000"] for d in docs) / n >= 8:
        guidance.append("The corpus hedges heavily; keep claims calibrated and reserve boosters for strong evidence.")
    if sum(d["first_person_per_1000"] for d in docs) / n >= 8:
        guidance.append("First-person plural is common; use it for methodological choices, not for unsupported claims.")
    if sum(d["citation_density_per_1000"] for d in docs) / n >= 15:
        guidance.append("Citation density is high; support each empirical claim and synthesize rather than list.")
    return {
        "documents": n, "genres": genres, "languages": langs,
        "section_rates": section_rates,
        "avg_words": round(sum(d["words"] for d in docs) / n, 1),
        "avg_sentence_words": round(sum(d["avg_sentence_words"] for d in docs) / n, 1),
        "avg_hedges_per_1000": round(sum(d["hedges_per_1000"] for d in docs) / n, 1),
        "avg_citation_density_per_1000": round(sum(d["citation_density_per_1000"] for d in docs) / n, 1),
        "reporting_guidelines": sorted({g for d in docs for g in d["reporting_guidelines"]}),
        "docs": docs, "errors": errors, "guidance": guidance,
    }


def build(project: Path, corpus_dir: Path | None = None) -> dict:
    project = Path(project)
    corpus_dir = Path(corpus_dir) if corpus_dir else project / "corpus"
    if not corpus_dir.exists():
        raise FileNotFoundError(f"corpus directory not found: {corpus_dir}")
    files = sorted(p for p in corpus_dir.rglob("*")
                   if p.is_file() and p.suffix.lower() in (".pdf", ".xml", ".jats", ".html", ".htm", ".txt", ".md"))
    profile = analyze_files(files)
    profile["corpus_dir"] = str(corpus_dir)
    profile["generated_at"] = util.utcnow_iso()
    util.write_json(project / "corpus" / "profile.json", profile)
    lines = ["# Writing corpus profile", "",
             f"- Documents: {profile['documents']}",
             f"- Genres: {profile.get('genres')}",
             f"- Languages: {profile.get('languages')}",
             f"- Average words: {profile.get('avg_words')}",
             f"- Average sentence length: {profile.get('avg_sentence_words')}",
             f"- Section presence: {profile.get('section_rates')}",
             "", "## Guidance", ""]
    lines += [f"- {g}" for g in profile.get("guidance") or ["No strong corpus pattern detected."]]
    if profile.get("errors"):
        lines += ["", "## Extraction errors", ""]
        lines += [f"- {e['file']}: {e['error']}" for e in profile["errors"]]
    util.atomic_write_text(project / "corpus" / "README.md", "\n".join(lines) + "\n")
    return profile


def load(project: Path) -> dict:
    return util.read_json(Path(project) / "corpus" / "profile.json", {}) or {}
