---
question: "Does intermittent fasting reduce lean mass?"
title: "Does intermittent fasting reduce lean mass?"
profile: quick
cutoff: 2026-11-18
deliverable: research memo
deliverable_type: report
review_protocol: none
key_studies_target: 0
domain: general
maintenance: ok
privacy_mode: false
allow_paid: false
project_dir: "/tmp/dros-example-nifdroj2/vault/projects/does-intermittent-fasting-reduce-lean-mass"
success_criteria:
  - "supported answer with citations"
angles:
  - "physiology"
  - "clinical outcomes"
created: "2026-10-19T13:52:34Z"
---

# Brief — Does intermittent fasting reduce lean mass?

## Question

Does intermittent fasting reduce lean mass?

## Scope & Out of Scope

- **In scope:** (fill during phase 0)
- **Out of scope:** (this list seeds the report's Limitations)

## Deliverable

research memo with cited findings

- **Deliverable type:** `report`- **Review protocol:** `none`> **Outputs location:** this project lives in `/tmp/dros-example-nifdroj2/vault/projects/does-intermittent-fasting-reduce-lean-mass`.
> Keep everything for this run inside that folder; learning data stays in
> `~/.config/deep-research-os/`. From another cwd, address it with
> `--project "/tmp/dros-example-nifdroj2/vault/projects/does-intermittent-fasting-reduce-lean-mass"` or `export RESEARCH_OS_PROJECT=…`.

## Requirements (extracted from the user's prompt)

Every explicit requirement of the user prompt is tracked in `requirements.json`:

```bash
python scripts/research_ctl.py requirements add --text "«…»"
python scripts/research_ctl.py requirements map RQ-01 "Report §11 Sensitivity"
python scripts/research_ctl.py requirements waive RQ-03 --reason "…"
```

`report build` fails until each requirement is mapped (its anchor text must appear
in the report) or explicitly waived with a reason shown in Limitations.

## Success Criteria

- supported answer with citations

## Angles (sub-questions)

1. physiology
1. clinical outcomes

## Budget

Ceilings are profile defaults (see `references/integrations/budget-policy.md`),
recorded in `state.json`. Exceptions get logged with reasons.

## Maintenance

`learn status` was checked at intake: **ok**.

## Notes

(free-form notes; will survive across sessions)