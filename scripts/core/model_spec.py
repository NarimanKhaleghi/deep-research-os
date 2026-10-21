"""Structured model card — validation, exact recomputation, and report context.

The model card is a project-level ``model.json``. It publishes the parameter
vectors, equations, comparator dimensions and robustness cases behind a
computational finding so a reader can rerun the arithmetic without trusting the
prose.
"""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from typing import Any

from core import report_i18n
from lib import util

MODEL_FILENAME = "model.json"
ROLES = {"input", "parameter", "probability", "state", "constant"}
CASE_KINDS = {"baseline", "scenario", "sensitivity"}
STRUCTURES = {"single-stage", "multi-stage"}
SELECTIONS = {"none", "greedy", "ranking", "heuristic", "optimization", "exact"}
DIMENSIONS = ("cost_of_delay", "staging", "learning")
DIMENSION_VALUES = {"yes", "partial", "no", "na"}
SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SRC_RE = re.compile(r"^SRC-\d{4}$")


def load(project: Path) -> tuple[dict | None, str | None]:
    path = Path(project) / MODEL_FILENAME
    if not path.exists():
        return None, "missing"
    try:
        data = util.read_json(path, None)
    except Exception as exc:  # noqa: BLE001
        return None, f"not valid JSON: {type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "top-level value must be an object"
    return data, None


def is_required(state: dict, findings: list[dict] | None = None) -> tuple[bool, str]:
    """Whether a report may ship without a validated model card."""
    if state.get("deliverable_type") == "decision-framework":
        return True, "decision-framework deliverable"
    if state.get("model_required") is True:
        return True, "state.model_required"
    for finding in findings or []:
        kind = str(finding.get("kind") or "")
        body = str(finding.get("body") or finding.get("body_text")
                   or finding.get("_body") or "")
        if kind not in {"model", "scenarios", "sensitivity"}:
            continue
        if kind == "model" and _looks_computational(body):
            return True, f"computational {kind} finding {finding.get('id', '')}".strip()
    return False, ""


def _looks_computational(body: str) -> bool:
    if not body:
        return False
    has_math = bool(re.search(r"(?<![A-Za-z])[A-Za-z_][A-Za-z0-9_]*\s*=|"
                              r"\b(?:OV|NPV|IRR|WSJF|RICE|VOI)\b|"
                              r"\b(?:formula|equation|expected value|option value)\b",
                              body, re.I))
    return has_math


