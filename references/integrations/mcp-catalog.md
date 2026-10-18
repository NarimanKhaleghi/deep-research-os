# MCP Integration Catalog — optional turbo layers

deep-research-os runs with **zero** of these installed. Each adds a capability
(the "turbo" ladder in `sources/fallbacks.md`). `doctor.py` detects existing MCP
servers and API keys automatically; this file is the human-readable map plus
ready-to-paste configs.

## Detection rules

`doctor` looks for MCP server configs in common locations (`~/.config/opencode/`,
`~/.claude/`, project `.mcp.json`, etc.) and for env keys. Detected capabilities
are written to `~/.config/deep-research-os/capabilities.json`. The router consults
that file — no manual wiring.

## Catalog (by need)

| Need | Turbo option | Key env | Cost model | Notes |
| --- | --- | --- | --- | --- |
| JS-heavy / anti-bot pages | **Playwright MCP** | none | free | Fallback for `web fetch` failures |
| Structured web extraction | **Firecrawl** | `FIRECRAWL_API_KEY` | paid, per page | Snapshot-friendly; respect brief `allow_paid` |
| Semantic/neural search | **Exa** | `EXA_API_KEY` | paid, per query | Great for "find like this" expansion |
| News-grade search | **Tavily** | `TAVILY_API_KEY` | paid | Fast news shelf; good FA support |
| Privacy search | **Brave Search** | `BRAVE_API_KEY` | free tier | Independent index (design choice) |
| Scraping at scale | **Apify** | `APIFY_TOKEN` | paid | Only for approved large crawls |
| Residential access | **Bright Data** | creds | paid | Last resort; ToS reviewed per use |
| Reference manager | **Zotero** | local | free | Import citations into the bibliography |
| Notebook execution | **Jupyter MCP** | local | free | For data-analysis method's reproducibility |
| Document conversion | **Docling** | local/GPU | free | Better PDF→structure than pdftotext for tables |
| Reddit deep-dive | **Dialog community server** | none/paid | varies | Community sentiment (tier 3, labeled) |
| Financial data | **Yahoo Finance / market data MCPs** | none/paid | varies | Corroborate with EDGAR; never sole source |

## Config snippets

OpenCode / Claude-style (`opencode.jsonc` / `claude_desktop_config.json`):

```jsonc
{
  "mcp": {
    "firecrawl": {
      "type": "local",
      "command": ["npx", "-y", "firecrawl-mcp"],
      "environment": { "FIRECRAWL_API_KEY": "{env:FIRECRAWL_API_KEY}" }
    },
    "exa": {
      "type": "local",
      "command": ["npx", "-y", "exa-mcp-server"],
      "environment": { "EXA_API_KEY": "{env:EXA_API_KEY}" }
    }
  }
}
```

(Remote-hosted MCPs use their published URLs; keep keys in env, never in the repo.)

## Governance hooks

- **Budget:** every paid call is journaled to `state.budget.spent_usd`; profiles
  have `max_spend_usd` ceilings (`budget-policy.md`). Paid path requires
  `--allow-paid` or `brief.allow_paid: true`.
- **Learning:** per-MCP outcomes (success/failure/latency/unique-yield) feed
  `source_stats.json` under the MCP's id, same as built-in connectors — so the
  router learns when a turbo layer is worth its cost per domain.
- **Privacy:** when `brief.privacy_mode: true`, cloud MCPs are skipped entirely and
  the local ladder is used — always.
- **Never required:** no phase doc, gate, template, or eval depends on any MCP;
  the offline eval suite passes with all of them absent.
