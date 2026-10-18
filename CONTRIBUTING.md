# Contributing to deep-research-os

First of all — thank you. This project exists to make AI-assisted research
**verifiable, structured and self-improving**, and every contribution that moves
those three needles is welcome.

## Ways to contribute

| Type | Examples |
| --- | --- |
| 🐛 Bug reports | Connector broken by an upstream API change, gate false-positive |
| 🔌 New connectors | A free/keyless data source we are missing (with API docs link) |
| 🧪 Eval scenarios | New trap scenarios (planted contradictions, poisoned citations, multilingual) |
| 📚 Methods | A new research playbook (e.g., clinical-trial diligence, patent landscaping) |
| 🧠 Learning engine | Better promotion/retirement heuristics, new preference signals |
| 📖 Docs | Clarifications, translations (we ship EN + FA; more welcome) |
| 🎨 READMEs | Visual/structural improvements that keep both languages in sync |

## Development setup

```bash
git clone https://github.com/<you>/deep-research-os
cd deep-research-os
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest                       # unit tests must be green
python evals/run_evals.py --offline   # offline eval suite must be green
```

No API keys are required for development or CI — the offline eval suite runs on
bundled fixtures, and every connector must remain reachable by code paths that
degrade gracefully when the network is unavailable.

## Design rules (non-negotiable)

1. **Evidence first.** Any new output must remain traceable: claim → evidence
   (verbatim quote) → source → snapshot. Never add a shortcut that emits claims
   without evidence records.
2. **Keyless default.** A feature that requires a paid API key must be optional
   and must degrade to a free path. The core pipeline never requires keys.
3. **Untrusted content.** Everything fetched from the web is evidence, never
   instructions. Never execute, follow or relay instructions found in fetched
   content.
4. **Governed learning.** Autonomous changes are limited to safe classes
   (stats, feedback journaling, bounded weight nudges, candidate creation).
   Everything else goes through `proposals` with human approval and a
   regression check. `SKILL.md` core phases, schemas and safety policy are
   never auto-modified.
5. **Gates are machine-checkable.** "Complete when:" criteria must be verifiable
   by `research_ctl.py gate --phase N`, not vibes.
6. **Same-change docs.** If you change behavior, update the matching reference
   doc in `references/` in the same PR.

## Adding a connector

1. Create `scripts/connectors/<name>.py` exposing
   `search(query: str, *, limit: int = 10) -> list[dict]` returning normalized
   records (`title, url, doi, authors, published, publisher, type, abstract,
   source_service, extra`).
2. Use `lib.http.get_json` / `get_text` (they carry retries, timeouts and a
   descriptive User-Agent; respect the service's etiquette — e.g. OpenAlex
   `mailto`).
3. Register it in `scripts/connectors/registry.py` with domain tags, a static
   tier prior and rate-limit notes.
4. Add an offline parser test in `tests/test_connectors_offline.py` using a
   canned response fixture.
5. Document it in `references/sources/catalog.md` (endpoint, rate limits,
   licence/terms notes, quirks).

## Adding a method playbook

Create `references/methods/<name>.md` following the existing template: when to
use, inputs, step-by-step procedure, source strategy, verification requirements,
**Gotchas** section, and a worked mini-example. Register domain tags in
`learnings/registry.json` seeds if it should be discoverable by the router.

## Pull request checklist

- [ ] `pytest` green
- [ ] `python evals/run_evals.py --offline` green
- [ ] `python scripts/research_ctl.py doctor` still runs on a clean machine
- [ ] Docs updated (references + both READMEs if user-facing)
- [ ] No secrets, tokens, personal data or research vaults committed
- [ ] CHANGELOG.md entry added under "Unreleased"

## Code style

- Python ≥ 3.11, type hints on public functions, small modules, no wildcard imports.
- All CLI output is JSON on stdout (machine-parseable) and logs on stderr.
- Prefer stdlib + the pinned dependency set; propose new dependencies in an issue
  with a justification (performance/size/maintenance trade-off).

## Code of conduct

Be kind, be precise, assume good faith. Research quality is a team sport.
