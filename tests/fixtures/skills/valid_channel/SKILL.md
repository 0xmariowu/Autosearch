<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
---
name: valid_channel
description: Use for bilingual paper-style searches that may need a detail lookup.
version: 1
languages: [zh, en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: [env:ARXIV_TOKEN]
    rate_limit:
      per_min: 30
      per_hour: 500
  - id: api_detail
    impl: methods/api_detail.py
    requires: [cookie:arxiv_session]
    rate_limit:
      per_min: 10
fallback_chain: [api_search, api_detail]
when_to_use:
  query_languages: [zh, en]
  query_types: [academic-papers, literature-review]
  domain_hints: [citations, scholarly-search]
  avoid_for: [real-time-news]
quality_hint:
  typical_yield: medium-high
  chinese_native: false
layer: leaf
domains: [academic]
scenarios: [paper-search, detail-hydration]
model_tier: Standard
tier: 1
fix_hint: "autosearch configure ARXIV_TOKEN <value>"
---

Prefer the search endpoint first, then hydrate selected records with the detail method.
Keep body prose descriptive only.
