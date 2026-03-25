"""Provider policy and free-first routing rules."""

from __future__ import annotations

from typing import Any

from source_capability import get_source_decision

FREE_BREADTH_PROVIDERS = ["searxng", "ddgs"]
PREMIUM_BREADTH_PROVIDERS = {"exa", "tavily"}


def default_platform_config(name: str) -> dict[str, Any]:
    if name == "github_repos":
        return {"name": name, "limit": 5, "min_stars": 20}
    if name == "github_issues":
        return {"name": name, "limit": 5}
    if name == "github_code":
        return {"name": name, "limit": 5}
    if name == "twitter_xreach":
        return {"name": name, "limit": 10}
    if name in {"searxng", "ddgs", "exa", "tavily"}:
        return {"name": name, "limit": 8}
    return {"name": name, "limit": 5}


def goal_provider_names(goal_case: dict[str, Any]) -> list[str]:
    requested = [
        str(name or "").strip()
        for name in list(goal_case.get("providers") or [])
        if str(name or "").strip()
    ]
    names: list[str] = []
    if not requested:
        names.extend(FREE_BREADTH_PROVIDERS)
    elif any(name in PREMIUM_BREADTH_PROVIDERS for name in requested):
        names.extend(FREE_BREADTH_PROVIDERS)
    names.extend(requested)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def available_platforms(goal_case: dict[str, Any], capability_report: dict[str, Any]) -> list[dict[str, Any]]:
    platforms: list[dict[str, Any]] = []
    for name in goal_provider_names(goal_case):
        decision = get_source_decision(capability_report, name)
        if decision["should_skip"]:
            continue
        platforms.append(default_platform_config(name))
    return platforms
