from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_video_to_text_local() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    transcribe_path = (
        root / "autosearch" / "skills" / "tools" / "video-to-text-local" / "transcribe.py"
    )
    spec = importlib.util.spec_from_file_location("video_to_text_local_under_test", transcribe_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIDEO_TO_TEXT_LOCAL = _load_video_to_text_local()


def _fake_mlx_payload() -> dict[str, object]:
    return {
        "text": "Hello world. Second line.",
        "language": "en",
        "duration": 3.75,
        "segments": [
            {"start": 0.0, "end": 1.25, "text": "Hello world."},
            {"start": 1.25, "end": 3.75, "text": "Second line."},
        ],
    }


def _mlx_module(transcribe_fn) -> SimpleNamespace:
    return SimpleNamespace(transcribe=transcribe_fn)


def test_url_happy_path_returns_text_srt_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_mp3 = tmp_path / "audio.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setattr(VIDEO_TO_TEXT_LOCAL, "_extract_audio", lambda source: str(fake_mp3))

    captured: dict[str, object] = {}

    def fake_transcribe(audio_path: str, *, path_or_hf_repo: str) -> dict[str, object]:
        captured["audio_path"] = audio_path
        captured["model"] = path_or_hf_repo
        return _fake_mlx_payload()

    result = VIDEO_TO_TEXT_LOCAL.transcribe(
        "https://www.youtube.com/watch?v=example",
        mlx_whisper_module=_mlx_module(fake_transcribe),
    )

    assert result["ok"] is True
    assert result["raw_txt"] == "Hello world. Second line."
    assert "1\n00:00:00,000 --> 00:00:01,250\nHello world." in result["subtitle_srt"]
    assert "2\n00:00:01,250 --> 00:00:03,750\nSecond line." in result["subtitle_srt"]
    assert result["meta"] == {
        "language": "en",
        "duration_sec": 3.75,
        "model": "mlx-community/whisper-large-v3-turbo",
        "backend": "mlx-whisper",
    }
    assert result["audio_path"] == str(fake_mp3)
    assert result["source"] == "https://www.youtube.com/watch?v=example"
    assert captured["audio_path"] == str(fake_mp3)
    assert captured["model"] == "mlx-community/whisper-large-v3-turbo"


def test_local_audio_happy_path_skips_yt_dlp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")

    def fail_extract(source: str) -> str:
        raise AssertionError(f"yt-dlp should not run for local audio: {source}")

    monkeypatch.setattr(VIDEO_TO_TEXT_LOCAL, "_extract_audio", fail_extract)

    def fake_transcribe(audio_path: str, *, path_or_hf_repo: str) -> dict[str, object]:
        return _fake_mlx_payload()

    result = VIDEO_TO_TEXT_LOCAL.transcribe(
        str(fake_mp3),
        mlx_whisper_module=_mlx_module(fake_transcribe),
    )

    assert result["ok"] is True
    assert result["raw_txt"] == "Hello world. Second line."
    assert result["audio_path"] == str(fake_mp3)


def test_mlx_whisper_unavailable_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setattr(VIDEO_TO_TEXT_LOCAL, "_load_mlx_whisper", lambda: None)

    result = VIDEO_TO_TEXT_LOCAL.transcribe(str(fake_mp3))

    assert result["ok"] is False
    assert result["reason"] == "mlx_whisper_unavailable"
    assert "mlx-whisper" in result["suggest"]
    assert "video-to-text-groq" in result["suggest"]


def test_custom_model_via_env_var_is_passed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")
    monkeypatch.setenv("AUTOSEARCH_MLX_WHISPER_MODEL", "mlx-community/whisper-tiny")

    captured: dict[str, object] = {}

    def fake_transcribe(audio_path: str, *, path_or_hf_repo: str) -> dict[str, object]:
        captured["model"] = path_or_hf_repo
        return _fake_mlx_payload()

    result = VIDEO_TO_TEXT_LOCAL.transcribe(
        str(fake_mp3),
        mlx_whisper_module=_mlx_module(fake_transcribe),
    )

    assert result["ok"] is True
    assert result["meta"]["model"] == "mlx-community/whisper-tiny"
    assert captured["model"] == "mlx-community/whisper-tiny"


def test_yt_dlp_failure_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_extract(source: str) -> str:
        raise subprocess.CalledProcessError(
            1,
            ["yt-dlp", source],
            stderr="unsupported URL\nnetwork failure",
        )

    monkeypatch.setattr(VIDEO_TO_TEXT_LOCAL, "_extract_audio", fail_extract)

    def fake_transcribe(audio_path: str, *, path_or_hf_repo: str) -> dict[str, object]:
        raise AssertionError("mlx should not run if yt-dlp failed")

    result = VIDEO_TO_TEXT_LOCAL.transcribe(
        "https://unsupported.example/video",
        mlx_whisper_module=_mlx_module(fake_transcribe),
    )

    assert result["ok"] is False
    assert result["reason"] == "yt_dlp_failed"
    assert "unsupported URL" in result["stderr_tail"]


def test_mlx_runtime_error_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_mp3 = tmp_path / "local.mp3"
    fake_mp3.write_bytes(b"fake mp3")

    def fake_transcribe(audio_path: str, *, path_or_hf_repo: str) -> dict[str, object]:
        raise RuntimeError("metal kernel launch failed")

    result = VIDEO_TO_TEXT_LOCAL.transcribe(
        str(fake_mp3),
        mlx_whisper_module=_mlx_module(fake_transcribe),
    )

    assert result["ok"] is False
    assert result["reason"] == "mlx_whisper_runtime_error"
    assert "metal kernel launch failed" in result["message"]
