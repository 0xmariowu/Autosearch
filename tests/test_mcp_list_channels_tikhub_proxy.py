from __future__ import annotations

from pathlib import Path

import pytest


def _isolate_tikhub_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)
    monkeypatch.delenv("AUTOSEARCH_PROXY_URL", raising=False)
    monkeypatch.delenv("AUTOSEARCH_PROXY_TOKEN", raising=False)


def _list_channels_zhihu() -> dict:
    from autosearch.mcp.server import create_server

    server = create_server()
    data = server._tool_manager._tools["list_channels"].fn()
    channels = {channel["name"]: channel for channel in data["channels"]}
    return channels["zhihu"]


def test_mcp_list_channels_tikhub_proxy_marks_zhihu_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://x")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "y")

    channel = _list_channels_zhihu()

    assert channel["status"] == "ok"
    assert channel["unmet_requires"] == []
    assert "TIKHUB_API_KEY" not in channel["fix_hint"]


def test_mcp_list_channels_tikhub_api_key_marks_zhihu_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TIKHUB_API_KEY", "tk-test")

    channel = _list_channels_zhihu()

    assert channel["status"] == "ok"
    assert channel["unmet_requires"] == []


def test_mcp_list_channels_zhihu_off_without_tikhub_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)

    channel = _list_channels_zhihu()

    assert channel["status"] == "off"
    assert channel["unmet_requires"] == ["env:TIKHUB_API_KEY"]
    assert channel["fix_hint"] == "autosearch configure TIKHUB_API_KEY <your-key>"
