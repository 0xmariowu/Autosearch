---
name: kr36
description: Chinese tech business news, startup funding, and industry analysis from 36kr.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [news, startup-funding, industry-analysis, product-launch]
  domain_hints: [tech, business, finance, consumer]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [cn-tech]
scenarios: [chinese-tech-media, startup-coverage, funding]
model_tier: Fast
experience_digest: experience.md
---

## Overview

36kr adds Chinese-language technology and business coverage through the public search results page, with strong value for startup funding updates, product launches, sector analysis, and broader tech-industry reporting that often surfaces earlier in Chinese media than on English aggregators.

## Known Quirks

- The search page is a SPA with server-rendered snippets only, so this channel returns SERP metadata rather than full article bodies.
- The visible HTML layout is scraped directly and may be volatile.
- If the search endpoint or SSR markup changes, the channel logs a warning and returns an empty result set.
