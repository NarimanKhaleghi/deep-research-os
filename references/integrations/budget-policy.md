# Budget Policy — ceilings, not quotas

Budgets protect against the two research failure modes that look like diligence:
**infinite search** (never deciding) and **budget burn on one angle** (starving
the rest). Profiles set default ceilings; the agent may rebalance *within* totals,
never exceed them silently.

## Profile ceilings (defaults)

| Counter | quick | standard | deep | max |
| --- | --- | --- | --- | --- |
| Search calls (total) | 3 | 8 | 20 | declared |
| Sources read | 3 | 5 | 8 | declared |
| Evidence records | 10 | 25 | 60 | declared |
| Claims | 5 | 15 | 40 | declared |
| Verify passes | 1 | 2 | 3 | declared |
| Preference questions | 0 | 1 | 2 | 3 |
| max_spend_usd (paid MCPs) | 0 | 0 | 2 | declared |

`max` profiles **must** declare explicit ceilings in `brief.md` before phase 3;
"uncapped" is not a valid state (protocol §2).

## Rebalancing rules (allowed)

- Move budget between angles/counters **within** the same class (search↔search,
  read↔read) as long as run totals stay ≤ ceilings.
- Borrow from "claims" to "evidence", or unspent search → read, when justified:
  record in `state.budget_exceptions[]` with a one-line reason.
- Early stop is always allowed and encouraged (saturation rule); under-spend never
  needs justification — spending the whole budget "because it's there" does.

## Overrun rules (forbidden by default)

Exceeding a ceiling requires an **exception record**:

```json
{"counter": "sources_read", "ceiling": 8, "actual": 9,
 "reason": "backward snowball surfaced the sole primary on angle 3; last source, verified figure",
 "at": "…"}
```

Exceptions appear in report Limitations. More than two exceptions in a run, or any
exception that doesn't cite a load-bearing uncertainty, should be treated as a
process smell (note it in retrospect `failed[]`).

## Cost journaling (paid MCPs)

- Every paid call: `state.budget.spent_usd += cost`, plus `source_health[<mcp>]`
  outcome. Unknown cost models are estimated conservatively (worst-case per page/
  query) and marked `cost_estimated: true`.
- Spend cap check happens *before* the call: if the next call could exceed
  `max_spend_usd`, stop and fall down the ladder instead.
- `report check` surfaces any spend if > 0 in the methodology footer.

## Time-ish budget (attention proxy)

There is no wall-clock timer (agent time varies), but two proxies keep runs bounded:
**action count** (`state.counters` total ops vs profile norms) and **phase loops**
(re-entering a phase >2 times without gate progress = either a real blocker — record
it — or thrash — escalate to the user once).

## Enforcement points

| Phase | Enforced |
| --- | --- |
| 0 | Ceilings recorded in state (profile defaults or declared) |
| 3 | read/search counters vs ceilings (gate check + exception records) |
| 6 | verify passes counter |
| 8 | report check surfaces exceptions + spend in Limitations/footer |
| 9 | retrospect records `budget_used{}` vs ceilings for the digest trends |
