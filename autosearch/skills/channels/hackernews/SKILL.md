# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: hackernews
description: Use for real-time developer discussion, tooling opinions, and early-stage product signals from the HN community.
version: 1
languages: [en]
methods:
  - id: algolia_search
    impl: methods/algolia.py
    requires: []
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [algolia_search]
when_to_use:
  query_languages: [en]
  query_types: [tech-opinion, tooling, startup, product-launch, hacker-culture]
  avoid_for: [academic, chinese-query]
quality_hint:
  typical_yield: medium-high
  chinese_native: false
---

## Overview

Hacker News is a strong source for English-language developer reactions to tools, startups, launches, and technical blog posts. It is especially useful when the user wants candid operator sentiment, early adoption signals, or discussion around a new product in the developer ecosystem.

For autosearch coverage, this channel adds community judgment that is often missing from official docs or vendor pages. It matters because HN can surface quality critiques, deployment pain points, and adoption signals earlier than more polished media sources.

## When to Choose It

- Choose it for English queries about developer opinion on a tool, launch, or startup.
- Choose it when comment quality and community debate matter more than formal documentation.
- Choose it for "what do engineers think of this" style prompts.
- Prefer it for early-stage product signals before broader media coverage stabilizes.
- Avoid it for academic paper retrieval or Chinese-language discourse.

## How To Search (Planned)

- `algolia_search` - Query the Algolia-backed HN search API for stories and comments matching the query, then rank by recency and discussion value.
- `algolia_search` - Capture story title, points, comment count, author, created time, and the HN thread URL.
- `algolia_search` - Support both top-level launch discovery and comment-level opinion lookup for tooling and startup queries.

## Known Quirks

- The Algolia index is convenient and fast, but ranking can drift toward viral threads instead of the most technically useful ones.
- HN is English-first and culturally specific, so it should not be treated as representative public sentiment.
- Comment quality varies sharply by thread age and topic.
- Some external links disappear or change after posting, leaving the HN thread as the durable evidence source.
