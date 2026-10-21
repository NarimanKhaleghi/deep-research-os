"""Shared utilities: ids, atomic JSON/JSONL IO with locking, text normalization,
number extraction/matching, minimal front-matter parsing, fuzzy matching."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

try:  # rapidfuzz is a required dep; fall back to difflib when stripped down
    from rapidfuzz import fuzz as _fuzz

    def fuzzy(a: str, b: str) -> float:
        """Similarity in [0, 1]."""
        return _fuzz.ratio(a, b) / 100.0

except Exception:  # pragma: no cover
    import difflib

    def fuzzy(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------- time & ids

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slugify(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return (text[:maxlen].rstrip("-")) or "project"


def next_id(prefix: str, existing: Iterable[str], width: int = 4) -> str:
    """Next ``PREFIX-0001`` style id given existing ones."""
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    mx = 0
    for e in existing:
        m = pat.match(str(e))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}-{mx + 1:0{width}d}"


# ------------------------------------------------------------- atomic IO

def ensure_dir(path: Path) -> Path:
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def write_json(path: Path, obj: Any) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return rows


@contextlib.contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Advisory exclusive lock via a sibling ``.lock`` file."""
    lock_path = Path(str(path) + ".lock")
    ensure_dir(lock_path.parent)
    with open(lock_path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def append_jsonl(path: Path, obj: dict) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    with file_lock(path):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    tmp.replace(path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    tmp.replace(path)


# ---------------------------------------------------------------- hashing

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------- text tools

_FA_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"  # Persian + Arabic-Indic digits
    "٫٬٪،",                 # Arabic decimal, thousands, percent, comma
    "01234567890123456789"
    ".,%,",
)
_ZWNJ = "\u200c"


def normalize_digits(text: str) -> str:
    return text.translate(_FA_DIGITS)


def normalize_text(text: str, keep_zwnj: bool = False) -> str:
    """NFKC, digit-fold, collapse whitespace, casefold for matching."""
    text = unicodedata.normalize("NFKC", text)
    text = normalize_digits(text)
    if not keep_zwnj:
        text = text.replace(_ZWNJ, "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def quote_in_text(quote: str, text: str, threshold: float = 0.95) -> tuple[bool, Optional[int], Optional[int]]:
    """Is ``quote`` present in ``text``? Returns (found, start, end).

    Tries normalized substring first, then a sliding fuzzy window.
    """
    nq, nt = normalize_text(quote), normalize_text(text)
    if not nq:
        return False, None, None
    idx = nt.find(nq)
    if idx >= 0:
        return True, idx, idx + len(nq)
    # fuzzy fallback: slide a window around best match start
    window = len(nq)
    best_score, best_pos = 0.0, None
    step = max(1, window // 8)
    for pos in range(0, max(1, len(nt) - window), step):
        score = fuzzy(nq, nt[pos : pos + window])
        if score > best_score:
            best_score, best_pos = score, pos
        if best_score >= 0.995:
            break
    if best_score >= threshold and best_pos is not None:
        return True, best_pos, best_pos + window
    return False, None, None


# --------------------------------------------------------------- numbers

_NUM_RE = re.compile(
    r"(?<![\w.])"
    r"(\d{1,3}(?:[,\u202f\u00a0]\d{3})+|\d+(?:\.\d+)?)"  # mantissa (grouped or plain)
    r"\s*(%|percent|bn|billion|mn|million|k\b|km|kg|mw|gw|kwh|€|\$|£|usd|eur)?"  # unit
)


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "").replace("\u202f", "").replace("\u00a0", ""))


def extract_numbers(text: str) -> list[dict]:
    """Extract {raw, value, unit, decimals} from text (FA digits normalized)."""
    out: list[dict] = []
    for m in _NUM_RE.finditer(normalize_digits(text)):
        raw, unit = m.group(1), (m.group(2) or "").strip().lower() or None
        try:
            value = _to_float(raw)
        except ValueError:
            continue
        dec = len(raw.split(".")[1]) if "." in raw else 0
        out.append({"raw": m.group(0).strip(), "value": value, "unit": unit, "decimals": dec})
    return out


def numbers_match(claim: dict, quote_numbers: list[dict]) -> bool:
    """Precision-aware presence check.

    A claim number matches when either:
      - it equals a quote number within the quote number's rounding half-step, or
      - the claim keeps >= the source precision and equals it when rounded to
        the claim's precision (rounding *up* in precision is forbidden:
        97 from 96.555 fails).
    """
    cv, cu = claim.get("value"), claim.get("unit")
    cdec = claim.get("decimals", 0)
    for qn in quote_numbers:
        if cu and qn.get("unit") and cu != qn["unit"] and not _units_compatible(cu, qn["unit"]):
            continue
        qv, qdec = qn.get("value"), qn.get("decimals", 0)
        if qv is None:
            continue
        exact_tol = 0.51 * (10 ** -qdec)
        if abs(cv - qv) <= exact_tol:
            return True
        if cdec >= qdec and round(qv, cdec) == round(cv, cdec):
            return True
    return False


def _units_compatible(a: str, b: str) -> bool:
    groups = [{"%", "percent"}, {"bn", "billion"}, {"mn", "million"}]
    for g in groups:
        if a in g and b in g:
            return True
    return False


# ---------------------------------------------------------- front-matter

def parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse a minimal YAML-ish front-matter block (no PyYAML).

    Supports: scalars, quoted strings, booleans, numbers, inline lists
    ``[a, b]`` and block lists. Returns (meta, body).
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end].strip("\n"), text[end + 4 :].lstrip("\n")
    meta: dict = {}
    key: Optional[str] = None
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"^\s+-\s*", line) and key is not None:
            item = re.sub(r"^\s+-\s*", "", line).strip().strip('"').strip("'")
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(_coerce_scalar(item))
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        key = k
        if v == "":
            meta[k] = []  # may be filled by block list lines
            continue
        if v.startswith("[") and v.endswith("]"):
            items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            meta[k] = [_coerce_scalar(i) for i in items]
        else:
            meta[k] = _coerce_scalar(v)
    return meta, body


def _coerce_scalar(v: str) -> Any:
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", "~"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


# ------------------------------------------------------------ markdown

def md_sections(text: str) -> dict[str, str]:
    """Map '## Heading' (level 2) -> section body text."""
    sections: dict[str, str] = {}
    current: Optional[str] = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip().casefold()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def count_bullets(section_text: str) -> int:
    n = 0
    for line in section_text.splitlines():
        if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line):
            n += 1
    return n


def truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


def domain_of(url: str) -> str:
    """Registered-ish domain key for origin counting."""
    m = re.match(r"^[a-z]+://([^/]+)", url or "")
    host = (m.group(1) if m else (url or "")).split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) > 2 and parts[-2] in {"co", "com", "org", "ac", "gov", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) > 2 else host


def load_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
