# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: douyin
description: Chinese short-form video platform for trending content, product launches, consumer commentary, and lifestyle segments in Chinese.
version: 1
languages: [zh]
methods:
  - id: via_douyin_mcp
    impl: methods/via_douyin_mcp.py
    requires: [mcp:douyin-mcp-server, cookie:douyin]
    rate_limit: {per_min: 10, per_hour: 120}
fallback_chain: [via_douyin_mcp]
when_to_use:
  query_languages: [zh]
  query_types: [trending, short-form, product-launch, consumer-commentary, lifestyle]
  avoid_for: [technical-deep-dive, academic]
quality_hint:
  typical_yield: medium
  chinese_native: true
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

- `via_douyin_mcp` - Use the `douyin-mcp-server` route with authenticated session access to search clips, creators, and topical results.
- `via_douyin_mcp` - Normalize clip title or caption, creator identity, publish time, engagement counts, and canonical share URL.
- `via_douyin_mcp` - Keep extraction lightweight and ranking recency-aware because the platform is heavily short-form and trend-driven.

## Known Quirks

- The planned route depends on both `mcp:douyin-mcp-server` and `cookie:douyin`.
- Short-form content is high-noise and can be weak on factual detail without corroboration.
- Trend vocabulary changes quickly, so rigid keyword matching will miss some relevant clips.
- Platform defenses and session expiry can make access more brittle than standard web APIs.
