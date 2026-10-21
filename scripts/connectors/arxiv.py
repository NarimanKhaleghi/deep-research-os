"""arXiv connector — preprints (Atom API). Label preprints; credibility caps at B.

Docs: https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "arxiv"
DOMAINS = ["academic"]
TIER = 2
BASE = "https://export.arxiv.org/api/query"
_NS = {"a": "http://www.w3.org/2005/Atom"}


def parse_feed(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for e in root.findall("a:entry", _NS):
        title = " ".join((e.findtext("a:title", "", _NS) or "").split())
        summary = " ".join((e.findtext("a:summary", "", _NS) or "").split())
        link = ""
        for ln in e.findall("a:link", _NS):
            if ln.get("rel") == "alternate" or ln.get("type") == "text/html":
                link = ln.get("href", "")
                break
        if not link:
            link = e.findtext("a:id", "", _NS)
        authors = [
            (a.findtext("a:name", "", _NS) or "").strip()
            for a in e.findall("a:author", _NS)
        ]
        published = (e.findtext("a:published", "", _NS) or "")[:10] or None
        doi = e.findtext("{http://arxiv.org/schemas/atom}doi")
        jref = e.findtext("{http://arxiv.org/schemas/atom}journal_ref")
        out.append(
            make_record(
                service=SERVICE,
                title=title,
                url=link,
                doi=doi,
                authors=[a for a in authors if a],
                published=published,
                publisher="arXiv",
                type_="preprint",
                abstract=summary,
                extra={
                    "journal_ref": jref,
                    "arxiv_id": re.sub(r"^.*/abs/", "", e.findtext("a:id", "", _NS)),
                },
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, offset: int = 0, **kw) -> list[dict]:
    xml = http.get_text(
        BASE,
        params={
            "search_query": f"all:{query}",
            "start": max(0, offset),
            "max_results": max(1, min(limit, 100)),
            "sortBy": "relevance",
        },
    )
    return parse_feed(xml)