def validate(project: Path, source_ids: set[str] | None = None,
             strict_contract: bool = False) -> dict:
    data, load_error = load(project)
    result: dict[str, Any] = {
        "present": data is not None or load_error not in (None, "missing"),
        "valid": False,
        "errors": [],
        "warnings": [],
        "summary": {},
        "strict_contract": strict_contract,
        "_data": data,
    }
    errors: list[str] = result["errors"]
    warnings: list[str] = result["warnings"]
    if data is None:
        errors.append(load_error or "model.json missing")
        return _finish(result)
    if load_error:
        errors.append(load_error)
        return _finish(result)
    if not isinstance(data, dict):
        errors.append("model.json must be a JSON object")
        return _finish(result)

    title = str(data.get("title") or "").strip()
    if not title:
        (errors if strict_contract else warnings).append("title is required")
    if data.get("schema_version") not in (None, "1.0", 1, 1.0):
        warnings.append("schema_version should be '1.0'")

    scope = data.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope object is required")
        scope = {}
    structure = str(scope.get("structure") or "")
    if structure not in STRUCTURES:
        errors.append(f"scope.structure must be one of {sorted(STRUCTURES)}")
    implemented = scope.get("implemented_stages")
    if not isinstance(implemented, int) or isinstance(implemented, bool) \
            or implemented < 1:
        errors.append("scope.implemented_stages must be a positive integer")
    total = scope.get("total_stages")
    if total is not None and (not isinstance(total, int) or isinstance(total, bool)
                              or total < 1):
        errors.append("scope.total_stages must be a positive integer")
    elif isinstance(total, int) and isinstance(implemented, int) and total < implemented:
        errors.append("scope.total_stages cannot be smaller than implemented_stages")
    if not isinstance(scope.get("learning"), bool):
        errors.append("scope.learning must be true or false")
    selection = str(scope.get("selection") or "")
    if selection not in SELECTIONS:
        errors.append(f"scope.selection must be one of {sorted(SELECTIONS)}")
    notes = scope.get("limitations")
    if notes is not None and (not isinstance(notes, list)
                              or any(not isinstance(x, str) for x in notes)):
        errors.append("scope.limitations must be an array of strings")

    source_ids = set(source_ids or [])
    variables = data.get("variables")
    vmap: dict[str, dict] = {}
    if not isinstance(variables, list) or not variables:
        errors.append("variables must be a non-empty array")
        variables = []
    for index, variable in enumerate(variables):
        where = f"variables[{index}]"
        if not isinstance(variable, dict):
            errors.append(f"{where} must be an object")
            continue
        symbol = str(variable.get("symbol") or "").strip()
        if not SYMBOL_RE.match(symbol):
            errors.append(f"{where}.symbol must be a valid identifier")
            continue
        if symbol in vmap:
            errors.append(f"{where}.symbol duplicates {symbol}")
            continue
        vmap[symbol] = variable
        if not str(variable.get("name") or "").strip():
            errors.append(f"{where}.name is required")
        role = str(variable.get("role") or "parameter")
        if role not in ROLES:
            errors.append(f"{where}.role must be one of {sorted(ROLES)}")
        baseline = variable.get("baseline")
        if not _is_number(baseline):
            errors.append(f"{where}.baseline must be a finite number")
        else:
            rng = variable.get("range")
            if rng is not None:
                if (not isinstance(rng, (list, tuple)) or len(rng) != 2
                        or not all(_is_number(x) for x in rng) or rng[0] > rng[1]):
                    errors.append(f"{where}.range must be [low, high]")
                elif not (rng[0] <= float(baseline) <= rng[1]):
                    errors.append(f"{where}.baseline is outside its range")
        source = str(variable.get("source") or "").strip()
        if source == "ASSUMPTION":
            if not str(variable.get("assumption") or "").strip():
                errors.append(f"{where}.assumption is required when source is ASSUMPTION")
        elif not SRC_RE.match(source):
            errors.append(f"{where}.source must be an SRC-#### id or ASSUMPTION")
        elif source_ids and source not in source_ids:
            errors.append(f"{where}.source references unknown {source}")
        if not str(variable.get("unit") or "").strip():
            warnings.append(f"{where}.unit is missing; dimensionless values should be '1'")

    equations = data.get("equations")
    eq_outputs: list[str] = []
    eqmap: dict[str, dict] = {}
    if not isinstance(equations, list) or not equations:
        errors.append("equations must be a non-empty array")
        equations = []
    for index, equation in enumerate(equations):
        where = f"equations[{index}]"
        if not isinstance(equation, dict):
            errors.append(f"{where} must be an object")
            continue
        eq_id = str(equation.get("id") or f"EQ-{index + 1:02d}").strip()
        if not ID_RE.match(eq_id):
            errors.append(f"{where}.id must be a simple identifier")
        if eq_id in eqmap:
            errors.append(f"{where}.id duplicates {eq_id}")
        output = str(equation.get("output") or "").strip()
        if not SYMBOL_RE.match(output):
            errors.append(f"{where}.output must be a valid identifier")
            continue
        if output in vmap:
            errors.append(f"{where}.output collides with variable {output}")
            continue
        if output in eq_outputs:
            errors.append(f"{where}.output duplicates {output}")
            continue
        expression = str(equation.get("expression") or "").strip()
        if not expression:
            errors.append(f"{where}.expression is required")
            continue
        names = _expr_names(expression, errors, where)
        known = set(vmap) | set(eq_outputs)
        unknown = sorted(names - known - set(_FUNCS))
        if unknown:
            errors.append(f"{where}.expression references unknown symbol(s): {', '.join(unknown)}")
        eq_outputs.append(output)
        eqmap[eq_id] = equation
        source = str(equation.get("source") or "").strip()
        if source and source != "ASSUMPTION" and not SRC_RE.match(source):
            errors.append(f"{where}.source must be an SRC-#### id or ASSUMPTION")
        elif source and source.startswith("SRC-") and source_ids and source not in source_ids:
            errors.append(f"{where}.source references unknown {source}")

    if not eq_outputs:
        errors.append("no computable equation outputs")

    cases = data.get("cases")
    case_map: dict[str, dict] = {}
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty array")
        cases = []
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{where} must be an object")
            continue
        cid = str(case.get("id") or "").strip()
        if not ID_RE.match(cid):
            errors.append(f"{where}.id must be a simple identifier")
            continue
        if cid in case_map:
            errors.append(f"{where}.id duplicates {cid}")
            continue
        case_map[cid] = case
        kind = str(case.get("kind") or "").strip().lower()
        if kind not in CASE_KINDS:
            errors.append(f"{where}.kind must be one of {sorted(CASE_KINDS)}")
        inputs = case.get("inputs")
        outputs = case.get("outputs")
        if not isinstance(inputs, dict):
            errors.append(f"{where}.inputs must be an object")
            inputs = {}
        if not isinstance(outputs, dict):
            errors.append(f"{where}.outputs must be an object")
            outputs = {}
        required_inputs = set(vmap) - set(eq_outputs)
        missing_inputs = sorted(required_inputs - set(inputs))
        if missing_inputs:
            errors.append(f"{where}.inputs missing: {', '.join(missing_inputs)}")
        unknown_inputs = sorted(set(inputs) - set(vmap))
        if unknown_inputs:
            errors.append(f"{where}.inputs has unknown symbol(s): {', '.join(unknown_inputs)}")
        for symbol, value in inputs.items():
            if symbol in vmap and not _is_number(value):
                errors.append(f"{where}.inputs.{symbol} must be a finite number")
        if not outputs:
            errors.append(f"{where}.outputs must include every equation output")
        if not str(case.get("decision") or "").strip():
            (errors if strict_contract and kind in {"baseline", "scenario"} else warnings).append(
                f"{where}.decision is required")
        if kind == "scenario" and not str(case.get("early_warning") or "").strip():
            (errors if strict_contract else warnings).append(
                f"{where}.early_warning is required for scenarios")
        computed = _evaluate_case(vmap, equations, inputs, errors, where)
        if computed is not None:
            for output in eq_outputs:
                if output not in outputs:
                    errors.append(f"{where}.outputs missing equation output {output}")
                    continue
                expected = computed[output]
                actual = outputs[output]
                if not _is_number(actual):
                    errors.append(f"{where}.outputs.{output} must be a finite number")
                elif not _close(float(actual), expected):
                    errors.append(
                        f"{where}.outputs.{output}={actual} does not reproduce "
                        f"equation value {expected:.8g}")
            unknown_outputs = sorted(set(outputs) - set(eq_outputs))
            if unknown_outputs:
                errors.append(
                    f"{where}.outputs has undeclared output(s): {', '.join(unknown_outputs)}")

    baseline = data.get("baseline")
    if not isinstance(baseline, dict):
        (errors if strict_contract else warnings).append("baseline object is required")
        baseline = {}
    else:
        if not str(baseline.get("method") or "").strip():
            errors.append("baseline.method is required")
        bcase = str(baseline.get("case_id") or "").strip()
        if not bcase:
            errors.append("baseline.case_id is required")
        elif bcase not in case_map:
            errors.append(f"baseline.case_id references unknown case {bcase}")
        elif str(case_map[bcase].get("kind") or "") != "baseline":
            errors.append("baseline.case_id must point at a kind=baseline case")
        for sid in _source_ids(baseline, errors, "baseline"):
            if source_ids and sid not in source_ids:
                errors.append(f"baseline.source_ids references unknown {sid}")

    comparators = data.get("comparators")
    if comparators is None:
        comparators = []
    if not isinstance(comparators, list):
        errors.append("comparators must be an array")
        comparators = []
    if strict_contract and not comparators:
        errors.append("at least one baseline comparator is required for a decision framework")
    for index, comparator in enumerate(comparators):
        where = f"comparators[{index}]"
        if not isinstance(comparator, dict):
            errors.append(f"{where} must be an object")
            continue
        if not str(comparator.get("name") or "").strip():
            errors.append(f"{where}.name is required")
        sids = _source_ids(comparator, errors, where)
        if not sids:
            errors.append(f"{where}.source_ids must name at least one SRC")
        for sid in sids:
            if source_ids and sid not in source_ids:
                errors.append(f"{where}.source_ids references unknown {sid}")
        dims = comparator.get("dimensions")
        notes = comparator.get("dimension_notes") or {}
        if not isinstance(notes, dict):
            errors.append(f"{where}.dimension_notes must be an object")
            notes = {}
        if not isinstance(dims, dict):
            errors.append(f"{where}.dimensions must be an object")
            continue
        missing_dims = [d for d in DIMENSIONS if d not in dims]
        if missing_dims:
            errors.append(f"{where}.dimensions missing: {', '.join(missing_dims)}")
        for dim, value in dims.items():
            if dim not in DIMENSIONS:
                warnings.append(f"{where}.dimensions has unknown dimension {dim}")
            if str(value) not in DIMENSION_VALUES:
                errors.append(f"{where}.dimensions.{dim} must be one of "
                              f"{sorted(DIMENSION_VALUES)}")
            elif str(value) in {"no", "partial"} and not str(notes.get(dim) or "").strip():
                errors.append(f"{where}.dimension_notes.{dim} is required for '{value}'")
        if not any(str(v) == "yes" for v in dims.values()):
            warnings.append(f"{where} claims no full-strength dimension; verify it is not a strawman")
        if not str(comparator.get("where_it_differs") or "").strip():
            errors.append(f"{where}.where_it_differs is required")

    sensitivity = data.get("sensitivity")
    if sensitivity is None:
        sensitivity = []
    if not isinstance(sensitivity, list):
        errors.append("sensitivity must be an array")
        sensitivity = []
    if strict_contract and len(sensitivity) < 3:
        errors.append("decision frameworks require sensitivity tests for at least 3 parameters")
    for index, entry in enumerate(sensitivity):
        where = f"sensitivity[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be an object")
            continue
        param = str(entry.get("parameter") or "").strip()
        if param not in vmap:
            errors.append(f"{where}.parameter references unknown variable {param or '—'}")
        cids = entry.get("case_ids")
        if not isinstance(cids, list) or len(cids) < 2:
            errors.append(f"{where}.case_ids must list at least 2 sensitivity cases")
            cids = []
        seen_values: list[float] = []
        for cid in cids:
            case = case_map.get(str(cid))
            if case is None:
                errors.append(f"{where}.case_ids references unknown case {cid}")
                continue
            if str(case.get("kind") or "") != "sensitivity":
                errors.append(f"{where}.case_ids case {cid} must have kind=sensitivity")
            value = (case.get("inputs") or {}).get(param)
            if not _is_number(value):
                errors.append(f"{where}.case {cid} lacks numeric input {param}")
            else:
                seen_values.append(float(value))
        if len(set(seen_values)) < 2:
            errors.append(f"{where} does not vary {param} across its cases")
        if strict_contract and not str(entry.get("breakpoint") or "").strip():
            errors.append(f"{where}.breakpoint is required (state 'none within range' if robust)")

    if strict_contract:
        scenario_count = sum(1 for c in case_map.values()
                             if str(c.get("kind") or "") == "scenario")
        if scenario_count < 5:
            errors.append("decision frameworks require at least 5 scenario cases")
        if not any(str(c.get("kind") or "") == "baseline" for c in case_map.values()):
            errors.append("a baseline case is required")

    result["summary"] = {
        "title": title,
        "variables": len(vmap),
        "equations": len(eq_outputs),
        "cases": len(case_map),
        "scenarios": sum(1 for c in case_map.values()
                         if str(c.get("kind") or "") == "scenario"),
        "comparators": len(comparators),
        "sensitivity": len(sensitivity),
        "assumptions": sum(1 for v in vmap.values()
                           if str(v.get("source") or "") == "ASSUMPTION"),
    }
    return _finish(result)


