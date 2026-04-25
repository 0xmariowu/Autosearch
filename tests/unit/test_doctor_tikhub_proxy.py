from __future__ import annotations

from pathlib import Path

import pytest

from autosearch.core.doctor import ChannelStatus, scan_channels


def _isolate_tikhub_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)
    monkeypatch.delenv("AUTOSEARCH_PROXY_URL", raising=False)
    monkeypatch.delenv("AUTOSEARCH_PROXY_TOKEN", raising=False)


def _zhihu_status() -> ChannelStatus:
    statuses = {status.channel: status for status in scan_channels()}
    return statuses["zhihu"]


def test_doctor_tikhub_proxy_satisfies_zhihu_requires(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://x")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "y")

    status = _zhihu_status()

    assert status.status == "ok"
    assert status.unmet_requires == []
    assert "TIKHUB_API_KEY" not in status.fix_hint


def test_doctor_tikhub_api_key_still_satisfies_zhihu_requires(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TIKHUB_API_KEY", "tk-test")

    status = _zhihu_status()

    assert status.status == "ok"
    assert status.unmet_requires == []


def test_doctor_zhihu_not_configured_without_tikhub_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_tikhub_env(monkeypatch, tmp_path)

    status = _zhihu_status()

    assert status.status == "off"
    assert status.unmet_requires == ["env:TIKHUB_API_KEY"]
    assert status.fix_hint == "autosearch configure TIKHUB_API_KEY <your-key>"
