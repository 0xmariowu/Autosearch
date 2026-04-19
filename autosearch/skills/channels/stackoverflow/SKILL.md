---
name: stackoverflow
description: Programming Q&A with community-voted answers across 200+ technical tags via api.stackexchange.com.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 300}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [programming-error, how-to, api-usage, technical-reference]
  domain_hints: [software, programming, devops]
quality_hint:
  typical_yield: high
  chinese_native: false
---

## Overview

Stack Overflow provides high-signal programming Q&A, code-level troubleshooting, API usage guidance, and technical reference material via the public Stack Exchange API. It is especially valuable when the query is about concrete errors, implementation details, or how practitioners resolved a specific development problem in production code.

## Known Quirks

- Unauthenticated requests are limited to roughly 300 requests per day per IP, so this channel uses a conservative rate limit.
- The request must include `filter=withbody` or the API omits `body_markdown`, which makes evidence snippets much less useful.
- Because unauthenticated quota is IP-scoped, parallel E2B or shared-runner executions can collide even when one local run is well behaved.
