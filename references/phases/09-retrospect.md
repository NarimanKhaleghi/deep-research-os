# Phase 9 — Retrospect

**So that:** the run's experience becomes durable — journaled feedback, updated source stats, a capability candidate when something genuinely new worked, and honest numbers for the monthly digest.

## Inputs

- The completed run: state counters, gate outcomes, verify metrics, user reactions.
- `learnings/` runtime state (registry, stats, preferences).

## Procedure

1. **Journal feedback** — explicit and implicit signals as they happened:
   - explicit: user comments, corrections, praise ("the pricing section missed X");
   - implicit: follow-up questions (= gap), edits requested (= style signal),
     accepted as-is (= positive), abandoned (= investigate);
   - adjudications: how the user resolved open contradictions.
   `learn feedback` writes `feedback.jsonl` entries (privacy-scrubbed labels).
2. **Run `learn retrospect`** — deterministic summary: counters vs ceilings, gate
   pass/fail per phase, verification metrics, time-ish proxies (actions count).
   Writes `retrospective.json` (schema `references/schemas/retrospective.schema.json`).
3. **Source stats** — record per-source outcomes (kept, yielded evidence, verified,
   fabrication, retraction) → Beta-smoothed updates in `source_stats.json`. This is
   the raw material routing learns from.
4. **Capability candidate** — if the run invented a repeatable routine (a unique
   query pattern, a validation trick, a report structure), draft it as a candidate
   (`learnings/capabilities/CAP-xxx.md`, `status: candidate`). Candidate creation is
   autonomous; **promotion needs approval** (≥3 successful uses + regression eval).
5. **Preference questions** — if an A/B pair was captured during the run and the
   profile's question budget is unspent, ask now via `learn pref ask` (never
   mid-task; never hypothetical).
6. **Maintenance nudge** — if this run pushed the counter past the maintenance
   interval, mention it once; `learn maintain` remains user-triggered in advisory
   posture, automatic in `auto` posture.

## Artifacts

- `retrospective.json` in the project dir (schema above).
- `feedback.jsonl` entries; `source_stats.json` deltas; optional capability candidate.
- Updated `insights.md` happens at next `learn maintain`, not here.

```bash
$R learn feedback --type implicit --label "report accepted as-is" --project ev-charging-eu
$R learn retrospect
$R learn pref ask          # only if A/B exists and budget remains
$R gate --phase 9
```

## Complete when (machine-checked by `gate --phase 9`)

- [ ] `retrospective.json` exists: `worked[]`, `failed[]`, `budget_used{}`,
      `metrics{}` (from verify/report), `suggestions[]`, `capability_candidate`
      (null or object).
- [ ] ≥1 feedback entry for this project — *or* `retrospective.feedback_skipped=true`
      with a reason recorded.
- [ ] Source stats updated for all sources that yielded evidence.
- [ ] `state.preferences_asked` ≤ profile cap; unanswered-asks counter updated.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Empty retrospect | "All good" | Use the metrics; failures are recorded every run |
| Feedback amnesia | User feedback only in chat | Journal it now — chat is not state |
| Candidate spam | Every run "discovers" a routine | Distinct trigger + repeatability required |
| Preference nagging | Third A/B ask in a row unanswered | Trigger self-disables at 3 — check `pref status` |

## Tips

- `failed[]` is the most valuable array in the whole vault — make it specific
  ("GDELT returned 0 for FA queries; synonym set too narrow"), not emotional.
- Retrospect is where you earn the right to skip a step next time: if a shortcut
  proved safe and repeatable, write it as a candidate routine with the proof.
