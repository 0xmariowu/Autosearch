---
name: search-bilibili
description: "Use when the task needs Chinese tech video content, tutorials, conference recordings, or developer talks from China's largest video platform."
---

# Platform

Bilibili (B站) — China's largest video platform. Rich in tech tutorials, developer talks, product demos, and conference recordings. Claude's training data has near-zero B站 content.

# When To Choose It

Choose this when:

- need Chinese-language tech tutorials or demos
- searching for product reviews and usage demonstrations
- looking for Chinese tech conference recordings
- the topic has active video creators in Chinese community

# How To Search

## Lite Mode (always available)

Use WebSearch with site filter:
- `site:bilibili.com {Chinese keywords}`
- Returns video titles, descriptions, view counts

Example queries:
- `site:bilibili.com 自进化 AI agent 教程`
- `site:bilibili.com LLM agent 框架 对比 2026`
- `site:bilibili.com Claude Code 使用教程`

## Full Mode (when yt-dlp is installed)

Use yt-dlp to extract metadata and subtitles:
- `yt-dlp --dump-json "https://www.bilibili.com/video/BVxxxxxx"` — metadata
- `yt-dlp --write-auto-subs --sub-lang zh --skip-download URL` — Chinese subtitles
- Search via B站 API: `curl "https://api.bilibili.com/x/web-interface/search/all/v2?keyword={query}"`

Full mode provides: view count, like count, subtitle text, upload date, creator info.

Check if yt-dlp is available: `which yt-dlp`

# Standard Output Schema

- `source`: `"bilibili"`

# Date Metadata

B站 videos have upload dates. Extract from snippet or API response.

# Quality Bar

This skill is working when it discovers Chinese video content (tutorials, demos, talks) that no text-based English search would find.
