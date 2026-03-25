"""Registry for provider-backed search backends."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from search_mesh.backends.base import SearchProvider


_PROVIDERS: dict[str, "SearchProvider"] = {}

_CLASSIFICATION_HINTS: dict[str, tuple[str, ...]] = {
    "code": ("repo", "repository", "sdk", "library", "tool", "package", "source", "implementation", "code", "patch", "diff"),
    "discussion": ("issue", "bug", "failure", "incident", "discussion", "postmortem", "reddit", "hacker news", "hn"),
    "dataset": ("dataset", "benchmark", "eval set", "corpus", "trajectory"),
    "social": ("tweet", "twitter", "xreach", "social", "thread"),
    "academic": ("paper", "arxiv", "academic", "citation", "study"),
}


def _ensure_default_registry() -> None:
    if _PROVIDERS:
        return
    from search_mesh.backends import register_builtin_providers

    register_builtin_providers()


def register_provider(provider: "SearchProvider") -> None:
    for name in tuple(getattr(provider, "provider_names", ())):
        clean = str(name or "").strip()
        if clean:
            _PROVIDERS[clean] = provider


def get_provider(name: str) -> "SearchProvider | None":
    _ensure_default_registry()
    return _PROVIDERS.get(str(name or "").strip())


def registered_provider_names() -> list[str]:
    _ensure_default_registry()
    return sorted(_PROVIDERS)


def clear_registry() -> None:
    _PROVIDERS.clear()


def providers_for_role(role: str) -> list["SearchProvider"]:
    _ensure_default_registry()
    desired = str(role or "").strip()
    if not desired:
        return []
    unique: list["SearchProvider"] = []
    seen: set[int] = set()
    for provider in _PROVIDERS.values():
        if desired not in set(getattr(provider, "roles", set())):
            continue
        marker = id(provider)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(provider)
    return unique


def classify_query(text: str, *, plan_role: str = "") -> str:
    lowered = str(text or "").strip().lower()
    role = str(plan_role or "").strip().lower()
    if role in {"graph_followup", "decomposition_followup"}:
        return "verification"
    if role in {"broad_recall", "breadth"}:
        return "breadth"
    for classification, hints in _CLASSIFICATION_HINTS.items():
        if any(hint in lowered for hint in hints):
            return classification
    tokens = set(re.findall(r"[a-z0-9_\-]{4,}", lowered))
    if tokens & {"repo", "code", "patch", "diff"}:
        return "code"
    if tokens & {"issue", "incident", "discussion"}:
        return "discussion"
    return "web"


def provider_names_for_classification(classification: str) -> list[str]:
    _ensure_default_registry()
    desired = str(classification or "").strip().lower()
    matched: list[str] = []
    for name, provider in _PROVIDERS.items():
        family = str(provider.family_for(name) or "").strip().lower()
        roles = {str(item or "").strip().lower() for item in set(getattr(provider, "roles", set()))}
        if desired == "breadth":
            if "breadth" in roles:
                matched.append(name)
            continue
        if desired == "verification":
            if "verification" in roles:
                matched.append(name)
            continue
        if desired == "code" and (family in {"code_host", "source_code"} or "code" in roles):
            matched.append(name)
            continue
        if desired == "discussion" and (family == "discussion" or "discussion" in roles):
            matched.append(name)
            continue
        if desired == "dataset" and (family == "dataset" or "datasets" in roles):
            matched.append(name)
            continue
        if desired == "social" and family == "social":
            matched.append(name)
            continue
        if desired == "academic" and ("academic" in roles or family == "web_search"):
            matched.append(name)
            continue
        if desired == "web" and family == "web_search":
            matched.append(name)
    return matched
