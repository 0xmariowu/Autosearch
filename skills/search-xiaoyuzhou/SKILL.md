---
name: search-xiaoyuzhou
description: "Use when the task needs Chinese podcast content — interviews, deep discussions, and expert conversations transcribed to searchable text."
---

# Platform

Xiaoyuzhou (小宇宙) — China's leading podcast platform. Tech interviews, industry discussions, expert conversations.

# When To Choose It

Choose this when:

- need expert interview content from Chinese tech leaders
- searching for in-depth discussions not found in written articles
- looking for industry insider perspectives shared in podcasts

# How To Search

- `site:xiaoyuzhoufm.com {Chinese keywords}`
- Returns episode titles and descriptions (not transcript)

Example queries:
- `site:xiaoyuzhoufm.com AI agent 自进化`
- `site:xiaoyuzhoufm.com 大模型 创业 访谈`

- Download audio
- Transcribe to text via Whisper
- Full-text search on transcript content

# Standard Output Schema

- `source`: `"xiaoyuzhou"`

# Date Metadata

Episodes have publish dates. Extract from snippet.

# Quality Bar

This skill is working when it discovers expert perspectives from podcast conversations that written content doesn't capture.
