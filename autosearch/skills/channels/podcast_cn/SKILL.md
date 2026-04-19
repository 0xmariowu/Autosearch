---
name: podcast_cn
description: Chinese-language podcasts searchable via the Apple iTunes store public API.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [interview, long-form-discussion, experience-report]
  domain_hints: [tech, business, culture, education]
quality_hint:
  typical_yield: low
  chinese_native: true
---

## Overview

`podcast_cn` searches the Apple iTunes China store for Chinese-language podcast shows, which is useful when the query is better served by long-form discussion, founder interviews, or experience-sharing content rather than short articles or social posts.

## Known Quirks

- The iTunes search endpoint returns podcast-show metadata rather than episode-level content, so downstream reranking should expect thin evidence bodies.
- `country=cn` restricts results to the China store catalog and can differ from other Apple storefronts.
- iTunes search responses are often cached server-side for a minute or two, so very recent changes may not appear immediately.
