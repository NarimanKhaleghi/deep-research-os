# Contradiction Protocol

Contradictions are **findings**, not embarrassments. This protocol defines how the
scanner flags them (`scripts/core/contradictions.py`) and how they are adjudicated.

## What counts as a contradiction

| Kind | Detection | Example |
| --- | --- | --- |
| **Numeric** | Same metric (tags + unit) differs beyond tolerance | "sales grew 12%" vs "10%" |
| **Polarity** | Opposite directional/negation terms on same subject | "queue times improved" vs "queue times worsened" |
| **Scope** | Different populations/periods presented as the same fact | "price fell" (US) vs "price rose" (EU) |
| **Study-vs-study** | Same question, different designs/effect | RCT vs observational |

Tolerance for numeric flags: relative diff >5% **and** beyond combined rounding
(claims merely rounding differently are reconciled silently — but a *precision-loss*
mismatch (protocol §6) is still a verify failure, not a contradiction).

## Scanner output

Each candidate becomes a `CX-####` record: `claim_ids`, `kind`, `severity`
(high = decision-relevant/headline numbers; medium; low = context),
`detail` (the exact values/terms in conflict), and status `open`.

## Adjudication ladder (apply in order)

1. **Scope check** — do the claims actually measure the same thing (period,
   geography, population, definition)? If not: resolve as `scope_difference`,
   restate both claims with their qualifiers. *Most "contradictions" die here.*
2. **Credibility check** — band gap ≥2 (A vs C): the lower-band claim is
   `outweighed`; record for provenance but do not cite as equivalent.
3. **Directness check** — primary vs secondary: for contradictions about *a
   source's own data*, the primary wins.
4. **Vintage check** — later (still-in-half-life) data supersedes earlier when
   measuring the same evolving quantity (market share moves; legal texts don't).
5. **Method check** (study-vs-study) — higher design tier wins (meta > RCT >
   cohort > case study); if equal, larger sample/newer > older.
6. **Remain unresolved** — if 1–5 don't separate them, the honest resolution is
   `unresolved: both credible`. The report must present both values side by side
   with the disagreement named. This is a *result*, not a failure.

## Resolutions (enforced enum)

`source_a_wins · source_b_wins · scope_difference · outweighed ·
unresolved_both · superseded`

Every adjudication records: `resolution`, `rationale` (which ladder step, with
numbers), `resolved_by` (agent or human), `at`. Human adjudications are gold
signals for the learning loop (`type=adjudication` feedback).

## Rules of engagement

- **Never silently pick one.** Unresolved pairs must appear in the report's
  contradiction table. Open (unadjudicated) contradictions block phase 6 gate
  unless explicitly kept open *with a reason* — and then they surface in the
  report's Limitations.
- **Adjudicate before synthesis**, not during. Findings built on a claim whose
  contradiction is still open must carry the conflict inline.
- **Feed the loop:** adjudications update source stats (a source whose claim lost
  an adjudication loses standing; repeated fabrication-adjacent patterns escalate
  to `source_health` and possibly a retirement proposal).
- **Human override wins** over the ladder, always — with the override logged.

## Worked example

- CL-0007 (band A, 2025 EEA report): "EU charging points reached 900k in 2025."
- CL-0013 (band C, blog citing 2024 trade body): "EU charging points ~700k in 2025."
- Ladder: same scope? Both EU total, 2025 → yes. Band gap: A vs C → outweighed.
  Resolution `source_a_wins`, rationale "band gap 2 + primary (EEA vs blog)",
  CL-0013 status → `outweighed`, kept in ledger with note.
