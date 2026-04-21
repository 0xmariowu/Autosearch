from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence


class SecretsError(ValueError):
    """Raised when the secrets env file cannot be parsed."""


def load_secrets(path: Path) -> dict[str, str]:
    """Load a simple KEY=VALUE env file without shell-style parsing."""
    if not path.exists():
        raise SecretsError(f"Secrets file not found: {path}")

    secrets: dict[str, str] = {}
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in raw_line:
            raise SecretsError(f"Invalid secrets line {line_no}: expected KEY=VALUE")

        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key:
            raise SecretsError(f"Invalid secrets line {line_no}: missing key")
        secrets[key] = value

    return secrets


def build_task_env(
    secrets: Mapping[str, str],
    env_keys: Sequence[str],
    unset_env: Sequence[str],
) -> tuple[dict[str, str], list[str], list[str], dict[str, str]]:
    """Build task envs from file-backed secrets with a host-env fallback."""
    env: dict[str, str] = {}
    resolved_keys: list[str] = []
    missing_keys: list[str] = []
    resolved_sources: dict[str, str] = {}

    for key in env_keys:
        source = "file"
        value = secrets.get(key)
        # Treat empty-string values as absent so the host-env fallback fires.
        # File entries like `export FOO=` produce empty strings, not None.
        if not value:
            source = "host_env"
            value = os.environ.get(key)
        if not value:
            missing_keys.append(key)
            continue
        env[key] = value
        resolved_keys.append(key)
        resolved_sources[key] = source

    for key in unset_env:
        env.pop(key, None)
        if key in resolved_keys:
            resolved_keys.remove(key)
        resolved_sources.pop(key, None)

    return env, resolved_keys, missing_keys, resolved_sources
