---
name: channels-video-audio
description: Video / audio discovery and transcription — YouTube search, RSS video feeds, and the v2 transcription trio (groq / openai / local) plus yt-dlp dependency.
layer: group
domains: [video-audio, transcription]
scenarios: [video-discovery, podcast-transcription, video-to-text, subtitle-extraction]
model_tier: Fast
experience_digest: experience.md
---

# Video & Audio Channels

Find and transcribe video / audio content. Pairs with `channels-chinese-ugc` (`search-bilibili`, `search-xiaoyuzhou`) for Chinese-platform coverage.

## Leaf skills — discovery

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-youtube` | YouTube video search | Fast | free |
| `search-rss` | RSS / podcast feed polling | Fast | free |

## Leaf skills — transcription (choose by environment)

| Leaf | Best for | Tier | Auth / cost |
|---|---|---|---|
| `video-to-text-groq` | Default; free Groq Whisper API | Fast | `GROQ_API_KEY` (free) |
| `video-to-text-openai` | Paid fallback when Groq is rate-limited | Fast | `OPENAI_API_KEY` (paid ~$0.006/min) |
| `video-to-text-local` | Apple Silicon + mlx-whisper installed | Fast | offline, free |

## Routing notes

- The runtime AI picks the transcription skill based on available env vars: prefer `video-to-text-local` on Apple Silicon if `mlx-whisper` is installed; else `video-to-text-groq` if `GROQ_API_KEY` is set; else `video-to-text-openai`.
- Transcription skills return `raw_txt` and SRT; **they do not summarize**. The runtime AI synthesizes from `raw_txt`.
- For Chinese video / podcast content, combine with `channels-chinese-ugc` (`search-bilibili`, `search-xiaoyuzhou`).
