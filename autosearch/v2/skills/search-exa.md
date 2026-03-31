---
name: search-exa
description: "Use when the task needs high-quality semantic web search, strong paraphrase matching, or premium search precision across the open web through Exa."
---

# Platform

Exa semantic search API, accessed through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- semantic matches that keyword search may miss
- premium web search quality
- better first-pass precision on research-heavy tasks
- site-filtered semantic search across chosen domains

Use this when retrieval quality matters enough to justify API spend.

# API Surface

This restores the V1 Exa connector through the local `mcporter` interface.

Treat Exa as semantic web retrieval with result fields such as:

- title
- URL
- snippet or summary
- domain
- optional metadata depending on the endpoint

# What It Is Good For

Exa is best for:

- semantically phrased search over the web
- hard recall problems where keywords are brittle
- premium-quality discovery when free platforms are noisy
- filtered search across specific sites or source classes

It is especially useful when the user's concept can be phrased many ways across the wild web.

# Quality Signals

Prioritize results with:

- high semantic fit to the user intent
- trustworthy domains
- titles and snippets that mention the target mechanism, not just a loose keyword
- source diversity across different sites

Down-rank results when:

- many results are semantic cousins but not task-relevant
- domain trust is weak
- the result repeats evidence already found on free sources

# Known V1 Patterns

Patterns already validated in state:

- Exa outperformed GitHub issue search on at least one issue-discovery task, finding strong matches where `gh search issues` found none.

Take that seriously for semantically indirect search problems.
If keyword search keeps missing likely evidence, route to Exa early.

# Rate Limits And Requirements

Requirements:

- `EXA_API_KEY`
- `mcporter` available in the environment

This is a paid API.
Budget usage should be intentional, especially when many follow-up queries are possible.
Prefer compact, high-information queries over brute-force paraphrase sweeps.

# Output Expectations

Return web-result evidence.
Each result should normally preserve:

- title
- URL
- snippet
- domain
- short semantic-fit note

Expect Exa to contribute fewer but cleaner candidates than broad free search layers.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"exa"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, and date fields

The `source` field must be exactly `"exa"` for this platform.
`judge.py` uses `source` for diversity scoring, so inconsistent tags hurt the diversity dimension.

After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write them to `metadata`:

- `metadata.published_at`: when the content was created (ISO 8601)
- `metadata.updated_at`: when the content was last modified (ISO 8601)
- `metadata.created_utc`: creation timestamp (ISO 8601)

See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.
