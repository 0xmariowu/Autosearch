---
name: pubmed
description: Use for biomedical and life-science literature searches when query expects PubMed articles, clinical trials, or medical research papers.
version: 1
languages: [en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 300}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [academic, medical, clinical, literature-review]
  avoid_for: [news, product-review, real-time, programming]
quality_hint:
  typical_yield: medium-high
  chinese_native: false
layer: leaf
domains: [academic, medical]
scenarios: [medical-research, clinical-trial, drug-review, biomedical-paper]
model_tier: Fast
---

## Overview

PubMed is NCBI's free search engine for biomedical and life sciences literature. No API key required. Best for medical research, clinical trials, drug studies, and biological science papers.

## When to Choose It

- Biomedical, clinical, or pharmaceutical research queries
- Searching for peer-reviewed medical journal articles
- Finding abstracts with DOI or PubMed ID for citation

## How To Search

Uses E-utilities API: `esearch.fcgi` to get IDs, `esummary.fcgi` to fetch metadata.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
