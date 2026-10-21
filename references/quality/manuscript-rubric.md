# Manuscript Rubric

Hard checks are implemented in `scripts/core/manuscript.py` and surfaced by
`manuscript check` / `manuscript build`.

## Structure

- `draft_exists` — `manuscript/draft.md` exists and is non-empty.
- `imrad_sections` — Introduction, Methods, Results, Discussion, Conclusion,
  each ≥40 words.
- `title_length` — 4–30 words.
- `keywords` — 3–8.
- `metadata_complete` — authors, affiliations, funding, conflicts, data
  availability, ethics.

## Abstract

- `abstract_comprehensive` — `fulltext.assess_abstract` verdict
  `comprehensive`: ≥200 words, ≥3 structured components, numeric finding,
  no truncation.
- Venue abstract limit is enforced separately.

## Evidence and citations

- `citations_resolve` — every `SRC-####` exists.
- `citations_present` — at least one citation.
- `included_sources_cited` — at most `max(2, 20%)` included sources uncited.
- `key_studies_cited` — every key study cited.
- `numeric_claims_cited` — numeric body paragraphs carry a citation marker.
- `fulltext_coverage` — ≥80% verified, ≤20% abstract-only.
- `fulltext_key_studies` — 100% of key studies verified.
- `fulltext_critical_claims` — 100% of critical claims rest on verified text.
- `fulltext_integrity` — artifact/text/snapshot hashes agree.

## Hygiene

- `no_placeholders` — no TODO/TBD/FIXME/XXX/lorem/[insert.
- `reporting_guideline` — declared guideline checklist structurally covered
  (soft if none declared).
- `venue_profile` — style, limits, keywords and sections valid.
- `venue_warning` — soft warnings such as word count far below the limit.

## What still needs a human

- Whether the argument is novel and correct.
- Whether the statistical model is appropriate.
- Whether the limitations are complete.
- Whether the venue is the right fit.
- Whether the abstract overstates the results.
