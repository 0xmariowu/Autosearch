from __future__ import annotations

import pytest
from typer.testing import CliRunner

from autosearch.cli.main import app
from autosearch.skills.channels.xiaohongshu.methods import via_signsrv

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_secrets_file(tmp_path, monkeypatch):
    """Point AUTOSEARCH_SECRETS_FILE at a fresh, empty file so the CLI's
    inject_into_env() does not bleed the developer's real ~/.config/ai-secrets.env
    cookies into the test process — that would mask the missing-cookies branch."""
    secrets_file = tmp_path / "ai-secrets.env"
    secrets_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))
    monkeypatch.delenv("XHS_COOKIES", raising=False)
    monkeypatch.delenv("XIAOHONGSHU_COOKIES", raising=False)
    monkeypatch.delenv("XHS_A1_COOKIE", raising=False)


@pytest.fixture
def patch_health(monkeypatch: pytest.MonkeyPatch):
    def _install(result: tuple[bool, str | None]) -> None:
        async def _fake_check(client: object, headers: object) -> tuple[bool, str | None]:
            return result

        monkeypatch.setattr(via_signsrv, "_check_account_health", _fake_check)

    return _install


def test_check_health_reports_healthy_on_ok(monkeypatch: pytest.MonkeyPatch, patch_health) -> None:
    monkeypatch.setenv("XHS_COOKIES", "a1=test-cookie")
    patch_health((True, None))

    result = runner.invoke(app, ["login", "xhs", "--check-health"])

    assert result.exit_code == 0
    assert "OK:" in result.output
    assert "healthy" in result.output


def test_check_health_reports_flagged_on_300011(
    monkeypatch: pytest.MonkeyPatch, patch_health
) -> None:
    monkeypatch.setenv("XHS_COOKIES", "a1=test-cookie")
    patch_health((False, "300011"))

    result = runner.invoke(app, ["login", "xhs", "--check-health"])

    assert result.exit_code == 1
    assert "FLAGGED:" in result.output
    assert "300011" in result.output


def test_check_health_exits_when_cookies_missing() -> None:
    result = runner.invoke(app, ["login", "xhs", "--check-health"])

    assert result.exit_code == 1
    assert "No XHS_COOKIES" in result.output


def test_check_health_rejects_non_xhs_platform() -> None:
    result = runner.invoke(app, ["login", "twitter", "--check-health"])

    assert result.exit_code == 2
    assert "only supported for xhs" in result.output
