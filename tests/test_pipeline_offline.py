"""Full offline pipeline — gates 0–9 on a synthetic but realistic run."""

from __future__ import annotations

from conftest import full_quick_run, run_cli


def test_full_run_passes_all_gates(env):
    project, ids = full_quick_run(env)

    for phase in range(0, 9):
        code, result, err = run_cli("gate", "--phase", str(phase))
        assert result is not None, err
        assert result["pass"] is True, (phase, result["failures"])

    code, status, _ = run_cli("status", expect=0)
    assert status["next_failing"]["phase"] == 9  # retrospect is the last step
    assert "gate --phase 9" in status["hint"]

    code, build, _ = run_cli("report", "build", "--allow-flagged", expect=0)
    assert build["pass"] is True

    report_md = project / "report.md"
    report_html = project / "report.html"
    assert report_md.exists() and report_html.exists()
    text = report_md.read_text(encoding="utf-8")
    assert ids["cl1"] in text and ids["src_a"] in text
    assert "Executive Summary" in text and "Bibliography" in text
    html = report_html.read_text(encoding="utf-8")
    assert "<li>" in html and ids["cl1"] in html

    code, check, _ = run_cli("report", "check", expect=0)
    assert check["pass"] is True


def test_retrospect_then_gate9(env):
    project, ids = full_quick_run(env)
    run_cli("report", "build", expect=0)

    code, retro, err = run_cli(
        "learn", "retrospect", "--worked", "offline verify kept citations honest",
        "--failed", "no PDF locators available offline",
        "--suggestion", "add pdftotext-ladder eval", expect=0)
    assert retro["feedback_skipped"] is False
    assert retro["journaled"]
    payload = (project / "retrospective.json").read_text(encoding="utf-8")
    for key in ("worked", "failed", "budget_used", "metrics", "suggestions",
                "capability_candidate"):
        assert f'"{key}"' in payload

    code, gate9, _ = run_cli("gate", "--phase", "9")
    assert gate9["pass"] is True, gate9["failures"]


def test_status_reports_next_failing_phase(env):
    from conftest import seed_project

    seed_project(env)  # no sources yet
    code, status, _ = run_cli("status", expect=0)
    assert status["next_failing"]["phase"] == 3
    checks = {f["check"] for f in status["next_failing"]["failures"]}
    assert "sources_well_formed" in checks
