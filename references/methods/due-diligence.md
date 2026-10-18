# Method — Due Diligence

Read this before phase 2 for: decisions with money behind them — investments,
vendor selection, partnerships, M&A-adjacent questions, procurement.

## When to use
- The deliverable supports a go/no-go or a comparative scorecard with financial/
  operational consequences.

## Inputs
- Entity names + scope (what exactly is being evaluated, from whose perspective).
- Shelves: SEC EDGAR / national registries, court records, regulator actions,
  official statistics, pricing pages (snapshotted), GDELT (negative news sweep),
  professional references, patent/trademark databases.

## Procedure
1. **Define the decision** explicitly in brief: what would change the decision?
   These become the mandatory angles ("triggers": litigation history, ownership
   opacity, financial trajectory, dependence risks…).
2. **Identity resolution first** (phase 1): legal entity ≠ brand ≠ parent. Resolve
   IDs (LEI, registration number, CIK) via registries/Wikidata/EDGAR; make a
   one-entity-one-row map before pulling any number.
3. **Tranche the checks** (phases 3–5):
   - **Financial:** filings/XBRL (public), registry accounts (private), payment
     behavior signals (press, lawsuits). Debt/liens/court claims where available.
   - **Legal/reputation:** courts, regulator actions, GDELT negative sweep with
     entity aliases (including misspellings).
   - **Operational:** scale claims vs. physical evidence (patents, job postings,
     premises, certifications).
   - **Continuity:** ownership changes, key-person dependence, concentration of
     revenue/customers (from filings).
4. **Red-flag sweep with its own evidence class** (`refutes` + `methodological`):
   each red flag gets a CX record when contested, a severity, and a mitigation
   note. Absence of evidence is recorded as "not found in sources searched",
   never as "clean".
5. **Scorecard synthesis** (phase 7): per angle: verdict + confidence + the two
   strongest facts for and against. No single overall "score" unless methodology
   is declared.

## Verification requirements
- Every financial number: filing page/XBRL tag; press numbers demoted.
- Legal records: court/law-firm summaries labeled secondary; the docket is primary.
- Company claims ("customers include…") require a third-party anchor to count.
- All entity names disambiguated in the identity map; alias list attached to
  every GDELT sweep (misses are how DD fails silently).

## Gotchas
- **Alias misses:** "Acme GmbH" vs "Acme Europe B.V." vs trade name — sweep the
  alias list, log it.
- **Registry jurisdiction gaps:** EU registries differ in depth; absence ≠ no record.
- **Press-release decoys:** announced projects that never happened; check permits/
  procurement/progress records.
- **Litigation noise:** every scale company has suits — triage by status (active/
  settled/dismissed), amount, and relevance to the decision.
- **Recency cliff:** pre-decision events (management change 3 months ago) matter
  more than decades-old history; weight by half-life.
- **Optimism asymmetry:** user may be seeking confirmation ("can we go ahead?").
  The counter-evidence sweep is anti-sycophancy insurance — run it fully.

## Worked mini-example
Decision: *"Europe-based CDMO vendor for clinical-stage fill-finish — shortlist
ready?"*
Triggers: GMP status (EMEA/FDA inspection records), capacity claims (filings/
press), ownership opacity, client concentration. Output: 4-row scorecard with
per-cell evidence, red-flag register (2 flags, one open), and an explicit list of
what was not verifiable from open sources.
