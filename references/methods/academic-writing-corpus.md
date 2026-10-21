# Method — Academic Writing Corpus

A small, lawful corpus helps match the conventions of a target field without
copying prose. The corpus is optional and local-only.

## Target

- ~60 papers: 50 English + 10 Persian.
- Six genres: empirical, review, theoretical, methods, case study, policy.
- Prefer open-access PDFs/XML with clear licenses.
- Keep a `LICENSE.md` or per-file license note; do not commit copyrighted PDFs.

## Layout

```text
corpus/
  empirical/…
  review/…
  theoretical/…
  methods/…
  case-study/…
  policy/…
  fa/…
```

## Analyze

```bash
R=".venv/bin/python scripts/research_ctl.py"
$R corpus analyze --dir corpus
$R corpus show
```

The analyzer records:

- section headings and order;
- abstract structure and length;
- citation density and style signals;
- hedging/booster phrases;
- tense and person distribution;
- paragraph and sentence length;
- numeric/reporting conventions.

## Use

- Choose section order and abstract shape.
- Match hedging strength to the evidence (no “proves” for a single trial).
- Match reporting detail (sample, effect size, CI, limitations).
- Match Persian conventions for RTL manuscripts.

## Do not

- paste corpus sentences into the manuscript;
- treat corpus frequency as evidence;
- include paywalled PDFs without permission;
- commit the corpus to a public repository.
