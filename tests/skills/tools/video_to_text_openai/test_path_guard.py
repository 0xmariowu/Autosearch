from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_video_to_text_openai() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    transcribe_path = (
        root / "autosearch" / "skills" / "tools" / "video-to-text-openai" / "transcribe.py"
    )
    spec = importlib.util.spec_from_file_location(
        "video_to_text_openai_path_guard_under_test", transcribe_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIDEO_TO_TEXT_OPENAI = _load_video_to_text_openai()


def test_local_path_rejected_when_no_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", raising=False)

    try:
        result = VIDEO_TO_TEXT_OPENAI.transcribe("/tmp/x.mp3")
    except PermissionError as exc:
        assert "transcribe path guard" in str(exc)
        return

    assert result["ok"] is False
    assert "transcribe path guard" in str(result.get("message") or result.get("reason") or "")
