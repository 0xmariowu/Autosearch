---
name: search-ddgs
description: "Use when the task needs broad web coverage from a free search layer across articles, blogs, docs, and product pages via the DDGS Python package."
---

# Platform

DuckDuckGo search through the `ddgs` Python package.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- broad web coverage beyond code hosts and forums
- articles, blogs, launch pages, documentation, and independent writeups
- a low-cost general web source to widen diversity

This platform is useful when you want non-GitHub evidence without paying for a search API.

# API Surface

This restores the V1 DDGS connector.
The retrieval layer is the Python `ddgs` package rather than a paid web-search API.

Treat it as a general web search source with results such as:

- title
- URL
- snippet
- domain

# What It Is Good For

DDGS is best for:

- broad discovery
- blog and article collection
- official product pages
- documentation and tutorial surfaces

It is weaker than semantic APIs on hard paraphrase matching, but it is very useful for source diversity at zero API cost.

# Quality Signals

Prioritize results with:

- strong domain authority for the task
- titles that closely match the query intent
- snippets that contain the target entities or constraints
- domains that add a new source class rather than duplicating what GitHub or Reddit already supplied

Down-rank results when:

- the domain is low-trust or SEO-heavy
- the title is only a loose keyword overlap
- multiple results collapse to the same site without adding new information

# Known V1 Patterns

Patterns already validated in state:

- DDGS works reliably when run under Python 3.11.
- Adding a year qualifier such as `2025` can materially improve freshness.

Use DDGS to widen coverage, then use query qualifiers when stale content starts to dominate.

# Rate Limits And Requirements

Requirements:

- Python 3.11 or newer for the SSL path used in V1
- `ddgs` package installed in the active runtime

There is no paid API key requirement, but practical rate limits still exist because this depends on upstream search behavior.
Be conservative with request volume and avoid bursty repetition.

# Output Expectations

Return web-result evidence.
Each result should normally preserve:

- title
- URL
- snippet
- domain
- short relevance note

Write date metadata when available.
Extract publication dates from snippets, titles, or page metadata and write them to `metadata.published_at` in ISO 8601 format.
If no date is available, omit the field rather than guessing.
The judge uses `published_at`, `created_utc`, and `updated_at` for freshness scoring.
Missing dates hurt the freshness dimension directly.

Expect this platform to contribute breadth and source diversity more than deep platform-native metadata.
