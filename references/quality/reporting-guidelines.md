# Reporting Guidelines

Structural checklists for manuscript QA. They are prompts, not substitutes for
the official documents.

| Key | Guideline | Use |
| --- | --- | --- |
| `consort` | CONSORT 2010 | randomised trials |
| `prisma` | PRISMA 2020 | systematic reviews / meta-analyses |
| `strobe` | STROBE | cohort, case-control, cross-sectional |
| `coreq` | COREQ | qualitative interviews / focus groups |
| `care` | CARE | case reports |
| `tripod` | TRIPOD | prediction models |
| `arrive` | ARRIVE | animal research |

## Declare

In `manuscript/draft.md` front matter:

```yaml
reporting_guidelines: ["consort"]
```

or in `venue.json`:

```json
{"reporting_guidelines": ["consort"]}
```

## Check

```bash
R=".venv/bin/python scripts/research_ctl.py"
$R reporting check --file manuscript/draft.md --guideline consort
$R manuscript check
```

`manuscript check` runs the declared guideline(s) against the draft + abstract.
Missing items fail the `reporting_guideline` hard check when a guideline is
declared. If none is declared, the check is soft and the report records
“not declared”.

## Limits

The checker uses keyword/structure presence, not semantic review. A checklist
item can be present but inadequate. The author remains responsible for the
official checklist, page numbers and flow diagrams.
