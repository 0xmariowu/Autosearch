# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: weibo
description: Chinese microblog platform for real-time opinion, trending topics, and event-level commentary in Chinese discourse, via TikHub.
version: 1
languages: [zh, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [via_tikhub]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [real-time, trending, public-opinion, event]
  avoid_for: [academic, tutorial, deep-technical]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, social-trending, public-opinion]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Weibo is a Chinese real-time social platform oriented around trends, public reaction, and event-level commentary. It is useful when the query needs live Chinese discourse, viral narratives, or fast-moving reaction around a person, brand, release, or public event.

For autosearch coverage, this channel gives strong Chinese social recency that blog and Q&A sources cannot provide. It matters because many Chinese public-opinion signals appear on Weibo first, especially around launches, controversies, and trending hashtags.

## When to Choose It

- Choose it for Chinese real-time or trending-topic queries.
- Choose it when event-level commentary and public reaction matter more than depth.
- Choose it for launch buzz, controversy tracking, or fast sentiment checks in Chinese discourse.
- Prefer it over slower Q&A channels when recency is the main routing signal.
- Avoid it for academic lookup, tutorials, or deep technical explanation.

## How To Search

- `via_tikhub` - Query TikHub's `/api/v1/weibo/web/fetch_search` for public Weibo search results using a BYOK `TIKHUB_API_KEY`.
- `via_tikhub` - Extract only post cards from the heterogeneous card list, including direct `card_type=9` results and nested post cards inside `card_type=11` layout groups.
- `via_tikhub` - Normalize author handle, cleaned post text, and canonical web or mobile detail URLs into evidence records.

## Known Quirks

- TikHub access is billed per request at roughly `$0.0036/request`, so broad exploratory use still needs budgeting discipline.
- TikHub generates the visitor session and cookie server-side for this route, so no local Weibo cookies or login state are required.
- The search payload is a heterogeneous card list, and evidence extraction keeps only direct post cards plus nested post cards inside layout groups.
- Trending content is noisy and can include spam, repost farms, or thin commentary.
- Entity ambiguity is common because nicknames, hashtags, and shorthand terms dominate conversation.
