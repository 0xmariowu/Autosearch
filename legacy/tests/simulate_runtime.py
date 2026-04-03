import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import project_experience as pe


PLATFORMS = [
    {"name": "github_repos"},
    {"name": "github_issues"},
    {"name": "twitter_xreach"},
    {"name": "exa"},
    {"name": "reddit_exa"},
    {"name": "hn_exa"},
]


def _event(
    *,
    run_id: str,
    provider: str,
    query_family: str,
    attempts: int,
    results: int,
    new_urls: int,
    errors: int,
) -> dict:
    return pe.build_search_experience_event(
        run_id=run_id,
        provider=provider,
        query_family=query_family,
        attempts=attempts,
        results=results,
        new_urls=new_urls,
        errors=errors,
        timestamp=f"{run_id}T06:00:00+08:00".replace("daily-", ""),
    )


def _ordered_providers(policy: dict, query_family: str) -> list[dict]:
    decisions = []
    for platform in PLATFORMS:
        provider = platform["name"]
        decision = pe.get_provider_decision(policy, provider, query_family)
        decisions.append(
            {
                "provider": provider,
                "status": decision["status"],
                "should_skip": decision["should_skip"],
                "priority": decision["priority"],
                "reason": decision["reason"],
            }
        )
    return sorted(decisions, key=lambda item: (item["priority"], item["provider"]))


def simulate_preferred_and_cooldown() -> dict:
    events = []
    for idx in range(8):
        run_id = f"2026-03-24-daily-a{idx}"
        events.extend(
            [
                _event(
                    run_id=run_id,
                    provider="exa",
                    query_family="coding-agent",
                    attempts=1,
                    results=6,
                    new_urls=2,
                    errors=0,
                ),
                _event(
                    run_id=run_id,
                    provider="github_repos",
                    query_family="coding-agent",
                    attempts=1,
                    results=4,
                    new_urls=1,
                    errors=0,
                ),
                _event(
                    run_id=run_id,
                    provider="xreach_auth_error",
                    query_family="coding-agent",
                    attempts=1,
                    results=0,
                    new_urls=0,
                    errors=1,
                ),
                _event(
                    run_id=run_id,
                    provider="reddit_exa",
                    query_family="coding-agent",
                    attempts=1,
                    results=3,
                    new_urls=0,
                    errors=0,
                ),
            ]
        )

    index = pe.build_project_experience_index(events)
    policy = pe.build_project_experience_policy(index)
    return {
        "name": "preferred-vs-cooldown",
        "policy": policy,
        "ordered_providers": _ordered_providers(policy, "coding-agent"),
    }


def simulate_small_sample_stays_active() -> dict:
    events = []
    for idx in range(4):
        run_id = f"2026-03-24-daily-b{idx}"
        events.extend(
            [
                _event(
                    run_id=run_id,
                    provider="exa",
                    query_family="browser-automation",
                    attempts=1,
                    results=5,
                    new_urls=2,
                    errors=0,
                ),
                _event(
                    run_id=run_id,
                    provider="hn_exa",
                    query_family="browser-automation",
                    attempts=1,
                    results=2,
                    new_urls=1,
                    errors=0,
                ),
            ]
        )

    index = pe.build_project_experience_index(events)
    policy = pe.build_project_experience_policy(index)
    return {
        "name": "small-sample-stays-active",
        "policy": policy,
        "ordered_providers": _ordered_providers(policy, "browser-automation"),
    }


def simulate_github_auth_outage() -> dict:
    events = []
    for idx in range(8):
        run_id = f"2026-03-24-daily-c{idx}"
        events.extend(
            [
                _event(
                    run_id=run_id,
                    provider="gh_auth_error",
                    query_family="mcp",
                    attempts=1,
                    results=0,
                    new_urls=0,
                    errors=1,
                ),
                _event(
                    run_id=run_id,
                    provider="exa",
                    query_family="mcp",
                    attempts=1,
                    results=5,
                    new_urls=1,
                    errors=0,
                ),
            ]
        )

    index = pe.build_project_experience_index(events)
    policy = pe.build_project_experience_policy(index)
    return {
        "name": "github-auth-outage",
        "policy": policy,
        "ordered_providers": _ordered_providers(policy, "mcp"),
    }


def summarize_case(case: dict) -> dict:
    search_policy = case["policy"]["aspects"]["search"]
    providers = search_policy["providers"]
    families = search_policy["query_families"]
    family_name = next(iter(families.keys()))

    provider_summary = {
        provider: {
            "status": record["status"],
            "attempts": record["attempts"],
            "new_url_rate": record["new_url_rate"],
            "error_rate": record["error_rate"],
        }
        for provider, record in providers.items()
        if provider in pe.CANONICAL_PROVIDERS
    }

    return {
        "case": case["name"],
        "query_family": family_name,
        "family_policy": families[family_name],
        "providers": provider_summary,
        "runtime_order": case["ordered_providers"],
    }


def main() -> None:
    cases = [
        simulate_preferred_and_cooldown(),
        simulate_small_sample_stays_active(),
        simulate_github_auth_outage(),
    ]
    summary = [summarize_case(case) for case in cases]
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
