---
name: openalex
description: Search scholarly works through OpenAlex's public works search API with open-access URL fallback.
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
  query_types: [academic-paper, citation, survey, research]
  domain_hints: [academia, literature-review, scholarly-search, citations]
quality_hint:
  typical_yield: high
  chinese_native: false
---

## Overview

OpenAlex provides broad scholarly metadata coverage across papers, preprints, chapters, and other research outputs through a free public API. It is useful when the query needs paper titles, authors, abstracts, citation counts, and open-access landing pages across a much larger corpus than a single publisher or preprint server.

## When to Choose It

- Choose it for paper discovery, survey-building, citation-oriented lookup, and research-heavy English or mixed-language queries.
- Choose it when open-access landing pages or DOI links are valuable because the planner may need a direct path from metadata to readable paper pages.
- Choose it when the search should cover both preprints and published literature rather than only one repository.

## How To Search

- `api_search` - Calls `https://api.openalex.org/works` with the `search` query parameter and `per-page=10`, then maps `results` entries into normalized evidence.
- `api_search` - Reconstructs abstract text from OpenAlex's positional `abstract_inverted_index` representation before building snippet and content fields.
- `api_search` - Resolves evidence URLs in priority order: `best_oa_location.landing_page_url`, then `doi`, then the OpenAlex `id` fallback.

## Known Quirks

- Abstracts are returned as an inverted index rather than plain prose, so the channel reconstructs them into normal text before truncation.
- Use OpenAlex's `search` query parameter for keyword search, not `filter`, which is for metadata filtering syntax.
- OpenAlex is rate-limited to roughly 10 requests per second without auth, and the single-call-per-subquery pattern here stays well under that ceiling.
