---
name: video-to-text-local
description: Transcribe video/audio URL or local file to text + SRT using yt-dlp + local mlx-whisper (Apple Silicon). Free, offline, fastest on M-series Macs. Opt-in advanced path for users with Apple Silicon + mlx-whisper installed. Returns raw text and segments; summary is caller's responsibility.
version: 0.1.0
layer: leaf
domains: [video-audio, transcription]
scenarios: [video-to-text, subtitle-extraction, podcast-transcription, offline-transcription]
trigger_keywords: [转文字, 字幕, 转录, transcribe, whisper, video to text, 播客字幕, 本地转录, offline transcribe]
model_tier: Fast
auth_required: false
cost: free
experience_digest: experience.md
---

Transcribe video or audio entirely on-device using `yt-dlp` audio extraction plus local `mlx-whisper` inference. Works offline, zero API cost, fastest on Apple Silicon M-series with MLX Metal acceleration.

## Input Fit

- YouTube URLs.
- Bilibili URLs.
- Douyin URLs.
- Xiaoyuzhou podcast URLs.
- Local audio files such as MP3, M4A, WAV, AAC, FLAC, OGG, and OPUS.
- Local video files such as MP4, MOV, MKV, AVI, WEBM, FLV, and M4V.

## Invocation

Call `transcribe.py`'s sync `transcribe(url_or_path: str)` function with the original URL or local file path:

```python
result = transcribe("https://www.youtube.com/watch?v=example")
```

Successful calls return:

```python
{
    "ok": True,
    "raw_txt": "...",
    "subtitle_srt": "1\n00:00:00,000 --> 00:00:03,100\n...\n",
    "meta": {
        "language": "en",
        "duration_sec": 123.4,
        "model": "mlx-community/whisper-large-v3-turbo",
        "backend": "mlx-whisper",
    },
    "audio_path": "/tmp/autosearch-video-to-text-local-.../audio.mp3",
    "source": "https://www.youtube.com/watch?v=example",
}
```

## Failure Modes

- Missing `mlx-whisper` package returns `reason: mlx_whisper_unavailable` (install with `pip install mlx-whisper`, Apple Silicon only).
- Unsupported URLs, network failures, and non-zero `yt-dlp` exits return `reason: yt_dlp_failed`.
- Missing local `ffmpeg` for video conversion returns `reason: ffmpeg_missing`.
- Model download failure (no network on first run) returns `reason: model_download_failed`.
- Other MLX / transcription runtime errors return `reason: mlx_whisper_runtime_error`.

Downgrade chain: use `video-to-text-groq` as the free cloud fallback (requires `GROQ_API_KEY`), then `video-to-text-openai` as the paid cloud fallback.

## Limits

- Requires Apple Silicon (M1 / M2 / M3 / M4). Not compatible with Intel Macs, Linux, or Windows.
- Requires `mlx-whisper` package installed separately: `pip install mlx-whisper` (not a default autosearch dependency because it's macOS/ARM-only).
- First run downloads the Whisper model to `~/.cache/huggingface/hub/` (~3 GB for large-v3-turbo).
- Default model: `mlx-community/whisper-large-v3-turbo`. Override via `AUTOSEARCH_MLX_WHISPER_MODEL` env var to any HuggingFace repo or local model path.

This tool does **not** produce a summary. It returns `raw_txt` and subtitles so the runtime AI can decide how to process, summarize, quote, or cite the transcript.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
