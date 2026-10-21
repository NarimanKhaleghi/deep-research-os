# Method — Academic Manuscript Writing

Use this for `deliverable: academic-manuscript`. It turns a verified evidence
ledger into a submission-shaped manuscript; it never invents prose, data or
references.

## Preconditions

- `brief set --deliverable-type academic-manuscript`
- full-text policy satisfied for key studies and critical claims
  (`fulltext coverage`, `fulltext verify`)
- `claims` verified, contradictions adjudicated, `findings` written
- `venue.json` configured (or defaults accepted)

## Workflow

```bash
R=".venv/bin/python scripts/research_ctl.py"

$R brief set --deliverable-type academic-manuscript
$R venue init                         # writes venue.json defaults
$R manuscript scaffold                # manuscript/draft.md
# write the draft with [@SRC-0001] markers
$R manuscript build                   # renders manuscript.md + manuscript.html
$R manuscript check                   # hard gates; exit 1 on failure
$R manuscript show                    # paths + check summary
```

`manuscript build` renders citations in the venue style, builds the reference
list from cited sources only, writes a print-ready self-contained HTML file and
runs the same hard checks. It does not write the report-style `report.md`.

## Structure

Required sections, each substantive (≥40 words):

1. **Introduction** — problem, gap, contribution, roadmap.
2. **Methods** — design, setting, participants/materials, measures, analysis.
3. **Results** — findings with effect sizes, uncertainty and sample base.
4. **Discussion** — interpretation against prior work, limitations,
   implications.
5. **Conclusion** — one paragraph, no overclaim.

Recommended additional sections: Limitations, Ethics and consent, Funding,
Conflicts of interest, Data availability, Registration.

## Abstract

A comprehensive abstract is required (≥200 words) and should contain:

- Background/rationale;
- Objective/question;
- Methods (design, sample, measures, analysis);
- Results with at least one numeric finding and uncertainty;
- Conclusions and limitations/implications.

Structured labels (`Background:`, `Methods:`, …) are encouraged. An abstract is
never used as evidence for a key study or critical claim.

## Citations and claims

- Every factual paragraph carries `[@SRC-0001]` markers; multiple IDs may be
  combined (`[@SRC-0001; @SRC-0004]`).
- Markers resolve only to ledger sources; unknown IDs fail the build.
- Citation style comes from `venue.json`: `apa` (default), `vancouver`, `ieee`.
- The bibliography contains cited, non-excluded sources only.
- Numeric claims in body paragraphs require a citation marker in the same
  paragraph.
- Every included source should be cited; key studies must be cited.

## Reporting guidelines

Declare the relevant guideline in `draft.md` front matter or `venue.json`:

```yaml
reporting_guidelines: ["consort"]
```

Supported: `consort`, `prisma`, `strobe`, `coreq`, `care`, `tripod`, `arrive`.
`reporting check` and `manuscript check` verify structural coverage. The official
checklist remains the author’s responsibility.

## Venue profile

`venue.json` controls style, language, word/abstract/title limits, keyword
bounds, required sections, reporting guidelines and reference/figure/table
limits. `venue check` reports hard errors and soft warnings. A manuscript far
below the venue’s word limit is a warning, not a failure.

## Quality bar

- No placeholders (`TODO`, `TBD`, `FIXME`, `lorem`, `[insert`).
- No unsupported numbers; no precision inflation.
- Limitations are specific (design, sample, measurement, generalisability).
- Preprints labelled; version of record preferred.
- Persian manuscripts use RTL HTML and Vazirmatn; citations remain stable.

## Corpus-assisted style (optional)

`corpus analyze` builds a local style profile from lawful, user-supplied papers.
Use it for section order, tense, hedging and reporting conventions — never to
copy sentences. See `references/methods/academic-writing-corpus.md`.
