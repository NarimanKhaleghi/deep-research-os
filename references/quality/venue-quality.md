# Venue Profile Quality

`venue.json` makes journal constraints explicit and machine-checkable.

## Defaults

```json
{
  "name": "Target venue",
  "style": "apa",
  "language": "en",
  "word_limit": 8000,
  "abstract_limit": 300,
  "title_limit": 20,
  "keyword_min": 3,
  "keyword_max": 8,
  "sections": ["Abstract", "Introduction", "Methods", "Results",
               "Discussion", "Conclusion", "References"],
  "reporting_guidelines": [],
  "blind_review": true,
  "reference_limit": null,
  "figure_limit": null,
  "table_limit": null
}
```

## Commands

```bash
R=".venv/bin/python scripts/research_ctl.py"
$R venue init
$R venue check
```

## Hard errors

- unknown citation style;
- word count above the venue limit;
- abstract above the limit;
- fewer than `keyword_min` or more than `keyword_max` keywords;
- declared reporting guideline missing structural items.

## Warnings

- word count below 55% of the venue limit (likely under-developed);
- other soft constraints recorded for the author.

## Choosing a venue

1. Match scope and audience, not prestige alone.
2. Check open-access policy and full-text availability.
3. Check word/abstract/figure limits before writing.
4. Check the reporting guideline the venue expects.
5. Record the profile in `venue.json` so the manuscript and checks agree.
