"""Planner stage for research-oriented search execution."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .decision import SearchDecision
from .modes import get_mode_policy

GENERIC_ANCHOR_TOKENS = {
    "https",
    "http",
    "github",
    "issue",
    "issues",
    "about",
    "using",
    "validation",
    "report",
    "implementation",
    "details",
    "failure",
    "modes",
    "dataset",
    "public",
    "release",
}
STRONG_EVIDENCE_CONTENT_TYPES = ["code", "repository", "issue", "reference", "web"]


def _current_round_role(active_program: dict[str, Any], round_history: list[dict[str, Any]]) -> str:
    roles = [str(item or "").strip() for item in list(active_program.get("round_roles") or []) if str(item or "").strip()]
    if not roles:
        return str(active_program.get("current_role") or "broad_recall")
    if round_history:
        return roles[min(len(round_history), len(roles) - 1)]
    return roles[0]


def _retired_mutation_kinds(active_program: dict[str, Any]) -> set[str]:
    stats = dict(active_program.get("evolution_stats") or {})
    return {
        str(item).strip()
        for item in list(stats.get("retired_mutation_kinds") or [])
        if str(item).strip()
    }


def _branch_budget(active_program: dict[str, Any]) -> dict[str, int]:
    policy = dict(active_program.get("population_policy") or {})
    raw = dict(policy.get("branch_budget_per_round") or {})
    budget = {
        "breadth": 1,
        "repair": 2,
        "followup": 2,
        "probe": 1,
        "research": 1,
    }
    for key, value in raw.items():
        budget[str(key)] = max(int(value or 0), 0)
    return budget


def _recursive_depth_limit(active_program: dict[str, Any]) -> int:
    policy = dict(active_program.get("population_policy") or {})
    return int(policy.get("recursive_depth_limit", policy.get("max_branch_depth", 4)) or 4)


def _anchor_tokens(local_evidence_records: list[dict[str, Any]] | None, *, limit: int = 4) -> list[str]:
    counts: Counter[str] = Counter()
    for item in list(local_evidence_records or []):
        title = str(item.get("title") or "").lower()
        for token in title.split():
            token = token.strip(".,:;()[]{}")
            if len(token) < 5:
                continue
            if token in GENERIC_ANCHOR_TOKENS:
                continue
            counts[token] += 1
    return [token for token, _ in counts.most_common(limit)]


def _goal_case_from_searcher(searcher: Any) -> dict[str, Any]:
    direct_goal_case = dict(getattr(searcher, "goal_case", {}) or {})
    if direct_goal_case:
        return direct_goal_case
    for attr in ("heuristic", "llm"):
        nested = dict(getattr(getattr(searcher, attr, None), "goal_case", {}) or {})
        if nested:
            return nested
    return {}


def _dimension_phrases(goal_case: dict[str, Any], judge_result: dict[str, Any], *, limit: int = 6) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    prioritized = list(judge_result.get("missing_dimensions") or [])
    scores = dict(judge_result.get("dimension_scores") or {})
    if scores:
        prioritized.extend([
            dim_id
            for dim_id, _ in sorted(scores.items(), key=lambda item: int(item[1] or 0))
        ])
    for dim_id in prioritized:
        for dim in list(goal_case.get("dimensions") or []):
            if str(dim.get("id") or "") != str(dim_id):
                continue
            for keyword in list(dim.get("keywords") or []) + list(dim.get("aliases") or []):
                phrase = str(keyword or "").strip()
                lowered = phrase.lower()
                if not phrase or lowered in seen:
                    continue
                seen.add(lowered)
                phrases.append(phrase)
                if len(phrases) >= limit:
                    return phrases
    return phrases


def _missed_keyword_phrases(judge_result: dict[str, Any], *, limit: int = 4) -> list[str]:
    misses = dict(judge_result.get("dimension_keyword_misses") or {})
    scores = dict(judge_result.get("dimension_scores") or {})
    if not misses or not scores:
        return []
    result: list[str] = []
    seen: set[str] = set()
    sorted_dims = sorted(scores.keys(), key=lambda key: int(scores.get(key, 0) or 0))
    for dim_id in sorted_dims:
        for keyword in list(misses.get(dim_id) or []):
            phrase = str(keyword or "").strip()
            lowered = phrase.lower()
            if not phrase or lowered in seen:
                continue
            seen.add(lowered)
            result.append(phrase)
            if len(result) >= limit:
                return result
    return result


def _is_pair_extract_phrase(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    pair_tokens = {
        "pair_extract",
        "pair extract",
        "trajectory",
        "resolved",
        "unresolved",
        "success",
        "failure",
        "successful",
        "failed",
        "instance",
        "swe-bench",
        "same task",
        "verified trajectories",
    }
    return any(token in lowered for token in pair_tokens)


def _is_dedupe_phrase(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    dedupe_tokens = {
        "dedupe",
        "dedup",
        "duplicate",
        "semhash",
        "semantic hash",
        "near duplicate",
        "fake gold",
        "similarity",
    }
    return any(token in lowered for token in dedupe_tokens)


def _pair_followup_templates(*, include_anchor: bool) -> list[str]:
    templates = [
        "{phrase} same task",
        "{phrase} successful failed runs",
        "{phrase} resolved unresolved subset",
        "{phrase} verified trajectories",
    ]
    if include_anchor:
        templates.append("{anchor} {phrase} same benchmark instance")
    return templates


def _dedupe_followup_templates(*, include_anchor: bool) -> list[str]:
    templates = [
        "{phrase} implementation",
        "{phrase} algorithm comparison",
        "{phrase} near duplicate detection",
    ]
    if include_anchor:
        templates.append("{anchor} {phrase} code")
    return templates


def _pair_decomposition_templates(*, include_anchor: bool) -> list[str]:
    templates = [
        "{phrase} same benchmark instance",
        "{phrase} successful failed runs",
        "{phrase} resolved unresolved subset",
        "{phrase} verified trajectories",
    ]
    if include_anchor:
        templates.append("{anchor} {phrase} same task")
    return templates


def _dedupe_decomposition_templates(*, include_anchor: bool) -> list[str]:
    templates = [
        "{phrase} hash function",
        "{phrase} similarity threshold",
        "{phrase} benchmark evaluation",
    ]
    if include_anchor:
        templates.append("{anchor} {phrase} open source")
    return templates


def _followup_program_overrides(active_program: dict[str, Any]) -> dict[str, Any]:
    current_acquisition = dict(active_program.get("acquisition_policy") or {})
    current_evidence = dict(active_program.get("evidence_policy") or {})
    return {
        "current_role": "dimension_repair",
        "acquisition_policy": {
            **current_acquisition,
            "acquire_pages": True,
            "page_fetch_limit": max(int(current_acquisition.get("page_fetch_limit", 2) or 2), 3),
            "use_render_fallback": bool(current_acquisition.get("use_render_fallback", True)),
            "use_crawl4ai_adapter": bool(current_acquisition.get("use_crawl4ai_adapter", True)),
        },
        "evidence_policy": {
            **current_evidence,
            "preferred_content_types": list(STRONG_EVIDENCE_CONTENT_TYPES),
            "prefer_acquired_text": True,
        },
    }


def _merge_preferred_content_types(existing: list[str] | None, extra: list[str] | None) -> list[str]:
    merged: list[str] = []
    for item in list(existing or []) + list(extra or []):
        value = str(item or "").strip()
        if value and value not in merged:
            merged.append(value)
    return merged


def _cross_verification_queries(
    *,
    queries: list[dict[str, Any]],
    tried_queries: set[str],
    max_queries: int,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    suffixes = ["independent review", "limitations", "comparison"]
    for query in list(queries or []):
        text = str((query or {}).get("text") or "").strip()
        if not text:
            continue
        for suffix in suffixes:
            spec = {
                "text": f"{text} {suffix}".strip(),
                "platforms": list((query or {}).get("platforms") or []),
            }
            if str(spec) in tried_queries or spec in variants:
                continue
            variants.append(spec)
            if len(variants) >= max_queries:
                return variants
    return variants


def _decision_for_plan(
    *,
    active_program: dict[str, Any],
    role: str,
    branch_type: str,
    queries: list[dict[str, Any]],
    program_overrides: dict[str, Any],
    judge_result: dict[str, Any],
    tried_queries: set[str],
    max_queries: int,
) -> SearchDecision:
    mode = str(active_program.get("mode") or "balanced")
    mode_policy = get_mode_policy(mode, dict(active_program.get("mode_policy_overrides") or {}))
    provider_mix = list(program_overrides.get("provider_mix") or active_program.get("provider_mix") or [])
    search_backends = list(program_overrides.get("search_backends") or active_program.get("search_backends") or provider_mix)
    backend_roles = dict(active_program.get("backend_roles") or {})
    sampling_policy = {
        **dict(active_program.get("sampling_policy") or {}),
        **dict(program_overrides.get("sampling_policy") or {}),
    }
    acquisition_policy = {
        **dict(active_program.get("acquisition_policy") or {}),
        **dict(program_overrides.get("acquisition_policy") or {}),
    }
    evidence_policy = {
        **dict(active_program.get("evidence_policy") or {}),
        **dict(program_overrides.get("evidence_policy") or {}),
    }
    cross_verify = bool(mode_policy.enable_cross_verification and branch_type in {"repair", "followup", "research"})
    cross_queries = _cross_verification_queries(
        queries=queries,
        tried_queries=tried_queries,
        max_queries=max_queries,
    ) if cross_verify else []
    if cross_queries:
        evidence_policy["cross_verification_required"] = True
    if branch_type in {"repair", "followup", "research"}:
        evidence_policy["preferred_content_types"] = _merge_preferred_content_types(
            list(evidence_policy.get("preferred_content_types") or []),
            STRONG_EVIDENCE_CONTENT_TYPES,
        )
        evidence_policy["prefer_acquired_text"] = True
    if branch_type == "repair" or (mode_policy.enable_acquisition and branch_type in {"followup", "research"}):
        acquisition_policy["acquire_pages"] = True
        acquisition_policy["page_fetch_limit"] = max(int(acquisition_policy.get("page_fetch_limit", 2) or 2), 2)
    rationale = f"{mode} mode -> {role}"
    missing = list(judge_result.get("missing_dimensions") or [])
    if missing:
        rationale += f"; weakest={missing[0]}"
    return SearchDecision(
        role=role,
        mode=mode,
        provider_mix=provider_mix,
        search_backends=search_backends,
        backend_roles=backend_roles,
        sampling_policy=sampling_policy,
        acquisition_policy=acquisition_policy,
        evidence_policy=evidence_policy,
        cross_verify=cross_verify,
        cross_verification_queries=cross_queries,
        stop_if_saturated=not bool(missing),
        rationale=rationale,
    )


def _planning_ops_for_plan(
    *,
    role: str,
    branch_type: str,
    branch_targets: list[str],
    branch_depth: int,
    recursive_depth_limit: int,
    decision: SearchDecision,
) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    primary_target = str((branch_targets or [""])[0]).strip()
    if decision.cross_verify and primary_target:
        ops.append({"op": "request_cross_check", "target": primary_target, "mode": "cross_check"})
    if branch_type in {"followup", "research"} and decision.mode == "deep":
        ops.append({"op": "raise_budget", "amount": 1, "target": primary_target})
    if branch_depth >= recursive_depth_limit and role:
        ops.append({"op": "retire_branch", "target": role, "mutation_kind": _mutation_kind_for_role(role)})
    if primary_target and branch_type == "repair":
        ops.append({"op": "add_branch", "target": primary_target, "role": "graph_followup"})
    if decision.stop_if_saturated and primary_target:
        ops.append({"op": "mark_saturated", "target": primary_target})
    return ops


def _repair_terms(judge_result: dict[str, Any], goal_case: dict[str, Any] | None = None) -> list[str]:
    goal_case = dict(goal_case or {})

    def _repair_label(dim_id: Any) -> str:
        normalized_id = str(dim_id or "").strip()
        if not normalized_id:
            return ""
        for dimension in list(goal_case.get("dimensions") or []):
            if str(dimension.get("id") or "").strip() != normalized_id:
                continue
            for keyword in list(dimension.get("keywords") or []):
                phrase = str(keyword or "").strip()
                if phrase:
                    return phrase
            for alias in list(dimension.get("aliases") or []):
                phrase = str(alias or "").strip()
                if phrase:
                    return phrase
            break
        return normalized_id.replace("_", " ").strip()

    terms: list[str] = []
    for item in list(judge_result.get("missing_dimensions") or [])[:3]:
        text = _repair_label(item)
        if text:
            terms.append(text)
    weakest = ""
    scores = dict(judge_result.get("dimension_scores") or {})
    if scores:
        weakest = min(scores.keys(), key=lambda key: int(scores.get(key, 0) or 0))
    weakest = _repair_label(weakest)
    if weakest and weakest not in terms:
        terms.insert(0, weakest)
    return terms[:3]


def _branch_type(role: str) -> str:
    lowered = str(role or "").strip().lower()
    if lowered in {"broad_recall", "breadth"}:
        return "breadth"
    if lowered in {"graph_followup", "followup"}:
        return "followup"
    if "repair" in lowered:
        return "repair"
    if "probe" in lowered:
        return "probe"
    return "research"


def _mutation_kind_for_role(role: str) -> str:
    branch_type = _branch_type(role)
    if branch_type == "repair":
        return "dimension_repair"
    if branch_type == "probe":
        return "frontier_probe"
    if branch_type == "followup":
        return "anchor_followup"
    if branch_type == "breadth":
        return "broad_recall"
    return "mutation"


def _branch_subgoal(role: str, judge_result: dict[str, Any], goal_case: dict[str, Any] | None = None) -> str:
    repairs = _repair_terms(judge_result, goal_case)
    if repairs:
        return repairs[0]
    return str(role or "research").replace("_", " ")


def _node_id(role: str, index: int, depth: int) -> str:
    return f"{_branch_type(role)}-d{depth}-n{index}"


def _augment_queries(
    queries: list[dict[str, Any]],
    *,
    goal_case: dict[str, Any] | None,
    local_evidence_records: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    tried_queries: set[str],
    max_queries: int,
) -> list[dict[str, Any]]:
    augmented = list(queries)
    anchors = _anchor_tokens(local_evidence_records)
    repairs = _repair_terms(judge_result, goal_case)
    for anchor in anchors:
        for repair in repairs:
            query = {"text": f"{anchor} {repair}".strip(), "platforms": []}
            key = str(query)
            if key in tried_queries:
                continue
            if query not in augmented:
                augmented.append(query)
            if len(augmented) >= max_queries:
                return augmented[:max_queries]
    return augmented[:max_queries]


def _follow_up_queries(
    *,
    goal_case: dict[str, Any],
    local_evidence_records: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    max_queries: int,
    tried_queries: set[str],
) -> list[dict[str, Any]]:
    anchors = _anchor_tokens(local_evidence_records, limit=6)
    repairs = _repair_terms(judge_result, goal_case)
    missed = _missed_keyword_phrases(judge_result, limit=4)
    missed_lower = {phrase.lower() for phrase in missed}
    phrases = missed + [
        phrase
        for phrase in (_dimension_phrases(goal_case, judge_result, limit=6) or repairs)
        if str(phrase or "").strip().lower() not in missed_lower
    ]
    follow_ups: list[dict[str, Any]] = []
    for phrase in phrases or repairs:
        templates = (
            _pair_followup_templates(include_anchor=bool(anchors))
            if _is_pair_extract_phrase(phrase)
            else _dedupe_followup_templates(include_anchor=bool(anchors))
            if _is_dedupe_phrase(phrase)
            else [
                "{phrase} repository implementation",
                "{anchor} {phrase} source proof",
                "{phrase} release issue",
            ]
        )
        for template in templates:
            anchor = anchors[0] if anchors else ""
            spec = {"text": template.format(anchor=anchor, phrase=phrase).strip(), "platforms": []}
            if str(spec) in tried_queries or spec in follow_ups:
                continue
            follow_ups.append(spec)
            if len(follow_ups) >= max_queries:
                return follow_ups
    for repair in repairs:
        for anchor in anchors:
            spec = {"text": f"{anchor} {repair} implementation".strip(), "platforms": []}
            if str(spec) in tried_queries or spec in follow_ups:
                continue
            follow_ups.append(spec)
            if len(follow_ups) >= max_queries:
                return follow_ups
    return follow_ups


def _decomposition_followups(
    *,
    goal_case: dict[str, Any],
    local_evidence_records: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    max_queries: int,
    tried_queries: set[str],
) -> list[dict[str, Any]]:
    anchors = _anchor_tokens(local_evidence_records, limit=8)
    repairs = _repair_terms(judge_result, goal_case)
    missed = _missed_keyword_phrases(judge_result, limit=4)
    missed_lower = {phrase.lower() for phrase in missed}
    phrases = missed + [
        phrase
        for phrase in (_dimension_phrases(goal_case, judge_result, limit=8) or repairs)
        if str(phrase or "").strip().lower() not in missed_lower
    ]
    queries: list[dict[str, Any]] = []
    for phrase in phrases or repairs:
        patterns = (
            _pair_decomposition_templates(include_anchor=bool(anchors))
            if _is_pair_extract_phrase(phrase)
            else _dedupe_decomposition_templates(include_anchor=bool(anchors))
            if _is_dedupe_phrase(phrase)
            else [
                "{phrase} repository source",
                "{phrase} release blocker",
                "{phrase} issue discussion",
                "{anchor} {phrase} implementation proof",
            ]
        )
        for anchor in anchors or [""]:
            for pattern in patterns:
                spec = {"text": pattern.format(anchor=anchor, phrase=phrase).strip(), "platforms": []}
                if str(spec) in tried_queries or spec in queries:
                    continue
                queries.append(spec)
                if len(queries) >= max_queries:
                    return queries
    return queries


def build_research_plan(
    *,
    searcher: Any,
    bundle_state: dict[str, Any],
    judge_result: dict[str, Any],
    tried_queries: set[str],
    available_providers: list[str],
    active_program: dict[str, Any],
    round_history: list[dict[str, Any]],
    plan_count: int,
    max_queries: int,
    local_evidence_records: list[dict[str, Any]] | None = None,
    gap_queue: list[dict[str, Any]] | None = None,
    diary_summary: list[str] | None = None,
    action_policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    current_role = _current_round_role(active_program, round_history)
    retired_mutations = _retired_mutation_kinds(active_program)
    if _mutation_kind_for_role(current_role) in retired_mutations:
        current_role = "orthogonal_probe" if "orthogonal_probe" in list(active_program.get("round_roles") or []) else "broad_recall"
    local_evidence_records = list(local_evidence_records or [])
    gap_dimensions = [
        str(item.get("dimension") or "").strip()
        for item in list(gap_queue or [])
        if str(item.get("status") or "open") == "open" and str(item.get("dimension") or "").strip()
    ]
    action_policy = dict(action_policy or {})
    allowed_actions = set(action_policy.get("allowed_actions") or ["search", "repair", "cross_verify"])
    goal_case = _goal_case_from_searcher(searcher)
    plans = searcher.candidate_plans(
        bundle_state=bundle_state,
        judge_result=judge_result,
        tried_queries=tried_queries,
        available_providers=available_providers,
        active_program=active_program,
        round_history=round_history,
        plan_count=plan_count,
        max_queries=max_queries,
    )
    normalized: list[dict[str, Any]] = []
    previous_node = str((round_history[-1] or {}).get("graph_node") or "") if round_history else ""
    branch_depth = int((round_history[-1] or {}).get("branch_depth", 0) or 0) if round_history else 0
    recursive_depth_limit = _recursive_depth_limit(active_program)
    branch_budget = _branch_budget(active_program)
    allow_recursive_followups = bool(local_evidence_records) or bool(round_history)
    follow_up_candidates = (
        _follow_up_queries(
            goal_case=goal_case,
            local_evidence_records=local_evidence_records,
            judge_result=judge_result,
            max_queries=max_queries,
            tried_queries=tried_queries,
        )
        if allow_recursive_followups
        else []
    )
    decomposition_candidates = (
        _decomposition_followups(
            goal_case=goal_case,
            local_evidence_records=local_evidence_records,
            judge_result=judge_result,
            max_queries=max_queries,
            tried_queries=tried_queries,
        )
        if allow_recursive_followups
        else []
    )
    for index, plan in enumerate(list(plans or []), start=1):
        queries = _augment_queries(
            list(plan.get("queries") or []),
            goal_case=goal_case,
            local_evidence_records=local_evidence_records if current_role != "broad_recall" else [],
            judge_result=judge_result,
            tried_queries=tried_queries,
            max_queries=max_queries,
        )
        role = str(plan.get("role") or current_role or "broad_recall")
        branch_type = _branch_type(role)
        if _mutation_kind_for_role(role) in retired_mutations:
            continue
        graph_node = _node_id(role, index, branch_depth + 1)
        branch_targets = gap_dimensions[:3] or _repair_terms(judge_result, goal_case)
        plan_priority = int(plan.get("branch_priority", 0) or 0)
        program_overrides = dict(plan.get("program_overrides") or {})
        decision = _decision_for_plan(
            active_program=active_program,
            role=role,
            branch_type=branch_type,
            queries=queries,
            program_overrides=program_overrides,
            judge_result=judge_result,
            tried_queries=tried_queries,
            max_queries=max_queries,
        )
        planning_ops = _planning_ops_for_plan(
            role=role,
            branch_type=branch_type,
            branch_targets=branch_targets,
            branch_depth=branch_depth + 1,
            recursive_depth_limit=recursive_depth_limit,
            decision=decision,
        )
        normalized.append({
            "label": str(plan.get("label") or "plan"),
            "queries": queries,
            "intents": queries,
            "role": role,
            "branch_type": branch_type,
            "branch_subgoal": _branch_subgoal(role, judge_result, goal_case),
            "stage": "repair" if role != "broad_recall" else "breadth",
            "graph_node": graph_node,
            "graph_edges": [
                {
                    "from": previous_node,
                    "to": graph_node,
                    "kind": "branch",
                }
            ] if previous_node else [],
            "branch_targets": branch_targets,
            "program_overrides": program_overrides,
            "decision": decision.to_dict(),
            "planning_ops": planning_ops,
            "local_evidence_records": local_evidence_records,
            "diary_summary": list(diary_summary or []),
            "branch_depth": branch_depth + 1,
            "branch_priority": plan_priority or (3 if branch_type == "repair" else 2 if branch_type == "followup" else 1),
        })
    if follow_up_candidates and len(normalized) < max(plan_count, 1) and branch_depth + 1 <= recursive_depth_limit and "anchor_followup" not in retired_mutations:
        if "cross_verify" not in allowed_actions:
            follow_up_candidates = []
    if follow_up_candidates and len(normalized) < max(plan_count, 1) and branch_depth + 1 <= recursive_depth_limit and "anchor_followup" not in retired_mutations:
        graph_node = _node_id("graph_followup", len(normalized) + 1, branch_depth + 1)
        followup_overrides = _followup_program_overrides(active_program)
        followup_decision = _decision_for_plan(
            active_program=active_program,
            role="graph_followup",
            branch_type="followup",
            queries=follow_up_candidates[:max_queries],
            program_overrides=followup_overrides,
            judge_result=judge_result,
            tried_queries=tried_queries,
            max_queries=max_queries,
        )
        normalized.append({
            "label": "graph-followup",
            "queries": follow_up_candidates[:max_queries],
            "intents": follow_up_candidates[:max_queries],
            "role": "graph_followup",
            "branch_type": "followup",
            "branch_subgoal": _branch_subgoal("graph_followup", judge_result, goal_case),
            "stage": "followup",
            "graph_node": graph_node,
            "graph_edges": [{"from": previous_node, "to": graph_node, "kind": "follow_up"}] if previous_node else [],
            "branch_targets": gap_dimensions[:3] or _repair_terms(judge_result, goal_case),
            "program_overrides": followup_overrides,
            "decision": followup_decision.to_dict(),
            "planning_ops": _planning_ops_for_plan(
                role="graph_followup",
                branch_type="followup",
                branch_targets=gap_dimensions[:3] or _repair_terms(judge_result, goal_case),
                branch_depth=branch_depth + 1,
                recursive_depth_limit=recursive_depth_limit,
                decision=followup_decision,
            ),
            "local_evidence_records": local_evidence_records,
            "branch_depth": branch_depth + 1,
            "branch_priority": 4,
            "diary_summary": list(diary_summary or []),
        })
    if decomposition_candidates and len(normalized) < max(plan_count + 1, 2) and branch_depth + 2 <= recursive_depth_limit and "anchor_followup" not in retired_mutations:
        if "cross_verify" not in allowed_actions:
            decomposition_candidates = []
    if decomposition_candidates and len(normalized) < max(plan_count + 1, 2) and branch_depth + 2 <= recursive_depth_limit and "anchor_followup" not in retired_mutations:
        graph_node = _node_id("decomposition_followup", len(normalized) + 1, branch_depth + 2)
        decomposition_overrides = _followup_program_overrides(active_program)
        decomposition_decision = _decision_for_plan(
            active_program=active_program,
            role="decomposition_followup",
            branch_type="followup",
            queries=decomposition_candidates[:max_queries],
            program_overrides=decomposition_overrides,
            judge_result=judge_result,
            tried_queries=tried_queries,
            max_queries=max_queries,
        )
        normalized.append({
            "label": "graph-decomposition-followup",
            "queries": decomposition_candidates[:max_queries],
            "intents": decomposition_candidates[:max_queries],
            "role": "decomposition_followup",
            "branch_type": "followup",
            "branch_subgoal": _branch_subgoal("decomposition_followup", judge_result, goal_case),
            "stage": "followup",
            "graph_node": graph_node,
            "graph_edges": [{"from": previous_node, "to": graph_node, "kind": "recursive_follow_up"}] if previous_node else [],
            "branch_targets": gap_dimensions[:3] or _repair_terms(judge_result, goal_case),
            "program_overrides": decomposition_overrides,
            "decision": decomposition_decision.to_dict(),
            "planning_ops": _planning_ops_for_plan(
                role="decomposition_followup",
                branch_type="followup",
                branch_targets=gap_dimensions[:3] or _repair_terms(judge_result, goal_case),
                branch_depth=branch_depth + 2,
                recursive_depth_limit=recursive_depth_limit,
                decision=decomposition_decision,
            ),
            "local_evidence_records": local_evidence_records,
            "branch_depth": branch_depth + 2,
            "branch_priority": 5,
            "diary_summary": list(diary_summary or []),
        })
    ranked = sorted(
        normalized,
        key=lambda item: (
            int(item.get("branch_priority", 0) or 0),
            -int(item.get("branch_depth", 0) or 0),
        ),
        reverse=True,
    )
    counts: Counter[str] = Counter()
    filtered: list[dict[str, Any]] = []
    max_slots = max(plan_count, 1)
    if follow_up_candidates:
        max_slots += 1
    if decomposition_candidates:
        max_slots += 1
    for item in ranked:
        branch_type = str(item.get("branch_type") or "research")
        if counts[branch_type] >= int(branch_budget.get(branch_type, plan_count) or plan_count):
            continue
        filtered.append(item)
        counts[branch_type] += 1
        if len(filtered) >= max_slots:
            break
    return filtered
