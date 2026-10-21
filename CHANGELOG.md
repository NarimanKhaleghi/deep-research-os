# Changelog

All notable changes to **deep-research-os** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [1.3.0] — 2026-10-20

The “rigor pack” release: computational models become reproducible artifacts,
comparators are audited for fidelity, and provenance is enforced at the claim
level.

### Added

- **Model cards** (`scripts/core/model_spec.py`, `references/schemas/model.schema.json`):
  project `model.json` with declared scope, variables, safe arithmetic
  equations, complete case inputs, exact outputs, baseline, comparators and
  sensitivity breakpoints. `model check` validates the card; reports fail on
  arithmetic drift, hidden inputs, unknown sources or missing comparator
  dimensions.
- **`model check` CLI** and report gates `model_artifact`,
  `model_scope_disclosed`; model sections in Markdown and HTML with variables,
  equations, cases, comparator fidelity, sensitivity and reproduction command.
- **Evidence depth** (`read_depth`, `read_at`): key studies require full-text
  reading in academic/decision-framework runs; `sources update --depth` records
  it, and the `evidence_depth` gate blocks abstract-only critical claims.
- **Numeric provenance**: `numeric_provenance` requires a dated source and
  locator for every numeric claim, plus a document/effective date for official
  normative sources; the report renders a provenance table.
- **Table citation audit**: numeric Findings tables must carry claim/source IDs
  or explicit assumption/derived markers.
- **Comparator fidelity**: every comparator is scored on cost of delay, staging
  and learning, with notes for missing capabilities and a required
  `where_it_differs` statement.
- **Automatic scope limitations** for single-stage, no-learning, heuristic and
  partially implemented-stage models.

### Changed

- `report_i18n.t()` accepts `default=`; EN/FA labels added for model scope,
  variables, equations, cases, provenance and evidence depth.
- Report order now includes Methodology evidence depth/provenance and an
  optional Model & Reproducibility section before Limitations.
- Version bumped to `1.3.0`; test suite is 53 tests, offline evals 8/8.

### Fixed

- Provenance gaps now apply the date check to non-numeric normative claims too.
- Model report-gate language resolution is independent of legacy `report_lang`
  state.

## [1.2.0] — 2026-10-20

The “research instrument” release: reports and the public site become bilingual,
self-contained, print-ready artifacts.

### Added

- **Bilingual report engine** (`report_i18n.py`): English/Persian detection from
  the brief/question (`--lang en|fa` to force), localized labels, headings,
  tables, gates, limitations and footer. `report build` records
  `state.report_lang`; requirement anchors resolve across language variants.
- **Claim & evidence appendix** in HTML and Markdown: every `CL-` claim links to
  its status, finding(s), quote, locator and `#ref-SRC-…` bibliography entry.
- **Self-hosted OFL fonts** (`assets/fonts/`): subset WOFF2 for Instrument Serif,
  Source Serif 4, Inter, IBM Plex Mono and Vazirmatn, embedded base64 into each
  report by `report_assets.py`. Reports stay offline and portable; Persian gets
  Vazirmatn with full Arabic/Persian shaping.
- **Direction A redesign** of `report.html.j2` / `report.md.j2`: paper-and-ink
  tokens, hero verification band, sticky TOC with scrollspy, finding cards,
  methodology grid, hanging-indent APA bibliography, dark mode, A4 print.
- **Bilingual landing site** (`site/`, built by `scripts/build_site.py` into
  `docs/`): `/` and `/fa/`, reciprocal hreflang, canonical URLs, per-language OG
  cards, JSON-LD (SoftwareApplication + FAQPage + HowTo), sitemap, robots,
  `llms.txt`, `.nojekyll`, a self-contained 404 and real EN/FA sample reports.
- **Site QA**: content hashing for CSS/JS cache busting, keyboard-scrollable
  command blocks, mobile menu, reduced-motion support, axe WCAG AA clean.

### Changed

- `report build` gains `--lang`; `report check` gates accept English and Persian
  section headings. The version fallback is now `1.2.0`.
- Test suite is 49 tests; offline evals are 8/8 (requirement coverage and
  normative overclaim scenarios included).
- The installer ignores `docs/` and `site/` so skill installs stay lean.

### Fixed

- Persian reports with legacy English requirement anchors no longer fail gate 8.
- Localized health-limitation lines could raise “multiple values for argument key”.
- Dark-theme printing produced light ink on white paper; print now forces the
  light palette.
- Long bibliography credential badges and long tokens overflowed on phones.
- The site install-copy buttons leaked Jinja dict methods into `data-*`
  attributes and rendered empty labels.

## [1.1.1] — 2026-10-19

Fixes found while validating v1.1.0 on the fintech research re-run:

### Fixed
- `verify` stamped `verify_report.generated_at` before updating claims, so the
  freshness gates (`verify_report_fresh`, `contradictions_scanned`) failed right
  after a verify pass. The timestamp is now taken after the claim loop, and the
  doc'd order (`verify` → `contradictions scan`) satisfies both gates.
- Bibliography printed the DOI twice when the source URL was the DOI link; URLs
  are deduplicated against the normalized DOI, and DOIs that arrive as full
  `https://doi.org/...` URLs are normalized before rendering.
- Report builder ignored the deduplicated URL from `bibmeta.apa_reference`.

## [1.1.0] — 2026-10-19

