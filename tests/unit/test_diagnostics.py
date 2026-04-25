"""Tests for autosearch.cli.diagnostics — the redact-by-default support bundle."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from autosearch.cli import main as cli_main
from autosearch.cli.diagnostics import build_bundle, redact, render_bundle

runner = CliRunner()


# ── Redaction ────────────────────────────────────────────────────────────────


def test_redact_strips_anthropic_key() -> None:
    body = "ANTHROPIC_API_KEY=sk-ant-abcdef0123456789ABCDEFGHIJKL"
    out = redact(body)
    assert "sk-ant-" not in out
    assert "ANTHROPIC_API_KEY" in out  # key name preserved
    assert "REDACTED" in out


def test_redact_strips_openrouter_key() -> None:
    out = redact("OPENROUTER_API_KEY=sk-or-v1-abcdef0123456789ABCDEFG")
    assert "sk-or-" not in out


def test_redact_strips_github_pat() -> None:
    out = redact("token = github_pat_11ABCDEFGH0123456789abcdefgh")
    assert "github_pat_" not in out


def test_redact_strips_bearer_header() -> None:
    out = redact('"Authorization": "Bearer abcdef.ghi.jklmno"')
    assert "Bearer abcdef" not in out
    assert "REDACTED" in out


def test_redact_strips_cookie_header() -> None:
    out = redact("Cookie: SESSDATA=xxx; bili_jct=yyy")
    assert "SESSDATA" in out
    assert "bili_jct" in out
    assert "xxx" not in out
    assert "yyy" not in out
    assert "REDACTED" in out


def test_redact_preserves_safe_text() -> None:
    out = redact("Python 3.12.13 on Darwin / 39 channels available")
    assert out == "Python 3.12.13 on Darwin / 39 channels available"


# ── Bundle shape ─────────────────────────────────────────────────────────────


def test_build_bundle_returns_required_top_level_fields() -> None:
    bundle = build_bundle()
    assert bundle.autosearch_version
    assert bundle.python_version
    assert bundle.python_executable
    assert bundle.platform_string
    assert bundle.install_method in {"pipx", "venv", "uv", "system"}
    assert isinstance(bundle.mcp_config_paths, dict)
    assert set(bundle.mcp_config_paths) >= {"claude", "cursor", "zed"}


def test_render_bundle_with_redact_strips_any_planted_secret(monkeypatch) -> None:
    """End-to-end: even if a key value somehow makes it into the bundle (e.g.
    via an env-name containing the value), redacted render must scrub it."""
    monkeypatch.setenv("FAKE_API_KEY", "sk-ant-fake-secret-value-do-not-leak-12345")
    bundle = build_bundle()
    text = render_bundle(bundle, redact_output=True)
    assert "sk-ant-fake-secret" not in text


def test_secrets_file_status_lists_key_names_only(tmp_path, monkeypatch) -> None:
    """When the secrets file is present, the bundle exposes key NAMES (so
    support knows what's configured) but never values."""
    secrets_file = tmp_path / "ai-secrets.env"
    secrets_file.write_text("OPENAI_API_KEY=sk-shouldnotappear\n", encoding="utf-8")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))

    bundle = build_bundle()
    rendered = render_bundle(bundle, redact_output=True)

    assert "OPENAI_API_KEY" in rendered  # name OK
    assert "sk-shouldnotappear" not in rendered  # value scrubbed


# ── CLI command ──────────────────────────────────────────────────────────────


def test_diagnostics_command_refuses_without_redact() -> None:
    """Default-deny: prevent a user from copy-pasting a non-redacted bundle
    into a public GitHub issue."""
    result = runner.invoke(cli_main.app, ["diagnostics"])
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "--redact" in combined.lower()


def test_diagnostics_command_emits_json_with_redact(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret-do-not-leak-abcd1234efgh")
    result = runner.invoke(cli_main.app, ["diagnostics", "--redact"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # Output must be valid JSON
    payload = json.loads(result.stdout)
    assert "autosearch_version" in payload
    assert "mcp_config_paths" in payload
    # Secret value must not appear anywhere
    assert "sk-ant-test-secret" not in result.stdout
