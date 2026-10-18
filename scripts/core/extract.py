"""Extraction — URL/HTML fetch, PDF text ladder, and quote locating.

PDF ladder: PyMuPDF → pdftotext (subprocess) → pypdf. Page markers are form
feeds so evidence locators can say "p.12" and be re-checked.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import util  # noqa: E402


# --------------------------------------------------------------- fetch

def fetch_page(url: str) -> dict:
    """Fetch + readability-extract a page. Returns {url, final_url, title, text, html, published}."""
    from connectors import web as web_connector

    return web_connector.fetch_url(url)


# --------------------------------------------------------------- PDFs

def extract_pdf(data: bytes) -> tuple[str, list[int]]:
    """Extract PDF text. Returns (text_with_formfeeds, page_start_offsets)."""
    text = _pdf_via_pymupdf(data)
    if not text:
        text = _pdf_via_pdftotext(data)
    if not text:
        text = _pdf_via_pypdf(data)
    pages = page_offsets(text)
    return text, pages


def _pdf_via_pymupdf(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        doc.close()
        return "\f".join(parts)
    except Exception:
        return ""


def _pdf_via_pdftotext(data: bytes) -> str:
    exe = _which("pdftotext")
    if not exe:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(data)
            tmp = fh.name
        out = subprocess.run(
            [exe, "-layout", tmp, "-"],
            capture_output=True, timeout=60, check=False,
        )
        os.unlink(tmp)
        if out.returncode == 0:
            return out.stdout.decode("utf-8", errors="replace").replace("\x0c", "\f")
    except Exception:
        pass
    return ""


def _pdf_via_pypdf(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        return "\f".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


def page_offsets(text: str) -> list[int]:
    """Offsets where each page starts (form-feed separated)."""
    offs, pos = [0], 0
    for chunk in text.split("\f"):
        pos += len(chunk) + 1
        offs.append(pos)
    return offs[:-1]


def page_of_offset(text: str, offset: int) -> int:
    offs = page_offsets(text)
    page = 1
    for i, start in enumerate(offs):
        if offset >= start:
            page = i + 1
        else:
            break
    return page


# --------------------------------------------------------------- files

def extract_file(path: str | Path) -> tuple[str, dict]:
    """Extract a local file (.pdf/.txt/.html/.md). Returns (text, meta)."""
    p = Path(path)
    data = p.read_bytes()
    if p.suffix.lower() == ".pdf":
        text, _ = extract_pdf(data)
        return text, {"kind": "text", "title": p.stem, "published": None}
    text = data.decode("utf-8", errors="replace")
    if p.suffix.lower() in (".html", ".htm"):
        try:
            import trafilatura  # type: ignore

            title = None
            extracted = trafilatura.extract(text, include_tables=True)
            meta = trafilatura.extract_metadata(text)
            if meta:
                title = getattr(meta, "title", None)
            return (extracted or text), {"kind": "text", "title": title or p.stem, "published": None}
        except Exception:
            return text, {"kind": "text", "title": p.stem, "published": None}
    return text, {"kind": "text", "title": p.stem, "published": None}


# ---------------------------------------------------------- quote finding

def find_quote_raw(quote: str, raw_text: str) -> tuple[bool, int | None, int | None]:
    """Locate a quote in raw text with whitespace tolerance.

    Tries: exact substring → regex with flexible whitespace → normalized fuzzy.
    Returns (found, start, end) — offsets are into ``raw_text`` when found via
    the first two methods, else None (fuzzy match).
    """
    if not quote or not raw_text:
        return False, None, None
    if quote in raw_text:
        i = raw_text.find(quote)
        return True, i, i + len(quote)
    pat = re.compile(r"\s+".join(re.escape(tok) for tok in quote.split()), re.IGNORECASE)
    m = pat.search(raw_text)
    if m:
        return True, m.start(), m.end()
    ok, _, _ = util.quote_in_text(quote, raw_text, threshold=0.95)
    return (True, None, None) if ok else (False, None, None)
