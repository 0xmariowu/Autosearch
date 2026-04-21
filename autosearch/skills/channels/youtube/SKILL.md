# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: youtube
description: Use for video tutorial discovery, conference talks, technical walkthroughs, and product demos.
version: 1
languages: [en, zh, mixed]
methods:
  - id: data_api_search
    impl: methods/data_api_v3.py
    requires: [env:YOUTUBE_API_KEY]
    rate_limit: {per_min: 100, per_hour: 10000}
fallback_chain: [data_api_search]
when_to_use:
  query_languages: [en, zh, mixed]
  query_types: [tutorial, conference-talk, walkthrough, demo]
  avoid_for: [latest-text-news]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [video-audio]
scenarios: [video-discovery, tutorial-video, conference-talk]
model_tier: Fast
experience_digest: experience.md
---

## Overview

YouTube is the broadest video discovery channel in the stack for tutorials, talks, walkthroughs, and product demos. It is useful when the user wants audiovisual explanation, presenter context, or conference footage rather than text-first sources.

For autosearch coverage, this channel adds strong visual learning and long-form talk retrieval across both English and Chinese queries. It matters because many technical explanations are easier to validate from recorded demos and conference sessions than from short text summaries.

## When to Choose It

- Choose it for tutorial and walkthrough queries where visual explanation is part of the answer.
- Choose it for conference talks, keynote sessions, and recorded technical presentations.
- Choose it for product demo discovery across English, Chinese, or mixed-language queries.
- Prefer it when channel reputation and video format matter more than text recency.
- Avoid it for latest text-only news where a news or social channel is a better primary source.

## How To Search (Planned)

- `data_api_search` - Call the YouTube Data API v3 search endpoint with query text, language hints, and video result filters.
- `data_api_search` - Follow up with video metadata fields such as title, channel, duration, publish time, description, and watch URL for normalization.
- `data_api_search` - Rank toward tutorials, talks, and demos instead of general entertainment matches by combining keyword and channel-level cues.

## Known Quirks

- The Data API requires `YOUTUBE_API_KEY`, and quota cost can rise quickly if detail lookups are added later.
- Search quality varies by language and by how creators title multilingual content.
- Video metadata is useful, but true instructional quality still depends on transcript and channel context.
- Recency alone can be misleading because older talks may remain the authoritative explanation.
