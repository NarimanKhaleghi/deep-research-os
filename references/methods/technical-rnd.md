# Method — Technical & R&D Research

Read this before phase 2 for: technology selection, feasibility, "is X mature",
benchmark/model/tooling questions, engineering best-practice claims.

## When to use
- Outdated documentation is actively harmful; the answer will drive engineering
  decisions, and the field moves fast.
- Also for "what broke / what changed" questions (API/service changes).

## Inputs
- Shelves: official docs + changelogs (web fetch, snapshotted), GitHub (repos,
  releases, issues, stars as *signals only*), arXiv/HN (frontier, tier-labeled),
  SEC/compliance docs for vendor stability.

## Procedure
1. **Pin the scope to versions** (phase 1): "Kubernetes" is not a query —
   "K8s 1.31 external secrets operators" is. Record the version window;
   deprecation timelines differ per minor release.
2. **Source hierarchy for technical truth:**
   - Spec/RFC > official docs > maintainer comments (issues/PRs) > release notes
     > high-karma blog posts > tutorials (often stale) > AI-generated content
     (excluded as evidence).
3. **Freshness is a dimension** (phase 5): rubric half-life for infra/ML topics
   is ~12–18 months. A 2024 tutorial may still pass — label the version it targets.
4. **Benchmarks get scrutiny:** who ran them, on what hardware, with what config?
   Vendor benchmarks = marketing until reproduced by a third party.
5. **Maturity assessment needs four probes:** adoption (registry downloads, GH
   activity), support (docs quality, response latency in issues), stability
   (breaking-change cadence, SemVer discipline), longevity (funding/backing).
   "Vibes per README" is not a probe.
6. **Reproduce minimal claims where cheap:** config snippets, version conflicts —
   if a claim is checkable in 5 minutes locally, check it and record the result
   as methodological evidence.

## Verification requirements
- Every API/config claim: cite the doc version (URL + accessed date + snapshot).
- "X is faster than Y": benchmark source + hardware + config; else downgrade to
  "vendor claims".
- Dependency health claims: check release recency and issue responsiveness at
  verify time (both can change within months).
- Community claims from HN/Reddit: tier 3; promote to source or drop.

## Gotchas
- **LLM-hallucinated docs:** tutorials written by models cite APIs that never
  existed — prefer docs, and cross-check signatures.
- **Silent deprecation:** the thing works but is deprecated (e.g., auth flow
  changes) — changelog sweep is mandatory.
- **Star-count theater:** stars measure marketing; check commit cadence and
  maintainer count instead.
- **Monorepo version drift:** examples for v1 copied into v2 docs; verify against
  the actual release tag you care about.
- **Benchmark gaming:** micro-benchmark wins that vanish in end-to-end pipelines.
- **Works-on-my-machine:** record the exact versions; "latest" is not a version.

## Worked mini-example
Question: *"RabbitMQ vs NATS JetStream for 50k msg/s event bus, self-hosted"*
Pin: current GA versions. Probes: official throughput docs + independent benchmark
repos (scrutinize configs), GH issue response times, breaking-change history.
Checkable locally: demo throughput on equivalent hardware (if feasible) → record.
Finding: conditional ("if you need persistence + replay semantics, X; else Y")
with the condition table as the headline artifact.
