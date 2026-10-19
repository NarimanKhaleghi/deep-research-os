# Changelog

All notable changes to **deep-research-os** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

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
