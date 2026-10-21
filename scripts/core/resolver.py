"""Legal full-text resolver.

Given a source record (or DOI/URL/file), return ranked *lawful* candidates:
publisher OA, PMC/Europe PMC, repositories, preprints, then landing pages.
No paywall bypass, no pirate hosts, no browser-cookie tricks.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from core import fulltext  # noqa: E402
from lib import http, util  # noqa: E402

MAILTO = os.environ.get("RESEARCH_OS_MAILTO", "deep-research-os@users.noreply.github.com")
_PDF_HINT = re.compile(r"(\.pdf(?:$|\?)|/pdf/|pdf_url|download)", re.I)
_VERSION_HINTS = (
    ("version-of-record", ("publisher", "doi.org", "sciencedirect", "springer", "wiley",
                           "tandfonline", "sagepub", "nature.com", "science.org", "jamanetwork")),
    ("accepted-manuscript", ("repository", "escholarship", "hal.", "openaccess", "core.ac.uk",
                             "researchgate", "academia.edu", "dspace", "repositor")),
    ("preprint", ("arxiv", "biorxiv", "medrxiv", "ssrn", "preprint", "osf.io/preprints")),
)


def classify_version(url: str, declared: str | None = None) -> str:
    if declared in ("version-of-record", "accepted-manuscript", "preprint"):
        return declared
    low = (url or "").lower()
    for version, hints in _VERSION_HINTS:
        if any(h in low for h in hints):
            return version
    return "unknown"


def _candidate(url: str | None, *, kind: str, provider: str, landing_url: str | None = None,
               version: str | None = None, license_: str | None = None,
               priority: int = 50, note: str = "") -> dict | None:
    if not url:
        return None
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        return None
    host = (urlparse(url).hostname or "").lower()
    if http.is_blocked_host(host):
        return None
    return {
        "url": url, "kind": kind, "provider": provider,
        "landing_url": landing_url or url, "host": host,
        "version": classify_version(url, version), "license": license_,
        "priority": priority, "note": note,
    }


def _doi_variants(doi: str | None, source: dict) -> list[str]:
    out: list[str] = []
    for value in (doi, source.get("doi"), source.get("published_doi"), source.get("preprint_doi")):
        norm = fulltext.normalize_doi(value)
        if norm and norm not in out:
            out.append(norm)
    return out


def _unpaywall(doi: str) -> list[dict]:
    try:
        payload = http.get_json(f"https://api.unpaywall.org/v2/{quote(doi, safe='')}",
                                params={"email": MAILTO}, timeout=20)
    except Exception:
        return []
    out = []
    for loc in [payload.get("best_oa_location"), *(payload.get("oa_locations") or [])]:
        if not loc:
            continue
        out.append(_candidate(
            loc.get("url_for_pdf"), kind="pdf", provider="unpaywall",
            landing_url=loc.get("url") or payload.get("doi_url"),
            version="version-of-record" if loc.get("version") == "publishedVersion" else None,
            license_=loc.get("license"), priority=10,
            note=f"oa_status={payload.get('oa_status') or 'unknown'}",
        ))
        out.append(_candidate(
            loc.get("url"), kind="html", provider="unpaywall",
            landing_url=loc.get("url"), version=None, license_=loc.get("license"),
            priority=60, note="landing page",
        ))
    return [c for c in out if c]


def _openalex(doi: str) -> list[dict]:
    try:
        w = http.get_json(f"https://api.openalex.org/works/doi:{quote(doi, safe='')}",
                          params={"mailto": MAILTO}, timeout=20)
    except Exception:
        return []
    out = []
    for loc in w.get("locations") or []:
        if not loc.get("is_oa"):
            continue
        src = (loc.get("source") or {}).get("display_name") or "openalex"
        out.append(_candidate(
            loc.get("pdf_url"), kind="pdf", provider=f"openalex:{src}",
            landing_url=loc.get("landing_page_url"), license_=loc.get("license"),
            version="version-of-record" if loc.get("version") == "publishedVersion" else None,
            priority=15,
        ))
    oa = w.get("open_access") or {}
    out.append(_candidate(oa.get("oa_url"), kind="html", provider="openalex:oa_url",
                          landing_url=w.get("doi") or w.get("id"), priority=65))
    return [c for c in out if c]


def _europepmc(doi: str) -> list[dict]:
    out = []
    try:
        payload = http.get_json(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": f'DOI:"{doi}"', "format": "json", "resultType": "core",
                    "pageSize": 5}, timeout=25)
    except Exception:
        return []
    for rec in (payload.get("resultList") or {}).get("result") or []:
        pmcid = rec.get("pmcid")
        if pmcid:
            out.append(_candidate(
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
                kind="jats", provider="europepmc", landing_url=rec.get("doi") or rec.get("id"),
                version="version-of-record", license_=rec.get("license"), priority=5,
                note=f"pmcid={pmcid}",
            ))
        for link in ((rec.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
            if str(link.get("availability") or "").lower() != "open access":
                continue
            style = str(link.get("documentStyle") or "").lower()
            kind = "pdf" if "pdf" in style else "html"
            out.append(_candidate(
                link.get("url"), kind=kind, provider="europepmc",
                landing_url=rec.get("doi") or rec.get("id"),
                version="version-of-record", license_=rec.get("license"),
                priority=8 if kind == "pdf" else 55,
            ))
    return [c for c in out if c]


def _crossref(doi: str) -> list[dict]:
    try:
        msg = http.get_json(f"https://api.crossref.org/works/{quote(doi, safe='')}",
                            params={"mailto": MAILTO}, timeout=20).get("message") or {}
    except Exception:
        return []
    out = []
    for link in msg.get("link") or []:
        ctype = str(link.get("content-type") or "").lower()
        if "pdf" in ctype:
            out.append(_candidate(link.get("URL"), kind="pdf", provider="crossref",
                                  landing_url=msg.get("URL"), priority=25,
                                  note="publisher link (may require entitlement)"))
    return [c for c in out if c]


def _semantic_scholar(doi: str) -> list[dict]:
    try:
        p = http.get_json(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}",
            params={"fields": "title,openAccessPdf,externalIds"}, timeout=20)
    except Exception:
        return []
    pdf = p.get("openAccessPdf") or {}
    return [c for c in [_candidate(pdf.get("url"), kind="pdf", provider="semanticscholar",
                                   landing_url=p.get("externalIds", {}).get("DOI"),
                                   priority=20)] if c]


def _arxiv(doi: str, source: dict) -> list[dict]:
    ids: list[str] = []
    for value in (doi, source.get("url"), source.get("preprint_doi")):
        if not value:
            continue
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#\s]+?)(?:\.pdf)?$", str(value), re.I)
        if m:
            ids.append(m.group(1))
        m = re.search(r"10\.48550/arxiv\.([^?#\s]+)", str(value), re.I)
        if m:
            ids.append(m.group(1))
    return [c for c in [_candidate(f"https://arxiv.org/pdf/{i}.pdf", kind="pdf",
                                   provider="arxiv", landing_url=f"https://arxiv.org/abs/{i}",
                                   version="preprint", priority=30) for i in dict.fromkeys(ids)] if c]


def _biorxiv(doi: str) -> list[dict]:
    out = []
    for server in ("biorxiv", "medrxiv"):
        try:
            payload = http.get_json(f"https://api.biorxiv.org/details/{server}/{quote(doi, safe='')}",
                                    timeout=20)
        except Exception:
            continue
        for rec in (payload.get("collection") or [])[-1:]:
            out.append(_candidate(rec.get("jatsxml"), kind="jats", provider=server,
                                  landing_url=f"https://doi.org/{doi}",
                                  version="preprint", priority=32))
            out.append(_candidate(f"https://www.{server}.org/content/{doi}v{rec.get('version', 1)}.full.pdf",
                                  kind="pdf", provider=server,
                                  landing_url=f"https://doi.org/{doi}",
                                  version="preprint", priority=34))
    return [c for c in out if c]


def _doaj(doi: str) -> list[dict]:
    try:
        payload = http.get_json(f"https://doaj.org/api/search/articles/doi:{quote(doi, safe='')}",
                                timeout=20)
    except Exception:
        return []
    out = []
    for rec in payload.get("results") or []:
        for link in ((rec.get("bibjson") or {}).get("link") or []):
            kind = "pdf" if "pdf" in str(link.get("type") or "").lower() or _PDF_HINT.search(
                str(link.get("url") or "")) else "html"
            out.append(_candidate(link.get("url"), kind=kind, provider="doaj",
                                  landing_url=(rec.get("bibjson") or {}).get("link", [{}])[0].get("url"),
                                  version="version-of-record", priority=18))
    return [c for c in out if c]


def _zenodo(doi: str) -> list[dict]:
    try:
        payload = http.get_json("https://zenodo.org/api/records",
                                params={"q": f'doi:"{doi}"', "size": 3}, timeout=20)
    except Exception:
        return []
    out = []
    for rec in payload.get("hits", {}).get("hits") or []:
        for f in rec.get("files") or []:
            out.append(_candidate(f.get("links", {}).get("self"), kind="pdf",
                                  provider="zenodo", landing_url=rec.get("links", {}).get("self_html"),
                                  version="accepted-manuscript", priority=35))
    return [c for c in out if c]


def _hal(doi: str) -> list[dict]:
    try:
        payload = http.get_json("https://api.archives-ouvertes.fr/search/",
                                params={"q": f'doiId_s:"{doi}"', "fl": "fileMain_s,uri_s,title_s",
                                        "rows": 3, "wt": "json"}, timeout=20)
    except Exception:
        return []
    out = []
    for rec in (payload.get("response") or {}).get("docs") or []:
        out.append(_candidate(rec.get("fileMain_s"), kind="pdf", provider="hal",
                              landing_url=rec.get("uri_s"), version="accepted-manuscript",
                              priority=28))
    return [c for c in out if c]


def _pmc_from_ids(source: dict, doi: str | None) -> list[dict]:
    out = []
    pmcid = source.get("pmcid") or (source.get("extra") or {}).get("pmcid")
    if pmcid:
        out.append(_candidate(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
                              kind="jats", provider="pmc", landing_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                              version="version-of-record", priority=5))
    return [c for c in out if c]


def _direct(url: str | None) -> list[dict]:
    if not url:
        return []
    kind = "pdf" if _PDF_HINT.search(url) or url.lower().endswith(".pdf") else "html"
    return [c for c in [_candidate(url, kind=kind, provider="direct", landing_url=url,
                                   priority=40 if kind == "pdf" else 70)] if c]


def resolve(source: dict, *, doi: str | None = None, url: str | None = None,
            include_preprint: bool = True, timeout: float = 20.0) -> list[dict]:
    """Return de-duplicated, ranked lawful candidates for one source."""
    del timeout  # each helper uses its own bounded timeout
    dois = _doi_variants(doi, source)
    candidates: list[dict] = []
    candidates += _direct(url or source.get("url"))
    for d in dois:
        candidates += _pmc_from_ids(source, d)
        candidates += _europepmc(d)
        candidates += _unpaywall(d)
        candidates += _openalex(d)
        candidates += _semantic_scholar(d)
        candidates += _crossref(d)
        candidates += _doaj(d)
        candidates += _zenodo(d)
        candidates += _hal(d)
        candidates += _arxiv(d, source)
        if include_preprint:
            candidates += _biorxiv(d)
    seen: set[str] = set()
    out: list[dict] = []
    for c in sorted(candidates, key=lambda x: (x["priority"], x["url"])):
        key = c["url"].split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def request_template(source: dict) -> dict:
    """Author/institution request text for a paywalled source."""
    title = source.get("title") or "(title unknown)"
    doi = source.get("doi") or ""
    authors = ", ".join((source.get("authors") or [])[:3]) or "(authors unknown)"
    body = (
        f"Subject: Request for full-text copy — {title}\n\n"
        f"Dear {authors},\n\n"
        "I am conducting an academic literature review and would like to request a copy of "
        f"your article “{title}”{f' (DOI: {doi})' if doi else ''} for reading and citation. "
        "If you can share the accepted manuscript or version of record, I would be grateful.\n\n"
        "Thank you for your time.\n"
    )
    return {"to": "", "subject": f"Request for full-text copy — {title}", "body": body,
            "doi": doi, "legal_note": "author/institution request; no paywall bypass"}
