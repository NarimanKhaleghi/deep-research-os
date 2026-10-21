# Phase 7 — Synthesize

**So that:** verified claims become findings — argued, weighted, counter-pointed units of insight — not a dump of bullet points.

## Inputs

- `claims.jsonl` (classified), `contradictions.jsonl` (adjudicated/unresolved).
- `brief.md` deliverable + success criteria; angles = skeleton.

## Procedure

1. **Structure by angle** (or the deliverable's own logic): each finding answers one
   angle or one decision-relevant sub-question. If a finding doesn't serve the
   deliverable, it belongs in an appendix note — or nowhere.
2. **Every finding references claims** (`claims: [CL-0004, CL-0009]` in front-matter).
   Prose statements that assert facts outside claim refs are violations — turn them
   into claims or delete them.
3. **Tag the finding kind** (`--kind`): `analysis` (default), `model`, `scenarios`,
   `sensitivity`, `literature-matrix`, `methodology`, `conclusion`.
   - `academic-paper` deliverables **must** have `model`, `scenarios`, and
     `sensitivity` findings (gate `findings_kinds`); see
     `references/methods/decision-modeling.md`.
   - `academic-manuscript` deliverables use the manuscript gates instead; model
     findings are required only when the manuscript makes a computational claim.
   - `scenarios`: ≥5 scenarios including one combination scenario (two stressors at
     once), each with driver values, model output, decision change, and an
     early-warning indicator.
   - `sensitivity`: one-at-a-time variation of the top 3–5 variables with numeric
     breakpoints and a dominance ranking — not prose.
   - Any `decision-framework` or finding with equations also needs a validated
     `model.json` (`model check`): declared scope, sourced/assumption variables,
     equations, complete case inputs/outputs, baseline, comparators and
     sensitivity cases. See `references/methods/decision-modeling.md`.
4. **Key-study matrix** (academic deliverables): mark ≥ `key_studies_target` sources
   with `sources review --key` and fill all seven comparison fields — these render as
   the report's Literature Comparison Matrix and are the evidence for the gap claim.
5. **Strength & confidence:**
   - `strength`: how much the evidence supports it (`established | supported | tentative`).
   - `confidence`: `high | medium | low` — from source tiers, corroboration, and
     verification status. `weakly_supported` claims can never yield more than `tentative`.
6. **Counterpoints are mandatory fields**, even if empty (`[]`). Where refuting or
   contradicting evidence exists: state it, cite it, and say how the finding stands
   (outweighs / narrows scope / remains genuinely uncertain).
7. **Numbers stay faithful:** keep source precision in findings; rounding in prose is
   allowed only with `~` and must not exceed one significant digit of loss.
8. **Gap logging:** each finding ends with `gaps:` — what a skeptic would still want
   (missing region, vintage, methodology). These roll up into the report's Limitations.
   For a research-gap claim, point to the specific empty matrix cell(s) rather than
   asserting "few studies exist".
9. **Synthesis ordering rule:** conclusions must not depend on a single C-band source;
   if the story only works that way, the honest output is "insufficient evidence" —
   write *that* as the finding.

## Artifacts

- `findings/FN-01.md`, `FN-02.md`, … front-matter schema
  `references/schemas/finding.schema.json` (`id, title, strength, confidence,
  kind, claims[], counterpoints[], gaps[]`).

```bash
$R findings new --title "EU charging UX: queue pain dominates" \
                --strength supported --confidence medium --claims CL-0004,CL-0009 \
                --kind analysis --counterpoints "CX-0002 narrowed to urban networks"
$R findings new --title "Staged option value under five scenarios" \
                --claims CL-0012,CL-0015 --kind scenarios
$R model check
$R sources review --source-id SRC-0003 --key --problem "…" --framework "…" \
                  --method "…" --context "…" --findings "…" --limitations "…" \
                  --relevance "…"
# then write the body prose with [CL-xxxx] markers inline
$R gate --phase 7
```

## Complete when (machine-checked by `gate --phase 7`)

- [ ] ≥1 finding file with valid front-matter.
- [ ] Every finding: valid `id` (FN-##), `title`, `strength` ∈ enum,
      `confidence` ∈ enum, ≥1 `claims` entry — all existing claim IDs.
- [ ] `counterpoints` and `gaps` fields present (lists; empty allowed).
- [ ] ≥1 finding (the summary candidate) references only claims whose status is
      `supported` or `resolved`.
- [ ] No finding references a claim whose evidence was later invalidated
      (`contradicted` without resolution).
- [ ] Academic/PRISMA deliverables: ≥ `key_studies_target` key studies with
      complete review fields (`key_studies_reviewed`) and verified full text.
- [ ] `academic-paper`: `model`, `scenarios`, `sensitivity` findings exist
      (`findings_kinds`).
- [ ] Decision-framework/computational findings: `model check` passes with zero
      errors (scope, sources, comparator notes, complete inputs, exact outputs).
- [ ] `academic-manuscript`: `fulltext_coverage`, `fulltext_key_studies`,
      `fulltext_critical_claims` and `fulltext_integrity` pass.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Orphan prose | Facts in body not in any claim | Extract claims or drop sentences |
| Confidence inflation | `tentative` evidence → `high` | Tie confidence to verification classes |
| Counterpoint vacuum | `[]` everywhere with contradictory sources on file | Run counter-evidence sweep first |
| Kitchen-sink finding | Every angle in one blob | One finding = one question |

## Tips

- Write the finding's title as the **answer**, not the topic ("Queue pain dominates",
  not "Charging UX").
- A finding that survives its own counterpoint section is the real product of the run.
- If two findings overlap >50% in claims, merge them — the maintain loop will flag
  this pattern anyway.
