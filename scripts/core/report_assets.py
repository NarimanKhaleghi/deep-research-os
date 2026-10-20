"""Report HTML assets — self-contained CSS/JS with embedded (base64) WOFF2 fonts.

Generated reports must open correctly from any folder, offline, with no
network. Fonts are subset upstream (see assets/fonts/README.md); a language
gets only the families it needs:

  en → Instrument Serif + Source Serif 4 + Inter + IBM Plex Mono
  fa → Vazirmatn + IBM Plex Mono
"""

from __future__ import annotations

import base64
import os
import sys
from functools import lru_cache

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import paths  # noqa: E402

FONT_DIR = paths.repo_root() / "assets" / "fonts"

# file -> (family, weight, style)
FONT_SETS: dict[str, list[tuple[str, str, str, str]]] = {
    "en": [
        ("instrument-serif.woff2", "Instrument Serif", "400", "normal"),
        ("instrument-serif-italic.woff2", "Instrument Serif", "400", "italic"),
        ("source-serif-var.woff2", "Source Serif 4", "200 900", "normal"),
        ("source-serif-italic.woff2", "Source Serif 4", "200 900", "italic"),
        ("inter-var.woff2", "Inter", "100 900", "normal"),
        ("ibm-plex-mono.woff2", "IBM Plex Mono", "400", "normal"),
    ],
    "fa": [
        ("vazirmatn-var.woff2", "Vazirmatn", "100 900", "normal"),
        ("ibm-plex-mono.woff2", "IBM Plex Mono", "400", "normal"),
    ],
}


def _b64(path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


@lru_cache(maxsize=4)
def font_css(lang: str) -> str:
    """@font-face rules with base64 WOFF2 payloads for the report's language."""
    if lang not in FONT_SETS:
        lang = "en"
    blocks: list[str] = []
    for filename, family, weight, style in FONT_SETS[lang]:
        path = FONT_DIR / filename
        if not path.exists():
            continue
        blocks.append(
            "@font-face{"
            f"font-family:'{family}';"
            f"font-style:{style};font-weight:{weight};font-display:swap;"
            f"src:url(data:font/woff2;base64,{_b64(path)}) format('woff2');"
            "}"
        )
    return "\n".join(blocks)


def _read(name: str) -> str:
    path = paths.repo_root() / "templates" / "assets" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


@lru_cache(maxsize=4)
def report_css(lang: str) -> str:
    """Full stylesheet: embedded fonts + report.css."""
    return font_css(lang) + "\n" + _read("report.css")


@lru_cache(maxsize=1)
def report_js() -> str:
    return _read("report.js")


def available() -> bool:
    return FONT_DIR.is_dir() and any(FONT_DIR.glob("*.woff2"))
