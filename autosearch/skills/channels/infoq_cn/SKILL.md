---
name: infoq_cn
description: Chinese engineering articles covering architecture, AI, and enterprise tech from InfoQ 中文, via public RSS feed.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 100}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [architecture, technical-deep-dive, industry-case-study, news]
  domain_hints: [tech, software, ai, enterprise]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [cn-tech]
scenarios: [chinese-tech-media, enterprise-architecture]
model_tier: Fast
experience_digest: experience.md
---

## Overview

InfoQ 中文 adds Chinese-language engineering and enterprise technology coverage through its public RSS feed, making it useful for architecture discussions, AI platform work, deep technical explainers, and industry case studies when the query is in Chinese or mixed language.

## Known Quirks

- The feed is unfiltered and only returns the latest articles, so this channel applies client-side query token matching after fetch.
- RSS only exposes headline and summary fields, not the full article body.
- `pubDate` can be stale or less reliable than on-page timestamps for feed-only sources.
