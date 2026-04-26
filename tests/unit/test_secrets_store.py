"""Tests for autosearch.core.secrets_store."""

from __future__ import annotations

import builtins
import importlib.util
import os
from pathlib import Path

import pytest

from autosearch.core import secrets_store as secrets_store_mod
from autosearch.core.secrets_store import (
    available_env_keys,
    inject_into_env,
    load_secrets,
    resolve_env_value,
    secrets_path,
    write_secret,
)


@pytest.fixture(autouse=True)
def _reset_file_injection_tracking():
    secrets_store_mod._FILE_INJECTED_VALUES.clear()
    yield
    secrets_store_mod._FILE_INJECTED_VALUES.clear()


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_module_imports_when_fcntl_is_unavailable(monkeypatch):
    real_import = builtins.__import__

    def import_without_fcntl(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fcntl":
            raise ImportError("fcntl unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_fcntl)
    spec = importlib.util.spec_from_file_location(
        "secrets_store_without_fcntl",
        secrets_store_mod.__file__,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert module._fcntl is None


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


def test_write_secret_basic(tmp_path):
    f = tmp_path / "ai-secrets.env"

    write_secret("OPENAI_API_KEY", "sk-basic", path=f)

    assert f.read_text(encoding="utf-8") == "OPENAI_API_KEY=sk-basic\n"
    assert load_secrets(f) == {"OPENAI_API_KEY": "sk-basic"}


@pytest.mark.parametrize(
    "bad_key",
    ["", "1OPENAI_API_KEY", "OPENAI-API-KEY", "OPENAI.API.KEY", "OPENAI API KEY"],
)
def test_write_secret_rejects_invalid_key(tmp_path, bad_key):
    f = tmp_path / "ai-secrets.env"

    with pytest.raises(ValueError, match=r"secret key must match"):
        write_secret(bad_key, "sk-basic", path=f)

    assert not f.exists()


@pytest.mark.parametrize(
    "bad_value",
    ["sk-line-1\nINJECTED_KEY=bad", "sk-line-1\rsk-line-2", "sk-prefix\0sk-suffix"],
)
def test_write_secret_rejects_newline_and_nul_values(tmp_path, bad_value):
    f = tmp_path / "ai-secrets.env"

    with pytest.raises(ValueError, match=r"secret value must not contain"):
        write_secret("OPENAI_API_KEY", bad_value, path=f)

    assert not f.exists()


def test_write_secret_preserves_comments_and_unknown_lines(tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(
        f,
        "\n".join(
            [
                "# keep this comment",
                "",
                "MALFORMED_LINE_WITHOUT_EQUALS",
                "OPENAI_API_KEY=old-value",
                "TIKHUB_API_KEY=keep-value",
            ]
        )
        + "\n",
    )

    write_secret("OPENAI_API_KEY", "new value", path=f)

    assert f.read_text(encoding="utf-8") == "\n".join(
        [
            "# keep this comment",
            "",
            "MALFORMED_LINE_WITHOUT_EQUALS",
            "OPENAI_API_KEY='new value'",
            "TIKHUB_API_KEY=keep-value",
            "",
        ]
    )
    assert load_secrets(f) == {
        "OPENAI_API_KEY": "new value",
        "TIKHUB_API_KEY": "keep-value",
    }


def test_write_secret_fsyncs_temp_before_replace(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    events: list[str] = []
    real_replace = secrets_store_mod.os.replace

    def fake_fsync(fd: int) -> None:
        events.append("fsync")

    def fake_replace(src: str, dst: str | os.PathLike[str]) -> None:
        events.append("replace")
        assert "fsync" in events
        real_replace(src, dst)

    monkeypatch.setattr(secrets_store_mod.os, "fsync", fake_fsync)
    monkeypatch.setattr(secrets_store_mod.os, "replace", fake_replace)

    write_secret("OPENAI_API_KEY", "sk-fsync", path=f)

    assert events == ["fsync", "replace"]


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


def test_force_inject_does_not_overwrite_preexisting_process_env(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "TIKHUB_API_KEY=from-file\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.setenv("TIKHUB_API_KEY", "from-process")

    injected = inject_into_env(force=True)

    assert "TIKHUB_API_KEY" not in injected
    assert os.environ["TIKHUB_API_KEY"] == "from-process"


def test_force_inject_refreshes_key_previously_injected_from_file(monkeypatch, tmp_path):
    f = tmp_path / "ai-secrets.env"
    _write(f, "TIKHUB_API_KEY=v1\n")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(f))
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    first = inject_into_env()
    assert "TIKHUB_API_KEY" in first
    assert os.environ["TIKHUB_API_KEY"] == "v1"

    _write(f, "TIKHUB_API_KEY=v2\n")
    second = inject_into_env(force=True)

    assert "TIKHUB_API_KEY" in second
    assert os.environ["TIKHUB_API_KEY"] == "v2"


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