Hardening release driven by a real end-to-end run (fintech stage-gate research,
62% → target ≥85%): reproducibility, requirement coverage, normative-claim
discipline and bibliography quality are now machine-gated.

### Added

- **Output-location guard** — `init` refuses to write research projects inside
  the skill/repo/runtime tree; `--dir` creates the project exactly where the user
  wants it, `RESEARCH_OS_PROJECT` / direct paths are honored, and
  `project move --to <folder>` relocates existing projects.
- **Requirements ledger** (`requirements.json`, `RQ-##`) — every explicit prompt
  requirement is captured and must be mapped to an anchor that appears in the
  report or waived with a reason (waivers print in Limitations).
  `report build` hard-gates on unmet requirements; academic deliverables require
  ≥1 recorded requirement (phase-0 `requirements_recorded`).
- **Search journal** (`searches.jsonl`, `SCH-####`) — connector searches log
  automatically; manual/scholar searches via `searchlog add`. Academic/PRISMA
  phase 3 adds `search_logged` + `screening_reasons` (excluded sources need
  reasons). Reports render a search-and-screening (PRISMA-lite) block.
- **Screening & key-study fields on sources** — `status` (screened/included/
  excluded), `exclusion_reason`, `as_of`, venue/year/volume/issue/pages,
  `published_doi`/`preprint_doi`, `key_study` + seven comparison fields
  (`sources review`) rendered as the Literature Comparison Matrix.
- **APA-7 bibliography pipeline** (`sources enrich` via Crossref) — authors,
  year, venue, volume/pages, version notes flagging preprint/published DOI
  spread; academic `bibliography_complete` is a hard gate (title, authors/
  publisher, year, DOI for articles, journal venue).
- **Normative-claim discipline** — `claims add --kind empirical|normative|
  theoretical`; verify adds `modality_mismatches` (prohibition/obligation
  wording must appear in a supporting quote, EN+FA), `primary_source_gaps`
  (normative claims need official/primary sources) and `staleness_warnings`
  (official documents >18 months old); failing claims classify as
  `weakly_supported`.
- **Finding kinds** (`findings new --kind`) — academic deliverables must ship
  `model`, `scenarios` and `sensitivity` findings (`findings_kinds`) plus
  ≥ `key_studies_target` fully reviewed key studies (`key_studies_reviewed`,
  default 8).
- **New playbooks** — `references/methods/systematic-review.md` (PRISMA-lite)
  and `references/methods/decision-modeling.md` (operational models, ≥5
  scenarios incl. combination, sensitivity breakpoints, baseline comparison).
- **New schemas** — `requirements.schema.json`, `searchlog.schema.json`;
  extended source/claim/finding/run_state schemas.
- **New eval scenarios** — `requirement_coverage` (unmet requirement must block
  the report; waiver path must surface in Limitations) and `overclaim_modality`
  (prohibition claim without a normative quote must downgrade).

## [1.0.0] — 2026-10-18

### Added

- **10-phase research state machine** with machine-checkable *Complete-when* gates
  (scoping → landscape → planning → collection → extraction → verification →
  synthesis → reporting → retrospective).
- **Evidence Ledger** — append-only, file-locked JSONL journals for sources,
  evidence (verbatim quotes), claims, contradictions, findings and feedback.
  Every claim is traceable to a snapshot-backed source.
- **12 keyless source connectors** — OpenAlex, Crossref, arXiv, PubMed, Unpaywall,
  GDELT, World Bank, Data Commons, US Census, Wikidata, SEC EDGAR, Hacker News —
  plus a generic web fetcher with readability extraction. Zero API keys required.
- **Search router** with per-domain source statistics, Beta-smoothed weights and an
  ε-greedy exploration floor (never tunnel-visions; always keeps discovering sources).
- **Credibility scorer** — 6-dimension rubric (authority, peer-review, recency,
  evidence quality, conflicts of interest, retraction status) with score bands A–D.
- **Citation verification** — DOI resolution, title fuzzy-matching (rapidfuzz),
  URL liveness, Wayback fallbacks; FACT-style citation-precision metric.
- **Contradiction engine** — numeric-conflict and polarity-conflict detection across
  claims, plus a documented adjudication protocol.
- **Report builder** with hard quality gates: a report cannot ship with uncited
  findings or unverified citations unless explicitly flagged.
- **Source permanence** — local text/HTML snapshots with SHA-256 hashes so claims
  survive link rot and page edits.
- **Continuous Learning Engine** — fast per-run loop (feedback capture, source stats)
  and governed slow loop (champion/challenger, merge, retire, upstream discovery
  scans) with three governance levels (`auto | advisory | off`), human-in-the-loop
  preference elicitation, regression-tested applies and one-command revert.
- **Upstream scanner** — periodically searches GitHub, arXiv and skill marketplaces
  for new research tools/methods and produces a reviewable discovery report.
- **Eval harness** — 6 scenario suites with planted traps (fake citations, planted
  contradictions, number conflicts, multilingual), offline fixtures mode for CI and
  RACE/FACT/DRACO-aligned rubric methodology.
- **One-command installer** for Claude Code, OpenCode, Codex, Cursor and generic
  destinations, with environment doctor and capability detection.
- English and Persian READMEs, full reference documentation, JSON schemas, unit
  tests and a GitHub Actions CI workflow.
