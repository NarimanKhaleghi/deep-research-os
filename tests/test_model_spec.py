"""Model-card rigor — exact recomputation, comparator fidelity, provenance."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import full_quick_run, run_cli
from jsonschema import Draft202012Validator


def _case(cid, kind, p=0.6, i0=100, v=300, c=20, decision="stage"):
    return {
        "id": cid, "kind": kind,
        "inputs": {"I0": i0, "p": p, "V": v, "C": c},
        "outputs": {"OV": -i0 + p * v - c},
        "decision": decision,
        "early_warning": "pilot conversion below 55%",
    }


def _model():
    cases = [_case("BASE", "baseline")]
    scenarios = [(0.30, 100, 300, 20), (0.45, 100, 300, 20), (0.60, 100, 300, 20),
                 (0.75, 100, 300, 20), (0.40, 120, 260, 30)]
    for index, values in enumerate(scenarios, 2):
        cases.append(_case(f"S{index}", "scenario", *values))
    sensitivity = []
    for param, values, prefix in (("p", (0.3, 0.7), "SP"), ("I0", (50, 150), "SI"),
                                  ("V", (200, 400), "SV")):
        ids = []
        for index, value in enumerate(values, 1):
            kwargs = {"p": 0.6, "i0": 100, "v": 300, "c": 20}
            kwargs[{"p": "p", "I0": "i0", "V": "v"}[param]] = value
            cid = f"{prefix}{index}"
            ids.append(cid)
            cases.append(_case(cid, "sensitivity", **kwargs))
        sensitivity.append({"parameter": param, "case_ids": ids,
                            "breakpoint": "none within the tested range"})
    return {
        "schema_version": "1.0",
        "title": "Illustrative stage-gate model",
        "scope": {"structure": "single-stage", "implemented_stages": 1,
                  "learning": False, "selection": "ranking",
                  "limitations": ["A deterministic model is not a forecast."]},
        "variables": [
            {"symbol": "I0", "name": "Initial investment", "role": "parameter",
             "unit": "USD", "baseline": 100, "range": [0, 200], "source": "ASSUMPTION",
             "assumption": "illustrative"},
            {"symbol": "p", "name": "Success probability", "role": "probability",
             "unit": "1", "baseline": 0.6, "range": [0, 1], "source": "ASSUMPTION",
             "assumption": "illustrative"},
            {"symbol": "V", "name": "Success payoff", "role": "parameter",
             "unit": "USD", "baseline": 300, "source": "ASSUMPTION",
             "assumption": "illustrative"},
            {"symbol": "C", "name": "Gate cost", "role": "parameter",
             "unit": "USD", "baseline": 20, "source": "ASSUMPTION",
             "assumption": "illustrative"},
        ],
        "equations": [{"id": "EQ-01", "output": "OV",
                       "expression": "-I0 + p*V - C",
                       "description": "One-stage option value."}],
        "comparators": [{
            "name": "WSJF", "source_ids": ["SRC-0001"],
            "dimensions": {"cost_of_delay": "yes", "staging": "no", "learning": "no"},
            "dimension_notes": {
                "staging": "WSJF prioritizes work items; it does not value a gate.",
                "learning": "No information-update step.",
            },
            "where_it_differs": "WSJF is a static ranking; OV prices deferral.",
        }],
        "baseline": {"method": "NPV", "case_id": "BASE",
                     "source_ids": ["SRC-0001"], "notes": "same input vector"},
        "cases": cases,
        "sensitivity": sensitivity,
        "reproduction": {"command": "python scripts/research_ctl.py model check"},
    }


def _write(project, model):
    (project / "model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")


def _check(result, name):
    return next((c for c in result["checks"] if c["name"] == name), None)


def test_model_card_recomputes_and_discloses_scope(env):
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "references" / "schemas"
         / "model.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(_model())) == []

    project, _ = full_quick_run(env)
    run_cli("brief", "set", "--deliverable-type", "decision-framework", expect=0)
    run_cli("brief", "show", expect=0)

    code, result, _ = run_cli("report", "build", expect=1)
    assert _check(result, "model_artifact")["ok"] is False

    _write(project, _model())
    _, checked, _ = run_cli("model", "check", expect=0)
    assert checked["valid"] is True and checked["summary"]["scenarios"] == 5

    _, built, _ = run_cli("report", "build", expect=0)
    assert _check(built, "model_artifact")["ok"] is True
    assert _check(built, "model_scope_disclosed")["ok"] is True
    text = (project / "report.md").read_text(encoding="utf-8")
    assert "Model & Reproducibility" in text
    assert "single-stage" in text and "WSJF" in text
    assert "A deterministic model is not a forecast." in text
    assert "built-in method" not in text
    assert "2.3%, 8" in text
    html = (project / "report.html").read_text(encoding="utf-8")
    assert "built-in method" not in html and "2.3%, 8" in html

    broken = _model()
    broken["cases"][0]["outputs"]["OV"] += 1
    _write(project, broken)
    _, rejected, _ = run_cli("report", "build", expect=1)
    artifact = _check(rejected, "model_artifact")
    assert artifact["ok"] is False
    assert "does not reproduce" in artifact["detail"]

    unsafe = _model()
    unsafe["equations"][0]["expression"] = "().__class__"
    _write(project, unsafe)
    _, rejected, _ = run_cli("model", "check", expect=1)
    assert "unsupported" in " ".join(rejected["errors"])

    no_scope = _model()
    del no_scope["scope"]
    _write(project, no_scope)
    _, rejected, _ = run_cli("model", "check", expect=1)
    assert "scope" in " ".join(rejected["errors"]).lower()


def test_comparator_must_name_where_it_differs(env):
    project, _ = full_quick_run(env)
    run_cli("brief", "set", "--deliverable-type", "decision-framework", expect=0)
    model = _model()
    del model["comparators"][0]["dimension_notes"]["staging"]
    model["comparators"][0]["where_it_differs"] = ""
    _write(project, model)
    _, result, _ = run_cli("model", "check", expect=1)
    joined = " ".join(result["errors"])
    assert "dimension_notes.staging" in joined
    assert "where_it_differs" in joined


def test_uncited_numeric_table_rows_and_undated_provenance(env):
    project, ids = full_quick_run(env)
    body = (
        f"The comparator table below is uncited.\n\n"
        f"| Lever | Value |\n| --- | --- |\n| Stage cost | 42 |\n\n"
        f"See [{ids['cl1']}]."
    )
    run_cli("findings", "new", "--title", "Uncited comparator table",
            "--claims", ids["cl1"], "--body", body, expect=0)
    _, result, _ = run_cli("report", "build", expect=1)
    assert _check(result, "findings_cited")["ok"] is False

    for finding in (project / "findings").glob("FN-*.md"):
        if "uncited comparator table" in finding.read_text(encoding="utf-8").lower():
            finding.unlink()
    run_cli("brief", "set", "--deliverable-type", "decision-framework", expect=0)
    _write(project, _model())

    source_file = project / "sources" / f"{ids['src_a']}.json"
    source = json.loads(source_file.read_text(encoding="utf-8"))
    source["published"] = None
    source["as_of"] = None
    source_file.write_text(json.dumps(source), encoding="utf-8")
    _, result, _ = run_cli("report", "build", expect=1)
    assert _check(result, "numeric_provenance")["ok"] is False


def test_key_study_requires_full_text_reading(env):
    project, ids = full_quick_run(env)
    run_cli("brief", "set", "--deliverable-type", "academic-paper",
            "--key-studies-target", "1", expect=0)
    run_cli("requirements", "add", "--text", "Provide a decision model",
            expect=0)
    run_cli("requirements", "map", "--requirement", "RQ-01",
            "--target", "Findings", expect=0)
    run_cli("sources", "update", "--source-id", ids["src_a"],
            "--venue", "Journal of Tests", expect=0)
    run_cli("sources", "review", "--source-id", ids["src_a"], "--key",
            "--problem", "p", "--framework", "f", "--method", "m",
            "--context", "c", "--findings", "fi", "--limitations", "l",
            "--relevance", "r", expect=0)
    for kind, title in (("model", "Decision model"), ("scenarios", "Five scenarios"),
                        ("sensitivity", "Breakpoints")):
        run_cli("findings", "new", "--title", title, "--claims", ids["cl1"],
                "--kind", kind, "--body", f"Variant prose for {title} "
                f"[{ids['cl1']}].", expect=0)

    _, result, _ = run_cli("report", "build", expect=1)
    assert _check(result, "evidence_depth")["ok"] is False
    assert "full-text" in _check(result, "evidence_depth")["detail"]

    run_cli("sources", "update", "--source-id", ids["src_a"],
            "--depth", "full-text", expect=0)
    _, result, _ = run_cli("report", "build", expect=0)
    assert _check(result, "evidence_depth")["ok"] is True
