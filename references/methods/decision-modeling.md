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

## Procedure (phase 7)
1. Draft the model in a `--kind model` finding: variable table → thresholds →
   numbered procedure → worked example → baseline comparison table.
2. Draft `--kind scenarios` finding with **at least five scenarios**, including:
   - base, optimistic, pessimistic (classic three), plus
   - the domain-specific stressor scenarios named in the prompt (regulatory,
     infrastructure, inflation/credit, trust/demand), plus
   - one **combination scenario** (two stressors at once) — interactions are
     where stage-gate value collapses or shines.
   - Each scenario: driver values, model output, decision change, early-warning
     indicator a manager can watch.
3. Draft `--kind sensitivity` finding: one-at-a-time variation of the top 3–5
   variables, report **breakpoints** ("the staging decision flips when WACC > 34%
   or regulatory delay > 17 months"). Where possible state elasticity
   (Δ output per Δ input) and which variable dominates.
4. Convert key model outputs into claims (`claims add --kind theoretical` for
   model-implied statements; `empirical` when a number comes from evidence).
5. Cross-link: every variable heading should cite its source or be explicitly
   labeled `assumption` (assumptions then appear in Limitations).

## Quality bar (self-audit before phase 8)
- Would an analyst with your tables reproduce your worked example exactly? If no,
  the model finding is incomplete.
- Does any scenario leave the decision unchanged for an unstated reason? Name the
  mechanism or drop the scenario.
- Are breakpoints plausible relative to the observed range of the variable? If
  the flip point is 3× beyond any historical value, say the decision is robust
  instead — robustness is a finding too.

## Failure modes to avoid
- Scenario count theater: five scenarios that all move the same lever.
- Sensitivity as prose ("results are sensitive to growth") instead of numbers
  (breakpoints, elasticities, rankings).
- Missing baseline: without a comparison, readers cannot tell what the model adds.
- Unlabeled assumptions floating into the Executive Summary as facts.
