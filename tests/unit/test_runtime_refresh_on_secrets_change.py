"""Bug 1 (fix-plan): a long-running MCP process used to keep the first-load
ChannelRuntime forever. After `autosearch configure NEW_KEY` wrote to the
secrets file, `doctor` saw the new key (it re-scans every call) but
`run_channel` did not (it ran against the cached runtime), so the same MCP
process gave contradictory answers about channel availability.

This pins the new fingerprint-based refresh: when the secrets-file mtime
changes OR a channel-relevant env-key flips presence, `get_channel_runtime()`
returns a fresh runtime."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from autosearch.core import channel_runtime as cr_mod
from autosearch.core import secrets_store


@pytest.fixture(autouse=True)
def _isolate_secrets(tmp_path, monkeypatch):
    secrets_file = tmp_path / "ai-secrets.env"
    secrets_file.write_text("# empty\n", encoding="utf-8")
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))
    secrets_store._FILE_INJECTED_VALUES.clear()
    # Drop any inherited keys so the fingerprint is deterministic.
    for key in cr_mod._CHANNEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    cr_mod.reset_channel_runtime()
    yield secrets_file
    cr_mod.reset_channel_runtime()
    secrets_store._FILE_INJECTED_VALUES.clear()


def test_runtime_rebuilds_when_env_key_appears(monkeypatch) -> None:
    """A new env key appearing post-startup must invalidate the cached runtime."""
    first = cr_mod.get_channel_runtime()
    assert first is cr_mod.get_channel_runtime(), (
        "stable: identical fingerprint → same runtime instance"
    )

    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy-key")
    second = cr_mod.get_channel_runtime()
    assert second is not first, "fingerprint changed (new env key) but runtime was not rebuilt"


def test_runtime_rebuilds_when_secrets_file_mtime_changes(_isolate_secrets) -> None:
    secrets_file: Path = _isolate_secrets
    first = cr_mod.get_channel_runtime()

    # Bump mtime to a clearly later instant — file-system mtime resolution
    # on some filesystems is 1s, so write a non-trivial gap.
    later = time.time() + 5
    os.utime(secrets_file, (later, later))

    second = cr_mod.get_channel_runtime()
    assert second is not first, "secrets-file mtime changed but runtime was not rebuilt"


def test_stable_state_does_not_rebuild(_isolate_secrets) -> None:
    first = cr_mod.get_channel_runtime()
    second = cr_mod.get_channel_runtime()
    third = cr_mod.get_channel_runtime()
    assert first is second is third, (
        "no fingerprint change → must reuse the cached runtime (cheap path)"
    )


def test_fingerprint_includes_secrets_mtime_and_env_presence() -> None:
    fp = cr_mod._current_fingerprint()
    assert isinstance(fp, tuple) and len(fp) == 2
    mtime, env_presence = fp
    assert isinstance(env_presence, tuple)
    # mtime can be a float or None depending on whether the file exists
    assert mtime is None or isinstance(mtime, float)


def test_secrets_file_refresh_does_not_clobber_explicit_process_env(
    _isolate_secrets, monkeypatch
) -> None:
    secrets_file: Path = _isolate_secrets
    monkeypatch.setenv("TIKHUB_API_KEY", "from-process")
    secrets_file.write_text(
        "TIKHUB_API_KEY=from-file-v1\nYOUTUBE_API_KEY=file-owned-v1\n",
        encoding="utf-8",
    )

    cr_mod.get_channel_runtime()
    assert os.environ["TIKHUB_API_KEY"] == "from-process"
    assert os.environ["YOUTUBE_API_KEY"] == "file-owned-v1"

    secrets_file.write_text(
        "TIKHUB_API_KEY=from-file-v2\nYOUTUBE_API_KEY=file-owned-v2\n",
        encoding="utf-8",
    )
    later = time.time() + 5
    os.utime(secrets_file, (later, later))

    cr_mod.get_channel_runtime()
    assert os.environ["TIKHUB_API_KEY"] == "from-process"
    assert os.environ["YOUTUBE_API_KEY"] == "file-owned-v2"
