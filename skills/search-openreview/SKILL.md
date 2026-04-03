---
name: search-openreview
description: "Use when you need to find papers accepted at top ML conferences like ICLR, NeurIPS, or ICML for a specific year and topic."
---

# Platform

OpenReview API (free, no key required).
This is a specialized platform skill for conference paper discovery.

# When To Choose It

Choose this when:

- you need accepted papers from a specific conference and year
- systematic-recall.md identified a GAP in recent conference papers
- you want to verify whether a paper was accepted at a specific venue
- you want to find all papers on a topic from a recent top conference

# API Surface

OpenReview API v2: `https://api2.openreview.net/`

Key endpoints:
- `GET /notes/search?query={topic}&venue={venue_id}` → search papers by topic within a venue
- Venue IDs: `ICLR.cc/2026/Conference`, `NeurIPS.cc/2025/Conference`, `ICML.cc/2025/Conference`

Alternative: web search with `site:openreview.net {topic} {conference} {year}`

# Conference Calendar

For reference when choosing which venues to search:

- ICLR: usually May (submission Sep-Oct previous year)
- ICML: usually July (submission Jan-Feb)
- NeurIPS: usually December (submission May-Jun)
- ACL/EMNLP: varies, usually mid-year
- AAAI: usually February

# Strategy

1. Identify which conferences are relevant to the topic
2. Search the most recent 2-3 years
3. Filter by topic relevance
4. Add accepted papers that web search and arXiv search missed

# Standard Output Schema

- `url`: openreview paper URL
- `title`: paper title
- `snippet`: abstract excerpt
- `source`: `"openreview"`
- `query`: topic + venue
- `metadata.published_at`: conference date

# Quality Bar

This skill finds officially accepted papers that arXiv-only search misses — especially papers with different arXiv titles or papers not on arXiv at all.
