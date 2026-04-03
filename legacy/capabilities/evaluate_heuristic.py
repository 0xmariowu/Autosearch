"""Heuristic goal-bundle evaluation using keyword matching — no LLM needed."""

name = "evaluate_heuristic"
description = "Score an evidence bundle against a goal case using deterministic keyword matching. Returns dimension scores, matched/missing terms, and an overall score."
when = "When you need a fast, deterministic evaluation of evidence quality against rubric dimensions without calling an external LLM."
input_type = "evidence"
output_type = "scores"


def run(evidence, **context):
    from goal_judge import _heuristic_bundle_eval, _bundle_findings

    goal_case = context.get("goal_case") or {}
    findings = _bundle_findings(evidence)
    result = _heuristic_bundle_eval(goal_case, findings)
    return result


def test():

    return "ok"
