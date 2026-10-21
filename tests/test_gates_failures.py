"""Gate failure modes — the traps the quality gates exist to catch."""

from __future__ import annotations

from conftest import add_source, full_quick_run, run_cli, seed_project


def test_quote_not_in_snapshot_fails_gate4(env):
    project = seed_project(env)
    sid, _ = add_source(project, text="The snapshot contains only this sentence.",
                        title="Study A", url="https://example.org/a")

    code, ev, _ = run_cli("evidence", "add", "--source-id", sid, "--locator", "p.1",
                          "--quote", "This sentence never appeared in the page at all",
                          expect=0)
    assert ev["validation"]["quote_found"] is False
    assert "warning" in ev

    code, gate4, _ = run_cli("gate", "--phase", "4")
    assert gate4["pass"] is False
    names = {f["check"] for f in gate4["failures"]}
    assert "evidence_valid" in names
    assert any("quote∉snapshot" in f["detail"] for f in gate4["failures"])


def test_number_drift_marks_weak_and_report_flags_label(env):
    project = seed_project(env)
    sid, _ = add_source(
        project, text="Efficiency improved to 96.555% during 2024.",
        title="Efficiency report", url="https://example.org/efficiency",
        doi="10.1234/eff.2024", published="2025-03-01")
    run_cli("credibility", "score", expect=0)
    _, ev, _ = run_cli("evidence", "add", "--source-id", sid, "--locator", "p.2",
                       "--angle", "physiology",
                       "--quote", "Efficiency improved to 96.555% during 2024", expect=0)
    _, cl, _ = run_cli("claims", "add", "--text", "Efficiency reached 97% in 2024",
                       "--type", "statistic", "--tags", "efficiency",
                       "--angles", "physiology", "--evidence", ev["evidence_id"], expect=0)
    run_cli("verify", expect=0)
    run_cli("contradictions", "scan", expect=0)

    code, verify, _ = run_cli("verify", expect=0)
    assert verify["number_mismatches"], "precision-loss drift must be recorded"
    assert verify["number_mismatches"][0]["claim_status"] == "weakly_supported"

    # gate 6 passes: the mismatch is acknowledged (claim labeled weak)
    code, gate6, _ = run_cli("gate", "--phase", "6")
    assert gate6["pass"] is True, gate6["failures"]

    # an *established* finding leaning on the weak claim must fail report gates
    run_cli("findings", "new", "--title", "Efficiency outcome summary",
            "--strength", "established", "--confidence", "high",
            "--claims", cl["claim_id"],
            "--body", f"Efficiency reached 97% in 2024 [{cl['claim_id']}].",
            expect=0)
    code, build, _ = run_cli("report", "build")
    assert code == 1 and build["pass"] is False
    assert any(c["name"] == "weak_labeled" for c in build["failures"])

    code, flagged, _ = run_cli("report", "build", "--allow-flagged", expect=0)
    assert flagged["pass"] is True
    downgraded = [c for c in flagged["checks"] if c.get("downgraded")]
    assert any(c["name"] == "weak_labeled" for c in downgraded)
    # downgrades are written into Limitations
    report_text = (project / "report.md").read_text(encoding="utf-8")
    assert "Gate downgrades via --allow-flagged" in report_text


def test_placeholder_regex_catches_bracket_and_ellipsis():
    from core import manuscript, report_builder

    for rx in (manuscript.PLACEHOLDER_RE, report_builder.PLACEHOLDER_RE):
        assert rx.search("see [insert citation] here")
        assert rx.search("TODO: tighten")
        assert not rx.search("sha256 abc123…")


def test_placeholder_marker_fails_report(env):
    project, ids = full_quick_run(env)
    finding = project / "findings" / "FN-01.md"
    finding.write_text(finding.read_text(encoding="utf-8")
                       + f"\nTODO: tighten the wording [{ids['cl1']}]\n", encoding="utf-8")

    code, build, _ = run_cli("report", "build")
    assert code == 1
    assert any(c["name"] == "no_placeholders" for c in build["failures"])

    run_cli("report", "build", "--allow-flagged", expect=0)


def test_unknown_id_fails_ids_resolve(env):
    project, ids = full_quick_run(env)
    finding = project / "findings" / "FN-01.md"
    finding.write_text(finding.read_text(encoding="utf-8")
                       + f"\nCross-checked against earlier work [CL-9999] [{ids['cl1']}].\n",
                       encoding="utf-8")

    code, build, _ = run_cli("report", "build", "--allow-flagged")
    assert code == 1
    assert any(c["name"] == "ids_resolve" for c in build["failures"])


def test_gate_waiver_surfaces_in_limitations(env):
    project, ids = full_quick_run(env)
    from lib import paths, util

    state = paths.load_state(project)
    state.setdefault("gate_waivers", []).append({
        "phase": 4, "check": "pdf_page_locators",
        "reason": "pdftotext unavailable in eval sandbox; paragraph locators used",
        "at": util.utcnow_iso(),
    })
    paths.save_state(project, state)

    run_cli("report", "build", expect=0)
    report = (project / "report.md").read_text(encoding="utf-8")
    assert "pdftotext unavailable" in report
    assert "Gate waiver" in report


def test_open_contradiction_must_appear_in_report(env):
    project = seed_project(env)
    a, _ = add_source(project, text="Revenue grew 12% in 2024 as reported.",
                      title="Revenue report A", url="https://alpha.example/rev",
                      service="web", type_="report", published="2025-01-01")
    b, _ = add_source(project, text="Revenue grew 10% in 2024 as reported.",
                      title="Revenue report B", url="https://beta.example/rev",
                      service="web", type_="report", published="2025-01-05",
                      angles=("clinical outcomes",))
    run_cli("credibility", "score", expect=0)
    _, ev1, _ = run_cli("evidence", "add", "--source-id", a, "--locator", "p.1",
                        "--angle", "physiology", "--quote", "Revenue grew 12% in 2024",
                        expect=0)
    _, ev2, _ = run_cli("evidence", "add", "--source-id", b, "--locator", "p.1",
                        "--angle", "clinical outcomes", "--quote", "Revenue grew 10% in 2024",
                        expect=0)
    _, cl1, _ = run_cli("claims", "add", "--text", "Revenue grew 12% in 2024",
                        "--tags", "revenue", "--angles", "physiology",
                        "--evidence", ev1["evidence_id"], expect=0)
    _, cl2, _ = run_cli("claims", "add", "--text", "Revenue grew 10% in 2024",
                        "--tags", "revenue", "--angles", "clinical outcomes",
                        "--evidence", ev2["evidence_id"], expect=0)
    _, scan, _ = run_cli("contradictions", "scan", expect=0)
    assert scan["created_count"] >= 1
    cx = scan["created"][0]

    run_cli("verify", expect=0)
    run_cli("contradictions", "scan", expect=0)

    run_cli("findings", "new", "--title", "Revenue growth summary",
            "--strength", "tentative", "--confidence", "low",
            "--claims", f"{cl1['claim_id']},{cl2['claim_id']}",
            "--body", f"Reported growth disagrees across sources "
                      f"[{cl1['claim_id']}] [{cl2['claim_id']}]. See {cx}.",
            expect=0)
    run_cli("report", "build", expect=0)
    text = (project / "report.md").read_text(encoding="utf-8")
    assert cx in text, "open contradiction must appear in the report"

    run_cli("contradictions", "adjudicate", cx, "--resolution", "unresolved_both",
            "--rationale", "ladder 6: both reports credible, keep unresolved", expect=0)
    _, gate6, _ = run_cli("gate", "--phase", "6")
    assert gate6["pass"] is True, gate6["failures"]
