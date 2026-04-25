from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import httpx
import pytest


def _load_video_to_text_groq() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    transcribe_path = (
        root / "autosearch" / "skills" / "tools" / "video-to-text-groq" / "transcribe.py"
    )
    spec = importlib.util.spec_from_file_location("video_to_text_groq_under_test", transcribe_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIDEO_TO_TEXT_GROQ = _load_video_to_text_groq()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _verbose_json() -> dict[str, object]:
    return {
        "text": "Hello world. Second line.",
        "language": "en",
        "duration": 3.75,
        "segments": [
            {"start": 0.0, "end": 1.25, "text": "Hello world."},
            {"start": 1.25, "end": 3.75, "text": "Second line."},
        ],
    }


def test_url_happy_path_returns_text_srt_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_mp3 = tmp_path / "audio.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(VIDEO_TO_TEXT_GROQ, "_extract_audio", lambda source: str(fake_mp3))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == VIDEO_TO_TEXT_GROQ.GROQ_TRANSCRIPTIONS_URL
        assert request.headers["authorization"] == "Bearer test-key"
        assert b'name="model"' in request.content
        assert b"whisper-large-v3" in request.content
        assert b'name="response_format"' in request.content
        assert b"verbose_json" in request.content
        return httpx.Response(200, json=_verbose_json(), request=request)

    with _client(handler) as client:
        result = VIDEO_TO_TEXT_GROQ.transcribe(
            "https://www.youtube.com/watch?v=example",
            http_client=client,
        )

    assert result["ok"] is True
    assert result["raw_txt"] == "Hello world. Second line."
    assert "1\n00:00:00,000 --> 00:00:01,250\nHello world." in result["subtitle_srt"]
    assert "2\n00:00:01,250 --> 00:00:03,750\nSecond line." in result["subtitle_srt"]
    assert result["meta"] == {
        "language": "en",
        "duration_sec": 3.75,
        "model": "whisper-large-v3",
        "backend": "groq",
    }
    assert result["audio_path"] == str(fake_mp3)
    # P0-2: source URL is sanitized via redact_url — query string stripped
    # to avoid leaking signed-URL credentials (access_token, X-Amz-Signature, …).
    assert result["source"] == "https://www.youtube.com/watch"


def test_local_audio_happy_path_skips_yt_dlp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fail_extract(source: str) -> str:
        raise AssertionError(f"yt-dlp should not run for local audio: {source}")

    monkeypatch.setattr(VIDEO_TO_TEXT_GROQ, "_extract_audio", fail_extract)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_verbose_json(), request=request)

    with _client(handler) as client:
        result = VIDEO_TO_TEXT_GROQ.transcribe(str(fake_mp3), http_client=client)

    assert result["ok"] is True
    assert result["raw_txt"] == "Hello world. Second line."
    assert result["audio_path"] == str(fake_mp3)


def test_missing_groq_api_key_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = VIDEO_TO_TEXT_GROQ.transcribe(str(fake_mp3))

    assert result["ok"] is False
    assert result["reason"] == "missing_api_key"
    assert result["suggest"] == "配置 GROQ_API_KEY env var（免费注册 https://console.groq.com）"


def test_groq_429_returns_rate_limited(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="too many requests", request=request)

    with _client(handler) as client:
        result = VIDEO_TO_TEXT_GROQ.transcribe(str(fake_mp3), http_client=client)

    assert result["ok"] is False
    assert result["reason"] == "rate_limited"
    assert result["suggest"] == "降级 video-to-text-openai 或等待"


def test_yt_dlp_failure_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "audio.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fail_extract(source: str) -> str:
        raise subprocess.CalledProcessError(
            1,
            ["yt-dlp", source],
            stderr="unsupported URL\nnetwork failure",
        )

    monkeypatch.setattr(VIDEO_TO_TEXT_GROQ, "_extract_audio", fail_extract)

    result = VIDEO_TO_TEXT_GROQ.transcribe("https://unsupported.example/video")

    assert result["ok"] is False
    assert result["reason"] == "yt_dlp_failed"
    assert "unsupported URL" in result["stderr_tail"]
