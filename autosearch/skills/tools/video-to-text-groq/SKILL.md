---
name: video-to-text-groq
description: Transcribe video/audio URL or local file to text + SRT using yt-dlp + Groq Whisper API (free tier). Preferred default for v2 transcription. Returns raw text and segments; summary is caller's responsibility.
version: 0.1.0
layer: leaf
domains: [video-audio, transcription]
scenarios: [video-to-text, subtitle-extraction, podcast-transcription]
trigger_keywords: [转文字, 字幕, 转录, transcribe, whisper, video to text, 播客字幕]
model_tier: Fast
auth_required: true
auth_env: GROQ_API_KEY
cost: free
experience_digest: experience.md
---

Transcribe video or audio into raw text and SRT subtitles through the cheapest fast path: `yt-dlp` audio extraction plus Groq Whisper.

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
        "model": "whisper-large-v3",
        "backend": "groq",
    },
    "audio_path": "/tmp/autosearch-video-to-text-groq-.../audio.mp3",
    "source": "https://www.youtube.com/watch?v=example",
}
```

## Failure Modes

- Missing `GROQ_API_KEY` returns `reason: missing_api_key`.
- Unsupported URLs, network failures, and non-zero `yt-dlp` exits return `reason: yt_dlp_failed`.
- Missing local `ffmpeg` for video conversion returns `reason: ffmpeg_missing`.
- Groq rate limits return `reason: rate_limited`.
- Other Groq API 4xx or 5xx responses return `reason: groq_api_error`.
- Audio larger than 25 MB returns `reason: audio_too_large`.

Downgrade chain: use `video-to-text-openai` as the paid fallback, then `video-to-text-local` on Apple Silicon with LM Studio when cloud transcription is unavailable or unsuitable.

## Limits

- Requires a free Groq API key in `GROQ_API_KEY`.
- Groq free-tier rate limits can throttle bursts or long files.
- The free-tier audio upload cap is 25 MB; slice long media or use local transcription.
- URL extraction depends on `yt-dlp` support for the target platform and current site behavior.

This tool does **not** produce a summary. It returns `raw_txt` and subtitles so the runtime AI can decide how to process, summarize, quote, or cite the transcript.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
