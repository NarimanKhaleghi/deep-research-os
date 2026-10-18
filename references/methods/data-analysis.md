# Method — Data Analysis & Quantitative Questions

Read this before phase 2 for: numbers-driven questions (series, comparisons,
dashboards-from-scratch, "is X growing faster than Y"), and any run where the
deliverable centers on statistics rather than prose.

## When to use
- The question reduces to quantities: levels, trends, ratios, rankings, breaks.
- You will present tables/figures whose numbers must be defensible.

## Inputs
- Shelf plan: World Bank, Data Commons, US Census, SEC EDGAR XBRL, official
  statistical releases (via web fetch), Wikidata for entity keys.
- A declared unit/definition sheet in `plan.md` (see step 1).

## Procedure
1. **Define measurement before numbers** (phase 1): unit, base, deflator, nominal
   vs real, per-capita vs absolute, calendar vs fiscal year, geographic code
   (ISO-3 vs ISO-2 vs NUTS). Write the definitions sheet; every number entered
   into evidence must declare which definition it satisfies.
2. **Prefer machine-readable primaries:** API pulls > PDF tables > chart images.
   API pulls get their request parameters recorded (they are reproducibility
   metadata, stored in the source `extra`).
3. **Store values as claims with structure** (phase 4/6):
   `value, unit, period, geography, definition, source` — the claim schema keeps
   numbers[]; you add the qualifiers in tags/notes. "3.2M" without "in Germany,
   2025, BEVs only" is not a datum.
4. **Vintage discipline:** every series carries an extraction date. Revisions
   happen (GDP, registrations); note whenever two sources differ due to revision
   vintage before calling it a contradiction.
5. **Comparisons need alignment:** to compare A vs B, align period, unit,
   definition first; if alignment is impossible, the comparison is qualitative
   ("A larger than B") — never a fabricated ratio.
6. **Chart-grade tables in findings:** raw values, source per column, footnote
   for any transformation (sums, FX conversion rate + date).

## Verification requirements
- Every headline number: 2 independent origins OR a primary-source exclamation
  ("official single source" label allowed, propagated to report).
- Recompute derived numbers (sums, growth, ratio) from base claims — derived
  claims reference the base claim IDs; a mismatch between stated derived value
  and recomputation fails the gate.
- FX conversions: rate + date recorded as evidence, not assumed.
- Rounding: source precision preserved; "~" marks any prose rounding.

## Gotchas
- **Denominator switching:** "% of EV sales" vs "% of new car sales" are different
  stories — check the base of every percentage.
- **Nominal traps:** 20% growth with 15% inflation is ~4% real; both versions
  labeled.
- **Revisions:** first-estimate numbers (flash PMIs, early registrations) differ
  from final; vintage matters more than precision.
- **Aggregation blindness:** EU totals hide Germany's weight (~25% of registrations);
  name the heavy constituent before generalizing.
- **Rate vs level confusion:** "fastest growth" often means smallest base — report
  both.
- **Per-capita ambush:** rankings flip; always state which basis you ranked on.

## Worked mini-example
Question: *"Which EU countries grew EV share fastest 2023→2025?"*
Pull registrations by country-year (official) → compute shares with aligned
definitions (BEV / total new registrations) → rank Δshare → sanity-check vintages
(registrations revised June 2026?) → present table: country, 2023, 2025, Δpp, base
n, source hash. Finding distinguishes "fastest from small base" vs "largest
absolute gain".
