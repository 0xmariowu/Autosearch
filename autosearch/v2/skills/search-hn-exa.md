---
name: search-hn-exa
description: "Use when the task needs semantic retrieval of Hacker News discussions through Exa with `site:news.ycombinator.com`, especially for product or launch discovery with varied phrasing."
---

# Platform

Exa semantic search with a `site:news.ycombinator.com` filter, accessed through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- HN threads that keyword HN search is likely to miss
- semantic recall around launches, products, or companies
- premium discovery over HN discussion pages

Use this when Algolia keyword search is too literal or when you only know a concept family, not the exact post wording.

# API Surface

This restores the V1-style premium HN connector by constraining Exa to HN pages.

Treat it as HN-thread retrieval with Exa semantics.
Expected fields are web-like:

- title
- URL
- snippet
- domain

HN-native points and comment counts may require enrichment from HN data afterward.

# What It Is Good For

This platform is best for:

- semantically related HN discussions
- launch and trend discovery
- premium recall for startup or tooling research

It is often a good escalation path when you suspect HN has relevant discussion but the exact title wording is unknown.

# Quality Signals

Prioritize results with:

- clear product or company names in the title
- snippets indicating launch, discussion, or technical adoption
- recent threads when the topic is fast-moving
- high engagement after enrichment

Down-rank results when:

- the result is semantically related but not actually about the target product or mechanism
- the page is a low-signal thread with minimal discussion

# Known V1 Patterns

Carry forward HN-specific V1 lessons:

- exact product names still matter a lot
- abstract conceptual wording performs poorly
- Show HN threads need community validation, not just existence

Exa improves semantic reach, but HN remains a named-entity-heavy platform.

# Rate Limits And Requirements

Requirements:

- `EXA_API_KEY`
- `mcporter` available

This is a paid API route.
Use it when the expected gain from semantic HN recall outweighs the cost.

# Output Expectations

Return HN-thread candidates with web-style fields:

- title
- HN URL
- snippet
- short note on why the thread fits

Expect better discovery than keyword-only HN search on fuzzy or indirect phrasings, with engagement metadata added later if needed.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- url: canonical URL
- title: result title
- snippet: description or summary
- source: "hn"
- query: the query that found this
- metadata: object with llm_relevant, llm_reason, date fields

The source field must be exactly "hn" for this platform.
judge.py uses source for diversity scoring - inconsistent tags hurt the diversity dimension.

After collecting results, pass them to normalize-results.md for cross-platform dedup and extract-dates.md for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to metadata:

- metadata.published_at - when the content was created (ISO 8601)
- metadata.updated_at - when the content was last modified (ISO 8601)
- metadata.created_utc - creation timestamp (ISO 8601)

See extract-dates.md for the full extraction priority and format rules.
Missing dates score as zero freshness in judge.py.
