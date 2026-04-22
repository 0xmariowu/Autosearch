# Skill Attribution
> Source: self-written for task Plan-0420 W7 F701 + F702.

---
name: dblp
description: Computer science bibliography search — technical papers, proceedings, and journal articles indexed by venue, author, and year.
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
  query_types: [academic, computer-science, research, technical-paper]
  avoid_for: [social, multimedia, real-time]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [academic]
scenarios: [computer-science, author-bibliography]
model_tier: Fast
experience_digest: experience.md
---

## Overview

`dblp` is the focused bibliography channel for computer science papers, conference proceedings, and journal articles. It is useful when the query is clearly CS-oriented and benefits from venue, author, and year metadata even when abstracts are unavailable.

## When To Choose It

- Choose it for English CS paper discovery, author lookup, venue lookup, and bibliography-style queries.
- Choose it when the planner wants broader CS venue coverage than a single preprint index.
- Avoid it for social discussion, multimedia content, or breaking news.

## How To Search

- `api_search` queries the DBLP publication API and normalizes hits into evidence with external links when available.
- Result snippets are synthesized from authors, venue, year, and record type because DBLP does not provide abstracts.

## Known Quirks

- Titles may end with a trailing period in the raw API payload and should be normalized.
- Some hits only expose a DBLP record page while others provide an external DOI landing page.
- Coverage is strongest for computer science and adjacent technical literature, not general scholarly search.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
