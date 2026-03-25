"""
Goal judge for project-specific search loops.

Supports:

- heuristic local judging (always available)
- OpenRouter judging when OPENROUTER_API_KEY is configured
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from typing import Any


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3-flash-preview"
OPENROUTER_REQUEST_TIMEOUT = float(os.environ.get("OPENROUTER_REQUEST_TIMEOUT", "15"))
OPENROUTER_BUNDLE_TIMEOUT = float(os.environ.get("OPENROUTER_BUNDLE_TIMEOUT", "20"))


def _strict_openrouter_judge() -> bool:
    return os.environ.get("OPENROUTER_STRICT_JUDGE", "1").strip().lower() not in {"0", "false", "no"}


def _normalize_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        for key in ("title", "url", "body", "source", "canonical_text", "fit_markdown", "clean_markdown", "acquired_text"):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(value.lower())
    return "\n".join(parts)


def _criterion_score(weight: int, keywords: list[str], text: str) -> tuple[int, list[str]]:
    hits = [keyword for keyword in keywords if keyword.lower() in text]
    if not hits:
        return 0, []
    ratio = min(1.0, len(hits) / max(2, len(keywords) // 2 or 1))
    return round(weight * ratio), hits


class HeuristicGoalJudge:
    def evaluate(self, goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
        text = _normalize_text(findings)
        total = 0
        criteria_rows: list[dict[str, Any]] = []
        missing_terms: list[str] = []
        matched_terms: list[str] = []
        for criterion in goal_case.get("rubric", []):
            weight = int(criterion.get("weight", 0) or 0)
            keywords = [str(keyword) for keyword in criterion.get("keywords", []) if str(keyword).strip()]
            score, hits = _criterion_score(weight, keywords, text)
            total += score
            criteria_rows.append({
                "id": criterion.get("id", ""),
                "score": score,
                "weight": weight,
                "hits": hits,
            })
            if hits:
                matched_terms.extend(hits)
            elif keywords:
                missing_terms.append(keywords[0])

        total = min(100, total)
        return {
            "query": query,
            "score": total,
            "criteria": criteria_rows,
            "matched_terms": sorted(set(matched_terms)),
            "missing_terms": missing_terms,
            "judge": "heuristic",
        }


class OpenRouterGoalJudge:
    def __init__(self, model: str | None = None):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)

    def enabled(self) -> bool:
        return bool(self.api_key)

    def evaluate(self, goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.enabled():
            raise RuntimeError("OPENROUTER_API_KEY not configured")

        rubric = goal_case.get("rubric", [])
        sample = [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "source": str(item.get("source") or ""),
            }
            for item in findings[:12]
        ]
        prompt = (
            "You are scoring whether search findings improve progress on a concrete project problem.\n"
            f"Problem: {goal_case.get('problem', '')}\n"
            f"Query: {query}\n"
            f"Rubric: {json.dumps(rubric, ensure_ascii=False)}\n"
            f"Findings: {json.dumps(sample, ensure_ascii=False)}\n\n"
            "Return only JSON with keys: score (0-100), matched_terms (array), missing_terms (array), rationale."
        )
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode("utf-8")
        request = urllib.request.Request(
            OPENROUTER_API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=OPENROUTER_REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            content = content[start:end]
        result = json.loads(content)
        result["judge"] = f"openrouter:{self.model}"
        result["query"] = query
        return result


def evaluate_goal_case(goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    openrouter = OpenRouterGoalJudge(model=str(goal_case.get("judge_model") or "").strip() or None)
    if openrouter.enabled():
        if _strict_openrouter_judge():
            return openrouter.evaluate(goal_case, query, findings)
        try:
            return openrouter.evaluate(goal_case, query, findings)
        except Exception:
            pass
    return HeuristicGoalJudge().evaluate(goal_case, query, findings)


def _heuristic_bundle_dimension_score(dimension: dict[str, Any], text: str) -> tuple[int, list[str]]:
    weight = int(dimension.get("weight", 0) or 0)
    keywords = [str(keyword) for keyword in dimension.get("keywords", []) if str(keyword).strip()]
    score, hits = _criterion_score(weight, keywords, text)
    return score, hits


def _bundle_dimensions(goal_case: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = [
        dict(dimension)
        for dimension in list(goal_case.get("dimensions") or [])
        if str(dimension.get("id") or "").strip()
    ]
    if explicit:
        return explicit
    derived: list[dict[str, Any]] = []
    for index, criterion in enumerate(list(goal_case.get("rubric") or []), start=1):
        criterion_id = str(criterion.get("id") or f"criterion_{index}").strip()
        if not criterion_id:
            continue
        derived.append({
            "id": criterion_id,
            "weight": int(criterion.get("weight", 0) or 0),
            "keywords": [str(keyword) for keyword in list(criterion.get("keywords") or []) if str(keyword).strip()],
        })
    return derived


def _normalize_bundle_result(result: dict[str, Any], dimensions: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_ids = [str(dimension.get("id") or "").strip() for dimension in dimensions if str(dimension.get("id") or "").strip()]
    dimension_scores = {
        dimension_id: int((result.get("dimension_scores") or {}).get(dimension_id, 0) or 0)
        for dimension_id in dimension_ids
    }
    matched_dimensions = [
        dimension_id
        for dimension_id in dimension_ids
        if dimension_id in set(str(item) for item in list(result.get("matched_dimensions") or []))
        or int(dimension_scores.get(dimension_id, 0) or 0) > 0
    ]
    missing_dimensions = [
        dimension_id
        for dimension_id in dimension_ids
        if dimension_id not in set(matched_dimensions)
    ]
    normalized = dict(result)
    normalized["score"] = min(100, max(0, int(result.get("score", 0) or 0)))
    normalized["dimension_scores"] = dimension_scores
    normalized["matched_dimensions"] = matched_dimensions
    normalized["missing_dimensions"] = missing_dimensions
    return normalized


def _heuristic_bundle_eval(goal_case: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    text = _normalize_text(findings)
    total = 0
    dimension_scores: dict[str, int] = {}
    missing_dimensions: list[str] = []
    matched_dimensions: list[str] = []
    for dimension in _bundle_dimensions(goal_case):
        dim_id = str(dimension.get("id") or "")
        score, hits = _heuristic_bundle_dimension_score(dimension, text)
        dimension_scores[dim_id] = score
        total += score
        if hits:
            matched_dimensions.append(dim_id)
        else:
            missing_dimensions.append(dim_id)
    return {
        "score": min(100, total),
        "dimension_scores": dimension_scores,
        "missing_dimensions": missing_dimensions,
        "matched_dimensions": matched_dimensions,
        "rationale": "heuristic bundle evaluation",
        "judge": "heuristic-bundle",
    }


def _bundle_sample(findings: list[dict[str, Any]], limit: int = 18, per_query: int = 3) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ordered_queries: list[str] = []
    for item in findings:
        query = str(item.get("query") or "unknown")
        if query not in grouped:
            ordered_queries.append(query)
        grouped[query].append(item)

    sample: list[dict[str, Any]] = []
    round_index = 0
    while len(sample) < limit:
        added = False
        for query in ordered_queries:
            items = grouped.get(query, [])
            if round_index >= len(items) or round_index >= per_query:
                continue
            item = items[round_index]
            sample.append({
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "source": str(item.get("source") or ""),
                "query": str(item.get("query") or ""),
                "body": str(item.get("body") or "")[:400],
            })
            added = True
            if len(sample) >= limit:
                break
        if not added:
            break
        round_index += 1
    return sample


def _openrouter_bundle_eval(goal_case: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = str(goal_case.get("judge_model") or "").strip() or os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    dimensions = _bundle_dimensions(goal_case)
    sample = _bundle_sample(findings, limit=18, per_query=3)
    prompt = (
        "You are a scoring judge only. Do not suggest strategies.\n"
        "Score the cumulative evidence bundle for a concrete project problem.\n"
        f"Problem: {goal_case.get('problem', '')}\n"
        f"Context: {goal_case.get('context_notes', '')}\n"
        f"Dimensions: {json.dumps(dimensions, ensure_ascii=False)}\n"
        f"Evidence bundle: {json.dumps(sample, ensure_ascii=False)}\n\n"
        "Return only JSON with keys: score, dimension_scores, matched_dimensions, missing_dimensions, rationale.\n"
        "dimension_scores must map each dimension id to an integer 0-20.\n"
        "Use both the evidence titles and body snippets. Treat concrete implementation patterns and operational guardrails as positive evidence."
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=OPENROUTER_BUNDLE_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        content = content[start:end]
    result = _normalize_bundle_result(json.loads(content), dimensions)
    result["judge"] = f"openrouter:{model}"
    return result


def evaluate_goal_bundle(goal_case: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    if os.environ.get("OPENROUTER_API_KEY"):
        if _strict_openrouter_judge():
            return _openrouter_bundle_eval(goal_case, findings)
        try:
            return _openrouter_bundle_eval(goal_case, findings)
        except Exception:
            pass
    return _heuristic_bundle_eval(goal_case, findings)
