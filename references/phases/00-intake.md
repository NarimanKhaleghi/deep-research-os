# Phase 0 — Intake & Scoping

**So that:** the run has a sharp question, an explicit deliverable, and declared budgets before any searching happens. Most bad research fails here, not at search time.

## Inputs

- The user's request (verbatim), plus any context they volunteered.
- `~/.config/deep-research-os/` learning state (for maintenance-due check).
- Existing projects via `status` (is this a continuation?).

## Procedure

1. **Restate the question** in one sentence. If the request is ambiguous, formulate the
   single most likely interpretation *plus* a proposed default and confirm **once** —
   never resume the run on an unconfirmed guess.
2. **Decompose into 2–6 angles** (sub-questions) that, answered together, answer the
   top question. Angles must be checkable (each will get sources, evidence, and claims).
3. **Define the deliverable**: memo / briefing / literature review / dataset summary /
   decision table. Match report structure to it later. Set `deliverable_type`
   (`report|academic-paper|decision-framework|memo|osint-brief|dataset`); for
   academic papers also set `review_protocol: prisma` (default when the type is
   academic-paper) and `key_studies_target` (default 8).
4. **Extract requirements verbatim** — every explicit constraint in the prompt
   (scenario minimums, required steps, citation style, word range, theory to use)
   becomes an RQ-## entry. The report gate refuses to pass until each is mapped to
   an anchor that appears in the report or waived with a reason. This is the step
   that prevents long prompts from silently losing requirements.
5. **Choose the output folder before `init`** — research belongs in the user's
   folder (`~/Research/<slug>` etc.), never inside the skill installation. Pass
   `--dir` or run from the target vault; `init` refuses to write into the
   skill/repo/runtime directories. Registered projects are found automatically
   afterwards (or via `--project <path>` / `$RESEARCH_OS_PROJECT`).
6. **Set success criteria** (≥1): what must be true for this run to be *useful*
   ("all key numbers have ≥2 independent sources"; "covers EU + US markets"; etc.).
7. **Set the research cutoff** (today, or user-specified date). Sources newer than the
   cutoff are out of scope; historical depth is bounded by the method doc.
8. **Choose the profile** (`quick|standard|deep|max`) and let it set budget ceilings.
   For `max`, write explicit ceilings yourself — deferred ceilings are a protocol violation.
9. **Check maintenance-due** (`learn status`): if the maintain cycle is due, say so in
   the brief and *offer* (don't force) a maintenance pass after the run.
10. **Privacy check** — if the topic is sensitive (medical, legal, HR, personal), set
    `privacy_mode: true` (snapshots stay local; no cloud/MCP submission).

## Artifacts

- `brief.md` — front-matter is the machine contract; body is the narrative for humans.
  Schema: `references/schemas/brief.schema.json`.
- `state.json` initialized (counters zeroed, ceilings recorded).
  Schema: `references/schemas/run_state.schema.json`.
- `requirements.json` — one entry per explicit requirement.
  Schema: `references/schemas/requirements.schema.json`.

```bash
R="python scripts/research_ctl.py"
$R init "question…" --profile deep --title "Short title" \
     --dir ~/Research/short-title --deliverable-type academic-paper
$R brief set --angles "angle one; angle two; angle three" \
             --deliverable "decision memo" \
             --cutoff 2026-10-18 \
             --success "key numbers corroborated; EU+US coverage"
$R requirements add --text "At least five scenarios including a combination scenario"
$R requirements add --text "APA-7 bibliography with DOIs"
$R gate --phase 0
```

## Complete when (machine-checked by `gate --phase 0`)

- [ ] `brief.md` exists with parseable front-matter.
- [ ] `question` non-empty; `title` non-empty.
- [ ] `profile` ∈ {quick, standard, deep, max}; `state.json.profile` matches.
- [ ] `cutoff` set (ISO date).
- [ ] `deliverable` non-empty.
- [ ] `success_criteria` has ≥1 item.
- [ ] `angles` has ≥2 items.
- [ ] `deliverable_type` recorded (default `report`); academic papers record
      `review_protocol` and `key_studies_target`.
- [ ] Academic deliverables: ≥1 requirement captured (`requirements_recorded`).
- [ ] Project lives outside the skill/repo/runtime tree (`init --dir` guard — not a
      gate check, enforced at init time).
- [ ] `maintenance` ∈ {ok, due} recorded (from `learn status`).
- [ ] `privacy_mode` boolean present.
- [ ] Budget ceilings recorded in state (profile defaults or declared for `max`).

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Fuzzy question | "research AI in education" | Force one-sentence restatement + angles |
| Hidden deliverable | No idea what output shape user wants | Ask once; propose default memo |
| Angle sprawl | 9 angles for a `standard` run | Merge; keep 2–6 |
| Unbounded `max` | "take as long as you need" | Declare ceilings explicitly |

## Tips

- Angles are your future coverage table — pick the ones that make gaps *visible*.
- Write "out of scope" items down now (in brief body); they become the Limitations seed.
- For recurring topics, check `projects/` for a prior run — reuse its brief, then delta.
