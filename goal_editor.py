"""
Goal searcher for bundle-based search loops.

The searcher does not score results.
It only looks at:

- the fixed goal
- current bundle score and dimension gaps
- which queries and strategy shapes have already been tried

and decides what to search next.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from urllib.parse import urlparse
from typing import Any


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_EDITOR_MODEL = "google/gemini-3-flash-preview"
OPENROUTER_EDITOR_TIMEOUT = float(os.environ.get("OPENROUTER_EDITOR_TIMEOUT", "20"))
ENABLE_OPENROUTER_EDITOR = os.environ.get("OPENROUTER_ENABLE_EDITOR", "0").strip().lower() in {"1", "true", "yes"}


def _normalize_query_spec(query: Any) -> dict[str, Any]:
    if isinstance(query, dict):
        text = str(query.get("text") or "").strip()
        return {
            "text": text,
            "platforms": _sanitize_platforms(text, list(query.get("platforms") or [])),
        }
    return {"text": str(query or "").strip(), "platforms": []}


def _query_key(query: Any) -> str:
    spec = _normalize_query_spec(query)
    platforms = spec.get("platforms") or []
    return f"{spec.get('text', '')}::{platforms!r}"


def _looks_like_code_literal(text: str) -> bool:
    lowered = text.lower()
    if len(text) > 140:
        return True
    if any(token in lowered for token in ["raise exception", "def ", "class ", "return ", "import "]):
        return True
    punctuation_hits = len(re.findall(r"[{}();=<>]", text))
    if punctuation_hits >= 3:
        return True
    return False


def _sanitize_platforms(query_text: str, platforms: list[Any]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    fallback_query = str(query_text or "").strip()
    for item in platforms:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        platform = dict(item)
        raw_query = str(platform.get("query") or fallback_query).strip()
        if raw_query and _looks_like_code_literal(raw_query):
            platform["query"] = fallback_query
        sanitized.append(platform)
    return sanitized


def _normalize_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {"label": "candidate", "queries": [], "program_overrides": {}}
    queries = [
        _normalize_query_spec(query)
        for query in list(plan.get("queries") or [])
        if _normalize_query_spec(query)["text"]
    ]
    return {
        "label": str(plan.get("label") or "candidate").strip() or "candidate",
        "queries": queries,
        "program_overrides": dict(plan.get("program_overrides") or {}),
    }


def _provider_mix_for_queries(queries: list[dict[str, Any]], available_providers: list[str]) -> list[str]:
    inferred: list[str] = []
    has_unscoped_query = False
    for query in list(queries or []):
        query_platforms = list((query or {}).get("platforms") or [])
        if not query_platforms:
            has_unscoped_query = True
        for platform in query_platforms:
            name = str((platform or {}).get("name") or "").strip()
            if name and name in available_providers and name not in inferred:
                inferred.append(name)
    if has_unscoped_query:
        for provider in list(available_providers):
            if provider not in inferred:
                inferred.append(provider)
    return inferred or list(available_providers)


def _search_backends(active_program: dict[str, Any], available_providers: list[str], provider_mix: list[str] | None = None) -> list[str]:
    preferred = [str(name).strip() for name in list(active_program.get("search_backends") or []) if str(name).strip()]
    candidates = list(provider_mix or preferred or available_providers)
    broad_priority = ["searxng", "ddgs", "exa", "tavily"]
    selected = [name for name in broad_priority if name in candidates and name in available_providers]
    return selected or [name for name in candidates if name in available_providers]


def _backend_roles(
    active_program: dict[str, Any],
    available_providers: list[str],
    *,
    breadth_backends: list[str],
) -> dict[str, list[str]]:
    roles = dict(active_program.get("backend_roles") or {})
    normalized: dict[str, list[str]] = {}
    for key, value in roles.items():
        normalized[str(key)] = [
            str(provider).strip()
            for provider in list(value or [])
            if str(provider).strip() in available_providers
        ]
    normalized["breadth"] = list(breadth_backends)
    return normalized


def _preferred_content_types_for_queries(queries: list[dict[str, Any]]) -> list[str]:
    preferred: list[str] = []
    for query in list(queries or []):
        for platform in list((query or {}).get("platforms") or []):
            name = str((platform or {}).get("name") or "").strip()
            if name == "github_code" and "code" not in preferred:
                preferred.append("code")
            elif name == "github_issues" and "issue" not in preferred:
                preferred.append("issue")
            elif name == "github_repos" and "repository" not in preferred:
                preferred.append("repository")
            elif name == "huggingface_datasets" and "dataset" not in preferred:
                preferred.append("dataset")
    if not preferred:
        preferred.append("web")
    return preferred


def _active_query_templates(
    active_program: dict[str, Any],
    fallback_templates: dict[str, Any],
) -> dict[str, list[Any]]:
    raw = active_program.get("query_templates")
    if isinstance(raw, dict) and raw:
        return {str(key): list(value or []) for key, value in raw.items()}
    return {str(key): list(value or []) for key, value in dict(fallback_templates or {}).items()}


def _active_dimension_strategies(
    active_program: dict[str, Any],
    query_templates: dict[str, list[Any]],
) -> dict[str, dict[str, Any]]:
    raw = dict(active_program.get("dimension_strategies") or {})
    if raw:
        return {
            str(key): {
                "queries": [
                    _normalize_query_spec(query)
                    for query in list((value or {}).get("queries") or [])
                    if _normalize_query_spec(query)["text"]
                ],
                "preferred_providers": [
                    str(provider).strip()
                    for provider in list((value or {}).get("preferred_providers") or [])
                    if str(provider).strip()
                ],
            }
            for key, value in raw.items()
        }
    return {
        str(key): {
            "queries": [
                _normalize_query_spec(query)
                for query in list(value or [])
                if _normalize_query_spec(query)["text"]
            ],
            "preferred_providers": [],
        }
        for key, value in dict(query_templates or {}).items()
    }


def _synthesized_query_templates(goal_case: dict[str, Any]) -> dict[str, list[Any]]:
    def _unique_terms(items: list[str], *, limit: int) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            normalized = str(item or "").strip()
            lowered = normalized.lower()
            if not normalized or lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(normalized)
            if len(ordered) >= limit:
                break
        return ordered

    def _compose_query(*groups: list[str]) -> str:
        terms: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for term in group:
                normalized = str(term or "").strip()
                lowered = normalized.lower()
                if not normalized or lowered in seen:
                    continue
                seen.add(lowered)
                terms.append(normalized)
        return " ".join(terms).strip()

    def _structured_platforms(criterion_id: str, keywords: list[str], query_text: str) -> list[dict[str, Any]]:
        providers = {str(provider).strip() for provider in list(goal_case.get("providers") or []) if str(provider).strip()}
        lowered_id = criterion_id.lower()
        lowered_keywords = [keyword.lower() for keyword in keywords]
        implementation_like = (
            "implementation" in lowered_id
            or "runtime" in lowered_id
            or any(term in lowered_keywords for term in ["cli", "command", "script", "tool", "preflight", "skip", "runtime"])
        )
        config_like = (
            "auth" in lowered_id
            or "config" in lowered_id
            or any(term in lowered_keywords for term in ["auth", "authenticated", "login", "config", "configured"])
        )
        platforms: list[dict[str, Any]] = []
        short_query = " ".join(keywords[:3]) or query_text
        if "github_code" in providers and implementation_like:
            platforms.append({
                "name": "github_code",
                "query": short_query,
                "limit": 5,
            })
        if "github_issues" in providers and (implementation_like or config_like):
            issue_query = " ".join(keywords[:2] + ["provider"]) or query_text
            platforms.append({
                "name": "github_issues",
                "query": issue_query,
                "limit": 5,
            })
        if "github_repos" in providers and ("provider" in lowered_id or config_like):
            repo_query = " ".join(keywords[:2] + ["cli"]) or query_text
            platforms.append({
                "name": "github_repos",
                "query": repo_query,
                "limit": 5,
                "min_stars": 5,
            })
        return platforms

    synthesized: dict[str, list[Any]] = {}
    mutation_terms = [
        str(term).strip()
        for term in list(goal_case.get("mutation_terms") or goal_case.get("refinement_terms") or [])
        if str(term).strip()
    ]
    provider_terms = _unique_terms([
        str(provider).replace("_", " ")
        for provider in list(goal_case.get("providers") or [])
        if str(provider).strip()
    ], limit=2)
    seed_queries = [
        _normalize_query_spec(query)
        for query in list(goal_case.get("seed_queries") or [])
        if _normalize_query_spec(query)["text"]
    ]
    ranked_seed_queries = sorted(
        seed_queries,
        key=lambda item: len(str(item.get("text") or "").split()),
        reverse=True,
    )
    for index, criterion in enumerate(list(goal_case.get("rubric") or []), start=1):
        criterion_id = str(criterion.get("id") or f"criterion_{index}").strip()
        if not criterion_id:
            continue
        keywords = _unique_terms([
            str(keyword).strip()
            for keyword in list(criterion.get("keywords") or [])
            if str(keyword).strip()
        ], limit=4)
        if not keywords:
            continue
        queries: list[dict[str, Any]] = []
        for seed in ranked_seed_queries[:3]:
            seed_query = _compose_query([seed["text"]], [keywords[0]], mutation_terms[:1])
            queries.append(_normalize_query_spec({
                "text": seed_query,
                "platforms": _structured_platforms(criterion_id, keywords, seed_query),
            }))
        base = _compose_query(keywords[:3], provider_terms[:1])
        if base:
            queries.append(_normalize_query_spec({
                "text": base,
                "platforms": _structured_platforms(criterion_id, keywords, base),
            }))
        if base and mutation_terms:
            implementation_query = _compose_query(keywords[:2], provider_terms, mutation_terms[:1], ["implementation"])
            queries.append(_normalize_query_spec({
                "text": implementation_query,
                "platforms": _structured_platforms(criterion_id, keywords + ["implementation"], implementation_query),
            }))
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in queries:
            key = _query_key(query)
            if query["text"] and key not in seen:
                seen.add(key)
                merged.append(query)
        if merged:
            synthesized[criterion_id] = merged
    return synthesized


def _updated_query_templates(
    current_templates: dict[str, list[Any]],
    dim_id: str,
    queries: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    updated = {str(key): list(value or []) for key, value in dict(current_templates or {}).items()}
    if not dim_id:
        return updated
    merged: list[Any] = []
    for query in list(queries or []):
        spec = _normalize_query_spec(query)
        if spec["text"] and spec not in merged:
            merged.append(spec)
    for query in list(updated.get(dim_id) or []):
        spec = _normalize_query_spec(query)
        if spec["text"] and spec not in merged:
            merged.append(spec)
    updated[dim_id] = merged
    return updated


def _updated_dimension_strategies(
    current_strategies: dict[str, dict[str, Any]],
    dim_id: str,
    queries: list[dict[str, Any]],
    available_providers: list[str],
) -> dict[str, dict[str, Any]]:
    updated = {
        str(key): {
            "queries": [
                _normalize_query_spec(query)
                for query in list((value or {}).get("queries") or [])
                if _normalize_query_spec(query)["text"]
            ],
            "preferred_providers": [
                str(provider).strip()
                for provider in list((value or {}).get("preferred_providers") or [])
                if str(provider).strip()
            ],
        }
        for key, value in dict(current_strategies or {}).items()
    }
    if not dim_id:
        return updated
    merged_queries: list[dict[str, Any]] = []
    preferred_providers = list((updated.get(dim_id) or {}).get("preferred_providers") or [])
    for query in list(queries or []) + list((updated.get(dim_id) or {}).get("queries") or []):
        spec = _normalize_query_spec(query)
        if spec["text"] and spec not in merged_queries:
            merged_queries.append(spec)
        for platform in list(spec.get("platforms") or []):
            name = str((platform or {}).get("name") or "").strip()
            if name and name in available_providers and name not in preferred_providers:
                preferred_providers.append(name)
    updated[dim_id] = {
        "queries": merged_queries,
        "preferred_providers": preferred_providers,
    }
    return updated


def _provider_capability_notes(available_providers: list[str]) -> dict[str, str]:
    notes = {
        "github_repos": "use for repos, benchmarks, libraries, and projects",
        "github_issues": "use for design discussions, bug threads, operational guardrails, and release failures",
        "github_code": "use for implementation artifacts, concrete keywords in files, release-gate code, and dedup logic",
        "huggingface_datasets": "use for public datasets and benchmarks",
        "twitter_xreach": "use for public threads that point to concrete external artifacts",
    }
    return {name: notes.get(name, "use only when directly relevant") for name in available_providers}


def _repo_name_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if "github.com" not in parsed.netloc.lower():
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def _dataset_name_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if "huggingface.co" not in parsed.netloc.lower():
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "datasets":
        return parts[1]
    return ""


def _weak_dimensions(goal_case: dict[str, Any], judge_result: dict[str, Any], max_count: int = 2) -> list[str]:
    dimension_scores = judge_result.get("dimension_scores", {}) or {}
    if dimension_scores:
        return [
            dim_id
            for dim_id, _score in sorted(dimension_scores.items(), key=lambda item: int(item[1] or 0))[:max_count]
        ]
    return [str(dim.get("id") or "") for dim in list(goal_case.get("dimensions") or [])[:max_count] if str(dim.get("id") or "")]


def _repair_focus_dimensions(
    goal_case: dict[str, Any],
    active_program: dict[str, Any],
    judge_result: dict[str, Any],
    max_count: int = 2,
) -> list[str]:
    focus: list[str] = []
    for dim_id in [str(dim).strip() for dim in list(judge_result.get("missing_dimensions") or []) if str(dim).strip()]:
        if dim_id not in focus:
            focus.append(dim_id)

    stagnation = {
        str(key): int(value or 0)
        for key, value in dict(((active_program.get("plateau_state") or {}).get("dimension_stagnation") or {})).items()
        if str(key).strip()
    }
    for dim_id, _score in sorted(stagnation.items(), key=lambda item: int(item[1] or 0), reverse=True):
        if dim_id not in focus:
            focus.append(dim_id)
        if len(focus) >= max_count:
            return focus[:max_count]

    for dim_id in _weak_dimensions(goal_case, judge_result, max_count=max_count * 2):
        if dim_id and dim_id not in focus:
            focus.append(dim_id)
        if len(focus) >= max_count:
            break
    return focus[:max_count]


def _dimension_keywords(goal_case: dict[str, Any], dim_id: str, limit: int = 2) -> list[str]:
    for dimension in goal_case.get("dimensions", []):
        if str(dimension.get("id") or "") == dim_id:
            return [str(keyword) for keyword in list(dimension.get("keywords") or [])[:limit] if str(keyword).strip()]
    return []


def _anchor_evidence(goal_case: dict[str, Any], bundle_state: dict[str, Any], judge_result: dict[str, Any]) -> dict[str, list[str]]:
    weak = set(_weak_dimensions(goal_case, judge_result, max_count=3))
    repos: list[str] = []
    datasets: list[str] = []
    for item in bundle_state.get("accepted_findings", []) or []:
        title = str(item.get("title") or "").lower()
        body = str(item.get("body") or "").lower()
        if weak:
            matched = False
            for dim_id in weak:
                if any(keyword.lower() in f"{title}\n{body}" for keyword in _dimension_keywords(goal_case, dim_id, limit=3)):
                    matched = True
                    break
            if not matched:
                continue
        repo_name = _repo_name_from_url(str(item.get("url") or ""))
        dataset_name = _dataset_name_from_url(str(item.get("url") or ""))
        if repo_name and repo_name not in repos:
            repos.append(repo_name)
        if dataset_name and dataset_name not in datasets:
            datasets.append(dataset_name)
        if len(repos) >= 4 and len(datasets) >= 4:
            break
    return {"repos": repos[:4], "datasets": datasets[:4]}


def _topic_frontier_queries(goal_case: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    frontier = list(goal_case.get("topic_frontier") or [])
    queries: list[dict[str, Any]] = []
    for topic in frontier:
        for query in list((topic or {}).get("queries") or []):
            spec = _normalize_query_spec(query)
            if spec["text"] and spec not in queries:
                queries.append(spec)
            if len(queries) >= limit:
                return queries
    return queries


def _current_round_role(
    active_program: dict[str, Any],
    bundle_state: dict[str, Any],
    judge_result: dict[str, Any],
    round_history: list[dict[str, Any]],
) -> str:
    round_roles = [str(role).strip() for role in list(active_program.get("round_roles") or []) if str(role).strip()]
    if not round_roles:
        round_roles = ["broad_recall", "dimension_repair", "orthogonal_probe"]
    missing_dimensions = list(judge_result.get("missing_dimensions") or [])
    dimension_scores = {
        str(key): int(value or 0)
        for key, value in dict(judge_result.get("dimension_scores") or {}).items()
        if str(key).strip()
    }
    if not list(bundle_state.get("accepted_findings") or []) and not missing_dimensions and not dimension_scores:
        return "broad_recall"
    low_dimensions = [dim_id for dim_id, score in sorted(dimension_scores.items(), key=lambda item: int(item[1] or 0)) if score < 20]
    if missing_dimensions or low_dimensions:
        recent_repair_rounds = [
            item for item in list(round_history or [])[-2:]
            if str(item.get("round_role") or "") == "dimension_repair"
        ]
        if len(recent_repair_rounds) >= 2 and not any(bool(item.get("accepted")) for item in recent_repair_rounds):
            return "orthogonal_probe" if "orthogonal_probe" in round_roles else round_roles[-1]
        return "dimension_repair" if "dimension_repair" in round_roles else round_roles[0]
    current = str(active_program.get("current_role") or "").strip()
    if current == "orthogonal_probe" and "broad_recall" in round_roles:
        return "broad_recall"
    return "orthogonal_probe" if "orthogonal_probe" in round_roles else round_roles[-1]


def _rotate_frontier(frontier: list[dict[str, Any]], focus_topic_id: str) -> list[dict[str, Any]]:
    if not focus_topic_id:
        return list(frontier or [])
    prioritized: list[dict[str, Any]] = []
    remainder: list[dict[str, Any]] = []
    for topic in list(frontier or []):
        if str((topic or {}).get("id") or "") == focus_topic_id:
            prioritized.append(dict(topic))
        else:
            remainder.append(dict(topic))
    return prioritized + remainder


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    payload = json.loads(text)
    return payload if isinstance(payload, dict) else {}


class HeuristicGoalSearcher:
    def __init__(self, goal_case: dict[str, Any]):
        self.goal_case = goal_case
        dimension_queries = goal_case.get("dimension_queries", {})
        self.dimension_queries = dict(dimension_queries or _synthesized_query_templates(goal_case))
        self.refinement_terms = list(goal_case.get("refinement_terms") or goal_case.get("mutation_terms") or [])
        self.seed_queries = list(goal_case.get("seed_queries", []))
        self.topic_frontier = list(goal_case.get("topic_frontier") or [])

    def initial_queries(self) -> list[Any]:
        return [_normalize_query_spec(query) for query in self.seed_queries if _normalize_query_spec(query)["text"]]

    def next_queries(
        self,
        *,
        bundle_state: dict[str, Any],
        judge_result: dict[str, Any],
        tried_queries: set[str],
        query_templates: dict[str, list[Any]] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        focus_dimensions: list[str] | None = None,
        max_queries: int = 5,
    ) -> list[Any]:
        round_history = list(round_history or [])
        query_templates = {
            str(key): list(value or [])
            for key, value in dict(query_templates or self.dimension_queries).items()
        }
        missing_dimensions = list(judge_result.get("missing_dimensions", []))
        dimension_scores = judge_result.get("dimension_scores", {}) or {}
        recent_failed_queries = {
            str(query.get("text") or "").strip().lower()
            for item in round_history[-3:]
            if not item.get("accepted")
            for query in item.get("queries", [])
            if str(query.get("text") or "").strip()
        }

        effective_focus_dimensions: list[str] = []
        for dim in list(focus_dimensions or []):
            if dim not in effective_focus_dimensions:
                effective_focus_dimensions.append(dim)
        for dim in missing_dimensions:
            if dim not in effective_focus_dimensions:
                effective_focus_dimensions.append(dim)

        if not effective_focus_dimensions:
            ordered = sorted(
                dimension_scores.items(),
                key=lambda item: int(item[1]),
            )
            effective_focus_dimensions = [dim for dim, _ in ordered[:2]]

        if not effective_focus_dimensions and query_templates:
            effective_focus_dimensions = [str(key) for key in list(query_templates.keys())[:2] if str(key)]

        candidate_queries: list[Any] = []
        dim_candidates = {
            dim: [
                _normalize_query_spec(query)
                for query in list(query_templates.get(dim, []) or [])
                if _normalize_query_spec(query)["text"]
            ]
            for dim in effective_focus_dimensions
        }
        round_index = 0
        while len(candidate_queries) < max_queries:
            added = False
            has_more_candidates = False
            for dim in effective_focus_dimensions:
                queries = dim_candidates.get(dim) or []
                if round_index >= len(queries):
                    continue
                if round_index + 1 < len(queries):
                    has_more_candidates = True
                spec = queries[round_index]
                if (
                    spec["text"]
                    and _query_key(spec) not in tried_queries
                    and spec["text"].lower() not in recent_failed_queries
                    and spec not in candidate_queries
                ):
                    candidate_queries.append(spec)
                    added = True
                    if len(candidate_queries) >= max_queries:
                        break
            if not added and not has_more_candidates:
                break
            round_index += 1

        if not candidate_queries:
            best_titles = [
                str(item.get("title") or "")
                for item in (bundle_state.get("accepted_findings") or [])[:3]
                if str(item.get("title") or "").strip()
            ]
            for title in best_titles:
                for term in self.refinement_terms[:3]:
                    query = _normalize_query_spec(f"{title} {term}".strip())
                    if _query_key(query) not in tried_queries and query not in candidate_queries:
                        candidate_queries.append(query)
                    if len(candidate_queries) >= max_queries:
                        break
                if len(candidate_queries) >= max_queries:
                    break

        if not candidate_queries:
            for seed in self.initial_queries()[:max_queries]:
                if _query_key(seed) not in tried_queries and seed["text"].lower() not in recent_failed_queries:
                    candidate_queries.append(seed)
                if len(candidate_queries) >= max_queries:
                    break

        return candidate_queries[:max_queries]

    def candidate_plans(
        self,
        *,
        bundle_state: dict[str, Any],
        judge_result: dict[str, Any],
        tried_queries: set[str],
        available_providers: list[str],
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
    ) -> list[dict[str, Any]]:
        round_history = list(round_history or [])
        active_program = dict(active_program or {})
        current_frontier = list(active_program.get("topic_frontier") or self.topic_frontier)
        current_templates = _active_query_templates(active_program, self.dimension_queries)
        current_strategies = _active_dimension_strategies(active_program, current_templates)
        current_role = _current_round_role(active_program, bundle_state, judge_result, round_history)
        current_acquisition_policy = dict(active_program.get("acquisition_policy") or {})
        current_evidence_policy = dict(active_program.get("evidence_policy") or {})
        current_repair_policy = dict(active_program.get("repair_policy") or {})
        current_population_policy = dict(active_program.get("population_policy") or {})
        explore_budget = float(active_program.get("explore_budget", 0.4) or 0.4)
        exploit_budget = float(active_program.get("exploit_budget", 0.6) or 0.6)
        repair_dimensions = _repair_focus_dimensions(
            self.goal_case,
            active_program,
            judge_result,
            max_count=int(current_repair_policy.get("target_weak_dimensions", 2) or 2),
        )
        recent_failed_queries = {
            str(query.get("text") or "").strip().lower()
            for item in round_history[-3:]
            if not item.get("accepted")
            for query in item.get("queries", [])
            if str(query.get("text") or "").strip()
        }
        focus = self.next_queries(
            bundle_state=bundle_state,
            judge_result=judge_result,
            tried_queries=tried_queries,
            query_templates=current_templates,
            round_history=round_history,
            focus_dimensions=repair_dimensions,
            max_queries=max_queries,
        )
        if current_role == "broad_recall":
            seed_focus = [
                _normalize_query_spec(query)
                for query in self.initial_queries()
                if _normalize_query_spec(query)["text"]
                and _query_key(_normalize_query_spec(query)) not in tried_queries
                and _normalize_query_spec(query)["text"].lower() not in recent_failed_queries
            ]
            if seed_focus:
                focus = seed_focus[:max_queries]
        anchor_queries: list[dict[str, Any]] = []
        anchors = _anchor_evidence(self.goal_case, bundle_state, judge_result)
        weak_dimensions = list(repair_dimensions)
        for dim_id in weak_dimensions:
            keywords = _dimension_keywords(self.goal_case, dim_id, limit=2)
            keyword_query = " ".join(keywords) or dim_id.replace("_", " ")
            for repo_name in anchors["repos"][:2]:
                spec = _normalize_query_spec({
                    "text": f"{repo_name} {dim_id.replace('_', ' ')} implementation",
                    "platforms": [
                        {"name": "github_code", "repo": repo_name, "query": keyword_query, "limit": 5},
                        {"name": "github_issues", "repo": repo_name, "query": keyword_query, "limit": 5},
                    ],
                })
                if _query_key(spec) not in tried_queries and spec not in anchor_queries:
                    anchor_queries.append(spec)
            for dataset_name in anchors["datasets"][:1]:
                spec = _normalize_query_spec({
                    "text": f"{dataset_name} {dim_id.replace('_', ' ')} dataset details",
                    "platforms": [
                        {"name": "huggingface_datasets", "query": dataset_name, "limit": 5},
                    ],
                })
                if _query_key(spec) not in tried_queries and spec not in anchor_queries:
                    anchor_queries.append(spec)

        if not focus and not anchor_queries:
            focus = _topic_frontier_queries(self.goal_case, limit=max_queries)
            if not focus:
                return []
        plans: list[dict[str, Any]] = []
        if anchor_queries:
            anchor_dim = weak_dimensions[:1] or list(judge_result.get("missing_dimensions", []))[:1]
            anchor_provider_mix = _provider_mix_for_queries(anchor_queries[:max_queries], available_providers)
            anchor_search_backends = _search_backends(active_program, available_providers, anchor_provider_mix)
            plans.append({
                "label": f"{current_role}-anchored",
                "queries": anchor_queries[:max_queries],
                "program_overrides": {
                    "provider_mix": anchor_provider_mix,
                    "search_backends": anchor_search_backends,
                    "backend_roles": _backend_roles(active_program, available_providers, breadth_backends=anchor_search_backends),
                    "query_templates": _updated_query_templates(
                        current_templates,
                        anchor_dim[0] if anchor_dim else "",
                        anchor_queries[:max_queries],
                    ),
                    "dimension_strategies": _updated_dimension_strategies(
                        current_strategies,
                        anchor_dim[0] if anchor_dim else "",
                        anchor_queries[:max_queries],
                        available_providers,
                    ),
                    "current_role": "dimension_repair",
                    "exploit_budget": max(exploit_budget, 0.75),
                    "explore_budget": min(explore_budget, 0.25),
                    "acquisition_policy": {
                        **current_acquisition_policy,
                        "acquire_pages": True,
                        "page_fetch_limit": max(int(current_acquisition_policy.get("page_fetch_limit", 1) or 1), 1),
                    },
                    "evidence_policy": {
                        **current_evidence_policy,
                        "preferred_content_types": _preferred_content_types_for_queries(anchor_queries[:max_queries]),
                        "prefer_acquired_text": True,
                    },
                    "repair_policy": {
                        **current_repair_policy,
                        "target_weak_dimensions": max(int(current_repair_policy.get("target_weak_dimensions", 2) or 2), len(anchor_dim) or 1),
                    },
                    "population_policy": {
                        **current_population_policy,
                        "plan_count": max(int(current_population_policy.get("plan_count", plan_count) or plan_count), plan_count),
                        "max_queries": max(int(current_population_policy.get("max_queries", max_queries) or max_queries), max_queries),
                    },
                    "sampling_policy": {
                        **dict(active_program.get("sampling_policy") or {}),
                        "anchor_followups": True,
                    },
                },
            })
        if focus:
            primary_dim = weak_dimensions[:1] or list(judge_result.get("missing_dimensions", []))[:1]
            preferred_providers = list((current_strategies.get(primary_dim[0]) or {}).get("preferred_providers") or []) if primary_dim else []
            provider_mix = _provider_mix_for_queries(focus, available_providers)
            for provider in preferred_providers:
                if provider in available_providers and provider not in provider_mix:
                    provider_mix.append(provider)
            primary_search_backends = _search_backends(active_program, available_providers, provider_mix)
            plans.append({
                "label": f"{current_role}-primary",
                "queries": focus,
                "program_overrides": {
                    "provider_mix": provider_mix,
                    "search_backends": primary_search_backends,
                    "backend_roles": _backend_roles(active_program, available_providers, breadth_backends=primary_search_backends),
                    "query_templates": _updated_query_templates(
                        current_templates,
                        primary_dim[0] if primary_dim else "",
                        focus,
                    ),
                    "dimension_strategies": _updated_dimension_strategies(
                        current_strategies,
                        primary_dim[0] if primary_dim else "",
                        focus,
                        available_providers,
                    ),
                    "current_role": current_role,
                    "exploit_budget": max(exploit_budget, 0.65),
                    "explore_budget": min(explore_budget, 0.35),
                    "acquisition_policy": {
                        **current_acquisition_policy,
                        "acquire_pages": True,
                        "page_fetch_limit": max(int(current_acquisition_policy.get("page_fetch_limit", 1) or 1), 1),
                    },
                    "evidence_policy": {
                        **current_evidence_policy,
                        "preferred_content_types": _preferred_content_types_for_queries(focus),
                    },
                    "repair_policy": {
                        **current_repair_policy,
                        "target_weak_dimensions": max(int(current_repair_policy.get("target_weak_dimensions", 2) or 2), len(primary_dim) or 1),
                    },
                    "population_policy": {
                        **current_population_policy,
                        "plan_count": max(int(current_population_policy.get("plan_count", plan_count) or plan_count), plan_count),
                        "max_queries": max(int(current_population_policy.get("max_queries", max_queries) or max_queries), max_queries),
                    },
                },
            })

        recent_topics = {
            str(item.get("selected_plan_label") or "").strip().lower()
            for item in round_history[-4:]
            if str(item.get("selected_plan_label") or "").strip()
        }
        for topic in current_frontier:
            topic_id = str(topic.get("id") or "frontier").strip()
            topic_queries = [
                _normalize_query_spec(query)
                for query in list(topic.get("queries") or [])
                if _normalize_query_spec(query)["text"]
                and _query_key(_normalize_query_spec(query)) not in tried_queries
                and _normalize_query_spec(query)["text"].lower() not in recent_failed_queries
            ][:max_queries]
            if not topic_queries:
                continue
            label = f"frontier-{topic_id}"
            if label.lower() in recent_topics:
                continue
            plans.append({
                "label": label,
                "queries": topic_queries,
                "program_overrides": {
                    "provider_mix": _provider_mix_for_queries(topic_queries, available_providers),
                    "search_backends": _search_backends(active_program, available_providers, _provider_mix_for_queries(topic_queries, available_providers)),
                    "backend_roles": _backend_roles(active_program, available_providers, breadth_backends=_search_backends(active_program, available_providers, _provider_mix_for_queries(topic_queries, available_providers))),
                    "topic_frontier": _rotate_frontier(current_frontier, topic_id),
                    "current_role": "orthogonal_probe",
                    "explore_budget": max(explore_budget, 0.7),
                    "exploit_budget": min(exploit_budget, 0.3),
                    "acquisition_policy": {
                        **current_acquisition_policy,
                        "acquire_pages": False,
                    },
                    "evidence_policy": {
                        **current_evidence_policy,
                        "preferred_content_types": _preferred_content_types_for_queries(topic_queries),
                    },
                    "repair_policy": {
                        **current_repair_policy,
                        "prefer_backend_rotation": True,
                    },
                    "population_policy": {
                        **current_population_policy,
                        "plan_count": max(int(current_population_policy.get("plan_count", plan_count) or plan_count), plan_count),
                        "max_queries": max(int(current_population_policy.get("max_queries", max_queries) or max_queries), max_queries),
                    },
                    "sampling_policy": {
                        **dict(active_program.get("sampling_policy") or {}),
                        "anchor_followups": False,
                    },
                },
            })
            if len(plans) >= plan_count:
                return plans[:plan_count]

        missing_dimensions = list(judge_result.get("missing_dimensions", []))
        for index, dim in enumerate(missing_dimensions[: max(0, plan_count - 1)], start=1):
            dim_queries = [
                _normalize_query_spec(query)
                for query in self.dimension_queries.get(dim, [])
                if _normalize_query_spec(query)["text"]
                and _query_key(_normalize_query_spec(query)) not in tried_queries
                and _normalize_query_spec(query)["text"].lower() not in recent_failed_queries
            ][:max_queries]
            if dim_queries:
                plans.append({
                    "label": f"heuristic-{dim}",
                    "queries": dim_queries,
                    "program_overrides": {
                        "provider_mix": _provider_mix_for_queries(dim_queries, available_providers),
                        "search_backends": _search_backends(active_program, available_providers, _provider_mix_for_queries(dim_queries, available_providers)),
                        "backend_roles": _backend_roles(active_program, available_providers, breadth_backends=_search_backends(active_program, available_providers, _provider_mix_for_queries(dim_queries, available_providers))),
                        "query_templates": _updated_query_templates(current_templates, dim, dim_queries),
                        "dimension_strategies": _updated_dimension_strategies(
                            current_strategies,
                            dim,
                            dim_queries,
                            available_providers,
                        ),
                        "current_role": "dimension_repair",
                        "exploit_budget": max(exploit_budget, 0.7),
                        "explore_budget": min(explore_budget, 0.3),
                        "acquisition_policy": {
                            **current_acquisition_policy,
                            "acquire_pages": True,
                            "page_fetch_limit": max(int(current_acquisition_policy.get("page_fetch_limit", 1) or 1), 1),
                        },
                        "evidence_policy": {
                            **current_evidence_policy,
                            "preferred_content_types": _preferred_content_types_for_queries(dim_queries),
                        },
                        "repair_policy": {
                            **current_repair_policy,
                            "target_weak_dimensions": max(int(current_repair_policy.get("target_weak_dimensions", 2) or 2), 1),
                        },
                        "population_policy": {
                            **current_population_policy,
                            "plan_count": max(int(current_population_policy.get("plan_count", plan_count) or plan_count), plan_count),
                            "max_queries": max(int(current_population_policy.get("max_queries", max_queries) or max_queries), max_queries),
                        },
                    },
                })
        return plans[:plan_count]


class OpenRouterGoalSearcher:
    def __init__(self, goal_case: dict[str, Any]):
        self.goal_case = goal_case
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("OPENROUTER_EDITOR_MODEL") or os.environ.get(
            "OPENROUTER_MODEL", DEFAULT_EDITOR_MODEL
        )

    def enabled(self) -> bool:
        return bool(self.api_key) and ENABLE_OPENROUTER_EDITOR

    def candidate_plans(
        self,
        *,
        bundle_state: dict[str, Any],
        judge_result: dict[str, Any],
        tried_queries: set[str],
        available_providers: list[str],
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.enabled():
            return []

        round_history = list(round_history or [])
        tried_texts = sorted(
            {
                key.split("::", 1)[0]
                for key in tried_queries
                if "::" in key
            }
        )[:40]
        sample_findings = [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "source": str(item.get("source") or ""),
                "query": str(item.get("query") or ""),
                "body": str(item.get("body") or "")[:260],
            }
            for item in (bundle_state.get("accepted_findings") or [])[:10]
        ]
        weak_dimensions = [
            dim_id
            for dim_id, _score in sorted(
                (judge_result.get("dimension_scores") or {}).items(),
                key=lambda item: int(item[1] or 0),
            )[:3]
        ]
        recent_rounds = [
            {
                "round": int(item.get("round") or 0),
                "accepted": bool(item.get("accepted")),
                "candidate_score": int(item.get("candidate_score") or 0),
                "bundle_score_after_round": int(item.get("bundle_score_after_round") or 0),
                "selected_plan_label": str(item.get("selected_plan_label") or ""),
                "missing_dimensions": list(item.get("missing_dimensions") or []),
                "queries": [str(query.get("text") or "") for query in item.get("queries", [])],
            }
            for item in round_history[-5:]
        ]
        anchors = _anchor_evidence(self.goal_case, bundle_state, judge_result)
        prompt = (
            "You are the autonomous searcher in an autoresearch-style loop.\n"
            "You do not score evidence. Your only job is to propose better next search plans to raise the score.\n"
            f"Problem: {self.goal_case.get('problem', '')}\n"
            f"Context: {self.goal_case.get('context_notes', '')}\n"
            f"Dimensions: {json.dumps(self.goal_case.get('dimensions', []), ensure_ascii=False)}\n"
            f"Current score: {bundle_state.get('score', 0)}\n"
            f"Current dimension scores: {json.dumps(judge_result.get('dimension_scores', {}), ensure_ascii=False)}\n"
            f"Active program: {json.dumps({k: active_program.get(k) for k in ['explore_budget', 'exploit_budget', 'sampling_policy', 'topic_frontier', 'search_backends', 'acquisition_policy', 'evidence_policy', 'repair_policy', 'population_policy']}, ensure_ascii=False)}\n"
            f"Weakest dimensions: {json.dumps(weak_dimensions, ensure_ascii=False)}\n"
            f"Missing dimensions: {json.dumps(judge_result.get('missing_dimensions', []), ensure_ascii=False)}\n"
            f"Judge rationale: {judge_result.get('rationale', '')}\n"
            f"Available providers: {json.dumps(available_providers, ensure_ascii=False)}\n"
            f"Provider notes: {json.dumps(_provider_capability_notes(available_providers), ensure_ascii=False)}\n"
            f"Topic frontier: {json.dumps(self.goal_case.get('topic_frontier', []), ensure_ascii=False)}\n"
            f"Already tried queries: {json.dumps(tried_texts, ensure_ascii=False)}\n"
            f"Recent rounds: {json.dumps(recent_rounds, ensure_ascii=False)}\n"
            f"Anchor repos: {json.dumps(anchors['repos'], ensure_ascii=False)}\n"
            f"Anchor datasets: {json.dumps(anchors['datasets'], ensure_ascii=False)}\n"
            f"Current evidence sample: {json.dumps(sample_findings, ensure_ascii=False)}\n\n"
            f"Return only JSON: {{\"plans\": [{{\"label\": \"...\", \"program_overrides\": {{\"topic_frontier\": [], \"explore_budget\": 0.4, \"exploit_budget\": 0.6, \"sampling_policy\": {{}}, \"search_backends\": [], \"acquisition_policy\": {{}}, \"evidence_policy\": {{}}, \"repair_policy\": {{}}, \"population_policy\": {{}}}}, \"queries\": [{{\"text\": \"...\", \"platforms\": [{{\"name\": \"provider\", \"query\": \"...\", \"repo\": \"owner/repo\", \"limit\": 5, \"min_stars\": 0}}]}}]}}]}}\n"
            f"Propose {plan_count} distinct plans. Each plan must have 2-{max_queries} queries.\n"
            "Use only the available providers.\n"
            "The goal and the judge standard are fixed. Only the search strategy can change.\n"
            "Favor explicit datasets, benchmarks, repo issues, code search artifacts, and implementation details.\n"
            "When possible, follow up inside the anchor repos or anchor datasets instead of issuing only broad generic queries.\n"
            "Use topic rotation: at least one plan should come from a different frontier topic than the recent rejected rounds.\n"
            "Write search-engine-style queries, not code literals or pseudo-code.\n"
            "For github_code, prefer 2-6 plain search terms or short quoted phrases, not full code snippets.\n"
            "Do not repeat stagnant themes from recent rejected rounds unless you materially change the angle.\n"
            "At least one plan should target the weakest dimensions directly, and at least one plan should be orthogonal.\n"
            "Do not include explanations outside the JSON."
        )
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }).encode("utf-8")
        request = urllib.request.Request(
            OPENROUTER_API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=OPENROUTER_EDITOR_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)
        plans = [
            _normalize_plan(plan)
            for plan in list(parsed.get("plans") or [])
        ]
        filtered_plans: list[dict[str, Any]] = []
        for plan in plans:
            queries = [
                query for query in plan["queries"]
                if _query_key(query) not in tried_queries
            ]
            if queries:
                normalized_queries = queries[:max_queries]
                overrides = dict(plan.get("program_overrides") or {})
                overrides.setdefault("provider_mix", _provider_mix_for_queries(normalized_queries, available_providers))
                filtered_plans.append({
                    "label": plan["label"],
                    "queries": normalized_queries,
                    "program_overrides": overrides,
                })
        return filtered_plans[:plan_count]


class GoalSearcher:
    def __init__(self, goal_case: dict[str, Any]):
        self.heuristic = HeuristicGoalSearcher(goal_case)
        self.llm = OpenRouterGoalSearcher(goal_case)

    def initial_queries(self) -> list[Any]:
        return self.heuristic.initial_queries()

    def candidate_plans(
        self,
        *,
        bundle_state: dict[str, Any],
        judge_result: dict[str, Any],
        tried_queries: set[str],
        available_providers: list[str],
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
    ) -> list[dict[str, Any]]:
        if self.llm.enabled():
            try:
                plans = self.llm.candidate_plans(
                    bundle_state=bundle_state,
                    judge_result=judge_result,
                    tried_queries=tried_queries,
                    available_providers=available_providers,
                    active_program=active_program,
                    round_history=round_history,
                    plan_count=plan_count,
                    max_queries=max_queries,
                )
                if plans:
                    return plans
            except Exception:
                pass
        return self.heuristic.candidate_plans(
            bundle_state=bundle_state,
            judge_result=judge_result,
            tried_queries=tried_queries,
            available_providers=available_providers,
            active_program=active_program,
            round_history=round_history,
            plan_count=plan_count,
            max_queries=max_queries,
        )


# Backwards-compatible aliases while the rest of the repo migrates.
HeuristicGoalEditor = HeuristicGoalSearcher
OpenRouterGoalDirector = OpenRouterGoalSearcher
GoalDirector = GoalSearcher
