"""Shared resolution for SKILL.md ``requires`` tokens."""

from __future__ import annotations

from collections.abc import Iterable

TIKHUB_API_KEY_TOKEN = "env:TIKHUB_API_KEY"
TIKHUB_PROXY_FALLBACK_ENV_KEYS = frozenset({"AUTOSEARCH_PROXY_URL", "AUTOSEARCH_PROXY_TOKEN"})


def resolve_requires(
    requires: Iterable[str],
    *,
    env_keys: Iterable[str] = (),
    cookies: Iterable[str] = (),
    mcp_servers: Iterable[str] = (),
    binaries: Iterable[str] = (),
) -> list[str]:
    """Return unmet ``requires`` tokens for the current environment."""
    available_env_keys = set(env_keys)
    available_cookies = set(cookies)
    available_mcp_servers = set(mcp_servers)
    available_binaries = set(binaries)

    unmet: list[str] = []
    for token in requires:
        kind, value = token.split(":", maxsplit=1)
        if kind == "cookie" and value not in available_cookies:
            unmet.append(token)
        elif kind == "mcp" and value not in available_mcp_servers:
            unmet.append(token)
        elif kind == "env" and value not in available_env_keys:
            if token == TIKHUB_API_KEY_TOKEN and TIKHUB_PROXY_FALLBACK_ENV_KEYS.issubset(
                available_env_keys
            ):
                continue
            unmet.append(token)
        elif kind == "binary" and value not in available_binaries:
            unmet.append(token)

    return unmet
