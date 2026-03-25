"""Formal search mesh package for provider policy and routing."""

from .provider_policy import (
    FREE_BREADTH_PROVIDERS,
    PREMIUM_BREADTH_PROVIDERS,
    available_platforms,
    default_platform_config,
    goal_provider_names,
)
from .router import search_platform

__all__ = [
    "FREE_BREADTH_PROVIDERS",
    "PREMIUM_BREADTH_PROVIDERS",
    "available_platforms",
    "default_platform_config",
    "goal_provider_names",
    "search_platform",
]
