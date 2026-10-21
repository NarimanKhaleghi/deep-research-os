"""Full-text trust chain, legal resolver guards, and manuscript gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import add_source, run_cli, seed_project

from core import fulltext, fulltext_store, gates, resolver
from core.evidence_store import Ledger
from lib import http, util


JATS = """<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front>
    <journal-meta><journal-title>Journal of Tests</journal-title></journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">10.1234/test.2024</article-id>
      <title-group><article-title>Intermittent fasting and lean mass: a randomized trial</article-title></title-group>
      <contrib-group><contrib><name><surname>Smith</surname><given-names>Jane</given-names></name></contrib></contrib-group>
      <abstract><p>Background: intermittent fasting may affect lean mass. Methods: we randomized 120 adults to time-restricted eating or control for 8 weeks with resistance training. Results: the intervention arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01), while the control arm retained lean mass. Conclusions: time-restricted eating may reduce lean mass despite resistance training.</p></abstract>
      <pub-date><year>2024</year></pub-date>
    </article-meta>
  </front>
  <body>
    <sec><title>Introduction</title><p>Intermittent fasting is widely used, but its effects on lean mass during resistance training remain uncertain. Prior trials were short and underpowered, and few measured body composition with dual-energy X-ray absorptiometry. We therefore tested whether eight weeks of time-restricted eating would reduce lean mass compared with a usual eating window in adults who performed supervised resistance training three times per week. Our primary outcome was appendicular lean mass measured by DXA.</p></sec>
    <sec><title>Methods</title><p>We conducted a parallel-group randomized controlled trial at a single academic center. Eligible participants were adults aged 18 to 45 years with a body mass index between 20 and 32 and no metabolic disease. Participants were randomized one-to-one to an eight-hour eating window or a twelve-hour window, both with three supervised resistance sessions per week. The primary outcome was change in appendicular lean mass from baseline to week eight, measured by DXA. Secondary outcomes included strength, adherence, and total fat mass. Analyses used intention-to-treat linear mixed models adjusted for baseline values.</p></sec>
    <sec><title>Results</title><p>A total of 120 participants were randomized, and 112 completed the trial. The time-restricted arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01), whereas the control arm retained lean mass within measurement error. Adherence was 84% in the intervention arm and 91% in the control arm. Strength increased in both arms, with no significant between-group difference. Total fat mass decreased more in the intervention arm, but the difference was not statistically significant after adjustment.</p></sec>
    <sec><title>Discussion</title><p>These findings suggest that a compressed eating window may blunt lean-mass retention during resistance training, even when protein intake is adequate. The result is consistent with mechanistic work on muscle protein synthesis and with observational studies of fasting duration. However, the trial was single-center, relatively short, and not powered for subgroup analyses. Participants were also younger and more active than the general population, which limits generalisability. Future trials should test longer interventions and strategies to preserve lean mass.</p></sec>
    <sec><title>Conclusion</title><p>Time-restricted eating reduced lean mass over eight weeks despite supervised resistance training. Clinicians and coaches should monitor body composition when recommending compressed eating windows, and longer trials are needed before these findings are used to guide practice.</p></sec>
  </body>
  <back><ref-list><ref id="r1"><mixed-citation>Prior trial.</mixed-citation></ref></ref-list></back>
