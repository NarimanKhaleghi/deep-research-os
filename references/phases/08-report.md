# Phase 8 — Report

**So that:** the deliverable ships with zero silent corners: every statement cited, every number checked, every contradiction shown, every limitation stated.

## Inputs

- Findings, claims, sources, credibility scores, contradiction records.
- `brief.md` (deliverable shape, success criteria).

## Procedure

1. **Build** — `report build` renders `report.md` (+ `report.html` with embedded CSS)
   from the ledger: summary from the strongest findings, findings with claim/source
   annotations, contradiction table, methodology & coverage table, limitations,
   APA-7 bibliography (tied to `SRC-*`; includes snapshot hash), plus (when present)
   the Requirement Coverage table, the search & screening (PRISMA-lite) block, and
   the Literature Comparison Matrix.
2. **Satisfy the requirements contract** — `report build` refuses to pass while any
   RQ-## is unmet: map each requirement to a report section or finding id
   (`requirements map --requirement RQ-01 --target "Sensitivity analysis"`) whose
   tokens appear in the report, or waive it with a reason
   (`requirements waive --requirement RQ-03 --reason "…"`) — waivers print in
   Limitations. Academic deliverables additionally require complete bibliography
   metadata (authors/year/venue/DOI), via `sources enrich` when DOIs exist.
3. **Check** — `report check` runs the hard gates (below). Fix or waive; a waiver
   writes itself into the report's Limitations — silent waivers are impossible.
4. **Read it as the user.** Executive summary first: the 3–5 answers, confidence
   labels attached. If the summary needs the appendix to be true, the summary is wrong.
5. **Limitations section is mandatory and substantive**: gate waivers, requirement
   waivers, uncovered angles, single-origin critical claims, offline-verification
   mode, any refuted finding kept for completeness.
6. **Deliver** per profile: `quick`/`standard` → report + one-line confidence note;
   `deep`/`max` → report + coverage table walkthrough. If preference triggers are
   pending, this is when the A/B question is asked (never mid-task) — max per
   profile, via `learn pref ask`.

## Artifacts

- `report.md` and `report.html` in the project dir. Schema conventions:
  `templates/report.md.j2`, `templates/report.html.j2`.
- `state.ran.last_report_check_at` + recorded check results.

```bash
$R report build
$R report check                 # exit 1 if hard gate fails
$R report check --allow-flagged # downgrades named checks to warnings (recorded)
$R requirements map --requirement RQ-01 --target "Sensitivity analysis"
$R requirements waive --requirement RQ-04 --reason "prompt asked for paywalled dataset"
$R gate --phase 8
```

## Complete when (machine-checked by `gate --phase 8`)

- [ ] `report.md` exists; contains `## Executive Summary`, `## Findings`,
      `## Methodology`, `## Limitations`, `## Bibliography`.
- [ ] **Zero uncited findings:** every fact-bearing line in Findings carries
      `[CL-xxxx]` or `(SRC-xxxx)`.
- [ ] Every cited `CL-*`/`SRC-*` ID exists in the ledger; bibliography covers every
      referenced source at least once.
- [ ] Numeric consistency: numbers appearing in the report body match their claim
      records (string-level check against claim `numbers[]`).
- [ ] Every open contradiction appears in the contradictions table.
- [ ] Every `weakly_supported` claim shown as fact carries its label inline.
- [ ] No placeholder markers (`TODO`, `TBD`, `lorem`, `XXX`).
- [ ] `requirements_coverage`: every RQ-## mapped to an anchor present in the report
      or waived with a reason; academic deliverables have ≥1 requirement recorded.
- [ ] `bibliography_complete`: title + authors/publisher + venue/url for every
      non-excluded source (hard for academic: year, DOI, journal venue too).
- [ ] `report check` metrics recorded: `citation_precision`, `uncited_count=0`.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Summary overreach | Punchy summary, cautious appendix | Demote claims in summary to match |
| Phantom bibliography | Entries never cited | Prune; bibliography = cited sources only |
| Orphan round number | "60% of users" with no `[CL-]` | Find the claim or cut the number |
| Limitation theater | One generic sentence | List actual waivers/gaps from state |

## Tips

- Run `report check` early and often — it's a linter, not a final exam.
- The coverage table (angle × sources × tiers) is the fastest honesty check for
  "did we actually research this?"
- HTML report is self-contained — safe to email/archive as-is.
