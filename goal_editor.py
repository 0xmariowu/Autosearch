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
    for query in list(queries or []):
        for platform in list((query or {}).get("platforms") or []):
            name = str((platform or {}).get("name") or "").strip()
            if name and name in available_providers and name not in inferred:
                inferred.append(name)
    return inferred or list(available_providers)


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
        self.dimension_queries = goal_case.get("dimension_queries", {})
        self.refinement_terms = list(goal_case.get("refinement_terms", []))
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
        round_history: list[dict[str, Any]] | None = None,
        max_queries: int = 5,
    ) -> list[Any]:
        round_history = list(round_history or [])
        missing_dimensions = list(judge_result.get("missing_dimensions", []))
        dimension_scores = judge_result.get("dimension_scores", {}) or {}
        recent_failed_queries = {
            str(query.get("text") or "").strip().lower()
            for item in round_history[-3:]
            if not item.get("accepted")
            for query in item.get("queries", [])
            if str(query.get("text") or "").strip()
        }

        focus_dimensions: list[str] = []
        for dim in missing_dimensions:
            if dim not in focus_dimensions:
                focus_dimensions.append(dim)

        if not focus_dimensions:
            ordered = sorted(
                dimension_scores.items(),
                key=lambda item: int(item[1]),
            )
            focus_dimensions = [dim for dim, _ in ordered[:2]]

        candidate_queries: list[Any] = []
        for dim in focus_dimensions:
            for query in self.dimension_queries.get(dim, []):
                spec = _normalize_query_spec(query)
                if (
                    spec["text"]
                    and _query_key(spec) not in tried_queries
                    and spec["text"].lower() not in recent_failed_queries
                    and spec not in candidate_queries
                ):
                    candidate_queries.append(spec)
            if len(candidate_queries) >= max_queries:
                break

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
        explore_budget = float(active_program.get("explore_budget", 0.4) or 0.4)
        exploit_budget = float(active_program.get("exploit_budget", 0.6) or 0.6)
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
            round_history=round_history,
            max_queries=max_queries,
        )
        anchor_queries: list[dict[str, Any]] = []
        anchors = _anchor_evidence(self.goal_case, bundle_state, judge_result)
        for dim_id in _weak_dimensions(self.goal_case, judge_result, max_count=2):
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
            plans.append({
                "label": "heuristic-anchored",
                "queries": anchor_queries[:max_queries],
                "program_overrides": {
                    "provider_mix": _provider_mix_for_queries(anchor_queries[:max_queries], available_providers),
                    "exploit_budget": max(exploit_budget, 0.75),
                    "explore_budget": min(explore_budget, 0.25),
                    "sampling_policy": {
                        **dict(active_program.get("sampling_policy") or {}),
                        "anchor_followups": True,
                    },
                },
            })
        if focus:
            plans.append({
                "label": "heuristic-primary",
                "queries": focus,
                "program_overrides": {
                    "provider_mix": _provider_mix_for_queries(focus, available_providers),
                    "exploit_budget": max(exploit_budget, 0.65),
                    "explore_budget": min(explore_budget, 0.35),
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
                    "topic_frontier": _rotate_frontier(current_frontier, topic_id),
                    "explore_budget": max(explore_budget, 0.7),
                    "exploit_budget": min(exploit_budget, 0.3),
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
                        "exploit_budget": max(exploit_budget, 0.7),
                        "explore_budget": min(explore_budget, 0.3),
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
        return bool(self.api_key)

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
            f"Active program: {json.dumps({k: active_program.get(k) for k in ['explore_budget', 'exploit_budget', 'sampling_policy', 'topic_frontier']}, ensure_ascii=False)}\n"
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
            f"Return only JSON: {{\"plans\": [{{\"label\": \"...\", \"program_overrides\": {{\"topic_frontier\": [], \"explore_budget\": 0.4, \"exploit_budget\": 0.6, \"sampling_policy\": {{}}}}, \"queries\": [{{\"text\": \"...\", \"platforms\": [{{\"name\": \"provider\", \"query\": \"...\", \"repo\": \"owner/repo\", \"limit\": 5, \"min_stars\": 0}}]}}]}}]}}\n"
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
