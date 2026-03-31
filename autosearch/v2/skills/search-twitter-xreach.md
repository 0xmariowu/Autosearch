---
name: search-twitter-xreach
description: "Use when the task explicitly needs the direct XReach Twitter/X connector through mcporter, but treat it as a fragile source and validate its health before trusting it."
---

# Platform

XReach API through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this only when you specifically want:

- direct Twitter/X search from the native connector path
- native social retrieval behavior rather than web-indexed Twitter pages

This should not be the default Twitter/X route.
Use it as a probe or fallback only if direct X-specific retrieval is required.

# API Surface

This restores the V1 XReach connector through `mcporter`.

Treat it as native Twitter/X retrieval when healthy.
Expected result shapes may include:

- tweet or post URL
- account identity
- text snippet
- created time
- engagement metadata if the connector provides it

# What It Is Good For

In principle, XReach is good for:

- direct Twitter/X search
- account-level or post-level discovery
- engagement-aware social signal

In practice, V1 evidence says reliability was poor.

# Quality Signals

If the connector is healthy, prioritize results with:

- clear relevance in the text
- recognizable accounts
- recency when the topic is time-sensitive
- engagement metrics when available

Down-rank or reject runs when:

- the connector returns empty results across varied reasonable queries
- results are malformed
- retrieval quality is obviously below the Exa `site:twitter.com` path

# Known V1 Patterns

Pattern already validated in state:

- XReach returned empty results for all tested query types in V1.
- The saved recommendation was to prefer Exa with `site:twitter.com`.

That means this connector starts in a skeptical posture.
Check provider health and be ready to abandon it quickly.

# Rate Limits And Requirements

Requirements:

- `XREACH_API_KEY`
- `mcporter` available

This is a paid API route.
Because reliability is uncertain, keep probing lightweight and do not spend heavily before the connector proves healthy in the current session.

# Output Expectations

Return native social evidence only if the connector is producing real results.
Each result should normally preserve:

- URL
- account
- text snippet
- created time
- engagement if available
- short relevance note

If the connector is empty or unstable, treat that as provider-health evidence and route Twitter/X discovery to `search-twitter-exa.md` instead.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- url: canonical URL
- title: result title
- snippet: description or summary
- source: "twitter"
- query: the query that found this
- metadata: object with llm_relevant, llm_reason, date fields

The source field must be exactly "twitter" for this platform.
`judge.py` uses `source` for diversity scoring, so inconsistent tags reduce the diversity dimension.

After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write them to `metadata`:

- `metadata.published_at`: when the content was created (ISO 8601)
- `metadata.updated_at`: when the content was last modified (ISO 8601)
- `metadata.created_utc`: creation timestamp (ISO 8601)

For XReach, map native created-time fields into these canonical keys when available.
See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.
