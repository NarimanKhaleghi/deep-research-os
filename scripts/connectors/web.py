"""Web connector — generic fetch + extraction, and the keyless web-search shelf.

Search order: local SearXNG (detected at 127.0.0.1:8888) → DuckDuckGo lite.
Fetched content is UNTRUSTED evidence (see references/protocol.md §8).
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "web"
DOMAINS = ["web"]
TIER = 2
SEARXNG = os.environ.get("RESEARCH_OS_SEARXNG", "http://127.0.0.1:8888")
DDG_LITE = "https://lite.duckduckgo.com/lite/"


# ------------------------------------------------------------------- fetch

def fetch_url(url: str) -> dict:
    """Fetch a URL and extract main text. Returns {url, final_url, title, text, html, published}."""
    resp = http.request("GET", url)
    html = resp.text
    text, title, published = html, None, None
    try:
        import trafilatura  # type: ignore

        text = trafilatura.extract(html, url=str(resp.url), include_comments=False, include_tables=True) or ""
        meta = trafilatura.extract_metadata(html, default_url=str(resp.url))
        if meta:
            title = getattr(meta, "title", None)
            published = getattr(meta, "date", None)
    except Exception:
        pass
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    return {
        "url": url,
        "final_url": str(resp.url),
        "title": title,
        "text": text or "",
        "html": html,
        "published": published,
    }


# ------------------------------------------------------------------ search

def _searxng(query: str, limit: int) -> list[dict] | None:
    try:
        payload = http.get_json(
            f"{SEARXNG}/search",
            params={"q": query, "format": "json", "language": "all"},
            timeout=6.0,
            retries=0,
        )
    except Exception:
        return None
    results = payload.get("results") or []
    if not isinstance(results, list):
        return None
    out = []
    for r in results[:limit]:
        out.append(
            make_record(
                service="searxng",
                title=r.get("title", ""),
                url=r.get("url", ""),
                abstract=r.get("content"),
                published=(r.get("publishedDate") or "")[:10] or None,
                publisher=r.get("engine"),
                type_="webpage",
            )
        )
    return dedupe(out)


def _ddg_lite(query: str, limit: int) -> list[dict]:
    try:
        html = http.get_text(DDG_LITE, params={"q": query}, timeout=10.0)
    except Exception:
        return []
    out = []
    for href, raw_title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        if "duckduckgo.com" in href and "uddg=" not in href:
            continue
        url = href
        if "uddg=" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            url = (qs.get("uddg") or [""])[0]
        if not url.startswith("http"):
            continue
        title = re.sub(r"<[^>]+>", "", raw_title)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 8:
            continue
        out.append(
            make_record(service="ddg", title=title, url=url, type_="webpage")
        )
        if len(out) >= limit:
            break
    return dedupe(out)


def search_web(query: str, limit: int = 10) -> list[dict]:
    got = _searxng(query, limit)
    if got:
        return got
    return _ddg_lite(query, limit)
