"""Formal search mesh package for provider policy and routing."""

from .provider_policy import (
    FREE_BREADTH_PROVIDERS,
    PREMIUM_BREADTH_PROVIDERS,
    available_platforms,
    default_platform_config,
    goal_provider_names,
)
from .registry import get_provider, providers_for_role, register_provider, registered_provider_names
from .router import search_platform
from .models import SearchHit, SearchHitBatch

__all__ = [
    "FREE_BREADTH_PROVIDERS",
    "PREMIUM_BREADTH_PROVIDERS",
    "SearchHit",
    "SearchHitBatch",
    "available_platforms",
    "default_platform_config",
    "get_provider",
    "goal_provider_names",
    "providers_for_role",
    "register_provider",
    "registered_provider_names",
    "search_platform",
]
