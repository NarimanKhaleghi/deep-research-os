# Phase 1 — Landscape

**So that:** you search like someone who knows the territory — right vocabulary, right actors, right sources — instead of with the user's first phrasing only.

## Inputs

- `brief.md` (question + angles).
- Domain method doc (`references/methods/<domain>.md`) — read it *now*, before planning.

## Procedure

1. **Vocabulary sweep.** List ≥5 key terms, and for each its synonyms, acronyms,
   and — when the topic spans regions — translations (e.g., FA: «خودروی برقی»,
   «شارژ سریع»). Search in ≥1 non-English language when the topic has non-English
   substantive literature. Ledger searches count against budget: batch them.
2. **Actors map.** ≥3 named actors: institutions, companies, agencies, researchers,
   datasets. These become source targets and corroboration anchors.
3. **Source map.** Per angle: where does authoritative information *live*? Official
   statistics, regulator filings, peer-reviewed venues, industry associations, etc.
   Prefer primary > secondary > tertiary.
4. **Initial queries.** ≥2 concrete queries per angle (exact strings, operators
   included). These seed phase 2's matrix; bad queries here waste collection budget.
5. **Known-unknowns snapshot.** 3–5 open questions the landscape raised — these often
   sharpen the angles before locking the plan.

## Artifacts

- `plan.md` — sections `## Terminology`, `## Actors`, `## Source Map`,
  `## Initial Queries`, `## Known Unknowns`. Schema: `references/schemas/plan.schema.json`.

```bash
$R plan set-section terminology --content "…bullets…"   # helper writes the section
$R gate --phase 1
```

## Complete when (machine-checked by `gate --phase 1`)

- [ ] `plan.md` exists with parseable front-matter.
- [ ] `## Terminology` — ≥5 bullets.
- [ ] `## Actors` — ≥3 bullets.
- [ ] `## Source Map` — ≥2 bullets.
- [ ] `## Initial Queries` — ≥2 bullets.
- [ ] Every brief angle string appears somewhere in `plan.md` (case-insensitive).

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Monolingual tunnel | FA topic searched only in English | Add native-language queries + sources |
| Acronym soup | "SHAP" assumed known | Expand every acronym once in Terminology |
| Source poverty | Only "google it" | Name the 3–4 authorities per angle |
| Actor bias | Only vendors listed | Add regulators, academics, critics |

## Tips

- The best query strings often come from the literature itself — after the first
  search, harvest terminology from titles/abstracts and re-query.
- Actors become `## Source Map` rows; regulators and official stats usually anchor
  the numbers your report will need.
