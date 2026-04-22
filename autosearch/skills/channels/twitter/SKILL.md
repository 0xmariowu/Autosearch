# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: twitter
description: Real-time public discourse including product launches, tech announcements, and breaking news, via TikHub.
version: 1
languages: [en, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
  - id: api_search
    impl: methods/api_search.py
    requires: [env:TWITTER_BEARER_TOKEN]
    rate_limit: {per_min: 10, per_hour: 100}
fallback_chain: [via_tikhub, api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [current-events, product-launch, breaking-news, developer-announcement]
  domain_hints: [tech, politics, startups, product]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [social-career]
scenarios: [social-signal, expert-opinion, announcement]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Twitter is a real-time public discussion channel for launches, breaking updates, tech commentary, and expert reactions. It is useful when the query depends on timely public discourse, especially around product releases, developer announcements, or topics where the first useful signal appears in short-form posts before longer coverage lands.

## Known Quirks

- TikHub access is billed per request, so broad exploratory use still needs budgeting discipline.
- `search_type=Top` surfaces the most relevant tweets; `Latest` is available later if we need chronological coverage.
- Twitter's nested timeline payload is fragile, so extraction is defensive and silently drops entries that do not match the expected shape.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
