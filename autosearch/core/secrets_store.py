"""Secrets file loader for ~/.config/ai-secrets.env.

`autosearch configure` and `autosearch login` write KEY=value pairs to this file
so they survive across shells and GUI-launched MCP clients (which do not inherit
the developer's interactive shell environment). The runtime — doctor, channel
probes, MCP server startup — must read the same file, otherwise users configure
keys that no code path actually picks up.

Lookup order:

1. process environment (`os.environ`) — explicit override wins
2. `~/.config/ai-secrets.env` (or `$AUTOSEARCH_SECRETS_FILE` if set)

Values are never printed or logged. Only key presence is exposed via
`available_env_keys()`.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path


def secrets_path() -> Path:
    """Return the configured secrets-file path (env override or default)."""
    override = os.environ.get("AUTOSEARCH_SECRETS_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "ai-secrets.env"


def load_secrets(path: Path | None = None) -> dict[str, str]:
    """Parse the secrets file into a dict. Returns {} if missing or unreadable.

    Format mirrors what `autosearch configure` writes (shell-sourceable):
      KEY=value
      KEY='quoted value'
      # comments and blank lines are ignored
    """
    target = path or secrets_path()
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        try:
            tokens = shlex.split(value)
        except ValueError:
            continue
        result[key] = tokens[0] if tokens else ""
    return result


def available_env_keys(path: Path | None = None) -> set[str]:
    """Return the set of keys with non-empty values in env OR the secrets file."""
    keys = {key for key, val in os.environ.items() if val}
    keys.update(k for k, v in load_secrets(path).items() if v)
    return keys


def resolve_env_value(key: str, path: Path | None = None) -> str | None:
    """Return the value for `key`: process env first, then secrets file."""
    env_value = os.environ.get(key)
    if env_value:
        return env_value
    return load_secrets(path).get(key) or None
