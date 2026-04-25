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

_FILE_INJECTED_VALUES: dict[str, str] = {}


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


def inject_into_env(path: Path | None = None, *, force: bool = False) -> set[str]:
    """Push secrets-file values into `os.environ`. Returns the keys that were
    newly written or replaced.

    This is what makes the v2 contract true end-to-end: `autosearch configure`
    writes to the secrets file, but channel methods, LLM providers, and
    external libraries (yt-dlp, firecrawl, tikhub) all read process env via
    `os.getenv()`. Without this push, doctor sees the file but the actual
    runtime call sees nothing.

    `force=False` (default): user's explicit `KEY=…` env vars override the
    file — used by every CLI / MCP entrypoint at startup.

    `force=True`: file values overwrite env values only when this module owns
    the current env value because it injected an earlier file value. Bug 2
    (fix-plan): when ChannelRuntime detects a secrets-file mtime change and
    rebuilds, it must call this with `force=True` so `autosearch configure
    --replace KEY new` is actually seen by the next `run_channel`. Explicit
    env values provided by the parent process still win.
    """
    injected: set[str] = set()
    for key, value in load_secrets(path).items():
        if not value:
            continue
        current = os.environ.get(key)
        previous_injected = _FILE_INJECTED_VALUES.get(key)
        file_owned = previous_injected is not None and current == previous_injected
        if current and previous_injected is not None and not file_owned:
            _FILE_INJECTED_VALUES.pop(key, None)

        if current and (not force or not file_owned):
            continue
        if current == value:
            continue
        os.environ[key] = value
        _FILE_INJECTED_VALUES[key] = value
        injected.add(key)
    return injected
