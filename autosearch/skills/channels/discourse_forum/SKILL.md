---
name: discourse_forum
description: Use for public Discourse-based community discussions, especially Linux DO, when queries need Chinese AI/dev forum posts and native operator troubleshooting.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 400}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [community, developer, product-feedback, tech-discussion, chinese-ugc]
  avoid_for: [academic, consumer-lifestyle, multimedia]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [developer-community, ai-tools, troubleshooting, public-forum]
model_tier: Fast
---

## Overview

Public Discourse communities are a distinct forum surface: long-form troubleshooting, operator notes, product limitations, and community-native workarounds. This channel starts with Linux DO as the first built-in source.

## How To Search

- `api_search` — queries the site's public Discourse search endpoint and maps topic-oriented results into canonical topic URLs.

## Known Quirks

- Discourse search payloads can vary by site version and plugin stack.
- Some public forums may block anonymous search or require region-specific network access.
- v1 ships with a built-in Linux DO preset only; more Discourse communities can be added later through site presets.

# Quality Bar

- Evidence items have non-empty title and url.
- Multiple posts from the same topic deduplicate to one evidence item.
- HTTP or payload failures degrade to an empty result list.
