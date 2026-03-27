"""LLM-based goal-bundle evaluation via OpenRouter."""

import os

name = "evaluate_llm"
description = "Score an evidence bundle against a goal case using an OpenRouter LLM judge. Returns dimension scores, matched/missing terms, rationale, and an overall score."
when = "When you need a nuanced LLM evaluation of evidence quality against rubric dimensions. Requires OPENROUTER_API_KEY."
input_type = "evidence"
output_type = "scores"


def run(evidence, **context):
    from goal_judge import evaluate_goal_bundle, _bundle_findings

    goal_case = context.get("goal_case") or {}
    result = evaluate_goal_bundle(goal_case, evidence)
    return result


def health_check():
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if api_key:
        return {"status": "ok", "message": "OPENROUTER_API_KEY is set"}
    return {"status": "off", "message": "OPENROUTER_API_KEY not configured"}


def test():
    from goal_judge import evaluate_goal_bundle, _bundle_findings  # noqa: F401
    return "ok"
