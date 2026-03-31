---
name: search-youtube
description: "Use when the task needs video tutorials, tech talks, conference presentations, or product demos with extractable transcripts."
---

# Platform

YouTube — world's largest video platform. Tech talks, conference recordings (NeurIPS, ICLR), product demos, tutorials. Transcript extraction enables searching video CONTENT, not just titles.

# When To Choose It

Choose this when:

- need conference talk recordings and presentations
- looking for product demos and walkthroughs
- want tutorial content with code demonstrations
- searching for tech podcasts and interviews on YouTube

# How To Search

- `site:youtube.com {keywords}`

Example queries:
- `site:youtube.com "self-evolving agent" talk 2026`
- `site:youtube.com NeurIPS 2025 agent memory`
- `site:youtube.com LLM tool use tutorial`

- `yt-dlp --dump-json URL` — full metadata (title, description, upload date, view count, duration)
- `yt-dlp --write-auto-subs --sub-lang en --skip-download URL` — English transcript
- `yt-dlp --flat-playlist --dump-json "ytsearch10:{query}"` — search top 10 results

Full mode provides: actual transcript text (searchable content!), precise upload date, engagement metrics.

# Standard Output Schema

- `source`: `"youtube"`

# Date Metadata

YouTube videos have upload dates. Extract from snippet or yt-dlp metadata.

# Quality Bar

This skill is working when it discovers video content (explanations, demos, Q&A) that text-based searches miss entirely.
