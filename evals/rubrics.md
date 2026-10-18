# Eval rubrics

Behavior evals plant a known trap and assert the pipeline catches it.
They are deterministic and offline by default (`python evals/run_evals.py --offline`);
`--live` adds a network sanity check. Exit 0 = all scenarios pass.

| # | Scenario | Trap planted | Pass condition |
| --- | --- | --- | --- |
| 1 | `citation_fabrication` | Evidence quote that does **not** exist in the source snapshot ("93%" not in a "71%" page) | Evidence validation returns `quote_found: false` **and** gate 4 fails with `quote∉snapshot` |
| 2 | `planted_contradiction` | Two sources disagree on the same number (12% vs 10% growth) | Scanner creates a CX record, adjudication via the ladder succeeds, a second scan creates nothing (dedupe) |
| 3 | `number_drift` | Claim says "97%" while the quote says "96.555%" | `verify` records a `number_mismatches` entry and classifies the claim `weakly_supported` (precision-aware rule) |
| 4 | `echo_chamber` | Two "independent" sources share one `origin_key` backing a **critical** claim | A `corroboration_gaps` entry is recorded and the claim is downgraded from `supported` |
| 5 | `multilingual_fa` | Persian text with Persian digits and `٪`/`٫` ("۹۶٫۵٪") | Digits normalize, quote matches, verify shows **no** number drift, claim accepted |
| 6 | `budget_quick` | Quick profile overspends its search ceiling (4 > 3) | `status` reports the exceeded counter; after `budget exception` with a reason, it clears |

## Live scenario

| Scenario | Pass condition |
| --- | --- |
| `live_search` | One connector (OpenAlex by default) returns ≥1 record with no failures |

## Grading philosophy

- **Fail loud, not silent.** Every scenario asserts the *specific* detection
  surface (a JSON field or gate check name), never "no crash".
- **Offline-first.** Traps are synthetic; the assertions are about pipeline
  behavior, not world facts. This keeps evals reproducible in CI without keys.
- **One scenario per failure mode.** When adding a new failure mode, add a
  scenario + rubric row here rather than growing an existing one.
- Regression use: `learn approve` runs `evals/run_evals.py --offline` plus
  `pytest` before applying a proposal; a red result auto-reverts the proposal.
