from __future__ import annotations

import importlib
import os
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse

import structlog

from autosearch.core.redact import redact_url

LOGGER = structlog.get_logger(__name__).bind(component="tool", skill="video-to-text-local")

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
LOCAL_BACKEND = "mlx-whisper"
MODEL_ENV_VAR = "AUTOSEARCH_MLX_WHISPER_MODEL"

AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}
VIDEO_EXTENSIONS = {
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ts",
    ".webm",
}

VideoToTextLocalResult = dict[str, object]


class YtDlpError(RuntimeError):
    def __init__(self, stderr_tail: str) -> None:
        super().__init__(stderr_tail)
        self.stderr_tail = stderr_tail


class FFmpegMissingError(RuntimeError):
    pass


class FFmpegFailedError(RuntimeError):
    def __init__(self, stderr_tail: str) -> None:
        super().__init__(stderr_tail)
        self.stderr_tail = stderr_tail


class ModelDownloadError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def transcribe(
    url_or_path: str,
    *,
    mlx_whisper_module: ModuleType | None = None,
) -> VideoToTextLocalResult:
    """Transcribe a video/audio URL or local file through local mlx-whisper."""
    mlx = mlx_whisper_module if mlx_whisper_module is not None else _load_mlx_whisper()
    if mlx is None:
        return _failure(
            source=url_or_path,
            reason="mlx_whisper_unavailable",
            suggest="pip install mlx-whisper（Apple Silicon 专用）或降级 video-to-text-groq",
        )

    model = os.environ.get(MODEL_ENV_VAR) or DEFAULT_MODEL

    try:
        audio_path = _prepare_audio(url_or_path)
    except YtDlpError as exc:
        LOGGER.warning(
            "video_to_text_local_yt_dlp_failed",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(source=url_or_path, reason="yt_dlp_failed", stderr_tail=exc.stderr_tail)
    except subprocess.CalledProcessError as exc:
        stderr_tail = _stderr_tail(exc.stderr)
        LOGGER.warning(
            "video_to_text_local_yt_dlp_failed",
            source=redact_url(url_or_path),
            reason=stderr_tail,
        )
        return _failure(source=url_or_path, reason="yt_dlp_failed", stderr_tail=stderr_tail)
    except FFmpegMissingError:
        LOGGER.warning("video_to_text_local_ffmpeg_missing", source=redact_url(url_or_path))
        return _failure(source=url_or_path, reason="ffmpeg_missing")
    except FFmpegFailedError as exc:
        LOGGER.warning(
            "video_to_text_local_ffmpeg_failed",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="ffmpeg_failed",
            stderr_tail=exc.stderr_tail,
        )
    except OSError as exc:
        LOGGER.warning(
            "video_to_text_local_local_file_error",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="local_file_error",
            message=str(exc) or exc.__class__.__name__,
        )

    try:
        payload = mlx.transcribe(audio_path, path_or_hf_repo=model)
    except ModelDownloadError as exc:
        LOGGER.warning(
            "video_to_text_local_model_download_failed",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="model_download_failed",
            message=exc.message,
            suggest="检查网络并重试，或预先下载模型到 ~/.cache/huggingface/hub/",
        )
    except Exception as exc:  # pragma: no cover - defensive boundary for runtime tools
        LOGGER.warning(
            "video_to_text_local_runtime_error",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="mlx_whisper_runtime_error",
            message=str(exc) or exc.__class__.__name__,
        )

    segments = payload.get("segments") if isinstance(payload, dict) else None
    normalized_segments = segments if isinstance(segments, list) else []
    return {
        "ok": True,
        "raw_txt": str(payload.get("text") or "") if isinstance(payload, dict) else "",
        "subtitle_srt": _build_srt(normalized_segments),
        "meta": {
            "language": str(payload.get("language") or "") if isinstance(payload, dict) else "",
            "duration_sec": _duration_seconds(payload, normalized_segments),
            "model": model,
            "backend": LOCAL_BACKEND,
        },
        "audio_path": audio_path,
        "source": redact_url(url_or_path),
    }


def _load_mlx_whisper() -> ModuleType | None:
    try:
        return importlib.import_module("mlx_whisper")
    except ImportError:
        return None


def _prepare_audio(url_or_path: str) -> str:
    if _looks_like_url(url_or_path):
        return _extract_audio(url_or_path)

    source_path = Path(url_or_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Local input file not found: {source_path}")

    if _is_audio_file(source_path):
        return str(source_path)

    if _is_video_file(source_path):
        return _convert_local_video_to_mp3(source_path)

    return str(source_path)


def _extract_audio(url_or_path: str) -> str:
    tmp_dir = Path(tempfile.mkdtemp(prefix="autosearch-video-to-text-local-"))
    output_template = tmp_dir / "audio.%(ext)s"
    command = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "128K",
        "--output",
        str(output_template),
        url_or_path,
    ]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", None)
        raise YtDlpError(_stderr_tail(stderr)) from exc

    mp3_path = tmp_dir / "audio.mp3"
    if mp3_path.exists():
        return str(mp3_path)

    candidates = sorted(path for path in tmp_dir.glob("audio.*") if path.is_file())
    if candidates:
        return str(candidates[0])

    raise YtDlpError(_stderr_tail(result.stderr))


def _convert_local_video_to_mp3(source_path: Path) -> str:
    tmp_dir = Path(tempfile.mkdtemp(prefix="autosearch-video-to-text-local-"))
    audio_path = tmp_dir / "audio.mp3"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(audio_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise FFmpegMissingError from exc
    except subprocess.CalledProcessError as exc:
        raise FFmpegFailedError(_stderr_tail(exc.stderr)) from exc

    return str(audio_path)


def _build_srt(segments: list[Any]) -> str:
    entries: list[str] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue

        start = _to_float(segment.get("start"), default=0.0)
        end = _to_float(segment.get("end"), default=start)
        text = str(segment.get("text") or "").strip()
        entries.append(f"{index}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{text}")

    return "\n\n".join(entries) + ("\n" if entries else "")


def _format_timestamp(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def _duration_seconds(payload: object, segments: list[Any]) -> float:
    if isinstance(payload, dict) and payload.get("duration") is not None:
        return _to_float(payload.get("duration"), default=0.0)

    ends = [
        _to_float(segment.get("end"), default=0.0)
        for segment in segments
        if isinstance(segment, dict)
    ]
    return max(ends, default=0.0)


def _to_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _stderr_tail(stderr: object, *, max_chars: int = 1000) -> str:
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        text = stderr.decode(errors="replace")
    else:
        text = str(stderr)
    return text[-max_chars:]


def _failure(*, source: str, reason: str, **extra: object) -> VideoToTextLocalResult:
    result: VideoToTextLocalResult = {"ok": False, "source": redact_url(source), "reason": reason}
    result.update(extra)
    return result
