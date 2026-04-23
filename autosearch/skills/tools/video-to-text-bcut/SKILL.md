---
name: video-to-text-bcut
description: Transcribe video/audio URL to text + word-level timestamps using Bilibili Bcut ASR API (free, no API key). Preferred for Chinese content — Bcut gives character-level timestamps vs Whisper word-level. Returns text + segments [{start, end, text}]. Requires yt-dlp + ffmpeg.
version: 0.1.0
layer: leaf
domains: [video-audio, transcription, chinese]
scenarios: [video-to-text, bilibili-transcription, chinese-subtitle]
trigger_keywords: [转文字, 字幕, 转录, bcut, 必剪, bilibili transcribe, 中文转录]
model_tier: Fast
auth_required: false
cost: free
---

Uses Bilibili's public Bcut ASR API (no login required):
1. yt-dlp extracts audio from video URL
2. ffmpeg converts to 16kHz mono WAV
3. Bcut API: upload → create task → poll → get word-level timestamps
4. SegmentBuilder aggregates chars into sentence-level segments

## Output

```json
{
  "ok": true,
  "text": "完整转录文本",
  "segments": [{"start": 0.0, "end": 2.5, "text": "第一句话。"}],
  "duration_seconds": 120.5,
  "source": "https://..."
}
```

# Quality Bar

- Returns segments with `start`/`end` in seconds
- Handles Bcut polling timeout gracefully (returns partial text)
- Falls back gracefully if Bcut fails
