# Skill Attribution
> Source: self-written for TikHub channel expansion task on 2026-04-19.

---
name: kuaishou
description: Chinese short-video platform with lifestyle, humor, regional culture, and product demos, via TikHub.
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
  query_types: [short-video, lifestyle, regional-culture, product-demo]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, short-video, lower-tier-market]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Kuaishou is a Chinese short-video platform with strong coverage of everyday lifestyle content, regional culture, humor, and product demonstration clips. It is useful when the query needs Chinese-native short-form video evidence outside the more trend-heavy Douyin lane.

## When to Choose It

- Choose it for Chinese or mixed-language short-video searches with everyday or regional context.
- Choose it for lifestyle, humor, and product-demo coverage where creator clips are likely to surface first.
- Choose it when you want Chinese short-form signals that may differ from Weibo text chatter or Xiaohongshu notes.
- Avoid it for deep technical explanation or formal reporting.

## How To Search

- `via_tikhub` - Use TikHub's comprehensive Kuaishou search endpoint with first-page parameters fixed to broad keyword coverage.
- `via_tikhub` - Skip non-video cards, keep only feeds that expose a real `photo_id`, and build canonical Kuaishou web URLs from that identifier.
- `via_tikhub` - Normalize captions into concise snippets and label results with the creator name when present.

## Known Quirks

- TikHub access is billed per request, so this channel should not be used for wide exploratory fan-out.
- Search responses mix headers, ads, and other non-post cards, so extraction intentionally drops a lot of items.
- Captions can be terse, slang-heavy, or empty, which limits snippet quality.
