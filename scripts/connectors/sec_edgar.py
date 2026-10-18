"""SEC EDGAR connector — full-text search + filings for US public companies (tier 1).

Canonical upstream for public-company financials. Declared User-Agent mandatory;
we send ours via lib.http. Docs: https://www.sec.gov/search-filings/edgar-search-assistance
"""

from __future__ import annotations

import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from connectors.base import dedupe, make_record  # noqa: E402
from lib import http  # noqa: E402

SERVICE = "sec_edgar"
DOMAINS = ["filings"]
TIER = 1
FTS = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS = "https://data.sec.gov/submissions"


def _filing_url(adsh: str, cik: str, file_id: str | None) -> str:
    acc = adsh.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
    return f"{base}/{file_id}" if file_id else f"{base}/{adsh}-index.htm"


def parse_hits(payload: dict) -> list[dict]:
    out = []
    hits = ((payload.get("hits") or {}).get("hits")) or []
    for h in hits:
        src = h.get("_source") or {}
        adsh = src.get("adsh") or h.get("_id", "").split(":")[0]
        file_id = h.get("_id", "").split(":")[1] if ":" in h.get("_id", "") else None
        names = src.get("display_names") or []
        ciks = src.get("ciks") or []
        cik = ciks[0] if ciks else "0"
        out.append(
            make_record(
                service=SERVICE,
                title=f"{names[0] if names else 'Filing'} — {src.get('root_form', 'form')} ({src.get('file_date', '')})",
                url=_filing_url(adsh, str(cik).lstrip("0") or "0", file_id),
                published=src.get("file_date"),
                publisher="SEC EDGAR",
                type_="filing",
                extra={"adsh": adsh, "form": src.get("root_form"), "cik": cik},
            )
        )
    return dedupe(out)


def search(query: str, limit: int = 10, forms: str = "", **kw) -> list[dict]:
    params = {"q": f'"{query}"', "dateRange": "custom"}
    if forms:
        params["forms"] = forms
    payload = http.get_json(FTS, params=params)
    return parse_hits(payload)[:limit]


_ACC_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def company_filings(cik: str, limit: int = 20) -> list[dict]:
    """Recent filings for a CIK (from the submissions JSON)."""
    cik10 = str(cik).zfill(10)
    try:
        payload = http.get_json(f"{SUBMISSIONS}/CIK{cik10}.json")
    except Exception:
        return []
    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    out = []
    for f, d, a in list(zip(forms, dates, accs))[:limit]:
        out.append(
            make_record(
                service=SERVICE,
                title=f"{payload.get('name', cik)} — {f} ({d})",
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}&type={f}",
                published=d,
                publisher="SEC EDGAR",
                type_="filing",
                extra={"cik": cik10, "form": f, "accession": a},
            )
        )
    return dedupe(out)
