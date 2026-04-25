---
name: xueqiu
description: Chinese stock market platform — stock search, trending posts, hot stock rankings. Use for financial/investment queries in Chinese.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: [env:XUEQIU_COOKIES]
    rate_limit: {per_min: 10, per_hour: 100}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [stock, investment, finance, market]
  domain_hints: [finance, investment, stocks, china-market]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [finance]
scenarios: [stock-search, hot-posts, investment-research]
model_tier: Fast
experience_digest: experience.md
tier: 2
fix_hint: "autosearch login xueqiu"
---

## Overview

Xueqiu (雪球) is China's leading stock discussion and investment platform. Useful for stock quotes, investor sentiment, trending financial topics, and hot stock rankings.

## When to Choose It

- Chinese stock (A-share, HK, US) searches by name or ticker
- Trending investor discussions and hot posts
- Hot stock rankings (popularity board)

## Known Quirks

- Requires `xq_a_token` cookie for authenticated requests — run `autosearch login xueqiu`
- Rate limiting: max 10 requests/min to avoid triggering anti-bot


# Quality Bar

- Evidence has non-empty url and title.
- Cookie invalid or expired -> ChannelAuthError surfaces auth_failed.
