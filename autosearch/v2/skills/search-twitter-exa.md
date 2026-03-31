---
name: search-twitter-exa
description: "Use when the task needs semantic discovery of Twitter/X pages through Exa with `site:twitter.com`, especially for social signal, topical chatter, and workaround for weak native Twitter search."
---

# Platform

Exa semantic search with a `site:twitter.com` filter, accessed through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- social signal around products, launches, or trends
- Twitter/X discovery without relying on the native search API
- semantic recovery of tweets, profiles, or thread pages

Use this when Twitter matters as a signal source but the direct connector is unreliable.

# API Surface

This restores the premium Twitter/X semantic connector using Exa rather than a native X API.

Treat it as web retrieval over Twitter pages.
Expected fields are web-style:

- title
- URL
- snippet
- domain

Native engagement metrics may not always be present and may require separate enrichment if critical.

# What It Is Good For

This platform is best for:

- trend and chatter detection
- discovering relevant accounts or tweet threads
- recovering social discussion when the direct search surface is unstable

It is weaker than a strong native social API for exact engagement stats, but stronger than a broken native connector.

# Quality Signals

Prioritize results with:

- clear account or product name matches
- snippets indicating discussion, launch, or comparison relevance
- recency when the topic is news-like
- recognizable accounts or organizations

Down-rank results when:

- the result is a weak semantic neighbor
- the page has low credibility or unclear context
- engagement cannot be inferred and the content is thin

# Known V1 Patterns

Patterns already validated in state:

- Native Twitter/X search via XReach was unreliable in V1 and often returned empty results.
- The saved recommendation was to use Exa with `site:twitter.com` instead.

Treat this platform as the preferred Twitter/X search path unless direct native retrieval becomes healthy again.

# Rate Limits And Requirements

Requirements:

- `EXA_API_KEY`
- `mcporter` available

This is a paid API route.
Use it when social discovery is important enough to justify spend.

# Output Expectations

Return Twitter/X page candidates with web-style fields:

- title
- Twitter/X URL
- snippet
- probable account or topic note
- short relevance summary

Expect useful social coverage, with exact engagement enrichment added later only if the task truly needs it.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"twitter"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, date fields

The `source` field must be exactly `"twitter"` for this platform.
`judge.py` uses `source` for diversity scoring - inconsistent tags hurt the diversity dimension.

After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to `metadata`:

- `metadata.published_at` - when the content was created (ISO 8601)
- `metadata.updated_at` - when the content was last modified (ISO 8601)
- `metadata.created_utc` - creation timestamp (ISO 8601)

See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.
