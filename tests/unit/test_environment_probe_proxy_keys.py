from __future__ import annotations

from pathlib import Path

import pytest

from autosearch.channels.base import ChannelRegistry
from autosearch.core.environment_probe import probe_environment


def _isolate_secrets_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))


def test_probe_environment_detects_proxy_env_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_secrets_file(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://x")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "y")
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    env = probe_environment(cookies_dir=tmp_path / "cookies")

    assert "AUTOSEARCH_PROXY_URL" in env.env_keys
    assert "AUTOSEARCH_PROXY_TOKEN" in env.env_keys


def test_probe_environment_proxy_keys_satisfy_tikhub_requires(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_secrets_file(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://x")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "y")
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    env = probe_environment(cookies_dir=tmp_path / "cookies")

    unmet = ChannelRegistry._resolve_requires(["env:TIKHUB_API_KEY"], env)

    assert unmet == []
