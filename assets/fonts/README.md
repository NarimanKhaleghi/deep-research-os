# Bundled Fonts

All fonts in this directory are subset to the glyphs the report template and
landing site actually use, converted to WOFF2, and self-hosted so that generated
reports and published pages need zero network requests.

| File | Family | Role | Scripts |
| --- | --- | --- | --- |
| `instrument-serif.woff2` | Instrument Serif 400 | Display / editorial headings | Latin |
| `instrument-serif-italic.woff2` | Instrument Serif 400 italic | Display emphasis | Latin |
| `source-serif-var.woff2` | Source Serif 4 (opsz,wght) | Long-form body text | Latin |
| `source-serif-italic.woff2` | Source Serif 4 italic | Body emphasis / APA titles | Latin |
| `inter-var.woff2` | Inter (wght) | UI labels, captions | Latin |
| `ibm-plex-mono.woff2` | IBM Plex Mono 400/500 | IDs, hashes, metadata | Latin |
| `vazirmatn-var.woff2` | Vazirmatn (wght) | Body, UI, display | Persian/Arabic + Latin |

Subsetting recipe (fontTools):

```bash
fonttools subset <file>.ttf --flavor=woff2 --no-hinting \
  --unicodes="U+0020-007E,U+00A0-00FF,U+2000-200F,U+2010-2027,U+2030-205E,U+2190-2193,U+2212,U+2713,U+2717,U+FEFF,U+FFFD" \
  --layout-features='kern,liga,clig,calt,ccmp'
# Vazirmatn additionally keeps U+0600-06FF,U+0750-077F,U+08A0-08FF,
# U+200C-200D,U+2010-2011,U+FB50-FDFF,U+FE70-FEFF and all layout features
# required for Arabic shaping.
```

Licenses (SIL Open Font License 1.1) are copied verbatim in `licenses/`.
