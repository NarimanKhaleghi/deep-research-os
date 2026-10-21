#!/usr/bin/env python3
"""run_evals — behavior evals for deep-research-os.

Each scenario plants a known trap and asserts the pipeline catches it
(offline by default; all network access is disabled). Exit 0 = all pass.

Usage:
  python evals/run_evals.py --offline        # default: deterministic, no network
  python evals/run_evals.py --live           # adds one live search sanity check
  python evals/run_evals.py --only number_drift
  python evals/run_evals.py --keep-temp      # keep scenario sandboxes for debugging
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
for p in (SCRIPTS, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_TMP_DIRS: list[Path] = []


def _fresh_env() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="dros-eval-"))
    _TMP_DIRS.append(tmp)
    (tmp / "home").mkdir()
    (tmp / "vault").mkdir()
    env = {"home": tmp / "home", "vault": tmp / "vault", "root": tmp}
    os.environ.update({
        "RESEARCH_OS_HOME": str(tmp / "home"),
        "RESEARCH_OS_VAULT": str(tmp / "vault"),
        "RESEARCH_OS_OFFLINE": "1",
    })
    return env


def _cli(*argv, expect=None):
    from conftest import run_cli

    return run_cli(*argv, expect=expect)


# --------------------------------------------------------------- scenarios

def scenario_citation_fabrication():
    from conftest import add_source, seed_project

    env = _fresh_env()
    project = seed_project(env, question="Is the retention rate 71%?")
    sid, _ = add_source(project, text="The page states the retention rate was 71%.",
                        title="Retention study", url="https://example.org/r",
                        doi="10.1234/r.2025", published="2025-01-01")
    _cli("credibility", "score", expect=0)
    _, ev, _ = _cli("evidence", "add", "--source-id", sid, "--locator", "p.1",
                    "--angle", "physiology",
                    "--quote", "retention rate was 93% according to management", expect=0)
    ok_validation = ev["validation"]["quote_found"] is False
    _, gate4, _ = _cli("gate", "--phase", "4")
    detected = gate4["pass"] is False and any("quote∉snapshot" in f["detail"]
                                              for f in gate4["failures"])
    return ok_validation and detected, {"quote_rejected": ok_validation, "gate4_blocks": detected}


def scenario_planted_contradiction():
    from conftest import add_source, seed_project

    env = _fresh_env()
    project = seed_project(env, question="How fast did revenue grow?")
    a, _ = add_source(project, text="Revenue grew 12% in 2024 per the annual report.",
                      title="Annual report", url="https://alpha.example/ar",
                      service="web", type_="report", published="2025-01-01")
    b, _ = add_source(project, text="Revenue grew 10% in 2024 per the filing.",
                      title="Filing summary", url="https://beta.example/f",
                      service="web", type_="report", published="2025-02-01",
                      angles=("clinical outcomes",))
    _cli("credibility", "score", expect=0)
    _, ev1, _ = _cli("evidence", "add", "--source-id", a, "--locator", "p.1",
                     "--angle", "physiology", "--quote", "Revenue grew 12% in 2024", expect=0)
    _, ev2, _ = _cli("evidence", "add", "--source-id", b, "--locator", "p.1",
                     "--angle", "clinical outcomes", "--quote", "Revenue grew 10% in 2024",
                     expect=0)
    _cli("claims", "add", "--text", "Revenue grew 12% in 2024", "--tags", "revenue",
         "--angles", "physiology", "--evidence", ev1["evidence_id"], expect=0)
    _cli("claims", "add", "--text", "Revenue grew 10% in 2024", "--tags", "revenue",
         "--angles", "clinical outcomes", "--evidence", ev2["evidence_id"], expect=0)
    _, scan, _ = _cli("contradictions", "scan", expect=0)
    found = scan["created_count"] >= 1
    cx = scan["created"][0] if found else None
    adjudicated = False
    if found:
        _, r, _ = _cli("contradictions", "adjudicate", cx, "--resolution", "scope_difference",
                       "--rationale", "ladder 1: growth measures differ (revenue vs bookings)",
                       expect=0)
        adjudicated = r["contradiction"]["status"] == "adjudicated"
    _, scan2, _ = _cli("contradictions", "scan", expect=0)
    deduped = scan2["created_count"] == 0
    return found and adjudicated and deduped, {
        "cx_found": found, "cx_id": cx, "adjudicated": adjudicated, "deduped": deduped}


def scenario_number_drift():
    from conftest import add_source, seed_project

    env = _fresh_env()
    project = seed_project(env, question="What was the yield?")
    sid, _ = add_source(project, text="Yield improved to 96.555% during the quarter.",
                        title="Yield report", url="https://example.org/y",
                        doi="10.1234/y.2024", published="2025-03-01")
    _cli("credibility", "score", expect=0)
    _, ev, _ = _cli("evidence", "add", "--source-id", sid, "--locator", "p.2",
                    "--angle", "physiology",
                    "--quote", "Yield improved to 96.555% during the quarter", expect=0)
    _cli("claims", "add", "--text", "Yield reached 97% this quarter",
         "--tags", "yield", "--angles", "physiology",
         "--evidence", ev["evidence_id"], expect=0)
    _, verify, _ = _cli("verify", expect=0)
    drift = verify["number_mismatches"]
    detected = bool(drift) and drift[0]["claim_status"] == "weakly_supported"
    return detected, {"mismatches": drift}


def scenario_echo_chamber():
    from conftest import add_source, seed_project

    env = _fresh_env()
    project = seed_project(env, question="What was adoption?")
    a, _ = add_source(project, text="Adoption reached 64% across the surveyed segment (wire).",
                      title="Wire copy A", url="https://news.example/wire-a",
                      service="web", type_="news", published="2025-04-01",
                      origin_key="news.example")
    b, _ = add_source(project, text="Adoption reached 64% across the surveyed segment (republish).",
                      title="Wire copy B", url="https://news.example/wire-b",
                      service="web", type_="news", published="2025-04-02",
                      origin_key="news.example", angles=("clinical outcomes",))
    _cli("credibility", "score", expect=0)
    _, ev1, _ = _cli("evidence", "add", "--source-id", a, "--locator", "p.1",
                     "--angle", "physiology",
                     "--quote", "Adoption reached 64% across the surveyed segment", expect=0)
    _, ev2, _ = _cli("evidence", "add", "--source-id", b, "--locator", "p.1",
                     "--angle", "clinical outcomes",
                     "--quote", "Adoption reached 64% across the surveyed segment (republish)",
                     expect=0)
    _, cl, _ = _cli("claims", "add", "--text", "Adoption reached 64% across the segment",
                    "--tags", "adoption", "--angles", "physiology", "--critical",
                    "--evidence", f"{ev1['evidence_id']},{ev2['evidence_id']}", expect=0)
    _, verify, _ = _cli("verify", expect=0)
    gaps = verify["corroboration_gaps"]
    single_origin = any(g["claim_id"] == cl["claim_id"] for g in gaps)
    weak = verify["claims_summary"].get("weakly_supported", 0) >= 1
    return single_origin and weak, {"corroboration_gaps": gaps,
                                    "claims_summary": verify["claims_summary"]}


def scenario_multilingual_fa():
    from conftest import add_source, seed_project

    env = _fresh_env()
    project = seed_project(env, question="میزان رشد عملکرد چقدر بود؟")
    text = "در مطالعه سال ۲۰۲۵، رشد ۹۶٫۵٪ در عملکرد ثبت شد."
    sid, _ = add_source(project, text=text, title="مطالعه رشد عملکرد",
                        url="https://example.org/fa-study", doi="10.1234/fa.2025",
                        published="2025-06-01")
    _cli("credibility", "score", expect=0)
    _, ev, _ = _cli("evidence", "add", "--source-id", sid, "--locator", "ص.۱",
                    "--angle", "physiology", "--quote", "رشد ۹۶٫۵٪ در عملکرد ثبت شد", expect=0)
    _cli("claims", "add", "--text", "رشد ۹۶٫۵٪ در عملکرد ثبت شد",
         "--tags", "growth", "--angles", "physiology",
         "--evidence", ev["evidence_id"], expect=0)
    _, verify, _ = _cli("verify", expect=0)
    no_drift = verify["number_mismatches"] == []
    status = verify["claims_summary"]
    accepted = status.get("supported", 0) + status.get("weakly_supported", 0) >= 1
    return no_drift and accepted, {
        "normalized_match": no_drift, "claims_summary": status,
        "evidence_validation": ev["validation"]}


def scenario_budget_quick():
    from conftest import seed_project

    env = _fresh_env()
    project = seed_project(env, question="Quick fact check?", profile="quick")

    from core import budget as budget_mod
    from lib import paths

    state = paths.load_state(project)
    budget_mod.spend(state, "searches", 4)  # ceiling is 3 for quick
    paths.save_state(project, state)

    _, status, _ = _cli("status", expect=0)
    blocked = "searches" in status["budget"]["exceeded"]

    state = paths.load_state(project)
    budget_mod.add_exception(state, "searches", "one extra query for the negative-control angle")
    paths.save_state(project, state)
    _, status2, _ = _cli("status", expect=0)
    excused = status2["budget"]["exceeded"] == []
    return blocked and excused, {"blocked_before": blocked, "excused_with_reason": excused}


def scenario_requirement_coverage():
    """A strict academic project must not ship while an explicit requirement is
    unmet; mapping to an anchor that doesn't exist must not count; waiver reasons
    must surface in Limitations."""
    from conftest import full_quick_run

    env = _fresh_env()
    full_quick_run(env)
    project = next((env["vault"] / "projects").glob("*"))
    sid_a = "SRC-0001"
    _cli("brief", "set", "--deliverable-type", "academic-paper", expect=0)
    _cli("sources", "update", "--source-id", sid_a, "--venue", "Journal of Tests",
         expect=0)
    _cli("requirements", "add", "--text", "Sensitivity analysis with breakpoints",
         expect=0)

    _, build1, _ = _cli("report", "build")
    blocks = any(c["name"] == "requirements_coverage" and not c["ok"]
                 for c in build1["checks"]) if build1 else False

    _cli("requirements", "map", "--requirement", "RQ-01",
         "--target", "Sensitivity analysis", expect=0)
    _, build2, _ = _cli("report", "build")
    unmapped_anchor_blocks = any(
        c["name"] == "requirements_coverage" and not c["ok"]
        for c in build2["checks"]) if build2 else False

    _cli("requirements", "map", "--requirement", "RQ-01", "--target", "Findings",
         expect=0)
    _, build3, _ = _cli("report", "build", expect=0)

    _cli("requirements", "add", "--text", "Provide the paywalled dataset", expect=0)
    _cli("requirements", "waive", "--requirement", "RQ-02",
         "--reason", "dataset is paywalled; excerpts quoted instead", expect=0)
    _, build4, _ = _cli("report", "build", expect=0)
    report = (project / "report.md").read_text(encoding="utf-8")
    waiver_visible = "paywalled" in report and "Requirement Coverage" in report
    return blocks and unmapped_anchor_blocks and build3 is not None \
        and build4 is not None and waiver_visible, {
            "unmet_blocks_build": blocks,
            "missing_anchor_blocks": unmapped_anchor_blocks,
            "coverage_table_rendered": "Requirement Coverage" in report,
            "waiver_in_limitations": waiver_visible}


def scenario_overclaim_modality():
    """A claim saying 'not allowed' cannot stand on a quote that only says who is
    responsible; the modality check must downgrade it, and an official-source
    quote must clear it."""
    from conftest import add_source, seed_project

    env = _fresh_env()
    seed_project(env, question="Can lendtechs assess credit?")
    project = next((env["vault"] / "projects").glob("*"))
    news_id, _ = add_source(
        project,
        text="The central bank statement said banks bear final responsibility for "
             "credit decisions; cooperation with lendtechs was described as optional.",
        title="Central bank briefing coverage", url="https://news.example/cb",
        service="web", type_="news", published="2025-06-01")
    _cli("credibility", "score", expect=0)
    _, ev_news, _ = _cli("evidence", "add", "--source-id", news_id, "--locator", "¶2",
                         "--angle", "physiology",
                         "--quote", "banks bear final responsibility for credit "
                                    "decisions; cooperation with lendtechs was "
                                    "described as optional", expect=0)
    _, bad_claim, _ = _cli("claims", "add", "--text",
                           "Lendtechs are not allowed to assess credit risk",
                           "--kind", "normative", "--tags", "credit",
                           "--angles", "physiology",
                           "--evidence", ev_news["evidence_id"], expect=0)
    _, verify1, _ = _cli("verify", expect=0)
    flagged = any(m["claim_id"] == bad_claim["claim_id"]
                  for m in verify1["modality_mismatches"])
    official_gap = any(g["claim_id"] == bad_claim["claim_id"]
                       for g in verify1["primary_source_gaps"])
    downgraded = (verify1["claims_summary"].get("weakly_supported", 0) >= 1)

    reg_id, _ = add_source(project,
                           text="Regulation X prohibits non-bank lenders from "
                                "conducting independent credit assessments.",
                           title="Regulation X", url="https://regulator.example/x",
                           service="web", type_="regulation", published="2026-01-15",
                           doi=None, authors=("Regulator",))
    _, ev_reg, _ = _cli("evidence", "add", "--source-id", reg_id, "--locator", "Art. 4",
                        "--angle", "physiology",
                        "--quote", "Regulation X prohibits non-bank lenders from "
                                   "conducting independent credit assessments", expect=0)
    _, good_claim, _ = _cli("claims", "add", "--text",
                            "Non-bank lenders are prohibited from independent "
                            "credit assessments", "--kind", "normative",
                            "--tags", "credit", "--angles", "physiology",
                            "--evidence", ev_reg["evidence_id"], expect=0)
    _, verify2, _ = _cli("verify", expect=0)
    cleared = not any(m["claim_id"] == good_claim["claim_id"]
                      for m in verify2["modality_mismatches"]) \
        and not any(g["claim_id"] == good_claim["claim_id"]
                    for g in verify2["primary_source_gaps"])
    return flagged and official_gap and downgraded and cleared, {
        "modality_mismatch_flagged": flagged,
        "primary_source_gap_flagged": official_gap,
        "claim_downgraded": downgraded,
        "official_source_clears": cleared}




def _manuscript_body() -> str:
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
    return f"""---
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


