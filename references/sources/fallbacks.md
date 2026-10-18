# Fallback Ladder — graceful degradation without silent gaps

Capability discovery (`doctor`) writes `~/.config/deep-research-os/capabilities.json`.
The router consults it at startup of every search. This file is the human-readable
contract for what happens when things are missing.

## The ladder (first available wins; every hop is logged)

1. **Dedicated MCP server** — Firecrawl / Exa / Tavily / Brave / Apify / Bright Data /
   Zotero / Docling. Richest results, possibly paid. Detected via MCP config files or
   env keys. Used only when profile allows cost and the free ladder failed for *this
   need* (never preemptively).
2. **Local infrastructure** — user's SearXNG (`http://127.0.0.1:8888`), Playwright MCP
   for JS-heavy pages, Camofox when configured. Free, private, no keys.
3. **Built-in keyless connectors** — the 12 catalog entries. Always available (network
   permitting). This is the guaranteed floor.
4. **Generic web fetch** — direct httpx + readability, when search found a URL but no
   API covers the site.
5. **Declared gap** — write the miss into `state.source_health` and the report's
   Limitations. *Never* silently drop coverage.

## Decision table

| Situation | Ladder response |
| --- | --- |
| MCP detected, free path works | Use free path; MCP reserved (budget discipline) |
| MCP detected, free path fails for this need | MCP call, cost journaled to `budget.spent_usd` |
| No MCP, SearXNG up | SearXNG for web-search shelf; APIs for the rest |
| No MCP, no SearXNG | Keyless connectors + DDG-lite fallback for web search |
| Connector 429/5xx after retries | Hop to next tier; log `source_health[service].failures` |
| Offline (`RESEARCH_OS_OFFLINE=1`) | Steps 1–4 disabled; snapshot-only verification; Limitations updated |
| Paywalled article, Unpaywall misses | `read --metadata-only`; credibility capped; note in source record |

## Budget interaction

- Profiles cap *paid* spend implicitly: `quick/standard` default `max_spend_usd: 0`.
  `deep: 2`, `max: declared`. `doctor` can print an estimated cost table.
- Any paid call requires `--allow-paid` on the triggering command *or* a brief
  front-matter `allow_paid: true`. Two gates, on purpose.

## Health reporting

`state.json.source_health` shape:

```json
{
  "openalex": {"attempts": 12, "failures": 1, "last_error": "429 @ 12:04Z"},
  "searxng":  {"attempts": 4,  "failures": 0},
  "firecrawl":{"attempts": 1,  "failures": 0, "cost_usd": 0.002}
}
```

`report build` folds non-trivial failures (≥2 or any error on a sole-shelf source)
into Limitations automatically. The learning loop reads the same table to
re-weight routing (a consistently failing source loses mass — bounded by ±10%
per cycle per `learning-protocol.md` §4).

## What we deliberately do NOT fall back to

- Scraping search-engine HTML beyond the tolerant DDG-lite endpoint (ToS risk).
- Any source requiring login or accepting ToS on the user's behalf.
- Paywalled full-text circumvention of any kind.
- Content farms / aggregators as evidence (they are at most a pointer to the
  primary source, logged as tier 3 lead).
