---
name: sogou_weixin
description: Chinese WeChat Official Account articles via the public Sogou WeChat search SERP.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 200}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [experience-report, technical-deep-dive, industry-analysis, tutorial]
  domain_hints: [tech, finance, business, culture]
quality_hint:
  typical_yield: high
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, wechat-article, long-form]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Sogou Weixin adds Chinese-language WeChat Official Account discovery through the public Sogou WeChat search results page. It is useful when the query needs Chinese-native tutorials, industry analysis, practitioner writeups, or business commentary that often appears first on public account articles rather than English-language web search surfaces.

## Known Quirks

- The HTML structure is scraped directly and may change without notice.
- Result links can be Sogou redirect URLs such as `weixin.sogou.com/link?url=...` instead of direct article URLs.
- Rate limits stay intentionally strict because aggressive scraping can trigger a `302` captcha flow.
