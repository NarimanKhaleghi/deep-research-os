"""Report HTML/PDF-facing output: language, embedded assets, anchors, appendix."""

from __future__ import annotations

from conftest import full_quick_run, run_cli


def test_report_defaults_to_english_with_embedded_fonts(env):
    project, ids = full_quick_run(env)
    html = (project / "report.html").read_text(encoding="utf-8")
    md = (project / "report.md").read_text(encoding="utf-8")

    assert '<html lang="en" dir="ltr">' in html
    assert "data:font/woff2;base64" in html
    assert "@font-face" in html
    assert '<script>' in html  # theme/Toc enhancement, no external request
    assert f'id="ref-{ids["src_a"]}"' in html
    assert f'id="claim-{ids["cl1"]}"' in html
    assert "Claim &amp; Evidence Index" in html
    assert 'class="finding"' in html and 'class="claim"' in html

    assert "## Executive Summary" in md
    assert "## Bibliography" in md
    assert "## Claim & Evidence Index" in md
    assert f"[{ids['cl1']}]" in md


def test_report_persian_language_rtl_and_gates_pass(env):
    project, ids = full_quick_run(env)
    code, data, _ = run_cli("report", "build", "--lang", "fa", expect=0)
    assert data["lang"] == "fa" and data["pass"] is True

    html = (project / "report.html").read_text(encoding="utf-8")
    md = (project / "report.md").read_text(encoding="utf-8")

    assert '<html lang="fa" dir="rtl">' in html
    assert "Vazirmatn" in html
    assert "خلاصهٔ اجرایی" in html
    assert "یافته‌ها" in html
    assert "نمایهٔ ادعاها و شواهد" in html
    assert f'id="ref-{ids["src_a"]}"' in html
    assert f'id="claim-{ids["cl1"]}"' in html

    assert "## خلاصهٔ اجرایی" in md
    assert "## یافته‌ها" in md
    assert "## منابع" in md
    assert "## نمایهٔ ادعاها و شواهد" in md
    assert "No waivers" not in html and "No waivers" not in md
    assert "Weakly supported / contradicted claims" not in html

    # gates are language-agnostic and the run stays green after a rebuild
    code, check, _ = run_cli("report", "check", expect=0)
    assert check["pass"] is True


def test_language_detection_heuristic():
    from core.report_i18n import detect, resolve

    assert detect("این یک پرسش پژوهشی فارسی است") == "fa"
    assert detect("Does intermittent fasting reduce lean mass?") == "en"
    assert resolve("en", "پرسش فارسی") == "en"
    assert resolve(None, "پرسش فارسی", "") == "fa"


def test_legacy_english_anchor_resolves_in_persian_report(env):
    project, _ = full_quick_run(env)
    run_cli("requirements", "add", "--text", "Every finding is reported with citations",
            "--id", "RQ-90", expect=0)
    run_cli("requirements", "map", "--requirement-id", "RQ-90",
            "--target", "Findings", expect=0)
    code, data, _ = run_cli("report", "build", "--lang", "fa", expect=0)
    assert data["pass"] is True
    code, cov, _ = run_cli("requirements", "list", expect=0)
    row = next(r for r in cov["rows"] if r["id"] == "RQ-90")
    assert row["status"] == "mapped"
