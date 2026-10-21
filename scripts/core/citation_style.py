"""Citation rendering: stable ``[@SRC-0001]`` markers to APA/Vancouver/IEEE."""

from __future__ import annotations

import re
from typing import Iterable

MARKER_RE = re.compile(r"\[@SRC-\d{4}(?:\s*;\s*@?SRC-\d{4})*\]")
SINGLE_RE = re.compile(r"\[@(SRC-\d{4})\]")

STYLES = ("apa", "vancouver", "ieee")


def _year(src: dict) -> str:
    raw = str(src.get("published") or src.get("year") or src.get("as_of") or "")
    m = re.search(r"(19|20)\d{2}", raw)
    return m.group(0) if m else "n.d."


def _authors(src: dict, style: str) -> str:
    authors = [a.strip() for a in (src.get("authors") or []) if str(a).strip()]
    if not authors:
        return "Anonymous"
    if style == "apa":
        out = []
        for a in authors[:20]:
            parts = a.split()
            if len(parts) == 1:
                out.append(parts[0])
            else:
                out.append(f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1])}")
        if len(authors) > 20:
            return ", ".join(out[:19]) + ", … " + out[-1]
        return ", ".join(out[:-1]) + (", & " + out[-1] if len(out) > 1 else out[0])
    if style == "vancouver":
        out = []
        for a in authors[:6]:
            parts = a.split()
            out.append((parts[-1] + " " + "".join(p[0] for p in parts[:-1])).strip())
        if len(authors) > 6:
            out.append("et al")
        return ", ".join(out)
    out = []
    for a in authors[:6]:
        parts = a.split()
        out.append(" ".join(p[0] + "." for p in parts[:-1]) + " " + parts[-1])
    if len(authors) > 6:
        out.append("et al.")
    return ", ".join(out)


def _title(src: dict) -> str:
    return (src.get("title") or "Untitled").strip().rstrip(".")


def _venue(src: dict) -> str:
    return (src.get("venue") or src.get("publisher") or "").strip()


def _doi(src: dict) -> str:
    doi = src.get("doi") or src.get("published_doi")
    return f"https://doi.org/{doi}" if doi else ""


def format_reference(src: dict, style: str = "apa", number: int | None = None) -> str:
    style = style.lower()
    authors, year, title = _authors(src, style), _year(src), _title(src)
    venue = _venue(src)
    volume = src.get("volume") or ""
    issue = src.get("issue") or ""
    pages = src.get("pages") or ""
    doi = _doi(src)
    if style == "vancouver":
        loc = f"{year}"
        if volume:
            loc += f";{volume}"
        if issue:
            loc += f"({issue})"
        if pages:
            loc += f":{pages}"
        bits = [f"{authors}.", f"{title}.", f"{venue}." if venue else "", loc + "."]
        if doi:
            bits.append(f"doi:{doi.replace('https://doi.org/', '')}.")
        return " ".join(b for b in bits if b).strip()
    if style == "ieee":
        bits = [f"[{number}]" if number else "", f"{authors},", f"“{title},”"]
        if venue:
            bits.append(f"{venue},")
        if volume:
            bits.append(f"vol. {volume},")
        if issue:
            bits.append(f"no. {issue},")
        if pages:
            bits.append(f"pp. {pages},")
        bits.append(f"{year}.")
        if doi:
            bits.append(f"doi: {doi.replace('https://doi.org/', '')}.")
        return " ".join(b for b in bits if b).strip()
    bits = [f"{authors} ({year}).", f"{title}."]
    if venue:
        bits.append(f"{venue}.")
    if volume:
        bits.append(f"{volume}" + (f"({issue})" if issue else "") + (f", {pages}" if pages else "") + ".")
    elif pages:
        bits.append(f"{pages}.")
    if doi:
        bits.append(doi)
    return " ".join(b for b in bits if b).strip()


def _in_text(src: dict, style: str, number: int | None) -> str:
    if style == "vancouver":
        return str(number or "?")
    if style == "ieee":
        return f"[{number or '?'}]"
    authors = [a for a in (src.get("authors") or []) if str(a).strip()]
    if not authors:
        label = (src.get("title") or "Anonymous").split()[0]
    elif len(authors) == 1:
        label = authors[0].split()[-1]
    elif len(authors) == 2:
        label = authors[0].split()[-1] + " & " + authors[1].split()[-1]
    else:
        label = authors[0].split()[-1] + " et al."
    return f"{label}, {_year(src)}"


def render_citations(text: str, sources: Iterable[dict], style: str = "apa") -> str:
    by_id = {s["id"]: s for s in sources}
    numbers = {sid: i + 1 for i, sid in enumerate(by_id)}
    style = style.lower()
    if style not in STYLES:
        style = "apa"

    def one(match: re.Match) -> str:
        ids = re.findall(r"SRC-\d{4}", match.group(0))
        parts = []
        for sid in ids:
            src = by_id.get(sid)
            if not src:
                parts.append(sid)
            else:
                parts.append(_in_text(src, style, numbers.get(sid)))
        if style == "vancouver":
            return "(" + ", ".join(parts) + ")"
        if style == "ieee":
            return ", ".join(parts)
        return "(" + "; ".join(parts) + ")"

    return MARKER_RE.sub(one, text)


def bibliography(sources: Iterable[dict], style: str = "apa") -> list[str]:
    ordered = sorted((s for s in sources if s.get("status") != "excluded"),
                     key=lambda s: ((s.get("authors") or ["zzz"])[0].lower(),
                                    _year(s), s.get("title") or ""))
    if style in ("vancouver", "ieee"):
        ordered = sorted(ordered, key=lambda s: s.get("id", ""))
    return [format_reference(s, style, i + 1) for i, s in enumerate(ordered)]
