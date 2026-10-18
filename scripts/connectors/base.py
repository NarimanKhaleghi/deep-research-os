"""Connector base: normalized record shape shared by every connector."""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402


def make_record(
    *,
    service: str,
    title: str,
    url: str,
    doi: str | None = None,
    authors: list[str] | None = None,
    published: str | None = None,
    publisher: str | None = None,
    type_: str = "other",
    abstract: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Normalized candidate record returned by every connector search()."""
    return {
        "service": service,
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "doi": (doi or "").strip().lower() or None,
        "authors": authors or [],
        "published": published,
        "publisher": publisher,
        "type": type_,
        "abstract": util.truncate(abstract or "", 1200) or None,
        "origin_key": util.domain_of(url or ""),
        "extra": extra or {},
    }


def dedupe(records: list[dict]) -> list[dict]:
    """Drop duplicates by DOI, then by normalized URL/title."""
    seen_doi, seen_url, seen_title, out = set(), set(), set(), []
    for r in records:
        doi = (r.get("doi") or "").lower()
        url = util.normalize_text(r.get("url") or "")
        title = util.normalize_text(r.get("title") or "")
        if doi and doi in seen_doi:
            continue
        if url and url in seen_url:
            continue
        if title and title in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if url:
            seen_url.add(url)
        if title:
            seen_title.add(title)
        out.append(r)
    return out
