"""Registry for provider-backed search backends."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from search_mesh.backends.base import SearchProvider


_PROVIDERS: dict[str, "SearchProvider"] = {}


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