</article>
"""


def _verified_source(env):
    project = seed_project(env)
    sid, _ = add_source(project, text="placeholder snapshot", title="Intermittent fasting and lean mass: a randomized trial",
                        url="https://example.org/trial", doi="10.1234/test.2024",
                        angles=("physiology",))
    ledger = Ledger(project)
    ledger.update_source(sid, abstract="Background: intermittent fasting may affect lean mass. Methods: we randomized 120 adults to time-restricted eating or control for 8 weeks with resistance training. Results: the intervention arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01), while the control arm retained lean mass. Conclusions: time-restricted eating may reduce lean mass despite resistance training.")
    source = ledger.source(sid)
    artifact = fulltext.extract_artifact(JATS.encode(), filename="trial.xml")
    validation = fulltext.validate_identity(source, artifact)
    assert validation["ok"], validation
    rec = fulltext_store.store_artifact(
        project, ledger, source, JATS.encode(), artifact,
        {"url": "https://example.org/trial.xml", "final_url": "https://example.org/trial.xml",
         "host": "example.org", "bytes": len(JATS), "license": "CC-BY"},
        status="verified", version="version-of-record", validation=validation)
    return project, rec


def test_jats_extraction_and_identity(env):
    project, rec = _verified_source(env)
    assert rec["fulltext"]["status"] == "verified"
    assert rec["fulltext"]["format"] == "jats"
    assert rec["fulltext"]["text_chars"] > 1200
    assert fulltext_store.verify(project, rec)["ok"]


def test_abstract_quality():
    short = fulltext.assess_abstract("Background: x. Methods: y. Results: 2%. Conclusions: z.")
    assert short["verdict"] != "comprehensive"
    long = ("Background: intermittent fasting is common. " * 20
            + "Methods: we randomized 120 adults to two eating windows and measured lean mass. " * 12
            + "Results: the intervention arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01). " * 8
            + "Conclusions: time-restricted eating may reduce lean mass despite training. " * 8)
    assert fulltext.assess_abstract(long)["verdict"] == "comprehensive"


def test_pirate_hosts_blocked():
    with pytest.raises(ValueError):
        http.validate_url("https://sci-hub.se/10.1234/test")
    assert resolver._candidate("https://libgen.is/book.pdf", kind="pdf", provider="x") is None
    assert resolver._candidate("https://example.org/paper.pdf", kind="pdf", provider="x")


def test_download_validates_redirect_hops_before_following(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", "/final.pdf")
                self.end_headers()
                return
            if self.path == "/evil":
                self.send_response(302)
                self.send_header("Location", "https://sci-hub.se/x.pdf")
                self.end_headers()
                return
            body = b"%PDF-1.4 test"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        info = http.download(base + "/start", tmp_path / "ok.pdf", allow_private=True)
        assert info["final_url"].endswith("/final.pdf")
        assert info["bytes"] == len(b"%PDF-1.4 test")
        with pytest.raises(ValueError):
            http.download(base + "/evil", tmp_path / "bad.pdf", allow_private=True)
        assert not (tmp_path / "bad.pdf").exists()
    finally:
        server.shutdown()


def test_manuscript_build_passes_with_verified_fulltext(env):
    project, rec = _verified_source(env)
    run_cli("brief", "set", "--deliverable-type", "academic-manuscript", "--project", str(project), expect=0)
    run_cli("manuscript", "scaffold", "--project", str(project), expect=0)
    abstract = ("Background: intermittent fasting is widely used, but its effect on lean mass during resistance training is uncertain. "
                "Objective: we tested whether eight weeks of time-restricted eating would reduce lean mass compared with a usual eating window. "
                "Methods: we conducted a parallel-group randomized controlled trial in 120 adults with supervised resistance training three times per week. "
                "Eligible participants were adults aged 18 to 45 years with a body mass index between 20 and 32 and no metabolic disease. "
                "The primary outcome was change in appendicular lean mass measured by dual-energy X-ray absorptiometry. "
                "Results: the intervention arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01), while the control arm retained lean mass. "
                "Adherence was 84% in the intervention arm and 91% in the control arm, and strength increased in both groups. "
                "Conclusions: time-restricted eating may reduce lean mass despite resistance training, and longer trials are needed. "
                "Clinicians and coaches should monitor body composition when recommending compressed eating windows. "
                "The trial was conducted at a single academic center, and the eight-week follow-up limits inference about long-term body-composition trajectories. "
                "Future studies should test whether higher protein intake or targeted resistance-training volume preserves lean mass during compressed eating windows.")
    body = f"""---
title: "Time-restricted eating and lean mass during resistance training"
authors:
  - "Jane Smith"
affiliations:
  - "Department of Nutrition, Test University"
keywords:
  - "intermittent fasting"
  - "lean mass"
  - "resistance training"
