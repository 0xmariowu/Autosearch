---
name: video-to-text-openai
description: Transcribe video/audio URL or local file to text + SRT using yt-dlp + OpenAI Whisper API. Paid fallback for v2 transcription when Groq is rate-limited or unavailable. Returns raw text and segments; summary is caller's responsibility.
version: 0.1.0
layer: leaf
domains: [video-audio, transcription]
scenarios: [video-to-text, subtitle-extraction, podcast-transcription]
trigger_keywords: [转文字, 字幕, 转录, transcribe, whisper, video to text, 播客字幕]
model_tier: Fast
auth_required: true
auth_env: OPENAI_API_KEY
cost: paid
experience_digest: experience.md
---

Transcribe video or audio into raw text and SRT subtitles through a reliable paid path: `yt-dlp` audio extraction plus OpenAI Whisper. Use this when `video-to-text-groq` is unavailable or quota-exceeded.

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
        "model": "whisper-1",
        "backend": "openai",
    },
    "audio_path": "/tmp/autosearch-video-to-text-openai-.../audio.mp3",
    "source": "https://www.youtube.com/watch?v=example",
}
```

## Failure Modes

- Missing `OPENAI_API_KEY` returns `reason: missing_api_key`.
- Unsupported URLs, network failures, and non-zero `yt-dlp` exits return `reason: yt_dlp_failed`.
- Missing local `ffmpeg` for video conversion returns `reason: ffmpeg_missing`.
- OpenAI rate limits return `reason: rate_limited`.
- Other OpenAI API 4xx or 5xx responses return `reason: openai_api_error`.
- Audio larger than 25 MB returns `reason: audio_too_large`.

Downgrade chain: use `video-to-text-local` on Apple Silicon with LM Studio when cloud transcription is unavailable or unsuitable. When possible, prefer `video-to-text-groq` (free tier) first and fall back to this skill for quality or quota reasons.

## Limits

- Requires a paid OpenAI API key in `OPENAI_API_KEY` (pay-as-you-go, approximately $0.006/min for whisper-1).
- OpenAI rate limits and tier quotas can throttle bursts or long files.
- The upload cap is 25 MB per request; slice long media or use local transcription.
- URL extraction depends on `yt-dlp` support for the target platform and current site behavior.

This tool does **not** produce a summary. It returns `raw_txt` and subtitles so the runtime AI can decide how to process, summarize, quote, or cite the transcript.
