# Retraction & Integrity Checks

Academic retractions are rising; fabricated and paper-mill content is now a
standard attack on research quality. These checks are mandatory at phase 5
(assess) and phase 6 (verify).

## Checks by source type

| Source type | Check | Where |
| --- | --- | --- |
| DOI-bearing work | `is_retracted` flag | OpenAlex `works/{doi}` |
| DOI-bearing work | `update-to` relations (retraction/correction/withdrawal) | Crossref `works/{doi}` |
| Biomedical | Publication type "Retracted Publication"; expression-of-concern notices | PubMed |
| Preprint→paper | Journal version exists & matches claims taken from preprint | OpenAlex cross-ref |
| Any URL | Liveness + content hash vs snapshot | snapshot module |
| Domain | Impersonation check (fake journal/registry clones) | heuristics on domain vs venue name |

## Rules

1. **Retracted source → band D, dependent claims re-flagged.** Claims resting on it
   get status `contradicted` (pending adjudication) and must be dropped from
   findings unless independently re-supported.
2. **Expression of concern** (EoC): source capped at C; claims marked
   `weakly_supported` at best, with the EoC noted inline in the report.
3. **Correction notice:** refetch the corrected version; if numbers changed, the
   old numbers are `superseded` in their claims.
4. **Preprint with later peer-reviewed version:** prefer the journal version;
   if numbers differ, journal wins (vintage + review ladder step).
5. **Paper-mill signals** (raised in rationale, not auto-fail): template abstracts,
   citation cartels (self-citation cluster), suspicious author patterns, venue not
   indexed. Any two signals → recommend a second corroborating source, regardless
   of band.
6. **Fabricated-citation defense** (phase 6 verify): the title/DOI/author triple
   must co-resolve. If DOI resolves to a different title (fuzzy <0.75) →
   `fabrication_suspected`, source quarantined from findings and named in the
   verify report. Known hallucination patterns: real-author + fake-title,
   real-title + invented DOI, plausible-journal + nonexistent article.
7. **Re-check window:** retraction status is re-checked at verify time for all
   cited works, not just when collected (retractions lag citations).

## Data sources for the checks (all keyless)

- OpenAlex: `is_retracted`, `cited_by_api_url`, work metadata.
- Crossref: `update-to` array (retraction/correction notices), canonical metadata.
- PubMed: E-utilities full record includes retraction publication types.
- Retraction Watch DB is *not* API-keyless; where a check specifically needs it
  (contested cases), record as "not checked — outside toolset" in Limitations.

## What the run records

`verify_report.json` keeps, per DOI: `resolved`, `title_match` (score),
`retraction.status` ∈ {clean, retracted, eoc, corrected, unknown},
`checked_at`, `method`. Unknown (network/offline) is a legitimate value — but it
must propagate: any claim resting on an `unknown` source is capped
`weakly_supported` in offline runs, and the Limitations section says why.

## Escalation to the learning loop

Repeated fabrication/retraction flags from one source family or domain become a
`source_health` signal and, past threshold, a **source retirement proposal**
(approval required). The watchlist can also carry integrity watches (e.g., a
journal previously flagged). This is how the toolset hardens over time without
silent policy changes.
