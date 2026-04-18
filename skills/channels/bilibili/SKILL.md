# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: bilibili
description: Chinese video platform for tech tutorials, comparison videos, gaming/ACG, and expert breakdowns — use for visual content in Chinese.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
  - id: api_video_detail
    impl: methods/api_video_detail.py
    requires: [cookie:bilibili]
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [api_search, api_video_detail]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [tutorial-video, comparison, breakdown, tech-opinion]
  avoid_for: [text-only-query, academic-papers]
quality_hint:
  typical_yield: medium
  chinese_native: true
---

## Overview

Bilibili is a Chinese video platform with strong coverage in tutorials, hardware comparisons, software explainers, gaming, and creator-led technical commentary. It is useful when the user wants Chinese-language visual content rather than text-first references.

For autosearch coverage, this channel fills a gap between global video search and Chinese-native creator ecosystems. It matters because many Chinese tutorials, teardown videos, and side-by-side product breakdowns are published on Bilibili long before they appear elsewhere.

## When to Choose It

- Choose it for Chinese tutorial-video and breakdown queries.
- Choose it for device comparisons, creator explainers, and tech-opinion in video form.
- Choose it when visual demonstration matters more than short text description.
- Prefer it over YouTube when the target audience, terminology, or creator ecosystem is Chinese-native.
- Avoid it for pure text lookup or formal academic paper search.

## How To Search (Planned)

- `api_search` - Call Bilibili search endpoints for videos and creators using Chinese or mixed query text, then rank by topical relevance and engagement.
- `api_video_detail` - Fetch richer metadata for shortlisted videos with authenticated detail access when `cookie:bilibili` is available.
- `api_video_detail` - Normalize title, uploader, publish time, duration, play stats, and canonical video URL.

## Known Quirks

- Basic search works without auth, but video detail and richer metadata are more stable with a valid cookie.
- Many results are entertainment-adjacent, so ranking must distinguish tech and tutorial intent carefully.
- Some high-signal tutorials use slang or fandom terminology that generic keyword matching may miss.
- Video popularity can dominate search ordering even when a smaller creator has the better explanation.
