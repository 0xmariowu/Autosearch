---
name: ddgs
description: "DuckDuckGo Search — free general web search with no auth, use as broad default for any English or mixed query."
version: 1
languages: [en, mixed]
methods:
  - id: text_search
    impl: methods/api.py
    requires: []
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [text_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [general, news, product, how-to]
  avoid_for: [deep-technical-papers, chinese-content]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [generic-web]
scenarios: [general-search, fallback, keyword-lookup]
model_tier: Fast
experience_digest: experience.md
---

## Overview

General-purpose web search via DuckDuckGo. No API key required, no cookie. Serves as the always-on broad default for English and mixed-language queries where more specialized channels may not cover the topic.

## When to Choose It

- First-line web discovery before specialized channels
- Queries where platform-specific coverage (github, arxiv, HN) is unlikely to help
- Mixed-domain topics that need broad source variety

## How To Search (Planned)

`text_search` — calls the `ddgs` PyPI package (renamed from `duckduckgo-search`). Sync API wrapped in `asyncio.to_thread`. Returns `{title, href, body}` hits mapped to Evidence with 500-char snippet truncation.

## Known Quirks

- DDGS occasionally returns empty results during rate limit; channel returns `[]` and logs warn without crashing pipeline.
- Result URLs may redirect; we keep the original href (no unwrap).
