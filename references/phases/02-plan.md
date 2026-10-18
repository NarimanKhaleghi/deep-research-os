# Phase 2 — Plan

**So that:** collection is systematic — every angle has ≥2 independent query strategies, every query has a target shelf, and stopping is planned, not improvised.

## Inputs

- `plan.md` (landscape sections), `brief.md` (angles, ceilings), method doc.

## Procedure

1. **Build the collection matrix** — the core artifact of this phase:

   | Angle | Strategy A (broad) | Strategy B (deep/targeted) | Target sources |
   | --- | --- | --- | --- |
   | … | phrasing 1 + engine | phrasing 2 + filters | OpenAlex, GDELT, official stats |

   ≥2 *independent* strategies per angle. "Independent" = different phrasing basis
   or different source family — if both die together, the angle is uncovered.
2. **Target sources per angle** — name the 2–4 shelves you will read (not just search):
   e.g., *OpenAlex + Crossref for academic; regulator site + World Bank for numbers*.
3. **Define stop rules** — when is an angle *done*? Options: saturation (3 consecutive
   sources add no new claims), budget ceiling, or sufficiency (success criteria met).
   Write the rule per angle.
4. **Budget allocation** — split the profile ceilings across angles (e.g., deep: ~8
   sources → 2–3 per angle). Record in the matrix; `state.json` counters enforce totals.
5. **Fallback ladder per shelf** — MCP → local infra → keyless connector → web fetch
   (protocol §9). Decide which applies before you start, so degradation is quick.

## Artifacts

- `plan.md` extended: `## Collection Matrix`, `## Target Sources`, `## Stop Rules`,
  `## Budget Split`. Front-matter: `planned_at`, `queries[]`.

```bash
$R plan set-section collection-matrix --content "…markdown table…"
$R gate --phase 2
```

## Complete when (machine-checked by `gate --phase 2`)

- [ ] `## Collection Matrix` — ≥ 2 × (number of brief angles) bullet/table lines.
- [ ] `## Target Sources` — ≥1 bullet; every angle named in matrix rows.
- [ ] `## Stop Rules` — ≥1 bullet (a global rule is acceptable if per-angle is implicit).
- [ ] Every brief angle string appears in the matrix section.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Correlated strategies | Same query on two engines | Vary phrasing basis and source family |
| No stop rule | "I'll know when I'm done" | Write saturation/sufficiency rule now |
| Budget blind | All remaining budget → first angle | Allocate per angle upfront |
| Loophole ladder | Nothing about when tools die | Map fallback per shelf explicitly |

## Tips

- The matrix is also your *report coverage table skeleton* — angles as rows pay off twice.
- Saturation is measurable: track new-claim rate per source during phase 3; drop an
  angle when it flatlines (record in `plan.md` and move on).
