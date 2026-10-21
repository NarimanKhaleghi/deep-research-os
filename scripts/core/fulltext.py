"""Full-text artifacts — detection, extraction, identity checks and abstract QA.

The module is deliberately format-aware but dependency-light: PDFs go through the
existing PyMuPDF/pdftotext/pypdf ladder; JATS XML is parsed with defusedxml when
available; HTML is only ever a ``partial`` source.
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import extract as extract_mod  # noqa: E402
from lib import util  # noqa: E402

PDF_MAGIC = b"%PDF"
XML_HINTS = ("<article", "<jats", "<?xml", "<!doctype article")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)
ABSTRACT_HEADING_RE = re.compile(r"^\s*(abstract|summary|چکیده)\s*:?\s*$", re.I | re.M)
SECTION_WORDS = {
    "introduction": ("introduction", "background", "مقدمه"),
    "methods": ("method", "methods", "methodology", "materials and methods", "روش"),
    "results": ("result", "results", "findings", "یافته"),
    "discussion": ("discussion", "interpretation", "بحث"),
    "conclusion": ("conclusion", "conclusions", "نتیجه"),
    "references": ("references", "bibliography", "منابع"),
}
ABSTRACT_MARKERS = {
    "objective": ("objective", "aim", "purpose", "background", "هدف", "زمینه"),
    "methods": ("method", "methods", "design", "participants", "sample", "روش", "نمونه"),
    "results": ("result", "results", "findings", "we found", "یافته", "نتایج"),
    "conclusions": ("conclusion", "conclusions", "we conclude", "نتیجه"),
    "numbers": ("%", "percent", "p =", "p<", "p >", "ci ", "confidence interval",
                "n =", "n=", " participants", " patients", "درصد"),
}


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = str(value).strip()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
    m = DOI_RE.search(doi)
    return m.group(0).rstrip(".,;)]}").lower() if m else None


def detect_format(data: bytes, filename: str | None = None,
                  content_type: str | None = None) -> str:
    head = (data or b"")[:4096].lstrip()
    suffix = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    if head.startswith(PDF_MAGIC) or suffix == ".pdf" or "pdf" in ctype:
        return "pdf"
    if suffix in (".xml", ".jats") or "xml" in ctype or any(h in head[:512].lower() for h in XML_HINTS):
        return "jats"
    if suffix in (".html", ".htm") or "html" in ctype:
        return "html"
    if suffix in (".txt", ".md") or ctype.startswith("text/"):
        return "text"
    return "unknown"


def _safe_xml_root(data: bytes):
    try:
        from defusedxml import ElementTree as SafeET  # type: ignore

        return SafeET.fromstring(data)
    except ImportError:
        import xml.etree.ElementTree as ET

        return ET.fromstring(data)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _xml_text(el) -> str:
    return " ".join("".join(el.itertext()).split())


def _find_first(root, names: set[str]):
    for el in root.iter():
        if _local(el.tag) in names:
            return el
    return None


def _find_all(root, names: set[str]):
    return [el for el in root.iter() if _local(el.tag) in names]


def extract_jats(data: bytes) -> dict:
    """Extract metadata and body text from a JATS XML document."""
    root = _safe_xml_root(data)
    meta = _find_first(root, {"article-meta"})
    ctx = meta if meta is not None else root
    journal = _find_first(root, {"journal-meta", "journal-title"})
    title_el = _find_first(ctx, {"article-title", "title"})
    title = _xml_text(title_el) if title_el is not None else ""
    doi = None
    for el in ctx.iter():
        if _local(el.tag) in {"article-id", "doi"}:
            text = _xml_text(el)
            if text and (DOI_RE.search(text) or _local(el.tag) == "doi"):
                doi = normalize_doi(text) or text
                break
    authors: list[str] = []
    for contrib in _find_all(ctx, {"contrib"}):
        surname = _find_first(contrib, {"surname"})
        given = _find_first(contrib, {"given-names"})
        name = " ".join(x for x in (
            _xml_text(given) if given is not None else "",
            _xml_text(surname) if surname is not None else "",
        ) if x).strip()
        if name:
            authors.append(name)
    abstract_el = _find_first(ctx, {"abstract"})
    abstract = _xml_text(abstract_el) if abstract_el is not None else ""
    body_el = _find_first(root, {"body"})
    sections: list[str] = []
    if body_el is not None:
        for sec in _find_all(body_el, {"sec"}):
            title_el = _find_first(sec, {"title"})
            if title_el is not None:
                heading = _xml_text(title_el).lower()
                if heading and heading not in sections:
                    sections.append(heading)
    body = _xml_text(body_el) if body_el is not None else ""
    refs = _find_first(root, {"ref-list", "references"})
    ref_count = len(_find_all(refs, {"ref"})) if refs is not None else 0
    year = ""
    pub_date = _find_first(ctx, {"pub-date", "year"})
    if pub_date is not None:
        year = _xml_text(pub_date)[:4]
    return {
        "format": "jats", "title": title, "doi": doi, "authors": authors,
        "abstract": abstract, "text": (abstract + "\n\n" + body).strip(),
        "body": body, "sections": sections, "references": ref_count,
        "year": year, "venue": _xml_text(journal) if journal is not None else "",
        "pages": 0, "page_offsets": [0], "extractor": "defusedxml",
    }


def _pdf_metadata(data: bytes) -> dict:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        raw = doc.metadata or {}
        pages = doc.page_count
        first = doc[0].get_text("text") if pages else ""
        doc.close()
        return {"pdf_title": (raw.get("title") or "").strip(),
                "pdf_author": (raw.get("author") or "").strip(),
                "pages": pages, "first_page": first}
    except Exception:
        return {"pdf_title": "", "pdf_author": "", "pages": 0, "first_page": ""}


def _headings_from_text(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        clean = line.strip().strip("#").strip()
        if not clean or len(clean) > 90:
            continue
        low = clean.lower().rstrip(":")
        if any(low == w or low.startswith(w + " ") for words in SECTION_WORDS.values()
               for w in words):
            if low not in found:
                found.append(low)
    return found


def section_presence(text: str, headings: list[str] | None = None) -> dict:
    low = (text or "").lower()
    heads = " | ".join(headings or []) + " | " + " | ".join(_headings_from_text(text))
    return {key: any(w in heads for w in words) for key, words in SECTION_WORDS.items()}


def assess_abstract(text: str, *, title: str = "") -> dict:
    """Score whether an abstract is comprehensive enough to stand in for full text."""
    abstract = (text or "").strip()
    # If the caller supplied a full page, isolate the abstract when possible.
    m = ABSTRACT_HEADING_RE.search(abstract)
    if m:
        tail = abstract[m.end():]
        stop = re.search(r"^\s*(keywords?|introduction|background|1\.\s|مقدمه)\b",
                         tail, re.I | re.M)
        abstract = tail[:stop.start()] if stop else tail[:4000]
    words = len(abstract.split())
    low = abstract.lower()
    checks = {key: any(marker in low for marker in markers)
              for key, markers in ABSTRACT_MARKERS.items()}
    score = sum(1 for v in checks.values() if v)
    structured = bool(re.search(
        r"(background|objective|aim|methods?|results?|conclusions?)\s*[:\-]",
        abstract, re.I))
    if words < 120:
        verdict = "insufficient"
    elif score >= 4 and words >= 200:
        verdict = "comprehensive"
    elif structured and words >= 180 and score >= 3:
        verdict = "comprehensive"
    elif words >= 250 and score >= 3:
        verdict = "comprehensive"
    else:
        verdict = "limited"
    return {
        "verdict": verdict, "score": score, "words": words,
        "structured": structured, "checks": checks,
        "text": abstract[:6000],
    }


def extract_artifact(data: bytes, *, filename: str | None = None,
                     content_type: str | None = None) -> dict:
    """Detect, extract and return a normalized artifact descriptor."""
    fmt = detect_format(data, filename, content_type)
    if fmt == "pdf":
        text, offsets = extract_mod.extract_pdf(data)
        meta = _pdf_metadata(data)
        headings = _headings_from_text(text)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        return {
            "format": "pdf", "text": text, "body": text,
            "page_offsets": offsets, "pages": meta.get("pages") or len(offsets),
            "title": meta.get("pdf_title") or util.truncate(first_line, 200),
            "doi": normalize_doi(first_line) or normalize_doi(text[:5000]),
            "authors": [meta["pdf_author"]] if meta.get("pdf_author") else [],
            "abstract": "", "sections": headings, "references": 0,
            "year": "", "venue": "", "extractor": "pdf-ladder",
        }
    if fmt == "jats":
        return extract_jats(data)
    if fmt == "html":
        try:
            import trafilatura  # type: ignore

            raw = data.decode("utf-8", errors="replace")
            text = trafilatura.extract(raw, include_tables=True) or raw
            md = trafilatura.extract_metadata(raw)
            title = getattr(md, "title", "") if md else ""
            return {"format": "html", "text": text, "body": text,
                    "page_offsets": [0], "pages": 1, "title": title,
                    "doi": normalize_doi(text[:5000]), "authors": [],
                    "abstract": "", "sections": _headings_from_text(text),
                    "references": 0, "year": "", "venue": "",
                    "extractor": "trafilatura"}
        except Exception:
            text = data.decode("utf-8", errors="replace")
            return {"format": "html", "text": text, "body": text,
                    "page_offsets": [0], "pages": 1, "title": "",
                    "doi": normalize_doi(text[:5000]), "authors": [],
                    "abstract": "", "sections": _headings_from_text(text),
                    "references": 0, "year": "", "venue": "",
                    "extractor": "raw-html"}
    if fmt == "text":
        text = data.decode("utf-8", errors="replace")
        return {"format": "text", "text": text, "body": text,
                "page_offsets": [0], "pages": 1, "title": "",
                "doi": normalize_doi(text[:5000]), "authors": [],
                "abstract": "", "sections": _headings_from_text(text),
                "references": 0, "year": "", "venue": "",
                "extractor": "text"}
    raise ValueError("unsupported artifact format; expected PDF, JATS XML, HTML or text")


def _match(a: str, b: str) -> float:
    return util.fuzzy(util.normalize_text(a), util.normalize_text(b))


def validate_identity(source: dict, artifact: dict, *, strict: bool = True) -> dict:
    """Compare artifact metadata/text against the source record."""
    title_match = None
    if source.get("title") and artifact.get("title"):
        title_match = round(_match(source["title"], artifact["title"]), 3)
    abstract_match = None
    if source.get("abstract") and artifact.get("abstract"):
        abstract_match = round(_match(source["abstract"], artifact["abstract"]), 3)
    src_doi = normalize_doi(source.get("doi"))
    art_doi = normalize_doi(artifact.get("doi"))
    doi_match = bool(src_doi and art_doi and src_doi == art_doi)
    doi_conflict = bool(src_doi and art_doi and src_doi != art_doi)
    text = artifact.get("text") or ""
    sections = section_presence(text, artifact.get("sections"))
    chars = len(text.strip())
    pages = int(artifact.get("pages") or 0)
    abstract_only = (
        pages <= 2 and chars < 6000
        and not any(sections.get(k) for k in ("introduction", "methods", "results"))
    ) or (chars < 2500 and not any(sections.get(k) for k in ("introduction", "methods")))
    checks = {
        "doi_match": doi_match,
        "doi_conflict": doi_conflict,
        "title_match": title_match,
        "abstract_match": abstract_match,
        "sections": sections,
        "chars": chars,
        "pages": pages,
        "abstract_only": abstract_only,
    }
    reasons: list[str] = []
    if doi_conflict:
        reasons.append("DOI mismatch")
    if strict and title_match is not None and title_match < 0.90 and not doi_match:
        reasons.append(f"title similarity {title_match:.3f} < 0.90")
    if strict and abstract_match is not None and abstract_match < 0.75:
        reasons.append(f"abstract similarity {abstract_match:.3f} < 0.75")
    if strict and chars < 1200:
        reasons.append(f"text too short ({chars} chars)")
    if strict and abstract_only:
        reasons.append("artifact looks abstract-only")
    if strict and not any(sections.get(k) for k in ("introduction", "methods", "results")):
        reasons.append("no recognizable body sections")
    return {
        "ok": not reasons, "reasons": reasons, **checks,
        "title_match": title_match, "abstract_match": abstract_match,
    }


def fulltext_descriptor(artifact: dict, *, status: str, path: str, sha256: str,
                        text_path: str, text_sha256: str, text_chars: int,
                        origin: dict | None = None, validation: dict | None = None,
                        version: str = "unknown", license_: str | None = None,
                        exception: dict | None = None) -> dict:
    return {
        "status": status,
        "format": artifact.get("format") or "unknown",
        "path": path,
        "sha256": sha256,
        "bytes": int(origin.get("bytes") or 0) if origin else 0,
        "pages": int(artifact.get("pages") or 0),
        "text_path": text_path,
        "text_sha256": text_sha256,
        "text_chars": int(text_chars),
        "version": version or "unknown",
        "host": (origin or {}).get("host") or "",
        "license": license_ or (origin or {}).get("license"),
        "landing_url": (origin or {}).get("landing_url"),
        "retrieved_from": (origin or {}).get("final_url") or (origin or {}).get("url"),
        "retrieved_at": util.utcnow_iso(),
        "extractor": artifact.get("extractor") or "",
        "validation": validation or {},
        "exception": exception,
    }
