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

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"web-ddgs"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, and date fields

The `source` field must be exactly `"web-ddgs"` for this platform.
`judge.py` uses `source` for diversity scoring, so inconsistent tags directly hurt the diversity dimension.

After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Standardize the date metadata expectations above by extracting dates from platform-specific fields and writing them to `metadata`:

- `metadata.published_at`: when the content was created, in ISO 8601
- `metadata.updated_at`: when the content was last modified, in ISO 8601
- `metadata.created_utc`: creation timestamp, in ISO 8601

See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.
