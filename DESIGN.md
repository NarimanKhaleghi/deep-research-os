# Design System — “Research Instrument”

The visual language for deep-research-os output (HTML reports) and its public
site. Direction A of the design lab: an editorial, instrument-like surface that
reads as a *research ledger made printable* — paper tones, hairline rules,
stamped verification marks, mono metadata.

Applies to: `templates/report.html.j2`, `templates/assets/report.css`,
`site/`, `docs/`.

## Principles

1. **Evidence looks like evidence.** Claims, IDs (`FN-`/`CL-`/`SRC-`) and hashes
   are set in mono, hairline-ruled, never decorative.
2. **Paper, not dashboard.** Warm paper backgrounds, ink text, one accent. No
   glassmorphism, no gradients-as-decoration.
3. **One accent, earned.** Green (`--accent`) marks verification, links, and
   live state only.
4. **Bilingual by construction.** Every layout is LTR/RTL symmetrical via
   logical properties; Persian never gets a degraded layout.
5. **Print is a first-class target.** Reports must print clean to A4.

## Tokens

### Color

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--paper` | `#f4f1e8` | `#101412` | Page background |
| `--paper2` | `#fbf9f2` | `#171c18` | Cards, sheets, insets |
| `--ink` | `#171a1a` | `#ece9dd` | Primary text |
| `--muted` | `#5f655d` | `#a0a79b` | Secondary text |
| `--line` | `rgba(23,26,26,.14)` | `rgba(236,233,221,.14)` | Hairline rules |
| `--line2` | `rgba(23,26,26,.30)` | `rgba(236,233,221,.30)` | Strong rules, borders |
| `--accent` | `#0c6b50` | `#71d8ae` | Verification, links, live |
| `--accent-soft` | `#dbe9e1` | `#162d25` | Accent wash |
| `--stamp` | `#0c6b50` | `#71d8ae` | Stamps/verdict marks |

Contrast: ink/paper ≥ 12:1, muted/paper ≥ 4.6:1, accent on paper ≥ 4.6:1
(both themes). Never use accent for body text.

### Type

| Token | Stack | Role |
| --- | --- | --- |
| `--display` | `"Instrument Serif", Georgia, serif` | h1, hero numerals |
| `--display-rtl` | `"Vazirmatn", Tahoma, sans-serif` | RTL display |
| `--body` | `"Source Serif 4", Georgia, serif` | Long-form prose |
| `--ui` | `"Inter", system-ui, sans-serif` | Labels, nav, UI |
| `--mono` | `"IBM Plex Mono", ui-monospace, monospace` | IDs, hashes, metadata |

RTL: `--display`, `--body`, `--ui`, `--mono` all resolve to Vazirmatn; mono
labels become `--ui` at +0.1rem with `letter-spacing: 0`.

Scale (clamp, mobile→desktop): display `clamp(54px,7vw,110px)` hero,
`clamp(34px,4.3vw,58px)` h2, `clamp(26px,2.6vw,34px)` h3; body
`clamp(17px,1.45vw,20px)` lede, `1rem` prose; labels `0.6–0.85rem` mono.
RTL display sizes drop ~30% (Vazirmatn is physically wider).

### Space & layout

- Page max width `1240px`; gutters `clamp(20px,4vw,44px)`.
- Vertical rhythm: 8px base; section padding `clamp(56px,7vw,104px)`.
- Hairlines: `1px solid var(--line)` between rows, `--line2` for frame edges.
- Grids collapse 3→2→1 at 980px/640px; mobile tables become stacked cards
  (each cell labeled via `data-label`).
- Focus: `2px` accent outline, `offset: 2px`, never removed.

### Motion

- Easing `cubic-bezier(.22,1,.36,1)`, durations 200–900ms.
- Entrance: ledger rows stagger `0.1s` apart; sheets slide `+22px` and settle.
- Theme switch: 350ms color transition only.
- All motion respects `prefers-reduced-motion: reduce` (transforms off, states
  still change). No motion is load-bearing: content renders fully without JS.

## Components

- **Ledger sheet** — paper2 card, double hairline frame (outer border + inset
  `::after`), soft long shadow. Hero and report preview.
- **Ledger row** — claim + mono source trail (`FN-·· · CL-···· · SRC-····`) +
  verdict chip. The core evidence unit; reused in reports as finding cards.
- **Verdict chip** — mono, accent border, no fill: `VERIFIED`, `WEAK`,
  `UNVERIFIED`, `CONTRADICTED`.
- **Stamp** — rotated accent outline label (`VERIFIED · 24/24`) pinned to a
  sheet corner; rotates mirror-image in RTL.
- **Metrics band** — 4-up ruled cells, display numerals over mono labels.
- **Toolbar** — sticky report bar: theme toggle, language toggle, print, TOC.
- **TOC rail** — mono list, dotted leaders, active item accent; hidden < 980px.
- **Callout** — 2px accent inline-start border, tinted wash, used for
  limitations/contradictions. Variants: `warn` (amber `#9a5b13`/dark
  `#f0b35e`), `danger` (brick `#8f2f2f`/dark `#e88b8b`).

## Report template rules

- Sections in fixed order: Executive Summary, Requirement Coverage,
  Findings, Literature Comparison Matrix, Contradictions, Methodology
  (search & screening), Limitations, Bibliography, Claim & Evidence Index.
- Every finding: strength badge (established/supported/tentative), claims with
  status chips, inline anchor links to `#ref-SRC-xxxx` and `#claim-CL-xxxx`.
- Bibliography: hanging indent, APA-7, `[SRC-xxxx]` mono anchor, credential
  band + sha256 in a muted audit line.
- Open contradictions always visible; never collapsed by default.
- Dark mode via `prefers-color-scheme` + manual toggle (persisted
  `localStorage`, `data-theme` on `<html>`); print always light.

## Landing site rules

- Same tokens; hero = ledger sheet with live verification loop animation.
- Two static pages: `/` (en) and `/fa/` (fa), reciprocal `hreflang`, no
  redirects. Toggle swaps to the sibling URL.
- Motion budget: hero stagger, scroll reveals (`IntersectionObserver`), metric
  count-ups, pipeline draw. Nothing beyond that.
- All content in `site/content/` — copy changes never touch layout code.

## Implementation map

- **Language** — `scripts/core/report_i18n.py` resolves EN/FA from the brief
  title/question, with `--lang en|fa` as the override; the chosen language is
  recorded as `state.report_lang`. It owns every label/heading and the bilingual
  requirement-anchor aliases. Gates test both heading languages.
- **Fonts** — only pre-subset WOFF2 files ship (`assets/fonts/`, recipes and OFL
  licenses included). `report_assets.py` base64-embeds just the needed set per
  language, so report builds never require fontTools or network access.
- **Report render** — `report_builder.py` builds one context and renders HTML and
  Markdown from it; claim/source anchors come from the same claim index.
- **Site render** — `site/content/{en,fa}.json` + `site/templates/` +
  `scripts/build_site.py` → `docs/`. `site/site.json` is the only place the
  public base URL is declared; templates use relative assets and configured
  sibling paths. CSS/JS URLs carry a content hash.
- **QA contract** — build fails on broken local links; axe WCAG AA (0
  violations), Lighthouse mobile accessibility/best-practices/SEO 100, EN+FA
  at 390/1440 px without horizontal overflow. Sample reports are real runs, not
  mock copy.