def scenario_manuscript_fulltext_gate():
    from test_fulltext import _verified_source

    env = _fresh_env()
    project, rec = _verified_source(env)
    _cli("brief", "set", "--deliverable-type", "academic-manuscript", expect=0)
    _cli("manuscript", "scaffold", expect=0)
    (project / "manuscript" / "draft.md").write_text(_manuscript_body(), encoding="utf-8")
    _, built, _ = _cli("manuscript", "build", expect=0)
    cov = built["metrics"]["fulltext"]
    path = project / rec["fulltext"]["text_path"]
    path.write_text(path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")
    _, checked, _ = _cli("manuscript", "check")
    integrity = any(c["name"] == "fulltext_integrity" and not c["ok"]
                    for c in checked["checks"])
    return built["ok"] and cov["verified_ratio"] == 1.0 and integrity, {
        "built": built["ok"], "verified_ratio": cov["verified_ratio"],
        "tamper_detected": integrity}


def scenario_live_search():
    _fresh_env()
    os.environ["RESEARCH_OS_OFFLINE"] = "0"
    try:
        from connectors import registry

        res = registry.route("intermittent fasting lean mass", domains=["academic", "web"],
                             limit=5, override_source="openalex")
        got = len(res["records"]) > 0
        return got, {"records": len(res["records"]), "failures": res["failures"]}
    except Exception as exc:  # noqa: BLE001
        return False, {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        os.environ["RESEARCH_OS_OFFLINE"] = "1"


SCENARIOS = {
    "citation_fabrication": scenario_citation_fabrication,
    "planted_contradiction": scenario_planted_contradiction,
    "number_drift": scenario_number_drift,
    "echo_chamber": scenario_echo_chamber,
    "multilingual_fa": scenario_multilingual_fa,
    "budget_quick": scenario_budget_quick,
    "requirement_coverage": scenario_requirement_coverage,
    "overclaim_modality": scenario_overclaim_modality,
    "manuscript_fulltext_gate": scenario_manuscript_fulltext_gate,
}

LIVE_SCENARIOS = {"live_search": scenario_live_search}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="run offline scenarios (default)")
    ap.add_argument("--live", action="store_true", help="also run live-network scenarios")
    ap.add_argument("--only", help="run a single scenario by name")
    ap.add_argument("--keep-temp", action="store_true", help="keep scenario sandboxes")
    args = ap.parse_args()

    os.environ.setdefault("RESEARCH_OS_OFFLINE", "1")
    todo = dict(SCENARIOS)
    if args.live:
        todo.update(LIVE_SCENARIOS)
    if args.only:
        todo = {k: v for k, v in todo.items() if k == args.only}
        if not todo:
            print(json.dumps({"error": f"unknown scenario '{args.only}'"}))
            sys.exit(2)

    results, passed = [], 0
    for name, fn in todo.items():
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, {"exception": f"{type(exc).__name__}: {exc}",
                                 "trace": traceback.format_exc()[-800:]}
        results.append({"scenario": name, "pass": bool(ok), "detail": detail})
        if ok:
            passed += 1

    if not args.keep_temp:
        for d in _TMP_DIRS:
            shutil.rmtree(d, ignore_errors=True)

    summary = {"scenarios": len(results), "passed": passed,
               "failed": len(results) - passed, "results": results}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
