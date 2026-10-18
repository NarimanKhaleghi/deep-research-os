# Method — Market & Competitive Research

Read this before phase 2 for: market sizing, competitive landscapes, pricing,
positioning, adoption/trend questions.

## When to use
- "Who are the players in X", "how big is the market", "how does Y price",
  "what's the adoption story".
- Competitive intelligence in coordination with the `competitive-intel` skill.

## Inputs
- Brief angles phrased as: size/growth, players, pricing, adoption/demand, risks.
- Shelf plan: filings (SEC EDGAR), official statistics (Census/World Bank/Eurostat
  via Data Commons), company sites/pricing pages, quality press (GDELT), HN for
  tooling signals.

## Procedure
1. **Define the market boundary first** (phase 1) — geography, segment, product
   definition. Market numbers without boundaries are decorative. Record the
   definition; every number's scan must match it.
2. **Triangulate size/growth with three independent methods:**
   - Top-down: analyst/official market totals (cite method & year).
   - Bottom-up: unit counts × price (anchor units in filings or census).
   - Growth proxies: adoption surveys, search interest, shipment data.
   If the three disagree >30%, say so — that *is* the finding.
3. **Player map** (≥5 named, tiered): leaders, challengers, niche, enablers.
   For each: what they sell, to whom, with what proof (filings > press releases >
   landing pages).
4. **Pricing hygiene:** capture list price, terms, and date. Never mix list vs
   street prices; never present a promo as the price. Pricing pages are snapshotted
   (they change silently — that's why we hash them).
5. **Adoption evidence over vibes:** prefer primary stats (registrations,
   shipments, downloads) over surveys-of-intent; label surveys as such.
6. **Risk section is mandatory:** concentration, regulation, substitutes, FX,
   platform dependency — each tied to evidence or flagged as analyst judgment.

## Source strategy
- Numbers: official statistics and filings first; analysts second (and cite the
  analyst, dated); press only as pointer to the primary.
- Private companies: filings of competitors (comparables), job postings (scale
  signals), pricing pages, patents, HN/community sentiment (tier 3, labeled).
- GDELT for unexpected-market-events sweep (last 90 days) before synthesis.

## Verification requirements
- Every market number: source + boundary + date + method. Two independent origins
  for headline numbers.
- Growth rates must state CAGR vs YoY and the base year.
- Debt/financial claims about public companies: XBRL from EDGAR Company Facts,
  never a news summary.
- Pricing claims carry snapshot hashes (pages edit retroactively).

## Gotchas
- **Press-release inflation:** TAM numbers from vendors are marketing; prefer
  third-party or bottom-up.
- **Survivorship in "adoption"**: installation counts ≠ active usage; and shipped
  ≠ sold.
- **Stale reports:** "the market will reach $X by 2027" written in 2022 is a
  forecast to *check*, not a fact to cite (forecast vintage matters).
- **Comparable drift:** using US SaaS multiples for an EU hardware business.
- **Echo pricing:** aggregator "average price" pages often scrape each other —
  find the source of the number, or drop it.

## Worked mini-example
Question: *"European home EV-charger market, 2026"*
Boundary: EU-27, residential AC chargers, installed base + annual units.
Bottom-up: 2025 BEV registrations (official, e.g. ACEA) × home-charger attach
rate (survey, labeled) → units; × ASP (vendor pricing snapshotted, median) → €.
Top-down: analyst totals (cited, dated). Divergence flagged if >30%.
Players: 6 named with tier + proof. Risks: grid-code changes, subsidy phase-out.
