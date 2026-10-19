"""Improvement batch — output-location guard, requirements coverage, search log,
normative modality checks, bibliography metadata, strict academic gates."""

from __future__ import annotations

from pathlib import Path

from conftest import add_source, full_quick_run, run_cli, seed_project


def test_init_refuses_repo_directory(env):
    repo = Path(__file__).resolve().parents[1]
    target = repo / "tmp-guard-test"
    code, data, err = run_cli("init", "guard test", "--profile", "quick",
                              "--dir", str(target), expect=2)
    assert "refusing" in data["error"]
    assert not target.exists()


def test_init_dir_and_env_resolution(env, monkeypatch):
    target = env["vault"].parent / "my-research" / "topic-a"
    code, data, _ = run_cli("init", "Directional test question", "--profile", "quick",
                            "--dir", str(target), "--angles", "one;two",
                            "--success", "cited", expect=0)
    assert (target / "state.json").exists()
    assert data["path"] == str(target)
    monkeypatch.setenv("RESEARCH_OS_PROJECT", str(target))
    code, status, _ = run_cli("status", expect=0)
    assert status["project"] == "topic-a"
    assert status["path"] == str(target)


def test_project_move_relocates(env):
    project = seed_project(env)
    dest = env["vault"].parent / "research" / "moved-here"
    code, res, _ = run_cli("project", "move", "--to", str(dest),
                           "--remove-original", expect=0)
    assert res["moved_to"] == str(dest)
    assert not project.exists()
    assert (dest / "state.json").exists()
    from lib import paths

    assert paths.load_state(dest)["project_dir"] == str(dest)


def test_project_registry_finds_dir_projects(env):
    target = env["vault"].parent / "direct-run"
    run_cli("init", "Registry question", "--profile", "quick",
            "--dir", str(target), "--angles", "a;b", "--success", "s", expect=0)
    # no env var needed: the runtime registry points at the newest project
    code, status, _ = run_cli("status", expect=0)
    assert status["path"] == str(target)
    code, where, _ = run_cli("project", "where", expect=0)
    assert where["path"] == str(target)


def test_requirements_anchor_semantics(env):
    from core import requirements as req

    project = seed_project(env)
    req.add(project, "Report must include a sensitivity analysis", rid="RQ-01")
    req.add(project, "Provide the raw dataset", rid="RQ-02")

    cov = req.coverage(project)
    assert cov["unmet"] == ["RQ-01", "RQ-02"]

    req.map_target(project, "RQ-01", "Sensitivity")
    cov = req.coverage(project, report_text="Appendix: sensitivity checks were run")
    assert cov["unmet"] == ["RQ-02"]
    assert cov["mapped"] == 1

    cov = req.coverage(project, report_text="Nothing relevant here")
    assert cov["unmet"] == ["RQ-01", "RQ-02"]

    req.waive(project, "RQ-02", "dataset is paywalled")
    cov = req.coverage(project, report_text="Appendix: sensitivity checks were run")
    assert cov["unmet"] == [] and cov["waived"] == 1


def test_searchlog_cli_and_summary(env):
    project = seed_project(env)
    run_cli("searchlog", "add", "--query", "site:oecd.org fintech",
            "--engine", "google", "--hits", "42", "--kept", "3",
            "--angle", "physiology", expect=0)
    run_cli("searchlog", "add", "--query", "BNPL regulation iran",
            "--engine", "scholar", "--hits", "18", "--kept", "2", expect=0)
    code, res, _ = run_cli("searchlog", "list", expect=0)
    assert res["entries"] == 2
    assert res["engines"][0]["engine"] in ("google", "scholar")
    assert res["queries"][0]["id"] == "SCH-0001"
    assert (project / "searches.jsonl").exists()

    from core import searchlog

    summary = searchlog.summarize(project)
    assert sum(e["hits"] for e in summary["engines"]) == 60


def test_claims_cli_kind_and_modality_warning(env):
    project = seed_project(env)
    sid, _ = add_source(project, text="Regulation X prohibits independent credit checks.",
                        title="Regulation X", url="https://reg.example/x",
                        service="web", type_="regulation")
    run_cli("credibility", "score", expect=0)
    _, ev, _ = run_cli("evidence", "add", "--source-id", sid, "--locator", "Art. 1",
                       "--angle", "physiology",
                       "--quote", "Regulation X prohibits independent credit checks",
                       expect=0)
    code, cl, _ = run_cli("claims", "add", "--text",
                          "Non-banks are prohibited from independent credit checks",
                          "--kind", "normative", "--evidence", ev["evidence_id"],
                          "--angles", "physiology", expect=0)
    assert cl["kind"] == "normative" and cl["modality"] is True
    assert any("normative" in w for w in cl["warnings"])

    from core import claims as cm

    try:
        cm.build_claim("bad kind", kind="wishful")
        raise AssertionError("expected ValueError for invalid kind")
    except ValueError as exc:
        assert "kind" in str(exc)


