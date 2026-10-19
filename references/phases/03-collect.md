# Phase 3 — Collect

**So that:** every source in the ledger is *real, dated, archived and mapped to an angle* — no link-only bookmarks that rot before the report ships.

## Inputs

- `plan.md` (collection matrix, target sources, stop rules).
- Router (`search`) with learned source weights; `doctor` capability file.

## Procedure

1. **Run the matrix.** Use `search` per strategy with `--domains` and record results.
   The router handles source selection (ε-greedy over learned weights — you don't pick
   engines by hand unless overriding with `--source`).
   - Every connector search is logged automatically to `searches.jsonl` (SCH-####).
   - Manual searches (Google Scholar, Persian databases, site queries, hand-picked
     journals) **must** be logged too:
     `searchlog add --query "…" --engine scholar --hits 120 --kept 9 --angle "…"`.
   - `--angle` on `search` tags which angle the query served — the report's
     reproducibility block uses it.
2. **Triage then read.** Search results are *candidates*, not sources. Promote a
   candidate with `read` only if it plausibly carries evidence for ≥1 angle:
   - primary/official/peer-reviewed first (source map says where truth lives);
   - cherry-pick breadth per tier: don't let Tier-3 reads eat Tier-1 budget.
   - Exclusions are decisions too: `sources update --source-id SRC-000X --status excluded --exclude-reason "…"`.
     `status: screened` marks title/abstract-level candidates that were not read.
3. **`read` does the boring work** — fetch, extract (readability/PDF), snapshot to
   `sources/SRC-####.txt`, hash (SHA-256), metadata record. One `read` = one source.
   - Paywalled/unfetchable? `read --metadata-only` (abstract-level source; credibility
     will cap accordingly) — never fake a snapshot.
4. **Tag angles** at read time: `--angles "a;b"`. Coverage is checked here, and later
   fetched by the coverage table.
5. **Saturation check per angle** while budget remains: if 2 consecutive new reads add
   no new material evidence, mark the angle saturated in `plan.md` and reallocate.
6. **Budget discipline:** `search` and `read` increment counters; watch them with
   `status`. Stop at ceilings even if "one more source" looks tempting — synthesize,
   then note gaps.

## Artifacts

- `sources/SRC-####.json` + `sources/SRC-####.txt` (or `.html`), schema
  `references/schemas/source.schema.json`.
- `searches.jsonl` — the append-only search journal, schema
  `references/schemas/searchlog.schema.json`.
- `state.json.counters` updated (`searches`, `sources_read`).

```bash
$R search --query "…" --domains academic,web --limit 10 --angle "pricing"
$R searchlog add --query "site:oecd.org …" --engine google --hits 40 --kept 3 --angle "regulation"
$R read --url "https://…" --angles "pricing; adoption" --title "…" --published 2026-03-02
$R read --doi "10.1038/s41586-…" --angles "efficacy"
$R read --file ~/downloads/report.pdf --angles "cost"
$R sources update --source-id SRC-0004 --status excluded --exclude-reason "off-topic"
$R searchlog list
$R status
$R gate --phase 3
```

## Complete when (machine-checked by `gate --phase 3`)

- [ ] ≥2 sources recorded.
- [ ] Every source has `title`, `url` (or DOI), `accessed_at`, `tier`, `angles_covered` (≥1).
- [ ] Every source has `snapshot.path` + `snapshot.sha256` (metadata-only snapshot counts).
- [ ] Coverage: union of `angles_covered` ⊇ all brief angles — *or* a recorded
      `gate_waivers[]` entry naming the uncovered angle and why.
- [ ] `state.counters.sources_read` ≤ profile ceiling (or `budget_exceptions` recorded).
- [ ] Academic/PRISMA deliverables: ≥1 search logged (`search_logged`) and every
      excluded source carries a reason (`screening_reasons`).

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Candidate hoarding | 40 search hits, 2 reads | Triage by tier; read only evidence-carriers |
| Snapshot skipped | Source has URL only | Re-`read` it; metadata-only if unfetchable |
| Angle desert | An angle has zero sources | Re-query with synonym set, or waive visibly |
| Tier inflation | 8 blog posts, no primary source | Rebalance: primary first |

## Tips

- Search snippets often reveal *numbers* — if a snippet has your key stat, read that
  document next (priority read).
- One `read` with a multi-angle tag set beats three reads with single tags.
- Keep an eye on `source_stats.json` effects: consistently low-yield sources lose
  routing weight — that's learning doing its job.
