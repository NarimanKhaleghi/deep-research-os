# Sample run (offline, generated)

A complete quick-profile run for the question:
**"Does intermittent fasting reduce lean mass?"**

Generated with `RESEARCH_OS_OFFLINE=1` on synthetic sources, then frozen here
as a reference for what a finished project looks like:

- `brief.md` / `plan.md` / `state.json` — intake, plan, machine state
- `sources/` — SRC records + content snapshots
- `evidence.jsonl` — quotes with validation results
- `claims.jsonl` — atomic claims with verification status
- `findings/FN-01.md` — a supported finding citing claims
- `verify_report.json` — citation check + number scan
- `report.md` / `report.html` — final deliverables
- `retrospective.json` — phase-9 learning payload

Regenerate: `python evals/run_evals.py --offline` (scenarios) or follow
`SKILL.md` to run the real pipeline on your own question.