def test_modality_and_official_source_helpers():
    from core import claims as cm

    assert cm.has_modality("Lendtechs are not allowed to assess credit")
    assert cm.has_modality("تسهیلات‌یار ممنوع است")
    assert not cm.has_modality("Banks bear final responsibility")

    claim = cm.build_claim("X is prohibited", kind="normative")
    news_ev = [{"quote": "The bank said it bears responsibility"}]
    reg_ev = [{"quote": "the regulation prohibits X"}]
    assert cm.modality_mismatch(claim, news_ev) is True
    assert cm.modality_mismatch(claim, reg_ev) is False

    officials = cm.official_sources([
        {"id": "SRC-0001", "type": "news"},
        {"id": "SRC-0002", "type": "regulation"},
        {"id": "SRC-0003", "type": "report", "extra": {"official": True}},
    ])
    assert [s["id"] for s in officials] == ["SRC-0002", "SRC-0003"]

    old = {"as_of": "2019-01-01"}
    assert (cm.staleness_months(old) or 0) > 18
    fresh = {"as_of": "2026-06-01"}
    assert (cm.staleness_months(fresh) or 99) < 18


def test_bibmeta_apa_versions_and_missing():
    from core import bibmeta

    source = {
        "id": "SRC-0001", "title": "Staging options",
        "authors": [{"family": "Mirzaei", "given": "Ali"},
                    {"family": "Smith", "given": "J. R."}],
        "venue": "Journal of Fintech", "year": 2022, "volume": "3",
        "issue": "2", "pages": "99-120",
        "doi": "10.2139/ssrn.123", "published_doi": "10.1080/17938120.2022.2143749",
        "url": "https://doi.org/10.2139/ssrn.123",
    }
    assert bibmeta.authors_apa(source) == "Mirzaei, A., & Smith, J. R."
    assert bibmeta.source_year(source) == "2022"
    note = bibmeta.version_note(source)
    assert "preprint" in note or "cited DOI" in note
    apa = bibmeta.apa_reference(source)
    assert apa["year"] == "2022" and apa["doi"] == "10.1080/17938120.2022.2143749"
    assert "Journal of Fintech" in apa["venue_parts"]

    bare = {"id": "SRC-0002", "title": "Some page", "url": "https://x.example"}
    missing = bibmeta.missing_bib_fields(bare, strict=True)
    assert "authors/publisher" in missing and "year" in missing
    assert "authors/publisher" in bibmeta.missing_bib_fields(bare, strict=False)
    assert "year" not in bibmeta.missing_bib_fields(bare, strict=False)


def test_strict_academic_gates_phase3(env):
    project = seed_project(env)
    run_cli("brief", "set", "--deliverable-type", "academic-paper",
            "--key-studies-target", "1", expect=0)
    sid_a, _ = add_source(project, text="First study reports 12% growth.",
                          title="Study A", url="https://a.example/1")
    sid_b, _ = add_source(project, text="Second source confirms the trend.",
                          title="Source B", url="https://b.example/2",
                          angles=("clinical outcomes",))

    code, gate3, _ = run_cli("gate", "--phase", "3")
    names = {f["check"] for f in gate3["failures"]}
    assert "search_logged" in names and "screening_reasons" in names

    run_cli("searchlog", "add", "--query", "growth fintech", "--engine", "google",
            "--hits", "10", "--kept", "2", expect=0)
    run_cli("sources", "update", "--source-id", sid_a, "--status", "included", expect=0)
    run_cli("sources", "update", "--source-id", sid_b, "--status", "excluded",
            "--exclude-reason", "duplicate of SRC-0001", expect=0)

    code, gate3b, _ = run_cli("gate", "--phase", "3")
    assert gate3b["pass"] is True, gate3b["failures"]

    code, bad, _ = run_cli("sources", "update", "--source-id", sid_b,
                           "--status", "excluded", expect=2)
    assert "--exclude-reason" in bad["error"]


def test_strict_academic_gates_phase7(env):
    project, ids = full_quick_run(env)
    run_cli("brief", "set", "--deliverable-type", "academic-paper",
            "--key-studies-target", "1", expect=0)
    run_cli("sources", "review", "--source-id", ids["src_a"], "--key",
            "--problem", "p", "--framework", "f", "--method", "m",
            "--context", "c", "--findings", "fi", "--limitations", "l",
            "--relevance", "r", expect=0)

    code, gate7, _ = run_cli("gate", "--phase", "7")
    names = {f["check"] for f in gate7["failures"]}
    assert "findings_kinds" in names
    assert "key_studies_reviewed" not in names

    for kind, title in (("model", "Decision model"), ("scenarios", "Five scenarios"),
                        ("sensitivity", "Breakpoints")):
        run_cli("findings", "new", "--title", title,
                "--claims", ids["cl1"], "--kind", kind,
                "--body", f"Variant prose for {title} [{ids['cl1']}].", expect=0)

    code, gate7b, _ = run_cli("gate", "--phase", "7")
    assert gate7b["pass"] is True, gate7b["failures"]