def context(project: Path, lang: str = "en") -> dict:
    data, _ = load(project)
    validation = validate(project, strict_contract=False)
    if data is None:
        return {"present": False, "valid": False, "limitations": [], "errors": validation["errors"],
                "warnings": []}
    variables = [v for v in (data.get("variables") or []) if isinstance(v, dict)]
    equations = [e for e in (data.get("equations") or []) if isinstance(e, dict)]
    cases = [c for c in (data.get("cases") or []) if isinstance(c, dict)]
    sensitivity = [s for s in (data.get("sensitivity") or []) if isinstance(s, dict)]
    comparators = [c for c in (data.get("comparators") or []) if isinstance(c, dict)]
    case_by_id = {str(c.get("id")): c for c in cases}
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    t = report_i18n.t
    variables_ctx = []
    for v in variables:
        source = str(v.get("source") or "")
        grounding = "ASSUMPTION"
        if source.startswith("SRC-"):
            grounding = f"[{source}]"
        elif source == "ASSUMPTION":
            grounding = f"{t(lang, 'model.assumption')}: {v.get('assumption') or '—'}"
        elif source:
            grounding = source
        variables_ctx.append({
            "symbol": v.get("symbol"),
            "name": v.get("name") or "—",
            "role": t(lang, f"model.role.{v.get('role')}", default=v.get("role") or "—"),
            "unit": v.get("unit") or "1",
            "baseline": _fmt(v.get("baseline")),
            "range": _fmt_range(v.get("range")),
            "grounding": grounding,
        })
    equations_ctx = [{
        "id": e.get("id") or "—",
        "output": e.get("output") or "—",
        "expression": e.get("expression") or "—",
        "description": e.get("description") or "",
        "source": e.get("source") or "",
    } for e in equations]
    case_ctx = []
    for c in cases:
        inputs = c.get("inputs") if isinstance(c.get("inputs"), dict) else {}
        outputs = c.get("outputs") if isinstance(c.get("outputs"), dict) else {}
        case_ctx.append({
            "id": c.get("id") or "—",
            "kind": t(lang, f"model.case.{c.get('kind')}"),
            "label": c.get("label") or "",
            "inputs": "; ".join(f"{k}={_fmt(v)}" for k, v in inputs.items()),
            "outputs": "; ".join(f"{k}={_fmt(v)}" for k, v in outputs.items()),
            "decision": c.get("decision") or "—",
            "early_warning": c.get("early_warning") or "—",
        })
    sensitivity_ctx = []
    for entry in sensitivity:
        raw_cids = entry.get("case_ids")
        cids = [str(x) for x in raw_cids] if isinstance(raw_cids, list) else []
        values = []
        for cid in cids:
            case = case_by_id.get(cid) or {}
            case_inputs = case.get("inputs") if isinstance(case.get("inputs"), dict) else {}
            value = case_inputs.get(entry.get("parameter"))
            values.append(_fmt(value))
        sensitivity_ctx.append({
            "parameter": entry.get("parameter") or "—",
            "values": ", ".join(values),
            "cases": ", ".join(cids),
            "breakpoint": entry.get("breakpoint") or "—",
        })
    comparator_ctx = []
    for c in comparators:
        dims = c.get("dimensions") if isinstance(c.get("dimensions"), dict) else {}
        notes = c.get("dimension_notes") if isinstance(c.get("dimension_notes"), dict) else {}
        comparator_ctx.append({
            "name": c.get("name") or "—",
            "cost_of_delay": t(lang, f"model.dim.{dims.get('cost_of_delay', 'na')}"),
            "staging": t(lang, f"model.dim.{dims.get('staging', 'na')}"),
            "learning": t(lang, f"model.dim.{dims.get('learning', 'na')}"),
            "notes": "; ".join(f"{k}: {v}" for k, v in notes.items()),
            "sources": ", ".join(
                f"[{x}]" for x in (c.get("source_ids") if isinstance(c.get("source_ids"), list) else [])
            ),
            "where": c.get("where_it_differs") or "—",
        })
    baseline = data.get("baseline") if isinstance(data.get("baseline"), dict) else {}
    auto_limitations = _auto_limitations(scope, lang)
    structure = str(scope.get("structure") or "unspecified")
    selection = str(scope.get("selection") or scope.get("optimization") or "unspecified")
    learning = bool(scope.get("learning"))
    return {
        "present": True,
        "valid": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "title": data.get("title") or "Model",
        "scope": {
            "structure": t(lang, f"model.structure.{structure}", default=structure),
            "implemented_stages": scope.get("implemented_stages") or "—",
            "learning": t(lang, "model.yes" if learning else "model.no"),
            "selection": t(lang, f"model.selection.{selection}", default=selection),
            "notes": scope.get("limitations") or [],
        },
        "variables": variables_ctx,
        "equations": equations_ctx,
        "cases": case_ctx,
        "sensitivity": sensitivity_ctx,
        "comparators": comparator_ctx,
        "baseline": {
            "method": baseline.get("method") or "—",
            "case_id": baseline.get("case_id") or "—",
            "sources": ", ".join(
                f"[{x}]" for x in (baseline.get("source_ids")
                                  if isinstance(baseline.get("source_ids"), list) else [])
            ),
            "notes": baseline.get("notes") or "",
        },
        "reproduction": (data.get("reproduction") or {}).get("command")
                        if isinstance(data.get("reproduction"), dict) else None,
        "limitations": auto_limitations,
    }


