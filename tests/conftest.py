"""Shared fixtures + offline builders for the deep-research-os test suite.

All tests run with RESEARCH_OS_OFFLINE=1 and isolated HOME/VAULT directories
(monkeypatched per test). CLI calls go through subprocesses so the real
command surface is exercised.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    home.mkdir()
    vault.mkdir()
    monkeypatch.setenv("RESEARCH_OS_HOME", str(home))
    monkeypatch.setenv("RESEARCH_OS_VAULT", str(vault))
    monkeypatch.setenv("RESEARCH_OS_OFFLINE", "1")
    return {"home": home, "vault": vault}


def run_cli(*argv: str, expect: int | None = None) -> tuple[int, dict | None, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "research_ctl.py"), *argv],
        capture_output=True, text=True, env=os.environ.copy(),
        cwd=str(ROOT), timeout=180,
    )
    payload = None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = None
    if expect is not None:
        assert proc.returncode == expect, (
            f"cli {argv} rc={proc.returncode} (expected {expect})\n"
            f"stdout={proc.stdout[:800]}\nstderr={proc.stderr[:400]}")
    return proc.returncode, payload, proc.stderr


PLAN_SECTIONS = {
    "Terminology": "- intermittent fasting\n- time-restricted eating\n- lean mass\n"
                   "- muscle protein synthesis\n- resistance training",
    "Actors": "- researchers\n- clinicians\n- fitness coaches",
    "Source Map": "- academic: pubmed\n- news: gdelt",
}

SOURCE_A_TEXT = (
    "Intermittent fasting and lean mass — a randomized controlled trial.\n\n"
    "Results: participants in the time-restricted eating arm lost 2.3% lean mass "
    "over 8 weeks of resistance training.\n\n"
    "The control group retained lean mass within measurement error."
)

SOURCE_B_TEXT = (
    "Registry summary — time-restricted eating adherence.\n\n"
    "Adherence to time-restricted eating reached 84% at 12 weeks in the pooled cohort.\n\n"
    "Overall dropout was 9%."
)


def seed_project(env, question="Does intermittent fasting reduce lean mass?",
                 angles=("physiology", "clinical outcomes"), profile="quick"):
    code, data, err = run_cli(
        "init", question, "--profile", profile,
        "--angles", ";".join(angles),
        "--success", "supported answer with citations", expect=0)
    project = env["vault"] / "projects" / data["project"]

    sections = dict(PLAN_SECTIONS)
    sections["Initial Queries"] = f"- {angles[0]}: query one\n- {angles[1]}: query two"
    sections["Collection Matrix"] = "\n".join([
        f"- {angles[0]}: strategy A", f"- {angles[0]}: strategy B",
        f"- {angles[1]}: strategy C", f"- {angles[1]}: strategy D",
        f"- {angles[0]}: cross-check via {angles[1]} sources",
        f"- {angles[1]}: cross-check via {angles[0]} sources",
    ])
    sections["Target Sources"] = "- pubmed RCTs"
    sections["Stop Rules"] = "- stop when every angle has 2 sources"
    for name, text in sections.items():
        run_cli("plan", "set-section", "--name", name, "--text", text, expect=0)
    return project


def add_source(project, *, text, title, url, service="pubmed", type_="journal-article",
               doi=None, published="2024-05-01", angles=("physiology",),
               origin_key=None, authors=("Smith, J.",), publisher="Journal of Tests",
               extra=None, credibility_override=None):
    from core import credibility
    from core import snapshot as snapshot_mod
    from core.evidence_store import Ledger
    from lib import paths, util

    ledger = Ledger(project)
    sid = util.next_id("SRC", [s["id"] for s in ledger.sources()])
    snap = snapshot_mod.snapshot_text(project, sid, text, "text")
    rec = ledger.add_source({
        "id": sid, "url": url, "doi": doi, "title": title, "authors": list(authors),
        "publisher": publisher, "published": published, "accessed_at": util.utcnow_iso(),
        "service": service, "type": type_,
        "tier": 1 if type_ in ("journal-article", "statistics", "filing") else 2,
        "origin_key": origin_key or util.domain_of(url), "angles_covered": list(angles),
        "snapshot": snap, "extra": extra or {},
    })
    cred = credibility.score_source(rec)
    rec = ledger.update_source(sid, credibility=cred)
    state = paths.load_state(project)
    state.setdefault("ran", {})["last_credibility_at"] = util.utcnow_iso()
    paths.save_state(project, state)
    return sid, rec


def full_quick_run(env):
    """A complete offline run that passes gates 0–8 (phase 9 is exercised
    separately by test_retrospect_then_gate9). Returns (project, ids)."""
    project = seed_project(env)
    sid_a, _ = add_source(project, text=SOURCE_A_TEXT, title="IF and lean mass RCT",
                          url="https://example.org/trial-a", doi="10.1234/test.a.2024",
                          angles=("physiology",))
    sid_b, _ = add_source(project, text=SOURCE_B_TEXT, title="TRE adherence registry",
                          url="https://cdc.gov/data/tre", service="web", type_="statistics",
                          doi=None, published="2025-02-10", angles=("clinical outcomes",))
    run_cli("credibility", "score", expect=0)
    _, ev1, _ = run_cli("evidence", "add", "--source-id", sid_a, "--locator", "Results ¶1",
                        "--angle", "physiology",
                        "--quote", "participants in the time-restricted eating arm lost "
                                   "2.3% lean mass over 8 weeks", expect=0)
    _, ev2, _ = run_cli("evidence", "add", "--source-id", sid_b, "--locator", "Summary",
                        "--angle", "clinical outcomes",
                        "--quote", "Adherence to time-restricted eating reached 84% at 12 weeks",
                        expect=0)
    _, cl1, _ = run_cli("claims", "add", "--text",
                        "Time-restricted eating reduced lean mass by 2.3% over 8 weeks",
                        "--type", "statistic", "--tags", "fasting",
                        "--angles", "physiology",
                        "--evidence", ev1["evidence_id"], expect=0)
    _, cl2, _ = run_cli("claims", "add", "--text",
                        "Adherence to time-restricted eating reached 84% at 12 weeks",
                        "--type", "statistic", "--tags", "adherence",
                        "--angles", "clinical outcomes",
                        "--evidence", ev2["evidence_id"], expect=0)
    run_cli("verify", expect=0)
    run_cli("contradictions", "scan", expect=0)
    body = (f"The randomized trial found lean-mass loss of 2.3% in the time-restricted "
            f"eating arm over 8 weeks [{cl1['claim_id']}].")
    run_cli("findings", "new", "--title", "Intermittent fasting reduced lean mass",
            "--strength", "supported", "--confidence", "medium",
            "--claims", cl1["claim_id"], "--gaps", "single-site trial",
            "--body", body, expect=0)
    run_cli("report", "build", expect=0)
    return project, {"src_a": sid_a, "src_b": sid_b, "ev1": ev1["evidence_id"],
                     "ev2": ev2["evidence_id"], "cl1": cl1["claim_id"], "cl2": cl2["claim_id"]}
