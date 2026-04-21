---
name: reddit
description: Reddit community discussions, user experience reports, and topic debates via the public search.json endpoint.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 300}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [community-opinion, experience-report, troubleshooting, debate]
  domain_hints: [software, tech, product, consumer]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [community-en]
scenarios: [community-opinion, user-experience, comparison]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Reddit adds public community discussion, user experience reports, troubleshooting threads, and debate-oriented evidence through the unauthenticated `search.json` endpoint. It is useful when the query needs candid practitioner commentary or consumer sentiment that is less polished than docs, vendor content, or editorial articles.

## Known Quirks

- Reddit blocks default client signatures, so requests must set a non-empty custom User-Agent.
- The public endpoint is relatively open, but this channel keeps a conservative rate limit to stay polite.
- The unauthenticated search API supports broad search well enough for this use case, but it does not provide reliable time-range filtering.
