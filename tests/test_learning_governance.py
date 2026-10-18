"""Learning governance — stats, feedback, preferences, proposals, maintenance."""

from __future__ import annotations

import pytest

from learning import feedback, maintain, preferences, proposals, sources_learning, upstream_scan


def test_source_stats_and_weight_bounds(env):
    for _ in range(3):
        sources_learning.record_search("web", ["web"], n_results=2)
    stats = sources_learning.load_stats()
    assert sources_learning.attempts_for(stats, "web", ["web"]) == 3
    w = sources_learning.weight(stats, "web", ["web"])
    assert 0.05 <= w <= 1.0

    sources_learning.record_outcome("web", "example.org", "evidence")
    movers = sources_learning.movers(sources_learning.load_stats())
    assert movers and movers[0]["source"] == "web"


def test_feedback_journal_validation(env):
    with pytest.raises(ValueError):
        feedback.journal("nonsense", "label")
    rec = feedback.journal("explicit", "user liked the contradiction table", project="p1")
    assert rec["id"] == "FB-0001"
    rec2 = feedback.journal("implicit", "report accepted unchanged", project="p1")
    assert rec2["id"] == "FB-0002"
    assert feedback.count_for_project("p1") == 2


def test_preference_caps_and_kill_switch(env):
    allowed, why = preferences.can_ask("quick", 0)
    assert not allowed and "never asks" in why
    allowed, _ = preferences.can_ask("standard", 0)
    assert allowed
    allowed, why = preferences.can_ask("standard", 1)
    assert not allowed and "cap" in why

    q = preferences.create_question({"project": "p1", "context": "ctx",
                                     "a": {"label": "A"}, "b": {"label": "B"}})
    a = preferences.answer(q["id"], "A", note="shorter wins")
    assert a["status"] == "answered"

    for _ in range(preferences.UNANSWERED_LIMIT):
        qq = preferences.create_question({"project": "p1", "a": {}, "b": {}})
        preferences.mark_unanswered(qq["id"])
    assert preferences.load()["disabled"] is True
    preferences.enable()
    assert preferences.load()["disabled"] is False


def test_proposal_lifecycle_with_regression_and_revert(env):
    p = proposals.create(
        "adopt_method", "Adopt PDF ladder fallback",
        "Use pdftotext before pypdf when PyMuPDF fails on scanned layouts.",
        evidence={"notes": "3 scanned PDFs failed PyMuPDF but extracted via pdftotext"},
        changes=[{"action": "create", "file": "scratch-method.md", "content": "ladder"}],
    )
    assert p["status"] == "proposed"
    assert p["validation"]["ok"] is True

    bad = proposals.create(
        "nope", "x", "too short", evidence={}, changes=[])
    assert bad["status"] == "invalid"

    # regression failure blocks the apply and marks regressed
    proposals.decide(p["id"], "approve")
    r = proposals.apply(p["id"], regression=lambda: (False, ["gate regression detected"]))
    assert r["status"] == "regressed"

    # a green regression applies the change
    p2 = proposals.create(
        "adopt_method", "Adopt PDF ladder fallback (retry)",
        "Use pdftotext before pypdf when PyMuPDF fails on scanned layouts.",
        evidence={"notes": "retry after fixing the eval fixture"},
        changes=[{"action": "create", "file": "scratch-method.md", "content": "ladder"}],
    )
    proposals.decide(p2["id"], "approve")
    r2 = proposals.apply(p2["id"], regression=lambda: (True, ["ok"]))
    assert r2["status"] == "applied"
    from lib import paths
    assert (paths.runtime_learning_dir() / "scratch-method.md").exists()

    rev = proposals.revert(p2["id"])
    assert rev["status"] == "reverted"
    assert not (paths.runtime_learning_dir() / "scratch-method.md").exists()


def test_maintain_writes_insights_and_digest(env):
    result = maintain.run(create_proposals=True)
    assert set(result) >= {"nudges", "proposals", "insights_updated", "digest_written"}
    from lib import paths
    assert (paths.runtime_learning_dir() / "insights.md").exists()
    digests = list(paths.runtime_learning_dir().glob("digest-*.md"))
    assert digests, "monthly digest must be written"


def test_upstream_scan_offline_is_safe(env):
    result = upstream_scan.scan(write_report=True)
    assert result["offline"] is True
    assert result["candidates"] == []
    from lib import paths
    assert list((paths.runtime_learning_dir() / "discoveries").glob("*.md")) or result.get("written")


def test_learn_mode_kill_switch(env):
    from conftest import run_cli

    run_cli("learn", "mode", "off", expect=0)
    code, res, _ = run_cli("learn", "feedback", "--type", "explicit", "--label", "should fail")
    assert code == 2
    assert "learning is off" in res["error"]
    run_cli("learn", "mode", "auto", expect=0)
    run_cli("learn", "feedback", "--type", "explicit", "--label", "now works", expect=0)
