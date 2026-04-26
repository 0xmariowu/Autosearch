from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import httpx
import pytest


def _load_video_to_text_openai() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    transcribe_path = (
        root / "autosearch" / "skills" / "tools" / "video-to-text-openai" / "transcribe.py"
    )
    spec = importlib.util.spec_from_file_location(
        "video_to_text_openai_path_redact_under_test", transcribe_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIDEO_TO_TEXT_OPENAI = _load_video_to_text_openai()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _verbose_json() -> dict[str, object]:
    return {
        "text": "Local path redaction transcript.",
        "language": "en",
        "duration": 1.0,
        "segments": [{"start": 0.0, "end": 1.0, "text": "Local path redaction transcript."}],
    }


def test_local_path_not_in_structured_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local_mp3 = tmp_path / "private-recording.mp3"
    local_mp3.write_bytes(b"ID3 fake mp3")
    absolute_input = str(local_mp3)

    monkeypatch.setenv("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_extract(source: str) -> str:
        raise AssertionError(f"yt-dlp should not run for local audio: {source}")

    monkeypatch.setattr(VIDEO_TO_TEXT_OPENAI, "_extract_audio", fail_extract)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_verbose_json(), request=request)

    with _client(handler) as client:
        success = VIDEO_TO_TEXT_OPENAI.transcribe(absolute_input, http_client=client)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    failure = VIDEO_TO_TEXT_OPENAI.transcribe(absolute_input)

    assert success["ok"] is True
    assert failure["ok"] is False
    assert failure["reason"] == "missing_api_key"
    assert absolute_input not in str(failure["reason"])

    leaked_fields = []
    if success["source"] == absolute_input:
        leaked_fields.append("success.source")
    if success["audio_path"] == absolute_input:
        leaked_fields.append("success.audio_path")
    if failure["source"] == absolute_input:
        leaked_fields.append("failure.source")

    for label, result in (("success", success), ("failure", failure)):
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if absolute_input in serialized:
            leaked_fields.append(f"{label}.serialized")

    assert not leaked_fields
