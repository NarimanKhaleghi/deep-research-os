# Quality Gates — master list

Machine-checkable gates per phase, plus the hard report gates. This file is the
**contract**: `scripts/research_ctl.py gate` implements exactly these checks;
if code and doc disagree, that's a bug (fix in the same PR, per CONTRIBUTING).

## Phase gates

### Phase 0 — Intake
- `brief.md` front-matter: `question`, `title` non-empty; `profile` valid;
  `cutoff` ISO date; `deliverable` non-empty; `success_criteria` ≥1; `angles` ≥2;
  `maintenance` ∈ {ok,due}; `privacy_mode` boolean.
- Budget ceilings present in `state.json` (defaults per profile, or declared for max).

### Phase 1 — Landscape
- `plan.md` sections with minimum bullets: Terminology ≥5 · Actors ≥3 ·
  Source Map ≥2 · Initial Queries ≥2.
- Every brief angle string appears in `plan.md` (case/whitespace-insensitive).

### Phase 2 — Plan
- `## Collection Matrix` ≥ 2×angles bullet/table lines.
- `## Target Sources` ≥1 bullet · `## Stop Rules` ≥1 bullet · every angle in matrix.

### Phase 3 — Collect
- ≥2 sources; each: `title`, `url|doi`, `accessed_at`, `tier`, `angles_covered` ≥1,
  `snapshot.path` + `snapshot.sha256`.
- Coverage union ⊇ brief angles, or a `gate_waivers[]` entry names the missing angle.
- `sources_read` ≤ ceiling or `budget_exceptions[]` recorded.
- **Academic / PRISMA deliverables add:**
  - `search_logged` — `searches.jsonl` has ≥1 entry (connector searches log
    automatically; manual ones via `searchlog add`).
  - `screening_reasons` — every source carries a `status` ∈ {screened, included,
    excluded}; every excluded source has `exclusion_reason`.

### Phase 4 — Extract
- ≥1 evidence; each: valid `source_id`, non-empty quote + locator,
  `relevance` ∈ {supports, refutes, contextual, methodological},
  `angle` ∈ brief angles, quote present in snapshot (fuzzy ≥0.95 normalized),
  offsets consistent when snapshot is text.

### Phase 5 — Assess
- All sources scored 0–100 with band ∈ {A,B,C,D}; ≥1 source in A∪B.
- `retraction.checked_at` present for every DOI-bearing source.
- `state.ran.last_credibility_at` ≥ newest source `accessed_at`.

### Phase 6 — Verify
- `verify_report.json` exists, newer than newest claim; contains citation precision
  + fabrication list + corroboration gaps + modality mismatches + primary-source
  gaps + staleness warnings.
- Every claim: valid `evidence_ids`; `status` ∈ {unverified→(fail), supported,
  weakly_supported, contradicted, unverifiable, resolved}; critical claims have
  ≥2 origins or explicit weak-labels.
- Normative claims (`kind: normative` or prohibition/obligation phrasing): a
  supporting quote must contain normative language (`modality_mismatches`), and an
  official/primary source (regulation, statistics, central bank) must be present
  (`primary_source_gaps`); official documents older than 18 months yield
  `staleness_warnings`.
- Contradictions: scan ran after last claim change; `contradicted` claims link a CX;
  every CX `adjudicated` or `open` with reason.
- Zero unacknowledged number mismatches.

### Phase 7 — Synthesize
- ≥1 `findings/FN-##.md`; front-matter: `id`, `title`, `strength` ∈
  {established, supported, tentative}, `confidence` ∈ {high, medium, low},
  `kind` (default `analysis`), `claims` ≥1 all existing; `counterpoints[]` +
  `gaps[]` present.
- Every finding cites no contradicted-unresolved claim as support.
- **Academic / PRISMA deliverables add:**
  - `findings_kinds` — at least one `model`, one `scenarios`, and one
    `sensitivity` finding (`findings new --kind …`).
  - `key_studies_reviewed` — ≥ `state.key_studies_target` sources marked
    `key_study` (default 8 for academic-paper), each with complete `review`
    fields (problem, framework, method, context, findings, limitations,
    relevance) via `sources review`.

### Phase 8 — Report
- `report.md` exists with sections: Executive Summary, Findings, Methodology,
  Limitations, Bibliography.
- **Zero uncited findings** — every fact-bearing line in Findings has `[CL-####]`
  or `(SRC-####)`; all IDs exist; bibliography ⊇ cited sources.
- Numbers in told claims match claim records; no placeholders (TODO/TBD/lorem/XXX).
- Open contradictions appear in the contradiction table; weak claims labeled.

### Phase 9 — Retrospect
- `retrospective.json` with `worked[]`, `failed[]`, `budget_used{}`, `metrics{}`,
  `suggestions[]`, `capability_candidate` (null|object).
- ≥1 feedback entry for the project OR `feedback_skipped: true` + reason.
- Source stats updated for all evidence-yielding sources; preference budget
  respected (`preferences_asked` ≤ profile cap).

## Hard report gates (subset enforced at phase 8, re-runnable anytime)

1. All ledger IDs referenced in the report exist.
2. Zero uncited fact-bearing lines in Findings.
3. Bibliography covers every source cited anywhere in the report.
4. Numbers: claim-record consistency for every `numbers[]`-bearing claim shown.
5. No placeholder markers.
6. Contradiction visibility: every open CX appears in the table.
7. Weak-claim labeling inline.
8. Limitations section non-empty and non-generic (must mention every waiver in
   `state.gate_waivers[]`, requirement waivers, and any source_health failures).
9. `requirements_coverage` — every RQ-## in `requirements.json` is either
   **mapped** with an anchor whose tokens appear in report.md, or **waived** with
   a reason (waivers print in Limitations). Academic deliverables must have ≥1
   requirement recorded.
10. `bibliography_complete` — every non-excluded source has title,
    authors/publisher, and venue/publisher/url. **Hard** for academic
    deliverables, where it additionally requires year, DOI for
    journal/conference/preprint types, and a journal venue for journal articles.

`--allow-flagged` converts gates 4–7 to warnings **and writes each downgrade into
the report's Limitations**; gates 1–3 and 9–10 are never downgradable (fix the
files or waive the specific requirement with a reason).

## Waivers

Environment-limited passes (offline run, no PDF tooling) are recorded as:

```json
{"phase": 4, "check": "pdf_page_locators", "reason": "pdftotext unavailable; paragraph locators used", "at": "…"}
```

in `state.gate_waivers[]` and automatically surfaced in report Limitations.
A waiver never silences a gate for *future* runs of the same project — it is
per-project, with the reason visible.