abstract: "{abstract}"
funding: "Test grant"
conflicts: "The authors declare no competing interests."
data_availability: "De-identified data are available from the corresponding author."
ethics: "The institutional review board approved the study."
registration: "NCT00000000"
language: "en"
reporting_guidelines: []
---

## Introduction

Intermittent fasting is widely used for weight management, yet its effects on lean mass during resistance training remain uncertain. Prior trials were short, underpowered, and rarely measured body composition with dual-energy X-ray absorptiometry. We therefore tested whether eight weeks of time-restricted eating would reduce lean mass compared with a usual eating window in adults performing supervised resistance training. The contribution is a randomized comparison with a prespecified body-composition outcome [@SRC-0001].

## Methods

We conducted a parallel-group randomized controlled trial at a single academic center. Eligible participants were adults aged 18 to 45 years with a body mass index between 20 and 32 and no metabolic disease. Participants were randomized one-to-one to an eight-hour eating window or a twelve-hour window, both with three supervised resistance sessions per week. The primary outcome was change in appendicular lean mass from baseline to week eight, measured by DXA. Secondary outcomes included strength, adherence, and total fat mass. Analyses used intention-to-treat linear mixed models adjusted for baseline values [@SRC-0001].

## Results

A total of 120 participants were randomized, and 112 completed the trial. The time-restricted arm lost 2.3% lean mass (95% CI 1.1 to 3.5; p = 0.01), whereas the control arm retained lean mass within measurement error [@SRC-0001]. Adherence was 84% in the intervention arm and 91% in the control arm. Strength increased in both arms, with no significant between-group difference. Total fat mass decreased more in the intervention arm, but the difference was not statistically significant after adjustment.

## Discussion

These findings suggest that a compressed eating window may blunt lean-mass retention during resistance training, even when protein intake is adequate. The result is consistent with mechanistic work on muscle protein synthesis and with observational studies of fasting duration. However, the trial was single-center, relatively short, and not powered for subgroup analyses. Participants were also younger and more active than the general population, which limits generalisability. Future trials should test longer interventions and strategies to preserve lean mass [@SRC-0001].

## Conclusion

Time-restricted eating reduced lean mass over eight weeks despite supervised resistance training. Clinicians and coaches should monitor body composition when recommending compressed eating windows, and longer trials are needed before these findings are used to guide practice. These results should be interpreted alongside the single-center design and the relatively short follow-up, and future work should test strategies that preserve lean mass during energy restriction.
"""
    draft = project / "manuscript" / "draft.md"
    draft.write_text(body, encoding="utf-8")
    code, data, err = run_cli("manuscript", "build", "--project", str(project), expect=0)
    assert data["ok"], data
    assert (project / "manuscript.md").exists()
    assert (project / "manuscript.html").exists()
    assert "References" in (project / "manuscript.md").read_text(encoding="utf-8")


def test_fulltext_gates_allow_documented_abstract_only(env):
    project, rec = _verified_source(env)
    ledger = Ledger(project)
    sid, _ = add_source(project, text="placeholder", title="Abstract-only test source",
                        url="https://example.org/abstract", doi="10.1234/abstract.2024",
                        angles=("physiology",))
    abstract = ("Background: this is a structured abstract about a randomized trial. " * 12
                + "Methods: we randomized 120 adults and measured the primary outcome. " * 12
                + "Results: the intervention changed the outcome by 2.3% (95% CI 1.1 to 3.5; p = 0.01). " * 10
                + "Conclusions: the intervention may improve the outcome, but longer trials are needed. " * 10)
    quality = fulltext.assess_abstract(abstract)
    assert quality["verdict"] == "comprehensive"
    fulltext_store.store_abstract(project, ledger, ledger.source(sid), abstract,
                                  quality=quality,
                                  exception={"reason": "publisher refused lawful access"})
    checks = []
    gates._fulltext_gates(project, ledger, {"deliverable_type": "academic-manuscript"},
                          lambda name, ok, detail="": checks.append({"name": name, "ok": ok}))
    by_name = {c["name"]: c["ok"] for c in checks}
    assert by_name["fulltext_integrity"] is True
    assert by_name["abstract_quality"] is True
