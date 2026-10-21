# Source Catalog — 19 connectors (+ web/PDF)

Every connector below is free; `CORE` needs a free API key and is skipped without
one. Etiquette is enforced in code (descriptive User-Agent, backoff on 429/5xx,
conservative default limits). Domain tags: `academic · news · economics ·
statistics · entities · filings · tech · web`.

Conventions: `search(query, limit, offset)` returns normalized records
(`title, url, doi, authors, published, publisher, type, abstract, service, extra`).
`extra.is_oa`, `extra.pdf_url`, `extra.cited_by` and `extra.license` drive the
`--oa-only`, `--sort citations` and full-text resolver paths.

## Academic

### OpenAlex
- Base: `https://api.openalex.org/works?search=…&per-page=…&page=…` (+ `mailto=`).
- 240M+ works; `is_retracted`, citation counts, OA links in each record.
- Quirks: abstract is an inverted index — de-inverted by the connector; scores are
  relevance, not similarity — never present as confidence.

### Crossref
- Base: `https://api.crossref.org/works?query=…&rows=…&offset=…`.
- DOI metadata truth (publisher, year, container-title), update-to
  (retraction/correction) relations. Used by `verify` and `read --doi`.

### arXiv
- Base: `https://export.arxiv.org/api/query?search_query=…` (Atom XML).
- Preprints only: credibility rubric caps at B unless a peer-reviewed version is
  found (check DOI/`journal_ref`). Pagination via `start`.

### PubMed (E-utilities)
- `esearch.fcgi` → `esummary.fcgi` (JSON). Keyless ≤3 req/s.
- PMIDs, MeSH terms, retraction publication types. Pagination via `retstart`.

### Europe PMC
- Base: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`.
- Biomedical literature plus PMC JATS full text and preprints (`source=PPR`).
- `extra.pmcid` feeds the resolver’s `fullTextXML` path.

### DOAJ
- Base: `https://doaj.org/api/search/articles/{query}`.
- Peer-reviewed open-access journals; every record is OA. Pagination via `page`.

### Semantic Scholar
- Base: `https://api.semanticscholar.org/graph/v1/paper/search`.
- Citation graph and `openAccessPdf`; keyless but rate-limited. Pagination via
  `offset`.

### OpenAIRE
- Base: `https://api.openaire.eu/graph/v1/researchProducts`.
- Funded research outputs and repository records; `bestAccessRight` drives OA.

### Zenodo
- Base: `https://zenodo.org/api/records`.
- Open repository records, datasets and preprints. Pagination via `page`.

### HAL
- Base: `https://api.archives-ouvertes.fr/search/`.
- French open archive across disciplines; `openAccess_bool` drives OA.

### CORE
- Base: `https://api.core.ac.uk/v3/search/works`.
- Aggregated open-access repositories. Set `CORE_API_KEY` to enable; without it
  the connector returns an empty list (not a failure).

### Unpaywall — helper, not a search source
- `https://api.unpaywall.org/v2/{doi}?email=…` → legal OA PDF locations.
- Used by `read --doi` and `resolver` to find lawful full text.

## News & events

### GDELT 2.0 — `news`
- `https://api.gdeltproject.org/api/v2/doc/doc?query=…&mode=artlist&format=json`.
- Global, multilingual. `maxrecords` ≤250; dedupe syndications.

## Economics & statistics

### World Bank — `economics`
- `https://api.worldbank.org/v2/country/{iso}/indicator/{code}?format=json`.
- Indicator time series (200+ economies). Two-element JSON array `[meta, data]`.

### Data Commons — `statistics`
- `https://api.datacommons.org/v2/observation` (POST) or v1 fallback.
- Knowledge-graph statistics across government datasets.

### US Census — `statistics (US)`
- `https://api.census.gov/data/{year}/{dataset}?get=…&for=…`.
- ACS/decennial tables; keyless ≤500 queries/day. Rows are arrays with a header.

## Entities, filings, tech

### Wikidata — `entities`
- `https://www.wikidata.org/w/api.php?action=wbsearchentities…`.
- Disambiguation only: canonical names, HQ, parent orgs, IDs. Never the sole
  source for a disputed number.

### SEC EDGAR — `filings (US public cos)`
- `https://efts.sec.gov/LATEST/search-index?q=…` + submissions/XBRL APIs.
- Canonical upstream for public-company financials. Declared User-Agent mandatory.

### Hacker News (Algolia) — `tech`
- `https://hn.algolia.com/api/v1/search?query=…&tags=story`.
- Tier 3 lead generation only; promote to the linked primary source.

## Web & files (infrastructure, not “sources”)

- **`read --url`** — direct fetch + readability extraction (trafilatura) with
  snapshot + hash; the catch-all when no API covers it.
- **PDF/XML extraction** — PyMuPDF → `pdftotext` → pypdf ladder; page markers
  preserved so evidence locators can say “p.12”. JATS uses structured XML.
- **Local browser infra (optional)** — user’s SearXNG (`127.0.0.1:8888`) is a
  web-search shelf; results are candidates and must be `read` like anything else.

## Search filters and pagination

`search` supports `--all-academic`, `--per-source`, `--page`, `--year-from`,
`--year-to`, `--oa-only`, `--type` and `--sort relevance|citations|date`.
Filters apply after cross-service dedupe; `--all-academic` queries every enabled
academic connector (slower, broader) instead of the ε-greedy subset.

## Source tier → credibility ceiling (quick reference)

| Tier | Examples | Ceiling band* |
| --- | --- | --- |
| 1 | OpenAlex, Crossref, PubMed, Europe PMC, DOAJ, World Bank, Census, EDGAR | A |
| 2 | arXiv, GDELT, Wikidata, quality journalism | B (A with corroboration) |
| 3 | HN, blogs, forums | C–D (leads only) |

\* Ceiling assumes no COI and adequate recency; the rubric can lower it further.

## Rate-limit & failure notes

- All HTTP goes through `lib/http.py`: 15 s timeout, 2 retries with exponential
  backoff and jitter; 429 honours `Retry-After`; 5xx retries then falls down the
  ladder.
- Offline mode (`RESEARCH_OS_OFFLINE=1`) disables all network calls — connectors
  raise `OfflineError` and the phase doc’s offline path takes over.
- Every connector failure is logged to `state.source_health`; the report’s
  Limitations names degraded shelves honestly.
