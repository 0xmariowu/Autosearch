# Skill Attribution
> Source: self-written for TikHub channel expansion task on 2026-04-19.

---
name: tiktok
description: Global short-video platform with creator content, product demos, viral trends, and topical reactions, via TikHub.
version: 1
languages: [en, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [via_tikhub]
when_to_use:
  query_languages: [en, mixed]
  query_types: [product-launch, viral-content, creator-content, short-video, trend]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [video-audio]
scenarios: [short-video, viral-demo]
model_tier: Fast
experience_digest: experience.md
---

## Overview

TikTok is a global short-video platform centered on creator-led clips, topical reactions, product demos, and viral formats. It is useful when the query depends on short-form creator coverage or fast-moving audience attention rather than long-form articles.

## When to Choose It

- Choose it for creator-driven short-video coverage in English or mixed-language searches.
- Choose it for product launch reactions, viral topics, and topical creator commentary.
- Choose it when the likely first useful signal is a short clip rather than a blog post or newsroom article.
- Avoid it when the task depends on deep factual explanation or long-form sourcing.

## How To Search

- `via_tikhub` - Use TikHub's TikTok general search endpoint with fixed first-page parameters tuned for broad keyword discovery.
- `via_tikhub` - Normalize caption text, prefer TikHub's canonical `share_url`, and fall back to a constructed `@handle/video/id` URL when needed.
- `via_tikhub` - Return lightweight evidence with creator-derived titles and clipped snippets suitable for routing and synthesis.

## Known Quirks

- TikHub access is billed per request, so this route should stay deliberate.
- Search results are clip-oriented and do not include transcript extraction.
- Captions can be sparse or mostly emoji, which limits snippet quality.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