def _auto_limitations(scope: dict, lang: str) -> list[str]:
    t = report_i18n.t
    out: list[str] = []
    structure = str(scope.get("structure") or "")
    implemented = scope.get("implemented_stages")
    declared = scope.get("total_stages")
    if structure == "single-stage":
        out.append(t(lang, "lim.model.single_stage"))
    elif structure == "multi-stage" and isinstance(declared, int) \
            and isinstance(implemented, int) and implemented < declared:
        out.append(t(lang, "lim.model.partial_stages", implemented=implemented, total=declared))
    if not bool(scope.get("learning")):
        out.append(t(lang, "lim.model.no_learning"))
    selection = str(scope.get("selection") or scope.get("optimization") or "")
    if selection in {"greedy", "ranking", "heuristic"}:
        out.append(t(lang, "lim.model.heuristic", method=selection))
    notes = scope.get("limitations")
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, str) and note.strip():
                out.append(note.strip())
    return out


def _finish(result: dict) -> dict:
    result["valid"] = not result["errors"]
    result["ok"] = result["valid"]
    return result


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-9)


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value:.8g}" if isinstance(value, float) else str(value)
    return "—"


def _fmt_range(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{_fmt(value[0])} … {_fmt(value[1])}"
    return "—"


def _source_ids(obj: dict, errors: list[str], where: str) -> list[str]:
    ids = obj.get("source_ids") or []
    if not isinstance(ids, list):
        errors.append(f"{where}.source_ids must be an array")
        return []
    out = []
    for sid in ids:
        sid = str(sid)
        if not SRC_RE.match(sid):
            errors.append(f"{where}.source_ids has invalid id {sid}")
        else:
            out.append(sid)
    return out


def _expr_names(expression: str, errors: list[str], where: str) -> set[str]:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        errors.append(f"{where}.expression is not valid arithmetic: {exc.msg}")
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
                errors.append(f"{where}.expression only allows {', '.join(sorted(_FUNCS))} calls")
            if node.keywords:
                errors.append(f"{where}.expression does not allow keyword arguments")
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda,
                               ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            errors.append(f"{where}.expression contains an unsupported construct")
        elif isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            errors.append(f"{where}.expression contains an unsupported constant")
        elif not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Load,
                                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
                                   ast.Mod, ast.USub, ast.UAdd, ast.Constant)):
            errors.append(f"{where}.expression contains unsupported syntax {type(node).__name__}")
    return names


