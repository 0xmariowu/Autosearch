"""
Goal judge for project-specific search loops.

Supports:

- heuristic local judging (always available)
- OpenRouter judging when OPENROUTER_API_KEY is configured
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import defaultdict
from typing import Any


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3-flash-preview"
OPENROUTER_REQUEST_TIMEOUT = float(os.environ.get("OPENROUTER_REQUEST_TIMEOUT", "15"))
OPENROUTER_BUNDLE_TIMEOUT = float(os.environ.get("OPENROUTER_BUNDLE_TIMEOUT", "20"))
CONCEPT_ALIASES = {
    "extract": "extraction",
    "extracts": "extraction",
    "extracting": "extraction",
    "extracted": "extraction",
    "ingest": "extraction",
    "ingests": "extraction",
    "ingestion": "extraction",
    "validate": "validation",
    "validates": "validation",
    "validated": "validation",
    "validating": "validation",
    "schema": "validation",
    "schemas": "validation",
    "check": "validation",
    "checks": "validation",
    "checking": "validation",
    "qa": "validation",
    "quality": "validation",
    "label": "validation",
    "labels": "validation",
    "labeling": "validation",
    "after": "after",
    "later": "after",
    "defer": "after",
    "deferred": "after",
    "subsequent": "after",
    "then": "after",
    "separate": "separate",
    "separated": "separate",
    "separates": "separate",
    "distinct": "separate",
    "different": "separate",
    "split": "separate",
    "stage": "separate",
    "stages": "separate",
    "pass": "separate",
    "passes": "separate",
    "filter": "filter",
    "filters": "filter",
    "filtering": "filter",
    "gate": "filter",
    "gates": "filter",
    "postprocessing": "filter",
    "post-processing": "filter",
}
TOKEN_STOP_WORDS = {
    "and",
    "the",
    "with",
    "from",
    "into",
    "that",
    "this",
    "then",
    "until",
    "later",
    "after",
}
PAIR_SHARED_UNIT_TERMS = (
    "same benchmark instance",
    "same instance",
    "same task",
    "same task identifier",
    "same issue",
    "same benchmark case",
)
PAIR_TRAJECTORY_TERMS = (
    "trajectory",
    "trajectories",
    "trace",
    "traces",
    "rollout",
    "rollouts",
    "run",
    "runs",
    "pair",
    "pairs",
)
PAIR_ARTIFACT_TEXT_TERMS = (
    "dataset",
    "repository",
    "repo",
    "issue",
    "pull request",
    "benchmark release",
    "artifact",
)


def _strict_openrouter_judge() -> bool:
    return os.environ.get("OPENROUTER_STRICT_JUDGE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _normalize_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        for key in (
            "title",
            "url",
            "body",
            "source",
            "canonical_text",
            "fit_markdown",
            "clean_markdown",
            "acquired_text",
        ):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(value.lower())
    return "\n".join(parts)


def _finding_texts(items: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in list(items or []):
        parts = [
            str(item.get(key) or "").strip()
            for key in (
                "title",
                "body",
                "extract",
                "canonical_text",
                "fit_markdown",
                "clean_markdown",
                "acquired_text",
            )
        ]
        text = "\n".join(part for part in parts if part)
        if text:
            texts.append(text)
    return texts


def _stem_token(token: str) -> str:
    normalized = str(token or "").strip().lower()
    for suffix in ("ing", "ed", "es", "s"):
        if len(normalized) > len(suffix) + 2 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _concept_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9_\-]{2,}", str(text or "").lower())
    concepts: set[str] = set()
    for token in tokens:
        stemmed = _stem_token(token)
        concept = CONCEPT_ALIASES.get(token) or CONCEPT_ALIASES.get(stemmed) or stemmed
        if concept and concept not in TOKEN_STOP_WORDS:
            concepts.add(concept)
    return concepts


def _keyword_match(keyword: str, texts: list[str]) -> bool:
    normalized_keyword = str(keyword or "").strip().lower()
    if not normalized_keyword:
        return False
    keyword_concepts = _concept_tokens(normalized_keyword)
    for text in list(texts or []):
        lowered = str(text or "").lower()
        if normalized_keyword in lowered:
            return True
        if not keyword_concepts:
            continue
        overlap = keyword_concepts.intersection(_concept_tokens(lowered))
        if len(keyword_concepts) == 1 and overlap:
            return True
        if len(keyword_concepts) == 2 and len(overlap) == 2:
            return True
        if len(keyword_concepts) >= 3 and len(overlap) >= max(
            2, len(keyword_concepts) - 1
        ):
            return True
    return False


def _criterion_score(
    weight: int, keywords: list[str], texts: list[str]
) -> tuple[int, list[str]]:
    hits = [keyword for keyword in keywords if _keyword_match(keyword, texts)]
    if not hits:
        return 0, []
    ratio = min(1.0, len(hits) / max(2, len(keywords) // 2 or 1))
    return round(weight * ratio), hits


def _dimension_keywords(dimension: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for keyword in list(dimension.get("keywords") or []) + list(
        dimension.get("aliases") or []
    ):
        phrase = str(keyword or "").strip()
        lowered = phrase.lower()
        if not phrase or lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(phrase)
    return keywords


def _pair_extract_text(item: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            str(item.get("title") or "").strip(),
            str(item.get("body") or "").strip(),
            str(item.get("extract") or "").strip(),
            str(item.get("canonical_text") or "").strip(),
            str(item.get("fit_markdown") or "").strip(),
            str(item.get("clean_markdown") or "").strip(),
            str(item.get("acquired_text") or "").strip(),
            str(item.get("query") or "").strip(),
        )
        if part
    ).lower()


def _has_pair_shared_unit(text: str) -> bool:
    return any(term in text for term in PAIR_SHARED_UNIT_TERMS)


def _has_pair_dual_outcome(text: str) -> bool:
    success_side = any(
        term in text
        for term in ("successful", "success", "passed", "passing", "resolved")
    )
    failure_side = any(
        term in text for term in ("failed", "failure", "failing", "unresolved")
    )
    return success_side and failure_side


def _has_pair_trajectory_form(text: str) -> bool:
    return any(term in text for term in PAIR_TRAJECTORY_TERMS)


def _has_pair_artifact_link(item: dict[str, Any], text: str) -> bool:
    source = str(item.get("source") or "").strip().lower()
    url = str(item.get("url") or "").strip().lower()
    if source in {
        "github_repos",
        "github_issues",
        "github_code",
        "huggingface_datasets",
    }:
        return True
    if "github.com" in url or "huggingface.co" in url:
        return True
    return any(term in text for term in PAIR_ARTIFACT_TEXT_TERMS)


def _pair_extract_finding_score(item: dict[str, Any]) -> int:
    text = _pair_extract_text(item)
    if not text:
        return 0
    score = 0
    if _has_pair_shared_unit(text):
        score += 3
    if _has_pair_dual_outcome(text):
        score += 3
    if _has_pair_trajectory_form(text):
        score += 2
    if _has_pair_artifact_link(item, text):
        score += 1
    return score


def _pair_extract_detail(findings: list[dict[str, Any]]) -> dict[str, Any]:
    shared_unit = False
    dual_outcome = False
    trajectory_form = False
    artifact_link = False
    supporting_urls: list[str] = []
    matched_terms: list[str] = []
    seen_urls: set[str] = set()
    seen_terms: set[str] = set()
    for item in list(findings or []):
        text = _pair_extract_text(item)
        if not text:
            continue
        item_shared = _has_pair_shared_unit(text)
        item_dual = _has_pair_dual_outcome(text)
        item_trajectory = _has_pair_trajectory_form(text)
        item_artifact = _has_pair_artifact_link(item, text)
        shared_unit = shared_unit or item_shared
        dual_outcome = dual_outcome or item_dual
        trajectory_form = trajectory_form or item_trajectory
        artifact_link = artifact_link or item_artifact
        if item_shared and "shared_unit" not in seen_terms:
            seen_terms.add("shared_unit")
            matched_terms.append("shared_unit")
        if item_dual and "dual_outcome" not in seen_terms:
            seen_terms.add("dual_outcome")
            matched_terms.append("dual_outcome")
        if item_trajectory and "trajectory_form" not in seen_terms:
            seen_terms.add("trajectory_form")
            matched_terms.append("trajectory_form")
        if item_artifact and "artifact_link" not in seen_terms:
            seen_terms.add("artifact_link")
            matched_terms.append("artifact_link")
        url = str(item.get("url") or "").strip()
        if url and _pair_extract_finding_score(item) >= 5 and url not in seen_urls:
            seen_urls.add(url)
            supporting_urls.append(url)
    return {
        "shared_unit": shared_unit,
        "dual_outcome": dual_outcome,
        "trajectory_form": trajectory_form,
        "artifact_link": artifact_link,
        "matched_terms": matched_terms,
        "supporting_urls": supporting_urls,
    }


def _pair_extract_structural_score(weight: int, detail: dict[str, Any]) -> int:
    signal_count = sum(
        1
        for key in ("shared_unit", "dual_outcome", "trajectory_form", "artifact_link")
        if bool(detail.get(key))
    )
    supporting_count = len(list(detail.get("supporting_urls") or []))
    if signal_count >= 4:
        return weight if supporting_count >= 2 else max(weight - 2, 0)
    if signal_count == 3:
        return max(weight - 5, 0)
    if signal_count == 2:
        return max(weight // 2, 0)
    if signal_count == 1:
        return max(weight // 3, 0)
    return 0


class HeuristicGoalJudge:
    def evaluate(
        self, goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        texts = _finding_texts(findings)
        total = 0
        criteria_rows: list[dict[str, Any]] = []
        missing_terms: list[str] = []
        matched_terms: list[str] = []
        for criterion in goal_case.get("rubric", []):
            weight = int(criterion.get("weight", 0) or 0)
            keywords = [
                str(keyword)
                for keyword in criterion.get("keywords", [])
                if str(keyword).strip()
            ]
            score, hits = _criterion_score(weight, keywords, texts)
            total += score
            criteria_rows.append(
                {
                    "id": criterion.get("id", ""),
                    "score": score,
                    "weight": weight,
                    "hits": hits,
                }
            )
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
        self.model = model or os.environ.get(
            "OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL
        )

    def enabled(self) -> bool:
        return bool(self.api_key)

    def evaluate(
        self, goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]
    ) -> dict[str, Any]:
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
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            OPENROUTER_API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(
            request, timeout=OPENROUTER_REQUEST_TIMEOUT
        ) as response:
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


def evaluate_goal_case(
    goal_case: dict[str, Any], query: str, findings: list[dict[str, Any]]
) -> dict[str, Any]:
    openrouter = OpenRouterGoalJudge(
        model=str(goal_case.get("judge_model") or "").strip() or None
    )
    if openrouter.enabled():
        if _strict_openrouter_judge():
            return openrouter.evaluate(goal_case, query, findings)
        try:
            return openrouter.evaluate(goal_case, query, findings)
        except Exception:
            pass
    return HeuristicGoalJudge().evaluate(goal_case, query, findings)


def _heuristic_bundle_dimension_score(
    dimension: dict[str, Any], findings: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    weight = int(dimension.get("weight", 0) or 0)
    keywords = _dimension_keywords(dimension)
    score, hits = _criterion_score(weight, keywords, _finding_texts(findings))
    if str(dimension.get("id") or "") == "pair_extract":
        detail = _pair_extract_detail(findings)
        score = max(score, _pair_extract_structural_score(weight, detail))
        merged_hits: list[str] = []
        for item in list(hits) + list(detail.get("matched_terms") or []):
            value = str(item or "").strip()
            if value and value not in merged_hits:
                merged_hits.append(value)
        hits = merged_hits
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
        derived.append(
            {
                "id": criterion_id,
                "weight": int(criterion.get("weight", 0) or 0),
                "keywords": [
                    str(keyword)
                    for keyword in list(criterion.get("keywords") or [])
                    if str(keyword).strip()
                ],
                "aliases": [
                    str(keyword)
                    for keyword in list(criterion.get("aliases") or [])
                    if str(keyword).strip()
                ],
            }
        )
    return derived


def _normalize_bundle_result(
    result: dict[str, Any], dimensions: list[dict[str, Any]]
) -> dict[str, Any]:
    def _normalize_dimension_keyword_map(raw: Any) -> dict[str, list[str]]:
        keyword_map = dict(raw or {})
        normalized_map: dict[str, list[str]] = {}
        for dimension_id in dimension_ids:
            phrases: list[str] = []
            seen: set[str] = set()
            for item in list(keyword_map.get(dimension_id) or []):
                phrase = str(item or "").strip()
                lowered = phrase.lower()
                if not phrase or lowered in seen:
                    continue
                seen.add(lowered)
                phrases.append(phrase)
            normalized_map[dimension_id] = phrases
        return normalized_map

    dimension_ids = [
        str(dimension.get("id") or "").strip()
        for dimension in dimensions
        if str(dimension.get("id") or "").strip()
    ]
    dimension_scores = {
        dimension_id: int(
            (result.get("dimension_scores") or {}).get(dimension_id, 0) or 0
        )
        for dimension_id in dimension_ids
    }
    matched_dimensions = [
        dimension_id
        for dimension_id in dimension_ids
        if dimension_id
        in set(str(item) for item in list(result.get("matched_dimensions") or []))
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
    if "dimension_keyword_hits" in result:
        normalized["dimension_keyword_hits"] = _normalize_dimension_keyword_map(
            result.get("dimension_keyword_hits")
        )
    if "dimension_keyword_misses" in result:
        normalized["dimension_keyword_misses"] = _normalize_dimension_keyword_map(
            result.get("dimension_keyword_misses")
        )
    return normalized


def _heuristic_bundle_eval(
    goal_case: dict[str, Any], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    total = 0
    dimension_scores: dict[str, int] = {}
    dimension_keyword_hits: dict[str, list[str]] = {}
    dimension_keyword_misses: dict[str, list[str]] = {}
    missing_dimensions: list[str] = []
    matched_dimensions: list[str] = []
    for dimension in _bundle_dimensions(goal_case):
        dim_id = str(dimension.get("id") or "")
        keywords = _dimension_keywords(dimension)
        score, hits = _heuristic_bundle_dimension_score(dimension, findings)
        matched = {
            str(item or "").strip().lower() for item in hits if str(item or "").strip()
        }
        misses = [keyword for keyword in keywords if keyword.lower() not in matched]
        dimension_scores[dim_id] = score
        dimension_keyword_hits[dim_id] = list(hits)
        dimension_keyword_misses[dim_id] = misses
        total += score
        if hits:
            matched_dimensions.append(dim_id)
        else:
            missing_dimensions.append(dim_id)
    return {
        "score": min(100, total),
        "dimension_scores": dimension_scores,
        "dimension_keyword_hits": dimension_keyword_hits,
        "dimension_keyword_misses": dimension_keyword_misses,
        "missing_dimensions": missing_dimensions,
        "matched_dimensions": matched_dimensions,
        "rationale": "heuristic bundle evaluation",
        "judge": "heuristic-bundle",
    }


def _bundle_sample(
    findings: list[dict[str, Any]], limit: int = 18, per_query: int = 3
) -> list[dict[str, Any]]:
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
            sample.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                    "source": str(item.get("source") or ""),
                    "query": str(item.get("query") or ""),
                    "body": str(item.get("body") or "")[:400],
                }
            )
            added = True
            if len(sample) >= limit:
                break
        if not added:
            break
        round_index += 1
    return sample


def _openrouter_bundle_eval(
    goal_case: dict[str, Any], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = str(goal_case.get("judge_model") or "").strip() or os.environ.get(
        "OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL
    )
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
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode("utf-8")
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


def _bundle_findings(findings: Any) -> list[dict[str, Any]]:
    if isinstance(findings, dict) and "evidence_records" in findings:
        return list(findings.get("evidence_records") or [])
    return list(findings or [])


def evaluate_goal_bundle(goal_case: dict[str, Any], findings: Any) -> dict[str, Any]:
    bundle_findings = _bundle_findings(findings)
    dimensions = _bundle_dimensions(goal_case)
    if os.environ.get("OPENROUTER_API_KEY"):
        if _strict_openrouter_judge():
            result = _openrouter_bundle_eval(goal_case, bundle_findings)
        else:
            try:
                result = _openrouter_bundle_eval(goal_case, bundle_findings)
            except Exception:
                result = _heuristic_bundle_eval(goal_case, bundle_findings)
    else:
        result = _heuristic_bundle_eval(goal_case, bundle_findings)
    if str(result.get("judge") or "") == "heuristic-bundle":
        result = _normalize_bundle_result(result, dimensions)
        result["rationale"] = str(
            result.get("rationale") or "heuristic bundle evaluation"
        )
        result["judge"] = "heuristic-bundle"
    if any(
        str(dimension.get("id") or "") == "pair_extract" for dimension in dimensions
    ):
        result = dict(result)
        result["pair_extract_detail"] = _pair_extract_detail(bundle_findings)
    return result
