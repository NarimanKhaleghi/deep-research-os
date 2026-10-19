"""Bibliographic metadata — Crossref enrichment + APA 7 reference rendering.

Two jobs:
1. ``enrich_source`` pulls canonical metadata (authors, venue, year, volume,
   pages, published DOI) from Crossref so the bibliography is auditable instead
   of "mdpi.com (n.d.)".
2. ``apa_reference`` renders APA-7-style entries and reports missing required
   fields, so ``report build`` can hard-gate bibliography completeness for
   academic deliverables (preprints vs published versions are flagged, not
   silently mixed).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core.evidence_store import Ledger  # noqa: E402
from lib import http, util  # noqa: E402

PREPRINT_DOI_RE = re.compile(r"10\.2139/|10\.48550/|10\.31224/|10\.1101/")
CROSSREF_WORK = "https://api.crossref.org/works/{doi}"


# ------------------------------------------------------------------ enrich

def enrich_source(project: Path, source_id: str, online: bool = True) -> dict:
    """Fill bibliographic fields from Crossref. Returns the updated record.

    Offline (or no DOI / unreachable API): a no-op with a ``reason`` — never a
    failure, so pipelines keep moving and the gap is later reported as a
    bibliography warning.
    """
    ledger = Ledger(project)
    rec = ledger.source(source_id)
    if rec is None:
        raise KeyError(f"source {source_id} not found")
    doi = (rec.get("doi") or "").strip()
    if not doi:
        return {"source_id": source_id, "enriched": False, "reason": "no DOI on record"}
    if not online or http.is_offline():
        return {"source_id": source_id, "enriched": False, "reason": "offline mode"}

    try:
        data = http.get_json(CROSSREF_WORK.format(doi=doi),
                             params={"mailto": os.environ.get("RESEARCH_OS_MAILTO", "")},
                             mailto=os.environ.get("RESEARCH_OS_MAILTO") or None)
        msg = (data or {}).get("message") or {}
    except Exception as exc:  # noqa: BLE001
        return {"source_id": source_id, "enriched": False,
                "reason": f"crossref unreachable: {type(exc).__name__}"}

    fields: dict = {}
    authors = []
    for a in msg.get("author") or []:
        family, given = (a.get("family") or "").strip(), (a.get("given") or "").strip()
        if family or given:
            authors.append({"family": family, "given": given})
    if authors and (not rec.get("authors") or len(rec.get("authors") or []) <= 1):
        fields["authors"] = authors

    if not rec.get("title"):
        titles = msg.get("title") or []
        if titles:
            fields["title"] = str(titles[0]).strip()

    container = (msg.get("container-title") or [])
    if container and not rec.get("venue"):
        fields["venue"] = str(container[0]).strip()

    for src_key, dst_key in (("volume", "volume"), ("issue", "issue")):
        if msg.get(src_key) and not rec.get(dst_key):
            fields[dst_key] = str(msg[src_key])
    if msg.get("page") and not rec.get("pages"):
        fields["pages"] = str(msg["page"])

    year = _issued_year(msg)
    if year and not rec.get("year"):
        fields["year"] = year
    if not rec.get("published") and year:
        fields["published"] = f"{year}-01-01"

    if not rec.get("published_doi"):
        fields["published_doi"] = doi
    if PREPRINT_DOI_RE.search(doi) and not rec.get("preprint_doi"):
        fields["preprint_doi"] = doi

    if fields:
        ledger.update_source(source_id, **fields)
    return {"source_id": source_id, "enriched": bool(fields),
            "updated_fields": sorted(fields), "crossref_type": msg.get("type")}


def _issued_year(msg: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = ((msg.get(key) or {}).get("date-parts") or [[]])[0]
        if parts and parts[0]:
            try:
                return int(parts[0])
            except (TypeError, ValueError):
                continue
    return None


# ------------------------------------------------------------------ APA 7

_LATIN_RE = re.compile(r"^[A-Za-z\s.\-']+$")


def _fmt_person(name: str) -> str:
    """'David J. Teece' -> 'Teece, D. J.' (latin names only)."""
    name = name.strip()
    if not name or not _LATIN_RE.match(name):
        return name  # Persian / CJK / organizational names stay as-is
    parts = [p for p in re.split(r"\s+", name) if p]
    if len(parts) == 1:
        return parts[0]
    family = parts[-1]
    initials = " ".join(f"{p[0].upper()}." for p in parts[:-1] if p and p[0].isalpha())
    return f"{family}, {initials}".strip().rstrip(",")


def authors_apa(source: dict, max_authors: int = 20) -> str:
    authors = source.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    names: list[str] = []
    for a in authors:
        if isinstance(a, dict):
            family, given = (a.get("family") or "").strip(), (a.get("given") or "").strip()
            if family:
                initials = " ".join(f"{g[0].upper()}." for g in re.split(r"[\s.]+", given) if g)
                names.append(f"{family}, {initials}".strip().rstrip(","))
            elif given:
                names.append(given)
        else:
            names.append(_fmt_person(str(a)))
    names = [n for n in names if n]
    if not names:
        return source.get("publisher") or util.domain_of(source.get("url", "")) or "Unknown"
    if len(names) > max_authors:
        return ", ".join(names[:max_authors - 1]) + ", … " + names[-1]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, & {names[1]}"
    return ", ".join(names[:-1]) + f", & {names[-1]}"


def source_year(source: dict) -> str:
    if source.get("year"):
        return str(source["year"])
    published = str(source.get("published") or "")
    m = re.match(r"(\d{4})", published)
    return m.group(1) if m else "n.d."


def version_note(source: dict) -> str:
    """Flag preprint/published DOI spread so benchmark citations stay honest."""
    doi = (source.get("doi") or "").lower()
    published_doi = (source.get("published_doi") or "").lower()
    preprint_doi = (source.get("preprint_doi") or "").lower()
    url = (source.get("url") or "").lower()
    notes = []
    if published_doi and preprint_doi and published_doi != preprint_doi:
        notes.append(f"version: preprint {preprint_doi} · published {published_doi}")
    elif doi and published_doi and doi != published_doi:
        notes.append(f"version: cited DOI {doi} · published {published_doi}")
    if doi and url and "doi.org/" in url and url.split("doi.org/")[-1].strip() != doi \
            and not notes:
        notes.append(f"URL points to {url.split('doi.org/')[-1].strip()} while record DOI is {doi}")
    return "; ".join(notes)


def missing_bib_fields(source: dict, strict: bool) -> list[str]:
    """Fields missing for an auditable bibliography entry.

    Lenient (default): a citation needs an identifiable author/publisher. APA
    permits "n.d." for undated web pages, so year is only required in strict
    (academic) mode.
    """
    missing = []
    if not source.get("title"):
        missing.append("title")
    if not (source.get("authors") or source.get("publisher")):
        missing.append("authors/publisher")
    if not (source.get("venue") or source.get("publisher") or source.get("url")):
        missing.append("venue")
    if strict:
        if source_year(source) == "n.d.":
            missing.append("year")
        stype = source.get("type") or ""
        if stype in ("journal-article", "conference-paper", "preprint") and not source.get("doi"):
            missing.append("DOI")
        if stype == "journal-article" and not source.get("venue"):
            missing.append("journal venue")
    return missing


def apa_reference(source: dict) -> dict:
    """Render the pieces the template needs, with honest fallbacks."""
    year = source_year(source)
    title = source.get("title") or "Untitled"
    venue = source.get("venue") or ""
    parts = []
    if venue:
        vol = source.get("volume") or ""
        issue = f"({source['issue']})" if source.get("issue") else ""
        pages = f", {source['pages']}" if source.get("pages") else ""
        parts.append(f"*{venue}*{f', {vol}{issue}{pages}' if (vol or issue or pages) else ''}.")
    elif source.get("publisher"):
        parts.append(f"{source['publisher']}.")
    doi = (source.get("published_doi") or source.get("doi") or "").strip()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
    flags = []
    if PREPRINT_DOI_RE.search(doi) or source.get("preprint_doi"):
        flags.append("preprint")
    if (source.get("retraction") or {}).get("status") == "retracted":
        flags.append("retracted")
    url = str(source.get("url") or "").strip()
    if doi and url:
        doi_link = "https://doi.org/" + doi
        if url.rstrip("/").lower() == doi_link.rstrip("/").lower():
            url = ""
    return {
        "authors": authors_apa(source),
        "year": year,
        "title": title,
        "venue_parts": " ".join(parts),
        "doi": doi,
        "url": url,
        "accessed": str(source.get("accessed_at") or "")[:10],
        "version_note": version_note(source),
        "flags": ", ".join(flags),
        "missing": missing_bib_fields(source, strict=False),
    }
