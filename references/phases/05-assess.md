# Phase 5 — Assess

**So that:** every source carries a transparent, rubric-based credibility score — so claims can be weighted, not just counted.

## Inputs

- `sources/SRC-*.json` (all collected sources).
- Rubric: `references/quality/credibility-rubric.md`.

## Procedure

1. **Score every source** with `credibility score` — the scorer applies the
   six-dimension rubric heuristically (authority, peer-review, recency vs half-life,
   evidence quality, conflicts of interest, retraction/integrity) and proposes
   dimensions + band. You review and **override with justification** when context
   beats heuristics (e.g., regulator blog vs journal article on policy).
2. **Check retraction/integrity** for every academic source: OpenAlex `is_retracted`,
   Crossref `update-to` relations. A retracted source caps at **D** and its claims
   become `contradicted`-candidates at verify time.
3. **Record conflicts of interest** explicitly (funded by the vendor being evaluated,
   advocacy org, etc.) — it is a dimension, not a footnote.
4. **Apply recency by half-life** — the rubric defines half-lives per domain (e.g.,
   ML benchmarks ~18 months; legal texts ~decades). A 2019 number in a fast domain
   must lose points even if famous.
5. **Tier sanity pass**: tier comes from the source map (primary/secondary/tertiary),
   score comes from the rubric — they should roughly agree. Big disagreements go in
   the source `notes` for the report's methodology section.

## Artifacts

- `sources/SRC-*.json.credibility` filled: `{score, band, dimensions{}, rationale,
  scored_at, overrides[]}`. Bands: A ≥85 · B 70–84 · C 55–69 · D <55.
- Counter/marker `state.ran.last_credibility_at`.

```bash
$R credibility score                 # scores all unscored sources
$R credibility show SRC-0003         # full breakdown
$R gate --phase 5
```

## Complete when (machine-checked by `gate --phase 5`)

- [ ] Every source has `credibility.score` (0–100) and `credibility.band` ∈ {A,B,C,D}.
- [ ] ≥1 source at band A or B (a run anchored entirely in C/D cannot pass gates later).
- [ ] Retraction status recorded for all sources with DOI (`retraction.checked_at`).
- [ ] `state.ran.last_credibility_at` newer than the newest source `accessed_at`.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Uniform scores | Everything 80 | Actually read rationale; heuristics flagged it |
| Prestige bias | Nature paper scored A on topic it doesn't cover | Score *fit to this question*, not venue halo |
| COI blindness | Vendor-funded study scored A | Apply the conflict-of-interest dimension |
| Stale anchor | 2018 number starring in 2026 decision | Half-life penalty + find a fresher corroboration |

## Tips

- The score is *for routing evidence*, not for judging the source's general worth.
- When two sources disagree, credibility difference is your first adjudication lever
  (see `quality/contradiction-protocol.md`).
- Overriding the rubric is allowed and encouraged — but `overrides[]` must say why;
  the learning loop reads these.
