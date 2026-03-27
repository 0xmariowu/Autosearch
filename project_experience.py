"""
Lightweight project experience for AutoSearch search runtime.

This module keeps the runtime guidance layer intentionally separate from:

- raw execution history (`patterns.jsonl`, `evolution.jsonl`, `outcomes.jsonl`)
- per-run artifacts
- downstream routing or admission logic
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EXPERIENCE_ROOT = REPO_ROOT / "experience"
EXPERIENCE_LIBRARY_ROOT = EXPERIENCE_ROOT / "library"
EXPERIENCE_INDEX_ROOT = EXPERIENCE_ROOT / "INDEX.jsonl"
EXPERIENCE_LEDGER_PATH = EXPERIENCE_LIBRARY_ROOT / "experience-ledger.jsonl"
EXPERIENCE_INDEX_PATH = EXPERIENCE_LIBRARY_ROOT / "experience-index.json"
EXPERIENCE_POLICY_PATH = EXPERIENCE_LIBRARY_ROOT / "experience-policy.json"
EXPERIENCE_HEALTH_PATH = EXPERIENCE_ROOT / "latest-health.json"

SEARCH_ASPECT = "search"

RECENT_RUN_WINDOW = 12
PREFERRED_MIN_ATTEMPTS = 8
COOLDOWN_MIN_ATTEMPTS = 8
HIGH_VALUE_NEW_URL_RATE = 0.08
COOLDOWN_ERROR_RATE = 0.70

CANONICAL_PROVIDERS = [
    "github_repos",
    "github_issues",
    "twitter_xreach",
    "exa",
    "reddit_exa",
    "hn_exa",
]

ERROR_ALIAS_TO_PROVIDER = {
    "github_repo_error": ["github_repos", "github_issues"],
    "gh_auth_error": ["github_repos", "github_issues"],
    "xreach_auth_error": ["twitter_xreach"],
    "exa_unavailable": ["exa"],
    "reddit_exa_error": ["reddit_exa"],
    "hn_exa_error": ["hn_exa"],
}


def _default_policy() -> dict[str, Any]:
    return {"aspects": {SEARCH_ASPECT: {"providers": {}, "query_families": {}}}}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default or {})
    return payload if isinstance(payload, dict) else dict(default or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ensure_experience_files() -> None:
    EXPERIENCE_ROOT.mkdir(parents=True, exist_ok=True)
    EXPERIENCE_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    if not EXPERIENCE_LEDGER_PATH.exists():
        EXPERIENCE_LEDGER_PATH.write_text("", encoding="utf-8")
    if not EXPERIENCE_INDEX_PATH.exists():
        write_json(
            EXPERIENCE_INDEX_PATH,
            {"generated_at": None, "recent_run_ids": [], "aspects": {}},
        )
    if not EXPERIENCE_POLICY_PATH.exists():
        write_json(EXPERIENCE_POLICY_PATH, _default_policy())
    if not EXPERIENCE_HEALTH_PATH.exists():
        write_json(
            EXPERIENCE_HEALTH_PATH,
            {
                "generated_at": None,
                "aspects": {
                    SEARCH_ASPECT: {
                        "by_provider": {},
                        "by_query_family": {},
                        "cooldown_providers": [],
                        "top_providers": [],
                    }
                },
            },
        )


def normalize_provider(provider: str) -> str:
    return (provider or "").strip()


def is_error_provider(provider: str) -> bool:
    provider = normalize_provider(provider)
    return provider in ERROR_ALIAS_TO_PROVIDER


def canonical_provider_for(provider: str) -> str:
    provider = normalize_provider(provider)
    targets = ERROR_ALIAS_TO_PROVIDER.get(provider)
    if targets:
        return targets[0]
    return provider


def canonical_providers_for(provider: str) -> list[str]:
    provider = normalize_provider(provider)
    targets = ERROR_ALIAS_TO_PROVIDER.get(provider)
    if targets:
        return list(targets)
    return [provider]


def build_search_experience_event(
    *,
    run_id: str,
    provider: str,
    query_family: str,
    attempts: int,
    results: int,
    new_urls: int,
    errors: int,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "aspect": SEARCH_ASPECT,
        "run_id": run_id,
        "timestamp": timestamp or datetime.now().astimezone().isoformat(),
        "provider": normalize_provider(provider),
        "query_family": query_family or "unknown",
        "attempts": int(attempts or 0),
        "results": int(results or 0),
        "new_urls": int(new_urls or 0),
        "errors": int(errors or 0),
    }


def _empty_stats() -> dict[str, int]:
    return {"attempts": 0, "results": 0, "new_urls": 0, "errors": 0}


def _merge_stats(target: dict[str, int], source: dict[str, Any]) -> None:
    for key in _empty_stats().keys():
        target[key] = int(target.get(key, 0)) + int(source.get(key, 0) or 0)


def _recent_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    run_ids: list[str] = []
    seen: set[str] = set()
    for event in events:
        run_id = str(event.get("run_id") or "")
        if run_id and run_id not in seen:
            run_ids.append(run_id)
            seen.add(run_id)
    recent_run_ids = run_ids[-RECENT_RUN_WINDOW:]
    if not recent_run_ids:
        return [], []
    allowed = set(recent_run_ids)
    recent_events = [
        event for event in events if str(event.get("run_id") or "") in allowed
    ]
    return recent_events, recent_run_ids


def _finalize_provider_record(provider: str, stats: dict[str, int]) -> dict[str, Any]:
    attempts = int(stats.get("attempts") or 0)
    results = int(stats.get("results") or 0)
    new_urls = int(stats.get("new_urls") or 0)
    errors = int(stats.get("errors") or 0)
    new_url_rate = round(new_urls / max(attempts, 1), 4)
    error_rate = round(errors / max(attempts, 1), 4)

    if (
        attempts >= COOLDOWN_MIN_ATTEMPTS
        and error_rate >= COOLDOWN_ERROR_RATE
        and new_urls == 0
    ):
        status = "cooldown"
        reason = "high recent error rate with no new urls"
    elif (
        not is_error_provider(provider)
        and attempts >= PREFERRED_MIN_ATTEMPTS
        and errors == 0
        and new_url_rate >= HIGH_VALUE_NEW_URL_RATE
        and new_urls > 0
    ):
        status = "preferred"
        reason = "enough recent attempts with strong new-url rate"
    else:
        status = "active"
        if attempts < min(PREFERRED_MIN_ATTEMPTS, COOLDOWN_MIN_ATTEMPTS):
            reason = "insufficient recent samples for promotion or cooldown"
        elif errors > 0 and new_urls > 0:
            reason = "mixed recent signal with both errors and useful output"
        elif new_urls == 0 and errors == 0:
            reason = "enough recent attempts but no strong positive signal"
        else:
            reason = "enough recent attempts but append/new-url rate below preferred threshold"

    return {
        "attempts": attempts,
        "results": results,
        "new_urls": new_urls,
        "errors": errors,
        "new_url_rate": new_url_rate,
        "error_rate": error_rate,
        "status": status,
        "reason": reason,
    }


def build_project_experience_index(events: list[dict[str, Any]]) -> dict[str, Any]:
    search_events = [event for event in events if event.get("aspect") == SEARCH_ASPECT]
    recent_events, recent_run_ids = _recent_events(search_events)

    raw_provider_stats: dict[str, dict[str, int]] = defaultdict(_empty_stats)
    canonical_provider_stats: dict[str, dict[str, int]] = defaultdict(_empty_stats)
    query_family_stats: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_stats)
    )

    for event in recent_events:
        provider = normalize_provider(str(event.get("provider") or "unknown"))
        query_family = str(event.get("query_family") or "unknown")
        _merge_stats(raw_provider_stats[provider], event)

        for canonical_provider in canonical_providers_for(provider):
            if canonical_provider in CANONICAL_PROVIDERS:
                _merge_stats(canonical_provider_stats[canonical_provider], event)
                _merge_stats(
                    query_family_stats[query_family][canonical_provider], event
                )

    providers = {
        provider: _finalize_provider_record(provider, stats)
        for provider, stats in sorted(raw_provider_stats.items())
    }
    canonical_providers = {
        provider: _finalize_provider_record(provider, stats)
        for provider, stats in sorted(canonical_provider_stats.items())
    }
    query_families = {
        family: {
            provider: _finalize_provider_record(provider, stats)
            for provider, stats in sorted(provider_stats.items())
        }
        for family, provider_stats in sorted(query_family_stats.items())
    }

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "recent_run_ids": recent_run_ids,
        "aspects": {
            SEARCH_ASPECT: {
                "providers": providers,
                "canonical_providers": canonical_providers,
                "query_families": query_families,
            }
        },
    }


def build_project_experience_policy(index: dict[str, Any]) -> dict[str, Any]:
    search_index = ((index or {}).get("aspects") or {}).get(SEARCH_ASPECT) or {}
    canonical_providers = search_index.get("canonical_providers") or {}
    raw_providers = search_index.get("providers") or {}
    query_family_stats = search_index.get("query_families") or {}

    provider_policy = {
        provider: dict(record)
        for provider, record in sorted(canonical_providers.items())
    }
    for provider, record in sorted(raw_providers.items()):
        if provider not in provider_policy:
            provider_policy[provider] = dict(record)

    query_family_policy: dict[str, dict[str, list[str]]] = {}
    for family, providers in sorted(query_family_stats.items()):
        preferred = [
            provider
            for provider, record in sorted(
                providers.items(),
                key=lambda item: (
                    0 if item[1].get("status") == "preferred" else 1,
                    -(item[1].get("new_url_rate") or 0.0),
                    -(item[1].get("attempts") or 0),
                    item[0],
                ),
            )
            if provider in CANONICAL_PROVIDERS and record.get("status") == "preferred"
        ]
        cooldown = [
            provider
            for provider, record in sorted(providers.items())
            if provider in CANONICAL_PROVIDERS and record.get("status") == "cooldown"
        ]
        query_family_policy[family] = {
            "preferred_providers": preferred,
            "cooldown_providers": cooldown,
        }

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "aspects": {
            SEARCH_ASPECT: {
                "providers": provider_policy,
                "query_families": query_family_policy,
            }
        },
    }


def summarize_search_experience_for_health(
    *,
    index: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    search_index = ((index or {}).get("aspects") or {}).get(SEARCH_ASPECT) or {}
    search_policy = ((policy or {}).get("aspects") or {}).get(SEARCH_ASPECT) or {}
    providers = search_policy.get("providers") or {}
    query_families = search_policy.get("query_families") or {}

    canonical_provider_rows = {
        provider: record
        for provider, record in providers.items()
        if provider in CANONICAL_PROVIDERS
    }
    cooldown_providers = sorted(
        [
            provider
            for provider, record in canonical_provider_rows.items()
            if record.get("status") == "cooldown"
        ]
    )
    top_providers = [
        provider
        for provider, _ in sorted(
            canonical_provider_rows.items(),
            key=lambda item: (
                0 if item[1].get("status") == "preferred" else 1,
                -(item[1].get("new_url_rate") or 0.0),
                -(item[1].get("attempts") or 0),
                item[0],
            ),
        )[:5]
    ]

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "recent_run_ids": index.get("recent_run_ids") or [],
        "aspects": {
            SEARCH_ASPECT: {
                "by_provider": providers,
                "by_query_family": query_families,
                "cooldown_providers": cooldown_providers,
                "top_providers": top_providers,
                "provider_index": search_index.get("canonical_providers") or {},
            }
        },
    }


def refresh_project_experience(
    new_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ensure_experience_files()
    if new_events:
        append_jsonl(EXPERIENCE_LEDGER_PATH, new_events)
    all_events = load_jsonl(EXPERIENCE_LEDGER_PATH)
    index = build_project_experience_index(all_events)
    policy = build_project_experience_policy(index)
    health = summarize_search_experience_for_health(index=index, policy=policy)
    write_json(EXPERIENCE_INDEX_PATH, index)
    write_json(EXPERIENCE_POLICY_PATH, policy)
    write_json(EXPERIENCE_HEALTH_PATH, health)
    return {"index": index, "policy": policy, "health": health}


def load_project_experience_policy() -> dict[str, Any]:
    ensure_experience_files()
    return load_json(EXPERIENCE_POLICY_PATH, _default_policy())


def get_provider_decision(
    policy: dict[str, Any],
    provider: str,
    query_family: str | None = None,
) -> dict[str, Any]:
    provider = normalize_provider(provider)
    query_family = query_family or "unknown"
    search_policy = ((policy or {}).get("aspects") or {}).get(SEARCH_ASPECT) or {}
    provider_policy = (search_policy.get("providers") or {}).get(provider) or {
        "status": "active",
        "reason": "no experience yet",
        "attempts": 0,
        "new_url_rate": 0.0,
        "error_rate": 0.0,
    }
    family_policy = (search_policy.get("query_families") or {}).get(query_family) or {
        "preferred_providers": [],
        "cooldown_providers": [],
    }

    family_preferred = provider in family_policy.get("preferred_providers", [])
    family_cooldown = provider in family_policy.get("cooldown_providers", [])
    provider_status = str(provider_policy.get("status") or "active")

    if family_cooldown or provider_status == "cooldown":
        status = "cooldown"
        priority = 99
        reason = (
            "query-family cooldown"
            if family_cooldown
            else str(provider_policy.get("reason") or "")
        )
    elif family_preferred or provider_status == "preferred":
        status = "preferred"
        priority = 0 if family_preferred else 1
        reason = (
            "query-family preferred provider"
            if family_preferred
            else str(provider_policy.get("reason") or "")
        )
    else:
        status = "active"
        priority = 10
        reason = str(provider_policy.get("reason") or "no strong recent signal")

    return {
        "provider": provider,
        "query_family": query_family,
        "status": status,
        "should_skip": status == "cooldown",
        "priority": priority,
        "reason": reason,
        "provider_status": provider_status,
        "family_preferred": family_preferred,
        "family_cooldown": family_cooldown,
        "provider_record": provider_policy,
    }
