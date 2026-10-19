# Method — Systematic Review (PRISMA-lite, reproducible)

Read this before phase 2 for any `deliverable_type: academic-paper`, or whenever
`review_protocol` is `prisma` / `systematic-review`. The point of this playbook is
that **every number in the report's review section is reconstructible from the
project files** — a reader can replay your searches, screening decisions, and
key-study extractions without trusting prose.

## When to use
- The deliverable is a paper, systematic review, or evidence synthesis.
- The prompt demands a "systematic review", "PRISMA", "gap analysis grounded in prior work".
- Multiple competing schools/studies must be compared on fixed dimensions.

## Hard rules (enforced by gates)
- Phase 3 adds `search_logged` and `screening_reasons` (hard) when the project is
  academic (`deliverable_type: academic-paper` or `review_protocol: prisma`).
- Phase 7 adds `findings_kinds` (a `model`, a `scenarios`, and a `sensitivity`
  finding must exist) and `key_studies_reviewed` (default 8 key studies, all
  comparison fields filled).
- `report build` adds `requirements_coverage` (hard) and `bibliography_complete`
  (hard in strict mode — authors/year/venue/DOI per source).

## Procedure
1. **Intake — extract requirements verbatim** (phase 0):
   `requirements add --text "..."` for every explicit constraint in the prompt
   (counts, scenario minimums, citation style, word range, theory to use).
   These become RQ-01… and are checked against the final report.
2. **Protocol declaration** (phase 2, `plan.md`): record the review protocol,
   inclusion/exclusion criteria, constructs, and the synonym/term ledger before
   searching. If you change criteria later, note the amendment — do not silently
   move goalposts.
3. **Search transparently** (phase 1→3):
   - Connector searches log automatically (`searchlog list` shows SCH-####).
   - Manual searches (Google Scholar, site-specific, Persian-language databases,
     hand-picked journals) **must** be recorded: `searchlog add --query "..." --engine scholar --hits 120 --kept 9 --angle "..."`.
   - Snowballing counts as a search too: record seed IDs and what you mined.
4. **Screen with reasons** (phase 3):
   - Every kept source is `status: included` by default (set by `read`).
   - Excluding a candidate? `sources update --source-id SRC-000X --status excluded --exclude-reason "off-topic: no regulatory angle"`.
   - `status screened` = seen at title/abstract stage but not read; use it for
     counts, not for load-bearing claims.
5. **Key-study extraction** (phase 4→6): for each of the target key studies
   (≥ `key_studies_target`):
   - `sources enrich --source-id SRC-000X` (Crossref metadata: authors, venue, year, pages, published DOI — fixes "mdpi.com (n.d.)" bibliography entries).
   - `sources review --source-id SRC-000X --key --problem "..." --framework "..." --method "..." --context "..." --findings "..." --limitations "..." --relevance "..."`.
   - The literature matrix in the report renders exactly these fields — no
     blank cells (gates treat missing fields as failures).
6. **Citation hygiene** (phase 6):
   - Prefer the published version of record; Crossref enrichment sets
     `published_doi` and flags `preprint_doi` so versions are not silently mixed.
   - Normative/regulatory statements are claims with `--kind normative`; they
     require an official/primary source (regulation, statistics bureau, central
     bank) or `verify` downgrades them and lists them under `primary_source_gaps`.
   - Statements about what a regulator *prohibits or requires* must have a quote
     containing normative language — otherwise `modality_mismatches` fires.
   - Check document dates (`--as-of`); normative claims resting on documents
     older than 18 months get `staleness_warnings`.
7. **Synthesize by divergence** (phase 7): compare key studies on the matrix
   dimensions; the gap claim must name the specific comparison cell that is
   empty/contradictory. "Few studies exist" is not a gap; "no study combines
   stage-gating with real options under FX+regulatory uncertainty in Iran
   (cells X/Y/Z empty across all 8 key studies)" is.
8. **Report** (phase 8): the review section must state the funnel counts
   (found → screened → included/excluded with reasons → read → key studies),
   sourced from `searchlog list` and the screening statuses — never from memory.

## PRISMA-lite counts (what the report prints)
- Identified: sum of `hits` across log entries.
- Screened / excluded: source `status` counts + exclusion reasons table.
- Included: sources read (`status: included`).
- Key studies: `key_study` sources with complete review fields.
If a number cannot be produced from the ledger, say so — do not estimate.

## Failure modes to avoid
- Two parallel bibliographies (preprint DOI in one claim, journal DOI in another) → use `sources enrich` + `version_note`.
- Overclaiming prohibition: "the regulator does not allow X" when the source says "banks bear responsibility" — modality check catches this; rewrite to the source's actual claim.
- Screening theatre: logging only the searches that worked. Log failures too (`notes`), they belong in Limitations.
