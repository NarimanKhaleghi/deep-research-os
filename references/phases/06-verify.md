# Phase 6 — Verify

**So that:** no claim sails into synthesis un-checked: citations resolve, numbers match their quotes, contradictions are surfaced, and the report's citation precision is measured — not assumed.

## Inputs

- `evidence.jsonl`, `sources/SRC-*.json` (with credibility), `claims.jsonl` (drafts).

## Procedure

1. **Draft claims** from evidence (`claims add`) — one statement per claim:
   - `type`: `statistic|causal|forecast|opinion|methodological|definition`;
   - `kind`: `empirical` (default) | `normative` | `theoretical`. Mark
     regulatory/legal statements `--kind normative` — they must be backed by an
     official/primary source and by a quote that actually says what is
     prohibited/required;
   - `tags` (topic axes — these power contradiction pairing);
   - `evidence_ids` it rests on; numbers auto-parsed from text.
2. **Run verification** — `verify` executes:
   - **Citation resolution:** DOI lookup (doi.org / Crossref), URL liveness,
     title fuzzy-match vs. the registry record. ≥0.90 verified · 0.75–0.89 manual
     review · <0.75 mismatch → `fabrication_suspected` flag.
   - **Quote integrity:** claim text must be entailed by its evidence quotes —
     you confirm entailment; the machine confirms quote-in-snapshot.
   - **Numeric consistency:** every number in a claim must appear in its quotes
     with equal-or-greater precision (`96.555% ≠ 97%`: silent precision loss fails).
   - **Modality check:** a claim phrased as prohibition/obligation ("X may not…",
     "الزام…") must have a supporting quote containing normative language;
     otherwise `modality_mismatches` → downgraded to weakly_supported.
   - **Primary-source rule:** normative claims need an official/primary source
     (regulation, statistics bureau, central bank, filing). Without one:
     `primary_source_gaps`.
   - **Staleness:** official documents older than 18 months backing a normative
     claim produce `staleness_warnings` — re-check for an updated regulation
     before treating it as current.
   - **Corroboration:** critical claims (statistics, causal) need ≥2 independent
     origins (different registered domain / publisher — syndication doesn't count).
3. **Scan contradictions** — `contradictions scan` pairs claims by tag overlap and
   detects numeric conflicts (±tolerance) and polarity conflicts ("rose" vs "fell").
   Adjudicate each with the protocol (`quality/contradiction-protocol.md`) or log it
   unresolved — both are legitimate end states; hiding is not.
4. **Classification is set by results**, not by preference: each claim becomes
   `supported | weakly_supported | contradicted | unverifiable` (+ `resolved` after
   adjudication re-check). Weakly-supported claims may ship only if labeled.
5. **Re-verify on retraction:** if step 2 reveals a retraction upstream, downgrade
   dependent claims and re-scan.

## Artifacts

- `verify_report.json` — per-source verification results, per-claim checks,
  metrics: `citation_precision`, `corroboration_gaps`, `number_conflicts`,
  `modality_mismatches`, `primary_source_gaps`, `staleness_warnings`.
- `claims.jsonl` updated statuses; `contradictions.jsonl` records.
- Markers `state.ran.last_verify_at`, `state.ran.last_contradictions_scan_at`.

```bash
$R claims add --text "EU EV sales grew 36% in 2025" --type statistic \
              --tags "ev,eu,market" --evidence EV-0007,EV-0012 --critical
$R claims add --text "The central bank requires banks to retain final credit risk" \
              --kind normative --evidence EV-0021
$R sources update --source-id SRC-0011 --as-of 1402-10-14
$R verify --online            # --offline = snapshot-integrity checks only
$R contradictions scan
$R contradictions adjudicate CX-0002 --resolution source_a_wins --rationale "…"
$R gate --phase 6
```

## Complete when (machine-checked by `gate --phase 6`)

- [ ] `verify_report.json` exists and is newer than the newest claim.
- [ ] Every claim has a `status` from the enum and valid `evidence_ids` (all existing).
- [ ] Every claim with `critical: true` has ≥2 origins *or* is `weakly_supported`
      with an explicit note.
- [ ] Citation precision computed; `fabrication_suspected` list present (may be empty).
- [ ] `contradictions scan` ran after the last claim change; every `contradicted`
      claim links ≥1 contradiction record; every contradiction is `adjudicated` or
      `open` with a reason (open ones must appear in the report).
- [ ] Numeric checks: zero unacknowledged number mismatches.
- [ ] Normative claims: no unaddressed `modality_mismatches` or
      `primary_source_gaps`; `staleness_warnings` acknowledged in the claim wording
      or Limitations.

## Failure modes

| Mode | Smell | Fix |
| --- | --- | --- |
| Citation theater | DOI present but resolves elsewhere | Fix mapping or drop the claim |
| Precision laundering | "97%" from a 96.555% source | Restore full precision or downgrade |
| Echo corroboration | 3 sources, 1 press release | Independent origins or downgrade |
| Contradiction burial | Conflicting numbers both reported as fact | Adjudicate per protocol or mark both |

## Tips

- `verify --offline` is legitimate for air-gapped runs — but say so in Limitations.
- The contradiction scan is cheap; run it after *any* claim change, not once.
- A run with zero contradictions among 20+ claims usually means weak extraction
  (you pulled only friendly sources), not a harmonious world.
