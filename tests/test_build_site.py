"""Landing-site build: bilingual pages, asset wiring, SEO contract."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import build_site


def test_site_builds_bilingual_pages(tmp_path):
    out = tmp_path / "docs"
    result = build_site.build(out, samples=True, quiet=True)
    assert result["ok"], result["warnings"]
    assert result["pages"] == 2

    en = (out / "index.html").read_text(encoding="utf-8")
    fa = (out / "fa" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en" dir="ltr">' in en
    assert '<html lang="fa" dir="rtl">' in fa
    assert 'href="https://narimankhaleghi.github.io/deep-research-os/"' in en
    assert 'href="https://narimankhaleghi.github.io/deep-research-os/fa/"' in fa
    assert 'hreflang="x-default"' in en
    assert 'hreflang="x-default"' in fa
    assert "assets/og.png" in en
    assert "assets/og-fa.png" in fa
    assert "font/woff2" in en

    graph = json.loads(re.search(
        r'<script type="application/ld\+json">(.*?)</script>', en, re.S).group(1))["@graph"]
    assert [n["@type"] for n in graph] == ["SoftwareApplication", "FAQPage", "HowTo"]

    for asset in ("site.css", "site.js", "favicon.svg", "fonts/vazirmatn-var.woff2"):
        assert (out / "assets" / asset).is_file(), asset
    assert (out / "samples" / "report.html").is_file()
    assert (out / "fa" / "samples" / "report.html").is_file()
    assert (out / ".nojekyll").is_file()

    ET.parse(out / "sitemap.xml")
    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://narimankhaleghi.github.io/deep-research-os/sitemap.xml" in robots
    assert '# deep-research-os' in (out / "llms.txt").read_text(encoding="utf-8")
