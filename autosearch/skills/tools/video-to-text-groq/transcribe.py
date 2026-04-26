from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from autosearch.core.redact import redact_url

LOGGER = structlog.get_logger(__name__).bind(component="tool", skill="video-to-text-groq")

DEFAULT_TIMEOUT_SECONDS = 120.0
GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
GROQ_BACKEND = "groq"
MAX_AUDIO_BYTES = 25 * 1024 * 1024

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

VideoToTextGroqResult = dict[str, object]


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


def transcribe(
    url_or_path: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_client: httpx.Client | None = None,
) -> VideoToTextGroqResult:
    """Transcribe a video/audio URL or local file through Groq Whisper."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return _failure(
            source=url_or_path,
            reason="missing_api_key",
            suggest="配置 GROQ_API_KEY env var（免费注册 https://console.groq.com）",
        )

    try:
        audio_path = _prepare_audio(url_or_path)
        size_bytes = Path(audio_path).stat().st_size
        if size_bytes > MAX_AUDIO_BYTES:
            return _failure(
                source=url_or_path,
                reason="audio_too_large",
                size_mb=round(size_bytes / 1024 / 1024, 2),
                suggest="切片或本地转录",
            )

        response = _post_transcription(
            audio_path=audio_path,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )
    except YtDlpError as exc:
        LOGGER.warning(
            "video_to_text_groq_yt_dlp_failed",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="yt_dlp_failed",
            stderr_tail=exc.stderr_tail,
        )
    except subprocess.CalledProcessError as exc:
        stderr_tail = _stderr_tail(exc.stderr)
        LOGGER.warning(
            "video_to_text_groq_yt_dlp_failed",
            source=redact_url(url_or_path),
            reason=stderr_tail,
        )
        return _failure(
            source=url_or_path,
            reason="yt_dlp_failed",
            stderr_tail=stderr_tail,
        )
    except FFmpegMissingError:
        LOGGER.warning("video_to_text_groq_ffmpeg_missing", source=redact_url(url_or_path))
        return _failure(source=url_or_path, reason="ffmpeg_missing")
    except FFmpegFailedError as exc:
        LOGGER.warning(
            "video_to_text_groq_ffmpeg_failed",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="ffmpeg_failed",
            stderr_tail=exc.stderr_tail,
        )
    except httpx.HTTPError as exc:
        LOGGER.warning(
            "video_to_text_groq_http_error",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="groq_api_error",
            status=None,
            body=_truncate_body(str(exc) or exc.__class__.__name__),
        )
    except OSError as exc:
        LOGGER.warning(
            "video_to_text_groq_local_file_error",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="local_file_error",
            message=str(exc) or exc.__class__.__name__,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary for runtime tools
        LOGGER.warning(
            "video_to_text_groq_unexpected_error",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="unexpected_error",
            message=str(exc) or exc.__class__.__name__,
        )

    if response.status_code == 429:
        return _failure(
            source=url_or_path,
            reason="rate_limited",
            suggest="降级 video-to-text-openai 或等待",
        )

    if response.status_code >= 400:
        return _failure(
            source=url_or_path,
            reason="groq_api_error",
            status=response.status_code,
            body=_truncate_body(response.text),
        )

    try:
        payload = response.json()
    except ValueError as exc:
        LOGGER.warning(
            "video_to_text_groq_invalid_json",
            source=redact_url(url_or_path),
            reason=str(exc),
        )
        return _failure(
            source=url_or_path,
            reason="groq_api_error",
            status=response.status_code,
            body=_truncate_body(response.text),
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
            "model": GROQ_MODEL,
            "backend": GROQ_BACKEND,
        },
        "audio_path": audio_path,
        "source": redact_url(url_or_path),
    }


def _prepare_audio(url_or_path: str) -> str:
    if _looks_like_url(url_or_path):
        return _extract_audio(url_or_path)

    from autosearch.core.transcribe_path_guard import validate_local_path

    source_path = validate_local_path(url_or_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Local input file not found: {source_path}")

    if _is_audio_file(source_path):
        return str(source_path)

    if _is_video_file(source_path):
        return _convert_local_video_to_mp3(source_path)

    return str(source_path)


def _extract_audio(url_or_path: str) -> str:
    tmp_dir = Path(tempfile.mkdtemp(prefix="autosearch-video-to-text-groq-"))
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
    tmp_dir = Path(tempfile.mkdtemp(prefix="autosearch-video-to-text-groq-"))
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


def _post_transcription(
    *,
    audio_path: str,
    api_key: str,
    timeout_seconds: float,
    http_client: httpx.Client | None,
) -> httpx.Response:
    path = Path(audio_path)
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": GROQ_MODEL, "response_format": "verbose_json"}

    with path.open("rb") as audio_file:
        files = {"file": (path.name, audio_file, "audio/mpeg")}
        if http_client is not None:
            return http_client.post(
                GROQ_TRANSCRIPTIONS_URL,
                data=data,
                files=files,
                headers=headers,
                timeout=timeout_seconds,
            )

        with httpx.Client(timeout=timeout_seconds) as client:
            return client.post(
                GROQ_TRANSCRIPTIONS_URL,
                data=data,
                files=files,
                headers=headers,
            )


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


def _truncate_body(body: str, *, max_chars: int = 500) -> str:
    return body[:max_chars]


def _failure(*, source: str, reason: str, **extra: object) -> VideoToTextGroqResult:
    result: VideoToTextGroqResult = {"ok": False, "source": redact_url(source), "reason": reason}
    result.update(extra)
    return result
