---
name: wikipedia
description: Authoritative encyclopedia articles via the Wikipedia Action API (English edition).
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 60, per_hour: 2000}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [definition, background, factual-overview, historical]
  domain_hints: [science, history, culture, general-knowledge]
quality_hint:
  typical_yield: high
  chinese_native: false
---

## Overview

Wikipedia provides authoritative encyclopedia-style background, definitions, factual overviews, and historical context through the English Wikipedia Action API. It is useful when the query needs broad, neutral summary coverage across science, history, culture, and general-knowledge topics before drilling into more specialized sources.

## Known Quirks

- English Wikipedia only in v1; Chinese Wikipedia support is a future follow-up.
- Search results only expose list-API snippets, not full article bodies.
- Requests must include a policy-compliant User-Agent with contact information per Wikimedia requirements.
