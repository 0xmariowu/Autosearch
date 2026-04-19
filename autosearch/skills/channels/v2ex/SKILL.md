---
name: v2ex
description: Chinese developer community discussions on programming, tech, and career — useful for native-zh developer sentiment and niche technical troubleshooting.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [developer, programming, career, community, tech-discussion]
  avoid_for: [academic, multimedia, social-lifestyle]
quality_hint:
  typical_yield: medium
  chinese_native: true
---

## Overview

V2EX (www.v2ex.com) is a long-standing Chinese developer community centered on programming, career, products, and niche technical discussion. This channel queries sov2ex.com, a third-party ElasticSearch-style search index over V2EX threads.

## When to Choose It

- Choose it for Chinese developer-scene queries (programming opinions, framework tradeoffs, career discussions, niche troubleshooting).
- Choose it when the query implies programmer-audience in Chinese discourse but zhihu is too broad and weibo is too noisy.
- Avoid for academic, multimedia, or general consumer lifestyle queries.

## How To Search

- `api_search` — Queries `https://www.sov2ex.com/api/search?q=<q>&size=10`. Extracts threads from `hits[*]._source` and constructs canonical thread URLs as `https://www.v2ex.com/t/{id}`.

## Known Quirks

- sov2ex.com is a third-party index, not V2EX's official search. Index freshness depends on that operator; thread titles/bodies are usually current but index lag can be hours.
- V2EX itself has no public search API — the site relies on external indexes or Google site-search. This channel picks sov2ex as the most stable JSON option.
- Developer community, so Chinese + English code snippets mix naturally in content. Language tag is `[zh, mixed]`.
