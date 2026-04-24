"""Tests for autosearch.core.secrets_store."""

from __future__ import annotations

from pathlib import Path

from autosearch.core.secrets_store import (
    available_env_keys,
    load_secrets,
    resolve_env_value,
    secrets_path,
)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_secrets_path_honors_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom.env"
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(custom))
    assert secrets_path() == custom


def test_load_secrets_returns_empty_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "nope.env"))
    assert load_secrets() == {}


def test_load_secrets_parses_kv_with_quotes_and_skips_comments(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(
        f,
        "\n".join(
            [
                "# top comment",
                "",
                "OPENAI_API_KEY=sk-plain",
                "TIKHUB_API_KEY='quoted secret'",
                'WEIBO_COOKIES="double quoted"',
                "  # indented comment",
                "MALFORMED_LINE_WITHOUT_EQUALS",
                "=missing_key",
            ]
        )
        + "\n",
    )
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))

    result = load_secrets()
    assert result == {
        "OPENAI_API_KEY": "sk-plain",
        "TIKHUB_API_KEY": "quoted secret",
        "WEIBO_COOKIES": "double quoted",
    }


def test_available_env_keys_unions_env_and_file(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "FROM_FILE_KEY=value1\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.setenv("FROM_PROCESS_KEY", "value2")

    keys = available_env_keys()
    assert "FROM_FILE_KEY" in keys
    assert "FROM_PROCESS_KEY" in keys


def test_available_env_keys_skips_empty_file_values(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "EMPTY_KEY=\nGOOD_KEY=present\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))

    keys = available_env_keys()
    assert "GOOD_KEY" in keys
    assert "EMPTY_KEY" not in keys


def test_resolve_env_value_prefers_process_env_over_file(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "OVERRIDE_ME=from_file\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.setenv("OVERRIDE_ME", "from_process")

    assert resolve_env_value("OVERRIDE_ME") == "from_process"


def test_resolve_env_value_falls_back_to_file_when_env_unset(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "FILE_ONLY=in_file\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.delenv("FILE_ONLY", raising=False)

    assert resolve_env_value("FILE_ONLY") == "in_file"


def test_resolve_env_value_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    assert resolve_env_value("DEFINITELY_NOT_SET") is None


def test_doctor_picks_up_key_from_secrets_file(monkeypatch, tmp_path):
    """Integration: a key written to ai-secrets.env should be visible to doctor's
    `_current_env_keys`, so a configured channel actually shows as available."""
    from autosearch.core import doctor

    f = tmp_path / "ai-secrets.env"
    _write(f, "TIKHUB_API_KEY=test-token\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    keys = doctor._current_env_keys()
    assert "TIKHUB_API_KEY" in keys
