# Method — Operational Decision Modeling

Read this before phase 7 for `decision-framework` deliverables, and for any report
where the user asks for a **model, framework, or decision procedure** rather than
an explanation. Conceptual diagrams do not count: the model must be executable by
a practitioner with numbers.

## When to use
- "Design a model/framework for deciding X", "how should a firm/agency choose…".
- Portfolio, stage-gate, real-options, risk-scoring, prioritization problems.

## What "operational" means here (source of the finding kinds)
A model finding is operational only when it specifies all six:
1. **Variables** — inputs with units and plausible ranges (market growth %, WACC,
   regulatory delay months, FX volatility σ…), each grounded in evidence or a
   clearly labeled assumption.
2. **Thresholds / decision rules** — the actual cut points ("proceed if the
   stage-2 option value under the base scenario exceeds the gate cost by ≥ X%",
   "flag if regulatory ambiguity score > 3/5"). No "consider", "evaluate",
   "assess" as steps.
3. **Procedure** — ordered steps 1..N a practitioner executes (the user counts
   these; include every requested step).
4. **Worked example** — the model run once end-to-end on realistic numbers,
   showing each computation and the final decision.
5. **Baseline comparison** — the same decision under a simpler incumbent method
   (RICE, WSJF, NPV, scorecard); state where the new model changes the answer and
   why that change is defensible (this is what makes the model a contribution,
   not a restatement).
6. **Boundaries** — where the model is not valid (data-hungry regimes, political
   overrides), stated as preconditions, not apologies.

## Model card contract (`model.json`)

Every `decision-framework` deliverable, and any finding that presents equations or
computed outputs, needs a project-level `model.json` validated by:

```bash
python scripts/research_ctl.py model check
```

The card is the reproducible evidence for the prose model. It records:

- `scope` — `structure` (`single-stage` / `multi-stage`), `implemented_stages`,
  `total_stages` when known, `learning` (whether probabilities are updated),
  `selection` (`none` / `greedy` / `ranking` / `heuristic` / `optimization` /
  `exact`), and any extra `limitations[]`.
- `variables` — every symbol, name, role, unit, baseline value, optional range,
  and grounding (`source: "SRC-####"` or `source: "ASSUMPTION"` plus an
  `assumption` sentence).
- `equations` — ordered arithmetic expressions over variables and earlier
  outputs. Allowed functions: `max`, `min`, `abs`, `round`, `sqrt`, `exp`,
  `log`, `log10`. No arbitrary code.
- `cases` — a baseline case, at least five scenarios, and sensitivity cases.
  Each case carries a **complete input vector** (`inputs`) and every equation
  output (`outputs`). The validator recomputes every output and rejects any
  mismatch. Scenario cases also carry `decision` and `early_warning`.
- `baseline` — the incumbent method, the baseline case id, source ids, and why
  the comparison is fair.
- `comparators` — for each RICE/WSJF/NPV/scorecard comparator: source ids,
  `dimensions` (`cost_of_delay`, `staging`, `learning` = `yes` / `partial` /
  `no` / `na`), a note for every `no`/`partial`, and `where_it_differs`.
- `sensitivity` — at least three parameters, each with sensitivity case ids and
  a numeric `breakpoint` (use `"none within the tested range"` when robust).
- `reproduction.command` — optional, but recommended.

The report gate fails when the card is missing, malformed, references unknown
sources, omits an input, or fails to reproduce an output. The report renders the
variables, equations, exact input vectors, comparator dimensions, sensitivity
table, baseline, and scope disclosures. Single-stage/no-learning/heuristic
models also get automatic Limitations entries, so the prose cannot quietly
overclaim a multi-stage optimization.

## Procedure (phase 7)
1. Draft the model in the `model.json` card first. Then write the `--kind model`
   finding as a readable narrative that points to the card: variable table →
   thresholds → numbered procedure → worked example → baseline comparison.
2. Draft `--kind scenarios` finding with **at least five scenarios**, including:
   - base, optimistic, pessimistic (classic three), plus
   - the domain-specific stressor scenarios named in the prompt (regulatory,
     infrastructure, inflation/credit, trust/demand), plus
   - one **combination scenario** (two stressors at once) — interactions are
     where stage-gate value collapses or shines.
   - Each scenario must exist as a `kind: "scenario"` case with full driver
     values, model output, decision, and early-warning indicator.
3. Draft `--kind sensitivity` finding from the card's one-at-a-time cases:
   vary the top 3–5 parameters, report **breakpoints** ("the staging decision
   flips when WACC > 34% or regulatory delay > 17 months") and which variable
   dominates.
4. Convert key model outputs into claims (`claims add --kind theoretical` for
   model-implied statements; `empirical` when a number comes from evidence).
5. Cross-link: every variable heading should cite its source or be explicitly
   labeled `assumption`; the card's assumption text and scope limitations must
   also appear in the report Limitations.
6. Run `model check`, then `report build`. Do not use `--allow-flagged` to hide
   a model arithmetic failure.

## Quality bar (self-audit before phase 8)
- Does `model check` pass with zero errors? If not, the model finding is
  incomplete regardless of how persuasive the prose is.
- Would an analyst with the card reproduce every case exactly? Every input must
  be printed; no hidden parameter may live only in the narrative.
- Does every comparator use the same three dimensions and a sourced note for
  every missing capability? WSJF has cost-of-delay inputs, but it is not a
  stage-gate or learning model; say that instead of claiming it has no cost of
  delay.
- Does any scenario leave the decision unchanged for an unstated reason? Name the
  mechanism or drop the scenario.
- Are breakpoints plausible relative to the observed range of the variable? If
  the flip point is 3× beyond any historical value, say the decision is robust
  instead — robustness is a finding too.
- Are the declared scope and report limitations consistent? A one-stage model
  must not be described as valuing staged learning; a heuristic ranking must not
  be described as portfolio optimization.

## Failure modes to avoid
- Scenario count theater: five scenarios that all move the same lever.
- Sensitivity as prose ("results are sensitive to growth") instead of numbers
  (breakpoints, elasticities, rankings).
- Missing baseline: without a comparison, readers cannot tell what the model adds.
- Unlabeled assumptions floating into the Executive Summary as facts.
- A comparator strawman: describing WSJF/RICE/NPV as having no cost of delay,
  no time criticality, or no risk reduction instead of naming the real
  difference (staging, deferral, probability updating, value of information).
- `model.json` and the model finding telling different stories; the card is the
  source of truth and the report gate only checks the card.
