# Method — OSINT & Investigation

Read this before phase 2 for: investigations, verification of claims about people/
organizations/events, conflict/incident questions, and any topic where sources may
be adversarial or deceptive.

## When to use
- Verify/attribute an event, trace a claim to its origin, map an organization or
  network, or investigate contested narratives.

## Inputs
- Shelf plan: GDELT (coverage sweep), company registries, court/regulatory filings,
  official statements, archived pages (Wayback), Wikidata for entity anchors.
- **Privacy stance declared in `brief.md`** — subject is usually public-interest;
  minimize personal data; never store identifiers beyond research necessity.

## Procedure
1. **Timeline first** (phase 1): build the event chronology before analyzing any
   claim. Disagreements about *when* invalidate most narrative comparisons.
2. **Claim provenance chains** (phase 4): for each contentious claim, find the
   *earliest* appearance ("patient zero"), then trace who re-reported whom. A claim
   with 40 hits and one origin is one source — record `origin_key` so the router
   counts it once.
3. **Corroborate across types:** official statement + independent reporting +
   verifiable artifact (filing, registry record, procurement doc, satellite/fixed
   dataset). Three retweets are not corroboration; three *different types* are.
4. **Check for the debunk:** actively search "[claim] false", "[claim] debunked",
   native-language variants, and institutional denials. Record findings as
   `refutes` evidence.
5. **Entity intersector check** (phase 5/6): do the disputants share an owner,
   funder, PR firm? Wikidata + registries + filings resolve a surprising amount.
6. **Snapshot everything** (phase 3): adversarial sources delete pages. WayBack in
   addition to local snapshots for contested pages; the hash chain is the point.

## Verification requirements
- Every attribution: ≥2 independent types for the assertion; single-type stays
  `weakly_supported`.
- Images/video: source URL, earliest known post, metadata caveats — if unverifiable,
  excluded from findings (may appear as context, labeled "unverified").
- Quotes from statements: link to the primary publication, not aggregator.
- Originating accounts: assess age/history for influence ops (account created
  recently + burst amplification = flag).

## Gotchas
- **Poisoned clock:** fake "original" posts backdated after the fact — trust the
  platform timestamp + earliest archived copy.
- **Selective quotes:** official statements misquoted by partisans; always fetch
  the full primary text before repeating.
- **Translation drift:** machine translation mangles nuance; use native-language
  search first, quote the original, translate with care.
- **Sock-puppet echo:** dozens of accounts, one invoice — provenance chains expose
  this; counts don't.
- **Over-attribution:** correlation of sectors ≠ coordination; state inference
  level ("documents show" vs "suggests").
- **Privacy overreach:** the subject is organizations/events, not individuals'
  private lives; do not collect personal data beyond public-interest scope.

## Worked mini-example
Question: *"Did supplier X's claim about '30 GW of signed contracts' hold up?"*
Chain: presser (2026-01) → trade press repeats → regional outlet inflates to
"delivered". Check: company registry capitalization, procurement award lists
(official), earnings filings. Finding: 30 GW = LOIs, not binding; deliverable
table splits "announced / LOI / binding" with per-cell evidence.
