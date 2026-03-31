---
name: search-author-track
description: "Use when you know a key researcher and want to discover their full body of work, especially recent papers not yet well-known."
---

# Platform

Semantic Scholar Author API (free).
This is a specialized platform skill for researcher-centric discovery.

# When To Choose It

Choose this when:

- systematic-recall.md identified key researchers in the field
- you want to find a researcher's latest unpublished or less-cited work
- you want to map the research output of a lab or group
- a paper's author list suggests other relevant work

# API Surface

- `GET /author/search?query={name}` → find author ID
- `GET /author/{author_id}/papers` → all papers by this author

Base URL: `https://api.semanticscholar.org/graph/v1/`

# Strategy

1. From systematic-recall.md, collect researcher names tagged in dimension 2 (Key People)
2. For each researcher, search their name on Semantic Scholar
3. Get their paper list, sorted by recency
4. Filter for papers relevant to the current topic
5. Add undiscovered papers to the evidence bundle

This is high-yield because prolific researchers often have recent work that search engines have not indexed well yet.

# Standard Output Schema

- `url`: paper URL
- `title`: paper title
- `snippet`: abstract excerpt
- `source`: `"semantic-scholar"`
- `query`: author name
- `metadata.published_at`, `metadata.citations`

# Date Metadata

Extract `year` from API response → write to `metadata.published_at` as `{year}-01-01T00:00:00Z`.

# Quality Bar

This skill discovers papers that topic-based search misses by following the researcher rather than the keyword.
