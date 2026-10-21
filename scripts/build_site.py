#!/usr/bin/env python3
"""build_site.py — render the bilingual landing site into ``docs/``.

GitHub Pages serves ``docs/`` from ``main``. Everything is static: two
pre-rendered pages (``/`` and ``/fa/``) with self-hosted subset fonts, plus
sample reports, sitemap, robots and ``llms.txt``. No client-side redirects.

Usage:
    python scripts/build_site.py                 # build docs/
    python scripts/build_site.py --check         # build + verify local links
    python scripts/build_site.py --out /tmp/x    # build elsewhere
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import jinja2

HERE = Path(__file__).resolve()
REPO = HERE.parent.parent
for entry in (REPO, REPO / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from scripts import __version__  # noqa: E402

SITE = REPO / "site"
ASSETS = SITE / "assets"
TEMPLATES = SITE / "templates"
DOCS = REPO / "docs"

LANGS = ("en", "fa")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return True


def _jsonld(lang: str, c: dict, site: dict, canonical: str, version: str) -> str:
    meta = c["meta"]
    base = site["base_url"]
    graph: list[dict[str, Any]] = [
        {
            "@type": "SoftwareApplication",
            "name": site["site_name"],
            "description": meta["description"],
            "url": canonical,
            "image": _join(base, c["cfg"]["og_image"]),
            "inLanguage": c["cfg"]["html_lang"],
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Linux, macOS, Windows",
            "softwareVersion": version,
            "codeRepository": site["repo_url"],
            "license": "https://opensource.org/license/mit",
            "author": {"@type": "Person", "name": site["author"]},
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "featureList": [item["title"] for item in c["features"]["items"]],
        },
        {
            "@type": "FAQPage",
            "inLanguage": c["cfg"]["html_lang"],
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
                }
                for item in c["faq"]["items"]
            ],
        },
        {
            "@type": "HowTo",
            "name": c["install"]["title"],
            "description": c["install"]["desc"],
            "inLanguage": c["cfg"]["html_lang"],
            "url": canonical + "#install",
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i,
                    "name": step["title"],
                    "text": f"{step['title']}: {step['cmd']}",
                }
                for i, step in enumerate(c["install"]["steps"], 1)
            ],
        },
    ]
    payload = {"@context": "https://schema.org", "@graph": graph}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _context(lang: str, content: dict, site: dict, version: str) -> dict[str, Any]:
    lang_cfg = site["langs"][lang]
    other = "fa" if lang == "en" else "en"
    page_path = lang_cfg["path"]
    canonical = _join(site["base_url"], page_path)
    prefix = "" if page_path == "" else "../"
    home = "./" if page_path == "" else "../"
    cfg = {
        **lang_cfg,
        "lang": lang,
        "other_lang": other,
        "canonical": canonical,
        "asset_prefix": prefix,
    }
    content = {**content, "cfg": cfg}
    return {
        "site": site,
        "cfg": cfg,
        "meta": content["meta"],
        "skip": content["skip"],
        "theme": content["theme"],
        "nav": content["nav"],
        "hero": content["hero"],
        "metrics": content["metrics"],
        "features": content["features"],
        "pipeline": content["pipeline"],
        "preview": content["preview"],
        "validation": content["validation"],
        "install": content["install"],
        "faq": content["faq"],
        "footer": content["footer"],
        "canonical": canonical,
        "asset_prefix": prefix,
        "home_href": home,
        "other_lang": other,
        "jsonld": _jsonld(lang, content, site, canonical, version),
        "version": version,
        "asset_version": _asset_version(),
    }


def _asset_version() -> str:
    digest = hashlib.sha256()
    for name in ("site.css", "site.js"):
        digest.update((ASSETS / name).read_bytes())
    return digest.hexdigest()[:10]


def _version(source: Path) -> str:
    try:
        import tomllib

        data = tomllib.loads(source.read_text(encoding="utf-8"))
        return str(data["project"]["version"])
    except Exception:
        return __version__


def _copy_assets(out: Path, warnings: list[str]) -> None:
    for name in ("site.css", "site.js", "favicon.svg"):
        if not _copy(ASSETS / name, out / "assets" / name):
            warnings.append(f"missing site asset: {name}")
    for name in ("og.png", "og-fa.png"):
        if not _copy(ASSETS / name, out / "assets" / name):
            warnings.append(f"missing social card: {name} (run the Playwright capture)")
    fonts = REPO / "assets" / "fonts"
    for font in sorted(fonts.glob("*.woff2")):
        _copy(font, out / "assets" / "fonts" / font.name)
    if (fonts / "licenses").is_dir():
        _copy(fonts / "licenses", out / "assets" / "fonts" / "licenses")
    if not any((out / "assets" / "fonts").glob("*.woff2")):
        warnings.append("no WOFF2 fonts copied — site typography will fall back")


def _copy_samples(out: Path, warnings: list[str], enabled: bool) -> None:
    if not enabled:
        warnings.append("samples skipped (--no-samples)")
        return
    en = REPO / "examples" / "sample-run"
    if _copy(en / "report.html", out / "samples" / "report.html"):
        _copy(en / "report.md", out / "samples" / "report.md")
    else:
        warnings.append("missing EN sample: examples/sample-run/report.html")
    fa = SITE / "samples" / "report-fa.html"
    if _copy(fa, out / "fa" / "samples" / "report.html"):
        _copy(fa.with_suffix(".md"), out / "fa" / "samples" / "report.md")
    else:
        warnings.append("missing FA sample: site/samples/report-fa.html")


def _sitemap(site: dict) -> str:
    base = site["base_url"].rstrip("/") + "/"
    rows = []
    for lang, path in (("en", ""), ("fa", "fa/")):
        alternates = "\n".join(
            f'    <xhtml:link rel="alternate" hreflang="{code}" href="{_join(base, p)}" />'
            for code, p in (("en", ""), ("fa", "fa/"), ("x-default", ""))
        )
        rows.append(
            "  <url>\n"
            f"    <loc>{_join(base, path)}</loc>\n"
            f"{alternates}\n"
            "  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )


def _llms(site: dict, c_en: dict, c_fa: dict, version: str) -> str:
    base = site["base_url"].rstrip("/") + "/"
    return (
        "# deep-research-os\n\n"
        f"> {c_en['meta']['description']}\n\n"
        f"Version {version} · MIT · {site['author']}\n\n"
        "## Pages\n\n"
        f"- English: {base}\n"
        f"- فارسی: {base}fa/\n"
        f"- Sample report (EN): {_join(base, 'samples/report.html')}\n"
        f"- Sample report (FA): {_join(base, 'fa/samples/report.html')}\n"
        f"- Source: {site['repo_url']}\n"
        f"- Docs: {site['docs_url']}\n\n"
        "## What it does\n\n"
        + "\n".join(f"- {item['title']}: {item['desc']}" for item in c_en["features"]["items"])
        + "\n\n## Install\n\n"
        + "\n".join(f"{i}. {step['title']}: `{step['cmd'].splitlines()[0]}`"
                    for i, step in enumerate(c_en["install"]["steps"], 1))
        + "\n\n"
        f"## In Persian\n\n{c_fa['meta']['description']}\n"
    )


def _check_links(out: Path) -> list[str]:
    missing: list[str] = []
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for attr in ("href", "src"):
            marker = f'{attr}="'
            start = 0
            while True:
                i = text.find(marker, start)
                if i < 0:
                    break
                j = text.find('"', i + len(marker))
                start = j + 1
                if j < 0:
                    break
                url = html.unescape(text[i + len(marker):j])
                if not url or url.startswith(("#", "http://", "https://", "mailto:", "data:", "//")):
                    continue
                clean = url.split("#", 1)[0].split("?", 1)[0]
                if not clean:
                    continue
                target = (page.parent / clean).resolve()
                if target.is_dir():
                    target = target / "index.html"
                if not target.exists():
                    missing.append(f"{page.relative_to(out)} → {url}")
    return missing


def build(out: Path = DOCS, samples: bool = True, quiet: bool = False) -> dict[str, Any]:
    site = _read_json(SITE / "site.json")
    site["base_url"] = site["base_url"].rstrip("/") + "/"
    contents = {lang: _read_json(SITE / "content" / f"{lang}.json") for lang in LANGS}
    warnings: list[str] = []
    version = _version(REPO / "pyproject.toml")

    out = out.resolve()
    if out == REPO or out in REPO.parents:
        raise SystemExit("refusing to build the site over the repository root")
    cname = None
    if out.exists():
        candidate = out / "CNAME"
        if candidate.exists():
            cname = candidate.read_text(encoding="utf-8").strip()
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    if cname:
        _write(out / "CNAME", cname)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    index = env.get_template("index.html.j2")
    pages = 0
    for lang in LANGS:
        ctx = _context(lang, contents[lang], site, version)
        target = out / site["langs"][lang]["path"] / "index.html"
        _write(target, index.render(**ctx))
        pages += 1

    notfound = env.get_template("404.html.j2").render(site=site)
    _write(out / "404.html", notfound)
    _write(out / ".nojekyll", "")

    _copy_assets(out, warnings)
    _copy_samples(out, warnings, samples)

    _write(out / "robots.txt",
           "User-agent: *\nAllow: /\n\n"
           f"Sitemap: {_join(site['base_url'], 'sitemap.xml')}\n")
    _write(out / "sitemap.xml", _sitemap(site))
    _write(out / "llms.txt", _llms(site, contents["en"], contents["fa"], version))

    missing = _check_links(out)
    for link in missing:
        warnings.append(f"broken local link: {link}")
    result = {
        "ok": not missing,
        "out": str(out),
        "pages": pages,
        "version": version,
        "samples": samples,
        "warnings": warnings,
        "broken_links": missing,
    }
    if not quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="build_site", description="build the bilingual landing site")
    ap.add_argument("--out", default=str(DOCS), help="output directory (default: docs/)")
    ap.add_argument("--no-samples", action="store_true", help="do not copy sample reports")
    ap.add_argument("--check", action="store_true", help="exit 1 when local links are broken")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    result = build(Path(args.out), samples=not args.no_samples, quiet=args.quiet)
    sys.exit(0 if (result["ok"] or not args.check) else 1)


if __name__ == "__main__":
    main()
