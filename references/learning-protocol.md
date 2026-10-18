# Learning Protocol — the Governance Contract

deep-research-os improves itself across runs. This document defines **what may
change, who approves it, how it is tested, and how it is undone**. It is the
contract every learning loop must obey; `scripts/learning/*` implement it and
the eval suite tests it.

## 1. Design principles

1. **No silent self-modification.** Any change beyond the autonomous classes
   below requires an explicit human `approve`. Unapproved proposals expire.
2. **Evidence-backed changes.** A proposal without numeric evidence (yield,
   verification outcomes, eval deltas, user preferences) is rejected by the
   proposal validator before a human ever sees it.
3. **Test before adopt.** Every approved change runs the offline regression
   suite. Regression → automatic revert + proposal marked `regressed`.
4. **Reversible by one command.** `learn revert <id>` restores prior state.
   History is append-only; nothing is ever hard-deleted without `--purge`.
5. **Kill switch.** `learn mode off` disables all learning writes; the skill
   still runs, it just stops adapting.

## 2. Data layout

Runtime data lives in `~/.config/deep-research-os/` (override: `RESEARCH_OS_HOME`),
seeded from the repo's `learnings/`:

```text
learning/
├── registry.json          # capabilities index (id, level, status, metrics)
├── capabilities/          # CAP-*.md playbook files (frozen header + routine body)
├── source_stats.json      # per-source × per-domain Beta stats
├── preferences.md         # preference pairs + resolutions (human-readable)
├── feedback.jsonl         # every signal, append-only
├── proposals.jsonl        # lifecycle: proposed→approved/rejected/applied/regressed/reverted
├── insights.md            # human-readable narrative, updated monthly
├── watchlist.json         # tools/sources/methods being watched for adoption
├── digest-YYYY-MM.md      # monthly digest (generated)
└── archive/               # retired/superseded capabilities
```

## 3. Signal collection (fast loop, every run)

| Signal | Source | Recorded as |
| --- | --- | --- |
| Explicit feedback | user comment at report delivery | `feedback.jsonl` `type=explicit` |
| Implicit feedback | follow-up questions, edits requested, report accepted as-is | `type=implicit` |
| Adjudications | user's contradiction resolutions | `type=adjudication` |
| Preference answers | A/B question responses | `type=preference` |
| Source outcomes | kept/dropped sources, verification results | `source_stats.json` |
| Run outcome | gate pass/fail, budget adherence, reverification results | `state.json` + retrospect |

Signals are privacy-scrubbed: no personal data, no verbatim user messages
beyond a short label the user approved (or, in stricter mode, a hash + category).

## 4. Autonomy classes

| Class | Examples | Rule |
| --- | --- | --- |
| 🟢 **Autonomous** | stats updates, feedback journaling, weight nudges within ±ε bounds, candidate creation, digest generation | Applied immediately, always logged, reversible |
| 🔴 **Approval-required** | candidate → active promotion; capability retire/merge; new source/method/tool adoption; template changes; watchlist promotion | `propose` → validate → human `approve` → regression test → apply |
| ⛔ **Never auto** | SKILL.md phase definitions, evidence/claim schemas, safety & privacy policy, governance levels, autonomy bounds themselves | Human edit + version bump only |

Weight nudge bounds: any source weight may move at most **±10% relative** per
maintenance cycle, must remain within `[0.05, 0.60]` of its domain's total
mass, and every nudge is logged with the statistic that caused it.

## 5. Source learning (ε-greedy routing)

- Stats per `(source, domain)`: attempts, yields (kept results), verification
  pass rate, freshness of results — Beta-smoothed with prior α=2, β=2 (never
  0-confidence, never 100%-confidence from small n).
- Routing: with probability **0.85** pick sources by weight; with **0.15**
  explore (uniform among enabled sources). The exploration floor can rise to
  0.25 for domains with <20 total attempts.
- **Floor rule:** no enabled source may receive <5% of a domain's routing mass,
  and disabled sources require a retirement proposal (never silent).
