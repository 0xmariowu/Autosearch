---
name: searxng
description: Use for general web meta-search via a local SearXNG instance when broad multi-engine web coverage is needed and SEARXNG_URL is configured.
version: 1
languages: [en, zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: [env:SEARXNG_URL]
    rate_limit: {per_min: 30, per_hour: 1000}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, zh, mixed]
  query_types: [web, news, general, broad-coverage]
  avoid_for: [academic, chinese-ugc-specific, video]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [generic-web]
scenarios: [broad-web-search, news, general-research]
model_tier: Fast
---

## Overview

SearXNG is a self-hosted meta-search engine aggregating results from 70+ sources (Google, Bing, DuckDuckGo, etc.). Requires a local SearXNG instance reachable at `SEARXNG_URL` (default: `http://localhost:8080`). Free, no external API key.

## When to Choose It

- Broad web coverage without a specific platform focus
- News and current events research
- Fallback when other channels return insufficient results

## How To Search

POST/GET to `$SEARXNG_URL/search?q=<query>&format=json`.
