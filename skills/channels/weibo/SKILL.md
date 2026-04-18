# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: weibo
description: Chinese microblog platform for real-time opinion, trending topics, and event-level commentary in Chinese discourse.
version: 1
languages: [zh, mixed]
methods:
  - id: mobile_api_search
    impl: methods/mobile_api.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
  - id: api_detail
    impl: methods/api_detail.py
    requires: [cookie:weibo]
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [mobile_api_search, api_detail]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [real-time, trending, public-opinion, event]
  avoid_for: [academic, tutorial, deep-technical]
quality_hint:
  typical_yield: medium
  chinese_native: true
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

## How To Search (Planned)

- `mobile_api_search` - Query mobile-oriented search endpoints for posts, keywords, and trending topic matches without assuming authenticated detail access.
- `api_detail` - Fetch richer post metadata and engagement details when a valid `cookie:weibo` is present.
- `api_detail` - Normalize post author, created time, reposts, comments, likes, and canonical mobile or web URLs.

## Known Quirks

- Search endpoints can be unstable and rate-limited during major events.
- Detail access is more reliable with a valid `cookie:weibo`, especially for older or restricted posts.
- Trending content is noisy and can include spam, repost farms, or thin commentary.
- Entity ambiguity is common because nicknames, hashtags, and shorthand terms dominate conversation.
