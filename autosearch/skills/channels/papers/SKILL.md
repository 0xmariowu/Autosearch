# Skill Attribution
> Source: self-written for task F203.

---
name: papers
description: Multi-source academic paper search (arxiv, pubmed, biorxiv, medrxiv, google_scholar) via paper-search-mcp.
version: 1
languages: [en, mixed]
methods:
  - id: via_paper_search
    impl: methods/via_paper_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [via_paper_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [academic-paper, research, technical-deep-dive]
  domain_hints: [science, medicine, biology, cs, physics, chem]
quality_hint:
  typical_yield: high
  chinese_native: false
layer: leaf
domains: [academic]
scenarios: [paper-collection, survey]
model_tier: Fast
experience_digest: experience.md
---

## Overview

`papers` is the broad academic search channel for research-heavy queries that benefit from cross-checking multiple paper sources instead of relying on a single index. It aggregates arXiv, PubMed, bioRxiv, medRxiv, and Google Scholar so the planner can surface preprints, medical literature, and general scholarly coverage through one paper-oriented channel.

## Known Quirks

- Google Scholar can rate-limit or degrade if queried too aggressively, so this channel uses conservative limits.
- bioRxiv can be flaky on some requests and may intermittently return no results even when related sources succeed.
- Overlap with the standalone `arxiv` channel is intentional; duplicate arXiv fetches are acceptable because reranking dedupes by URL later.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
