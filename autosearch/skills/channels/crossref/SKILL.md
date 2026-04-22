# Skill Attribution
> Source: self-written for task Plan-0420 W7 F701 + F702.

---
name: crossref
description: Cross-publisher scholarly search via the Crossref DOI registry, useful for journal articles, book chapters, and citation-linked research metadata.
version: 1
languages: [en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en]
  query_types: [academic, doi-lookup, citation, scholarly, journal-article]
  avoid_for: [social, multimedia, real-time]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [academic]
scenarios: [doi-lookup, publication-metadata]
model_tier: Fast
experience_digest: experience.md
---

## Overview

`crossref` is the broad DOI-registry channel for scholarly metadata across many publishers, journals, books, and proceedings. It complements specialized paper indexes by widening recall when the user asks for citation-oriented or publisher-agnostic academic coverage.

## When To Choose It

- Choose it for English scholarly search, DOI-oriented lookup, journal article discovery, and citation-heavy queries.
- Choose it when a cross-publisher registry is more useful than a discipline-specific bibliography.
- Avoid it for social content, multimedia search, or real-time discussion.

## How To Search

- `api_search` queries the Crossref works API by title and normalizes title, author, venue, year, abstract, and DOI URL fields.
- When abstracts are missing, snippets are synthesized from authors, container title, year, type, and citation count.

## Known Quirks

- Abstracts may arrive as JATS-like tagged strings and need lightweight tag stripping.
- Metadata quality varies by publisher, so author and date completeness can differ between records.
- Crossref is broad rather than domain-specific, so relevance can be noisier than a focused academic index.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
