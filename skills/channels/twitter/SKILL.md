# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: twitter
description: Use for real-time public commentary, AI researcher threads, and announcements when query targets current events or expert takes.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: [env:TWITTER_BEARER_TOKEN]
    rate_limit: {per_min: 10, per_hour: 100}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [real-time, expert-take, announcement, researcher-thread]
  avoid_for: [academic-papers, deep-technical-tutorial]
quality_hint:
  typical_yield: medium
  chinese_native: false
---

## Overview

Twitter is a real-time public commentary channel for announcements, expert reactions, and short-form discussion threads. It is useful when the query targets current events, AI researcher commentary, launch announcements, or ongoing public conversation that has not yet settled into longer-form coverage.

For autosearch, this channel expands timely coverage beyond static web pages and official press posts. It matters because expert accounts and organizational announcement threads often appear first here, even when a later route will be needed for higher-confidence confirmation.

## When to Choose It

- Choose it for current-event and announcement queries where timing matters.
- Choose it for AI researcher threads, conference reactions, or short expert takes.
- Choose it when the user wants public commentary around a model release, paper release, or product launch.
- Use it for mixed-language queries only when the likely evidence source is still English-dominant public discussion.
- Avoid it for academic paper retrieval or deep tutorial-style instruction.

## How To Search (Planned)

- `api_search` - Use the official recent search API with keyword, account, hashtag, and recency filters under the assumed Basic tier route.
- `api_search` - Normalize posts around author handle, created time, engagement counts, thread linkage, and canonical status URL.
- `api_search` - Prefer high-signal accounts such as researchers, labs, maintainers, and official product teams when ranking evidence.

## Known Quirks

- This route is intentionally provisional; plan F006 may replace or reshape the implementation strategy.
- Official API quotas are relatively tight, so broad exploratory queries need careful budgeting.
- Search results can be noisy around viral topics and ambiguous entity names.
- Important evidence may live inside threads or quote posts rather than standalone posts.
