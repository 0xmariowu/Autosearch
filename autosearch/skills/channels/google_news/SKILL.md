---
name: google_news
description: Current news headlines aggregated across publishers via Google News RSS (English US feed).
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [current-events, news, recent-development, company-announcement]
  domain_hints: [tech, politics, business, science, health]
quality_hint:
  typical_yield: high
  chinese_native: false
layer: leaf
domains: [generic-web]
scenarios: [recent-news, time-sensitive]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Google News adds current editorial coverage aggregated across many publishers through the public RSS search feed. It is useful when the query is about recent events, announcements, or developing stories and the search should stay broad across mainstream news outlets without depending on a private API key.

## Known Quirks

- RSS only provides headlines and short summaries, not full article bodies.
- The `link` field is a Google News redirect URL rather than the direct publisher URL, and v1 keeps it intentionally to avoid lossy or failure-prone decoding.
- The feed is hardcoded to `hl=en-US&gl=US&ceid=US:en` for v1; non-English and non-US market variants are a follow-up.
