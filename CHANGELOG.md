# Changelog

All notable changes to **deep-research-os** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

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
