# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: xiaohongshu
description: Chinese lifestyle and consumer product platform — use when query is Chinese and targets product recommendations, lifestyle experiences, or consumer reviews.
version: 1
languages: [zh]
methods:
  - id: via_mcporter
    impl: methods/via_mcporter.py
    requires: [mcp:mcporter, cookie:xiaohongshu]
    rate_limit: {per_min: 5, per_hour: 60}
  - id: via_xhs_cli
    impl: methods/via_xhs_cli.py
    requires: [binary:xhs-cli, cookie:xiaohongshu]
    rate_limit: {per_min: 5, per_hour: 60}
fallback_chain: [via_mcporter, via_xhs_cli]
when_to_use:
  query_languages: [zh]
  query_types: [product-recommendation, lifestyle, consumer-review, food, travel]
  avoid_for: [technical, academic, code]
quality_hint:
  typical_yield: medium
  chinese_native: true
---

## Overview

Xiaohongshu is a Chinese lifestyle and consumer discovery platform centered on short posts, shopping notes, travel tips, and product impressions. It is useful when the user wants Chinese-language recommendation content, daily-life experience reports, or creator-style product reviews.

For autosearch coverage, this channel adds consumer and lifestyle evidence that is poorly covered by developer-oriented sources. It matters because many Chinese purchase decisions, travel planning queries, and beauty or gadget recommendation workflows depend on Xiaohongshu-native content.

## When to Choose It

- Choose it for Chinese product recommendation and consumer review queries.
- Choose it for food, travel, beauty, lifestyle, and everyday experience lookup.
- Choose it when creator-style usage notes matter more than formal specifications.
- Prefer it for Chinese consumer intent rather than technical or code-heavy questions.
- Avoid it for academic, engineering deep-dive, or implementation detail queries.

## How To Search (Planned)

- `via_mcporter` - Route search through the `mcporter` MCP bridge with authenticated Xiaohongshu session access for note discovery and metadata extraction.
- `via_xhs_cli` - Use a local `xhs-cli` executable plus authenticated cookies as a fallback when MCP access is unavailable.
- `via_xhs_cli` - Normalize note title, author, engagement counts, tags, and canonical note URL for downstream evidence ranking.

## Known Quirks

- Both planned methods require an authenticated Xiaohongshu cookie; anonymous access is unreliable.
- Rate budgets are intentionally conservative because anti-automation defenses are common.
- Content is recommendation-heavy and can skew toward influencer aesthetics instead of balanced comparison.
- Search quality is best for native Chinese product and lifestyle terminology, not English technical jargon.
