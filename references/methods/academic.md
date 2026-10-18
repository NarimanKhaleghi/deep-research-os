# Method — Academic Research (literature review, evidence synthesis)

Read this before phase 2 for: literature reviews, state-of-the-art surveys,
research-grounded policy/technical questions.

## When to use
- Question asks "what does the research say", "state of the art", "evidence for X".
- Deliverable is a review, a research memo, or a claim that must survive academic scrutiny.

## Inputs
- Brief angles phrased as researchable constructs (not topics).
- Access to the academic shelf: OpenAlex, Crossref, arXiv, PubMed, Unpaywall.

## Procedure
1. **Construct vocabulary** (phase 1): expand each construct into synonyms and
   controlled terms — MeSH terms from PubMed, OpenAlex topic tags, and related
   field jargon. Keep a term ledger; you will reuse it for every query.
2. **Search broadly, then snowball:**
   - Broad pass: each construct × (synonym set) on OpenAlex (relevance) and
     Crossref (metadata).
   - Backward snowball: from the 2–3 seed papers, mine references (OpenAlex
     `referenced_works`) for classics.
   - Forward snowball: `cited_by` for the seeds to find what superseded them.
3. **Screen in two rounds** (like PRISMA-lite):
   - Title/abstract screen → `sources` candidates with exclusion reasons.
   - Full-text screen → `read` only what plausibly carries findings.
   - Log exclusions in plan.md; the coverage table in the report shows the funnel.
4. **Extract by design** (phase 4): for empirical works pull: population/sample,
   method, effect size / key statistic, limitations stated by authors. These become
   typed evidence (`methodological` relevance for design facts).
5. **Weight by design and venue** (phase 5): meta-analyses/RCTs > cohort > case
   studies; preprint = B cap; retraction check mandatory (OpenAlex `is_retracted`,
   Crossref `update-to`).
6. **Synthesize by divergence** (phase 7): group findings by agreement, not by
   paper. The interesting finding is where studies disagree — effect moderated by
   population, dose, geography — and name the moderator.

## Source strategy
- OpenAlex first (coverage + citation graph), Crossref to confirm canonical DOI
  metadata, PubMed when biomedical, arXiv for CS/ML frontiers (label preprints).
- Unpaywall to legally reach OA full texts; `read --metadata-only` otherwise.

## Verification requirements
- Every cited work resolves (DOI verified) and is not retracted.
- Effect sizes/statistics carry their sample base ("36% *of 1,204 participants*").
- Contradictory studies are reported as such (contradiction protocol §"study vs study":
  weight by design first, then recency, then directness).
- Preprints marked as such in the report; peer-reviewed version linked when it exists.

## Gotchas
- **Abstract-only claims:** the abstract's number often differs from the paper's
  (rounder, less qualified). Prefer full-text numbers; else mark precision loss.
- **Citation context drift:** a famous paper often doesn't say what others cite it
  for — verify in the original, not in secondary citations.
- **Prestige ≠ fit:** a Nature paper 3 fields away is not evidence for your construct.
- **Publication bias:** null results are underrepresented; explicitly note when a
  literature's positive results cluster in small studies.
- **Retraction lag:** retracted papers keep earning citations for years — always
  run the retraction check at verify time, not just at collection time.

## Worked mini-example
Question: *"Does EV smart charging shift peak load in practice?"*
Terms: smart charging, V1G/V2G, peak shaving, demand response, load shifting.
Ground truth for synthesis is not "yes/no" — the finding is usually conditional:
"pilot studies show 20–40% peak reduction under TOU tariffs, but effects vanish
without automation" with moderators (tariff design, charger penetration) cited
per study. Deliverable: review with a moderation table, not a verdict.
