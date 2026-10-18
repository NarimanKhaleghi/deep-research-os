# Credibility Rubric

Six weighted dimensions, 0–100 total. Implemented in `scripts/core/credibility.py`
as deterministic heuristics the agent may override with justification
(recorded in `overrides[]`).

## Dimensions

| # | Dimension | Weight | What scores well |
| --- | --- | --- | --- |
| 1 | Authority | 25 | Official stats, regulators, peer-reviewed venues, primary documents, named expert authors with affiliation |
| 2 | Editorial / peer review | 20 | Peer-reviewed > edited/journalistic > moderated > self-published |
| 3 | Recency vs topic half-life | 15 | Age ≤ half-life (see table), with vintage noted |
| 4 | Evidence quality | 20 | Primary data, methodology disclosed, sample size, verifiable artifacts, references |
| 5 | Conflicts of interest | 10 | Independent funding; negative if vendor/advocacy funded, disclosed or not |
| 6 | Retraction / integrity | 10 | No retractions/corrections; formal integrity flags checked; domain not impersonated |

## Scoring bands

| Band | Score | Meaning / permitted use |
| --- | --- | --- |
| **A** | 85–100 | Can anchor key claims (still needs a second origin for decisive numbers) |
| **B** | 70–84 | Solid support; A-corrobotation needed for headline numbers |
| **C** | 55–69 | Context only; cannot be sole support for any critical claim |
| **D** | <55 | Leads only; never cited as fact in findings; excluded from bibliography |

## Topic half-lives (dimension 3)

| Domain | Half-life | Notes |
| --- | --- | --- |
| ML/AI benchmarks, tooling | 12–18 mo | Also: version-pinned docs only |
| Market sizes / pricing | 12–24 mo | Analyst reports age fast; vintage required |
| Elections, conflict events | weeks | Point-in-time facts; timestamp everything |
| Regulatory / legal texts | 5–10 yr+ | In-force version matters more than date |
| Medicine (guidelines) | 3–5 yr | Guidelines supersede; check current revision |
| Foundational science | decades | Classic is fine where field stable |

## Heuristic rules baked into the scorer

- DOI present + journal venue in the peer-reviewed registry → authority & review boost.
- `.gov`, national statistical offices, central banks, regulators → authority boost.
- Vendor domain or "funded by"/"sponsored" language → COI penalty (min −5).
- `is_retracted` (OpenAlex) or `update-to` retraction (Crossref) → dimension 6 = 0,
  whole score capped at 49 (**D**) until re-verified.
- Preprint without peer-reviewed version → dimension 2 capped at half.
- Aggregator/content-farm patterns (no byline + no organization + high ad density
  heuristic) → dimension 4 penalty.

## Override protocol

The agent may override any dimension ±N with a written rationale:

```json
"overrides": [{"dimension": "recency", "delta": -10,
               "reason": "2019 infrastructure benchmark; field changed (V2G std)."}]
```

Overrides are visible in `credibility show` and feed the learning loop's
rubric-tuning candidates. Systematic override patterns → proposal to adjust
heuristics (approval required; protocol §4).

## Output shape

```json
{
  "score": 82, "band": "B",
  "dimensions": {"authority": 21, "review": 16, "recency": 12,
                  "evidence": 17, "coi": 8, "integrity": 8},
  "rationale": "peer-reviewed (Crossref), 18mo old vs 24mo half-life, no COI signals",
  "scored_at": "2026-10-18T09:12:00Z", "overrides": []
}
```