class _ModelEvalError(ValueError):
    pass


def _eval_node(node: ast.AST, env: dict[str, float],
               errors: list[str], where: str) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env, errors, where)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in env:
            return float(env[node.id])
        errors.append(f"{where} expression references unavailable symbol {node.id}")
        raise _ModelEvalError(node.id)
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, env, errors, where)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
        raise _ModelEvalError("unary operator")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env, errors, where)
        right = _eval_node(node.right, env, errors, where)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                errors.append(f"{where} exponent is too large to evaluate safely")
                raise _ModelEvalError("exponent")
            return left ** right
        raise _ModelEvalError("binary operator")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and not node.keywords:
        args = [_eval_node(arg, env, errors, where) for arg in node.args]
        return float(_FUNCS[node.func.id](*args))
    errors.append(f"{where} expression contains unsupported syntax {type(node).__name__}")
    raise _ModelEvalError(type(node).__name__)


_FUNCS = {
    "max": max, "min": min, "abs": abs, "round": round,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log, "log10": math.log10,
}


def _evaluate_case(vmap: dict, equations: list, inputs: dict, errors: list[str],
                   where: str) -> dict | None:
    env: dict[str, float] = {}
    for symbol, variable in vmap.items():
        value = inputs.get(symbol, variable.get("baseline"))
        if _is_number(value):
            env[symbol] = float(value)
    outputs: dict[str, float] = {}
    try:
        for equation in equations:
            if not isinstance(equation, dict):
                continue
            output = str(equation.get("output") or "")
            expression = str(equation.get("expression") or "")
            if not output or not expression:
                return None
            tree = ast.parse(expression, mode="eval")
            value = _eval_node(tree, {**env, **outputs}, errors, where)
            if not _is_number(value):
                errors.append(f"{where} equation {output} produced a non-finite result")
                return None
            outputs[output] = float(value)
            env[output] = float(value)
    except ZeroDivisionError:
        errors.append(f"{where} equation divides by zero for this input vector")
        return None
    except (NameError, TypeError, ValueError, SyntaxError, OverflowError) as exc:
        errors.append(f"{where} equation evaluation failed: {exc}")
        return None
    return outputs
