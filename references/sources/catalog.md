# Source Catalog — the 12 keyless connectors (+ web/PDF)

Every connector below is **free and keyless**. Etiquette is enforced in code
(descriptive User-Agent, backoff on 429/5xx, conservative default limits).
`classify()` in the router reads this file's tags; keep tags in sync.

Conventions: `search(query, limit)` returns normalized records
(`title, url, doi, authors, published, publisher, type, abstract, service, extra`).
Domain tags: `academic · news · economics · statistics · entities · filings ·
tech · web`.

---

## Academic

### 1. OpenAlex — `academic` · tier 1
- Base: `https://api.openalex.org/works?search=…&per-page=…` (+ `mailto=` polite pool).
- 240M+ works; `is_retracted`, citation counts, OA links in each record.
- Limits: ~10 req/s polite; we cap 5 req/s with backoff.
- Quirks: abstract is inverted index — de-inverted by the connector; scores are
  relevance, not similarity — never present as confidence.

### 2. Crossref — `academic` · tier 1
- Base: `https://api.crossref.org/works?query=…&rows=…`.
- Best for: DOI metadata truth (publisher, year, container-title) and update-to
  (retraction/correction) relations. Used by `verify` for DOI resolution.
- Limits: polite pool via `mailto`; 50 req/s shared — we stay far below.

### 3. arXiv — `academic (preprints)` · tier 2
- Base: `http://export.arxiv.org/api/query?search_query=…` (Atom XML).
- Preprints only: credibility rubric caps at B unless peer-reviewed version found
  (check DOI/`journal_ref`).
- Rate: 1 req / 3 s sustained — the connector enforces a sleep.

### 4. PubMed (E-utilities) — `academic (biomed)` · tier 1
- Base: `esearch.fcgi` → `efetch` (JSON/XML). Keyless ≤3 req/s.
- Provides PMIDs, MeSH terms (great for building synonym sets), retraction flags
  via `pubmed` publication type ("Retracted Publication").

### 5. Unpaywall — `academic (OA links)` · helper, not a search source
- `https://api.unpaywall.org/v2/{doi}?email=…` → legal OA PDF locations.
- Used by `read --doi` to find an open full text before giving up.

## News & events

### 6. GDELT 2.0 — `news` · tier 2 (context; tier 1 for *existence of coverage*)
- Base: `https://api.gdeltproject.org/api/v2/doc/doc?query=…&mode=artlist&format=json`.
- Global, multilingual (works for Persian queries). Tone/`sourcelang` fields.
- Quirks: `maxrecords` ≤250; timespan syntax (`7d`, `24h`); dedupe near-identical
  syndications (router drops same-title clusters).

## Economics & statistics

### 7. World Bank — `economics` · tier 1
- Base: `https://api.worldbank.org/v2/country/{iso}/indicator/{code}?format=json`.
- Indicator time series (200+ economies). Great for anchoring macro numbers with
  a primary, citable source instead of news figures.
- Quirks: two-element JSON array `[meta, data]`; pagination via `page=`.

### 8. Data Commons — `statistics` · tier 1
- Base: `https://api.datacommons.org/v2/observation` (POST) or v1 fallback.
- Knowledge-graph statistics across gov datasets; optional API key raises limits —
  keyless path kept as default.
- Used for: population/GDP/health/energy series by place & time.

### 9. US Census — `statistics (US)` · tier 1
- Base: `https://api.census.gov/data/{year}/{dataset}?get=…&for=…`.
- ACS/decennial tables; keyless ≤500 queries/day — fine for research profiles.
- Quirks: rows are arrays with a header row; connector converts to dicts.

## Entities, filings, tech

### 10. Wikidata — `entities` · tier 2 (tier 1 for *identity/relationships*, not facts-under-dispute)
- Base: `https://www.wikidata.org/w/api.php?action=wbsearchentities…` plus entity fetch.
- Use for disambiguation: canonical names, HQ locations, parent orgs, IDs
  (LEI, ISIN, ticker) to anchor other queries. Never the sole source for numbers.

### 11. SEC EDGAR — `filings (US public cos)` · tier 1
- Base: `https://efts.sec.gov/LATEST/search-index?q=…` (full-text) and
  submissions JSON per CIK. Company facts API for XBRL numbers.
- The canonical upstream for public-company financials — prefer over press releases.
- Etiquette: declared User-Agent mandatory (we send one); ≤10 req/s.

### 12. Hacker News (Algolia) — `tech` · tier 3 (lead generation only)
- Base: `https://hn.algolia.com/api/v1/search?query=…&tags=story`.
- Early signal for tooling/technologies; discussions point to primary sources.
- Never load-bearing; always promote to the linked primary source before citing.

## Web & files (infrastructure, not "sources")

- **`web fetch`** — direct fetch + readability extraction (trafilatura) with
  snapshot + hash; the catch-all when no API covers it.
- **`pdf extract`** — PyMuPDF → `pdftotext` → pypdf ladder; page markers preserved
  so evidence locators can say "p.12".
- **Local browser infra (optional)** — user's SearXNG (127.0.0.1:8888) is used as
  a *web search* shelf when detected; results are candidates only and must be
  `read` like anything else.

## Source tier → credibility ceiling (quick reference)

| Tier | Examples here | Ceiling band* |
| --- | --- | --- |
| 1 | OpenAlex, Crossref, PubMed, World Bank, Census, EDGAR, Data Commons | A |
| 2 | arXiv, GDELT, Wikidata, quality journalism | B (A with corroboration) |
| 3 | HN, blogs, forums | C–D (leads only) |

\* Ceiling assumes no COI and adequate recency; the rubric can lower it further.

## Rate-limit & failure notes (operational)

- All HTTP goes through `lib/http.py`: 15 s timeout, 2 retries with exponential
  backoff, jittered; 429 → honor `Retry-After`; 5xx → single retry then fall down
  the ladder (protocol §9).
- Offline mode (`RESEARCH_OS_OFFLINE=1`) disables all network calls — connectors
  raise `OfflineError` and the phase doc's offline path takes over.
- Every connector failure is logged to the run's `state.json.source_health` so the
  report's Limitations can name degraded shelves honestly.