- Champion/challenger: when a new source looks promising (≥20 attempts, pass
  rate within CI of champion, higher unique-contribution rate), create a
  challenger proposal to shift weight — subject to `maintain` cycle.

## 6. Preference elicitation (asking the human)

- **When:** only when a real, pre-captured A/B comparison exists (two
  strategies, two syntheses, champion vs challenger artifact). Never
  hypothetical, never mid-task.
- **How:** `learn pref ask` renders the preference-question template
  (side-by-side excerpts + 1 question). Max per profile: quick 0 · standard 1
  · deep 2 · max 3.
- **When NOT:** user is in a hurry (implicit signal), or the last 3 asks were
  unanswered (trigger self-disables until a manual `pref enable`).
- Answers update `preferences.md` + relevant weights; a preference may also
  file a proposal (e.g., "always prefer structure B for market reports").

## 7. Proposal lifecycle

```text
proposed → validated → (human) approved | rejected
approved → regression-tested → applied | regressed(auto-revert)
applied → reverted (manual, via learn revert <id>)
```

- **Validation (automatic, before human review):** JSON schema + evidence
  fields present + change class matches declared type + no protected-class
  changes. Invalid proposals are marked `invalid` with reasons, never shown.
- **Review card** (`templates/proposal-card.md.j2`): what changes, why (with
  stats), expected effect, risk, rollback plan, exact diff of affected files.
- **Regression gate:** `evals/run_evals.py --offline` + a scoped scenario
  re-run for the affected capability. Pass → apply. Fail → auto-revert,
  proposal → `regressed` with the failing checks attached.
- **Expiry:** pending proposals expire after 30 days (configurable); expired
  proposals may be re-proposed once with fresh evidence.

## 8. Upstream discovery (self-research)

`learn scan-upstream` (monthly, or on demand) searches for things that could
improve *this skill's own research capability*:

- GitHub: new repos, releases of watched tools (watchlist.json), awesome-lists deltas
- arXiv: new benchmarks/methods for deep research, verification, agents
- Skill marketplaces & awesome-lists: new Agent Skills relevant to research
- MCP registries: new servers in the research/data category

Output: `learnings/discoveries/YYYY-MM.md` — candidates table (name, what it
does, why it matters, estimated integration cost, watched/propose/skip
recommendation) → user picks which become watchlist entries or proposals.
Discovery reports never auto-apply anything, ever.

## 9. Maintenance cycle (`learn maintain`)

Runs monthly or after every N=10 runs (whichever first; at intake the skill
checks `maintenance due` and nags once). Steps:

1. Recompute source stats; emit weight nudges (autonomous, bounded).
2. Cluster capabilities by trigger similarity (rapidfuzz); propose merges.
3. Propose retirements: capabilities with ≥5 uses, success rate <40%, or
   superseded by a newer capability with victory margin in head-to-head.
4. Promote candidates: ≥3 successful uses, distinct trigger, no overlap >85%
   with existing → proposal.
5. Regenerate `insights.md` narrative + monthly `digest-YYYY-MM.md`.

## 10. Commands & observability

```bash
R="python scripts/research_ctl.py"
$R learn status                    # modes, counters, pending proposals
$R learn explain <item>            # why is this weight/capability like this (evidence chain)
$R learn proposals [--all]         # review queue
$R learn approve <id> | reject <id>
$R learn revert <id> [--purge]
$R learn mode auto|advisory|off    # kill switch (persisted)
$R learn retain <signal-file>      # bulk signal ingestion (offline batch)
$R learn maintain | scan-upstream | digest
```

`advisory` mode: learning still analyzes and proposes, but autonomous classes
are also downgraded to proposals (maximally conservative).

## 11. What we measure (is learning working?)

Tracked in `insights.md` per month: citation precision trend, contradiction
find-rate, gate pass-on-first-attempt rate, budget adherence, user-approval
ratio of proposals, preference-answer rate, source diversity (Shannon entropy
over domains). Learning is considered healthy when precision and pass rates
are non-decreasing while source diversity stays above the exploration floor.
If metrics worsen two months in a row → the maintain cycle proposes a
rollback of the biggest recent weight change (with evidence) automatically.
