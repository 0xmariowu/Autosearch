# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: douyin
description: Chinese short-video content with product demos, tech reviews, and viral trends, via TikHub.
version: 1
languages: [zh]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [via_tikhub]
when_to_use:
  query_languages: [zh]
  query_types: [trending, short-form, product-launch, consumer-commentary, lifestyle]
  avoid_for: [technical-deep-dive, academic]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, short-video, viral-content]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Douyin is a Chinese short-form video platform geared toward trends, launches, fast product reactions, and lifestyle content. It is useful when the query needs highly current Chinese consumer commentary or creator-driven short-form coverage.

For autosearch coverage, this channel adds a format and audience segment that neither Weibo nor Xiaohongshu fully captures. It matters because some product launches and viral consumer narratives spread first through short-form video rather than text posts.

## When to Choose It

- Choose it for Chinese trending or short-form video queries.
- Choose it for product launch buzz, consumer commentary, and fast lifestyle coverage.
- Choose it when creator clips and short demonstrations are more relevant than long-form explanation.
- Prefer it over deeper video channels when immediacy and viral spread matter most.
- Avoid it for technical deep dives or academic-style research questions.

## How To Search (Planned)

- `via_tikhub` - Use TikHub's paid Douyin search API to discover public video results by keyword without relying on local session cookies.
- `via_tikhub` - Normalize caption text, creator nickname, canonical share URL, and fallback video URL from `aweme_id` when the share link is missing.
- `via_douyin_mcp` - Use the `douyin-mcp-server` route with authenticated session access to search clips, creators, and topical results.
- `via_douyin_mcp` - Normalize clip title or caption, creator identity, publish time, engagement counts, and canonical share URL.
- `via_douyin_mcp` - Keep extraction lightweight and ranking recency-aware because the platform is heavily short-form and trend-driven.

## Known Quirks

- TikHub billing applies per request, so this route should stay deliberate rather than broad exploratory search.
- TikHub search currently exposes caption text only; it does not provide transcript or in-video OCR extraction.
- Engagement stats are present in the payload but are not yet mapped into `Evidence`; they remain a future rerank signal.
- The planned route depends on both `mcp:douyin-mcp-server` and `cookie:douyin`.
- Short-form content is high-noise and can be weak on factual detail without corroboration.
- Trend vocabulary changes quickly, so rigid keyword matching will miss some relevant clips.
- Platform defenses and session expiry can make access more brittle than standard web APIs.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
