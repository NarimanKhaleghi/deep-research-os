# Full-Text Catalog — lawful acquisition, trust chain and coverage

`deep-research-os` is full-text-first for academic work, but it never bypasses a
paywall. This file is the contract for what counts as a verified full text, how
to acquire one lawfully, and how coverage is enforced.

## Legal boundary (hard)

Allowed:

- publisher open-access (gold/green/hybrid) PDFs or HTML;
- PubMed Central / Europe PMC JATS XML;
- arXiv, bioRxiv, medRxiv, SSRN, OSF preprints (labelled `preprint`);
- institutional or subject repositories (CORE, OpenAIRE, HAL, Zenodo, DOAJ);
- author manuscripts deposited in a repository;
- a file the user supplies in `inbox/`;
- interlibrary loan or an author request (generated template, user sends it).

Never:

- Sci-Hub, LibGen, Anna’s Archive, Z-Library or mirror domains;
- paywall bypass, proxy/cookie tricks, credential sharing;
- scraping a publisher page in violation of its terms;
- presenting an abstract, landing page, supplementary file or erratum as the
  article.

`lib/http.py` blocks known pirate hosts and private/loopback SSRF targets on the
initial URL and every redirect hop.

## Trust chain

A source is `verified` only when all three links agree:

```text
original artifact bytes  --SHA-256-->  fulltext.sha256
extracted text bytes     --SHA-256-->  fulltext.text_sha256
snapshot.sha256          ------------->  same text hash
```

`read_depth: full-text` is a compatibility hint, not proof. Gates use
`fulltext.status == "verified"` plus a passing `fulltext verify`.

Storage:

```text
sources/SRC-0001.pdf|xml|html     original bytes (immutable)
sources/SRC-0001.txt              extracted text (the snapshot)
sources/archive/…                 superseded originals, hash-suffixed
```

Replacing an artifact with different bytes archives the old file instead of
silently overwriting it.

## Status values

| Status | Meaning | Counts as full text? |
| --- | --- | --- |
| `verified` | identity + hash chain + sufficient text | yes |
| `abstract-only` | comprehensive abstract with a documented exception | no |
| `partial` | landing page/metadata/truncated text | no |
| `needs_ocr` | artifact exists but text is unusable without OCR | no |
| `failed` | acquisition or validation failed | no |

Coverage policy defaults (`state.fulltext_policy`):

- ≥80% of included sources `verified`;
- ≤20% `abstract-only`;
- 100% of key studies `verified`;
- 100% of critical claims supported by `verified` sources.

## Acquisition ladder

`resolver.resolve()` returns ranked candidates and `read --doi` tries them in
order, recording every attempt:

1. Europe PMC JATS (`fullTextXML`) — best structure and provenance;
2. Unpaywall `best_oa_location` + all OA locations;
3. OpenAlex OA locations (`pdf_url`, `oa_url`);
4. Semantic Scholar `openAccessPdf`;
5. arXiv / bioRxiv / medRxiv / OSF preprints;
6. DOAJ fulltext links;
7. Zenodo / HAL / OpenAIRE / CORE repository copies;
8. Crossref publisher links (only if actually open);
9. direct URL, if the user supplied one.

Landing-page HTML is stored as `partial`, never `verified`. A PDF that is only an
abstract, a login page, an erratum or supplementary material fails identity
validation.

## Identity validation

`fulltext.validate_identity()` checks, in order:

- DOI exact match when both sides carry one;
- normalized title fuzzy score ≥0.90;
- abstract similarity ≥0.75 when both abstracts exist;
- expected section presence (Introduction/Methods/Results/Discussion);
- text length ≥1,200 characters for `verified`;
- rejection of abstract-only PDFs, login pages, errata and supplementary-only
  files.

`--force` bypasses the strict identity check for a user-supplied file, but the
record keeps the validation result and the exception is visible in the ledger.

## Commands

```bash
R=".venv/bin/python scripts/research_ctl.py"

# DOI: metadata -> resolver -> download -> validate -> archive
$R read --doi 10.1038/s41586-024-00000-0 --angles "efficacy" --require-fulltext

# Local PDF/XML (user-supplied, lawful)
$R read --file ~/Downloads/paper.pdf --angles "methods"

# Metadata/abstract only (context; never counts as full text)
$R read --doi 10.1000/paywalled --metadata-only

# Documented abstract-only exception (comprehensive abstract required)
$R read --doi 10.1000/paywalled --allow-abstract \
  --abstract-reason "publisher permits abstract reuse; full text unavailable"

# Audit and coverage
$R fulltext verify
$R fulltext verify --source-id SRC-0003
$R fulltext coverage
$R fulltext assess --source-id SRC-0003

# ILL / author request template
$R fulltext request --source-id SRC-0003

# Manual inbox (copy files, then scan)
$R fulltext scan-inbox
$R fulltext scan-inbox --inbox ~/Downloads/dros-inbox
```

## Manual inbox

Create `inbox/` inside the project (or pass `--inbox`). Copy PDF/XML/HTML/TXT
files there. `fulltext scan-inbox` matches by DOI first, then title ≥0.90, creates
a source if needed, validates identity, archives the artifact and leaves the
user’s original file untouched. Do not rename files to force a match.

## Export and privacy

`export` excludes original full-text artifacts by default.
The ledger, extracted text snapshot, hashes and report remain. Use
`--include-fulltext` only for a private local backup; never publish that export.

## Failure handling

- No lawful full text: `read` fails with the attempt list. Use `--metadata-only`
  for context, `--allow-abstract` only with a comprehensive abstract and a reason,
  or add a file to `inbox/`.
- `needs_ocr`: the artifact is kept, but gates do not count it. Run OCR outside
  the tool, then `read --file` the OCR’d text/PDF.
- TLS/API failure: the resolver continues to the next provider and records the
  failure in `state.source_health`; the report’s Limitations names the gap.
