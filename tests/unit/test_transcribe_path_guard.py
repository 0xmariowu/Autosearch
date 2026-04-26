from __future__ import annotations

from pathlib import Path

import pytest


def test_default_deny_unknown_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", raising=False)

    import autosearch.core.transcribe_path_guard

    with pytest.raises(PermissionError):
        autosearch.core.transcribe_path_guard.validate_local_path("/tmp/random.mp3")


def test_rejects_non_audio_extension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", "/tmp")
    candidate = Path("/tmp") / f"{tmp_path.name}.txt"
    candidate.write_text("not media", encoding="utf-8")

    import autosearch.core.transcribe_path_guard

    try:
        with pytest.raises(PermissionError, match="extension"):
            autosearch.core.transcribe_path_guard.validate_local_path(candidate)
    finally:
        candidate.unlink(missing_ok=True)


def test_rejects_blacklisted_path_even_in_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", str(tmp_path))
    candidate = tmp_path / ".env"
    candidate.write_text("SECRET=value", encoding="utf-8")

    import autosearch.core.transcribe_path_guard

    with pytest.raises(PermissionError, match="hard-deny"):
        autosearch.core.transcribe_path_guard.validate_local_path(candidate)


@pytest.mark.mime
def test_rejects_text_file_with_mp3_extension(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", str(tmp_path))
    candidate = tmp_path / "fake.mp3"
    candidate.write_text("hello world", encoding="utf-8")

    import autosearch.core.transcribe_path_guard

    with pytest.raises(PermissionError, match="magic"):
        autosearch.core.transcribe_path_guard.validate_local_path(candidate)
