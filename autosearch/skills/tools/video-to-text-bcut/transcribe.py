"""video-to-text-bcut: Bilibili Bcut ASR — free, character-level timestamps.

Five-step Bcut flow:
  1. POST /resource/create      → upload authorisation
  2. PUT  {upload_urls[]}       → chunked upload
  3. POST /resource/create/complete → commit
  4. POST /task                 → start ASR task
  5. GET  /task/result          → poll until state==4 (done)
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import structlog

from autosearch.core.redact import redact, redact_url

LOGGER = structlog.get_logger(__name__).bind(component="tool", skill="video-to-text-bcut")

_BCUT_BASE = "https://member.bilibili.com/x/bcut/rubick-interface"
_DEFAULT_TIMEOUT = 180.0
_POLL_INTERVAL = 3.0
_MAX_POLLS = 60  # 3 min max

BcutResult = dict[str, object]


# ── Segment builder ──────────────────────────────────────────────────────────

_SENTENCE_ENDINGS = frozenset("。！？；…")
_MINOR_BREAKS = frozenset("，,、")
_MAX_CHARS = 20
_MAX_SECONDS = 6.0
_GAP_MS = 600


def _build_segments(utterances: list[dict]) -> list[dict[str, object]]:
    """Convert Bcut utterances (with word-level timestamps) to sentence segments."""
    segments: list[dict[str, object]] = []

    for utt in utterances:
        words = utt.get("words") or []
        text = utt.get("transcript", "")

        if not words:
            # No word timestamps — use utterance boundaries
            segments.append(
                {
                    "start": utt.get("start_time", 0) / 1000.0,
                    "end": utt.get("end_time", 0) / 1000.0,
                    "text": text,
                }
            )
            continue

        current: list[dict] = []
        for i, word in enumerate(words):
            current.append(word)
            char = word.get("label", "")
            cur_text = "".join(w.get("label", "") for w in current)
            should_split = False

            if char in _SENTENCE_ENDINGS:
                should_split = True
            elif len(cur_text) >= _MAX_CHARS:
                should_split = char in _MINOR_BREAKS or len(cur_text) > _MAX_CHARS
            elif current:
                dur_ms = word.get("end_time", 0) - current[0].get("start_time", 0)
                if dur_ms >= _MAX_SECONDS * 1000:
                    should_split = True

            if not should_split and i + 1 < len(words):
                gap = words[i + 1].get("start_time", 0) - word.get("end_time", 0)
                if gap >= _GAP_MS:
                    should_split = True

            if should_split and current:
                segments.append(
                    {
                        "start": current[0].get("start_time", 0) / 1000.0,
                        "end": current[-1].get("end_time", 0) / 1000.0,
                        "text": cur_text,
                    }
                )
                current = []

        if current:
            cur_text = "".join(w.get("label", "") for w in current)
            segments.append(
                {
                    "start": current[0].get("start_time", 0) / 1000.0,
                    "end": current[-1].get("end_time", 0) / 1000.0,
                    "text": cur_text,
                }
            )

    return segments


# ── Bcut API ──────────────────────────────────────────────────────────────────


async def _bcut_upload(client: httpx.AsyncClient, audio_path: Path) -> str:
    """Upload audio to Bcut and return task-ready download_url."""
    audio_bytes = audio_path.read_bytes()
    size = len(audio_bytes)

    # Step 1: Request upload slots
    r = await client.post(
        f"{_BCUT_BASE}/resource/create",
        json={
            "type": 2,
            "name": audio_path.name,
            "size": size,
            "ResourceFileType": "mp3",
            "model_id": "8",
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json().get("data", {})
    in_boss_key = d["in_boss_key"]
    resource_id = d["resource_id"]
    upload_id = d["upload_id"]
    upload_urls: list[str] = d["upload_urls"]
    per_size: int = d["per_size"]

    # Step 2: Chunked PUT upload
    etags: list[str] = []
    async with httpx.AsyncClient(timeout=60) as up_client:
        for i, url in enumerate(upload_urls):
            chunk = audio_bytes[i * per_size : (i + 1) * per_size]
            resp = await up_client.put(url, content=chunk)
            resp.raise_for_status()
            etags.append(resp.headers.get("ETag", "").strip('"'))

    # Step 3: Commit upload
    r2 = await client.post(
        f"{_BCUT_BASE}/resource/create/complete",
        json={
            "InBossKey": in_boss_key,
            "ResourceId": resource_id,
            "Etags": ",".join(etags),
            "UploadId": upload_id,
            "model_id": "8",
        },
        timeout=30,
    )
    r2.raise_for_status()
    return r2.json()["data"]["download_url"]


async def _bcut_transcribe(audio_path: Path) -> list[dict]:
    """Full Bcut pipeline: upload → task → poll → return utterances."""
    async with httpx.AsyncClient(timeout=30) as client:
        download_url = await _bcut_upload(client, audio_path)

        # Step 4: Create ASR task
        r3 = await client.post(
            f"{_BCUT_BASE}/task",
            json={"resource": download_url, "model_id": "8"},
            timeout=30,
        )
        r3.raise_for_status()
        task_id = r3.json()["data"]["task_id"]

        # Step 5: Poll until state == 4 (complete) or -1 (failed)
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            r4 = await client.get(
                f"{_BCUT_BASE}/task/result",
                params={"model_id": "7", "task_id": task_id},
                timeout=15,
            )
            r4.raise_for_status()
            task = r4.json().get("data", {})
            state = task.get("state")
            if state == 4:
                import json as _json

                result_raw = task.get("result", "{}")
                return _json.loads(result_raw).get("utterances", [])
            if state == -1:
                raise RuntimeError(f"Bcut task failed: {task.get('message', 'unknown')}")

    raise TimeoutError("Bcut transcription timed out after polling")


# ── Audio extraction ──────────────────────────────────────────────────────────


def _extract_audio_to_wav(source: str, output_wav: Path) -> None:
    """Download (if URL) and convert to 16kHz mono WAV via yt-dlp + ffmpeg."""
    parsed = urlparse(source)
    is_url = parsed.scheme in {"http", "https"} and parsed.netloc

    with tempfile.TemporaryDirectory() as tmpdir:
        if is_url:
            audio_tmp = Path(tmpdir) / "audio"
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-x",
                    "--audio-format",
                    "mp3",
                    "-o",
                    str(audio_tmp),
                    source,
                    "--quiet",
                    "--no-playlist",
                ],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"yt-dlp failed: {result.stderr[-500:].decode(errors='replace')}"
                )
            # yt-dlp appends extension
            candidates = list(Path(tmpdir).glob("audio.*"))
            if not candidates:
                raise RuntimeError("yt-dlp produced no output file")
            input_path = str(candidates[0])
        else:
            input_path = source

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                input_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                "-y",
                str(output_wav),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )


# ── Public entry point ────────────────────────────────────────────────────────


async def transcribe(source: str, timeout: float = _DEFAULT_TIMEOUT) -> BcutResult:
    """Transcribe a video/audio URL or local path using Bcut ASR.

    Returns:
        {ok, text, segments, duration_seconds, source}
        or {ok: False, reason, source}
    """
    if not isinstance(source, str):
        return {"ok": False, "source": "", "reason": "source must be a string"}

    if not source.strip():
        return {"ok": False, "source": "", "reason": "empty source"}

    redacted_source = redact_url(source)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "audio.wav"

            try:
                _extract_audio_to_wav(source, wav_path)
            except Exception as exc:
                reason = redact(str(exc).replace(source, redacted_source))
                LOGGER.warning(
                    "bcut_audio_extraction_failed",
                    source=redacted_source,
                    reason=reason,
                )
                return {
                    "ok": False,
                    "source": redacted_source,
                    "reason": f"audio_extraction: {reason}",
                }

            try:
                utterances = await asyncio.wait_for(
                    _bcut_transcribe(wav_path),
                    timeout=timeout,
                )
            except Exception as exc:
                reason = redact(str(exc).replace(source, redacted_source))
                LOGGER.warning(
                    "bcut_api_failed",
                    source=redacted_source,
                    reason=reason,
                )
                return {"ok": False, "source": redacted_source, "reason": f"bcut_api: {reason}"}

            segments = _build_segments(utterances)
            full_text = "".join(s["text"] for s in segments)
            duration = max((s["end"] for s in segments), default=0.0)

            return {
                "ok": True,
                "source": redacted_source,
                "text": full_text,
                "segments": segments,
                "duration_seconds": duration,
            }

    except Exception as exc:
        reason = redact(str(exc).replace(source, redacted_source))
        LOGGER.warning(
            "bcut_unexpected_error",
            source=redacted_source,
            error_type=type(exc).__name__,
            reason=reason,
        )
        return {"ok": False, "source": redacted_source, "reason": f"unexpected: {reason}"}
